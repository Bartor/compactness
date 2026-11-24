"""Population-weighted sample of routed public-transport trips, Wednesday 07:00-09:00 (ROADMAP item 14, node use
from item 4).  Validation step: transfer shares, where transfers happen, walk and wait shares of trip time.

    python -m pipeline.trips_sample plan  [--agg ...]                 # draw origins and departure slots (no JVM)
    python -m pipeline.trips_sample route [--agg ...] [--threads 4] [--xmx 8G]   # resumable, chunks + .sig
    python -m pipeline.trips_sample status
    python -m pipeline.trips_sample nik   [--threads 4] [--xmx 8G]    # 15 NIK P/25/019 suburban pairs
    python -m pipeline.trips_sample analyse                           # tables, node_use.parquet (no JVM)

Sample (per agglomeration and destination set)
* Trips are independent draws: origin cell with probability proportional to census-scaled residents (FUA cells,
  production origin frame), departure slot [07:00 + m, 07:00 + m + 5 min), m uniform in 0..115.
* Destination: one cell drawn with probability proportional to residents ("res") or to jobs ("jobs", only where
  the Goliszek jobs grid exists) among the cells reachable within 60 min from the origin, by the production travel
  time rule min(R5 transit median 07-09, walk-only time) (destination frame: FUA + 15 km), excluding the origin cell.
* Itinerary: R5 v7.5.1 regional task to the one destination with includePathResults; R5 range-RAPTOR returns the
  optimal path for every departure minute of the slot (fewest rides among equal arrival times); the fastest
  departure (total time, then rides, then the earlier minute) is kept.  Same parameters as the production transit
  computation (walk 5 km/h, access / egress <= 12 min, up to 8 rides, all feeds), except the trip-duration limit,
  which is 90 min so that a slot slower than the 07-09 median still yields a path.
* Each trip is a self-weighting draw (weight 1), so shares are plain proportions with binomial (Wilson) intervals.

Why not r5py DetailedItineraries: ~6 s per pair (200 pairs ~20 min per city, access_samples.py) and an 8-16 GB
McRaptor heap; the regional path results take ~0.1 s per pair and use the same RAPTOR as the production numbers.

Files: plan and chunks under data/interim/trips/<agg>/, network copies under data/interim/trips/r5/<agg>/,
QA under results/qa/trips/, layer results/layers/node_use.parquet.  Production files are read only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import shutil
import struct
import threading
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="The provided departure time window is below 5 minutes")

import numpy as np
import pandas as pd

from pipeline import access_inputs as AI
from pipeline.common import INTERIM, RESULTS, load_config

CFG = load_config()
REF_DAY = CFG["reference_day"]
AGGS = ["trojmiasto", "poznan", "wroclaw", "gzm", "lodz", "krakow", "warszawa"]   # smallest network first
CODE_VERSION = "trips-2026-11-24.2"
SEED = 20261126
N_TRIPS = {"res": 15000, "jobs": 5000}
MAX_DRAWS = 50000                 # length of the per-set uniform stream (prefix-stable when N grows)
CHUNK = 500
SLOT_MIN = 5
N_SLOTS = 116                     # m in 0..115 -> last slot 08:55-09:00
REACH_MAX_MIN = 60
PATH_MAX_MIN = 90
MIN_FREE_GB = 14.0
OUT = INTERIM / "trips"
QA = RESULTS / "qa" / "trips"
PROGRESS = INTERIM / "proposals" / "trips_progress.md"
SET_CODE = {"res": 1, "jobs": 2}
AGG_CODE = {a: i + 1 for i, a in enumerate(sorted(AGGS))}
INT_MAX = 2 ** 31 - 1


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def sets_for(agg: str) -> list[str]:
    return ["res", "jobs"] if agg in AI.JOBS_AGGS else ["res"]


# ------------------------------------------------------------------ plan (no JVM)
def plan_path(agg: str) -> Path:
    return OUT / agg / "plan.parquet"


def make_plan(agg: str) -> pd.DataFrame:
    o = AI.origins(agg)
    w = o["w_census"].to_numpy(float)
    cdf = np.cumsum(w) / w.sum()
    rows = []
    for s in sets_for(agg):
        rng = np.random.default_rng([SEED, AGG_CODE[agg], SET_CODE[s]])
        u = rng.random(MAX_DRAWS)
        m = rng.integers(0, N_SLOTS, MAX_DRAWS)
        n = N_TRIPS[s]
        oi = np.minimum(np.searchsorted(cdf, u[:n], side="right"), len(o) - 1)
        rows.append(pd.DataFrame({"set": s, "trip": np.arange(n), "origin_idx": oi,
                                  "origin": o["cell_id"].to_numpy()[oi], "minute": m[:n]}))
    p = pd.concat(rows, ignore_index=True)
    p["chunk"] = p["trip"] // CHUNK
    return p


def plan(aggs: list[str]) -> None:
    for agg in aggs:
        p = make_plan(agg)
        f = plan_path(agg)
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.exists() and pd.read_parquet(f).equals(p):
            log(f"{agg}: plan unchanged ({len(p)} trips)")
            continue
        p.to_parquet(f.with_suffix(".tmp"), index=False)
        os.replace(f.with_suffix(".tmp"), f)
        log(f"{agg}: plan written, {len(p)} trips, {p.origin.nunique()} distinct origins")


# ------------------------------------------------------------------ network copy and R5 helpers
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
        shutil.copyfile(f, dst / (f.name + ".tmp"))
        os.replace(dst / (f.name + ".tmp"), tgt)
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


def pointset(lons, lats):
    """FreeFormPointSet in r5py's byte format (count, ids, lats, lons, opportunities)."""
    import com.conveyal.r5
    import java.io
    import jpype
    b = bytearray(struct.pack(">i", len(lons)))
    for k in range(len(lons)):
        s = str(k).encode()
        b += struct.pack(">H", len(s)) + s
    for v in lats:
        b += struct.pack(">d", float(v))
    for v in lons:
        b += struct.pack(">d", float(v))
    for _ in lons:
        b += struct.pack(">d", 0.0)
    return com.conveyal.r5.analyst.FreeFormPointSet(java.io.ByteArrayInputStream(jpype.JArray(jpype.JByte)(bytes(b))))


def wait_for_memory() -> None:
    import psutil
    while True:
        free = psutil.virtual_memory().available / 2 ** 30
        if free >= MIN_FREE_GB:
            return
        log(f"only {free:.1f} GB free (< {MIN_FREE_GB}); waiting 5 min")
        time.sleep(300)


ROUTE_CLASS = [((0, 0), "tram"), ((900, 999), "tram"), ((1, 1), "metro"), ((400, 499), "metro"), ((2, 2), "rail"),
               ((100, 199), "rail"), ((3, 3), "bus"), ((700, 799), "bus"), ((200, 299), "bus"), ((11, 11), "trolleybus"),
               ((800, 899), "trolleybus"), ((4, 4), "ferry"), ((1000, 1099), "ferry")]


def route_class(rt: int) -> str:
    for (a, b), c in ROUTE_CLASS:
        if a <= rt <= b:
            return c
    return "other"


def _best(task, jnet, olon, olat, dlon, dlat, minute: int, max_rides: int | None = None):
    """(key, RouteSequence, Iteration) of the fastest departure in the slot, or None.  key = (s, rides, dep)."""
    import com.conveyal.r5
    import jpype
    t = task.clone()
    t.fromLat, t.fromLon = float(olat), float(olon)
    t.destinationPointSets = jpype.JArray(com.conveyal.r5.analyst.PointSet)([pointset([dlon], [dlat])])
    t.includePathResults = True
    t.fromTime = int(task.fromTime) + 60 * int(minute)
    t.toTime = t.fromTime + 60 * SLOT_MIN
    t.maxTripDurationMinutes = PATH_MAX_MIN
    if max_rides is not None:
        t.maxRides = int(max_rides)
    res = com.conveyal.r5.analyst.TravelTimeComputer(t, jnet).computeTravelTimes()
    mm = res.paths.iterationsForPathTemplates[0]
    best = None
    if mm is None:
        return None
    for rs in mm.keySet():
        nr = 0 if rs.routes is None else int(rs.routes.size())
        for it in mm.get(rs):
            key = (int(it.totalTime), nr, int(it.departureTime))
            if best is None or key < best[0]:
                best = (key, rs, it)
    return best


def path_to(task, jnet, olon, olat, dlon, dlat, minute: int):
    """Fastest itinerary of the slot to one destination: (row dict, legs list) or (None, None) if no path <= 90 min.

    For itineraries with k >= 2 rides the fastest itinerary with at most 1, ..., k-1 rides is also recorded
    (best_r<j>_s, best_r<j>_rides; None = no such itinerary within 90 min), for the transfer-penalty variants."""
    best = _best(task, jnet, olon, olat, dlon, dlat, minute)
    if best is None:
        return None, None
    (tot, nr, dep), rs, it = best
    row = {"dep_s": dep, "total_s": tot, "n_rides": nr}
    if nr == 0:
        row.update({"access_s": None, "egress_s": None, "wait_first_s": None, "wait_transfer_s": 0, "ride_s": 0,
                    "transfer_walk_s": 0, "r5_walk_only": True})
        return row, []
    tl = jnet.transitLayer
    ss = rs.stopSequence
    board = list(ss.boardStops.toArray())
    alight = list(ss.alightStops.toArray())
    rides = list(ss.rideTimesSeconds.toArray())
    waits = list(it.waitTimes.toArray())
    routes = list(rs.routes.toArray())
    acc, egr = int(ss.access.time), int(ss.egress.time)
    xfer_total = int(tot - acc - egr - sum(waits) - sum(rides))
    speed = float(task.walkSpeed)
    xw = []
    for k in range(nr - 1):
        a, b = alight[k], board[k + 1]
        if a == b:
            xw.append(0)
            continue
        st = tl.streetTransfers.get(a)
        v = None
        if st is not None:
            arr = list(st.toArray())
            for j in range(0, len(arr), 2):
                if arr[j] == b:
                    v = int(round(arr[j + 1] / 1000.0 / speed))
                    break
        xw.append(v)
    if nr == 2:
        xw = [xfer_total]          # one transfer: the exact residual
    legs, clock = [], dep + acc
    for k in range(nr):
        walk_before = acc if k == 0 else xw[k - 1]
        if k > 0:
            clock += xw[k - 1] if xw[k - 1] is not None else 0
        clock += waits[k]
        ri = tl.routes.get(routes[k])
        legs.append({"ride": k, "route_id": str(ri.route_id), "route_short_name": str(ri.route_short_name or ""),
                     "route_type": int(ri.route_type), "mode": route_class(int(ri.route_type)),
                     "feed": str(tl.feedFromStop(board[k])),
                     "board_stop": str(tl.stopIdForIndex.get(board[k])), "board_name": str(tl.stopNames.get(board[k])),
                     "alight_stop": str(tl.stopIdForIndex.get(alight[k])),
                     "alight_name": str(tl.stopNames.get(alight[k])),
                     "walk_before_s": walk_before, "wait_s": int(waits[k]), "ride_s": int(rides[k]),
                     "board_time_s": int(clock)})
        clock += rides[k]
    row.update({"access_s": acc, "egress_s": egr, "access_mode": str(ss.access.mode), "wait_first_s": int(waits[0]),
                "wait_transfer_s": int(sum(waits[1:])), "ride_s": int(sum(rides)), "transfer_walk_s": xfer_total,
                "transfer_walk_split_ok": bool(all(x is not None for x in xw) and abs(sum(x or 0 for x in xw) - xfer_total) <= 2 * nr),
                "r5_walk_only": False})
    for j in range(1, 4):
        if j < nr:
            b = _best(task, jnet, olon, olat, dlon, dlat, minute, max_rides=j)
            row[f"best_r{j}_s"] = None if b is None else b[0][0]
            row[f"best_r{j}_rides"] = None if b is None else b[0][1]
    return row, legs


# ------------------------------------------------------------------ chunks
class Ctx:
    """Per-agglomeration state shared by worker threads."""

    def __init__(self, agg: str):
        import geopandas as gpd
        from pipeline.access import make_task
        self.agg = agg
        self.o = AI.origins(agg)
        self.d = AI.destinations(agg)
        self.dlon, self.dlat = AI.TO4326.transform(self.d["x"].to_numpy(), self.d["y"].to_numpy())
        self.own = pd.Series(np.arange(len(self.d)), index=self.d["cell_id"].to_numpy())
        t0 = time.time()
        self.tn = load_network(agg)
        self.jnet = self.tn._transport_network
        dests = gpd.GeoDataFrame({"id": self.d["cell_id"].to_numpy()},
                                 geometry=gpd.points_from_xy(self.dlon, self.dlat), crs="EPSG:4326")
        self.reach_task, self.task_info = make_task(self.tn, dests, "pt_am")
        # path task: same parameters, its own destination set per trip
        self.path_task = self.reach_task.clone()
        log(f"{agg}: network and tasks ready in {time.time() - t0:.0f} s")
        self._walk = {}
        self._lock = threading.Lock()

    def walk_row(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        from pipeline.access import CHUNK as OCH, walk_cache
        k = i // OCH
        with self._lock:
            if k not in self._walk:
                self._walk[k] = walk_cache(self.agg, k)
        ip, ix, tt = self._walk[k]
        r = i - k * OCH
        return ix[ip[r]:ip[r + 1]], tt[ip[r]:ip[r + 1]]


def chunk_sig(agg: str, s: str, k: int, p: pd.DataFrame) -> str:
    from pipeline.access import unit_signature
    net = net_copy(agg).name
    parts = {"code": CODE_VERSION, "agg": agg, "set": s, "chunk": k, "net": net,
             "plan": hashlib.sha1(pd.util.hash_pandas_object(p[["trip", "origin_idx", "minute"]], index=False)
                                 .values.tobytes()).hexdigest()[:16],
             "inputs": AI.inputs_hash(agg), "walk_unit": unit_signature(agg, "street", "walk")[0],
             "params": [SEED, SLOT_MIN, REACH_MAX_MIN, PATH_MAX_MIN, REF_DAY]}
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def chunk_files(agg: str, s: str, k: int) -> tuple[Path, Path, Path]:
    d = OUT / agg / "chunks"
    return d / f"{s}_{k:04d}.trips.parquet", d / f"{s}_{k:04d}.legs.parquet", d / f"{s}_{k:04d}.sig"


def chunk_done(agg: str, s: str, k: int, sig: str) -> bool:
    a, b, c = chunk_files(agg, s, k)
    return a.exists() and b.exists() and c.exists() and c.read_text() == sig


def route_chunk(ctx: Ctx, s: str, p: pd.DataFrame, threads: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    from pipeline.access import travel_times
    W = ctx.d["w_census" if s == "res" else "w_jobs"].to_numpy(float)
    nd = len(ctx.d)

    def one_origin(oi: int):
        olon, olat = ctx.o["lon"].iat[oi], ctx.o["lat"].iat[oi]
        pt = travel_times(ctx.reach_task, ctx.jnet, olon, olat).astype(np.int64)
        pt[pt > REACH_MAX_MIN] = INT_MAX
        walk = np.full(nd, INT_MAX, np.int64)
        ix, tt = ctx.walk_row(oi)
        walk[ix] = tt
        comb = np.minimum(pt, walk)
        cand = (comb <= REACH_MAX_MIN) & (W > 0)
        own = ctx.own.get(ctx.o["cell_id"].iat[oi])
        if own is not None:
            cand[int(own)] = False
        ci = np.flatnonzero(cand)
        cw = np.cumsum(W[ci])
        out_rows, out_legs = [], []
        for r in p[p["origin_idx"] == oi].itertuples():
            base = {"set": s, "trip": int(r.trip), "origin": ctx.o["cell_id"].iat[oi], "origin_idx": int(oi),
                    "o_in_core": bool(ctx.o["in_core"].iat[oi]), "minute": int(r.minute),
                    "n_candidates": int(len(ci)), "reach_weight": float(cw[-1]) if len(ci) else 0.0}
            if not len(ci):
                out_rows.append({**base, "dest": None, "status": "no_destination"})
                continue
            rng = np.random.default_rng([SEED, AGG_CODE[ctx.agg], SET_CODE[s], int(r.trip)])
            j = int(ci[min(int(np.searchsorted(cw, rng.random() * cw[-1], side="right")), len(ci) - 1)])
            row = {**base, "dest": ctx.d["cell_id"].iat[j], "dest_idx": j, "d_in_core": bool(ctx.d["in_core"].iat[j]),
                   "d_in_fua": bool(ctx.d["in_fua"].iat[j]),
                   "o_lon": float(olon), "o_lat": float(olat), "d_lon": float(ctx.dlon[j]), "d_lat": float(ctx.dlat[j]),
                   "dist_km": float(np.hypot(ctx.d["x"].iat[j] - ctx.o["x"].iat[oi], ctx.d["y"].iat[j] - ctx.o["y"].iat[oi]) / 1000),
                   "regional_pt_min": None if pt[j] >= INT_MAX else int(pt[j]),
                   "walk_only_min": None if walk[j] >= INT_MAX else int(walk[j])}
            res, legs = path_to(ctx.path_task, ctx.jnet, olon, olat, ctx.dlon[j], ctx.dlat[j], int(r.minute))
            if res is None:
                row["status"] = "no_path_90"
            else:
                row.update(res)
                row["status"] = "ok"
                for lg in legs:
                    out_legs.append({"set": s, "trip": int(r.trip), **lg})
            out_rows.append(row)
        return out_rows, out_legs

    rows, legs = [], []
    with cf.ThreadPoolExecutor(max_workers=threads) as ex:
        for a, b in ex.map(one_origin, sorted(p["origin_idx"].unique())):
            rows += a
            legs += b
    t = pd.DataFrame(rows).sort_values("trip").reset_index(drop=True)
    lg = pd.DataFrame(legs, columns=["set", "trip", "ride", "route_id", "route_short_name", "route_type", "mode", "feed",
                                     "board_stop", "board_name", "alight_stop", "alight_name", "walk_before_s",
                                     "wait_s", "ride_s", "board_time_s"])
    lg = lg.sort_values(["trip", "ride"]).reset_index(drop=True)
    return t, lg


def route(aggs: list[str], threads: int) -> None:
    for agg in aggs:
        if not plan_path(agg).exists():
            plan([agg])
        p = pd.read_parquet(plan_path(agg))
        todo = []
        for (s, k), g in p.groupby(["set", "chunk"], sort=True):
            sig = chunk_sig(agg, s, int(k), g)
            if not chunk_done(agg, s, int(k), sig):
                todo.append((s, int(k), g, sig))
        if not todo:
            log(f"{agg}: all {p.groupby(['set', 'chunk']).ngroups} chunks up to date")
            continue
        wait_for_memory()
        ctx = Ctx(agg)
        for s, k, g, sig in todo:
            t0 = time.time()
            t, lg = route_chunk(ctx, s, g, threads)
            a, b, c = chunk_files(agg, s, k)
            a.parent.mkdir(parents=True, exist_ok=True)
            for df, f in ((t, a), (lg, b)):
                df.to_parquet(f.with_name(f.name + ".tmp"), index=False)
                os.replace(f.with_name(f.name + ".tmp"), f)
            c.write_text(sig)
            log(f"{agg} {s} chunk {k}: {len(t)} trips, {int((t.status == 'ok').sum())} with a path, "
                f"{time.time() - t0:.0f} s ({threads} threads)")
        del ctx
        import gc
        gc.collect()


def status() -> None:
    for agg in AGGS:
        if not plan_path(agg).exists():
            print(f"{agg}: no plan")
            continue
        p = pd.read_parquet(plan_path(agg))
        n = done = 0
        for (s, k), g in p.groupby(["set", "chunk"], sort=True):
            n += 1
            a, b, c = chunk_files(agg, s, int(k))
            done += a.exists() and c.exists()
        print(f"{agg}: {done}/{n} chunks on disk")


def load_trips(agg: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = OUT / agg / "chunks"
    t = pd.concat([pd.read_parquet(f) for f in sorted(d.glob("*.trips.parquet"))], ignore_index=True)
    lg = pd.concat([pd.read_parquet(f) for f in sorted(d.glob("*.legs.parquet"))], ignore_index=True)
    t.insert(0, "agglomeration", agg)
    lg.insert(0, "agglomeration", agg)
    return t, lg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "route", "status", "nik", "analyse"])
    ap.add_argument("--agg", nargs="*", default=AGGS)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--xmx", default="8G")
    a = ap.parse_args()
    if a.threads > 4:
        raise SystemExit("at most 4 threads (shared machine)")
    if a.cmd == "plan":
        plan(a.agg)
    elif a.cmd == "status":
        status()
    elif a.cmd in ("route", "nik"):
        from pipeline.r5_env import start
        start(xmx=a.xmx, tmp=OUT / "_tmp")
        if a.cmd == "route":
            route(a.agg, a.threads)
        else:
            from pipeline import trips_nik
            trips_nik.route_nik()
    else:
        from pipeline import trips_analyse
        trips_analyse.main()


if __name__ == "__main__":
    main()
