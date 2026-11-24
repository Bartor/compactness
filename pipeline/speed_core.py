"""Shared foundation for the scheduled-speed outputs (speed_tables, tram_stretches, speed_areas).

Measure: "rozkładowa prędkość komunikacyjna" = route length / scheduled time including stops, always from the
timetable (never real).  This module turns the de-duplicated service layer (pipeline.gtfs_service, variant "all";
each row keeps its feed, so unofficial feeds can be flagged or filtered) into one row per *hop* = a vehicle running
from one stop to the next stop of the same trip.

Hop table (``hops(agg, day_type)``, cached in data/interim/speed/hops_<agg>_<day>.parquet)
* time ``t_s`` = arrival at the next stop - departure from the stop (GTFS times; the feeds give whole minutes and
  no separate dwell, so the dwell at a stop sits inside the hop time)
* length: along the trip's GTFS shape between the two stops (``d_shape``) when the trip's stop pattern projects
  onto its shape; otherwise the straight stop-to-stop distance (``d_straight``).  ``len_src`` says which:
  ``shape`` / ``straight_noshape`` (trip has no shape) / ``straight_badshape`` (one of the two stops farther than
  MAX_OFF from the shape, no monotone projection of the pattern, or a hop where the shape is shorter than the
  straight line).  The fallback is per hop: a shape that leaves out a terminal loop only affects the end hops.
* projection: every stop of a pattern (feed, shape_id, stop sequence) is projected on the shape; candidate positions
  are the local minima of the stop-to-shape distance within MAX_OFF, and a Viterbi pass picks the sequence with
  the smallest summed offset whose position along the shape never decreases (tolerance 5 m).  Loops and lines that
  pass the same street twice are handled by the monotone constraint.
* ``band``: time band of the hop's departure (config ``speed_time_bands``); ``trip_band``: band of the trip's
  first departure (used by the line tables).  Times past 24:00 are taken modulo 24 h.
* ``in_buf``: both stops inside FUA + 15 km (rail trips of the nationwide feed run far outside).

Geometry helpers cut a hop out of its shape (EPSG:2180) for the area and stretch steps.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline import gtfs_service as gs
from pipeline.common import CRS_METRIC, INTERIM, load_config
from pipeline.gtfs_io import Feed

CODE_VERSION = "speed-core-2026-11-24.3"
CACHE = INTERIM / "speed"
VARIANT = "all"
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
AGG_NAMES = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
             "trojmiasto": "Trójmiasto", "gzm": "GZM"}
MODES = ["tram", "bus", "trolleybus", "metro", "rail"]
MODE_PL = {"tram": "tramwaj", "bus": "autobus", "trolleybus": "trolejbus", "metro": "metro", "rail": "kolej"}
# largest distance (m) between a stop and its trip's shape for the shape to be used; rail and metro stations are
# single points that can lie far from the track axis
MAX_OFF = {"tram": 80.0, "bus": 80.0, "trolleybus": 80.0, "metro": 250.0, "rail": 300.0, "ferry": 300.0, "other": 80.0}
BACK_TOL_M = 5.0
N_CAND = 6
WORKERS = 18
# fixed, city-independent speed classes (km/h) for every output: below 12, 12-15, 15-18, 18-22, 22-26, 26 and above
CLASS_BREAKS = [12.0, 15.0, 18.0, 22.0, 26.0]
CLASS_LABELS = ["poniżej 12", "12–15", "15–18", "18–22", "22–26", "26 i więcej"]


def speed_class(v) -> np.ndarray:
    """Class index 0..5 of speeds (km/h) on CLASS_BREAKS (a value on a break belongs to the upper class); NaN -> -1."""
    v = np.asarray(v, dtype=float)
    out = np.searchsorted(np.asarray(CLASS_BREAKS), v, side="right").astype(int)
    return np.where(np.isfinite(v), out, -1)


# ------------------------------------------------------------------ config: days and bands
def days() -> dict[str, str]:
    cfg = load_config()
    return {"weekday": cfg["reference_day"], "saturday": cfg["reference_saturday"]}


DAY_BANDSET = {"weekday": "weekday", "saturday": "weekend"}
DAY_PL = {"weekday": "środa", "saturday": "sobota"}


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 3600 + int(m) * 60


@functools.lru_cache(maxsize=4)
def bands(day_type: str) -> tuple:
    """Bands of a day type as tuples (id, label, start_s, end_s, minutes) in config order."""
    out = []
    for b in load_config()["speed_time_bands"][DAY_BANDSET[day_type]]:
        s, e = _hm(b["start"]), _hm(b["end"])
        mins = ((e - s) % 86400) / 60
        out.append((b["id"], b["label"], s, e, mins))
    return tuple(out)


def band_ids(day_type: str) -> list[str]:
    return [b[0] for b in bands(day_type)]


def band_label(day_type: str, bid: str) -> str:
    for b in bands(day_type):
        if b[0] == bid:
            s, e = b[2] // 3600, b[3] // 3600
            return f"{b[1]} {s:02d}–{e:02d}"
    return bid


def band_minutes(day_type: str, bid: str) -> float:
    return {b[0]: b[4] for b in bands(day_type)}[bid]


def band_of(sec, day_type: str) -> np.ndarray:
    s = np.mod(np.asarray(sec, dtype=float), 86400)
    out = np.full(len(s), None, dtype=object)
    for bid, _, a, b, _ in bands(day_type):
        m = (s >= a) & (s < b) if a < b else (s >= a) | (s < b)
        out[m & pd.isna(out)] = bid
    return out


# ------------------------------------------------------------------ shapes
def _shape_cache_path(fid: str):
    return CACHE / f"shapes_{fid}.parquet"


def _zip_sig(fid: str) -> str:
    from pipeline.gtfs_io import latest_zip
    p = latest_zip(fid)
    s = p.stat()
    return f"{p.parent.name}/{p.name}:{s.st_size}"


def shapes_table(fid: str) -> pd.DataFrame:
    """shape_id, x, y (EPSG:2180) in sequence order; empty when the feed has no shapes.txt (cached)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    p, sf = _shape_cache_path(fid), CACHE / f"shapes_{fid}.sig"
    sig = _zip_sig(fid)
    if p.exists() and sf.exists() and sf.read_text() == sig:
        return pd.read_parquet(p)
    f = Feed(fid)
    sh = f.table("shapes.txt", ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
    if sh is None or sh.empty:
        out = pd.DataFrame({"shape_id": pd.Series(dtype=str), "x": pd.Series(dtype=float), "y": pd.Series(dtype=float)})
    else:
        sh["lat"] = pd.to_numeric(sh["shape_pt_lat"], errors="coerce")
        sh["lon"] = pd.to_numeric(sh["shape_pt_lon"], errors="coerce")
        sh["seq"] = pd.to_numeric(sh["shape_pt_sequence"], errors="coerce")
        sh = sh.dropna(subset=["lat", "lon", "seq"]).sort_values(["shape_id", "seq"], kind="stable")
        tr = Transformer.from_crs("EPSG:4326", CRS_METRIC, always_xy=True)
        x, y = tr.transform(sh["lon"].to_numpy(), sh["lat"].to_numpy())
        out = pd.DataFrame({"shape_id": sh["shape_id"].astype(str).to_numpy(), "x": x, "y": y})
    out.to_parquet(p, index=False)
    sf.write_text(sig)
    return out


_SHAPES: dict = {}


def shape_arrays(fid: str) -> dict:
    """shape_id -> (xy (n, 2), cumulative length (n,)) with repeated points removed."""
    if fid in _SHAPES:
        return _SHAPES[fid]
    t = shapes_table(fid)
    out = {}
    if len(t):
        ids = t["shape_id"].to_numpy()
        xy = t[["x", "y"]].to_numpy()
        starts = np.flatnonzero(np.r_[True, ids[1:] != ids[:-1]])
        ends = np.r_[starts[1:], len(ids)]
        for s, e in zip(starts, ends):
            p = xy[s:e]
            if len(p) > 1:
                keep = np.r_[True, np.hypot(*np.diff(p, axis=0).T) > 0.01]
                p = p[keep]
            if len(p) < 2:
                continue
            cum = np.r_[0.0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
            out[ids[s]] = (p, cum)
    _SHAPES[fid] = out
    return out


def project_stops(p: np.ndarray, cum: np.ndarray, s: np.ndarray, max_off: float):
    """Monotone projection of stops ``s`` (k, 2) on polyline ``p`` -> (along (k,), offset (k,)) or None.

    A stop farther than ``max_off`` from the shape (e.g. a terminal loop the shape leaves out, as in feed lodz) gets
    NaN; only the hops between two projected stops then use the shape.  None when fewer than two stops project."""
    a, b = p[:-1], p[1:]
    ab = b - a
    L2 = (ab ** 2).sum(1)
    L2[L2 == 0] = 1e-9
    seglen = np.sqrt(L2)
    k = len(s)
    cand_al, cand_d, idx_ok = [], [], []
    for i in range(k):
        if not np.isfinite(s[i]).all():
            continue
        t = np.clip(((s[i] - a) * ab).sum(1) / L2, 0, 1)
        q = a + ab * t[:, None]
        d = np.hypot(*(s[i] - q).T)
        al = cum[:-1] + t * seglen
        n = len(d)
        if n > 2:
            left = np.r_[np.inf, d[:-1]]
            right = np.r_[d[1:], np.inf]
            loc = (d <= left) & (d <= right)
        else:
            loc = np.ones(n, bool)
        idx = np.flatnonzero(loc & (d <= max_off))
        if len(idx) == 0:
            continue
        if len(idx) > N_CAND:
            idx = idx[np.argsort(d[idx], kind="stable")[:N_CAND]]
        idx = np.sort(idx)
        cand_al.append(al[idx]); cand_d.append(d[idx]); idx_ok.append(i)
    m = len(idx_ok)
    if m < 2:
        return None
    # Viterbi: minimise summed offset subject to non-decreasing position
    cost = cand_d[0].copy()
    back = []
    for i in range(1, m):
        ok = cand_al[i - 1][None, :] <= cand_al[i][:, None] + BACK_TOL_M
        c = np.where(ok, cost[None, :], np.inf)
        j = np.argmin(c, axis=1)
        best = c[np.arange(len(j)), j]
        back.append(j)
        cost = best + cand_d[i]
        if not np.isfinite(cost).any():
            return None
    sel = [int(np.argmin(cost))]
    for i in range(m - 2, -1, -1):
        sel.append(int(back[i][sel[-1]]))
    sel = sel[::-1]
    along = np.full(k, np.nan)
    off = np.full(k, np.nan)
    al_ok = np.maximum.accumulate(np.array([cand_al[i][sel[i]] for i in range(m)]))
    along[idx_ok] = al_ok
    off[idx_ok] = [cand_d[i][sel[i]] for i in range(m)]
    return along, off


def _project_task(args):
    fid, items = args
    shp = shape_arrays(fid)
    out = []
    for pid, shape_id, mode, xy in items:
        r = None
        if shape_id in shp:
            p, cum = shp[shape_id]
            r = project_stops(p, cum, xy, MAX_OFF.get(mode, 80.0))
        out.append((pid, r))
    return out


# ------------------------------------------------------------------ hop table
def _hop_sig(agg: str, day: str) -> str:
    payload = [CODE_VERSION, gs.RULES_VERSION, agg, day, gs._build_sig(agg, VARIANT), MAX_OFF,
               load_config()["speed_time_bands"]]
    return hashlib.sha1(json.dumps(payload, default=str).encode()).hexdigest()[:12]


def _build_hops(agg: str, day_type: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    day = days()[day_type]
    t = gs.active_trips(agg, day, VARIANT)
    st = gs.stop_times(agg, day, VARIANT)
    st = st.sort_values(["feed", "uid", "stop_sequence"], kind="stable").reset_index(drop=True)
    tt = t.set_index("uid")
    # ---- patterns
    key = st.groupby("uid", sort=True)["suid"].agg(">".join)
    pat = pd.DataFrame({"uid": key.index, "stops_key": key.to_numpy()})
    pat["feed"] = pat["uid"].map(tt["feed"])
    pat["shape_id"] = pat["uid"].map(tt["shape_id"]).astype(object).where(lambda s: s.notna(), "")
    pat["mode"] = pat["uid"].map(tt["route_class"])
    pat["pkey"] = pat["feed"] + "|" + pat["shape_id"].astype(str) + "|" + pat["stops_key"]
    up = pat.drop_duplicates("pkey").sort_values("pkey", kind="stable").reset_index(drop=True)
    up["pid"] = np.arange(len(up))
    pat = pat.merge(up[["pkey", "pid"]], on="pkey", how="left")
    # stop coordinates of the representative trip of each pattern
    first_idx = st.groupby("uid", sort=True).indices
    tasks: dict[str, list] = {}
    for r in up.itertuples(index=False):
        if not r.shape_id:
            continue
        ix = first_idx[r.uid]
        xy = st.loc[ix, ["x", "y"]].to_numpy(dtype=float)
        tasks.setdefault(r.feed, []).append((r.pid, str(r.shape_id), r.mode, xy))
    chunks = []
    for fid in sorted(tasks):
        items = tasks[fid]
        n = max(1, int(np.ceil(len(items) / 400)))
        for i in range(n):
            chunks.append((fid, items[i::n]))
    res: dict[int, tuple] = {}
    if chunks:
        with ProcessPoolExecutor(max_workers=min(WORKERS, len(chunks))) as ex:
            for part in ex.map(_project_task, chunks):
                for pid, r in part:
                    res[pid] = r
    up["shape_ok"] = up["pid"].map(lambda i: res.get(i) is not None)
    # ---- hops
    uid = st["uid"].to_numpy()
    same = uid[1:] == uid[:-1]
    i0 = np.flatnonzero(same)
    i1 = i0 + 1
    # k = position of the from-stop within the trip
    h = pd.DataFrame({"uid": uid[i0], "k": st.groupby("uid", sort=False).cumcount().to_numpy()[i0].astype(np.int32)})
    h["from_suid"] = st["suid"].to_numpy()[i0]
    h["to_suid"] = st["suid"].to_numpy()[i1]
    for c, src, ix in (("x0", "x", i0), ("y0", "y", i0), ("x1", "x", i1), ("y1", "y", i1)):
        h[c] = st[src].to_numpy()[ix].astype("float32")
    h["dep_s"] = st["dep_s"].to_numpy()[i0].astype("float64")
    h["arr_s"] = st["arr_s"].to_numpy()[i1].astype("float64")
    h["t_s"] = (h["arr_s"] - h["dep_s"]).astype("float32")
    h["in_buf"] = st["in_buffer"].to_numpy()[i0] & st["in_buffer"].to_numpy()[i1]
    h["d_straight"] = np.hypot(h["x1"].astype(float) - h["x0"], h["y1"].astype(float) - h["y0"]).astype("float32")
    h = h.merge(pat[["uid", "pid"]], on="uid", how="left")
    # along positions
    a0 = np.full(len(h), np.nan)
    a1 = np.full(len(h), np.nan)
    pidv = h["pid"].to_numpy()
    kv = h["k"].to_numpy()
    order = np.argsort(pidv, kind="stable")
    ps = pidv[order]
    starts = np.flatnonzero(np.r_[True, ps[1:] != ps[:-1]])
    ends = np.r_[starts[1:], len(ps)]
    for s_, e_ in zip(starts, ends):
        r = res.get(int(ps[s_]))
        if r is None:
            continue
        al = r[0]
        rows = order[s_:e_]
        a0[rows] = al[kv[rows]]
        a1[rows] = al[kv[rows] + 1]
    h["a0"], h["a1"] = a0, a1
    h["d_shape"] = (h["a1"] - h["a0"]).astype("float32")
    bad = h["d_shape"].notna() & (h["d_shape"] < 0.9 * h["d_straight"] - 20)
    has_shape = h["pid"].map(up.set_index("pid")["shape_id"]).astype(str).ne("")
    h["len_src"] = np.where(h["d_shape"].notna() & ~bad, "shape",
                            np.where(has_shape, "straight_badshape", "straight_noshape"))
    h["len_m"] = np.where(h["len_src"] == "shape", h["d_shape"], h["d_straight"]).astype("float32")
    # trip attributes
    for c, src in (("feed", "feed"), ("line", "route_short_name"), ("mode", "route_class"),
                   ("direction_id", "direction_id"), ("first_dep_s", "first_dep_s"), ("repl_bus", "is_replacement_bus")):
        h[c] = h["uid"].map(tt[src])
    h["direction_id"] = h["direction_id"].astype(object).where(h["direction_id"].notna(), None).astype(str)
    h["band"] = band_of(h["dep_s"].to_numpy(), day_type)
    h["trip_band"] = band_of(h["first_dep_s"].to_numpy(), day_type)
    h["shape_id"] = h["pid"].map(up.set_index("pid")["shape_id"]).astype(str)
    cols = ["feed", "uid", "line", "mode", "direction_id", "repl_bus", "pid", "shape_id", "k", "from_suid", "to_suid",
            "x0", "y0", "x1", "y1", "dep_s", "arr_s", "t_s", "first_dep_s", "band", "trip_band", "in_buf",
            "d_straight", "d_shape", "a0", "a1", "len_m", "len_src"]
    h = h[cols].sort_values(["feed", "uid", "k"], kind="stable").reset_index(drop=True)
    up = up[["pid", "feed", "shape_id", "mode", "uid", "shape_ok"]].rename(columns={"uid": "rep_uid"})
    return h, up


def hops(agg: str, day_type: str, refresh: bool = False) -> pd.DataFrame:
    return _get(agg, day_type, refresh)[0]


def patterns(agg: str, day_type: str) -> pd.DataFrame:
    return _get(agg, day_type)[1]


def _get(agg: str, day_type: str, refresh: bool = False):
    CACHE.mkdir(parents=True, exist_ok=True)
    day = days()[day_type]
    base = CACHE / f"hops_{agg}_{day}"
    sigf = CACHE / f"hops_{agg}_{day}.sig"
    sig = _hop_sig(agg, day)
    ph, pp = base.with_suffix(".parquet"), CACHE / f"patterns_{agg}_{day}.parquet"
    if not refresh and sigf.exists() and sigf.read_text() == sig and ph.exists() and pp.exists():
        return pd.read_parquet(ph), pd.read_parquet(pp)
    t0 = time.time()
    h, up = _build_hops(agg, day_type)
    h.to_parquet(ph, index=False)
    up.to_parquet(pp, index=False)
    sigf.write_text(sig)
    print(f"  hops {agg} {day}: {len(h):,} hops, {len(up):,} patterns, {time.time() - t0:.0f} s", flush=True)
    return h, up


# ------------------------------------------------------------------ geometry of a hop
def cut(p: np.ndarray, cum: np.ndarray, a0: float, a1: float) -> np.ndarray:
    """Part of polyline (p, cum) between positions a0 <= a1 (m) as an (n, 2) array (at least 2 points)."""
    a0 = float(np.clip(a0, 0, cum[-1])); a1 = float(np.clip(a1, a0, cum[-1]))
    i0 = int(np.searchsorted(cum, a0, side="right"))
    i1 = int(np.searchsorted(cum, a1, side="left"))

    def at(a):
        j = int(np.clip(np.searchsorted(cum, a, side="right") - 1, 0, len(cum) - 2))
        L = cum[j + 1] - cum[j]
        f = 0.0 if L <= 0 else (a - cum[j]) / L
        return p[j] + (p[j + 1] - p[j]) * f

    mid = p[i0:i1] if i1 > i0 else np.empty((0, 2))
    return np.vstack([at(a0), mid, at(a1)])


def hop_geometry(h: pd.Series | tuple, shp: dict) -> np.ndarray:
    """Polyline of one hop: shape part when len_src == 'shape', else the straight segment."""
    if h.len_src == "shape" and h.shape_id in shp:
        p, cum = shp[h.shape_id]
        return cut(p, cum, h.a0, h.a1)
    return np.array([[h.x0, h.y0], [h.x1, h.y1]], dtype=float)


def terminal_shuffle(h: pd.DataFrame, agg: str) -> pd.Series:
    """True for hops that open or close a trip between two stops of the same (normalised) name, e.g. arrival platform ->
    departure platform of a terminal loop.  Their time often holds a layover (Łódź "Rondo Powstańców 1863r.": 35 m in
    4 min; Warszawa "Al. Lotników": 183 m in 4 min), so the stretch and area steps leave them out; the line tables keep
    them (trip time = last arrival - first departure, as pipeline.tram_speed)."""
    st = gs.stops(agg, VARIANT)
    nk = dict(zip(st["suid"], gs._norm_name(st["stop_name"].astype(str))))
    first = h["k"].eq(0)
    last = h["k"].eq(h.groupby("uid")["k"].transform("max"))
    same = h["from_suid"].map(nk).eq(h["to_suid"].map(nk))
    return (first | last) & same


def feed_official() -> dict[str, bool]:
    off = set(load_config().get("official_feeds") or [])
    return {f: f in off for f in load_config()["feeds"]}


def main() -> None:
    import sys
    refresh = "--refresh" in sys.argv
    t0 = time.time()
    for agg in AGGS:
        for dt in ("weekday", "saturday"):
            _get(agg, dt, refresh)
    print(f"hop tables ready in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
