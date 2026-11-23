"""Daily Parquet partitions: <root>/<name>/date=YYYY-MM-DD/part-HHMMSS.parquet (+ compact)."""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

LOCAL_TZ = ZoneInfo("Europe/Warsaw")  # partition date = Polish local day
log = logging.getLogger("collector.writer")

COMPRESSION = "zstd"
COMPRESSION_LEVEL = 6
COMPACTED = "part-compacted.parquet"


def local_date(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")


def write_parquet_atomic(table: pa.Table, final: Path) -> None:
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.with_name("." + final.name + ".tmp")  # dot-prefixed: ignored by readers
    pq.write_table(table, tmp, compression=COMPRESSION, compression_level=COMPRESSION_LEVEL,
                   use_dictionary=True)
    os.replace(tmp, final)


class PartitionWriter:
    def __init__(self, root: Path, name: str, schema: pa.Schema, sort_by: list[str]):
        self.dir = Path(root) / name
        self.name, self.schema, self.sort_by = name, schema, sort_by
        self._buf: list[dict] = []
        self._lock = threading.Lock()
        self.bytes_written = 0
        self.rows_written = 0

    def add(self, rows: list[dict]) -> None:
        if rows:
            with self._lock:
                self._buf.extend(rows)

    def pending(self) -> int:
        with self._lock:
            return len(self._buf)

    def flush(self, now: datetime | None = None) -> list[Path]:
        with self._lock:
            rows, self._buf = self._buf, []
        if not rows:
            return []
        now = now or datetime.now(LOCAL_TZ)
        by_day: dict[str, list[dict]] = {}
        for r in rows:
            by_day.setdefault(local_date(r["fetched_at"]), []).append(r)
        paths = []
        for day, drows in by_day.items():
            try:
                table = pa.Table.from_pylist(drows, schema=self.schema)
                table = table.sort_by([(c, "ascending") for c in self.sort_by])
                stamp = now.astimezone(LOCAL_TZ).strftime("%H%M%S")
                final = self.dir / f"date={day}" / f"part-{stamp}.parquet"
                n = 1
                while final.exists():
                    final = final.with_name(f"part-{stamp}-{n}.parquet")
                    n += 1
                write_parquet_atomic(table, final)
                self.bytes_written += final.stat().st_size
                self.rows_written += len(drows)
                paths.append(final)
            except Exception:
                log.exception("flush failed for %s %s; rows put back", self.name, day)
                with self._lock:
                    self._buf = drows + self._buf
        return paths


def compact_day(day_dir: Path, schema: pa.Schema, sort_by: list[str]) -> Path | None:
    """Merge all part-*.parquet of one day into part-compacted.parquet."""
    day_dir = Path(day_dir)
    parts = sorted(p for p in day_dir.glob("part-*.parquet") if p.name != COMPACTED)
    target = day_dir / COMPACTED
    if not parts:
        return None
    sources = ([target] if target.exists() else []) + parts
    merged = pa.concat_tables([pq.read_table(p, schema=schema) for p in sources])
    merged = merged.sort_by([(c, "ascending") for c in sort_by])
    write_parquet_atomic(merged, target)
    if pq.read_metadata(target).num_rows != merged.num_rows:
        raise RuntimeError(f"row count mismatch after compaction in {day_dir}")
    for p in parts:
        p.unlink()
    return target
