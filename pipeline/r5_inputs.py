"""Inputs for Conveyal R5 (phase 3, accessibility): clipped OSM extracts and cleaned GTFS zips.

    python -m pipeline.r5_inputs --aggs wroclaw warszawa            # OSM + GTFS for both feed variants
    python -m pipeline.r5_inputs --aggs krakow --skip-osm           # GTFS only

Outputs (never committed; data/interim is ignored by git)
* ``data/interim/r5/<agg>/osm.pbf``                   street network for R5
* ``data/interim/r5/<agg>/gtfs_<variant>/<feed>.zip``  one cleaned zip per source feed
* ``data/interim/r5/<agg>/inputs.json``               sizes, timings, signatures, validation counts

OSM extract (pyosmium; the ``osmium`` CLI is not available on this machine)
* Region = FUA + ``edge_buffer_km`` (config, 15 km) + ``OSM_MARGIN_M`` (3 km), so that walk/bike paths
  leaving the destination domain near its edge still exist.
* One pass over the national PBF with node locations: a way is kept when it carries ``highway`` (any
  value; R5 decides routability itself) or is a platform (``railway=platform`` /
  ``public_transport=platform``) and at least one of its nodes lies inside the region.  Ways are kept
  complete: every referenced node is written (``osmium.BackReferenceWriter``), so ways crossing the
  region edge are not cut.  Node tags are kept (barriers, crossings).  Relations are not written: R5 uses
  them only for turn restrictions (car routing, not used here) and does not need them for walk/bike.

Cleaned GTFS (one zip per source feed and variant, feed_id = feed name, so ids never collide across feeds)
* Trips: exactly those kept by ``pipeline.gtfs_service.active_trips`` on the reference Wednesday and the
  reference Saturday (config ``reference_day`` / ``reference_saturday``), i.e. after config drops, the SKM
  Warszawa agency rule, the rail clip to FUA + 15 km, within-feed exact and block duplicates and the
  cross-feed rule.  ``frequencies.txt`` runs are materialised as ordinary scheduled trips (trip_id
  ``<id>~<k>``) exactly as the service layer counts them; this also keeps R5 deterministic (R5 would
  otherwise draw random schedules for frequency trips).
* Calendar: three synthetic services in ``calendar_dates.txt`` only: ``WED`` (reference Wednesday), ``SAT``
  (reference Saturday) and ``WED_SAT`` (trips kept on both days).  A trip therefore runs on a reference
  day in R5 exactly when the service layer keeps it on that day.  Other dates have no service.
* Stops: only stops used by the kept trips; stops without coordinates (lodz 3876 / 3877 at 0,0) are
  dropped together with their stop_times rows; a trip left with fewer than two timed stops is dropped
  and counted.  ``parent_station`` and ``location_type`` are not written (R5 routes on stops; parents
  would need their own rows).  ``shapes.txt`` and ``block_id`` are not written (R5 does not need them for
  travel times; GZM blocks overlap, see RAPORT 2.2).
* Validation: trips per feed active on each reference day in the zip == ``active_trips`` counts (minus
  trips dropped for missing coordinates, reported separately).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from shapely.geometry import mapping

from pipeline import gtfs_service as gs
from pipeline.boundaries import load_agglomeration
from pipeline.common import INTERIM, RAW, load_config, write_json
from pipeline.gtfs_io import Feed

PBF = RAW / "osm" / "poland-latest.osm.pbf"
R5_DIR = INTERIM / "r5"
OSM_MARGIN_M = 3000
PHASE1 = gs.PHASE1
INPUTS_VERSION = "2026-11-25.1"
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def agg_dir(agg: str) -> Path:
    return R5_DIR / agg


def osm_path(agg: str) -> Path:
    return agg_dir(agg) / "osm.pbf"


def gtfs_dir(agg: str, variant: str) -> Path:
    return agg_dir(agg) / f"gtfs_{variant}"


def gtfs_paths(agg: str, variant: str) -> list[Path]:
    return sorted(gtfs_dir(agg, variant).glob("*.zip"))


def ref_days() -> dict[str, str]:
    cfg = load_config()
    return {"WED": cfg["reference_day"], "SAT": cfg["reference_saturday"]}


# ------------------------------------------------------------------ OSM
def osm_region_ll(agg: str):
    """FUA + edge buffer + margin, in lon/lat, slightly simplified (prepared)."""
    reg = load_agglomeration(agg)["buffered"].buffer(OSM_MARGIN_M).simplify(100)
    reg_ll = shapely.transform(reg, lambda xy: np.column_stack(TO4326.transform(xy[:, 0], xy[:, 1])))
    shapely.prepare(reg_ll)
    return reg_ll


def _is_kept_way(tags) -> bool:
    if "highway" in tags:
        return True
    return tags.get("railway") == "platform" or tags.get("public_transport") == "platform"


def extract_osm(aggs: list[str], force: bool = False) -> dict:
    """One pass over the national PBF for all ``aggs``; complete ways + referenced nodes per agglomeration."""
    import osmium
    todo = [a for a in aggs if force or not osm_path(a).exists()]
    stats = {}
    if not todo:
        return stats
    regions = {a: osm_region_ll(a) for a in todo}
    boxes = {a: r.bounds for a, r in regions.items()}
    writers = {}
    for a in todo:
        agg_dir(a).mkdir(parents=True, exist_ok=True)
        tmp = osm_path(a).with_suffix(".tmp.pbf")
        tmp.unlink(missing_ok=True)
        writers[a] = osmium.BackReferenceWriter(str(tmp), ref_src=str(PBF), overwrite=True, remove_tags=False)
    counts = {a: 0 for a in todo}
    t0 = time.time()
    fp = (osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY)
          .with_locations("flex_mem")
          .with_filter(osmium.filter.KeyFilter("highway", "railway", "public_transport")))
    for o in fp:
        if not o.is_way() or not _is_kept_way(o.tags):
            continue
        lon = []
        lat = []
        for n in o.nodes:
            loc = n.location
            if loc.valid():
                lon.append(loc.lon)
                lat.append(loc.lat)
        if not lon:
            continue
        x0, x1, y0, y1 = min(lon), max(lon), min(lat), max(lat)
        for a, (bx0, by0, bx1, by1) in boxes.items():
            if x1 < bx0 or x0 > bx1 or y1 < by0 or y0 > by1:
                continue
            if shapely.contains_xy(regions[a], lon, lat).any():
                writers[a].add(o)
                counts[a] += 1
    t_scan = time.time() - t0
    for a in todo:
        t1 = time.time()
        writers[a].close()           # completes referenced nodes from ref_src
        tmp = osm_path(a).with_suffix(".tmp.pbf")
        tmp.replace(osm_path(a))
        stats[a] = {"ways": counts[a], "bytes": osm_path(a).stat().st_size, "scan_s": round(t_scan, 1),
                    "complete_s": round(time.time() - t1, 1), "margin_m": OSM_MARGIN_M,
                    "source": PBF.name, "source_bytes": PBF.stat().st_size}
        print(f"osm {a}: {counts[a]} ways, {stats[a]['bytes'] / 1e6:.1f} MB, scan {t_scan:.0f}s, "
              f"complete {stats[a]['complete_s']:.0f}s", flush=True)
    return stats


# ------------------------------------------------------------------ GTFS
def _hms(s: pd.Series) -> pd.Series:
    v = s.round().astype("int64")
    h, m, sec = v // 3600, (v // 60) % 60, v % 60
    return h.astype(str).str.zfill(2) + ":" + m.astype(str).str.zfill(2) + ":" + sec.astype(str).str.zfill(2)


def _csv(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False, lineterminator="\n")
    return buf.getvalue().encode("utf-8")


def _kept(agg: str, variant: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trips kept on either reference day (with the WED / SAT / WED_SAT service) and their stop_times."""
    days = ref_days()
    trips, sts = [], []
    for code, day in days.items():
        t = gs.active_trips(agg, day, variant)
        t["day"] = code
        trips.append(t)
        st = gs.stop_times(agg, day, variant)[["feed", "uid", "stop_id", "stop_sequence", "arr_s", "dep_s", "x", "y"]]
        sts.append(st)
    t = pd.concat(trips, ignore_index=True)
    svc = t.groupby("uid")["day"].agg(lambda d: "_".join(sorted(set(d), key=["WED", "SAT"].index)))
    t = t.sort_values(["feed", "uid", "day"], kind="stable").drop_duplicates("uid", keep="first")
    t["service_id"] = t["uid"].map(svc)
    st = pd.concat(sts, ignore_index=True).drop_duplicates(["uid", "stop_sequence"], keep="first")
    return t.reset_index(drop=True), st.reset_index(drop=True)


def build_gtfs(agg: str, variant: str) -> dict:
    """Write one cleaned zip per source feed for (agg, variant); return per-feed counts."""
    t0 = time.time()
    out_dir = gtfs_dir(agg, variant)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.zip"):
        old.unlink()
    days = ref_days()
    trips, st = _kept(agg, variant)
    report = {}
    for fid in sorted(trips["feed"].unique()):
        t = trips[trips["feed"] == fid].copy()
        s = st[st["feed"] == fid].copy()
        n_rows0 = len(s)
        s = s[np.isfinite(s["x"]) & np.isfinite(s["y"])]
        dropped_rows = n_rows0 - len(s)
        nstop = s.groupby("uid").size()
        ok_uids = set(nstop[nstop >= 2].index)
        dropped_trips = t[~t["uid"].isin(ok_uids)]
        t = t[t["uid"].isin(ok_uids)]
        s = s[s["uid"].isin(ok_uids)].sort_values(["uid", "stop_sequence"], kind="stable")
        f = Feed(fid)
        # stops
        fs = gs.feed_stops(fid)
        used = set(s["stop_id"].astype(str))
        fs = fs[fs["stop_id"].astype(str).isin(used) & fs["lat"].notna()].copy()
        stops = pd.DataFrame({"stop_id": fs["stop_id"].astype(str), "stop_name": fs["stop_name"].fillna(""),
                              "stop_lat": fs["lat"].map(lambda v: f"{v:.7f}"),
                              "stop_lon": fs["lon"].map(lambda v: f"{v:.7f}")}).sort_values("stop_id")
        # routes and agencies
        r = f.table("routes.txt").drop_duplicates("route_id")
        r = r[r["route_id"].isin(set(t["route_id"].astype(str)))]
        rcols = [c for c in ("route_id", "agency_id", "route_short_name", "route_long_name", "route_type") if c in r]
        r = r[rcols].copy()
        for col in ("route_short_name", "route_long_name"):
            r[col] = r[col].fillna("") if col in r else ""
        if (r["route_short_name"] == "").all() and (r["route_long_name"].fillna("") == "").all():
            r["route_short_name"] = r["route_id"]
        ag = f.table("agency.txt")
        acols = [c for c in ("agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang") if c in ag]
        ag = ag[acols].copy()
        if "agency_id" in r and "agency_id" in ag:
            ag = ag[ag["agency_id"].isin(set(r["agency_id"].dropna()))] if r["agency_id"].notna().any() else ag
        for col, default in (("agency_timezone", "Europe/Warsaw"), ("agency_url", "https://example.invalid"),
                             ("agency_name", fid)):
            ag[col] = ag[col].fillna(default) if col in ag else default
        if len(ag) > 1 and ("agency_id" not in r or r["agency_id"].isna().any()):
            raise ValueError(f"{fid}: several agencies but routes without agency_id")
        # trips
        tr = pd.DataFrame({"route_id": t["route_id"].astype(str), "service_id": t["service_id"],
                           "trip_id": t["uid"].str.slice(len(fid) + 1),
                           "direction_id": t["direction_id"].astype(object).where(t["direction_id"].notna(), "")})
        tr = tr.sort_values("trip_id", kind="stable")
        stt = pd.DataFrame({"trip_id": s["uid"].str.slice(len(fid) + 1), "arrival_time": _hms(s["arr_s"]),
                            "departure_time": _hms(s["dep_s"]), "stop_id": s["stop_id"].astype(str),
                            "stop_sequence": s["stop_sequence"].astype(int)})
        cd = []
        for sid in sorted(t["service_id"].unique()):
            for code in sid.split("_"):
                cd.append({"service_id": sid, "date": days[code].replace("-", ""), "exception_type": 1})
        cd = pd.DataFrame(cd)
        fi = pd.DataFrame([{"feed_publisher_name": "compactness pipeline (cleaned from " + fid + ")",
                            "feed_publisher_url": "https://example.invalid", "feed_lang": "pl", "feed_id": fid,
                            "feed_start_date": min(days.values()).replace("-", ""),
                            "feed_end_date": max(days.values()).replace("-", ""),
                            "feed_version": INPUTS_VERSION}])
        path = out_dir / f"{fid}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, df in (("agency.txt", ag), ("routes.txt", r), ("trips.txt", tr), ("stops.txt", stops),
                             ("stop_times.txt", stt), ("calendar_dates.txt", cd), ("feed_info.txt", fi)):
                zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(zi, _csv(df))
        report[fid] = {"trips": int(len(tr)), "stop_times": int(len(stt)), "stops": int(len(stops)),
                       "routes": int(len(r)), "bytes": path.stat().st_size,
                       "dropped_stop_time_rows_no_coords": int(dropped_rows),
                       "dropped_trips_lt2_stops": int(len(dropped_trips)),
                       "dropped_trips_by_day": {c: int((dropped_trips["service_id"].str.contains(c)).sum())
                                                for c in days}}
    report["_build_s"] = round(time.time() - t0, 1)
    return report


def validate_gtfs(agg: str, variant: str, report: dict) -> pd.DataFrame:
    """Trips per feed per reference day: zip vs ``gtfs_service.active_trips``."""
    rows = []
    for code, day in ref_days().items():
        ref = gs.active_trips(agg, day, variant).groupby("feed").size()
        ymd = day.replace("-", "")
        for path in gtfs_paths(agg, variant):
            fid = path.stem
            with zipfile.ZipFile(path) as z:
                tr = pd.read_csv(z.open("trips.txt"), dtype=str)
                cd = pd.read_csv(z.open("calendar_dates.txt"), dtype=str)
            svc = set(cd.loc[(cd["date"] == ymd) & (cd["exception_type"] == "1"), "service_id"])
            n_zip = int(tr["service_id"].isin(svc).sum())
            n_ref = int(ref.get(fid, 0))
            dropped = int(report.get(fid, {}).get("dropped_trips_by_day", {}).get(code, 0))
            rows.append({"agglomeration": agg, "variant": variant, "day": day, "feed": fid, "trips_service_layer": n_ref,
                         "trips_zip": n_zip, "dropped_no_coords": dropped, "match": n_zip + dropped == n_ref})
        missing = set(ref.index) - {p.stem for p in gtfs_paths(agg, variant)}
        for fid in sorted(missing):
            rows.append({"agglomeration": agg, "variant": variant, "day": day, "feed": fid,
                         "trips_service_layer": int(ref[fid]), "trips_zip": 0, "dropped_no_coords": 0, "match": False})
    return pd.DataFrame(rows)


def inputs_signature(agg: str, variant: str) -> str:
    """Signature of the R5 inputs of one network (file names, sizes and content hashes)."""
    h = hashlib.sha1()
    for p in [osm_path(agg), *gtfs_paths(agg, variant)]:
        h.update(p.name.encode())
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                h.update(chunk)
    return h.hexdigest()[:16]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aggs", nargs="+", default=PHASE1)
    ap.add_argument("--variants", nargs="+", default=list(gs.VARIANTS))
    ap.add_argument("--skip-osm", action="store_true")
    ap.add_argument("--force-osm", action="store_true")
    a = ap.parse_args()
    osm_stats = {} if a.skip_osm else extract_osm(a.aggs, force=a.force_osm)
    for agg in a.aggs:
        info_path = agg_dir(agg) / "inputs.json"
        info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
        if agg in osm_stats:
            info["osm"] = osm_stats[agg]
        info["inputs_version"] = INPUTS_VERSION
        info.setdefault("gtfs", {})
        for v in a.variants:
            rep = build_gtfs(agg, v)
            val = validate_gtfs(agg, v, rep)
            val.to_csv(agg_dir(agg) / f"gtfs_{v}_validation.csv", index=False, lineterminator="\n")
            info["gtfs"][v] = {"feeds": rep, "all_match": bool(val["match"].all())}
            print(f"gtfs {agg} {v}: {sum(x['trips'] for k, x in rep.items() if not k.startswith('_'))} trips, "
                  f"{rep['_build_s']} s, validation {'OK' if val['match'].all() else 'MISMATCH'}", flush=True)
            if not val["match"].all():
                print(val[~val["match"]].to_string(), flush=True)
        write_json(info_path, info)


if __name__ == "__main__":
    main()
