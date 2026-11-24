"""Precomputed isochrones for the map's "skąd dojadę" mode (ROADMAP item 6).

    python -m pipeline.isochrones origins [--agg ...]                  # origin index, no JVM
    python -m pipeline.isochrones route   [--agg ...] [--threads 4] [--xmx 8G]
    python -m pipeline.isochrones build   [--agg ...]                  # polygons, web JSON, QA

The site is static, so it cannot route on demand: every agglomeration gets a fixed set of origins and, per origin,
isochrone polygons that the site shows for the origin nearest to a click.

Origins (per agglomeration)
* the configured centre and hub, and every extra centre of the polycentric agglomerations (GZM, Trójmiasto);
* the 30 busiest stop areas by departures per hour over the reference day (``results/layers/transfer_nodes.parquet``,
  ``dep_per_h_day``, stop areas in the FUA), skipping any within 300 m of a centre or hub;
* a regular lattice: 1 km blocks over the populated part of the core city (block with >= 100 residents) and
  2 km blocks over the rest of the GTFS-covered FUA (block with >= 100 residents in covered cells).  The origin of
  a block is the centre of its most populated 250 m cell, so it lies where people live and not in a field.
  ``LATTICE_KM`` holds the two spacings; they were widened per city where the web file would pass ~4 MB.

Travel times (R5, the production parameters of pipeline.access via ``pipeline.access.make_task``)
* to every 250 m cell of the FUA + 15 km region whose centre is in Poland (populated or not, so polygons have no
  holes in parks and fields);
* public transport + walking, Wednesday 2026-11-25, median over departures every minute 07:00-09:00 ("am") and
  20:00-22:00 ("evening"); walk 5 km/h, access / egress <= 12 min; per cell min(transit, walk only) as in
  production; walking only ("walk") for comparison.  Scheduled times, not real ones.
* stored sparse (cells reached within 60 min) in chunks under data/interim/isochrones/<agg>/<scenario>/,
  resumable: a chunk is skipped when it exists with the current signature.

Polygons
* cells with time <= T for T in 15, 30, 45, 60 (walk: 15, 30) are dissolved (4-connected), simplified with
  Douglas-Peucker at 50 m in EPSG:2180, transformed to WGS84 and encoded as Google encoded polylines at 5 decimals
  ([lat, lon] order, as the format defines).  Polygons are cumulative ("do 30 min" contains "do 15 min").
* residents per band: census-scaled population (NSP 2021 on the GHSL 250 m pattern), cumulative and per band.

Outputs: results/web/isochrones/<agg>.json (+ _meta.json), QA in results/qa/isochrones/.
Copies of the production networks are made under data/interim/isochrones/r5/<agg>/ (production files are read only).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gc
import hashlib
import json
import os
import shutil
import sys
import time
import warnings
from functools import lru_cache
from pathlib import Path

warnings.filterwarnings("ignore", message="The provided departure time window is below 5 minutes")

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from pipeline import access_inputs as AI
from pipeline.common import INTERIM, RESULTS, load_config

CFG = load_config()
AGGS = ["trojmiasto", "poznan", "wroclaw", "lodz", "krakow", "gzm", "warszawa"]
OUT = INTERIM / "isochrones"
WEB = RESULTS / "web" / "isochrones"
QA = RESULTS / "qa" / "isochrones"
CODE_VERSION = "isochrones-2026-11-24.1"
CELL = 250.0
MAX_MIN = 60
UNREACHED = 255
CHUNK = 50
N_STOPS = 30
STOP_MIN_GAP_M = 300.0
BLOCK_MIN_POP = 100.0
SIMPLIFY_M = 50.0
TARGET_BYTES = 4_000_000
# lattice spacing in km: (core, rest of the covered area); widened where the file would pass TARGET_BYTES
# (core and rest must differ: the spacing is part of the origin id).  Chosen 2026-11-24 from measured bytes per
# origin: at (1, 2) Kraków was 5.4 MB and GZM 8.6 MB; Kraków (1, 4) 4.12 MB, Warszawa (2, 6) 4.17 MB.
LATTICE_KM = {a: (1, 2) for a in AGGS}
LATTICE_KM.update({"krakow": (1, 5), "gzm": (2, 3), "warszawa": (2, 7)})
# production scenario used for the R5 task, thresholds drawn
SCEN = {"am": ("pt_am", [15, 30, 45, 60]), "evening": ("pt_evening", [15, 30, 45, 60]), "walk": ("walk", [15, 30])}
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
KIND_ORDER = {"hub": 0, "centre": 1, "stop_area": 2, "grid": 3}


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# ------------------------------------------------------------------ destination lattice
@lru_cache(maxsize=None)
def lattice(agg: str) -> pd.DataFrame:
    """All 250 m cells with centre in FUA + 15 km and in Poland: cell_id, i, j, x, y, lon, lat, pop (census-scaled)."""
    import rasterio
    reg = AI.load_agglomeration(agg)["buffered"]
    x0, y0, x1, y1 = reg.bounds
    i = np.arange(int(np.floor(x0 / CELL)), int(np.ceil(x1 / CELL)))
    j = np.arange(int(np.floor(y0 / CELL)), int(np.ceil(y1 / CELL)))
    ii, jj = np.meshgrid(i, j, indexing="ij")
    ii, jj = ii.ravel(), jj.ravel()
    x, y = (ii + 0.5) * CELL, (jj + 0.5) * CELL
    m = shapely.contains_xy(reg, x, y)
    ii, jj, x, y = ii[m], jj[m], x[m], y[m]
    with rasterio.open(INTERIM / "grid250" / "poland_mask_250m_epsg2180.tif") as r:
        rr, cc = rasterio.transform.rowcol(r.transform, x, y)
        rr, cc = np.asarray(rr), np.asarray(cc)
        a = r.read(1)
        ok = (rr >= 0) & (rr < a.shape[0]) & (cc >= 0) & (cc < a.shape[1])
        pl = np.zeros(len(x), bool)
        pl[ok] = a[rr[ok], cc[ok]] == 1
    cid = np.char.add(np.char.add("E", (ii * 250).astype(str)), np.char.add("N", (jj * 250).astype(str)))
    pop = AI.destinations(agg).set_index("cell_id")["w_census"]
    pl |= pd.Index(cid).isin(pop.index[pop > 0])          # populated coastal cells whose centre lies in the sea
    ii, jj, x, y, cid = ii[pl], jj[pl], x[pl], y[pl], cid[pl]
    d = pd.DataFrame({"cell_id": cid, "i": ii, "j": jj, "x": x, "y": y})
    d["pop"] = d["cell_id"].map(pop).fillna(0.0).to_numpy()
    d = d.sort_values("cell_id", kind="stable").reset_index(drop=True)
    d["lon"], d["lat"] = TO4326.transform(d["x"].to_numpy(), d["y"].to_numpy())
    return d


def lattice_hash(agg: str) -> str:
    return AI.frame_hash(lattice(agg), ["cell_id", "pop"])


# ------------------------------------------------------------------ origins
def _slug(s: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _blocks(c: pd.DataFrame, km: int, prefix: str) -> list[dict]:
    """One origin per km x km block with >= BLOCK_MIN_POP residents, at its most populated 250 m cell."""
    if not len(c):
        return []
    s = km * 1000
    c = c.assign(bi=np.floor(c["x"] / s).astype(np.int64), bj=np.floor(c["y"] / s).astype(np.int64))
    tot = c.groupby(["bi", "bj"])["w_census"].sum()
    keep = tot[tot >= BLOCK_MIN_POP].index
    c = c.set_index(["bi", "bj"]).loc[keep].reset_index()
    best = c.sort_values(["bi", "bj", "w_census", "cell_id"], ascending=[True, True, False, True]).groupby(["bi", "bj"]).head(1)
    out = []
    for r in best.itertuples():
        out.append({"id": f"{prefix}{km}-{int(r.bi * km)}-{int(r.bj * km)}", "kind": "grid",
                    "name": f"siatka {km} km", "x": float(r.x), "y": float(r.y)})
    return out


def build_origins(agg: str) -> pd.DataFrame:
    a = CFG["agglomerations"][agg]
    pts = []
    for c in AI.centres(agg):
        kind = "hub" if c["kind"] == "hub" else "centre"
        if c["kind"] == "centre" and "hub" in a and (a["hub"]["lon"], a["hub"]["lat"]) == (a["centre"]["lon"], a["centre"]["lat"]):
            kind = "hub"           # the same point is centre and hub (Trójmiasto, GZM)
        oid = "hub" if kind == "hub" else ("centre" if c["kind"] == "centre" else f"centre-{_slug(c['name'])}")
        pts.append({"id": oid, "kind": kind, "name": c["name"], "x": c["x"], "y": c["y"]})
    tn = pd.read_parquet(RESULTS / "layers" / "transfer_nodes.parquet",
                         columns=["node_id", "agglomeration", "name", "dep_per_h_day", "in_fua", "geometry"])
    tn = tn[(tn["agglomeration"] == agg) & tn["in_fua"] & tn["dep_per_h_day"].notna()]
    tn = tn.sort_values(["dep_per_h_day", "node_id"], ascending=[False, True])
    g = shapely.from_wkb(tn["geometry"].to_numpy())
    sx, sy = TO2180.transform(shapely.get_x(g), shapely.get_y(g))
    fixed = np.array([[p["x"], p["y"]] for p in pts])
    n = 0
    for k, r in enumerate(tn.itertuples()):
        if n >= N_STOPS:
            break
        if np.min(np.hypot(fixed[:, 0] - sx[k], fixed[:, 1] - sy[k])) < STOP_MIN_GAP_M:
            continue
        pts.append({"id": f"stop-{r.node_id.split('-', 1)[1]}", "kind": "stop_area", "name": r.name,
                    "x": float(sx[k]), "y": float(sy[k]), "dep_per_h_day": round(float(r.dep_per_h_day), 1)})
        n += 1
    d = AI.destinations(agg)
    d = d[d["populated"] & d["in_fua"]]
    m = AI.mask(agg).set_index("cell_id")["in_mask_all"]
    d = d.assign(in_mask=d["cell_id"].map(m).fillna(False).astype(bool))
    core_km, rest_km = LATTICE_KM[agg]
    pts += _blocks(d[d["in_core"]], core_km, "g")
    pts += _blocks(d[~d["in_core"] & d["in_mask"]], rest_km, "g")
    o = pd.DataFrame(pts)
    o["lon"], o["lat"] = TO4326.transform(o["x"].to_numpy(), o["y"].to_numpy())
    o["order"] = o["kind"].map(KIND_ORDER)
    o = o.sort_values(["order", "id"], kind="stable").drop(columns="order").reset_index(drop=True)
    assert o["id"].is_unique, o[o["id"].duplicated()]
    return o


def origins_path(agg: str) -> Path:
    return OUT / agg / "origins.parquet"


def origins(agg: str) -> pd.DataFrame:
    p = origins_path(agg)
    if not p.exists():
        o = build_origins(agg)
        p.parent.mkdir(parents=True, exist_ok=True)
        o.to_parquet(p.with_suffix(".tmp.parquet"), index=False)
        os.replace(p.with_suffix(".tmp.parquet"), p)
    return pd.read_parquet(p)


def cmd_origins(aggs: list[str], force: bool) -> None:
    for agg in aggs:
        if force and origins_path(agg).exists():
            origins_path(agg).unlink()
        o = origins(agg)
        log(f"{agg}: {len(o)} origins ({o['kind'].value_counts().to_dict()}); lattice {LATTICE_KM[agg]} km; "
            f"{len(lattice(agg))} destination cells")


# ------------------------------------------------------------------ routing
def net_copy(agg: str) -> Path:
    from pipeline.r5_env import network_dir
    src = network_dir(agg, "all")
    files = sorted(src.glob("*.transport_network"))
    if len(files) != 1:
        raise FileNotFoundError(f"expected one built network in {src}")
    f = files[0]
    dst = OUT / "r5" / agg
    dst.mkdir(parents=True, exist_ok=True)
    tgt = dst / f.name
    if not tgt.exists() or tgt.stat().st_size != f.stat().st_size:
        for old in dst.glob("*.transport_network"):
            old.unlink()
        shutil.copyfile(f, tgt.with_suffix(".tmp"))
        os.replace(tgt.with_suffix(".tmp"), tgt)
    return tgt


def load_network(agg: str):
    import com.conveyal.r5
    import java.io
    from r5py import TransportNetwork
    from r5py.util import GoodEnoughEquidistantCrs
    p = net_copy(agg)
    tn = TransportNetwork.__new__(TransportNetwork)
    tn._transport_network = com.conveyal.r5.kryo.KryoNetworkSerializer.read(java.io.File(str(p)))
    tn.EQUIDISTANT_CRS = GoodEnoughEquidistantCrs(tn.extent)
    return tn


def unit_sig(agg: str, scen: str) -> str:
    from pipeline import access as A
    from pipeline.r5_env import R5_VERSION
    net = sorted(p.name for p in (OUT / "r5" / agg).glob("*.transport_network")) if (OUT / "r5" / agg).exists() else []
    parts = {"code": CODE_VERSION, "scen": SCEN[scen][0], "params": A.unit_params(agg, "all", SCEN[scen][0]),
             "lattice": lattice_hash(agg), "net": net, "r5": R5_VERSION, "chunk": CHUNK}
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def unit_dir(agg: str, scen: str) -> Path:
    return OUT / agg / scen


def chunk_file(agg: str, scen: str, k: int) -> Path:
    return unit_dir(agg, scen) / f"chunk_{k:04d}.npz"


def chunk_ok(agg: str, scen: str, k: int, sig: str, ids: list[str]) -> bool:
    p = chunk_file(agg, scen, k)
    if not p.exists():
        return False
    try:
        z = np.load(p)
        return str(z["sig"]) == sig and list(z["ids"]) == ids
    except Exception:  # noqa: BLE001 - a broken file is redone
        return False


def wait_for_memory(min_gb: float = 14.0, every_s: int = 180) -> None:
    import psutil
    while True:
        free = psutil.virtual_memory().available / 2 ** 30
        if free >= min_gb:
            log(f"free memory {free:.1f} GB: starting")
            return
        log(f"free memory {free:.1f} GB < {min_gb} GB: waiting {every_s} s")
        time.sleep(every_s)


def route(aggs: list[str], threads: int, xmx: str) -> None:
    import geopandas as gpd
    from pipeline import access as A
    from pipeline.r5_env import start
    if threads > 4:
        raise SystemExit("at most 4 threads (shared machine)")
    wait_for_memory()
    sys.argv = sys.argv[:1]
    start(xmx=xmx, tmp=OUT / "_tmp")
    for agg in aggs:
        o = origins(agg)
        ids = o["id"].tolist()
        nck = int(np.ceil(len(o) / CHUNK))
        net_copy(agg)
        sigs = {s: unit_sig(agg, s) for s in SCEN}
        todo = {s: [k for k in range(nck) if not chunk_ok(agg, s, k, sigs[s], ids[k * CHUNK:(k + 1) * CHUNK])] for s in SCEN}
        if not any(todo.values()):
            log(f"{agg}: routing up to date ({len(o)} origins)")
            continue
        lt = lattice(agg)
        t0 = time.time()
        tn = load_network(agg)
        jnet = tn._transport_network
        dests = gpd.GeoDataFrame({"id": lt["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(lt["lon"], lt["lat"]),
                                 crs="EPSG:4326")
        log(f"{agg}: network loaded in {time.time() - t0:.0f} s; {len(o)} origins, {len(lt)} destination cells")
        tasks = {}
        # walk first: transit cells take min(transit, walk only)
        for scen in ["walk", "am", "evening"]:
            if not todo[scen]:
                continue
            if scen not in tasks:
                t1 = time.time()
                tasks[scen], info = A.make_task(tn, dests, SCEN[scen][0])
                unit_dir(agg, scen).mkdir(parents=True, exist_ok=True)
                (unit_dir(agg, scen) / "r5_params.json").write_text(json.dumps(info, indent=1, sort_keys=True))
                log(f"{agg} {scen}: task ready in {time.time() - t1:.0f} s")
            task = tasks[scen]
            for k in todo[scen]:
                sl = o.iloc[k * CHUNK:(k + 1) * CHUNK]
                lon, lat = sl["lon"].to_numpy(), sl["lat"].to_numpy()
                walk = None
                if scen != "walk":
                    walk = np.load(chunk_file(agg, "walk", k))

                def one(r):
                    tt = A.travel_times(task, jnet, lon[r], lat[r])
                    tt = np.where((tt >= 0) & (tt <= MAX_MIN), tt, UNREACHED).astype(np.int32)
                    if walk is not None:
                        ip = walk["indptr"]
                        ix, wt = walk["idx"][ip[r]:ip[r + 1]], walk["tt"][ip[r]:ip[r + 1]]
                        tt[ix] = np.minimum(tt[ix], wt.astype(np.int32))
                    sel = np.flatnonzero(tt <= MAX_MIN)
                    return sel.astype(np.int32), tt[sel].astype(np.uint8)

                t1 = time.time()
                with cf.ThreadPoolExecutor(max_workers=threads) as ex:
                    res = list(ex.map(one, range(len(sl))))
                lens = np.array([len(r[0]) for r in res], np.int64)
                import io
                buf = io.BytesIO()
                np.savez_compressed(buf, sig=np.array(sigs[scen]), ids=np.array(sl["id"].tolist()),
                                    indptr=np.r_[0, np.cumsum(lens)].astype(np.int64),
                                    idx=np.concatenate([r[0] for r in res]), tt=np.concatenate([r[1] for r in res]))
                atomic_bytes(chunk_file(agg, scen, k), buf.getvalue())
                wall = time.time() - t1
                log(f"{agg} {scen} chunk {k + 1}/{nck}: {len(sl)} origins in {wall:.1f} s "
                    f"({1000 * wall / max(len(sl), 1):.0f} ms/origin, {threads} threads)")
        del tn, jnet, tasks
        gc.collect()


def times(agg: str, scen: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """origin id -> (destination positions in lattice(agg), minutes) for cells reached within 60 min."""
    o = origins(agg)
    ids = o["id"].tolist()
    sig = unit_sig(agg, scen)
    out = {}
    for k in range(int(np.ceil(len(o) / CHUNK))):
        part = ids[k * CHUNK:(k + 1) * CHUNK]
        if not chunk_ok(agg, scen, k, sig, part):
            raise FileNotFoundError(f"{agg} {scen}: chunk {k} missing or stale; run route first")
        z = np.load(chunk_file(agg, scen, k))
        ip = z["indptr"]
        for r, oid in enumerate(part):
            out[oid] = (z["idx"][ip[r]:ip[r + 1]], z["tt"][ip[r]:ip[r + 1]])
    return out


# ------------------------------------------------------------------ polygons and encoding
def encode_polyline(coords: np.ndarray) -> str:
    """Google encoded polyline, precision 5; ``coords`` is (n, 2) of (lat, lon)."""
    v = np.round(np.asarray(coords, float) * 1e5).astype(np.int64)
    d = np.diff(np.vstack([[0, 0], v]), axis=0).ravel()
    out = []
    for x in d.tolist():
        x = ~(x << 1) if x < 0 else (x << 1)
        while x >= 0x20:
            out.append(chr((0x20 | (x & 0x1F)) + 63))
            x >>= 5
        out.append(chr(x + 63))
    return "".join(out)


def decode_polyline(s: str) -> np.ndarray:
    vals, i, n = [], 0, len(s)
    while i < n:
        shift = res = 0
        while True:
            b = ord(s[i]) - 63
            i += 1
            res |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        vals.append(~(res >> 1) if res & 1 else res >> 1)
    return np.cumsum(np.array(vals, np.int64).reshape(-1, 2), axis=0) / 1e5


class Raster:
    """Boolean raster over the lattice of one agglomeration (rows from the north)."""

    def __init__(self, lt: pd.DataFrame):
        from affine import Affine
        self.i0, self.j1 = int(lt["i"].min()), int(lt["j"].max())
        self.col = (lt["i"].to_numpy() - self.i0).astype(np.int64)
        self.row = (self.j1 - lt["j"].to_numpy()).astype(np.int64)
        self.shape = (int(self.row.max()) + 1, int(self.col.max()) + 1)
        self.transform = Affine(CELL, 0, self.i0 * CELL, 0, -CELL, (self.j1 + 1) * CELL)

    def polygons(self, pos: np.ndarray) -> list:
        import rasterio.features
        if not len(pos):
            return []
        g = np.zeros(self.shape, np.uint8)
        g[self.row[pos], self.col[pos]] = 1
        # crop to the occupied window to keep shapes() fast
        r0, r1 = self.row[pos].min(), self.row[pos].max() + 1
        c0, c1 = self.col[pos].min(), self.col[pos].max() + 1
        sub = g[r0:r1, c0:c1]
        tr = self.transform * self.transform.translation(c0, r0)
        out = []
        for geom, val in rasterio.features.shapes(sub, mask=sub.astype(bool), transform=tr, connectivity=4):
            out.append(shapely.geometry.shape(geom))
        return out


def encode_polys(polys: list) -> tuple[list, int]:
    """Simplify (EPSG:2180), transform, encode: [[outer, hole, ...], ...] sorted for determinism; vertex count."""
    enc, nv = [], 0
    for p in polys:
        p = shapely.simplify(p, SIMPLIFY_M, preserve_topology=True)
        if p.is_empty:
            continue
        parts = [p] if p.geom_type == "Polygon" else list(p.geoms)
        for q in parts:
            rings = []
            for ring in [q.exterior, *q.interiors]:
                xy = np.asarray(ring.coords)[:-1]        # closing vertex implied
                lon, lat = TO4326.transform(xy[:, 0], xy[:, 1])
                rings.append(encode_polyline(np.c_[lat, lon]))
                nv += len(xy)
            enc.append(rings)
    enc.sort(key=lambda r: (-len(r[0]), r[0]))
    return enc, nv


# ------------------------------------------------------------------ build
def build(aggs: list[str]) -> None:
    from pipeline.common import write_meta
    t_start = time.time()
    WEB.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    rows, sizes = [], {}
    for agg in aggs:
        t0 = time.time()
        o = origins(agg)
        lt = lattice(agg)
        pop = lt["pop"].to_numpy()
        ras = Raster(lt)
        tt = {s: times(agg, s) for s in SCEN}
        iso = {}
        for r in o.itertuples():
            rec = {}
            for s, (_, cuts) in SCEN.items():
                pos, mins = tt[s][r.id]
                cum, geoms = [], []
                for c in cuts:
                    sel = pos[mins <= c]
                    cum.append(int(round(pop[sel].sum())))
                    enc, nv = encode_polys(ras.polygons(sel))
                    geoms.append(enc)
                    rows.append({"agglomeration": agg, "origin": r.id, "kind": r.kind, "scenario": s, "minutes": c,
                                 "residents": cum[-1], "cells": int(len(sel)), "vertices": nv,
                                 "polygons": len(enc), "chars": sum(len(x) for p in enc for x in p)})
                band = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, len(cum))]
                rec[s] = {"residents": cum, "residents_band": band, "geom": geoms}
            iso[r.id] = rec
        index = [{"id": r.id, "kind": r.kind, "name": r.name, "lon": round(float(r.lon), 5), "lat": round(float(r.lat), 5)}
                 for r in o.itertuples()]
        doc = {
            "agglomeration": agg, "name": CFG["agglomerations"][agg]["name"], "code_version": CODE_VERSION,
            "day": CFG["reference_day"], "encoding": "polyline5 [lat, lon], rings: outer first, then holes",
            "polygons": "cumulative: do T min contains every shorter band",
            "residents": "NSP 2021 na wzorze GHSL 2020, komórki 250 m; residents = narastająco, residents_band = w paśmie",
            "scenarios": {
                "am": {"label": "komunikacja + pieszo, środa 7:00–9:00 (mediana)", "minutes": SCEN["am"][1]},
                "evening": {"label": "komunikacja + pieszo, środa 20:00–22:00 (mediana)", "minutes": SCEN["evening"][1]},
                "walk": {"label": "tylko pieszo (5 km/h)", "minutes": SCEN["walk"][1]}},
            "lattice_km": {"core": LATTICE_KM[agg][0], "rest": LATTICE_KM[agg][1]},
            "note": "Czas rozkładowy, nie rzeczywisty. Izochrona dotyczy najbliższego z wyliczonych punktów, nie miejsca kliknięcia.",
            "origins": index, "iso": iso,
        }
        data = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        atomic_bytes(WEB / f"{agg}.json", data + b"\n")
        sizes[agg] = len(data) + 1
        log(f"{agg}: {len(o)} origins, {sizes[agg] / 1e6:.2f} MB in {time.time() - t0:.0f} s")
    df = pd.DataFrame(rows)
    old = QA / "polygons.csv"
    if old.exists():
        prev = pd.read_csv(old)
        df = pd.concat([prev[~prev["agglomeration"].isin(aggs)], df], ignore_index=True)
    df = df.sort_values(["agglomeration", "origin", "scenario", "minutes"]).reset_index(drop=True)
    df.to_csv(old, index=False, lineterminator="\n")
    allsizes = {p.stem: p.stat().st_size for p in sorted(WEB.glob("*.json")) if not p.name.startswith("_")}
    write_meta(WEB, "isochrones", started=t_start,
               extra={"code_version": CODE_VERSION, "file_bytes": allsizes, "lattice_km": LATTICE_KM,
                      "day": CFG["reference_day"], "windows": {"am": "07:00-09:00", "evening": "20:00-22:00"},
                      "simplify_m": SIMPLIFY_M, "inputs_note": "R5 networks of data/interim/r5/<agg>/net_all (copied); "
                      "census-scaled 250 m grid; results/layers/transfer_nodes.parquet"})


# ------------------------------------------------------------------ QA
def _prod_cell(agg: str, scen: str, cell_id: str) -> dict | None:
    """Production per-origin sums (data/interim/access, read only) of one 250 m cell, or None."""
    d = AI.ACCESS_INT / agg / "all" / scen
    for f in sorted(d.glob("chunk_*.parquet")):
        t = pd.read_parquet(f, columns=["cell_id", "acc_census_15", "acc_census_30", "acc_census_45", "acc_census_60"])
        r = t[t["cell_id"] == cell_id]
        if len(r):
            return r.iloc[0].to_dict()
    return None


def _published_tp(agg: str, domain: str, metric: str) -> float | None:
    m = pd.read_csv(RESULTS / "metrics" / "metrics.csv")
    r = m[(m["agglomeration"] == agg) & (m["domain"] == domain) & (m["metric"] == metric)
          & (m["feed_variant"] == "all") & (m["population_grid"] == "ghsl_census_scaled")]
    return float(r["value"].iloc[0]) if len(r) else None


def _runtimes() -> dict:
    """Routing wall seconds per agglomeration and scenario from run.log (sum of chunk times; last run wins)."""
    import re
    out: dict = {}
    if not (OUT / "run.log").exists():
        return out
    for line in (OUT / "run.log").read_text(encoding="utf-8").splitlines():
        s = re.search(r" (\w+): network loaded", line)
        if s:                                   # a new routing run of this agglomeration replaces the earlier one
            out[s.group(1)] = {}
            continue
        m = re.search(r" (\w+) (walk|am|evening) chunk (\d+)/(\d+): (\d+) origins in ([\d.]+) s", line)
        if m:
            agg, scen, k = m.group(1), m.group(2), int(m.group(3))
            out.setdefault(agg, {}).setdefault(scen, {})[k] = float(m.group(6))
    return {a: {s: round(sum(v.values()), 1) for s, v in d.items()} for a, d in out.items()}


def pl(x, d: int = 1) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "brak"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def qa(aggs: list[str]) -> None:
    QA.mkdir(parents=True, exist_ok=True)
    poly = pd.read_csv(QA / "polygons.csv")
    rt = _runtimes()
    checks, counts = [], []
    for agg in aggs:
        f = WEB / f"{agg}.json"
        doc = json.loads(f.read_text(encoding="utf-8"))
        o = origins(agg)
        counts.append({"agg": agg, "n": len(o), **{k: int((o["kind"] == k).sum()) for k in KIND_ORDER},
                       "lattice": LATTICE_KM[agg], "bytes": f.stat().st_size, "dest": len(lattice(agg)),
                       "route_s": sum(rt.get(agg, {}).values()) if rt.get(agg) else None})
        # internal consistency over all origins
        bad_mono = bad_walk = 0
        for oid, rec in doc["iso"].items():
            for s in SCEN:
                r = rec[s]["residents"]
                bad_mono += any(b < a for a, b in zip(r, r[1:]))
            bad_walk += any(rec["am"]["residents"][i] < rec["walk"]["residents"][i] for i in range(2))
        checks.append({"agg": agg, "check": "liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty)",
                       "ok": bad_mono == 0, "detail": f"{bad_mono} naruszeń"})
        checks.append({"agg": agg, "check": "komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano)",
                       "ok": bad_walk == 0, "detail": f"{bad_walk} naruszeń"})
        # hub (and the main centre) against the published phase-3 results
        lt = lattice(agg)
        dest = AI.destinations(agg)
        for oid in ["hub", "centre"]:
            if oid not in doc["iso"]:
                continue
            row = o[o["id"] == oid].iloc[0]
            cell = f"E{int(np.floor(row.x / CELL) * 250)}N{int(np.floor(row.y / CELL) * 250)}"
            rec = doc["iso"][oid]
            prod = _prod_cell(agg, "pt_am", cell)
            prod_ev = _prod_cell(agg, "pt_evening", cell)
            for i, c in enumerate([15, 30, 45, 60]):
                ours = rec["am"]["residents"][i]
                ref = prod.get(f"acc_census_{c}") if prod else None
                checks.append({"agg": agg, "check": f"{oid}: osiągalni rano do {c} min vs wynik produkcyjny komórki {cell}",
                               "ours": ours, "ref": ref, "ratio": (ours / ref if ref else None),
                               "ok": None, "detail": "inny punkt startu niż środek komórki"})
                if c in (30, 45):
                    ref_e = prod_ev.get(f"acc_census_{c}") if prod_ev else None
                    ours_e = rec["evening"]["residents"][i]
                    checks.append({"agg": agg, "check": f"{oid}: osiągalni wieczorem do {c} min vs wynik produkcyjny komórki {cell}",
                                   "ours": ours_e, "ref": ref_e, "ratio": (ours_e / ref_e if ref_e else None),
                                   "ok": None, "detail": "inny punkt startu niż środek komórki"})
            dom = "hub_1km" if oid == "hub" else "centre_1km"
            for c, r_m in [(30, 7500.0), (45, 11250.0)]:
                prox = float(dest.loc[np.hypot(dest["x"] - row.x, dest["y"] - row.y) <= r_m, "w_census"].sum())
                tp = 100 * rec["am"]["residents"][[15, 30, 45, 60].index(c)] / prox if prox else None
                pub = _published_tp(agg, dom, f"tp_pt_am_{c}min")
                if pub is None and oid == "hub":
                    pub = _published_tp(agg, "centre_1km", f"tp_pt_am_{c}min")
                checks.append({"agg": agg, "check": f"{oid}: transport performance {c} min z punktu vs opublikowana średnia komórek ≤ 1 km ({dom})",
                               "ours": tp, "ref": pub, "ratio": (tp / pub if tp and pub else None),
                               "ok": None, "detail": "inna wielkość: jeden punkt wobec średniej ok. 50 komórek"})
        # grid origins start at a cell centre, exactly as production: the sums must agree
        prod = {s: pd.concat([pd.read_parquet(f, columns=["cell_id"] + [f"acc_census_{c}" for c in (15, 30, 45, 60)])
                              for f in sorted((AI.ACCESS_INT / agg / "all" / s).glob("chunk_*.parquet"))]).set_index("cell_id")
                for s in ("pt_am", "pt_evening")}
        g = o[o["kind"] == "grid"]
        gcell = {f"E{int(np.floor(r.x / CELL) * 250)}N{int(np.floor(r.y / CELL) * 250)}": r.id for r in g.itertuples()}
        for s, ps in (("am", "pt_am"), ("evening", "pt_evening")):
            common = [c for c in gcell if c in prod[ps].index]
            rel = []
            for c in common:
                ours = np.asarray(doc["iso"][gcell[c]][s]["residents"], float)
                ref = prod[ps].loc[c, [f"acc_census_{m}" for m in (15, 30, 45, 60)]].to_numpy(float)
                ok = ref > 0
                rel += list(np.abs(ours[ok] / ref[ok] - 1))
            rel = np.asarray(rel)
            checks.append({"agg": agg, "check": f"punkty siatki ({s}): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki",
                           "ours": float(np.percentile(rel, 95) * 100) if len(rel) else None,
                           "ref": float(rel.max() * 100) if len(rel) else None, "ratio": None,
                           "ok": bool(len(rel) and rel.max() <= 0.02),
                           "detail": f"{len(common)} punktów; kolumny: 95. centyl i maksimum różnicy względnej w %"})
        # walk 30 min never beyond 2.5 km in a straight line from the origin (+ one cell)
        far = 0
        tw = times(agg, "walk")
        for r in o.itertuples():
            pos, mins = tw[r.id]
            sel = pos[mins <= 30]
            if len(sel):
                dmax = np.hypot(lt["x"].to_numpy()[sel] - r.x, lt["y"].to_numpy()[sel] - r.y).max()
                far += dmax > 2500 + 1.5 * CELL + 1600   # R5 links a cell to the street up to 1.6 km away
        checks.append({"agg": agg, "check": "pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy)",
                       "ok": far == 0, "detail": f"{far} punktów z komórką dalej"})
        picture(agg, doc)
    cdf = pd.DataFrame(checks)
    cdf.to_csv(QA / "checks.csv", index=False, lineterminator="\n")
    pd.DataFrame(counts).to_csv(QA / "origins.csv", index=False, lineterminator="\n")
    write_note(pd.DataFrame(counts), cdf, poly)


def picture(agg: str, doc: dict) -> None:
    """QA picture: the hub's morning bands and walk lines decoded from the web file, with all origins."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon
    colors = {15: "#3FC1B0", 30: "#6CCFC1", 45: "#9BDDD3", 60: "#C9EEE8"}
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5), facecolor="#1c1f26")
    hub = next(o for o in doc["origins"] if o["kind"] == "hub")
    for ax, scen in zip(axes, ["am", "evening"]):
        ax.set_facecolor("#1c1f26")
        rec = doc["iso"][hub["id"]]
        for mins, enc in reversed(list(zip(doc["scenarios"][scen]["minutes"], rec[scen]["geom"]))):
            for poly in enc:
                for k, ring in enumerate(poly):
                    xy = decode_polyline(ring)[:, ::-1]
                    ax.add_patch(MplPolygon(xy, closed=True, facecolor="#1c1f26" if k else colors[mins],
                                            alpha=1 if k else 0.55, edgecolor=colors[mins], lw=0.4))
        for enc in rec["walk"]["geom"]:
            for poly in enc:
                xy = decode_polyline(poly[0])[:, ::-1]
                ax.plot(np.r_[xy[:, 0], xy[:1, 0]], np.r_[xy[:, 1], xy[:1, 1]], color="#F1E7C9", lw=0.8, ls="--")
        ox = [o["lon"] for o in doc["origins"]]
        oy = [o["lat"] for o in doc["origins"]]
        ax.scatter(ox, oy, s=2, color="#8A909C")
        ax.scatter([hub["lon"]], [hub["lat"]], s=30, color="white")
        ax.set_aspect(1 / np.cos(np.radians(hub["lat"])))
        ax.autoscale_view()
        ax.set_title(f"{doc['name']}: {hub['name']}, {doc['scenarios'][scen]['label']}; "
                     + ", ".join(f"do {m}: {r:,}".replace(",", " ") for m, r in zip(doc["scenarios"][scen]["minutes"], rec[scen]["residents"])),
                     color="#e6e8ee", fontsize=8)
        ax.tick_params(colors="#8A909C", labelsize=6)
    fig.tight_layout()
    fig.savefig(QA / f"hub_{agg}.png", dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def write_note(counts: pd.DataFrame, checks: pd.DataFrame, poly: pd.DataFrame) -> None:
    names = {a: CFG["agglomerations"][a]["name"] for a in AGGS}
    L = ["# Izochrony z wyliczonych punktów („skąd dojadę”)", "",
         f"Kod: `pipeline/isochrones.py` ({CODE_VERSION}); pliki dla strony: `results/web/isochrones/<aglomeracja>.json`; "
         "tabele: `results/qa/isochrones/origins.csv`, `checks.csv`, `polygons.csv`; obrazy kontrolne `hub_<aglomeracja>.png` "
         "(pasma z węzła odczytane z pliku strony, linia przerywana: pieszo, szare kropki: wszystkie punkty startu).", "",
         "## Metoda", "",
         "- **Punkty startu.** Centrum i węzeł z `config.yaml` (w GZM i Trójmieście także wszystkie centra dodatkowe), "
         f"{N_STOPS} zespołów przystanków o największej liczbie odjazdów na godzinę w ciągu doby (warstwa łatwości przesiadki, "
         f"z pominięciem leżących bliżej niż {STOP_MIN_GAP_M:.0f} m od centrum lub węzła) oraz regularna siatka: bloki 1 km "
         "w zamieszkanej części rdzenia miasta i 2 km na pozostałym obszarze FUA pokrytym danymi GTFS (blok liczy się, gdy "
         f"mieszka w nim co najmniej {BLOCK_MIN_POP:.0f} osób; punkt to środek najludniejszej komórki 250 m bloku). Tam, gdzie "
         "plik przekroczyłby ok. 4 MB, siatkę rozrzedzono (tabela niżej).",
         "- **Czasy.** R5 v7.5.1 z parametrami wyniku głównego (`pipeline.access.make_task`): komunikacja + pieszo, środa "
         f"{CFG['reference_day']}, mediana z odjazdów co minutę w oknie 7:00–9:00 (rano) i 20:00–22:00 (wieczorem), pieszo 5 km/h, "
         "dojście i odejście do 12 min, wszystkie feedy; w każdej komórce min(komunikacja, sam spacer), jak w wyniku głównym. "
         "Cele: wszystkie komórki 250 m obszaru FUA + 15 km z centrum w Polsce (oraz każda zamieszkana komórka, także nadmorska), również niezamieszkane (żeby izochrona nie miała dziur w parkach).",
         f"- **Wielokąty.** Komórki z czasem ≤ 15, 30, 45, 60 min (pieszo ≤ 15, 30) połączone w wielokąty, uproszczone "
         f"o {SIMPLIFY_M:.0f} m, współrzędne do 5 miejsc po przecinku (zapis „encoded polyline”). Pasma są narastające.",
         "- **Mieszkańcy.** Siatka NSP 2021 na wzorze GHSL 2020 (250 m); podawane narastająco i w samym paśmie.", "",
         "## Punkty, rozmiary, czas liczenia", "",
         "| Aglomeracja | Punktów | węzeł / centra / przystanki / siatka | Siatka (rdzeń / reszta), km | Komórek celu | Plik, MB | Routing, s (4 wątki) |",
         "|---|---:|---|---|---:|---:|---:|"]
    for r in counts.itertuples():
        L.append(f"| {names[r.agg]} | {r.n} | {r.hub} / {r.centre} / {r.stop_area} / {r.grid} | {r.lattice[0]} / {r.lattice[1]} | "
                 f"{pl(r.dest, 0)} | {pl(r.bytes / 1e6, 2)} | {pl(r.route_s, 0) if r.route_s else 'brak'} |")
    v = poly.groupby(["scenario", "minutes"])["vertices"].agg(["mean", "max"])
    L += ["", "Wierzchołki na wielokąt pasma (wszystkie miasta): " + "; ".join(
        f"{s} {m} min: średnio {pl(r['mean'], 0)}, najwięcej {pl(r['max'], 0)}" for (s, m), r in v.iterrows()) + ".", "",
          "## Kontrole", "",
          "Porównanie z wynikiem fazy 3: liczba osiągalnych mieszkańców z punktu węzła (i centrum) i z komórki 250 m, w której "
          "ten punkt leży, w produkcyjnym przebiegu (start ze środka komórki, ten sam silnik i parametry, cele tylko w komórkach "
          "zamieszkanych). To porównanie jest informacyjne: punkt węzła leży do ok. 175 m od środka komórki i R5 dowiązuje go "
          "do innego odcinka ulicy, co przy 15 i 30 min potrafi zmienić wynik o kilkadziesiąt procent. Ścisłą kontrolą są punkty siatki, "
          "które startują dokładnie ze środka komórki, tak jak przebieg produkcyjny (wiersze „punkty siatki”). Transport performance z punktu porównano z opublikowaną średnią komórek ≤ 1 km od "
          "punktu (`metrics.csv`, domena hub_1km / centre_1km), także informacyjnie: to nie ta sama wielkość (średnia po ok. 50 komórkach).", "",
          "| Aglomeracja | Kontrola | Nasze | Odniesienie | Stosunek | Wynik |", "|---|---|---:|---:|---:|---|"]
    for r in checks.itertuples():
        ours = getattr(r, "ours", None)
        ref = getattr(r, "ref", None)
        ratio = getattr(r, "ratio", None)
        okv = r.ok
        if okv is None or (isinstance(okv, float) and np.isnan(okv)):
            res = "informacyjnie" if ref is not None and ref == ref else "brak odniesienia"
        else:
            res = "zgodne" if okv else "NIEZGODNE"
        det = f" ({r.detail})" if isinstance(r.detail, str) and r.detail else ""
        L.append(f"| {names[r.agg]} | {r.check}{det} | {pl(ours, 1) if ours == ours and ours is not None else ''} | "
                 f"{pl(ref, 1) if ref == ref and ref is not None else ''} | {pl(ratio, 2) if ratio == ratio and ratio is not None else ''} | {res} |")
    nbad = int((checks["ok"] == False).sum())  # noqa: E712
    L += ["", f"Niezgodnych kontroli: {nbad} z {int(checks['ok'].notna().sum())} rozstrzygniętych.", "",
          "## Ograniczenia", "",
          "- Strona pokazuje izochronę **najbliższego wyliczonego punktu**, a nie klikniętego miejsca; karta podaje nazwę punktu "
          "i odległość od kliknięcia. Między punktami siatki (1–4 km) czas dojścia do przystanku może się wyraźnie różnić.",
          "- Czasy rozkładowe (jeden dzień, środa), nie rzeczywiste: bez opóźnień i korków (RAPORT §16.2).",
          "- Mediana z odjazdów co minutę: połowa odjazdów w oknie daje czas dłuższy niż pokazany.",
          "- Komórki poza maską pokrycia GTFS są celami jak każde inne: brak kursów w danych wygląda tam jak brak zasięgu.",
          "- Komórka liczy się w całości, gdy osiągnięto jej środek; granica wielokąta ma dokładność ok. 250 m (plus uproszczenie 50 m).",
          "- Mieszkańcy z lat 2020–2021, rozkłady z 2026 r.", "",
          "## Nie zweryfikowano", "",
          "- Wyglądu na mapie (warstwy nie są jeszcze podłączone do strony) ani czasu wczytania plików na telefonie.",
          "- Izochron z pojedynczych punktów nie porównano z wyszukiwarką połączeń (poza kontrolą fazy 3 dla par start–cel).",
          "- Przyczyny różnic między punktem węzła lub centrum a środkiem jego komórki 250 m (tabela kontroli, wiersze "
          "informacyjne) nie badano; najpewniej R5 dowiązuje oba punkty do różnych odcinków ulic. Dotyczy to też każdego "
          "zespołu przystanków: jego punkt to środek zespołu, a nie konkretny peron.",
          ""]
    (QA / "isochrones.md").write_text("\n".join(L), encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["origins", "route", "build", "qa"])
    ap.add_argument("--agg", nargs="+", default=AGGS, choices=AGGS)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--xmx", default="8G")
    ap.add_argument("--force", action="store_true", help="origins: rebuild the origin index")
    a, _ = ap.parse_known_args()
    if a.cmd == "origins":
        cmd_origins(a.agg, a.force)
    elif a.cmd == "route":
        route(a.agg, a.threads, a.xmx)
    elif a.cmd == "build":
        build(a.agg)
    else:
        qa(a.agg)


if __name__ == "__main__":
    main()
