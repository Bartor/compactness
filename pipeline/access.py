"""Phase 3, brief §4.6: accessibility and transport performance with R5, at full resolution, resumable.

    python -m pipeline.access run [--agg wroclaw ...] [--max-priority N] [--threads 20] [--xmx 16G]
    python -m pipeline.access status [--agg ...] [--max-priority N]
    python -m pipeline.access aggregate          # results/ from whatever is finished (pipeline.access_aggregate)

What is computed (decisions of 2026-11-23/24, see results/qa/access/access.md)
* origins: every populated 250 m cell (either population grid) with centre in the FUA; destinations: every
  populated cell in FUA + 15 km, plus cells holding jobs (pipeline.access_inputs).  No sampling.
* per origin and unit, the destination weight reachable within 5, 10, ..., 60 min for four weights: census-scaled
  population, raw GHSL population, jobs (Goliszek; city proper only) and census-scaled population of the city
  proper (benchmark only).  Proximity, performance and every aggregate are derived later from these sums
  (pipeline.access_aggregate), so the two population grids and jobs need no extra routing.
* transit: R5 TRANSIT + WALK, departures every minute in the window, 50th percentile over departures, max trip
  60 min, walk 5 km/h with R5 maxWalkTime 12 min (= 1 km) per access / egress leg.  Because that limit also caps
  walk-only trips inside a transit request, the travel time used is, per origin-destination pair,
  min(transit median, walk-only time without the 12-min cap) BEFORE any cutoff is applied, so that "public
  transport + walking" is never worse than walking alone.  min() with a constant commutes with the median over
  departures, so this equals the median of the per-departure minimum.  The walk-only times come from the walk
  unit of the same agglomeration (stored sparse next to its chunks) and are routed once.
* walk: 5 km/h, 60 min.  bike: 15 km/h, 60 min, R5 level of traffic stress <= 3 (r5py default) and <= 4.
* transfers: R5's regional computation returns only travel times; the number of transfers is estimated on a
  population-weighted sample of origin-destination pairs with r5py DetailedItineraries (unit transfers_am).
* odpairs: 3-5 named origin-destination pairs per city with a specific departure time (brief §7.4), for a later
  manual comparison with a journey planner (no planner is queried here).

Units of work = (agglomeration, network variant, scenario), processed in chunks of CHUNK origins (sorted by
cell_id).  Each chunk is written to data/interim/access/<agg>/<network>/<scenario>/chunk_<k>.parquet by atomic
rename; manifest.json holds the unit signature (R5 input files, origin/destination sets and weights, scenario
parameters, code version, R5 version, chunk size).  A unit whose signature changed is wiped and recomputed;
finished chunks are skipped, so the run can be killed at any moment and restarted with the same command.
Network variants: "all" and "official" feed sets; "street" = walk / bike (routed on the "all" network, whose
street layer does not depend on the feeds).  A common-ticket network can be added later as one more network
variant ("fare_<name>", GTFS zips in data/interim/r5/<agg>/gtfs_fare_<name>/) plus one UNITS entry; nothing
else is recomputed.

Order (results arrive progressively): priority 1 (transit AM all feeds, walk, bike LTS 3 and 4, transfers sample,
OD pairs) for all 7 agglomerations, smallest first; then priority 2 (transit AM, official feeds); 3 (midday,
evening, Saturday; all feeds); 4 (max 3 rides, AM, all feeds); 5 (secondary windows, official feeds); 6 (direct
trips only: max 1 ride, AM, all feeds; added 2026-11-24 for the transfer-dependence measure).  Within an
agglomeration the walk unit runs first because transit units reuse its walk-only times.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gc
import hashlib
import json
import os
import sys
import threading
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="The provided departure time window is below 5 minutes")

import numpy as np
import pandas as pd

from pipeline import access_inputs as AI
from pipeline.common import RESULTS, load_config

CODE_VERSION = "access-2026-11-25.1"      # bump when the routing / reduction code changes (invalidates chunks)
CHUNK = 1000
MAX_INT = 2 ** 31 - 1
WALK_KMH, BIKE_KMH = 5.0, 15.0
WALK_ACCESS_MIN = 12                       # 1 km at 5 km/h, per access / egress leg (brief: "max dojście 1 km")
MAX_MIN = 60
AGGS_BY_SIZE = ["trojmiasto", "poznan", "wroclaw", "gzm", "lodz", "krakow", "warszawa"]   # FUA origin cells
RUN_LOG = AI.ACCESS_INT / "run.log"
CFG = load_config()

# scenario -> parameters (kind: walk / bike / transit / itineraries / odpairs)
SCENARIOS: dict[str, dict] = {
    "walk": {"kind": "walk"},
    "bike_lts3": {"kind": "bike", "lts": 3},
    "bike_lts4": {"kind": "bike", "lts": 4},
    "pt_am": {"kind": "transit", "window": "am_peak", "rides": 8},
    "pt_midday": {"kind": "transit", "window": "midday", "rides": 8},
    "pt_evening": {"kind": "transit", "window": "evening", "rides": 8},
    "pt_saturday": {"kind": "transit", "window": "saturday", "rides": 8},
    "pt_am_max3rides": {"kind": "transit", "window": "am_peak", "rides": 3},
    "pt_am_direct": {"kind": "transit", "window": "am_peak", "rides": 1},     # no transfers (one ride at most)
    "transfers_am": {"kind": "itineraries", "window": "am_peak", "n_pairs": 200, "seed": 20261125, "slot_min": 5},
    "odpairs": {"kind": "odpairs", "seed": 20261125},
}
# (priority, network variant, scenarios) in run order; the walk unit is listed first (transit reuses its times)
UNITS: list[tuple[int, str, list[str]]] = [
    (1, "street", ["walk"]),
    (1, "all", ["pt_am"]),
    (1, "street", ["bike_lts3", "bike_lts4"]),
    (1, "all", ["transfers_am", "odpairs"]),
    (2, "official", ["pt_am"]),
    (3, "all", ["pt_midday", "pt_evening", "pt_saturday"]),
    (4, "all", ["pt_am_max3rides"]),
    (5, "official", ["pt_midday", "pt_evening", "pt_saturday"]),
    (6, "all", ["pt_am_direct"]),
    # future: (6, "fare_<name>", ["pt_am"])  -- common-ticket network, official mask (access_inputs.mask_variant)
]


def unit_list(aggs: list[str], max_priority: int) -> list[tuple[int, str, str, str]]:
    """[(priority, agg, network, scenario)] in run order: priority, then agglomeration (smallest first)."""
    order = [a for a in AGGS_BY_SIZE if a in aggs]
    out = []
    for pr in sorted({u[0] for u in UNITS}):
        if pr > max_priority:
            continue
        for agg in order:
            for p, net, scens in UNITS:
                if p == pr:
                    out += [(p, agg, net, s) for s in scens]
    return out


# ------------------------------------------------------------------ logging
def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def hms(s: float) -> str:
    s = max(0, int(round(s)))
    return f"{s // 3600}:{(s // 60) % 60:02d}:{s % 60:02d}"


# ------------------------------------------------------------------ signatures and files
_SIG_CACHE: dict = {}


def network_for(net: str) -> str:
    return "all" if net == "street" else net


def net_signature(agg: str, net: str) -> str:
    """Signature of the R5 inputs: street units depend on the OSM extract only, transit units on OSM + GTFS."""
    key = (agg, net)
    if key not in _SIG_CACHE:
        from pipeline.r5_inputs import gtfs_paths, inputs_signature, osm_path
        if net == "street":
            h = hashlib.sha1()
            with open(osm_path(agg), "rb") as f:
                for b in iter(lambda: f.read(1 << 22), b""):
                    h.update(b)
            _SIG_CACHE[key] = "osm:" + h.hexdigest()[:16]
        else:
            if not gtfs_paths(agg, net):
                raise FileNotFoundError(f"no GTFS zips for {agg}/{net}: run python -m pipeline.r5_inputs")
            _SIG_CACHE[key] = inputs_signature(agg, net)
    return _SIG_CACHE[key]


def unit_dir(agg: str, net: str, scen: str) -> Path:
    return AI.ACCESS_INT / agg / net / scen


def unit_params(agg: str, net: str, scen: str) -> dict:
    p = {"scenario": scen, **SCENARIOS[scen], "network": net, "routed_on": network_for(net),
         "walk_kmh": WALK_KMH, "bike_kmh": BIKE_KMH, "max_min": MAX_MIN, "walk_access_min": WALK_ACCESS_MIN,
         "cutoffs": AI.CUTOFFS, "weights": AI.WEIGHTS, "chunk": CHUNK, "code_version": CODE_VERSION}
    k = SCENARIOS[scen]["kind"]
    if k in ("transit", "itineraries", "odpairs"):
        w = CFG["time_windows"][SCENARIOS[scen].get("window", "am_peak")]
        p["window_def"] = w
        p["day"] = CFG["reference_saturday"] if w["day"] == "saturday" else CFG["reference_day"]
    return p


def unit_signature(agg: str, net: str, scen: str) -> tuple[str, dict]:
    from pipeline.r5_env import R5_VERSION
    p = unit_params(agg, net, scen)
    parts = {"params": p, "net": net_signature(agg, net), "inputs": AI.inputs_hash(agg), "r5": R5_VERSION}
    if SCENARIOS[scen]["kind"] in ("transit", "itineraries"):
        parts["walk_unit"] = net_signature(agg, "street")      # transit reuses the walk unit's times
    s = hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return s, parts


def n_chunks(agg: str, scen: str) -> int:
    if SCENARIOS[scen]["kind"] in ("itineraries", "odpairs"):
        return 1
    return int(np.ceil(len(AI.origins(agg)) / CHUNK))


def chunk_path(d: Path, k: int, scen: str) -> Path:
    if SCENARIOS[scen]["kind"] in ("itineraries", "odpairs"):
        return d / "result.parquet"
    return d / f"chunk_{k:05d}.parquet"


def chunk_done(d: Path, k: int, scen: str) -> bool:
    p = chunk_path(d, k, scen)
    if not p.exists():
        return False
    if SCENARIOS[scen]["kind"] == "walk" and not (d / f"chunk_{k:05d}.walk.npz").exists():
        return False
    return True


def open_unit(agg: str, net: str, scen: str) -> tuple[Path, str]:
    """Create / validate the unit directory; wipe it when its signature changed."""
    d = unit_dir(agg, net, scen)
    sig, parts = unit_signature(agg, net, scen)
    man = d / "manifest.json"
    if d.exists():
        old = json.loads(man.read_text(encoding="utf-8")).get("signature") if man.exists() else None
        if old != sig:
            n = sum(1 for _ in d.glob("chunk_*")) + sum(1 for _ in d.glob("result*"))
            log(f"{agg} {net}/{scen}: signature changed ({old} -> {sig}); removing {n} stale files")
            for f in d.iterdir():
                f.unlink()
    d.mkdir(parents=True, exist_ok=True)
    if not man.exists():
        atomic_text(man, json.dumps({"signature": sig, **parts, "n_origins": int(len(AI.origins(agg))),
                                     "n_destinations": int(len(AI.destinations(agg))),
                                     "n_chunks": n_chunks(agg, scen)}, indent=1, sort_keys=True, default=str))
    return d, sig


def unit_state(agg: str, net: str, scen: str) -> tuple[int, int]:
    """(chunks done with the current signature, chunks total)."""
    d = unit_dir(agg, net, scen)
    tot = n_chunks(agg, scen)
    man = d / "manifest.json"
    if not man.exists():
        return 0, tot
    try:
        sig, _ = unit_signature(agg, net, scen)
    except FileNotFoundError:
        return 0, tot
    if json.loads(man.read_text(encoding="utf-8")).get("signature") != sig:
        return 0, tot
    return sum(chunk_done(d, k, scen) for k in range(tot)), tot


def atomic_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False, compression="zstd")
    os.replace(tmp, path)


# ------------------------------------------------------------------ R5 tasks and routing
def window_departure(window: str) -> tuple[dt.datetime, dt.timedelta, str]:
    w = CFG["time_windows"][window]
    day = CFG["reference_saturday"] if w["day"] == "saturday" else CFG["reference_day"]
    h0, m0 = map(int, w["start"].split(":"))
    h1, m1 = map(int, w["end"].split(":"))
    dep = dt.datetime.fromisoformat(day).replace(hour=h0, minute=m0)
    return dep, dt.timedelta(hours=h1 - h0, minutes=m1 - m0), day


def make_task(tn, dests_gdf, scen: str):
    """Java RegionalTask template for one scenario (cloned per origin); returns (task, R5 parameter dict)."""
    from r5py import RegionalTask, TransportMode
    s = SCENARIOS[scen]
    if s["kind"] == "transit":
        dep, span, _ = window_departure(s["window"])
        kw = dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], departure=dep,
                  departure_time_window=span, percentiles=[50], max_time=dt.timedelta(minutes=MAX_MIN),
                  max_time_walking=dt.timedelta(minutes=WALK_ACCESS_MIN), speed_walking=WALK_KMH,
                  max_public_transport_rides=s["rides"])
    elif s["kind"] == "walk":
        dep, _, _ = window_departure("am_peak")
        kw = dict(transport_modes=[TransportMode.WALK], departure=dep, departure_time_window=dt.timedelta(minutes=1),
                  percentiles=[50], max_time=dt.timedelta(minutes=MAX_MIN), speed_walking=WALK_KMH)
    elif s["kind"] == "bike":
        dep, _, _ = window_departure("am_peak")
        kw = dict(transport_modes=[TransportMode.BICYCLE], departure=dep,
                  departure_time_window=dt.timedelta(minutes=1), percentiles=[50],
                  max_time=dt.timedelta(minutes=MAX_MIN), speed_cycling=BIKE_KMH,
                  max_bicycle_traffic_stress=s["lts"])
    else:
        raise ValueError(scen)
    rt = RegionalTask(tn, origin=None, destinations=dests_gdf, **kw)
    t = rt._regional_task
    info = {"r5_fromTime": int(t.fromTime), "r5_toTime": int(t.toTime), "r5_maxWalkTime_min": int(t.maxWalkTime),
            "r5_maxBikeTime_min": int(t.maxBikeTime), "r5_maxTripDurationMinutes": int(t.maxTripDurationMinutes),
            "r5_maxRides": int(t.maxRides), "r5_walkSpeed_ms": float(t.walkSpeed),
            "r5_bikeSpeed_ms": float(t.bikeSpeed), "r5_maxBikeTrafficStress": int(t.bikeTrafficStress),
            "r5_monteCarloDraws": int(t.monteCarloDraws)}
    return t, info


def travel_times(task, jnet, lon: float, lat: float) -> np.ndarray:
    import com.conveyal.r5
    t = task.clone()
    t.fromLat, t.fromLon = float(lat), float(lon)
    res = com.conveyal.r5.analyst.TravelTimeComputer(t, jnet).computeTravelTimes()
    return np.asarray(res.travelTimes.getValues()[0], dtype=np.int32).copy()


def reduce_sums(tt: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Weight reachable within each cutoff: (n_weights, n_cutoffs).  Reachable = travel time <= cutoff."""
    sel = np.flatnonzero(tt <= MAX_MIN)
    m = tt[sel]
    out = np.empty((W.shape[1], len(AI.CUTOFFS)))
    cut = np.asarray(AI.CUTOFFS)
    for k in range(W.shape[1]):
        cs = np.cumsum(np.bincount(m, weights=W[sel, k], minlength=MAX_MIN + 1))
        out[k] = cs[cut]
    return out


class Router:
    """One loaded R5 network at a time (switching costs 2-4 s from the cache, a first build 20-55 s)."""

    def __init__(self, threads: int):
        self.threads = threads
        self.key = None
        self.tn = None
        self.dests = None
        self.tasks = {}
        self.task_info = {}

    def get(self, agg: str, net: str):
        key = (agg, network_for(net))
        if self.key != key:
            from pipeline.r5_env import network, network_dir
            self.tn = None
            gc.collect()
            built = not any(network_dir(*key).glob("*.transport_network"))
            t0 = time.time()
            self.tn, info = network(*key)
            log(f"{agg}: network {key[1]} {'built' if built else 'loaded'} in {time.time() - t0:.0f} s")
            self.key = key
            self.dests = None
            self.tasks = {}
        if self.dests is None:
            import geopandas as gpd
            d = AI.destinations(agg)
            lon, lat = AI.TO4326.transform(d["x"].to_numpy(), d["y"].to_numpy())
            self.dests = gpd.GeoDataFrame({"id": d["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(lon, lat),
                                          crs="EPSG:4326")
        return self.tn, self.dests

    def task(self, scen: str):
        """Task template per scenario on the loaded network (R5 links the destination point set once per task)."""
        if scen not in self.tasks:
            self.tasks[scen], self.task_info[scen] = make_task(self.tn, self.dests, scen)
        return self.tasks[scen]


def walk_cache(agg: str, k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(unit_dir(agg, "street", "walk") / f"chunk_{k:05d}.walk.npz")
    return z["indptr"], z["idx"], z["tt"]


def route_chunk(router: Router, agg: str, net: str, scen: str, k: int) -> tuple[pd.DataFrame, dict | None, dict]:
    """Route one chunk of origins; returns (per-origin table, walk cache arrays or None, timing info)."""
    o = AI.origins(agg).iloc[k * CHUNK:(k + 1) * CHUNK]
    d = AI.destinations(agg)
    W = d[[f"w_{w}" for w in AI.WEIGHTS]].to_numpy(np.float64)
    tn, dests = router.get(agg, net)
    task = router.task(scen)
    jnet = tn._transport_network
    kind = SCENARIOS[scen]["kind"]
    if kind == "transit":
        wp, wi, wt = walk_cache(agg, k)
    lon, lat = o["lon"].to_numpy(), o["lat"].to_numpy()
    n = len(o)
    i_census = AI.WEIGHTS.index("census")

    def one(i):
        tt = travel_times(task, jnet, lon[i], lat[i])
        extra = None
        if kind == "transit":
            raw = reduce_sums(tt, W[:, [i_census]])[0]
            sl = slice(wp[i], wp[i + 1])
            ix = wi[sl]
            tt[ix] = np.minimum(tt[ix], wt[sl].astype(np.int32))   # transit + walk never worse than walking
            extra = raw
        elif kind == "walk":
            sel = np.flatnonzero(tt <= MAX_MIN)
            extra = (sel.astype(np.int32), tt[sel].astype(np.uint8))
        return reduce_sums(tt, W), int((tt <= MAX_MIN).sum()), extra

    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=router.threads) as ex:
        res = list(ex.map(one, range(n)))
    wall = time.time() - t0
    out = {"cell_id": o["cell_id"].to_numpy(), "n_reach60": np.array([r[1] for r in res], dtype=np.int32)}
    sums = np.stack([r[0] for r in res])           # (n, weights, cutoffs)
    for a, w in enumerate(AI.WEIGHTS):
        for b, c in enumerate(AI.CUTOFFS):
            out[f"acc_{w}_{c}"] = sums[:, a, b].astype(np.float32)
    if kind == "transit":   # transit alone (R5 output before the walk minimum), census grid, for QA
        raw = np.stack([r[2] for r in res])
        for b, c in enumerate(AI.CUTOFFS):
            if c in (15, 30, 45, 60):
                out[f"r5only_census_{c}"] = raw[:, b].astype(np.float32)
    walk = None
    if kind == "walk":
        lens = np.array([len(r[2][0]) for r in res], dtype=np.int64)
        walk = {"indptr": np.r_[0, np.cumsum(lens)].astype(np.int64),
                "idx": np.concatenate([r[2][0] for r in res]) if n else np.zeros(0, np.int32),
                "tt": np.concatenate([r[2][1] for r in res]) if n else np.zeros(0, np.uint8)}
    return pd.DataFrame(out), walk, {"wall_s": round(wall, 2), "n": n}


# ------------------------------------------------------------------ cost estimate (for ETA / status)
def _bench() -> pd.DataFrame:
    p = RESULTS / "qa" / "access" / "benchmark.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


_BENCH = None
# relative to the benchmark's 30-minute runs (bike 60 min and walk 60 min are measured on Wroclaw; transit windows
# from the benchmark subsets); calibrated at run time against finished chunks of the same scenario
FACTOR = {"walk": 2.4, "bike_lts3": 3.0, "bike_lts4": 3.6, "pt_am": 1.0, "pt_midday": 1.35, "pt_evening": 1.0,
          "pt_saturday": 1.3, "pt_am_max3rides": 0.9,
          "pt_am_direct": 0.6}
FIXED_S = {"transfers_am": 1200.0, "odpairs": 100.0}   # measured on Wroclaw (200 pairs: 1188 s; 7 pairs: 98 s)


def est_s_per_origin(agg: str, scen: str) -> float:
    global _BENCH
    if _BENCH is None:
        _BENCH = _bench()
    b = _BENCH[(_BENCH["agglomeration"] == agg) & (_BENCH["variant"] == "all")].set_index("run")["s_per_origin"] \
        if len(_BENCH) else pd.Series(dtype=float)
    base = {"walk": "walk_uniform", "bike_lts3": "bike_uniform", "bike_lts4": "bike_uniform"}.get(scen,
                                                                                                "transit_am_uniform")
    v = float(b.get(base, 0.01))
    if scen.startswith("pt_") and scen not in ("pt_am", "pt_am_direct"):
        sub = {"pt_midday": "transit_midday_subset", "pt_evening": "transit_evening_subset",
               "pt_saturday": "transit_saturday_subset", "pt_am_max3rides": "transit_am_max3rides_subset"}[scen]
        if sub in b and "transit_am_subset" in b:
            return v * float(b[sub]) / float(b["transit_am_subset"])
    return v * FACTOR.get(scen, 1.0)


def est_unit_s(agg: str, scen: str, chunks: list[int] | None = None) -> float:
    if scen in FIXED_S:
        return FIXED_S[scen] if chunks is None or chunks else 0.0
    n = len(AI.origins(agg))
    if chunks is None:
        cnt = n
    else:
        cnt = sum(min(CHUNK, n - k * CHUNK) for k in chunks)
    return est_s_per_origin(agg, scen) * cnt


def calibration() -> dict[str, float]:
    """measured / estimated seconds per scenario over all finished chunks with a timing sidecar."""
    num, den = {}, {}
    for f in AI.ACCESS_INT.glob("*/*/*/chunk_*.time.json"):
        try:
            t = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        scen, agg = f.parent.name, f.parent.parent.parent.name
        if scen not in SCENARIOS or scen in FIXED_S or agg not in AGGS_BY_SIZE:
            continue
        num[scen] = num.get(scen, 0.0) + t["wall_s"]
        den[scen] = den.get(scen, 0.0) + est_s_per_origin(agg, scen) * t["n"]
    out = {s: num[s] / den[s] for s in num if den[s] > 0}
    if out:   # scenarios without measurements take the mean ratio of the transit scenarios that have some
        tr = [v for s, v in out.items() if s.startswith("pt_")]
        if tr:
            for s in SCENARIOS:
                if s.startswith("pt_") and s not in out:
                    out[s] = float(np.mean(tr))
    return out


def remaining(units, cal) -> tuple[float, list[dict]]:
    rows, tot = [], 0.0
    for pr, agg, net, scen in units:
        done, total = unit_state(agg, net, scen)
        d = unit_dir(agg, net, scen)
        todo = [k for k in range(total) if not chunk_done(d, k, scen)] if done < total else []
        if done == 0:
            todo = list(range(total))
        s = est_unit_s(agg, scen, todo) * cal.get(scen, 1.0)
        tot += s
        rows.append({"priority": pr, "agg": agg, "network": net, "scenario": scen, "done": done, "total": total,
                     "remaining_h": s / 3600})
    return tot, rows


# ------------------------------------------------------------------ run
def run(aggs: list[str], max_priority: int, threads: int, xmx: str) -> None:
    from pipeline.r5_env import start
    units = unit_list(aggs, max_priority)
    log(f"run start: aggs={','.join(a for a in AGGS_BY_SIZE if a in aggs)} max_priority={max_priority} "
        f"threads={threads} xmx={xmx} units={len(units)} code={CODE_VERSION}")
    start(xmx=xmx)
    router = Router(threads)
    t_run = time.time()
    cal = calibration()
    left, _ = remaining(units, cal)
    log(f"estimated routing left: {left / 3600:.2f} h (calibration {json.dumps({k: round(v, 2) for k, v in cal.items()})})")
    for ui, (pr, agg, net, scen) in enumerate(units):
        d, sig = open_unit(agg, net, scen)
        tot = n_chunks(agg, scen)
        todo = [k for k in range(tot) if not chunk_done(d, k, scen)]
        tag = f"[P{pr} {ui + 1}/{len(units)}] {agg} {net}/{scen}"
        if not todo:
            continue
        kind = SCENARIOS[scen]["kind"]
        if kind in ("itineraries", "odpairs"):
            from pipeline import access_samples
            t0 = time.time()
            tn, _ = router.get(agg, net)
            df = access_samples.transfers(tn, agg, net, scen) if kind == "itineraries" else \
                access_samples.od_pairs(tn, agg, net, scen)
            atomic_parquet(df, chunk_path(d, 0, scen))
            atomic_text(d / "result.time.json", json.dumps({"wall_s": round(time.time() - t0, 1), "n": len(df)}))
            log(f"{tag}: {len(df)} rows in {time.time() - t0:.0f} s")
            continue
        for k in todo:
            if kind == "transit":
                wd = unit_dir(agg, "street", "walk")
                if not chunk_done(wd, k, "walk"):          # the walk unit of this agglomeration comes first
                    open_unit(agg, "street", "walk")
                    df, walk, tinfo = route_chunk(router, agg, "street", "walk", k)
                    np.savez(wd / f"chunk_{k:05d}.walk.tmp.npz", **walk)
                    os.replace(wd / f"chunk_{k:05d}.walk.tmp.npz", wd / f"chunk_{k:05d}.walk.npz")
                    atomic_parquet(df, chunk_path(wd, k, "walk"))
                    atomic_text(wd / f"chunk_{k:05d}.time.json", json.dumps(tinfo))
            df, walk, tinfo = route_chunk(router, agg, net, scen, k)
            if walk is not None:
                tmp = d / f"chunk_{k:05d}.walk.tmp.npz"
                np.savez(tmp, **walk)
                os.replace(tmp, d / f"chunk_{k:05d}.walk.npz")
            atomic_parquet(df, chunk_path(d, k, scen))
            atomic_text(d / f"chunk_{k:05d}.time.json", json.dumps(tinfo))
            if not (d / "r5_params.json").exists():
                atomic_text(d / "r5_params.json", json.dumps(router.task_info[scen], indent=1, sort_keys=True))
            cal = calibration()
            left, _ = remaining(units, cal)
            done = sum(chunk_done(d, j, scen) for j in range(tot))
            log(f"{tag} chunk {k + 1}/{tot}: {tinfo['n']} origins in {tinfo['wall_s']:.1f} s "
                f"({1000 * tinfo['wall_s'] / max(tinfo['n'], 1):.1f} ms/origin); unit {done}/{tot}; "
                f"elapsed {hms(time.time() - t_run)}; ETA {hms(left)}")
    log(f"run finished in {hms(time.time() - t_run)}")


def status(aggs: list[str], max_priority: int) -> None:
    units = unit_list(aggs, max_priority)
    cal = calibration()
    tot, rows = remaining(units, cal)
    df = pd.DataFrame(rows)
    df["state"] = np.where(df["done"] == df["total"], "done", np.where(df["done"] > 0, "partial", "pending"))
    pd.set_option("display.width", 200)
    print(df.assign(remaining_h=df["remaining_h"].round(3)).to_string(index=False))
    print(f"\nunits done {int((df.state == 'done').sum())}/{len(df)}; chunks {int(df.done.sum())}/{int(df.total.sum())}; "
          f"estimated routing left {tot / 3600:.2f} h (+ network builds ~0.5 min each, JVM start ~1 min)")
    print("calibration (measured / benchmark-based estimate): " +
          (", ".join(f"{k} {v:.2f}" for k, v in sorted(cal.items())) or "none yet"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["run", "status", "aggregate"])
    ap.add_argument("--agg", nargs="+", default=AGGS_BY_SIZE, choices=AGGS_BY_SIZE)
    ap.add_argument("--max-priority", type=int, default=6)
    ap.add_argument("--threads", type=int, default=20)
    ap.add_argument("--xmx", default="16G")
    a, _ = ap.parse_known_args()
    sys.argv = sys.argv[:1]       # r5py parses sys.argv when imported; keep only what r5_env.start adds
    if a.command == "run":
        run(a.agg, a.max_priority, a.threads, a.xmx)
    elif a.command == "status":
        status(a.agg, a.max_priority)
    else:
        from pipeline.access_aggregate import main as agg_main
        agg_main()


if __name__ == "__main__":
    main()
