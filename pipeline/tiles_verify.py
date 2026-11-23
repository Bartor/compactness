"""Read a finished PMTiles file back and compare it with the class grid it was built from.

* header, metadata, tile counts and bytes per zoom;
* every feature property is one of the class values (no-data features carry none);
* z12: for every cell centre inside a tile, the feature that covers it is the one of the cell's class
  (and unpopulated cells are covered by nothing);
* z12: area per agglomeration and class, summed over the tiles clipped to their bounds without buffer,
  against the area of the source cells.
"""
from __future__ import annotations

import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import mapbox_vector_tile as mvt
import numpy as np
import shapely
from pmtiles.reader import MemorySource, Reader, all_tiles
from pmtiles.tile import tileid_to_zxy
from rasterio import features
from rasterio.transform import Affine

from pipeline.tiles_core import (CELL, EXTENT, MAX_Z, T_2180_3857, T_3857_2180, ClassGrid, tile_bounds,
                                 window)


TILE_BOX = shapely.box(0, 0, EXTENT, EXTENT)


def open_reader(path: Path) -> tuple[Reader, bytes]:
    buf = Path(path).read_bytes()
    return Reader(MemorySource(buf)), buf


def decode(data: bytes, source_layer: str) -> list[tuple[dict, shapely.Geometry]]:
    d = mvt.decode(gzip.decompress(data), default_options={"y_coord_down": True})
    return [(f["properties"], shapely.geometry.shape(f["geometry"])) for f in d.get(source_layer, {}).get("features", [])]


def to_2180(geom, z: int, x: int, y: int):
    xmin, ymax, w = tile_bounds(z, x, y)

    def fn(c):
        X, Y = T_3857_2180.transform(xmin + c[:, 0] / EXTENT * w, ymax - c[:, 1] / EXTENT * w)
        return np.column_stack((X, Y))
    return shapely.transform(geom, fn)


def viewport_bytes(reader: Reader, lon: float, lat: float, z: int, px=(1440, 900), tile_px=512) -> int:
    """Bytes of the tiles a px-sized map window centred on lon/lat requests at zoom z (compressed, as transferred)."""
    n = 1 << z
    tx = (lon + 180) / 360 * n
    ty = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    total = 0
    for x in range(math.floor(tx - px[0] / 2 / tile_px), math.floor(tx + px[0] / 2 / tile_px) + 1):
        for y in range(math.floor(ty - px[1] / 2 / tile_px), math.floor(ty + px[1] / 2 / tile_px) + 1):
            if 0 <= x < n and 0 <= y < n:
                t = reader.get(z, x, y)
                total += len(t) if t else 0
    return total


def verify(path: Path, cg: ClassGrid, aggs: list[str], props: dict[int, dict], source_layer: str,
           classes: list[dict], log=print) -> dict:
    reader, buf = open_reader(path)
    head = reader.header()
    meta = reader.metadata()
    out: dict = {
        "header": {
            "tile_type": head["tile_type"].name, "tile_compression": head["tile_compression"].name,
            "internal_compression": head["internal_compression"].name, "clustered": bool(head["clustered"]),
            "min_zoom": head["min_zoom"], "max_zoom": head["max_zoom"],
            "bounds": [round(head[k] / 1e7, 5) for k in ("min_lon_e7", "min_lat_e7", "max_lon_e7", "max_lat_e7")],
            "center": [round(head["center_lon_e7"] / 1e7, 5), round(head["center_lat_e7"] / 1e7, 5), head["center_zoom"]],
            "addressed_tiles": head["addressed_tiles_count"], "tile_contents": head["tile_contents_count"],
        },
        "vector_layers": [v["id"] for v in meta.get("vector_layers", [])],
    }
    allowed = {tuple(sorted(p.items())): c for c, p in props.items()}
    per_zoom: dict[int, list[int]] = defaultdict(list)
    bad_props = 0
    grid_codes, _ = cg.level(1)
    area = defaultdict(float)        # (agg, code) -> km2 from the tiles
    checked = mism_missing = mism_wrong = mism_extra = 0
    z12 = []
    for (z, x, y), data in all_tiles(reader.get_bytes):
        per_zoom[z].append(len(data))
        feats = decode(data, source_layer)
        for p, _g in feats:
            if tuple(sorted(p.items())) not in allowed:
                bad_props += 1
        if z == MAX_Z:
            z12.append((x, y, feats))
    log(f"    read back {sum(len(v) for v in per_zoom.values())} tiles; checking z{MAX_Z} against the grid")

    for x, y, feats in z12:
        xmin, ymax, w = tile_bounds(MAX_Z, x, y)
        win = window(cg, MAX_Z, x, y)
        by_code = {}
        for p, g in feats:
            code = allowed[tuple(sorted(p.items()))]
            by_code.setdefault(code, []).append(shapely.intersection(g, TILE_BOX))
        by_code = {c: shapely.union_all(gs) for c, gs in by_code.items()}
        if win is None:
            continue
        r0, r1, c0, c1 = win
        sub = grid_codes[r0:r1, c0:c1]
        rr, cc = np.nonzero(np.ones_like(sub, bool))
        cx = cg.x0 + (c0 + cc + 0.5) * CELL
        cy = cg.y1 - (r0 + rr + 0.5) * CELL
        # cell centres into tile units (EPSG:2180 -> 3857 via the inverse of what the tiles used)
        mx, my = T_2180_3857.transform(cx, cy)
        px, py = (mx - xmin) / w * EXTENT, (ymax - my) / w * EXTENT
        inside = (px >= 0) & (px < EXTENT) & (py >= 0) & (py < EXTENT)
        exp = sub[rr, cc]
        covered_by = np.zeros(len(exp), np.uint8)
        for code, g in by_code.items():
            hit = inside & shapely.contains_xy(g, px, py)
            covered_by[hit & (covered_by == 0)] = code
        sel = inside
        checked += int((sel & (exp > 0)).sum())
        mism_missing += int((sel & (exp > 0) & (covered_by == 0)).sum())
        mism_wrong += int((sel & (exp > 0) & (covered_by > 0) & (covered_by != exp)).sum())
        mism_extra += int((sel & (exp == 0) & (covered_by > 0)).sum())
        # area per agglomeration: footprint of each agglomeration inside the window
        aggwin = cg.agg[r0:r1, c0:c1]
        wt = Affine(CELL, 0, cg.x0 + c0 * CELL, 0, -CELL, cg.y1 - r0 * CELL)
        foot = {}
        for a in np.unique(aggwin[aggwin > 0]):
            polys = [shapely.geometry.shape(gj) for gj, _ in features.shapes(
                np.ascontiguousarray(aggwin), mask=aggwin == a, transform=wt, connectivity=4)]
            foot[int(a)] = shapely.union_all(polys)
        for code, g in by_code.items():
            if g.is_empty:
                continue
            g2180 = to_2180(g, MAX_Z, x, y)
            for a, fp in foot.items():
                area[(aggs[a - 1], code)] += shapely.intersection(g2180, fp).area / 1e6

    src = Counter()
    for a_idx, a in enumerate(aggs):
        m = cg.agg == a_idx + 1
        vals, cnt = np.unique(grid_codes[m], return_counts=True)
        for v, n in zip(vals, cnt):
            if v > 0:
                src[(a, int(v))] = n * CELL * CELL / 1e6
    rows = []
    for (a, code), s in sorted(src.items()):
        t = area.get((a, code), 0.0)
        rows.append({"agg": a, "code": code, "source_km2": round(s, 3), "tiles_km2": round(t, 3),
                     "diff_pct": round(100 * (t - s) / s, 3) if s else None})
    out.update({
        "tiles_per_zoom": {str(z): len(v) for z, v in sorted(per_zoom.items())},
        "bytes_per_zoom": {str(z): sum(v) for z, v in sorted(per_zoom.items())},
        "max_tile_bytes": {str(z): max(v) for z, v in sorted(per_zoom.items())},
        "bad_properties": bad_props,
        "cells_checked": checked, "cells_not_covered": mism_missing, "cells_wrong_class": mism_wrong,
        "empty_cells_covered": mism_extra,
        "area": rows,
        "max_abs_diff_pct": round(max((abs(r["diff_pct"]) for r in rows if r["diff_pct"] is not None), default=0.0), 3),
    })
    return out
