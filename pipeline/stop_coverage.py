"""Phase 0: preliminary GTFS coverage check (brief section 6).

    python -m pipeline.stop_coverage            # all phase-1 agglomerations -> results/qa/phase0/coverage/

Question: which OSM public-transport stops have a counterpart in the timetable data we hold
(GTFS feeds assigned to the agglomeration + nationwide rail)?  The indicator is
"% of OSM stops with a GTFS counterpart", per gmina (LAU 2021) and per 1 km ring from the
centre, by mode.  Outside the covered area transport results are "no data", never 0.

Method in short (details, the radius test and its sensitivity in coverage.md):
* GTFS side: stops with >= 1 stop event on the reference day, with the mode classes of the routes
  serving them; stops that are in stops.txt but not served that day are kept separately.  Parent
  stations (rail / metro) inherit the union of their children's modes, because OSM
  ``railway=station`` sits at the station centre while GTFS points may be platforms.
* OSM side: de-duplicated stops (data/interim/osm/stops_dedup.parquet) inside the FUA.
  - rail platforms within the rail radius of an OSM rail station are absorbed by the station
    (one station = one unit); orphan platforms become mode "unknown", because many of them turn
    out to be tram / bus platforms carrying ``railway=platform``;
  - heritage, draisine, narrow-gauge tourist and park railways and the Gdynia funicular are left
    out of the rail denominator (name / operator rules below), and counted.
* Matching (EPSG:2180, KD-tree), with mode compatibility:
  bus <- bus/trolleybus; tram <- tram; rail <- rail (incl. replacement buses of the rail feed);
  metro <- metro; ferry <- ferry; unknown <- any mode.
  A stop is matched when (a) a compatible served GTFS point lies within the distance radius, or
  (b) a compatible served GTFS point within the name radius (200 m; rail 500 m) has the same
  normalised name or the same stop code (OSM ``ref`` vs GTFS stop_id / stop_code).
  For the all-mode indicator (the coverage mask), a tram / rail / metro stop whose own mode has no
  counterpart but which has a served stop of another mode within the bus radius counts as covered
  ("replacement": e.g. trams replaced by buses during works); the per-mode indicators stay strict.
* Chance control: the distance match repeated on OSM points shifted in a random direction (fixed
  seed; 200-400 m for bus/tram, 1000-1500 m for rail) estimates accidental matches.

Code and comments in English, report in Polish.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import warnings
from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely import contains_xy

from pipeline.boundaries import load_agglomeration, load_lau
from pipeline.common import CRS_METRIC, INTERIM, RAW, RESULTS, load_config, round_sig, sig, write_meta
from pipeline.gtfs_io import Feed, service_dates, stop_events, trip_stats

OUT = RESULTS / "qa" / "phase0" / "coverage"
OSM_DEDUP = INTERIM / "osm" / "stops_dedup.parquet"
NSP_SHP = RAW / "nsp2021" / "extracted" / "GRID_NSP2021_RES.shp"
REF_DAYS = RESULTS / "qa" / "phase0" / "gtfs" / "reference_days.json"

AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
MODES = ["bus", "tram", "rail", "metro", "ferry", "unknown"]
RAIL_BOUND = ["tram", "rail", "metro"]
REPORT_MODES = ["all", "bus", "tram", "rail"]          # metro / ferry / unknown only inside "all"
BUS_RADII = [30, 50, 75, 100, 150]                     # bus, tram, metro, ferry, unknown
RAIL_RADII = [100, 200, 300, 500]
DEFAULT_RAIL_RADIUS = 200                             # PROPOSAL: config key osm_gtfs_rail_match_radius_m
NAME_RADIUS = {"rail": 500, "other": 200}              # name / code assisted match
SHIFT = {"rail": (1000, 1500), "other": (200, 400)}    # chance control
POP_THRESHOLDS = [0.5, 0.7, 0.85]
GMINA_WELL, GMINA_POOR, GMINA_MIN_N = 0.8, 0.4, 10     # gap classification of unmatched stops
LOCAL_RADIUS_M = 1000                                  # local (cell) variant of the population side
SEED = 20261125
COVERED = ["matched", "matched_name", "matched_replacement"]

KIND_TO_MODE = {"bus": "bus", "tram": "tram", "rail_station": "rail", "rail_platform": "rail",
                "subway": "metro", "ferry": "ferry", "platform_unknown": "unknown"}
CLASS_TO_FLAG = {"bus": "bus", "trolleybus": "bus", "tram": "tram", "rail": "rail", "metro": "metro",
                 "ferry": "ferry", "other": "other"}
FLAGS = ["bus", "tram", "rail", "metro", "ferry", "zka", "other"]
COMPAT = {"bus": ["bus"], "tram": ["tram"], "rail": ["rail", "zka"], "metro": ["metro"],
          "ferry": ["ferry"], "unknown": FLAGS}
MODE_PL = {"all": "wszystkie", "bus": "autobus", "tram": "tramwaj", "rail": "kolej", "metro": "metro",
           "ferry": "prom", "unknown": "peron (tryb nieznany)"}

# Heritage / tourist railways (not part of the timetabled network).  Matched on name, operator,
# network.  Poznan: the Maltanka park railway (operator MPK Poznan, stations Maltanka, Balbinka,
# Ptys, Zwierzyniec) has no distinctive word, so it is named explicitly.
HERITAGE_RE = re.compile(r"wąskotor|waskotor|drezyn|kolejka parkowa|muzeum kolej|zabytkow|miłośników kolei|"
                         r"kolei wąskotorowych|turystyki|stanica|^stacja (górna|dolna)$", re.I)
HERITAGE_NAMES_POZNAN = {"maltanka", "balbinka", "ptyś", "zwierzyniec"}

_TO2180 = Transformer.from_crs("EPSG:4326", CRS_METRIC, always_xy=True)


# ------------------------------------------------------------------ config / small helpers
def ref_day() -> pd.Timestamp:
    cfg = load_config()
    d = cfg.get("reference_day") or json.loads(REF_DAYS.read_text(encoding="utf-8"))["reference_day"]
    return pd.Timestamp(d)


def radii() -> tuple[int, int]:
    cfg = load_config()
    return (int(cfg.get("osm_gtfs_match_radius_m", 50)),
            int(cfg.get("osm_gtfs_rail_match_radius_m", DEFAULT_RAIL_RADIUS)))


def radius_list(mode: str) -> list[int]:
    return RAIL_RADII if mode == "rail" else BUS_RADII


def write_csv(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(sig)
    df.to_csv(OUT / name, index=False, encoding="utf-8", lineterminator="\n")


def feeds_for(agg: str) -> list[str]:
    feeds = load_config()["feeds"]
    return sorted(f for f, c in feeds.items() if agg in (c.get("agglomerations") or []))


_NZ = re.compile(r"\(?\b(n/ż|nż|na żądanie|nz)\b\)?|\[nż\]", re.I)


def norm_name(v) -> str:
    """Stop name -> comparable form: case-folded, 'na zadanie' marks and post numbers dropped."""
    if not isinstance(v, str) or not v.strip():
        return ""
    s = unicodedata.normalize("NFC", v).casefold()
    s = _NZ.sub(" ", s)
    s = re.sub(r"[-–—/,.;:()\[\]\"„”'`]+", " ", s)
    toks = s.split()
    while toks and re.fullmatch(r"\d{1,2}|[ivx]{1,3}", toks[-1]) and len(toks) > 1:
        toks.pop()   # trailing post number ("Bukowiecka 02")
    return " ".join(toks)


def names_agree(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return small <= large and sum(len(t) for t in small) >= 5


def refs_agree(osm_ref, keys: set[str]) -> bool:
    if not isinstance(osm_ref, str):
        return False
    for r in osm_ref.split(";"):
        r = r.strip().casefold()
        if len(r) < 4:
            continue
        if r in keys or any(r.startswith(k + "-") for k in keys if len(k) >= 4):
            return True
    return False


# ------------------------------------------------------------------ GTFS side
@lru_cache(maxsize=None)
def gtfs_points(feed_id: str) -> pd.DataFrame:
    """One row per GTFS stop (location_type 0/blank) and per parent station, in EPSG:2180.

    Columns: feed, stop_id, stop_code, name, x, y, is_parent, has_parent, served, in_any_trip,
    n_events (stop events on the reference day, duplicates not removed), s_<flag> (served on the
    reference day by a route of that class), a_<flag> (on any day of the feed).
    """
    day = ref_day()
    feed = Feed(feed_id)
    stops = feed.table("stops.txt", ["stop_id", "stop_code", "stop_name", "stop_lat", "stop_lon",
                                     "location_type", "parent_station"])
    for c in ("location_type", "parent_station", "stop_code"):
        if c not in stops:
            stops[c] = np.nan
    stops["location_type"] = stops["location_type"].fillna("0").replace("", "0")
    ts = trip_stats(feed)[["trip_id", "service_id", "route_class"]].copy()
    sd = service_dates(feed)
    active = set(sd.loc[sd["date"] == day, "service_id"])
    ts["served"] = ts["service_id"].isin(active)
    flag = ts["route_class"].map(CLASS_TO_FLAG).fillna("other")
    if feed_id == "polish_trains":
        flag = flag.where(flag != "bus", "zka")   # replacement buses (ZKA) of the rail feed
    ts["flag"] = flag
    ev = stop_events(feed)[["trip_id", "stop_id"]]
    ev = pd.DataFrame({"trip_id": ev["trip_id"].astype(str).to_numpy(),
                       "stop_id": ev["stop_id"].astype(str).to_numpy()})
    ev = ev.merge(ts[["trip_id", "served", "flag"]], on="trip_id", how="inner")
    any_flags = pd.crosstab(ev["stop_id"], ev["flag"]).gt(0)
    sev = ev[ev["served"]]
    srv_flags = pd.crosstab(sev["stop_id"], sev["flag"]).gt(0)
    n_ev = sev.groupby("stop_id").size()

    pts = stops[stops["location_type"].isin(["0", "1"])].copy()
    pts["lat"] = pd.to_numeric(pts["stop_lat"], errors="coerce")
    pts["lon"] = pd.to_numeric(pts["stop_lon"], errors="coerce")
    pts = pts.dropna(subset=["lat", "lon"])
    pts = pts[(pts["lat"].abs() > 1) & (pts["lon"].abs() > 1)]
    for f in FLAGS:
        pts[f"s_{f}"] = pts["stop_id"].map(srv_flags[f] if f in srv_flags else {}).fillna(False).astype(bool)
        pts[f"a_{f}"] = pts["stop_id"].map(any_flags[f] if f in any_flags else {}).fillna(False).astype(bool)
    pts["n_events"] = pts["stop_id"].map(n_ev).fillna(0).astype(int)
    pts["is_parent"] = pts["location_type"] == "1"
    parents = set(pts.loc[pts["is_parent"], "stop_id"])
    pts["has_parent"] = pts["parent_station"].isin(parents)
    kids = pts[pts["has_parent"]]
    if len(kids):   # parents inherit their children's modes and events
        cols = [f"s_{f}" for f in FLAGS] + [f"a_{f}" for f in FLAGS]
        agg = kids.groupby("parent_station")[cols].any()
        nev = kids.groupby("parent_station")["n_events"].sum()
        par = pts["is_parent"].to_numpy()
        for c in cols:
            inh = pts.loc[par, "stop_id"].map(agg[c]).fillna(False).astype(bool).to_numpy()
            pts.loc[par, c] = inh | pts.loc[par, c].to_numpy()
        pts.loc[par, "n_events"] = pts.loc[par, "stop_id"].map(nev).fillna(0).astype(int).to_numpy()
    pts["served"] = pts[[f"s_{f}" for f in FLAGS]].any(axis=1)
    pts["in_any_trip"] = pts[[f"a_{f}" for f in FLAGS]].any(axis=1)
    pts["x"], pts["y"] = _TO2180.transform(pts["lon"].to_numpy(), pts["lat"].to_numpy())
    pts["feed"] = feed_id
    pts = pts.rename(columns={"stop_name": "name"})
    pts["name_n"] = pts["name"].map(norm_name)
    keep = ["feed", "stop_id", "stop_code", "name", "name_n", "x", "y", "is_parent", "has_parent", "served",
            "in_any_trip", "n_events"] + [f"s_{f}" for f in FLAGS] + [f"a_{f}" for f in FLAGS]
    return pts[keep].sort_values(["feed", "stop_id"]).reset_index(drop=True)


def gtfs_mode(g: pd.DataFrame) -> pd.Series:
    """Primary mode of a GTFS unit for reporting (rail > metro > tram > bus > ferry > zka > other)."""
    out = pd.Series("other", index=g.index)
    for f in ["other", "zka", "ferry", "bus", "tram", "metro", "rail"]:
        out = out.where(~g[f"s_{f}"], f)
    return out


# ------------------------------------------------------------------ OSM side
@lru_cache(maxsize=1)
def osm_all() -> pd.DataFrame:
    d = pd.read_parquet(OSM_DEDUP)
    d["mode"] = d["kind"].map(KIND_TO_MODE).fillna("unknown")
    return d


def is_heritage(d: pd.DataFrame) -> np.ndarray:
    txt = (d["name"].fillna("") + " | " + d["operator"].fillna("") + " | " + d["network"].fillna(""))
    h = txt.map(lambda s: any(HERITAGE_RE.search(p.strip()) for p in s.split("|"))).to_numpy()
    park = (d["operator"].fillna("") == "MPK Poznań") & d["name"].fillna("").str.casefold().isin(HERITAGE_NAMES_POZNAN)
    return (h | park.to_numpy()) & (d["mode"] == "rail").to_numpy()


def osm_in(geom, r_rail: float) -> tuple[pd.DataFrame, dict]:
    """OSM stops inside ``geom`` with the rail clean-up described in the module docstring."""
    d = osm_all()
    xmin, ymin, xmax, ymax = geom.bounds
    d = d[(d.x >= xmin) & (d.x <= xmax) & (d.y >= ymin) & (d.y <= ymax)]
    d = d[contains_xy(geom, d.x.to_numpy(), d.y.to_numpy())].copy()
    st = d[d.kind == "rail_station"]
    pl = (d.kind == "rail_platform").to_numpy()
    near = np.zeros(len(d), bool)
    if len(st) and pl.any():
        dist, _ = cKDTree(st[["x", "y"]].to_numpy()).query(d.loc[pl, ["x", "y"]].to_numpy())
        near[np.flatnonzero(pl)] = dist <= r_rail
    orphan = pl & ~near
    d.loc[orphan, "mode"] = "unknown"
    her = is_heritage(d)
    stats = {"rail_platforms_absorbed": int(near.sum()), "rail_platforms_orphan_to_unknown": int(orphan.sum()),
             "rail_heritage_excluded": int(her.sum()),
             "rail_heritage_names": sorted(set(d.loc[her, "name"].fillna("(bez nazwy)")))}
    d = d[~near & ~her].sort_values(["osm_type", "osm_id"]).reset_index(drop=True)
    d["name_n"] = d["name"].map(norm_name)
    return d, stats


# ------------------------------------------------------------------ matching
def nearest(points: np.ndarray, targets: np.ndarray) -> np.ndarray:
    if len(targets) == 0 or len(points) == 0:
        return np.full(len(points), np.inf)
    d, _ = cKDTree(targets).query(points)
    return d


def name_distance(osm: pd.DataFrame, sel: np.ndarray, g: pd.DataFrame, comp: np.ndarray, radius: float) -> np.ndarray:
    """Distance to the nearest compatible served GTFS point within ``radius`` that agrees by name or code."""
    out = np.full(int(sel.sum()), np.inf)
    gg = g[comp]
    if gg.empty or not sel.any():
        return out
    tree = cKDTree(gg[["x", "y"]].to_numpy())
    o = osm[sel]
    cand = tree.query_ball_point(o[["x", "y"]].to_numpy(), radius)
    gx, gy = gg["x"].to_numpy(), gg["y"].to_numpy()
    gname = gg["name_n"].to_numpy()
    gkeys = [{str(a).casefold(), str(b).casefold()} - {"nan", ""} for a, b in zip(gg["stop_id"], gg["stop_code"])]
    for i, (idx, x, y, nm, ref) in enumerate(zip(cand, o["x"], o["y"], o["name_n"], o["ref"])):
        best = np.inf
        for j in idx:
            if names_agree(nm, gname[j]) or refs_agree(ref, gkeys[j]):
                best = min(best, float(np.hypot(gx[j] - x, gy[j] - y)))
        out[i] = best
    return out


def match_distances(osm: pd.DataFrame, g: pd.DataFrame, xy: np.ndarray | None = None, names: bool = True) -> pd.DataFrame:
    """Per OSM stop: d_compat (compatible, served), d_name (compatible, served, same name/code within the
    name radius), d_any (any served), d_unserved (in the feed but not served on the reference day,
    compatible by any-day modes or in no trip at all)."""
    xy = osm[["x", "y"]].to_numpy() if xy is None else xy
    gxy = g[["x", "y"]].to_numpy()
    out = pd.DataFrame(index=osm.index)
    for c in ("d_compat", "d_name", "d_unserved", "d_name_any"):
        out[c] = np.inf
    srv = g["served"].to_numpy()
    out["d_any"] = nearest(xy, gxy[srv])
    for m in MODES:
        sel = (osm["mode"] == m).to_numpy()
        if not sel.any():
            continue
        flags = COMPAT[m]
        comp = g[[f"s_{f}" for f in flags]].any(axis=1).to_numpy()
        out.loc[sel, "d_compat"] = nearest(xy[sel], gxy[comp])
        anyday = g[[f"a_{f}" for f in flags]].any(axis=1).to_numpy() | ~g["in_any_trip"].to_numpy()
        out.loc[sel, "d_unserved"] = nearest(xy[sel], gxy[~srv & anyday])
        if names:
            rad = NAME_RADIUS["rail" if m == "rail" else "other"]
            out.loc[sel, "d_name"] = name_distance(osm, sel, g, comp & srv, rad)
            if m in RAIL_BOUND:
                out.loc[sel, "d_name_any"] = name_distance(osm, sel, g, srv, NAME_RADIUS["other"])
    return out


def shifted_xy(osm: pd.DataFrame, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0, 2 * np.pi, len(osm))
    u = rng.uniform(0, 1, len(osm))
    lo = np.where(osm["mode"] == "rail", SHIFT["rail"][0], SHIFT["other"][0])
    hi = np.where(osm["mode"] == "rail", SHIFT["rail"][1], SHIFT["other"][1])
    r = lo + u * (hi - lo)
    return osm[["x", "y"]].to_numpy() + np.c_[r * np.cos(ang), r * np.sin(ang)]


def mode_radius(mode: pd.Series, r_bus: float, r_rail: float) -> np.ndarray:
    return np.where(np.asarray(mode) == "rail", r_rail, r_bus).astype(float)


def covered_mask(d: pd.DataFrame, r_bus: float, r_rail: float, *, names: bool = True,
                 replacement: bool = False) -> np.ndarray:
    """Matched at the given radii (strict mode); ``replacement`` adds the all-mode rule for rail-bound stops."""
    r = mode_radius(d["mode"], r_bus, r_rail)
    m = (d["d_compat"] <= r).to_numpy().copy()
    if names:
        m = m | np.isfinite(d["d_name"].to_numpy())
    if replacement:
        rb = d["mode"].isin(RAIL_BOUND).to_numpy()
        m = m | rb &((d["d_any"] <= r_bus).to_numpy() | np.isfinite(d["d_name_any"].to_numpy()))
    return m


def status(o: pd.DataFrame, r_bus: float, r_rail: float) -> pd.Series:
    r = mode_radius(o["mode"], r_bus, r_rail)
    rb = o["mode"].isin(RAIL_BOUND)
    s = np.select(
        [o["d_compat"] <= r, np.isfinite(o["d_name"]),
         rb & ((o["d_any"] <= r_bus) | np.isfinite(o["d_name_any"])),
         o["d_any"] <= r, o["d_unserved"] <= r],
        ["matched", "matched_name", "matched_replacement", "other_mode_only", "in_feed_not_served"], "no_gtfs")
    return pd.Series(s, index=o.index)


# ------------------------------------------------------------------ geography
@lru_cache(maxsize=None)
def agg_geo(agg: str) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = load_agglomeration(agg)
    c = load_config()["agglomerations"][agg]["centre"]
    a["cx"], a["cy"] = _TO2180.transform(c["lon"], c["lat"])
    a["centre_name"] = c["name"]
    lau = load_lau()
    lau = lau[lau.intersects(a["fua"])].copy()
    lau["share_in_fua"] = lau.geometry.intersection(a["fua"]).area / lau.geometry.area
    # town and rural gmina of the same name (Pabianice, Zgierz, ...): the smaller one is the town
    lau["area"] = lau.geometry.area
    dup = lau["LAU_NAME"].duplicated(keep=False)
    rank = lau.groupby("LAU_NAME")["area"].rank(method="first")
    lau.loc[dup, "LAU_NAME"] = lau.loc[dup, "LAU_NAME"] + np.where(rank[dup] == 1, " (miasto)", " (gmina wiejska)")
    a["lau"] = lau[["LAU_ID", "LAU_NAME", "share_in_fua", "geometry"]].reset_index(drop=True)
    return a


def assign_gmina(df: pd.DataFrame, lau: gpd.GeoDataFrame) -> pd.DataFrame:
    pts = gpd.GeoDataFrame(df[[]].copy(), geometry=gpd.points_from_xy(df.x, df.y), crs=CRS_METRIC)
    j = gpd.sjoin(pts, lau[["LAU_ID", "LAU_NAME", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    miss = j["LAU_ID"].isna()
    if miss.any():  # coarse 1:1M coastline / borders: nearest gmina
        n = gpd.sjoin_nearest(pts[miss], lau[["LAU_ID", "LAU_NAME", "geometry"]], how="left")
        n = n[~n.index.duplicated(keep="first")]
        j.loc[miss, ["LAU_ID", "LAU_NAME"]] = n[["LAU_ID", "LAU_NAME"]].to_numpy()
    out = df.copy()
    out["gmina_id"], out["gmina"] = j["LAU_ID"].to_numpy(), j["LAU_NAME"].to_numpy()
    return out


# ------------------------------------------------------------------ per agglomeration
def build(agg: str, r_bus: int, r_rail: int) -> dict:
    a = agg_geo(agg)
    fua, core = a["fua"], a["core"]
    osm, ostats = osm_in(fua, r_rail)
    feeds = feeds_for(agg)
    g = pd.concat([gtfs_points(f) for f in feeds], ignore_index=True)
    big = fua.buffer(2000)
    xmin, ymin, xmax, ymax = big.bounds
    g = g[(g.x >= xmin) & (g.x <= xmax) & (g.y >= ymin) & (g.y <= ymax)]
    g = g[contains_xy(big, g.x.to_numpy(), g.y.to_numpy())].reset_index(drop=True)

    osm = assign_gmina(osm, a["lau"])
    osm["in_core"] = contains_xy(core, osm.x.to_numpy(), osm.y.to_numpy())
    osm["ring_km"] = (np.hypot(osm.x - a["cx"], osm.y - a["cy"]) // 1000).astype(int)
    osm = pd.concat([osm, match_distances(osm, g)], axis=1)
    ch = match_distances(osm, g, shifted_xy(osm, SEED), names=False)
    osm["d_compat_shifted"] = ch["d_compat"].to_numpy()
    osm["status"] = status(osm, r_bus, r_rail)
    osm["covered"] = osm["status"].isin(COVERED)
    osm["agg"] = agg

    # reverse direction: served GTFS units (parent stations + stops without a parent) inside the FUA
    gu = g[g["served"] & ~g["has_parent"]].copy()
    gu = gu[contains_xy(fua, gu.x.to_numpy(), gu.y.to_numpy())].reset_index(drop=True)
    gu["mode"] = gtfs_mode(gu)
    gu["in_core"] = contains_xy(core, gu.x.to_numpy(), gu.y.to_numpy())
    gu = assign_gmina(gu, a["lau"])
    oxy = osm[["x", "y"]].to_numpy()
    gu["d_osm_any"] = nearest(gu[["x", "y"]].to_numpy(), oxy)
    gu["d_osm_compat"] = np.inf
    for m in gu["mode"].unique():
        sel = (gu["mode"] == m).to_numpy()
        om = {"zka": ["rail", "bus"], "other": MODES}.get(m, [m])
        tsel = osm["mode"].isin(om + ["unknown"]).to_numpy()
        gu.loc[sel, "d_osm_compat"] = nearest(gu.loc[sel, ["x", "y"]].to_numpy(), oxy[tsel])
    gu["agg"] = agg
    return {"osm": osm, "gtfs": gu, "ostats": ostats, "feeds": feeds, "geo": a}


# ------------------------------------------------------------------ aggregation
def subset(osm: pd.DataFrame, mode: str) -> pd.DataFrame:
    return osm if mode == "all" else osm[osm["mode"] == mode]


def _cov(d: pd.DataFrame, mode: str, r_bus: float, r_rail: float, **kw) -> float:
    if not len(d):
        return np.nan
    return float(covered_mask(d, r_bus, r_rail, replacement=(mode == "all"), **kw).mean())


def table_by(osm: pd.DataFrame, key: list[str], r_bus: int, r_rail: int) -> pd.DataFrame:
    rows = []
    for mode in REPORT_MODES:
        s = subset(osm, mode)
        for k, d in s.groupby(key, sort=True):
            k = k if isinstance(k, tuple) else (k,)
            row = dict(zip(key, k))
            cov = covered_mask(d, r_bus, r_rail, replacement=(mode == "all"))
            st = d["status"].value_counts()
            row.update({"mode": mode, "n_osm": len(d), "n_covered": int(cov.sum()), "coverage": float(cov.mean()),
                        "coverage_distance_only": _cov(d, mode, r_bus, r_rail, names=False),
                        **{f"n_{s_}": int(st.get(s_, 0)) for s_ in
                           ["matched", "matched_name", "matched_replacement", "other_mode_only",
                            "in_feed_not_served", "no_gtfs"]}})
            for r in radius_list(mode):
                rb, rr = (r_bus, r) if mode == "rail" else (r, r_rail)
                row[f"cov_r{r}"] = _cov(d, mode, rb, rr)
            rows.append(row)
    return pd.DataFrame(rows)


def summary_rows(res: dict, r_bus: int, r_rail: int) -> list[dict]:
    osm, gu, agg = res["osm"], res["gtfs"], res["osm"]["agg"].iloc[0]
    rows = []
    for mode in REPORT_MODES:
        s = subset(osm, mode)
        gs = gu if mode == "all" else gu[gu["mode"].isin([mode] + (["zka"] if mode == "rail" else []))]
        for r in radius_list(mode):
            rb, rr = (r_bus, r) if mode == "rail" else (r, r_rail)
            row = {"agg": agg, "mode": mode, "radius_m": r, "rail_radius_m": rr if mode != "bus" and mode != "tram" else None,
                   "recommended": bool(r == (r_rail if mode == "rail" else r_bus))}
            for area, sel in (("fua", np.ones(len(s), bool)), ("core", s["in_core"].to_numpy()),
                              ("outside", ~s["in_core"].to_numpy())):
                d = s[sel]
                row[f"n_osm_{area}"] = len(d)
                row[f"cov_{area}"] = _cov(d, mode, rb, rr)
                row[f"cov_dist_{area}"] = _cov(d, mode, rb, rr, names=False)
            rad = mode_radius(s["mode"], rb, rr)
            row["cov_chance_fua"] = float((s["d_compat_shifted"] <= rad).mean()) if len(s) else np.nan
            row["cov_any_mode_fua"] = float((s["d_any"] <= rad).mean()) if len(s) else np.nan
            grad = np.where(gs["mode"].isin(["rail", "zka"]), rr, rb)
            row["n_gtfs_served"] = len(gs)
            row["n_gtfs_without_osm"] = int((gs["d_osm_compat"] > grad).sum())
            row["share_gtfs_without_osm"] = row["n_gtfs_without_osm"] / len(gs) if len(gs) else np.nan
            rows.append(row)
    return rows


def gmina_class(cov: float, n: int) -> str:
    if n < GMINA_MIN_N:
        return "small_n"
    if cov >= GMINA_WELL:
        return "well"
    if cov < GMINA_POOR:
        return "poor"
    return "mixed"


_LEGAL = re.compile(r"\b(sp\.? ?z ?o\.? ?o\.?|s\.? ?a\.?|sp\.? ?j\.?|sp\.? ?k\.?|spółka z ograniczoną odpowiedzialnością|"
                    r"spółka jawna|spółka akcyjna)(?=\s|$|[,.;])")


def norm_tag(v) -> str:
    if not isinstance(v, str) or not v.strip():
        return ""
    s = unicodedata.normalize("NFC", v).casefold()
    s = re.sub(r"[\"„”“'`]", "", s)
    s = _LEGAL.sub("", s)
    s = re.sub(r"[\s,.]+", " ", s).strip(" -;")
    s = ";".join(sorted(p.strip() for p in s.split(";") if p.strip()))
    return s


def tag_frame(d: pd.DataFrame) -> pd.DataFrame:
    has_net = d["network"].fillna("").str.strip() != ""
    has_op = d["operator"].fillna("").str.strip() != ""
    raw = d["network"].where(has_net, d["operator"])
    out = pd.DataFrame(index=d.index)
    out["tag"] = raw.map(norm_tag).replace("", "(brak tagu)")
    out["tag_label"] = raw.fillna("(brak tagu)")
    out["tag_src"] = np.where(has_net, "network", np.where(has_op, "operator", ""))
    return out


def operator_table(osm: pd.DataFrame, gm: pd.DataFrame) -> pd.DataFrame:
    """Uncovered OSM stops by normalised network (fallback: operator) tag."""
    d = pd.concat([osm, tag_frame(osm)], axis=1)
    cls = gm[gm["mode"] == "all"].set_index(["agg", "gmina_id"])["gmina_class"]
    d["gmina_class"] = [cls.get((a, g), "small_n") for a, g in zip(d["agg"], d["gmina_id"])]
    rows = []
    for (agg, tag), t in d.groupby(["agg", "tag"], sort=True):
        un = t[~t["covered"]]
        if un.empty:
            continue
        top = un.groupby("gmina").size().sort_values(ascending=False, kind="stable")
        lab = t["tag_label"].value_counts()
        lab = lab[lab == lab.max()].sort_index().index[0]
        rows.append({
            "agg": agg, "tag": tag, "tag_label": lab,
            "tag_source": ";".join(sorted(set(t["tag_src"]) - {""})),
            "n_uncovered": len(un), "n_covered": int(t["covered"].sum()),
            "n_uncovered_poor_gmina": int((un["gmina_class"] == "poor").sum()),
            "n_uncovered_mixed_gmina": int((un["gmina_class"] == "mixed").sum()),
            "n_uncovered_well_gmina": int((un["gmina_class"] == "well").sum()),
            "n_uncovered_small_gmina": int((un["gmina_class"] == "small_n").sum()),
            "n_uncovered_in_core": int(un["in_core"].sum()),
            "n_uncovered_in_feed_not_served": int((un["status"] == "in_feed_not_served").sum()),
            "modes": ";".join(f"{k}:{v}" for k, v in un["mode"].value_counts().sort_index().items()),
            "top_gminas": "; ".join(f"{k} ({v})" for k, v in top.head(4).items()),
        })
    out = pd.DataFrame(rows)
    return out.sort_values(["agg", "n_uncovered", "tag"], ascending=[True, False, True]).reset_index(drop=True)


def gtfs_without_osm(gu: pd.DataFrame, r_bus: int, r_rail: int) -> pd.DataFrame:
    gw = gu.assign(area=np.where(gu["in_core"], "core", "outside"))
    rows = []
    for (agg, feed, mode, area), d in gw.groupby(["agg", "feed", "mode", "area"], sort=True):
        rail = mode in ("rail", "zka")
        rr = r_rail if rail else r_bus
        row = {"agg": agg, "feed": feed, "mode": mode, "area": area, "n_served": len(d),
               "n_events_ref_day": int(d["n_events"].sum())}
        for r in (RAIL_RADII if rail else BUS_RADII):
            row[f"n_without_osm_r{r}"] = int((d["d_osm_compat"] > r).sum())
        row["n_without_osm_any_mode"] = int((d["d_osm_any"] > rr).sum())
        row["share_without_osm"] = row[f"n_without_osm_r{rr}"] / len(d)
        row["median_d_osm_m"] = float(np.median(d["d_osm_compat"]))
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ population (preliminary)
@lru_cache(maxsize=1)
def nsp_points() -> pd.DataFrame:
    g = gpd.read_file(NSP_SHP)[["RES", "geometry"]].to_crs(CRS_METRIC)
    c = g.geometry.centroid
    return pd.DataFrame({"RES": g["RES"].astype(float).to_numpy(), "x": c.x.to_numpy(), "y": c.y.to_numpy()})


def population(res: dict, gm: pd.DataFrame) -> dict:
    a, osm = res["geo"], res["osm"]
    agg = osm["agg"].iloc[0]
    p = nsp_points()
    p = p[contains_xy(a["fua"], p.x.to_numpy(), p.y.to_numpy())].reset_index(drop=True)
    p = assign_gmina(p, a["lau"])
    p["in_core"] = contains_xy(a["core"], p.x.to_numpy(), p.y.to_numpy())
    total = p["RES"].sum()
    cov = gm[(gm["mode"] == "all") & (gm["agg"] == agg)].set_index("gmina_id")
    p["gcov"] = p["gmina_id"].map(cov["coverage"])
    p["gn"] = p["gmina_id"].map(cov["n_osm"]).fillna(0)
    out = {"agg": agg, "nsp_pop_fua": int(round(total)), "nsp_pop_core_share": p.loc[p["in_core"], "RES"].sum() / total,
           "gmina_pop_share_no_osm_stops": p.loc[p["gn"] == 0, "RES"].sum() / total}
    for t in POP_THRESHOLDS:
        out[f"gmina_pop_share_cov_ge_{int(t * 100)}"] = p.loc[p["gcov"] >= t, "RES"].sum() / total
    # local variant: share of OSM stops within 1 km of the 1 km cell centroid that are covered
    tree = cKDTree(osm[["x", "y"]].to_numpy())
    covered = osm["covered"].to_numpy()
    nb = tree.query_ball_point(p[["x", "y"]].to_numpy(), LOCAL_RADIUS_M)
    n = np.array([len(i) for i in nb])
    m = np.array([covered[i].sum() if len(i) else 0 for i in nb])
    lc = np.where(n > 0, m / np.maximum(n, 1), np.nan)
    out["cell_pop_share_no_osm_stop_1km"] = p.loc[n == 0, "RES"].sum() / total
    for t in POP_THRESHOLDS:
        out[f"cell_pop_share_cov_ge_{int(t * 100)}"] = p.loc[lc >= t, "RES"].sum() / total
    return out


# ------------------------------------------------------------------ plots
BLUE, ORANGE, GREY, INK = "#2a78d6", "#eb6834", "#c9c7bf", "#52514e"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_map(res: dict, r_bus: int, r_rail: int) -> None:
    plt = _plt()
    a, osm = res["geo"], res["osm"]
    agg = osm["agg"].iloc[0]
    fig, ax = plt.subplots(figsize=(9, 9), dpi=130)
    gpd.GeoSeries(list(a["lau"].geometry), crs=CRS_METRIC).boundary.plot(ax=ax, color=GREY, lw=0.5)
    gpd.GeoSeries([a["fua"]], crs=CRS_METRIC).boundary.plot(ax=ax, color=INK, lw=1.0)
    gpd.GeoSeries([a["core"]], crs=CRS_METRIC).boundary.plot(ax=ax, color=INK, lw=0.8, ls="--")
    m = osm["covered"].to_numpy()
    ax.scatter(osm.x[m], osm.y[m], s=1.5, c=BLUE, lw=0, label=f"z odpowiednikiem w GTFS ({m.sum()})")
    ax.scatter(osm.x[~m], osm.y[~m], s=4, c=ORANGE, lw=0, label=f"bez odpowiednika ({(~m).sum()})")
    ax.plot([a["cx"]], [a["cy"]], marker="+", color=INK, ms=10)
    xmin, ymin, xmax, ymax = a["fua"].bounds
    ax.set_xlim(xmin - 2000, xmax + 2000)
    ax.set_ylim(ymin - 2000, ymax + 2000)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for s in ax.spines.values():
        s.set_visible(False)
    var = f", wariant granicy {a['variant']}" if a.get("variant") else ""
    ax.set_title(f"{a['name']}: przystanki OSM (stan 2026-11-22) a GTFS z dnia {ref_day():%Y-%m-%d}{var}\n"
                 f"promień {r_bus} m (kolej {r_rail} m) + zgodna nazwa/kod do {NAME_RADIUS['other']} m; "
                 "ciągła linia: FUA, przerywana: rdzeń, szare: gminy LAU 2021, +: centrum",
                 fontsize=8, color=INK, loc="left")
    ax.legend(loc="lower left", fontsize=8, frameon=False, markerscale=4)
    fig.tight_layout()
    fig.savefig(OUT / f"map_{agg}.png")
    plt.close(fig)


def plot_hist(res: dict, r_bus: int, r_rail: int) -> None:
    plt = _plt()
    osm = res["osm"]
    agg, name = osm["agg"].iloc[0], res["geo"]["name"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), dpi=130)
    for ax, mode in zip(axes, ["bus", "tram", "rail"]):
        d = osm[osm["mode"] == mode]
        hi, step = (1000, 20) if mode == "rail" else (300, 5)
        bins = np.arange(0, hi + step, step)
        ax.hist(d["d_compat"].clip(upper=hi), bins=bins, color=BLUE, label="przystanki OSM")
        ax.hist(d["d_compat_shifted"].clip(upper=hi), bins=bins, histtype="step", color=ORANGE, lw=1.2,
                label="kontrola: OSM przesunięte losowo")
        for r in radius_list(mode):
            ax.axvline(r, color=INK, lw=0.7, ls="-" if r == (r_rail if mode == "rail" else r_bus) else ":")
        ax.set_title(f"{MODE_PL[mode]} (n={len(d)}); ostatni słupek: ≥{hi} m lub brak", fontsize=8, color=INK, loc="left")
        ax.set_xlabel("odległość do najbliższego obsłużonego przystanku GTFS zgodnego trybu [m]", fontsize=7, color=INK)
        ax.tick_params(labelsize=7, colors=INK)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].legend(fontsize=7, frameon=False)
    fig.suptitle(f"{name}: odległość OSM → GTFS, dzień {ref_day():%Y-%m-%d}; pionowe linie: badane promienie "
                 "(ciągła = przyjęty)", fontsize=9, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT / f"nn_hist_{agg}.png")
    plt.close(fig)


# ------------------------------------------------------------------ report (Polish)
def pct(v, nd: int = 1) -> str:
    return "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{100 * v:.{nd}f}%".replace(".", ",")


def num(v) -> str:
    return f"{int(v):,}".replace(",", " ")


def md_table(df: pd.DataFrame, cols: dict[str, str]) -> str:
    h = "| " + " | ".join(cols.values()) + " |\n|" + "---|" * len(cols) + "\n"
    return h + "".join("| " + " | ".join(str(r[c]) for c in cols) + " |\n" for _, r in df.iterrows())


def _note(key: str, **kw) -> str:
    t = NOTES[key].strip()
    return "\n\n" + (t.format(**kw) if kw else t) + "\n\n"


def write_report(ctx: dict) -> None:
    sm, gm, rg, ops, pop, gwo = ctx["sm"], ctx["gm"], ctx["rg"], ctx["ops"], ctx["pop"], ctx["gwo"]
    r_bus, r_rail = ctx["r_bus"], ctx["r_rail"]
    names = {a: ctx["results"][a]["geo"]["name"] for a in AGGS}
    L = []
    L.append(f"# Wstępne pokrycie danymi GTFS (przystanki OSM ↔ GTFS)\n\n"
             f"Faza 0, krok `python -m pipeline.stop_coverage` (brief §6). **Wynik wstępny**: maska pokrycia właściwa "
             f"powstaje w fazie 2. Dzień referencyjny rozkładów: **{ref_day():%Y-%m-%d} (śr)**; stan OSM: "
             f"**2026-11-22**; ludność: **NSP 2021** (siatka 1 km, stan 31.03.2021). GZM w wariancie granicy "
             f"**{ctx['results']['gzm']['geo']['variant']}** (prowizoryczny „suma czterech FUA”; decyzja Bartora w toku).\n")
    L.append(_note("summary"))
    L.append("## Metoda\n")
    L.append(_note("method", r_bus=r_bus, r_rail=r_rail, nr=NAME_RADIUS["other"], nrr=NAME_RADIUS["rail"]))
    # radius decision
    L.append("## Wybór promienia i wrażliwość\n")
    L.append(_note("radius", r_bus=r_bus, r_rail=r_rail))
    for mode in ["bus", "tram", "rail"]:
        t = sm[sm["mode"] == mode].copy()
        piv = t.pivot(index="agg", columns="radius_m", values="cov_dist_fua").reindex(AGGS)
        ch = t.pivot(index="agg", columns="radius_m", values="cov_chance_fua").reindex(AGGS)
        nm = t.pivot(index="agg", columns="radius_m", values="cov_fua").reindex(AGGS)
        L.append(f"\n**{MODE_PL[mode]}**: pokrycie FUA wg samej odległości (w nawiasie: dopasowania przypadkowe "
                 f"z kontroli przesunięcia); ostatnia kolumna: przy przyjętym promieniu z dopasowaniem po nazwie/kodzie.\n\n")
        cols = list(piv.columns)
        rr = r_rail if mode == "rail" else r_bus
        L.append("| Aglomeracja | n | " + " | ".join(f"{c} m" for c in cols) + f" | {rr} m + nazwa/kod |\n")
        L.append("|---|---|" + "---|" * (len(cols) + 1) + "\n")
        for a in AGGS:
            n = int(t[(t["agg"] == a)]["n_osm_fua"].iloc[0])
            cells = [f"{pct(piv.loc[a, c])} ({pct(ch.loc[a, c], 1)})" for c in cols]
            L.append(f"| {names[a]} | {n} | " + " | ".join(cells) + f" | **{pct(nm.loc[a, rr])}** |\n")
    L.append("\nHistogramy odległości: `nn_hist_<aglomeracja>.png`.\n")
    # main table
    L.append("\n## Pokrycie: FUA, rdzeń, poza rdzeniem\n")
    L.append(f"Przyjęte promienie: {r_bus} m (autobus, tramwaj, metro, peron nieokreślony), {r_rail} m (kolej), "
             f"plus dopasowanie po nazwie/kodzie. „Wszystkie” = maska (tramwaj/kolej z przystankiem zastępczym innego "
             f"trybu liczone jako pokryte). W nawiasach liczba przystanków OSM (mianownik).\n\n")
    rec = sm[sm["recommended"]]
    L.append("| Aglomeracja | tryb | FUA | rdzeń | poza rdzeniem | GTFS bez OSM |\n|---|---|---|---|---|---|\n")
    for a in AGGS:
        for mode in REPORT_MODES:
            r = rec[(rec["agg"] == a) & (rec["mode"] == mode)].iloc[0]
            L.append(f"| {names[a]} | {MODE_PL[mode]} | {pct(r.cov_fua)} ({num(r.n_osm_fua)}) | "
                     f"{pct(r.cov_core)} ({num(r.n_osm_core)}) | {pct(r.cov_outside)} ({num(r.n_osm_outside)}) | "
                     f"{pct(r.share_gtfs_without_osm)} ({num(r.n_gtfs_without_osm)} z {num(r.n_gtfs_served)}) |\n")
    L.append("\n" + _note("main_table") + "\n")
    # status breakdown
    L.append("\n### Dlaczego przystanek nie ma odpowiednika (wszystkie tryby, FUA)\n\n")
    st = gm[gm["mode"] == "all"].groupby("agg")[["n_osm", "n_matched", "n_matched_name", "n_matched_replacement",
                                                  "n_other_mode_only", "n_in_feed_not_served", "n_no_gtfs"]].sum()
    L.append("| Aglomeracja | OSM | odległość | nazwa/kod | zastępczy | tylko inny tryb | w feedzie, nieobsł. w dniu ref. | brak w GTFS |\n"
             "|---|---|---|---|---|---|---|---|\n")
    for a in AGGS:
        r = st.loc[a]
        L.append(f"| {names[a]} | {num(r.n_osm)} | {num(r.n_matched)} | {num(r.n_matched_name)} | "
                 f"{num(r.n_matched_replacement)} | {num(r.n_other_mode_only)} | {num(r.n_in_feed_not_served)} | {num(r.n_no_gtfs)} |\n")
    # rings
    L.append("\n## Pokrycie wg odległości od centrum (pasy 5 km, wszystkie tryby)\n\n")
    ra = rg[rg["mode"] == "all"].copy()
    ra["band"] = (ra["ring_km"] // 5) * 5
    b = ra.groupby(["agg", "band"])[["n_osm", "n_covered"]].sum().reset_index()
    bands = sorted(b["band"].unique())
    bands = [x for x in bands if x < 40]
    L.append("| Aglomeracja | " + " | ".join(f"{x}–{x + 5} km" for x in bands) + " | ≥40 km |\n|---|" + "---|" * (len(bands) + 1) + "\n")
    for a in AGGS:
        cells = []
        for x in bands:
            r = b[(b["agg"] == a) & (b.band == x)]
            cells.append("–" if r.empty else f"{pct(r.n_covered.iloc[0] / r.n_osm.iloc[0], 0)} ({r.n_osm.iloc[0]})")
        r = b[(b["agg"] == a) & (b.band >= 40)]
        cells.append("–" if r.empty or r.n_osm.sum() == 0 else f"{pct(r.n_covered.sum() / r.n_osm.sum(), 0)} ({r.n_osm.sum()})")
        L.append(f"| {names[a]} | " + " | ".join(cells) + " |\n")
    L.append(f"\nCentra: {', '.join(f'{names[a]}: {ctx['results'][a]['geo']['centre_name']}' for a in AGGS)}. "
             "Trójmiasto i GZM są policentryczne; pierścienie od jednego centrum są tu tylko orientacyjne. "
             "Pełne dane (pierścienie 1 km, wszystkie tryby, promienie): `coverage_by_ring.csv`.\n")
    # gminas
    L.append("\n## Gminy\n\n")
    L.append(_note("gminas"))
    ga = gm[gm["mode"] == "all"].copy()
    for a in AGGS:
        t = ga[ga["agg"] == a].sort_values(["coverage", "n_osm"], ascending=[True, False])
        t = t[t.n_osm >= GMINA_MIN_N]
        L.append(f"\n**{names[a]}** ({len(ga[ga['agg'] == a])} gmin z przystankami OSM; poniżej {GMINA_MIN_N} przystanków: "
                 f"{int((ga[ga['agg'] == a].n_osm < GMINA_MIN_N).sum())}). Najsłabiej pokryte (≥ {GMINA_MIN_N} przystanków):\n\n")
        tt = t.head(10).assign(c=lambda x: x.coverage.map(pct), n=lambda x: x.n_osm.astype(int),
                               sh=lambda x: x.lau_area_share_in_fua.map(lambda v: pct(v, 0)))
        L.append(md_table(tt, {"gmina": "Gmina", "n": "OSM", "c": "pokrycie", "n_no_gtfs": "brak w GTFS",
                               "sh": "udział pow. gminy w FUA"}))
    # operators
    L.append("\n## Kto brakuje: tagi `network` / `operator` przystanków bez odpowiednika\n\n")
    L.append(_note("operators", well=pct(GMINA_WELL, 0), poor=pct(GMINA_POOR, 0)))
    for a in AGGS:
        t = ops[ops["agg"] == a].head(12)
        L.append(f"\n**{names[a]}**\n\n")
        L.append(md_table(t, {"tag_label": "tag (najczęstszy zapis)", "n_uncovered": "bez odp.",
                              "n_covered": "z odp.", "n_uncovered_poor_gmina": "w gminach słabo pokrytych",
                              "n_uncovered_well_gmina": "w gminach dobrze pokrytych", "top_gminas": "gdzie"}))
    L.append("\n" + _note("carriers") + "\n")
    # GTFS without OSM
    L.append("\n## Kierunek odwrotny: przystanki GTFS bez przystanku OSM\n\n")
    L.append(_note("reverse"))
    t = gwo.copy()
    t["rr"] = np.where(t["mode"].isin(["rail", "zka"]), r_rail, r_bus)
    t["n_wo"] = [int(r[f"n_without_osm_r{rr}"]) for rr, (_, r) in zip(t["rr"], t.iterrows())]
    t2 = t.groupby(["agg", "mode"])[["n_served", "n_wo", "n_without_osm_any_mode"]].sum().reset_index()
    t2 = t2[t2.n_served >= 5]
    t2["share"] = (t2.n_wo / t2.n_served).map(pct)
    t2["agg"] = t2["agg"].map(names)
    t2["mode"] = t2["mode"].map(lambda m: MODE_PL.get(m, {"zka": "ZKA (autobus zastępczy kolei)", "other": "inne",
                                                          "trolleybus": "trolejbus"}.get(m, m)))
    L.append(md_table(t2, {"agg": "Aglomeracja", "mode": "tryb GTFS", "n_served": "obsłużone w dniu ref.",
                           "n_wo": "bez OSM zgodnego trybu", "share": "udział",
                           "n_without_osm_any_mode": "bez żadnego OSM"}))
    # population
    L.append("\n## Ludność w obszarze pokrytym: pierwsze przybliżenie (WSTĘPNE)\n\n")
    L.append(_note("population", thr=", ".join(pct(t, 0) for t in POP_THRESHOLDS)))
    p = pop.set_index("agg").reindex(AGGS)
    hdr = ("| Aglomeracja | ludność FUA (NSP 2021) | w rdzeniu | " +
           " | ".join(f"gminy ≥{int(t * 100)}%" for t in POP_THRESHOLDS) + " | gminy bez przyst. OSM | " +
           " | ".join(f"komórki ≥{int(t * 100)}%" for t in POP_THRESHOLDS) + " | komórki bez przyst. OSM w 1 km |\n")
    L.append(hdr + "|---|" + "---|" * (4 + 2 * len(POP_THRESHOLDS)) + "\n")
    for a in AGGS:
        r = p.loc[a]
        L.append(f"| {names[a]} | {num(r.nsp_pop_fua)} | {pct(r.nsp_pop_core_share)} | " +
                 " | ".join(pct(r[f"gmina_pop_share_cov_ge_{int(t * 100)}"]) for t in POP_THRESHOLDS) +
                 f" | {pct(r.gmina_pop_share_no_osm_stops)} | " +
                 " | ".join(pct(r[f"cell_pop_share_cov_ge_{int(t * 100)}"]) for t in POP_THRESHOLDS) +
                 f" | {pct(r.cell_pop_share_no_osm_stop_1km)} |\n")
    L.append("\n" + _note("population_after") + "\n")
    L.append("\n## Zaniżenie przez brak przewoźników podmiejskich\n\n")
    L.append("| Aglomeracja | ludność FUA w gminach z pokryciem < 50% | ludność FUA w gminach z pokryciem < 85% | "
             "przystanki OSM bez odp. w gminach słabo pokrytych | główni nazwani przewoźnicy bez GTFS (przystanki bez odp.) |\n"
             "|---|---|---|---|---|\n")
    for a in AGGS:
        r = p.loc[a]
        o = ops[(ops["agg"] == a) & (ops.tag != "(brak tagu)") & ~ops.tag.str.fullmatch(r"[\d ,;]+") & (ops.n_uncovered > ops.n_covered)].head(4)
        poor = int(ops.loc[ops["agg"] == a, "n_uncovered_poor_gmina"].sum())
        L.append(f"| {names[a]} | {pct(1 - r.gmina_pop_share_cov_ge_50 - r.gmina_pop_share_no_osm_stops)} | "
                 f"{pct(1 - r.gmina_pop_share_cov_ge_85 - r.gmina_pop_share_no_osm_stops)} | {num(poor)} | "
                 + "; ".join(f"{t} ({n})" for t, n in zip(o.tag_label, o.n_uncovered)) + " |\n")
    L.append("\n" + _note("understated") + "\n")
    L.append("\n## Ograniczenia\n\n" + _note("limitations") + "\n")
    L.append("\n## Pliki\n\n" + _note("files") + "\n")
    L.append("\n## Propozycje do `config.yaml`\n\n" + _note("config", r_rail=r_rail) + "\n")
    text = re.sub(r"\n{3,}", "\n\n", "".join(L)).rstrip() + "\n"
    (OUT / "coverage.md").write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ hand-written report text (Polish)
# Interpretation written after reviewing the run on the 2026-11-25 reference day / OSM 2026-11-22.
# Tables in the report are generated; re-check these paragraphs whenever the inputs change.
NOTES = {
    "summary": """
## W skrócie

- **Rdzenie są pokryte dobrze** (95–98% przystanków OSM w rdzeniu ma odpowiednik w GTFS, we wszystkich siedmiu
  aglomeracjach). Braki w rdzeniach to w dużej części przystanki z tagiem sieci miejskiej (np. ok. 90 przystanków
  „ZTM Warszawa” w Warszawie), czyli chwilowo nieobsługiwane, przesunięte albo nieaktualne w OSM, oraz pojedyncze
  przystanki przewoźników regionalnych (np. „MDA” w Krakowie). Żadne miasto-rdzeń nie wypada podejrzanie nisko.
- **Poza rdzeniem pokrycie jest bardzo nierówne**: GZM ok. 89% i Poznań ok. 79% (zarządy transportu obejmują
  większość gmin FUA), pozostałe pięć aglomeracji tylko 30–37%. W Warszawie, Krakowie, Łodzi, Trójmieście
  i we Wrocławiu feedy GTFS nie zawierają gminnych i prywatnych przewoźników podmiejskich.
- **Wstępnie**: przy progu 85% pokrycia gminy obszar pokryty obejmuje ok. 60–75% ludności FUA w pięciu „słabych”
  aglomeracjach, 87% w Poznaniu i 96% w GZM. Według reguły z §6 wyniki transportowe dla FUA Warszawy, Krakowa,
  Łodzi, Wrocławia i Trójmiasta będą oznaczone jako niepełne; do porównań trzeba będzie użyć wariantu „obszar
  pokryty” albo „rdzeń”.
- **Promień**: 50 m dla autobusu/tramwaju zostaje, ale z dopasowaniem pomocniczym po nazwie lub kodzie przystanku
  (do 200 m); dla kolei 200 m. Z dopasowaniem po nazwie wynik prawie nie zależy od promienia (zmiana o 1–2,5 pkt
  proc. między 30 a 150 m), więc wybór 50 m nie przesądza o wnioskach.
""",
    "method": """
1. **GTFS.** Feedy przypisane aglomeracji w `config.yaml` plus `polish_trains` (dla Warszawy także `warsaw_wkd`).
   Przystanek GTFS jest „obsłużony”, jeśli w dniu referencyjnym zatrzymuje się na nim co najmniej jeden kurs
   (`calendar` + `calendar_dates`). Każdy przystanek dostaje zbiór klas tras, które go obsługują (`route_type`:
   autobus i trolejbus = autobus; tramwaj; kolej; metro; prom). Autobusy w `polish_trains` (`route_type` 3) to
   komunikacja zastępcza kolei (ZKA): obsługują stację kolejową, ale nie sieć autobusową. Stacje nadrzędne
   (`location_type` = 1, w `polish_trains` i `warsaw_ztm`) dziedziczą tryby i kursy swoich peronów, bo węzeł OSM
   `railway=station` leży w środku stacji, a punkty GTFS bywają peronami. Przystanki obecne w `stops.txt`, ale
   nieobsłużone w dniu ref., są trzymane osobno (kategoria „w feedzie, nieobsłużony”). Duplikaty kursów
   (GZM, SKM Warszawa) nie mają znaczenia dla obecności przystanku.
2. **OSM.** Przystanki po deduplikacji (`data/interim/osm/stops_dedup.parquet`, reguły w
   `results/qa/phase0/osm/osm_stops.md`) wewnątrz FUA. Kolej: perony OSM w promieniu {r_rail} m od stacji OSM
   są wchłaniane przez stację (jedna stacja = jedna jednostka); perony „sieroce” (bez stacji w pobliżu) dostają
   tryb nieokreślony, bo przegląd pokazał, że to w dużej części perony tramwajowe i autobusowe oznaczone
   `railway=platform` (np. w Krakowie i Łodzi). Stacje kolei turystycznych, drezynowych, wąskotorowych,
   parkowej Maltanki i kolejki na Kamienną Górę są wyłączone z mianownika (reguła po nazwie i operatorze).
3. **Dopasowanie** w EPSG:2180 (KD-drzewo), z **zgodnością trybu**: przystanek autobusowy OSM tylko do autobusu
   lub trolejbusu GTFS, tramwajowy tylko do tramwaju, stacja kolejowa do kolei (także ZKA), metro do metra; peron
   o nieokreślonym trybie do czegokolwiek. Przystanek OSM ma odpowiednik, jeśli (a) obsłużony przystanek GTFS
   zgodnego trybu leży w promieniu odległości ({r_bus} m; kolej {r_rail} m), albo (b) w promieniu {nr} m (kolej
   {nrr} m) leży obsłużony przystanek zgodnego trybu o tej samej znormalizowanej nazwie (bez numeru słupka i
   oznaczeń „nż”) albo o tym samym kodzie (`ref` w OSM = `stop_id`/`stop_code` w GTFS, kody ≥ 4 znaki).
4. **Maska (tryb „wszystkie”).** Przystanek tramwajowy, kolejowy lub metra, przy którym (≤ {r_bus} m albo ta sama
   nazwa ≤ {nr} m) jest obsłużony przystanek innego trybu, liczy się jako pokryty („zastępczy”): w dniu ref.
   na części tras tramwajowych w Krakowie i Łodzi tramwaj nie kursuje, a tuż przy przystankach są obsłużone
   przystanki autobusowe (wniosek z danych, zapewne autobusy zastępcze w czasie remontu; przyczyn nie
   sprawdzano). Obszar ma więc dane rozkładowe. Wskaźniki per tryb pozostają ścisłe.
5. **Kontrola przypadkowych dopasowań.** Dopasowanie po samej odległości powtórzone dla punktów OSM przesuniętych
   o losowy wektor (stałe ziarno; 200–400 m dla autobusu i tramwaju, 1000–1500 m dla kolei). Odsetek takich
   „trafień” pokazuje, ile dopasowań dany promień daje przypadkiem przy lokalnej gęstości przystanków GTFS.
6. **Agregacja.** Wskaźnik = % przystanków OSM z odpowiednikiem, per gmina (LAU 2021, przypisanie punktu do
   wielokąta; poza wielokątami 1:1M najbliższa gmina), per pierścień 1 km od centrum, per tryb; rdzeń = miasto(a)
   URAU (Trójmiasto + Sopot). Zawsze z liczbą przystanków (mianownik).
""",
    "radius": """
Badane promienie: 30 / 50 / 75 / 100 / 150 m (autobus, tramwaj) i 100 / 200 / 300 / 500 m (kolej).

- **Autobus.** Rozkład odległości do najbliższego przystanku GTFS jest wyraźnie dwumodalny: ostry szczyt poniżej
  ~20 m (ten sam słupek) i długi ogon setek metrów do kilometrów (przystanki bez odpowiednika). Między 50 a 150 m
  pokrycie po samej odległości rośnie o 2–7 pkt proc., ale kontrola przesunięcia pokazuje, że przypadkowe trafienia
  rosną tam z ~3% do ~20%: duża część „zysku” z większego promienia to łapanie sąsiedniego, innego przystanku.
  Przy 50 m odsetek przypadkowy wynosi ok. 2–4%. Część prawdziwych par jest jednak oddalona o 50–150 m (inne
  położenie słupka w OSM i w bazie przewoźnika, zwłaszcza w Poznaniu i Wrocławiu), dlatego dopasowanie
  pomocnicze po nazwie/kodzie do 200 m. Z nim pokrycie zmienia się między 30 a 150 m tylko o 1–2,5 pkt proc.
- **Tramwaj.** Węzeł `railway=tram_stop` leży na torze, punkt GTFS często przy krawędzi peronu: 30 m gubi 1–5 pkt
  proc. prawdziwych par, 50 m łapie prawie wszystko, a powyżej rośnie już głównie składnik przypadkowy.
- **Kolej.** Wbrew obawom z briefu punkty GTFS stacji (`polish_trains`: stacja nadrzędna i perony) leżą zwykle
  blisko węzła OSM: mediana kilkunastu metrów, pokrycie po odległości nasyca się przy 150–200 m; 300 i 500 m
  nic istotnego nie dodają, a zwiększają ryzyko przypisania stacji nieczynnej linii do czynnej stacji obok.
  Wyjątki (Rzozów Centrum, Żukowo, Borkowo, Rębiechowo: punkt GTFS 350–640 m od węzła OSM; w Żukowie i Borkowie
  w dniu ref. tylko ZKA) łapie dopasowanie po nazwie do 500 m. **Rekomendacja: {r_rail} m + nazwa do 500 m**;
  wrażliwość w tabeli niżej (300 m daje ten sam wynik).
- **Rekomendacja ogólna:** zostawić `osm_gtfs_match_radius_m: {r_bus}` i dodać dopasowanie po nazwie/kodzie.
""",
    "main_table": """
„GTFS bez OSM” = obsłużone w dniu ref. przystanki GTFS w FUA (stacje nadrzędne zamiast peronów), przy których nie ma
przystanku OSM zgodnego trybu w tym samym promieniu (bez dopasowania po nazwie). To dolne oszacowanie braków OSM
(szczegóły niżej). Wskaźnik kolejowy liczony po wyłączeniu kolei turystycznych i peronów-sierot (te są w „wszystkie”
jako perony o nieokreślonym trybie).
""",
    "gminas": f"""
Pełna tabela: `coverage_by_gmina.csv` (wszystkie tryby, promienie, liczniki przyczyn, udział powierzchni gminy w FUA,
klasa gminy). Klasa gminy (wszystkie tryby): **dobrze** ≥ {int(GMINA_WELL * 100)}%, **słabo** < {int(GMINA_POOR * 100)}%,
pośrodku **mieszana**; gminy z mniej niż {GMINA_MIN_N} przystankami OSM: **mało danych** (wskaźnik niemiarodajny).
Gminy o tej samej nazwie (miasto i gmina wiejska, np. Pabianice, Zgierz, Mińsk Mazowiecki) mają dopisek „(miasto)”
lub „(gmina wiejska)”: mniejsza powierzchniowo to miasto.
""",
    "operators": """
Przystanki OSM bez odpowiednika pogrupowane po tagu `network` (gdy brak: `operator`), znormalizowanym (wielkość liter,
cudzysłowy, formy prawne, kolejność wartości rozdzielonych `;`). Kolumny „w gminach słabo/dobrze pokrytych” rozdzielają
dwa różne zjawiska: brak odpowiednika **w gminie słabo pokrytej** (< {poor}) to zwykle brakujący przewoźnik, a **w gminie
dobrze pokrytej** (≥ {well}) to raczej przystanek chwilowo nieobsługiwany, nieczynny, szkolny, przesunięty albo szum
mapowania. Pełna tabela: `unmatched_operators.csv`.

**Uwaga:** większość przystanków bez odpowiednika nie ma w OSM ani `network`, ani `operator` („brak tagu”); tagi
nazywają więc przewoźników tylko tam, gdzie mapujący je wpisali. Tagi liczbowe (np. „3, 16” w Wejherowie) to numery
linii wpisane w złe pole.
""",
    "carriers": """
**Brakujący przewoźnicy (interpretacja; dostępność ich GTFS niesprawdzona):**

- **Warszawa:** Grodziskie Przewozy Autobusowe (Grodzisk Maz., Żabia Wola, Błonie), PKS Grójec (Tarczyn, Prażmów,
  Chynów), Nadwiślańska Komunikacja Autobusowa (Góra Kalwaria, Karczew), Bezpłatna Komunikacja Miejska w Otwocku,
  Pruszkowska Komunikacja Miejska, Nowodworska Komunikacja Autobusowa, linie powiatu legionowskiego i DKM Legionowo,
  UTJ Wołoszka, komunikacja w Pułtusku; bez tagów: Mińsk Maz., Błonie, Brwinów, Żyrardów, Milanówek, Serock.
  Te gminy mają kolej (KM, WKD, SKM: stacje dopasowane), brakuje dowozowych autobusów. Przystanki z tagiem
  „ZTM Warszawa” bez odpowiednika poza Warszawą (np. Sulejówek) to zapewne zlikwidowane lub zmienione linie ZTM
  (niesprawdzone).
- **Kraków:** Małopolskie Linie Dowozowe (ponad 800 przystanków: Wieliczka, Myślenice, Gdów, Drwinia), Niepołomicka
  i Skawińska Komunikacja Gminna, Wielicka Spółka Transportowa; „MDA” (Małopolskie Dworce Autobusowe) w Krakowie
  to przystanki linii regionalnych; bez tagów: Miechów, Krzeszowice, Myślenice, Dobczyce, Sułkowice
  (prywatni przewoźnicy busowi). Mobilis (ZTP) jest w danych i pokrywa gminy sąsiadujące z Krakowem.
- **Wrocław:** Siechnicka Komunikacja Publiczna, komunikacja gminna Czernicy i Kobierzyc; przystanki z tagiem
  „Wrocław” w Siechnicach i Długołęce bez odpowiednika (prawdopodobnie linie, które przeszły do innego organizatora;
  niesprawdzone); bez tagów: Oleśnica, Trzebnica, Oborniki Śl., Żmigród, Sobótka (autobusy prywatne; kolej KD jest).
- **Poznań:** ZTM Poznań obejmuje większość gmin FUA; braki: Pobiedziska (komunikacja gminy), Kostrzyn (Kostrzyńska
  Komunikacja Publiczna), Stęszew, Łubowo, Nekla.
- **Łódź:** brak **MZK Pabianice** i **MUK Zgierz** (komunikacja miejska dwóch miast po ok. 55–65 tys. mieszkańców;
  w danych są tylko linie MPK-Łódź, które tam dojeżdżają), a także Łask, Koluszki, Stryków, Tuszyn, Ksawerów, Brójce.
  To najpoważniejsza luka w zestawie: dotyczy miast, nie wsi.
- **Trójmiasto:** **MZK Wejherowo** (Wejherowo, Reda), PKS Gdynia (Szemud), Przewozy Autokarowe Albatros (Żukowo);
  bez tagów: Pruszcz Gdański (gmina wiejska), Trąbki Wielkie, Przywidz, Cedry Wielkie, Kolbudy, Stegna.
- **GZM:** feed ZTM GZM pokrywa prawie wszystko; luki tylko w gminach brzegowych: Rudziniec, Sośnicowice (PKS Gliwice,
  ZGKiM Sośnicowice), Miedźna (poza Metropolią, w FUA Tychów), Bieruń, Łazy (poza Metropolią; ZPG „Jedźmy Razem”).
""",
    "reverse": """
Ile obsłużonych przystanków GTFS nie ma w pobliżu przystanku OSM (promienie jak wyżej, sama odległość). To ogranicza
zaufanie do OSM jako mianownika: tam, gdzie OSM gubi przystanki obsługiwane przez GTFS, gubi zapewne także przystanki
przewoźników spoza GTFS, więc pokrycie jest tam **zawyżone**. Kolumna „bez żadnego OSM” liczy przystanki bez
jakiegokolwiek przystanku OSM w promieniu (więc nie różnice w oznaczeniu trybu). Najwięcej braków: przedmieścia Poznania
(ok. 15% przystanków ZTM poza rdzeniem; połowa ponad 100 m od czegokolwiek w OSM) i Wrocławia (ok. 16% poza rdzeniem),
GZM (ok. 7%). W rdzeniach oraz w Warszawie, Krakowie, Łodzi i Trójmieście 1–6%. Kolej: prawie zero (2 stacje
w Krakowie).
Tabela: przyjęte promienie, sama odległość.
""",
    "population": """
Pierwsze przybliżenie: jaka część ludności FUA (NSP 2021, siatka 1 km, komórka przypisana do gminy i FUA wg centroidu)
mieszka na obszarze, który można uznać za pokryty danymi. Dwa warianty, oba **wstępne** (definicja maski należy do fazy 2):
- **gminy**: ludność gmin, w których pokrycie (wszystkie tryby) ≥ próg; progi {thr};
- **komórki**: ludność komórek 1 km, w których ≥ próg przystanków OSM w promieniu 1 km od centroidu ma odpowiednik
  (komórki bez żadnego przystanku OSM w 1 km są osobno i nie wchodzą do obszaru pokrytego).
""",
    "population_after": """
Reguła z §6 (≥ ~85% ludności FUA w obszarze pokrytym) jest spełniona tylko w **GZM** i, przy progu gminnym do 85%
włącznie, w **Poznaniu** (w wariancie komórkowym przy progu 85% Poznań spada do ok. 80%). Dla Warszawy, Krakowa,
Łodzi, Wrocławia i Trójmiasta udział wynosi ok. 60–83% niezależnie od progu i wariantu: obszar pokryty to w praktyce
rdzeń plus gminy obsługiwane przez zarząd transportu miasta. Wybór progu (50 / 70 / 85%) zmienia wynik o 2–13 pkt
proc., wariant (gmina / komórka) o kilka punktów: o ocenie „niepełny” decyduje brak przewoźników, a nie parametr.
""",
    "understated": """
Systematycznie zaniżone (gdyby liczyć na całej FUA bez maski) byłyby: **Warszawa, Kraków, Łódź, Wrocław i Trójmiasto**.
W każdej z nich ok. 20–35% ludności FUA mieszka w gminach, gdzie mniej niż połowa przystanków OSM ma odpowiednik
w GTFS; tam miary z §4.5–4.7 widziałyby tylko kolej i linie zarządu transportu miasta, bez gminnych i prywatnych
autobusów. Skala zaniżenia samej miary (np. PNFT) nie jest jeszcze znana: brakujący przewoźnicy jeżdżą zwykle
rzadko, więc dla progu częstej komunikacji (≤ 10 min) strata może być mała, a dla dostępności (§4.6) i podaży
(wozokm na mieszkańca) duża. **Poznań** jest zaniżony nieznacznie (kilka gmin wschodnich), **GZM** praktycznie wcale.
Do porównań między aglomeracjami zostaje wariant „obszar pokryty” lub „rdzeń”, z adnotacją.
""",
    "limitations": """
1. **OSM jako mianownik jest niepełny i nierówny.** 1–16% obsłużonych przystanków GTFS nie ma odpowiednika w OSM
   (tabela wyżej). Gdzie OSM jest rzadszy, wskaźnik pokrycia jest zawyżony (brakuje także przystanków przewoźników
   spoza GTFS). Odwrotnie: OSM zawiera przystanki nieczynne, szkolne, zakładowe i prywatne bez oznaczenia; to zaniża
   wskaźnik w gminach dobrze pokrytych o kilka punktów.
2. **Jeden dzień.** Przystanek obsługiwany tylko w inne dni (weekend, sezon, wydarzenia, np. Gdańsk Stadion Expo)
   liczy się jako bez odpowiednika (kategoria „w feedzie, nieobsłużony”, gdy jest w `stops.txt`). Remonty w dniu ref.
   (tramwaje w Krakowie i Łodzi) obsłużono regułą „zastępczy” tylko w masce; w wskaźnikach tramwajowych zostają brakiem.
3. **Obecność, nie częstotliwość.** Przystanek z jednym kursem dziennie liczy się tak samo jak z dwustoma. Maska
   mówi, czy są dane, a nie czy jest dobra obsługa.
4. **Dopasowanie po nazwie** może połączyć przystanek z przeciwnym kierunkiem tego samego przystanku albo z przystankiem
   innego przewoźnika o tej samej nazwie po drugiej stronie ulicy. Dla maski (czy obszar ma dane) to nieszkodliwe;
   dla nazwania brakujących przewoźników lekko zaniża ich listę.
5. **Tagi przewoźników** są w OSM rzadkie (większość braków „bez tagu”); nazwy przewoźników w raporcie to próbka,
   nie inwentarz. Dostępność GTFS dla wymienionych przewoźników nie była sprawdzana.
6. **Filtr kolei turystycznych** działa po nazwie i operatorze; stacje nieczynnych linii bez znacznika `disused`
   zostają w mianowniku jako braki (w FUA fazy 1 to pojedyncze przypadki).
7. **Granice gmin LAU 2021 w skali 1:1M** są uogólnione: przystanki przy granicy gminy mogą trafić do sąsiedniej.
   Gminy brzegowe przecięte granicą FUA mają w tabeli udział powierzchni w FUA.
8. **GZM** w prowizorycznym wariancie „suma FUA”; wariant „Metropolia (41 gmin)” zmieniłby zestaw gmin brzegowych
   (np. Miedźna i Łazy wypadają, dochodzą inne gminy). Trójmiasto i GZM: pierścienie od jednego centrum są tylko
   orientacyjne.
9. **Ludność**: NSP 2021 (stan 31.03.2021) wobec rozkładów z 2026; nowe osiedla podmiejskie nie są w siatce.
   Wariant gminny jest zgrubny (gmina 30% pokryta, ale z pokrytym głównym miastem, wypada cała).
10. **Rozkłady**: PKM (Pomorska Kolej Metropolitalna) w `polish_trains` rusza dopiero od 13.12.2026, więc w dniu ref.
    część linii 201 obsługuje ZKA; to przypisane do kolei. Duplikaty kursów (GZM, SKM Warszawa) nie wpływają na wynik.
""",
    "files": """
- `coverage_summary.csv`: aglomeracja × tryb × promień: liczba przystanków OSM, pokrycie FUA / rdzeń / poza rdzeniem
  (z nazwą/kodem i samą odległością), kontrola przypadku, pokrycie dowolnym trybem, GTFS bez OSM; `recommended` = przyjęty promień.
- `coverage_by_gmina.csv`, `coverage_by_ring.csv` (pierścienie 1 km): liczniki przyczyn i pokrycie przy wszystkich promieniach.
- `unmatched_operators.csv`: tagi przystanków bez odpowiednika, z rozbiciem na klasy gmin i listą gmin.
- `gtfs_without_osm.csv`: aglomeracja × feed × tryb × rdzeń/poza: przystanki GTFS bez OSM przy kolejnych promieniach.
- `population_coverage_preliminary.csv`: wstępne udziały ludności (wariant gminny i komórkowy).
- `map_<aglomeracja>.png`: przystanki OSM z odpowiednikiem / bez na tle gmin; `nn_hist_<aglomeracja>.png`: histogramy odległości.
- `_meta.json`: wejścia (manifest), promienie, wyłączone stacje kolei turystycznych, przypisanie feedów.
""",
    "config": """
- `osm_gtfs_match_radius_m: 50` (bez zmian; autobus, tramwaj, metro, perony o nieokreślonym trybie);
- nowe: `osm_gtfs_rail_match_radius_m: {r_rail}` (stacje kolejowe);
- nowe: `osm_gtfs_name_match_radius_m: {{bus_tram: 200, rail: 500}}` (dopasowanie pomocnicze po nazwie/kodzie);
- do decyzji przy masce w fazie 2: próg pokrycia gminy/komórki (50 / 70 / 85%) i wariant (gmina czy komórka 1 km).
Moduł czyta `osm_gtfs_rail_match_radius_m`, jeśli klucz istnieje; w przeciwnym razie używa 200 m.
""",
}


# ------------------------------------------------------------------ main
def compute() -> dict:
    r_bus, r_rail = radii()
    OUT.mkdir(parents=True, exist_ok=True)
    results = {agg: build(agg, r_bus, r_rail) for agg in AGGS}
    osm = pd.concat([r["osm"] for r in results.values()], ignore_index=True)
    gu = pd.concat([r["gtfs"] for r in results.values()], ignore_index=True)
    lau_share = pd.concat([r["geo"]["lau"].assign(agg=k)[["agg", "LAU_ID", "share_in_fua"]]
                           for k, r in results.items()]).set_index(["agg", "LAU_ID"])["share_in_fua"]
    gm = table_by(osm, ["agg", "gmina_id", "gmina"], r_bus, r_rail)
    core_n = osm.groupby(["agg", "gmina_id"])["in_core"].mean()
    gm["core_share_of_stops"] = [core_n.get((a, g), np.nan) for a, g in zip(gm["agg"], gm["gmina_id"])]
    gm["lau_area_share_in_fua"] = [lau_share.get((a, g), np.nan) for a, g in zip(gm["agg"], gm["gmina_id"])]
    allcov = gm[gm["mode"] == "all"].set_index(["agg", "gmina_id"])
    gm["gmina_class"] = [gmina_class(allcov.loc[(a, g), "coverage"], allcov.loc[(a, g), "n_osm"])
                         for a, g in zip(gm["agg"], gm["gmina_id"])]
    gm = gm.sort_values(["agg", "mode", "gmina_id"]).reset_index(drop=True)
    rg = table_by(osm, ["agg", "ring_km"], r_bus, r_rail).sort_values(["agg", "mode", "ring_km"]).reset_index(drop=True)
    sm = pd.DataFrame([row for r in results.values() for row in summary_rows(r, r_bus, r_rail)])
    sm = sm.sort_values(["agg", "mode", "radius_m"]).reset_index(drop=True)
    sm["rail_radius_m"] = sm["rail_radius_m"].astype("Int64")
    ops = operator_table(osm, gm)
    gwo = gtfs_without_osm(gu, r_bus, r_rail)
    pop = pd.DataFrame([population(results[a], gm) for a in AGGS]).sort_values("agg").reset_index(drop=True)
    extra = {"reference_day": f"{ref_day():%Y-%m-%d}", "radius_bus_m": r_bus, "radius_rail_m": r_rail,
             "name_radius_m": NAME_RADIUS, "gzm_boundary_variant": results["gzm"]["geo"]["variant"],
             "osm_rail_cleanup": {k: r["ostats"] for k, r in results.items()},
             "feeds": {k: r["feeds"] for k, r in results.items()}}
    return {"results": results, "osm": osm, "gu": gu, "gm": gm, "rg": rg, "sm": sm, "ops": ops, "gwo": gwo,
            "pop": pop, "r_bus": r_bus, "r_rail": r_rail, "extra": extra}


def run() -> dict:
    t0 = time.time()
    ctx = compute()
    write_csv(ctx["gm"], "coverage_by_gmina.csv")
    write_csv(ctx["rg"], "coverage_by_ring.csv")
    write_csv(ctx["sm"], "coverage_summary.csv")
    write_csv(ctx["ops"], "unmatched_operators.csv")
    write_csv(ctx["gwo"], "gtfs_without_osm.csv")
    write_csv(ctx["pop"], "population_coverage_preliminary.csv")
    for r in ctx["results"].values():
        plot_map(r, ctx["r_bus"], ctx["r_rail"])
        plot_hist(r, ctx["r_bus"], ctx["r_rail"])
    write_report(ctx)
    feeds = sorted({f for r in ctx["results"].values() for f in r["feeds"]})
    write_meta(OUT, "stop_coverage", started=t0,
               inputs=["osm_poland_pbf", "lau_2021_01m", "nsp2021_grid_1km_shp", "urau_2021_100k_all"]
               + [f"gtfs_{f}" for f in feeds],
               extra=round_sig(ctx["extra"]))
    return ctx


if __name__ == "__main__":
    run()
