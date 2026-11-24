"""Outputs of pipeline.tram_stretches: tables, layer, rankings, sensitivity, rounding and separation checks.

Files
* results/tables/tram_stretches.csv          one row per stretch direction: ids, names, stop sequence, lines, length,
                                             OSM attributes, per-band speed / scheduled time / slack / trips
* results/tables/tram_stretch_bands.csv      long form (stretch direction x day x band) for scenarios
* results/tables/tram_stretch_stop_pairs.csv GTFS stop pair -> stretch direction and edge index (scenario mapping)
* results/tables/tram_stretch_stops.csv      stop places of each stretch direction in order, with member stop ids
* results/layers/tram_stretches.parquet      the same rows as tram_stretches.csv with line geometry (EPSG:4326)
* results/qa/speed/stretches/*.csv           rankings, sensitivity, rounding check, separation spot-check, diagnostics
"""
from __future__ import annotations

import shutil
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from pipeline import speed_core as sc
from pipeline import tram_stretches as T
from pipeline.common import RESULTS, sig, write_meta

TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
DAYCODE = {"weekday": "wd", "saturday": "sat"}
LF = chr(10)


def _fmt(df: pd.DataFrame) -> pd.DataFrame:
    o = df.copy()
    for c in o.columns:
        if o[c].dtype.kind == "f":
            o[c] = o[c].map(sig)
    return o


def below_min(S: pd.DataFrame, M: pd.DataFrame) -> pd.Series:
    a = M[(M["band"] == "all_day")].sort_values(["sd", "day_type"], ascending=[True, False], kind="stable")
    a = a.drop_duplicates("sd").set_index("sd")       # weekday when it runs on Wednesday, else Saturday
    t = S["stretch_dir_id"].map(a["sched_min"])
    return (t < T.MIN_MIN) | (S["n_hops"] < T.MIN_HOPS) | t.isna()


def wide(S: pd.DataFrame, M: pd.DataFrame) -> pd.DataFrame:
    out = S.drop(columns=["edge_lengths_m", "_curves"]).copy()
    out["below_min"] = below_min(S, M).to_numpy()
    fm = M.drop_duplicates("sd").set_index("sd")["free_min"]
    out["free_running_min"] = out["stretch_dir_id"].map(fm)
    wd = M[(M["day_type"] == "weekday") & (M["band"] == "all_day")].set_index("sd")
    out["lines_weekday"] = out["stretch_dir_id"].map(wd["lines"])
    out["vehicle_km_weekday"] = out["stretch_dir_id"].map(wd["len_sum"] / 1000)
    for dt in sc.days():
        for b in sc.band_ids(dt) + ["all_day"]:
            m = M[(M["day_type"] == dt) & (M["band"] == b)].set_index("sd")
            p = f"{DAYCODE[dt]}_{b}"
            out[f"speed_kmh_{p}"] = out["stretch_dir_id"].map(m["speed_kmh"])
            out[f"sched_min_{p}"] = out["stretch_dir_id"].map(m["sched_min"])
            out[f"slack_min_{p}"] = out["stretch_dir_id"].map(m["slack_min"])
            out[f"slack_min_per_km_{p}"] = out["stretch_dir_id"].map(m["slack_min_per_km"])
            out[f"trips_{p}"] = out["stretch_dir_id"].map(m["n_trips"]).astype("Int64")
            if b != "all_day":
                out[f"tph_{p}"] = out[f"trips_{p}"].astype(float) / (sc.band_minutes(dt, b) / 60)
    am = M[(M["day_type"] == "weekday") & (M["band"] == "am_peak")].set_index("sd")
    sl = out["stretch_dir_id"].map(am["slack_min"])
    nrc = pd.to_numeric(out["n_road_crossings"], errors="coerce")
    out["slack_s_per_road_crossing_wd_am_peak"] = sl * 60 / nrc.where(nrc > 0)
    return out.sort_values(["agglomeration", "stretch_id", "dir"], kind="stable").reset_index(drop=True)


def ranking(W: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for agg, g in W.groupby("agglomeration", sort=True):
        ok = g[~g["below_min"] & (g["trips_wd_am_peak"].fillna(0) >= T.RANK_MIN_TRIPS)]
        for kind, col, asc in (("najniższa prędkość", "speed_kmh_wd_am_peak", True),
                               ("największy zapas na km", "slack_min_per_km_wd_am_peak", False)):
            r = ok.sort_values([col, "stretch_dir_id"], ascending=[asc, True], kind="stable").head(10)
            for i, x in enumerate(r.itertuples(index=False), start=1):
                rows.append({"agglomeration": agg, "ranking": kind, "rank": i, "stretch_dir_id": x.stretch_dir_id,
                             "name": x.name, "lines": x.lines_weekday, "length_m": x.length_m, "n_stops": x.n_stops,
                             "speed_kmh_am_peak": x.speed_kmh_wd_am_peak, "speed_kmh_evening": x.speed_kmh_wd_evening,
                             "sched_min_am_peak": x.sched_min_wd_am_peak, "free_running_min": x.free_running_min,
                             "slack_min_am_peak": x.slack_min_wd_am_peak, "slack_min_per_km_am_peak": x.slack_min_per_km_wd_am_peak,
                             "trips_am_peak": x.trips_wd_am_peak, "share_street": x.share_street,
                             "share_pedestrian": x.share_pedestrian, "share_separated": x.share_separated,
                             "n_road_crossings": x.n_road_crossings, "n_signalised": x.n_signalised,
                             "n_ped_standalone": x.n_ped_standalone, "n_switches": x.n_switches,
                             "n_curves_r50": x.n_curves_r50, "osm_match_share": x.osm_match_share,
                             "stop_sequence": x.stop_sequence})
    return pd.DataFrame(rows)


def city_slow_share(W: pd.DataFrame, M: pd.DataFrame, thresholds=(12.0, T.SLOW_KMH, 18.0)) -> pd.DataFrame:
    rows = []
    bm = W.set_index("stretch_dir_id")["below_min"]
    for (agg, dt, band), g in M.assign(agg=M["sd"].str[:3]).groupby(["agg", "day_type", "band"], sort=True):
        g = g.assign(bm=g["sd"].map(bm).fillna(True))
        ok = g[~g["bm"]]
        tot = ok["len_sum"].sum()
        r = {"city_code": agg, "day_type": dt, "band": band, "vehicle_km": float(g["len_sum"].sum() / 1000),
             "share_vkm_below_min_stretches": float(g.loc[g["bm"], "len_sum"].sum() / g["len_sum"].sum()),
             "speed_kmh_all_stretches": float(g["len_sum"].sum() / g["t_sum"].sum() * 3.6)}
        for th in thresholds:
            r[f"share_vkm_below_{int(th)}kmh"] = float(ok.loc[ok["speed_kmh"] < th, "len_sum"].sum() / tot) if tot else None
        # slack share: traversal-equivalents x slack over traversal-equivalents x scheduled time
        te = ok["len_sum"] / ok["length_m"]
        r["slack_share_of_scheduled_time"] = float((te * ok["slack_min"]).sum() / (te * ok["sched_min"]).sum())
        rows.append(r)
    out = pd.DataFrame(rows)
    inv = {v: k for k, v in T.CITY_CODE.items()}
    out.insert(0, "agglomeration", out["city_code"].map(inv))
    return out.drop(columns="city_code")


def sensitivity(S: pd.DataFrame, ST: pd.DataFrame, W: pd.DataFrame) -> pd.DataFrame:
    rows = []
    bm = W.set_index("stretch_dir_id")["below_min"]
    base = None
    for name, ch in T.SENS:
        p = {**T.KIN, **ch}
        M = T.stretch_metrics(S, ST, p)
        am = M[(M["day_type"] == "weekday") & (M["band"] == "am_peak")].copy()
        am = am[~am["sd"].map(bm).fillna(True)]
        am["agg"] = am["sd"].str[:3]
        if base is None:
            base = am.set_index("sd")["slack_min_per_km"]
        for agg, g in am.groupby("agg", sort=True):
            te = g["len_sum"] / g["length_m"]
            b = base.reindex(g["sd"]).to_numpy()
            rk = pd.Series(g["slack_min_per_km"].to_numpy()).rank().corr(pd.Series(b).rank())
            top_main = set(g.assign(b=b).sort_values(["b", "sd"], ascending=[False, True]).head(10)["sd"])
            top_now = set(g.sort_values(["slack_min_per_km", "sd"], ascending=[False, True]).head(10)["sd"])
            rows.append({"variant": name, "city_code": agg,
                         "slack_share_of_scheduled_time": float((te * g["slack_min"]).sum() / (te * g["sched_min"]).sum()),
                         "median_slack_min_per_km": float(g["slack_min_per_km"].median()),
                         "share_stretches_negative_slack": float((g["slack_min"] < 0).mean()),
                         "rank_corr_with_main": float(rk), "top10_overlap_with_main": len(top_main & top_now)})
    out = pd.DataFrame(rows)
    inv = {v: k for k, v in T.CITY_CODE.items()}
    out.insert(0, "agglomeration", out["city_code"].map(inv))
    return out.drop(columns="city_code")


def rounding_check(per_city: dict, W: pd.DataFrame) -> pd.DataFrame:
    """Line-to-line spread of the scheduled time on the same stretch direction (Wednesday 09-15): if timetables were
    exact, lines sharing track at the same hour would mostly agree; the spread bounds the rounding noise."""
    rows = []
    L = W.set_index("stretch_dir_id")["length_m"]
    nh = W.set_index("stretch_dir_id")["n_hops"]
    for agg, R in per_city.items():
        h = R["H"]["weekday"].dropna(subset=["sid"])
        h = h[h["band"] == "midday"]
        h = h.assign(sd=h["sid"] + "-" + h["sdir"])
        # only trips that run the whole stretch
        cov = h.groupby(["sd", "uid"]).agg(n=("eidx", "nunique"), t=("t_s", "sum"))
        cov = cov.reset_index()
        cov = cov[cov["n"] == cov["sd"].map(nh)]
        cov = cov.merge(h.drop_duplicates("uid")[["uid", "line"]], on="uid")
        per_line = cov.groupby(["sd", "line"])["t"].mean().reset_index()
        for sd, g in per_line.groupby("sd"):
            if len(g) < 2:
                continue
            t = g["t"].to_numpy() / 60
            rows.append({"agglomeration": agg, "stretch_dir_id": sd, "n_lines": len(g), "mean_min": float(t.mean()),
                         "sd_min": float(t.std(ddof=1)), "range_min": float(t.max() - t.min()), "length_m": float(L.get(sd, np.nan))})
    d = pd.DataFrame(rows)
    d["bin"] = pd.cut(d["mean_min"], [0, 3, 5, 8, 12, 100], right=False,
                      labels=["< 3 min", "3-5 min", "5-8 min", "8-12 min", ">= 12 min"]).astype(str)
    s = d.groupby("bin").agg(stretch_directions=("sd_min", "size"), median_sd_min=("sd_min", "median"),
                             median_rel_sd=("sd_min", lambda x: float((x / d.loc[x.index, "mean_min"]).median())),
                             median_range_min=("range_min", "median"),
                             share_with_line_difference=("range_min", lambda x: float((x > 0).mean())),
                             mean_range_min=("range_min", "mean")).reset_index()
    s["_o"] = s["bin"].map({b: i for i, b in enumerate(["< 3 min", "3-5 min", "5-8 min", "8-12 min", ">= 12 min"])})
    s = s.sort_values("_o").drop(columns="_o")
    return d, s


def separation_probe(per_city: dict, W: pd.DataFrame) -> pd.DataFrame:
    """For each stretch direction: the most common named road within 30 m of the track, its highway class, tags and
    median distance, and the inferred shares; used for the manual spot-check in speed.md."""
    rows = []
    for agg, R in per_city.items():
        O = R["O"]
        S = R["S"].set_index("stretch_dir_id")
        for sd, geom in zip(R["S"]["stretch_dir_id"], R["geoms"]):
            pts, _ = T._resample(geom, 20.0)
            pg = shapely.points(pts)
            ip, ir = O["road_tree"].query_nearest(pg, max_distance=30.0, return_distance=False, all_matches=False)
            if len(ip) == 0:
                rows.append({"agglomeration": agg, "stretch_dir_id": sd, "road": None})
                continue
            w = O["road_way_of_seg"][ir]
            dd = shapely.distance(pg[ip], O["road_geom"][ir])
            nm = pd.Series(O["road_names"][w]).fillna("(bez nazwy)")
            top = nm.value_counts().sort_index().sort_values(ascending=False, kind="stable").index[0]
            m = (nm == top).to_numpy()
            rows.append({"agglomeration": agg, "stretch_dir_id": sd, "name": S.loc[sd, "name"], "road": top,
                         "road_highway": pd.Series(O["road_hw"][w][m]).value_counts().index[0],
                         "road_oneway_share": float(O["road_oneway"][w][m].mean()),
                         "road_embedded_rails_share": float(O["road_emb"][w][m].mean()),
                         "median_dist_track_to_road_axis_m": float(np.median(dd[m])),
                         "share_points_with_road_within_30m": float(len(ip) / len(pg)),
                         "share_street": S.loc[sd, "share_street"], "share_pedestrian": S.loc[sd, "share_pedestrian"],
                         "share_separated": S.loc[sd, "share_separated"]})
    return pd.DataFrame(rows)


def layer(W: pd.DataFrame, geoms: list, S: pd.DataFrame) -> gpd.GeoDataFrame:
    gi = dict(zip(S["stretch_dir_id"], geoms))
    lines = []
    for sd in W["stretch_dir_id"]:
        c = gi[sd]
        lo, la = TO4326.transform(c[:, 0], c[:, 1])
        xy = np.round(np.c_[lo, la], 6)
        keep = np.r_[True, (np.diff(xy, axis=0) != 0).any(axis=1)]
        xy = xy[keep]
        if len(xy) < 2:
            xy = np.vstack([xy, xy])
        lines.append(shapely.linestrings(xy))
    g = gpd.GeoDataFrame(W.copy(), geometry=lines, crs="EPSG:4326")
    for c in g.columns:
        if g[c].dtype.kind == "f":
            g[c] = g[c].map(sig).astype(float)
    return g


def write_all(S, M, ST, geoms, pairs, diag, per_city, t0) -> dict:
    QA, TB, LY = T.QA, T.TABLES, T.LAYERS
    for d in (QA, TB, LY):
        d.mkdir(parents=True, exist_ok=True)
    W = wide(S, M)
    _fmt(W).to_csv(TB / "tram_stretches.csv", index=False, lineterminator="\n")
    lay = layer(W, geoms, S)
    lay.to_parquet(LY / "tram_stretches.parquet", index=False)
    # long form
    bm = W.set_index("stretch_dir_id")["below_min"]
    lg = M.rename(columns={"sd": "stretch_dir_id", "n_hops": "hop_traversals"}).copy()
    lg["below_min"] = lg["stretch_dir_id"].map(bm)
    lg["timetable_date"] = lg["day_type"].map(sc.days())
    lg = lg[["stretch_dir_id", "day_type", "timetable_date", "band", "length_m", "speed_kmh", "sched_min", "free_min",
             "slack_min", "slack_min_per_km", "hop_traversals", "n_trips", "len_sum", "t_sum", "lines", "below_min"]]
    order = {b: i for i, b in enumerate(["night", "early", "am_peak", "midday", "pm_peak", "early_eve", "evening",
                                         "morning", "day", "all_day"])}
    lg = lg.assign(_o=lg["band"].map(order)).sort_values(["stretch_dir_id", "day_type", "_o"], kind="stable").drop(columns="_o")
    lg = lg.rename(columns={"len_sum": "sum_hop_length_m", "t_sum": "sum_hop_time_s"})
    _fmt(lg).to_csv(TB / "tram_stretch_bands.csv", index=False, lineterminator="\n")
    # stop pairs and stop places
    pr = pairs.copy()
    pr["feed"] = pr["from_suid"].str.split(":").str[0]
    pr["from_stop_id"] = pr["from_suid"].str.split(":", n=1).str[1]
    pr["to_stop_id"] = pr["to_suid"].str.split(":", n=1).str[1]
    pr["stretch_dir_id"] = pr["sid"] + "-" + pr["sdir"]
    pr = pr.rename(columns={"sid": "stretch_id", "sdir": "dir", "eidx": "edge_index"})
    pr = pr[["agglomeration", "feed", "from_stop_id", "to_stop_id", "stretch_id", "dir", "stretch_dir_id", "edge_index",
             "trips_weekday"]].sort_values(["agglomeration", "stretch_dir_id", "edge_index", "from_stop_id", "to_stop_id"], kind="stable")
    pr.to_csv(TB / "tram_stretch_stop_pairs.csv", index=False, lineterminator="\n")
    srows = []
    for agg, R in per_city.items():
        pl = R["places"]
        mem = pl.groupby("place_key")["suid"].agg(lambda v: " ".join(sorted(x.split(":", 1)[1] for x in v)))
        pn = pl.drop_duplicates("place_key").set_index("place_key")["place_name"]
        for r in R["S"].itertuples(index=False):
            for i, pk in enumerate(r.place_keys.split(" > ")):
                srows.append({"agglomeration": agg, "stretch_dir_id": r.stretch_dir_id, "position": i, "place_key": pk,
                              "place_name": pn[pk], "stop_ids": mem[pk]})
    pd.DataFrame(srows).sort_values(["agglomeration", "stretch_dir_id", "position"], kind="stable").to_csv(
        TB / "tram_stretch_stops.csv", index=False, lineterminator="\n")
    # QA
    rk = ranking(W)
    _fmt(rk).to_csv(QA / "ranking_am_peak.csv", index=False, lineterminator="\n")
    sh = city_slow_share(W, M)
    _fmt(sh).to_csv(QA / "city_stretch_summary.csv", index=False, lineterminator="\n")
    sens = sensitivity(S, ST, W)
    _fmt(sens).to_csv(QA / "sensitivity_kinematics.csv", index=False, lineterminator="\n")
    rd, rs = rounding_check(per_city, W)
    _fmt(rd.sort_values(["agglomeration", "stretch_dir_id"])).to_csv(QA / "stretch_rounding_check.csv", index=False, lineterminator="\n")
    _fmt(rs).to_csv(QA / "stretch_rounding_summary.csv", index=False, lineterminator="\n")
    sp = separation_probe(per_city, W)
    _fmt(sp.sort_values(["agglomeration", "stretch_dir_id"])).to_csv(QA / "separation_probe.csv", index=False, lineterminator="\n")
    _fmt(diag).to_csv(QA / "stretch_diagnostics.csv", index=False, lineterminator="\n")
    sizes = {p: round((d / p).stat().st_size / 1e6, 2) for d, p in
             ((TB, "tram_stretches.csv"), (TB, "tram_stretch_bands.csv"), (TB, "tram_stretch_stop_pairs.csv"),
              (TB, "tram_stretch_stops.csv"), (LY, "tram_stretches.parquet"))}
    from pipeline import gtfs_service as gs
    inputs = sorted({f"gtfs_{f}" for _, f, _ in T.CITIES} | {"osm_poland_pbf"})
    extra = {"timetable_dates": sc.days(), "osm_date": "2026-11-22", "code_version": T.CODE_VERSION,
             "rules_version": gs.RULES_VERSION, "kinematics": T.KIN, "sizes_mb": sizes,
             "stretch_rule": {"min_min": T.MIN_MIN, "min_hops": T.MIN_HOPS, "target_min": T.TARGET_MIN,
                              "merge_share": T.MERGE_SHARE, "top_places": T.TOP_PLACES,
                              "term_min_trips": T.TERM_MIN_TRIPS, "term_share": T.TERM_SHARE},
             "files": {"tram_stretches.parquet": {"crs": "EPSG:4326", "rows": "one per stretch direction (tram)",
                                                  "geometry": "GTFS shape pieces along the stretch (EPSG:2180 -> 4326, 6 decimals)"}}}
    mp = write_meta(QA, "tram_stretches", inputs=inputs, started=t0, extra=extra)
    shutil.copyfile(mp, LY / "_meta_tram_stretches.json")
    print(f"tram_stretches done in {time.time() - t0:.0f} s; sizes {sizes}")
    return {"W": W, "M": M, "rank": rk, "share": sh, "sens": sens, "round": rs, "probe": sp}


BUS_DOC = ("Autobusy i trolejbusy, feedy oficjalne z kształtami tras (shapes); ta sama reguła odcinków co dla tramwajów, "
           "bez atrybutów OSM i bez zapasu (model ruchu dotyczy tramwaju).")


def write_bus(S: pd.DataFrame, M: pd.DataFrame, geoms: list, diag: pd.DataFrame, t0: float) -> dict:
    """results/tables/bus_stretches.csv + results/layers/bus_stretches.parquet (same columns as the tram files; OSM,
    slack and free-running columns are null)."""
    QA, TB, LY = T.QA, T.TABLES, T.LAYERS
    W = wide(S, M)
    for c in [c for c in W.columns if c.startswith(("slack_", "free_running"))]:
        W[c] = np.nan
    W["geometry_quality"] = np.where(W["share_hops_shape"] >= 0.95, "kształt trasy",
                                     np.where(W["share_hops_shape"] >= 0.5, "kształt, część odcinków prosto",
                                              "głównie odcinki proste"))
    _fmt(W).to_csv(TB / "bus_stretches.csv", index=False, lineterminator=LF)
    layer(W, geoms, S).to_parquet(LY / "bus_stretches.parquet", index=False)
    _fmt(diag.sort_values(["agglomeration", "mode"])).to_csv(QA / "bus_stretch_diagnostics.csv", index=False, lineterminator=LF)
    bm = W.set_index("stretch_dir_id")["below_min"]
    rows = []
    for (agg, mode), g in W.groupby(["agglomeration", "mode"], sort=True):
        k = g["vehicle_km_weekday"].fillna(0)
        rows.append({"agglomeration": agg, "mode": mode, "stretch_directions": int(len(g)),
                     "share_directions_below_min": float(g["below_min"].mean()),
                     "share_vkm_below_min": float(k[g["below_min"]].sum() / k.sum()),
                     "median_length_m": float(g["length_m"].median()),
                     "share_vkm_geometry_shape": float(k[g["share_hops_shape"] >= 0.95].sum() / k.sum())})
    _fmt(pd.DataFrame(rows)).to_csv(QA / "bus_stretch_quality.csv", index=False, lineterminator=LF)
    return {"W": W, "quality": pd.DataFrame(rows),
            "sizes": {p: round((d / p).stat().st_size / 1e6, 2) for d, p in ((TB, "bus_stretches.csv"), (LY, "bus_stretches.parquet"))}}


def write_rail_metro(t0: float) -> dict:
    """Metro and rail: one geometry per line (the line's most frequent stop pattern on the reference Wednesday, cut to
    the hops inside FUA + 15 km) with the line-level speed and trips per band from results/tables/speed_lines.csv."""
    lines = pd.read_csv(T.TABLES / "speed_lines.csv", dtype={"line": str})
    lines = lines[lines["mode"].isin(["metro", "rail"])]
    rows, geoms = [], []
    for agg in sc.AGGS:
        h = sc.hops(agg, "weekday")
        h = h[h["mode"].isin(["metro", "rail"]) & h["in_buf"]]
        if h.empty:
            continue
        cnt = h.drop_duplicates("uid").groupby(["mode", "feed", "line", "pid"]).size().rename("n").reset_index()
        cnt = cnt.sort_values(["mode", "feed", "line", "n", "pid"], ascending=[True, True, True, False, True], kind="stable")
        best = cnt.drop_duplicates(["mode", "feed", "line"])
        for r in best.itertuples(index=False):
            hp = h[h["pid"] == r.pid]
            hp = hp[hp["uid"] == hp["uid"].iloc[0]].sort_values("k")
            shp = sc.shape_arrays(r.feed)
            parts = [sc.hop_geometry(x, shp) for x in hp.itertuples(index=False)]
            coords = np.vstack([parts[0]] + [p[1:] for p in parts[1:]])
            l = lines[(lines["agglomeration"] == agg) & (lines["feed"] == r.feed) & (lines["line"] == str(r.line))]
            rec = {"agglomeration": agg, "mode": r.mode, "feed": r.feed, "line": str(r.line),
                   "terminals": l["terminals"].iloc[0] if len(l) else None, "pattern_trips_weekday": int(r.n)}
            for dt in sc.days():
                for b in sc.band_ids(dt) + ["all_day"]:
                    x = l[(l["day_type"] == dt) & (l["band"] == b)]
                    p = f"{DAYCODE[dt]}_{b}"
                    rec[f"speed_kmh_{p}"] = float(x["speed_kmh"].iloc[0]) if len(x) else np.nan
                    rec[f"trips_{p}"] = int(x["n_trips"].iloc[0]) if len(x) else 0
                    if b != "all_day":
                        rec[f"tph_{p}"] = rec[f"trips_{p}"] / (sc.band_minutes(dt, b) / 60)
            rows.append(rec); geoms.append(coords)
    W = pd.DataFrame(rows)
    o = W.sort_values(["agglomeration", "mode", "feed", "line"], kind="stable").index
    W = W.loc[o].reset_index(drop=True)
    geoms = [geoms[i] for i in o]
    W["stretch_dir_id"] = W["agglomeration"] + ":" + W["feed"] + ":" + W["line"]
    g = layer(W, geoms, pd.DataFrame({"stretch_dir_id": W["stretch_dir_id"]}))
    g = g.drop(columns="stretch_dir_id")
    g.to_parquet(T.LAYERS / "rail_metro_lines.parquet", index=False)
    return {"rows": len(g), "size_mb": round((T.LAYERS / "rail_metro_lines.parquet").stat().st_size / 1e6, 2)}
