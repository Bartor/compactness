"""Ease of transfer at stop areas (extra layer approved 2026-11-24, RAPORT §12.2).

    python -m pipeline.transfer_ease                 # 7 phase-1 agglomerations -> layer, metrics, QA note
    python -m pipeline.transfer_ease --report-only   # rebuild tables / note from data/interim/transfer/results.pkl

Own description of interchanges from data already held (GTFS service layer, OSM walk graph, stop clusters), in the
spirit of the transfer-penalty literature (walk, wait and the rest of the transfer cost) and of the Polish AMPTI
interchange assessment, but restricted to what timetables and OSM support.  The components are published side by
side and never blended into one score.  Definitions (all fixed in the Polish note results/qa/transfer/transfer.md):

* Stop area: frequent.clusters (served stops, parent stations, 100 m complete linkage) merged when the nearest member
  stops of two clusters are <= LINK_M apart (LINK_RAIL_M when either cluster has rail or metro departures), then
  split by complete linkage of cluster centres at DMAX_M so that an area never chains along a street.
* Line: feed + route class + route_short_name; rail of the nationwide feed whose route_short_name is a train category
  (no digit: IC, TLK, EIP, ...) is split further by its pair of terminal stops.  A line counts at an area when it has
  >= MIN_LINE_EVENTS departures (for boarding) or arrivals (for alighting) there 06:00-20:00.
* Transfer pair: ordered (A arriving, B departing), A != B, unless the two lines are "parallel": the share of the
  smaller line's stop areas (whole day) that the other line also serves is >= PARALLEL_SHARE (variants of one line,
  short workings, lines sharing most of their route).
* Walk: for each ordered pair the best (alighting stop of A, boarding stop of B), shortest along the OSM walk graph;
  5 km/h; obstacles from pipeline.transfer_walk.
* Wait: expected wait for B for a passenger arriving at a random moment of the window (07-09 and 06-20), from the
  real departure times of B at the area (all stops), per direction (next stop area), averaged over B's main
  directions (>= MAIN_DIR_SHARE of its departures); wait capped at WAIT_CAP_MIN.
* Possible timed connections (approximate): actual waits of A's arrivals at the chosen stop for B's next departure
  after the walk, against the random-arrival expectation at that stop.

Revisions after the literature review (2026-11-24, code version .3; ROADMAP item 9).  All are extra columns; the
earlier ones keep their ids and values:
* Connection wait: per movement, the wait of each scheduled arrival of A (in that arrival direction, in the window)
  for the next departure of B in that departure direction after the walk; mean, median and 90th percentile per
  movement, weighted median / P90 per node over all such arrivals (weight = B's departures in that direction 06-20,
  so a movement weighs n_a x n_b as in the additive trio).  Visit times: A's arrival at the first stop of its run in
  the area, B's departure from the last stop of its run.
* Generalised transfer time (GTT_BAND): published weights only, never used to rank nodes.
* Crossings on the AMPTI W6 scale (pipeline.transfer_walk): mean score per movement over its scored crossings, node
  mean weighted by trips.
* Frequent pairs: share of movements whose A (arrival direction) and B (departure direction) both run on average
  every 10 (15) min or better in 07-09.
* Coordination test restricted to pairs where both lines run every 15 min or less often (headway_a and headway_b
  >= TIMED_MIN_HEADWAY) and, as a positive control, the same test in the night window NIGHT for lines that run
  there (night_timed).
* Node detail (rule main, nodes with >= DETAIL_MIN_DEP_H departures an hour 06-20): path geometry with crossings
  and steps for the best stop pair of every movement; written out by pipeline.transfer_detail.
"""
from __future__ import annotations

import pickle
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from pipeline import frequent as F
from pipeline import gtfs_service as gs
from pipeline.boundaries import load_agglomeration
from pipeline.common import INTERIM, RESULTS, load_config

CFG = load_config()
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
DAY = CFG["reference_day"]
VARIANT = "all"
CODE_VERSION = "transfer-2026-11-24.3"

WALK_KMH = 5.0
M_PER_MIN = WALK_KMH * 1000 / 60
WIN_DAY = (6 * 3600, 20 * 3600)
WIN_AM = (7 * 3600, 9 * 3600)
MIN_LINE_EVENTS = 7            # departures (or arrivals) 06-20 at the area, i.e. on average at least every 2 h
PARALLEL_SHARE = 0.8
MAIN_DIR_SHARE = 0.2
WAIT_CAP_MIN = 60.0
WAIT_STEP_S = 30
TIMED_MIN_HEADWAY = 15.0       # timed-connection test only for onward services at most every 15 min apart or rarer
TIMED_RATIO = 0.5
TIMED_MIN_ARR = 4
STOP_MAX_SNAP_M = F.STOP_MAX_SNAP_M
DETOUR_MIN_STRAIGHT_M = 30.0
NIGHT = (23 * 3600, 28 * 3600 + 1800)   # positive control of the coordination test: 23:00-04:30 of the service day
NIGHT_MAX_HEADWAY = 60.0                # ... for lines that run there at least hourly on average (a night network)
PULSE_CYCLE_MIN = 30                    # pulse test: departures folded on a 30-min cycle ...
PULSE_BIN_MIN = 3                       # ... in 3-min bins; a node pulses when its busiest bin is above the
PULSE_Q = 0.99                          # ... 99th percentile of that share for the same number of uniform departures
PULSE_MIN_DEP = 20
PULSE_SIMS = 1000
FREQ_HEADWAYS = (10.0, 15.0)            # "frequent x frequent" movements: both lines at least this often, 07-09
DETAIL_MIN_DEP_H = 20.0                 # node detail export: nodes with at least this many departures an hour 06-20
# Generalised transfer time in equivalent in-vehicle minutes: walk x a + wait x b + fixed penalty P.
# a: Wardman 1998 (ITS Leeds WP 525, s. 4.1) 1.66; low variant 1.2 (Ortelli et al. 2026, STRC, pooled 1.21).
# b: Wardman 1998 (s. 4.4) 1.47.  P: 5 (Ortelli et al. 2026, residual penalty 5-9), 13 and 18 (Jara-Diaz et al.
# 2022, planning range 13-18).  Published beside the components, never used to rank nodes.
GTT_BAND = {"low": (1.2, 1.47, 5.0), "central": (1.66, 1.47, 13.0), "high": (1.66, 1.47, 18.0)}

RULES = {   # stop-area rules: main + sensitivity
    "main": {"link_m": 150.0, "link_rail_m": 250.0, "dmax_m": 400.0, "dmax_rail_m": 600.0},
    "clusters100": {"link_m": 0.0, "link_rail_m": 0.0, "dmax_m": 100.0, "dmax_rail_m": 100.0},
    "wide": {"link_m": 250.0, "link_rail_m": 350.0, "dmax_m": 600.0, "dmax_rail_m": 800.0},
}

OUT_INT = INTERIM / "transfer"
LAYERS = RESULTS / "layers"
METRICS = RESULTS / "metrics"
QA = RESULTS / "qa" / "transfer"
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


# ================================================================== stop areas
def areas(s: pd.DataFrame, cl: pd.DataFrame, rail_cl: np.ndarray, rule: dict) -> np.ndarray:
    """Area label per frequent cluster (index = cl.cl)."""
    n = len(cl)
    if rule["link_m"] <= 0:
        return np.arange(n)
    lmax = max(rule["link_m"], rule["link_rail_m"])
    xy = s[["x", "y"]].to_numpy()
    pairs = cKDTree(xy).query_pairs(lmax, output_type="ndarray")
    ca, cb = s.cl.to_numpy()[pairs[:, 0]], s.cl.to_numpy()[pairs[:, 1]]
    d = np.hypot(*(xy[pairs[:, 0]] - xy[pairs[:, 1]]).T)
    ok = (ca != cb) & ((d <= rule["link_m"]) | ((d <= rule["link_rail_m"]) & (rail_cl[ca] | rail_cl[cb])))
    g = coo_matrix((np.ones(int(ok.sum())), (ca[ok], cb[ok])), shape=(n, n))
    _, comp = connected_components(g, directed=False)
    cxy = cl[["x", "y"]].to_numpy()
    lab = np.zeros(n, dtype=np.int64)
    nxt = 0
    order = np.argsort(comp, kind="stable")
    bounds = np.flatnonzero(np.r_[True, np.diff(comp[order]) != 0, True])
    for a, b in zip(bounds[:-1], bounds[1:]):
        idx = order[a:b]
        if len(idx) == 1:
            lab[idx] = nxt; nxt += 1
            continue
        p = cxy[idx]
        dmax = rule["dmax_rail_m"] if rail_cl[idx].any() else rule["dmax_m"]
        dm = np.max(np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1]))
        if dm <= dmax:
            lab[idx] = nxt; nxt += 1
            continue
        f = fcluster(linkage(p, method="complete"), t=dmax, criterion="distance")
        for k in np.unique(f):
            lab[idx[f == k]] = nxt; nxt += 1
    return lab


# ================================================================== lines and visits
def _norm(s: pd.Series) -> pd.Series:
    return gs._norm_name(s.astype(object))


def line_keys(st: pd.DataFrame, stops: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """line key per trip uid and a line table (key, label, mode)."""
    first = st.groupby("uid", sort=False).head(1).set_index("uid")
    last = st.groupby("uid", sort=False).tail(1).set_index("uid")
    nm = stops.set_index("suid").stop_name
    rsn = first.route_short_name.astype(str)
    cls = first.route_class.astype(str)
    key = first.feed.astype(str) + "|" + cls + "|" + rsn
    cat = (first.feed == "polish_trains") & (cls == "rail") & ~rsn.str.contains(r"\d", regex=True)
    if cat.any():
        e1 = _norm(first.suid.map(nm)).to_numpy()
        e2 = _norm(last.suid.reindex(first.index).map(nm)).to_numpy()
        ends = np.where(e1 <= e2, pd.Series(e1) + " - " + pd.Series(e2), pd.Series(e2) + " - " + pd.Series(e1))
        key = key.where(~cat, key + "|" + pd.Series(ends, index=key.index))
    lines = pd.DataFrame({"line": key.to_numpy(), "label": rsn.to_numpy(), "mode": cls.to_numpy(),
                          "feed": first.feed.to_numpy()}).drop_duplicates("line").sort_values("line")
    return key, lines.reset_index(drop=True)


def visits(st: pd.DataFrame, area_of: pd.Series, line_of: pd.Series) -> pd.DataFrame:
    """One row per (trip, consecutive run of stops in one area)."""
    a = st.suid.map(area_of).to_numpy()
    uid = st.uid.to_numpy()
    new = np.r_[True, (uid[1:] != uid[:-1]) | (a[1:] != a[:-1])]
    start = np.flatnonzero(new)
    end = np.r_[start[1:], len(st)] - 1
    v = pd.DataFrame({"uid": uid[start], "area": a[start], "arr": st.arr_s.to_numpy()[start].astype(float),
                      "dep": st.dep_s.to_numpy()[end].astype(float), "s_in": st.suid.to_numpy()[start],
                      "s_out": st.suid.to_numpy()[end]})
    same_prev = np.r_[False, uid[start][1:] == uid[start][:-1]]
    same_next = np.r_[uid[start][:-1] == uid[start][1:], False]
    v["is_first"], v["is_last"] = ~same_prev, ~same_next
    v["next_area"] = np.where(same_next, np.r_[v.area.to_numpy()[1:], -1], -1)
    v["prev_area"] = np.where(same_prev, np.r_[-1, v.area.to_numpy()[:-1]], -1)
    v["line"] = v.uid.map(line_of).to_numpy()
    return v


# ================================================================== waits
def expected_wait(dep_s: np.ndarray, win: tuple[int, int]) -> float | None:
    """Mean wait (min) for a passenger arriving uniformly in the window, from sorted departure seconds (whole day).

    None when there is no departure from the window start to the window end + cap."""
    d = np.sort(dep_s)
    if not len(d) or not ((d >= win[0]) & (d < win[1] + WAIT_CAP_MIN * 60)).any():
        return None
    t = np.arange(win[0], win[1], WAIT_STEP_S, dtype=float) + WAIT_STEP_S / 2
    j = np.searchsorted(d, t, side="left")
    w = np.where(j < len(d), d[np.minimum(j, len(d) - 1)] - t, np.inf) / 60.0
    return float(np.minimum(w, WAIT_CAP_MIN).mean())


def line_waits(v: pd.DataFrame) -> pd.DataFrame:
    """Per (area, line): departures in the windows and the direction-averaged expected wait."""
    d = v[~v.is_last]
    rows = []
    for (area, line), g in d.groupby(["area", "line"], sort=True):
        dd = g[(g.dep >= WIN_DAY[0]) & (g.dep < WIN_DAY[1])]
        if dd.empty:
            continue
        cnt = dd.groupby("next_area").size()
        main = cnt.index[cnt >= MAIN_DIR_SHARE * cnt.sum()]
        w, per_dir = {}, {}
        for nm, win in (("am", WIN_AM), ("day", WIN_DAY)):
            vals = []
            for k in main:
                x = expected_wait(g.loc[g.next_area == k, "dep"].to_numpy(), win)
                per_dir.setdefault(int(k), {})[nm] = x
                if x is not None:
                    vals.append(x)
            w[nm] = float(np.mean(vals)) if vals else None
        rows.append({"area": area, "line": line, "n_dep_day": len(dd), "n_dirs": len(main),
                     "n_dep_am": int(((g.dep >= WIN_AM[0]) & (g.dep < WIN_AM[1])).sum()),
                     "wait_am": w["am"], "wait_day": w["day"], "dir_waits": per_dir})
    return pd.DataFrame(rows)


# ================================================================== per agglomeration
def prepare(agg: str) -> dict:
    """Day-independent inputs shared by all area rules."""
    s, cl = F.clusters(agg)
    st = gs.stop_times(agg, DAY, VARIANT)
    ok = np.isfinite(st.x.to_numpy(float)) & np.isfinite(st.y.to_numpy(float))
    st = st[ok].reset_index(drop=True)
    st = st[st.suid.isin(set(s.suid))].reset_index(drop=True)
    trips = gs.active_trips(agg, DAY, VARIANT)[["uid", "is_replacement_bus", "block_id"]]
    rail_suid = set(st.loc[st.route_class.isin(["rail", "metro"]), "suid"])
    s = s.copy()
    s["rail"] = s.suid.isin(rail_suid)
    rail_cl = s.groupby("cl").rail.any().reindex(cl.cl).fillna(False).to_numpy()
    line_of, lines = line_keys(st, s)
    # per stop and trip position: first / last row of the trip
    uid = st.uid.to_numpy()
    st["is_first_row"] = np.r_[True, uid[1:] != uid[:-1]]
    st["is_last_row"] = np.r_[uid[:-1] != uid[1:], True]
    st["line"] = st.uid.map(line_of).to_numpy()
    # terminus of each trip (last served stop in the stop clusters): the "kierunek" shown in the node detail
    nm = s.drop_duplicates("suid").set_index("suid").stop_name
    term_of = st[st.is_last_row].set_index("uid").suid.map(nm)
    return {"agg": agg, "stops": s, "clusters": cl, "st": st, "rail_cl": rail_cl, "line_of": line_of,
            "lines": lines, "trips": trips, "term_of": term_of}


def run_rule(P: dict, rule_name: str, G) -> dict:
    from pipeline.transfer_walk import area_paths
    agg, s, cl, st = P["agg"], P["stops"], P["clusters"], P["st"]
    rule = RULES[rule_name]
    lab_cl = areas(s, cl, P["rail_cl"], rule)
    s = s.assign(area=lab_cl[s.cl.to_numpy()])
    area_of = s.set_index("suid").area
    v = visits(st, area_of, P["line_of"])
    # counted lines per area
    vd = v[(~v.is_last) & (v.dep >= WIN_DAY[0]) & (v.dep < WIN_DAY[1])]
    va = v[(~v.is_first) & (v.arr >= WIN_DAY[0]) & (v.arr < WIN_DAY[1])]
    ndep = vd.groupby(["area", "line"]).size().rename("n_dep")
    narr = va.groupby(["area", "line"]).size().rename("n_arr")
    al = pd.concat([ndep, narr], axis=1).fillna(0).astype(int).reset_index()
    al["board"] = al.n_dep >= MIN_LINE_EVENTS
    al["alight"] = al.n_arr >= MIN_LINE_EVENTS
    # parallel test: stop areas served by each line over the whole day
    served = v.groupby("line").area.apply(lambda x: frozenset(x.unique()))
    # boarding / alighting stops per (area, line) in the day window
    rows = st[(st.dep_s >= WIN_DAY[0]) & (st.dep_s < WIN_DAY[1]) & ~st.is_last_row]
    board_st = rows.groupby([rows.suid.map(area_of), rows.line]).suid.apply(lambda x: sorted(set(x)))
    rows = st[(st.arr_s >= WIN_DAY[0]) & (st.arr_s < WIN_DAY[1]) & ~st.is_first_row]
    alight_st = rows.groupby([rows.suid.map(area_of), rows.line]).suid.apply(lambda x: sorted(set(x)))
    waits = line_waits(v).set_index(["area", "line"])
    arr_dirs, dep_dirs = direction_groups(va, vd)
    dir_waits = {(r.area, r.line): r.dir_waits for r in waits.reset_index().itertuples()}
    waits = waits.drop(columns="dir_waits")
    dinfo = direction_info(v, P["term_of"])
    conn_acc: dict = {}
    # node detail: busy nodes of the main rule keep the geometry of their movement paths
    dep_h = vd.groupby("area").size() / ((WIN_DAY[1] - WIN_DAY[0]) / 3600)
    detail_areas = set(dep_h.index[dep_h >= DETAIL_MIN_DEP_H]) if rule_name == "main" else set()
    detail_paths: dict = {}
    mov_rows = []
    sxy = s.set_index("suid")[["x", "y"]]
    srail = s.set_index("suid").rail
    snap_max = np.where(s.rail.to_numpy(), STOP_MAX_SNAP_M["rail"], STOP_MAX_SNAP_M["default"])
    se, stt, sd = G.snap(s[["x", "y"]].to_numpy(), snap_max)
    snap = pd.DataFrame({"e": se, "t": stt, "d": sd}, index=s.suid)
    pair_rows = []
    node_all = {}
    for area, g in al.groupby("area", sort=True):
        A = g[g.alight].line.tolist()
        B = g[g.board].line.tolist()
        cand = [(a, b) for a in A for b in B if a != b]
        if not cand:
            continue
        good = []
        for a, b in cand:
            sa, sb = served[a], served[b]
            inter = len(sa & sb) / min(len(sa), len(sb))
            good.append((a, b, inter >= PARALLEL_SHARE, inter))
        if not any(not x[2] for x in good):
            continue
        m0 = len(mov_rows)
        stops_here = sorted(set().union(*[alight_st.get((area, a), []) for a, b, par, _ in good if not par],
                                        *[board_st.get((area, b), []) for a, b, par, _ in good if not par]))
        idx = {sid: i for i, sid in enumerate(stops_here)}
        xy = sxy.reindex(stops_here).to_numpy()
        sn = snap.reindex(stops_here)
        need = set()
        for a, b, par, _ in good:
            if par:
                continue
            for x in alight_st.get((area, a), []):
                for y in board_st.get((area, b), []):
                    if x != y:
                        need.add((idx[x], idx[y]))
        paths = area_paths(G, xy, sn.e.to_numpy(), sn.t.to_numpy(), sn.d.to_numpy(), sorted(need), all_pairs=True,
                           geom=area in detail_areas)
        node_all[area] = paths.pop("_all", {"n": 0, "mean_net_m": None, "mean_straight_m": None})
        for a, b, par, inter in good:
            rec = {"area": area, "line_a": a, "line_b": b, "parallel": par, "overlap": inter,
                   "n_arr_a": int(narr.get((area, a), 0)), "n_dep_b": int(ndep.get((area, b), 0))}
            if not par:
                best = None
                for x in alight_st.get((area, a), []):
                    for y in board_st.get((area, b), []):
                        if x == y:
                            cand_ = (0.0, 0, x, y, None)
                        else:
                            p = paths.get((idx[x], idx[y]))
                            if p is None or not np.isfinite(p["dist_m"]):
                                continue
                            cand_ = (p["dist_m"], p["crossings"], x, y, p)
                        if best is None or cand_[:4] < best[:4]:
                            best = cand_
                sf = None
                for x in alight_st.get((area, a), []):
                    for y in board_st.get((area, b), []):
                        if x == y:
                            val = 0.0
                        else:
                            p = paths.get((idx[x], idx[y]))
                            val = p["dist_stepfree_m"] if p is not None else np.inf
                        sf = val if sf is None else min(sf, val)
                if best is not None and best[4] is not None and srail.get(best[2], False) and srail.get(best[3], False)                         and np.hypot(*(sxy.loc[best[2]].to_numpy() - sxy.loc[best[3]].to_numpy())) < 1.0:
                    # two rail / metro stop_ids at one point: platforms are not located in the feed
                    rec.update({"stop_a": best[2], "stop_b": best[3], "walk_m": None, "platform_unknown": True,
                                "rail_involved": True})
                    best = None
                if best is not None:
                    dist, _, x, y, p = best
                    rec.update({"stop_a": x, "stop_b": y, "walk_m": dist, "same_stop": x == y,
                                "straight_m": float(np.hypot(*(sxy.loc[x].to_numpy() - sxy.loc[y].to_numpy()))),
                                "stepfree_m": sf if sf is not None and np.isfinite(sf) else None,
                                "rail_involved": bool(srail.get(x, False) or srail.get(y, False))})
                    if p is not None:
                        rec.update({k: p[k] for k in ("crossings", "crossings_signal", "crossings_tagged",
                                                      "crossings_value", "crossings_track", "steps", "tunnel",
                                                      "bridge", "road_m", "len_m")})
                    else:
                        rec.update({"crossings": 0, "crossings_signal": 0, "crossings_tagged": 0,
                                    "crossings_value": 0, "crossings_track": 0, "steps": False, "tunnel": False,
                                    "bridge": False, "road_m": 0.0, "len_m": 0.0})
                mv = []
                rec.update(directional(arr_dirs.get((area, a), []), dep_dirs.get((area, b), []), idx, paths, srail, sxy,
                                       dir_waits.get((area, b)), mv,
                                       {"area": area, "line_a": a, "line_b": b, "dinfo": dinfo, "conn": conn_acc}))
                for m_ in mv:
                    mov_rows.append({"area": area, **m_})
                wb = waits.loc[(area, b)] if (area, b) in waits.index else None
                rec["wait_am"] = None if wb is None else wb["wait_am"]
                rec["wait_day"] = None if wb is None else wb["wait_day"]
            pair_rows.append(rec)
        if area in detail_areas:
            used = {(m_["stop_a"], m_["stop_b"]) for m_ in mov_rows[m0:] if m_["stop_a"] != m_["stop_b"]}
            keep = {}
            for x, y in sorted(used):
                p = paths.get((idx[x], idx[y]))
                if p is not None and "xy" in p:
                    keep[(x, y)] = {k: p[k] for k in ("xy", "xings", "steps_xy", "dist_m", "steps", "crossings")}
            detail_paths[area] = keep
    pairs = pd.DataFrame(pair_rows)
    timed = timed_connections(P, pairs[~pairs.parallel & pairs.get("stop_a", pd.Series(dtype=object)).notna()]
                              if len(pairs) else pairs)
    night = night_timed(P, s, v, served, G, snap) if rule_name == "main" else None
    pulse = pulse_nodes(v) if rule_name == "main" else None
    conn_node = []
    for (area, nm), lst in sorted(conn_acc.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        w = np.concatenate([x for x, _ in lst])
        wt = np.concatenate([np.full(len(x), q) for x, q in lst])
        conn_node.append({"area": area, "win": nm, "median": _wq(pd.Series(w), pd.Series(wt), .5),
                          "p90": _wq(pd.Series(w), pd.Series(wt), .9), "n_events": int(len(w))})
    conn_node = pd.DataFrame(conn_node, columns=["area", "win", "median", "p90", "n_events"])
    return {"agg": agg, "rule": rule_name, "stops": s[["suid", "cl", "area", "x", "y", "stop_name", "rail"]],
            "visits_dep": vd[["area", "line", "dep"]], "visits_dep_am": None, "al": al, "pairs": pairs,
            "timed": timed, "waits": waits.reset_index(), "node_all": node_all,
            "movements": pd.DataFrame(mov_rows, columns=MOV_COLS), "conn_node": conn_node, "night": night, "pulse": pulse,
            "detail": {"areas": sorted(detail_areas), "paths": detail_paths, "term_arr": {
                k: t for k, t in dinfo["term_arr"].items() if k[0] in detail_areas}, "term_dep": {
                k: t for k, t in dinfo["term_dep"].items() if k[0] in detail_areas}} if rule_name == "main" else None,
            "snap_unsnapped": int(np.isinf(sd).sum()), "n_stops": int(len(s))}


MOV_COLS = ["area", "walk_m", "wait_am", "wait_day", "weight", "line_a", "prev_a", "line_b", "next_b", "stop_a",
            "stop_b", "n_a", "n_b", "n_a_am", "n_b_am", "crossings", "steps", "w6_n", "w6_hi_sum", "w6_lo_sum",
            "x_grade", "x_signal", "x_zebra", "x_unmarked", "x_unknown", "conn_am_mean", "conn_am_med", "conn_am_p90",
            "conn_day_mean", "conn_day_med", "conn_day_p90"]


def _obs_wait(ta: np.ndarray, db: np.ndarray, walk_s: float) -> np.ndarray:
    """Mean actual wait (min, capped) of arrivals ta (rows: shifted copies) for the next departure in db."""
    ready = ta + walk_s
    j = np.searchsorted(db, ready, side="left")
    w = np.where(j < len(db), db[np.minimum(j, len(db) - 1)] - ready, np.inf) / 60
    return np.minimum(w, WAIT_CAP_MIN).mean(axis=-1)


def direction_groups(va: pd.DataFrame, vd: pd.DataFrame) -> tuple[dict, dict]:
    """Main arrival directions (by previous stop area) and departure directions (by next stop area) per (area, line).

    arr: list of (prev_area, continuing next_area or -1, stops, arrivals 06-20);
    dep: list of (next_area, stops, departures 06-20)."""
    arr, dep = {}, {}
    for (area, line), g in va.groupby(["area", "line"], sort=True):
        cnt = g.groupby("prev_area").size()
        out = []
        for k in sorted(cnt.index[cnt >= MAIN_DIR_SHARE * cnt.sum()]):
            h = g[g.prev_area == k]
            nxt = h.next_area.value_counts()
            nxt = int(nxt.sort_index().idxmax()) if len(nxt) else -1
            out.append((int(k), nxt, sorted(set(h.s_in) | set(h.s_out)), int(cnt[k])))
        arr[(area, line)] = out
    for (area, line), g in vd.groupby(["area", "line"], sort=True):
        cnt = g.groupby("next_area").size()
        dep[(area, line)] = [(int(k), sorted(set(g.loc[g.next_area == k, "s_in"]) | set(g.loc[g.next_area == k, "s_out"])),
                              int(cnt[k])) for k in sorted(cnt.index[cnt >= MAIN_DIR_SHARE * cnt.sum()])]
    return arr, dep


def direction_info(v: pd.DataFrame, term_of: pd.Series) -> dict:
    """Per arrival direction (area, line, previous area) the sorted arrival times, per departure direction (area, line,
    next area) the sorted departure times (whole service day), and the most common terminus of each direction."""
    out = {"arr_t": {}, "dep_t": {}, "term_arr": {}, "term_dep": {}}
    va = v[~v.is_first]
    vd = v[~v.is_last]
    for key, src, col, tcol in (("arr", va, "prev_area", "arr"), ("dep", vd, "next_area", "dep")):
        t = src[tcol].to_numpy(float)
        d = out[f"{key}_t"]
        for k, ix in src.groupby(["area", "line", col], sort=True).indices.items():
            d[(k[0], k[1], int(k[2]))] = np.sort(t[ix])
        tm = src[["area", "line", col]].assign(term=src.uid.map(term_of).fillna("").to_numpy())
        c = tm.groupby(["area", "line", col, "term"], sort=True).size().rename("n").reset_index()
        c = c.sort_values(["area", "line", col, "n", "term"], ascending=[True, True, True, False, True], kind="stable")
        c = c.drop_duplicates(["area", "line", col])
        out[f"term_{key}"] = {(r[0], r[1], int(r[2])): r[3] for r in zip(c.area, c.line, c[col], c.term)}
    return out


def _conn_waits(ta: np.ndarray, db: np.ndarray, walk_s: float, win: tuple[int, int]) -> np.ndarray | None:
    """Connection waits (min, capped) of the arrivals ta inside the window for the next departure in db after the
    walk; None when there is no arrival in the window or no departure from the window start to its end + cap."""
    a = ta[(ta >= win[0]) & (ta < win[1])]
    if not len(a) or db is None or not len(db) or not ((db >= win[0]) & (db < win[1] + WAIT_CAP_MIN * 60)).any():
        return None
    ready = a + walk_s
    j = np.searchsorted(db, ready, side="left")
    w = np.where(j < len(db), db[np.minimum(j, len(db) - 1)] - ready, np.inf) / 60.0
    return np.minimum(w, WAIT_CAP_MIN)


def _n_in(t: np.ndarray | None, win: tuple[int, int]) -> int:
    return 0 if t is None else int(((t >= win[0]) & (t < win[1])).sum())


def directional(adirs: list, bdirs: list, idx: dict, paths: dict, srail, sxy, bwait: dict | None = None,
                movements: list | None = None, ctx: dict | None = None) -> dict:
    """Direction-aware walk of an ordered pair: mean over the valid movements (A's main arrival direction x B's main
    departure direction), a movement being valid unless B leaves towards the stop area A continues to (no reason to
    change) or back towards where A came from.  Per movement the shortest pair of stops; rail-rail at one point = unknown.

    With ``movements`` (a list) one dict per movement is appended: walk, the random-arrival waits of B in that
    direction, the weight n_a x n_b, the connection waits (with ``ctx``: area, line_a, line_b, direction_info,
    accumulator ``conn`` of per-node events), the 07-09 counts for the frequency classes and the W6 sums of the path."""
    walks, cross, steps, free, unknown = [], [], [], [], 0
    bwait = bwait or {}
    for prev_a, next_a, sa, n_a in adirs:
        for next_b, sb, n_b in bdirs:
            if (next_a >= 0 and next_b == next_a) or (prev_a >= 0 and next_b == prev_a):
                continue
            best = None
            sf = np.inf
            rail_point = False
            for x in sa:
                for y in sb:
                    if x == y:
                        c = (0.0, 0, False, x, y, None)
                        sf = 0.0
                    else:
                        if x not in idx or y not in idx:
                            continue
                        p = paths.get((idx[x], idx[y]))
                        if p is None or not np.isfinite(p["dist_m"]):
                            continue
                        if srail.get(x, False) and srail.get(y, False) and                                 np.hypot(*(sxy.loc[x].to_numpy() - sxy.loc[y].to_numpy())) < 1.0:
                            rail_point = True
                            continue
                        c = (p["dist_m"], p["crossings"], p["steps"], x, y, p)
                        sf = min(sf, p["dist_stepfree_m"])
                    if best is None or c[:2] < best[:2]:
                        best = c
            if best is None:
                unknown += int(rail_point)
                continue
            walks.append(best[0]); cross.append(best[1]); steps.append(best[2]); free.append(np.isfinite(sf))
            if movements is not None:
                wd = bwait.get(next_b, {})
                rec = {"walk_m": best[0], "wait_am": wd.get("am"), "wait_day": wd.get("day"),
                       "weight": float(n_a * n_b), "prev_a": int(prev_a), "next_b": int(next_b),
                       "stop_a": best[3], "stop_b": best[4], "n_a": int(n_a), "n_b": int(n_b),
                       "crossings": int(best[1]), "steps": bool(best[2])}
                p = best[5]
                cnt = p["w6_counts"] if p is not None else {}
                rec.update({"w6_n": int(p["w6_n"]) if p is not None else 0,
                            "w6_hi_sum": float(p["w6_hi_sum"]) if p is not None else 0.0,
                            "w6_lo_sum": float(p["w6_lo_sum"]) if p is not None else 0.0,
                            **{f"x_{k}": int(cnt.get(k, 0)) for k in ("grade", "signal", "zebra", "unmarked", "unknown")}})
                if ctx is not None:
                    di = ctx["dinfo"]
                    ta = di["arr_t"].get((ctx["area"], ctx["line_a"], int(prev_a)))
                    db = di["dep_t"].get((ctx["area"], ctx["line_b"], int(next_b)))
                    rec["line_a"], rec["line_b"] = ctx["line_a"], ctx["line_b"]
                    rec["n_a_am"], rec["n_b_am"] = _n_in(ta, WIN_AM), _n_in(db, WIN_AM)
                    walk_s = best[0] / M_PER_MIN * 60
                    for nm, win in (("am", WIN_AM), ("day", WIN_DAY)):
                        w = _conn_waits(ta, db, walk_s, win) if ta is not None else None
                        if w is None:
                            rec.update({f"conn_{nm}_mean": None, f"conn_{nm}_med": None, f"conn_{nm}_p90": None})
                            continue
                        rec.update({f"conn_{nm}_mean": float(w.mean()), f"conn_{nm}_med": float(np.quantile(w, .5)),
                                    f"conn_{nm}_p90": float(np.quantile(w, .9))})
                        ctx["conn"].setdefault((ctx["area"], nm), []).append((w, float(n_b)))
                movements.append(rec)
    if not walks:
        return {"walk_dir_m": None, "crossings_dir": None, "steps_dir": None, "stepfree_dir": None,
                "n_movements": 0, "n_movements_unknown": unknown}
    return {"walk_dir_m": float(np.mean(walks)), "crossings_dir": float(np.mean(cross)),
            "steps_dir": float(np.mean(steps)), "stepfree_dir": float(np.mean(free)), "n_movements": len(walks),
            "n_movements_unknown": unknown}


def timed_connections(P: dict, pairs: pd.DataFrame) -> pd.DataFrame:
    """Approximate test for scheduled timed connections on the chosen stop pair of each line pair.

    Only onward lines B with an average headway >= TIMED_MIN_HEADWAY 06-20 at the chosen stop are tested.  The
    observed mean wait of A's arrivals (after the walk) is compared with the same quantity for A's timetable shifted
    by 1, 2, ..., h_B - 1 minutes.  ``rank`` = share of shifts that give a strictly shorter wait; a pair is a
    candidate when rank <= 0.1 and the observed wait <= TIMED_RATIO x the random-arrival wait.  With unrelated
    timetables about one pair in ten passes the rank condition by chance."""
    cols = ["area", "line_a", "line_b", "n_arr", "obs_wait", "rand_wait", "headway_b", "rank", "timed",
            "headway_a", "mode_a", "mode_b", "both_infrequent"]
    if pairs is None or not len(pairs) or "stop_a" not in pairs:
        return pd.DataFrame(columns=cols)
    mode = P["lines"].set_index("line")["mode"]
    pairs = pairs[pd.to_numeric(pairs.walk_m, errors="coerce").notna()]
    st = P["st"]
    arr = st[~st.is_first_row & (st.arr_s >= WIN_DAY[0]) & (st.arr_s < WIN_DAY[1])]
    arr_g = {k: np.sort(g.arr_s.to_numpy(float)) for k, g in arr.groupby(["suid", "line"])}
    dep = st[~st.is_last_row]
    dep_g = {k: np.sort(g.dep_s.to_numpy(float)) for k, g in dep.groupby(["suid", "line"])}
    rows = []
    for r in pairs.itertuples():
        ta = arr_g.get((r.stop_a, r.line_a))
        db = dep_g.get((r.stop_b, r.line_b))
        if ta is None or db is None or len(ta) < TIMED_MIN_ARR:
            continue
        nwin = ((db >= WIN_DAY[0]) & (db < WIN_DAY[1])).sum()
        if nwin == 0:
            continue
        hw = (WIN_DAY[1] - WIN_DAY[0]) / 60 / nwin
        if hw < TIMED_MIN_HEADWAY:
            continue
        rnd = expected_wait(db, WIN_DAY)
        if rnd is None or rnd <= 0:
            continue
        walk_s = float(r.walk_m) / M_PER_MIN * 60
        obs = float(_obs_wait(ta, db, walk_s))
        k = np.arange(1, int(min(round(hw), WAIT_CAP_MIN)))
        shifted = _obs_wait(ta[None, :] + k[:, None] * 60.0, db, walk_s) if len(k) else np.array([])
        rank = float((shifted < obs - 1e-9).mean()) if len(shifted) else None
        hw_a = (WIN_DAY[1] - WIN_DAY[0]) / 60 / len(ta)
        rows.append({"area": r.area, "line_a": r.line_a, "line_b": r.line_b, "n_arr": len(ta), "obs_wait": obs,
                     "rand_wait": rnd, "headway_b": hw, "rank": rank,
                     "timed": bool(rank is not None and rank <= 0.1 and obs <= TIMED_RATIO * rnd),
                     "headway_a": hw_a, "mode_a": mode.get(r.line_a), "mode_b": mode.get(r.line_b),
                     "both_infrequent": bool(hw_a >= TIMED_MIN_HEADWAY)})
    return pd.DataFrame(rows, columns=cols)


def shift_test(ta: np.ndarray, db: np.ndarray, walk_s: float, win: tuple[int, int]) -> dict | None:
    """The shift test of timed_connections on one pair in a window: observed mean wait of the arrivals ta after the
    walk against A's timetable shifted by 1 .. h_B - 1 minutes (h_B = B's mean headway in the window)."""
    nwin = int(((db >= win[0]) & (db < win[1])).sum())
    if len(ta) < TIMED_MIN_ARR or nwin == 0:
        return None
    hw = (win[1] - win[0]) / 60 / nwin
    rnd = expected_wait(db, win)
    if rnd is None or rnd <= 0:
        return None
    obs = float(_obs_wait(ta, db, walk_s))
    k = np.arange(1, int(min(round(hw), WAIT_CAP_MIN)))
    shifted = _obs_wait(ta[None, :] + k[:, None] * 60.0, db, walk_s) if len(k) else np.array([])
    rank = float((shifted < obs - 1e-9).mean()) if len(shifted) else None
    return {"n_arr": int(len(ta)), "obs_wait": obs, "rand_wait": rnd, "headway_b": hw,
            "headway_a": (win[1] - win[0]) / 60 / len(ta), "rank": rank,
            "timed": bool(rank is not None and rank <= 0.1 and obs <= TIMED_RATIO * rnd)}


def _window_max(h: np.ndarray) -> np.ndarray:
    """Largest count in PULSE_BIN_MIN consecutive minutes of a cyclic minute histogram (last axis)."""
    return np.max(sum(np.roll(h, -k, axis=-1) for k in range(PULSE_BIN_MIN)), axis=-1)


def pulse_nodes(v: pd.DataFrame) -> pd.DataFrame:
    """Node-level pulse test (no walk, no arrival times).  In a window (day 06-20, night NIGHT) the departures of the
    lines that run every 15 min or less often there (night: every 15-60 min) are folded on a PULSE_CYCLE_MIN cycle
    (whole minutes, as in GTFS); the statistic is the share of them in the busiest PULSE_BIN_MIN consecutive minutes.
    Null: each line keeps its own timetable and is rotated by an independent random whole-minute offset
    (PULSE_SIMS rotations, seed from the node), so a single regular line or several unrelated ones do not count as a
    pulse; only lines whose departures line up do.  A node pulses when the observed share is above the PULSE_Q
    quantile of the null.  It also finds pulses coded as arrival = departure in the same minute at different stops,
    which the pair test with the walk misses."""
    rows = []
    d = v[~v.is_last]
    for win_name, win, hmax in (("day", WIN_DAY, None), ("night", NIGHT, NIGHT_MAX_HEADWAY)):
        x = d[(d.dep >= win[0]) & (d.dep < win[1])]
        if x.empty:
            continue
        wmin = (win[1] - win[0]) / 60
        hw = wmin / x.groupby(["area", "line"]).dep.transform("size")
        ok = hw >= TIMED_MIN_HEADWAY
        if hmax is not None:
            ok &= hw <= hmax
        x = x[ok.to_numpy()]
        for area, g in x.groupby("area", sort=True):
            nl = g.line.nunique()
            if len(g) < PULSE_MIN_DEP or nl < 2:
                continue
            mins = ((g.dep.to_numpy() // 60) % PULSE_CYCLE_MIN).astype(int)
            li = pd.factorize(g.line, sort=True)[0]
            H = np.zeros((nl, PULSE_CYCLE_MIN))
            np.add.at(H, (li, mins), 1)
            obs = float(_window_max(H.sum(axis=0)) / len(g))
            rng = np.random.default_rng(int(area) + (0 if win_name == "day" else 10 ** 7))
            off = rng.integers(0, PULSE_CYCLE_MIN, size=(PULSE_SIMS, nl))
            m = (np.arange(PULSE_CYCLE_MIN)[None, None, :] - off[:, :, None]) % PULSE_CYCLE_MIN
            sim = H[np.arange(nl)[None, :, None], m].sum(axis=1)
            null = float(np.quantile(_window_max(sim) / len(g), PULSE_Q))
            hh = H.sum(axis=0)
            peak = int(np.argmax(sum(np.roll(hh, -k) for k in range(PULSE_BIN_MIN))))
            rows.append({"area": area, "win": win_name, "n_dep": int(len(g)), "n_lines": int(nl),
                         "peak_minute": peak, "max_share": obs, "null_q": null, "pulse": bool(obs > null + 1e-12)})
    return pd.DataFrame(rows, columns=["area", "win", "n_dep", "n_lines", "peak_minute", "max_share", "null_q",
                                       "pulse"])


def night_timed(P: dict, s: pd.DataFrame, v: pd.DataFrame, served: pd.Series, G, snap: pd.DataFrame) -> pd.DataFrame:
    """Positive control of the coordination test: the same shift test in the night window NIGHT, for every ordered
    pair of different, non-parallel lines that arrive (A, >= TIMED_MIN_ARR times, at least hourly) and depart (B,
    every 15-60 min on average) in an area in that window; the stop pair with the shortest walk (OSM paths)."""
    from pipeline.transfer_walk import area_paths
    cols = ["area", "line_a", "line_b", "stop_a", "stop_b", "walk_m", "n_arr", "obs_wait", "rand_wait", "headway_b",
            "headway_a", "rank", "timed", "mode_a", "mode_b"]
    st = P["st"]
    mode = P["lines"].set_index("line")["mode"]
    area_of = s.set_index("suid").area
    arr = st[~st.is_first_row & (st.arr_s >= NIGHT[0]) & (st.arr_s < NIGHT[1])]
    dep = st[~st.is_last_row & (st.dep_s >= NIGHT[0]) & (st.dep_s < NIGHT[1])]
    if arr.empty or dep.empty:
        return pd.DataFrame(columns=cols)
    arr = arr.assign(area=arr.suid.map(area_of).to_numpy())
    dep = dep.assign(area=dep.suid.map(area_of).to_numpy())
    arr_g = {k: np.sort(g.arr_s.to_numpy(float)) for k, g in arr.groupby(["suid", "line"])}
    alld = st[~st.is_last_row]
    dep_g = {k: np.sort(g.dep_s.to_numpy(float)) for k, g in alld.groupby(["suid", "line"])}
    a_lines = arr.groupby(["area", "line"]).size()
    nwin_min = (NIGHT[1] - NIGHT[0]) / 60
    a_lines = a_lines[(a_lines >= TIMED_MIN_ARR) & (nwin_min / a_lines <= NIGHT_MAX_HEADWAY)]
    d_lines = dep.groupby(["area", "line"]).size()
    d_lines = d_lines[(nwin_min / d_lines >= TIMED_MIN_HEADWAY) & (nwin_min / d_lines <= NIGHT_MAX_HEADWAY)]
    sxy = s.set_index("suid")[["x", "y"]]
    rows = []
    for area in sorted(set(a_lines.index.get_level_values(0)) & set(d_lines.index.get_level_values(0))):
        A = sorted(a_lines.loc[area].index)
        B = sorted(d_lines.loc[area].index)
        pairs = []
        for a in A:
            for b in B:
                if a == b:
                    continue
                sa, sb = served[a], served[b]
                if len(sa & sb) / min(len(sa), len(sb)) >= PARALLEL_SHARE:
                    continue
                pairs.append((a, b))
        if not pairs:
            continue
        sa_ = {a: sorted(set(arr.loc[(arr.area == area) & (arr.line == a), "suid"])) for a in A}
        sb_ = {b: sorted(set(dep.loc[(dep.area == area) & (dep.line == b), "suid"])) for b in B}
        stops_here = sorted(set().union(*sa_.values(), *sb_.values()))
        idx = {x: i for i, x in enumerate(stops_here)}
        need = sorted({(idx[x], idx[y]) for a, b in pairs for x in sa_[a] for y in sb_[b] if x != y})
        sn = snap.reindex(stops_here)
        paths = area_paths(G, sxy.reindex(stops_here).to_numpy(), sn.e.to_numpy(), sn.t.to_numpy(), sn.d.to_numpy(),
                           need)
        for a, b in pairs:
            best = None
            for x in sa_[a]:
                for y in sb_[b]:
                    d = 0.0 if x == y else (paths.get((idx[x], idx[y])) or {}).get("dist_m", np.inf)
                    if d is not None and np.isfinite(d) and (best is None or (d, x, y) < best):
                        best = (d, x, y)
            if best is None:
                continue
            d, x, y = best
            r = shift_test(arr_g[(x, a)], dep_g[(y, b)], d / M_PER_MIN * 60, NIGHT)
            if r is None:
                continue
            rows.append({"area": area, "line_a": a, "line_b": b, "stop_a": x, "stop_b": y, "walk_m": d, **r,
                         "mode_a": mode.get(a), "mode_b": mode.get(b)})
    return pd.DataFrame(rows, columns=cols)


def run_agg(agg: str) -> dict:
    from pipeline.transfer_walk import CityGraph
    t0 = time.time()
    P = prepare(agg)
    G = CityGraph(agg)
    out = {"agg": agg, "lines": P["lines"], "clusters": P["clusters"], "census": G.crossing_census(), "rules": {}}
    for rn in RULES:
        out["rules"][rn] = run_rule(P, rn, G)
        print(f"  {agg} {rn}: {time.time() - t0:.0f} s", flush=True)
    # departures per area (all lines, not only counted ones), both windows
    out["seconds"] = time.time() - t0
    return out


# ================================================================== node table
def _q(x: pd.Series, q: float):
    x = pd.to_numeric(x, errors="coerce").dropna()
    return float(np.quantile(x, q)) if len(x) else None


def _wq(x: pd.Series, w: pd.Series, q: float = 0.5):
    """Weighted quantile (lower), None when empty."""
    x = pd.to_numeric(x, errors="coerce")
    ok = x.notna() & (w > 0)
    if not ok.any():
        return None
    xs, ws = x[ok].to_numpy(float), w[ok].to_numpy(float)
    o = np.lexsort((ws, xs))
    xs, ws = xs[o], ws[o]
    c = np.cumsum(ws) / ws.sum()
    return float(xs[np.searchsorted(c, q - 1e-12)])


ADDITIVE = {"am": ("walk_w_am_min", "wait_w_am_min", "walkwait_w_am_min", "n_movements_am"),
            "day": ("walk_w_day_min", "wait_w_day_min", "walkwait_w_day_min", "n_movements_day")}


def additive(mv: pd.DataFrame | None) -> dict:
    """Additive decomposition of a node on ONE set of rows: the direction-based movements (A's main arrival direction x
    B's main departure direction, valid as in ``directional``) that have both a walk and an expected wait of B in that
    departure direction in the window.  Weight of a movement = A's arrivals in that direction x B's departures in
    that direction (06-20).  walk, wait = weighted means; total = weighted mean of walk + wait per movement, so
    total = walk + wait up to floating point."""
    out = {}
    for win, (cw, ct, cs, cn) in ADDITIVE.items():
        col = f"wait_{win}"
        if mv is None or not len(mv):
            out.update({cw: None, ct: None, cs: None, cn: 0})
            continue
        m = mv[pd.to_numeric(mv[col], errors="coerce").notna() & mv.walk_m.notna() & (mv.weight > 0)]
        if m.empty:
            out.update({cw: None, ct: None, cs: None, cn: 0})
            continue
        w = m.weight.to_numpy(float)
        walk = m.walk_m.to_numpy(float) / M_PER_MIN
        wait = m[col].to_numpy(float)
        W = w.sum()
        out.update({cw: float((w * walk).sum() / W), ct: float((w * wait).sum() / W),
                    cs: float((w * (walk + wait)).sum() / W), cn: int(len(m))})
    return out


def gtt(walk, wait, variant: str):
    """Generalised transfer time (equivalent in-vehicle minutes) of a walk and a wait in minutes; None when missing."""
    if walk is None or wait is None or pd.isna(walk) or pd.isna(wait):
        return None
    a, b, pen = GTT_BAND[variant]
    return float(a * walk + b * wait + pen)


REVISION_COLS = ["conn_wait_am_median", "conn_wait_am_p90", "conn_wait_day_median", "conn_wait_day_p90",
                 "conn_wait_w_am_min", "conn_delta_w_am_min", "gtt_low_am_min", "gtt_central_am_min",
                 "gtt_high_am_min", "w6_hi_mean", "w6_lo_mean", "w6_scored_share", "crossings_grade_share",
                 "crossings_w_mean", "freq10_share", "freq15_share", "n_movements_all"]


def revisions(mv: pd.DataFrame | None, cn: dict, add: dict) -> dict:
    """Node columns added after the literature review (see the module docstring); ``cn`` = {win: (median, p90)}."""
    out = {c: None for c in REVISION_COLS}
    out["n_movements_all"] = 0
    for win in ("am", "day"):
        med, p90 = cn.get(win, (None, None))
        out[f"conn_wait_{win}_median"], out[f"conn_wait_{win}_p90"] = med, p90
    for v_ in ("low", "central", "high"):
        out[f"gtt_{v_}_am_min"] = gtt(add.get("walk_w_am_min"), add.get("wait_w_am_min"), v_)
    if mv is None or not len(mv):
        return out
    out["n_movements_all"] = int(len(mv))
    w = mv.weight.to_numpy(float)
    m = mv[pd.to_numeric(mv.wait_am, errors="coerce").notna() & mv.walk_m.notna() & (mv.weight > 0)
           & pd.to_numeric(mv.conn_am_mean, errors="coerce").notna()]
    if len(m):
        ww = m.weight.to_numpy(float)
        c = m.conn_am_mean.to_numpy(float)
        out["conn_wait_w_am_min"] = float((ww * c).sum() / ww.sum())
        out["conn_delta_w_am_min"] = float((ww * (c - m.wait_am.to_numpy(float))).sum() / ww.sum())
    sc = mv[(mv.w6_n > 0) & (mv.weight > 0)]
    if len(sc):
        ww = sc.weight.to_numpy(float)
        out["w6_hi_mean"] = float((ww * sc.w6_hi_sum / sc.w6_n).sum() / ww.sum())
        out["w6_lo_mean"] = float((ww * sc.w6_lo_sum / sc.w6_n).sum() / ww.sum())
    tot = mv[["x_grade", "x_signal", "x_zebra", "x_unmarked", "x_unknown"]].to_numpy(float).sum()
    if tot > 0:
        out["w6_scored_share"] = float(1 - mv.x_unknown.sum() / tot)
        out["crossings_grade_share"] = float(mv.x_grade.sum() / tot)
    if w.sum() > 0:
        out["crossings_w_mean"] = float((w * mv.crossings.to_numpy(float)).sum() / w.sum())
    na, nb = mv.n_a_am.to_numpy(float), mv.n_b_am.to_numpy(float)
    win_min = (WIN_AM[1] - WIN_AM[0]) / 60
    for h, col in zip(FREQ_HEADWAYS, ("freq10_share", "freq15_share")):
        need = win_min / h
        out[col] = float(((na >= need - 1e-9) & (nb >= need - 1e-9)).mean())
    return out


def node_table(R: dict, rule_name: str, geo: dict, mask) -> pd.DataFrame:
    agg = R["agg"]
    rr = R["rules"][rule_name]
    s, pairs, vd = rr["stops"], rr["pairs"], rr["visits_dep"]
    cl = R["clusters"]
    lines = R["lines"].set_index("line")
    dep_day = vd.groupby("area").size()
    dep_am = vd[(vd.dep >= WIN_AM[0]) & (vd.dep < WIN_AM[1])].groupby("area").size()
    ar = s.groupby("area").agg(x=("x", "mean"), y=("y", "mean"), n_stops=("suid", "size"), rail=("rail", "any"))
    # name: the cluster with the most departures
    cdep = F.visits(agg, VARIANT)
    cdep = cdep[(~cdep.is_last) & (cdep.cl >= 0) & (cdep.dep >= WIN_DAY[0]) & (cdep.dep < WIN_DAY[1])].groupby("cl").size()
    cl2 = cl.set_index("cl")
    cl_area = s.drop_duplicates("cl").set_index("cl").area
    tmp = pd.DataFrame({"area": cl_area, "dep": cdep.reindex(cl_area.index).fillna(0).to_numpy(),
                        "name": cl2.name.reindex(cl_area.index).to_numpy(),
                        "cid": cl2.cluster_id.reindex(cl_area.index).to_numpy()})
    tmp = tmp.sort_values(["area", "dep", "cid"], ascending=[True, False, True], kind="stable")
    names = tmp.groupby("area").name.agg(lambda x: x.iloc[0])
    alln = tmp.groupby("area").name.agg(lambda x: "; ".join(dict.fromkeys(x)))
    cids = tmp.groupby("area").cid.agg(lambda x: ";".join(sorted(x)))
    ncl = tmp.groupby("area").size()
    tp = pairs[~pairs.parallel] if len(pairs) else pairs
    mv = rr.get("movements")
    mvs = {a: g_ for a, g_ in mv.groupby("area", sort=True)} if mv is not None and len(mv) else {}
    cnn = {}
    if rr.get("conn_node") is not None:
        for r_ in rr["conn_node"].itertuples():
            cnn.setdefault(r_.area, {})[r_.win] = (r_.median, r_.p90)
    counted = R["rules"][rule_name]["al"]
    rows = []
    for area, g in tp.groupby("area", sort=True):
        w = g[g.walk_m.notna()] if "walk_m" in g else g.iloc[0:0]
        walk_min = w.walk_m / M_PER_MIN
        ww_am = (walk_min + w.wait_am.astype(float))
        ww_day = (walk_min + w.wait_day.astype(float))
        det = w[(w.straight_m >= DETOUR_MIN_STRAIGHT_M)]
        det = det.walk_m / det.straight_m
        cross = w.crossings.astype(float)
        stp = w[w.steps.astype(bool)]
        al = counted[counted.area == area]
        ln = sorted(set(al.loc[al.board | al.alight, "line"]))
        modes = sorted(set(lines.reindex(ln)["mode"].dropna()))
        tm = rr["timed"]
        tm = tm[tm.area == area] if len(tm) else tm
        nx = float(w.crossings.sum()) if len(w) else 0.0
        rows.append({
            "area": area, "n_lines": len(ln), "modes": ",".join(modes),
            "n_pairs": int(len(g)), "n_pairs_walk": int(len(w)),
            "n_pairs_platform_unknown": int(g["platform_unknown"].fillna(False).astype(bool).sum())
            if "platform_unknown" in g else 0, "n_pairs_parallel_excluded":
                int(pairs[(pairs.area == area) & pairs.parallel].shape[0]),
            "walk_min_median": _q(walk_min, .5), "walk_min_p90": _q(walk_min, .9),
            "walk_m_median": _q(w.walk_m, .5), "detour_median": _q(det, .5),
            "same_stop_share": float(w.same_stop.mean()) if len(w) else None,
            "crossings_median": _q(cross, .5), "crossings_max": float(cross.max()) if len(w) else None,
            "crossings_signal_share": float(w.crossings_signal.sum() / nx) if nx > 0 else None,
            "crossings_value_share": float(w.crossings_value.sum() / nx) if nx > 0 else None,
            "track_crossing_pair_share": float((w.crossings_track > 0).mean()) if len(w) else None,
            "steps_pair_share": float(w.steps.astype(bool).mean()) if len(w) else None,
            "tunnel_pair_share": float(w.tunnel.astype(bool).mean()) if len(w) else None,
            "bridge_pair_share": float(w.bridge.astype(bool).mean()) if len(w) else None,
            "stepfree_pair_share": float(w.stepfree_m.notna().mean()) if len(w) else None,
            "stepfree_extra_min_median": _q((stp.stepfree_m - stp.walk_m) / M_PER_MIN, .5) if len(stp) else None,
            "road_share_median": _q((w.road_m / w.len_m.where(w.len_m > 0)), .5),
            "wait_am_median": _q(w.wait_am, .5), "wait_day_median": _q(w.wait_day, .5),
            "walkwait_am_median": _q(ww_am, .5), "walkwait_am_p90": _q(ww_am, .9),
            "walkwait_day_median": _q(ww_day, .5),
            "walkwait_am_median_w": _wq(ww_am, (w.n_arr_a * w.n_dep_b).astype(float)),
            "walk_dir_min_median": _q(g.walk_dir_m / M_PER_MIN, .5) if "walk_dir_m" in g else None,
            "walk_dir_min_p90": _q(g.walk_dir_m / M_PER_MIN, .9) if "walk_dir_m" in g else None,
            "crossings_dir_median": _q(g.crossings_dir, .5) if "crossings_dir" in g else None,
            "steps_dir_share": float(pd.to_numeric(g.steps_dir, errors="coerce").mean())
            if "steps_dir" in g and g.steps_dir.notna().any() else None,
            "stepfree_dir_share": float(pd.to_numeric(g.stepfree_dir, errors="coerce").mean())
            if "stepfree_dir" in g and g.stepfree_dir.notna().any() else None,
            "walkwait_dir_am_median": _q(g.walk_dir_m / M_PER_MIN + pd.to_numeric(g.wait_am, errors="coerce"), .5)
            if "walk_dir_m" in g else None,
            "n_pairs_dir": int(g.walk_dir_m.notna().sum()) if "walk_dir_m" in g else 0,
            **(add_ := additive(mvs.get(area))),
            **revisions(mvs.get(area), cnn.get(area, {}), add_),
            "stops_mean_walk_m": rr["node_all"].get(area, {}).get("mean_net_m"),
            "stops_mean_straight_m": rr["node_all"].get(area, {}).get("mean_straight_m"),
            "timed_pairs_checked": int(len(tm)), "timed_pairs": int(tm.timed.sum()) if len(tm) else 0,
            "rail_pair_share": float(w.rail_involved.mean()) if len(w) else None,
        })
    nt = pd.DataFrame(rows)
    if nt.empty:
        return nt
    nt = nt.join(ar, on="area")
    nt["name"] = nt.area.map(names); nt["names_all"] = nt.area.map(alln)
    nt["cluster_ids"] = nt.area.map(cids); nt["n_clusters"] = nt.area.map(ncl)
    nt["dep_per_h_day"] = nt.area.map(dep_day).fillna(0) / ((WIN_DAY[1] - WIN_DAY[0]) / 3600)
    nt["dep_per_h_am"] = nt.area.map(dep_am).fillna(0) / ((WIN_AM[1] - WIN_AM[0]) / 3600)
    # diameter of the area (member stops)
    diam = {}
    for area, g in s[s.area.isin(set(nt.area))].groupby("area"):
        p = g[["x", "y"]].to_numpy()
        diam[area] = float(np.max(np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1]))) if len(p) > 1 else 0.0
    nt["diameter_m"] = nt.area.map(diam)
    x, y = nt.x.to_numpy(), nt.y.to_numpy()
    nt["in_fua"] = shapely.contains_xy(geo["fua"], x, y)
    nt["in_core"] = shapely.contains_xy(geo["core"], x, y)
    nt["in_mask"] = shapely.contains_xy(mask, x, y) if mask is not None else True
    nt.insert(0, "agglomeration", agg)
    nt = nt.sort_values(["y", "x"], ascending=[False, True], kind="stable").reset_index(drop=True)
    nt.insert(1, "node_id", [f"{agg}-T{i:05d}" for i in range(len(nt))])
    return nt


def mask_geom(agg: str):
    m = gpd.read_parquet(RESULTS / "layers" / "gtfs_coverage_mask.parquet")
    m = m[(m.agglomeration == agg) & (m.feed_variant == VARIANT) & (m.status_code.isin([1, 2]))].to_crs("EPSG:2180")
    if m.empty:
        return None
    g = shapely.union_all(m.geometry.values)
    shapely.prepare(g)
    return g


def compute_all() -> list[dict]:
    with ProcessPoolExecutor(max_workers=7) as ex:
        res = list(ex.map(run_agg, AGGS))
    return res


def main() -> None:
    t0 = time.time()
    OUT_INT.mkdir(parents=True, exist_ok=True)
    cache = OUT_INT / "results.pkl"
    if "--report-only" in sys.argv and cache.exists():
        with open(cache, "rb") as f:
            results = pickle.load(f)
    else:
        from pipeline.transfer_osm import load as load_osm
        load_osm()        # build the OSM cache once before the workers start
        results = compute_all()
        with open(cache, "wb") as f:
            pickle.dump(results, f)
    from pipeline.transfer_report import write_all
    write_all(results, t0)
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
