"""Shared helpers: paths, config, downloads with a manifest, step metadata, rounding.

Every pipeline module imports from here so that paths and the manifest format
stay in one place.  Run modules from the repo root: ``python -m pipeline.<module>``.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml
from filelock import FileLock

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"            # downloaded files, never committed
INTERIM = DATA / "interim"    # intermediate products, never committed
RESULTS = ROOT / "results"    # committed
TILES = ROOT / "tiles"        # committed
TOOLS = ROOT / ".tools"       # local JDK, jars, binaries; never committed
MANIFEST = DATA / "manifest.csv"

CRS_METRIC = "EPSG:2180"
USER_AGENT = "compactness-pipeline/0.1 (research; python-requests)"

MANIFEST_FIELDS = [
    "id", "path", "url", "downloaded_at", "sha256", "bytes",
    "license", "source", "data_date", "notes",
]


def load_config() -> dict[str, Any]:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest() -> list[dict[str, str]]:
    if not MANIFEST.exists():
        return []
    with open(MANIFEST, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def register(
    id: str,
    path: Path,
    url: str,
    *,
    license: str = "",
    source: str = "",
    data_date: str = "",
    notes: str = "",
    downloaded_at: str | None = None,
) -> dict[str, str]:
    """Record a raw file in data/manifest.csv (one row per id, sorted, locked).

    Safe to call from several processes at once.
    """
    path = Path(path)
    row = {
        "id": id,
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "url": url,
        "downloaded_at": downloaded_at or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sha256": sha256_of(path),
        "bytes": str(path.stat().st_size),
        "license": license,
        "source": source,
        "data_date": data_date,
        "notes": notes,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(MANIFEST) + ".lock"):
        rows = {r["id"]: r for r in read_manifest()}
        rows[id] = row
        with open(MANIFEST, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
            w.writeheader()
            for key in sorted(rows):
                w.writerow({k: rows[key].get(k, "") for k in MANIFEST_FIELDS})
    return row


def download(
    id: str,
    url: str,
    dest: Path,
    *,
    license: str = "",
    source: str = "",
    data_date: str = "",
    notes: str = "",
    force: bool = False,
    timeout: int = 120,
    headers: dict[str, str] | None = None,
) -> Path:
    """Download ``url`` to ``dest`` (under data/raw) and register it in the manifest.

    Skips the download when the file exists and is already in the manifest,
    unless ``force``.  Retries transient failures three times.
    """
    dest = Path(dest)
    known = {r["id"] for r in read_manifest()}
    if dest.exists() and id in known and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    last: Exception | None = None
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=timeout, headers=hdrs) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            tmp.replace(dest)
            break
        except Exception as e:  # noqa: BLE001 - retried, then re-raised
            last = e
            time.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError(f"download failed: {url}: {last}")
    register(id, dest, url, license=license, source=source, data_date=data_date, notes=notes)
    return dest


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:  # noqa: BLE001 - no commit yet
        return ""


def write_meta(
    out_dir: Path,
    step: str,
    *,
    inputs: Iterable[str] = (),
    started: float | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write ``_meta.json`` next to a step's outputs (brief §14.2).

    ``inputs`` are manifest ids; their hashes are copied from the manifest.
    A result without ``_meta.json`` counts as incomplete.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {r["id"]: r for r in read_manifest()}
    meta = {
        "step": step,
        "git_sha": git_sha(),
        "run_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "duration_s": round(time.time() - started, 1) if started else None,
        "inputs": {
            i: {k: manifest[i][k] for k in ("sha256", "downloaded_at", "data_date")}
            for i in sorted(inputs) if i in manifest
        },
        "missing_inputs": sorted(i for i in inputs if i not in manifest),
        **(extra or {}),
    }
    path = out_dir / "_meta.json"
    write_json(path, meta)
    return path


def sig(x: Any, digits: int = 4) -> Any:
    """Round a number to ``digits`` significant figures; pass anything else through."""
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, int):
        return x
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(v) or math.isinf(v):
        return None
    if v == 0:
        return 0.0
    return round(v, digits - 1 - int(math.floor(math.log10(abs(v)))))


def round_sig(obj: Any, digits: int = 4) -> Any:
    """Apply :func:`sig` through nested dicts and lists."""
    if isinstance(obj, dict):
        return {k: round_sig(v, digits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_sig(v, digits) for v in obj]
    return sig(obj, digits)


def write_json(path: Path, obj: Any) -> None:
    """Deterministic JSON: sorted keys, UTF-8, trailing newline."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
