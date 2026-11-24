"""Wrocław tram what-if (ROADMAP 15): how much would residents' reach improve if slow tram stretches ran at
realistic target speeds (and, in one scenario, every line ran every 10 minutes in the peak)?

    python -m pipeline.whatif_tram build                 # scenario feeds + validation + speed tables (no JVM)
    python -m pipeline.whatif_tram route [--scen ...]    # R5 networks and routing (one JVM, 4 threads, 8 GB heap)
    python -m pipeline.whatif_tram aggregate             # results (pipeline.whatif_tram_out)

Everything is SCHEDULED time.  The scenarios say what faster (or more frequent) trams would be worth in the
accessibility measure of phase 3; they do not say how to get there or what it costs.

Scenario feeds (data/interim/whatif/gtfs/<scen>/, never under results/)
* Source: the production cleaned GTFS of Wrocław, all feeds (data/interim/r5/wroclaw/gtfs_all/, read only).  Only
  stop_times.txt (and trips.txt in the headway scenarios) of wroclaw.zip change, and only for tram trips (route_type
  0) running on the reference Wednesday; every other feed zip is copied byte for byte.
* Hops (stop to next stop) of the tram trips come from the speed layer's hop cache (pipeline.speed_core, weekday
  2026-11-25: hop length along the shape, band of the hop's departure) and are matched to the zip's stop_times by
  trip and position; stop pair -> stretch from results/tables/tram_stretch_stop_pairs.csv.  Hops that open or close a
  trip between two stops of one name (terminal shuffles) and the 0.3 % of hops on no stretch are not changed.
* Target per (stretch direction, band): a target speed v*.  Target time of the band's traversals S* = max(L / v*, F)
  with L = sum of hop lengths, F = sum of free-running hop times (tram_stretches.free_time, main parameters: 1.0 m/s2,
  1.0 m/s2, 50 km/h, 20 s dwell).  If S* < S (current time) the saving S - S* is taken out of the hops' time above
  free running ("slack", max(0, t - free)) in proportion to it, so no hop gets faster than its own free-running time,
  the modelled 20 s dwell is never cut and hops already at or below free running are left alone.
* Whole minutes: per trip the continuous savings are summed along the trip; the shift at stop k is
  60 x floor(cum_k / 60 + u), u in [0, 1) a fixed number per trip (SHA-1 of the trip id).  E[floor(x + u)] = x, so the
  expected shift at every stop equals the continuous saving (unbiased over trips), the shift is non-decreasing along
  the trip (times stay monotone; a hop never gets negative), and the first departure is unchanged (cum_0 = 0), so
  frequencies at the first stop stay as they are.  Arrival and departure at a stop move together (dwell kept).
* Headways (S4, S4h): every main trip pattern of a tram line and direction (most frequent stop sequence) whose median
  peak headway is above 10 min is re-timed in the first-departure window 05:45-10:00 to every 10 min: the phase of the
  first departure after 07:00 within the old cycle is scaled by 10 / old headway, new departures every 10 min across
  the window, each copying the stop-time offsets of the original trip nearest in departure time.  The original trips
  of that pattern in the window are removed.  Wrocław's peak tram headway is 12 min on every line, so inserting
  duplicates would give 6 / 12 min gaps, not 10; re-timing is the clean way.  Coordination of lines on shared
  trunks is not preserved exactly (phases scale at the first stop, running times do not).

Scenarios (targets applied in every weekday band; a stretch never gets slower)
* S0  control: the unmodified feed through the same reader and writer; must reproduce production cell by cell.
* S1  stretch-band speeds below 15 km/h raised to 15 km/h.
* S2  every stretch at its own evening (20-23) scheduled speed in every band ("peak runs like evening").
* S3  every stretch at the median morning-peak speed of comparable stretches in Kraków and Poznań; comparable =
      same class of street running (share of length in the roadway or a pedestrian zone >= 15 %) and mean stop
      spacing (>= 450 m), reference stretches with >= 5 min, >= 8 trips 07-09 (classes of 14-49 stretches).
* S4  S2 + 10-minute peak headways on every line (re-timing above).
* S4h headways only (S0 running times + 10-minute peak headways), to separate the wait from the speed effect.

Routing (production settings, pipeline.access): R5 v7.5.1, transit + walk, Wednesday 07:00-09:00 departures every
minute, median, 60 min, walk 5 km/h, access / egress <= 12 min, max 8 rides, min(transit, walk-only) per pair with
the production walk cache; origins and destinations = the production frame of Wrocław (20 153 origins, 42 554
destinations).  Per origin the census-scaled and raw GHSL population reachable within 5..60 min, over all
destinations and over the urban-centre destinations (pipeline.access_uc), so core, covered area, FUA and urban centre
all come from one routing.  Networks are built from the scenario zips in data/interim/whatif/r5/<scen>/.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gc
import hashlib
import io
import json
import os
import shutil
import sys
import time
import warnings
import zipfile
from functools import lru_cache
from pathlib import Path

warnings.filterwarnings("ignore", message="The provided departure time window is below 5 minutes")

import numpy as np
import pandas as pd

from pipeline.common import INTERIM, RESULTS, write_json

AGG = "wroclaw"
FEED = "wroclaw"
CODE_VERSION = "whatif-tram-2026-11-24.2"
PROD_GTFS = INTERIM / "r5" / AGG / "gtfs_all"
PROD_OSM = INTERIM / "r5" / AGG / "osm.pbf"
OUT = INTERIM / "whatif"
QA = RESULTS / "qa" / "whatif"
TABLES = RESULTS / "tables"
PROGRESS = INTERIM / "proposals" / "whatif_progress.md"
HOPS = INTERIM / "speed" / "hops_wroclaw_2026-11-25.parquet"

SLOW_KMH = 15.0
S3_STREET_SHARE, S3_SPACING_M, S3_REF_MIN_TRIPS = 0.15, 450.0, 8
S3_REF = ("krakow", "poznan")
HW_TARGET_MIN = 10.0
HW_WINDOW = (5 * 3600 + 45 * 60, 10 * 3600)       # first departures re-timed in [05:45, 10:00)
HW_ANCHOR = 7 * 3600
SCENARIOS = {
    "S0": {"speed": None, "headway": False, "label": "kontrola (rozkład bez zmian)"},
    "S1": {"speed": "slow15", "headway": False, "label": "odcinki wolniejsze niż 15 km/h podniesione do 15 km/h"},
    "S2": {"speed": "evening", "headway": False, "label": "każdy odcinek z prędkością wieczorną (20–23) przez cały dzień"},
    "S3": {"speed": "peer", "headway": False, "label": "odcinki z medianą prędkości porównywalnych odcinków Krakowa i Poznania"},
    "S4": {"speed": "evening", "headway": True, "label": "S2 + kursy co 10 min w szczycie na każdej linii"},
    "S4h": {"speed": None, "headway": True, "label": "same kursy co 10 min w szczycie (bez przyspieszenia)"},
}
THREADS, XMX, MIN_FREE_GB = 4, "8G", 14.0


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def progress(msg: str) -> None:
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write(f"- {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}: {msg}\n")


def sha_file(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()[:16]


def sec(s: pd.Series) -> np.ndarray:
    p = s.str.split(":", expand=True).astype(np.int64)
    return (p[0] * 3600 + p[1] * 60 + p[2]).to_numpy()


def hms(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, np.int64)
    return np.array([f"{x // 3600:02d}:{(x // 60) % 60:02d}:{x % 60:02d}" for x in v], dtype=object)


# ------------------------------------------------------------------ source feed and hops
@lru_cache(maxsize=1)
def source_zip() -> tuple[list[zipfile.ZipInfo], dict[str, bytes]]:
    with zipfile.ZipFile(PROD_GTFS / f"{FEED}.zip") as z:
        infos = z.infolist()
        return infos, {i.filename: z.read(i.filename) for i in infos}


def read_table(name: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(source_zip()[1][name]), dtype=str, keep_default_na=False)


def table_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False, lineterminator="\n")
    return buf.getvalue().encode("utf-8")


@lru_cache(maxsize=1)
def tram_trip_ids() -> pd.DataFrame:
    r, t = read_table("routes.txt"), read_table("trips.txt")
    tr = set(r.loc[r["route_type"] == "0", "route_id"])
    t = t[t["route_id"].isin(tr) & (t["service_id"] == "WED")].copy()
    return t.merge(r[["route_id", "route_short_name"]], on="route_id", how="left")


@lru_cache(maxsize=1)
def base_stop_times() -> pd.DataFrame:
    """stop_times of the source zip with seconds, position in trip (k) and a tram flag."""
    st = read_table("stop_times.txt")
    st["row"] = np.arange(len(st))
    st["seq"] = st["stop_sequence"].astype(np.int64)
    st["arr"] = sec(st["arrival_time"])
    st["dep"] = sec(st["departure_time"])
    st = st.sort_values(["trip_id", "seq"], kind="stable").reset_index(drop=True)
    st["k"] = st.groupby("trip_id", sort=False).cumcount().astype(np.int64)
    st["tram"] = st["trip_id"].isin(set(tram_trip_ids()["trip_id"]))
    return st


@lru_cache(maxsize=1)
def hops() -> pd.DataFrame:
    """Tram hops of the reference Wednesday with stretch, length, free-running time and shuffle flag, matched to the
    zip rows (validated: same from-stop, same departure and arrival)."""
    from pipeline import speed_core as sc
    from pipeline import tram_stretches as ts
    h = pd.read_parquet(HOPS, columns=["feed", "uid", "mode", "repl_bus", "k", "from_suid", "to_suid", "dep_s", "arr_s",
                                       "t_s", "len_m", "band", "line", "direction_id"])
    h = h[(h["mode"] == "tram") & (h["feed"] == FEED)].copy()
    h["shuffle"] = sc.terminal_shuffle(h, AGG).to_numpy()
    h["trip_id"] = h["uid"].str.slice(len(FEED) + 1)
    h["from_stop"] = h["from_suid"].str.slice(len(FEED) + 1)
    h["to_stop"] = h["to_suid"].str.slice(len(FEED) + 1)
    sp = pd.read_csv(TABLES / "tram_stretch_stop_pairs.csv", dtype={"from_stop_id": str, "to_stop_id": str})
    sp = sp[(sp["agglomeration"] == AGG) & (sp["feed"] == FEED)]
    h = h.merge(sp[["from_stop_id", "to_stop_id", "stretch_dir_id"]].rename(
        columns={"from_stop_id": "from_stop", "to_stop_id": "to_stop"}), on=["from_stop", "to_stop"], how="left")
    h.loc[h["shuffle"], "stretch_dir_id"] = None
    h["free_s"] = ts.free_time(h["len_m"].to_numpy(float), ts.KIN)
    st = base_stop_times()
    a = st[["trip_id", "k", "stop_id", "dep"]].rename(columns={"stop_id": "zip_from", "dep": "zip_dep"})
    b = st[["trip_id", "k", "stop_id", "arr"]].rename(columns={"stop_id": "zip_to", "arr": "zip_arr"})
    b["k"] -= 1
    h = h.merge(a, on=["trip_id", "k"], how="left").merge(b, on=["trip_id", "k"], how="left")
    bad = (h["zip_from"] != h["from_stop"]) | (h["zip_to"] != h["to_stop"]) | (h["zip_dep"] != h["dep_s"]) | \
          (h["zip_arr"] != h["arr_s"])
    if bad.any():
        raise AssertionError(f"{int(bad.sum())} hops do not match the zip's stop_times")
    return h.sort_values(["trip_id", "k"], kind="stable").reset_index(drop=True)


# ------------------------------------------------------------------ targets
@lru_cache(maxsize=1)
def stretch_table() -> pd.DataFrame:
    return pd.read_csv(TABLES / "tram_stretches.csv", low_memory=False)


@lru_cache(maxsize=1)
def band_table() -> pd.DataFrame:
    b = pd.read_csv(TABLES / "tram_stretch_bands.csv")
    return b[b["stretch_dir_id"].str.startswith("WRO-") & (b["day_type"] == "weekday")]


def peer_classes() -> tuple[pd.DataFrame, pd.DataFrame]:
    """S3: class targets from Kraków + Poznań and the class of every Wrocław stretch direction."""
    s = stretch_table().copy()
    s["street"] = s["share_street"] + s["share_pedestrian"]
    s["spacing_m"] = s["length_m"] / s["n_hops"]
    s["track"] = np.where(s["street"] >= S3_STREET_SHARE, "w jezdni", "wydzielone")
    s["spacing"] = np.where(s["spacing_m"] >= S3_SPACING_M, f"≥ {S3_SPACING_M:.0f} m", f"< {S3_SPACING_M:.0f} m")
    ref = s[s["agglomeration"].isin(S3_REF) & ~s["below_min"] & s["speed_kmh_wd_am_peak"].notna() &
            (s["trips_wd_am_peak"] >= S3_REF_MIN_TRIPS)]
    cls = (ref.groupby(["track", "spacing"])
           .agg(n_ref=("speed_kmh_wd_am_peak", "size"), target_kmh=("speed_kmh_wd_am_peak", "median"),
                p25_kmh=("speed_kmh_wd_am_peak", lambda v: float(np.percentile(v, 25))),
                p75_kmh=("speed_kmh_wd_am_peak", lambda v: float(np.percentile(v, 75))),
                n_krakow=("agglomeration", lambda v: int((v == "krakow").sum())),
                n_poznan=("agglomeration", lambda v: int((v == "poznan").sum())))
           .reset_index())
    w = s[s["agglomeration"] == AGG][["stretch_dir_id", "track", "spacing", "street", "spacing_m", "below_min",
                                       "speed_kmh_wd_am_peak", "name"]]
    w = w.merge(cls[["track", "spacing", "target_kmh"]], on=["track", "spacing"], how="left")
    return cls, w


def targets(kind: str | None) -> pd.DataFrame:
    """Target speed per (stretch_dir_id, band); NaN = no target."""
    b = band_table()[["stretch_dir_id", "band", "speed_kmh"]].copy()
    if kind is None:
        b["v_target"] = np.nan
    elif kind == "slow15":
        b["v_target"] = np.where(b["speed_kmh"] < SLOW_KMH, SLOW_KMH, np.nan)
    elif kind == "evening":
        ev = b[b["band"] == "evening"].set_index("stretch_dir_id")["speed_kmh"]
        b["v_target"] = b["stretch_dir_id"].map(ev)
    elif kind == "peer":
        _, w = peer_classes()
        b["v_target"] = b["stretch_dir_id"].map(w.set_index("stretch_dir_id")["target_kmh"])
    else:
        raise ValueError(kind)
    return b[b["band"] != "all_day"]


def savings(kind: str | None) -> tuple[pd.Series, pd.DataFrame]:
    """Continuous saving (s) per hop (index of hops()) and the per-group table."""
    h = hops()
    g = h.dropna(subset=["stretch_dir_id"]).copy()
    g["slack_pos"] = np.maximum(0.0, g["t_s"].to_numpy(float) - g["free_s"].to_numpy(float))
    grp = g.groupby(["stretch_dir_id", "band"]).agg(S=("t_s", "sum"), L=("len_m", "sum"), F=("free_s", "sum"),
                                                    P=("slack_pos", "sum"), n=("t_s", "size")).reset_index()
    grp = grp.merge(targets(kind)[["stretch_dir_id", "band", "v_target"]], on=["stretch_dir_id", "band"], how="left")
    with np.errstate(invalid="ignore", divide="ignore"):
        s_star = np.maximum(grp["L"] / (grp["v_target"] / 3.6), grp["F"])
    cut = np.where(np.isfinite(s_star) & (s_star < grp["S"]), grp["S"] - s_star, 0.0)
    grp["saving_s"] = cut
    grp["ratio"] = np.where(grp["P"] > 0, np.minimum(1.0, cut / grp["P"].where(grp["P"] > 0, 1.0)), 0.0)
    grp["capped_by_free"] = np.isfinite(s_star) & (grp["L"] / (grp["v_target"] / 3.6) < grp["F"]) & (cut > 0)
    r = g.merge(grp[["stretch_dir_id", "band", "ratio"]], on=["stretch_dir_id", "band"], how="left")
    sv = pd.Series(0.0, index=h.index)
    sv.loc[g.index] = (g["slack_pos"].to_numpy() * r["ratio"].to_numpy())
    return sv, grp


def dither(trip_ids: pd.Series) -> pd.Series:
    u = {t: int(hashlib.sha1(f"whatif|{t}".encode()).hexdigest()[:12], 16) / 16 ** 12 for t in trip_ids.unique()}
    return trip_ids.map(u)


def shifts(sv: pd.Series) -> pd.DataFrame:
    """Whole-minute shift (s) per (trip_id, k) for every stop of the tram trips (k = 0 .. last)."""
    h = hops()
    d = pd.DataFrame({"trip_id": h["trip_id"], "k": h["k"] + 1, "save": sv.to_numpy()})
    d["cum"] = d.groupby("trip_id", sort=False)["save"].cumsum()
    first = pd.DataFrame({"trip_id": h.loc[h["k"] == 0, "trip_id"], "k": 0, "save": 0.0, "cum": 0.0})
    d = pd.concat([first, d], ignore_index=True).sort_values(["trip_id", "k"], kind="stable")
    d["u"] = dither(d["trip_id"]).to_numpy()
    d["shift"] = 60 * np.floor(d["cum"] / 60.0 + d["u"]).astype(np.int64)
    return d[["trip_id", "k", "cum", "shift"]].reset_index(drop=True)


# ------------------------------------------------------------------ headways
def retime_headways(st: pd.DataFrame, trips: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Re-time main tram patterns to HW_TARGET_MIN in the first-departure window; returns (stop_times, trips, report)."""
    tt = tram_trip_ids()
    s = st[st["tram"]]
    key = s.groupby("trip_id", sort=False)["stop_id"].agg(">".join)
    first = s[s["k"] == 0].set_index("trip_id")["dep"]
    info = tt.set_index("trip_id")[["route_id", "direction_id", "route_short_name"]].copy()
    info["pattern"] = key
    info["first_dep"] = first
    lo, hi = HW_WINDOW
    add_st, add_tr, drop, rows = [], [], [], []
    for (rid, did), g in info.groupby(["route_id", "direction_id"], sort=True):
        win = g[(g["first_dep"] >= lo) & (g["first_dep"] < hi)]
        if win.empty:
            continue
        main = win["pattern"].value_counts().sort_index().sort_values(ascending=False, kind="stable").index[0]
        m = g[g["pattern"] == main].sort_values("first_dep")
        mw = m[(m["first_dep"] >= lo) & (m["first_dep"] < hi)]
        pk = m[(m["first_dep"] >= HW_ANCHOR - 15 * 60) & (m["first_dep"] < 9 * 3600)]["first_dep"].to_numpy()
        hw = float(np.median(np.diff(pk))) / 60 if len(pk) > 2 else np.nan
        row = {"route_id": rid, "line": g["route_short_name"].iloc[0], "direction_id": did, "pattern_stops": main.count(">") + 1,
               "trips_window_before": len(mw), "peak_headway_min_before": hw, "retimed": False}
        if not np.isfinite(hw) or hw <= HW_TARGET_MIN:
            rows.append(row)
            continue
        after = m[m["first_dep"] >= HW_ANCHOR]["first_dep"].to_numpy()
        phase = float(after[0] - HW_ANCHOR) % (hw * 60)
        a0 = HW_ANCHOR + 60 * round(phase * HW_TARGET_MIN / hw / 60)      # whole minutes, as the timetable
        step = int(HW_TARGET_MIN * 60)
        kmin = int(np.ceil((lo - a0) / step))
        kmax = int(np.ceil((hi - a0) / step))
        new = [int(round(a0 + k * step)) for k in range(kmin, kmax)]
        new = [x for x in new if lo <= x < hi]
        tmpl = mw["first_dep"]
        for x in new:
            j = (tmpl - x).abs().sort_values(kind="stable").index[0]       # nearest original (ties: earlier, sorted)
            src = s[s["trip_id"] == j]
            nid = f"{j}~hw{x // 60:04d}"
            c = src.copy()
            off = x - int(first[j])
            c["trip_id"] = nid
            c["row"] = np.nan
            c["arr"] = c["arr"] + off
            c["dep"] = c["dep"] + off
            add_st.append(c)
            tr = trips[trips["trip_id"] == j].copy()
            tr["trip_id"] = nid
            add_tr.append(tr)
        drop += list(mw.index)
        before = m[m["first_dep"] < lo]["first_dep"].to_numpy()
        later = m[m["first_dep"] >= hi]["first_dep"].to_numpy()
        allt = np.sort(np.r_[before, new, later])
        gaps = np.diff(allt) / 60
        inner = (allt[:-1] >= lo) & (allt[1:] < hi)
        row.update({"retimed": True, "trips_window_after": len(new), "first_new": hms([new[0]])[0], "last_new": hms([new[-1]])[0],
                    "max_gap_min_inside": float(gaps[inner].max()),
                    "gap_min_at_start": float((new[0] - before[-1]) / 60) if len(before) else None,
                    "gap_min_at_end": float((later[0] - new[-1]) / 60) if len(later) else None,
                    "veh_h_removed": float(sum((s[s["trip_id"] == t]["arr"].max() - first[t]) for t in mw.index) / 3600),
                    })
        row["veh_h_added"] = float(sum((c["arr"].max() - c["dep"].min()) for c in add_st[-len(new):]) / 3600)
        rows.append(row)
    st2 = pd.concat([st[~st["trip_id"].isin(drop)]] + add_st, ignore_index=True)
    tr2 = pd.concat([trips[~trips["trip_id"].isin(drop)]] + add_tr, ignore_index=True)
    return st2, tr2, pd.DataFrame(rows)


# ------------------------------------------------------------------ build one scenario feed
def feed_dir(scen: str) -> Path:
    return OUT / "gtfs" / scen


def feed_sig(scen: str) -> str:
    parts = {"code": CODE_VERSION, "scen": SCENARIOS[scen], "src": sha_file(PROD_GTFS / f"{FEED}.zip"),
             "hops": sha_file(HOPS), "pairs": sha_file(TABLES / "tram_stretch_stop_pairs.csv"),
             "bands": sha_file(TABLES / "tram_stretch_bands.csv"), "stretches": sha_file(TABLES / "tram_stretches.csv"),
             "s3": [S3_STREET_SHARE, S3_SPACING_M, S3_REF_MIN_TRIPS, S3_REF], "hw": [HW_TARGET_MIN, HW_WINDOW, HW_ANCHOR],
             "others": {p.name: sha_file(p) for p in sorted(PROD_GTFS.glob("*.zip")) if p.stem != FEED}}
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def build_feed(scen: str) -> dict:
    d = feed_dir(scen)
    sigf = d / "feed.sig"
    if sigf.exists() and sigf.read_text() == feed_sig(scen) and (d / "build.json").exists():
        return json.loads((d / "build.json").read_text(encoding="utf-8"))
    t0 = time.time()
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    spec = SCENARIOS[scen]
    st = base_stop_times().copy()
    trips = read_table("trips.txt")
    sv, grp = savings(spec["speed"])
    sh = shifts(sv)
    st = st.merge(sh[["trip_id", "k", "shift"]], on=["trip_id", "k"], how="left")
    st["shift"] = st["shift"].fillna(0).astype(np.int64)
    st["arr"] = st["arr"] - st["shift"]
    st["dep"] = st["dep"] - st["shift"]
    hw_rep = None
    if spec["headway"]:
        st, trips, hw_rep = retime_headways(st, trips)
    # write: original row order for existing rows, new trips appended sorted (deterministic)
    st = st.sort_values(["row"], kind="stable", na_position="last")
    new = st["row"].isna()
    st = pd.concat([st[~new], st[new].sort_values(["trip_id", "seq"], kind="stable")], ignore_index=True)
    out_st = pd.DataFrame({"trip_id": st["trip_id"], "arrival_time": hms(st["arr"]), "departure_time": hms(st["dep"]),
                           "stop_id": st["stop_id"], "stop_sequence": st["stop_sequence"]})
    infos, data = source_zip()
    files = dict(data)
    files["stop_times.txt"] = table_bytes(out_st)
    if spec["headway"]:
        files["trips.txt"] = table_bytes(trips)
    path = d / f"{FEED}.zip"
    with zipfile.ZipFile(path.with_suffix(".tmp"), "w", compression=zipfile.ZIP_DEFLATED) as z:
        for i in infos:
            zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, files[i.filename])
    os.replace(path.with_suffix(".tmp"), path)
    for p in sorted(PROD_GTFS.glob("*.zip")):
        if p.stem != FEED:
            shutil.copyfile(p, d / p.name)
    val = validate(scen, path, hw_rep)
    stats = speed_stats(scen, sv, sh, grp)
    rep = {"scenario": scen, "label": spec["label"], "validation": val, **stats, "build_s": round(time.time() - t0, 1),
           "stop_times_identical_to_source": files["stop_times.txt"] == data["stop_times.txt"],
           "zip_sha1": sha_file(path)}
    grp.to_csv(d / "groups.csv", index=False, lineterminator="\n")
    if hw_rep is not None:
        hw_rep.to_csv(d / "headways.csv", index=False, lineterminator="\n")
    write_json(d / "build.json", rep)
    sigf.write_text(feed_sig(scen))
    return rep


def validate(scen: str, path: Path, hw_rep) -> dict:
    """Same trips (unless re-timed), same stop sequences, monotone times, unchanged first departures (speed),
    non-tram rows identical, other files identical."""
    with zipfile.ZipFile(path) as z:
        st = pd.read_csv(z.open("stop_times.txt"), dtype=str, keep_default_na=False)
        tr = pd.read_csv(z.open("trips.txt"), dtype=str, keep_default_na=False)
        same_files = all(z.read(n) == source_zip()[1][n] for n in source_zip()[1] if n not in ("stop_times.txt", "trips.txt"))
    src = base_stop_times()
    st["seq"] = st["stop_sequence"].astype(np.int64)
    st["arr"], st["dep"] = sec(st["arrival_time"]), sec(st["departure_time"])
    st = st.sort_values(["trip_id", "seq"], kind="stable").reset_index(drop=True)
    tram = set(tram_trip_ids()["trip_id"])
    out = {"other_members_identical": bool(same_files)}
    a = st[st["trip_id"].isin(src["trip_id"])].reset_index(drop=True)
    s0 = src[src["trip_id"].isin(set(a["trip_id"]))].reset_index(drop=True)
    out["rows_kept_same_stops"] = bool((a["trip_id"].to_numpy() == s0["trip_id"].to_numpy()).all() and
                                       (a["stop_id"].to_numpy() == s0["stop_id"].to_numpy()).all())
    nt = ~s0["trip_id"].isin(tram)
    out["non_tram_rows_identical"] = bool((a.loc[nt, "arr"].to_numpy() == s0.loc[nt, "arr"].to_numpy()).all() and
                                          (a.loc[nt, "dep"].to_numpy() == s0.loc[nt, "dep"].to_numpy()).all())
    same_trip = st["trip_id"].to_numpy()[1:] == st["trip_id"].to_numpy()[:-1]
    out["monotone"] = bool(((st["arr"].to_numpy()[1:] >= st["dep"].to_numpy()[:-1]) | ~same_trip).all() and
                           (st["dep"] >= st["arr"]).all())
    f0 = s0[s0["k"] == 0].set_index("trip_id")["dep"]
    f1 = a.groupby("trip_id")["dep"].first()
    out["first_departures_unchanged"] = bool((f1.reindex(f0.index) == f0).all())
    out["trips_source"] = int(src["trip_id"].nunique())
    out["trips_scenario"] = int(st["trip_id"].nunique())
    out["trip_ids_same"] = set(st["trip_id"]) == set(src["trip_id"])
    out["trips_txt_rows"] = int(len(tr))
    hop = st["arr"].to_numpy()[1:] - st["dep"].to_numpy()[:-1]
    ist = st["trip_id"].isin(tram).to_numpy()[1:] & same_trip
    out["tram_hops_0min"] = int((hop[ist] == 0).sum())
    out["tram_hops"] = int(ist.sum())
    if hw_rep is not None:
        out["headway_patterns_retimed"] = int(hw_rep["retimed"].sum())
    ok = out["other_members_identical"] and out["rows_kept_same_stops"] and out["non_tram_rows_identical"] and \
        out["monotone"] and out["first_departures_unchanged"] and (out["trip_ids_same"] or hw_rep is not None)
    out["ok"] = bool(ok)
    if not ok:
        raise AssertionError(f"{scen}: validation failed {out}")
    return out


def speed_stats(scen: str, sv: pd.Series, sh: pd.DataFrame, grp: pd.DataFrame) -> dict:
    """Scheduled tram speed on stretch hops per band before / after (rounded times), saved vehicle-hours."""
    h = hops().copy()
    k = sh.set_index(["trip_id", "k"])["shift"]
    s0 = k.reindex(pd.MultiIndex.from_arrays([h["trip_id"], h["k"]])).to_numpy()
    s1 = k.reindex(pd.MultiIndex.from_arrays([h["trip_id"], h["k"] + 1])).to_numpy()
    h["t_new"] = h["t_s"].to_numpy(float) - (s1 - s0)
    h["t_cont"] = h["t_s"].to_numpy(float) - sv.to_numpy()
    on = h["stretch_dir_id"].notna()
    bands = []
    for b, g in h[on].groupby("band"):
        bands.append({"band": b, "hops": int(len(g)), "km": round(float(g["len_m"].sum()) / 1000, 1),
                      "speed_before": round(float(g["len_m"].sum() / g["t_s"].sum() * 3.6), 2),
                      "speed_after": round(float(g["len_m"].sum() / g["t_new"].sum() * 3.6), 2),
                      "speed_after_continuous": round(float(g["len_m"].sum() / g["t_cont"].sum() * 3.6), 2),
                      "veh_h_saved": round(float((g["t_s"] - g["t_new"]).sum()) / 3600, 1),
                      "veh_h_saved_continuous": round(float(sv[g.index].sum()) / 3600, 1)})
    # share of tram vehicle-km on stretch-bands below 15 km/h (am peak), with the scenario's rounded times
    g = h[on & (h["band"] == "am_peak")]
    sb = g.groupby("stretch_dir_id").agg(L=("len_m", "sum"), T0=("t_s", "sum"), T1=("t_new", "sum"))
    below_min = set(stretch_table().loc[stretch_table()["below_min"] & (stretch_table()["agglomeration"] == AGG), "stretch_dir_id"])
    sb = sb[~sb.index.isin(below_min)]
    slow0 = float(sb.loc[sb["L"] / sb["T0"] * 3.6 < SLOW_KMH, "L"].sum() / sb["L"].sum())
    slow1 = float(sb.loc[sb["L"] / sb["T1"] * 3.6 < SLOW_KMH, "L"].sum() / sb["L"].sum())
    last = sh.groupby("trip_id")["shift"].last()
    return {"bands": bands, "share_vkm_below_15_am_peak_before": round(100 * slow0, 1),
            "share_vkm_below_15_am_peak_after": round(100 * slow1, 1),
            "veh_h_saved_day": round(float(last.sum()) / 3600, 1),
            "veh_h_saved_day_continuous": round(float(sv.sum()) / 3600, 1),
            "trips_shortened": int((last > 0).sum()), "trips": int(len(last)),
            "max_trip_saving_min": round(float(last.max()) / 60, 1) if len(last) else 0.0,
            "groups_changed": int((grp["saving_s"] > 0).sum()), "groups": int(len(grp)),
            "groups_capped_by_free_running": int(grp["capped_by_free"].sum())}


def build(scens: list[str]) -> None:
    for s in scens:
        t0 = time.time()
        r = build_feed(s)
        am = next((b for b in r["bands"] if b["band"] == "am_peak"), {})
        log(f"{s}: feed ok={r['validation']['ok']} am-peak stretch speed {am.get('speed_before')} -> {am.get('speed_after')} km/h, "
            f"saved {r['veh_h_saved_day']} veh-h/day ({time.time() - t0:.0f} s)")
    # check: recomputed band sums vs the stretch table (same hops?)
    h = hops()
    g = h.dropna(subset=["stretch_dir_id"]).groupby(["stretch_dir_id", "band"]).agg(t=("t_s", "sum"), n=("t_s", "size"),
                                                                                    L=("len_m", "sum")).reset_index()
    b = band_table().merge(g, on=["stretch_dir_id", "band"], how="inner")
    chk = {"groups_compared": int(len(b)),
           "max_abs_diff_time_s": float((b["t"] - b["sum_hop_time_s"]).abs().max()),
           "max_rel_diff_length": float(((b["L"] - b["sum_hop_length_m"]).abs() / b["sum_hop_length_m"]).max()),
           "traversals_equal": bool((b["n"] == b["hop_traversals"]).all()),
           "hops_total": int(len(h)), "hops_on_stretch": int(h["stretch_dir_id"].notna().sum()),
           "hops_terminal_shuffle": int(h["shuffle"].sum())}
    write_json(OUT / "hop_check.json", chk)
    cls, w = peer_classes()
    cls.to_csv(OUT / "s3_classes.csv", index=False, lineterminator="\n")
    w.to_csv(OUT / "s3_wroclaw_stretches.csv", index=False, lineterminator="\n")
    log(f"hop check: {chk}")


# ------------------------------------------------------------------ R5
def net_dir(scen: str) -> Path:
    return OUT / "r5" / scen


def net_inputs(scen: str) -> list[Path]:
    return sorted(feed_dir(scen).glob("*.zip"))


def net_sig(scen: str) -> str:
    h = hashlib.sha1()
    for p in [PROD_OSM, *net_inputs(scen)]:
        h.update(p.name.encode())
        h.update(sha_file(p).encode())
    return h.hexdigest()[:16]


def wait_for_memory() -> None:
    import psutil
    while True:
        free = psutil.virtual_memory().available / 2 ** 30
        if free >= MIN_FREE_GB:
            log(f"free memory {free:.1f} GB")
            return
        log(f"free memory {free:.1f} GB < {MIN_FREE_GB} GB: waiting 3 min")
        time.sleep(180)


def load_network(scen: str):
    from r5py import TransportNetwork
    from r5py.util import Config
    d = net_dir(scen)
    sig = net_sig(scen)
    if d.exists() and (not (d / "inputs.sig").exists() or (d / "inputs.sig").read_text() != sig):
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    Config().__dict__["CACHE_DIR"] = d
    t0 = time.time()
    tn = TransportNetwork(PROD_OSM, net_inputs(scen), allow_errors=True)
    (d / "inputs.sig").write_text(sig)
    log(f"{scen}: network ready in {time.time() - t0:.0f} s")
    return tn


@lru_cache(maxsize=1)
def frame():
    """Production origins / destinations of Wrocław and destination weights: census, raw, urban-centre census / raw."""
    from pipeline import access_inputs as AI
    from pipeline import access_uc as U
    d = U.frame(AGG)
    W = np.c_[d["w_census"], d["w_raw"], np.where(d["in_uc"], d["w_census"], 0.0), np.where(d["in_uc"], d["w_raw"], 0.0)]
    return AI.origins(AGG), AI.destinations(AGG), W.astype(np.float64)


WCOLS = ["census", "raw", "uccensus", "ucraw"]


def route_sig(scen: str) -> str:
    from pipeline import access as A
    from pipeline import access_inputs as AI
    parts = {"code": CODE_VERSION, "net": net_sig(scen), "inputs": AI.inputs_hash(AGG), "params": A.unit_params(AGG, "all", "pt_am"),
             "walk": json.loads((AI.ACCESS_INT / AGG / "street" / "walk" / "manifest.json").read_text(encoding="utf-8"))["signature"],
             "w": WCOLS}
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def route_dir(scen: str) -> Path:
    return OUT / "route" / scen


def route_state(scen: str) -> tuple[Path, str, list[int]]:
    from pipeline import access as A
    o, _, _ = frame()
    n = int(np.ceil(len(o) / A.CHUNK))
    d = route_dir(scen)
    s = route_sig(scen)
    man = d / "manifest.json"
    if d.exists() and (not man.exists() or json.loads(man.read_text(encoding="utf-8")).get("signature") != s):
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    if not man.exists():
        write_json(man, {"signature": s, "n_chunks": n, "scenario": scen, "net_sig": net_sig(scen)})
    todo = [k for k in range(n) if not (d / f"chunk_{k:05d}.parquet").exists()]
    return d, s, todo


def route(scens: list[str]) -> None:
    from pipeline import access as A
    from pipeline import access_inputs as AI
    pending = [s for s in scens if route_state(s)[2]]
    if not pending:
        log(f"route: {scens} up to date")
        return
    wait_for_memory()
    from pipeline.r5_env import start
    sys.argv = sys.argv[:1]
    start(xmx=XMX, tmp=OUT / "_tmp")
    import geopandas as gpd
    o, dd, W = frame()
    lon_d, lat_d = AI.TO4326.transform(dd["x"].to_numpy(), dd["y"].to_numpy())
    dests = gpd.GeoDataFrame({"id": dd["cell_id"].to_numpy()}, geometry=gpd.points_from_xy(lon_d, lat_d), crs="EPSG:4326")
    for scen in pending:
        d, s, todo = route_state(scen)
        t_net = time.time()
        tn = load_network(scen)
        task, info = A.make_task(tn, dests, "pt_am")
        write_json(d / "r5_params.json", info)
        jnet = tn._transport_network
        t0 = time.time()
        for k in todo:
            oo = o.iloc[k * A.CHUNK:(k + 1) * A.CHUNK]
            wp, wi, wt = A.walk_cache(AGG, k)
            lon, lat = oo["lon"].to_numpy(), oo["lat"].to_numpy()

            def one(i):
                tt = A.travel_times(task, jnet, lon[i], lat[i])
                r5 = A.reduce_sums(tt, W[:, :1])[0]
                sl = slice(wp[i], wp[i + 1])
                ix = wi[sl]
                tt[ix] = np.minimum(tt[ix], wt[sl].astype(np.int32))
                return A.reduce_sums(tt, W), r5

            t1 = time.time()
            with cf.ThreadPoolExecutor(max_workers=THREADS) as ex:
                res = list(ex.map(one, range(len(oo))))
            out = {"cell_id": oo["cell_id"].to_numpy()}
            sums = np.stack([r[0] for r in res])
            for a, w in enumerate(WCOLS):
                for b, c in enumerate(AI.CUTOFFS):
                    out[f"acc_{w}_{c}"] = sums[:, a, b].astype(np.float32)
            r5 = np.stack([r[1] for r in res])
            for b, c in enumerate(AI.CUTOFFS):
                if c in (30, 45):
                    out[f"r5only_census_{c}"] = r5[:, b].astype(np.float32)
            p = d / f"chunk_{k:05d}.parquet"
            pd.DataFrame(out).to_parquet(p.with_suffix(".tmp"), index=False)
            os.replace(p.with_suffix(".tmp"), p)
            log(f"{scen} chunk {k + 1}/{int(np.ceil(len(o) / A.CHUNK))}: {len(oo)} origins in {time.time() - t1:.1f} s")
        wall = time.time() - t0
        write_json(d / "timing.json", {"network_s": round(t0 - t_net, 1), "routing_s": round(wall, 1), "threads": THREADS,
                                       "xmx": XMX, "origins": int(len(o)), "chunks_routed_now": len(todo)})
        progress(f"routing {scen} done: {len(todo)} chunks in {wall:.0f} s (network {t0 - t_net:.0f} s, {THREADS} threads)")
        del tn, jnet, task
        gc.collect()


def load_route(scen: str) -> pd.DataFrame | None:
    from pipeline import access as A
    o, _, _ = frame()
    n = int(np.ceil(len(o) / A.CHUNK))
    d = route_dir(scen)
    man = d / "manifest.json"
    if not man.exists() or json.loads(man.read_text(encoding="utf-8")).get("signature") != route_sig(scen):
        return None
    ps = [d / f"chunk_{k:05d}.parquet" for k in range(n)]
    if not all(p.exists() for p in ps):
        return None
    return pd.concat([pd.read_parquet(p) for p in ps], ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "route", "aggregate"])
    ap.add_argument("--scen", nargs="*", default=list(SCENARIOS))
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.scen)
    elif a.cmd == "route":
        build(a.scen)
        route(a.scen)
    else:
        from pipeline import whatif_tram_out
        whatif_tram_out.main()


if __name__ == "__main__":
    main()
