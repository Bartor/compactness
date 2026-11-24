"""Urban-form additions (ROADMAP item 16): Angel's proximity and cohesion indices, polycentricity (eta and density
hotspots), degree-of-urbanisation shares against the official Eurostat 2021 urban centres, and residents by density
class of their 250 m cell.

    python -m pipeline.form_extra        # needs pipeline.density (data/interim/density/<agg>.npz) and pipeline.popgrid

Outputs
* results/metrics/metrics_form.csv + .json    long format, the row schema of the other step files, step "form"
* results/metrics/_meta_form.json, results/charts/_meta_form.json, data/interim/form/_meta.json
* results/charts/form.json                    residents by density class (250 m) + hotspot rank-size data
* data/interim/form/<agg>.json + <agg>.npz    full results and the extent masks for the QA note (pipeline.form_md)

Rules (described in Polish in results/qa/form/form.md)

Urban extent, two definitions
* "urban_extent" (main; Atlas of Urban Expansion / Angel et al. method, rebuilt on GHS-BUILT-S 100 m):
  1. built-up pixel: GHS-BUILT-S 2020 built surface >= BUILT_PIXEL_SHARE (10 %) of the 100 m cell, in Poland;
  2. urbanness of a built-up pixel = share of built-up pixels in the circle of 1 km2 around it (radius 564 m; the
     denominator counts pixels in Poland only): urban >= 50 %, suburban 25-50 %, rural < 25 %;
  3. fringe open space: non-built pixels within 100 m (rook neighbours) of urban or suburban built-up pixels;
  4. captured open space: holes of (urban + suburban + fringe) smaller than 200 ha (4-connected, not touching the
     window edge);
  5. urban extent = urban + suburban built-up + fringe + captured open space; clusters 8-connected after bridging
     gaps of up to 600 m (EXTENT_GAP_CELLS, the rule of the rho mask in pipeline.density; without it the Vistula
     cuts Warsaw's town hall off from Praga); the city's extent is the cluster containing the town hall
     (pipeline.density_centres).
  Sensitivity: built-up pixel at 5 % and 20 %; no gap bridging.  Differences from the Atlas: 100 m GHSL building footprints instead of
  30 m Landsat built-up (roads and paved yards are not "built" in GHS-BUILT-S), no water layer, one cluster only.
* "urban_centre_main" (published, coarse): the Eurostat GISCO 2021 urban centre (HDENS_CLST_2021, 1 km, census
  2021) whose 1 km cell holds the town hall; 100 m cells whose centre (LAEA) lies in one of its cells.
Indices on an extent of area A (n cells x 0.01 km2, Mollweide equal-area), R = sqrt(A / pi), centre = town hall:
* proximity index PRX = (2/3 R) / mean distance of all extent cells to the centre (Angel et al.);
* cohesion index = (128 / (45 pi)) R / mean distance between all pairs of extent cells (exact, all pairs);
* population-weighted counterpart on the same extent: rho_ext = mean distance of residents to the centre / (2/3 R)
  (Bertaud's rho with Angel's extent and centre); land_over_pop = mean land distance / mean resident distance
  (> 1: residents live closer to the town hall than the land is).
Population: census-scaled GHS-POP 100 m (NSP 2021 1 km totals, GHSL 2020 pattern), as in pipeline.density.

Polycentricity
* eta (Volpati and Barthelemy 2018, eq. 6) on the built-up mask >= 20 % of pipeline.density (FUA), LouBar hotspots,
  here with exact mean distances over all pairs (pipeline.density uses a 4 000-cell sample; both are reported).
* density hotspots on the 250 m census-scaled grid (FUA cells): contiguous (8-connected) clusters of cells with
  density >= HOT_MAIN (10 000 /km2, the top class but one of the site's density layer); per agglomeration the
  number of hotspots with >= HOT_MIN_POP residents, the share of the hotspot population in the largest hotspot,
  the ratio second / largest, and the rank-size slope (OLS of ln population on ln rank over hotspots with >=
  HOT_MIN_POP residents, at least 4 of them).  Sensitivity: 5 000 /km2 and the LouBar density of the FUA's 250 m cells.

Degree of urbanisation (census 1 km grid, NSP 2021)
* official urban centres: cells of HDENS_CLST_2021 (cluster population > 0);
* simplified classification of pipeline.density.degurba_grid (own urban centres) for the comparison;
* "degurba2021" shares: official urban centre; urban cluster = cells >= 300 /km2 in 8-connected clusters of
  >= 5 000 residents, outside the official urban centres (simplified: no smoothing of clusters, no level 2);
  rural = the rest.

Density classes: 250 m cells of the census-scaled grid (data/interim/popgrid/cells_<agg>.parquet), density =
residents / 0.0625 km2, classes = pipeline.tiles_layers.DENSITY_STOPS (the site's density layer), FUA and core.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import shutil
import time

import numpy as np
import pandas as pd
import rasterio
import shapely
from scipy import ndimage

from pipeline import density as D
from pipeline.boundaries import all_agglomeration_ids, load_lau, load_urau
from pipeline.common import INTERIM, RAW, RESULTS, load_config, round_sig, sig, write_json, write_meta
from pipeline.density_centres import NOT_SEAT_RX, SEAT_RX, WGS_TO_2180, townhall, townhalls
from pipeline.tiles_layers import DENSITY_STOPS

OUT = INTERIM / "form"
METRICS = RESULTS / "metrics"
CHARTS = RESULTS / "charts"
POPGRID = INTERIM / "popgrid"
HDENS = RAW / "eurostat_hdens_2021" / "extracted" / "HDENS_CLST_2021.tif"
STEP = "form"

BUILT_PIXEL_SHARE = 0.10
BUILT_PIXEL_SENS = (0.05, 0.20)
WALK_CIRCLE_M = math.sqrt(1e6 / math.pi)       # 564.19 m: circle of 1 km2
URBAN_MIN, SUBURBAN_MIN = 0.50, 0.25
CAPTURED_MAX_HA = 200
EXTENT_GAP_CELLS = 3                            # bridge gaps <= 600 m between extent clusters, as pipeline.density
# second core city: hand pick when the townhall rule of pipeline.density_centres does not decide
SECOND_PICK = {"bydgoszcz_torun": ("way", 86490360, "6 obiektów z townhall:type=city; wybrano Wały gen. Sikorskiego 8 "
                                                    "(siedziba prezydenta; pozostałe to punkty obsługi, USC, filie)")}
CELL_HA = 1.0                                   # 100 m Mollweide cell
CELL250_KM2 = 0.0625
HOT_MAIN = 10000.0
HOT_SENS = (5000.0,)
HOT_MIN_POP = 5000
RANK_MIN_N = 4
COHESION_K = 128 / (45 * math.pi)               # mean distance between two random points of a unit disc

SRC_BUILT = "JRC GHS-BUILT-S R2023A, epoka 2020 (model)"
SRC_TH = "OSM 2026-11-22 (amenity=townhall; wybór ratusza: pipeline.density_centres)"
SRC_HDENS = "Eurostat GISCO HDENS_CLST_2021 (centra miejskie 2021, wyd. 2024-11-19)"
GRID_100 = "GHSL 100 m (Mollweide)"
GRID_250S = "GHSL 250 m przeskalowany do NSP 2021 (EPSG:2180)"
GRID_NSP = D.GRID_NSP
POP_SCALED = D.POP_DATE_SCALED
POP_NSP = D.POP_DATE_NSP
POP_BUILT = D.POP_DATE_GHSL
SRC_SCALED = D.SRC_SCALED
MAIN = D.MAIN
POLY_FLAG = ("Aglomeracja wielomiejska lub liniowa: miara względem jednego ratusza opisuje tylko miasto, w którego "
             "zasięgu leży ratusz, albo nie ma sensu (form.md).")
INPUT_IDS = ["ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20", "ghs_built_s_2020_R3_C20", "ghs_built_s_2020_R4_C20",
             "nsp2021_grid_1km_shp", "urau_2021_100k_all", "lau_2021_01m", "osm_poland_pbf",
             "eurostat_hdens_clst_2021"]


def log(msg: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S} {msg}", flush=True)


# ------------------------------------------------------------------ geometry helpers

def mean_pair_dist(x: np.ndarray, y: np.ndarray, chunk: int = 256) -> float:
    """Exact mean Euclidean distance over all ordered pairs i != j (m)."""
    n = len(x)
    if n < 2:
        return float("nan")
    # float32 offsets from the mean (sub-metre precision at these extents), float64 sums per row
    x = (x - x.mean()).astype(np.float32)
    y = (y - y.mean()).astype(np.float32)
    tot = 0.0
    for i0 in range(0, n, chunk):
        dx = x[i0:i0 + chunk, None] - x[None, :]
        dy = y[i0:i0 + chunk, None] - y[None, :]
        tot += float(np.sqrt(dx * dx + dy * dy).sum(axis=1, dtype=np.float64).sum())
    return tot / (n * (n - 1))


def disk_kernel(radius_cells: float) -> np.ndarray:
    k = int(math.ceil(radius_cells))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    return ((xx * xx + yy * yy) <= radius_cells * radius_cells).astype(np.float64)


class Win:
    """The 100 m Mollweide window of pipeline.density for one agglomeration (from its npz)."""

    def __init__(self, agg: str):
        z = np.load(D.OUT / f"{agg}.npz")
        a, b, c, d, e, f = z["tr"]
        self.tr = rasterio.Affine(a, b, c, d, e, f)
        self.built = z["built"]
        self.pop = z["pop"].astype(np.float64)
        self.dom_f = z["dom_f"]
        self.dom_c = z["dom_c"]
        self.mask20 = z["mask"]
        self.shape = self.built.shape
        with rasterio.open(D.GHS_POP_VRT) as s:
            g = s.transform
        c0 = int(round((self.tr.c - g.c) / g.a))
        r0 = int(round((self.tr.f - g.f) / g.e))
        pl = D.poland_mask_100()
        self.poland = pl[r0:r0 + self.shape[0], c0:c0 + self.shape[1]] == 1
        assert self.poland.shape == self.shape
        rows, cols = np.mgrid[0:self.shape[0], 0:self.shape[1]]
        X = self.tr.c + (cols + 0.5) * self.tr.a
        Y = self.tr.f + (rows + 0.5) * self.tr.e
        x, y = D.MOLL_TO_2180.transform(X.ravel(), Y.ravel())
        self.x = x.reshape(self.shape)
        self.y = y.reshape(self.shape)

    def cell_of(self, x2180: float, y2180: float) -> tuple[int, int]:
        X, Y = D.TO_MOLL.transform(x2180, y2180)
        return int((Y - self.tr.f) // self.tr.e), int((X - self.tr.c) // self.tr.a)


# ------------------------------------------------------------------ urban extent (Atlas-like, GHSL)

def urban_extent(W: Win, built_share: float, gap_cells: int = 3) -> dict:
    """Atlas-of-Urban-Expansion style extent on GHS-BUILT-S 100 m; returns arrays and component labels."""
    B = W.poland & (W.built != 65535) & (W.built >= built_share * 10000)
    K = disk_kernel(WALK_CIRCLE_M / 100.0)
    num = ndimage.convolve(B.astype(np.float64), K, mode="constant", cval=0.0)
    den = ndimage.convolve(W.poland.astype(np.float64), K, mode="constant", cval=0.0)
    u = np.where(den > 0, num / np.maximum(den, 1e-9), 0.0)
    urban = B & (u >= URBAN_MIN)
    suburban = B & (u >= SUBURBAN_MIN) & (u < URBAN_MIN)
    US = urban | suburban
    fringe = W.poland & ~B & ndimage.binary_dilation(US, structure=ndimage.generate_binary_structure(2, 1))
    E0 = US | fringe
    lab, n = ndimage.label(~E0, structure=ndimage.generate_binary_structure(2, 1))
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    edge = np.unique(np.concatenate([lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]]))
    small = (sizes * CELL_HA < CAPTURED_MAX_HA)
    small[0] = False
    small[edge] = False
    captured = small[lab] & W.poland
    E = E0 | captured
    # clusters: 8-connected after bridging gaps of up to 2 * gap_cells * 100 m (dilated cells never enter the extent)
    Ed = ndimage.binary_dilation(E, structure=D.disk(gap_cells)) if gap_cells > 0 else E
    clab, _ = ndimage.label(Ed, structure=np.ones((3, 3), bool))
    clab = np.where(E, clab, 0)
    return {"E": E, "lab": clab, "urban": urban, "suburban": suburban, "fringe": fringe, "captured": captured,
            "rural_built": B & ~US, "built": B}


def pick_cluster(lab: np.ndarray, W: Win, x: float, y: float) -> tuple[int, float]:
    """Label of the cluster at (x, y); if none, the nearest labelled cell (distance in m)."""
    r, c = W.cell_of(x, y)
    if 0 <= r < lab.shape[0] and 0 <= c < lab.shape[1] and lab[r, c] > 0:
        return int(lab[r, c]), 0.0
    m = lab > 0
    d = np.hypot(W.x[m] - x, W.y[m] - y)
    i = int(np.argmin(d))
    return int(lab[m][i]), float(d[i])


def indices(W: Win, M: np.ndarray, cx: float, cy: float, cohesion: bool = True) -> dict:
    n = int(M.sum())
    if n == 0:
        return {"cells": 0}
    A = n * D.PIX_KM2
    R = math.sqrt(A / math.pi) * 1000.0
    xs, ys = W.x[M], W.y[M]
    d = np.hypot(xs - cx, ys - cy)
    d_land = float(d.mean())
    p = W.pop[M]
    d_pop = float((p * d).sum() / p.sum()) if p.sum() > 0 else float("nan")
    out = {"cells": n, "area_km2": A, "R_km": R / 1000, "mean_dist_land_km": d_land / 1000,
           "mean_dist_pop_km": d_pop / 1000, "prx": (2 / 3 * R) / d_land, "rho_ext": d_pop / (2 / 3 * R),
           "land_over_pop": d_land / d_pop, "pop": float(p.sum()),
           "pop_share_of_fua": float(p.sum() / W.pop[W.dom_f].sum()),
           "share_outside_fua": float((M & ~W.dom_f).sum() / n),
           "density_gross": float(p.sum() / A)}
    if cohesion:
        mpd = mean_pair_dist(xs, ys)
        out["mean_pair_dist_km"] = mpd / 1000
        out["cohesion"] = COHESION_K * R / mpd
    return out


def second_centre(agg: str) -> dict | None:
    """Town hall of the second core city (Toruń, Gdynia) by the rule of pipeline.density_centres, or the configured
    extra centre when the rule does not decide."""
    cfg = load_config()["agglomerations"][agg]
    if agg not in ("bydgoszcz_torun", "trojmiasto"):
        return None
    code = cfg["city_codes"][1]
    u = load_urau().set_index("URAU_CODE")
    geom, name = u.loc[code, "geometry"], u.loc[code, "URAU_NAME"]
    cand = []
    for r in townhalls():
        x, y = WGS_TO_2180.transform(r["lon"], r["lat"])
        if shapely.contains_xy(geom, x, y):
            cand.append({**r, "x": x, "y": y})
    city = [c for c in cand if c["townhall_type"] == "city"]
    pick, rule = None, ""
    if agg in SECOND_PICK:
        t, i, why = SECOND_PICK[agg]
        hit = [c for c in cand if c["osm_type"] == t and c["osm_id"] == i]
        if len(hit) != 1:
            raise RuntimeError(f"{agg}: hand-picked second townhall {t}/{i} not among the candidates")
        pick, rule = hit[0], f"ręcznie: {why}"
    elif len(city) == 1:
        pick, rule = city[0], "townhall:type=city"
    else:
        pool = city or cand
        seat = [c for c in pool if SEAT_RX.search(c["name"] + " " + c["official_name"])
                and not NOT_SEAT_RX.search(c["name"] + " " + c["official_name"])]
        if len(seat) == 1:
            pick, rule = seat[0], "nazwa"
    if pick is None:
        e = cfg["extra_centres"][0]
        x, y = WGS_TO_2180.transform(e["lon"], e["lat"])
        return {"city": name, "name": e["name"], "x": x, "y": y, "osm": None,
                "rule": f"punkt z config.yaml (reguła ratusza nie rozstrzyga: {len(cand)} kandydatów)"}
    return {"city": name, "name": pick["name"] or pick["official_name"], "x": pick["x"], "y": pick["y"],
            "osm": f"{pick['osm_type']}/{pick['osm_id']}", "rule": rule}


# ------------------------------------------------------------------ Eurostat 2021 urban centres

_HD = None


def hdens():
    global _HD
    if _HD is None:
        with rasterio.open(HDENS) as s:
            a, tr = s.read(1), s.transform
        lab, _ = ndimage.label(a > 0)     # 4-connectivity, as the degree-of-urbanisation clusters
        _HD = (a, lab, tr)
    return _HD


def hdens_lookup(x2180: np.ndarray, y2180: np.ndarray) -> np.ndarray:
    a, lab, tr = hdens()
    x, y = D.TO_3035.transform(np.asarray(x2180, float), np.asarray(y2180, float))
    r = np.floor((np.asarray(y) - tr.f) / tr.e).astype(int)
    c = np.floor((np.asarray(x) - tr.c) / tr.a).astype(int)
    ok = (r >= 0) & (r < lab.shape[0]) & (c >= 0) & (c < lab.shape[1])
    v = np.zeros(len(r), np.int64)
    v[ok] = lab[r[ok], c[ok]]
    return v


def uc_extent(W: Win, x: float, y: float) -> tuple[np.ndarray, dict]:
    v = hdens_lookup(W.x.ravel(), W.y.ravel()).reshape(W.shape)
    at = int(hdens_lookup(np.array([x]), np.array([y]))[0])
    info = {"townhall_in_uc": at > 0}
    if at == 0:
        m = v > 0
        d = np.hypot(W.x[m] - x, W.y[m] - y)
        i = int(np.argmin(d))
        at = int(v[m][i])
        info["dist_to_uc_m"] = float(d[i])
    a, lab, _ = hdens()
    info["uc_population_official"] = int(a[lab == at].max())
    info["uc_cells_1km"] = int((lab == at).sum())
    return (v == at) & W.poland, info


# ------------------------------------------------------------------ polycentricity

def eta_exact(W: Win) -> dict:
    M = W.mask20
    p, x, y = W.pop[M], W.x[M], W.y[M]
    n = len(p)
    order = np.argsort(p, kind="stable")
    ps = p[order]
    F_star = 1 - ps.sum() / (n * ps[-1])
    k = int(math.floor(F_star * n))
    hot = np.sort(order[k:])
    d_all = mean_pair_dist(x, y)
    d_hot = mean_pair_dist(x[hot], y[hot])
    return {"eta": d_hot / d_all, "n_cells": n, "n_hotspots": int(len(hot)),
            "loubar_density": float(ps[min(k, n - 1)] / D.PIX_KM2), "mean_dist_all_km": d_all / 1000,
            "mean_dist_hot_km": d_hot / 1000}


def cells250(agg: str) -> pd.DataFrame:
    d = pd.read_parquet(POPGRID / f"cells_{agg}.parquet",
                        columns=["cell_id", "x", "y", "pop_ghsl_census_scaled", "in_fua", "in_core"])
    return d.rename(columns={"pop_ghsl_census_scaled": "pop"}).sort_values("cell_id").reset_index(drop=True)


def loubar_threshold(dens: np.ndarray, pop: np.ndarray) -> float:
    """LouBar value on the cells' population (cells of equal area), returned as density."""
    ps = np.sort(pop)
    n = len(ps)
    F = 1 - ps.sum() / (n * ps[-1])
    return float(ps[min(int(math.floor(F * n)), n - 1)] / CELL250_KM2)


def hotspots(d: pd.DataFrame, thr: float, centres: list[dict], lau) -> dict:
    f = d[d.in_fua & (d["pop"] > 0)]
    x0, y0 = f.x.min(), f.y.max()
    col = np.round((f.x.values - x0) / 250).astype(int)
    row = np.round((y0 - f.y.values) / 250).astype(int)
    H = np.zeros((row.max() + 1, col.max() + 1), bool)
    P = np.zeros(H.shape)
    dens = f["pop"].values / CELL250_KM2
    hot = dens >= thr
    H[row[hot], col[hot]] = True
    P[row, col] = f["pop"].values
    lab, n = ndimage.label(H, structure=np.ones((3, 3), bool))
    total_fua = float(f["pop"].sum())
    cl = []
    if n:
        idx = np.arange(1, n + 1)
        pops = ndimage.sum(P, lab, idx)
        cells = ndimage.sum(H, lab, idx)
        rr, cc = np.mgrid[0:H.shape[0], 0:H.shape[1]]
        Xg = x0 + cc * 250.0
        Yg = y0 - rr * 250.0
        cx = ndimage.sum(P * Xg, lab, idx) / pops
        cy = ndimage.sum(P * Yg, lab, idx) / pops
        pts = shapely.points(cx, cy)
        names = lau_names(pts, lau)
        for i in range(n):
            dist = [math.hypot(cx[i] - c["x"], cy[i] - c["y"]) for c in centres]
            j = int(np.argmin(dist))
            cl.append({"label": i + 1, "pop": float(pops[i]), "cells": int(cells[i]), "x": float(cx[i]),
                       "y": float(cy[i]), "gmina": names[i], "nearest_centre": centres[j]["name"],
                       "nearest_centre_km": dist[j] / 1000})
        cl.sort(key=lambda r: (-r["pop"], r["x"], r["y"]))
        for k, r in enumerate(cl, 1):
            r["rank"] = k
    hot_pop = sum(r["pop"] for r in cl)
    big = [r for r in cl if r["pop"] >= HOT_MIN_POP]
    slope = r2 = None
    if len(big) >= RANK_MIN_N:
        lr = np.log(np.arange(1, len(big) + 1))
        lp = np.log([r["pop"] for r in big])
        A = np.vstack([lr, np.ones_like(lr)]).T
        coef, res, *_ = np.linalg.lstsq(A, lp, rcond=None)
        slope = float(coef[0])
        ss = float(((lp - lp.mean()) ** 2).sum())
        r2 = float(1 - (res[0] / ss)) if len(res) and ss > 0 else None
    # every configured centre: the hotspot whose cells come closest (cell centre within 1 km), if any
    cen = []
    if n:
        hx = x0 + col[hot] * 250.0
        hy = y0 - row[hot] * 250.0
        hl = lab[row[hot], col[hot]]
        by_label = {r["label"]: r for r in cl}
        for c in centres:
            dd = np.hypot(hx - c["x"], hy - c["y"])
            i = int(np.argmin(dd))
            k = by_label[int(hl[i])]
            cen.append({"centre": c["name"], "nearest_hot_cell_km": float(dd[i] / 1000),
                        "hotspot_rank": k["rank"], "hotspot_pop": k["pop"], "hotspot_gmina": k["gmina"]})
    else:
        cen = [{"centre": c["name"], "nearest_hot_cell_km": None, "hotspot_rank": None, "hotspot_pop": None}
               for c in centres]
    return {"threshold": thr, "n_hotspots": len(cl), "n_hotspots_min_pop": len(big), "hot_pop": hot_pop,
            "hot_pop_share_of_fua": hot_pop / total_fua if total_fua else None,
            "largest_share": cl[0]["pop"] / hot_pop if cl else None,
            "second_over_largest": cl[1]["pop"] / cl[0]["pop"] if len(cl) > 1 else None,
            "rank_size_slope": slope, "rank_size_r2": r2, "rank_size_n": len(big),
            "clusters": cl, "centres": cen}


def lau_names(pts, lau) -> list[str]:
    g = lau.geometry.values
    tree = shapely.STRtree(g)
    i_pt, i_g = tree.query(pts, predicate="within")
    out = [""] * len(pts)
    for a, b in zip(i_pt, i_g):
        out[a] = lau.LAU_NAME.values[b]
    return out


# ------------------------------------------------------------------ degree of urbanisation

def degurba_official() -> dict:
    """Per census cell: own class (pipeline.density), official urban centre flag, hybrid class."""
    c = D.census()
    own = D.degurba_grid()
    a, lab, tr = hdens()
    col = np.floor((c.E.values + 500 - tr.c) / tr.a).astype(int)
    row = np.floor((c.N.values + 500 - tr.f) / tr.e).astype(int)
    ok = (row >= 0) & (row < a.shape[0]) & (col >= 0) & (col < a.shape[1])
    uc_pop = np.zeros(len(c), np.int64)
    uc_pop[ok] = a[row[ok], col[ok]]
    uc_lab = np.zeros(len(c), np.int64)
    uc_lab[ok] = lab[row[ok], col[ok]]
    off = uc_pop > 0
    # urban clusters (simplified): >= 300 /km2, 8-connected, >= 5 000 residents, outside the official centres
    e0, n1 = int(c.E.min()), int(c.N.max())
    rows = ((n1 - c.N.values) // 1000).astype(int)
    cols = ((c.E.values - e0) // 1000).astype(int)
    shape = (rows.max() + 1, cols.max() + 1)
    pop = np.zeros(shape)
    dens = np.zeros(shape)
    pop[rows, cols] = c.RES.values
    dens[rows, cols] = c.RES.values / c.area_km2.values
    m = dens >= D.DEGURBA_CL_DENS
    L, n = ndimage.label(m, structure=np.ones((3, 3), bool))
    sums = ndimage.sum(pop, L, index=np.arange(1, n + 1))
    keep = np.r_[False, sums >= D.DEGURBA_CL_POP]
    cl = keep[L][rows, cols] & ~off
    hybrid = np.where(off, 2, np.where(cl, 1, 0)).astype(np.int8)
    p = c.RES.values.astype(float)
    dens_c = p / c.area_km2.values
    # national comparison and reasons for the differences
    only_off = off & (own != 2)
    only_own = (own == 2) & ~off
    # population of each official cluster inside Poland (census) vs its official population (cross-border clusters)
    pl_sum = pd.Series(p[off]).groupby(uc_lab[off]).sum()
    off_pop = pd.Series(uc_pop[off]).groupby(uc_lab[off]).max()
    cross = set(pl_sum.index[(off_pop / pl_sum) > 1.001])
    reasons = {
        "only_official_cells": int(only_off.sum()), "only_official_pop": float(p[only_off].sum()),
        "only_official_lt1500_cells": int((only_off & (dens_c < D.DEGURBA_UC_DENS)).sum()),
        "only_official_lt1500_pop": float(p[only_off & (dens_c < D.DEGURBA_UC_DENS)].sum()),
        "only_official_zero_pop_cells": int((only_off & (p == 0)).sum()),
        "only_official_ge1500_cells": int((only_off & (dens_c >= D.DEGURBA_UC_DENS)).sum()),
        "only_official_ge1500_pop": float(p[only_off & (dens_c >= D.DEGURBA_UC_DENS)].sum()),
        "only_official_ge1500_crossborder_pop": float(p[only_off & (dens_c >= D.DEGURBA_UC_DENS)
                                                         & np.isin(uc_lab, list(cross))].sum()),
        "only_own_cells": int(only_own.sum()), "only_own_pop": float(p[only_own].sum()),
        "crossborder_clusters": len(cross),
        "official_clusters_in_poland": int(len(pl_sum)),
        "official_pop_equals_census_sum_clusters": int(((off_pop - pl_sum).abs() < 0.5).sum()),
        "pop_share_official": float(p[off].sum() / p.sum()), "pop_share_own": float(p[own == 2].sum() / p.sum()),
        "cells_official": int(off.sum()), "cells_own": int((own == 2).sum()),
        "cells_both": int((off & (own == 2)).sum()),
        "cluster_share_hybrid": float(p[hybrid == 1].sum() / p.sum()),
        "cluster_share_own": float(p[own == 1].sum() / p.sum()),
    }
    return {"own": own, "official": off, "hybrid": hybrid, "reasons": reasons}


def degurba_area(geom, dg: dict) -> dict:
    idx = D.census_in(geom)
    p = D.census().RES.values[idx].astype(float)
    tot = p.sum()
    own, off, hyb = dg["own"][idx], dg["official"][idx], dg["hybrid"][idx]
    return {"pop": tot,
            "uc_official": p[off].sum() / tot, "uc_own": p[own == 2].sum() / tot,
            "cluster_hybrid": p[hyb == 1].sum() / tot, "rural_hybrid": p[hyb == 0].sum() / tot,
            "cluster_own": p[own == 1].sum() / tot, "rural_own": p[own == 0].sum() / tot,
            "only_official_pop": p[off & (own != 2)].sum(), "only_own_pop": p[(own == 2) & ~off].sum()}


# ------------------------------------------------------------------ density classes

def density_classes(d: pd.DataFrame) -> dict:
    out = {}
    for dom, flag in (("fua", "in_fua"), ("core", "in_core")):
        f = d[d[flag] & (d["pop"] > 0)]
        dens = f["pop"].values / CELL250_KM2
        k = np.searchsorted(DENSITY_STOPS, dens, side="right")
        pops = np.bincount(k, weights=f["pop"].values, minlength=len(DENSITY_STOPS) + 1)
        cells = np.bincount(k, minlength=len(DENSITY_STOPS) + 1)
        tot = pops.sum()
        o = np.argsort(dens, kind="stable")
        cum = np.cumsum(f["pop"].values[o])
        med = float(dens[o][np.searchsorted(cum, tot / 2)])
        out[dom] = {"pop": [float(v) for v in pops], "cells": [int(v) for v in cells], "total": float(tot),
                    "share": [float(v / tot) for v in pops],
                    "at_or_above": {str(int(s)): float(pops[i + 1:].sum() / tot) for i, s in enumerate(DENSITY_STOPS)},
                    "median_density": med}
    return out


# ------------------------------------------------------------------ per agglomeration

def run_agglomeration(agg: str, dg: dict, lau) -> dict:
    t0 = time.time()
    cfg = load_config()["agglomerations"][agg]
    a = D.load_agglomeration(agg)
    poly = bool(cfg.get("polycentric"))
    cs = D.centres(agg)
    th = townhall(agg)
    res = {"id": agg, "name": a["name"], "polycentric": poly, "townhall": {k: th[k] for k in
                                                                             ("name", "x", "y", "osm", "rule")},
           "config_centre": cs[0]}
    W = Win(agg)
    # --- extents
    ext = {}
    npz = {}
    for share, gap in ((BUILT_PIXEL_SHARE, EXTENT_GAP_CELLS), *((s, EXTENT_GAP_CELLS) for s in BUILT_PIXEL_SENS),
                       (BUILT_PIXEL_SHARE, 0)):
        U = urban_extent(W, share, gap)
        L, dist = pick_cluster(U["lab"], W, th["x"], th["y"])
        M = U["E"] & (U["lab"] == L)
        main = share == BUILT_PIXEL_SHARE and gap == EXTENT_GAP_CELLS
        if gap == 0:
            e = indices(W, M, th["x"], th["y"], cohesion=False)
            e["townhall_offset_m"] = dist
            ext["b10_gap0"] = e
            continue
        e = indices(W, M, th["x"], th["y"], cohesion=main)
        e["townhall_offset_m"] = dist
        e["built_share_rule"] = share
        e["touches_window_edge"] = bool(M[0, :].any() or M[-1, :].any() or M[:, 0].any() or M[:, -1].any())
        if main:
            e["composition_km2"] = {k: float((U[k] & M).sum() * D.PIX_KM2)
                                    for k in ("urban", "suburban", "fringe", "captured")}
            e["clusters_ge_1km2_in_window"] = int((np.bincount(U["lab"].ravel())[1:] >= 100).sum())
            cfg_c = indices(W, M, cs[0]["x"], cs[0]["y"], cohesion=False)
            e["prx_config_centre"] = cfg_c["prx"]
            e["rho_ext_config_centre"] = cfg_c["rho_ext"]
            npz["extent"] = M
            npz["urban"] = U["urban"]
            npz["suburban"] = U["suburban"]
            sc = second_centre(agg)
            if sc:
                L2, dist2 = pick_cluster(U["lab"], W, sc["x"], sc["y"])
                M2 = U["E"] & (U["lab"] == L2)
                e2 = indices(W, M2, sc["x"], sc["y"], cohesion=True)
                e2.update({"centre": sc, "same_cluster_as_first": bool(L2 == L), "townhall_offset_m": dist2})
                ext["second"] = e2
                npz["extent2"] = M2
        ext[f"b{int(round(share * 100))}"] = e
    res["extent"] = ext
    Muc, info = uc_extent(W, th["x"], th["y"])
    e = indices(W, Muc, th["x"], th["y"], cohesion=True)
    e.update(info)
    res["uc_extent"] = e
    npz["uc"] = Muc
    # --- polycentricity
    res["eta"] = eta_exact(W)
    d = cells250(agg)
    f = d[d.in_fua & (d["pop"] > 0)]
    lb = loubar_threshold(f["pop"].values / CELL250_KM2, f["pop"].values)
    hs = {}
    for thr, key in ((HOT_MAIN, "main"), *((t, f"t{int(t)}") for t in HOT_SENS), (lb, "loubar")):
        hs[key] = hotspots(d, thr, cs, lau)
    res["hotspots"] = hs
    # --- degree of urbanisation
    res["degurba"] = {dom: degurba_area(a[dom], dg) for dom in ("fua", "core")}
    # --- density classes
    res["density_classes"] = density_classes(d)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / f"{agg}.npz", tr=np.array(W.tr)[:6], dom_f=W.dom_f, pop=W.pop.astype(np.float32),
                        townhall=np.array([th["x"], th["y"]]), **npz)
    log(f"{agg}: PRX {ext['b10']['prx']:.3f} coh {ext['b10']['cohesion']:.3f} rho_ext {ext['b10']['rho_ext']:.3f} "
        f"UC PRX {res['uc_extent']['prx']:.3f} eta {res['eta']['eta']:.3f} hot {hs['main']['n_hotspots_min_pop']} "
        f"({time.time() - t0:.0f} s)")
    return res


# ------------------------------------------------------------------ rows

def metric_rows(r: dict, density_rows: dict) -> list[dict]:
    rows = []
    agg, poly = r["id"], r["polycentric"]

    def add(domain, metric, label, value, unit, grid, source, pop_date, tier, flag="", pop_grid=None, poly_flag=False):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            value = None
        if poly and poly_flag:
            flag = (flag + " " if flag else "") + POLY_FLAG
        rows.append({"agglomeration": agg, "domain": domain, "metric": metric, "label": label,
                     "value": sig(value) if value is not None else None, "unit": unit, "grid": grid,
                     "source": source, "population_date": pop_date, "timetable_date": None, "coverage_share": None,
                     "flag": flag, "tier": tier, "feed_variant": None, "population_grid": pop_grid})

    th = r["townhall"]
    thn = f"ratusz: {th['name']} ({th['osm']})"
    ext_rule = ("Zasięg miejski wg metody Atlas of Urban Expansion (Angel i in.) odtworzonej na GHS-BUILT-S 100 m: "
                "komórka zabudowana ≥ 10 % powierzchni, zabudowa miejska i podmiejska (≥ 25 % komórek zabudowanych "
                "w kole 1 km²), otwarte tereny do 100 m od nich i enklawy < 200 ha; skupisko z ratuszem (przerwy "
                "do 600 m łączone); " + thn + ".")
    src_ext = f"{SRC_BUILT}; {SRC_TH}"
    src_ext_pop = f"{SRC_SCALED}; {SRC_BUILT}; {SRC_TH}"
    e = r["extent"]["b10"]
    for dom, ee, extra_flag in (("urban_extent", e, ext_rule),):
        add(dom, "angel_proximity", "Indeks bliskości Angela (PRX) zasięgu miejskiego, centrum: ratusz",
            ee["prx"], "", GRID_100, src_ext, POP_BUILT, "table",
            extra_flag + " 1 = koło; niższy = teren zabudowany dalej od ratusza niż w kole o tym samym polu.",
            poly_flag=True)
        add(dom, "angel_cohesion", "Indeks spójności Angela zasięgu miejskiego",
            ee["cohesion"], "", GRID_100, src_ext, POP_BUILT, "table",
            extra_flag + " 1 = koło; średnia odległość między wszystkimi parami komórek (dokładnie).")
        add(dom, "urban_extent_area", "Pole zasięgu miejskiego (metoda Angela, GHSL)", ee["area_km2"], "km²",
            GRID_100, src_ext, POP_BUILT, "table", extra_flag)
        add(dom, "urban_extent_pop_share_fua", "Udział ludności FUA mieszkającej w zasięgu miejskim",
            ee["pop_share_of_fua"] * 100, "%", GRID_100, src_ext_pop, POP_SCALED, "table", extra_flag,
            pop_grid=MAIN)
        add(dom, "urban_extent_density", "Gęstość zasięgu miejskiego (ludność / pole zasięgu)", ee["density_gross"],
            "os./km²", GRID_100, src_ext_pop, POP_SCALED, "table", extra_flag, pop_grid=MAIN)
        add(dom, "rho_urban_extent", "Indeks Bertauda ρ na zasięgu miejskim Angela, centrum: ratusz", ee["rho_ext"],
            "", GRID_100, src_ext_pop, POP_SCALED, "table",
            extra_flag + " Średnia odległość mieszkańca od ratusza / ⅔R koła o polu zasięgu; inna maska niż ρ "
            "z kroku density (maska zabudowy ≥ 20 %).", pop_grid=MAIN, poly_flag=True)
        add(dom, "land_over_pop_distance", "Średnia odległość terenu od ratusza / średnia odległość mieszkańca",
            ee["land_over_pop"], "", GRID_100, src_ext_pop, POP_SCALED, "qa",
            "Równe PRX × ρ zasięgu. > 1: mieszkańcy bliżej ratusza niż teren zasięgu (gęstość maleje od centrum).",
            pop_grid=MAIN, poly_flag=True)
        add(dom, "angel_proximity_config_centre", "PRX z centrum z config.yaml zamiast ratusza",
            ee["prx_config_centre"], "", GRID_100, src_ext, POP_BUILT, "qa", "Wrażliwość na centrum.",
            poly_flag=True)
    for key in ("b5", "b20"):
        s = r["extent"][key]
        t = key[1:]
        add("urban_extent", f"angel_proximity_b{t}", f"PRX, wariant: komórka zabudowana ≥ {t} %", s["prx"], "",
            GRID_100, src_ext, POP_BUILT, "qa", "Wrażliwość reguły zasięgu.", poly_flag=True)
        add("urban_extent", f"urban_extent_area_b{t}", f"Pole zasięgu miejskiego, wariant: komórka zabudowana ≥ {t} %",
            s["area_km2"], "km²", GRID_100, src_ext, POP_BUILT, "qa", "Wrażliwość reguły zasięgu.")
    s = r["extent"]["b10_gap0"]
    add("urban_extent", "angel_proximity_gap0", "PRX, wariant: jedno skupisko bez mostkowania przerw",
        s["prx"], "", GRID_100, src_ext, POP_BUILT, "qa", "Wrażliwość reguły zasięgu (bez łączenia przerw ≤ 600 m).",
        poly_flag=True)
    add("urban_extent", "urban_extent_area_gap0", "Pole zasięgu, wariant: jedno skupisko bez mostkowania przerw",
        s["area_km2"], "km²", GRID_100, src_ext, POP_BUILT, "qa", "Wrażliwość reguły zasięgu.")
    if "second" in r["extent"]:
        s = r["extent"]["second"]
        c = s["centre"]
        dom = "urban_extent_" + D_slug(c["city"])
        fl = (f"Zasięg miejski z ratuszem drugiego miasta ({c['city']}: {c['name']}, {c['osm'] or 'brak OSM'}, "
              f"wybór: {c['rule']}); ta sama reguła zasięgu."
              + (" Leży w tym samym skupisku co pierwszy ratusz." if s["same_cluster_as_first"] else ""))
        add(dom, "angel_proximity", f"Indeks bliskości Angela (PRX), centrum: ratusz, {c['city']}", s["prx"], "",
            GRID_100, src_ext, POP_BUILT, "table", fl)
        add(dom, "angel_cohesion", f"Indeks spójności Angela, {c['city']}", s["cohesion"], "", GRID_100, src_ext,
            POP_BUILT, "table", fl)
        add(dom, "urban_extent_area", f"Pole zasięgu miejskiego, {c['city']}", s["area_km2"], "km²", GRID_100,
            src_ext, POP_BUILT, "table", fl)
        add(dom, "rho_urban_extent", f"Indeks Bertauda ρ na zasięgu miejskim, {c['city']}", s["rho_ext"], "",
            GRID_100, src_ext_pop, POP_SCALED, "table", fl, pop_grid=MAIN)
    u = r["uc_extent"]
    ucf = (f"Zasięg = centrum miejskie Eurostatu 2021 (HDENS_CLST_2021, komórki 1 km, ludność oficjalna "
           f"{u['uc_population_official']:,}".replace(",", " ") + f"), w którym leży {thn}; komórki 100 m o środku w nim.")
    add("urban_centre_main", "angel_proximity", "Indeks bliskości Angela (PRX) centrum miejskiego Eurostatu 2021",
        u["prx"], "", GRID_100, f"{SRC_HDENS}; {SRC_TH}", POP_NSP, "table", ucf, poly_flag=True)
    add("urban_centre_main", "angel_cohesion", "Indeks spójności Angela centrum miejskiego Eurostatu 2021",
        u["cohesion"], "", GRID_100, f"{SRC_HDENS}; {SRC_TH}", POP_NSP, "table", ucf)
    add("urban_centre_main", "rho_urban_extent", "Indeks Bertauda ρ na centrum miejskim Eurostatu 2021, centrum: ratusz",
        u["rho_ext"], "", GRID_100, f"{SRC_SCALED}; {SRC_HDENS}; {SRC_TH}", POP_SCALED, "table", ucf,
        pop_grid=MAIN, poly_flag=True)
    add("urban_centre_main", "urban_extent_area", "Pole centrum miejskiego Eurostatu 2021 z ratuszem", u["area_km2"],
        "km²", GRID_100, SRC_HDENS, POP_NSP, "table", ucf)

    # polycentricity
    et = r["eta"]
    samp = density_rows.get(("fua", "eta_mask"))
    add("fua", "poly_eta_mask_t20", "Rozproszenie skupisk gęstości η (Volpati i Barthelemy)", et["eta"], "",
        GRID_100, D.SRC_SCALED_BUILT, POP_SCALED, "table",
        "Średnia odległość między komórkami 100 m powyżej progu LouBar / średnia odległość między wszystkimi "
        f"komórkami maski zabudowy ≥ 20 % (FUA); dokładnie po wszystkich parach. Próg LouBar "
        f"{sig(et['loubar_density'])} os./km², {et['n_hotspots']} komórek z {et['n_cells']}. "
        "Bliżej 0: jedno skupisko; bliżej 1: skupiska rozrzucone po całym obszarze."
        + (f" Wartość z próby 4 000 komórek (krok density): {samp}." if samp is not None else ""), pop_grid=MAIN)
    add("fua", "poly_loubar_cells_t20", "Liczba komórek 100 m powyżej progu LouBar (maska ≥ 20 %)",
        float(et["n_hotspots"]), "", GRID_100, D.SRC_SCALED_BUILT, POP_SCALED, "qa", pop_grid=MAIN)
    for key, h in r["hotspots"].items():
        tier = "table" if key == "main" else "qa"
        tl = f"{int(round(h['threshold'])):,}".replace(",", " ")
        suffix = "" if key == "main" else ("_loubar" if key == "loubar" else f"_{key}")
        th_lab = "próg LouBar" if key == "loubar" else f"≥ {tl} os./km²"
        fl = (f"Skupisko gęstości: spójne (8 sąsiadów) komórki 250 m o gęstości ≥ {tl} os./km² w FUA"
              + (" (próg LouBar komórek 250 m FUA)" if key == "loubar" else "")
              + f"; liczone skupiska z ≥ {HOT_MIN_POP:,} mieszkańców.".replace(",", " "))
        add("fua", f"hotspots_n{suffix}", f"Liczba skupisk gęstości ({th_lab}, ≥ 5 000 mieszkańców)",
            float(h["n_hotspots_min_pop"]), "", GRID_250S, SRC_SCALED, POP_SCALED, tier, fl, pop_grid=MAIN)
        add("fua", f"hotspots_largest_share{suffix}", f"Udział największego skupiska gęstości ({th_lab}) w ludności wszystkich skupisk",
            None if h["largest_share"] is None else h["largest_share"] * 100, "%", GRID_250S, SRC_SCALED, POP_SCALED,
            tier, fl + " Wszystkie skupiska (bez progu ludności) w mianowniku.", pop_grid=MAIN)
        add("fua", f"hotspots_pop_share_fua{suffix}", f"Udział ludności FUA w skupiskach gęstości ({th_lab})",
            None if h["hot_pop_share_of_fua"] is None else h["hot_pop_share_of_fua"] * 100, "%", GRID_250S,
            SRC_SCALED, POP_SCALED, tier, fl, pop_grid=MAIN)
        add("fua", f"hotspots_rank_size_slope{suffix}", f"Nachylenie zależności ranga–wielkość skupisk gęstości ({th_lab})",
            h["rank_size_slope"], "", GRID_250S, SRC_SCALED, POP_SCALED, tier,
            fl + f" MNK ln(ludność) na ln(ranga), n = {h['rank_size_n']}; brak przy < {RANK_MIN_N} skupiskach. "
            "Bliżej 0: skupiska podobnej wielkości; bardziej ujemne: jedno dominuje.", pop_grid=MAIN)
        add("fua", f"hotspots_second_over_largest{suffix}", f"Ludność drugiego skupiska / największego ({th_lab})",
            h["second_over_largest"], "", GRID_250S, SRC_SCALED, POP_SCALED, "qa", fl, pop_grid=MAIN)

    # degree of urbanisation
    simp = ("Centra miejskie: oficjalna warstwa Eurostatu 2021 (HDENS_CLST_2021). Skupiska miejskie: uproszczenie "
            "projektu (komórki ≥ 300 os./km², spójne 8-kierunkowo, ≥ 5 000 mieszkańców, poza centrami), bez "
            "wygładzania i bez poziomu 2 klasyfikacji. Ludność NSP 2021 w komórkach 1 km o środku w obszarze.")
    for dom in ("fua", "core"):
        g = r["degurba"][dom]
        add(dom, "degurba2021_share_urban_centre", "Udział ludności w centrach miejskich (Eurostat 2021)",
            g["uc_official"] * 100, "%", GRID_NSP, f"{SRC_HDENS}; {D.SRC_NSP}", POP_NSP, "table", simp)
        add(dom, "degurba2021_share_urban_cluster", "Udział ludności w skupiskach miejskich poza centrami (uproszczone)",
            g["cluster_hybrid"] * 100, "%", GRID_NSP, f"{SRC_HDENS}; {D.SRC_NSP}", POP_NSP, "table", simp)
        add(dom, "degurba2021_share_rural", "Udział ludności w komórkach wiejskich (uproszczone)",
            g["rural_hybrid"] * 100, "%", GRID_NSP, f"{SRC_HDENS}; {D.SRC_NSP}", POP_NSP, "table", simp)
        add(dom, "degurba_uc_own_minus_official_pp",
            "Różnica udziału w centrach miejskich: klasyfikacja projektu − Eurostat 2021",
            (g["uc_own"] - g["uc_official"]) * 100, "pp", GRID_NSP, f"{SRC_HDENS}; {D.SRC_NSP}", POP_NSP, "qa",
            "Kontrola uproszczonej klasyfikacji z kroku density.")

    # density classes
    for dom in ("fua", "core"):
        c = r["density_classes"][dom]
        fl = ("Gęstość komórki 250 m = mieszkańcy / 0,0625 km²; ludność NSP 2021 rozłożona wzorem GHSL 2020. "
              "Klasy jak warstwa gęstości na mapie.")
        add(dom, "share_residents_ge5000", "Mieszkańcy komórek 250 m o gęstości ≥ 5 000 os./km²",
            c["at_or_above"]["5000"] * 100, "%", GRID_250S, SRC_SCALED, POP_SCALED, "table", fl, pop_grid=MAIN)
        add(dom, "share_residents_ge10000", "Mieszkańcy komórek 250 m o gęstości ≥ 10 000 os./km²",
            c["at_or_above"]["10000"] * 100, "%", GRID_250S, SRC_SCALED, POP_SCALED, "table", fl, pop_grid=MAIN)
        add(dom, "share_residents_lt1000", "Mieszkańcy komórek 250 m o gęstości < 1 000 os./km²",
            (c["share"][0] + c["share"][1]) * 100, "%", GRID_250S, SRC_SCALED, POP_SCALED, "table", fl,
            pop_grid=MAIN)
        add(dom, "median_resident_density_250m", "Gęstość komórki 250 m typowego mieszkańca (mediana)",
            c["median_density"], "os./km²", GRID_250S, SRC_SCALED, POP_SCALED, "table",
            fl + " Połowa mieszkańców mieszka w komórkach gęstszych, połowa w rzadszych.", pop_grid=MAIN)
    return rows


def D_slug(name: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def density_step_values() -> dict:
    """(agg, domain, metric) -> value of the census-scaled rows of metrics_density.json (for comparisons)."""
    raw = json.loads((METRICS / "metrics_density.json").read_text(encoding="utf-8"))["metrics"]
    out = {}
    for m in raw:
        if m.get("population_grid") in (None, MAIN):
            out[(m["agglomeration"], m["domain"], m["metric"])] = m["value"]
    return out


# ------------------------------------------------------------------ outputs

FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]


def write_metrics(rows: list[dict], today: str) -> None:
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["domain"], m["metric"], m["population_grid"] or ""))
    keys = [(m["agglomeration"], m["domain"], m["metric"], m["population_grid"]) for m in rows]
    assert len(keys) == len(set(keys)), "duplicate metric keys"
    write_json(METRICS / "metrics_form.json", {"generated": today, "metrics": rows})
    with open(METRICS / "metrics_form.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


def class_labels() -> list[dict]:
    s = [0] + [int(v) for v in DENSITY_STOPS] + [None]
    nf = lambda v: f"{v:,}".replace(",", " ")  # noqa: E731
    out = []
    for lo, hi in zip(s, s[1:]):
        lab = f"< {nf(hi)}" if lo == 0 else (f"≥ {nf(lo)}" if hi is None else f"{nf(lo)}–{nf(hi)}")
        out.append({"label": lab, "min": lo, "max": hi})
    return out


def write_charts(results: list[dict], today: str) -> None:
    cities = []
    for r in sorted(results, key=lambda r: -r["density_classes"]["fua"]["at_or_above"]["5000"]):
        c = {"id": r["id"], "name": r["name"], "polycentric": r["polycentric"]}
        for dom in ("fua", "core"):
            x = r["density_classes"][dom]
            c[dom] = {"residents": [int(round(v)) for v in x["pop"]], "share": [sig(v) for v in x["share"]],
                      "at_or_above": {k: sig(v) for k, v in x["at_or_above"].items()},
                      "median_density": sig(x["median_density"]), "total": int(round(x["total"]))}
        h = r["hotspots"]["main"]
        c["hotspots"] = {"threshold": HOT_MAIN, "rank_size_slope": sig(h["rank_size_slope"]),
                         "largest_share": sig(h["largest_share"]),
                         "clusters": [{"rank": k["rank"], "residents": int(round(k["pop"])), "gmina": k["gmina"]}
                                      for k in h["clusters"] if k["pop"] >= 1000]}
        cities.append(c)
    write_json(CHARTS / "form.json", {
        "generated": today,
        "title": "Mieszkańcy według gęstości zaludnienia ich komórki 250 m",
        "unit": "udział mieszkańców (0–1); gęstość w os./km²",
        "grid": GRID_250S, "source": SRC_SCALED, "population_date": POP_SCALED, "timetable_date": None,
        "population_grid": MAIN,
        "classes": class_labels(),
        "class_note": "Klasy jak warstwa gęstości na mapie (pipeline.tiles_layers.DENSITY_STOPS); próg 5 000 "
                      "os./km² jak w warstwie gęstość × częstotliwość.",
        "highlight_threshold": 5000,
        "domains": {"fua": "FUA (Eurostat URAU 2021)", "core": "rdzeń (miasta URAU 2021)"},
        "sorted_by": "fua.at_or_above.5000 desc",
        "caveats": ["Gęstość komórki 250 m jest wyższa niż gęstość tej samej zabudowy liczona na 1 km; liczb nie "
                    "porównywać z gęstością ważoną populacją z siatki 1 km.",
                    "Ludność NSP 2021 z komórek 1 km rozłożona wewnątrz komórki wzorem GHS-POP 2020: wielkie osiedla "
                    "mogą być w komórkach 250 m za rzadkie, centra i strefy przemysłowe za gęste.",
                    "Liczeni tylko mieszkańcy, bez miejsc pracy.",
                    "hotspots: skupiska komórek ≥ 10 000 os./km² (8 sąsiadów) w FUA, lista od 1 000 mieszkańców; "
                    "do wykresu ranga–wielkość (oś logarytmiczna)."],
        "cities": cities})


def jsonable(r: dict) -> dict:
    return round_sig(json.loads(json.dumps(r, default=float)), 6)


def main() -> None:
    t0 = time.time()
    today = dt.date.today().isoformat()
    log("degree of urbanisation (national census grid)")
    dg = degurba_official()
    lau = load_lau().to_crs("EPSG:2180")[["LAU_NAME", "geometry"]]
    dens_vals = density_step_values()
    results, rows = [], []
    for agg in sorted(all_agglomeration_ids()):
        r = run_agglomeration(agg, dg, lau)
        results.append(r)
        dv = {(d, m): v for (a, d, m), v in dens_vals.items() if a == agg}
        r["density_step"] = {k: dv.get(k) for k in (("fua", "rho_t20"), ("core", "rho_t10"), ("core", "rho_t20"),
                                                    ("fua", "eta_mask"), ("fua", "rho_nearest_t20"))}
        r["density_step"] = {f"{d}:{m}": v for (d, m), v in r["density_step"].items()}
        rows += metric_rows(r, dv)
        write_json(OUT / f"{agg}.json", jsonable(r))
    write_json(OUT / "degurba_national.json", round_sig(dg["reasons"], 6))
    write_metrics(rows, today)
    write_charts(results, today)
    extra = {"built_pixel_share": BUILT_PIXEL_SHARE, "built_pixel_sensitivity": list(BUILT_PIXEL_SENS),
             "walk_circle_m": WALK_CIRCLE_M, "urban_min": URBAN_MIN, "suburban_min": SUBURBAN_MIN,
             "captured_max_ha": CAPTURED_MAX_HA, "extent_gap_m": 2 * EXTENT_GAP_CELLS * 100,
             "hotspot_threshold": HOT_MAIN, "hotspot_sensitivity": list(HOT_SENS),
             "hotspot_min_pop": HOT_MIN_POP, "density_stops": list(DENSITY_STOPS),
             "population_dates": {"census": POP_NSP, "census_scaled": POP_SCALED, "built": POP_BUILT},
             "eurostat_hdens_2021": {"path": "data/raw/eurostat_hdens_2021/HDENS-CLST-2021.zip",
                                     "source": json.loads((RAW / "eurostat_hdens_2021" / "SOURCE.json")
                                                          .read_text(encoding="utf-8"))},
             "townhalls": "data/interim/density/townhalls_osm.csv (OSM 2026-11-22, amenity=townhall)",
             "outputs": ["results/metrics/metrics_form.csv", "results/metrics/metrics_form.json",
                         "results/charts/form.json"]}
    mp = write_meta(OUT, STEP, inputs=INPUT_IDS, started=t0, extra=extra)
    for d in (METRICS, CHARTS):
        shutil.copyfile(mp, d / "_meta_form.json")
    log(f"done: {len(rows)} rows ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
