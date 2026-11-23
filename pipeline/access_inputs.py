"""Inputs of the accessibility step (phase 3, brief §4.6) that need no JVM.

* origins / destinations: 250 m cells of ``data/interim/popgrid/cells_<agg>.parquet`` (populated on either grid,
  centre in FUA + 15 km).  Origins = cells with centre in the FUA.  Destinations = all those cells, plus 250 m
  cells that hold jobs (Goliszek dataset) but no population, so that jobs in industrial areas are not lost.
  Destination weights: census-scaled population, raw GHSL population, jobs, census-scaled population of cells in
  the city proper (``censuscore``, used only to mimic DG REGIO's urban-centre-only domain in the benchmark).
* jobs: Goliszek (2026) 100 m Mollweide cells (some multipart, some partial) stored in a planar CRS identical to
  EPSG:2180 (ESRI:102173 "ETRS_1989_UWPP_1992"), allocated to the 250 m EPSG:2180 grid in proportion to the
  intersected area, so totals are preserved exactly (up to floating point).  Cities proper only; no GZM; in
  Trójmiasto only Gdańsk.
* proximity: population (and jobs) within a straight-line radius of each origin cell centre, by FFT convolution
  on the 250 m grid.  Cell centres lie on the grid, so a disc of cell offsets (i, j) with
  250 * hypot(i, j) <= r is exact; the FFT adds only round-off (results rounded to 1e-3).
* coverage mask: ``results/layers/frequent_cells.parquet`` (``in_mask_<feed variant>`` per populated FUA cell),
  i.e. exactly the phase-2 mask of ``pipeline.frequent`` (the polygons in ``gtfs_coverage_mask.parquet`` are its
  dissolved form).
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from pipeline.boundaries import load_agglomeration
from pipeline.common import INTERIM, RAW, RESULTS, load_config

CELL = 250.0
ACCESS_INT = INTERIM / "access"
JOBS_GPKG = RAW / "jobs" / "Jobs_2025_7_Cities.gpkg"
JOBS_250 = ACCESS_INT / "jobs250.parquet"
JOBS_VERSION = "1"
# dataset city -> agglomeration (Szczecin is not a phase-1 agglomeration; GZM is not in the dataset)
JOBS_CITY = {"Warsaw": "warszawa", "Krakow": "krakow", "Wroclaw": "wroclaw", "Poznan": "poznan", "Lodz": "lodz",
             "Gdansk": "trojmiasto"}
JOBS_AGGS = set(JOBS_CITY.values())
WEIGHTS = ["census", "raw", "jobs", "censuscore"]
CUTOFFS = list(range(5, 61, 5))          # minutes; per-origin sums are stored at each of these
SPEEDS = {"walk": 5.0, "fast": 15.0}     # km/h: proximity radius = speed x cutoff (brief: 2.5 / 7.5 / 11.25 km)
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


def radius_m(speed: str, cutoff: int) -> float:
    return SPEEDS[speed] * 1000.0 * cutoff / 60.0


# ------------------------------------------------------------------ jobs
def build_jobs250(force: bool = False) -> pd.DataFrame:
    """Rasterise the Goliszek jobs to 250 m EPSG:2180 cells (area-proportional); cached in data/interim/access."""
    if JOBS_250.exists() and not force:
        j = pd.read_parquet(JOBS_250)
        if j.attrs.get("version", JOBS_VERSION) == JOBS_VERSION:
            return j
    import geopandas as gpd
    g = gpd.read_file(JOBS_GPKG)
    g["geometry"] = g.geometry.force_2d()
    g = g[g["Name_ALL"].isin(JOBS_CITY)].reset_index(drop=True)
    geoms = g.geometry.values
    area = shapely.area(geoms)
    b = shapely.bounds(geoms)
    i0 = np.floor(b[:, 0] / CELL).astype(np.int64)
    i1 = np.floor((b[:, 2] - 1e-6) / CELL).astype(np.int64)
    j0 = np.floor(b[:, 1] / CELL).astype(np.int64)
    j1 = np.floor((b[:, 3] - 1e-6) / CELL).astype(np.int64)
    rows_p, rows_i, rows_j = [], [], []
    for di in range(int((i1 - i0).max()) + 1):
        for dj in range(int((j1 - j0).max()) + 1):
            m = (i0 + di <= i1) & (j0 + dj <= j1)
            p = np.flatnonzero(m)
            rows_p.append(p)
            rows_i.append(i0[p] + di)
            rows_j.append(j0[p] + dj)
    p = np.concatenate(rows_p)
    ii = np.concatenate(rows_i)
    jj = np.concatenate(rows_j)
    sq = shapely.box(ii * CELL, jj * CELL, (ii + 1) * CELL, (jj + 1) * CELL)
    inter = shapely.area(shapely.intersection(geoms[p], sq))
    share = inter / area[p]
    val = g["Jobs_25"].to_numpy()[p] * share
    d = pd.DataFrame({"city": g["Name_ALL"].to_numpy()[p], "i": ii, "j": jj, "jobs": val})
    d = d[d["jobs"] > 0].groupby(["city", "i", "j"], sort=True)["jobs"].sum().reset_index()
    d["x"] = (d["i"] + 0.5) * CELL
    d["y"] = (d["j"] + 0.5) * CELL
    d["cell_id"] = "E" + (d["i"] * 250).astype(str) + "N" + (d["j"] * 250).astype(str)
    d["agglomeration"] = d["city"].map(JOBS_CITY)
    tot_src = g.groupby("Name_ALL")["Jobs_25"].sum()
    tot_out = d.groupby("city")["jobs"].sum()
    check = {c: {"source": float(tot_src[c]), "raster": float(tot_out.get(c, 0.0))} for c in sorted(JOBS_CITY)}
    d = d[["agglomeration", "city", "cell_id", "x", "y", "jobs"]].sort_values(["agglomeration", "cell_id"]).reset_index(drop=True)
    ACCESS_INT.mkdir(parents=True, exist_ok=True)
    tmp = JOBS_250.with_suffix(".tmp.parquet")
    d.to_parquet(tmp, index=False)
    tmp.replace(JOBS_250)
    (ACCESS_INT / "jobs250_check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
    return d


# ------------------------------------------------------------------ cells
@lru_cache(maxsize=None)
def destinations(agg: str) -> pd.DataFrame:
    """Destination cells (sorted by cell_id) with weights w_census, w_raw, w_jobs, w_censuscore and in_fua/in_core."""
    c = pd.read_parquet(INTERIM / "popgrid" / f"cells_{agg}.parquet")
    c = c[["cell_id", "x", "y", "pop_ghsl_census_scaled", "pop_ghsl_raw", "in_fua", "in_core"]].copy()
    c["jobs"] = 0.0
    if agg in JOBS_AGGS:
        j = build_jobs250()
        j = j[j["agglomeration"] == agg]
        reg = load_agglomeration(agg)["buffered"]
        j = j[shapely.contains_xy(reg, j["x"].to_numpy(), j["y"].to_numpy())]
        jm = j.set_index("cell_id")["jobs"]
        c["jobs"] = c["cell_id"].map(jm).fillna(0.0).to_numpy()
        extra = j[~j["cell_id"].isin(set(c["cell_id"]))]
        if len(extra):
            a = load_agglomeration(agg)
            e = pd.DataFrame({"cell_id": extra["cell_id"].to_numpy(), "x": extra["x"].to_numpy(),
                              "y": extra["y"].to_numpy(), "pop_ghsl_census_scaled": 0.0, "pop_ghsl_raw": 0.0,
                              "in_fua": shapely.contains_xy(a["fua"], extra["x"].to_numpy(), extra["y"].to_numpy()),
                              "in_core": shapely.contains_xy(a["core"], extra["x"].to_numpy(), extra["y"].to_numpy()),
                              "jobs": extra["jobs"].to_numpy()})
            c = pd.concat([c, e], ignore_index=True)
    c = c.sort_values("cell_id", kind="stable").reset_index(drop=True)
    c["w_census"] = c["pop_ghsl_census_scaled"].astype(np.float64)
    c["w_raw"] = c["pop_ghsl_raw"].astype(np.float64)
    c["w_jobs"] = c["jobs"].astype(np.float64)
    c["w_censuscore"] = np.where(c["in_core"], c["w_census"], 0.0)
    c["populated"] = (c["w_census"] > 0) | (c["w_raw"] > 0)
    return c


@lru_cache(maxsize=None)
def origins(agg: str) -> pd.DataFrame:
    """Origin cells: populated (either grid) cells with centre in the FUA, sorted by cell_id."""
    d = destinations(agg)
    o = d[d["in_fua"] & d["populated"]].reset_index(drop=True)
    lon, lat = TO4326.transform(o["x"].to_numpy(), o["y"].to_numpy())
    o["lon"], o["lat"] = lon, lat
    return o


def frame_hash(df: pd.DataFrame, cols: list[str]) -> str:
    h = hashlib.sha1()
    for col in cols:
        v = df[col].to_numpy()
        h.update(col.encode())
        h.update(np.ascontiguousarray(v.astype(str) if v.dtype == object or v.dtype.kind in "OUT" else v).tobytes())
    return h.hexdigest()[:16]


def inputs_hash(agg: str) -> str:
    """Hash of the origin and destination sets and destination weights (part of every unit signature)."""
    d = destinations(agg)
    return frame_hash(d, ["cell_id", "x", "y", "w_census", "w_raw", "w_jobs", "w_censuscore", "in_fua", "populated"])


# ------------------------------------------------------------------ proximity
def _disc(r_cells: float) -> np.ndarray:
    n = int(np.floor(r_cells + 1e-9))
    i = np.arange(-n, n + 1)
    return (i[:, None] ** 2 + i[None, :] ** 2 <= r_cells ** 2 + 1e-9).astype(np.float64)


@lru_cache(maxsize=None)
def proximity(agg: str) -> pd.DataFrame:
    """Per origin cell: destination weight within radius speed x cutoff, for both speeds, all cutoffs and weights.
    Columns prox_<weight>_<speed>_<cutoff>.  Cached in data/interim/access/<agg>/proximity.parquet."""
    from scipy.signal import fftconvolve
    sig = inputs_hash(agg) + "|prox1"
    path = ACCESS_INT / agg / "proximity.parquet"
    if path.exists():
        p = pd.read_parquet(path)
        if (path.with_suffix(".sig")).exists() and path.with_suffix(".sig").read_text() == sig:
            return p
    d = destinations(agg)
    o = origins(agg)
    i = np.round((d["x"].to_numpy() - CELL / 2) / CELL).astype(np.int64)
    j = np.round((d["y"].to_numpy() - CELL / 2) / CELL).astype(np.int64)
    i0, j0 = i.min(), j.min()
    shape = (int(i.max() - i0 + 1), int(j.max() - j0 + 1))
    oi = np.round((o["x"].to_numpy() - CELL / 2) / CELL).astype(np.int64) - i0
    oj = np.round((o["y"].to_numpy() - CELL / 2) / CELL).astype(np.int64) - j0
    out = {"cell_id": o["cell_id"].to_numpy()}
    for w in WEIGHTS:
        grid = np.zeros(shape)
        np.add.at(grid, (i - i0, j - j0), d[f"w_{w}"].to_numpy())
        for sp in SPEEDS:
            for c in CUTOFFS:
                k = _disc(radius_m(sp, c) / CELL)
                conv = fftconvolve(grid, k, mode="same")
                out[f"prox_{w}_{sp}_{c}"] = np.round(np.maximum(conv[oi, oj], 0.0), 3)
    p = pd.DataFrame(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.parquet")
    p.to_parquet(tmp, index=False)
    tmp.replace(path)
    path.with_suffix(".sig").write_text(sig)
    return p


# ------------------------------------------------------------------ mask, centres
@lru_cache(maxsize=None)
def mask(agg: str) -> pd.DataFrame:
    """Phase-2 GTFS coverage mask per populated FUA cell: cell_id, in_mask_official, in_mask_all."""
    f = pd.read_parquet(RESULTS / "layers" / "frequent_cells.parquet",
                        columns=["agglomeration", "cell_id", "in_mask_official", "in_mask_all"])
    return f[f["agglomeration"] == agg].drop(columns="agglomeration").reset_index(drop=True)


def mask_variant(network: str) -> str:
    """Which phase-2 mask applies to a network variant.  A future common-ticket network ('fare_*') is a subset of
    the official feeds, so it takes the official mask."""
    return "all" if network == "all" else "official"


def centres(agg: str) -> list[dict]:
    """Centre, hub and (polycentric agglomerations) extra centres, with EPSG:2180 coordinates and a slug."""
    import re
    import unicodedata
    a = load_config()["agglomerations"][agg]
    pts = [("centre", a["centre"])]
    if "hub" in a and (a["hub"]["lon"], a["hub"]["lat"]) != (a["centre"]["lon"], a["centre"]["lat"]):
        pts.append(("hub", a["hub"]))
    for e in a.get("extra_centres", []) if a.get("polycentric") else []:
        pts.append(("extra", e))
    out = []
    for kind, p in pts:
        x, y = TO2180.transform(p["lon"], p["lat"])
        s = unicodedata.normalize("NFKD", p["name"]).encode("ascii", "ignore").decode().lower()
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        dom = {"centre": "centre_1km", "hub": "hub_1km"}.get(kind, f"centre_1km_{s}")
        out.append({"kind": kind, "name": p["name"], "lon": p["lon"], "lat": p["lat"], "x": x, "y": y, "domain": dom})
    return out
