"""Phase 2, brief §4.5: population near frequent public transport, with an honest coverage mask (§6).

    python -m pipeline.frequent            # 7 phase-1 agglomerations -> metrics, charts, layers, QA

Inputs: pipeline.gtfs_service (de-duplicated trips, reference Wednesday), pipeline.popgrid (250 m grids,
ghsl_census_scaled and ghsl_raw), pipeline.walk_network (walk graph, Router), pipeline.stop_coverage (OSM <->
GTFS stop matching, reused for the mask).  Definitions are written out in results/qa/transit/frequent.md.

Short version
* Stop clusters: served stops (location_type 0) grouped by parent_station, then complete-linkage clustering of
  the groups at ``stop_cluster_radius_m`` (100 m, so a cluster's diameter between group centres is <= 100 m).
  Clustering is done once on the "all" feed set and reused for "official".
* Visits: a trip's consecutive stops in one cluster are one visit; a departure is a visit that is not the trip's
  last, with its departure time in the window (06:00-20:00 on the reference day, end exclusive).
* Direction from geometry, not from direction_id: bearing from the previous visit to the next visit (from the
  stop itself when the trip starts here).  Per cluster the axis is the bearing of its busiest segment
  (cluster -> next cluster); departures within 90 degrees of the axis are direction A, others B.
* Headway = window minutes / departures (average over the window, DG REGIO style).
  (i)  "all lines": all departures per direction summed; cluster headway = max(h_A, h_B);
  (ii) "segment": per direction the busiest segment (same next cluster, i.e. lines sharing the trunk to the
       next stop count together); cluster headway = max over directions;
  (ii-line) per direction the busiest single line (route_class + route_short_name), for comparison;
  (nodir) all departures, no direction requirement (isolates the direction rule).
  A cluster with departures in one direction only is a terminal (h = h_A) when >= 50 % of its departures start
  there or it has terminating arrivals >= 50 % of its departures; otherwise its other direction is looked for at
  a partner cluster <= PAIR_RADIUS_M away that serves one of the same lines in the opposite direction (one-way
  streets, opposite poles > 100 m apart); without a partner the cluster fails "both directions".
* ITDP-style replica (not an ITDP indicator): per (feed, stop_id), all stop_times rows 07:00-21:00 (both ends
  inclusive), all lines and directions together, mean of gaps between consecutive departures, frequent when
  0 < h <= 10 min (gtfs_kit compute_stop_stats + pedestriansfirst rule).
* Rail variant (modelled on DG REGIO classes): rail + metro departures (no replacement buses) per cluster, all
  directions, per hour of 06:00-20:00; classes < 4, 4-10, > 10; population within rail_station_radius_m (1 km).
* Access: walking network distance (pipeline.walk_network.Router) from 3 x 3 sample points per 250 m cell to the
  member stops of qualifying clusters, <= walk_to_stop_m (500 m); a cell's population counts in proportion to its
  sample points within reach.  Euclidean distance (same points) as control.
* Mask: per 250 m cell, OSM stops within MASK_RADIUS_M of the cell centre (matched to GTFS of the feed variant with
  pipeline.stop_coverage); in the mask when the matched share >= MASK_MIN_STOP_SHARE or there is no OSM stop within
  the radius.  Outside the mask a cell's value is null.
"""
from __future__ import annotations

import math
import time
import warnings
from functools import lru_cache

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer
from rasterio import features
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from pipeline import gtfs_service as gs
from pipeline import stop_coverage as sc
from pipeline.boundaries import load_agglomeration
from pipeline.common import INTERIM, RESULTS, load_config, round_sig, sig, write_json
from pipeline.popgrid import tif_path
from pipeline.walk_network import Router

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

CFG = load_config()
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
DAY = CFG["reference_day"]
FEEDV = list(CFG["feed_variants"])
GRIDV = list(CFG["population_grid_variants"])


def _hms(s: str) -> int:
    h, m = s.split(":")[:2]
    return int(h) * 3600 + int(m) * 60


WIN = (_hms(CFG["frequency_window"]["start"]), _hms(CFG["frequency_window"]["end"]))
WIN_MIN = (WIN[1] - WIN[0]) / 60
ITDP_WIN = (7 * 3600, 21 * 3600)
ITDP_T = 10.0
THRESH = [int(t) for t in CFG["headway_thresholds_min"]]
WALK_M = float(CFG["walk_to_stop_m"])
RAIL_M = float(CFG["rail_station_radius_m"])
CLUSTER_M = float(CFG["stop_cluster_radius_m"])
COV_MIN = float(CFG["coverage_min_share"])

# PROPOSAL config keys (see frequent.md)
PAIR_RADIUS_M = 300.0
TERMINAL_SHARE = 0.5
MASK_RADIUS_M = 1000.0
MASK_PLACE_M = 100.0             # OSM poles within 100 m count as one place (bus stations, interchanges)
MASK_MIN_STOP_SHARE = 0.85
MASK_SENSITIVITY = [0.5, 0.7, 0.85, 0.95]
STOP_MAX_SNAP_M = {"default": 150.0, "rail": 300.0}
PT_MAX_SNAP_M = 300.0
SAMPLE_N = 3                    # 3 x 3 sample points per 250 m cell
RAIL_CLASSES = [(">10", 10.0), ("4-10", 4.0), ("<4", 0.0)]
REC = {"feed_variant": "all", "population_grid": "ghsl_census_scaled", "agg": "seg", "dist": "net"}
CELL = 250.0

OUT_INT = INTERIM / "frequent"
METRICS = RESULTS / "metrics"
CHARTS = RESULTS / "charts"
LAYERS = RESULTS / "layers"
QA = RESULTS / "qa" / "transit" / "frequent"
QA_MD = RESULTS / "qa" / "transit" / "frequent.md"
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)

GRID_LABEL = {"ghsl_census_scaled": "GHSL 250 m przeskalowany do NSP 2021 (EPSG:2180)",
              "ghsl_raw": "GHSL 250 m (EPSG:2180)"}
POP_DATE = {"ghsl_census_scaled": "2021-03-31 (NSP 2021, wzór GHSL 2020)", "ghsl_raw": "2020 (GHSL, model)"}
FEED_LABEL = {"official": "feedy oficjalne", "all": "wszystkie feedy (w tym nieoficjalne)"}
AGG_LABEL = {"all": "wszystkie linie zsumowane w kierunku", "seg": "najczęstszy odcinek do następnego przystanku",
             "line": "najczęstsza pojedyncza linia", "nodir": "wszystkie linie, bez wymogu dwóch kierunków"}
DOM_LABEL = {"fua": "FUA", "core": "rdzeń", "covered": "obszar pokryty danymi"}


# ================================================================== clusters
@lru_cache(maxsize=None)
def clusters(agg: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(stops with cluster id, clusters).  Served stops of either feed variant."""
    served = set()
    for v in FEEDV:
        served |= set(gs.stop_times(agg, DAY, v)["suid"].unique())
    allst = gs.stops(agg, "all")
    s = pd.DataFrame(allst.drop(columns="geometry"))
    s = s[s.suid.isin(served) & np.isfinite(s.x) & np.isfinite(s.y)].copy()
    par_ok = set((allst.feed + ":" + allst.stop_id.astype(str))[allst.location_type == 1])
    pkey = s.feed + ":" + s.parent_station.astype(str)
    s["unit"] = np.where(s.parent_station.notna() & pkey.isin(par_ok), "p:" + pkey, "s:" + s.suid)
    s = s.sort_values(["unit", "suid"]).reset_index(drop=True)
    u = s.groupby("unit", sort=True).agg(x=("x", "mean"), y=("y", "mean")).reset_index()
    u["lab"] = complete_link(u[["x", "y"]].to_numpy(), CLUSTER_M)
    s["lab"] = s.unit.map(u.set_index("unit").lab)
    cl = s.groupby("lab").agg(x=("x", "mean"), y=("y", "mean"), n_stops=("suid", "size"),
                              name=("stop_name", lambda v: v.fillna("").value_counts().sort_index()
                                    .sort_values(ascending=False, kind="stable").index[0])).reset_index()
    cl = cl.sort_values(["y", "x"], ascending=[False, True]).reset_index(drop=True)
    cl["cl"] = np.arange(len(cl))
    cl["cluster_id"] = [f"{agg}-{i:05d}" for i in cl.cl]
    s["cl"] = s.lab.map(cl.set_index("lab").cl)
    s = s.drop(columns=["lab"]).sort_values("suid").reset_index(drop=True)
    return s, cl.drop(columns="lab")


def complete_link(xy: np.ndarray, radius: float) -> np.ndarray:
    """Labels: 100 m single-linkage components, split by complete linkage so that no group is wider than radius."""
    pairs = cKDTree(xy).query_pairs(radius, output_type="ndarray")
    n = len(xy)
    g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)) if len(pairs) else coo_matrix((n, n))
    _, comp = connected_components(g, directed=False)
    lab = np.zeros(n, dtype=np.int64)
    nxt = 0
    for c in np.unique(comp):
        idx = np.flatnonzero(comp == c)
        if len(idx) == 1:
            lab[idx] = nxt; nxt += 1
            continue
        p = xy[idx]
        dmax = np.max(np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1]))
        if dmax <= radius:
            lab[idx] = nxt; nxt += 1
            continue
        f = fcluster(linkage(p, method="complete"), t=radius, criterion="distance")
        for k in np.unique(f):
            lab[idx[f == k]] = nxt; nxt += 1
    return lab


# ================================================================== visits
def _bearing(dx, dy):
    return np.degrees(np.arctan2(dx, dy)) % 360.0


def _angdiff(a, b):
    d = np.abs((np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0)
    return d


NOCOORD: dict = {}   # (agg, variant) -> stops / events dropped for missing coordinates


@lru_cache(maxsize=None)
def visits(agg: str, variant: str) -> pd.DataFrame:
    st = gs.stop_times(agg, DAY, variant)
    tr = gs.active_trips(agg, DAY, variant)[["uid", "is_replacement_bus"]]
    s, _ = clusters(agg)
    # stop events without coordinates (e.g. lodz 3876/3877 with lat = lon = 0 in the source, NaN from the service
    # layer) are left out of every spatial step: the trip passes through them as if they were not there
    bad = ~(np.isfinite(st.x.to_numpy(dtype=float)) & np.isfinite(st.y.to_numpy(dtype=float)))
    NOCOORD[(agg, variant)] = {
        "stops": sorted(set(st.suid[bad])), "events": int(bad.sum()),
        "departures_in_window": int((bad & (st.dep_s >= WIN[0]).to_numpy() & (st.dep_s < WIN[1]).to_numpy()).sum())}
    st = st[~bad].reset_index(drop=True)
    st["cl"] = st.suid.map(s.set_index("suid").cl).fillna(-1).astype(np.int64)
    codes = pd.Categorical(st.suid).codes.astype(np.int64)
    key = np.where(st.cl.values >= 0, st.cl.values, 10_000_000 + codes)
    uid = st.uid.values
    new = np.r_[True, (uid[1:] != uid[:-1]) | (key[1:] != key[:-1])]
    start = np.flatnonzero(new)
    end = np.r_[start[1:], len(st)] - 1
    v = pd.DataFrame({
        "uid": uid[start], "feed": st.feed.values[start], "key": key[start], "cl": st.cl.values[start],
        "arr": st.arr_s.values[start].astype(np.float64), "dep": st.dep_s.values[end].astype(np.float64),
        "x": st.x.values[end].astype(np.float64), "y": st.y.values[end].astype(np.float64),
        "suid": st.suid.values[end], "suid_first": st.suid.values[start],
        "route_class": st.route_class.values[start], "rsn": st.route_short_name.values[start].astype(object),
    })
    v["is_replacement_bus"] = v.uid.map(tr.set_index("uid").is_replacement_bus).fillna(False).astype(bool)
    same_prev = np.r_[False, v.uid.values[1:] == v.uid.values[:-1]]
    same_next = np.r_[v.uid.values[:-1] == v.uid.values[1:], False]
    v["is_first"] = ~same_prev
    v["is_last"] = ~same_next
    nx = np.r_[v.x.values[1:], np.nan]; ny = np.r_[v.y.values[1:], np.nan]
    px = np.r_[np.nan, v.x.values[:-1]]; py = np.r_[np.nan, v.y.values[:-1]]
    v["next_key"] = np.where(same_next, np.r_[v.key.values[1:], -1], -1)
    bx = np.where(same_prev, px, v.x.values); by = np.where(same_prev, py, v.y.values)
    v["bearing"] = np.where(same_next, _bearing(nx - bx, ny - by), np.nan)
    v["line"] = v.route_class.astype(str) + "|" + v.rsn.astype(str)
    return v


def departures(v: pd.DataFrame, window: tuple[int, int], modes: set | None, no_replacement: bool) -> pd.DataFrame:
    m = (~v.is_last) & (v.cl >= 0) & (v.dep >= window[0]) & (v.dep < window[1])
    if modes is not None:
        m &= v.route_class.isin(modes)
    if no_replacement:
        m &= ~v.is_replacement_bus
    return v[m]


# ================================================================== headways per cluster
def _circmean(b: pd.Series) -> float:
    r = np.radians(b.to_numpy())
    return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360.0)


def cluster_headways(v: pd.DataFrame, cl: pd.DataFrame, modes: set | None = None,
                     no_replacement: bool = False) -> pd.DataFrame:
    """Per cluster: departures, direction split and headways for (i) all, (ii) seg, line, nodir."""
    D = departures(v, WIN, modes, no_replacement).copy()
    out = pd.DataFrame({"cl": cl.cl.values})
    if D.empty:
        for c in ("n", "nA", "nB", "h_all", "h_seg", "h_line", "h_nodir"):
            out[c] = np.inf if c.startswith("h") else 0
        out["dir_status"] = "none"
        return out
    seg = D.groupby(["cl", "next_key"], sort=True).agg(n=("dep", "size")).reset_index()
    seg = seg.sort_values(["cl", "n", "next_key"], ascending=[True, False, True], kind="stable")
    top = seg.drop_duplicates("cl").set_index("cl")
    Dt = D.merge(top[["next_key"]].rename(columns={"next_key": "top_key"}), left_on="cl", right_index=True)
    axis = Dt[Dt.next_key == Dt.top_key].groupby("cl").bearing.apply(_circmean)
    D["axis"] = D.cl.map(axis)
    D["grp"] = np.where(_angdiff(D.bearing, D.axis) <= 90.0, "A", "B")
    cnt = D.groupby(["cl", "grp"]).size().unstack(fill_value=0).reindex(columns=["A", "B"], fill_value=0)
    sg = D.groupby(["cl", "grp", "next_key"]).size().groupby(level=[0, 1]).max().unstack().reindex(columns=["A", "B"])
    ln = D.groupby(["cl", "grp", "line"]).size().groupby(level=[0, 1]).max().unstack().reindex(columns=["A", "B"])
    out = out.set_index("cl")
    out["n"] = D.groupby("cl").size().reindex(out.index).fillna(0).astype(int)
    out["nA"] = cnt["A"].reindex(out.index).fillna(0).astype(int)
    out["nB"] = cnt["B"].reindex(out.index).fillna(0).astype(int)
    out["axis"] = axis.reindex(out.index)
    for k, t in (("all", cnt), ("seg", sg), ("line", ln)):
        for g in ("A", "B"):
            nn = t[g].reindex(out.index).fillna(0).to_numpy(dtype=float)
            out[f"h{g}_{k}"] = np.where(nn > 0, WIN_MIN / np.maximum(nn, 1), np.inf)
    out["h_nodir"] = np.where(out.n > 0, WIN_MIN / np.maximum(out.n, 1), np.inf)
    # terminal test (departures that start here, or terminating arrivals)
    first_share = D.groupby("cl").is_first.mean().reindex(out.index).fillna(0)
    arr_end = v[v.is_last & (v.cl >= 0) & (v.arr >= WIN[0]) & (v.arr < WIN[1])]
    if modes is not None:
        arr_end = arr_end[arr_end.route_class.isin(modes)]
    if no_replacement:
        arr_end = arr_end[~arr_end.is_replacement_bus]
    n_end = arr_end.groupby("cl").size().reindex(out.index).fillna(0)
    one = (out.n > 0) & ((out.nA == 0) | (out.nB == 0))
    terminal = one & ((first_share >= TERMINAL_SHARE) | (n_end >= TERMINAL_SHARE * out.n))
    status = np.select([out.n == 0, ~one, terminal], ["none", "two_way", "terminal"], "one_way")
    out["dir_status"] = status
    # partner search for one-way clusters
    for k in ("all", "seg", "line"):
        out[f"hopp_{k}"] = np.inf
    ow = out.index[out.dir_status == "one_way"]
    if len(ow):
        cxy = cl.set_index("cl").loc[:, ["x", "y"]]
        tree = cKDTree(cxy.to_numpy())
        byc = {c: g for c, g in D.groupby("cl")}
        for c in ow:
            g = byc[c]
            ax = out.at[c, "axis"]
            lines = set(g.line)
            best = {"all": np.inf, "seg": np.inf, "line": np.inf}
            for j in tree.query_ball_point(cxy.loc[c].to_numpy(), PAIR_RADIUS_M):
                j = int(cxy.index[j])
                if j == c or j not in byc:
                    continue
                h = byc[j]
                opp = h[_angdiff(h.bearing, ax) > 90.0]
                if opp.empty or not (set(opp.line) & lines):
                    continue
                best["all"] = min(best["all"], WIN_MIN / len(opp))
                best["seg"] = min(best["seg"], WIN_MIN / opp.groupby("next_key").size().max())
                best["line"] = min(best["line"], WIN_MIN / opp.groupby("line").size().max())
            for k in best:
                out.at[c, f"hopp_{k}"] = best[k]
        paired = out.loc[ow, "hopp_all"] < np.inf
        out.loc[ow[paired.to_numpy()], "dir_status"] = "paired"
    for k in ("all", "seg", "line"):
        hA = np.where(out.nA > 0, out[f"hA_{k}"], out[f"hB_{k}"])   # the populated side of a one-way cluster
        out[f"h_{k}"] = np.select(
            [out.dir_status == "two_way", out.dir_status == "terminal", out.dir_status == "paired"],
            [np.maximum(out[f"hA_{k}"], out[f"hB_{k}"]), hA, np.maximum(hA, out[f"hopp_{k}"])], np.inf)
    return out.reset_index()


def itdp_stops(agg: str, variant: str) -> pd.DataFrame:
    """ITDP-style mean headway per (feed, stop_id) (suid)."""
    st = gs.stop_times(agg, DAY, variant)
    d = st[(st.dep_s >= ITDP_WIN[0]) & (st.dep_s <= ITDP_WIN[1])][["suid", "dep_s"]]
    d = d.sort_values(["suid", "dep_s"], kind="stable")
    g = d.groupby("suid").dep_s
    n = g.size()
    span = g.max() - g.min()
    h = (span / (n - 1)).where(n > 1) / 60.0
    return pd.DataFrame({"suid": n.index, "n": n.values, "h_itdp": h.values})


def rail_dph(v: pd.DataFrame, cl: pd.DataFrame) -> pd.DataFrame:
    D = departures(v, WIN, {"rail", "metro"}, True)
    n = D.groupby("cl").size().reindex(cl.cl).fillna(0).to_numpy()
    return pd.DataFrame({"cl": cl.cl.values, "n_rail": n, "dph": n / (WIN_MIN / 60.0)})


# ================================================================== coverage mask
@lru_cache(maxsize=None)
def osm_match(agg: str, variant: str) -> pd.DataFrame:
    """OSM stops in FUA + MASK_RADIUS with the phase-0 matching against the variant's feeds."""
    a = sc.agg_geo(agg)
    r_bus, r_rail = sc.radii()
    osm, _ = sc.osm_in(a["fua"].buffer(MASK_RADIUS_M), r_rail)
    feeds = gs.feeds_for(agg, variant)
    g = pd.concat([sc.gtfs_points(f) for f in feeds], ignore_index=True)
    big = a["fua"].buffer(MASK_RADIUS_M + 3000)
    xmin, ymin, xmax, ymax = big.bounds
    g = g[(g.x >= xmin) & (g.x <= xmax) & (g.y >= ymin) & (g.y <= ymax)]
    g = g[shapely.contains_xy(big, g.x.to_numpy(), g.y.to_numpy())].reset_index(drop=True)
    osm = osm.reset_index(drop=True)
    osm = pd.concat([osm, sc.match_distances(osm, g)], axis=1)
    osm["status"] = sc.status(osm, r_bus, r_rail)
    osm["covered"] = osm["status"].isin(sc.COVERED)
    osm = sc.assign_gmina(osm, a["lau"])
    osm["in_fua"] = shapely.contains_xy(a["fua"], osm.x.to_numpy(), osm.y.to_numpy())
    return osm[["osm_type", "osm_id", "x", "y", "mode", "name", "status", "covered", "gmina_id", "gmina", "in_fua"]]


def mask_places(osm: pd.DataFrame) -> pd.DataFrame:
    """OSM stops grouped into places (complete linkage, MASK_PLACE_M); a place's data share = mean over its poles of
    'has GTFS data' (matched, or in a feed but not served on the reference day)."""
    o = osm.sort_values(["osm_type", "osm_id"]).reset_index(drop=True)
    o["place"] = complete_link(o[["x", "y"]].to_numpy(), MASK_PLACE_M)
    o["has_data"] = o.covered | (o.status == "in_feed_not_served")
    return o.groupby("place").agg(x=("x", "mean"), y=("y", "mean"), share=("has_data", "mean"),
                                  n=("has_data", "size")).reset_index()


def mask_share(xy: np.ndarray, osm: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Per point: number of OSM stop places within MASK_RADIUS_M and the sum of their data shares."""
    pl = mask_places(osm)
    tree = cKDTree(pl[["x", "y"]].to_numpy())
    cov = pl.share.to_numpy()
    nb = tree.query_ball_point(xy, MASK_RADIUS_M)
    n = np.array([len(i) for i in nb])
    m = np.array([cov[i].sum() if len(i) else 0.0 for i in nb])
    return n, m


def in_mask(n: np.ndarray, m: np.ndarray, thr: float = MASK_MIN_STOP_SHARE) -> np.ndarray:
    return (n == 0) | (m >= thr * n - 1e-9)


# ================================================================== per agglomeration
def sample_points(cells: pd.DataFrame) -> np.ndarray:
    off = (np.arange(SAMPLE_N) - (SAMPLE_N - 1) / 2) * CELL / SAMPLE_N
    dx, dy = np.meshgrid(off, off)
    return np.c_[(cells.x.values[:, None] + dx.ravel()[None, :]).ravel(),
                 (cells.y.values[:, None] + dy.ravel()[None, :]).ravel()]


def run_agg(agg: str) -> dict:
    t0 = time.time()
    s, cl = clusters(agg)
    cells = pd.read_parquet(INTERIM / "popgrid" / f"cells_{agg}.parquet")
    cells = cells[cells.in_fua].reset_index(drop=True)
    pts = sample_points(cells)
    npts = SAMPLE_N * SAMPLE_N
    centre_idx = npts // 2
    # stops: rail / metro stations get a larger snap distance
    rail_suids = set()
    for v in FEEDV:
        vv = visits(agg, v)
        rail_suids |= set(vv.loc[vv.route_class.isin(["rail", "metro"]), "suid"])
    is_rail = s.suid.isin(rail_suids).to_numpy()
    nocoord = {v: NOCOORD[(agg, v)] for v in FEEDV}
    snap = np.where(is_rail, STOP_MAX_SNAP_M["rail"], STOP_MAX_SNAP_M["default"])
    router = Router(agg, s[["x", "y"]].to_numpy(), snap, pts, PT_MAX_SNAP_M)
    print(f"  {agg}: router built ({router.n_nodes:,} nodes) in {time.time() - t0:.0f} s", flush=True)
    sidx =pd.Series(np.arange(len(s)), index=s.suid)

    res = {"agg": agg, "cells": cells, "clusters": cl, "stops": s, "frac": {}, "cent": {}, "cl_tables": {},
           "nocoord": nocoord,
           "snap": {"stops_total": int(len(s)), "stops_unsnapped": int(np.isinf(router.stop_snap_d).sum()),
                    "stops_unsnapped_rail": int((np.isinf(router.stop_snap_d) & is_rail).sum()),
                    "points_total": int(len(pts)), "points_unsnapped": int(np.isinf(router.pt_snap_d).sum()),
                    "stop_snap_median_m": float(np.median(router.stop_snap_d[np.isfinite(router.stop_snap_d)])),
                    "point_snap_median_m": float(np.median(router.pt_snap_d[np.isfinite(router.pt_snap_d)])),
                    "point_snap_p95_m": float(np.quantile(router.pt_snap_d[np.isfinite(router.pt_snap_d)], 0.95))}}
    unsnapped_cell = np.isinf(router.pt_snap_d).reshape(-1, npts)
    res["snap"]["pop_share_unsnapped_points_scaled"] = float(
        (cells.pop_ghsl_census_scaled.values * unsnapped_cell.mean(axis=1)).sum() / cells.pop_ghsl_census_scaled.sum())

    def record(key, src_idx, limit):
        d_net = router.dist(src_idx, limit) if len(src_idx) else np.full(len(pts), np.inf)
        if len(src_idx):
            sub = cKDTree(s[["x", "y"]].to_numpy()[np.unique(src_idx)])
            d_euc, _ = sub.query(pts, distance_upper_bound=limit + 1)
        else:
            d_euc = np.full(len(pts), np.inf)
        for dist, d in (("net", d_net), ("euc", d_euc)):
            r = (d <= limit).reshape(-1, npts)
            res["frac"][key + (dist,)] = r.mean(axis=1)
            res["cent"][key + (dist,)] = r[:, centre_idx]

    def members(cl_ids, suid_ok):
        m = s.cl.isin(cl_ids).to_numpy() & s.suid.isin(suid_ok).to_numpy()
        return np.flatnonzero(m)

    for v in FEEDV:
        vv = visits(agg, v)
        D = departures(vv, WIN, None, False)
        dep_suids = set(D.suid)
        hw = cluster_headways(vv, cl)
        res["cl_tables"][(v, "main")] = hw
        for k in ("all", "seg", "line", "nodir"):
            for T in THRESH:
                ok = hw.cl[hw[f"h_{k}"] <= T + 1e-9]
                record((v, k, T), members(ok, dep_suids), WALK_M)
        # sensitivity: without the partner rule (paired one-way clusters fail "both directions")
        for T in THRESH:
            ok = hw.cl[(hw.h_seg <= T + 1e-9) & (hw.dir_status != "paired")]
            record((v, "seg_nopair", T), members(ok, dep_suids), WALK_M)
        # rail-bound (tram + metro + rail, no replacement buses)
        rbm = {"tram", "metro", "rail"}
        Drb = departures(vv, WIN, rbm, True)
        hrb = cluster_headways(vv, cl, rbm, True)
        res["cl_tables"][(v, "railbound")] = hrb
        for k in ("all", "seg"):
            for T in THRESH:
                ok = hrb.cl[hrb[f"h_{k}"] <= T + 1e-9]
                record((v, f"rb_{k}", T), members(ok, set(Drb.suid)), WALK_M)
        # ITDP-style
        it = itdp_stops(agg, v)
        res["cl_tables"][(v, "itdp")] = it
        ok = it.suid[(it.h_itdp > 0) & (it.h_itdp <= ITDP_T + 1e-9)]
        record((v, "itdp", 10), sidx.reindex(ok).dropna().astype(int).to_numpy(), WALK_M)
        # rail classes
        rd = rail_dph(vv, cl)
        res["cl_tables"][(v, "rail")] = rd
        Dr = departures(vv, WIN, {"rail", "metro"}, True)
        for lab, lo in RAIL_CLASSES:
            okc = rd.cl[(rd.dph > lo) if lab != "4-10" else (rd.dph >= lo)]
            record((v, f"rail{lab}", 0), members(okc, set(Dr.suid)), RAIL_M)
        print(f"  {agg} {v}: distances done ({time.time() - t0:.0f} s)", flush=True)

    # coverage mask per cell (populated FUA cells) and per variant
    a = sc.agg_geo(agg)
    fin = shapely.contains_xy(a["fua"], s.x.values, s.y.values)
    res["snap"]["stops_in_fua"] = int(fin.sum())
    res["snap"]["stops_in_fua_unsnapped"] = int((fin & np.isinf(router.stop_snap_d)).sum())
    cg = sc.assign_gmina(cells[["x", "y"]].copy(), a["lau"])
    cells["gmina_id"] = cg.gmina_id.values
    res["mask_sens"] = {}
    for v in FEEDV:
        osm = osm_match(agg, v)
        n, m = mask_share(cells[["x", "y"]].to_numpy(), osm)
        cells[f"osm_n_{v}"] = n
        cells[f"osm_cov_{v}"] = m
        cells[f"in_mask_{v}"] = in_mask(n, m)
        gm = (osm.covered | (osm.status == "in_feed_not_served"))[osm.in_fua].groupby(osm.gmina_id[osm.in_fua]).mean()
        cells[f"gmina_cov_{v}"] = cells.gmina_id.map(gm).values
        res["mask_sens"][v] = {str(t): in_mask(n, m, t) for t in MASK_SENSITIVITY}
        res["mask_sens"][v]["gmina_0.85"] = (cells[f"gmina_cov_{v}"].fillna(1.0) >= 0.85).to_numpy()
    cells["no_osm_stop_1km"] = cells["osm_n_all"].to_numpy() == 0
    res["cells"] = cells
    res["router_nodes"] = router.n_nodes
    res["seconds"] = time.time() - t0
    return res


# ================================================================== aggregation to metrics
def share(res: dict, key: tuple, grid: str, dom: str, v: str, centroid: bool = False) -> float | None:
    c = res["cells"]
    p = c[f"pop_{grid}"].to_numpy()
    sel = domain_sel(c, dom, v)
    if p[sel].sum() <= 0:
        return None
    f = res["cent" if centroid else "frac"][key]
    return float((p[sel] * f[sel]).sum() / p[sel].sum())


def domain_sel(c: pd.DataFrame, dom: str, v: str) -> np.ndarray:
    if dom == "fua":
        return np.ones(len(c), bool)
    if dom == "core":
        return c.in_core.to_numpy()
    return c[f"in_mask_{v}"].to_numpy()


def coverage(res: dict, grid: str, dom: str, v: str) -> float:
    c = res["cells"]
    p = c[f"pop_{grid}"].to_numpy()
    base = c.in_core.to_numpy() if dom == "core" else np.ones(len(c), bool)
    return float(p[base & c[f"in_mask_{v}"].to_numpy()].sum() / p[base].sum())


def metric_rows(res: dict) -> list[dict]:
    agg = res["agg"]
    rows = []
    src = ("GTFS (feedy wg config.yaml, dzień {d}, warstwa usług pipeline.gtfs_service); OSM 2026-11-22 "
           "(sieć piesza, przystanki); ludność: {g}").format(d=DAY, g="{g}")

    def add(dom, metric, label, value, unit, grid, v, tier, flag="", cov=None):
        rows.append({"agglomeration": agg, "domain": dom, "metric": metric, "label": label,
                     "value": sig(value) if value is not None else None, "unit": unit,
                     "grid": GRID_LABEL[grid], "source": src.format(g="NSP 2021 + GHSL 2020" if grid == "ghsl_census_scaled"
                                                                    else "GHSL 2020"),
                     "population_date": POP_DATE[grid], "timetable_date": DAY,
                     "coverage_share": sig(cov) if cov is not None else None, "flag": flag, "tier": tier,
                     "feed_variant": v, "population_grid": grid})

    win = f"{CFG['frequency_window']['start']}–{CFG['frequency_window']['end']}"
    for v in FEEDV:
        for grid in GRIDV:
            for dom in ("fua", "core", "covered"):
                cov = coverage(res, grid, "core" if dom == "core" else "fua", v)
                flag = ""
                if dom in ("fua", "core") and cov < COV_MIN:
                    flag = (f"niepełne pokrycie GTFS: {cov * 100:.1f} % ludności {'rdzenia' if dom == 'core' else 'FUA'} "
                            "w obszarze pokrytym (< 85 %); wynik zaniżony, do porównań wariant 'obszar pokryty' lub 'rdzeń'")
                if dom == "covered":
                    flag = "tylko komórki w masce pokrycia GTFS (§6); coverage_share = udział ludności FUA w masce"
                rec = (v == REC["feed_variant"] and grid == REC["population_grid"])
                for k in ("seg", "all", "line", "nodir"):
                    for T in THRESH:
                        for dist in ("net", "euc"):
                            if k in ("line", "nodir") and dist == "euc":
                                continue
                            main = rec and k == REC["agg"] and dist == "net" and dom in ("covered", "core")
                            tier = "main" if main else ("table" if k in ("seg", "all") else "qa")
                            dl = "pieszo po sieci OSM" if dist == "net" else "w linii prostej (kontrola)"
                            add(dom, f"freq_{k}_{dist}_le{T}min",
                                f"Ludność ≤ {int(WALK_M)} m ({dl}) od przystanku z odstępem ≤ {T} min w obu kierunkach "
                                f"(średnia {win}; {AGG_LABEL[k]})" if k != "nodir" else
                                f"Ludność ≤ {int(WALK_M)} m ({dl}) od przystanku z odstępem ≤ {T} min (średnia {win}; "
                                f"{AGG_LABEL[k]})",
                                pct(share(res, (v, k, T, dist), grid, dom, v)), "%", grid, v, tier, flag, cov)
                    if k == "seg":
                        for T in THRESH:
                            add(dom, f"freq_{k}_net_le{T}min_centroid",
                                f"Jak freq_{k}_net_le{T}min, ale komórka reprezentowana tylko środkiem (kontrola)",
                                pct(share(res, (v, k, T, "net"), grid, dom, v, centroid=True)), "%", grid, v, "qa",
                                flag, cov)
                for k in ("seg", "all"):
                    for T in THRESH:
                        add(dom, f"freq_railbound_{k}_net_le{T}min",
                            f"Ludność ≤ {int(WALK_M)} m pieszo od przystanku tramwaju, metra lub kolei z odstępem ≤ {T} min "
                            f"w obu kierunkach, tylko kursy szynowe ({AGG_LABEL[k]}; to nie jest wskaźnik ITDP PNRT)",
                            pct(share(res, (v, f"rb_{k}", T, "net"), grid, dom, v)), "%", grid, v, "table", flag, cov)
                for dist in ("net", "euc"):
                    add(dom, f"itdp_style_{dist}_le10min",
                        "Replika implementacji PNFT z kodu ITDP na naszych danych (okno 07–21, średnia przerw między "
                        "odjazdami, bez podziału na kierunki, linie sumowane na stop_id, ≤ 10 min, 500 m "
                        + ("po sieci" if dist == "net" else "w linii prostej") + "); nie jest to wartość ITDP",
                        pct(share(res, (v, "itdp", 10, dist), grid, dom, v)), "%", grid, v, "table", flag, cov)
                for dist in ("net", "euc"):
                    dl = "pieszo po sieci OSM" if dist == "net" else "w linii prostej (kontrola)"
                    s10 = share(res, (v, "rail>10", 0, dist), grid, dom, v)
                    s4 = share(res, (v, "rail4-10", 0, dist), grid, dom, v)
                    s0 = share(res, (v, "rail<4", 0, dist), grid, dom, v)
                    tier = "table"
                    add(dom, f"rail_ge4dph_{dist}_1km",
                        f"Ludność ≤ {int(RAIL_M)} m ({dl}) od stacji kolei lub metra z ≥ 4 odjazdami/h (średnia {win}, "
                        "bez komunikacji zastępczej)", pct(s4), "%", grid, v, tier, flag, cov)
                    add(dom, f"rail_gt10dph_{dist}_1km",
                        f"Ludność ≤ {int(RAIL_M)} m ({dl}) od stacji kolei lub metra z > 10 odjazdami/h (średnia {win})",
                        pct(s10), "%", grid, v, tier, flag, cov)
                    add(dom, f"rail_any_{dist}_1km",
                        f"Ludność ≤ {int(RAIL_M)} m ({dl}) od stacji kolei lub metra z jakimkolwiek odjazdem {win}",
                        pct(s0), "%", grid, v, tier, flag, cov)
                if dom != "covered":
                    add(dom, "coverage_share_pop", f"Udział ludności ({DOM_LABEL[dom]}) w masce pokrycia GTFS",
                        cov * 100, "%", grid, v, "qa", "", cov)
    return rows


def pct(x):
    return None if x is None else 100.0 * x


# ================================================================== layers
def best_class(res: dict, v: str, frac_min: float = 0.5) -> np.ndarray:
    c = res["cells"]
    out = np.full(len(c), ">30", dtype=object)
    for T in sorted(THRESH, reverse=True):
        f = res["frac"][(v, REC["agg"], T, "net")]
        out = np.where(f >= frac_min, str(T), out)
    out = np.where(c[f"in_mask_{v}"].to_numpy(), out, None)
    return out


def rail_class(res: dict, v: str) -> np.ndarray:
    out = np.full(len(res["cells"]), "brak stacji", dtype=object)
    for lab, _ in reversed(RAIL_CLASSES):
        f = res["frac"][(v, f"rail{lab}", 0, "net")]
        out = np.where(f >= 0.5, lab, out)
    return np.where(res["cells"][f"in_mask_{v}"].to_numpy(), out, None)


def write_layers(results: list[dict]) -> dict:
    LAYERS.mkdir(parents=True, exist_ok=True)
    parts, clparts, maskparts = [], [], []
    for r in results:
        c = r["cells"]
        lon, lat = TO4326.transform(c.x.to_numpy(), c.y.to_numpy())
        d = pd.DataFrame({"agglomeration": r["agg"], "cell_id": c.cell_id.values,
                          "pop_census_scaled": c.pop_ghsl_census_scaled.map(lambda x: sig(x, 4)).values,
                          "in_core": c.in_core.values})
        for v in FEEDV:
            d[f"headway_class_{v}"] = best_class(r, v)
            d[f"in_mask_{v}"] = c[f"in_mask_{v}"].values
        d["rail_class_all"] = rail_class(r, "all")
        parts.append(gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(np.round(lon, 6), np.round(lat, 6)), crs="EPSG:4326"))
        cl = r["clusters"]
        lon, lat = TO4326.transform(cl.x.to_numpy(), cl.y.to_numpy())
        e = pd.DataFrame({"agglomeration": r["agg"], "cluster_id": cl.cluster_id.values, "name": cl.name.values,
                          "n_stops": cl.n_stops.values})
        for v in FEEDV:
            hw = r["cl_tables"][(v, "main")].set_index("cl").reindex(cl.cl)
            e[f"departures_{v}"] = hw.n.fillna(0).astype(int).values
            for k in ("seg", "all"):
                e[f"headway_{k}_{v}"] = [None if not np.isfinite(x) else sig(x) for x in hw[f"h_{k}"].values]
            e[f"dir_status_{v}"] = hw.dir_status.values
            rd = r["cl_tables"][(v, "rail")].set_index("cl").reindex(cl.cl)
            e[f"rail_dph_{v}"] = [sig(x) for x in rd.dph.values]
        e = e[(e.departures_all > 0) | (e.departures_official > 0)]
        lon, lat = lon[e.index], lat[e.index]
        clparts.append(gpd.GeoDataFrame(e.reset_index(drop=True),
                                        geometry=gpd.points_from_xy(np.round(lon, 6), np.round(lat, 6)), crs="EPSG:4326"))
        maskparts.append(mask_polygons(r))
    cells = pd.concat(parts, ignore_index=True)
    cells.to_parquet(LAYERS / "frequent_cells.parquet", index=False)
    clu = pd.concat(clparts, ignore_index=True)
    clu.to_parquet(LAYERS / "frequent_stop_clusters.parquet", index=False)
    mk = pd.concat(maskparts, ignore_index=True)
    mk.to_parquet(LAYERS / "gtfs_coverage_mask.parquet", index=False)
    return {p.name: round((LAYERS / p.name).stat().st_size / 1e6, 2) for p in
            [LAYERS / "frequent_cells.parquet", LAYERS / "frequent_stop_clusters.parquet", LAYERS / "gtfs_coverage_mask.parquet"]}


def mask_polygons(r: dict) -> gpd.GeoDataFrame:
    """All 250 m cells with centre in the FUA (populated or not), mask status per variant, dissolved."""
    agg = r["agg"]
    a = load_agglomeration(agg)
    with rasterio.open(tif_path("ghsl_raw")) as s_:
        tr = s_.transform
    bx = a["fua"].bounds
    c0 = int(np.floor((bx[0] - tr.c) / CELL)); c1 = int(np.ceil((bx[2] - tr.c) / CELL))
    r0 = int(np.floor((tr.f - bx[3]) / CELL)); r1 = int(np.ceil((tr.f - bx[1]) / CELL))
    wt = rasterio.Affine(CELL, 0, tr.c + c0 * CELL, 0, -CELL, tr.f - r0 * CELL)
    shape = (r1 - r0, c1 - c0)
    inside = features.geometry_mask([a["fua"]], out_shape=shape, transform=wt, invert=True)
    rr, cc = np.nonzero(inside)
    xy = np.c_[wt.c + (cc + 0.5) * CELL, wt.f - (rr + 0.5) * CELL]
    out = []
    for v in FEEDV:
        n, m = mask_share(xy, osm_match(agg, v))
        code = np.where(n == 0, 1, np.where(in_mask(n, m), 2, 3)).astype(np.uint8)
        arr = np.zeros(shape, np.uint8)
        arr[rr, cc] = code
        lab = {1: "brak przystanków OSM w 1 km (w masce)", 2: "w masce (dane GTFS)", 3: "poza maską: brak danych"}
        for geom, val in features.shapes(arr, mask=arr > 0, transform=wt, connectivity=4):
            out.append({"agglomeration": agg, "feed_variant": v, "status_code": int(val), "status": lab[int(val)],
                        "geometry": shapely.geometry.shape(geom)})
    g = gpd.GeoDataFrame(out, geometry="geometry", crs="EPSG:2180")
    g = g.dissolve(by=["agglomeration", "feed_variant", "status_code", "status"], as_index=False)
    g = g.to_crs("EPSG:4326")          # reproject the frame, so that the CRS label follows the coordinates
    g["geometry"] = shapely.set_precision(g.geometry.values, 1e-6)
    return g.sort_values(["agglomeration", "feed_variant", "status_code"]).reset_index(drop=True)


# ================================================================== charts
def write_charts(results: list[dict]) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    win = f"{CFG['frequency_window']['start']}–{CFG['frequency_window']['end']}"
    base = {
        "timetable_date": DAY, "window": win, "osm_date": "2026-11-22",
        "population_grid": REC["population_grid"], "population_date": POP_DATE[REC["population_grid"]],
        "feed_variant": REC["feed_variant"], "walk_m": WALK_M,
    }
    curve = {
        **base,
        "title": "Ludność przy częstej komunikacji: odsetek ludności przy progach odstępu",
        "definition": (f"Odsetek ludności mieszkającej ≤ {int(WALK_M)} m pieszo (sieć OSM) od zespołu przystanków "
                       f"(słupki w promieniu {int(CLUSTER_M)} m), na którym w dniu roboczym {DAY} średni odstęp {win} "
                       "na najczęstszym odcinku do następnego przystanku wynosi ≤ T min w obu kierunkach "
                       "(kierunek z geometrii trasy, nie z direction_id). Średnia z okna = 840 min / liczba odjazdów."),
        "thresholds_min": THRESH,
        "recommended_domain": "covered",
        "caveats": [
            "Ludność: GHSL 2020 przeskalowany do siatki spisowej NSP 2021 (1 km); korekta poziomu na 1 km, nie wewnątrz komórki.",
            "Rozkłady 2026, ludność 2020–2021: brak migracji po 2021 r. i nowych osiedli.",
            "Poza maską pokrycia GTFS wynik to 'brak danych'. Wartość dla całej FUA przy pokryciu < 85 % jest zaniżona.",
            "Feedy nieoficjalne (28 z 30 dodanych podmiejskich) nie były weryfikowane z rozkładami przewoźników.",
            "Trójmiasto i GZM: układ wielobiegunowy; miara nie zależy od centrum, ale granice FUA są umowne.",
            "To nie jest wskaźnik ITDP PNFT; replika implementacji ITDP jest w metrics_frequent.csv (itdp_style_*).",
        ],
        "variants_in_metrics": "freq_{seg,all,line,nodir}_{net,euc}_le{T}min; feed_variant official/all; population_grid",
        "cities": {},
    }
    rail = {
        **base, "radius_m": RAIL_M,
        "title": "Ludność przy stacjach kolei i metra według liczby odjazdów (klasy wzorowane na DG REGIO)",
        "definition": (f"Odsetek ludności ≤ {int(RAIL_M)} m pieszo od zespołu przystanków kolei lub metra; klasa = "
                       f"najlepsza osiągalna stacja wg średniej liczby odjazdów na godzinę {win} (oba kierunki razem, "
                       "bez autobusowej komunikacji zastępczej). Klasy: > 10, 4–10, < 4 odjazdów/h."),
        "caveats": ["Tramwaj nie wchodzi do tego wariantu; wariant 'tylko szynowe' (tramwaj + metro + kolej) jest "
                    "w metrics_frequent.csv jako freq_railbound_*, pod własną nazwą (to nie jest ITDP PNRT).",
                    "Kolej: polish_trains (PKP PLK, przepakowanie mkuran.pl) i warsaw_wkd; SKM Warszawa z feedu warsaw_ztm."],
        "cities": {},
    }
    for r in results:
        agg = r["agg"]
        cc, rc = {}, {}
        for dom in ("covered", "core", "fua"):
            v, g = REC["feed_variant"], REC["population_grid"]
            cc[dom] = {
                "share_pct": [sig(pct(share(r, (v, REC["agg"], T, "net"), g, dom, v))) for T in THRESH],
                "share_pct_official_feeds": [sig(pct(share(r, ("official", REC["agg"], T, "net"), g,
                                                            dom if dom != "covered" else "covered", "official")))
                                             for T in THRESH],
                "share_pct_all_lines_variant": [sig(pct(share(r, (v, "all", T, "net"), g, dom, v))) for T in THRESH],
                "coverage_share_pct": sig(100 * coverage(r, g, "core" if dom == "core" else "fua", v)),
                "flag_incomplete": bool(dom != "covered" and coverage(r, g, "core" if dom == "core" else "fua", v) < COV_MIN),
                "population": sig(float(r["cells"].loc[domain_sel(r["cells"], dom, v), f"pop_{g}"].sum())),
            }
            s10 = share(r, (v, "rail>10", 0, "net"), g, dom, v)
            s4 = share(r, (v, "rail4-10", 0, "net"), g, dom, v)
            s0 = share(r, (v, "rail<4", 0, "net"), g, dom, v)
            rc[dom] = {"gt10_pct": sig(pct(s10)), "4to10_pct": sig(pct(s4 - s10)), "lt4_pct": sig(pct(s0 - s4)),
                       "ge4_pct": sig(pct(s4)), "none_pct": sig(pct(1 - s0)),
                       "coverage_share_pct": sig(100 * coverage(r, g, "core" if dom == "core" else "fua", v))}
        name = CFG["agglomerations"][agg]["name"]
        curve["cities"][agg] = {"name": name, "polycentric": bool(CFG["agglomerations"][agg].get("polycentric", False)),
                                "domains": cc}
        rail["cities"][agg] = {"name": name, "domains": rc}
    write_json(CHARTS / "frequent_curve.json", curve)
    write_json(CHARTS / "frequent_rail.json", rail)


# ================================================================== metrics files
FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]


def write_metrics(rows: list[dict]) -> None:
    import csv
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["feed_variant"], m["population_grid"], m["domain"], m["metric"]))
    METRICS.mkdir(parents=True, exist_ok=True)
    write_json(METRICS / "metrics_frequent.json", {"generated_for_timetable_date": DAY, "metrics": rows})
    with open(METRICS / "metrics_frequent.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


# ================================================================== main
def main() -> None:
    import pickle
    import sys
    t0 = time.time()
    for p in (OUT_INT, QA):
        p.mkdir(parents=True, exist_ok=True)
    cache = OUT_INT / "results.pkl"
    if "--report-only" in sys.argv and cache.exists():   # re-run tables / QA / md from the last computation
        with open(cache, "rb") as f:
            results = pickle.load(f)
    else:
        results = []
        for agg in AGGS:
            print(agg, flush=True)
            results.append(run_agg(agg))
        with open(cache, "wb") as f:
            pickle.dump(results, f)
    rows = []
    for r in results:
        rows += metric_rows(r)
    write_metrics(rows)
    write_charts(results)
    sizes = write_layers(results)
    from pipeline.frequent_qa import write_qa
    write_qa(results, rows, sizes)
    # _meta_frequent.json in metrics/ and charts/ is written by frequent_qa.write_qa (_meta.json there is the merge step's)
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
