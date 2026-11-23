"""Collector entry point.

  python -m collector.run --archive-dir D [--feeds a,b] [--once] [--duration-s N] [--trip-updates]
  python -m collector.run compact --archive-dir D [--feeds a,b] [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .dedup import trip_update_deduper, vehicle_deduper
from .feeds import DEFAULT_FEEDS_FILE, load_feeds
from .gaps import FeedGapTracker, GapLog
from .parse import VEHICLE_PARSERS, parse_gtfsrt_trip_updates
from .poller import PollJob
from .schema import TRIP_UPDATE_SCHEMA, VEHICLE_SCHEMA
from .writer import LOCAL_TZ, PartitionWriter, compact_day

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_IN_REPO = REPO_ROOT / "collector" / "archive"
VEH_SORT = ["vehicle_id", "vehicle_ts", "fetched_at"]
TU_SORT = ["trip_id", "stop_sequence", "fetched_at"]
TU_SUFFIX = "-tripupdates"
log = logging.getLogger("collector")


def die(msg: str):
    """Configuration error: exit code 2 (start.ps1 / systemd do not restart on it)."""
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def check_archive_dir(path: Path) -> Path:
    """Archive must live outside the git repo (brief 14.6), except collector/archive/ (gitignored)."""
    p = Path(path).expanduser().resolve()
    try:
        p.relative_to(REPO_ROOT)
    except ValueError:
        return p  # outside the repo: fine
    try:
        p.relative_to(ALLOWED_IN_REPO)
        return p
    except ValueError:
        die(f"Refusing to use archive dir inside the repo: {p}\n"
            f"Use a path outside {REPO_ROOT} (or under {ALLOWED_IN_REPO} for tests).")


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = logging.handlers.RotatingFileHandler(log_dir / "collector.log", maxBytes=5_000_000,
                                              backupCount=5, encoding="utf-8")
    sh = logging.StreamHandler()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (fh, sh):
        h.setFormatter(fmt)
        root.addHandler(h)


def write_json_atomic(path: Path, obj) -> None:
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def record_downtime(log_dir: Path, gaps: GapLog, now: datetime) -> None:
    """If the previous run's heartbeat is old, log a collector-level gap."""
    sp = log_dir / "status.json"
    try:
        prev = json.loads(sp.read_text(encoding="utf-8"))
        last = datetime.fromisoformat(prev["updated_at"])
    except Exception:
        return
    if (now - last).total_seconds() > 120:
        how = "clean shutdown" if prev.get("clean_shutdown") else "crash / killed / machine off"
        gaps.write("_collector", last, now, f"collector not running ({how})", 0)


def build_jobs(feeds, archive: Path, gaps: GapLog, stop, trip_updates: bool, ua: str):
    jobs, writers = [], []
    for f in feeds:
        if f.entity == "trip_updates":
            vw = PartitionWriter(archive, f.id + TU_SUFFIX, TRIP_UPDATE_SCHEMA, TU_SORT)
            writers.append(vw)
            jobs.append(PollJob(f.id + TU_SUFFIX, f.url, f.interval, parse_gtfsrt_trip_updates, f.opts,
                                trip_update_deduper(), vw, FeedGapTracker(f.id + TU_SUFFIX, gaps), stop, ua))
            continue
        vw = PartitionWriter(archive, f.id, VEHICLE_SCHEMA, VEH_SORT)
        writers.append(vw)
        jobs.append(PollJob(f.id, f.url, f.interval, VEHICLE_PARSERS[f.format], f.opts,
                            vehicle_deduper(), vw, FeedGapTracker(f.id, gaps), stop, ua))
        if trip_updates and f.trip_updates_url:
            tw = PartitionWriter(archive, f.id + TU_SUFFIX, TRIP_UPDATE_SCHEMA, TU_SORT)
            writers.append(tw)
            jobs.append(PollJob(f.id + TU_SUFFIX, f.trip_updates_url, f.interval, parse_gtfsrt_trip_updates,
                                f.opts, trip_update_deduper(), tw,
                                FeedGapTracker(f.id + TU_SUFFIX, gaps), stop, ua))
    return jobs, writers


def run_collector(args) -> int:
    archive = check_archive_dir(args.archive_dir)
    log_dir = archive / "_log"
    setup_logging(log_dir)
    all_feeds = load_feeds(args.feeds_file)
    if args.feeds:
        want = [x.strip() for x in args.feeds.split(",") if x.strip()]
        unknown = set(want) - {f.id for f in all_feeds}
        if unknown:
            die(f"unknown feeds: {sorted(unknown)}")
        feeds = [f for f in all_feeds if f.id in want]   # explicit selection overrides `enabled`
    else:
        feeds = [f for f in all_feeds if f.enabled]
    feeds = [f for f in feeds if f.url]
    if not feeds:
        die("no feeds selected")

    ua = f"gtfs-rt-archiver/{__version__} (research archive; polite polling)"
    stop = threading.Event()
    gaps = GapLog(log_dir / "gaps.jsonl")
    record_downtime(log_dir, gaps, datetime.now(timezone.utc))
    jobs, writers = build_jobs(feeds, archive, gaps, stop, args.trip_updates, ua)
    log.info("starting: archive=%s feeds=%s", archive, ",".join(j.job_name for j in jobs))

    def on_signal(signum, _frame):
        log.info("signal %s received, shutting down", signum)
        stop.set()

    for s in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, s):
            signal.signal(getattr(signal, s), on_signal)

    started = time.monotonic()
    pid = os.getpid()

    def write_status(clean=False):
        now = datetime.now(timezone.utc)
        write_json_atomic(log_dir / "status.json", {
            "updated_at": now.isoformat(timespec="seconds"), "pid": pid, "version": __version__,
            "started_at_uptime_s": round(time.monotonic() - started),
            "clean_shutdown": clean,
            "feeds": {j.job_name: j.status() for j in jobs},
            "bytes_written": {w.name: w.bytes_written for w in writers},
        })

    if args.once:
        for j in jobs:
            j.poll_once()
        for w in writers:
            w.flush()
        write_status(clean=True)
        for j in jobs:
            print(j.job_name, j.status()["objects_last_poll"], j.status()["last_error"])
        return 0

    for j in jobs:
        j.start()
    next_flush = next_status = time.monotonic()
    next_status += 60
    next_flush += args.flush_s
    write_status()
    while not stop.wait(1.0):
        t = time.monotonic()
        if args.duration_s and t - started >= args.duration_s:
            log.info("duration reached")
            stop.set()
            break
        if t >= next_status:
            write_status()
            next_status = t + 60
        if t >= next_flush:
            for w in writers:
                w.flush()
            next_flush = t + args.flush_s
    stop.set()
    for j in jobs:
        j.join(timeout=25)
    now = datetime.now(timezone.utc)
    for j in jobs:
        j.tracker.close(now)
    for w in writers:
        w.flush()
    write_status(clean=True)
    log.info("stopped cleanly")
    return 0


def run_compact(args) -> int:
    archive = check_archive_dir(args.archive_dir)
    setup_logging(archive / "_log")
    today = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    for fdir in sorted(p for p in archive.iterdir() if p.is_dir() and not p.name.startswith("_")):
        if args.feeds and fdir.name.removesuffix(TU_SUFFIX) not in args.feeds.split(","):
            continue
        schema, sort = ((TRIP_UPDATE_SCHEMA, TU_SORT) if fdir.name.endswith(TU_SUFFIX)
                        else (VEHICLE_SCHEMA, VEH_SORT))
        for day_dir in sorted(fdir.glob("date=*")):
            day = day_dir.name[5:]
            if (args.date and day != args.date) or (not args.date and day >= today):
                continue  # never touch today's partition unless asked
            before = sum(p.stat().st_size for p in day_dir.glob("*.parquet"))
            out = compact_day(day_dir, schema, sort)
            if out:
                log.info("compacted %s: %d -> %d bytes", day_dir, before, out.stat().st_size)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    compact = bool(argv) and argv[0] == "compact"
    if compact:
        argv = argv[1:]
    ap = argparse.ArgumentParser(prog="python -m collector.run" + (" compact" if compact else ""))
    ap.add_argument("--archive-dir", type=Path, required=True, help="outside the repo (or collector/archive/)")
    ap.add_argument("--feeds", help="comma-separated feed ids (overrides `enabled` in feeds.yaml)")
    if compact:
        ap.add_argument("--date", help="compact only this YYYY-MM-DD (default: all finished days)")
        return run_compact(ap.parse_args(argv))
    ap.add_argument("--feeds-file", type=Path, default=DEFAULT_FEEDS_FILE)
    ap.add_argument("--once", action="store_true", help="poll each feed once, flush and exit")
    ap.add_argument("--duration-s", type=float, default=0, help="stop after N seconds (default: run forever)")
    ap.add_argument("--flush-s", type=float, default=300, help="parquet flush interval")
    ap.add_argument("--trip-updates", action="store_true", help="also capture TripUpdates where offered (off by default)")
    return run_collector(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
