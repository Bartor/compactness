"""Population grids for the transit measures (phase 2-3), 250 m in EPSG:2180.

Two variants (config ``population_grid_variants``):

* ``ghsl_raw``           GHS-POP R2023A epoch 2020 on the 250 m grid, unchanged (pipeline.grid250).
* ``ghsl_census_scaled`` the same spatial pattern rescaled so that every 1 km census cell
                         (NSP 2021, field RES, usually-resident population, 31.03.2021) sums to its
                         census value.

Method (census_scaled)
* The census cells are the EU LAEA (EPSG:3035) 1 km grid; the 250 m grid is EPSG:2180, so the two
  do not align.  The scaling is therefore done on the GHSL source pixels (100 m, Mollweide), which
  are much smaller than a census cell, and the result is re-aggregated to 250 m with the same
  area-preserving GDAL kernel as pipeline.grid250 (Resampling.sum, exact transformer).
* Each 100 m pixel whose centre lies in Poland (census footprint) is split into 4 x 4 sub-pixels;
  every sub-pixel centre is projected to EPSG:3035 and assigned to the census cell containing it.
  A pixel's population is assumed uniform inside the pixel, so a pixel straddling a census-cell
  edge is split between the cells in proportion to area (1/16 resolution).
* G_j = GHSL population assigned to census cell j; C_j = census RES.
  - C_j = 0                     -> every GHSL person in j is removed (scaled value 0);
  - C_j > 0 and G_j > 0         -> factor C_j / G_j applied to every sub-pixel in j;
  - C_j > 0 and G_j = 0         -> fallback 1: C_j spread in proportion to GHS-BUILT-S 2020
                                   built-up surface of the sub-pixels in j;
                                   fallback 2 (no built-up surface either): spread uniformly over
                                   20 x 20 points of the census cell (clipped polygon).
  The number of people placed by each fallback is counted.
* Pixels outside Poland keep their raw GHSL value (no census there); they only matter at the
  western/eastern borders of phase-2 buffers.

Checks (data/interim/popgrid/qa.json, results/qa/transit/popgrid_*.png)
1. per census cell: the scaled 100 m pixels summed by sub-pixel assignment equal C_j (identity by
   construction; max abs error reported);
2. per census cell after re-aggregation to 250 m: each 250 m cell is split into 5 x 5 sub-cells
   assigned to census cells; the residual against C_j is the error introduced by 250 m cells that
   straddle census edges (RMSE, max, per FUA);
3. per FUA / core: census total (cell centroid rule, as in metrics.csv), census total weighted by
   area share, scaled 250 m total (cell centre rule), raw 250 m total;
4. pictures: raw, scaled and scaled/raw ratio in 20 x 20 km windows (striping / seam check).

Limits: the correction fixes the level at 1 km; inside a census cell the GHSL pattern is kept,
including its errors (e.g. people placed on industrial roofs next to a housing estate in the same
1 km cell).  The 250 m cells straddling census edges mix two factors (check 2).

Outputs (data/interim/popgrid/)
* pop_<variant>_250m_epsg2180.tif     float32, nodata -1
* cells_<agglomeration>.parquet       cells with pop > 0 in either variant inside FUA + 15 km:
  cell_id, x, y, pop_ghsl_raw, pop_ghsl_census_scaled, in_poland, in_fua, in_core
* qa.json, fallback_cells.csv, _meta.json

Run: python -m pipeline.popgrid
"""
from __future__ import annotations

import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer
from rasterio import features
from rasterio.warp import Resampling, reproject

from pipeline.boundaries import all_agglomeration_ids, load_agglomeration
from pipeline.common import INTERIM, RAW, RESULTS, round_sig, write_json, write_meta

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = INTERIM / "popgrid"
QA_DIR = RESULTS / "qa" / "transit" / "frequent"
GHS_POP_VRT = RAW / "ghsl" / "ghs_pop" / "ghs_pop_2020_poland.vrt"
GHS_BUILT_VRT = RAW / "ghsl" / "ghs_built_s" / "ghs_built_s_2020_poland.vrt"
NSP_SHP = RAW / "nsp2021" / "extracted" / "GRID_NSP2021_RES.shp"
GRID250 = INTERIM / "grid250" / "ghs_pop_2020_250m_epsg2180.tif"
PL_MASK_100 = INTERIM / "density" / "poland_mask_100m_moll.tif"
VARIANTS = ["ghsl_census_scaled", "ghsl_raw"]
NSUB = 4                    # sub-pixels per 100 m pixel side
NSUB250 = 5                 # sub-cells per 250 m cell side (check 2)
NUNIF = 20                  # points per census-cell side for the uniform fallback
RES = 250.0
CHUNK = 1_000_000
INPUT_IDS = ["ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20", "ghs_built_s_2020_R3_C20",
             "ghs_built_s_2020_R4_C20", "nsp2021_grid_1km_shp", "urau_2021_100k_all", "lau_2021_01m"]
MOLL_TO_3035 = Transformer.from_crs("ESRI:54009", "EPSG:3035", always_xy=True)
T3035_TO_MOLL = Transformer.from_crs("EPSG:3035", "ESRI:54009", always_xy=True)
T2180_TO_3035 = Transformer.from_crs("EPSG:2180", "EPSG:3035", always_xy=True)
QA_WINDOWS = {   # EPSG:2180 boxes, 20 x 20 km
    "warszawa": (627000.0, 476000.0, 647000.0, 496000.0),
    "krakow": (560000.0, 236000.0, 580000.0, 256000.0),
}


def tif_path(variant: str) -> str:
    return str(OUT / f"pop_{variant}_250m_epsg2180.tif")


# ------------------------------------------------------------------ census lookup
def census_table() -> tuple[gpd.GeoDataFrame, np.ndarray, int, int]:
    """Census cells in EPSG:3035 with a (row, col) lookup array of the 1 km squares."""
    g = gpd.read_file(NSP_SHP, columns=["CODE", "RES"])
    g = g.to_crs("EPSG:3035")
    g["E"] = g.CODE.str.extract(r"E(\d+)$")[0].astype(np.int64)
    g["N"] = g.CODE.str.extract(r"N(\d+)E")[0].astype(np.int64)
    g = g.sort_values("CODE").reset_index(drop=True)
    e0, n0 = int(g.E.min()), int(g.N.min())
    w, h = (int(g.E.max()) - e0) // 1000 + 1, (int(g.N.max()) - n0) // 1000 + 1
    lut = np.full((h, w), -1, dtype=np.int32)
    lut[((g.N.values - n0) // 1000), ((g.E.values - e0) // 1000)] = np.arange(len(g), dtype=np.int32)
    return g, lut, e0, n0


def lookup(x3035: np.ndarray, y3035: np.ndarray, lut, e0, n0) -> np.ndarray:
    c = np.floor((x3035 - e0) / 1000).astype(np.int64)
    r = np.floor((y3035 - n0) / 1000).astype(np.int64)
    ok = (c >= 0) & (c < lut.shape[1]) & (r >= 0) & (r < lut.shape[0])
    out = np.full(len(c), -1, dtype=np.int32)
    out[ok] = lut[r[ok], c[ok]]
    return out


def subcells_of_pixels(rows, cols, tr, lut, e0, n0) -> np.ndarray:
    """(n_pixels, NSUB**2) census index of every sub-pixel centre (-1 = no census cell)."""
    k = (np.arange(NSUB) + 0.5) / NSUB
    du, dv = np.meshgrid(k, k)
    du, dv = du.ravel(), dv.ravel()
    X = tr.c + (cols[:, None] + du[None, :]) * tr.a
    Y = tr.f + (rows[:, None] + dv[None, :]) * tr.e
    x, y = MOLL_TO_3035.transform(X.ravel(), Y.ravel())
    return lookup(x, y, lut, e0, n0).reshape(len(rows), NSUB * NSUB)


# ------------------------------------------------------------------ main computation
def scale_100m() -> tuple[np.ndarray, np.ndarray, rasterio.Affine, object, dict, pd.DataFrame]:
    with rasterio.open(GHS_POP_VRT) as s:
        pop = s.read(1)
        tr, crs, nd = s.transform, s.crs, s.nodata
    with rasterio.open(GHS_BUILT_VRT) as s:
        built = s.read(1).astype(np.float64)
        bnd = s.nodata
    built[built == bnd] = 0.0
    with rasterio.open(PL_MASK_100) as s:
        plm = s.read(1).astype(bool)
    nodata = pop == nd
    popv = np.where(nodata, 0.0, pop)
    cen, lut, e0, n0 = census_table()
    C = cen.RES.values.astype(np.float64)
    nc = len(cen)

    cand = plm & ((popv > 0) | (built > 0))
    rr, cc = np.nonzero(cand)
    print(f"candidate pixels: {len(rr):,}")
    G = np.zeros(nc)
    B = np.zeros(nc)
    sub = np.empty((len(rr), NSUB * NSUB), dtype=np.int32)
    for i in range(0, len(rr), CHUNK):
        s_ = slice(i, i + CHUNK)
        sub[s_] = subcells_of_pixels(rr[s_], cc[s_], tr, lut, e0, n0)
    pv = popv[rr, cc] / NSUB ** 2
    bv = built[rr, cc] / NSUB ** 2
    flat = sub.ravel()
    okf = flat >= 0
    G += np.bincount(flat[okf], weights=np.repeat(pv, NSUB ** 2)[okf], minlength=nc)
    B += np.bincount(flat[okf], weights=np.repeat(bv, NSUB ** 2)[okf], minlength=nc)
    # GHSL population of in-Poland pixels whose sub-pixel falls in no census square (coast / border)
    lost_raw = float(np.repeat(pv, NSUB ** 2)[~okf].sum())

    factor = np.where(G > 0, C / np.where(G > 0, G, 1.0), 0.0)
    fb_built = (C > 0) & (G == 0) & (B > 0)
    fb_unif = (C > 0) & (G == 0) & (B == 0)
    bfac = np.where(fb_built, C / np.where(B > 0, B, 1.0), 0.0)

    # scaled value per candidate pixel: sum over its sub-pixels
    sidx = np.where(sub >= 0, sub, 0)
    valid = sub >= 0
    per_sub = (pv[:, None] * factor[sidx] + bv[:, None] * bfac[sidx]) * valid
    scaled = np.zeros_like(popv)
    scaled[rr, cc] = per_sub.sum(axis=1)
    # sub-pixels in no census square keep their raw population (cannot be scaled)
    scaled[rr, cc] += (pv[:, None] * ~valid).sum(axis=1)
    # pixels outside Poland: raw
    outside = ~plm
    scaled[outside] = popv[outside]

    # fallback 2: uniform over the census cell
    unif_rows = []
    if fb_unif.any():
        k = (np.arange(NUNIF) + 0.5) / NUNIF * 1000
        du, dv = np.meshgrid(k, k)
        for j in np.flatnonzero(fb_unif):
            e, n = cen.E.values[j], cen.N.values[j]
            x, y = e + du.ravel(), n + dv.ravel()
            inside = shapely.contains_xy(cen.geometry.values[j], x, y)
            if not inside.any():
                inside[:] = True
            mx, my = T3035_TO_MOLL.transform(x[inside], y[inside])
            ci = np.floor((mx - tr.c) / tr.a).astype(int)
            ri = np.floor((my - tr.f) / tr.e).astype(int)
            np.add.at(scaled, (ri, ci), C[j] / inside.sum())
            unif_rows.append({"CODE": cen.CODE.values[j], "res": int(C[j]), "fallback": "uniform"})
    fb_rows = [{"CODE": cen.CODE.values[j], "res": int(C[j]), "fallback": "built_s"}
               for j in np.flatnonzero(fb_built)] + unif_rows
    fb = pd.DataFrame(fb_rows, columns=["CODE", "res", "fallback"]).sort_values("CODE").reset_index(drop=True)

    # check 1: the sub-pixel terms summed per census cell equal C_j
    back = np.bincount(sidx[valid], weights=per_sub[valid], minlength=nc)
    back[fb_unif] += C[fb_unif]   # uniform fallback is placed outside the candidate set
    qa = {
        "candidate_pixels_100m": int(len(rr)),
        "census_cells": int(nc), "census_total": float(C.sum()),
        "ghsl_total_in_poland_pixels": float(popv[plm].sum()),
        "ghsl_assigned_to_census_cells": float(G.sum()),
        "ghsl_in_poland_pixels_outside_census_squares": lost_raw,
        "cells_census_zero_ghsl_positive": int(((C == 0) & (G > 0)).sum()),
        "persons_removed_census_zero": float(G[C == 0].sum()),
        "fallback_built_cells": int(fb_built.sum()), "fallback_built_persons": float(C[fb_built].sum()),
        "fallback_uniform_cells": int(fb_unif.sum()), "fallback_uniform_persons": float(C[fb_unif].sum()),
        "check1_max_abs_cell_error": float(np.abs(back - C).max()),
        "check1_sum_error": float(back.sum() - C.sum()),
        "factor_quantiles_populated": {str(q): float(np.quantile(factor[(G > 0) & (C > 0)], q))
                                       for q in (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)},
        "scaled_total_all_pixels": float(scaled.sum()),
    }
    scaled_out = np.where(nodata & (scaled == 0), nd, scaled)
    return scaled_out, popv, tr, crs, qa, fb


def to_250(arr100: np.ndarray, tr100, crs100, nd) -> tuple[np.ndarray, rasterio.Affine]:
    with rasterio.open(GRID250) as s:
        tr, h, w = s.transform, s.height, s.width
    dst = np.full((h, w), -1.0)
    reproject(arr100, dst, src_transform=tr100, src_crs=crs100, src_nodata=nd, dst_transform=tr,
              dst_crs="EPSG:2180", dst_nodata=-1.0, resampling=Resampling.sum, num_threads=1, tolerance=0.0)
    return dst, tr


def write_tif(path, arr, transform, note: str) -> None:
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype="float32",
                crs="EPSG:2180", transform=transform, nodata=-1.0, compress="deflate", predictor=3,
                tiled=True, blockxsize=512, blockysize=512)
    with rasterio.open(path, "w", **prof) as d:
        d.write(arr.astype("float32"), 1)
        d.update_tags(source=note, units="persons per 250 m cell")


def back_to_census(p250: np.ndarray, tr, lut, e0, n0, nc) -> np.ndarray:
    """Check 2: 250 m cells split into NSUB250^2 sub-cells, summed into census cells."""
    rr, cc = np.nonzero(p250 > 0)
    k = (np.arange(NSUB250) + 0.5) / NSUB250
    du, dv = np.meshgrid(k, k)
    du, dv = du.ravel(), dv.ravel()
    out = np.zeros(nc)
    for i in range(0, len(rr), CHUNK // 4):
        r, c = rr[i:i + CHUNK // 4], cc[i:i + CHUNK // 4]
        X = tr.c + (c[:, None] + du[None, :]) * RES
        Y = tr.f - (r[:, None] + dv[None, :]) * RES
        x, y = T2180_TO_3035.transform(X.ravel(), Y.ravel())
        j = lookup(x, y, lut, e0, n0)
        wv = np.repeat(p250[r, c] / NSUB250 ** 2, NSUB250 ** 2)
        ok = j >= 0
        out += np.bincount(j[ok], weights=wv[ok], minlength=nc)
    return out


def poly_mask(geom, transform, shape) -> np.ndarray:
    return features.geometry_mask([geom], out_shape=shape, transform=transform, invert=True, all_touched=False)


def cells_tables(raw: np.ndarray, scl: np.ndarray, tr) -> dict:
    with rasterio.open(INTERIM / "grid250" / "poland_mask_250m_epsg2180.tif") as s:
        pm = s.read(1) == 1
    out = {}
    h, w = raw.shape
    for agg in sorted(all_agglomeration_ids()):
        a = load_agglomeration(agg)
        bx = a["buffered"].bounds
        c0 = max(int(np.floor((bx[0] - tr.c) / RES)), 0); c1 = min(int(np.ceil((bx[2] - tr.c) / RES)), w)
        r0 = max(int(np.floor((tr.f - bx[3]) / RES)), 0); r1 = min(int(np.ceil((tr.f - bx[1]) / RES)), h)
        sr, ss = raw[r0:r1, c0:c1], scl[r0:r1, c0:c1]
        wt = rasterio.Affine(RES, 0, tr.c + c0 * RES, 0, -RES, tr.f - r0 * RES)
        m_b = poly_mask(a["buffered"], wt, sr.shape)
        sel = m_b & ((sr > 0) | (ss > 0))
        r_, c_ = np.nonzero(sel)
        x = wt.c + (c_ + 0.5) * RES
        y = wt.f - (r_ + 0.5) * RES
        df = pd.DataFrame({
            "cell_id": [f"E{int(xx - RES / 2)}N{int(yy - RES / 2)}" for xx, yy in zip(x, y)],
            "x": x, "y": y,
            "pop_ghsl_raw": sr[sel].astype(np.float64), "pop_ghsl_census_scaled": ss[sel].astype(np.float64),
            "in_poland": pm[r0:r1, c0:c1][sel],
            "in_fua": poly_mask(a["fua"], wt, sr.shape)[sel],
            "in_core": poly_mask(a["core"], wt, sr.shape)[sel],
        }).sort_values(["y", "x"], ascending=[False, True]).reset_index(drop=True)
        df.to_parquet(OUT / f"cells_{agg}.parquet", index=False)
        out[agg] = {"cells": int(len(df)),
                    **{f"{dom}_{v}": float(df.loc[df[f"in_{dom}"], f"pop_{v}"].sum())
                       for dom in ("fua", "core") for v in VARIANTS}}
    return out


def totals_check(scl, raw, tr, cen3035: gpd.GeoDataFrame) -> dict:
    """Check 3 per FUA / core."""
    from pipeline.density import census, census_in
    c = census()
    out = {}
    for agg in sorted(all_agglomeration_ids()):
        a = load_agglomeration(agg)
        row = {}
        for dom in ("fua", "core"):
            g = a[dom]
            idx = census_in(g)
            nsp = float(c.RES.values[idx].sum())
            cand = c.iloc[np.sort(c.sindex.query(g, predicate="intersects"))]
            sh = cand.geometry.intersection(g).area / cand.geometry.area
            nsp_aw = float((cand.RES.values * sh.values).sum())
            bx = g.bounds
            c0 = int(np.floor((bx[0] - tr.c) / RES)); c1 = int(np.ceil((bx[2] - tr.c) / RES))
            r0 = int(np.floor((tr.f - bx[3]) / RES)); r1 = int(np.ceil((tr.f - bx[1]) / RES))
            wt = rasterio.Affine(RES, 0, tr.c + c0 * RES, 0, -RES, tr.f - r0 * RES)
            m = poly_mask(g, wt, (r1 - r0, c1 - c0))
            s_ = float(np.where(scl[r0:r1, c0:c1] > 0, scl[r0:r1, c0:c1], 0)[m].sum())
            r_ = float(np.where(raw[r0:r1, c0:c1] > 0, raw[r0:r1, c0:c1], 0)[m].sum())
            row[dom] = {"census_centroid_rule": nsp, "census_area_weighted": nsp_aw, "scaled_250m": s_,
                        "raw_250m": r_, "scaled_vs_census_aw": s_ / nsp_aw - 1, "scaled_vs_census_centroid": s_ / nsp - 1,
                        "raw_vs_census_aw": r_ / nsp_aw - 1}
        out[agg] = row
    return out


def qa_pictures(raw, scl, tr) -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(len(QA_WINDOWS), 3, figsize=(16, 5.4 * len(QA_WINDOWS)))
    for row, (name, bx) in zip(axs, QA_WINDOWS.items()):
        c0 = int((bx[0] - tr.c) / RES); r0 = int((tr.f - bx[3]) / RES)
        n = int((bx[2] - bx[0]) / RES)
        a = np.clip(raw[r0:r0 + n, c0:c0 + n], 0, None)
        b = np.clip(scl[r0:r0 + n, c0:c0 + n], 0, None)
        vmax = np.percentile(np.r_[a.ravel(), b.ravel()], 99.5) / 0.0625
        for ax, arr, t in ((row[0], a, "GHSL 2020 surowy"), (row[1], b, "GHSL przeskalowany do NSP 2021 (1 km)")):
            im = ax.imshow(arr / 0.0625, cmap="magma", vmin=0, vmax=vmax)
            fig.colorbar(im, ax=ax, shrink=0.8, label="os./km²")
            ax.set_title(f"{name}: {t}", fontsize=9)
        ratio = np.where(a > 5, b / np.where(a > 0, a, 1), np.nan)
        im = row[2].imshow(np.log2(ratio), cmap="RdBu_r", vmin=-2, vmax=2)
        fig.colorbar(im, ax=row[2], shrink=0.8, label="log2(przeskalowany / surowy)")
        row[2].set_title(f"{name}: współczynnik (komórki > 5 os.); widoczne kwadraty 1 km to cecha metody", fontsize=9)
        for ax in row:
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Siatka 250 m (EPSG:2180): GHSL 2020 vs GHSL przeskalowany do NSP 2021, okna 20×20 km", fontsize=10)
    fig.savefig(QA_DIR / "popgrid_windows.png", dpi=100, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    scaled100, popv, tr100, crs100, qa, fb = scale_100m()
    print(f"scaled 100 m in {time.time() - t0:.0f} s", {k: v for k, v in qa.items() if not isinstance(v, dict)})
    s250, tr = to_250(scaled100, tr100, crs100, -200.0)
    del scaled100, popv
    with rasterio.open(GRID250) as s:
        raw250 = s.read(1).astype(np.float64)
    write_tif(tif_path("ghsl_census_scaled"), s250, tr,
              "GHS-POP R2023A E2020 pattern rescaled to NSP 2021 1 km census cells (RES), see pipeline.popgrid")
    write_tif(tif_path("ghsl_raw"), raw250, tr, "GHS-POP R2023A E2020 on 250 m (copy of grid250)")
    # float32 as stored
    s250 = np.where(s250 < 0, -1.0, s250.astype(np.float32).astype(np.float64))
    cen, lut, e0, n0 = census_table()
    C = cen.RES.values.astype(np.float64)
    back = back_to_census(np.clip(s250, 0, None), tr, lut, e0, n0, len(cen))
    d = back - C
    pop_cells = C > 0
    qa["check2_250m_vs_census"] = {
        "sum_250m_in_census_squares": float(back.sum()), "sum_census": float(C.sum()),
        "rmse_persons": float(np.sqrt((d ** 2).mean())),
        "rmse_rel_to_mean_populated_cell": float(np.sqrt((d ** 2).mean()) / C[pop_cells].mean()),
        "mean_abs_rel_err_cells_ge_500": float(np.mean(np.abs(d[C >= 500]) / C[C >= 500])),
        "p95_abs_rel_err_cells_ge_500": float(np.quantile(np.abs(d[C >= 500]) / C[C >= 500], 0.95)),
        "max_abs_persons": float(np.abs(d).max()),
        "share_population_misplaced_across_census_edges": float(0.5 * np.abs(d).sum() / C.sum()),
    }
    rawc = back_to_census(np.clip(raw250, 0, None), tr, lut, e0, n0, len(cen))
    dr = rawc * C.sum() / rawc.sum() - C
    qa["check2_raw_for_comparison"] = {"share_population_misplaced_raw_vs_census": float(0.5 * np.abs(dr).sum() / C.sum())}
    qa["check3_totals"] = totals_check(s250, raw250, tr, cen)
    qa["cells_tables"] = cells_tables(np.clip(raw250, 0, None), np.clip(s250, 0, None), tr)
    qa_pictures(raw250, s250, tr)
    fb.to_csv(OUT / "fallback_cells.csv", index=False, encoding="utf-8", lineterminator="\n")
    write_json(OUT / "qa.json", round_sig(qa, 6))
    write_meta(OUT, "popgrid", inputs=INPUT_IDS, started=t0, extra={
        "variants": VARIANTS, "crs": "EPSG:2180", "res_m": RES,
        "population_date": {"ghsl_raw": "2020 (GHSL epoch, model)",
                            "ghsl_census_scaled": "2021-03-31 (NSP 2021 level at 1 km; GHSL 2020 pattern inside)"},
        "note": ("ghsl_census_scaled: GHS-POP 100 m pixels split into 4x4 sub-pixels, assigned to EU LAEA census "
                 "cells, scaled by C_j/G_j, fallbacks GHS-BUILT-S then uniform; re-aggregated to 250 m with GDAL "
                 "Resampling.sum (exact transformer)."),
        "outputs": sorted(p.name for p in OUT.iterdir() if p.name != "_meta.json"),
    })
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
