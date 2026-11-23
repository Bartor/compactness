import json
from datetime import datetime, timedelta, timezone

import pyarrow.parquet as pq
import pytest
from google.transit import gtfs_realtime_pb2 as pb

from collector.dedup import trip_update_deduper, vehicle_deduper
from collector.gaps import FeedGapTracker, GapLog
from collector.parse import parse_gdansk_json, parse_gtfsrt_trip_updates, parse_gtfsrt_vehicles
from collector.run import check_archive_dir
from collector.schema import VEHICLE_SCHEMA
from collector.writer import PartitionWriter, compact_day

NOW = datetime(2026, 11, 23, 12, 0, 5, tzinfo=timezone.utc)


def make_feed(vehicles=(), trip_updates=()):
    m = pb.FeedMessage()
    m.header.gtfs_realtime_version = "2.0"
    m.header.timestamp = 1795454137
    for i, (vid, ts, lat, lon) in enumerate(vehicles):
        e = m.entity.add()
        e.id = str(i)
        v = e.vehicle
        v.vehicle.id = vid
        v.timestamp = ts
        v.position.latitude, v.position.longitude = lat, lon
        v.trip.trip_id = "2026-11-23:19:PcS:4:1812"
        v.trip.start_date = "20261123"
    for tid in trip_updates:
        e = m.entity.add()
        e.id = "tu" + tid
        e.trip_update.trip.trip_id = tid
        stu = e.trip_update.stop_time_update.add()
        stu.stop_sequence = 3
        stu.arrival.delay = 60
    return m.SerializeToString()


def test_parse_vehicles_nulls_and_route_from_trip():
    ts, rows = parse_gtfsrt_vehicles(make_feed([("V/1", 1795454128, 52.2, 21.0)]), NOW,
                                     {"route_from_trip": "colon:1"})
    assert ts.year == 2026 and len(rows) == 1
    r = rows[0]
    assert r["vehicle_id"] == "V/1" and r["route_id"] == "19" and r["trip_id"].startswith("2026")
    assert r["bearing"] is None and r["speed"] is None and r["direction_id"] is None
    assert r["current_status"] is None and r["stop_id"] is None
    assert tuple(r) == tuple(VEHICLE_SCHEMA.names)


def test_parse_trip_updates():
    _, rows = parse_gtfsrt_trip_updates(make_feed(trip_updates=["t1"]), NOW)
    assert rows[0]["arrival_delay"] == 60 and rows[0]["departure_delay"] is None


def test_parse_gdansk_json():
    body = json.dumps({"lastUpdate": "2026-11-23T17:17:17Z", "vehicles": [
        {"generated": "2026-11-23T17:17:13Z", "routeId": 307, "tripId": 111, "vehicleCode": "8201",
         "vehicleId": 146136, "speed": 36, "direction": 180, "lat": 54.2, "lon": 18.6,
         "scheduledTripStartTime": "2026-11-23T17:07:00Z"}]}).encode()
    _, rows = parse_gdansk_json(body, NOW)
    assert rows[0]["speed"] == pytest.approx(10.0) and rows[0]["route_id"] == "307"
    assert rows[0]["vehicle_id"] == "146136" and rows[0]["label"] == "8201"


def test_dedup_drops_identical_observation():
    d = vehicle_deduper()
    _, a = parse_gtfsrt_vehicles(make_feed([("V/1", 100, 52.0, 21.0), ("V/2", 100, 52.1, 21.1)]), NOW)
    _, same = parse_gtfsrt_vehicles(make_feed([("V/1", 100, 52.0, 21.0)]), NOW)
    _, moved = parse_gtfsrt_vehicles(make_feed([("V/1", 100, 52.0001, 21.0)]), NOW)
    _, newer = parse_gtfsrt_vehicles(make_feed([("V/1", 130, 52.0, 21.0)]), NOW)
    assert len(d.filter(a)) == 2
    assert d.filter(same) == []
    assert len(d.filter(moved)) == 1
    assert len(d.filter(newer)) == 1


def test_trip_update_dedup():
    d = trip_update_deduper()
    _, r1 = parse_gtfsrt_trip_updates(make_feed(trip_updates=["t1"]), NOW)
    _, r2 = parse_gtfsrt_trip_updates(make_feed(trip_updates=["t1"]), NOW)
    assert len(d.filter(r1)) == 1 and d.filter(r2) == []


def test_partition_writer_and_compact(tmp_path):
    w = PartitionWriter(tmp_path, "feed", VEHICLE_SCHEMA, ["vehicle_id", "vehicle_ts"])
    _, rows = parse_gtfsrt_vehicles(make_feed([("V/2", 100, 52.0, 21.0), ("V/1", 100, 52.1, 21.1)]), NOW)
    w.add(rows)
    p1 = w.flush(NOW)
    w.add(rows)
    p2 = w.flush(NOW)  # same second: must not overwrite
    assert p1 and p2 and p1[0] != p2[0]
    day_dir = p1[0].parent
    assert day_dir.name == "date=2026-11-23" and p1[0].name.startswith("part-")
    assert not list(day_dir.glob(".*tmp"))
    t = pq.read_table(p1[0])
    assert t.schema.names == VEHICLE_SCHEMA.names and t["vehicle_id"].to_pylist() == ["V/1", "V/2"]
    assert pq.ParquetFile(p1[0]).metadata.row_group(0).column(0).compression == "ZSTD"
    out = compact_day(day_dir, VEHICLE_SCHEMA, ["vehicle_id", "vehicle_ts"])
    assert [p.name for p in day_dir.glob("*.parquet")] == ["part-compacted.parquet"]
    assert pq.read_table(out).num_rows == 4


def test_partition_by_local_day(tmp_path):
    w = PartitionWriter(tmp_path, "feed", VEHICLE_SCHEMA, ["vehicle_id"])
    _, rows = parse_gtfsrt_vehicles(make_feed([("V/1", 100, 52.0, 21.0)]), datetime(2026, 11, 23, 23, 30, tzinfo=timezone.utc))
    w.add(rows)
    assert w.flush(NOW)[0].parent.name == "date=2026-11-24"  # 00:30 in Warsaw


def test_gap_bookkeeping(tmp_path):
    log = GapLog(tmp_path / "gaps.jsonl")
    tr = FeedGapTracker("f", log, min_failures=2)
    t0 = NOW
    tr.success(t0)
    tr.failure(t0 + timedelta(seconds=20), "timeout")           # single failure: not logged
    tr.success(t0 + timedelta(seconds=40))
    assert not (tmp_path / "gaps.jsonl").exists()
    tr.failure(t0 + timedelta(seconds=60), "HTTPError 503")
    tr.failure(t0 + timedelta(seconds=80), "HTTPError 503")
    tr.failure(t0 + timedelta(seconds=100), "HTTPError 503")
    rec = tr.success(t0 + timedelta(seconds=300))
    assert rec["consecutive_failures"] == 3 and rec["duration_s"] == 260 and rec["feed"] == "f"
    lines = (tmp_path / "gaps.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["reason"] == "HTTPError 503"
    tr.failure(t0 + timedelta(seconds=320), "x")
    tr.failure(t0 + timedelta(seconds=340), "x")
    assert tr.close(t0 + timedelta(seconds=360))["open_at_stop"] is True


def test_archive_dir_guard(tmp_path):
    assert check_archive_dir(tmp_path) == tmp_path.resolve()
    from collector.run import ALLOWED_IN_REPO, REPO_ROOT
    assert check_archive_dir(ALLOWED_IN_REPO / "x") == (ALLOWED_IN_REPO / "x").resolve()
    with pytest.raises(SystemExit):
        check_archive_dir(REPO_ROOT / "data")
    with pytest.raises(SystemExit):
        check_archive_dir(REPO_ROOT)
