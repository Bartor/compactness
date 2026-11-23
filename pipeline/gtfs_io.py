"""Reusable GTFS loading and calendar helpers (plain pandas, reading straight from the zip).

Everything here treats the zip as untrusted data: it is only parsed as CSV.

Main entry points
-----------------
``Feed(feed_id)``            lazy table access (``feed.table("trips.txt")``)
``service_dates(feed)``      long table service_id x date from calendar + calendar_dates
``trip_stats(feed)``         per-trip table (times, distances, runs); cached in data/interim/gtfs
``stop_events(feed)``        per stop-time table with integer seconds; cached
``route_class(route_type)``  basic or extended route_type -> tram/metro/rail/bus/trolleybus/ferry/other
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.common import CRS_METRIC, INTERIM, RAW

INTERIM_GTFS = INTERIM / "gtfs"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def latest_zip(feed_id: str) -> Path:
    zips = sorted((RAW / "gtfs" / feed_id).glob("*/*.zip"))
    if not zips:
        raise FileNotFoundError(f"no raw GTFS for {feed_id}")
    return zips[-1]


def route_class(route_type: int | float | str) -> str:
    """Map basic and extended (HVT) route_type values to a small set of classes."""
    try:
        t = int(route_type)
    except (TypeError, ValueError):
        return "other"
    if t in (1,) or 500 <= t < 700 or t in (401, 402):
        return "metro"
    if t in (0, 5) or 900 <= t < 1000:
        return "tram"
    if t == 2 or 100 <= t < 200 or 400 <= t < 500:
        return "rail"
    if t == 3 or 200 <= t < 400 or 700 <= t < 800:
        return "bus"
    if t == 11 or 800 <= t < 900:
        return "trolleybus"
    if t == 4 or 1000 <= t < 1100 or t == 1200:
        return "ferry"
    return "other"


def parse_time(s: pd.Series) -> pd.Series:
    """'H:MM:SS' / 'HH:MM:SS' (hours may exceed 24) -> float seconds (NaN when empty)."""
    s = s.fillna("").str.strip()
    ok = s.str.len() >= 7
    h = pd.to_numeric(s.str.slice(0, -6), errors="coerce")
    m = pd.to_numeric(s.str.slice(-5, -3), errors="coerce")
    sec = pd.to_numeric(s.str.slice(-2), errors="coerce")
    out = h * 3600 + m * 60 + sec
    return out.where(ok)


class Feed:
    """A downloaded GTFS zip with cached table access."""

    def __init__(self, feed_id: str, path: Path | None = None):
        self.id = feed_id
        self.path = Path(path) if path else latest_zip(feed_id)
        self._zf = zipfile.ZipFile(self.path)
        self._names = set(self._zf.namelist())
        self.interim = INTERIM_GTFS / feed_id
        self.interim.mkdir(parents=True, exist_ok=True)

    def has(self, name: str) -> bool:
        return name in self._names

    def size(self, name: str) -> int:
        return self._zf.getinfo(name).file_size if name in self._names else 0

    def table(self, name: str, usecols: list[str] | None = None) -> pd.DataFrame | None:
        """Read one GTFS file as strings; ``None`` when absent. Missing ``usecols`` are skipped."""
        if name not in self._names:
            return None
        with self._zf.open(name) as f:
            head = f.readline().decode("utf-8-sig", errors="replace")
        cols = [c.strip() for c in head.rstrip("\r\n").split(",")]
        want = None
        if usecols is not None:
            want = [c for c in cols if c in usecols]
            if not want:
                return pd.DataFrame(columns=usecols)
        with self._zf.open(name) as f:
            df = pd.read_csv(f, dtype=str, encoding="utf-8-sig", usecols=want, keep_default_na=False,
                             na_values=[""], low_memory=False, skipinitialspace=True,
                             encoding_errors="replace", on_bad_lines="skip")
        df.columns = [c.strip() for c in df.columns]
        return df


# ------------------------------------------------------------------ per-feed filters (config.yaml: drop_routes / drop_agencies)
def drop_spec(feed: Feed) -> tuple[set[str], set[str]]:
    """route_ids / agency_ids that ``config.yaml`` feeds.<id> excludes (duplicates of services in another feed)."""
    from pipeline.common import load_config
    c = (load_config().get("feeds") or {}).get(feed.id, {}) or {}
    return set(map(str, c.get("drop_routes") or [])), set(map(str, c.get("drop_agencies") or []))


def dropped_route_ids(feed: Feed) -> set[str]:
    dr, da = drop_spec(feed)
    if not dr and not da:
        return set()
    rt = feed.table("routes.txt", ["route_id", "agency_id"])
    bad = set(dr)
    if da and "agency_id" in rt:
        bad |= set(rt.loc[rt["agency_id"].isin(da), "route_id"])
    return bad


def _cache_ok(feed: Feed, cache: Path, refresh: bool) -> bool:
    """Cache is valid when newer than the zip and built with the same drop filters."""
    sig = feed.interim / "drop_sig.txt"
    cur = repr((sorted(drop_spec(feed)[0]), sorted(drop_spec(feed)[1])))
    prev = sig.read_text(encoding="utf-8") if sig.exists() else repr(([], []))
    if prev != cur:
        for n in ("stop_events.parquet", "trip_stats.parquet"):
            (feed.interim / n).unlink(missing_ok=True)
        sig.write_text(cur, encoding="utf-8")
        return False
    return cache.exists() and not refresh and cache.stat().st_mtime >= feed.path.stat().st_mtime


# ------------------------------------------------------------------ calendar
def service_dates(feed: Feed) -> pd.DataFrame:
    """Long table (service_id, date) of every date each service runs.

    calendar.txt weekly patterns are expanded over [start_date, end_date];
    calendar_dates.txt then adds (type 1) or removes (type 2) single dates.
    """
    cal = feed.table("calendar.txt")
    cd = feed.table("calendar_dates.txt")
    parts = []
    if cal is not None and len(cal):
        for r in cal.itertuples(index=False):
            try:
                rng = pd.date_range(pd.to_datetime(r.start_date, format="%Y%m%d"),
                                    pd.to_datetime(r.end_date, format="%Y%m%d"))
            except Exception:  # noqa: BLE001 - skip malformed rows
                continue
            flags = np.array([getattr(r, d) == "1" for d in WEEKDAYS])
            sel = rng[flags[rng.weekday]]
            if len(sel):
                parts.append(pd.DataFrame({"service_id": r.service_id, "date": sel}))
    base = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        {"service_id": pd.Series(dtype=str), "date": pd.Series(dtype="datetime64[ns]")})
    if cd is not None and len(cd):
        cd = cd.copy()
        cd["date"] = pd.to_datetime(cd["date"], format="%Y%m%d", errors="coerce")
        cd = cd.dropna(subset=["date"])
        rem = cd[cd["exception_type"] == "2"][["service_id", "date"]].assign(_r=1)
        add = cd[cd["exception_type"] == "1"][["service_id", "date"]]
        if len(rem):
            base = base.merge(rem, on=["service_id", "date"], how="left")
            base = base[base["_r"].isna()].drop(columns="_r")
        base = pd.concat([base, add], ignore_index=True)
    return base.drop_duplicates().sort_values(["service_id", "date"]).reset_index(drop=True)


# ------------------------------------------------------------------ geometry
def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371008.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def shape_lengths(feed: Feed) -> pd.Series:
    """Length in metres (EPSG:2180) of every shape_id; empty Series when no shapes.txt."""
    from pyproj import Transformer
    sh = feed.table("shapes.txt", ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
    if sh is None or sh.empty:
        return pd.Series(dtype=float, name="shape_len_m")
    sh["lat"] = pd.to_numeric(sh["shape_pt_lat"], errors="coerce")
    sh["lon"] = pd.to_numeric(sh["shape_pt_lon"], errors="coerce")
    sh["seq"] = pd.to_numeric(sh["shape_pt_sequence"], errors="coerce")
    sh = sh.dropna(subset=["lat", "lon", "seq"]).sort_values(["shape_id", "seq"], kind="stable")
    tr = Transformer.from_crs("EPSG:4326", CRS_METRIC, always_xy=True)
    x, y = tr.transform(sh["lon"].to_numpy(), sh["lat"].to_numpy())
    same = (sh["shape_id"].to_numpy()[1:] == sh["shape_id"].to_numpy()[:-1])
    seg = np.hypot(np.diff(x), np.diff(y)) * same
    seg = np.concatenate([[0.0], seg])
    out = pd.Series(seg, index=sh["shape_id"].to_numpy()).groupby(level=0).sum()
    out.name = "shape_len_m"
    return out


# ------------------------------------------------------------------ stop times
def stop_events(feed: Feed, refresh: bool = False) -> pd.DataFrame:
    """stop_times with integer seconds (NaN -> -1 is avoided: columns are float32), cached as parquet."""
    cache = feed.interim / "stop_events.parquet"
    if _cache_ok(feed, cache, refresh):
        return pd.read_parquet(cache)
    st = feed.table("stop_times.txt", ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"])
    bad = dropped_route_ids(feed)
    if bad:
        tr0 = feed.table("trips.txt", ["trip_id", "route_id"])
        st = st[~st["trip_id"].isin(tr0.loc[tr0["route_id"].isin(bad), "trip_id"])]
    st["stop_sequence"] = pd.to_numeric(st["stop_sequence"], errors="coerce").astype("int32")
    st["arr_s"] = parse_time(st["arrival_time"]).astype("float32")
    st["dep_s"] = parse_time(st["departure_time"]).astype("float32")
    # a missing departure falls back to the arrival and vice versa
    a, d = st["arr_s"], st["dep_s"]
    st["arr_s"] = a.fillna(d)
    st["dep_s"] = d.fillna(a)
    st = st.drop(columns=["arrival_time", "departure_time"])
    st = st.sort_values(["trip_id", "stop_sequence"], kind="stable").reset_index(drop=True)
    st["trip_id"] = st["trip_id"].astype("category")
    st["stop_id"] = st["stop_id"].astype("category")
    st.to_parquet(cache)
    return st


def frequency_runs(feed: Feed) -> pd.DataFrame:
    """Per frequencies.txt row: trip_id, start_s, end_s, headway_s, runs (ceil((end-start)/headway))."""
    fr = feed.table("frequencies.txt")
    if fr is None or fr.empty:
        return pd.DataFrame(columns=["trip_id", "start_s", "end_s", "headway_s", "runs"])
    fr = fr.copy()
    fr["start_s"] = parse_time(fr["start_time"])
    fr["end_s"] = parse_time(fr["end_time"])
    fr["headway_s"] = pd.to_numeric(fr["headway_secs"], errors="coerce")
    fr = fr.dropna(subset=["start_s", "end_s", "headway_s"])
    fr = fr[fr["headway_s"] > 0]
    fr["runs"] = np.ceil((fr["end_s"] - fr["start_s"]) / fr["headway_s"]).clip(lower=0).astype(int)
    return fr[["trip_id", "start_s", "end_s", "headway_s", "runs"]]


def trip_stats(feed: Feed, refresh: bool = False) -> pd.DataFrame:
    """One row per trip: service_id, route_id, direction_id, shape_id, times, distances, runs.

    ``dist_m`` is the shape length (EPSG:2180) when the trip has a usable shape, otherwise the summed
    great-circle distance between consecutive stops; ``dist_method`` says which.  ``runs`` is 1, or the
    number of departures implied by frequencies.txt.
    """
    cache = feed.interim / "trip_stats.parquet"
    if _cache_ok(feed, cache, refresh):
        return pd.read_parquet(cache)
    trips = feed.table("trips.txt", ["trip_id", "route_id", "service_id", "direction_id", "shape_id", "block_id"])
    bad = dropped_route_ids(feed)
    if bad:
        trips = trips[~trips["route_id"].isin(bad)]
    for c in ("direction_id", "shape_id", "block_id"):   # optional GTFS columns; many small feeds omit them
        if c not in trips:
            trips[c] = None
    ev = stop_events(feed)
    stops = feed.table("stops.txt", ["stop_id", "stop_lat", "stop_lon"])
    stops["lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    sidx = pd.Index(stops["stop_id"])
    pos = sidx.get_indexer(ev["stop_id"].astype(object))
    lat = np.where(pos >= 0, stops["lat"].to_numpy()[pos], np.nan)
    lon = np.where(pos >= 0, stops["lon"].to_numpy()[pos], np.nan)
    tid = ev["trip_id"].cat.codes.to_numpy()
    same = tid[1:] == tid[:-1]
    seg = _haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    seg = np.where(same & np.isfinite(seg), seg, 0.0)
    ev = ev.assign(_seg=np.concatenate([[0.0], seg]))
    g = ev.groupby("trip_id", observed=True)
    ts = pd.DataFrame({
        "n_stops": g.size(),
        "first_dep_s": g["dep_s"].min(),
        "last_arr_s": g["arr_s"].max(),
        "dist_stops_m": g["_seg"].sum(),
        "first_stop_id": g["stop_id"].first().astype(object),
        "last_stop_id": g["stop_id"].last().astype(object),
    })
    ts.index = ts.index.astype(object)
    ts = ts.rename_axis("trip_id").reset_index()
    out = trips.merge(ts, on="trip_id", how="inner")
    sl = shape_lengths(feed)
    out["shape_len_m"] = out["shape_id"].map(sl) if len(sl) and "shape_id" in out else np.nan
    use_shape = out["shape_len_m"].notna() & (out["shape_len_m"] > 0)
    out["dist_m"] = np.where(use_shape, out["shape_len_m"], out["dist_stops_m"])
    out["dist_method"] = np.where(use_shape, "shape", "stops")
    out["duration_s"] = (out["last_arr_s"] - out["first_dep_s"]).clip(lower=0)
    # exact duplicates inside one service: same route/direction/first+last stop/times/stop count under the same service_id
    sig = ["service_id", "route_id", "direction_id", "first_stop_id", "first_dep_s", "last_stop_id", "last_arr_s", "n_stops"]
    out["is_dup"] = out.fillna({"direction_id": "-"}).duplicated(subset=sig, keep="first")
    fr = frequency_runs(feed)
    if len(fr):
        runs = fr.groupby("trip_id")["runs"].sum()
        out["runs"] = out["trip_id"].map(runs).fillna(1).astype(int)
    else:
        out["runs"] = 1
    routes = feed.table("routes.txt", ["route_id", "route_type", "agency_id"])
    if routes is not None:
        routes["route_class"] = routes["route_type"].map(route_class)
        out = out.merge(routes[["route_id", "route_type", "route_class", "agency_id"]].drop_duplicates("route_id"),
                        on="route_id", how="left")   # some feeds repeat route rows (e.g. Tczew)
    for c in ("shape_id", "block_id", "direction_id"):
        if c not in out:
            out[c] = None
    out.to_parquet(cache)
    return out
