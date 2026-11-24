"""Outputs of pipeline.speed_areas: the block layer and the city comparisons.

* results/layers/speed_areas.parquet   one row per 1 km block with tram or bus service (centre in FUA), EPSG:4326
                                       polygons; columns speed_<mode>_<day>_<band> (null when below the reporting
                                       rule), trav_<mode>_<day>_<band> (hop traversals), vkm_<mode>_<day> (all day)
* results/qa/speed/areas/city_by_density.csv, city_by_ring.csv, city_by_hub_ring.csv, coverage.csv, diag.csv
"""
from __future__ import annotations

import shutil
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from pipeline import speed_core as sc
from pipeline import speed_areas as SA
from pipeline.common import sig, write_meta

DAYCODE = {"weekday": "wd", "saturday": "sat"}
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def _fmt(df: pd.DataFrame) -> pd.DataFrame:
    o = df.copy()
    for c in o.columns:
        if o[c].dtype.kind == "f":
            o[c] = o[c].map(sig)
    return o


def layer(A: pd.DataFrame, B: pd.DataFrame) -> gpd.GeoDataFrame:
    b = B[B["in_fua"]].copy()
    keys = A[["agglomeration", "bx", "by"]].drop_duplicates()
    b = b.merge(keys, on=["agglomeration", "bx", "by"])
    b["block_id"] = "E" + b["bx"].astype(str) + "N" + b["by"].astype(str)
    out = b[["agglomeration", "block_id", "bx", "by", "in_core", "pop", "density_per_km2", "density_class",
             "dist_nearest_centre_km", "ring_nearest_centre", "dist_hub_km"]].copy()
    idx = pd.MultiIndex.from_frame(out[["agglomeration", "bx", "by"]])
    for mode in SA.AREA_MODES:
        for dt in sc.days():
            for band in sc.band_ids(dt) + ["all_day"]:
                g = A[(A["mode"] == mode) & (A["day_type"] == dt) & (A["band"] == band)].set_index(["agglomeration", "bx", "by"])
                g = g.reindex(idx)
                p = f"{mode}_{DAYCODE[dt]}_{band}"
                out[f"speed_{p}"] = np.where(g["reported"].fillna(False).to_numpy(bool), g["speed_kmh"].to_numpy(), np.nan)
                out[f"trav_{p}"] = g["n"].fillna(0).astype(int).to_numpy()
                if band == "all_day":
                    out[f"vkm_{mode}_{DAYCODE[dt]}"] = (g["dist"] / 1000).to_numpy()
                    out[f"lines_{mode}_{DAYCODE[dt]}"] = g["n_lines"].fillna(0).astype(int).to_numpy()
                    if mode == "bus":
                        out[f"share_unofficial_bus_km_{DAYCODE[dt]}"] = (g["dist_unoff"] / g["dist"]).to_numpy()
    out = out.sort_values(["agglomeration", "block_id"], kind="stable").reset_index(drop=True)
    polys = []
    for a, b_ in zip(out["bx"].to_numpy(float), out["by"].to_numpy(float)):
        xs = [a, a + SA.BLOCK_M, a + SA.BLOCK_M, a, a]
        ys = [b_, b_, b_ + SA.BLOCK_M, b_ + SA.BLOCK_M, b_]
        lo, la = TO4326.transform(xs, ys)
        polys.append(shapely.Polygon(np.round(np.c_[lo, la], 6)))
    out = out.drop(columns=["bx", "by"])
    g = gpd.GeoDataFrame(out, geometry=polys, crs="EPSG:4326")
    for c in g.columns:
        if g[c].dtype.kind == "f":
            g[c] = g[c].map(sig).astype(float)
    return g


def grouped(A: pd.DataFrame, B: pd.DataFrame, col: str, labels: list[str]) -> pd.DataFrame:
    j = A.merge(B[["agglomeration", "bx", "by", col]], on=["agglomeration", "bx", "by"])
    rows = []
    for (agg, mode, dt, band, cl), g in j.groupby(["agglomeration", "mode", "day_type", "band", col], sort=True):
        rows.append({"agglomeration": agg, "mode": mode, "day_type": dt, "timetable_date": sc.days()[dt], "band": band,
                     "group": cl, "blocks": int(len(g)), "blocks_reported": int(g["reported"].sum()),
                     "speed_kmh": float(g["dist"].sum() / g["time"].sum() * 3.6) if g["time"].sum() > 0 else None,
                     "vehicle_km": float(g["dist"].sum() / 1000),
                     "speed_kmh_reported_blocks": float(g.loc[g["reported"], "dist"].sum() / g.loc[g["reported"], "time"].sum() * 3.6)
                     if g["reported"].any() else None})
    out = pd.DataFrame(rows)
    out["_o"] = out["group"].map({l: i for i, l in enumerate(labels)})
    return out.sort_values(["agglomeration", "mode", "day_type", "band", "_o"], kind="stable").drop(columns="_o")


def write_all(A: pd.DataFrame, B: pd.DataFrame, diag: pd.DataFrame, t0: float) -> dict:
    QA, LY = SA.QA, SA.LAYERS
    QA.mkdir(parents=True, exist_ok=True)
    lay = layer(A, B)
    lay.to_parquet(LY / "speed_areas.parquet", index=False)
    dens = grouped(A, B, "density_class", SA.DENS_LABELS)
    ring = grouped(A, B, "ring_nearest_centre", SA.RING_LABELS)
    hub = grouped(A, B, "ring_hub", SA.RING_LABELS)
    _fmt(dens).to_csv(QA / "city_by_density.csv", index=False, lineterminator="\n")
    _fmt(ring).to_csv(QA / "city_by_nearest_centre.csv", index=False, lineterminator="\n")
    _fmt(hub).to_csv(QA / "city_by_hub_ring.csv", index=False, lineterminator="\n")
    cov = []
    for (agg, mode, dt, band), g in A.groupby(["agglomeration", "mode", "day_type", "band"], sort=True):
        cov.append({"agglomeration": agg, "mode": mode, "day_type": dt, "band": band, "blocks_with_service": int(len(g)),
                    "blocks_reported": int(g["reported"].sum()),
                    "share_vkm_in_reported_blocks": float(g.loc[g["reported"], "dist"].sum() / g["dist"].sum()),
                    "speed_kmh_all_blocks": float(g["dist"].sum() / g["time"].sum() * 3.6),
                    "median_block_speed_kmh": float(g.loc[g["reported"], "speed_kmh"].median()) if g["reported"].any() else None})
    cov = pd.DataFrame(cov)
    _fmt(cov).to_csv(QA / "coverage.csv", index=False, lineterminator="\n")
    _fmt(diag.sort_values(["agglomeration", "day_type", "mode"])).to_csv(QA / "diag_straight_hops.csv", index=False, lineterminator="\n")
    size = round((LY / "speed_areas.parquet").stat().st_size / 1e6, 2)
    from pipeline import gtfs_service as gs
    inputs = sorted({f"gtfs_{f}" for a in sc.AGGS for f in gs.feeds_for(a, "all")})
    extra = {"timetable_dates": sc.days(), "block_m": SA.BLOCK_M, "min_traversals": SA.MIN_TRAVERSALS,
             "min_lines": SA.MIN_LINES, "modes": SA.AREA_MODES, "population": "ghsl_census_scaled (NSP 2021, GHSL 2020)",
             "sizes_mb": {"speed_areas.parquet": size},
             "files": {"speed_areas.parquet": {"crs": "EPSG:4326", "rows": "1 km blocks (aligned with the 250 m grid) with tram or bus service, centre in FUA",
                                               "null": "speed null = fewer than MIN_TRAVERSALS hop traversals or fewer than MIN_LINES lines in the band"}}}
    mp = write_meta(QA, "speed_areas", inputs=inputs, started=t0, extra=extra)
    shutil.copyfile(mp, LY / "_meta_speed_areas.json")
    print(f"speed_areas done in {time.time() - t0:.0f} s; layer {size} MB")
    return {"A": A, "B": B, "dens": dens, "ring": ring, "hub": hub, "cov": cov}
