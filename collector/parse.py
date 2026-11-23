"""Parsers: GTFS-RT protobuf (vehicle positions, trip updates) and custom JSON adapters.

Every parser returns (feed_ts: datetime|None, rows: list[dict]) with keys of the
corresponding schema (nulls as None).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from google.transit import gtfs_realtime_pb2 as pb

_STATUS = {0: "INCOMING_AT", 1: "STOPPED_AT", 2: "IN_TRANSIT_TO"}


def _dt(sec: int | None) -> datetime | None:
    return datetime.fromtimestamp(sec, tz=timezone.utc) if sec else None


def _s(v) -> str | None:
    return v if v else None


def _route_from_trip(trip_id: str, spec: str) -> str | None:
    """spec 'colon:1' -> split trip_id on ':' and take field 1 (Warsaw / mkuran ids)."""
    _, idx = spec.split(":")
    parts = trip_id.split(":")
    return (parts[int(idx)] or None) if len(parts) > int(idx) else None


def parse_gtfsrt_vehicles(content: bytes, fetched_at: datetime, opts: dict | None = None):
    opts = opts or {}
    msg = pb.FeedMessage()
    msg.ParseFromString(content)
    feed_ts = _dt(msg.header.timestamp)
    rows = []
    for e in msg.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        if not v.HasField("position"):
            continue
        t = v.trip
        p = v.position
        trip_id = _s(t.trip_id)
        route_id = _s(t.route_id)
        if route_id is None and trip_id and opts.get("route_from_trip"):
            route_id = _route_from_trip(trip_id, opts["route_from_trip"])
        rows.append({
            "fetched_at": fetched_at,
            "feed_ts": feed_ts,
            "vehicle_ts": _dt(v.timestamp),
            "vehicle_id": _s(v.vehicle.id) or _s(e.id),
            "trip_id": trip_id,
            "route_id": route_id,
            "start_date": _s(t.start_date),
            "start_time": _s(t.start_time),
            "direction_id": t.direction_id if t.HasField("direction_id") else None,
            "lat": p.latitude,
            "lon": p.longitude,
            "bearing": p.bearing if p.HasField("bearing") else None,
            "speed": p.speed if p.HasField("speed") else None,
            "current_stop_sequence": v.current_stop_sequence if v.HasField("current_stop_sequence") else None,
            "stop_id": _s(v.stop_id),
            "current_status": _STATUS.get(v.current_status) if v.HasField("current_status") else None,
            "label": _s(v.vehicle.label),
        })
    return feed_ts, rows


def parse_gtfsrt_trip_updates(content: bytes, fetched_at: datetime, opts: dict | None = None):
    msg = pb.FeedMessage()
    msg.ParseFromString(content)
    feed_ts = _dt(msg.header.timestamp)
    rows = []
    for e in msg.entity:
        if not e.HasField("trip_update"):
            continue
        tu = e.trip_update
        t = tu.trip
        base = {
            "fetched_at": fetched_at, "feed_ts": feed_ts,
            "trip_id": _s(t.trip_id), "route_id": _s(t.route_id),
            "start_date": _s(t.start_date), "start_time": _s(t.start_time),
            "vehicle_id": _s(tu.vehicle.id),
        }
        for st in tu.stop_time_update:
            a, d = st.arrival, st.departure
            rows.append({
                **base,
                "stop_sequence": st.stop_sequence if st.HasField("stop_sequence") else None,
                "stop_id": _s(st.stop_id),
                "arrival_delay": a.delay if a.HasField("delay") else None,
                "arrival_time": _dt(a.time) if a.HasField("time") else None,
                "departure_delay": d.delay if d.HasField("delay") else None,
                "departure_time": _dt(d.time) if d.HasField("time") else None,
            })
    return feed_ts, rows


def _iso(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_gdansk_json(content: bytes, fetched_at: datetime, opts: dict | None = None):
    """ZTM Gdansk `gpsPositions?v=2`. speed is km/h in the source -> m/s here."""
    d = json.loads(content)
    feed_ts = _iso(d.get("lastUpdate"))
    rows = []
    for v in d.get("vehicles", []):
        if v.get("lat") is None or v.get("lon") is None:
            continue
        start = _iso(v.get("scheduledTripStartTime"))
        sp = v.get("speed")
        rows.append({
            "fetched_at": fetched_at,
            "feed_ts": feed_ts,
            "vehicle_ts": _iso(v.get("generated")),
            "vehicle_id": str(v["vehicleId"]) if v.get("vehicleId") is not None else None,
            "trip_id": str(v["tripId"]) if v.get("tripId") is not None else None,
            "route_id": str(v["routeId"]) if v.get("routeId") is not None else None,
            "start_date": start.strftime("%Y%m%d") if start else None,    # UTC date of scheduled start
            "start_time": start.strftime("%H:%M:%S") if start else None,  # UTC time of scheduled start
            "direction_id": None,
            "lat": float(v["lat"]),
            "lon": float(v["lon"]),
            "bearing": float(v["direction"]) if v.get("direction") is not None else None,
            "speed": sp / 3.6 if sp is not None else None,
            "current_stop_sequence": None,
            "stop_id": None,
            "current_status": None,
            "label": _s(str(v.get("vehicleCode") or "")),
        })
    return feed_ts, rows


VEHICLE_PARSERS = {
    "gtfs-rt": parse_gtfsrt_vehicles,
    "gdansk-json": parse_gdansk_json,
}
