"""Part 1 of the scheduled-speed work: speed per line, day type and time band, all modes, and city summaries.

    python -m pipeline.speed_tables

Measure: rozkładowa prędkość komunikacyjna (scheduled commercial speed, stops included) =
sum of trip lengths / sum of scheduled trip times over the trips of a line that start in the band.

Rules (all fixed here, repeated in results/qa/speed/speed.md)
* Trips: service layer (pipeline.gtfs_service, variant "all"; each row keeps its feed, rows of unofficial feeds
  carry the flag "feed nieoficjalny, niezweryfikowany").  Rail replacement buses (ZKA) are left out.
* Length of a trip: sum of its hop lengths (pipeline.speed_core): along the GTFS shape when the stops project on
  it, straight stop-to-stop otherwise.  Time: last arrival - first departure.  Rail trips of the nationwide feed
  are cut to the hops with both stops inside FUA + 15 km (the urban part of a long-distance run).
* Band: the band (config ``speed_time_bands``) of the trip's first departure; "all_day" = every trip.
* Exclusions (same as pipeline.tram_speed): length < 1 km, time < 5 min, < 3 stops, a stop without position, speed
  outside 5..V_MAX (tram 60, trolleybus 60, bus 80, metro 80, rail 160 km/h).
* Headway in the band: band length / trips of the busier direction (direction_id); when the line has no
  direction_id, band length / (trips / 2), flagged.
* Mean stop spacing: length / number of hops.
* Fallback: share of trips with at least one hop measured straight; a feed without shapes has share 1 and its speed
  is biased low by the detour factor (the median shape / straight ratio of shaped trips of the same mode and city
  is reported next to it).
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from pipeline import gtfs_service as gs
from pipeline import speed_core as sc
from pipeline.common import RESULTS, sig, write_json, write_meta

QA = RESULTS / "qa" / "speed" / "tables"
TABLES = RESULTS / "tables"
V_MAX = {"tram": 60.0, "trolleybus": 60.0, "bus": 80.0, "metro": 80.0, "rail": 160.0}
MIN_LEN_M, MIN_DUR_S, MIN_STOPS, V_MIN = 1000.0, 300.0, 3, 5.0
LABEL = "Rozkładowa prędkość komunikacyjna (z postojami na przystankach; z rozkładu, nie rzeczywista)"
UNOFFICIAL_FLAG = "feed nieoficjalny, niezweryfikowany"


# ------------------------------------------------------------------ trips
def trip_table(agg: str, day_type: str) -> pd.DataFrame:
    """One row per trip with length, time, band and exclusion reason (cached)."""
    sc.CACHE.mkdir(parents=True, exist_ok=True)
    day = sc.days()[day_type]
    p, sf = sc.CACHE / f"trips_{agg}_{day}.parquet", sc.CACHE / f"trips_{agg}_{day}.sig"
    s = sc._hop_sig(agg, day) + "|" + "trips-2026-11-24.2"
    if p.exists() and sf.exists() and sf.read_text() == s:
        return pd.read_parquet(p)
    h = sc.hops(agg, day_type)
    rail = h["mode"].eq("rail")
    h = h[~rail | h["in_buf"]]
    h = h.assign(fb=h["len_src"].ne("shape"), nopos=h["len_m"].isna() | h["t_s"].isna())
    g = h.groupby("uid", sort=True)
    t = pd.DataFrame({
        "feed": g["feed"].first(), "line": g["line"].first(), "mode": g["mode"].first(),
        "direction_id": g["direction_id"].first(), "repl_bus": g["repl_bus"].first(),
        "dep_s": g["dep_s"].min(), "arr_s": g["arr_s"].max(), "n_hops": g.size(),
        "len_m": g["len_m"].sum(), "len_straight_m": g["d_straight"].sum(),
        "n_fallback_hops": g["fb"].sum(), "nopos": g["nopos"].any(),
        "from_suid": g["from_suid"].first(), "to_suid": g["to_suid"].last(),
        "shape_src": g["len_src"].agg(lambda s: "shape" if (s == "shape").all() else
                                      ("straight_noshape" if (s == "straight_noshape").all() else "mixed")),
    }).reset_index()
    t["dur_s"] = t["arr_s"] - t["dep_s"]
    t["band"] = sc.band_of(t["dep_s"].to_numpy(), day_type)
    t["speed_kmh"] = t["len_m"] / t["dur_s"].where(t["dur_s"] > 0) * 3.6
    why = pd.Series("", index=t.index)
    why = why.mask(t["repl_bus"].astype(bool), "komunikacja zastępcza kolei")
    why = why.mask((why == "") & t["nopos"], "przystanek bez położenia")
    why = why.mask((why == "") & (t["len_m"] < MIN_LEN_M), "długość < 1 km")
    why = why.mask((why == "") & (t["dur_s"] < MIN_DUR_S), "czas < 5 min")
    why = why.mask((why == "") & (t["n_hops"] + 1 < MIN_STOPS), "< 3 przystanków")
    vmax = t["mode"].map(V_MAX).fillna(80.0)
    why = why.mask((why == "") & ~((t["speed_kmh"] >= V_MIN) & (t["speed_kmh"] <= vmax)), "prędkość poza zakresem")
    t["why_excluded"] = why
    t["official"] = t["feed"].map(sc.feed_official()).fillna(False)
    t.to_parquet(p, index=False)
    sf.write_text(s)
    return t


# ------------------------------------------------------------------ aggregation helpers
def wmedian(x, w) -> float:
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not ok.any():
        return float("nan")
    x, w = x[ok], w[ok]
    o = np.argsort(x, kind="stable")
    c = np.cumsum(w[o])
    return float(x[o][np.searchsorted(c, c[-1] / 2)])


def _speed(g: pd.DataFrame) -> float:
    d = g["dur_s"].sum()
    return float(g["len_m"].sum() / d * 3.6) if d > 0 else float("nan")


def _headway(g: pd.DataFrame, minutes: float) -> tuple[float, str]:
    dirs = g["direction_id"].astype(str)
    if dirs.isin(["None", "nan", ""]).all():
        return minutes / (len(g) / 2), "kursy/2 (brak direction_id)"
    return minutes / dirs.value_counts().max(), "kierunek z większą liczbą kursów"


def stop_names(agg: str) -> dict:
    s = gs.stops(agg, sc.VARIANT)
    return dict(zip(s["suid"], s["stop_name"].astype(str)))


def line_rows(t: pd.DataFrame, agg: str, day_type: str, names: dict, detour: dict) -> list[dict]:
    rows = []
    day = sc.days()[day_type]
    bands = [(b, sc.band_minutes(day_type, b)) for b in sc.band_ids(day_type)] + [("all_day", 1440.0)]
    for (mode, feed, line), g in t.groupby(["mode", "feed", "line"], sort=True):
        tp = g.groupby(["from_suid", "to_suid"]).size().sort_values(ascending=False, kind="stable")
        a, b = tp.index[0]
        term = f"{names.get(a, a)} – {names.get(b, b)}"
        for bid, mins in bands:
            gb = g if bid == "all_day" else g[g["band"] == bid]
            if gb.empty:
                continue
            hw, hw_rule = _headway(gb, mins)
            fb_share = float((gb["n_fallback_hops"] > 0).mean())
            src = "kształt trasy (shapes)" if fb_share == 0 else (
                "odcinki proste (brak shapes)" if (gb["shape_src"] == "straight_noshape").all() else "kształt, część odcinków prosto")
            flags = []
            if not bool(gb["official"].iloc[0]):
                flags.append(UNOFFICIAL_FLAG)
            if (gb["shape_src"] == "straight_noshape").all():
                f = detour.get((mode,))
                flags.append("długość w linii prostej między przystankami: prędkość zaniżona" +
                             (f" (kształt/linia prosta w tym mieście i środku: {f:.2f})" if f else ""))
            elif fb_share > 0.2:
                flags.append("ponad 20 % kursów z odcinkami w linii prostej")
            if len(gb) < 3:
                flags.append("mniej niż 3 kursy w paśmie")
            rows.append({"agglomeration": agg, "mode": mode, "feed": feed, "official": bool(gb["official"].iloc[0]),
                         "line": str(line), "terminals": term, "day_type": day_type, "timetable_date": day, "band": bid,
                         "band_label": "cała doba" if bid == "all_day" else sc.band_label(day_type, bid),
                         "speed_kmh": _speed(gb), "median_trip_speed_kmh": float(gb["speed_kmh"].median()),
                         "n_trips": int(len(gb)), "headway_min": hw if bid != "all_day" else None,
                         "headway_rule": hw_rule if bid != "all_day" else None,
                         "mean_trip_km": float(gb["len_m"].mean() / 1000),
                         "mean_stop_spacing_m": float(gb["len_m"].sum() / gb["n_hops"].sum()),
                         "vehicle_km": float(gb["len_m"].sum() / 1000),
                         "share_trips_fallback": fb_share, "length_source": src, "flag": "; ".join(flags) or None})
    return rows


def city_rows(t: pd.DataFrame, agg: str, day_type: str) -> list[dict]:
    rows = []
    day = sc.days()[day_type]
    for variant in gs.VARIANTS:
        tv = t if variant == "all" else t[t["official"]]
        for mode, gm in tv.groupby("mode", sort=True):
            for bid in sc.band_ids(day_type) + ["all_day"]:
                g = gm if bid == "all_day" else gm[gm["band"] == bid]
                if g.empty:
                    continue
                rows.append({"agglomeration": agg, "mode": mode, "variant": variant, "day_type": day_type,
                             "timetable_date": day, "band": bid,
                             "band_label": "cała doba" if bid == "all_day" else sc.band_label(day_type, bid),
                             "speed_kmh": _speed(g), "median_trip_speed_kmh": float(g["speed_kmh"].median()),
                             "wmedian_vkm_kmh": wmedian(g["speed_kmh"], g["len_m"]),
                             "n_trips": int(len(g)), "n_lines": int(g.groupby(["feed", "line"]).ngroups),
                             "vehicle_km": float(g["len_m"].sum() / 1000),
                             "share_trips_fallback": float((g["n_fallback_hops"] > 0).mean()),
                             "share_vkm_unofficial": float(g.loc[~g["official"], "len_m"].sum() / g["len_m"].sum())})
    return rows


def detour_factors(t: pd.DataFrame) -> dict:
    u = t[(t["why_excluded"] == "") & (t["shape_src"] == "shape")]
    out = {}
    for mode, g in u.groupby("mode"):
        out[(mode,)] = float((g["len_m"] / g["len_straight_m"]).median())
    return out


def tram_check(days: dict) -> pd.DataFrame:
    """Per-city tram medians from this step's trips vs results/qa/transit/tram_speed_per_city.csv and vs a re-run of
    pipeline.tram_speed.tram_trips (same rule as published: whole shape length, stop distance when > 15 % off)."""
    from pipeline import tram_speed as ts
    pub = pd.read_csv(RESULTS / "qa" / "transit" / "tram_speed_per_city.csv")
    rows = []
    for agg, feed, city in ts.CITIES:
        for dt, day in days.items():
            t = trip_table(agg, dt)
            u = t[(t["mode"] == "tram") & (t["why_excluded"] == "") & (t["feed"] == feed)]
            r = ts.tram_trips(agg, feed, day, "all")
            r["why"] = ts.exclusion(r)
            r = r[r["why"] == ""]
            p = pub[(pub["city"] == city) & (pub["variant"] == "all") & (pub["day_type"] == dt)]
            both = u.merge(r[["uid", "speed_kmh"]], on="uid", suffixes=("", "_ts"))
            rows.append({"agglomeration": agg, "city": city, "day_type": dt, "timetable_date": day,
                         "published_median_kmh": float(p["median_kmh"].iloc[0]) if len(p) else None,
                         "published_n_trips": int(p["n_trips"].iloc[0]) if len(p) else None,
                         "rerun_tram_speed_median_kmh": float(r["speed_kmh"].median()), "rerun_n_trips": int(len(r)),
                         "this_step_median_kmh": float(u["speed_kmh"].median()), "this_step_n_trips": int(len(u)),
                         "this_step_wmedian_vkm_kmh": wmedian(u["speed_kmh"], u["len_m"]),
                         "this_step_sum_ratio_kmh": _speed(u),
                         "median_diff_per_trip_kmh": float((both["speed_kmh"] - both["speed_kmh_ts"]).median()),
                         "p95_abs_diff_per_trip_kmh": float((both["speed_kmh"] - both["speed_kmh_ts"]).abs().quantile(.95)),
                         "trips_in_both": int(len(both))})
    return pd.DataFrame(rows)


def quick_check(days: dict) -> pd.DataFrame:
    """The earlier unverified quick look: straight hops x 1.04, peaks = trips starting 07-09 and 15-17, evening = after
    20:00.  Recomputed here with that definition and with this step's geometry, for the comparison in speed.md."""
    rows = []
    for agg in sc.AGGS:
        t = trip_table(agg, "weekday")
        u = t[(t["mode"] == "tram") & (t["why_excluded"] == "")]
        hr = np.mod(u["dep_s"], 86400) / 3600
        pk = u[((hr >= 7) & (hr < 9)) | ((hr >= 15) & (hr < 17))]
        ev = u[hr >= 20]
        for name, g in (("szczyty 07-09 + 15-17", pk), ("po 20:00", ev)):
            rows.append({"agglomeration": agg, "group": name, "n_trips": int(len(g)),
                         "speed_shape_kmh": _speed(g),
                         "speed_straight_x104_kmh": float(g["len_straight_m"].sum() * 1.04 / g["dur_s"].sum() * 3.6),
                         "median_trip_shape_kmh": float(g["speed_kmh"].median())})
    return pd.DataFrame(rows)


def _fmt(df: pd.DataFrame) -> pd.DataFrame:
    o = df.copy()
    for c in o.columns:
        if o[c].dtype.kind == "f":
            o[c] = o[c].map(sig)
    return o


def lines_json(lines: pd.DataFrame) -> dict:
    out = []
    for (agg, mode, feed, line), g in lines.groupby(["agglomeration", "mode", "feed", "line"], sort=True):
        rec = {"agglomeration": agg, "mode": mode, "feed": feed, "line": line, "official": bool(g["official"].iloc[0]),
               "terminals": g["terminals"].iloc[0]}
        for dt, gd in g.groupby("day_type", sort=True):
            rec[dt] = {r.band: {"speed_kmh": sig(r.speed_kmh), "n_trips": int(r.n_trips),
                                "headway_min": sig(r.headway_min) if pd.notna(r.headway_min) else None,
                                "share_trips_fallback": sig(r.share_trips_fallback), "flag": r.flag if isinstance(r.flag, str) else None}
                       for r in gd.itertuples(index=False)}
            rec[dt + "_mean_stop_spacing_m"] = sig(float(gd.loc[gd["band"] == "all_day", "mean_stop_spacing_m"].iloc[0])) \
                if (gd["band"] == "all_day").any() else None
        out.append(rec)
    return {"title": LABEL, "unit": "km/h", "timetable_dates": sc.days(),
            "bands": {dt: [{"id": b[0], "label": sc.band_label(dt, b[0])} for b in sc.bands(dt)] for dt in sc.days()},
            "band_rule": "kurs należy do pasma godziny pierwszego odjazdu; all_day = cała doba",
            "source": "GTFS (warstwa gtfs_service, wariant wszystkie feedy), długość wzdłuż shapes, rozkład jazdy",
            "lines": out}


def run() -> dict:
    t0 = time.time()
    days = sc.days()
    QA.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    L, C, X = [], [], []
    for agg in sc.AGGS:
        names = stop_names(agg)
        for dt in days:
            t = trip_table(agg, dt)
            ex = t[t["why_excluded"] != ""]
            for (mode, why), g in ex.groupby(["mode", "why_excluded"]):
                X.append({"agglomeration": agg, "day_type": dt, "mode": mode, "reason": why, "trips": int(len(g))})
            u = t[t["why_excluded"] == ""]
            det = detour_factors(t)
            L += line_rows(u, agg, dt, names, det)
            for r in city_rows(u, agg, dt):
                r["detour_factor_shaped_trips"] = det.get((r["mode"],))
                C.append(r)
            print(f"  {agg} {dt}: {len(u):,} trips", flush=True)
    lines = pd.DataFrame(L)
    border = {b: i for i, b in enumerate(sorted({b for dt in days for b in sc.band_ids(dt)}, key=lambda b: (
        [x for dt in days for x in sc.band_ids(dt)].index(b))) + ["all_day"])}
    lines["_b"] = lines["band"].map(border)
    lines = lines.sort_values(["agglomeration", "mode", "feed", "line", "day_type", "_b"], kind="stable").drop(columns="_b")
    city = pd.DataFrame(C)
    city["_b"] = city["band"].map(border)
    city = city.sort_values(["agglomeration", "mode", "variant", "day_type", "_b"], kind="stable").drop(columns="_b")
    excl = pd.DataFrame(X).sort_values(["agglomeration", "day_type", "mode", "reason"], kind="stable")
    # peak vs evening gap per city and mode
    gap = []
    for (agg, mode, variant), g in city.groupby(["agglomeration", "mode", "variant"], sort=True):
        w = g[g["day_type"] == "weekday"].set_index("band")
        s = g[g["day_type"] == "saturday"].set_index("band")
        def v(df, b):
            return float(df.loc[b, "speed_kmh"]) if b in df.index else float("nan")
        gap.append({"agglomeration": agg, "mode": mode, "variant": variant,
                    "weekday_am_peak_kmh": v(w, "am_peak"), "weekday_pm_peak_kmh": v(w, "pm_peak"),
                    "weekday_midday_kmh": v(w, "midday"), "weekday_evening_kmh": v(w, "evening"),
                    "gap_evening_minus_am_peak_kmh": v(w, "evening") - v(w, "am_peak"),
                    "gap_evening_minus_pm_peak_kmh": v(w, "evening") - v(w, "pm_peak"),
                    "ratio_am_peak_to_evening": v(w, "am_peak") / v(w, "evening"),
                    "saturday_day_kmh": v(s, "day"), "saturday_evening_kmh": v(s, "evening")})
    gap = pd.DataFrame(gap)
    chk = tram_check(days)
    qc = quick_check(days)
    _fmt(lines).to_csv(TABLES / "speed_lines.csv", index=False, lineterminator="\n")
    write_json(TABLES / "speed_lines.json", lines_json(lines))
    _fmt(city).to_csv(QA / "speed_city_mode_band.csv", index=False, lineterminator="\n")
    _fmt(gap).to_csv(QA / "speed_peak_evening_gap.csv", index=False, lineterminator="\n")
    _fmt(excl).to_csv(QA / "speed_excluded_trips.csv", index=False, lineterminator="\n")
    _fmt(chk).to_csv(QA / "tram_median_check.csv", index=False, lineterminator="\n")
    _fmt(qc).to_csv(QA / "quick_look_check.csv", index=False, lineterminator="\n")
    inputs = sorted({f"gtfs_{f}" for a in sc.AGGS for f in gs.feeds_for(a, "all")})
    write_meta(QA, "speed_tables", inputs=inputs, started=t0,
               extra={"timetable_dates": days, "code_version": sc.CODE_VERSION, "rules_version": gs.RULES_VERSION,
                      "label": LABEL, "outputs": ["results/tables/speed_lines.csv", "results/tables/speed_lines.json"]})
    print(f"speed_tables done in {time.time() - t0:.0f} s")
    return {"lines": lines, "city": city, "gap": gap, "check": chk, "quick": qc}


if __name__ == "__main__":
    run()
