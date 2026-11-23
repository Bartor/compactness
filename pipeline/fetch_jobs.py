"""Fetch the Goliszek jobs / working-age population dataset from Mendeley Data (public API)."""
from __future__ import annotations

import time

import requests

from .common import RAW, USER_AGENT, download, sha256_of, write_json

DS = "mr9ywkgd9t"
API = f"https://data.mendeley.com/public-api/datasets/{DS}"
OUT = RAW / "jobs"
CITATION = (
    "Goliszek S. (IGiPZ PAN), Spatially disaggregated working-age population and job estimates "
    "for seven Polish cities with a 2025 allocation horizon, Mendeley Data, v1, "
    "doi:10.17632/mr9ywkgd9t.1"
)


def main() -> None:
    t0 = time.time()
    h = {"User-Agent": USER_AGENT}
    meta = requests.get(API, headers=h, timeout=60)
    meta.raise_for_status()
    meta = meta.json()
    OUT.mkdir(parents=True, exist_ok=True)
    # keep the author's metadata (description + method) next to the data; deterministic JSON
    write_json(OUT / "dataset_metadata.json", meta)
    for f in meta["files"]:
        cd = f["content_details"]
        dest = OUT / f["filename"]
        download(
            f"jobs_{f['filename']}", cd["download_url"], dest,
            license="CC BY 4.0", source=CITATION,
            data_date=meta.get("publish_date", "")[:10],
            notes=f"Mendeley sha256 {cd['sha256_hash']}", timeout=300,
        )
        ok = sha256_of(dest) == cd["sha256_hash"]
        print(f["filename"], cd["size"], "sha256 matches Mendeley:", ok)
        if not ok:
            raise SystemExit(f"checksum mismatch for {dest}")
    # register the metadata snapshot too
    from .common import register
    register("jobs_dataset_metadata", OUT / "dataset_metadata.json", API,
             license="CC BY 4.0", source=CITATION, data_date=meta.get("publish_date", "")[:10],
             notes="Mendeley public-API record (description, method)")
    print("done in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
