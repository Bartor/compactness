"""Drop rows identical to the previous observation of the same entity."""
from __future__ import annotations


class Deduper:
    def __init__(self, key, value):
        self._key, self._value, self._last = key, value, {}

    def filter(self, rows):
        out = []
        for r in rows:
            k, v = self._key(r), self._value(r)
            if self._last.get(k) == v:
                continue
            self._last[k] = v
            out.append(r)
        return out


def vehicle_deduper() -> Deduper:
    return Deduper(
        key=lambda r: r["vehicle_id"] or ("trip:" + str(r["trip_id"])),
        value=lambda r: (r["vehicle_ts"], r["lat"], r["lon"]),
    )


def trip_update_deduper() -> Deduper:
    return Deduper(
        key=lambda r: (r["trip_id"], r["start_date"], r["stop_sequence"], r["stop_id"]),
        value=lambda r: (r["arrival_delay"], r["arrival_time"], r["departure_delay"], r["departure_time"]),
    )
