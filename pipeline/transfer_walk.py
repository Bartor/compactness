"""Walking paths between stops inside one stop area, with the obstacles on them (pipeline.transfer_ease).

City graph: pipeline.walk_network (one node per OSM node, undirected edges, way class) plus the OSM attributes of
pipeline.transfer_osm.  Per stop area a local graph is cut out (edges of main components within the area's bounding
box + LOCAL_MARGIN_M), the area's stops are snapped to their nearest main-component edge (as in
pipeline.walk_network.Router: split at the snap position, a leaf edge of the snap length), and Dijkstra with
predecessors gives the shortest path between every pair of stops, once on the full graph and once without steps
(highway=steps and escalators).

Obstacles on a path
* road crossing: an interior path node that lies on a carriageway or a tram / rail track (transfer_osm.ROAD / TRACK)
  where both path edges next to it are not carriageways (the walk goes across, not along), or a node tagged
  highway=crossing / railway=crossing / tram_crossing / level_crossing.  Events closer than GROUP_GAP_M along the
  path (two carriageways and the tracks between them) form one crossing.
* signalised: a node of the crossing has crossing=traffic_signals, crossing:signals=yes, crossing_ref=pelican /
  toucan or highway=traffic_signals, or an adjacent footway=crossing way has such a value.
* tagged: the crossing has any explicit OSM crossing information (node tag or footway=crossing way); "with a value":
  a crossing=* value or traffic signals.  Untagged crossings are found only where sidewalks are mapped as separate
  ways; where the walk follows a road centre line the crossing of side streets is invisible (road_share says how much
  of the path that is).
* steps: an edge of class steps (or conveying=*); tunnel: a walkable way with tunnel=* (not building_passage);
  bridge: a walkable way with bridge=* that is not itself a carriageway (sidewalks mapped on road bridges count too).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from pipeline.transfer_osm import load as load_osm
from pipeline.walk_network import load_graph

LOCAL_MARGIN_M = 600.0
DIJKSTRA_LIMIT_M = 2500.0
GROUP_GAP_M = 40.0
CARRIAGEWAY = {"residential", "service", "unclassified", "tertiary", "tertiary_link", "secondary", "secondary_link",
               "primary", "primary_link", "living_street", "trunk", "trunk_link", "road", "motorway", "motorway_link"}
SIGNAL_VALUES = {"traffic_signals", "pelican", "toucan", "pegasus"}


class CityGraph:
    """Walk graph of one agglomeration with per-edge and per-node attributes for the obstacle count."""

    def __init__(self, agg: str, osm: dict | None = None):
        nodes, edges = load_graph(agg)
        osm = osm or load_osm()
        self.nx, self.ny = nodes.x.to_numpy(), nodes.y.to_numpy()
        oid = nodes.osm_id.to_numpy()
        main = nodes.comp_main.to_numpy()
        keep = main[edges.u.to_numpy()]
        e = edges[keep].reset_index(drop=True)
        self.eu, self.ev, self.el = e.u.to_numpy(), e.v.to_numpy(), e.len_m.to_numpy()
        cls = e.cls.astype(str).to_numpy()
        self.road = np.isin(cls, list(CARRIAGEWAY))
        self.steps = cls == "steps"
        # way flags by unordered OSM node pair
        a, b = oid[self.eu], oid[self.ev]
        key = pd.DataFrame({"a": np.minimum(a, b), "b": np.maximum(a, b), "i": np.arange(len(e))})
        wf = osm["wayflags"]
        m = key.merge(wf, on=["a", "b"], how="left").sort_values("i")
        self.tunnel = m.tunnel.fillna(False).to_numpy(bool)
        self.bridge = m.bridge.fillna(False).to_numpy(bool) & ~self.road
        self.steps |= m.conveying.fillna(False).to_numpy(bool)
        self.fwc = m.fw_crossing.fillna(False).to_numpy(bool)
        wcv = m.crossing.astype(object).to_numpy()
        wsg = m.crossing_signals.astype(object).to_numpy()
        self.w_value = pd.notna(wcv)
        self.w_signal = np.isin(wcv.astype(str), list(SIGNAL_VALUES)) | (wsg.astype(str) == "yes")
        # node attributes
        idx = pd.Series(np.arange(len(oid)), index=oid)
        n = len(oid)
        rn = osm["roadnodes"]
        rn = rn[rn.id.isin(idx.index)]
        self.on_road = np.zeros(n, bool); self.on_track = np.zeros(n, bool)
        ii = idx.reindex(rn.id).to_numpy()
        self.on_road[ii[rn.road.to_numpy() > 0]] = True
        self.on_track[ii[rn.track.to_numpy() > 0]] = True
        nd = osm["nodes"]
        nd = nd[nd.id.isin(idx.index)]
        jj = idx.reindex(nd.id).to_numpy()
        hw, cr = nd.highway.astype(object), nd.crossing.astype(object)
        rw, cs, cref = nd.railway.astype(object), nd["crossing:signals"].astype(object), nd.crossing_ref.astype(object)
        tag_cross = (hw == "crossing") | cr.notna() | rw.isin(["crossing", "tram_crossing", "level_crossing",
                                                                 "tram_level_crossing"])
        sig = cr.isin(list(SIGNAL_VALUES)) | (cs == "yes") | cref.isin(["pelican", "toucan"]) | (hw == "traffic_signals")
        self.n_tag = np.zeros(n, bool); self.n_value = np.zeros(n, bool); self.n_signal = np.zeros(n, bool)
        self.n_hwcross = np.zeros(n, bool)
        self.n_tag[jj[tag_cross.to_numpy()]] = True
        self.n_value[jj[(cr.notna() | (hw == "traffic_signals")).to_numpy()]] = True
        self.n_signal[jj[sig.to_numpy()]] = True
        self.n_hwcross[jj[(hw == "crossing").to_numpy()]] = True
        self.n_elev = np.zeros(n, bool)
        self.n_elev[jj[(hw == "elevator").to_numpy()]] = True
        self.n_hwcross_value = np.zeros(n, bool)
        self.n_hwcross_value[jj[((hw == "crossing") & cr.notna()).to_numpy()]] = True
        self.segs = shapely.linestrings(np.stack([np.c_[self.nx[self.eu], self.ny[self.eu]],
                                                  np.c_[self.nx[self.ev], self.ny[self.ev]]], axis=1))
        self.tree = shapely.STRtree(self.segs)
        self.n_nodes = n

    def snap(self, xy: np.ndarray, maxd: np.ndarray):
        """Nearest main-component edge per point within maxd: (edge, t along edge in m, distance); edge -1 if none."""
        pts = shapely.points(xy)
        (pi, si), d = self.tree.query_nearest(pts, max_distance=float(np.max(maxd)), return_distance=True,
                                              all_matches=False)
        order = np.lexsort((si, pi))
        pi, si, d = pi[order], si[order], d[order]
        first = np.r_[True, pi[1:] != pi[:-1]] if len(pi) else np.zeros(0, bool)
        pi, si, d = pi[first], si[first], d[first]
        ok = d <= np.asarray(maxd, dtype=float)[pi]
        pi, si, d = pi[ok], si[ok], d[ok]
        e = np.full(len(xy), -1, dtype=np.int64); t = np.zeros(len(xy)); dd = np.full(len(xy), np.inf)
        e[pi] = si
        t[pi] = shapely.line_locate_point(self.segs[si], pts[pi])
        dd[pi] = d
        return e, t, dd

    def crossing_census(self) -> dict:
        """City-wide tag completeness: nodes where a separately mapped footway crosses a carriageway."""
        # a node on a carriageway with >= 2 incident non-carriageway walk edges = a mapped footway crossing the road
        nonroad = ~self.road
        deg = np.bincount(np.r_[self.eu[nonroad], self.ev[nonroad]], minlength=self.n_nodes)
        cand = self.on_road & (deg >= 2)
        degall = np.bincount(np.r_[self.eu, self.ev], minlength=self.n_nodes)
        return {"elevator_nodes": int(self.n_elev.sum()),
                "elevator_nodes_dead_end": int((self.n_elev & (degall <= 1)).sum()),
                "footway_road_nodes": int(cand.sum()),
                "footway_road_nodes_tagged": int((cand & self.n_tag).sum()),
                "footway_road_nodes_with_value": int((cand & self.n_value).sum()),
                "highway_crossing_nodes": int(self.n_hwcross.sum()),
                "highway_crossing_nodes_with_crossing_value": int(self.n_hwcross_value.sum())}


def area_paths(G: CityGraph, stop_xy: np.ndarray, snap_e: np.ndarray, snap_t: np.ndarray, snap_d: np.ndarray,
               pairs: list[tuple[int, int]], all_pairs: bool = False) -> dict:
    """Shortest paths between the given (source, target) stop index pairs of one area.

    Returns per pair: dist_m, dist_stepfree_m (inf when none within the limit) and the obstacle summary of the
    shortest path (crossings, signalised, tagged, with value, track crossings, steps, tunnel, bridge, road_m)."""
    k = len(stop_xy)
    xmin, ymin = stop_xy.min(axis=0) - LOCAL_MARGIN_M
    xmax, ymax = stop_xy.max(axis=0) + LOCAL_MARGIN_M
    E = np.unique(np.r_[G.tree.query(shapely.box(xmin, ymin, xmax, ymax)), snap_e[snap_e >= 0]])
    eu, ev, el = G.eu[E], G.ev[E], G.el[E]
    gnodes = np.unique(np.r_[eu, ev])
    loc = pd.Series(np.arange(len(gnodes)), index=gnodes)
    lu, lv = loc.reindex(eu).to_numpy(), loc.reindex(ev).to_numpy()
    n0 = len(gnodes)
    # snaps on local edges
    epos = pd.Series(np.arange(len(E)), index=E)
    ok = snap_e >= 0
    le = np.full(k, -1, dtype=np.int64)
    le[ok] = epos.reindex(snap_e[ok]).to_numpy()
    sp = pd.DataFrame({"e": le[ok], "t": np.round(snap_t[ok], 2)}).drop_duplicates().sort_values(["e", "t"])
    sp = sp.reset_index(drop=True)
    sp["node"] = n0 + np.arange(len(sp))
    # chains on split edges
    rows_u, rows_v, rows_w, rows_p = [], [], [], []
    split = np.zeros(len(E), bool)
    for e_, g in sp.groupby("e", sort=True):
        split[e_] = True
        prev_n, prev_t = lu[e_], 0.0
        for t_, nd in zip(g.t.to_numpy(), g.node.to_numpy()):
            rows_u.append(prev_n); rows_v.append(nd); rows_w.append(max(t_ - prev_t, 1e-3)); rows_p.append(e_)
            prev_n, prev_t = nd, t_
        rows_u.append(prev_n); rows_v.append(lv[e_]); rows_w.append(max(el[e_] - prev_t, 1e-3)); rows_p.append(e_)
    n1 = n0 + len(sp)
    leaf = np.full(k, -1, dtype=np.int64)
    key = {(int(a), float(b)): int(c) for a, b, c in zip(sp.e, sp.t, sp.node)}
    lu_, lv_, lw_, lp_ = [], [], [], []
    for i in np.flatnonzero(ok):
        leaf[i] = n1 + i
        lu_.append(leaf[i]); lv_.append(key[(int(le[i]), float(np.round(snap_t[i], 2)))])
        lw_.append(max(snap_d[i], 1e-3)); lp_.append(-1)
    keep = ~split
    U = np.r_[lu[keep], np.array(rows_u, dtype=np.int64), np.array(lu_, dtype=np.int64)].astype(np.int64)
    V = np.r_[lv[keep], np.array(rows_v, dtype=np.int64), np.array(lv_, dtype=np.int64)].astype(np.int64)
    W = np.r_[el[keep], np.array(rows_w, dtype=float), np.array(lw_, dtype=float)]
    P = np.r_[np.flatnonzero(keep), np.array(rows_p, dtype=np.int64), np.array(lp_, dtype=np.int64)].astype(np.int64)
    n = n1 + k
    gE = np.where(P >= 0, E[np.maximum(P, 0)], -1)          # global edge of each local edge (-1 = leaf)
    steps = np.where(gE >= 0, G.steps[np.maximum(gE, 0)], False)

    def csr(mask):
        return csr_matrix((np.r_[W[mask], W[mask]], (np.r_[U[mask], V[mask]], np.r_[V[mask], U[mask]])), shape=(n, n))

    g_all, g_free = csr(np.ones(len(W), bool)), csr(~steps)
    edge_of = {}
    for j, (a, b) in enumerate(zip(U, V)):
        edge_of[(min(a, b), max(a, b))] = j
    srcs = sorted({s for s, _ in pairs if leaf[s] >= 0} | (set(np.flatnonzero(leaf >= 0).tolist()) if all_pairs else set()))
    out = {}
    if srcs:
        D, Pr = dijkstra(g_all, directed=False, indices=leaf[srcs], return_predecessors=True, limit=DIJKSTRA_LIMIT_M)
        Df = dijkstra(g_free, directed=False, indices=leaf[srcs], limit=DIJKSTRA_LIMIT_M)
        row = {s: r for r, s in enumerate(srcs)}
    gnode_of = np.r_[gnodes, np.full(n - n0, -1)]
    if all_pairs:
        out["_all"] = {"n": 0, "mean_net_m": None, "mean_straight_m": None}
    if all_pairs and srcs:
        # mean network and straight distance over all pairs of stops at distinct positions (AMPTI-like comparison)
        nd, sd_ = [], []
        for i in srcs:
            for j in srcs:
                if j <= i:
                    continue
                st_ = float(np.hypot(*(stop_xy[i] - stop_xy[j])))
                if st_ < 1.0:
                    continue
                d_ = D[row[i], leaf[j]]
                if np.isfinite(d_):
                    nd.append(d_); sd_.append(st_)
        out["_all"] = {"n": len(nd), "mean_net_m": float(np.mean(nd)) if nd else None,
                       "mean_straight_m": float(np.mean(sd_)) if sd_ else None}
    for s, t in pairs:
        if leaf[s] < 0 or leaf[t] < 0:
            out[(s, t)] = None
            continue
        r = row[s]
        d, df = D[r, leaf[t]], Df[r, leaf[t]]
        if not np.isfinite(d):
            out[(s, t)] = {"dist_m": np.inf, "dist_stepfree_m": np.inf}
            continue
        # trace the path target -> source
        seq = [leaf[t]]
        while seq[-1] != leaf[s]:
            seq.append(Pr[r, seq[-1]])
        seq = seq[::-1]
        ej = [edge_of[(min(a, b), max(a, b))] for a, b in zip(seq[:-1], seq[1:])]
        ge = gE[ej]
        isroad = np.where(ge >= 0, G.road[np.maximum(ge, 0)], False)
        cum = np.r_[0.0, np.cumsum(W[ej])]
        ev_pos, ev_sig, ev_tag, ev_val, ev_trk = [], [], [], [], []
        for i in range(1, len(seq) - 1):
            gn = gnode_of[seq[i]]
            if gn < 0:
                continue
            a_road, b_road = isroad[i - 1], isroad[i]
            across = (G.on_road[gn] or G.on_track[gn]) and not a_road and not b_road
            tagged_node = G.n_tag[gn]
            if not (across or tagged_node):
                continue
            adj = [x for x in (ge[i - 1], ge[i]) if x >= 0]
            ev_pos.append(cum[i])
            ev_sig.append(bool(G.n_signal[gn] or any(G.w_signal[x] for x in adj)))
            ev_tag.append(bool(tagged_node or any(G.fwc[x] for x in adj)))
            ev_val.append(bool(G.n_value[gn] or any(G.w_value[x] for x in adj)))
            ev_trk.append(bool(G.on_track[gn]))
        groups = []
        for j, p in enumerate(ev_pos):
            if groups and p - groups[-1]["end"] < GROUP_GAP_M:
                g = groups[-1]
                g["end"] = p; g["sig"] |= ev_sig[j]; g["tag"] |= ev_tag[j]; g["val"] |= ev_val[j]; g["trk"] |= ev_trk[j]
            else:
                groups.append({"end": p, "sig": ev_sig[j], "tag": ev_tag[j], "val": ev_val[j], "trk": ev_trk[j]})
        real = ge >= 0
        out[(s, t)] = {
            "dist_m": float(d), "dist_stepfree_m": float(df),
            "crossings": len(groups), "crossings_signal": sum(g["sig"] for g in groups),
            "crossings_tagged": sum(g["tag"] for g in groups), "crossings_value": sum(g["val"] for g in groups),
            "crossings_track": sum(g["trk"] for g in groups),
            "steps": bool(np.any(G.steps[ge[real]])), "tunnel": bool(np.any(G.tunnel[ge[real]])),
            "bridge": bool(np.any(G.bridge[ge[real]])),
            "road_m": float(W[ej][isroad].sum()), "len_m": float(W[ej].sum()),
        }
    return out
