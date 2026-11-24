"""Phase 1, density measures (brief §4.1-4.4) for every agglomeration, FUA and core.

Outputs
* results/metrics/metrics_density.csv + .json long format, 4 significant digits, sorted
* results/charts/pwdens.json, profile_cumulative_monocentric.json, profile_cumulative_polycentric.json
* data/interim/density/<agg>.npz + <agg>.json  arrays and tables for the QA plots (pipeline.density_qa)
* data/interim/density/ghsl_on_census_1km.tif  GHSL 2020 summed into the census 1 km LAEA cells
* data/interim/density/poland_mask_100m_moll.tif

Rules made precise (described in Polish in results/qa/density/density.md)
* Census grid: a 1 km cell belongs to a domain when its centroid (EPSG:2180) is inside the
  polygon (phase-0 rule).  Cell density = RES / the cell's own area in EPSG:3035 (equal-area,
  the grid's native CRS): exactly 1 km2 for whole cells, less for cells clipped by the national
  border / coast.  Checked against (a) nominal 1 km2 for every cell and (b) area-weighted
  assignment of cells cut by the domain boundary.
* GHSL 250 m: data/interim/grid250 (pipeline.grid250), cell centre in polygon, density =
  pop / 0.0625 km2 (nominal EPSG:2180 cell area; the TM scale factor changes true area by
  < 0.3 %).
* Gross density: census population (centroid rule) / polygon area in EPSG:3035.
* Profile: GHS-POP 100 m Mollweide cells (true area 0.01 km2), distance from the cell centre to
  the centre in EPSG:2180, rings [k, k+1) km.  Variant (i) "fua": cells with centre in the FUA,
  share of the FUA total (GHSL), rings until the farthest FUA cell, so the last value is 100 %.
  Variant (ii) "free": every cell with centre in Poland (census-grid footprint), regardless of
  the FUA, out to 40 km; share of the population within 40 km.  Ring density = population /
  area of the ring's cells inside the domain (includes forests, water inside the polygon).
* Clark: OLS of ln(density) on ring mid-radius for rings [1,2) ... [24,25) km of variant (i)
  with population > 0 and >= 1 km2 of domain area; the first km is reported separately.
* Bertaud rho: built-up mask = GHS-BUILT-S 100 m cells with built share (value / 10000) >= X,
  centre inside the domain (FUA), that belong to a connected cluster reaching a seed.  Seeds:
  mask cells within 1 km of any configured centre (centre + extra_centres; the radius grows by
  1 km steps up to 5 km if none qualifies).  Connectivity: 8-neighbour after a binary dilation
  by GAP_CELLS (3) cells, i.e. gaps of up to 2 * GAP_CELLS * 100 m = 600 m of non-built cells
  (the Vistula in Warsaw, the Odra in Szczecin, rail yards) do not split the cluster; dilated
  cells themselves never enter the mask.  rho is null when the mask holds < 5 % of the domain's
  population (threshold 50 %: the mask is a few km2).  Water: no separate water layer; water cells carry ~0 m2 of built-up surface, so they
  fail every threshold.  R = sqrt(A / pi) with A = number of mask cells * 0.01 km2;
  rho = (sum p * dist / sum p) / (2/3 R), p = GHS-POP in mask cells.  Core: the same mask
  restricted to cells with centre in the core.
* Gini / eta (Volpati & Barthelemy 2018): cells = GHS-POP 100 m in a fixed domain (the rho mask
  at the working threshold; a 10 km circle around the centre, Poland only), Gini eq. (1)
  normalised by G_max = (n-1)/n (eq. 2-3); hotspots = cells above the LouBar population value
  (tangent of the Lorenz curve at F = 1); eta = mean distance between hotspots / mean distance
  between all cells (eq. 6), both estimated on a fixed random subsample (seed 0, <= 4000 cells).

Population grid of the 100 m measures (profiles, r50, Clark, rho, Gini, eta)
* Main (``population_grid`` = ``ghsl_census_scaled``): the census-rescaled grid of phase 2 at its native
  100 m resolution, i.e. GHS-POP 100 m pixels rescaled so that every NSP 2021 1 km cell sums to its census
  value (pipeline.popgrid.scale_100m; the 250 m grid data/interim/popgrid/pop_ghsl_census_scaled_250m is
  exactly this raster summed to 250 m).  Using the 100 m version keeps the 100 m built-up mask and
  distances unchanged, so the difference between the variants is the population alone.  Cached in
  data/interim/density/ghs_pop_census_scaled_100m_moll.tif (float32; delete to rebuild).
* Variant (``ghsl_raw``): raw GHS-POP 2020, as before; metric rows with tier ``qa``.
* The masks (built-up threshold, connectivity, seeds) do not depend on the population and are shared.
  Rows that exist in both variants carry ``population_grid``; every other row has it empty.

Centre sensitivity (tier ``table``): rho (FUA at the working threshold, core at 10 % and at the working
threshold) and r50 (FUA, core) with three centres: the configured one, the OSM city hall of the core
city (pipeline.density_centres) and the population-weighted centroid of the core (census-scaled 100 m).
The mask is the same for all three (seeded by the configured centres); only the distances change.

Degree of urbanisation (tier ``table``): population shares of FUA and core in urban centre / urban
cluster / rural census 1 km cells, classified on the whole census grid with the Eurostat rules
(DEGURBA level 1, simplified; see ``degurba_grid``).

Run: python -m pipeline.density
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import shutil
import time
from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer
from rasterio import features
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy import ndimage

from pipeline.boundaries import all_agglomeration_ids, load_agglomeration
from pipeline.common import INTERIM, RAW, RESULTS, load_config, round_sig, sig, write_json, write_meta

OUT = INTERIM / "density"
METRICS = RESULTS / "metrics"
CHARTS = RESULTS / "charts"
GHS_POP_VRT = RAW / "ghsl" / "ghs_pop" / "ghs_pop_2020_poland.vrt"
GHS_BUILT_VRT = RAW / "ghsl" / "ghs_built_s" / "ghs_built_s_2020_poland.vrt"
NSP_SHP = RAW / "nsp2021" / "extracted" / "GRID_NSP2021_RES.shp"
GRID250 = INTERIM / "grid250" / "ghs_pop_2020_250m_epsg2180.tif"
GHSL_1KM = OUT / "ghsl_on_census_1km.tif"
PL_MASK_100 = OUT / "poland_mask_100m_moll.tif"
SCALED_100 = OUT / "ghs_pop_census_scaled_100m_moll.tif"

INPUT_IDS = ["ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20", "ghs_built_s_2020_R3_C20",
             "ghs_built_s_2020_R4_C20", "nsp2021_grid_1km_shp", "urau_2021_100k_all", "lau_2021_01m"]

TO_MOLL = Transformer.from_crs("EPSG:2180", "ESRI:54009", always_xy=True)
MOLL_TO_2180 = Transformer.from_crs("ESRI:54009", "EPSG:2180", always_xy=True)
WGS_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
TO_3035 = Transformer.from_crs("EPSG:2180", "EPSG:3035", always_xy=True)
TO_WGS = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

PIX_KM2 = 0.01            # GHS 100 m Mollweide pixel, true area
CELL250_KM2 = 0.0625
PROFILE_MAX_KM = 40
CLARK_RINGS = (1, 25)     # rings [1,2) ... [24,25)
SEED_RADIUS_M = 1000
GAP_CELLS = 3             # dilation radius in 100 m cells: bridges gaps <= 600 m (rivers, rail yards)
GAP_SENSITIVITY = [0, 1, 2, 3, 4, 5, 7]
MIN_MASK_POP_SHARE = 0.05  # below this share of the domain's population in the mask, rho -> null
CIRCLE_KM = 10            # fixed circle for Gini / eta
ETA_SAMPLE = 4000
CENSUS_CHECK_STEPS_KM = [2, 5, 10, 15, 20, 25, 30, 35, 40]

POP_DATE_NSP = "2021-03-31"
POP_DATE_GHSL = "2020"
SRC_NSP = "GUS, NSP 2021 (siatka 1 km, ludność rezydująca)"
SRC_GHSL = "JRC GHS-POP R2023A, epoka 2020 (model, nie spis)"
SRC_GHSL_BUILT = "JRC GHS-POP + GHS-BUILT-S R2023A, epoka 2020 (model)"
GRID_NSP = "siatka spisowa 1 km (EU LAEA)"
GRID_250 = "GHSL 250 m (EPSG:2180)"
GRID_100 = "GHSL 100 m (Mollweide)"

POLY_FLAG = ("Aglomeracja policentryczna/liniowa: miara względem jednego centrum wymaga zastrzeżenia "
             "(brief §11); nie do zestawień jednopanelowych.")

# population grid variants of the 100 m measures; MAIN goes into the existing keys of the result dict
MAIN, RAWV = "ghsl_census_scaled", "ghsl_raw"
VARIANTS = (MAIN, RAWV)
POP_DATE_SCALED = "2021-03-31 (NSP 2021, wzór GHSL 2020)"
SRC_SCALED = "GUS NSP 2021 (siatka 1 km) rozłożony wzorem JRC GHS-POP R2023A 2020"
SRC_SCALED_BUILT = SRC_SCALED + "; maska JRC GHS-BUILT-S R2023A 2020"
GRID_100S = "GHSL 100 m (Mollweide) przeskalowany do NSP 2021 (komórki 1 km)"
RAW_FLAG = ("Wariant kontrolny: surowy GHS-POP 2020 (przed przeskalowaniem do NSP 2021); wynik główny w wierszu "
            "population_grid = ghsl_census_scaled.")
VARIANT_META = {MAIN: (GRID_100S, SRC_SCALED, SRC_SCALED_BUILT, POP_DATE_SCALED),
                RAWV: (GRID_100, SRC_GHSL, SRC_GHSL_BUILT, POP_DATE_GHSL)}
CENTRE_KINDS = ("config", "townhall", "popcentroid")
CENTRE_LABEL = {"config": "centrum z config.yaml", "townhall": "ratusz miasta rdzenia (OSM)",
                "popcentroid": "środek ciężkości ludności rdzenia"}
BERTAUD_THR = 0.1                 # built-up threshold closest to Bertaud & Malpezzi's built-up area (core)
# DEGURBA level 1 on the census 1 km grid (Eurostat manual 2021, simplified)
DEGURBA_UC_DENS, DEGURBA_UC_POP = 1500, 50000
DEGURBA_CL_DENS, DEGURBA_CL_POP = 300, 5000
DEGURBA_LABEL = {"urban_centre": "centrum miejskie", "urban_cluster": "skupisko miejskie (poza centrum)",
                 "rural": "obszar wiejski (komórki wiejskie)"}


# ------------------------------------------------------------------ shared data

@lru_cache(maxsize=1)
def census() -> gpd.GeoDataFrame:
    g = gpd.read_file(NSP_SHP, columns=["CODE", "RES"]).to_crs("EPSG:2180")
    area = g.geometry.to_crs("EPSG:3035").area.values / 1e6
    c = g.geometry.centroid
    out = gpd.GeoDataFrame({"CODE": g.CODE.values, "RES": g.RES.values.astype(np.int64),
                            "area_km2": area, "px": c.x.values, "py": c.y.values},
                           geometry=g.geometry.values, crs="EPSG:2180")
    out["clipped"] = out.area_km2 < 0.9999
    out["E"] = out.CODE.str.extract(r"E(\d+)$")[0].astype(np.int64)
    out["N"] = out.CODE.str.extract(r"N(\d+)E")[0].astype(np.int64)
    return out


@lru_cache(maxsize=1)
def census_points() -> gpd.GeoSeries:
    c = census()
    return gpd.GeoSeries(gpd.points_from_xy(c.px, c.py), crs="EPSG:2180")


def census_in(geom) -> np.ndarray:
    """Indices of census cells whose centroid is inside ``geom`` (sorted)."""
    return np.sort(census_points().sindex.query(geom, predicate="contains"))


@lru_cache(maxsize=1)
def ghs():
    """(pop float64 with nodata -> nan, built uint16, transform, crs)."""
    with rasterio.open(GHS_POP_VRT) as s:
        pop = s.read(1)
        tr, crs, nd = s.transform, s.crs, s.nodata
    with rasterio.open(GHS_BUILT_VRT) as s:
        built = s.read(1)
        assert s.transform == tr
    pop = np.where(pop == nd, np.nan, pop)
    return pop, built, tr, crs


def poland_mask_100() -> np.ndarray:
    if PL_MASK_100.exists():
        with rasterio.open(PL_MASK_100) as s:
            return s.read(1)
    pop, _, tr, crs = ghs()
    g = census().geometry.to_crs("ESRI:54009")
    m = features.rasterize(((geom, 1) for geom in g.values), out_shape=pop.shape, transform=tr,
                           fill=0, all_touched=False, dtype="uint8")
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(PL_MASK_100, "w", driver="GTiff", height=m.shape[0], width=m.shape[1], count=1,
                       dtype="uint8", crs=crs, transform=tr, compress="deflate", tiled=True) as d:
        d.write(m, 1)
    return m


def ghsl_on_census() -> np.ndarray:
    """GHSL 2020 population summed into each census cell (LAEA 1 km, exact transformer).

    Returns an array aligned with ``census()`` rows.  Clipped census cells receive the GHSL
    population of the whole 1 km square (which may include foreign population)."""
    c = census()
    e0, e1 = int(c.E.min()), int(c.E.max()) + 1000
    n0, n1 = int(c.N.min()), int(c.N.max()) + 1000
    tr = from_origin(e0, n1, 1000, 1000)
    w, h = (e1 - e0) // 1000, (n1 - n0) // 1000
    if not GHSL_1KM.exists():
        pop, _, s_tr, s_crs = ghs()
        src = np.where(np.isnan(pop), -200.0, pop)
        dst = np.full((h, w), -1.0)
        reproject(src, dst, src_transform=s_tr, src_crs=s_crs, src_nodata=-200.0, dst_transform=tr,
                  dst_crs="EPSG:3035", dst_nodata=-1.0, resampling=Resampling.sum, tolerance=0.0)
        OUT.mkdir(parents=True, exist_ok=True)
        with rasterio.open(GHSL_1KM, "w", driver="GTiff", height=h, width=w, count=1, dtype="float64",
                           crs="EPSG:3035", transform=tr, nodata=-1.0, compress="deflate", predictor=3) as d:
            d.write(dst, 1)
    with rasterio.open(GHSL_1KM) as s:
        arr = s.read(1)
    arr = np.where(arr < 0, 0.0, arr)
    rows = ((n1 - 1000 - c.N.values) // 1000).astype(int)
    cols = ((c.E.values - e0) // 1000).astype(int)
    return arr[rows, cols]


def build_scaled_100() -> None:
    """Census-scaled GHS-POP 100 m (pipeline.popgrid.scale_100m) cached as float32 on the GHSL grid."""
    if SCALED_100.exists():
        return
    from pipeline.popgrid import scale_100m
    scaled, _, tr, crs, _, _ = scale_100m()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = SCALED_100.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", driver="GTiff", height=scaled.shape[0], width=scaled.shape[1], count=1,
                       dtype="float32", crs=crs, transform=tr, nodata=-200.0, compress="deflate", predictor=3,
                       tiled=True, blockxsize=512, blockysize=512) as d:
        d.write(scaled.astype("float32"), 1)
        d.update_tags(source="GHS-POP R2023A E2020 100 m rescaled to NSP 2021 1 km cells (pipeline.popgrid.scale_100m)")
    tmp.replace(SCALED_100)


@lru_cache(maxsize=1)
def ghs_scaled() -> np.ndarray:
    """Census-scaled population on the GHSL 100 m grid (float32, nodata -> 0)."""
    build_scaled_100()
    with rasterio.open(SCALED_100) as s:
        a = s.read(1)
        assert s.transform == ghs()[2]
    a[a < 0] = 0.0
    return a


@lru_cache(maxsize=1)
def grid250():
    with rasterio.open(GRID250) as s:
        a = s.read(1).astype(np.float64)
        tr = s.transform
    return np.where(a < 0, 0.0, a), tr


def centres(agg: str) -> list[dict]:
    a = load_config()["agglomerations"][agg]
    out = []
    for c in [a["centre"], *(a.get("extra_centres") or [])]:
        x, y = WGS_TO_2180.transform(c["lon"], c["lat"])
        out.append({"name": c["name"], "x": x, "y": y})
    return out


def reproj(geom, T: Transformer):
    """Reproject a shapely geometry with a pyproj Transformer (vectorised)."""
    return shapely.transform(geom, lambda xy: np.column_stack(T.transform(xy[:, 0], xy[:, 1])))


def area_km2(geom) -> float:
    return float(reproj(shapely.segmentize(geom, 500), TO_3035).area / 1e6)


# ------------------------------------------------------------------ Mollweide window per agglomeration

class Window:
    """100 m Mollweide window around an agglomeration with domain masks and 2180 coordinates."""

    def __init__(self, agg: str, a: dict, cs: list[dict]):
        pop, built, tr, _ = ghs()
        geoms = [a["buffered"]] + [shapely.Point(c["x"], c["y"]).buffer((PROFILE_MAX_KM + 2) * 1000) for c in cs]
        u = shapely.union_all(geoms)
        g = reproj(shapely.segmentize(shapely.box(*u.bounds), 1000), TO_MOLL)
        b = g.bounds
        c0 = int(math.floor((b[0] - tr.c) / tr.a)) - 2
        r0 = int(math.floor((tr.f - b[3]) / -tr.e)) - 2
        c1 = int(math.ceil((b[2] - tr.c) / tr.a)) + 2
        r1 = int(math.ceil((tr.f - b[1]) / -tr.e)) + 2
        r0, c0 = max(r0, 0), max(c0, 0)
        r1, c1 = min(r1, pop.shape[0]), min(c1, pop.shape[1])
        self.sl = (slice(r0, r1), slice(c0, c1))
        self.tr = rasterio.Affine(tr.a, 0, tr.c + c0 * tr.a, 0, tr.e, tr.f + r0 * tr.e)
        self.pop = pop[self.sl]
        self.built = built[self.sl]
        self.shape = self.pop.shape
        rows, cols = np.mgrid[0:self.shape[0], 0:self.shape[1]]
        X = self.tr.c + (cols + 0.5) * self.tr.a
        Y = self.tr.f + (rows + 0.5) * self.tr.e
        x, y = MOLL_TO_2180.transform(X.ravel(), Y.ravel())
        self.x = x.reshape(self.shape)
        self.y = y.reshape(self.shape)
        self.poland = poland_mask_100()[self.sl] == 1
        self.popz = np.nan_to_num(self.pop, nan=0.0)
        self.valid = ~np.isnan(self.pop)
        self.pops = ghs_scaled()[self.sl].astype(np.float64)
        # people the rescaling placed on pixels without GHSL data (left out by the domain masks)
        self.scaled_on_invalid = float(self.pops[~self.valid].sum())

    def popv(self, variant: str) -> np.ndarray:
        return self.pops if variant == MAIN else self.popz

    def mask(self, geom) -> np.ndarray:
        g = reproj(shapely.segmentize(geom, 250), TO_MOLL)
        return features.geometry_mask([g], out_shape=self.shape, transform=self.tr, invert=True,
                                      all_touched=False)

    def dist(self, cs: list[dict]) -> np.ndarray:
        """Distance (m, EPSG:2180) to the nearest of the given centres."""
        d = None
        for c in cs:
            dd = np.hypot(self.x - c["x"], self.y - c["y"])
            d = dd if d is None else np.minimum(d, dd)
        return d


# ------------------------------------------------------------------ §4.1

def pwdens(p: np.ndarray, d: np.ndarray, w: np.ndarray | None = None) -> float:
    p = p.astype(np.float64)
    if w is not None:
        p = p * w
    s = p.sum()
    return float((p * d).sum() / s) if s > 0 else float("nan")


def pwdens_census(geom) -> dict:
    c = census()
    idx = census_in(geom)
    sub = c.iloc[idx]
    p = sub.RES.values
    main = pwdens(p, p / sub.area_km2.values)
    nominal = pwdens(p, p / 1.0)
    # area-weighted assignment: cells intersecting the polygon, weight = share of cell area inside
    cand = np.sort(c.sindex.query(geom, predicate="intersects"))
    cc = c.iloc[cand]
    inter = shapely.intersection(cc.geometry.values, geom)
    frac = shapely.area(inter) / shapely.area(cc.geometry.values)
    pw = cc.RES.values.astype(float)
    aw = pwdens(pw, pw / cc.area_km2.values, frac)
    ghsl_cells = ghsl_on_census()[idx]
    return {"pop": int(p.sum()), "pwdens": main, "pwdens_nominal": nominal, "pwdens_area_weighted": aw,
            "pop_area_weighted": float((pw * frac).sum()),
            "cells": int(len(idx)), "cells_populated": int((p > 0).sum()),
            "clipped_cells": int(sub.clipped.sum()), "clipped_pop": int(sub.RES.values[sub.clipped.values].sum()),
            "boundary_cells": int(((frac > 0) & (frac < 0.999)).sum()),
            "pwdens_ghsl_1km": pwdens(ghsl_cells, ghsl_cells / 1.0),
            "ghsl_1km_pop": float(ghsl_cells.sum())}


def pwdens_250(geom) -> dict:
    a, tr = grid250()
    b = geom.bounds
    c0 = int((b[0] - tr.c) // 250); c1 = int(-(-(b[2] - tr.c) // 250))
    r0 = int((tr.f - b[3]) // 250); r1 = int(-(-(tr.f - b[1]) // 250))
    sub = a[r0:r1, c0:c1]
    wt = rasterio.Affine(250, 0, tr.c + c0 * 250, 0, -250, tr.f - r0 * 250)
    m = features.geometry_mask([geom], out_shape=sub.shape, transform=wt, invert=True, all_touched=False)
    p = sub[m]
    return {"pop": float(p.sum()), "pwdens": pwdens(p, p / CELL250_KM2)}


# ------------------------------------------------------------------ degree of urbanisation (census 1 km)

def degurba_grid() -> np.ndarray:
    """DEGURBA level-1 class of every census cell (rows of ``census()``): 2 urban centre, 1 urban cluster, 0 rural.

    Simplified Eurostat (2021 manual) rules on the whole national census grid, density = RES / own cell area:
    * urban centre: cells >= 1 500 /km2, 4-connected clusters with >= 50 000 inhabitants, then gap filling
      (a non-centre cell with >= 5 of its 8 neighbours in a centre joins it; repeated until stable);
      the manual's extra rule for centres whose share of built-up land is high is not applied;
    * urban cluster: cells >= 300 /km2, 8-connected clusters with >= 5 000 inhabitants, minus centre cells;
    * rural: everything else (including populated cells of small clusters).
    Cells outside Poland are absent from the census grid, so clusters at the border are truncated."""
    c = census()
    e0, n1 = int(c.E.min()), int(c.N.max())
    rows = ((n1 - c.N.values) // 1000).astype(int)
    cols = ((c.E.values - e0) // 1000).astype(int)
    shape = (rows.max() + 1, cols.max() + 1)
    pop = np.zeros(shape)
    dens = np.zeros(shape)
    pop[rows, cols] = c.RES.values
    dens[rows, cols] = c.RES.values / c.area_km2.values
    four = ndimage.generate_binary_structure(2, 1)
    eight = np.ones((3, 3), bool)

    def big_clusters(m: np.ndarray, st: np.ndarray, minpop: float) -> np.ndarray:
        lab, n = ndimage.label(m, structure=st)
        sums = ndimage.sum(pop, lab, index=np.arange(1, n + 1))
        keep = np.r_[False, sums >= minpop]
        return keep[lab]

    uc = big_clusters(dens >= DEGURBA_UC_DENS, four, DEGURBA_UC_POP)
    while True:
        nb = ndimage.convolve(uc.astype(np.int16), eight.astype(np.int16), mode="constant") - uc
        add = (~uc) & (nb >= 5)
        if not add.any():
            break
        uc = uc | add
    cl = big_clusters(dens >= DEGURBA_CL_DENS, eight, DEGURBA_CL_POP) & ~uc
    cls = np.where(uc, 2, np.where(cl, 1, 0))
    return cls[rows, cols].astype(np.int8)


def degurba_shares(geom, cls: np.ndarray) -> dict:
    idx = census_in(geom)
    p = census().RES.values[idx].astype(float)
    k = cls[idx]
    tot = p.sum()
    return {name: float(p[k == code].sum() / tot) for code, name in ((2, "urban_centre"), (1, "urban_cluster"),
                                                                       (0, "rural"))}


# ------------------------------------------------------------------ §4.2

def rings(p: np.ndarray, inhabited: np.ndarray, d_m: np.ndarray, dom: np.ndarray, rmax: int) -> pd.DataFrame:
    k = np.floor(d_m / 1000).astype(np.int64)
    sel = dom & (k < rmax)
    kk = k[sel]
    pop = np.bincount(kk, weights=p[sel], minlength=rmax)
    inh = np.bincount(kk, weights=inhabited[sel].astype(float), minlength=rmax) * PIX_KM2
    area = np.bincount(kk, minlength=rmax) * PIX_KM2
    df = pd.DataFrame({"r_in_km": np.arange(rmax), "r_out_km": np.arange(1, rmax + 1), "pop": pop,
                       "inhabited_km2": inh, "area_km2": area})
    df["density"] = np.where(df.area_km2 > 0, df["pop"] / df.area_km2.where(df.area_km2 > 0, 1), np.nan)
    df["density_inhabited"] = np.where(df.inhabited_km2 > 0, df["pop"] / df.inhabited_km2.where(df.inhabited_km2 > 0, 1), np.nan)
    df["cum_pop"] = df["pop"].cumsum()
    return df


def clark(df: pd.DataFrame) -> dict:
    lo, hi = CLARK_RINGS
    s = df[(df.r_in_km >= lo) & (df.r_out_km <= hi) & (df["pop"] > 0) & (df.area_km2 >= 1.0)]
    if len(s) < 5:
        return {"b": None, "d0": None, "r2": None, "n": int(len(s))}
    r = (s.r_in_km + 0.5).values
    y = np.log(s.density.values)
    A = np.c_[np.ones_like(r), r]
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = A @ coef
    r2 = 1 - ((y - yhat) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    first = df[df.r_in_km == 0]
    return {"b": float(-coef[1]), "d0": float(math.exp(coef[0])), "r2": float(r2), "n": int(len(s)),
            "first_km_density": float(first.density.iloc[0]) if len(first) and first.area_km2.iloc[0] > 0 else None}


def r_at_share(df: pd.DataFrame, total: float, share: float) -> float:
    cum = df.cum_pop.values / total
    i = int(np.searchsorted(cum, share))
    if i >= len(cum):
        return float("nan")
    prev = cum[i - 1] if i > 0 else 0.0
    f = (share - prev) / (cum[i] - prev) if cum[i] > prev else 0.0
    return float(df.r_in_km.iloc[i] + f)


def census_cumulative(geom, cs: list[dict], steps: list[int]) -> list[float]:
    """Cumulative share of census population within each step (km) of the centre.

    geom given: cells with centroid in geom, share of their total (variant i);
    geom None: every census cell (Poland), share of the population within the last step (ii)."""
    c = census()
    sel = np.arange(len(c)) if geom is None else census_in(geom)
    x, y, p = c.px.values[sel], c.py.values[sel], c.RES.values[sel].astype(float)
    d = None
    for cc in cs:
        dd = np.hypot(x - cc["x"], y - cc["y"])
        d = dd if d is None else np.minimum(d, dd)
    tot = p.sum() if geom is not None else p[d < steps[-1] * 1000].sum()
    return [float(p[d < s * 1000].sum() / tot) for s in steps]


# ------------------------------------------------------------------ §4.3

def disk(k: int) -> np.ndarray:
    if k <= 0:
        return np.ones((1, 1), bool)
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    return (xx ** 2 + yy ** 2) <= k * k + k   # 3x3 for k=1, rounded disk beyond


def built_mask(W: Window, dom: np.ndarray, thr: float, cs: list[dict], gap_cells: int = GAP_CELLS) -> tuple[np.ndarray, dict]:
    B = dom & (W.built != 65535) & (W.built >= thr * 10000)
    D = ndimage.binary_dilation(B, structure=disk(gap_cells)) if gap_cells > 0 else B
    lab, n = ndimage.label(D, structure=np.ones((3, 3), bool))
    dmin = W.dist(cs)
    radius = SEED_RADIUS_M
    seeds = B & (dmin <= radius)
    while not seeds.any() and radius < 5000:
        radius += 1000
        seeds = B & (dmin <= radius)
    keep = np.unique(lab[seeds])
    keep = keep[keep > 0]
    M = B & np.isin(lab, keep)
    return M, {"seed_radius_m": radius, "components_kept": int(len(keep)), "built_cells_all": int(B.sum())}


def rho(W: Window, M: np.ndarray, cs: list[dict], pop: np.ndarray) -> dict:
    n = int(M.sum())
    if n == 0:
        return {"rho": None, "mean_dist_km": None, "R_km": None, "area_km2": 0.0, "pop": 0.0}
    A = n * PIX_KM2
    R = math.sqrt(A / math.pi)
    p = pop[M]
    d = W.dist(cs)[M] / 1000
    md = float((p * d).sum() / p.sum()) if p.sum() > 0 else float("nan")
    return {"rho": md / (2 / 3 * R), "mean_dist_km": md, "R_km": R, "area_km2": A, "pop": float(p.sum())}


# ------------------------------------------------------------------ §4.4

def mean_pair_dist(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> tuple[float, int]:
    n = len(x)
    if n < 2:
        return float("nan"), n
    if n > ETA_SAMPLE:
        idx = np.sort(rng.choice(n, ETA_SAMPLE, replace=False))
        x, y = x[idx], y[idx]
    m = len(x)
    tot = 0.0
    for i0 in range(0, m, 1000):
        dx = x[i0:i0 + 1000, None] - x[None, :]
        dy = y[i0:i0 + 1000, None] - y[None, :]
        tot += np.sqrt(dx * dx + dy * dy).sum()
    return float(tot / (m * (m - 1))), m


def gini_eta(p: np.ndarray, x: np.ndarray, y: np.ndarray) -> dict:
    n = len(p)
    if n < 10 or p.sum() <= 0:
        return {"gini_norm": None, "eta": None, "n_cells": n}
    order = np.argsort(p, kind="stable")
    ps = p[order]
    i = np.arange(1, n + 1)
    G = (2 * (i * ps).sum() / (n * ps.sum())) - (n + 1) / n
    G_norm = G / ((n - 1) / n)
    # LouBar: tangent of the Lorenz curve at F = 1 has slope n * p_max / sum(p);
    # it crosses L = 0 at F* = 1 - sum(p) / (n * p_max); hotspots = cells ranked above F*.
    F_star = 1 - ps.sum() / (n * ps[-1])
    k = int(math.floor(F_star * n))
    p_lb = float(ps[min(k, n - 1)])
    hot = order[k:]
    rng = np.random.default_rng(0)
    d_all, m_all = mean_pair_dist(x, y, rng)
    d_hot, m_hot = mean_pair_dist(x[np.sort(hot)], y[np.sort(hot)], rng)
    return {"gini": float(G), "gini_norm": float(G_norm), "n_cells": n, "loubar_F": float(F_star),
            "loubar_pop_per_cell": p_lb, "loubar_density": p_lb / PIX_KM2, "n_hotspots": int(len(hot)),
            "eta": d_hot / d_all, "mean_dist_all_km": d_all / 1000, "mean_dist_hot_km": d_hot / 1000,
            "sample_all": m_all, "sample_hot": m_hot}


# ------------------------------------------------------------------ per agglomeration

def pop_measures(W: Window, p: np.ndarray, a: dict, cs: list[dict], doms: dict, masks: dict, gap_masks: dict,
                 thresholds: list[float], thr_work: float, circ: np.ndarray) -> tuple[dict, dict]:
    """Every population-dependent 100 m measure for one population array ``p`` (same window as W).

    Returns (result dict, profiles {name: {"total", "rings"}})."""
    dom_f, dom_c, dom_free = doms["fua"], doms["core"], doms["free"]
    inhabited = p > 0
    d_main = W.dist(cs[:1])
    d_near = W.dist(cs)
    out: dict = {}
    prof = {}
    for name, dom, dist in [("fua", dom_f, d_main), ("core", dom_c, d_main), ("free", dom_free, d_main),
                            ("fua_nearest", dom_f, d_near), ("free_nearest", dom_free, d_near)]:
        if name.endswith("nearest") and len(cs) < 2:
            continue
        if name in ("free", "free_nearest"):
            rmax = PROFILE_MAX_KM
            total = float(p[dom & (dist < rmax * 1000)].sum())
        else:
            rmax = max(PROFILE_MAX_KM, int(math.ceil(dist[dom].max() / 1000)))
            total = float(p[dom].sum())
        df = rings(p, inhabited, dist, dom, rmax)
        df["cum_share"] = df.cum_pop / total
        prof[name] = {"total": total, "rings": df}
    out["profile_totals"] = {k: v["total"] for k, v in prof.items()}
    out["clark"] = clark(prof["fua"]["rings"])
    out["r50"] = {k: r_at_share(v["rings"], v["total"], 0.5) for k, v in prof.items()}
    out["share_within"] = {k: {str(s): float(v["rings"].cum_share.iloc[s - 1]) for s in (5, 10, 20, 40)}
                           for k, v in prof.items()}
    # census cross-check of the cumulative curve
    cc_fua = census_cumulative(a["fua"], cs[:1], CENSUS_CHECK_STEPS_KM)
    cc_free = census_cumulative(None, cs[:1], CENSUS_CHECK_STEPS_KM)
    g_fua = [float(prof["fua"]["rings"].cum_share.iloc[s - 1]) for s in CENSUS_CHECK_STEPS_KM]
    g_free = [float(prof["free"]["rings"].cum_share.iloc[s - 1]) for s in CENSUS_CHECK_STEPS_KM]
    out["census_check"] = {"steps_km": CENSUS_CHECK_STEPS_KM, "census_fua": cc_fua, "ghsl_fua": g_fua,
                           "census_free": cc_free, "ghsl_free": g_free,
                           "max_abs_diff_pp_fua": float(np.max(np.abs(np.array(cc_fua) - g_fua)) * 100),
                           "max_abs_diff_pp_free": float(np.max(np.abs(np.array(cc_free) - g_free)) * 100)}

    # §4.3
    rr: dict = {}
    pop_fua = float(p[dom_f].sum())
    pop_core = float(p[dom_c].sum())
    for thr in thresholds:
        M, info = masks[thr]
        rf = rho(W, M, cs[:1], p)
        rc = rho(W, M & dom_c, cs[:1], p)
        rf.update(info)
        rf["pop_share"] = rf["pop"] / pop_fua
        rc["pop_share"] = rc["pop"] / pop_core
        for e in (rf, rc):
            # a near-empty mask makes rho meaningless: keep the raw number for the QA table only
            e["rho_raw"] = e["rho"]
            if e["pop_share"] < MIN_MASK_POP_SHARE:
                e["rho"] = None
        entry = {"fua": rf, "core": rc}
        if len(cs) > 1:
            entry["fua_nearest"] = rho(W, M, cs, p)
            entry["core_nearest"] = rho(W, M & dom_c, cs, p)
            # reference: N equal discs of total area A -> mean distance 2/3 * sqrt(A / (N pi))
            for k, base in (("fua_nearest", rf), ("core_nearest", rc)):
                e = entry[k]
                e["rho_raw"] = e["rho"]
                if base["rho"] is None:
                    e["rho"] = None
                if e["rho"] is not None:
                    e["rho_ndisc"] = e["mean_dist_km"] / (2 / 3 * math.sqrt(e["area_km2"] / (len(cs) * math.pi)))
        rr[str(thr)] = entry
    out["rho"] = rr
    gap = {}
    for k in GAP_SENSITIVITY:
        r = rho(W, gap_masks[k], cs[:1], p)
        gap[str(k)] = {"gap_m": 2 * k * 100, "rho": r["rho"], "area_km2": r["area_km2"], "pop_share": r["pop"] / pop_fua}
    out["rho_gap_sensitivity"] = gap

    # §4.4
    Mw = masks[thr_work][0]
    out["gini_eta"] = {
        "mask_fua": gini_eta(p[Mw], W.x[Mw], W.y[Mw]),
        "mask_core": gini_eta(p[Mw & dom_c], W.x[Mw & dom_c], W.y[Mw & dom_c]),
        "circle": gini_eta(p[circ], W.x[circ], W.y[circ]),
    }
    out["pop_100m"] = {"fua": pop_fua, "core": pop_core}
    # Bertaud & Malpezzi comparison: core mask at 10 %, people per built-up hectare
    Mt = masks[BERTAUD_THR][0] & dom_c
    pc = float(p[Mt].sum())
    at = float(Mt.sum() * PIX_KM2)
    out["bertaud_core_t10"] = {"area_km2": at, "pop": pc, "people_per_ha": pc / (at * 100) if at > 0 else None}
    return out, prof


def centre_sensitivity(W: Window, p: np.ndarray, agg: str, cs: list[dict], doms: dict, masks: dict,
                       thr_work: float) -> dict:
    """rho and r50 with the configured centre, the OSM city hall and the population centroid of the core."""
    from pipeline.density_centres import townhall
    dom_f, dom_c = doms["fua"], doms["core"]
    pc = p[dom_c]
    cx, cy = float((pc * W.x[dom_c]).sum() / pc.sum()), float((pc * W.y[dom_c]).sum() / pc.sum())
    th = townhall(agg)
    lon, lat = TO_WGS.transform(cx, cy)
    cen = {"config": {"name": cs[0]["name"], "x": cs[0]["x"], "y": cs[0]["y"]},
           "townhall": {"name": th["name"], "x": th["x"], "y": th["y"], "osm": th["osm"], "rule": th["rule"],
                        "reason": th["reason"], "lon": th["lon"], "lat": th["lat"]},
           "popcentroid": {"name": "środek ciężkości ludności rdzenia", "x": cx, "y": cy, "lon": lon, "lat": lat}}
    for c in cen.values():
        c["offset_from_config_km"] = math.hypot(c["x"] - cs[0]["x"], c["y"] - cs[0]["y"]) / 1000
    pop_f, pop_c = float(p[dom_f].sum()), float(p[dom_c].sum())
    vals = {}
    for kind, c in cen.items():
        one = [c]
        v = {}
        for key, M, tot in (("rho_fua_work", masks[thr_work][0], pop_f),
                            ("rho_core_work", masks[thr_work][0] & dom_c, pop_c),
                            ("rho_core_t10", masks[BERTAUD_THR][0] & dom_c, pop_c)):
            r = rho(W, M, one, p)
            v[key] = r["rho"] if r["pop"] / tot >= MIN_MASK_POP_SHARE else None
        d = W.dist(one)
        for name, dom in (("fua", dom_f), ("core", dom_c)):
            rmax = max(PROFILE_MAX_KM, int(math.ceil(d[dom].max() / 1000)))
            df = rings(p, p > 0, d, dom, rmax)
            v[f"r50_{name}"] = r_at_share(df, float(p[dom].sum()), 0.5)
        vals[kind] = v
    spread = {}
    for key in ("rho_fua_work", "rho_core_work", "rho_core_t10", "r50_fua", "r50_core"):
        xs = [vals[k][key] for k in CENTRE_KINDS if vals[k][key] is not None]
        spread[key] = (max(xs) - min(xs)) if len(xs) == len(CENTRE_KINDS) else None
    return {"centres": cen, "values": vals, "spread": spread, "threshold_work": thr_work}


def run_agglomeration(agg: str, thresholds: list[float], thr_work: float, degurba: np.ndarray) -> dict:
    cfg = load_config()["agglomerations"][agg]
    a = load_agglomeration(agg)
    cs = centres(agg)
    poly = bool(cfg.get("polycentric"))
    res: dict = {"id": agg, "name": a["name"], "phase": a["phase"], "polycentric": poly, "centres": cs}

    # §4.1
    for dom in ("fua", "core"):
        g = a[dom]
        pc = pwdens_census(g)
        p250 = pwdens_250(g)
        ar = area_km2(g)
        res[dom] = {"area_km2": ar, "census": pc, "ghsl250": p250, "gross_density": pc["pop"] / ar,
                    "degurba": degurba_shares(g, degurba)}

    W = Window(agg, a, cs)
    doms = {"fua": W.mask(a["fua"]) & W.valid, "core": W.mask(a["core"]) & W.valid, "free": W.poland & W.valid}
    dom_f = doms["fua"]
    d_main = W.dist(cs[:1])
    circ = (d_main <= CIRCLE_KM * 1000) & W.poland & W.valid
    # masks do not depend on the population: computed once, shared by both variants
    masks = {thr: built_mask(W, dom_f, thr, cs) for thr in sorted(set(thresholds) | {BERTAUD_THR})}
    gap_masks = {k: built_mask(W, dom_f, thr_work, cs, gap_cells=k)[0] for k in GAP_SENSITIVITY}
    meas, profs = {}, {}
    for v in VARIANTS:
        meas[v], profs[v] = pop_measures(W, W.popv(v), a, cs, doms, masks, gap_masks, thresholds, thr_work, circ)
    res.update(meas[MAIN])
    res["raw"] = meas[RAWV]
    res["population_grid"] = MAIN
    res["ghsl_100m_pop"] = meas[RAWV]["pop_100m"]
    res["scaled_on_nodata_pixels"] = W.scaled_on_invalid
    # truncation: the same cluster rule on FUA + 15 km; share of the cluster outside the FUA
    dom_b = W.mask(a["buffered"]) & W.valid
    Mb, _ = built_mask(W, dom_b, thr_work, cs)
    res["rho_truncation"] = {"threshold": thr_work, "cluster_area_buffer_km2": float(Mb.sum() * PIX_KM2),
                             "cluster_area_outside_fua_km2": float((Mb & ~dom_f).sum() * PIX_KM2),
                             "share_outside_fua": float((Mb & ~dom_f).sum() / max(Mb.sum(), 1))}
    res["centre_sensitivity"] = centre_sensitivity(W, W.popv(MAIN), agg, cs, doms, masks, thr_work)

    # arrays for QA plots
    OUT.mkdir(parents=True, exist_ok=True)
    Mw = masks[thr_work][0]
    np.savez_compressed(OUT / f"{agg}.npz", mask=Mw, dom_f=dom_f, dom_c=doms["core"],
                        pop=W.pops.astype(np.float32), pop_raw=W.popz.astype(np.float32),
                        x0=W.x[0, 0], y0=W.y[0, 0], tr=np.array(W.tr)[:6], built=W.built, circle=circ)
    for v, suffix in ((MAIN, ""), (RAWV, "_raw")):
        for k, pr in profs[v].items():
            pr["rings"].to_csv(OUT / f"{agg}_profile_{k}{suffix}.csv", index=False, lineterminator="\n",
                               float_format="%.6g")
    res["profiles"] = {k: v["rings"].to_dict(orient="list") for k, v in profs[MAIN].items()}
    return res


# ------------------------------------------------------------------ metrics and charts

def metric_rows(r: dict, thresholds: list[float], thr_work: float) -> list[dict]:
    rows = []
    agg, poly = r["id"], r["polycentric"]

    def add(domain, metric, label, value, unit, grid, source, pop_date, tier, flag="", pop_grid=None):
        if value is not None and isinstance(value, float) and math.isnan(value):
            value = None
        if poly and metric.startswith(("rho", "clark", "profile", "density_first_km")) and "nearest" not in metric:
            flag = (flag + " " if flag else "") + POLY_FLAG
        if pop_grid == RAWV:
            flag = RAW_FLAG + (" " + flag if flag else "")
            tier = "qa"
        rows.append({"agglomeration": agg, "domain": domain, "metric": metric, "label": label,
                     "value": sig(value) if value is not None else None, "unit": unit, "grid": grid,
                     "source": source, "population_date": pop_date, "timetable_date": None,
                     "coverage_share": None, "flag": flag, "tier": tier, "population_grid": pop_grid})

    def vres(v):
        return r if v == MAIN else r["raw"]

    def popname(v):
        return "NSP 2021 rozłożony wzorem GHSL" if v == MAIN else "GHSL"

    for dom in ("fua", "core"):
        d = r[dom]
        c = d["census"]
        add(dom, "population_census", "Ludność (NSP 2021, komórki 1 km o środku w obszarze)", float(c["pop"]), "os.",
            GRID_NSP, SRC_NSP, POP_DATE_NSP, "table")
        add(dom, "area", "Powierzchnia obszaru", d["area_km2"], "km²", "granica URAU 2021 (EPSG:3035)",
            "Eurostat GISCO URAU 2021", None, "table")
        add(dom, "density_gross", "Gęstość brutto (ludność / powierzchnia obszaru)", d["gross_density"], "os./km²",
            GRID_NSP, SRC_NSP, POP_DATE_NSP, "table",
            "Zależy od rysunku granicy; tylko dla kontrastu z gęstością ważoną populacją.")
        add(dom, "pwdens_census_1km", "Gęstość ważona populacją (siatka spisowa 1 km)", c["pwdens"], "os./km²",
            GRID_NSP, SRC_NSP, POP_DATE_NSP, "main", "Nie porównywać z wartościami z innych siatek (MAUP).")
        add(dom, "pwdens_ghsl_250m", "Gęstość ważona populacją (GHSL 250 m, dane modelowane)", d["ghsl250"]["pwdens"],
            "os./km²", GRID_250, SRC_GHSL, POP_DATE_GHSL, "table",
            "Inna siatka niż wynik główny (1 km): liczby nieporównywalne z PWD 1 km.")
        add(dom, "pwdens_ghsl_1km", "PWD z GHSL zsumowanego do komórek spisowych 1 km (kontrola źródła)",
            c["pwdens_ghsl_1km"], "os./km²", GRID_NSP, SRC_GHSL, POP_DATE_GHSL, "qa")
        add(dom, "pwdens_census_1km_nominal_area", "PWD 1 km, wariant: pole nominalne 1 km² dla każdej komórki",
            c["pwdens_nominal"], "os./km²", GRID_NSP, SRC_NSP, POP_DATE_NSP, "qa")
        add(dom, "pwdens_census_1km_area_weighted", "PWD 1 km, wariant: komórki brzegowe ważone udziałem pola w obszarze",
            c["pwdens_area_weighted"], "os./km²", GRID_NSP, SRC_NSP, POP_DATE_NSP, "qa")
        add(dom, "ghsl_to_census_ratio", "Ludność GHSL 2020 / NSP 2021 (ta sama domena)",
            r["ghsl_100m_pop"][dom] / c["pop"], "", "GHSL 100 m vs siatka 1 km", f"{SRC_GHSL}; {SRC_NSP}",
            f"{POP_DATE_GHSL} / {POP_DATE_NSP}", "qa",
            "Część różnicy to definicja ludności (rezydująca w NSP), nie rozkład; patrz density.md §7.1.")
        # degree of urbanisation (census grid; one variant only)
        for k, lab in DEGURBA_LABEL.items():
            add(dom, f"degurba_share_{k}", f"Udział ludności obszaru w komórkach 1 km typu: {lab} (stopień urbanizacji)",
                d["degurba"][k] * 100, "%", GRID_NSP, SRC_NSP, POP_DATE_NSP, "table",
                "Klasyfikacja wg reguł Eurostatu (DEGURBA poziom 1, uproszczona: bez reguły zabudowy ≥ 50 %) "
                "liczona na całej siatce spisowej 1 km; centrum ≥ 1 500 os./km² i ≥ 50 000 os., skupisko "
                "≥ 300 os./km² i ≥ 5 000 os. Nie jest to oficjalna klasyfikacja Eurostatu.")
        for v in VARIANTS:
            x = vres(v)
            grid, src, src_b, pdate = VARIANT_META[v]
            add(dom, "profile_r50_km", "Promień od centrum obejmujący 50 % ludności obszaru", x["r50"][dom], "km",
                grid, src, pdate, "table", pop_grid=v)
            add(dom, "profile_share_10km", "Udział ludności obszaru w promieniu 10 km od centrum",
                x["share_within"][dom]["10"] * 100, "%", grid, src, pdate, "table", pop_grid=v)
            for thr in thresholds:
                t = f"{int(round(thr * 100))}"
                e = x["rho"][str(thr)][dom]
                work = "próg przyjęty do raportowania" if thr == thr_work else "wariant wrażliwości"
                if dom == "core" and thr == BERTAUD_THR:
                    cmp_ = ("Definicja najbliższa Bertaudowi i Malpezziemu (2003): wartości dla Warszawy i Krakowa "
                            "zbliżone do ich danych z lat 90. (density.md, tabela B).")
                else:
                    cmp_ = ("Poziom wyższy niż u Bertauda i Malpezziego z konstrukcji (maska netto); porównywalny "
                            "z ich wartościami jest rdzeń przy progu 10 % (density.md, tabela B).")
                fl = (f"Maska zabudowy GHS-BUILT-S ≥ {t} % ({work}). ρ = 1 to równomierna gęstość "
                      "na kole, nie optimum; ρ < 1: ludność bliżej centrum niż przy równomiernym rozkładzie. " + cmp_)
                if e["rho"] is None:
                    fl += f" Brak danych: maska obejmuje < {int(MIN_MASK_POP_SHARE * 100)} % ludności obszaru."
                add(dom, f"rho_t{t}", f"Indeks dyspersji Bertauda ρ (maska zabudowy ≥ {t} %)", e["rho"], "",
                    grid, src_b, pdate, "table", fl, pop_grid=v)
                if v == MAIN:
                    add(dom, f"mask_area_t{t}", f"Pole maski terenu zabudowanego (≥ {t} %)", e["area_km2"], "km²",
                        GRID_100, "JRC GHS-BUILT-S R2023A, epoka 2020", POP_DATE_GHSL, "table")
                add(dom, f"mask_pop_share_t{t}", f"Udział ludności obszaru ({popname(v)}) w masce zabudowy ≥ {t} %",
                    e["pop_share"] * 100, "%", grid, src_b, pdate, "table", pop_grid=v)
                nk = f"{dom}_nearest"
                if nk in x["rho"][str(thr)]:
                    en = x["rho"][str(thr)][nk]
                    add(dom, f"rho_nearest_t{t}",
                        f"ρ liczone do najbliższego z {len(r['centres'])} centrów (inna miara; maska ≥ {t} %)",
                        en["rho"], "", grid, src_b, pdate, "table",
                        "Inna miara niż ρ jednocentrowe: odległość do najbliższego centrum z listy w config.yaml; "
                        "mianownik ⅔R jak w ρ. Nie porównywać z ρ innych miast.", pop_grid=v)
            ge = x["gini_eta"][f"mask_{dom}"]
            add(dom, "gini_norm_mask", "Gini znormalizowany (G/Gmax) w masce zabudowy", ge.get("gini_norm"), "",
                grid, src_b, pdate, "qa",
                f"Tylko QA. Domena: maska ≥ {int(thr_work * 100)} %, komórki 100 m, n = {ge.get('n_cells')}.", pop_grid=v)
            add(dom, "eta_mask", "Indeks rozproszenia hotspotów η (Volpati i Barthelemy) w masce zabudowy",
                ge.get("eta"), "", grid, src_b, pdate, "qa",
                f"Tylko QA. Próg LouBar: {sig(ge.get('loubar_density') or float('nan'))} os./km² "
                f"({ge.get('n_hotspots')} hotspotów), rozdzielczość 100 m.", pop_grid=v)
    # FUA-only rows (profile shape, Clark, fixed circle)
    for v in VARIANTS:
        x = vres(v)
        grid, src, src_b, pdate = VARIANT_META[v]
        ck = x["clark"]
        add("fua", "clark_b", "Gradient Clarka b (pierścienie 1–25 km, FUA)", ck["b"], "1/km", grid, src,
            pdate, "table", "Nie na grafiki jako samodzielna liczba (brief §11).", pop_grid=v)
        add("fua", "clark_d0", "Gęstość D0 z modelu Clarka (wyraz wolny)", ck["d0"], "os./km²", grid, src,
            pdate, "table", pop_grid=v)
        add("fua", "clark_r2", "R² dopasowania Clarka", ck["r2"], "", grid, src, pdate, "qa", pop_grid=v)
        add("fua", "density_first_km", "Gęstość w pierwszym km od centrum (pierścień 0–1 km)",
            ck.get("first_km_density"), "os./km²", grid, src, pdate, "table", pop_grid=v)
        add("fua", "profile_share_10km_free",
            "Udział ludności w promieniu 10 km wśród mieszkańców w promieniu 40 km (bez granic FUA)",
            x["share_within"]["free"]["10"] * 100, "%", grid, src, pdate, "table",
            "Wariant bez granic: cała ludność Polski w promieniu r od centrum.", pop_grid=v)
        ge = x["gini_eta"]["circle"]
        add("fua", "gini_norm_circle10", f"Gini znormalizowany w kole {CIRCLE_KM} km wokół centrum",
            ge.get("gini_norm"), "", grid, src, pdate, "qa",
            f"Tylko QA. Domena: koło {CIRCLE_KM} km wokół centrum (niezależne od FUA), komórki 100 m, "
            f"n = {ge.get('n_cells')}.", pop_grid=v)
        add("fua", "eta_circle10", f"η (Volpati i Barthelemy) w kole {CIRCLE_KM} km wokół centrum", ge.get("eta"), "",
            grid, src, pdate, "qa",
            f"Tylko QA. Próg LouBar: {sig(ge.get('loubar_density') or float('nan'))} os./km², rozdzielczość 100 m.",
            pop_grid=v)
    # centre sensitivity (main grid only)
    cs_ = r["centre_sensitivity"]
    grid, src, src_b, pdate = VARIANT_META[MAIN]
    tw = int(round(thr_work * 100))
    cflag = ("Wrażliwość na wybór centrum; maska zabudowy ta sama dla trzech centrów (zarodki z config.yaml), "
             "zmieniają się tylko odległości.")
    for kind in ("townhall", "popcentroid"):
        c = cs_["centres"][kind]
        note = f"{CENTRE_LABEL[kind]}: {c['name']}" + (f" ({c['osm']}; wybór: {c['rule']})" if kind == "townhall" else "")
        add("core", f"centre_offset_{kind}_km", f"Odległość: centrum z config.yaml – {CENTRE_LABEL[kind]}",
            c["offset_from_config_km"], "km", "EPSG:2180", src if kind == "popcentroid" else "OSM 2026-11-22",
            pdate if kind == "popcentroid" else None, "table", note)
    for kind in CENTRE_KINDS:
        vv = cs_["values"][kind]
        lab = CENTRE_LABEL[kind]
        for dom, key, metric, label in (
                ("fua", "rho_fua_work", f"rho_t{tw}_centre_{kind}", f"ρ (maska ≥ {tw} %), centrum: {lab}"),
                ("core", "rho_core_work", f"rho_t{tw}_centre_{kind}", f"ρ (maska ≥ {tw} %), centrum: {lab}"),
                ("core", "rho_core_t10", f"rho_t10_centre_{kind}", f"ρ (maska ≥ 10 %), centrum: {lab}"),
                ("fua", "r50_fua", f"profile_r50_km_centre_{kind}", f"Promień obejmujący 50 % ludności, centrum: {lab}"),
                ("core", "r50_core", f"profile_r50_km_centre_{kind}", f"Promień obejmujący 50 % ludności, centrum: {lab}")):
            add(dom, metric, label, vv[key], "km" if key.startswith("r50") else "", grid,
                src_b if key.startswith("rho") else src, pdate, "table", cflag)
    for dom, key, metric, unit in (("fua", "rho_fua_work", f"rho_t{tw}_centre_spread", ""),
                                   ("core", "rho_core_work", f"rho_t{tw}_centre_spread", ""),
                                   ("core", "rho_core_t10", "rho_t10_centre_spread", ""),
                                   ("fua", "r50_fua", "profile_r50_km_centre_spread", "km"),
                                   ("core", "r50_core", "profile_r50_km_centre_spread", "km")):
        what = "ρ" if key.startswith("rho") else "r50"
        add(dom, metric, f"Rozrzut {what} między trzema centrami (maks. − min.)", cs_["spread"][key], unit, grid,
            src_b if key.startswith("rho") else src, pdate, "table", cflag)
    return rows


def write_metrics(rows: list[dict], today: str) -> None:
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["domain"], m["metric"], m["population_grid"] or ""))
    METRICS.mkdir(parents=True, exist_ok=True)
    write_json(METRICS / "metrics_density.json", {"generated": today, "metrics": rows})
    fields = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
              "timetable_date", "coverage_share", "flag", "tier", "population_grid"]
    with open(METRICS / "metrics_density.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in fields})


def write_charts(results: list[dict], today: str, thr_work: float) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    cities = []
    for r in sorted(results, key=lambda r: -r["fua"]["census"]["pwdens"]):
        cities.append({"id": r["id"], "name": r["name"], "phase": r["phase"], "polycentric": r["polycentric"],
                       "pwdens_fua": sig(r["fua"]["census"]["pwdens"]), "pwdens_core": sig(r["core"]["census"]["pwdens"]),
                       "gross_density_fua": sig(r["fua"]["gross_density"]),
                       "gross_density_core": sig(r["core"]["gross_density"]),
                       "population_fua": r["fua"]["census"]["pop"], "population_core": r["core"]["census"]["pop"],
                       "flag": ("Aglomeracja policentryczna/liniowa; granica to suma kilku FUA Eurostatu. "
                                "PWD nie zależy od wyboru centrum." if r["polycentric"] else "")})
    write_json(CHARTS / "pwdens.json", {
        "generated": today, "title": "Gęstość ważona populacją (experienced density) i gęstość brutto",
        "unit": "os./km²", "grid": GRID_NSP, "source": SRC_NSP, "population_date": POP_DATE_NSP,
        "timetable_date": None, "domains": {"fua": "FUA (Eurostat URAU 2021)", "core": "rdzeń (miasta URAU 2021)"},
        "method": ("PWD (gęstość ważona populacją: Σ p·d / Σ p) po komórkach 1 km, których środek leży w obszarze; d = ludność komórki / "
                   "jej pole (1 km², mniej dla komórek przyciętych granicą państwa). Gęstość brutto = ludność / pole obszaru."),
        "caveats": ["PWD zależy od rozmiaru komórki (MAUP): porównywać tylko liczby z tej samej siatki 1 km.",
                    "Ludność rezydująca NSP 2021 (ok. 2,7 % poniżej ludności wg definicji krajowej).",
                    "GZM i Trójmiasto: PWD nie zależy od centrum, ale granica GZM to suma 4 FUA (wariant a)."],
        "sorted_by": "pwdens_fua desc", "cities": cities})

    def series(r, key, rmax=None):
        df = pd.DataFrame(r["profiles"][key])
        if rmax:
            df = df[df.r_out_km <= rmax]
        return {"r_km": [int(v) for v in df.r_out_km], "cum_share": [sig(v) for v in df.cum_share],
                "cum_pop": [int(round(v)) for v in df.cum_pop], "ring_density": [sig(v) for v in df.density]}

    common = {"generated": today, "grid": GRID_100S, "source": SRC_SCALED, "population_date": POP_DATE_SCALED,
              "population_grid": MAIN, "timetable_date": None,
              "x": "odległość od centrum, km (koniec pierścienia; EPSG:2180)",
              "y": "udział skumulowany ludności (0–1)",
              "variants": {
                  "fua": "(i) tylko ludność w FUA; udział w ludności FUA; krzywa kończy się na 100 % na skraju FUA",
                  "free": "(ii) bez granic FUA: cała ludność (w Polsce) w promieniu r; udział w ludności w promieniu 40 km",
              },
              "caveats": ["Ludność NSP 2021 z komórek 1 km rozłożona wewnątrz komórki wzorem GHS-POP 2020 (100 m); "
                          "poziom spisowy na 1 km, rozkład wewnątrz komórki modelowany.",
                          "Wariant z surowym GHS-POP: data/interim/density/*_profile_*_raw.csv (density.md).",
                          "Wariant (ii): przy dużym r wchodzą sąsiednie miasta; ludność za granicą państwa pominięta."]}
    mono = [r for r in results if not r["polycentric"]]
    poly = [r for r in results if r["polycentric"]]
    write_json(CHARTS / "profile_cumulative_monocentric.json", {
        **common, "title": "Skumulowany profil ludności według odległości od centrum: aglomeracje jednocentrowe",
        "cities": [{"id": r["id"], "name": r["name"], "phase": r["phase"], "centre": r["centres"][0]["name"],
                    "fua": series(r, "fua"), "free": series(r, "free", PROFILE_MAX_KM)}
                   for r in sorted(mono, key=lambda r: r["id"])]})
    write_json(CHARTS / "profile_cumulative_polycentric.json", {
        **common, "title": "Skumulowany profil ludności: aglomeracje policentryczne / liniowe (osobny panel)",
        "caveats": common["caveats"] + [POLY_FLAG,
                                        "Wariant *_nearest: odległość do najbliższego z centrów z config.yaml; to inna miara."],
        "cities": [{"id": r["id"], "name": r["name"], "phase": r["phase"],
                    "centres": [c["name"] for c in r["centres"]],
                    "fua": series(r, "fua"), "free": series(r, "free", PROFILE_MAX_KM),
                    "fua_nearest": series(r, "fua_nearest"), "free_nearest": series(r, "free_nearest", PROFILE_MAX_KM)}
                   for r in sorted(poly, key=lambda r: r["id"])]})


def jsonable(r: dict) -> dict:
    r = dict(r)
    r.pop("profiles", None)
    return round_sig(json.loads(json.dumps(r, default=float)), 6)


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    thresholds = [float(t) for t in cfg["built_up_threshold_sensitivity"]]
    thr_work = float(cfg["built_up_threshold"])
    if thr_work not in thresholds:
        thresholds = sorted(thresholds + [thr_work])
    today = dt.date.today().isoformat()
    build_scaled_100()            # before the GHSL rasters are loaded (memory)
    degurba = degurba_grid()
    results, rows = [], []
    for agg in sorted(all_agglomeration_ids()):
        t1 = time.time()
        r = run_agglomeration(agg, thresholds, thr_work, degurba)
        results.append(r)
        rows += metric_rows(r, thresholds, thr_work)
        write_json(OUT / f"{agg}.json", jsonable(r))
        print(f"{agg}: PWD fua {r['fua']['census']['pwdens']:.0f} core {r['core']['census']['pwdens']:.0f} "
              f"rho20 {r['rho'][str(thr_work)]['fua']['rho']:.3f} ({time.time() - t1:.0f} s)", flush=True)
    write_metrics(rows, today)
    write_charts(results, today, thr_work)
    extra = {"thresholds": thresholds, "working_threshold": thr_work, "gap_cells": GAP_CELLS,
             "min_mask_pop_share": MIN_MASK_POP_SHARE,
             "seed_radius_m": SEED_RADIUS_M, "circle_km": CIRCLE_KM, "eta_sample": ETA_SAMPLE,
             "population_dates": {"census": POP_DATE_NSP, "ghsl": POP_DATE_GHSL, "census_scaled": POP_DATE_SCALED},
             "population_grids": {"main": MAIN, "variant": RAWV,
                                  "note": "100 m measures on the census-scaled GHSL grid (pipeline.popgrid.scale_100m "
                                          "at 100 m); raw GHS-POP kept as tier-qa rows with population_grid=ghsl_raw"},
             "bertaud_threshold": BERTAUD_THR,
             "degurba": {"urban_centre": [DEGURBA_UC_DENS, DEGURBA_UC_POP], "urban_cluster": [DEGURBA_CL_DENS,
                                                                                            DEGURBA_CL_POP]},
             "townhalls": "data/interim/density/townhalls_osm.csv (OSM 2026-11-22, amenity=townhall)"}
    mp = write_meta(OUT, "density", inputs=INPUT_IDS + ["osm_poland_pbf"], started=t0, extra=extra)
    # metrics/ and charts/ hold one _meta_<step>.json per step; the plain _meta.json there belongs to the merge step
    for d in (METRICS, CHARTS):
        shutil.copyfile(mp, d / "_meta_density.json")


if __name__ == "__main__":
    main()
