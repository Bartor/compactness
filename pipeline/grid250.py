"""GHS-POP 2020 on a 250 m grid in EPSG:2180: a reusable product (density layer, future
accessibility origins).

Method
* Source: GHS-POP R2023A, epoch 2020, 100 m, Mollweide (ESRI:54009), float64, nodata -200.
* Target: 250 m cells in EPSG:2180, edges at multiples of 250 m (the grid origin is a multiple
  of 1 km), extent = census-grid footprint of Poland plus every agglomeration's FUA + 15 km
  buffer, rounded outwards to 1 km.
* Resampling: ``rasterio.warp.reproject`` with ``Resampling.sum`` (GDAL warper, area-weighted
  sum of contributing source pixels) and ``tolerance=0`` (exact coordinate transformer).  With
  the default approximate transformer (0.125 source px) the result showed +-100-person dipoles
  per 250 m cell against the exact reference (RMSE ~19 persons); with tolerance 0 the RMSE is
  ~0.5 persons, i.e. at the level of the reference's own sampling error.  A naive reassignment of 100 m centres to 250 m cells
  would give 4-9 source cells per target cell and visible striping; the sum kernel splits
  each source pixel between the target cells it overlaps.
* Checks (written to data/interim/grid250/qa.json and results/qa/density/grid250_*.png):
  1. totals: whole grid vs source pixels whose centre falls in the grid; per FUA / core: the
     250 m cells with centre in the polygon vs the 100 m cells with centre in the polygon
     (both are centre-in-polygon rules, so part of the difference is boundary assignment);
  2. an exact reference in one window (Warsaw centre, 30 x 30 km): every 100 m source pixel is
     split into 20 x 20 sub-pixels, their centres are projected to EPSG:2180 and binned;
     the GDAL result is compared cell by cell;
  3. a picture: the GDAL sum next to the naive centroid reassignment (moire check).
* ``poland`` mask: 250 m cell whose centre lies in a census-grid cell (the census grid is
  clipped to the national border and coast), so foreign GHSL population can be excluded.

Outputs (data/interim/grid250/)
* ghs_pop_2020_250m_epsg2180.tif  float32, nodata -1 (sea / outside the source)
* poland_mask_250m_epsg2180.tif   uint8 (1 = centre in Poland)
* cells_<agglomeration>.parquet   populated cells (pop > 0) inside FUA + 15 km buffer:
  cell_id, x, y (cell centre, EPSG:2180), pop, in_poland, in_fua, in_core, in_buffer
* qa.json, _meta.json

Run: python -m pipeline.grid250
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
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

from pipeline.boundaries import all_agglomeration_ids, load_agglomeration
from pipeline.common import INTERIM, RAW, RESULTS, round_sig, write_json, write_meta

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = INTERIM / "grid250"
QA_DIR = RESULTS / "qa" / "density"
GHS_POP_VRT = RAW / "ghsl" / "ghs_pop" / "ghs_pop_2020_poland.vrt"
NSP_SHP = RAW / "nsp2021" / "extracted" / "GRID_NSP2021_RES.shp"
POP_TIF = OUT / "ghs_pop_2020_250m_epsg2180.tif"
MASK_TIF = OUT / "poland_mask_250m_epsg2180.tif"
RES = 250.0
NODATA_OUT = -1.0
INPUT_IDS = ["ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20", "nsp2021_grid_1km_shp",
             "urau_2021_100k_all", "lau_2021_01m"]
TO_2180 = Transformer.from_crs("ESRI:54009", "EPSG:2180", always_xy=True)
QA_WINDOW = (622000.0, 471000.0, 652000.0, 501000.0)   # Warsaw centre, 30 x 30 km, EPSG:2180


def target_grid() -> tuple[rasterio.Affine, int, int]:
    nsp = gpd.read_file(NSP_SHP, columns=["RES"])
    b = list(nsp.total_bounds)
    for a in all_agglomeration_ids():
        bb = load_agglomeration(a)["buffered"].bounds
        b = [min(b[0], bb[0]), min(b[1], bb[1]), max(b[2], bb[2]), max(b[3], bb[3])]
    x0, y0 = np.floor(b[0] / 1000) * 1000, np.floor(b[1] / 1000) * 1000
    x1, y1 = np.ceil(b[2] / 1000) * 1000, np.ceil(b[3] / 1000) * 1000
    w, h = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))
    return from_origin(x0, y1, RES, RES), w, h


def build_raster(src_arr, src, transform, w, h) -> np.ndarray:
    dst = np.full((h, w), NODATA_OUT, dtype=np.float64)
    reproject(src_arr, dst, src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
              dst_transform=transform, dst_crs="EPSG:2180", dst_nodata=NODATA_OUT,
              resampling=Resampling.sum, num_threads=1,
              tolerance=0.0)   # exact transformer: the default 0.125 px approximation leaves +-100-person dipoles
    return dst


def write_tif(path, arr, transform, dtype, nodata):
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype=dtype,
                crs="EPSG:2180", transform=transform, nodata=nodata, compress="deflate",
                predictor=3 if dtype.startswith("float") else 2, tiled=True, blockxsize=512, blockysize=512)
    with rasterio.open(path, "w", **prof) as d:
        d.write(arr.astype(dtype), 1)
        d.update_tags(source="GHS-POP R2023A E2020 100 m (JRC), resampled with GDAL Resampling.sum",
                      units="persons per 250 m cell", crs_note="EPSG:2180, cell edges at multiples of 250 m")


def poland_mask(transform, w, h) -> np.ndarray:
    nsp = gpd.read_file(NSP_SHP, columns=["RES"])
    shapes = ((g, 1) for g in nsp.geometry.values)
    return features.rasterize(shapes, out_shape=(h, w), transform=transform, fill=0,
                              all_touched=False, dtype="uint8")


def poly_mask(geom, transform, shape) -> np.ndarray:
    return features.geometry_mask([geom], out_shape=shape, transform=transform, invert=True,
                                  all_touched=False)


def source_centre_sum(src_arr, src, x0, y0, x1, y1) -> float:
    """Sum of source pixels whose centre (projected to EPSG:2180) lies in the box."""
    T = Transformer.from_crs("EPSG:2180", "ESRI:54009", always_xy=True)
    xs, ys = T.transform([x0, x1, x0, x1], [y0, y0, y1, y1])
    r0, c0 = src.index(min(xs) - 30000, max(ys) + 30000)
    r1, c1 = src.index(max(xs) + 30000, min(ys) - 30000)
    r0, c0 = max(r0, 0), max(c0, 0)
    sub = src_arr[r0:r1, c0:c1]
    rows, cols = np.mgrid[r0:r0 + sub.shape[0], c0:c0 + sub.shape[1]]
    X = src.transform.c + (cols + 0.5) * src.transform.a
    Y = src.transform.f + (rows + 0.5) * src.transform.e
    px, py = TO_2180.transform(X.ravel(), Y.ravel())
    v = sub.ravel()
    m = (px >= x0) & (px < x1) & (py >= y0) & (py < y1) & (v != src.nodata)
    return float(v[m].sum())


def window_reference(src_arr, src, box, nsub=20):
    """Exact-ish reference: split source pixels into nsub x nsub sub-pixels and bin them."""
    x0, y0, x1, y1 = box
    T = Transformer.from_crs("EPSG:2180", "ESRI:54009", always_xy=True)
    xs, ys = T.transform([x0, x1, x0, x1], [y0, y0, y1, y1])
    r0, c0 = src.index(min(xs) - 1000, max(ys) + 1000)
    r1, c1 = src.index(max(xs) + 1000, min(ys) - 1000)
    sub = src_arr[r0:r1, c0:c1].astype(np.float64)
    sub = np.where(sub == src.nodata, 0.0, sub)
    w, h = int((x1 - x0) / RES), int((y1 - y0) / RES)
    ref = np.zeros((h, w))
    naive = np.zeros((h, w))
    rows, cols = np.mgrid[r0:r0 + sub.shape[0], c0:c0 + sub.shape[1]]
    v = sub.ravel()
    # naive: whole pixel to the cell containing its centre
    X = src.transform.c + (cols.ravel() + 0.5) * src.transform.a
    Y = src.transform.f + (rows.ravel() + 0.5) * src.transform.e
    px, py = TO_2180.transform(X, Y)
    ci, ri = np.floor((px - x0) / RES).astype(int), np.floor((y1 - py) / RES).astype(int)
    ok = (ci >= 0) & (ci < w) & (ri >= 0) & (ri < h)
    np.add.at(naive, (ri[ok], ci[ok]), v[ok])
    for i in range(nsub):
        for j in range(nsub):
            X = src.transform.c + (cols.ravel() + (j + 0.5) / nsub) * src.transform.a
            Y = src.transform.f + (rows.ravel() + (i + 0.5) / nsub) * src.transform.e
            px, py = TO_2180.transform(X, Y)
            ci, ri = np.floor((px - x0) / RES).astype(int), np.floor((y1 - py) / RES).astype(int)
            ok = (ci >= 0) & (ci < w) & (ri >= 0) & (ri < h)
            np.add.at(ref, (ri[ok], ci[ok]), v[ok] / nsub ** 2)
    return ref, naive


def qa_picture(gdal_win, naive, ref) -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(1, 3, figsize=(16, 5.6))
    vmax = np.percentile(ref, 99.5) / 0.0625
    for ax, arr, t in zip(axs, [gdal_win, naive, gdal_win - ref],
                          ["GDAL Resampling.sum (produkt)", "naiwne przypisanie środków 100 m (dla porównania)",
                           "produkt minus referencja 20x20 podpikseli"]):
        if "minus" in t:
            lim = max(np.abs(arr).max(), 1e-9)
            im = ax.imshow(arr, cmap="RdBu_r", vmin=-lim, vmax=lim)
            fig.colorbar(im, ax=ax, shrink=0.8, label="osoby / komórka 250 m")
        else:
            im = ax.imshow(arr / 0.0625, cmap="magma", vmin=0, vmax=vmax)
            fig.colorbar(im, ax=ax, shrink=0.8, label="os./km²")
        ax.set_title(t, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Siatka 250 m (EPSG:2180) z GHS-POP R2023A 2020 100 m: okno 30×30 km, centrum Warszawy\n"
                 "kontrola moiré / prążków (dane modelowane JRC, nie spisowe)", fontsize=10)
    fig.savefig(QA_DIR / "grid250_moire_warszawa.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def cells_tables(pop, pmask, transform) -> dict:
    out = {}
    h, w = pop.shape
    for agg in sorted(all_agglomeration_ids()):
        a = load_agglomeration(agg)
        bx = a["buffered"].bounds
        c0 = int(np.floor((bx[0] - transform.c) / RES)); c1 = int(np.ceil((bx[2] - transform.c) / RES))
        r0 = int(np.floor((transform.f - bx[3]) / RES)); r1 = int(np.ceil((transform.f - bx[1]) / RES))
        c0, r0, c1, r1 = max(c0, 0), max(r0, 0), min(c1, w), min(r1, h)
        sub = pop[r0:r1, c0:c1]
        wt = rasterio.Affine(RES, 0, transform.c + c0 * RES, 0, -RES, transform.f - r0 * RES)
        m_b = poly_mask(a["buffered"], wt, sub.shape)
        m_f = poly_mask(a["fua"], wt, sub.shape)
        m_c = poly_mask(a["core"], wt, sub.shape)
        sel = m_b & (sub > 0)
        rr, cc = np.nonzero(sel)
        x = wt.c + (cc + 0.5) * RES
        y = wt.f - (rr + 0.5) * RES
        df = pd.DataFrame({
            "cell_id": [f"E{int(xx - RES / 2)}N{int(yy - RES / 2)}" for xx, yy in zip(x, y)],
            "x": x, "y": y, "pop": sub[sel].astype(np.float64),
            "in_poland": pmask[r0:r1, c0:c1][sel].astype(bool),
            "in_fua": m_f[sel], "in_core": m_c[sel], "in_buffer": np.ones(len(x), bool),
        }).sort_values(["y", "x"], ascending=[False, True]).reset_index(drop=True)
        df.to_parquet(OUT / f"cells_{agg}.parquet", index=False)
        out[agg] = {"cells_populated": int(len(df)), "pop_buffer": float(df["pop"].sum()),
                    "pop_fua": float(df.loc[df.in_fua, "pop"].sum()),
                    "pop_core": float(df.loc[df.in_core, "pop"].sum()),
                    "pop_buffer_outside_poland": float(df.loc[~df.in_poland, "pop"].sum())}
    return out


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    src = rasterio.open(GHS_POP_VRT)
    src_arr = src.read(1)
    transform, w, h = target_grid()
    print(f"target grid {w} x {h}, origin {transform.c}, {transform.f}")
    dst = build_raster(src_arr, src, transform, w, h)
    pop = np.where(dst == NODATA_OUT, 0.0, dst)
    write_tif(POP_TIF, dst.astype(np.float32), transform, "float32", NODATA_OUT)
    pop32 = np.where(dst == NODATA_OUT, 0.0, dst.astype(np.float32).astype(np.float64))
    pm = poland_mask(transform, w, h)
    write_tif(MASK_TIF, pm, transform, "uint8", 255)

    qa: dict = {"grid": {"crs": "EPSG:2180", "res_m": RES, "width": w, "height": h,
                         "x0": transform.c, "y1": transform.f, "nodata": NODATA_OUT}}
    x0, y1 = transform.c, transform.f
    x1, y0 = x0 + w * RES, y1 - h * RES
    tot_src = source_centre_sum(src_arr, src, x0, y0, x1, y1)
    qa["totals"] = {
        "grid_sum_float64": float(pop.sum()), "grid_sum_float32_file": float(pop32.sum()),
        "source_centres_in_grid_extent": tot_src,
        "rel_error_grid_vs_source": float(pop.sum() / tot_src - 1),
        "poland_sum_250m": float(pop[pm == 1].sum()),
    }
    # per FUA / core: 250 m centre-in-polygon vs 100 m centre-in-polygon (phase-0 rule)
    from pipeline.phase0_boundaries import ghsl_sum
    per = {}
    for agg in sorted(all_agglomeration_ids()):
        a = load_agglomeration(agg)
        row = {}
        for dom in ("fua", "core"):
            g = a[dom]
            bx = g.bounds
            c0 = int(np.floor((bx[0] - x0) / RES)); c1 = int(np.ceil((bx[2] - x0) / RES))
            r0 = int(np.floor((y1 - bx[3]) / RES)); r1 = int(np.ceil((y1 - bx[1]) / RES))
            sub = pop32[r0:r1, c0:c1]
            wt = rasterio.Affine(RES, 0, x0 + c0 * RES, 0, -RES, y1 - r0 * RES)
            s250 = float(sub[poly_mask(g, wt, sub.shape)].sum())
            s100 = ghsl_sum(g)
            row[dom] = {"sum_250m": s250, "sum_100m": s100, "rel_diff": s250 / s100 - 1}
        per[agg] = row
    qa["per_agglomeration"] = per
    # exact reference window
    bx = QA_WINDOW
    ref, naive = window_reference(src_arr, src, bx)
    c0 = int((bx[0] - x0) / RES); r0 = int((y1 - bx[3]) / RES)
    gw = pop[r0:r0 + ref.shape[0], c0:c0 + ref.shape[1]]
    d = gw - ref
    nz = ref > 1
    qa["window_check"] = {
        "box_epsg2180": list(bx), "subpixels_per_source_pixel": 400,
        "sum_gdal": float(gw.sum()), "sum_reference": float(ref.sum()), "sum_naive": float(naive.sum()),
        "sum_diff_gdal_minus_reference": float(gw.sum() - ref.sum()),
        "max_abs_cell_diff_gdal": float(np.abs(d).max()),
        "rel_rmse_gdal_vs_ref": float(np.sqrt((d ** 2).mean()) / ref[nz].mean()),
        "rel_rmse_naive_vs_ref": float(np.sqrt(((naive - ref) ** 2).mean()) / ref[nz].mean()),
        "mean_pop_per_populated_cell": float(ref[nz].mean()),
    }
    qa_picture(gw, naive, ref)
    qa["cells_tables"] = cells_tables(pop32, pm, transform)
    write_json(OUT / "qa.json", round_sig(qa, 6))
    write_meta(OUT, "grid250", inputs=INPUT_IDS, started=t0, extra={
        "note": ("GHS-POP R2023A E2020 (modelled by JRC, not census) on a 250 m EPSG:2180 grid aligned to "
                 "multiples of 250 m; area-preserving GDAL Resampling.sum from 100 m Mollweide; float32 file, "
                 "nodata -1 = sea/outside source. cells_<agg>.parquet: populated cells in FUA + 15 km buffer, "
                 "domain flags by cell centre in polygon. Population date: 2020 (GHSL epoch)."),
        "outputs": sorted(p.name for p in OUT.iterdir() if p.name != "_meta.json"),
    })
    print(qa["totals"], qa["window_check"])


if __name__ == "__main__":
    main()
