"""Part 2 of the scheduled-speed work: scheduled speed of the service passing through an area.

    python -m pipeline.speed_areas

Measure (per area, mode, day type and band): sum of distance travelled inside the area / sum of scheduled time
attributed to it, over every hop traversal (pipeline.speed_core).  A hop's time is attributed to the areas it passes
in proportion to the length of its path inside each (constant speed within a hop).  Scheduled, not real; stops are
inside the hop times, so this is prędkość komunikacyjna, not running speed.

Rules (repeated in results/qa/speed/speed.md)
* Areal unit: 1 km blocks of the project grid (4 x 4 cells of 250 m, EPSG:2180, edges at multiples of 1000 m);
  block_id = E<x0>N<y0> of the lower-left corner, so every 250 m cell_id maps to one block.  Why 1 km: a 250 m
  cell is crossed in under a minute, below the 1-minute resolution of the timetables; a 1 km block holds 2-3 tram
  stops and is crossed in about 3 minutes, so a traversal spans several hop times.
* Hops between two same-name stops at the start or end of a trip (terminal loops, often with a layover) are left
  out (speed_core.terminal_shuffle).
* Only hops whose length comes from the GTFS shape are used (the path is known); hops measured straight are left
  out and counted.
* Reported only when the block has at least MIN_TRAVERSALS hop traversals in the band and at least MIN_LINES
  distinct lines; otherwise null (never 0).
* Modes: tram (official feeds only carry trams) and bus (all feeds; unofficial feeds included, their share of
  bus-km per block is a column).  Rail replacement buses are left out.
* Blocks: centre inside the FUA.
* City comparison: instead of rings around one hub (meaningless for GZM and Trójmiasto) blocks are grouped by
  (a) population density of the block (census-scaled GHSL 2020, NSP 2021 level) and (b) distance to the nearest
  of the agglomeration's configured centres (centre, hub and extra_centres; nearest-of-N, as for the rho variant).
  The single-hub rings of the earlier quick look are recomputed alongside only for the comparison.
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
from pipeline.boundaries import load_agglomeration
from pipeline.common import INTERIM, RESULTS, load_config, sig, write_meta

QA = RESULTS / "qa" / "speed" / "areas"
LAYERS = RESULTS / "layers"
BLOCK_M = 1000.0
STEP_M = 10.0
MIN_TRAVERSALS = 20
MIN_LINES = 2
AREA_MODES = ["tram", "bus"]
DENS_BINS = [0, 1000, 2500, 5000, 10000, np.inf]
DENS_LABELS = ["< 1 000", "1 000–2 500", "2 500–5 000", "5 000–10 000", "≥ 10 000"]
RING_BINS = [0, 1.5, 3, 6, 10, np.inf]
RING_LABELS = ["0–1,5 km", "1,5–3 km", "3–6 km", "6–10 km", "> 10 km"]
TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
TO4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def block_of(x, y) -> np.ndarray:
    bx = (np.floor(np.asarray(x) / BLOCK_M) * BLOCK_M).astype(np.int64)
    by = (np.floor(np.asarray(y) / BLOCK_M) * BLOCK_M).astype(np.int64)
    return bx, by


def hop_block_lengths(h: pd.DataFrame) -> pd.DataFrame:
    """For each unique (feed, pid, k) hop with a shape: length (m) of its path in each 1 km block."""
    u = h[h["len_src"] == "shape"].drop_duplicates(["pid", "k"])[["feed", "pid", "k", "shape_id", "a0", "a1"]]
    rows_pid, rows_k, rows_bx, rows_by, rows_len, rows_tot = [], [], [], [], [], []
    for feed, g in u.groupby("feed", sort=True):
        shp = sc.shape_arrays(feed)
        for r in g.itertuples(index=False):
            p, cum = shp[r.shape_id]
            c = sc.cut(p, cum, r.a0, r.a1)
            seg = np.hypot(*np.diff(c, axis=0).T)
            tot = seg.sum()
            if tot <= 0:
                continue
            # split each segment into pieces of <= STEP_M and assign each piece to the block of its midpoint
            n = np.maximum(1, np.ceil(seg / STEP_M)).astype(int)
            idx = np.repeat(np.arange(len(seg)), n)
            frac = (np.concatenate([np.arange(k) for k in n]) + 0.5) / np.repeat(n, n)
            mid = c[:-1][idx] + (c[1:][idx] - c[:-1][idx]) * frac[:, None]
            plen = (seg / n)[idx]
            bx, by = block_of(mid[:, 0], mid[:, 1])
            key = bx * 10_000_000 + by
            uk, inv = np.unique(key, return_inverse=True)
            ln = np.bincount(inv, weights=plen)
            rows_pid.append(np.full(len(uk), r.pid)); rows_k.append(np.full(len(uk), r.k))
            rows_bx.append(uk // 10_000_000); rows_by.append(uk % 10_000_000)
            rows_len.append(ln); rows_tot.append(np.full(len(uk), tot))
    if not rows_pid:
        return pd.DataFrame(columns=["pid", "k", "bx", "by", "len_in", "geom_len"])
    return pd.DataFrame({"pid": np.concatenate(rows_pid), "k": np.concatenate(rows_k), "bx": np.concatenate(rows_bx),
                         "by": np.concatenate(rows_by), "len_in": np.concatenate(rows_len), "geom_len": np.concatenate(rows_tot)})


def agg_blocks(agg: str, day_type: str) -> tuple[pd.DataFrame, dict]:
    h = sc.hops(agg, day_type)
    h = h[h["mode"].isin(AREA_MODES) & ~h["repl_bus"].astype(bool)]
    h = h[~sc.terminal_shuffle(h, agg)]
    diag = {}
    for m, g in h.groupby("mode"):
        diag[m] = {"hops": int(len(g)), "share_hops_straight_left_out": float((g["len_src"] != "shape").mean()),
                   "share_len_straight_left_out": float(g.loc[g["len_src"] != "shape", "len_m"].sum() / g["len_m"].sum())}
    h = h[h["len_src"] == "shape"]
    h = h.assign(line=h["feed"] + ":" + h["line"].astype(str))
    off = sc.feed_official()
    h = h.assign(len_unoff=h["len_m"] * (~h["feed"].map(off).fillna(False).astype(bool)))
    bl = hop_block_lengths(h)
    out = []
    for band in sc.band_ids(day_type) + ["all_day"]:
        g = h if band == "all_day" else h[h["band"] == band]
        tr = g.groupby(["mode", "pid", "k"]).agg(n=("uid", "size"), t=("t_s", "sum"), L=("len_m", "sum"),
                                                 Lu=("len_unoff", "sum"), line=("line", "first")).reset_index()
        j = tr.merge(bl, on=["pid", "k"])
        f = j["len_in"] / j["geom_len"]
        j = j.assign(dist=f * j["L"], time=f * j["t"], dist_unoff=f * j["Lu"])
        a = j.groupby(["mode", "bx", "by"]).agg(dist=("dist", "sum"), time=("time", "sum"), n=("n", "sum"),
                                               dist_unoff=("dist_unoff", "sum"), n_lines=("line", "nunique")).reset_index()
        a["band"] = band
        out.append(a)
    A = pd.concat(out, ignore_index=True)
    A["day_type"] = day_type
    return A, diag


def block_context(agg: str, blocks: pd.DataFrame) -> pd.DataFrame:
    """Population density (census-scaled), FUA/core membership of the block centre, distance to nearest centre and
    to the hub."""
    cfg = load_config()["agglomerations"][agg]
    cells = pd.read_parquet(INTERIM / "popgrid" / f"cells_{agg}.parquet")
    bx, by = block_of(cells["x"] - 125, cells["y"] - 125)
    cells = cells.assign(bx=bx, by=by)
    pop = cells.groupby(["bx", "by"])["pop_ghsl_census_scaled"].sum()
    b = blocks[["bx", "by"]].drop_duplicates().sort_values(["bx", "by"]).reset_index(drop=True)
    b["pop"] = [pop.get((x, y), np.nan) for x, y in zip(b["bx"], b["by"])]
    b["density_per_km2"] = b["pop"] / (BLOCK_M / 1000) ** 2
    a = load_agglomeration(agg)
    cx, cy = b["bx"] + BLOCK_M / 2, b["by"] + BLOCK_M / 2
    b["in_fua"] = shapely.contains_xy(a["fua"], cx, cy)
    b["in_core"] = shapely.contains_xy(a["core"], cx, cy)
    pts = [cfg["centre"], cfg.get("hub", cfg["centre"])] + list(cfg.get("extra_centres") or [])
    px, py = TO2180.transform([p["lon"] for p in pts], [p["lat"] for p in pts])
    d = np.min(np.hypot(cx.to_numpy()[:, None] - np.asarray(px)[None], cy.to_numpy()[:, None] - np.asarray(py)[None]), axis=1)
    b["dist_nearest_centre_km"] = d / 1000
    hx, hy = TO2180.transform(cfg.get("hub", cfg["centre"])["lon"], cfg.get("hub", cfg["centre"])["lat"])
    b["dist_hub_km"] = np.hypot(cx - hx, cy - hy) / 1000
    b["density_class"] = pd.cut(b["density_per_km2"].fillna(0), DENS_BINS, right=False, labels=DENS_LABELS).astype(str)
    b["ring_nearest_centre"] = pd.cut(b["dist_nearest_centre_km"], RING_BINS, right=False, labels=RING_LABELS).astype(str)
    b["ring_hub"] = pd.cut(b["dist_hub_km"], RING_BINS, right=False, labels=RING_LABELS).astype(str)
    return b


def run() -> dict:
    t0 = time.time()
    QA.mkdir(parents=True, exist_ok=True)
    allA, ctx, diag = [], [], []
    for agg in sc.AGGS:
        parts = []
        for dt in sc.days():
            A, dg = agg_blocks(agg, dt)
            parts.append(A)
            for m, d in dg.items():
                diag.append({"agglomeration": agg, "day_type": dt, "mode": m, **d})
        A = pd.concat(parts, ignore_index=True)
        A.insert(0, "agglomeration", agg)
        b = block_context(agg, A)
        b.insert(0, "agglomeration", agg)
        ctx.append(b)
        allA.append(A)
        print(f"  {agg}: {len(b)} blocks, {time.time() - t0:.0f} s", flush=True)
    A = pd.concat(allA, ignore_index=True)
    B = pd.concat(ctx, ignore_index=True)
    A = A.merge(B[["agglomeration", "bx", "by", "in_fua"]], on=["agglomeration", "bx", "by"])
    A = A[A["in_fua"]].drop(columns="in_fua")
    A["speed_kmh"] = A["dist"] / A["time"].where(A["time"] > 0) * 3.6
    A["reported"] = (A["n"] >= MIN_TRAVERSALS) & (A["n_lines"] >= MIN_LINES)
    from pipeline import speed_areas_out as out
    return out.write_all(A, B, pd.DataFrame(diag), t0)


if __name__ == "__main__":
    run()
