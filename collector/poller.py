"""One polling thread per (feed, entity type): a slow/dead feed never delays the others."""
from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timezone

import requests

from .gaps import FeedGapTracker
from .writer import PartitionWriter, local_date

log = logging.getLogger("collector.poll")

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 20
MAX_BACKOFF = 300.0
STALE_AFTER_S = 600  # feed timestamp not advancing for this long counts as an outage


class PollJob(threading.Thread):
    def __init__(self, name, url, interval, parser, opts, deduper, writer: PartitionWriter,
                 tracker: FeedGapTracker, stop: threading.Event, user_agent: str,
                 session: requests.Session | None = None):
        super().__init__(name=f"poll-{name}", daemon=True)
        self.job_name, self.url, self.interval = name, url, float(interval)
        self.parser, self.opts, self.deduper = parser, opts or {}, deduper
        self.writer, self.tracker, self.stop_evt = writer, tracker, stop
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._etag = self._last_modified = None
        self._last_feed_ts = None
        self._last_change = time.time()
        # status
        self.last_attempt = self.last_success = None
        self.last_error = None
        self.polls_ok = self.polls_failed = self.polls_304 = 0
        self.vehicles_last = 0
        self.rows_today = 0
        self._rows_day = None
        self._retry_after = 0.0

    # ---- one poll -------------------------------------------------------
    def poll_once(self) -> None:
        now = datetime.now(timezone.utc)
        self.last_attempt = now
        try:
            headers = {}
            if self._etag:
                headers["If-None-Match"] = self._etag
            if self._last_modified:
                headers["If-Modified-Since"] = self._last_modified
            resp = self.session.get(self.url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            fetched_at = datetime.now(timezone.utc)
            if resp.status_code == 304:
                self.polls_304 += 1
                self._check_stale(None, fetched_at)
                self._ok(fetched_at)
                return
            if resp.status_code == 429:
                self._retry_after = float(resp.headers.get("Retry-After", 60) or 60)
            resp.raise_for_status()
            self._etag = resp.headers.get("ETag")
            self._last_modified = resp.headers.get("Last-Modified")
            feed_ts, rows = self.parser(resp.content, fetched_at, self.opts)
            self._check_stale(feed_ts, fetched_at)
            self.vehicles_last = len(rows)
            kept = self.deduper.filter(rows)
            self.writer.add(kept)
            day = local_date(fetched_at)
            if day != self._rows_day:
                self._rows_day, self.rows_today = day, 0
            self.rows_today += len(kept)
            self._ok(fetched_at)
        except Exception as e:  # network, HTTP, parse, stale
            self._fail(datetime.now(timezone.utc), f"{type(e).__name__}: {str(e)[:200]}")

    def _check_stale(self, feed_ts, now) -> None:
        if feed_ts is not None and feed_ts != self._last_feed_ts:
            self._last_feed_ts, self._last_change = feed_ts, time.time()
        if time.time() - self._last_change > STALE_AFTER_S:
            raise RuntimeError(f"stale feed: timestamp unchanged for {int(time.time() - self._last_change)} s")

    def _ok(self, now) -> None:
        self.polls_ok += 1
        self.last_success, self.last_error = now, None
        self._retry_after = 0.0
        self.tracker.success(now)

    def _fail(self, now, reason: str) -> None:
        self.polls_failed += 1
        self.last_error = f"{now.isoformat(timespec='seconds')} {reason}"
        self.tracker.failure(now, reason)
        log.warning("%s failed (%d in a row): %s", self.job_name, self.tracker.failures, reason)

    # ---- scheduling -----------------------------------------------------
    def next_delay(self) -> float:
        n = self.tracker.failures
        base = self.interval * (2 ** min(n, 4)) if n else self.interval
        base = min(max(base, self._retry_after), MAX_BACKOFF) if n else base
        return base * random.uniform(0.9, 1.1)

    def run(self) -> None:
        # spread start-up so feeds don't all hit at once
        if self.stop_evt.wait(random.uniform(0, min(self.interval, 5))):
            return
        while not self.stop_evt.is_set():
            t0 = time.monotonic()
            self.poll_once()
            delay = max(1.0, self.next_delay() - (time.monotonic() - t0))
            if self.stop_evt.wait(delay):
                break

    def status(self) -> dict:
        iso = lambda d: d.isoformat(timespec="seconds") if d else None
        return {
            "url": self.url,
            "last_attempt": iso(self.last_attempt),
            "last_success": iso(self.last_success),
            "rows_today": self.rows_today,
            "objects_last_poll": self.vehicles_last,
            "polls_ok": self.polls_ok,
            "polls_failed": self.polls_failed,
            "polls_304": self.polls_304,
            "consecutive_failures": self.tracker.failures,
            "last_error": self.last_error,
        }
