"""Transport performance on the urban-centre domain for all seven agglomerations (brief §4.6, comparison on the
same kind of area).

    python -m pipeline.access_uc prep                    # urban centres per agglomeration (no JVM)
    python -m pipeline.access_uc route [--agg ...] [--scen pt_am bike_lts3 bike_lts4] [--threads 6] [--xmx 8G]
    python -m pipeline.access_uc aggregate               # metrics_access_uc.* + results/qa/access_uc/

Domain ("urban_centre")
* Eurostat GISCO high-density clusters 2021 (HDENS_CLST_2021, 1 km, EPSG:3035, built on the 2021 census grid;
  cell value = cluster population).  Clusters = 4-connected components of populated cells.  An agglomeration's
  domain is the union of all clusters with more than half of their 1 km cells (cell centres) inside its FUA.
  Several centres (Warszawa, Łódź, Trójmiasto, GZM) are pooled into one domain; DG REGIO instead treats every
  urban centre as a city of its own.
* A 250 m cell belongs to the domain when its centre lies in a 1 km cell of the domain and in the FUA (production
  origins are FUA cells; the part of a cluster outside the FUA, if any, is reported, not used).
* Origins, destinations and the proximity denominator are all restricted to the domain.

Method = production phase 3 (pipeline.access), only the domain differs: R5 v7.5.1, transit + walk, departures
every minute Wednesday 07:00-09:00, median, 60 min, walk 5 km/h, access / egress <= 12 min (1 km), rule
min(transit, walk-only) per pair before the cutoffs; walk 5 km/h; bike 15 km/h at LTS <= 3 and <= 4; all feeds;
census-scaled 250 m grid (raw GHSL alongside).  Walk-only times come from the production walk caches (no new
routing); transit and bike are routed here on copies of the production network files (data/interim/access_uc/r5/).
City value: population-weighted mean of cell ratios (headline) and ratio of weighted means (table).
Production files under data/interim/access/ are read only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gc
import hashlib
import json
import shutil
import time
import warnings
from functools import lru_cache
from pathlib import Path

warnings.filterwarnings("ignore", message="The provided departure time window is below 5 minutes")

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline import access_inputs as AI
from pipeline.common import INTERIM, RAW, RESULTS, load_config

CFG = load_config()
REF_DAY = CFG["reference_day"]
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
UC_TIF = RAW / "eurostat_hdens_2021" / "extracted" / "HDENS_CLST_2021.tif"
UC_LABEL = "Eurostat GISCO HDENS_CLST_2021 (siatka spisowa 2021)"
OUT = INTERIM / "access_uc"
QA = RESULTS / "qa" / "access_uc"
METRICS = RESULTS / "metrics"
TO3035 = Transformer.from_crs("EPSG:2180", "EPSG:3035", always_xy=True)
CODE_VERSION = "access_uc-2026-11-24.1"
MAX_MIN = 60
NODATA = np.iinfo(np.int64).max
CUTS = AI.CUTOFFS
# routed scenarios (dgregio scenario id used to build the R5 task: identical production parameters)
SCENARIOS = {"pt_am": "pt_base", "bike_lts3": "bike_lts3", "bike_lts4": "bike_lts4"}
RADII = {"walk30": 2500.0, "fast30": 7500.0, "fast45": 11250.0}


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ urban centres
@lru_cache(maxsize=1)
def _raster():
    import rasterio
    from scipy import ndimage
    r = rasterio.open(UC_TIF)
    a = r.read(1)
    lab, _ = ndimage.label(a > 0)            # 4-connectivity, as the degree-of-urbanisation clusters
    return a, lab, r.transform


@lru_cache(maxsize=None)
def clusters(agg: str) -> pd.DataFrame:
    """All clusters touching the FUA: id, official population, 1 km cells, cells inside the FUA, LAU names,
    included (> half of the cells inside the FUA)."""
    import geopandas as gpd
    import rasterio.features
    import rasterio.transform as rt
    import shapely
    from pipeline.boundaries import load_agglomeration, load_lau
    a, lab, tr = _raster()
    fua = shapely.transform(load_agglomeration(agg)["fua"], lambda xy: np.c_[TO3035.transform(xy[:, 0], xy[:, 1])])
    m = rasterio.features.geometry_mask([fua], a.shape, tr, invert=True, all_touched=False)
    ids = np.unique(lab[m & (a > 0)])
    lau = load_lau().to_crs(3035)[["LAU_NAME", "geometry"]]
    rows = []
    for i in ids[ids > 0]:
        rr, cc = np.nonzero(lab == i)
        xs, ys = rt.xy(tr, rr, cc)
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xs, ys), crs=3035)
        inside = shapely.contains_xy(fua, np.asarray(xs), np.asarray(ys))
        j = gpd.sjoin(pts, lau, predicate="within")
        names = j["LAU_NAME"].value_counts()
        rows.append({"agglomeration": agg, "cluster": int(i), "population_2021_official": int(a[rr[0], cc[0]]),
                     "cells_1km": len(rr), "cells_1km_in_fua": int(inside.sum()),
                     "main_lau": names.index[0], "lau_cells": "; ".join(f"{k} {v}" for k, v in names.items()),
                     "included": bool(inside.sum() * 2 > len(rr))})
    return pd.DataFrame(rows).sort_values("population_2021_official", ascending=False).reset_index(drop=True)


def in_uc(agg: str, x2180, y2180) -> np.ndarray:
    import rasterio.transform as rt
    a, lab, tr = _raster()
    inc = set(clusters(agg).query("included")["cluster"])
    x, y = TO3035.transform(np.asarray(x2180, float), np.asarray(y2180, float))
    r, c = rt.rowcol(tr, x, y)
    r, c = np.asarray(r), np.asarray(c)
    ok = (r >= 0) & (r < lab.shape[0]) & (c >= 0) & (c < lab.shape[1])
    v = np.zeros(len(x), np.int64)
    v[ok] = lab[r[ok], c[ok]]
    return np.isin(v, list(inc))


@lru_cache(maxsize=None)
def frame(agg: str) -> pd.DataFrame:
    """Production destination frame + in_uc (urban centre and FUA) + production origin index."""
    d = AI.destinations(agg).copy()
    d["in_uc_any"] = in_uc(agg, d["x"].to_numpy(), d["y"].to_numpy())
    d["in_uc"] = d["in_uc_any"] & d["in_fua"]
    o = AI.origins(agg)
    pos = pd.Series(np.arange(len(o)), index=o["cell_id"].to_numpy())
    d["origin_idx"] = d["cell_id"].map(pos).fillna(-1).astype(np.int64).to_numpy()
    return d


@lru_cache(maxsize=None)
def uc_cells(agg: str) -> pd.DataFrame:
    """Populated domain cells (origins = destinations), with lon/lat and the production origin index."""
    d = frame(agg)
    u = d[d["in_uc"] & d["populated"]].copy()
    assert (u["origin_idx"] >= 0).all()
    u["lon"], u["lat"] = AI.TO4326.transform(u["x"].to_numpy(), u["y"].to_numpy())
    return u.reset_index().rename(columns={"index": "dest_idx"})


def uc_hash(agg: str) -> str:
    u = uc_cells(agg)
    return AI.frame_hash(u, ["cell_id", "w_census", "w_raw"])


# ------------------------------------------------------------------ walk-only times (production cache)
def walk_times(agg: str) -> dict:
    """Per domain origin row: (positions of domain destinations, walk minutes <= 60) from the production cache."""
    from pipeline.access import CHUNK, unit_dir
    d = frame(agg)
    u = uc_cells(agg)
    pos = np.full(len(d), -1, np.int64)
    pos[u["dest_idx"].to_numpy()] = np.arange(len(u))
    oi = u["origin_idx"].to_numpy()
    out = {}
    for k in np.unique(oi // CHUNK):
        z = np.load(unit_dir(agg, "street", "walk") / f"chunk_{k:05d}.walk.npz")
        ip, ix, tt = z["indptr"], z["idx"], z["tt"]
        for r in np.flatnonzero(oi // CHUNK == k):
            i = oi[r] - k * CHUNK
            sl = slice(ip[i], ip[i + 1])
            p = pos[ix[sl]]
            m = p >= 0
            out[r] = (p[m], tt[sl][m].astype(np.int64))
    return out


def sums(tt: np.ndarray, W: np.ndarray) -> dict:
    row = {}
    for c in CUTS:
        m = tt <= c
        row[f"acc_census_{c}"] = float(W[m, 0].sum())
        row[f"acc_raw_{c}"] = float(W[m, 1].sum())
    return row


def walk_unit(agg: str) -> pd.DataFrame:
    u = uc_cells(agg)
    W = np.c_[u["w_census"].to_numpy(), u["w_raw"].to_numpy()]
    wt = walk_times(agg)
    rows = []
    for r in range(len(u)):
        tt = np.full(len(u), NODATA, np.int64)
        p, t = wt[r]
        tt[p] = t
        rows.append(sums(tt, W))
    df = pd.DataFrame(rows)
    df.insert(0, "cell_id", u["cell_id"].to_numpy())
    return df


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
        tgt.with_suffix(".tmp").replace(tgt)
    (dst / "source.json").write_text(json.dumps({"copied_from": f.name, "bytes": f.stat().st_size,
                                                 "inputs_sig": (src / "inputs.sig").read_text().strip() if (src / "inputs.sig").exists() else None},
                                                indent=1), encoding="utf-8")
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
    net = json.loads((OUT / "r5" / agg / "source.json").read_text(encoding="utf-8"))["copied_from"] if (OUT / "r5" / agg / "source.json").exists() else ""
    from pipeline import access_dgregio as Dg
    parts = {"code": CODE_VERSION, "uc": uc_hash(agg), "net": net, "scen": scen, "task": Dg.SCENARIOS[SCENARIOS[scen]],
             "day": REF_DAY, "walk_unit": json.loads((AI.ACCESS_INT / agg / "street" / "walk" / "manifest.json").read_text(encoding="utf-8"))["signature"]}
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def unit_path(agg: str, scen: str) -> Path:
    return OUT / agg / f"{scen}.parquet"


def unit_done(agg: str, scen: str) -> bool:
    p = unit_path(agg, scen)
    s = p.with_suffix(".sig")
    return p.exists() and s.exists() and s.read_text() == unit_sig(agg, scen)


def route(aggs: list[str], scens: list[str], threads: int) -> None:
    import geopandas as gpd
    from pipeline import access_dgregio as Dg
    for agg in aggs:
        todo = [s for s in scens if not (net_copy(agg) and unit_done(agg, s))]
        if not todo:
            log(f"{agg}: {scens} up to date")
            continue
        u = uc_cells(agg)
        W = np.c_[u["w_census"].to_numpy(), u["w_raw"].to_numpy()]
        t0 = time.time()
        tn = load_network(agg)
        jnet = tn._transport_network
        dg = gpd.GeoDataFrame({"id": u["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(u["lon"], u["lat"]), crs="EPSG:4326")
        wt = walk_times(agg) if "pt_am" in todo else None
        log(f"{agg}: network loaded in {time.time() - t0:.0f} s; {len(u)} urban-centre cells")
        nd = len(u)
        lon, lat = u["lon"].to_numpy(), u["lat"].to_numpy()
        for scen in todo:
            task = Dg.make_tasks(tn, dg, SCENARIOS[scen])[0]
            transit = scen == "pt_am"

            def one(r):
                tt = Dg._tt(task, jnet, lon[r], lat[r])
                if transit:
                    p, t = wt[r]
                    walk = np.full(nd, NODATA, np.int64)
                    walk[p] = t
                    tt = np.minimum(tt, walk)          # transit + walk never worse than walking
                return sums(tt, W)

            t1 = time.time()
            with cf.ThreadPoolExecutor(max_workers=threads) as ex:
                rows = list(ex.map(one, range(nd)))
            df = pd.DataFrame(rows)
            df.insert(0, "cell_id", u["cell_id"].to_numpy())
            p = unit_path(agg, scen)
            p.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(p.with_suffix(".tmp.parquet"), index=False)
            p.with_suffix(".tmp.parquet").replace(p)
            p.with_suffix(".sig").write_text(unit_sig(agg, scen))
            wall = time.time() - t1
            log(f"{agg} {scen}: {nd} origins in {wall:.0f} s ({1000 * wall / max(nd, 1):.0f} ms/origin, {threads} threads)")
        del tn, jnet
        gc.collect()


def prep(aggs: list[str]) -> None:
    QA.mkdir(parents=True, exist_ok=True)
    rows = []
    for agg in aggs:
        c = clusters(agg)
        rows.append(c)
        u = uc_cells(agg)
        log(f"{agg}: {int(c.included.sum())} urban centre(s), {len(u)} populated 250 m cells, "
            f"pop {u.w_census.sum():,.0f}")
    pd.concat(rows).to_csv(QA / "urban_centres.csv", index=False, lineterminator="\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "route", "aggregate"])
    ap.add_argument("--agg", nargs="*", default=AGGS)
    ap.add_argument("--scen", nargs="*", default=list(SCENARIOS))
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--xmx", default="8G")
    a = ap.parse_args()
    if a.cmd == "prep":
        prep(a.agg)
    elif a.cmd == "route":
        if a.threads > 6:
            raise SystemExit("at most 6 threads while the production run is in progress")
        from pipeline.r5_env import start
        start(xmx=a.xmx, tmp=OUT / "_tmp")
        route(a.agg, a.scen, a.threads)
    else:
        from pipeline import access_uc_aggregate
        access_uc_aggregate.main(a.agg)


if __name__ == "__main__":
    main()
