"""Explicit Parquet schemas for the archive."""
from __future__ import annotations

import pyarrow as pa

TS_S = pa.timestamp("s", tz="UTC")
TS_MS = pa.timestamp("ms", tz="UTC")

VEHICLE_SCHEMA = pa.schema([
    ("fetched_at", TS_MS),            # when we received the response (UTC)
    ("feed_ts", TS_S),                # FeedHeader.timestamp
    ("vehicle_ts", TS_S),             # VehiclePosition.timestamp
    ("vehicle_id", pa.string()),
    ("trip_id", pa.string()),
    ("route_id", pa.string()),
    ("start_date", pa.string()),      # YYYYMMDD as published
    ("start_time", pa.string()),      # HH:MM:SS as published
    ("direction_id", pa.int8()),
    ("lat", pa.float32()),         # sources are float32 (protobuf) -> lossless
    ("lon", pa.float32()),
    ("bearing", pa.float32()),        # degrees
    ("speed", pa.float32()),          # m/s (GTFS-RT convention; converted for JSON adapters)
    ("current_stop_sequence", pa.int32()),
    ("stop_id", pa.string()),
    ("current_status", pa.string()),  # INCOMING_AT / STOPPED_AT / IN_TRANSIT_TO
    ("label", pa.string()),
])

TRIP_UPDATE_SCHEMA = pa.schema([
    ("fetched_at", TS_MS),
    ("feed_ts", TS_S),
    ("trip_id", pa.string()),
    ("route_id", pa.string()),
    ("start_date", pa.string()),
    ("start_time", pa.string()),
    ("vehicle_id", pa.string()),
    ("stop_sequence", pa.int32()),
    ("stop_id", pa.string()),
    ("arrival_delay", pa.int32()),    # seconds
    ("arrival_time", TS_S),
    ("departure_delay", pa.int32()),
    ("departure_time", TS_S),
])
