"""Phase 3 groundwork: R5 network build + routing cost benchmark + sanity check on sampled origins.

    python -m pipeline.r5_benchmark --agg wroclaw --variant all [--threads 20] [--n 200]
    python -m pipeline.r5_benchmark --report           # merge per-city runs into results/qa/access/

This is NOT the full accessibility computation (brief §4.6); it measures what that run will cost.

Routing set-up (brief §4.6; RAPORT §9.2 for the DG REGIO differences)
* origins: 250 m cells with population inside the FUA (``data/interim/popgrid/cells_<agg>.parquet``,
  ``in_fua``); destinations: every populated 250 m cell in FUA + 15 km (both population grids), cell centres.
* transit: modes TRANSIT + WALK, reference Wednesday, departures every minute 07:00-09:00
  (R5 ``fromTime``/``toTime``, range-RAPTOR evaluates each minute), 50th percentile over those departures,
  ``maxTripDurationMinutes`` 60.  "max dojście 1 km" = R5 ``maxWalkTime`` 12 min at walk speed 5 km/h
  (R5 limits access and egress walks by time, per leg; transfers between stops use R5's own transfer
  search, up to 1 km street distance).  NB: the same limit also caps the walk-only direct trip inside a
  transit request, so a destination 1.5 km away is reachable only by a transit leg.
* walk only: 5 km/h, 30 min cap.  bike only: 15 km/h, 30 min cap, R5 level of traffic stress <= 3 (r5py default).
  5 and 15 km/h match the proximity radii of the brief (2.5 km and 7.5 km in 30 min).
* frequencies were materialised as scheduled trips in the cleaned GTFS (pipeline.r5_inputs), so R5 does no
  Monte Carlo draws and results are deterministic (checked by routing the same sample twice).

Accessibility without an OD table: r5py 1.1.7 has no accessibility estimator, and ``TravelTimeMatrix``
builds a pandas OD frame per origin (plus a slow element-wise null fill).  Here each origin is routed with
R5's ``TravelTimeComputer`` directly (thread pool; JPype releases the GIL during the Java call), the
travel-time vector (int minutes, one per destination) is turned into population sums at the cutoffs
immediately, and only per-origin aggregates are kept.

Sample: ``--n`` draws with probability proportional to census-scaled population (with replacement); the
city-level population-weighted mean is the plain mean over draws (Hansen-Hurwitz); bootstrap gives its SE.
A second, cluster sample (``--blocks``) routes every 250 m cell of randomly drawn 500 m blocks plus the
block's population-weighted centroid, to measure what aggregating origins to 500 m would change.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import threading
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="The provided departure time window is below 5 minutes")

import numpy as np
import pandas as pd
import psutil

from pipeline.common import INTERIM, RESULTS, load_config, round_sig, sig, write_meta
from pipeline.r5_env import check_network, network, network_dir, start, versions
from pipeline.r5_inputs import agg_dir, ref_days

OUT = RESULTS / "qa" / "access"
RUNS = INTERIM / "r5" / "_bench"
SEED = 20261125
MAX_INT = 2 ** 31 - 1
WALK_KMH, BIKE_KMH = 5.0, 15.0
MAX_WALK_M = 1000
GRIDS = ["ghsl_census_scaled", "ghsl_raw"]

# (mode, minute cutoffs, proximity radii in m) as in brief §4.6
MEASURES = {"transit": ([30, 45], [7500, 11250]), "walk": ([30], [2500]), "bike": ([30], [7500])}

# Wroclaw OD pairs for the journey-planner check (brief §7.4); lon, lat WGS84
OD_PAIRS = [
    ("Kozanow (near KOZANOW Dokerska) -> Rynek", (16.9640, 51.1420), (17.0320, 51.1100)),
    ("Jagodno (near JAGODNO P+R) -> pl. Grunwaldzki", (17.0600, 51.0545), (17.0636, 51.1118)),
    ("Siechnice (stacja) -> Wroclaw Glowny", (17.1530, 51.0350), (17.0365, 51.0983)),
]


# ------------------------------------------------------------------ data
def cells(agg: str) -> pd.DataFrame:
    c = pd.read_parquet(INTERIM / "popgrid" / f"cells_{agg}.parquet")
    return c.sort_values("cell_id", kind="stable").reset_index(drop=True)


def to_ll(x: np.ndarray, y: np.ndarray):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    return tr.transform(x, y)


def dest_gdf(c: pd.DataFrame):
    import geopandas as gpd
    return gpd.GeoDataFrame({"id": c["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(c["x"], c["y"]),
                            crs="EPSG:2180")


def pps_sample(c: pd.DataFrame, n: int, seed: int) -> np.ndarray:
    """n draws (row indices into c) with probability proportional to census-scaled population, FUA only."""
    rng = np.random.default_rng(seed)
    w = np.where(c["in_fua"], c["pop_ghsl_census_scaled"].to_numpy(), 0.0)
    return np.sort(rng.choice(len(c), size=n, replace=True, p=w / w.sum()))


def block_sample(c: pd.DataFrame, n_blocks: int, seed: int) -> pd.DataFrame:
    """500 m blocks drawn by census-scaled population; every child 250 m cell in the FUA + the block centroid."""
    rng = np.random.default_rng(seed + 1)
    f = c[c["in_fua"]].copy()
    f["bx"] = (np.floor((f["x"] - 125) / 500)).astype(int)
    f["by"] = (np.floor((f["y"] - 125) / 500)).astype(int)
    f["block"] = f["bx"].astype(str) + "_" + f["by"].astype(str)
    b = f.groupby("block")["pop_ghsl_census_scaled"].sum()
    b = b[b > 0]
    pick = rng.choice(b.index.to_numpy(), size=min(n_blocks, len(b)), replace=False, p=(b / b.sum()).to_numpy())
    kids = f[f["block"].isin(set(pick))].copy()
    w = kids["pop_ghsl_census_scaled"].clip(lower=0)
    cen = kids.assign(wx=kids["x"] * w, wy=kids["y"] * w, w=w).groupby("block")[["wx", "wy", "w"]].sum()
    cen = pd.DataFrame({"x": cen["wx"] / cen["w"], "y": cen["wy"] / cen["w"]}).reset_index()
    kids["kind"] = "cell"
    cen["kind"] = "block_centroid"
    cen["cell_id"] = "B" + cen["block"]
    return pd.concat([kids[["block", "kind", "cell_id", "x", "y", "pop_ghsl_census_scaled"]],
                      cen[["block", "kind", "cell_id", "x", "y"]]], ignore_index=True).sort_values(
        ["block", "kind", "cell_id"], kind="stable").reset_index(drop=True)


# ------------------------------------------------------------------ routing
def base_task(tn, dests, mode: str, window: str = "am_peak", max_rides: int = 8, day: str | None = None,
              lts: int = 3, walk_min: int | None = None, max_min: int = 60):
    """Java RegionalTask template for one mode / window (cloned per origin)."""
    r5py = start()
    from r5py import RegionalTask, TransportMode
    cfg = load_config()
    w = cfg["time_windows"][window]
    day = day or (cfg["reference_saturday"] if w["day"] == "saturday" else cfg["reference_day"])
    h0, m0 = map(int, w["start"].split(":"))
    h1, m1 = map(int, w["end"].split(":"))
    dep = dt.datetime.fromisoformat(day).replace(hour=h0, minute=m0)
    span = dt.timedelta(hours=h1 - h0, minutes=m1 - m0)
    if mode == "transit":
        kw = dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], departure=dep,
                  departure_time_window=span, percentiles=[50], max_time=dt.timedelta(minutes=max_min),
                  max_time_walking=dt.timedelta(minutes=walk_min or round(MAX_WALK_M / 1000 / WALK_KMH * 60)),
                  speed_walking=WALK_KMH, max_public_transport_rides=max_rides)
    elif mode == "walk":
        kw = dict(transport_modes=[TransportMode.WALK], departure=dep, departure_time_window=dt.timedelta(minutes=1),
                  percentiles=[50], max_time=dt.timedelta(minutes=30), speed_walking=WALK_KMH)
    elif mode == "bike":
        kw = dict(transport_modes=[TransportMode.BICYCLE], departure=dep,
                  departure_time_window=dt.timedelta(minutes=1), percentiles=[50],
                  max_time=dt.timedelta(minutes=30), speed_cycling=BIKE_KMH, max_bicycle_traffic_stress=lts)
    else:
        raise ValueError(mode)
    rt = RegionalTask(tn, origin=None, destinations=dests.to_crs("EPSG:4326"), **kw)
    t = rt._regional_task
    return t, {k: str(v) for k, v in kw.items()} | {
        "r5_fromTime": int(t.fromTime), "r5_toTime": int(t.toTime), "r5_maxWalkTime_min": int(t.maxWalkTime),
        "r5_maxBikeTime_min": int(t.maxBikeTime), "r5_maxTripDurationMinutes": int(t.maxTripDurationMinutes),
        "r5_maxRides": int(t.maxRides), "r5_walkSpeed_ms": float(t.walkSpeed), "r5_bikeSpeed_ms": float(t.bikeSpeed),
        "r5_monteCarloDraws": int(t.monteCarloDraws)}


def route(tn, task, lon: np.ndarray, lat: np.ndarray, threads: int) -> tuple[np.ndarray, dict]:
    """Travel time (int minutes, MAX_INT = unreachable) from each origin to every destination."""
    import com.conveyal.r5
    import java.lang
    jnet = tn._transport_network
    out = [None] * len(lon)
    proc = psutil.Process()
    rt = java.lang.Runtime.getRuntime()
    peak = {"heap": 0, "rss": 0}
    lock = threading.Lock()

    def one(i):
        t = task.clone()
        t.fromLat, t.fromLon = float(lat[i]), float(lon[i])
        res = com.conveyal.r5.analyst.TravelTimeComputer(t, jnet).computeTravelTimes()
        v = np.asarray(res.travelTimes.getValues()[0], dtype=np.int32).copy()
        with lock:
            peak["heap"] = max(peak["heap"], rt.totalMemory() - rt.freeMemory())
            peak["rss"] = max(peak["rss"], proc.memory_info().rss)
        return i, v

    cpu0 = proc.cpu_times()
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=threads) as ex:
        for i, v in ex.map(one, range(len(lon))):
            out[i] = v
    wall = time.time() - t0
    cpu1 = proc.cpu_times()
    cpu = (cpu1.user + cpu1.system) - (cpu0.user + cpu0.system)
    return np.vstack(out), {"wall_s": wall, "cpu_s": cpu, "heap_peak_gb": peak["heap"] / 1024 ** 3,
                            "rss_peak_gb": peak["rss"] / 1024 ** 3}


def indicators(tt: np.ndarray, ox: np.ndarray, oy: np.ndarray, d: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Per origin: accessibility, proximity and performance for both population grids."""
    cuts, radii = MEASURES[mode]
    dx, dy = d["x"].to_numpy(), d["y"].to_numpy()
    rows = []
    for i in range(len(ox)):
        dist = np.hypot(dx - ox[i], dy - oy[i])
        r = {"origin": i, "reachable": int((tt[i] < MAX_INT).sum())}
        for g in GRIDS:
            pop = d[f"pop_{g}"].to_numpy()
            for c, rad in zip(cuts, radii):
                acc = float(pop[tt[i] <= c].sum())
                prox = float(pop[dist <= rad].sum())
                r[f"acc{c}_{g}"], r[f"prox{c}_{g}"] = acc, prox
                r[f"perf{c}_{g}"] = 100 * acc / prox if prox > 0 else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


def bootstrap_se(x: np.ndarray, n: int, reps: int = 2000, seed: int = SEED) -> float:
    rng = np.random.default_rng(seed)
    x = x[np.isfinite(x)]
    idx = rng.integers(0, len(x), size=(reps, n))
    return float(x[idx].mean(axis=1).std(ddof=1))


def r5_check(tn, agg: str, variant: str) -> dict:
    """R5's own trip counts per feed and reference day vs the service layer (pipeline.gtfs_service)."""
    from pipeline import gtfs_service as gs
    chk = check_network(tn, agg, ref_days())
    info = json.loads((agg_dir(agg) / "inputs.json").read_text(encoding="utf-8"))["gtfs"][variant]["feeds"]
    for code, day in ref_days().items():
        ref = gs.active_trips(agg, day, variant).groupby("feed").size()
        drop = {f: int(info.get(f, {}).get("dropped_trips_by_day", {}).get(code, 0)) for f in ref.index}
        chk[f"service_layer_{code}"] = {k: int(v) for k, v in sorted(ref.items())}
        chk[f"dropped_no_coords_{code}"] = {k: v for k, v in sorted(drop.items()) if v}
        chk[f"match_{code}"] = {f: chk[f"trips_{code}"].get(f, 0) + drop[f] == int(n) for f, n in ref.items()}
    return chk


# ------------------------------------------------------------------ one city
def run_city(agg: str, variant: str, n: int, n_blocks: int, threads: int, extra: bool) -> None:
    run_dir = RUNS / f"{agg}_{variant}"
    run_dir.mkdir(parents=True, exist_ok=True)
    t_all = time.time()
    start()
    tn, net_info = network(agg, variant)
    net_info["versions"] = versions()
    net_info["r5_check"] = r5_check(tn, agg, variant)
    net_info["osm_bytes"] = (agg_dir(agg) / "osm.pbf").stat().st_size
    net_info["gtfs_bytes"] = sum(p.stat().st_size for p in (agg_dir(agg) / f"gtfs_{variant}").glob("*.zip"))
    print(json.dumps(net_info), flush=True)
    c = cells(agg)
    dests = dest_gdf(c)
    n_origins_full = int(c["in_fua"].sum())
    draws = pps_sample(c, n, SEED)
    uniq = np.unique(draws)
    ox, oy = c["x"].to_numpy()[uniq], c["y"].to_numpy()[uniq]
    lon, lat = to_ll(ox, oy)
    bench, perf, params = [], {}, {}

    def record(name, mode, window, tt, st, n_or, rides=8):
        bench.append({"agglomeration": agg, "variant": variant, "run": name, "mode": mode, "window": window,
                      "max_rides": rides, "threads": threads, "n_origins": n_or, "n_destinations": len(c),
                      "wall_s": st["wall_s"], "s_per_origin": st["wall_s"] / n_or,
                      "cpu_s_per_origin": st["cpu_s"] / n_or, "cpu_utilisation": st["cpu_s"] / st["wall_s"] / psutil.cpu_count(),
                      "reachable_per_origin": float((tt < MAX_INT).sum(axis=1).mean()),
                      "rows_per_origin_ttm": len(c), "heap_peak_gb": st["heap_peak_gb"], "rss_peak_gb": st["rss_peak_gb"],
                      "n_origins_full_250m": n_origins_full})
        print(f"{agg} {name}: {n_or} origins, {st['wall_s']:.1f}s, {st['wall_s'] / n_or:.3f} s/origin, "
              f"cpu {st['cpu_s'] / st['wall_s']:.1f} cores, heap {st['heap_peak_gb']:.1f} GB", flush=True)

    # warm-up (linkage of destinations per street mode is cached by R5 on first use)
    for mode in ("transit", "walk", "bike"):
        task, params[mode] = base_task(tn, dests, mode)
        t0 = time.time()
        route(tn, task, lon[:threads], lat[:threads], threads)
        params[mode]["warmup_s"] = round(time.time() - t0, 1)

    # main timings on the PPS sample
    tts = {}
    for mode in ("transit", "walk", "bike"):
        task, _ = base_task(tn, dests, mode)
        tt, st = route(tn, task, lon, lat, threads)
        record(f"{mode}_am" if mode == "transit" else mode, mode, "am_peak" if mode == "transit" else "-", tt, st, len(uniq))
        tts[mode] = tt
    # uniform sample of FUA cells: the full run routes every cell once, so its cost per origin is the uniform
    # mean (the population-weighted sample over-represents dense, expensive origins)
    rng = np.random.default_rng(SEED + 2)
    uidx = np.sort(rng.choice(np.flatnonzero(c["in_fua"].to_numpy()), size=min(n, int(c["in_fua"].sum())), replace=False))
    ulon, ulat = to_ll(c["x"].to_numpy()[uidx], c["y"].to_numpy()[uidx])
    for mode in ("transit", "walk", "bike"):
        task, _ = base_task(tn, dests, mode)
        tt, st = route(tn, task, ulon, ulat, threads)
        record(f"{mode}_am_uniform" if mode == "transit" else f"{mode}_uniform", mode,
               "am_peak" if mode == "transit" else "-", tt, st, len(uidx))
    # determinism: same sample again
    task, _ = base_task(tn, dests, "transit")
    tt2, st = route(tn, task, lon, lat, threads)
    record("transit_am_repeat", "transit", "am_peak", tt2, st, len(uniq))
    identical = bool(np.array_equal(tts["transit"], tt2))
    # thread scaling: one origin at a time
    k = min(16, len(uniq))
    task, _ = base_task(tn, dests, "transit")
    tt1, st = route(tn, task, lon[:k], lat[:k], 1)
    record("transit_am_1thread", "transit", "am_peak", tt1, st | {}, k)
    bench[-1]["threads"] = 1
    if extra:
        # evenly spread subset (uniq is sorted by cell_id, i.e. west to east), with its own AM reference
        sub = np.arange(len(uniq))[:: max(1, len(uniq) // 60)][:60]
        m, sx, sy, slon, slat = len(sub), ox[sub], oy[sub], lon[sub], lat[sub]
        task, _ = base_task(tn, dests, "transit")
        tt, st = route(tn, task, slon, slat, threads)
        record("transit_am_subset", "transit", "am_peak", tt, st, m)
        ref = indicators(tt, sx, sy, c, "transit")
        for window in ("midday", "evening", "saturday"):
            task, _ = base_task(tn, dests, "transit", window=window)
            tt, st = route(tn, task, slon, slat, threads)
            record(f"transit_{window}_subset", "transit", window, tt, st, m)
            w = indicators(tt, sx, sy, c, "transit")
            for cut in (30, 45):
                perf[f"{window}_minus_am_perf{cut}_subset"] = float((w[f"perf{cut}_ghsl_census_scaled"] - ref[f"perf{cut}_ghsl_census_scaled"]).mean())
        task, _ = base_task(tn, dests, "transit", walk_min=60)    # walk legs up to 5 km (OTP set-up of DG REGIO)
        tt, st = route(tn, task, slon, slat, threads)
        record("transit_am_walk5km_subset", "transit", "am_peak", tt, st, m)
        w5 = indicators(tt, sx, sy, c, "transit")
        for cut in (30, 45):
            perf[f"walk5km_minus_1km_perf{cut}_subset"] = float((w5[f"perf{cut}_ghsl_census_scaled"] - ref[f"perf{cut}_ghsl_census_scaled"]).mean())
        task, _ = base_task(tn, dests, "transit", max_min=45)    # cap at the largest cutoff used
        tt, st = route(tn, task, slon, slat, threads)
        record("transit_am_max45min_subset", "transit", "am_peak", tt, st, m)
        p45 = indicators(tt, sx, sy, c, "transit")
        perf["max45min_minus_60_perf45_subset"] = float((p45["perf45_ghsl_census_scaled"] - ref["perf45_ghsl_census_scaled"]).mean())
        task, _ = base_task(tn, dests, "transit", max_rides=3)
        tt, st = route(tn, task, slon, slat, threads)
        record("transit_am_max3rides_subset", "transit", "am_peak", tt, st, m, rides=3)
        p3 = indicators(tt, sx, sy, c, "transit")
        for cut in (30, 45):
            perf[f"max3rides_minus_8_perf{cut}_subset"] = float((p3[f"perf{cut}_ghsl_census_scaled"] - ref[f"perf{cut}_ghsl_census_scaled"]).mean())
        task, _ = base_task(tn, dests, "bike", lts=4)
        tt, st = route(tn, task, slon, slat, threads)
        record("bike_lts4_subset", "bike", "-", tt, st, m)
        b4 = indicators(tt, sx, sy, c, "bike")
        b3 = indicators(tts["bike"][sub], sx, sy, c, "bike")
        perf["bike_lts4_minus_lts3_perf30_subset"] = float((b4["perf30_ghsl_census_scaled"] - b3["perf30_ghsl_census_scaled"]).mean())
        perf["subset_mean_am_perf30"] = float(ref["perf30_ghsl_census_scaled"].mean())
        perf["subset_mean_am_perf45"] = float(ref["perf45_ghsl_census_scaled"].mean())

    # indicators on the sample (per draw, Hansen-Hurwitz)
    pos = {u: i for i, u in enumerate(uniq)}
    di = np.array([pos[d] for d in draws])
    sample_rows = []
    for mode in ("transit", "walk", "bike"):
        ind = indicators(tts[mode], ox, oy, c, mode)
        ind["cell_id"] = c["cell_id"].to_numpy()[uniq]
        ind.insert(0, "mode", mode)
        sample_rows.append(ind)
        cuts, _ = MEASURES[mode]
        for cut in cuts:
            for g in GRIDS:
                x = ind[f"perf{cut}_{g}"].to_numpy()[di]
                key = f"{mode}_perf{cut}_{g}"
                if g == "ghsl_raw":   # draws are census-weighted: reweight to raw population
                    wr = (c["pop_ghsl_raw"].to_numpy()[uniq] / np.maximum(c["pop_ghsl_census_scaled"].to_numpy()[uniq], 1e-9))[di]
                    perf[key] = float(np.nansum(x * wr) / wr[np.isfinite(x)].sum())
                    continue
                perf[key] = float(np.nanmean(x))
                perf[key + "_se_n" + str(n)] = bootstrap_se(x, n)
                for nn in (500, 2000, 5000):
                    perf[key + f"_se_n{nn}"] = perf[key + "_se_n" + str(n)] * np.sqrt(n / nn)
                acc = ind[f"acc{cut}_{g}"].to_numpy()[di]
                prox = ind[f"prox{cut}_{g}"].to_numpy()[di]
                perf[key + "_ratio_of_means"] = float(100 * acc.mean() / prox.mean())
                core = c["in_core"].to_numpy()[uniq][di]       # origins in the city proper (closer to DG REGIO)
                perf[key + "_core"] = float(np.nanmean(x[core]))
                perf[key + "_core_ratio_of_means"] = float(100 * acc[core].mean() / prox[core].mean())
                perf[key + "_core_draws"] = int(core.sum())
    pd.concat(sample_rows, ignore_index=True).to_parquet(run_dir / "sample_indicators.parquet")

    # 500 m aggregation test (transit AM, cluster sample)
    agg_res = {}
    if n_blocks:
        bs = block_sample(c, n_blocks, SEED)
        blon, blat = to_ll(bs["x"].to_numpy(), bs["y"].to_numpy())
        task, _ = base_task(tn, dests, "transit")
        tt, st = route(tn, task, blon, blat, threads)
        record("transit_am_blocks", "transit", "am_peak", tt, st, len(bs))
        ind = indicators(tt, bs["x"].to_numpy(), bs["y"].to_numpy(), c, "transit")
        bs = pd.concat([bs, ind.drop(columns="origin")], axis=1)
        rows = []
        for b, g in bs.groupby("block"):
            kids, cen = g[g["kind"] == "cell"], g[g["kind"] == "block_centroid"].iloc[0]
            w = kids["pop_ghsl_census_scaled"].to_numpy()
            r = {"block": b, "n_cells": len(kids), "pop": w.sum()}
            for cut in (30, 45):
                v = kids[f"perf{cut}_ghsl_census_scaled"].to_numpy()
                r[f"perf{cut}_cells"] = float(np.nansum(v * w) / w[np.isfinite(v)].sum())
                r[f"perf{cut}_centroid"] = float(cen[f"perf{cut}_ghsl_census_scaled"])
            rows.append(r)
        br = pd.DataFrame(rows)
        br.to_csv(run_dir / "blocks.csv", index=False)
        for cut in (30, 45):
            dlt = br[f"perf{cut}_centroid"] - br[f"perf{cut}_cells"]
            w = br["pop"]
            agg_res[f"perf{cut}_block_bias_popw"] = float((dlt * w).sum() / w.sum())
            agg_res[f"perf{cut}_block_abs_diff_median"] = float(dlt.abs().median())
            agg_res[f"perf{cut}_block_abs_diff_p90"] = float(dlt.abs().quantile(0.9))
            agg_res[f"perf{cut}_cells_level_popw"] = float((br[f"perf{cut}_cells"] * w).sum() / w.sum())
        agg_res["n_blocks"] = int(len(br))
        agg_res["full_500m_blocks"] = int(len(set(zip(np.floor((c.loc[c.in_fua, 'x'] - 125) / 500),
                                                       np.floor((c.loc[c.in_fua, 'y'] - 125) / 500)))))

    # OD pairs (Wroclaw only)
    od = []
    if agg == "wroclaw":
        od = od_pairs(tn, agg, variant)
    res = {"network": net_info, "params": params, "deterministic_repeat_identical": identical,
           "sample": {"draws": n, "unique_origins": int(len(uniq)), "seed": SEED, "n_origins_full_250m": n_origins_full,
                      "n_destinations": len(c), "pop_fua_census_scaled": float(c.loc[c.in_fua, "pop_ghsl_census_scaled"].sum())},
           "performance": perf, "aggregation_500m": agg_res, "od_pairs": od, "total_s": round(time.time() - t_all, 1)}
    (run_dir / "result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    pd.DataFrame(bench).to_csv(run_dir / "bench.csv", index=False)
    print(json.dumps(round_sig(perf), indent=1), flush=True)
    print(json.dumps(round_sig(agg_res), indent=1), flush=True)


def gtfs_names(agg: str, variant: str) -> dict:
    """(feed, route_id) -> short name and (feed, stop_id) -> stop name from the cleaned zips."""
    import zipfile
    from pipeline.r5_inputs import gtfs_paths
    out = {"route": {}, "stop": {}}
    for p in gtfs_paths(agg, variant):
        with zipfile.ZipFile(p) as z:
            r = pd.read_csv(z.open("routes.txt"), dtype=str).fillna("")
            st = pd.read_csv(z.open("stops.txt"), dtype=str).fillna("")
        for a, b, c in zip(r["route_id"], r["route_short_name"], r["route_long_name"]):
            out["route"][(p.stem, a)] = b or c or a
        for a, b in zip(st["stop_id"], st["stop_name"]):
            out["stop"][(p.stem, a)] = b or a
    return out


def od_pairs(tn, agg: str, variant: str) -> list[dict]:
    """R5 travel time (median 07-09) and a fastest itinerary at 08:00 for the Wroclaw check pairs."""
    import geopandas as gpd
    import shapely
    r5py = start()
    from r5py import DetailedItineraries, TransportMode, TravelTimeMatrix
    cfg = load_config()
    day = dt.datetime.fromisoformat(cfg["reference_day"])
    o = gpd.GeoDataFrame({"id": [p[0] for p in OD_PAIRS]}, geometry=[shapely.Point(*p[1]) for p in OD_PAIRS], crs="EPSG:4326")
    # distinct ids: r5py sets the travel time to 0 where from_id == to_id
    d = gpd.GeoDataFrame({"id": ["to: " + p[0] for p in OD_PAIRS]}, geometry=[shapely.Point(*p[2]) for p in OD_PAIRS], crs="EPSG:4326")
    common = dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], speed_walking=WALK_KMH,
                  max_time=dt.timedelta(minutes=90), max_time_walking=dt.timedelta(minutes=12))
    names = gtfs_names(agg, variant)
    out = []
    for i, name in enumerate(o["id"]):
        ttm = TravelTimeMatrix(tn, origins=o.iloc[[i]], destinations=d.iloc[[i]], departure=day.replace(hour=7),
                               departure_time_window=dt.timedelta(hours=2), percentiles=[25, 50, 75], **common)
        di = DetailedItineraries(tn, origins=o.iloc[[i]], destinations=d.iloc[[i]], departure=day.replace(hour=8),
                                 departure_time_window=dt.timedelta(minutes=10), **common)
        di = pd.DataFrame(di.drop(columns="geometry"))
        opts = []
        for opt, g in di.groupby("option"):
            legs = []
            for r in g.itertuples():
                txt = str(r.transport_mode).replace("TransportMode.", "")
                if isinstance(r.route_id, str) and r.route_id:
                    txt += f" {names['route'].get((r.feed, r.route_id), r.route_id)}: "                            f"{names['stop'].get((r.feed, r.start_stop_id), r.start_stop_id)} -> "                            f"{names['stop'].get((r.feed, r.end_stop_id), r.end_stop_id)}"
                txt += f" {pd.Timedelta(r.travel_time).total_seconds() / 60:.1f} min"
                if pd.notna(r.wait_time) and pd.Timedelta(r.wait_time) > pd.Timedelta(0):
                    txt += f" (wait {pd.Timedelta(r.wait_time).total_seconds() / 60:.1f} min)"
                legs.append(txt)
            tot = g["travel_time"].sum() + g["wait_time"].fillna(pd.Timedelta(0)).sum()
            opts.append({"option": int(opt), "departure": str(g["departure_time"].min()),
                         "total_min": round(pd.Timedelta(tot).total_seconds() / 60, 1), "legs": legs})
        opts = sorted(opts, key=lambda x: (x["total_min"], x["departure"]))[:3]
        r = ttm.iloc[0]
        out.append({"pair": name, "origin": OD_PAIRS[i][1], "destination": OD_PAIRS[i][2],
                    "tt_p25": r.get("travel_time_p25"), "tt_p50": r.get("travel_time_p50"), "tt_p75": r.get("travel_time_p75"),
                    "itineraries_0800": opts})
        print(json.dumps(out[-1], default=str), flush=True)
    return out


# ------------------------------------------------------------------ cost model
# fare-integration networks per city (RAPORT §8: strict + broad variant where single and period tickets differ)
FARE_VARIANTS = {"warszawa": 1, "krakow": 2, "wroclaw": 2, "poznan": 2, "lodz": 2, "trojmiasto": 1, "gzm": 1}
JOBS_CITIES = {"warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto"}   # Gdansk only in Trojmiasto
CURVE_MINUTES = 61          # stored per origin: population reachable by minute 0..60 (cumulative)


def origin_counts(agg: str) -> dict:
    c = cells(agg)
    f = c[c["in_fua"]]
    blocks = set(zip(np.floor((f["x"] - 125) / 500).astype(int), np.floor((f["y"] - 125) / 500).astype(int)))
    return {"n250": int(len(f)), "n500": int(len(blocks)), "n_dest": int(len(c))}


def cost_estimate(bench: pd.DataFrame) -> pd.DataFrame:
    """Hours of routing (20 threads on this PC) and disk per element of brief §4.6, per city and origin grid."""
    b = bench[bench["variant"] == "all"].set_index(["agglomeration", "run"])["s_per_origin"]
    rows = []
    aggs = sorted(bench["agglomeration"].unique())
    fac = {}
    for w in ("midday", "evening", "saturday", "max3rides", "max45min"):
        r = [b[(a, f"transit_{w}_subset" if w in ("midday", "evening", "saturday") else f"transit_am_{w}_subset")]
             / b[(a, "transit_am_subset")] for a in aggs if (a, "transit_am_subset") in b.index]
        fac[w] = float(np.mean(r)) if r else 1.0
    for a in aggs:
        oc = origin_counts(a)
        am = b[(a, "transit_am_uniform")] if (a, "transit_am_uniform") in b.index else b[(a, "transit_am")]
        wk = b[(a, "walk_uniform")] if (a, "walk_uniform") in b.index else b[(a, "walk")]
        bk = b[(a, "bike_uniform")] if (a, "bike_uniform") in b.index else b[(a, "bike")]

        def f(w):
            key = (a, f"transit_{w}_subset") if w in ("midday", "evening", "saturday") else (a, f"transit_am_{w}_subset")
            return b[key] / b[(a, "transit_am_subset")] if key in b.index else fac[w]

        el = [("transit_am", "AM 7-9, per feed variant", am, 2),
              ("transit_midday", "10-14, per feed variant", am * f("midday"), 2),
              ("transit_evening", "20-22, per feed variant", am * f("evening"), 2),
              ("transit_saturday", "Sat 10-14, per feed variant", am * f("saturday"), 2),
              ("transit_max2transfers", "AM, max 3 rides, per feed variant", am * f("max3rides"), 2),
              ("transit_fare_network", "AM, common-ticket network(s), official feeds", am, FARE_VARIANTS[a]),
              ("walk", "street only", wk, 1),
              ("bike", "street only, LTS 3", bk, 1),
              ("population_grids", "2nd grid from the same travel times", 0.0, 1),
              ("jobs", "same travel times, other weights" if a in JOBS_CITIES else "no data (GZM)", 0.0, 1),
              ("from_centre", "cells within 1 km of centre + hub, all runs", 0.0, 1)]
        for key, note, spo, runs in el:
            for grid, n in (("250m", oc["n250"]), ("500m", oc["n500"])):
                hours = spo * n * runs / 3600
                curves = 0 if spo == 0 else n * runs * CURVE_MINUTES * (3 if a in JOBS_CITIES else 2) * 4
                rows.append({"agglomeration": a, "element": key, "note": note, "origin_grid": grid, "n_origins": n,
                             "runs": runs, "s_per_origin": sig(spo, 4), "hours": sig(hours, 4),
                             "curves_mb": sig(curves / 1e6, 4)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ report
def report() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    runs = sorted(p for p in RUNS.glob("*") if (p / "result.json").exists())
    bench = pd.concat([pd.read_csv(p / "bench.csv") for p in runs], ignore_index=True)
    for col in bench.columns:
        if bench[col].dtype.kind == "f":
            bench[col] = bench[col].map(lambda v: sig(v, 4))
    bench = bench.sort_values(["agglomeration", "variant", "run"], kind="stable")
    bench.to_csv(OUT / "benchmark.csv", index=False, lineterminator="\n")
    res = {p.name: json.loads((p / "result.json").read_text(encoding="utf-8")) for p in runs}
    nets = []
    for name, r in res.items():
        n = r["network"]
        b = n.get("first_build") or n
        chk = n["r5_check"]
        nets.append({"agglomeration": n["agglomeration"], "variant": n["variant"], "build_s": b["seconds"],
                     "build_heap_peak_gb": b.get("heap_peak_gb"), "build_rss_peak_gb": b.get("rss_peak_gb"),
                     "load_from_cache_s": n["seconds"] if n["loaded_from_cache"] else None,
                     "network_mb": b["network_bytes"] / 1e6, "mapdb_mb": b.get("mapdb_bytes", 0) / 1e6,
                     "cache_dir_mb": b["cache_bytes"] / 1e6, "osm_pbf_mb": n["osm_bytes"] / 1e6,
                     "gtfs_zips_mb": n["gtfs_bytes"] / 1e6, "patterns": chk["patterns"], "stops": chk["stops"],
                     "stops_unlinked": chk["stops_unlinked"], "trips_wed_r5": sum(chk["trips_WED"].values()),
                     "trips_sat_r5": sum(chk["trips_SAT"].values()),
                     "r5_trips_equal_service_layer": all(chk["match_WED"].values()) and all(chk["match_SAT"].values()),
                     "r5_warnings": len(b.get("r5_warnings", []))})
    nets = pd.DataFrame(nets).sort_values(["agglomeration", "variant"])
    nets = nets.apply(lambda col: col.map(lambda v: sig(v, 4)) if col.dtype.kind == "f" else col)
    nets.to_csv(OUT / "networks.csv", index=False, lineterminator="\n")
    cost_estimate(pd.read_csv(OUT / "benchmark.csv")).to_csv(OUT / "cost_estimate.csv", index=False, lineterminator="\n")
    summary = {name: {"performance": round_sig(r["performance"]), "aggregation_500m": round_sig(r["aggregation_500m"]),
                      "sample": r["sample"], "deterministic_repeat_identical": r["deterministic_repeat_identical"],
                      "params": r["params"], "od_pairs": r["od_pairs"]} for name, r in res.items()}
    from pipeline.common import write_json
    write_json(OUT / "sample_summary.json", summary)
    v = next(iter(res.values()))["network"]["versions"]
    from pipeline import gtfs_service as gs
    feeds = sorted({f"gtfs_{f}" for a in gs.PHASE1 for f in gs.feeds_for(a, "all")})
    write_meta(OUT, "r5_benchmark", inputs=["osm_poland_pbf", *feeds], started=t0,
               extra={"versions": v, "runs": [p.name for p in runs], "seed": SEED,
                      "note": "benchmark and sample sanity only; not the full accessibility run"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agg")
    ap.add_argument("--variant", default="all")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--blocks", type=int, default=30)
    ap.add_argument("--threads", type=int, default=20)
    ap.add_argument("--no-extra", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--report", action="store_true")
    a, _ = ap.parse_known_args()
    if a.report:
        report()
        return
    if a.build_only:
        start()
        if a.rebuild and network_dir(a.agg, a.variant).exists():
            import shutil
            shutil.rmtree(network_dir(a.agg, a.variant))
        tn, info = network(a.agg, a.variant)
        info["versions"] = versions()
        info["r5_check"] = r5_check(tn, a.agg, a.variant)
        print(json.dumps(info), flush=True)
        return
    run_city(a.agg, a.variant, a.n, a.blocks, a.threads, not a.no_extra)


if __name__ == "__main__":
    main()
