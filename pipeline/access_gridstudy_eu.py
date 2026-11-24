"""Polish city values of the DG REGIO grid study (Poelman & Ackermans, "Assessing the performance of urban public
transport using population grid data", PDF dated 2023-02 on ec.europa.eu), read from the public map service of its
interactive viewer.

    python -m pipeline.access_gridstudy_eu fetch [--workers 3]   # resumable, one JSONL per urban centre
    python -m pipeline.access_gridstudy_eu summary              # per-city values -> data/interim/access_gridstudy/eu_city_values.csv

The viewer (https://ec.europa.eu/regional_policy/assets/scripts/map/regio-gis-maps/public_transport/city_acc_grid.html)
draws ArcGIS MapServer raster layers ``PublicTransport/city_acc_grid`` (200 m cells, EPSG:3035).  Its public REST
endpoint answers ``identify`` with the exact pixel value of every layer at a point.  We ask it once per 200 m cell
centre inside each analysed Polish urban centre (GEOSTAT 2011 polygon from layer 0) and aggregate the cell values
ourselves, both as the population-weighted mean of cell performance (the paper, p. 15: "population weighted averages
of accessibility, proximity and performance") and as the ratio of the weighted means.

No login, no bot check: plain GET requests to the endpoint the viewer itself uses, at most a few in flight.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from pipeline.common import INTERIM, RAW

SERVICE = "https://europa.eu/regiogis/rest/services/PublicTransport/city_acc_grid/MapServer"
VIEWER = "https://ec.europa.eu/regional_policy/assets/scripts/map/regio-gis-maps/public_transport/city_acc_grid.html"
PDF_URL = "https://ec.europa.eu/regional_policy/sources/work/assessing_performance_of_urban_public_transport_using_griddata.pdf"
RAWDIR = RAW / "dgregio_gridstudy"
CELLDIR = RAWDIR / "cells"
OUT = INTERIM / "access_gridstudy"
HEADERS = {"User-Agent": "compactness-pipeline/0.1 (research; python-requests)"}
# analysed Polish urban centres (viewer list city_acc_grid_extents.csv); our agglomeration id
PL = {"GEOSTAT11_171": "warszawa", "GEOSTAT11_385": "krakow", "GEOSTAT11_178": "poznan", "GEOSTAT11_229": "lodz"}
LAYERS = {1: "perf30", 2: "perf45", 3: "acc30", 4: "acc45", 5: "prox8", 6: "prox12", 7: "walkshare30",
          8: "walkshare45", 9: "avgdist8", 10: "avgdist12", 11: "pop2018"}
CELL = 200.0
_lock = threading.Lock()


def uc_polygon(hid: str):
    """GEOSTAT 2011 urban centre polygon (EPSG:3035) and its attributes from layer 0."""
    import shapely.geometry
    p = RAWDIR / f"uc_{hid}.geojson"
    if not p.exists():
        r = requests.get(f"{SERVICE}/0/query", params={"where": f"HDENS_ID='{hid}'", "outFields": "*", "outSR": 3035,
                                                        "returnGeometry": "true", "f": "geojson"}, timeout=120, headers=HEADERS)
        r.raise_for_status()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
    j = json.loads(p.read_text(encoding="utf-8"))
    f = j["features"][0]
    return shapely.geometry.shape(f["geometry"]), f["properties"]


def cell_centres(hid: str) -> np.ndarray:
    """Centres of the 200 m cells (snapped to the 1 km grid) whose centre lies in the urban centre."""
    import shapely
    g, _ = uc_polygon(hid)
    x0, y0, x1, y1 = g.bounds
    xs = np.arange(np.floor(x0 / 1000) * 1000 + CELL / 2, x1, CELL)
    ys = np.arange(np.floor(y0 / 1000) * 1000 + CELL / 2, y1, CELL)
    X, Y = np.meshgrid(xs, ys)
    X, Y = X.ravel(), Y.ravel()
    ins = shapely.contains_xy(g, X, Y)
    return np.c_[X[ins], Y[ins]]


def identify(x: float, y: float) -> dict:
    p = {"geometry": f"{x:.0f},{y:.0f}", "geometryType": "esriGeometryPoint", "sr": 3035,
         "layers": "all:" + ",".join(str(k) for k in LAYERS), "tolerance": 0,
         "mapExtent": f"{x - 2000:.0f},{y - 2000:.0f},{x + 2000:.0f},{y + 2000:.0f}", "imageDisplay": "400,400,96",
         "returnGeometry": "false", "f": "json"}
    for attempt in range(5):
        try:
            r = requests.get(f"{SERVICE}/identify", params=p, timeout=60, headers=HEADERS)
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise RuntimeError(j["error"])
            row = {"x": x, "y": y}
            for res in j.get("results", []):
                v = res["attributes"].get("Classify.Pixel Value", res["attributes"].get("Pixel Value"))
                try:
                    row[LAYERS[res["layerId"]]] = float(v)
                except (TypeError, ValueError):
                    row[LAYERS[res["layerId"]]] = None       # NoData
            return row
        except Exception:  # noqa: BLE001 - retried
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"identify failed at {x},{y}")


def fetch(workers: int) -> None:
    CELLDIR.mkdir(parents=True, exist_ok=True)
    src = RAWDIR / "SOURCE.json"
    if not src.exists():
        src.write_text(json.dumps({
            "downloaded_at": time.strftime("%Y-%m-%d"),
            "pdf": PDF_URL, "pdf_last_modified": "Wed, 08 Feb 2023 07:38:38 GMT (HTTP header)",
            "viewer": VIEWER, "service": SERVICE,
            "cells": "cells/<HDENS_ID>.jsonl: one MapServer identify per 200 m cell centre (EPSG:3035) in the urban centre",
            "citation": "Poelman H., Ackermans L., Assessing the performance of urban public transport using population grid data, DG REGIO",
            "licence": "European Commission; reuse authorised provided the source is acknowledged (Commission Decision 2011/833/EU)"},
            indent=1), encoding="utf-8")
    for hid in PL:
        pts = cell_centres(hid)
        path = CELLDIR / f"{hid}.jsonl"
        done = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    done.add((r["x"], r["y"]))
        todo = [(float(x), float(y)) for x, y in pts if (float(x), float(y)) not in done]
        print(f"{hid} {PL[hid]}: {len(pts)} cells, {len(todo)} to fetch", flush=True)
        t0 = time.time()
        with open(path, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for i, row in enumerate(ex.map(lambda xy: identify(*xy), todo)):
                with _lock:
                    f.write(json.dumps(row, sort_keys=True) + "\n")
                if i % 500 == 0:
                    f.flush()
                    print(f"  {i}/{len(todo)} {time.time() - t0:.0f} s", flush=True)
        print(f"{hid}: done in {time.time() - t0:.0f} s", flush=True)


def cells(hid: str) -> pd.DataFrame:
    rows = [json.loads(l) for l in (CELLDIR / f"{hid}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    df = pd.DataFrame(rows).drop_duplicates(["x", "y"]).sort_values(["y", "x"]).reset_index(drop=True)
    return df


def city_values() -> pd.DataFrame:
    out = []
    for hid, agg in PL.items():
        if not (CELLDIR / f"{hid}.jsonl").exists():
            continue
        n_exp = len(cell_centres(hid))
        df = cells(hid)
        _, props = uc_polygon(hid)
        w = df["pop2018"].fillna(0).to_numpy()
        row = {"hdens_id": hid, "agglomeration": agg, "name": props.get("HDENS_NAME"), "area_km2": props.get("AREA_SQKM"),
               "pop2011_uc": props.get("POPL_2011"), "cells_expected": n_exp, "cells_fetched": len(df),
               "cells_populated": int((w > 0).sum()), "pop2018_cells": float(w.sum())}
        for c, a, p, k in ((30, "acc30", "prox8", "perf30"), (45, "acc45", "prox12", "perf45")):
            m = (w > 0) & df[k].notna() & df[a].notna() & df[p].notna()
            row[f"cells_with_value_{c}"] = int(m.sum())
            row[f"pop_with_value_{c}"] = float(w[m].sum())
            row[f"mean_of_ratios_{c}"] = float((w[m] * df.loc[m, k]).sum() / w[m].sum())
            row[f"ratio_of_means_{c}"] = float(100 * (w[m] * df.loc[m, a]).sum() / (w[m] * df.loc[m, p]).sum())
            # check: cell performance == acc / prox x 100
            row[f"max_abs_perf_check_{c}"] = float(np.abs(100 * df.loc[m, a] / df.loc[m, p] - df.loc[m, k]).max())
            ws = f"walkshare{c}"
            mm = m & df[ws].notna()
            row[f"walk_share_{c}"] = float((w[mm] * df.loc[mm, a] * df.loc[mm, ws]).sum() / (w[mm] * df.loc[mm, a]).sum())
        out.append(row)
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "summary"])
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.workers)
    else:
        v = city_values()
        OUT.mkdir(parents=True, exist_ok=True)
        v.to_csv(OUT / "eu_city_values.csv", index=False, lineterminator="\n", float_format="%.6g")
        print(v.T.to_string())


if __name__ == "__main__":
    main()
