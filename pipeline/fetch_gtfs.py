"""Fetch every GTFS feed from config.yaml and run the MobilityData gtfs-validator on it.

    python -m pipeline.fetch_gtfs fetch      # download + register in data/manifest.csv
    python -m pipeline.fetch_gtfs validate   # run validator -> results/qa/gtfs_validator + validator_summary.csv
    python -m pipeline.fetch_gtfs all

Raw files go to data/raw/gtfs/<feed_id>/<download-date>/<feed_id>.zip.  One download per
feed and day (the file is skipped when it is already in the manifest).  Downloaded zips
are only ever read as data; nothing inside them is executed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import requests

from pipeline import common
from pipeline.common import (RAW, RESULTS, TOOLS, load_config, register, write_json, write_meta)

QA_VALIDATOR = RESULTS / "qa" / "gtfs_validator"
QA_PHASE0 = RESULTS / "qa" / "phase0" / "gtfs"
VALIDATOR_REPO = "MobilityData/gtfs-validator"
JAVA = TOOLS / "jdk21" / "bin" / "java.exe"
MAX_REPORT_BYTES = 1_000_000
MANIFEST_PREFIX = "gtfs_"


def manifest_id(feed_id: str) -> str:
    return MANIFEST_PREFIX + feed_id


def latest_raw(feed_id: str) -> Path | None:
    """Newest downloaded zip for a feed (folders are ISO dates, so lexical order works)."""
    base = RAW / "gtfs" / feed_id
    zips = sorted(base.glob("*/*.zip")) if base.exists() else []
    return zips[-1] if zips else None


def _data_date(zpath: Path) -> str:
    """Cheap validity string 'first/last' from calendar.txt/feed_info.txt, for the manifest."""
    import io
    import pandas as pd
    try:
        with zipfile.ZipFile(zpath) as zf:
            names = set(zf.namelist())
            lo, hi = [], []
            for n, cols in (("calendar.txt", ("start_date", "end_date")),
                            ("calendar_dates.txt", ("date", "date"))):
                if n in names:
                    d = pd.read_csv(io.BytesIO(zf.read(n)), dtype=str, encoding="utf-8-sig")
                    lo.append(d[cols[0]].min())
                    hi.append(d[cols[1]].max())
            lo = [x for x in lo if isinstance(x, str)]
            hi = [x for x in hi if isinstance(x, str)]
            return f"{min(lo)}/{max(hi)}" if lo and hi else ""
    except Exception:  # noqa: BLE001 - informative only
        return ""


def resolve_url(f: dict) -> str:
    """Resolve feeds whose URL changes over time (only Wrocław's open-data resource ids so far)."""
    url = f["url"]
    if f.get("resolve") != "wroclaw_cui":
        return url
    import re
    n = int(re.search(r"/download/(\d+)/", url).group(1))
    best = url
    for k in range(n + 1, n + 9):
        u = re.sub(r"/download/\d+/", f"/download/{k}/", url)
        with requests.get(u, stream=True, timeout=60, headers={"User-Agent": common.USER_AGENT}) as r:
            if r.status_code != 200:
                break
            if "GTFS" in r.headers.get("content-disposition", ""):
                best = u
        time.sleep(0.5)
    return best


def fetch(only: list[str] | None = None, force: bool = False) -> dict[str, str]:
    cfg = load_config()["feeds"]
    today = dt.date.today().isoformat()
    status: dict[str, str] = {}
    for fid, f in cfg.items():
        if only and fid not in only:
            continue
        url = f.get("url")
        if not url:
            status[fid] = "NO URL"
            continue
        url = resolve_url(f)
        dest = RAW / "gtfs" / fid / today / f"{fid}.zip"
        try:
            common.download(
                manifest_id(fid), url, dest,
                license=f.get("license", ""), source=f.get("publisher", ""),
                notes=f.get("notes", "") + (f" licence terms: {f['license_url']}" if f.get("license_url") else ""),
                force=force,
            )
            if not zipfile.is_zipfile(dest):
                raise RuntimeError("downloaded file is not a zip")
            # refine the manifest row with the validity window (re-registers the same file)
            row = {r["id"]: r for r in common.read_manifest()}[manifest_id(fid)]
            register(manifest_id(fid), dest, url, license=f.get("license", ""),
                     source=f.get("publisher", ""), data_date=_data_date(dest),
                     notes=row["notes"], downloaded_at=row["downloaded_at"])
            status[fid] = f"ok {dest.stat().st_size/1e6:.1f} MB"
        except Exception as e:  # noqa: BLE001
            status[fid] = f"FAILED: {e}"
        print(fid, status[fid], flush=True)
        time.sleep(1)
    return status


# --------------------------------------------------------------------------- validator
def validator_jar() -> Path:
    """Return the newest gtfs-validator CLI jar in .tools, downloading it when missing."""
    TOOLS.mkdir(exist_ok=True)
    jars = sorted(TOOLS.glob("gtfs-validator-*-cli.jar"))
    if jars:
        return jars[-1]
    r = requests.get(f"https://api.github.com/repos/{VALIDATOR_REPO}/releases/latest",
                     headers={"User-Agent": common.USER_AGENT}, timeout=60)
    r.raise_for_status()
    rel = r.json()
    asset = next(a for a in rel["assets"] if a["name"].endswith("-cli.jar"))
    dest = TOOLS / asset["name"]
    common.download("tool_" + asset["name"], asset["browser_download_url"], dest,
                    license="Apache-2.0", source="MobilityData gtfs-validator " + rel["tag_name"])
    return dest


def run_validator(feed_id: str, jar: Path, force: bool = False) -> dict:
    zpath = latest_raw(feed_id)
    if zpath is None:
        return {"feed": feed_id, "error": "no raw file"}
    out_dir = QA_VALIDATOR / feed_id
    work = common.INTERIM / "gtfs_validator" / feed_id
    summary_path = out_dir / "summary.json"
    if summary_path.exists() and not force:
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        if s.get("input_sha256") == common.sha256_of(zpath):
            return s
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    cmd = [str(JAVA), "-Xmx6g", "-jar", str(jar), "-i", str(zpath), "-o", str(work),
           "-c", "pl", "--validation_report_name", "report.json",
           "--system_errors_report_name", "system_errors.json", "--html_report_name", "report.html"]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    rep = work / "report.json"
    if not rep.exists():
        return {"feed": feed_id, "error": f"validator failed rc={p.returncode}: {p.stderr[-500:]}"}
    report = json.loads(rep.read_text(encoding="utf-8"))
    notices = []
    for n in report.get("notices", []):
        notices.append({"code": n["code"], "severity": n["severity"], "count": n.get("totalNotices", len(n.get("sampleNotices", [])))})
    notices.sort(key=lambda x: ({"ERROR": 0, "WARNING": 1, "INFO": 2}.get(x["severity"], 3), -x["count"], x["code"]))
    sev = {k: sum(n["count"] for n in notices if n["severity"] == k) for k in ("ERROR", "WARNING", "INFO")}
    summary = {
        "feed": feed_id,
        "input_sha256": common.sha256_of(zpath),
        "validator_version": report.get("summary", {}).get("validatorVersion", jar.name),
        "validated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "duration_s": round(time.time() - t0, 1),
        "totals": sev,
        "notice_types": {k: sum(1 for n in notices if n["severity"] == k) for k in sev},
        "notices": notices,
        "gtfs_features": report.get("summary", {}).get("gtfsFeatures", []),
    }
    write_json(summary_path, summary)
    out_dir.mkdir(parents=True, exist_ok=True)
    if rep.stat().st_size <= MAX_REPORT_BYTES:
        shutil.copyfile(rep, out_dir / "report.json")
    elif (out_dir / "report.json").exists():
        (out_dir / "report.json").unlink()
    sysf = work / "system_errors.json"
    if sysf.exists() and sysf.stat().st_size < 100_000:
        shutil.copyfile(sysf, out_dir / "system_errors.json")
    return summary


def validate(only: list[str] | None = None, force: bool = False) -> None:
    t0 = time.time()
    jar = validator_jar()
    rows, inputs = [], []
    for fid in load_config()["feeds"]:
        if only and fid not in only:
            continue
        s = run_validator(fid, jar, force)
        inputs.append(manifest_id(fid))
        if "error" in s:
            print(fid, s["error"], flush=True)
            rows.append({"feed": fid, "validator_version": jar.name, "errors": "", "warnings": "", "infos": "",
                         "top_error_codes": s["error"][:120], "top_warning_codes": ""})
            continue
        top = [f"{n['code']}({n['count']})" for n in s["notices"] if n["severity"] == "ERROR"][:5]
        rows.append({"feed": fid, "validator_version": s["validator_version"], "errors": s["totals"]["ERROR"],
                     "warnings": s["totals"]["WARNING"], "infos": s["totals"]["INFO"],
                     "top_error_codes": "; ".join(top),
                     "top_warning_codes": "; ".join([f"{n['code']}({n['count']})" for n in s["notices"] if n["severity"] == "WARNING"][:3])})
        print(fid, s["totals"], flush=True)
    rows.sort(key=lambda r: r["feed"])
    QA_PHASE0.mkdir(parents=True, exist_ok=True)
    with open(QA_PHASE0 / "validator_summary.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["feed", "validator_version", "errors", "warnings", "infos", "top_error_codes", "top_warning_codes"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    write_meta(QA_VALIDATOR, "gtfs_validator", inputs=inputs, started=t0,
               extra={"validator_jar": jar.name})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "validate", "all"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd in ("fetch", "all"):
        st = fetch(a.only, a.force)
        if any(v.startswith(("FAILED", "NO URL")) for v in st.values()):
            print("some feeds failed", st, file=sys.stderr)
    if a.cmd in ("validate", "all"):
        validate(a.only, a.force)


if __name__ == "__main__":
    main()
