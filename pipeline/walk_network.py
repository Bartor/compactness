"""Walkable OSM network per agglomeration and network distances from stops to grid cells.

    python -m pipeline.walk_network           # extract + build graphs for the 7 phase-1 agglomerations

Extraction (one pyosmium pass over data/raw/osm/poland-latest.osm.pbf, ways with node locations):
a way is walkable when
* highway in WALK_ALWAYS (footway, path, pedestrian, steps, living_street, residential, service,
  unclassified, tertiary(_link), secondary(_link), primary(_link), track, road, corridor, platform),
  or highway in WALK_IF_SIDEWALK (trunk, trunk_link) with a sidewalk tag (yes/both/left/right) or
  an explicit foot permission, or highway = cycleway / bridleway with an explicit foot permission
  (in Poland a plain cycleway is closed to pedestrians), or motorway(_link) only with an explicit foot
  permission; or the way is a platform (railway=platform, public_transport=platform);
* and it is not closed to pedestrians: foot in (no, private, use_sidepath), or access in (no,
  private) without an explicit foot permission (yes, designated, permissive), or a lifecycle
  highway value (construction, proposed, ...).
Station tunnels and underpasses are ordinary footways / corridors / steps in OSM and pass the rule
as mapped.  Relations (multipolygon pedestrian areas) are not read: the outline of a pedestrian
area mapped as a closed way is walkable (around the edge, not across).

Kept per agglomeration: ways with at least one node inside FUA + WALK_BUFFER_M (bounding box first,
then the polygon on the edge level).  Graph: one node per OSM node, one undirected edge per pair
of consecutive way nodes, length in EPSG:2180 metres.

Routing (class Router): stops and sample points are snapped to the nearest edge of a "main"
component (connected components with >= MIN_COMPONENT_M of edges; tiny islands are mapping gaps
that would trap a snapped point) within a maximum snap distance; the snapped edges are split at the
snap positions, so a stop and a point on the same long edge get their along-edge distance.  Each
stop becomes a leaf node joined to its snap position by the snap distance; a point's distance is
the network distance of its snap position plus its own snap distance.  Multi-source Dijkstra
(scipy.sparse.csgraph.dijkstra, min_only=True, with a cut-off) gives, for a set of stops, the
distance from every point to the nearest stop of the set.

Outputs: data/interim/walk/<agg>_nodes.parquet, <agg>_edges.parquet, extract_stats.json, _meta.json
"""
from __future__ import annotations

import json
import time
from array import array

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

from pipeline.boundaries import load_agglomeration
from pipeline.common import INTERIM, RAW, round_sig, write_json, write_meta

PBF = RAW / "osm" / "poland-latest.osm.pbf"
OUT = INTERIM / "walk"
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
WALK_BUFFER_M = 3000          # network kept beyond the FUA edge (stops / paths just outside it)
MIN_COMPONENT_M = 2000        # snap only to components with at least this much edge length

WALK_ALWAYS = {"footway", "path", "pedestrian", "steps", "living_street", "residential", "service",
               "unclassified", "tertiary", "tertiary_link", "secondary", "secondary_link", "primary",
               "primary_link", "track", "road", "corridor", "platform"}
WALK_IF_SIDEWALK = {"trunk", "trunk_link"}
WALK_IF_FOOT = {"cycleway", "bridleway", "motorway", "motorway_link", "trunk", "trunk_link"}
FOOT_OK = {"yes", "designated", "permissive", "official"}
FOOT_NO = {"no", "private", "use_sidepath"}
ACCESS_NO = {"no", "private"}
SIDEWALK_YES = {"yes", "both", "left", "right"}
LIFECYCLE = {"construction", "proposed", "abandoned", "disused", "razed", "demolished", "removed"}

TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def walk_class(tags) -> str | None:
    """Return a class label for a walkable way, None otherwise (rule in the module docstring)."""
    g = tags.get
    hw, foot, access = g("highway"), g("foot"), g("access")
    if foot in FOOT_NO:
        return None
    if access in ACCESS_NO and foot not in FOOT_OK:
        return None
    if hw in LIFECYCLE or g("construction") is not None and hw == "construction":
        return None
    if hw in WALK_ALWAYS:
        return hw
    if hw in WALK_IF_SIDEWALK:
        sw = {g("sidewalk"), g("sidewalk:both"), g("sidewalk:left"), g("sidewalk:right")}
        if sw & SIDEWALK_YES or foot in FOOT_OK:
            return hw
        return None
    if hw in WALK_IF_FOOT and foot in FOOT_OK:
        return hw
    if hw is None and (g("railway") == "platform" or g("public_transport") == "platform"):
        return "platform"
    return None


# ------------------------------------------------------------------ extraction
def agg_regions() -> dict:
    out = {}
    for a in AGGS:
        geo = load_agglomeration(a)
        reg = geo["fua"].buffer(WALK_BUFFER_M)
        xmin, ymin, xmax, ymax = reg.bounds
        lo, la = TO4326.transform([xmin, xmax, xmin, xmax], [ymin, ymin, ymax, ymax])
        out[a] = {"region": reg, "bbox_ll": (min(lo), min(la), max(lo), max(la))}
    return out


def extract(regions: dict) -> dict:
    """One pass over the PBF; returns per agglomeration (node ids, lon, lat, way offsets, classes)."""
    import osmium
    boxes = [(a, r["bbox_ll"]) for a, r in regions.items()]
    gx0 = min(b[0] for _, b in boxes); gy0 = min(b[1] for _, b in boxes)
    gx1 = max(b[2] for _, b in boxes); gy1 = max(b[3] for _, b in boxes)
    store = {a: {"ids": array("q"), "lon": array("d"), "lat": array("d"), "off": array("q", [0]),
                 "cls": [], "wid": array("q")} for a in regions}
    fp = (osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY)
          .with_locations("flex_mem")
          .with_filter(osmium.filter.KeyFilter("highway", "railway", "public_transport")))
    n_ways = n_walk = 0
    for o in fp:
        if not o.is_way():
            continue
        n_ways += 1
        cls = walk_class(o.tags)
        if cls is None:
            continue
        ids, lons, lats = [], [], []
        for n in o.nodes:
            loc = n.location
            if loc.valid():
                ids.append(n.ref); lons.append(loc.lon); lats.append(loc.lat)
        if len(ids) < 2:
            continue
        x0, x1, y0, y1 = min(lons), max(lons), min(lats), max(lats)
        if x1 < gx0 or x0 > gx1 or y1 < gy0 or y0 > gy1:
            continue
        n_walk += 1
        for a, (bx0, by0, bx1, by1) in boxes:
            if x1 < bx0 or x0 > bx1 or y1 < by0 or y0 > by1:
                continue
            s = store[a]
            s["ids"].extend(ids); s["lon"].extend(lons); s["lat"].extend(lats)
            s["off"].append(len(s["ids"])); s["cls"].append(cls); s["wid"].append(o.id)
    print(f"ways with walk keys: {n_ways:,}; walkable in bbox: {n_walk:,}")
    return store


def build_graph(a: str, s: dict, region) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    ids = np.frombuffer(s["ids"], dtype=np.int64)
    lon = np.frombuffer(s["lon"], dtype=np.float64)
    lat = np.frombuffer(s["lat"], dtype=np.float64)
    off = np.frombuffer(s["off"], dtype=np.int64)
    cls = np.array(s["cls"], dtype=object)
    # edges: consecutive pairs inside each way
    way_of = np.repeat(np.arange(len(off) - 1), np.diff(off))
    same = way_of[1:] == way_of[:-1]
    i0 = np.flatnonzero(same)
    uid, inv = np.unique(ids, return_inverse=True)
    x, y = TO2180.transform(lon, lat)
    nx = np.zeros(len(uid)); ny = np.zeros(len(uid))
    nx[inv] = x; ny[inv] = y
    u, v = inv[i0], inv[i0 + 1]
    ln = np.hypot(nx[u] - nx[v], ny[u] - ny[v])
    ecls = cls[way_of[i0]]
    keep = u != v
    u, v, ln, ecls = u[keep], v[keep], ln[keep], ecls[keep]
    # region filter: keep an edge when one endpoint lies inside FUA + buffer
    inside = shapely.contains_xy(region, nx, ny)
    k = inside[u] | inside[v]
    u, v, ln, ecls = u[k], v[k], ln[k], ecls[k]
    # de-duplicate undirected edges (overlapping ways, e.g. platform + footway)
    a_, b_ = np.minimum(u, v), np.maximum(u, v)
    e = pd.DataFrame({"u": a_, "v": b_, "len_m": ln, "cls": ecls})
    e = e.sort_values(["u", "v", "len_m", "cls"], kind="stable").drop_duplicates(["u", "v"]).reset_index(drop=True)
    used = np.unique(np.r_[e.u.values, e.v.values])
    remap = np.full(len(uid), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    nodes = pd.DataFrame({"osm_id": uid[used], "x": nx[used], "y": ny[used]})
    e["u"], e["v"] = remap[e.u.values], remap[e.v.values]
    # components
    n = len(nodes)
    g = coo_matrix((np.ones(len(e)), (e.u.values, e.v.values)), shape=(n, n)).tocsr()
    ncomp, lab = connected_components(g, directed=False)
    clen = np.bincount(lab[e.u.values], weights=e.len_m.values, minlength=ncomp)
    nodes["comp"] = lab
    nodes["comp_main"] = clen[lab] >= MIN_COMPONENT_M
    stats = {"nodes": int(n), "edges": int(len(e)), "km_total": float(e.len_m.sum() / 1000),
             "km_by_class": {c: float(v / 1000) for c, v in e.groupby("cls")["len_m"].sum().items()},
             "components": int(ncomp), "km_in_main_components": float(clen[clen >= MIN_COMPONENT_M].sum() / 1000),
             "km_in_small_components": float(clen[clen < MIN_COMPONENT_M].sum() / 1000),
             "largest_component_share_km": float(clen.max() / clen.sum())}
    return nodes, e, stats


def load_graph(agg: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_parquet(OUT / f"{agg}_nodes.parquet"), pd.read_parquet(OUT / f"{agg}_edges.parquet")


# ------------------------------------------------------------------ routing
class Router:
    """Walk graph of one agglomeration with stops and sample points snapped onto it.

    ``stop_xy`` (k, 2) and ``pt_xy`` (m, 2) in EPSG:2180; ``stop_max_snap`` (k,) and ``pt_max_snap``
    (scalar) are the maximum snap distances.  After construction:
    ``stop_snap_d`` / ``pt_snap_d`` (inf when not snapped), ``dist(stop_idx, limit)`` -> (m,) distances
    from each point to the nearest of the given stops (inf beyond ``limit``).
    """

    def __init__(self, agg: str, stop_xy: np.ndarray, stop_max_snap: np.ndarray, pt_xy: np.ndarray,
                 pt_max_snap: float):
        nodes, edges = load_graph(agg)
        main = nodes.comp_main.values
        em = main[edges.u.values]          # both endpoints share the component
        nx, ny = nodes.x.values, nodes.y.values
        eu, ev, el = edges.u.values, edges.v.values, edges.len_m.values
        cand = np.flatnonzero(em)
        segs = shapely.linestrings(np.stack([np.c_[nx[eu[cand]], ny[eu[cand]]],
                                             np.c_[nx[ev[cand]], ny[ev[cand]]]], axis=1))
        tree = shapely.STRtree(segs)
        n0 = len(nodes)

        def snap(xy, maxd):
            pts = shapely.points(xy)
            md = float(np.max(maxd))
            (pi, si), d = tree.query_nearest(pts, max_distance=md, return_distance=True, all_matches=False)
            order = np.lexsort((si, pi))
            pi, si, d = pi[order], si[order], d[order]
            first = np.r_[True, pi[1:] != pi[:-1]]
            pi, si, d = pi[first], si[first], d[first]
            lim = np.broadcast_to(np.asarray(maxd, dtype=float), (len(xy),))[pi]
            ok = d <= lim
            pi, si, d = pi[ok], si[ok], d[ok]
            e = cand[si]
            t = shapely.line_locate_point(segs[si], pts[pi])
            out_e = np.full(len(xy), -1, dtype=np.int64); out_t = np.zeros(len(xy)); out_d = np.full(len(xy), np.inf)
            out_e[pi], out_t[pi], out_d[pi] = e, t, d
            return out_e, out_t, out_d

        se, st, sd = snap(stop_xy, stop_max_snap)
        pe, pt, pd_ = snap(pt_xy, pt_max_snap)
        # split snapped edges at the snap positions
        snaps = pd.DataFrame({"e": np.r_[se, pe], "t": np.r_[st, pt]})
        snaps = snaps[snaps.e >= 0]
        snaps["t"] = snaps.t.round(2)
        sp = snaps.drop_duplicates().sort_values(["e", "t"]).reset_index(drop=True)
        sp["node"] = n0 + np.arange(len(sp))
        # chain per edge: u - p1 - ... - pk - v
        grp = sp.groupby("e", sort=True)
        first_t = grp.t.transform("min").values
        prev_node = np.where(sp.t.values == first_t, eu[sp.e.values], np.r_[-1, sp.node.values[:-1]])
        prev_t = np.where(sp.t.values == first_t, 0.0, np.r_[0.0, sp.t.values[:-1]])
        last = sp.t.values == grp.t.transform("max").values
        chain_u = np.r_[prev_node, sp.node.values[last]]
        chain_v = np.r_[sp.node.values, ev[sp.e.values[last]]]
        chain_w = np.r_[sp.t.values - prev_t, el[sp.e.values[last]] - sp.t.values[last]]
        split = np.zeros(len(edges), bool)
        split[sp.e.unique()] = True
        # stop leaves
        key = pd.MultiIndex.from_frame(sp[["e", "t"]])
        ok_s = se >= 0
        s_node = np.full(len(se), -1, dtype=np.int64)
        s_node[ok_s] = sp.node.values[key.get_indexer(pd.MultiIndex.from_arrays([se[ok_s], np.round(st[ok_s], 2)]))]
        ok_p = pe >= 0
        p_node = np.full(len(pe), -1, dtype=np.int64)
        p_node[ok_p] = sp.node.values[key.get_indexer(pd.MultiIndex.from_arrays([pe[ok_p], np.round(pt[ok_p], 2)]))]
        n1 = n0 + len(sp)
        leaf = n1 + np.arange(len(se))
        U = np.r_[eu[~split], chain_u, leaf[ok_s]]
        V = np.r_[ev[~split], chain_v, s_node[ok_s]]
        W = np.r_[el[~split], np.maximum(chain_w, 1e-3), np.maximum(sd[ok_s], 1e-3)]
        n = n1 + len(se)
        g = csr_matrix((np.r_[W, W], (np.r_[U, V], np.r_[V, U])), shape=(n, n))
        g.sum_duplicates()   # parallel duplicates are impossible after edge de-dup; keep csr canonical
        self.g = g
        self.stop_leaf = np.where(ok_s, leaf, -1)
        self.stop_snap_d = sd
        self.pt_node = p_node
        self.pt_snap_d = pd_
        self.n_nodes = n

    def dist(self, stop_idx: np.ndarray, limit: float) -> np.ndarray:
        src = np.unique(self.stop_leaf[np.asarray(stop_idx, dtype=np.int64)])
        src = src[src >= 0]
        out = np.full(len(self.pt_node), np.inf)
        if not len(src):
            return out
        D = dijkstra(self.g, directed=False, indices=src, min_only=True, limit=limit)
        ok = self.pt_node >= 0
        out[ok] = D[self.pt_node[ok]] + self.pt_snap_d[ok]
        return out


# ------------------------------------------------------------------ main
def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    regions = agg_regions()
    store = extract(regions)
    print(f"extracted in {time.time() - t0:.0f} s")
    stats = {}
    for a in AGGS:
        nodes, edges, st = build_graph(a, store[a], regions[a]["region"])
        nodes.to_parquet(OUT / f"{a}_nodes.parquet", index=False)
        edges.to_parquet(OUT / f"{a}_edges.parquet", index=False)
        stats[a] = st
        print(a, {k: v for k, v in st.items() if k != "km_by_class"})
    write_json(OUT / "extract_stats.json", round_sig(stats, 6))
    write_meta(OUT, "walk_network", inputs=["osm_poland_pbf"], started=t0, extra={
        "walk_buffer_m": WALK_BUFFER_M, "min_component_m": MIN_COMPONENT_M,
        "walk_always": sorted(WALK_ALWAYS), "walk_if_sidewalk": sorted(WALK_IF_SIDEWALK),
        "walk_if_foot": sorted(WALK_IF_FOOT), "foot_no": sorted(FOOT_NO), "access_no": sorted(ACCESS_NO),
        "osm_date": "2026-11-22", "crs": "EPSG:2180",
        "outputs": sorted(p.name for p in OUT.iterdir() if p.name != "_meta.json"),
    })
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
