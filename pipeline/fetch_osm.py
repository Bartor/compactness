"""Download the Poland OSM extract (Geofabrik) and register it in the manifest.

Uses ``curl -C -`` so that an interrupted 2 GB download resumes.
"""
from __future__ import annotations

import subprocess
import sys

from .common import RAW, load_config, register

DEST = RAW / "osm" / "poland-latest.osm.pbf"
SOURCE = "OpenStreetMap contributors, extract by Geofabrik GmbH"


def pbf_timestamp(path) -> str:
    """Replication timestamp from the PBF header (data date of the extract)."""
    import osmium
    h = osmium.io.Reader(str(path)).header()
    return h.get("osmosis_replication_timestamp") or ""


def main() -> None:
    url = load_config()["sources"]["osm"]["pbf_url"]
    DEST.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["curl", "-sS", "-L", "--retry", "5", "-C", "-", "-A", "compactness-pipeline/0.1",
         "-o", str(DEST), url])
    if r.returncode != 0:
        sys.exit(f"curl failed with {r.returncode}")
    ts = pbf_timestamp(DEST)
    row = register(
        "osm_poland_pbf", DEST, url, license="ODbL 1.0", source=SOURCE, data_date=ts,
        notes="data_date = osmosis_replication_timestamp from the PBF header",
    )
    print(row["bytes"], "bytes; data_date", ts)


if __name__ == "__main__":
    main()
