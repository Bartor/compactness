"""Outage bookkeeping: one JSON line per outage per feed in <archive>/_log/gaps.jsonl."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds") if dt else None


class GapLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def write(self, feed: str, start: datetime, end: datetime, reason: str, failures: int,
              first_failure: datetime | None = None, open_at_stop: bool = False) -> dict:
        rec = {
            "feed": feed,
            "start": _iso(start),            # last successful poll (data missing from here)
            "end": _iso(end),                # first successful poll afterwards (or stop time)
            "duration_s": round((end - start).total_seconds()),
            "reason": reason,
            "consecutive_failures": failures,
            "first_failure": _iso(first_failure),
        }
        if open_at_stop:
            rec["open_at_stop"] = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec


class FeedGapTracker:
    """Tracks consecutive failures of one feed; writes a record when it recovers.

    Outages with fewer than `min_failures` consecutive failures are not logged.
    """

    def __init__(self, feed: str, log: GapLog, min_failures: int = 2):
        self.feed, self.log, self.min_failures = feed, log, min_failures
        self.last_ok: datetime | None = None
        self.failures = 0
        self.first_failure: datetime | None = None
        self.reason = ""

    def success(self, now: datetime) -> dict | None:
        rec = None
        if self.failures >= self.min_failures:
            rec = self.log.write(self.feed, self.last_ok or self.first_failure, now, self.reason,
                                 self.failures, self.first_failure)
        self.failures, self.first_failure, self.reason = 0, None, ""
        self.last_ok = now
        return rec

    def failure(self, now: datetime, reason: str) -> None:
        if self.failures == 0:
            self.first_failure = now
        self.failures += 1
        self.reason = reason

    def close(self, now: datetime) -> dict | None:
        """Called at shutdown: flush a still-open outage."""
        if self.failures >= self.min_failures:
            rec = self.log.write(self.feed, self.last_ok or self.first_failure, now,
                                 self.reason + " (collector stopped during outage)",
                                 self.failures, self.first_failure, open_at_stop=True)
            self.failures, self.first_failure = 0, None
            return rec
        return None
