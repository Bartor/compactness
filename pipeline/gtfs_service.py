"""Shared, de-duplicated GTFS service layer (phase 2): the one place that decides "which trips count".

Public API (stable; other modules code against it)
-------------------------------------------------
``VARIANTS``                          ("official", "all")
``feeds_for(agg_id, variant)``        feed ids serving the agglomeration (config ``feeds.<id>.agglomerations``);
                                      "official" keeps only config ``official_feeds``
``active_trips(agg_id, day, variant)``  one row per trip running on ``day`` after all rules below
``stop_times(agg_id, day, variant)``    stop_times rows of exactly those trips
``stops(agg_id, variant)``              GeoDataFrame (EPSG:2180) of stops inside FUA + 15 km buffer

Rules, in the order they are applied to the trips running on ``day`` (counts for each step land in
``results/qa/transit/service_summary.csv``)
1. ``config.yaml`` feeds.<id>.drop_routes / drop_agencies (applied in ``pipeline.gtfs_io``; counted here).
2. ``polish_trains`` agency ``SKM`` (SKM Warszawa) is dropped: the same trips are in ``warsaw_ztm``
   (284 vs 284 trips, 100 % match in phase 0).  SKM Trojmiasto is agency ``SKMT`` and stays.
3. Rail feeds (config ``rail: true``, i.e. the nationwide ``polish_trains``): only trips with at least one
   stop inside the agglomeration's FUA + 15 km buffer stay; all stop_times rows of a kept trip stay and
   the column ``in_buffer`` marks which stops are inside.  Other feeds are not clipped (each serves one area).
4. Exact duplicate trips inside one feed: identical route_id, direction_id, block_id, first departure and
   identical stop sequence (stops compared by position rounded to 1 m, because GZM repeats stop records
   under different ids and names) with identical arrival/departure times, running on the same day (even under
   different service_id), different trip_id.  Only the smallest trip_id stays.  (In practice this is GZM:
   ~23 % of its trips.)
4b. Block duplicates inside one feed: same route, direction, non-null block_id, first departure, last arrival
   and number of stops, but stop positions that differ slightly (GZM: 242 pairs, two versions of the same
   trip with a stop moved by up to 350 m).  One vehicle (block) cannot run two such trips, so the one with the
   smaller trip_id stays.
5. Cross-feed duplicates inside the agglomeration and variant: key = route_short_name + normalised name of
   the first stop + departure minute.  Every (feed, line) pair is reported; the lower-priority copy is
   dropped only when >= 90 % (and >= 3) of that line's trips match a higher-priority feed.  Priority:
   city/agency feed before ``polish_trains``, official before unofficial, then config order.  Only the
   matched trips are dropped.  A pair below the threshold is reported, never dropped.
6. Frequencies: ``frequencies.txt`` is expanded (only ``warsaw_ztm`` metro uses it) into one trip per run,
   trip_id ``<id>~<k>``; stop times are shifted by the run's start.

``is_replacement_bus`` = route_type 3 inside ``polish_trains`` / ``warsaw_wkd`` (rail replacement buses,
ZKA).  They stay in the tables (route_class "bus"), callers exclude them from rail measures.

Caches: ``data/interim/gtfs_service/``.  Per feed (``feed_<id>.parquet``) the day-independent trip table; per
(agglomeration, day, variant) ``trips`` / ``stop_times`` / ``summary``.  Both are invalidated by a signature of
the feed zips (name, size, mtime), the drop settings, the official list and ``RULES_VERSION``.
Row order is deterministic (feed, uid, stop_sequence).

Run ``python -m pipeline.gtfs_service`` to build the 7 phase-1 agglomerations x {reference day, Saturday} x
both variants and write ``results/qa/transit/service_summary.csv`` (+ cross_feed_duplicates.csv).
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from pipeline.boundaries import load_agglomeration
from pipeline.common import CRS_METRIC, INTERIM, RESULTS, load_config, write_meta
from pipeline.gtfs_io import (Feed, drop_spec, dropped_route_ids, frequency_runs, route_class, service_dates,
                              stop_events, trip_stats)

VARIANTS = ("official", "all")
PHASE1 = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
RULES_VERSION = "2026-11-24.4"
CACHE = INTERIM / "gtfs_service"
QA = RESULTS / "qa" / "transit"

# rules that are not (yet) keys in config.yaml; a config block ``service_layer:`` with the same keys overrides them
DEFAULT_RULES = {
    "drop_agencies": {"polish_trains": ["SKM"]},          # SKM Warszawa = same trips as warsaw_ztm
    "replacement_bus_feeds": ["polish_trains", "warsaw_wkd"],
    "cross_feed_min_share": 0.9,
    "cross_feed_min_trips": 3,
}


def rules() -> dict:
    r = json.loads(json.dumps(DEFAULT_RULES))
    r.update((load_config().get("service_layer") or {}))
    return r


def _cfg_feeds() -> dict:
    return load_config()["feeds"]


def feeds_for(agg_id: str, variant: str = "all") -> list[str]:
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}")
    cfg = load_config()
    off = set(cfg.get("official_feeds") or [])
    out = [f for f, c in cfg["feeds"].items() if agg_id in (c.get("agglomerations") or [])]
    return [f for f in out if variant == "all" or f in off]


def _prio(fid: str) -> tuple:
    cfg = load_config()
    order = list(cfg["feeds"])
    return (1 if fid == "polish_trains" else 0, 0 if fid in set(cfg.get("official_feeds") or []) else 1, order.index(fid))


# ------------------------------------------------------------------ signatures / caches
def _zip_sig(fid: str) -> str:
    from pipeline.gtfs_io import latest_zip
    p = latest_zip(fid)
    s = p.stat()
    return f"{p.parent.name}/{p.name}:{s.st_size}:{s.st_mtime_ns}"


def _feed_sig(fid: str) -> str:
    dr, da = drop_spec(Feed(fid))
    r = rules()
    payload = [RULES_VERSION, _zip_sig(fid), sorted(dr), sorted(da), sorted(r["drop_agencies"].get(fid, []))]
    return hashlib.sha1(json.dumps(payload).encode()).hexdigest()[:12]


def _build_sig(agg: str, variant: str) -> str:
    cfg = load_config()
    payload = [RULES_VERSION, agg, variant, [(f, _feed_sig(f)) for f in feeds_for(agg, variant)],
               sorted(cfg.get("official_feeds") or []), rules(), cfg.get("edge_buffer_km"),
               cfg["agglomerations"][agg].get("fua_codes"), cfg["agglomerations"][agg].get("boundary_variant")]
    return hashlib.sha1(json.dumps(payload, default=str).encode()).hexdigest()[:12]


def _norm_name(s: pd.Series) -> pd.Series:
    """Stop-name key: casefold, drop trailing platform numbers (' 01'), collapse spaces."""
    x = s.fillna("").str.casefold().str.replace(r"\s+", " ", regex=True).str.strip()
    x = x.str.replace(r"[\s,]+(nż|nz|\d{1,3}[a-z]?)$", "", regex=True)
    x = x.str.replace(r"\s+(peron|tor)\s*\S*$", "", regex=True)
    return x


# ------------------------------------------------------------------ per feed, day independent
def _to_xy(lat: pd.Series, lon: pd.Series):
    tr = Transformer.from_crs("EPSG:4326", CRS_METRIC, always_xy=True)
    ok = lat.notna() & lon.notna()
    x = np.full(len(lat), np.nan)
    y = np.full(len(lat), np.nan)
    if ok.any():
        xx, yy = tr.transform(lon[ok].to_numpy(), lat[ok].to_numpy())
        x[ok.to_numpy()], y[ok.to_numpy()] = xx, yy
    return x, y


@functools.lru_cache(maxsize=64)
def feed_stops(fid: str) -> pd.DataFrame:
    """All stops of a feed with EPSG:2180 coordinates (NaN when the feed gives none)."""
    f = Feed(fid)
    st = f.table("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"])
    for c in ("stop_name", "location_type", "parent_station"):
        if c not in st:
            st[c] = None
    st["lat"] = pd.to_numeric(st["stop_lat"], errors="coerce")
    st["lon"] = pd.to_numeric(st["stop_lon"], errors="coerce")
    zero = (st["lat"] == 0) & (st["lon"] == 0)       # placeholder coordinates (lodz stops 3876, 3877)
    st.loc[zero, ["lat", "lon"]] = np.nan
    st["x"], st["y"] = _to_xy(st["lat"], st["lon"])
    st["location_type"] = pd.to_numeric(st["location_type"], errors="coerce").fillna(0).astype(int)
    return st.drop(columns=["stop_lat", "stop_lon"]).drop_duplicates("stop_id").reset_index(drop=True)


def _trip_signatures(ev: pd.DataFrame, stp: pd.DataFrame) -> pd.Series:
    """Order-sensitive 64-bit fingerprint of each trip's (stop position, arr, dep) sequence; index trip_id.

    A stop is identified by its position rounded to 1 m (stop_id when the feed gives no coordinates), because
    GZM repeats stop records at the same place under different ids and names (e.g. 178 / 13065)."""
    ev = ev.reset_index(drop=True)
    code = ev["trip_id"].cat.codes.to_numpy()
    n = len(ev)
    starts = np.flatnonzero(np.r_[True, code[1:] != code[:-1]])
    rank = np.arange(n) - np.repeat(starts, np.diff(np.r_[starts, n]))
    cats = ev["stop_id"].cat.categories
    sx = stp.set_index("stop_id")["x"].reindex(cats).to_numpy()
    sy = stp.set_index("stop_id")["y"].reindex(cats).to_numpy()
    sc = ev["stop_id"].cat.codes.to_numpy()
    px, py = sx[sc], sy[sc]
    ok = np.isfinite(px) & np.isfinite(py)
    pos = np.where(ok, np.round(np.nan_to_num(px)) * 1_000_003 + np.round(np.nan_to_num(py)), 0).astype(np.int64).astype(np.uint64)
    hs = np.where(ok, pd.util.hash_array(pos), pd.util.hash_array(ev["stop_id"].astype(object).to_numpy().astype(str)))
    arr = ev["arr_s"].fillna(-1).to_numpy().astype(np.int64).astype(np.uint64)
    dep = ev["dep_s"].fillna(-1).to_numpy().astype(np.int64).astype(np.uint64)
    with np.errstate(over="ignore"):
        h = hs ^ (arr * np.uint64(0x9E3779B97F4A7C15)) ^ (dep * np.uint64(0xC2B2AE3D27D4EB4F)) \
            ^ (rank.astype(np.uint64) * np.uint64(0x165667B19E3779F9))
        h ^= h >> np.uint64(33)
        h *= np.uint64(0xFF51AFD7ED558CCD)
        h ^= h >> np.uint64(33)
        tot = np.add.reduceat(h, starts)
    tid = ev["trip_id"].astype(object).to_numpy()[starts]
    cnt = np.diff(np.r_[starts, n])
    return pd.Series([f"{int(t):016x}.{int(c)}" for t, c in zip(tot, cnt)], index=pd.Index(tid, name="trip_id"))


def _fix_placeholder_distances(ts: pd.DataFrame, ev: pd.DataFrame, stp: pd.DataFrame) -> pd.DataFrame:
    """gtfs_io sums stop distances with lat = lon = 0 placeholders (thousands of km).  For trips that touch such a stop,
    recompute ``dist_stops_m`` skipping the stop and fall back ``dist_m`` to it when the trip has no shape."""
    bad_ids = set(stp.loc[stp["x"].isna(), "stop_id"])
    if not bad_ids:
        return ts
    hit = ev.loc[ev["stop_id"].astype(object).isin(bad_ids), "trip_id"].astype(object).unique()
    if len(hit) == 0:
        return ts
    e = ev[ev["trip_id"].astype(object).isin(set(hit))][["trip_id", "stop_id", "stop_sequence"]].copy()
    e["trip_id"] = e["trip_id"].astype(object)
    e["stop_id"] = e["stop_id"].astype(object)
    e = e.merge(stp[["stop_id", "x", "y"]], on="stop_id", how="left").dropna(subset=["x", "y"])
    e = e.sort_values(["trip_id", "stop_sequence"], kind="stable")
    same = e["trip_id"].to_numpy()[1:] == e["trip_id"].to_numpy()[:-1]
    seg = np.where(same, np.hypot(np.diff(e["x"].to_numpy()), np.diff(e["y"].to_numpy())), 0.0)
    new = pd.Series(np.r_[0.0, seg], index=e.index).groupby(e["trip_id"]).sum()
    m = ts["trip_id"].isin(set(hit))
    ts.loc[m, "dist_stops_m"] = ts.loc[m, "trip_id"].map(new)
    nos = m & (ts["dist_method"] == "stops")
    ts.loc[nos, "dist_m"] = ts.loc[nos, "dist_stops_m"]
    return ts


def feed_table(fid: str) -> pd.DataFrame:
    """Day-independent trip table of one feed (cached): route names, shape/stop distances, fingerprint."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path, sigf = CACHE / f"feed_{fid}.parquet", CACHE / f"feed_{fid}.sig"
    sig = _feed_sig(fid)
    if path.exists() and sigf.exists() and sigf.read_text() == sig:
        return pd.read_parquet(path)
    f = Feed(fid)
    ts = trip_stats(f).copy()
    r = f.table("routes.txt", ["route_id", "route_short_name", "route_long_name"])
    r = r.drop_duplicates("route_id")
    for c in ("route_short_name", "route_long_name"):
        if c not in r:
            r[c] = None
    ts = ts.merge(r, on="route_id", how="left")
    ev = stop_events(f)
    stp = feed_stops(fid)
    ts = _fix_placeholder_distances(ts, ev, stp)
    ts["sig"] = ts["trip_id"].map(_trip_signatures(ev, stp))
    stp = stp.set_index("stop_id")
    ts["first_stop_key"] = _norm_name(ts["first_stop_id"].map(stp["stop_name"]))
    rs = rules()
    ts["is_replacement_bus"] = (fid in rs["replacement_bus_feeds"]) & (ts["route_type"].astype(str) == "3")
    for c in ("agency_id", "block_id", "direction_id", "shape_id"):
        if c not in ts:
            ts[c] = None
    ts["agency_id"] = ts["agency_id"].astype(object)
    # one SKM-like rule per feed: mark rows dropped by the agency rule
    ts["drop_agency_rule"] = ts["agency_id"].isin(set(map(str, rs["drop_agencies"].get(fid, []))))
    ts["feed"] = fid
    ts["runs"] = ts["runs"].astype(int)
    keep = ["feed", "trip_id", "service_id", "route_id", "route_short_name", "route_long_name", "agency_id", "route_type",
            "route_class", "direction_id", "shape_id", "block_id", "n_stops", "first_dep_s", "last_arr_s", "dist_m",
            "dist_method", "dist_stops_m", "shape_len_m", "first_stop_id", "first_stop_key", "sig", "runs",
            "is_replacement_bus", "drop_agency_rule"]
    ts = ts[keep].sort_values(["trip_id"], kind="stable").reset_index(drop=True)
    # trips of config-dropped routes, per service (only for the counts in the summary)
    bad = dropped_route_ids(f)
    if bad:
        tr0 = f.table("trips.txt", ["trip_id", "route_id", "service_id"])
        cd = tr0[tr0["route_id"].isin(bad)].groupby("service_id").size().rename("n").reset_index()
    else:
        cd = pd.DataFrame({"service_id": pd.Series(dtype=str), "n": pd.Series(dtype=int)})
    cd.to_parquet(CACHE / f"feed_{fid}_cfgdrop.parquet")
    ts.to_parquet(path)
    sigf.write_text(sig)
    return ts


@functools.lru_cache(maxsize=64)
def _service_dates(fid: str) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    path, sigf = CACHE / f"feed_{fid}_svc.parquet", CACHE / f"feed_{fid}_svc.sig"
    sig = _feed_sig(fid)
    if path.exists() and sigf.exists() and sigf.read_text() == sig:
        return pd.read_parquet(path)
    sd = service_dates(Feed(fid))
    sd.to_parquet(path)
    sigf.write_text(sig)
    return sd


def _cfg_dropped_on(fid: str, day: pd.Timestamp) -> int:
    feed_table(fid)  # make sure the sidecar exists
    cd = pd.read_parquet(CACHE / f"feed_{fid}_cfgdrop.parquet")
    svc = set(_service_dates(fid).query("date == @day")["service_id"])
    return int(cd.loc[cd["service_id"].isin(svc), "n"].sum())


@functools.lru_cache(maxsize=16)
def _geoms(agg: str):
    a = load_agglomeration(agg)
    buf = a["buffered"]
    shapely.prepare(buf)
    return a["fua"], buf


def _in_buffer(agg: str, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return shapely.contains_xy(_geoms(agg)[1], np.nan_to_num(x, nan=-1e9), np.nan_to_num(y, nan=-1e9))


def _freq_expand(fid: str, t: pd.DataFrame) -> pd.DataFrame:
    """Replace each frequency-based trip by one row per run (trip_id ``<id>~<k>``, ``offset_s`` = shift)."""
    t = t.copy()
    t["offset_s"] = 0.0
    t["base_trip_id"] = t["trip_id"]
    if not Feed(fid).has("frequencies.txt"):
        return t
    fr = frequency_runs(Feed(fid))
    fr = fr[fr["trip_id"].isin(set(t["trip_id"]))]
    if fr.empty:
        return t
    fq = t[t["trip_id"].isin(set(fr["trip_id"]))]
    rest = t[~t["trip_id"].isin(set(fr["trip_id"]))]
    parts = [rest]
    for tid, g in fr.groupby("trip_id", sort=True):
        base = fq[fq["trip_id"] == tid].iloc[0]
        k = 0
        rows = []
        for row in g.sort_values("start_s").itertuples():
            for j in range(int(row.runs)):
                off = row.start_s + j * row.headway_s - base["first_dep_s"]
                r = base.copy()
                r["trip_id"] = f"{tid}~{k}"
                r["offset_s"] = float(off)
                r["first_dep_s"] = base["first_dep_s"] + off
                r["last_arr_s"] = base["last_arr_s"] + off
                r["runs"] = 1
                rows.append(r)
                k += 1
        if rows:
            parts.append(pd.DataFrame(rows))
    return pd.concat(parts, ignore_index=True)


def _active_in_feed(fid: str, day: pd.Timestamp) -> pd.DataFrame:
    ft = feed_table(fid)
    svc = set(_service_dates(fid).query("date == @day")["service_id"])
    return ft[ft["service_id"].isin(svc)].copy()


def _dup_key(t: pd.DataFrame) -> pd.Series:
    out = t["route_id"].astype(str)
    for c in ("direction_id", "block_id", "sig", "first_dep_s"):
        out = out + "|" + t[c].astype(object).where(t[c].notna(), "-").astype(str)
    return out


def _block_key(t: pd.DataFrame) -> pd.Series:
    """Same route, direction, block, start, end and stop count: one vehicle cannot run two such trips."""
    out = t["route_id"].astype(str)
    for c in ("direction_id", "block_id", "first_dep_s", "last_arr_s", "n_stops"):
        out = out + "|" + t[c].astype(object).where(t[c].notna(), "-").astype(str)
    return out


def _dedup_within(t: pd.DataFrame) -> pd.Series:
    """True for trips to drop (exact duplicates of a trip with a smaller trip_id on the same day)."""
    t = t.sort_values("trip_id", kind="stable")
    key = _dup_key(t)
    return key.duplicated(keep="first")


# ------------------------------------------------------------------ build per (agg, day, variant)
def _cross_feed(trips: pd.DataFrame, rs: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (drop mask index set as DataFrame of trips to drop, report)."""
    df = trips[trips["route_short_name"].notna()].copy()
    df["minute"] = (df["first_dep_s"] // 60).astype(int)
    df["key"] = df["route_short_name"].astype(str) + "|" + df["first_stop_key"].astype(str) + "|" + df["minute"].astype(str)
    feeds = sorted(df["feed"].unique(), key=_prio)
    kept: dict[str, str] = {}
    report, drop_idx = [], []
    for fid in feeds:
        g = df[df["feed"] == fid]
        if kept:
            m = g["key"].map(kept)
            g = g.assign(match_feed=m)
            for (rsn, ), gg in g.groupby(["route_short_name"], sort=True):
                nm = int(gg["match_feed"].notna().sum())
                if nm == 0:
                    continue
                share = nm / len(gg)
                top = gg["match_feed"].value_counts().idxmax()
                drop = share >= rs["cross_feed_min_share"] and nm >= rs["cross_feed_min_trips"]
                if nm >= 3 or share >= 0.3:
                    report.append({"feed_kept": top, "feed_other": fid, "route_short_name": rsn, "trips_other": len(gg),
                                   "trips_matching": nm, "share": round(share, 4), "dropped": bool(drop)})
                if drop:
                    drop_idx.extend(gg.index[gg["match_feed"].notna()])
        keep_now = g if not kept else g[~g.index.isin(drop_idx)]
        for k in keep_now["key"]:
            kept.setdefault(k, fid)
    rep = pd.DataFrame(report, columns=["feed_kept", "feed_other", "route_short_name", "trips_other",
                                        "trips_matching", "share", "dropped"])
    return trips.loc[sorted(set(drop_idx))], rep


def _build(agg: str, day: str, variant: str) -> dict:
    d = pd.Timestamp(day)
    rs = rules()
    parts, summary, ev_parts = [], [], {}
    for fid in feeds_for(agg, variant):
        act = _active_in_feed(fid, d)
        row = {"agglomeration": agg, "variant": variant, "day": day, "feed": fid}
        cfgdrop = _cfg_dropped_on(fid, d)
        # frequency expansion first so that counts are in trips, not in templates
        act = _freq_expand(fid, act)
        row["trips_raw"] = int(len(act)) + cfgdrop
        row["dropped_config_routes_agencies"] = cfgdrop
        n = len(act)
        act = act[~act["drop_agency_rule"]]
        row["dropped_agency_rule"] = n - len(act)
        # spatial rule for rail feeds
        stp = feed_stops(fid)
        stp = stp.assign(in_buffer=_in_buffer(agg, stp["x"].to_numpy(), stp["y"].to_numpy()))
        ev = stop_events(Feed(fid))
        base_ids = set(act["base_trip_id"])
        ev = ev[ev["trip_id"].isin(base_ids)].copy()
        ev["trip_id"] = ev["trip_id"].astype(object)
        ev["stop_id"] = ev["stop_id"].astype(object)
        ev = ev.merge(stp[["stop_id", "x", "y", "in_buffer"]], on="stop_id", how="left")
        ev["in_buffer"] = ev["in_buffer"].fillna(False).astype(bool)
        nb = ev.groupby("trip_id")["in_buffer"].agg(["sum", "size"])
        act["n_stops_in_buffer"] = act["base_trip_id"].map(nb["sum"]).fillna(0).astype(int)
        n = len(act)
        if _cfg_feeds()[fid].get("rail"):
            act = act[act["n_stops_in_buffer"] > 0]
        row["dropped_outside_buffer"] = n - len(act)
        n = len(act)
        dup = _dedup_within(act)
        act = act[~dup.reindex(act.index).to_numpy()] if len(act) else act
        row["dropped_exact_duplicates"] = n - len(act)
        n = len(act)
        if len(act):
            act = act.sort_values("trip_id", kind="stable")
            bk = _block_key(act)
            act = act[~(bk.duplicated(keep="first") & act["block_id"].notna())]
        row["dropped_block_duplicates"] = n - len(act)
        parts.append(act)
        ev_parts[fid] = ev
        summary.append(row)
    trips = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    dropped, rep = _cross_feed(trips, rs)
    trips = trips.drop(index=dropped.index)
    for row in summary:
        row["dropped_cross_feed"] = int((dropped["feed"] == row["feed"]).sum())
        row["trips_final"] = int((trips["feed"] == row["feed"]).sum())
    rep.insert(0, "agglomeration", agg)
    rep.insert(1, "variant", variant)
    rep.insert(2, "day", day)
    # ---- final tables
    trips["uid"] = trips["feed"] + ":" + trips["trip_id"]
    rsn = trips["route_short_name"].fillna(trips["route_long_name"]).fillna(trips["route_id"])
    trips["route_short_name"] = rsn
    out = trips[["feed", "trip_id", "uid", "route_id", "route_short_name", "agency_id", "route_class", "direction_id",
                 "shape_id", "first_dep_s", "last_arr_s", "dist_m", "dist_method", "is_replacement_bus",
                 "route_type", "n_stops", "n_stops_in_buffer", "dist_stops_m", "block_id", "service_id"]]
    out = out.sort_values(["feed", "uid"], kind="stable").reset_index(drop=True)
    st_parts = []
    for fid, ev in ev_parts.items():
        t = trips[trips["feed"] == fid]
        if t.empty:
            continue
        # expand to the kept (possibly frequency-expanded) trips
        m = t[["trip_id", "base_trip_id", "uid", "offset_s", "route_class", "route_short_name", "direction_id"]].rename(
            columns={"trip_id": "new_trip_id"})
        e = ev.rename(columns={"trip_id": "base_trip_id"}).merge(m, on="base_trip_id", how="inner")
        e["arr_s"] = e["arr_s"] + e["offset_s"]
        e["dep_s"] = e["dep_s"] + e["offset_s"]
        e["feed"] = fid
        st_parts.append(e[["feed", "uid", "stop_id", "stop_sequence", "arr_s", "dep_s", "route_class",
                           "route_short_name", "direction_id", "x", "y", "in_buffer"]])
    stt = pd.concat(st_parts, ignore_index=True) if st_parts else pd.DataFrame()
    stt["suid"] = stt["feed"] + ":" + stt["stop_id"].astype(str)
    stt["arr_s"] = stt["arr_s"].astype("float32")
    stt["dep_s"] = stt["dep_s"].astype("float32")
    stt["x"] = stt["x"].astype("float32")
    stt["y"] = stt["y"].astype("float32")
    stt["stop_sequence"] = stt["stop_sequence"].astype("int32")
    stt = stt.sort_values(["feed", "uid", "stop_sequence"], kind="stable").reset_index(drop=True)
    return {"trips": out, "stop_times": stt, "summary": pd.DataFrame(summary), "crossdup": rep}


def _get(agg: str, day: str, variant: str, refresh: bool = False) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    base = CACHE / f"{agg}_{day}_{variant}"
    sigf = Path(str(base) + ".sig")
    sig = _build_sig(agg, variant)
    names = {"trips": ".trips.parquet", "stop_times": ".stop_times.parquet", "summary": ".summary.parquet",
             "crossdup": ".crossdup.parquet"}
    if not refresh and sigf.exists() and sigf.read_text() == sig and all(Path(str(base) + s).exists() for s in names.values()):
        return {k: pd.read_parquet(str(base) + s) for k, s in names.items()}
    res = _build(agg, day, variant)
    for k, s in names.items():
        res[k].to_parquet(str(base) + s)
    sigf.write_text(sig)
    return res


# ------------------------------------------------------------------ public API
def active_trips(agg_id: str, day: str, variant: str = "all") -> pd.DataFrame:
    """One row per trip running on ``day`` (YYYY-MM-DD) after the rules in the module docstring."""
    return _get(agg_id, day, variant)["trips"].copy()


def stop_times(agg_id: str, day: str, variant: str = "all") -> pd.DataFrame:
    """Stop-time rows of the active trips (seconds after midnight, may exceed 86400).

    Extra columns beyond the contract: ``suid``, ``x``, ``y`` (EPSG:2180, NaN without coordinates),
    ``in_buffer`` (stop inside FUA + 15 km)."""
    return _get(agg_id, day, variant)["stop_times"].copy()


def service_summary(agg_id: str, day: str, variant: str = "all") -> pd.DataFrame:
    return _get(agg_id, day, variant)["summary"].copy()


def cross_feed_report(agg_id: str, day: str, variant: str = "all") -> pd.DataFrame:
    return _get(agg_id, day, variant)["crossdup"].copy()


def stops(agg_id: str, variant: str = "all") -> gpd.GeoDataFrame:
    """Every stop of the selected feeds inside FUA + 15 km buffer, EPSG:2180."""
    rows = []
    for fid in feeds_for(agg_id, variant):
        s = feed_stops(fid)
        s = s[_in_buffer(agg_id, s["x"].to_numpy(), s["y"].to_numpy())].copy()
        s["feed"] = fid
        rows.append(s)
    s = pd.concat(rows, ignore_index=True)
    s["suid"] = s["feed"] + ":" + s["stop_id"].astype(str)
    s = s[["feed", "stop_id", "suid", "stop_name", "parent_station", "location_type", "x", "y"]]
    s = s.sort_values(["feed", "stop_id"], kind="stable").reset_index(drop=True)
    return gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s["x"], s["y"]), crs=CRS_METRIC)


def daily_series(agg_id: str, fid: str) -> pd.DataFrame:
    """Per date in the feed's calendar: trips and whole-trip vehicle-km after rules 1-4 (feed level).

    Used by the anomaly test.  Rule 5 (cross-feed) is not applied here (it is day dependent and tiny);
    rail feeds are clipped to trips touching the agglomeration's buffer."""
    ft = feed_table(fid)
    ft = ft[~ft["drop_agency_rule"]]
    if _cfg_feeds()[fid].get("rail"):
        ev = stop_events(Feed(fid))
        stp = feed_stops(fid)
        ok = set(stp.loc[_in_buffer(agg_id, stp["x"].to_numpy(), stp["y"].to_numpy()), "stop_id"])
        hit = ev[ev["stop_id"].astype(object).isin(ok)]["trip_id"].astype(object).unique()
        ft = ft[ft["trip_id"].isin(set(hit))]
    ft = ft.assign(key=_dup_key(ft))
    sd = _service_dates(fid)
    j = sd.merge(ft[["service_id", "trip_id", "key", "dist_m", "runs"]], on="service_id", how="inner")
    j = j.sort_values(["date", "key", "trip_id"], kind="stable").drop_duplicates(["date", "key"], keep="first")
    j["km"] = j["dist_m"] * j["runs"] / 1000
    out = j.groupby("date").agg(trips=("runs", "sum"), vehicle_km=("km", "sum")).reset_index()
    out["feed"] = fid
    return out


# ------------------------------------------------------------------ entry point
def main() -> None:
    t0 = time.time()
    cfg = load_config()
    days = [cfg["reference_day"], cfg["reference_saturday"]]
    QA.mkdir(parents=True, exist_ok=True)
    srows, crows = [], []
    for agg in PHASE1:
        for variant in VARIANTS:
            for day in days:
                res = _get(agg, day, variant)
                s = res["summary"].copy()
                tot = {c: int(s[c].sum()) for c in s.columns if c.startswith(("trips", "dropped"))}
                tot.update({"agglomeration": agg, "variant": variant, "day": day, "feed": "RAZEM"})
                srows.append(s)
                srows.append(pd.DataFrame([tot]))
                crows.append(res["crossdup"])
                print(f"{agg:11s} {variant:8s} {day}  trips {tot['trips_raw']:>6d} -> {tot['trips_final']:>6d}", flush=True)
    summ = pd.concat(srows, ignore_index=True)
    cols = ["agglomeration", "variant", "day", "feed", "trips_raw", "dropped_config_routes_agencies",
            "dropped_agency_rule", "dropped_outside_buffer", "dropped_exact_duplicates", "dropped_block_duplicates", "dropped_cross_feed", "trips_final"]
    summ = summ[cols]
    summ["_t"] = (summ["feed"] == "RAZEM").astype(int)
    summ = summ.sort_values(["agglomeration", "variant", "day", "_t", "feed"], kind="stable").drop(columns="_t")
    summ.to_csv(QA / "service_summary.csv", index=False, lineterminator="\n")
    cr = pd.concat(crows, ignore_index=True).sort_values(
        ["agglomeration", "variant", "day", "feed_other", "route_short_name"], kind="stable")
    cr.to_csv(QA / "cross_feed_duplicates.csv", index=False, lineterminator="\n")
    inputs = sorted({f"gtfs_{f}" for a in PHASE1 for f in feeds_for(a, "all")})
    write_meta(QA, "gtfs_service", inputs=inputs, started=t0, extra={"rules_version": RULES_VERSION, "rules": rules()})


if __name__ == "__main__":
    main()
