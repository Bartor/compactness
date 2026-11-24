"""Outputs of the transfer-ease step: layer, metrics, QA tables, Polish note, _meta files (pipeline.transfer_ease)."""
from __future__ import annotations

import csv
import shutil
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline import transfer_ease as T
from pipeline.boundaries import load_agglomeration
from pipeline.common import round_sig, sig, write_json, write_meta

NAMES = {a: T.CFG["agglomerations"][a]["name"] for a in T.AGGS}
TOPN = 20
WALK_EASY_MIN = 2.0
WALK_HARD_MIN = 5.0
COV_MIN = float(T.CFG["coverage_min_share"])

# Known interchanges: (agglomeration, label, lon, lat, name pattern).  The node chosen is the one with the most
# departures among nodes whose names match the pattern and whose centre is within KNOWN_RADIUS_M of the point.
KNOWN_RADIUS_M = 600.0
KNOWN = [
    ("warszawa", "Centrum", 21.0107, 52.2302, r"Centrum"),
    ("warszawa", "Dworzec Centralny", 21.0030, 52.2287, r"Centraln"),
    ("warszawa", "Dworzec Wileński", 21.0346, 52.2546, r"Wileński"),
    ("warszawa", "Dworzec Gdański", 20.9945, 52.2575, r"Gdański"),
    ("krakow", "Rondo Mogilskie", 19.9590, 50.0655, r"Mogilsk"),
    ("krakow", "Dworzec Główny Zachód (Basztowa, Pawia)", None, None, r"Dworzec Główny Zachód"),
    ("krakow", "Kraków Główny (kolej)", 19.9479, 50.0684, r"Kraków Główny"),
    ("krakow", "Rondo Grunwaldzkie", 19.9330, 50.0485, r"Grunwaldzk"),
    ("krakow", "Podgórze SKA", None, None, r"Podgórze SKA"),
    ("krakow", "Borek Fałęcki", 19.9290, 50.0115, r"Borek Fałęcki"),
    ("wroclaw", "Galeria Dominikańska", 17.0403, 51.1083, r"(?i)dominika"),
    ("wroclaw", "pl. Grunwaldzki", 17.0606, 51.1117, r"(?i)pl\. grunwaldzki"),
    ("wroclaw", "Dworzec Główny", 17.0365, 51.0985, r"(?i)dworzec główny|wrocław główny"),
    ("poznan", "Rondo Kaponiera", 16.9126, 52.4081, r"Kaponiera"),
    ("poznan", "Poznań Główny / Dworzec Zachodni", 16.9110, 52.4020, r"Poznań Główny|Dworzec Zachodni|Most Dworcowy"),
    ("poznan", "Rondo Rataje", 16.9535, 52.3935, r"Rataje"),
    ("lodz", "Piotrkowska Centrum", 19.4573, 51.7594, r"Piotrkowska Centrum"),
    ("lodz", "Łódź Fabryczna", 19.4700, 51.7700, r"Fabryczn"),
    ("lodz", "Łódź Kaliska", 19.4300, 51.7570, r"Kalisk"),
    ("trojmiasto", "Gdańsk Główny", 18.6440, 54.3556, r"Gdańsk Główny|Dworzec Główny|Brama Wyżynna"),
    ("trojmiasto", "Gdańsk Wrzeszcz", 18.6060, 54.3800, r"Wrzeszcz"),
    ("trojmiasto", "Gdynia Główna", 18.5268, 54.5218, r"Gdynia Główna|Dworzec"),
    ("gzm", "Katowice Rynek", 19.0216, 50.2594, r"Rynek"),
    ("gzm", "Katowice Dworzec", 19.0170, 50.2575, r"Katowice$|Dworzec|Katowice Dw"),
    ("gzm", "Sosnowiec Główny", 19.1290, 50.2780, r"Sosnowiec Główny|Dworzec PKP|Sosnowiec Dworzec"),
]

LAYER_COLS = [
    "node_id", "agglomeration", "name", "names_all", "cluster_ids", "n_stops", "n_clusters", "diameter_m", "modes",
    "has_rail_or_metro", "n_lines", "n_pairs", "n_pairs_walk", "n_pairs_parallel_excluded", "n_pairs_platform_unknown",
    "dep_per_h_day", "dep_per_h_am",
    "walk_min_median", "walk_min_p90", "walk_m_median", "detour_median", "same_stop_share",
    "walk_dir_min_median", "walk_dir_min_p90", "crossings_dir_median", "steps_dir_share", "stepfree_dir_share",
    "walkwait_dir_am_median", "n_pairs_dir",
    "crossings_median", "crossings_max", "crossings_signal_share", "crossings_value_share", "track_crossing_pair_share",
    "steps_pair_share", "tunnel_pair_share", "bridge_pair_share", "stepfree_pair_share", "stepfree_extra_min_median",
    "road_share_median", "wait_am_median", "wait_day_median", "walkwait_am_median", "walkwait_am_p90",
    "walkwait_day_median", "walkwait_am_median_w", "stops_mean_walk_m", "stops_mean_straight_m",
    "timed_pairs_checked", "timed_pairs", "rail_pair_share",
    "in_fua", "in_core", "in_mask", "flag",
]
COMPONENTS = [c for c in LAYER_COLS[LAYER_COLS.index("walk_min_median"):LAYER_COLS.index("in_fua")]]


def _pl(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "brak danych"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _known_pick(nt: pd.DataFrame, agg: str, lon, lat, pat: str):
    c = nt[(nt.agglomeration == agg) & nt.names_all.str.contains(pat, regex=True, na=False)]
    if lon is not None and len(c):
        x, y = T.TO2180.transform(lon, lat)
        c = c[np.hypot(c.x - x, c.y - y) <= KNOWN_RADIUS_M]
    if c.empty:
        return None
    return c.sort_values(["dep_per_h_day", "node_id"], ascending=[False, True]).iloc[0]


def build_tables(results: list[dict]) -> dict:
    out = {"nodes": {}, "geo": {}}
    for R in results:
        agg = R["agg"]
        geo = load_agglomeration(agg)
        mask = T.mask_geom(agg)
        for rn in T.RULES:
            nt = T.node_table(R, rn, geo, mask)
            nt["has_rail_or_metro"] = nt.modes.str.contains("rail|metro", regex=True)
            fl = []
            for r in nt.itertuples():
                f = []
                if not r.in_mask:
                    f.append("poza maską pokrycia GTFS: brak danych")
                if r.n_pairs_platform_unknown > 0:
                    f.append("kolej/metro: perony nierozróżnione w GTFS, przejście między pociągami nieznane")
                if r.has_rail_or_metro:
                    f.append("stacja: dojście do punktu stacji z GTFS, nie do konkretnego peronu")
                if r.road_share_median is not None and r.road_share_median > 0.5:
                    f.append("ścieżka głównie po osi jezdni w OSM: przejścia mogą być niepoliczone")
                fl.append("; ".join(f))
            nt["flag"] = fl
            # outside the mask: components are no data
            out_m = ~nt.in_mask.to_numpy()
            for c in COMPONENTS:
                nt[c] = nt[c].astype(object)
                nt.loc[out_m, c] = None
            out["nodes"].setdefault(rn, []).append(nt)
    for rn in T.RULES:
        out["nodes"][rn] = pd.concat(out["nodes"][rn], ignore_index=True)
    return out


def city_values(nt: pd.DataFrame, pairs_by_agg: dict, agg: str, dom: str) -> dict:
    n = nt[(nt.agglomeration == agg)]
    base = n[n.in_core] if dom == "core" else n[n.in_fua]
    cov = (base.loc[base.in_mask, "dep_per_h_day"].sum() / base.dep_per_h_day.sum()) if base.dep_per_h_day.sum() > 0 else None
    d = base[base.in_mask]
    w = d[d.walk_min_median.notna()]
    tot = w.dep_per_h_day.sum()
    v = {"coverage": cov, "nodes_n": int(len(d))}
    v["dep_share_walk_le2"] = float(w.loc[w.walk_min_median.astype(float) <= WALK_EASY_MIN, "dep_per_h_day"].sum() / tot * 100) if tot > 0 else None
    wd = d[d.walk_dir_min_median.notna()]
    td = wd.dep_per_h_day.sum()
    v["dep_share_walkdir_le2"] = float(wd.loc[wd.walk_dir_min_median.astype(float) <= WALK_EASY_MIN, "dep_per_h_day"].sum() / td * 100) if td > 0 else None
    v["dep_share_walkdir_gt5"] = float(wd.loc[wd.walk_dir_min_median.astype(float) > WALK_HARD_MIN, "dep_per_h_day"].sum() / td * 100) if td > 0 else None
    v["dep_share_walk_gt5"] = float(w.loc[w.walk_min_median.astype(float) > WALK_HARD_MIN, "dep_per_h_day"].sum() / tot * 100) if tot > 0 else None
    top = d.sort_values(["dep_per_h_day", "node_id"], ascending=[False, True]).head(TOPN)
    v["top_n"] = int(len(top))
    for k, c in (("top_walk", "walk_min_median"), ("top_ww_am", "walkwait_am_median"),
                 ("top_ww_day", "walkwait_day_median"), ("top_cross", "crossings_median"),
                 ("top_wait_am", "wait_am_median"), ("top_walk_dir", "walk_dir_min_median"),
                 ("top_ww_dir_am", "walkwait_dir_am_median"), ("top_cross_dir", "crossings_dir_median"),
                 ("top_ww_am_w", "walkwait_am_median_w")):
        x = pd.to_numeric(top[c], errors="coerce").dropna()
        v[k] = float(x.median()) if len(x) else None
    P = pairs_by_agg[agg]
    P = P[~P.parallel & P.walk_m.notna()] if len(P) else P
    pt = P[P.area.isin(set(top.area))]
    v["top_stepfree_share"] = float(pt.stepfree_m.notna().mean() * 100) if len(pt) else None
    v["top_steps_share"] = float(pt.steps.astype(bool).mean() * 100) if len(pt) else None
    pa = P[P.area.isin(set(d.area))]
    v["same_stop_share"] = float(pa.same_stop.mean() * 100) if len(pa) else None
    nx = pa.crossings.sum() if len(pa) else 0
    v["crossing_value_share"] = float(pa.crossings_value.sum() / nx * 100) if nx > 0 else None
    v["crossing_signal_share"] = float(pa.crossings_signal.sum() / nx * 100) if nx > 0 else None
    v["road_share"] = float((pa.road_m.sum() / pa.len_m.sum()) * 100) if len(pa) and pa.len_m.sum() > 0 else None
    v["pairs_n"] = int(len(pa))
    return v


METRIC_SPEC = [
    # id, key, unit, tier, label
    ("transfer_dep_share_walkdir_le2min", "dep_share_walkdir_le2", "%", "main",
     "Odjazdy w zespołach przesiadkowych, w których mediana dojścia między liniami (z uwzględnieniem kierunków jazdy) "
     "wynosi ≤ 2 min; udział odjazdów 6–20 we wszystkich zespołach przesiadkowych obszaru"),
    ("transfer_top20_walkwait_dir_am_median_min", "top_ww_dir_am", "min", "main",
     "20 zespołów z największą liczbą odjazdów: mediana (po zespołach) mediany dojścia (z kierunkami) + oczekiwanego "
     "czekania na linię docelową, 7–9"),
    ("transfer_top20_walk_dir_median_min", "top_walk_dir", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana dojścia między liniami z uwzględnieniem kierunków jazdy "
     "(sieć piesza OSM, 5 km/h)"),
    ("transfer_top20_crossings_dir_median", "top_cross_dir", "przejść", "table",
     "20 zespołów z największą liczbą odjazdów: mediana liczby przejść przez jezdnię lub torowisko na dojściu "
     "(z kierunkami)"),
    ("transfer_top20_wait_am_median_min", "top_wait_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana oczekiwanego czekania na linię docelową, 7–9"),
    ("transfer_top20_walkwait_am_median_w_min", "top_ww_am_w", "min", "table",
     "20 zespołów z największą liczbą odjazdów: dojście (najlepsza para słupków) + czekanie 7–9, mediana ważona "
     "liczbą kursów pary linii"),
    ("transfer_dep_share_walk_le2min", "dep_share_walk_le2", "%", "table",
     "Odjazdy w zespołach, w których mediana dojścia między liniami przy najlepszej parze słupków (bez kierunków) "
     "wynosi ≤ 2 min; udział odjazdów 6–20"),
    ("transfer_top20_walk_median_min", "top_walk", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana dojścia przy najlepszej parze słupków (bez kierunków)"),
    ("transfer_top20_walkwait_am_median_min", "top_ww_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: dojście (najlepsza para słupków) + oczekiwane czekanie 7–9, mediana"),
    ("transfer_top20_stepfree_pair_share", "top_stepfree_share", "%", "table",
     "20 zespołów z największą liczbą odjazdów: odsetek par linii z dojściem bez schodów znalezionym w sieci OSM"),
    ("transfer_dep_share_walkdir_gt5min", "dep_share_walkdir_gt5", "%", "table",
     "Odjazdy w zespołach z medianą dojścia (z kierunkami) > 5 min; udział odjazdów 6–20"),
    ("transfer_same_stop_pair_share", "same_stop_share", "%", "table",
     "Pary linii, dla których najlepsza para słupków to ten sam słupek"),
    ("transfer_nodes_n", "nodes_n", "zespołów", "table",
     "Liczba zespołów przystanków z co najmniej jedną parą linii do przesiadki"),
    ("transfer_osm_crossing_value_share", "crossing_value_share", "%", "qa",
     "Kontrola danych OSM: odsetek przejść na policzonych dojściach z wartością crossing=* lub sygnalizacją"),
    ("transfer_osm_road_centerline_share", "road_share", "%", "qa",
     "Kontrola danych OSM: odsetek długości dojść prowadzonych osią jezdni (chodniki niezmapowane osobno)"),
]


def metric_rows(nodes: pd.DataFrame, pairs_by_agg: dict) -> list[dict]:
    rows = []
    src = (f"GTFS (feedy wg config.yaml, wariant wszystkie feedy, dzień {T.DAY}, warstwa usług pipeline.gtfs_service); "
           "OSM 2026-11-22 (sieć piesza pipeline.walk_network, tagi przejść); bez danych o ludności")
    for agg in T.AGGS:
        for dom in ("core", "covered"):
            v = city_values(nodes, pairs_by_agg, agg, dom)
            cov = v["coverage"]
            for mid, key, unit, tier, label in METRIC_SPEC:
                flag = []
                if dom == "core" and cov is not None and cov < COV_MIN:
                    flag.append(f"niepełne pokrycie GTFS: {cov * 100:.1f} % odjazdów w zespołach przesiadkowych rdzenia w masce")
                if dom == "covered":
                    flag.append("tylko zespoły w masce pokrycia GTFS; coverage_share = udział odjazdów zespołów FUA w masce")
                if key.startswith("top") and v["top_n"] < TOPN:
                    flag.append(f"tylko {v['top_n']} zespołów w obszarze")
                flag.append("miara własna, nie AMPTI; składowe podawane osobno")
                val = v[key]
                rows.append({"agglomeration": agg, "domain": dom, "metric": mid, "label": label,
                             "value": sig(val) if val is not None else None, "unit": unit, "grid": None,
                             "source": src, "population_date": None, "timetable_date": T.DAY,
                             "coverage_share": sig(cov) if cov is not None else None, "flag": "; ".join(flag),
                             "tier": tier, "feed_variant": T.VARIANT, "population_grid": None})
    return rows


FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]


def write_metrics(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["feed_variant"], m["domain"], m["metric"]))
    T.METRICS.mkdir(parents=True, exist_ok=True)
    write_json(T.METRICS / "metrics_transfer.json", {"generated_for_timetable_date": T.DAY, "metrics": rows})
    with open(T.METRICS / "metrics_transfer.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


def _round_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f" or df[c].dtype == object:
            df[c] = [sig(x) if isinstance(x, (float, np.floating)) else x for x in df[c]]
    return df


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _round_df(df).to_csv(path, index=False, lineterminator="\n")


def write_layer(nodes: pd.DataFrame) -> int:
    n = nodes[nodes.in_fua].copy()
    lon, lat = T.TO4326.transform(n.x.to_numpy(), n.y.to_numpy())
    n = n[LAYER_COLS].reset_index(drop=True)
    n = _round_df(n)
    for c in COMPONENTS:
        n[c] = pd.to_numeric(n[c], errors="coerce")
    n = n.sort_values(["agglomeration", "node_id"]).reset_index(drop=True)
    g = gpd.GeoDataFrame(n, geometry=gpd.points_from_xy(np.round(lon, 6), np.round(lat, 6)), crs="EPSG:4326")
    # keep the geometry aligned to the sorted rows
    order = nodes[nodes.in_fua].reset_index(drop=True)
    order = order.assign(lon=np.round(lon, 6), lat=np.round(lat, 6)).set_index("node_id").reindex(n.node_id)
    g = gpd.GeoDataFrame(n, geometry=gpd.points_from_xy(order.lon.to_numpy(), order.lat.to_numpy()), crs="EPSG:4326")
    T.LAYERS.mkdir(parents=True, exist_ok=True)
    g.to_parquet(T.LAYERS / "transfer_nodes.parquet", index=False)
    return len(g)


def write_all(results: list[dict], t0: float) -> None:
    from pipeline.transfer_md import write_md
    tabs = build_tables(results)
    pairs = {rn: {R["agg"]: R["rules"][rn]["pairs"] for R in results} for rn in T.RULES}
    main = tabs["nodes"]["main"]
    rows = metric_rows(main, pairs["main"])
    write_metrics(rows)
    n_layer = write_layer(main)
    T.QA.mkdir(parents=True, exist_ok=True)
    # known interchanges, each rule
    kn = []
    for agg, label, lon, lat, pat in KNOWN:
        for rn in T.RULES:
            r = _known_pick(tabs["nodes"][rn], agg, lon, lat, pat)
            rec = {"agglomeration": agg, "interchange": label, "rule": rn}
            if r is not None:
                rec.update({c: r[c] for c in ["node_id", "name", "names_all", "n_stops", "n_clusters", "diameter_m",
                                              "modes", "n_lines", "n_pairs", "n_pairs_platform_unknown",
                                              "dep_per_h_day", "dep_per_h_am"] + COMPONENTS[:-1] + ["in_mask", "flag"]})
            kn.append(rec)
    kn = pd.DataFrame(kn)
    write_csv(kn[kn.rule == "main"].drop(columns="rule"), T.QA / "known_interchanges.csv")
    write_csv(kn, T.QA / "known_interchanges_rules.csv")
    # pairs at the known interchanges (main rule)
    lines = pd.concat([R["lines"] for R in results]).drop_duplicates("line").set_index("line")
    pk = []
    for _, r in kn[(kn.rule == "main") & kn.node_id.notna()].iterrows():
        area = int(main.loc[main.node_id == r.node_id, "area"].iloc[0])
        p = pairs["main"][r.agglomeration]
        p = p[(p.area == area) & ~p.parallel].copy()
        p.insert(0, "node_id", r.node_id)
        p["label_a"] = p.line_a.map(lines.label); p["label_b"] = p.line_b.map(lines.label)
        p["walk_min"] = p.walk_m / T.M_PER_MIN
        pk.append(p.drop(columns=["area", "parallel"]))
    pk = pd.concat(pk, ignore_index=True).sort_values(["node_id", "line_a", "line_b"])
    write_csv(pk, T.QA / "pairs_known_interchanges.csv")
    # city summaries for every rule
    cs = []
    for rn in T.RULES:
        for agg in T.AGGS:
            for dom in ("core", "covered"):
                v = city_values(tabs["nodes"][rn], pairs[rn], agg, dom)
                cs.append({"rule": rn, "agglomeration": agg, "domain": dom, **v})
    cs = pd.DataFrame(cs)
    write_csv(cs, T.QA / "city_summary_rules.csv")
    # OSM tag completeness per city
    ot = []
    for R in results:
        c = R["census"]
        v = city_values(main, pairs["main"], R["agg"], "covered")
        ot.append({"agglomeration": R["agg"], **c,
                   "share_footway_road_nodes_tagged": c["footway_road_nodes_tagged"] / c["footway_road_nodes"] * 100,
                   "share_footway_road_nodes_with_value": c["footway_road_nodes_with_value"] / c["footway_road_nodes"] * 100,
                   "share_highway_crossing_with_value": c["highway_crossing_nodes_with_crossing_value"] / c["highway_crossing_nodes"] * 100,
                   "paths_crossing_value_share": v["crossing_value_share"], "paths_crossing_signal_share": v["crossing_signal_share"],
                   "paths_road_centerline_share": v["road_share"],
                   "share_elevator_dead_end": c["elevator_nodes_dead_end"] / c["elevator_nodes"] * 100
                   if c["elevator_nodes"] else None})
    ot = pd.DataFrame(ot)
    write_csv(ot, T.QA / "osm_tag_completeness.csv")
    # timed connections
    tm = []
    for R in results:
        t = R["rules"]["main"]["timed"]
        if len(t):
            t = t.copy(); t.insert(0, "agglomeration", R["agg"])
            nid = main[main.agglomeration == R["agg"]].set_index("area").node_id
            t.insert(1, "node_id", t.area.map(nid))
            tm.append(t[t.timed].drop(columns=["area"]))
    tm = pd.concat(tm, ignore_index=True).dropna(subset=["node_id"]).sort_values(["agglomeration", "node_id", "line_a", "line_b"])
    write_csv(tm, T.QA / "timed_connections_possible.csv")
    # top nodes per city (main)
    top = (main[main.in_mask].sort_values(["agglomeration", "dep_per_h_day", "node_id"], ascending=[True, False, True])
           .groupby("agglomeration").head(TOPN))
    write_csv(top[["agglomeration", "node_id", "name", "n_stops", "diameter_m", "modes", "n_lines", "n_pairs",
                   "dep_per_h_day"] + COMPONENTS[:-1] + ["flag"]], T.QA / "top_nodes.csv")
    secs = {R["agg"]: round(R["seconds"], 1) for R in results}
    ctx = {"tabs": tabs, "known": kn, "pairs_known": pk, "city": cs, "osm": ot, "timed": tm, "top": top,
           "rows": rows, "n_layer": n_layer, "seconds": secs, "results": results}
    write_md(ctx)
    # _meta files
    inputs = ["osm_poland_pbf"] + sorted({f"gtfs_{f}" for a in T.AGGS for f in T.gs.feeds_for(a, T.VARIANT)})
    extra = {"code_version": T.CODE_VERSION, "timetable_date": T.DAY, "feed_variant": T.VARIANT,
             "osm_date": "2026-11-22", "rules": T.RULES, "params": params(), "seconds_per_agglomeration": secs}
    write_meta(T.QA, "transfer_ease", inputs=inputs, started=t0,
               extra={**extra, "outputs": sorted(p.name for p in T.QA.iterdir() if p.name != "_meta.json")})
    tmp = Path(tempfile.mkdtemp())
    for folder, outs in ((T.METRICS, ["metrics_transfer.csv", "metrics_transfer.json"]),
                         (T.LAYERS, ["transfer_nodes.parquet"])):
        ex = {**extra, "outputs": outs}
        if folder == T.LAYERS:
            ex["files"] = {"transfer_nodes.parquet": {
                "crs": "EPSG:4326", "geometry": "mean position of the member stops of the stop area",
                "rows": "stop areas inside the FUA with at least one counted transfer pair (main area rule)",
                "null": "no data (outside the GTFS coverage mask, or no measurable pair); never 0 for missing"}}
        write_meta(tmp, "transfer_ease", inputs=inputs, started=t0, extra=ex)
        shutil.copyfile(tmp / "_meta.json", folder / "_meta_transfer.json")
    shutil.rmtree(tmp, ignore_errors=True)


def params() -> dict:
    from pipeline import transfer_walk as W
    return {"walk_kmh": T.WALK_KMH, "window_day": "06:00-20:00", "window_am": "07:00-09:00",
            "min_line_events": T.MIN_LINE_EVENTS, "parallel_share": T.PARALLEL_SHARE,
            "main_dir_share": T.MAIN_DIR_SHARE, "wait_cap_min": T.WAIT_CAP_MIN,
            "timed": {"min_headway_min": T.TIMED_MIN_HEADWAY, "ratio": T.TIMED_RATIO, "min_arrivals": T.TIMED_MIN_ARR},
            "stop_max_snap_m": T.STOP_MAX_SNAP_M, "local_margin_m": W.LOCAL_MARGIN_M,
            "dijkstra_limit_m": W.DIJKSTRA_LIMIT_M, "crossing_group_gap_m": W.GROUP_GAP_M,
            "top_n": TOPN, "walk_easy_min": WALK_EASY_MIN, "walk_hard_min": WALK_HARD_MIN}
