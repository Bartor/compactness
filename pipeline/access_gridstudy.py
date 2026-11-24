"""Comparison-only variant of transport performance computed by the rules of the DG REGIO grid study
(Poelman & Ackermans, "Assessing the performance of urban public transport using population grid data", DG REGIO,
PDF of 2023-02; ROADMAP item 11), with a step-by-step decomposition from our published urban-centre values.

    python -m pipeline.access_gridstudy peak                         # 30-min morning peak per city (no JVM)
    python -m pipeline.access_gridstudy route [--agg ...] [--run r_prod r_grid r_peak] [--threads 4] [--xmx 8G] [--limit N]
    python -m pipeline.access_gridstudy report                       # results/qa/access/gridstudy/ + metrics_access_gridstudy.*

Grid-study rules (page numbers of the PDF):
* origins: populated 200 m cells in the urban centre (GEOSTAT 2011), p. 2; destinations: populated cells within
  8 / 12 km straight line of the origin, **also outside the urban centre**, p. 2 and 15; proximity: all population
  within 8 / 12 km (16 km/h), not clipped to the urban centre, p. 2; own cell included in both, p. 15;
* travel time: OTP Analyst 1.5, departures every 5 min in a 30-min morning peak whose start is the half hour
  beginning the busiest hour of departures at the centre's stops, the shortest of up to 6 times, p. 14-15;
* walking: at most 15 min in total (access + transfers + egress), walk-only trips at most 1.2 km, p. 2 and 15
  (1.2 km in 15 min = 4.8 km/h);
* city value: population-weighted averages of accessibility, proximity and performance, p. 15.

Here (comparison only; the production method is unchanged):
* origins: the urban-centre domain of pipeline.access_uc (Eurostat HDENS_CLST_2021, 250 m census-scaled grid);
* destinations: every populated 250 m cell within 12 km of any origin (production destination frame, FUA + 15 km);
* R5 v7.5.1 on our own copies of the production 'all' networks, Wednesday 2026-11-25:
    r_prod: production legs (walk 5 km/h, access/egress <= 12 min), 07:00-09:00 every minute, percentiles [P_LOW, 50]
    r_grid: walk 4.8 km/h, access/egress <= 15 min each (R5 limits each leg, not the total), same window and percentiles
    r_peak: as r_grid but 6 single departures every 5 min in the city's 30-min peak, minimum of the 6
* walk-only rule applied per pair: production min(transit, walk <= 60 min at 5 km/h); grid min(transit, walk <= 15 min
  at 4.8 km/h);
* per origin we store the population reached within 30 / 45 min for destination sets {urban centre only, all} and
  radii {7.5, 8} / {11.25, 12} km; radii, domain and walk rule are therefore varied on the same searches.
Interim: data/interim/access_gridstudy/ (resumable per agglomeration and run with .sig files).
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

from pipeline import access_inputs as AI
from pipeline import access_uc as U
from pipeline.common import INTERIM, RESULTS, load_config

CFG = load_config()
REF_DAY = CFG["reference_day"]
AGGS = U.AGGS
OUT = INTERIM / "access_gridstudy"
QA = RESULTS / "qa" / "access" / "gridstudy"
METRICS = RESULTS / "metrics"
PROGRESS = INTERIM / "proposals" / "gridstudy_progress.md"
CODE_VERSION = "gridstudy-2026-11-24.1"
NODATA = np.iinfo(np.int64).max
MAX_MIN = 60
P_LOW = 1                       # lowest percentile R5 accepts here (see check_percentile); ~ fastest of 120 minutes
RUNS = {
    "r_prod": {"walk_kmh": 5.0, "access_min": 12, "window": "am2h"},
    "r_grid": {"walk_kmh": 4.8, "access_min": 15, "window": "am2h"},
    "r_peak": {"walk_kmh": 4.8, "access_min": 15, "window": "peak30"},
}
RADII = {30: {"our": 7500.0, "grid": 8000.0}, 45: {"our": 11250.0, "grid": 12000.0}}
R_MAX = 12000.0
MIN_FREE_GB = 14.0


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ cells
@lru_cache(maxsize=None)
def origins(agg: str) -> pd.DataFrame:
    """Urban-centre domain cells of pipeline.access_uc (same order, same weights)."""
    return U.uc_cells(agg)


@lru_cache(maxsize=None)
def dests(agg: str) -> pd.DataFrame:
    """Populated production destination cells within R_MAX of any origin; in_uc flags the urban-centre domain."""
    from scipy.spatial import cKDTree
    d = U.frame(agg)
    d = d[d["populated"]].copy()
    o = origins(agg)
    t = cKDTree(np.c_[o["x"].to_numpy(), o["y"].to_numpy()])
    dist, _ = t.query(np.c_[d["x"].to_numpy(), d["y"].to_numpy()], distance_upper_bound=R_MAX + 1.0)
    d = d[np.isfinite(dist)].copy()
    d["lon"], d["lat"] = AI.TO4326.transform(d["x"].to_numpy(), d["y"].to_numpy())
    return d.reset_index().rename(columns={"index": "frame_idx"})


def cells_hash(agg: str) -> str:
    return U.uc_hash(agg) + "|" + AI.frame_hash(dests(agg), ["cell_id", "w_census", "w_raw", "in_uc"])


def neighbours(agg: str) -> list[np.ndarray]:
    """Per origin: positions (in dests) within R_MAX, and their distances."""
    from scipy.spatial import cKDTree
    o, d = origins(agg), dests(agg)
    t = cKDTree(np.c_[d["x"].to_numpy(), d["y"].to_numpy()])
    lists = t.query_ball_point(np.c_[o["x"].to_numpy(), o["y"].to_numpy()], R_MAX + 1e-6)
    return [np.asarray(sorted(ix), dtype=np.int64) for ix in lists]


def walk_times(agg: str) -> dict:
    """Per origin row: (positions in dests, walk minutes at 5 km/h <= 60) from the production walk cache."""
    from pipeline.access import CHUNK, unit_dir
    fr = U.frame(agg)
    d = dests(agg)
    pos = np.full(len(fr), -1, np.int64)
    pos[d["frame_idx"].to_numpy()] = np.arange(len(d))
    oi = origins(agg)["origin_idx"].to_numpy()
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


# ------------------------------------------------------------------ proximity (exact, both radii sets, both domains)
def proximity(agg: str) -> pd.DataFrame:
    p = OUT / agg / "proximity.parquet"
    s = p.with_suffix(".sig")
    h = cells_hash(agg) + "|prox2"
    if p.exists() and s.exists() and s.read_text() == h:
        return pd.read_parquet(p)
    o, d = origins(agg), dests(agg)
    nb = neighbours(agg)
    X, Y = d["x"].to_numpy(), d["y"].to_numpy()
    W = np.c_[d["w_census"].to_numpy(), d["w_raw"].to_numpy()]
    uc = d["in_uc"].to_numpy()
    ox, oy = o["x"].to_numpy(), o["y"].to_numpy()
    rows = []
    for r in range(len(o)):
        ix = nb[r]
        dist = np.hypot(X[ix] - ox[r], Y[ix] - oy[r])
        row = {}
        for c, rr in RADII.items():
            for rk, rad in rr.items():
                m = dist <= rad + 1e-6
                for dom, dm in (("uc", uc[ix]), ("all", np.ones(len(ix), bool))):
                    s2 = W[ix][m & dm].sum(0)
                    row[f"prox_census_{dom}_{rk}{c}"] = float(s2[0])
                    row[f"prox_raw_{dom}_{rk}{c}"] = float(s2[1])
        rows.append(row)
    df = pd.DataFrame(rows)
    df.insert(0, "cell_id", o["cell_id"].to_numpy())
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    s.write_text(h)
    return df


# ------------------------------------------------------------------ morning peak per city (paper p. 14-15)
def peak(agg: str) -> dict:
    """Start of the 30-min peak: half hour t (05:00-11:00) maximising departures at domain stops in [t, t + 60 min)."""
    from pipeline import gtfs_service as gs
    st = gs.stop_times(agg, REF_DAY, "all")
    ok = np.isfinite(st["x"].to_numpy(float))
    st = st[ok]
    ins = U.in_uc(agg, st["x"].to_numpy(float), st["y"].to_numpy(float))
    dep = st["dep_s"].to_numpy(float)[ins]
    starts = np.arange(5 * 3600, 11 * 3600 + 1, 1800)
    counts = np.array([int(((dep >= t) & (dep < t + 3600)).sum()) for t in starts])
    t = int(starts[int(np.argmax(counts))])
    return {"agglomeration": agg, "peak_start_s": t, "peak_start": f"{t // 3600:02d}:{(t % 3600) // 60:02d}",
            "departures_in_hour": int(counts.max()), "profile": {f"{s // 3600:02d}:{(s % 3600) // 60:02d}": int(c) for s, c in zip(starts, counts)}}


def peaks(aggs: list[str]) -> dict:
    p = OUT / "peaks.json"
    have = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for a in aggs:
        if a not in have:
            have[a] = peak(a)
            log(f"{a}: peak 30 min from {have[a]['peak_start']} ({have[a]['departures_in_hour']} departures in the hour)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(have, indent=1, sort_keys=True), encoding="utf-8")
    return have


# ------------------------------------------------------------------ R5
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


def make_tasks(tn, dg, run: str, peak_s: int | None) -> list:
    from r5py import RegionalTask, TransportMode
    s = RUNS[run]
    day = dt.datetime.fromisoformat(REF_DAY)
    common = dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], max_time=dt.timedelta(minutes=MAX_MIN),
                  max_time_walking=dt.timedelta(minutes=s["access_min"]), speed_walking=s["walk_kmh"])
    if s["window"] == "am2h":
        kws = [dict(departure=day.replace(hour=7), departure_time_window=dt.timedelta(hours=2), percentiles=[P_LOW, 50], **common)]
    else:
        kws = [dict(departure=day + dt.timedelta(seconds=peak_s + 300 * k), departure_time_window=dt.timedelta(minutes=1),
                    percentiles=[50], **common) for k in range(6)]
    return [RegionalTask(tn, origin=None, destinations=dg, **kw)._regional_task for kw in kws]


def _tt(task, jnet, lon, lat) -> np.ndarray:
    """Travel times (minutes) for every percentile of the task: array (n_percentiles, n_dest)."""
    import com.conveyal.r5
    t = task.clone()
    t.fromLat, t.fromLon = float(lat), float(lon)
    res = com.conveyal.r5.analyst.TravelTimeComputer(t, jnet).computeTravelTimes()
    v = res.travelTimes.getValues()
    return np.stack([np.asarray(v[i], dtype=np.int64) for i in range(len(v))])


def run_sig(agg: str, run: str, peak_s: int | None) -> str:
    src = OUT / "r5" / agg / "source.json"
    net = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
    parts = {"code": CODE_VERSION, "cells": cells_hash(agg), "net": net.get("copied_from"), "net_sig": net.get("inputs_sig"),
             "run": RUNS[run], "p_low": P_LOW, "peak": peak_s, "day": REF_DAY, "radii": RADII,
             "walk_unit": json.loads((AI.ACCESS_INT / agg / "street" / "walk" / "manifest.json").read_text(encoding="utf-8"))["signature"]}
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def run_path(agg: str, run: str, limit: int | None = None) -> Path:
    return OUT / agg / f"{run}{'_lim' + str(limit) if limit else ''}.parquet"


def run_done(agg: str, run: str, peak_s: int | None, limit: int | None = None) -> bool:
    p = run_path(agg, run, limit)
    s = p.with_suffix(".sig")
    return p.exists() and s.exists() and s.read_text() == run_sig(agg, run, peak_s)


def free_gb() -> float:
    import psutil
    return psutil.virtual_memory().available / 2 ** 30


def wait_memory() -> None:
    while (g := free_gb()) < MIN_FREE_GB:
        log(f"only {g:.1f} GB free (< {MIN_FREE_GB}); waiting 3 min")
        time.sleep(180)


def sums_for(tt: np.ndarray, ix: np.ndarray, dist: np.ndarray, uc: np.ndarray, W: np.ndarray, pre: str) -> dict:
    """Population reached (tt <= cutoff, within radius) for both destination domains and both radii sets."""
    row = {}
    for c, rr in RADII.items():
        ok = tt[ix] <= c
        for rk, rad in rr.items():
            m = ok & (dist <= rad + 1e-6)
            for dom, dm in (("uc", uc[ix]), ("all", None)):
                mm = m if dm is None else (m & dm)
                s2 = W[ix][mm].sum(0)
                row[f"{pre}_census_{dom}_{rk}{c}"] = float(s2[0])
                row[f"{pre}_raw_{dom}_{rk}{c}"] = float(s2[1])
    return row


def route(aggs: list[str], runs: list[str], threads: int, limit: int | None) -> None:
    import geopandas as gpd
    pk = peaks(aggs)
    for agg in aggs:
        ps = pk[agg]["peak_start_s"]
        todo = [r for r in runs if not run_done(agg, r, ps if r == "r_peak" else None, limit)]
        if not todo:
            log(f"{agg}: {runs} up to date")
            continue
        o, d = origins(agg), dests(agg)
        if limit:
            sel = np.linspace(0, len(o) - 1, limit).round().astype(int)
        else:
            sel = np.arange(len(o))
        proximity(agg)
        nb = neighbours(agg)
        wt = walk_times(agg)
        X, Y = d["x"].to_numpy(), d["y"].to_numpy()
        W = np.c_[d["w_census"].to_numpy(), d["w_raw"].to_numpy()]
        uc = d["in_uc"].to_numpy()
        ox, oy = o["x"].to_numpy(), o["y"].to_numpy()
        wait_memory()
        t0 = time.time()
        tn = load_network(agg)
        jnet = tn._transport_network
        dg = gpd.GeoDataFrame({"id": d["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(d["lon"], d["lat"]), crs="EPSG:4326")
        log(f"{agg}: network loaded in {time.time() - t0:.0f} s; {len(sel)} origins, {len(d)} destinations; free {free_gb():.0f} GB")
        nd = len(d)
        for run in todo:
            s = RUNS[run]
            tasks = make_tasks(tn, dg, run, ps)

            def one(r):
                ix = nb[r]
                dist = np.hypot(X[ix] - ox[r], Y[ix] - oy[r])
                p, t = wt[r]
                walk60 = np.full(nd, NODATA, np.int64)
                walk60[p] = t                                           # production rule: walk-only <= 60 min at 5 km/h
                walk15 = np.full(nd, NODATA, np.int64)
                tw = np.ceil(t * 5.0 / 4.8 - 1e-9).astype(np.int64)      # same path at 4.8 km/h
                walk15[p[tw <= 15]] = tw[tw <= 15]                      # grid rule: walk-only <= 15 min (1.2 km)
                res = [_tt(tk, jnet, o["lon"].iat[r], o["lat"].iat[r]) for tk in tasks]
                if s["window"] == "am2h":
                    A = res[0]
                    pcts = {"low": A[0], "med": A[1]}
                else:
                    pcts = {"min6": np.min(np.stack([a[0] for a in res]), axis=0)}
                row = {}
                for pk_, tt in pcts.items():
                    for rule, wv in (("w60", walk60), ("w15", walk15)):
                        if run == "r_prod" and rule == "w15":
                            continue
                        if run != "r_prod" and rule == "w60":
                            continue
                        row.update(sums_for(np.minimum(tt, wv), ix, dist, uc, W, f"acc_{pk_}_{rule}"))
                    if run != "r_prod":
                        # destinations whose best trip is the walk-only one (share of accessibility due to walking)
                        best = np.minimum(tt, walk15)
                        wo = np.where(walk15 <= tt, best, NODATA)
                        row.update(sums_for(wo, ix, dist, uc, W, f"walkonly_{pk_}"))
                return row

            t1 = time.time()
            with cf.ThreadPoolExecutor(max_workers=threads) as ex:
                rows = list(ex.map(one, sel))
            df = pd.DataFrame(rows)
            df.insert(0, "cell_id", o["cell_id"].to_numpy()[sel])
            path = run_path(agg, run, limit)
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(path.with_suffix(".tmp.parquet"), index=False)
            path.with_suffix(".tmp.parquet").replace(path)
            path.with_suffix(".sig").write_text(run_sig(agg, run, ps if run == "r_peak" else None))
            wall = time.time() - t1
            log(f"{agg} {run}{' limit ' + str(limit) if limit else ''}: {len(sel)} origins x {len(tasks)} searches in {wall:.0f} s "
                f"({1000 * wall / max(len(sel), 1):.0f} ms/origin, {threads} threads)")
            with open(PROGRESS, "a", encoding="utf-8") as f:
                f.write(f"- {dt.datetime.now():%Y-%m-%d %H:%M} routing {agg} {run}{' (próba ' + str(limit) + ')' if limit else ''}: "
                        f"{len(sel)} startów, {wall / 60:.1f} min.\n")
        del tn, jnet
        gc.collect()


def check_percentile(agg: str = "poznan") -> None:
    """Which low percentiles R5 accepts, and how they compare with the minimum of 120 single-minute departures."""
    import geopandas as gpd
    from r5py import RegionalTask, TransportMode
    o, d = origins(agg), dests(agg)
    tn = load_network(agg)
    jnet = tn._transport_network
    dg = gpd.GeoDataFrame({"id": d["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(d["lon"], d["lat"]), crs="EPSG:4326")
    day = dt.datetime.fromisoformat(REF_DAY)
    common = dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], max_time=dt.timedelta(minutes=MAX_MIN),
                  max_time_walking=dt.timedelta(minutes=15), speed_walking=4.8)
    r = len(o) // 2
    lon, lat = o["lon"].iat[r], o["lat"].iat[r]
    out = {}
    for p in ([0, 50], [1, 50], [2, 50], [5, 50]):
        try:
            tk = RegionalTask(tn, origin=None, destinations=dg, departure=day.replace(hour=7),
                              departure_time_window=dt.timedelta(hours=2), percentiles=p, **common)._regional_task
            out[str(p[0])] = _tt(tk, jnet, lon, lat)[0]
            log(f"percentile {p[0]}: ok")
        except Exception as e:  # noqa: BLE001 - probing
            log(f"percentile {p[0]}: rejected ({str(e)[:200]})")
    singles = []
    for k in range(120):
        tk = RegionalTask(tn, origin=None, destinations=dg, departure=day.replace(hour=7) + dt.timedelta(minutes=k),
                          departure_time_window=dt.timedelta(minutes=1), percentiles=[50], **common)._regional_task
        singles.append(_tt(tk, jnet, lon, lat)[0])
    mn = np.min(np.stack(singles), 0)
    fin = mn < 10 ** 6
    for k, v in out.items():
        f2 = fin & (v < 10 ** 6)
        diff = v[f2] - mn[f2]
        log(f"percentile {k} vs min of 120 singles: mean diff {diff.mean():.2f} min, max {diff.max()}, "
            f"share equal {np.mean(diff == 0):.3f}, reachable {f2.sum()} / {fin.sum()}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["peak", "route", "check", "report"])
    ap.add_argument("--agg", nargs="*", default=AGGS)
    ap.add_argument("--run", nargs="*", default=list(RUNS))
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--xmx", default="8G")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.cmd == "peak":
        print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "profile"} for k, v in peaks(a.agg).items()}, indent=1))
    elif a.cmd in ("route", "check"):
        if a.threads > 4:
            raise SystemExit("at most 4 threads (shared machine)")
        wait_memory()
        from pipeline.r5_env import start
        start(xmx=a.xmx, tmp=OUT / "_tmp")
        if a.cmd == "check":
            check_percentile(a.agg[0])
        else:
            route(a.agg, a.run, a.threads, a.limit)
    else:
        from pipeline import access_gridstudy_report as R
        R.main(a.agg)


if __name__ == "__main__":
    main()
