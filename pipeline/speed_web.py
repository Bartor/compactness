"""Scheduled-speed overlay for the map: stretches and lines -> results/web/speed/.

    python -m pipeline.speed_web

Reads the committed speed outputs (results/layers/tram_stretches.parquet, bus_stretches.parquet,
rail_metro_lines.parquet, results/tables/speed_lines.csv) and writes
* trams.geojson          tram stretches of all seven cities, one feature per stretch direction
* bus_<agg>.geojson      bus and trolleybus stretches of one agglomeration (official feeds with shapes)
* rail.geojson           metro and rail, one feature per line (most frequent Wednesday pattern, FUA + 15 km)
* lines.json             the line table for the site (all modes): speed per band, Wednesday and Saturday
* _meta.json             sizes, counts, rules

Every speed is scheduled ("z rozkładu"): rozkładowa prędkość komunikacyjna, stops included, not measured.
Geometry: simplified to SIMPLIFY_M in EPSG:2180, coordinates rounded to COORD_DECIMALS.  Missing values are left
out of a feature's properties (never written as 0); flags are written only when true.

Feature properties (compact names; B = a band key from BANDS, e.g. w_am = Wednesday 07-09, s_d = Saturday 09-18):
  id, dir, agg, m (mode), name, ln (",3,5,7,": the Wednesday lines, comma-fenced for substring tests), fd (feeds),
  len (m), ns (stops), stops (" > "-joined stop places; trams and rail only)
  v_B speed km/h (1 decimal), t_B trips per hour, c (one character per band in BANDS order: class 0-5, "-" none)
  short (below the 5-minute minimum), straight (geometry mostly straight stop-to-stop), unoff (unofficial feed)
  trams only: a_B / al_B / ah_B time above free running, s/km (central / low / high; model), fm_B (timetable faster
  than the free-running model: no a_B), st (street-running share 0..1), x (road crossings), xs (with signals),
  xp (pedestrian crossings away from junctions), sw (switches), ms (share of length with OSM maxspeed)
"""
from __future__ import annotations

import json
import math
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from pipeline import speed_core as sc
from pipeline.common import RESULTS, sig, write_json, write_meta

OUT = RESULTS / "web" / "speed"
LY = RESULTS / "layers"
TB = RESULTS / "tables"
SIMPLIFY_M = 5.0
COORD_DECIMALS = 5
TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
STRAIGHT_BELOW = 0.5       # share of hops with shape geometry below which a stretch is drawn as "straight"
TARGET_MB = {"trams": 1.5, "bus": 4.0, "total": 25.0, "lines": 2.0}

# band key -> (day type, band id in config / column suffix); order = the order of the class string `c`
BANDS = {
    "w_n": ("weekday", "night"), "w_e": ("weekday", "early"), "w_am": ("weekday", "am_peak"),
    "w_md": ("weekday", "midday"), "w_pm": ("weekday", "pm_peak"), "w_ee": ("weekday", "early_eve"),
    "w_ev": ("weekday", "evening"), "w_all": ("weekday", "all_day"),
    "s_n": ("saturday", "night"), "s_mo": ("saturday", "morning"), "s_d": ("saturday", "day"),
    "s_ev": ("saturday", "evening"), "s_all": ("saturday", "all_day"),
}
DAYCODE = {"weekday": "wd", "saturday": "sat"}


def num(v, nd: int = 1):
    """Rounded number, ints stay ints; None for null / NaN / pd.NA."""
    if v is None or v is pd.NA:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    r = round(f, nd)
    return int(r) if r == int(r) else r


def band_minutes(dt: str, b: str) -> float:
    return 1440.0 if b == "all_day" else sc.band_minutes(dt, b)


def fence(lines) -> str | None:
    """"3, 5, 7" -> ",3,5,7," (so that a filter can test ",5," in it)."""
    if lines is None or (isinstance(lines, float) and math.isnan(lines)):
        return None
    parts = [x.strip() for x in str(lines).split(",") if x.strip()]
    return "," + ",".join(parts) + "," if parts else None


def geometry(g) -> list:
    """Line geometry simplified in metres, as [[lon, lat], ...] with COORD_DECIMALS."""
    xy = np.asarray(g.coords)
    x, y = TO2180.transform(xy[:, 0], xy[:, 1])
    line = shapely.simplify(shapely.linestrings(np.c_[x, y]), SIMPLIFY_M, preserve_topology=False)
    c = np.asarray(line.coords)
    lo, la = TO4326.transform(c[:, 0], c[:, 1])
    out = np.round(np.c_[lo, la], COORD_DECIMALS)
    keep = np.r_[True, (np.diff(out, axis=0) != 0).any(axis=1)]
    out = out[keep]
    if len(out) < 2:
        out = np.vstack([out, out])
    return [[float(a), float(b)] for a, b in out]


def band_props(r, model: bool) -> dict:
    p, cls = {}, []
    for key, (dt, b) in BANDS.items():
        sfx = f"{DAYCODE[dt]}_{b}"
        v = num(r.get(f"speed_kmh_{sfx}"), 1)
        if v is not None:
            p[f"v_{key}"] = v
        trips = r.get(f"trips_{sfx}")
        if trips is not None and not pd.isna(trips) and trips > 0:
            p[f"t_{key}"] = num(float(trips) / (band_minutes(dt, b) / 60), 1)
        c = int(sc.speed_class([v])[0]) if v is not None else -1
        cls.append(str(c) if c >= 0 else "-")
        if model and v is not None:
            if bool(r.get(f"faster_than_model_{sfx}") is True):
                p[f"fm_{key}"] = 1
            else:
                for pre, col in (("a", "taf_s_per_km"), ("al", "taf_lo_s_per_km"), ("ah", "taf_hi_s_per_km")):
                    x = num(r.get(f"{col}_{sfx}"), 0)
                    if x is not None:
                        p[f"{pre}_{key}"] = x
    p["c"] = "".join(cls)
    return p


def stretch_feature(r: dict, geom, official: dict, model: bool, with_stops: bool) -> dict:
    p = {"id": r["stretch_dir_id"], "dir": r["dir"], "agg": r["agglomeration"], "m": r["mode"], "name": r["name"]}
    ln = fence(r.get("lines_weekday"))
    if ln:
        p["ln"] = ln
    if isinstance(r.get("feeds"), str):
        p["fd"] = r["feeds"]
    p["len"] = num(r["length_m"], 0)
    p["ns"] = int(r["n_stops"])
    if with_stops:
        p["stops"] = r["stop_sequence"]
    p.update(band_props(r, model))
    if bool(r["below_min"]):
        p["short"] = 1
    shp = r.get("share_hops_shape")
    if shp is not None and not pd.isna(shp) and shp < STRAIGHT_BELOW:
        p["straight"] = 1
    feeds = [f.strip() for f in str(r.get("feeds") or "").split(",") if f.strip()]
    if any(not official.get(f, False) for f in feeds):
        p["unoff"] = 1
    if model:
        for k, col, nd in (("st", "share_street", 2), ("x", "n_road_crossings", 0), ("xs", "n_signalised", 0),
                           ("xp", "n_ped_standalone", 0), ("sw", "n_switches", 0), ("ms", "share_maxspeed_tagged", 2)):
            x = num(r.get(col), nd)
            if x is not None:
                p[k] = x
    return {"type": "Feature", "properties": p, "geometry": {"type": "LineString", "coordinates": geometry(geom)}}


def rail_feature(r: dict, geom, official: dict) -> dict:
    p = {"id": f"{r['agglomeration']}:{r['feed']}:{r['line']}", "agg": r["agglomeration"], "m": r["mode"],
         "line": str(r["line"]), "ln": fence(r["line"]), "fd": r["feed"], "name": r["terminals"] or str(r["line"])}
    p.update(band_props(r, False))
    if not official.get(r["feed"], False):
        p["unoff"] = 1
    return {"type": "Feature", "properties": p, "geometry": {"type": "LineString", "coordinates": geometry(geom)}}


def dump(features: list) -> str:
    return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False,
                      separators=(",", ":")) + "\n"


def write_text(path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path.stat().st_size


def records(g: gpd.GeoDataFrame) -> list[tuple[dict, object]]:
    cols = [c for c in g.columns if c != "geometry"]
    return [(dict(zip(cols, row)), geom) for row, geom in zip(g[cols].itertuples(index=False, name=None), g.geometry)]


# ------------------------------------------------------------------ line table
LINE_COLUMNS = ["key", "agg", "mode", "feed", "line", "term", "official", "v", "n", "hw", "gap", "sp", "flags"]


def lines_table(lines: pd.DataFrame) -> dict:
    """Columnar line table: one row per agglomeration x mode x feed x line; v / n / hw are arrays in BANDS order
    (speed km/h, trips, headway min; null where the line does not run)."""
    rows = []
    idx = lines.set_index(["agglomeration", "mode", "feed", "line", "day_type", "band"])
    for (agg, mode, feed, line), g in lines.groupby(["agglomeration", "mode", "feed", "line"], sort=True):
        gi = g.set_index(["day_type", "band"])
        v, n, hw = [], [], []
        for dt, b in BANDS.values():
            if (dt, b) in gi.index:
                x = gi.loc[(dt, b)]
                v.append(num(x["speed_kmh"], 1)); n.append(int(x["n_trips"])); hw.append(num(x["headway_min"], 1))
            else:
                v.append(None); n.append(None); hw.append(None)
        am, ev = v[list(BANDS).index("w_am")], v[list(BANDS).index("w_ev")]
        gap = num(ev - am, 1) if am is not None and ev is not None else None
        wd = gi.loc[("weekday", "all_day")] if ("weekday", "all_day") in gi.index else None
        sp = num(wd["mean_stop_spacing_m"], 0) if wd is not None else None
        flags = sorted({f.strip() for f in g["flag"].dropna().astype(str) for f in f.split(";")
                        if f.strip() and f.strip() != "mniej niż 3 kursy w paśmie"})
        rows.append([f"{agg}|{feed}|{line}", agg, mode, feed, str(line), g["terminals"].iloc[0],
                     bool(g["official"].iloc[0]), v, n, hw, gap, sp, "; ".join(flags) or None])
    del idx
    return {"title": "Prędkość linii z rozkładu (rozkładowa prędkość komunikacyjna, z postojami; nie pomiar)",
            "timetable_dates": sc.days(), "columns": LINE_COLUMNS,
            "bands": [{"key": k, "day_type": dt, "band": b,
                       "label": ("cała doba" if b == "all_day" else sc.band_label(dt, b)),
                       "day_label": sc.DAY_PL[dt]} for k, (dt, b) in BANDS.items()],
            "classes": {"breaks": sc.CLASS_BREAKS, "labels": sc.CLASS_LABELS},
            "notes": {"v": "km/h, suma długości / suma czasu kursów rozpoczętych w paśmie",
                      "n": "kursy rozpoczęte w paśmie (oba kierunki)",
                      "hw": "odstęp, min: długość pasma / kursy kierunku z większą liczbą kursów",
                      "gap": "środa: wieczór 20–23 minus szczyt poranny 07–09, km/h",
                      "sp": "średnia odległość między przystankami w środę, m",
                      "flags": "uwagi (feed nieoficjalny, długość w linii prostej itp.)"},
            "rows": rows}


def main() -> None:
    t0 = time.time()
    official = sc.feed_official()
    sizes, counts = {}, {}
    # trams
    tr = gpd.read_parquet(LY / "tram_stretches.parquet").sort_values("stretch_dir_id", kind="stable")
    feats = [stretch_feature(r, g, official, True, True) for r, g in records(tr)]
    sizes["trams.geojson"] = write_text(OUT / "trams.geojson", dump(feats))
    counts["trams.geojson"] = len(feats)
    # buses per agglomeration
    bs = gpd.read_parquet(LY / "bus_stretches.parquet").sort_values("stretch_dir_id", kind="stable")
    for agg in sc.AGGS:
        g = bs[bs["agglomeration"] == agg]
        feats = [stretch_feature(r, geom, official, False, False) for r, geom in records(g)]
        name = f"bus_{agg}.geojson"
        sizes[name] = write_text(OUT / name, dump(feats))
        counts[name] = len(feats)
    # metro and rail
    rm = gpd.read_parquet(LY / "rail_metro_lines.parquet")
    rm = rm.assign(_k=rm["agglomeration"] + ":" + rm["feed"] + ":" + rm["line"].astype(str)).sort_values("_k", kind="stable")
    feats = [rail_feature(r, g, official) for r, g in records(rm.drop(columns="_k"))]
    sizes["rail.geojson"] = write_text(OUT / "rail.geojson", dump(feats))
    counts["rail.geojson"] = len(feats)
    # line table
    lines = pd.read_csv(TB / "speed_lines.csv", dtype={"line": str})
    lt = lines_table(lines)
    sizes["lines.json"] = write_text(OUT / "lines.json", json.dumps(lt, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts["lines.json"] = len(lt["rows"])
    mb = {k: round(v / 1e6, 3) for k, v in sorted(sizes.items())}
    total = round(sum(sizes.values()) / 1e6, 3)
    over = [k for k, v in mb.items() if (k == "trams.geojson" and v > TARGET_MB["trams"]) or
            (k.startswith("bus_") and v > TARGET_MB["bus"]) or (k == "lines.json" and v > TARGET_MB["lines"])]
    write_meta(OUT, "speed_web", inputs=[], started=t0, extra={
        "label": "rozkładowa prędkość komunikacyjna (z rozkładu, nie pomiar)", "timetable_dates": sc.days(),
        "sources": ["results/layers/tram_stretches.parquet", "results/layers/bus_stretches.parquet",
                    "results/layers/rail_metro_lines.parquet", "results/tables/speed_lines.csv"],
        "simplify_m": SIMPLIFY_M, "coord_decimals": COORD_DECIMALS, "bands": {k: list(v) for k, v in BANDS.items()},
        "speed_classes_kmh": {"breaks": sc.CLASS_BREAKS, "labels": sc.CLASS_LABELS},
        "features": counts, "sizes_mb": mb, "total_mb": total, "targets_mb": TARGET_MB, "over_target": over})
    print(f"speed_web: {counts}; sizes MB {mb}; total {total} MB; over target {over}; {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
