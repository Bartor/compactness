"""Travel time to the nearest secondary school and the nearest hospital emergency department (ROADMAP item 13).

    python -m pipeline.access_services route [--agg ...] [--threads 4] [--xmx 8G]   # resumable, chunked
    python -m pipeline.access_services status
    python -m pipeline.access_services aggregate     # metrics_services.*, layers/services_cells.parquet, QA tables

Side routing step: the production destination frame is not touched.  Per origin, R5 is asked for travel times to
every facility point of the agglomeration region and only the minimum over facilities of each kind is kept.

* origins: populated 250 m cells (either grid) with centre in the FUA and inside the phase-2 GTFS coverage mask
  (``in_mask_all``), i.e. exactly the cells of the "covered" domain of the production step;
* destinations: facility points from pipeline.services (main sets: secondary schools, adult SOR), all points in
  FUA + 15 km; several facilities at one point are routed once;
* walk: R5 WALK, 5 km/h, 60 min;
* transit: R5 TRANSIT + WALK, Wednesday 2026-11-25, departures every minute 07:00-09:00 (and 20:00-22:00 for SOR),
  50th percentile over departures, walk 5 km/h, access / egress <= 12 min, at most 8 rides, max 60 min - the
  production parameters (pipeline.access).  As in production, per origin-facility pair the time used is
  min(transit median, walk-only time) before taking the minimum over facilities;
* a facility not reached within 60 min gives null; an origin with no facility within 60 min has null time and is
  counted as "no service within 60 min".

R5 is run on a private copy of the production network file (data/interim/services/r5/<agg>/), one JVM, at most 4
threads, heap 8 GB, and only when at least 14 GB of RAM is free (checked every 3 min otherwise).  Chunks of 1000
origins are written by atomic rename with a signature; a finished chunk is never recomputed.
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
import time
import warnings
from functools import lru_cache
from pathlib import Path

warnings.filterwarnings("ignore", message="The provided departure time window is below 5 minutes")

import numpy as np
import pandas as pd

from pipeline import access_inputs as AI
from pipeline.common import INTERIM, load_config

CFG = load_config()
AGGS = ["trojmiasto", "poznan", "wroclaw", "gzm", "lodz", "krakow", "warszawa"]     # smallest first
OUT = INTERIM / "services"
RUN_LOG = OUT / "route.log"
CODE_VERSION = "access_services-2026-11-24.1"
CHUNK = 1000
MAX_MIN = 60
WALK_KMH = 5.0
WALK_ACCESS_MIN = 12
RIDES = 8
MIN_FREE_GB = 14.0
NA = np.iinfo(np.int32).max
SCEN = {"walk": None, "pt_am": "am_peak", "pt_evening": "evening"}
OUT_COLS = ["t_school_walk", "t_sor_walk", "t_school_pt_am", "t_sor_pt_am", "t_sor_pt_evening",
            "t_school_r5only_am", "t_sor_r5only_am", "near_school_pt_am", "near_sor_pt_am"]


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ frames
@lru_cache(maxsize=None)
def origins(agg: str) -> pd.DataFrame:
    o = AI.origins(agg)[["cell_id", "x", "y", "lon", "lat", "w_census", "w_raw", "in_core"]].copy()
    m = AI.mask(agg).set_index("cell_id").reindex(o["cell_id"])
    o["in_mask_all"] = m["in_mask_all"].fillna(False).astype(bool).to_numpy()
    return o[o["in_mask_all"]].reset_index(drop=True)


@lru_cache(maxsize=None)
def facilities(agg: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(facility table of the main sets, unique destination points with kind flags)."""
    f = pd.read_parquet(OUT / "facilities.parquet")
    f = f[(f["agglomeration"] == agg) & f["in_main"]].copy()
    f["pt_key"] = f["x"].round(0).astype(np.int64).astype(str) + "_" + f["y"].round(0).astype(np.int64).astype(str)
    pts = (f.groupby("pt_key", sort=True)
           .agg(x=("x", "first"), y=("y", "first"), lon=("lon", "first"), lat=("lat", "first"),
                school=("kind", lambda s: bool((s == "school").any())), sor=("kind", lambda s: bool((s == "sor").any())),
                n=("id", "size"))
           .reset_index())
    f["pt_idx"] = f["pt_key"].map(pd.Series(np.arange(len(pts)), index=pts["pt_key"]))
    return f.reset_index(drop=True), pts


def frame_sig(agg: str) -> str:
    o = origins(agg)
    _, p = facilities(agg)
    h = hashlib.sha1()
    h.update(o["cell_id"].astype(str).str.cat(sep=",").encode())
    h.update(p[["x", "y", "school", "sor"]].to_numpy().astype(np.float64).round(0).tobytes())
    return h.hexdigest()[:16]


def n_chunks(agg: str) -> int:
    return int(np.ceil(len(origins(agg)) / CHUNK))


# ------------------------------------------------------------------ network copy and signature
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
        (dst / "source.json").write_text(json.dumps({"copied_from": str(f.relative_to(INTERIM)), "bytes": f.stat().st_size,
                                                     "copied_at": dt.datetime.now().isoformat(timespec="seconds")},
                                                    indent=1), encoding="utf-8")
    return tgt


def unit_sig(agg: str) -> str:
    tgt = net_copy(agg)
    parts = {"code": CODE_VERSION, "frame": frame_sig(agg), "net": tgt.name, "day": CFG["reference_day"],
             "windows": {k: CFG["time_windows"][v] for k, v in SCEN.items() if v}, "max_min": MAX_MIN,
             "walk_kmh": WALK_KMH, "walk_access_min": WALK_ACCESS_MIN, "rides": RIDES, "chunk": CHUNK}
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def unit_dir(agg: str) -> Path:
    return OUT / "route" / agg


def chunk_path(agg: str, k: int) -> Path:
    return unit_dir(agg) / f"chunk_{k:05d}.parquet"


def open_unit(agg: str) -> str:
    d = unit_dir(agg)
    sig = unit_sig(agg)
    man = d / "manifest.json"
    if d.exists() and man.exists() and json.loads(man.read_text(encoding="utf-8"))["signature"] != sig:
        # inputs changed: move the stale chunks aside (never delete silently)
        stale = d.with_name(d.name + f"_stale_{dt.datetime.now().strftime('%Y%m%d%H%M%S')}")
        d.rename(stale)
        log(f"{agg}: signature changed, old chunks moved to {stale.name}")
    d.mkdir(parents=True, exist_ok=True)
    if not man.exists():
        f, p = facilities(agg)
        man.write_text(json.dumps({"signature": sig, "n_origins": int(len(origins(agg))), "n_points": int(len(p)),
                                   "n_school_points": int(p["school"].sum()), "n_sor_points": int(p["sor"].sum()),
                                   "n_chunks": n_chunks(agg)}, indent=1), encoding="utf-8")
    return sig


def done_chunks(agg: str) -> int:
    d = unit_dir(agg)
    man = d / "manifest.json"
    if not man.exists():
        return 0
    if json.loads(man.read_text(encoding="utf-8"))["signature"] != unit_sig(agg):
        return 0
    return sum(chunk_path(agg, k).exists() for k in range(n_chunks(agg)))


# ------------------------------------------------------------------ R5
def wait_for_memory() -> None:
    import psutil
    while True:
        free = psutil.virtual_memory().available / 1024 ** 3
        if free >= MIN_FREE_GB:
            log(f"free memory {free:.1f} GB: starting")
            return
        log(f"free memory {free:.1f} GB < {MIN_FREE_GB} GB: waiting 3 min")
        time.sleep(180)


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


def make_task(tn, dests, scen: str):
    from r5py import RegionalTask, TransportMode
    day = dt.datetime.fromisoformat(CFG["reference_day"])
    if scen == "walk":
        kw = dict(transport_modes=[TransportMode.WALK], departure=day.replace(hour=7),
                  departure_time_window=dt.timedelta(minutes=1), percentiles=[50],
                  max_time=dt.timedelta(minutes=MAX_MIN), speed_walking=WALK_KMH)
    else:
        w = CFG["time_windows"][SCEN[scen]]
        h0, m0 = map(int, w["start"].split(":"))
        h1, m1 = map(int, w["end"].split(":"))
        kw = dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], departure=day.replace(hour=h0, minute=m0),
                  departure_time_window=dt.timedelta(hours=h1 - h0, minutes=m1 - m0), percentiles=[50],
                  max_time=dt.timedelta(minutes=MAX_MIN), max_time_walking=dt.timedelta(minutes=WALK_ACCESS_MIN),
                  speed_walking=WALK_KMH, max_public_transport_rides=RIDES)
    return RegionalTask(tn, origin=None, destinations=dests, **kw)._regional_task


def tt(task, jnet, lon: float, lat: float) -> np.ndarray:
    import com.conveyal.r5
    t = task.clone()
    t.fromLat, t.fromLon = float(lat), float(lon)
    res = com.conveyal.r5.analyst.TravelTimeComputer(t, jnet).computeTravelTimes()
    a = np.asarray(res.travelTimes.getValues()[0], dtype=np.int64).copy()
    return np.where(a <= MAX_MIN, a, NA)


def nearest(t: np.ndarray, mask: np.ndarray) -> tuple[float, int]:
    if not mask.any():
        return np.nan, -1
    v = np.where(mask, t, NA)
    i = int(np.argmin(v))
    return (float(v[i]), i) if v[i] < NA else (np.nan, -1)


def route(aggs: list[str], threads: int) -> None:
    import geopandas as gpd
    for agg in aggs:
        open_unit(agg)
        tot = n_chunks(agg)
        todo = [k for k in range(tot) if not chunk_path(agg, k).exists()]
        if not todo:
            log(f"{agg}: {tot} chunks done")
            continue
        o = origins(agg)
        _, pts = facilities(agg)
        is_s, is_h = pts["school"].to_numpy(), pts["sor"].to_numpy()
        t0 = time.time()
        tn = load_network(agg)
        jnet = tn._transport_network
        dests = gpd.GeoDataFrame({"id": pts["pt_key"].to_numpy()}, geometry=gpd.points_from_xy(pts["lon"], pts["lat"]),
                                 crs="EPSG:4326")
        tasks = {s: make_task(tn, dests, s) for s in SCEN}
        log(f"{agg}: network and tasks in {time.time() - t0:.0f} s; {len(o)} origins, {len(pts)} points "
            f"({int(is_s.sum())} school, {int(is_h.sum())} SOR), {len(todo)}/{tot} chunks to do")
        lon, lat = o["lon"].to_numpy(), o["lat"].to_numpy()

        def one(i):
            w = tt(tasks["walk"], jnet, lon[i], lat[i])
            am = tt(tasks["pt_am"], jnet, lon[i], lat[i])
            ev = tt(tasks["pt_evening"], jnet, lon[i], lat[i])
            amw, evw = np.minimum(am, w), np.minimum(ev, w)
            s_am, ns = nearest(amw, is_s)
            h_am, nh = nearest(amw, is_h)
            return (nearest(w, is_s)[0], nearest(w, is_h)[0], s_am, h_am, nearest(evw, is_h)[0],
                    nearest(am, is_s)[0], nearest(am, is_h)[0], ns, nh)

        for k in todo:
            t1 = time.time()
            idx = range(k * CHUNK, min((k + 1) * CHUNK, len(o)))
            with cf.ThreadPoolExecutor(max_workers=threads) as ex:
                res = list(ex.map(one, idx))
            df = pd.DataFrame(res, columns=OUT_COLS)
            df.insert(0, "cell_id", o["cell_id"].to_numpy()[list(idx)])
            for c in ("near_school_pt_am", "near_sor_pt_am"):
                df[c] = df[c].astype(np.int32)
            p = chunk_path(agg, k)
            df.to_parquet(p.with_name(p.name + ".tmp"), index=False)
            os.replace(p.with_name(p.name + ".tmp"), p)
            wall = time.time() - t1
            log(f"{agg} chunk {k + 1}/{tot}: {len(df)} origins in {wall:.0f} s ({1000 * wall / max(len(df), 1):.0f} ms/origin, "
                f"{threads} threads)")
        del tasks, tn, jnet
        gc.collect()


def status() -> None:
    for agg in AGGS:
        print(agg, f"{done_chunks(agg)}/{n_chunks(agg)} chunks; origins {len(origins(agg))}")


def load(agg: str) -> pd.DataFrame | None:
    tot = n_chunks(agg)
    if done_chunks(agg) < tot:
        return None
    d = pd.concat([pd.read_parquet(chunk_path(agg, k)) for k in range(tot)], ignore_index=True)
    assert (d["cell_id"].to_numpy() == origins(agg)["cell_id"].to_numpy()).all()
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["route", "status", "aggregate"])
    ap.add_argument("--agg", nargs="*", default=AGGS)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--xmx", default="8G")
    a = ap.parse_args()
    if a.cmd == "route":
        if a.threads > 4:
            raise SystemExit("at most 4 threads (shared machine)")
        wait_for_memory()
        from pipeline.r5_env import start
        start(xmx=a.xmx, tmp=OUT / "_tmp")
        route([g for g in AGGS if g in a.agg], a.threads)
    elif a.cmd == "status":
        status()
    else:
        from pipeline import access_services_aggregate
        access_services_aggregate.main()


if __name__ == "__main__":
    main()
