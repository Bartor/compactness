"""Node detail for the map: results/web/transfer_detail/<agg>.json and index.json (pipeline.transfer_ease).

Called by pipeline.transfer_report.write_all (so it runs with ``python -m pipeline.transfer_ease`` and with
``--report-only``).  One compact record per stop area of the main rule with at least DETAIL_MIN_DEP_H departures an
hour 06-20, inside the FUA and the GTFS coverage mask:

    id, n (name), c [lon, lat], dep (departures / h 06-20), md (modes, "bus,tram"),
    sum: {walk, wait, conn, conn90, gtt [low, central, high], w6 [hi, lo], x (crossings / movement), f10, f15}
         (07-09; walk + wait = the additive trio of the layer, conn = trip-weighted mean connection wait)
    l:   lines [[label, mode], ...]
    d:   line directions [[line index, terminus, "a" (arriving) | "d" (departing), trips 06-20], ...]
    s:   stops [[lon, lat, name, [line indices]], ...]
    p:   paths [{a, b (stop indices), g (flat lon, lat, ...), m (metres), t (min at 5 km/h),
                 x [[lon, lat, W6 class], ...], st [[lon, lat], ...] (start of each run of steps)}, ...]
    mv:  movements [[from direction, to direction, path index (-1 = same stop, null = not stored), walk min,
                     random wait min, connection wait median min, connection wait P90 min, arrivals A, departures B,
                     W6 score (signals 70) or null], ...]  (07-09 waits; null = no data)
    top: indices into mv of the ten heaviest movements (arrivals A x departures B, 06-20)
    ar, dp: direction indices of the matrix rows (arriving) and columns (departing), heaviest first

Paths are the shortest OSM walking paths of the best stop pair of each movement (pipeline.transfer_walk), cached
in data/interim/transfer/results.pkl (rule main, ``detail``).  Coordinates WGS84 with 6 decimals; geometry
simplified with DETAIL_SIMPLIFY_M in EPSG:2180.  W6 classes: grade (100 %), signal (70 or 50 %), zebra (30 %),
unmarked (0 %), unknown (not scored).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import shapely

from pipeline import transfer_ease as T
from pipeline.common import RESULTS

OUT = RESULTS / "web" / "transfer_detail"
DETAIL_SIMPLIFY_M = 1.5
MATRIX_MAX = 8         # rows (arriving directions) and columns (departing directions) of the connection matrix
TOP_MOVEMENTS = 10
MAX_BYTES = 3_000_000


def _r(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)) or pd.isna(x):
        return None
    v = round(float(x), d)
    return int(v) if d == 0 else v


def _ll(x, y):
    lon, lat = T.TO4326.transform(np.asarray(x, float), np.asarray(y, float))
    return np.round(lon, 6), np.round(lat, 6)


def _path_rec(a: int, b: int, p: dict) -> dict:
    xy = p["xy"]
    if len(xy) > 2:
        g = shapely.simplify(shapely.linestrings(xy), DETAIL_SIMPLIFY_M, preserve_topology=False)
        xy = shapely.get_coordinates(g)
    lon, lat = _ll(xy[:, 0], xy[:, 1])
    flat = [float(v) for pair in zip(lon, lat) for v in pair]
    xs = []
    for x, y, c in p["xings"]:
        lo, la = _ll([x], [y])
        xs.append([float(lo[0]), float(la[0]), c])
    st = []
    for x, y in p["steps_xy"]:
        lo, la = _ll([x], [y])
        st.append([float(lo[0]), float(la[0])])
    return {"a": a, "b": b, "g": flat, "m": _r(p["dist_m"], 0), "t": _r(p["dist_m"] / T.M_PER_MIN, 1), "x": xs,
            "st": st}


def node_record(row: pd.Series, mv: pd.DataFrame, det: dict, stops: pd.DataFrame, lines: pd.DataFrame) -> dict:
    area = row.area
    m = mv[mv.area == area].copy()
    # line directions: arriving (line_a, prev_a) and departing (line_b, next_b), heaviest first
    arr = m.groupby(["line_a", "prev_a"]).n_a.first().rename("n").reset_index()
    dep = m.groupby(["line_b", "next_b"]).n_b.first().rename("n").reset_index()
    arr = arr.sort_values(["n", "line_a", "prev_a"], ascending=[False, True, True], kind="stable")
    dep = dep.sort_values(["n", "line_b", "next_b"], ascending=[False, True, True], kind="stable")
    m["w"] = m.n_a.astype(float) * m.n_b.astype(float)
    m = m.sort_values(["w", "line_a", "prev_a", "line_b", "next_b"], ascending=[False, True, True, True, True],
                      kind="stable").reset_index(drop=True)
    top = m.head(TOP_MOVEMENTS)
    rows_k = list(zip(arr.line_a, arr.prev_a))[:MATRIX_MAX]
    cols_k = list(zip(dep.line_b, dep.next_b))[:MATRIX_MAX]
    keep_a = set(rows_k) | set(zip(top.line_a, top.prev_a))
    keep_b = set(cols_k) | set(zip(top.line_b, top.next_b))
    m = m[np.array([(a, p) in keep_a and (b, n) in keep_b
                    for a, p, b, n in zip(m.line_a, m.prev_a, m.line_b, m.next_b)], dtype=bool)]
    m = m.reset_index(drop=True)
    # tables
    ln = sorted(set(m.line_a) | set(m.line_b) | {a for a, _ in keep_a} | {b for b, _ in keep_b})
    li = {x: i for i, x in enumerate(ln)}
    lt = lines.set_index("line")
    L = [[str(lt.label.get(x, x)), str(lt["mode"].get(x, ""))] for x in ln]
    D, di = [], {}
    for key, kind, tab in (("a", "a", arr), ("d", "d", dep)):
        lc, dc = ("line_a", "prev_a") if kind == "a" else ("line_b", "next_b")
        terms = det["term_arr"] if kind == "a" else det["term_dep"]
        for r in tab.itertuples(index=False):
            k = (getattr(r, lc), int(getattr(r, dc)))
            if (kind == "a" and k not in keep_a) or (kind == "d" and k not in keep_b):
                continue
            di[(kind, k)] = len(D)
            D.append([li[k[0]], terms.get((area, k[0], k[1]), "") or "", kind, int(r.n)])
    # stops: every stop of the movements kept
    sid = sorted(set(m.stop_a) | set(m.stop_b))
    si = {x: i for i, x in enumerate(sid)}
    sx = stops.drop_duplicates("suid").set_index("suid").reindex(sid)
    lon, lat = _ll(sx.x.to_numpy(), sx.y.to_numpy())
    serv = {x: set() for x in sid}
    for a, b, x, y in zip(m.line_a, m.line_b, m.stop_a, m.stop_b):
        serv[x].add(li[a]); serv[y].add(li[b])
    S = [[float(lo), float(la), str(nm), sorted(serv[x])] for x, lo, la, nm in zip(sid, lon, lat, sx.stop_name)]
    # paths
    P, pi = [], {}
    paths = det["paths"].get(area, {})
    for x, y in sorted({(x, y) for x, y in zip(m.stop_a, m.stop_b) if x != y}):
        p = paths.get((x, y))
        if p is None:
            continue
        pi[(x, y)] = len(P)
        P.append(_path_rec(si[x], si[y], p))
    MV = []
    for r in m.itertuples(index=False):
        pidx = -1 if r.stop_a == r.stop_b else pi.get((r.stop_a, r.stop_b))
        w6 = r.w6_hi_sum / r.w6_n if r.w6_n > 0 else None
        MV.append([di[("a", (r.line_a, int(r.prev_a)))], di[("d", (r.line_b, int(r.next_b)))], pidx,
                   _r(r.walk_m / T.M_PER_MIN), _r(r.wait_am), _r(r.conn_am_med), _r(r.conn_am_p90), int(r.n_a),
                   int(r.n_b), _r(w6, 0)])
    order = {(a, p, b, n): i for i, (a, p, b, n) in enumerate(zip(m.line_a, m.prev_a, m.line_b, m.next_b))}
    top_i = [order[k] for k in zip(top.line_a, top.prev_a, top.line_b, top.next_b) if k in order]
    lon0, lat0 = _ll([row.x], [row.y])
    return {
        "id": row.node_id, "n": str(row["name"]), "c": [float(lon0[0]), float(lat0[0])], "dep": _r(row.dep_per_h_day),
        "md": row.modes,
        "sum": {"walk": _r(row.walk_w_am_min), "wait": _r(row.wait_w_am_min), "conn": _r(row.conn_wait_w_am_min),
                "conn50": _r(row.conn_wait_am_median), "conn90": _r(row.conn_wait_am_p90),
                "gtt": [_r(row.gtt_low_am_min), _r(row.gtt_central_am_min), _r(row.gtt_high_am_min)],
                "w6": [_r(row.w6_hi_mean, 0), _r(row.w6_lo_mean, 0)], "x": _r(row.crossings_w_mean),
                "steps": _r(row.steps_dir_share, 2), "free": _r(row.stepfree_dir_share, 2),
                "f10": _r(row.freq10_share, 2), "f15": _r(row.freq15_share, 2)},
        "l": L, "d": D, "s": S, "p": P, "mv": MV, "top": top_i,
        "ar": [di[("a", k)] for k in rows_k if ("a", k) in di], "dp": [di[("d", k)] for k in cols_k if ("d", k) in di],
    }


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def write_detail(results: list[dict], main: pd.DataFrame) -> dict:
    """Writes the per-agglomeration files and the index; returns {agg: {nodes, bytes}} for the note."""
    OUT.mkdir(parents=True, exist_ok=True)
    index, info = {}, {}
    for R in results:
        agg = R["agg"]
        rr = R["rules"]["main"]
        det = rr.get("detail")
        if not det:
            continue
        nt = main[(main.agglomeration == agg) & main.in_fua & main.in_mask
                  & (main.dep_per_h_day >= T.DETAIL_MIN_DEP_H)].sort_values("node_id")
        mv = rr["movements"]
        recs = [node_record(r, mv, det, rr["stops"], R["lines"]) for _, r in nt.iterrows()]
        recs = [r for r in recs if r["mv"]]      # a busy node without any movement between lines has no detail
        doc = {"agglomeration": agg, "timetable_date": T.DAY, "osm_date": "2026-11-22",
               "code_version": T.CODE_VERSION, "min_dep_h": T.DETAIL_MIN_DEP_H, "nodes": recs}
        text = dumps(doc)
        path = OUT / f"{agg}.json"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        size = len(text.encode("utf-8"))
        info[agg] = {"nodes": len(recs), "bytes": size, "over_limit": size > MAX_BYTES,
                     "paths": int(sum(len(r["p"]) for r in recs)), "movements": int(sum(len(r["mv"]) for r in recs))}
        for r in recs:
            index[r["id"]] = [agg, r["n"], r["dep"]]
    idx = {"timetable_date": T.DAY, "code_version": T.CODE_VERSION, "min_dep_h": T.DETAIL_MIN_DEP_H,
           "files": {a: {"url": f"{a}.json", "nodes": v["nodes"], "bytes": v["bytes"]} for a, v in sorted(info.items())},
           "nodes": dict(sorted(index.items()))}
    with open(OUT / "index.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(idx))
    return info
