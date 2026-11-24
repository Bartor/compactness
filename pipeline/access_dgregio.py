"""Side step: reproduce the DG REGIO transport-performance benchmark (Poelman, Dijkstra, Ackermans 2020, WP 01/2020)
for Warszawa, Poznań and Łódź and decompose the difference to our phase-3 results.

    python -m pipeline.access_dgregio prep                 # urban centres, supply check, existing-chunk analyses
    python -m pipeline.access_dgregio route --scen pt_base [--agg poznan] [--threads 6] [--xmx 8G] [--limit N]
    python -m pipeline.access_dgregio report               # results/qa/access/dgregio/

What DG REGIO did (WP 01/2020, pp. 16, 34-43; data annex tables 1-2):
* domain: the 2011 urban centre (GEOSTAT 2011 1 km high-density cluster).  Origins AND destinations are populated
  Urban Atlas 2012 polygons inside it (p. 37); the proximity (denominator) is "constrained by the limits of the
  urban centre" (p. 42).  The cluster raster is Eurostat GISCO HDENS_CLST_2011 (cell value = cluster population);
  the annex areas and populations (Poznań 117 km2 / 532 166, Łódź 117 / 682 389, Warszawa 309 / 1 722 513) are
  matched exactly by the raster clusters, so this is the domain they used.
* travel time: OTP 1.2.0, maxWalkDistance 5000 m, maxTimeSec 3600; 9 requested departures every 15 min in a
  two-hour morning peak, mean of the 9 total travel times (including initial wait), pair counted if mean <= cutoff.
* city value: population-weighted mean accessibility / population-weighted mean proximity x 100 (the annex
  performance equals accessibility / proximity of its own columns, i.e. a ratio of means).

This module never writes under data/interim/access/ and never changes the production inputs.  It reads the
production per-origin chunks and walk caches read-only, and routes with its own copy of the R5 network files.
Outputs: data/interim/access_dgregio/ (routing results, copies of networks), results/qa/access/dgregio/.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import shutil
import sys
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
UC_TIF = RAW / "eurostat_hdens_2011" / "extracted" / "HDENS_CLST_2011.tif"
ANNEX = RAW / "dgregio_wp2020" / "wp_low_carbon_urban_accessibility_data_annex.xlsx"
OUT = INTERIM / "access_dgregio"
QA = RESULTS / "qa" / "access" / "dgregio"
CITIES = {"warszawa": ("GEOSTAT11_171", "Warszawa"), "poznan": ("GEOSTAT11_178", "Poznań"),
          "lodz": ("GEOSTAT11_229", "Łódź")}
TO3035 = Transformer.from_crs("EPSG:2180", "EPSG:3035", always_xy=True)
WALK_KMH, BIKE_KMH, MAX_MIN = 5.0, 15.0, 60
NODATA = np.iinfo(np.int32).max
CODE_VERSION = "dgregio-2026-11-24.1"

# scenario -> parameters.  access_min: R5 maxWalkTime per access / egress leg (12 min = 1 km as in production,
# 60 min = 5 km at 5 km/h = OTP maxWalkDistance 5000 m).  deps: None = every minute 7:00-9:00, median (production);
# list = single-minute departures, mean over them (DG REGIO: 9 departures every 15 min).
DEPS9 = [(7, 0), (7, 15), (7, 30), (7, 45), (8, 0), (8, 15), (8, 30), (8, 45), (9, 0)]
SCENARIOS = {
    "pt_base": {"kind": "transit", "access_min": 12, "deps": None},
    "pt_walk5km": {"kind": "transit", "access_min": 60, "deps": None},
    "pt_base_9dep": {"kind": "transit", "access_min": 12, "deps": DEPS9},
    "pt_walk5km_9dep": {"kind": "transit", "access_min": 60, "deps": DEPS9},
    # what-if: slower walking legs (4 km/h, 5 km kept as access limit = 75 min); tests whether the DG REGIO values
    # are consistent with systematically longer walking times (their walk-only results imply ~1.2-1.3x ours)
    "pt_walk5km_slow4": {"kind": "transit", "access_min": 75, "deps": None, "walk_kmh": 4.0},
    "bike_lts3": {"kind": "bike", "lts": 3},
    "bike_lts4": {"kind": "bike", "lts": 4},
}
CUTS = AI.CUTOFFS


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ DG REGIO annex and urban centres
@lru_cache(maxsize=None)
def annex() -> pd.DataFrame:
    """Annex tables 1 and 2 for the three cities (one row per agglomeration id)."""
    import openpyxl
    wb = openpyxl.load_workbook(ANNEX, read_only=True, data_only=True)
    rows = {}
    for name in ("table1", "table2"):
        ws = wb[name]
        data = list(ws.iter_rows(values_only=True))
        codes = data[4]
        for r in data[5:]:
            if r is None or r[0] is None:
                continue
            uc = r[2] if name == "table1" else r[1]
            for agg, (code, _) in CITIES.items():
                if uc == code:
                    rows.setdefault(agg, {}).update({c: v for c, v in zip(codes, r) if c})
    return pd.DataFrame.from_dict(rows, orient="index")


@lru_cache(maxsize=1)
def _uc_raster():
    import rasterio
    r = rasterio.open(UC_TIF)
    return r.read(1), r.transform


def in_uc(agg: str, x2180: np.ndarray, y2180: np.ndarray) -> np.ndarray:
    """Point (EPSG:2180) inside the 2011 urban centre of agg (cluster identified by its annex population)."""
    import rasterio.transform as rt
    a, tr = _uc_raster()
    pop = float(annex().loc[agg, "t1_05"])
    x, y = TO3035.transform(np.asarray(x2180, float), np.asarray(y2180, float))
    ok = np.isfinite(x) & np.isfinite(y)
    out = np.zeros(len(x), bool)
    r, c = rt.rowcol(tr, x[ok], y[ok])
    r, c = np.asarray(r), np.asarray(c)
    inside = (r >= 0) & (r < a.shape[0]) & (c >= 0) & (c < a.shape[1])
    v = np.full(len(r), np.nan)
    v[inside] = a[r[inside], c[inside]]
    out[np.flatnonzero(ok)] = np.isclose(v, pop, atol=0.5)
    return out


def uc_polygon(agg: str):
    """Urban centre as a (multi)polygon in EPSG:2180 (union of its 1 km cells)."""
    import rasterio.features
    import shapely
    from shapely.ops import transform as stransform
    a, tr = _uc_raster()
    pop = float(annex().loc[agg, "t1_05"])
    m = np.isclose(a, pop, atol=0.5)
    geoms = [shapely.geometry.shape(g) for g, v in rasterio.features.shapes(m.astype(np.uint8), mask=m, transform=tr)]
    u = shapely.union_all(geoms)
    back = Transformer.from_crs("EPSG:3035", "EPSG:2180", always_xy=True)
    return stransform(back.transform, u), int(m.sum())


@lru_cache(maxsize=None)
def frame(agg: str) -> pd.DataFrame:
    """Production destination frame with in_uc and the production origin index (or -1)."""
    d = AI.destinations(agg).copy()
    d["in_uc"] = in_uc(agg, d["x"].to_numpy(), d["y"].to_numpy())
    o = AI.origins(agg)
    pos = pd.Series(np.arange(len(o)), index=o["cell_id"].to_numpy())
    d["origin_idx"] = d["cell_id"].map(pos).fillna(-1).astype(np.int64).to_numpy()
    return d


def uc_origins(agg: str) -> pd.DataFrame:
    """Populated cells (either grid) with centre in the urban centre (all are in the FUA), as production origins."""
    d = frame(agg)
    o = d[d["in_uc"] & d["populated"]].copy()
    assert (o["origin_idx"] >= 0).all()
    lon, lat = AI.TO4326.transform(o["x"].to_numpy(), o["y"].to_numpy())
    o["lon"], o["lat"] = lon, lat
    return o.reset_index().rename(columns={"index": "dest_idx"})


def uc_dests(agg: str) -> pd.DataFrame:
    d = frame(agg)
    return d[d["in_uc"] & d["populated"]].reset_index().rename(columns={"index": "dest_idx"})


# ------------------------------------------------------------------ proximity on any destination subset
def proximity(o: pd.DataFrame, d: pd.DataFrame, radii_m: dict[str, float], weights=("w_census", "w_raw")) -> pd.DataFrame:
    """Destination weight with centre within each straight-line radius of each origin centre (exact)."""
    from scipy.spatial import cKDTree
    t = cKDTree(np.c_[d["x"].to_numpy(), d["y"].to_numpy()])
    P = np.c_[o["x"].to_numpy(), o["y"].to_numpy()]
    out = {}
    for name, r in radii_m.items():
        lists = t.query_ball_point(P, r + 1e-6)
        for w in weights:
            W = d[w].to_numpy()
            out[f"prox_{w[2:]}_{name}"] = np.array([W[ix].sum() for ix in lists])
    return pd.DataFrame(out, index=o.index)


RADII = {"walk30": 2500.0, "fast30": 7500.0, "fast45": 11250.0}


# ------------------------------------------------------------------ supply in the urban centre (annex table 1)
def supply(agg: str) -> pd.DataFrame:
    """DG REGIO annex table 1 definition (p. 44-46): segments between consecutive stops of a trip, departure from
    the first stop 6:00-20:00 on the reference day, both stops in the urban centre, straight-line distance (LAEA);
    vkm per 1000 inhabitants (2011 annex population) and straight-line speed by mode.  De-duplicated service layer
    of the 'all' feed variant (pipeline.gtfs_service)."""
    from pipeline import gtfs_service as gs
    st = gs.stop_times(agg, REF_DAY, "all").sort_values(["feed", "uid", "stop_sequence"], kind="stable")
    st = st.reset_index(drop=True)
    uid = st["uid"].to_numpy()
    same = uid[1:] == uid[:-1]
    x, y = TO3035.transform(st["x"].to_numpy(float), st["y"].to_numpy(float))
    ins = in_uc(agg, st["x"].to_numpy(float), st["y"].to_numpy(float))
    dep = st["dep_s"].to_numpy(float)
    arr = st["arr_s"].to_numpy(float)
    L = np.hypot(x[1:] - x[:-1], y[1:] - y[:-1])
    T = arr[1:] - dep[:-1]
    keep = same & ins[:-1] & ins[1:] & (dep[:-1] >= 6 * 3600) & (dep[:-1] < 20 * 3600) & np.isfinite(L)
    seg = pd.DataFrame({"feed": st["feed"].to_numpy()[:-1][keep], "mode": st["route_class"].to_numpy()[:-1][keep],
                        "km": L[keep] / 1000.0, "h": np.where(T[keep] > 0, T[keep], np.nan) / 3600.0})
    pop = float(annex().loc[agg, "t1_05"])
    g = seg.groupby("mode").agg(km=("km", "sum"), h=("h", "sum"), n=("km", "size"))
    g.loc["total"] = g.sum()
    g["vkm_per_1000inh"] = g["km"] / pop * 1000.0
    # speed only from segments with a positive scheduled time
    sp = seg[seg["h"] > 0].groupby("mode").agg(km=("km", "sum"), h=("h", "sum"))
    sp.loc["total"] = sp.sum()
    g["speed_kmh"] = sp["km"] / sp["h"]
    g["agglomeration"] = agg
    byfeed = seg.groupby(["feed", "mode"])["km"].sum().reset_index()
    byfeed["agglomeration"] = agg
    return g.reset_index(), byfeed


# ------------------------------------------------------------------ existing production chunks (read-only)
def prod_unit(agg: str, net: str, scen: str) -> pd.DataFrame:
    from pipeline.access_aggregate import load_unit
    u = load_unit(agg, net, scen)
    if u is None:
        raise RuntimeError(f"production unit {agg}/{net}/{scen} not finished")
    return u


def walk_uc(agg: str, cut_min: list[int]) -> pd.DataFrame:
    """Walk-only accessibility on the urban-centre domain, from the production walk cache (sparse times <= 60 min
    to every production destination).  Returns per UC origin the UC census/raw population with time <= c."""
    from pipeline.access import CHUNK, unit_dir
    d = frame(agg)
    uo = uc_origins(agg)
    W = np.c_[np.where(d["in_uc"] & d["populated"], d["w_census"], 0.0), np.where(d["in_uc"] & d["populated"], d["w_raw"], 0.0)]
    res = np.zeros((len(uo), 2, len(cut_min)))
    oi = uo["origin_idx"].to_numpy()
    for k in np.unique(oi // CHUNK):
        z = np.load(unit_dir(agg, "street", "walk") / f"chunk_{k:05d}.walk.npz")
        ip, ix, tt = z["indptr"], z["idx"], z["tt"]
        for r in np.flatnonzero(oi // CHUNK == k):
            i = oi[r] - k * CHUNK
            sl = slice(ip[i], ip[i + 1])
            for j, c in enumerate(cut_min):
                m = tt[sl] <= c
                res[r, :, j] = W[ix[sl][m]].sum(0)
    out = {}
    for j, c in enumerate(cut_min):
        out[f"acc_census_{c}"] = res[:, 0, j]
        out[f"acc_raw_{c}"] = res[:, 1, j]
    return pd.DataFrame(out, index=uo.index)


def walk_cache_uc(agg: str):
    """Walk-only times from each UC origin to UC destinations: dict origin row -> (uc dest positions, minutes)."""
    from pipeline.access import CHUNK, unit_dir
    d = frame(agg)
    ud = uc_dests(agg)
    pos = np.full(len(d), -1, np.int64)
    pos[ud["dest_idx"].to_numpy()] = np.arange(len(ud))
    uo = uc_origins(agg)
    oi = uo["origin_idx"].to_numpy()
    out = {}
    for k in np.unique(oi // CHUNK):
        z = np.load(unit_dir(agg, "street", "walk") / f"chunk_{k:05d}.walk.npz")
        ip, ix, tt = z["indptr"], z["idx"], z["tt"]
        for r in np.flatnonzero(oi // CHUNK == k):
            i = oi[r] - k * CHUNK
            sl = slice(ip[i], ip[i + 1])
            p = pos[ix[sl]]
            m = p >= 0
            out[r] = (p[m], tt[sl][m].astype(np.int32))
    return out


# ------------------------------------------------------------------ routing (side step)
def net_copy(agg: str) -> Path:
    """Copy the production 'all' network (Kryo file + warnings) into data/interim/access_dgregio/r5/<agg>/."""
    from pipeline.r5_env import network_dir
    src = network_dir(agg, "all")
    files = sorted(src.glob("*.transport_network"))
    if len(files) != 1:
        raise FileNotFoundError(f"expected one built network in {src}")
    dst = OUT / "r5" / agg
    dst.mkdir(parents=True, exist_ok=True)
    f = files[0]
    tgt = dst / f.name
    if not tgt.exists() or tgt.stat().st_size != f.stat().st_size:
        for old in dst.glob("*.transport_network"):
            old.unlink()
        shutil.copyfile(f, tgt.with_suffix(".tmp"))
        tgt.with_suffix(".tmp").replace(tgt)
        (dst / "source.json").write_text(json.dumps({"copied_from": str(f.relative_to(INTERIM.parent.parent)),
                                                     "bytes": f.stat().st_size,
                                                     "mtime": dt.datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                                                     "inputs_sig": (src / "inputs.sig").read_text() if (src / "inputs.sig").exists() else None},
                                                    indent=1), encoding="utf-8")
    return tgt


def load_network(agg: str):
    """r5py TransportNetwork object around our copy of the Kryo file (no OSM / GTFS working copies, no writes)."""
    import com.conveyal.r5
    import java.io
    from r5py import TransportNetwork
    from r5py.util import GoodEnoughEquidistantCrs
    p = net_copy(agg)
    tn = TransportNetwork.__new__(TransportNetwork)
    tn._transport_network = com.conveyal.r5.kryo.KryoNetworkSerializer.read(java.io.File(str(p)))
    tn.EQUIDISTANT_CRS = GoodEnoughEquidistantCrs(tn.extent)
    return tn


def make_tasks(tn, dests_gdf, scen: str) -> list:
    from r5py import RegionalTask, TransportMode
    s = SCENARIOS[scen]
    day = dt.datetime.fromisoformat(REF_DAY)
    if s["kind"] == "transit":
        common = dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], percentiles=[50],
                      max_time=dt.timedelta(minutes=MAX_MIN), max_time_walking=dt.timedelta(minutes=s["access_min"]),
                      speed_walking=s.get("walk_kmh", WALK_KMH))
        if s["deps"] is None:
            kws = [dict(departure=day.replace(hour=7), departure_time_window=dt.timedelta(hours=2), **common)]
        else:
            kws = [dict(departure=day.replace(hour=h, minute=m), departure_time_window=dt.timedelta(minutes=1), **common)
                   for h, m in s["deps"]]
    else:
        kws = [dict(transport_modes=[TransportMode.BICYCLE], departure=day.replace(hour=7),
                    departure_time_window=dt.timedelta(minutes=1), percentiles=[50],
                    max_time=dt.timedelta(minutes=MAX_MIN), speed_cycling=BIKE_KMH, max_bicycle_traffic_stress=s["lts"])]
    out = []
    for kw in kws:
        t = RegionalTask(tn, origin=None, destinations=dests_gdf, **kw)._regional_task
        out.append(t)
    return out


def _tt(task, jnet, lon, lat) -> np.ndarray:
    import com.conveyal.r5
    t = task.clone()
    t.fromLat, t.fromLon = float(lat), float(lon)
    res = com.conveyal.r5.analyst.TravelTimeComputer(t, jnet).computeTravelTimes()
    return np.asarray(res.travelTimes.getValues()[0], dtype=np.int64).copy()


def route(aggs: list[str], scens: list[str], threads: int, limit: int | None) -> None:
    import geopandas as gpd
    for agg in aggs:
        uo, ud = uc_origins(agg), uc_dests(agg)
        if limit:
            uo = uo.iloc[np.linspace(0, len(uo) - 1, limit).round().astype(int)]
        W = np.c_[ud["w_census"].to_numpy(), ud["w_raw"].to_numpy()]
        wc = walk_cache_uc(agg)
        t0 = time.time()
        tn = load_network(agg)
        jnet = tn._transport_network
        lon, lat = AI.TO4326.transform(ud["x"].to_numpy(), ud["y"].to_numpy())
        dg = gpd.GeoDataFrame({"id": ud["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")
        log(f"{agg}: network loaded in {time.time() - t0:.0f} s; {len(uo)} UC origins, {len(ud)} UC destinations")
        for scen in scens:
            path = OUT / agg / f"{scen}{'_lim' + str(limit) if limit else ''}.parquet"
            if path.exists():
                log(f"{agg} {scen}: exists, skipped")
                continue
            s = SCENARIOS[scen]
            tasks = make_tasks(tn, dg, scen)
            nd = len(ud)

            def one(r):
                o = uo.loc[r]
                tts = [_tt(t, jnet, o["lon"], o["lat"]) for t in tasks]
                if s["kind"] == "transit":
                    p, wt = wc[r]
                    walk = np.full(nd, NODATA, np.int64)
                    walk[p] = np.ceil(wt * WALK_KMH / s.get("walk_kmh", WALK_KMH)).astype(np.int64)
                    tts = [np.minimum(t, walk) for t in tts]     # transit + walk never worse than walking
                A = np.stack(tts).astype(float)
                A[A > MAX_MIN] = np.inf
                if len(tts) == 1:
                    variants = {"": A[0]}
                else:
                    strict = A.mean(0)                                   # unreachable in any departure -> inf
                    with np.errstate(invalid="ignore", divide="ignore"):
                        fin = np.isfinite(A)
                        lenient = np.where(fin.any(0), np.where(fin, A, 0).sum(0) / np.maximum(fin.sum(0), 1), np.inf)
                    variants = {"": strict, "lenient_": lenient}
                row = {}
                for pre, tt in variants.items():
                    for c in CUTS:
                        m = tt <= c
                        row[f"{pre}acc_census_{c}"] = float(W[m, 0].sum())
                        row[f"{pre}acc_raw_{c}"] = float(W[m, 1].sum())
                return row

            t1 = time.time()
            with cf.ThreadPoolExecutor(max_workers=threads) as ex:
                rows = list(ex.map(one, uo.index))
            df = pd.DataFrame(rows, index=uo.index)
            df.insert(0, "cell_id", uo["cell_id"].to_numpy())
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp.parquet")
            df.reset_index().rename(columns={"index": "uo_row"}).to_parquet(tmp, index=False)
            tmp.replace(path)
            wall = time.time() - t1
            log(f"{agg} {scen}: {len(uo)} origins x {len(tasks)} searches in {wall:.0f} s "
                f"({1000 * wall / max(len(uo), 1):.0f} ms/origin, {threads} threads)")
        del tn, jnet
        import gc
        gc.collect()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "route", "report"])
    ap.add_argument("--agg", nargs="*", default=list(CITIES))
    ap.add_argument("--scen", nargs="*", default=list(SCENARIOS))
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--xmx", default="8G")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.cmd == "route":
        if a.threads > 6:
            raise SystemExit("at most 6 threads (production run in progress)")
        from pipeline.r5_env import start
        start(xmx=a.xmx, tmp=OUT / "_tmp")
        route(a.agg, a.scen, a.threads, a.limit)
    elif a.cmd == "prep":
        from pipeline import access_dgregio_report as R
        R.prep(a.agg)
    else:
        from pipeline import access_dgregio_report as R
        R.report(a.agg)


if __name__ == "__main__":
    main()
