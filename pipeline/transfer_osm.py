"""OSM attributes for the transfer-ease step (pipeline.transfer_ease): crossings, signals, tunnels, bridges, roads.

    python -m pipeline.transfer_osm        # one pass over the Poland PBF -> data/interim/transfer/osm_*.parquet

The walk graph of pipeline.walk_network keeps only the way class per edge and the OSM id per node.  This module adds,
for the nodes of the seven phase-1 walk graphs, what the transfer step needs to describe a walk between two stops:

* ``osm_nodes.parquet``  tagged nodes that lie on a walk graph: ``highway`` (crossing, traffic_signals, elevator, ...),
  ``crossing``, ``crossing:signals``, ``crossing_ref``, ``railway`` (crossing, tram_crossing, level_crossing, ...)
* ``osm_wayflags.parquet``  consecutive node pairs (OSM ids, unordered) of walkable ways (pipeline.walk_network.walk_class)
  with a flag of interest: tunnel (any value except no / building_passage), bridge (any value except no),
  footway=crossing with its ``crossing`` / ``crossing:signals`` / ``crossing:markings`` / ``crossing_ref`` value,
  conveying (escalators)
* ``osm_roadnodes.parquet``  OSM ids of walk-graph nodes that lie on a carriageway (highway in ROAD) or on a track
  (railway in TRACK), with the highest road class and the track kind; used to find where a walk crosses a road

No locations are read (membership in the walk graphs is enough), so the pass takes a few minutes.  Cached by the PBF
signature (size, mtime) and CODE_VERSION.
"""
from __future__ import annotations

import json
import time
from array import array

import numpy as np
import pandas as pd

from pipeline.common import INTERIM, RAW, write_json
from pipeline.walk_network import AGGS, load_graph, walk_class

PBF = RAW / "osm" / "poland-latest.osm.pbf"
OUT = INTERIM / "transfer"
CODE_VERSION = "transfer-osm-2026-11-24.2"   # .2: crossing:markings and crossing_ref of footway=crossing ways (W6 classes)

# carriageways a pedestrian has to cross (service roads, living streets and tracks for farm use are not counted)
ROAD = {"motorway": 7, "trunk": 6, "primary": 5, "secondary": 4, "tertiary": 3, "unclassified": 2, "residential": 1,
        "motorway_link": 7, "trunk_link": 6, "primary_link": 5, "secondary_link": 4, "tertiary_link": 3,
        "busway": 2, "bus_guideway": 2}
TRACK = {"tram": 1, "light_rail": 1, "rail": 2, "subway": 2, "narrow_gauge": 2}
NODE_KEYS = ("highway", "crossing", "crossing:signals", "crossing_ref", "railway", "crossing:markings")


def _sig() -> str:
    s = PBF.stat()
    return json.dumps([CODE_VERSION, s.st_size, s.st_mtime_ns])


def graph_ids() -> np.ndarray:
    ids = [load_graph(a)[0].osm_id.to_numpy() for a in AGGS]
    return np.unique(np.concatenate(ids))


def extract() -> dict:
    import osmium
    gid = graph_ids()
    nodes = {k: [] for k in ("id",) + NODE_KEYS}
    road_ref, road_cls = array("q"), array("b")
    trk_ref, trk_cls = array("q"), array("b")
    wf = {"a": array("q"), "b": array("q"), "tunnel": array("b"), "bridge": array("b"), "conveying": array("b"),
          "fw_crossing": array("b")}
    wf_cross, wf_sig, wf_mark, wf_ref = [], [], [], []
    fp = (osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY)
          .with_filter(osmium.filter.KeyFilter("highway", "railway", "crossing", "public_transport")))
    for o in fp:
        t = o.tags
        if o.is_node():
            if ("crossing" in t or t.get("highway") in ("crossing", "traffic_signals", "elevator")
                    or t.get("railway") in ("crossing", "tram_crossing", "level_crossing", "tram_level_crossing")):
                nodes["id"].append(o.id)
                for k in NODE_KEYS:
                    nodes[k].append(t.get(k))
            continue
        if not o.is_way():
            continue
        refs = [n.ref for n in o.nodes]
        hw, rw = t.get("highway"), t.get("railway")
        if hw in ROAD and t.get("area") != "yes":
            road_ref.extend(refs); road_cls.extend([ROAD[hw]] * len(refs))
        if rw in TRACK and t.get("service") not in ("yard", "siding", "spur"):
            trk_ref.extend(refs); trk_cls.extend([TRACK[rw]] * len(refs))
        if walk_class(t) is None or len(refs) < 2:
            continue
        tun = t.get("tunnel")
        tunnel = tun is not None and tun not in ("no", "building_passage")
        br = t.get("bridge")
        bridge = br is not None and br != "no"
        conv = t.get("conveying") not in (None, "no")
        fwc = t.get("footway") == "crossing" or t.get("path") == "crossing" or t.get("cycleway") == "crossing"
        if not (tunnel or bridge or conv or fwc):
            continue
        n = len(refs) - 1
        wf["a"].extend(refs[:-1]); wf["b"].extend(refs[1:])
        wf["tunnel"].extend([tunnel] * n); wf["bridge"].extend([bridge] * n)
        wf["conveying"].extend([conv] * n); wf["fw_crossing"].extend([fwc] * n)
        wf_cross.extend([t.get("crossing")] * n); wf_sig.extend([t.get("crossing:signals")] * n)
        wf_mark.extend([t.get("crossing:markings")] * n); wf_ref.extend([t.get("crossing_ref")] * n)
    nd = pd.DataFrame(nodes)
    nd = nd[np.isin(nd["id"].to_numpy(), gid)].sort_values("id").drop_duplicates("id").reset_index(drop=True)
    rr = pd.DataFrame({"id": np.frombuffer(road_ref, dtype=np.int64), "road": np.frombuffer(road_cls, dtype=np.int8)})
    rr = rr[np.isin(rr["id"].to_numpy(), gid)].groupby("id")["road"].max()
    tt = pd.DataFrame({"id": np.frombuffer(trk_ref, dtype=np.int64), "track": np.frombuffer(trk_cls, dtype=np.int8)})
    tt = tt[np.isin(tt["id"].to_numpy(), gid)].groupby("id")["track"].max()
    rn = pd.concat([rr, tt], axis=1).fillna(0).astype(np.int8).reset_index().rename(columns={"index": "id"})
    rn = rn.sort_values("id").reset_index(drop=True)
    w = pd.DataFrame({k: np.frombuffer(v, dtype=np.int64 if k in ("a", "b") else np.int8) for k, v in wf.items()})
    w["crossing"] = wf_cross
    w["crossing_signals"] = wf_sig
    w["crossing_markings"] = wf_mark
    w["crossing_ref"] = wf_ref
    lo, hi = np.minimum(w["a"], w["b"]), np.maximum(w["a"], w["b"])
    w["a"], w["b"] = lo, hi
    w = w[np.isin(w["a"].to_numpy(), gid) & np.isin(w["b"].to_numpy(), gid)]
    for c in ("tunnel", "bridge", "conveying", "fw_crossing"):
        w[c] = w[c].astype(bool)
    w = (w.sort_values(["a", "b", "crossing", "crossing_signals"], na_position="last", kind="stable")
         .groupby(["a", "b"], sort=True)
         .agg(tunnel=("tunnel", "max"), bridge=("bridge", "max"), conveying=("conveying", "max"),
              fw_crossing=("fw_crossing", "max"), crossing=("crossing", "first"),
              crossing_signals=("crossing_signals", "first"), crossing_markings=("crossing_markings", "first"),
              crossing_ref=("crossing_ref", "first")).reset_index())
    return {"nodes": nd, "roadnodes": rn, "wayflags": w}


def load(refresh: bool = False) -> dict:
    """The three tables (cached in data/interim/transfer/)."""
    OUT.mkdir(parents=True, exist_ok=True)
    sigf = OUT / "osm.sig"
    paths = {k: OUT / f"osm_{k}.parquet" for k in ("nodes", "roadnodes", "wayflags")}
    if not refresh and sigf.exists() and sigf.read_text() == _sig() and all(p.exists() for p in paths.values()):
        return {k: pd.read_parquet(p) for k, p in paths.items()}
    t0 = time.time()
    res = extract()
    for k, p in paths.items():
        res[k].to_parquet(p, index=False)
    sigf.write_text(_sig())
    write_json(OUT / "osm_stats.json", {"seconds": round(time.time() - t0, 1),
                                         **{k: int(len(v)) for k, v in res.items()}})
    return res


if __name__ == "__main__":
    t0 = time.time()
    r = load(refresh=True)
    print({k: len(v) for k, v in r.items()}, f"{time.time() - t0:.0f} s")
