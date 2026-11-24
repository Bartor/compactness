"""OSM data for the tram stretch step (pipeline.tram_stretches): tram track, roads near it, crossings and signals.

    python -m pipeline.speed_osm        # one pass over data/raw/osm/poland-latest.osm.pbf (ways with node locations)

Read inside the bounding boxes of the seven phase-1 FUAs (+ 2 km), OSM snapshot 2026-11-22:
* ``tram_ways``   railway=tram (any service value; service is kept), node ids and EPSG:2180 coordinates, tags
                  service, embedded, bridge, tunnel, maxspeed, name
* ``roads``       highway ways used as carriageways (ROAD) plus living_street / pedestrian / service, with
                  highway class, oneway, embedded_rails, name, bridge, tunnel, node ids, coordinates
* ``footways``    node ids of footway / path / cycleway ways (only to find where a footpath meets the track)
* ``xnodes``      tagged nodes: highway=traffic_signals / crossing / stop / give_way, railway=level_crossing /
                  tram_level_crossing / crossing / tram_crossing / switch, any crossing=* or crossing:signals=*

Cached in data/interim/speed/osm_*.parquet by the PBF signature and CODE_VERSION.
"""
from __future__ import annotations

import json
import time
from array import array

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline.boundaries import load_agglomeration
from pipeline.common import CRS_METRIC, INTERIM, RAW, write_json

PBF = RAW / "osm" / "poland-latest.osm.pbf"
OUT = INTERIM / "speed"
CODE_VERSION = "speed-osm-2026-11-24.1"
OSM_DATE = "2026-11-22"
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
ROAD = {"motorway": 7, "trunk": 6, "primary": 5, "secondary": 4, "tertiary": 3, "unclassified": 2, "residential": 1,
        "motorway_link": 7, "trunk_link": 6, "primary_link": 5, "secondary_link": 4, "tertiary_link": 3,
        "busway": 2, "living_street": 0, "pedestrian": -1, "service": -2}
FOOT = {"footway", "path", "cycleway", "steps", "bridleway"}
XNODE_HW = {"traffic_signals", "crossing", "stop", "give_way"}
XNODE_RW = {"level_crossing", "tram_level_crossing", "crossing", "tram_crossing", "switch", "railway_crossing"}
TO2180 = Transformer.from_crs("EPSG:4326", CRS_METRIC, always_xy=True)
TO4326 = Transformer.from_crs(CRS_METRIC, "EPSG:4326", always_xy=True)


def _sig() -> str:
    s = PBF.stat()
    return json.dumps([CODE_VERSION, s.st_size, s.st_mtime_ns])


def boxes() -> list[tuple]:
    out = []
    for a in AGGS:
        g = load_agglomeration(a)["fua"].buffer(2000)
        x0, y0, x1, y1 = g.bounds
        lo, la = TO4326.transform([x0, x1, x0, x1], [y0, y0, y1, y1])
        out.append((min(lo), min(la), max(lo), max(la)))
    return out


def extract() -> dict:
    import osmium
    bx = boxes()

    def inside(x0, y0, x1, y1):
        return any(not (x1 < b[0] or x0 > b[2] or y1 < b[1] or y0 > b[3]) for b in bx)

    tram, road = [], []
    foot_ref = array("q")
    xn = []
    fp = (osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY)
          .with_locations("flex_mem")
          .with_filter(osmium.filter.KeyFilter("highway", "railway", "crossing", "crossing:signals")))
    for o in fp:
        t = o.tags
        if o.is_node():
            hw, rw = t.get("highway"), t.get("railway")
            if hw in XNODE_HW or rw in XNODE_RW or "crossing" in t or "crossing:signals" in t:
                loc = o.location
                if not loc.valid() or not inside(loc.lon, loc.lat, loc.lon, loc.lat):
                    continue
                xn.append((o.id, loc.lon, loc.lat, hw, rw, t.get("crossing"), t.get("crossing:signals"),
                           t.get("traffic_signals"), t.get("crossing:markings")))
            continue
        if not o.is_way():
            continue
        hw, rw = t.get("highway"), t.get("railway")
        is_tram = rw == "tram"
        is_road = hw in ROAD and t.get("area") != "yes"
        is_foot = hw in FOOT
        if not (is_tram or is_road or is_foot):
            continue
        refs, lons, lats = [], [], []
        for n in o.nodes:
            loc = n.location
            if loc.valid():
                refs.append(n.ref); lons.append(loc.lon); lats.append(loc.lat)
        if len(refs) < 2 or not inside(min(lons), min(lats), max(lons), max(lats)):
            continue
        if is_foot:
            foot_ref.extend(refs)
            continue
        rec = {"way_id": o.id, "refs": refs, "lon": lons, "lat": lats, "name": t.get("name"),
               "bridge": t.get("bridge"), "tunnel": t.get("tunnel"), "layer": t.get("layer")}
        if is_tram:
            rec.update({"service": t.get("service"), "embedded": t.get("embedded"), "maxspeed": t.get("maxspeed"),
                        "usage": t.get("usage")})
            tram.append(rec)
        if is_road:
            rec = dict(rec)
            rec.update({"highway": hw, "cls": ROAD[hw], "oneway": t.get("oneway"), "embedded_rails": t.get("embedded_rails"),
                        "lanes": t.get("lanes"), "maxspeed": t.get("maxspeed"), "junction": t.get("junction")})
            road.append(rec)
    return {"tram": tram, "road": road, "foot": np.unique(np.frombuffer(foot_ref, dtype=np.int64)), "xnodes": xn}


def _ways_df(recs: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(recs)
    xs, ys = [], []
    for lo, la in zip(df["lon"], df["lat"]):
        x, y = TO2180.transform(np.asarray(lo), np.asarray(la))
        xs.append(np.asarray(x)); ys.append(np.asarray(y))
    df["x"], df["y"] = xs, ys
    df = df.drop(columns=["lon", "lat"])
    df["refs"] = [np.asarray(r, dtype=np.int64) for r in df["refs"]]
    return df.sort_values("way_id", kind="stable").reset_index(drop=True)


def load(refresh: bool = False) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    sigf = OUT / "osm.sig"
    paths = {k: OUT / f"osm_{k}.parquet" for k in ("tram", "road", "foot", "xnodes")}
    if not refresh and sigf.exists() and sigf.read_text() == _sig() and all(p.exists() for p in paths.values()):
        out = {k: pd.read_parquet(p) for k, p in paths.items()}
        for k in ("tram", "road"):
            for c in ("refs", "x", "y"):
                out[k][c] = [np.asarray(v) for v in out[k][c]]
        return out
    t0 = time.time()
    r = extract()
    tram = _ways_df(r["tram"])
    road = _ways_df(r["road"])
    foot = pd.DataFrame({"id": r["foot"]})
    xn = pd.DataFrame(r["xnodes"], columns=["id", "lon", "lat", "highway", "railway", "crossing", "crossing_signals",
                                            "traffic_signals", "crossing_markings"])
    xn["x"], xn["y"] = TO2180.transform(xn["lon"].to_numpy(), xn["lat"].to_numpy())
    xn = xn.drop(columns=["lon", "lat"]).sort_values("id").drop_duplicates("id").reset_index(drop=True)
    res = {"tram": tram, "road": road, "foot": foot, "xnodes": xn}
    for k, p in paths.items():
        res[k].to_parquet(p, index=False)
    sigf.write_text(_sig())
    write_json(OUT / "osm_stats.json", {"seconds": round(time.time() - t0, 1), "osm_date": OSM_DATE,
                                         **{k: int(len(v)) for k, v in res.items()}})
    return res


if __name__ == "__main__":
    t0 = time.time()
    r = load(refresh=True)
    print({k: len(v) for k, v in r.items()}, f"{time.time() - t0:.0f} s")
