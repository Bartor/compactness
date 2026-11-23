"""Scheduled tram operating speed (brief 4.7).

LABEL EVERYWHERE: "rozkładowa prędkość eksploatacyjna (z postojami na przystankach)" = trip length /
(last arrival - first departure), as scheduled.  It is not running speed between stops and not real speed.

Rules
* Trips: every tram trip (route_class "tram") of the de-duplicated service layer on the reference day.
  Cities: Warszawa, Kraków, Wrocław, Poznań, Łódź, Gdańsk (feed ``gdansk`` inside Trójmiasto), GZM.  No other
  feed of the 42 has tram routes (checked).
* Length: shape length when the trip has a shape; the summed straight stop-to-stop distance is computed for every
  trip as a check.  Trips where the two differ by more than 15 % are flagged ``length_disagree``; for them
  (and for trips without a shape) the headline uses the stop distance, which is a lower bound of the real
  path (straight segments), so the speed is slightly underestimated.
* Excluded (not in any statistic, counted in ``tram_speed_excluded.csv``): length < 1 km, duration < 5 min,
  fewer than 3 stops (depot runs, short pull-ins), speed < 5 or > 60 km/h (implausible for a schedule).
* Layovers: dwell at an intermediate stop longer than 120 s is summed (``layover_s``).  The headline speed
  keeps them (it is operating speed including stops); the speed without layovers is given alongside.
* Weighted medians: ``trip`` = plain median of trips; ``vkm`` = median weighted by trip length.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline import gtfs_service as gs
from pipeline.common import round_sig, sig, write_json

CITIES = [("warszawa", "warsaw_ztm", "Warszawa"), ("krakow", "krakow_tram", "Kraków"), ("wroclaw", "wroclaw", "Wrocław"),
          ("poznan", "poznan", "Poznań"), ("lodz", "lodz", "Łódź"), ("trojmiasto", "gdansk", "Gdańsk"),
          ("gzm", "gzm", "GZM")]
MIN_LEN_M, MIN_DUR_S, MIN_STOPS = 1000, 300, 3
V_MIN, V_MAX = 5.0, 60.0
DISAGREE = 0.15
LAYOVER_S = 120
LABEL = "Rozkładowa prędkość eksploatacyjna tramwajów (z postojami na przystankach; nie prędkość jazdy ani rzeczywista)"


def wmedian(x: np.ndarray, w: np.ndarray) -> float:
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not ok.any():
        return float("nan")
    x, w = x[ok], w[ok]
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    c = np.cumsum(w)
    return float(x[np.searchsorted(c, c[-1] / 2)])


def tram_trips(agg: str, feed: str, day: str, variant: str = "all") -> pd.DataFrame:
    """Per-trip table with speeds (all tram trips of ``feed``, before exclusions)."""
    t = gs.active_trips(agg, day, variant)
    t = t[(t["feed"] == feed) & (t["route_class"] == "tram")].copy()
    st = gs.stop_times(agg, day, variant)
    st = st[st["uid"].isin(set(t["uid"]))]
    st = st.sort_values(["uid", "stop_sequence"], kind="stable")
    st["dwell"] = (st["dep_s"] - st["arr_s"]).clip(lower=0)
    last = st.groupby("uid")["stop_sequence"].transform("max")
    first = st.groupby("uid")["stop_sequence"].transform("min")
    mid = st[(st["stop_sequence"] > first) & (st["stop_sequence"] < last)]
    lay = mid[mid["dwell"] > LAYOVER_S].groupby("uid")["dwell"].agg(layover_s="sum", n_layovers="size")
    maxd = mid.groupby("uid")["dwell"].max().rename("max_dwell_s")
    t = t.join(lay, on="uid").join(maxd, on="uid")
    t[["layover_s", "n_layovers"]] = t[["layover_s", "n_layovers"]].fillna(0)
    t["duration_s"] = t["last_arr_s"] - t["first_dep_s"]
    shape_ok = t["dist_method"].eq("shape") & t["dist_m"].gt(0)
    ratio = np.where(shape_ok, t["dist_m"] / t["dist_stops_m"].where(t["dist_stops_m"] > 0), np.nan)
    t["shape_to_stops_ratio"] = ratio
    t["length_disagree"] = shape_ok & ~pd.Series(ratio, index=t.index).between(1 - DISAGREE, 1 + DISAGREE)
    # trips whose dist_method is "stops" already carry the stop distance in dist_m
    use_stops = ~shape_ok | t["length_disagree"]
    t["len_used_m"] = np.where(use_stops, t["dist_stops_m"], t["dist_m"])
    t["len_source"] = np.where(~shape_ok, "stops (brak kształtu)", np.where(t["length_disagree"], "stops (kształt niezgodny > 15 %)", "shape"))
    t["speed_kmh"] = t["len_used_m"] / t["duration_s"] * 3.6
    t["speed_noshape_kmh"] = t["dist_stops_m"] / t["duration_s"] * 3.6
    t["speed_ex_layover_kmh"] = t["len_used_m"] / (t["duration_s"] - t["layover_s"]).where(lambda s: s > 0) * 3.6
    t["hour"] = np.minimum(np.floor(t["first_dep_s"] / 3600), 29).astype(int)
    t["city_feed"] = feed
    return t


def exclusion(t: pd.DataFrame) -> pd.Series:
    why = pd.Series("", index=t.index)
    why = why.mask(t["len_used_m"] < MIN_LEN_M, "długość < 1 km")
    why = why.mask((why == "") & (t["duration_s"] < MIN_DUR_S), "czas < 5 min")
    why = why.mask((why == "") & (t["n_stops"] < MIN_STOPS), "< 3 przystanków")
    why = why.mask((why == "") & ~t["speed_kmh"].between(V_MIN, V_MAX), "prędkość poza 5-60 km/h")
    return why


def stats(g: pd.DataFrame) -> dict:
    s = g["speed_kmh"]
    return {"n_trips": int(len(g)), "length_km_total": float(g["len_used_m"].sum() / 1000),
            "median_kmh": float(s.median()), "q1_kmh": float(s.quantile(.25)), "q3_kmh": float(s.quantile(.75)),
            "min_kmh": float(s.min()), "max_kmh": float(s.max()),
            "wmedian_vkm_kmh": wmedian(s.to_numpy(), g["len_used_m"].to_numpy()),
            "median_ex_layover_kmh": float(g["speed_ex_layover_kmh"].median()),
            "median_trip_len_km": float(g["len_used_m"].median() / 1000)}


def unserved_tram_stops(agg: str, feed: str, day: str) -> dict:
    """Tram stops that the feed serves with trams on some date but not on ``day``, and the lines concerned."""
    from pipeline.gtfs_io import Feed, stop_events
    ft = gs.feed_table(feed)
    tr = ft[ft["route_class"] == "tram"]
    sd = gs._service_dates(feed)
    d = pd.Timestamp(day)
    svc_day = set(sd.loc[sd["date"] == d, "service_id"])
    ev = stop_events(Feed(feed))
    ev = ev[ev["trip_id"].isin(set(tr["trip_id"]))][["trip_id", "stop_id"]].copy()
    ev["trip_id"] = ev["trip_id"].astype(object)
    ev["stop_id"] = ev["stop_id"].astype(object)
    ev = ev.merge(tr[["trip_id", "service_id", "route_short_name"]], on="trip_id")
    ev["on_day"] = ev["service_id"].isin(svc_day)
    stops_all = set(ev["stop_id"])
    stops_day = set(ev.loc[ev["on_day"], "stop_id"])
    lost = stops_all - stops_day
    lines_day = set(ev.loc[ev["on_day"], "route_short_name"])
    rows = []
    for rsn, g in ev.groupby("route_short_name"):
        s_all, s_day = set(g["stop_id"]), set(g.loc[g["on_day"], "stop_id"])
        rows.append({"agglomeration": agg, "feed": feed, "line": rsn, "runs_on_day": rsn in lines_day,
                     "stops_all_dates": len(s_all), "stops_on_day": len(s_day),
                     "stops_lost_on_day": len(s_all - s_day),
                     "stops_lost_not_served_by_other_tram_line_on_day": len((s_all - s_day) & lost)})
    lines = pd.DataFrame(rows)
    names = feed_names(feed)
    return {"agglomeration": agg, "feed": feed, "tram_stops_all_dates": len(stops_all), "tram_stops_on_day": len(stops_day),
            "tram_stops_unserved_on_day": len(lost), "lines": lines[lines["stops_lost_not_served_by_other_tram_line_on_day"] > 0],
            "lost_stop_names": sorted({names.get(s, s) for s in lost})[:40]}


def feed_names(feed: str) -> dict:
    s = gs.feed_stops(feed)
    return dict(zip(s["stop_id"], s["stop_name"]))


def tram_gap(agg: str, feed: str, day: str, match_m: float = 75.0, near_m: float = 100.0) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """OSM tram stops (snapshot 2026-11-22) inside the FUA with no stop of a tram trip of ``day`` within ``match_m``
    (tracks closed for works, tram replaced by buses, or stops missing from the feed), the bus lines of the day
    that pass within ``near_m`` of those stops (candidates for replacement lines, not proven), and the tram routes
    of the feed that have no trip on ``day``."""
    import shapely
    from scipy.spatial import cKDTree
    from pipeline.boundaries import load_agglomeration
    from pipeline.common import INTERIM
    o = pd.read_parquet(INTERIM / "osm" / "stops_dedup.parquet")
    o = o[o["kind"] == "tram"]
    a = load_agglomeration(agg)
    o = o[shapely.contains_xy(a["fua"], o["x"].to_numpy(), o["y"].to_numpy())]
    t = gs.active_trips(agg, day, "all")
    st = gs.stop_times(agg, day, "all")
    tu = set(t[(t["route_class"] == "tram")]["uid"])
    ts = st[st["uid"].isin(tu)].drop_duplicates("suid").dropna(subset=["x", "y"])
    d, _ = cKDTree(ts[["x", "y"]].to_numpy(dtype=float)).query(o[["x", "y"]].to_numpy())
    un = o[d > match_m].copy()
    un = un[["name", "x", "y"]].sort_values(["name", "x"], kind="stable").reset_index(drop=True)
    un.insert(0, "agglomeration", agg)
    rows = []
    if len(un):
        bu = t[t["route_class"] == "bus"][["uid", "feed", "route_short_name"]]
        bs = st[st["uid"].isin(set(bu["uid"]))].dropna(subset=["x", "y"]).merge(bu, on="uid", suffixes=("", "_t"))
        tree = cKDTree(bs[["x", "y"]].to_numpy(dtype=float))
        idx = tree.query_ball_point(un[["x", "y"]].to_numpy(), near_m)
        cnt: dict[tuple, set] = {}
        for k, ids in enumerate(idx):
            for f, l in set(zip(bs.iloc[ids]["feed_t"], bs.iloc[ids]["route_short_name_t"])):
                cnt.setdefault((f, l), set()).add(k)
        ntr = bu.groupby(["feed", "route_short_name"]).size()
        for (f, l), ks in cnt.items():
            rows.append({"agglomeration": agg, "bus_feed": f, "bus_line": l, "gap_stops_within_100m": len(ks),
                         "gap_stops_total": len(un), "bus_trips_on_day": int(ntr.get((f, l), 0))})
    cand = pd.DataFrame(rows, columns=["agglomeration", "bus_feed", "bus_line", "gap_stops_within_100m", "gap_stops_total", "bus_trips_on_day"])
    cand = cand.sort_values(["gap_stops_within_100m", "bus_line"], ascending=[False, True], kind="stable").reset_index(drop=True)
    ft = gs.feed_table(feed)
    inactive = sorted(set(ft[ft["route_class"] == "tram"]["route_short_name"].dropna()) -
                      set(t[(t["feed"] == feed) & (t["route_class"] == "tram")]["route_short_name"]))
    return un, cand, inactive


def run(days: dict[str, str], qa, charts) -> dict:
    import matplotlib.pyplot as plt
    metrics, per_line, per_city, hourly, excl_rows, unserved, repl = [], [], [], [], [], [], []
    all_trips = {}
    for variant in gs.VARIANTS:
        for dname, day in days.items():
            for agg, feed, city in CITIES:
                if feed not in gs.feeds_for(agg, variant):
                    continue
                t = tram_trips(agg, feed, day, variant)
                t["why_excluded"] = exclusion(t)
                ex = t[t["why_excluded"] != ""]
                for why, g in ex.groupby("why_excluded"):
                    excl_rows.append({"city": city, "variant": variant, "day_type": dname, "day": day, "reason": why, "trips": len(g)})
                u = t[t["why_excluded"] == ""].copy()
                all_trips[(city, variant, dname)] = u
                for line, g in u.groupby("route_short_name"):
                    per_line.append({"city": city, "variant": variant, "day_type": dname, "day": day, "line": line, **stats(g),
                                     "n_length_disagree": int(g["length_disagree"].sum()),
                                     "n_no_shape": int((g["len_source"] == "stops (brak kształtu)").sum()),
                                     "share_trips_with_layover": float((g["n_layovers"] > 0).mean())})
                c = stats(u)
                c.update({"city": city, "variant": variant, "day_type": dname, "day": day, "n_lines": u["route_short_name"].nunique(),
                          "n_trips_before_exclusion": int(len(t)), "n_excluded": int(len(ex)),
                          "n_length_disagree": int(u["length_disagree"].sum()),
                          "n_no_shape": int((u["len_source"] == "stops (brak kształtu)").sum()),
                          "median_shape_only_kmh": float(u.loc[u["len_source"] == "shape", "speed_kmh"].median()),
                          "median_stops_only_kmh": float(u["speed_noshape_kmh"].median()),
                          "share_trips_with_layover": float((u["n_layovers"] > 0).mean()),
                          "mean_layover_min_in_those": float(u.loc[u["n_layovers"] > 0, "layover_s"].mean() / 60) if (u["n_layovers"] > 0).any() else float("nan")})
                per_city.append(c)
                for h, g in u.groupby("hour"):
                    hourly.append({"city": city, "variant": variant, "day_type": dname, "hour": int(h), "n_trips": len(g),
                                   "median_kmh": float(g["speed_kmh"].median()), "q1_kmh": float(g["speed_kmh"].quantile(.25)),
                                   "q3_kmh": float(g["speed_kmh"].quantile(.75))})
    pl = pd.DataFrame(per_line).sort_values(["day_type", "variant", "city", "line"], kind="stable").reset_index(drop=True)
    pc = pd.DataFrame(per_city).sort_values(["day_type", "variant", "city"], kind="stable").reset_index(drop=True)
    hr = pd.DataFrame(hourly).sort_values(["day_type", "variant", "city", "hour"], kind="stable").reset_index(drop=True)
    ex = pd.DataFrame(excl_rows).sort_values(["day_type", "variant", "city", "reason"], kind="stable").reset_index(drop=True)
    for name, df in (("tram_speed_per_line", pl), ("tram_speed_per_city", pc), ("tram_speed_hourly", hr), ("tram_speed_excluded", ex)):
        o = df.copy()
        for c in o.columns:
            if o[c].dtype.kind == "f":
                o[c] = o[c].map(sig)
        o.to_csv(qa / f"{name}.csv", index=False, lineterminator="\n")
    # trip-level file for the reference Wednesday, variant all (traceable)
    tl = pd.concat([v.assign(city=k[0]) for k, v in all_trips.items() if k[1] == "all" and k[2] == "weekday"], ignore_index=True)
    tl = tl[["city", "uid", "route_short_name", "direction_id", "first_dep_s", "last_arr_s", "duration_s", "n_stops", "dist_m",
             "dist_stops_m", "shape_to_stops_ratio", "length_disagree", "len_source", "len_used_m", "speed_kmh", "speed_ex_layover_kmh",
             "layover_s", "n_layovers", "max_dwell_s"]].sort_values(["city", "uid"], kind="stable")
    for c in tl.columns:
        if tl[c].dtype.kind == "f":
            tl[c] = tl[c].map(sig)
    tl.to_csv(qa / "tram_speed_trips.csv", index=False, lineterminator="\n")
    # unserved tram stops (Kraków, Łódź and the rest)
    uns, uns_lines, gaps, inact = [], [], [], []
    for agg, feed, city in CITIES:
        u = unserved_tram_stops(agg, feed, days["weekday"])
        uns.append({"city": city, "feed": feed, "tram_stops_all_dates": u["tram_stops_all_dates"],
                    "tram_stops_on_day": u["tram_stops_on_day"], "tram_stops_unserved_on_day": u["tram_stops_unserved_on_day"],
                    "examples": "; ".join(u["lost_stop_names"][:12])})
        if len(u["lines"]):
            uns_lines.append(u["lines"].assign(city=city))
        gap, cand, inactive = tram_gap(agg, feed, days["weekday"])
        gaps.append(gap.assign(city=city))
        repl.append(cand.assign(city=city))
        inact.append({"city": city, "tram_routes_without_trips_on_day": ", ".join(inactive)})
    pd.DataFrame(uns).to_csv(qa / "tram_stops_unserved.csv", index=False, lineterminator="\n")
    ul = pd.concat(uns_lines, ignore_index=True) if uns_lines else pd.DataFrame()
    ul.to_csv(qa / "tram_stops_unserved_by_line.csv", index=False, lineterminator="\n")
    rp = pd.concat(repl, ignore_index=True)
    rp.to_csv(qa / "tram_gap_bus_candidates.csv", index=False, lineterminator="\n")
    gp = pd.concat(gaps, ignore_index=True)
    gp.assign(x=gp["x"].round(0), y=gp["y"].round(0)).to_csv(qa / "tram_stops_osm_without_tram_service.csv", index=False, lineterminator="\n")
    pd.DataFrame(inact).to_csv(qa / "tram_routes_without_trips.csv", index=False, lineterminator="\n")
    # ---- plots
    _plot_city_dist(all_trips, qa)
    _plot_per_line(pl, qa)
    # ---- metrics (main only for per-city tram speed on the reference Wednesday)
    for r in pc.itertuples(index=False):
        sat = r.day_type == "saturday"
        daylab = "sobota 2026-11-28" if sat else "śr. 2026-11-25"
        agg = {c: a for a, f, c in CITIES}[r.city]
        base = {"agglomeration": agg, "domain": "city_tram_network", "grid": "", "population_date": "",
                "timetable_date": r.day, "coverage_share": None, "feed_variant": r.variant,
                "source": "GTFS (warstwa gtfs_service), kursy tramwajowe po deduplikacji; długość z kształtu trasy (przy niezgodności > 15 % z odległości między przystankami)",
                "unit": "km/h"}
        flag = "rozkładowa prędkość eksploatacyjna z postojami; sieć tramwajowa miasta, nie FUA"
        tier = "table" if sat else "main"
        tag = "_sat" if sat else ""
        for m, lab, val in (("tram_speed_median", "mediana kursów", r.median_kmh), ("tram_speed_wmedian_vkm", "mediana ważona długością kursu (wozkm)", r.wmedian_vkm_kmh),
                            ("tram_speed_q1", "pierwszy kwartyl kursów", r.q1_kmh), ("tram_speed_q3", "trzeci kwartyl kursów", r.q3_kmh)):
            metrics.append({**base, "metric": m + tag, "label": f"{LABEL.split(' (')[0]} ({daylab}), {r.city}: {lab}", "value": val,
                            "flag": flag, "tier": tier if m in ("tram_speed_median",) else "table"})
        metrics.append({**base, "metric": "tram_trips" + tag, "label": f"Kursy tramwajowe uwzględnione w prędkości ({daylab}), {r.city}",
                        "value": r.n_trips, "unit": "kursów", "flag": flag, "tier": "table"})
    _plot_hourly(hr, qa)
    write_json(charts / "tram_speed.json", chart_json(pl, pc, hr, days))
    return {"per_line": pl, "per_city": pc, "hourly": hr, "excluded": ex, "unserved": pd.DataFrame(uns), "unserved_lines": ul,
            "replacement": rp, "gap": gp, "inactive": pd.DataFrame(inact), "metrics": metrics}


def _plot_city_dist(all_trips: dict, qa) -> None:
    import matplotlib.pyplot as plt
    cities = [c for _, _, c in CITIES]
    fig, ax = plt.subplots(figsize=(11, 5))
    data = [all_trips[(c, "all", "weekday")]["speed_kmh"].to_numpy() for c in cities]
    w = [all_trips[(c, "all", "weekday")]["len_used_m"].to_numpy() for c in cities]
    parts = ax.violinplot(data, showmedians=False, showextrema=False)
    for b in parts["bodies"]:
        b.set_facecolor("#9ecae1"); b.set_edgecolor("#2171b5"); b.set_alpha(0.8)
    for i, (d, ww) in enumerate(zip(data, w), start=1):
        q1, med, q3 = np.percentile(d, [25, 50, 75])
        ax.plot([i, i], [q1, q3], color="k", lw=3)
        ax.plot(i, med, "o", color="w", mec="k")
        ax.plot(i, wmedian(d, ww), "D", color="#e6550d", ms=5)
        ax.text(i, ax.get_ylim()[0] if False else 4.2, f"n={len(d)}", ha="center", fontsize=8)
    ax.set_xticks(range(1, len(cities) + 1), cities)
    ax.set_ylabel("km/h")
    ax.set_ylim(4, max(np.max(d) for d in data) + 2)
    ax.set_title("Rozkładowa prędkość eksploatacyjna tramwajów (z postojami), kursy, śr. 2026-11-25\n"
                 "kółko = mediana kursów, romb = mediana ważona długością, belka = kwartyle", fontsize=10)
    fig.tight_layout()
    fig.savefig(qa / "tram_speed_per_city.png", dpi=110)
    plt.close(fig)


def _plot_per_line(pl: pd.DataFrame, qa) -> None:
    import matplotlib.pyplot as plt
    d = pl[(pl.variant == "all") & (pl.day_type == "weekday")]
    cities = [c for _, _, c in CITIES]
    fig, axes = plt.subplots(1, len(cities), figsize=(18, 7), sharex=True)
    for ax, c in zip(axes, cities):
        g = d[d.city == c].sort_values("median_kmh")
        y = np.arange(len(g))
        ax.hlines(y, g["q1_kmh"], g["q3_kmh"], color="#9ecae1", lw=4)
        ax.plot(g["median_kmh"], y, "o", color="#08519c", ms=4)
        ax.set_yticks(y, g["line"].astype(str), fontsize=7)
        ax.set_title(c, fontsize=10)
        ax.set_xlim(8, 40)
        ax.set_xlabel("km/h")
        ax.grid(axis="x", alpha=.3)
    fig.suptitle("Rozkładowa prędkość eksploatacyjna tramwajów wg linii (mediana i kwartyle kursów, z postojami), śr. 2026-11-25", fontsize=11)
    fig.tight_layout()
    fig.savefig(qa / "tram_speed_per_line.png", dpi=110)
    plt.close(fig)


def _plot_hourly(hr: pd.DataFrame, qa) -> None:
    import matplotlib.pyplot as plt
    d = hr[(hr.variant == "all") & (hr.day_type == "weekday") & (hr.n_trips >= 5)]
    fig, ax = plt.subplots(figsize=(11, 5))
    for c, g in d.groupby("city"):
        ax.plot(g["hour"], g["median_kmh"], marker="o", ms=3, label=c)
    ax.set_xlabel("godzina odjazdu z pierwszego przystanku (godz. z >= 5 kursami)")
    ax.set_ylabel("mediana, km/h")
    ax.set_title("Rozkładowa prędkość eksploatacyjna tramwajów (z postojami) wg godziny odjazdu, śr. 2026-11-25", fontsize=10)
    ax.legend(ncol=4, fontsize=8)
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(qa / "tram_speed_hourly.png", dpi=110)
    plt.close(fig)


def chart_json(pl: pd.DataFrame, pc: pd.DataFrame, hr: pd.DataFrame, days: dict) -> dict:
    out = {}
    for variant in gs.VARIANTS:
        for dname in days:
            key = f"{variant}/{dname}"
            cc = {}
            for r in pc[(pc.variant == variant) & (pc.day_type == dname)].itertuples(index=False):
                lines = pl[(pl.variant == variant) & (pl.day_type == dname) & (pl.city == r.city)]
                h = hr[(hr.variant == variant) & (hr.day_type == dname) & (hr.city == r.city)]
                cc[r.city] = round_sig({
                    "median_kmh": r.median_kmh, "wmedian_vkm_kmh": r.wmedian_vkm_kmh, "q1_kmh": r.q1_kmh, "q3_kmh": r.q3_kmh,
                    "n_trips": r.n_trips, "n_lines": r.n_lines, "n_excluded": r.n_excluded,
                    "lines": {str(x.line): {"median_kmh": x.median_kmh, "q1_kmh": x.q1_kmh, "q3_kmh": x.q3_kmh, "n_trips": x.n_trips,
                                            "length_km_total": x.length_km_total}
                              for x in lines.itertuples(index=False)},
                    "hourly_median_kmh": {int(x.hour): {"median_kmh": x.median_kmh, "n_trips": x.n_trips} for x in h.itertuples(index=False)}})
            out[key] = cc
    return {
        "title": LABEL,
        "definition": "długość kursu (kształt trasy; odległość między przystankami, gdy brak kształtu lub niezgodność > 15 %) / (ostatni przyjazd - pierwszy odjazd), kursy dnia referencyjnego, bez kursów zjazdowych/krótkich i o prędkości poza 5-60 km/h",
        "unit": "km/h", "timetable_dates": days, "population_date": None,
        "caveats": ["Prędkość z rozkładu jazdy, nie rzeczywista (warstwa 6b odłożona).",
                    "Zawiera postoje na przystankach i ewentualne postoje wyrównawcze wewnątrz kursu; wersja bez postojów > 120 s w CSV.",
                    "Różne definicje kursu (dłuższe lub krótsze relacje) wpływają na porównania między miastami.",
                    "Miasto = sieć tramwajowa feedu (Trójmiasto: tylko Gdańsk; GZM: cała sieć Tramwajów Śląskich w feedzie GZM)."],
        "series": out}
