"""Pure-Python vector tiles: a class grid (250 m cells in EPSG:2180) -> MVT tiles -> one PMTiles file.

No tippecanoe: for every tile the window of the class grid under it is polygonized (adjacent cells of one
class dissolve into one polygon), densified, projected to Web Mercator, clipped to the tile plus a small
buffer, snapped to the 4096 extent and encoded, one feature per class per tile.

Low zooms use a coarsened copy of the grid (block mode, see ``ClassGrid.level``), so the classes of
neighbouring blocks stay a partition of the plane: nothing is simplified polygon by polygon, hence no
gaps or overlaps between classes at any zoom.

Grid codes: 0 = nothing is drawn, 1 = no-data feature (no ``v`` property), 2.. = value classes.
"""
from __future__ import annotations

import gzip
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import mapbox_vector_tile as mvt
import numpy as np
import pyproj
import shapely
from mapbox_vector_tile.encoder import on_invalid_geometry_make_valid
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write as pmtiles_write
from rasterio import features
from rasterio.transform import Affine

CELL = 250.0                 # m, grid cell in EPSG:2180
EXTENT = 4096                # MVT extent
BUFFER = 64                  # clip buffer, in tile units
MIN_Z, MAX_Z = 4, 12
FULL_Z = 9                   # at and above this zoom the grid is used at full resolution
BLOCK = 2 ** (FULL_Z - MIN_Z)  # largest coarsening factor in cells; the grid is aligned and padded to it
WORLD = 20037508.342789244   # half the Web Mercator world, m

NODATA, FIRST_CLASS = 1, 2

T_2180_3857 = pyproj.Transformer.from_crs(2180, 3857, always_xy=True)
T_3857_2180 = pyproj.Transformer.from_crs(3857, 2180, always_xy=True)
T_3857_4326 = pyproj.Transformer.from_crs(3857, 4326, always_xy=True)
T_2180_4326 = pyproj.Transformer.from_crs(2180, 4326, always_xy=True)


def factor(z: int) -> int:
    """Coarsening factor of the grid for zoom z: one block stays about 1.3 px wide on screen."""
    return 1 if z >= FULL_Z else 2 ** (FULL_Z - z)


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float]:
    """(xmin, ymax, width) of a tile in EPSG:3857 metres."""
    w = 2 * WORLD / (1 << z)
    return -WORLD + x * w, WORLD - y * w, w


@dataclass
class ClassGrid:
    """Class codes on the 250 m lattice; x0 / y1 are the west and north edges in EPSG:2180."""
    x0: float
    y1: float
    codes: np.ndarray                  # uint8 (rows, cols)
    agg: np.ndarray                    # uint8 (rows, cols): agglomeration index + 1, 0 = none
    _levels: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_cells(cls, xll, yll, code, agg_idx) -> "ClassGrid":
        """Lower-left corners (multiples of 250 m), class code and agglomeration index per cell."""
        xll, yll = np.asarray(xll, np.int64), np.asarray(yll, np.int64)
        span = int(CELL * BLOCK)
        x0 = int(math.floor(xll.min() / span) * span)
        y1 = int(math.ceil((yll.max() + CELL) / span) * span)
        w = int(math.ceil((xll.max() + CELL - x0) / span)) * BLOCK
        h = int(math.ceil((y1 - yll.min()) / span)) * BLOCK
        col = ((xll - x0) // int(CELL)).astype(np.int64)
        row = ((y1 - yll) // int(CELL) - 1).astype(np.int64)
        codes = np.zeros((h, w), np.uint8)
        agg = np.zeros((h, w), np.uint8)
        codes[row, col] = np.asarray(code, np.uint8)
        agg[row, col] = np.asarray(agg_idx, np.uint8) + 1
        return cls(float(x0), float(y1), codes, agg)

    def level(self, f: int) -> tuple[np.ndarray, Affine]:
        """The grid coarsened by f (mode of the drawn cells of each f x f block; ties go to the lowest
        code, so no data beats a value) and its affine transform."""
        if f not in self._levels:
            if f == 1:
                arr = self.codes
            else:
                h, w = self.codes.shape
                blocks = self.codes.reshape(h // f, f, w // f, f)
                top = int(self.codes.max())
                counts = np.stack([(blocks == c).sum(axis=(1, 3), dtype=np.uint16) for c in range(1, top + 1)])
                arr = np.where(counts.max(axis=0) > 0, counts.argmax(axis=0) + 1, 0).astype(np.uint8)
            self._levels[f] = (arr, Affine(CELL * f, 0, self.x0, 0, -CELL * f, self.y1))
        return self._levels[f]

    def bounds_4326(self) -> tuple[float, float, float, float]:
        rows, cols = np.nonzero(self.codes)
        x0, x1 = self.x0 + cols.min() * CELL, self.x0 + (cols.max() + 1) * CELL
        y0, y1 = self.y1 - (rows.max() + 1) * CELL, self.y1 - rows.min() * CELL
        xs, ys = T_2180_4326.transform([x0, x1, x0, x1], [y0, y0, y1, y1])
        return min(xs), min(ys), max(xs), max(ys)


def tile_set(cg: ClassGrid, z: int) -> list[tuple[int, int]]:
    """Tiles (x, y) at zoom z that can hold drawn blocks: the tiles of the block centres and their neighbours."""
    arr, _ = cg.level(factor(z))
    cs = CELL * factor(z)
    rows, cols = np.nonzero(arr)
    mx, my = T_2180_3857.transform(cg.x0 + (cols + 0.5) * cs, cg.y1 - (rows + 0.5) * cs)
    n, w = 1 << z, 2 * WORLD / (1 << z)
    tx = np.floor((mx + WORLD) / w).astype(np.int64)
    ty = np.floor((WORLD - my) / w).astype(np.int64)
    found = {(int(a), int(b)) for a, b in zip(tx, ty)}
    found = {(x + dx, y + dy) for x, y in found for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    return sorted((x, y) for x, y in found if 0 <= x < n and 0 <= y < n)


def _polygons(g) -> list:
    return [p for p in shapely.get_parts(g) if p.geom_type == "Polygon" and not p.is_empty and p.area > 0]


def window(cg: ClassGrid, z: int, x: int, y: int) -> tuple[int, int, int, int] | None:
    """Rows and columns (r0, r1, c0, c1) of the level-z grid that cover the tile plus BUFFER, or None."""
    f = factor(z)
    arr, _ = cg.level(f)
    cs = CELL * f
    xmin, ymax, w = tile_bounds(z, x, y)
    pad = w * BUFFER / EXTENT
    t = np.linspace(0, 1, 17)
    ring_x = np.concatenate([xmin - pad + t * (w + 2 * pad), np.full(17, xmin + w + pad), xmin - pad + t * (w + 2 * pad),
                             np.full(17, xmin - pad)])
    ring_y = np.concatenate([np.full(17, ymax + pad), ymax + pad - t * (w + 2 * pad), np.full(17, ymax - w - pad),
                             ymax + pad - t * (w + 2 * pad)])
    ex, ny = T_3857_2180.transform(ring_x, ring_y)
    c0 = max(int(math.floor((min(ex) - cg.x0) / cs)) - 2, 0)
    c1 = min(int(math.ceil((max(ex) - cg.x0) / cs)) + 2, arr.shape[1])
    r0 = max(int(math.floor((cg.y1 - max(ny)) / cs)) - 2, 0)
    r1 = min(int(math.ceil((cg.y1 - min(ny)) / cs)) + 2, arr.shape[0])
    return None if c0 >= c1 or r0 >= r1 else (r0, r1, c0, c1)


def tile_polygons(cg: ClassGrid, z: int, x: int, y: int) -> dict[int, list]:
    """{class code: polygons in tile units (0..4096, y down)}, clipped to the tile plus BUFFER."""
    f = factor(z)
    arr, _ = cg.level(f)
    cs = CELL * f
    xmin, ymax, w = tile_bounds(z, x, y)
    win_ix = window(cg, z, x, y)
    if win_ix is None:
        return {}
    r0, r1, c0, c1 = win_ix
    win = np.ascontiguousarray(arr[r0:r1, c0:c1])
    if not win.any():
        return {}
    wt = Affine(cs, 0, cg.x0 + c0 * cs, 0, -cs, cg.y1 - r0 * cs)
    by_code: dict[int, list] = {}
    for geom, val in features.shapes(win, mask=win > 0, transform=wt, connectivity=4):
        by_code.setdefault(int(val), []).append(shapely.geometry.shape(geom))

    def to_tile(c):
        px, py = T_2180_3857.transform(c[:, 0], c[:, 1])
        return np.column_stack(((px - xmin) / w * EXTENT, (ymax - py) / w * EXTENT))

    out: dict[int, list] = {}
    for code in sorted(by_code):
        g = shapely.segmentize(np.array(by_code[code], dtype=object), cs)   # edges stay on the lattice
        g = shapely.transform(g, to_tile)
        g = shapely.clip_by_rect(g, -BUFFER, -BUFFER, EXTENT + BUFFER, EXTENT + BUFFER)
        parts = [p for geom in g for p in _polygons(geom)]
        if not parts:
            continue
        snapped = _polygons(shapely.set_precision(shapely.MultiPolygon(parts), 1.0))
        if snapped:
            out[code] = snapped
    return out


def encode_tile(source_layer: str, polys: dict[int, list], props: dict[int, dict]) -> bytes | None:
    feats = []
    for code in sorted(polys):
        ps = polys[code]
        geom = ps[0] if len(ps) == 1 else shapely.MultiPolygon(ps)
        feats.append({"geometry": geom, "properties": dict(props[code])})
    if not feats:
        return None
    raw = mvt.encode([{"name": source_layer, "features": feats}], default_options={
        "y_coord_down": True, "extents": EXTENT, "check_winding_order": True,
        "on_invalid_geometry": on_invalid_geometry_make_valid})
    return gzip.compress(raw, compresslevel=9, mtime=0)


def build_tiles(cg: ClassGrid, source_layer: str, props: dict[int, dict],
                log: Callable[[str], None] = print) -> dict[int, bytes]:
    """All tiles MIN_Z..MAX_Z as {PMTiles tile id: gzipped MVT}."""
    tiles: dict[int, bytes] = {}
    for z in range(MIN_Z, MAX_Z + 1):
        n0 = len(tiles)
        for x, y in tile_set(cg, z):
            data = encode_tile(source_layer, tile_polygons(cg, z, x, y), props)
            if data is not None:
                tiles[zxy_to_tileid(z, x, y)] = data
        log(f"    z{z}: {len(tiles) - n0} tiles")
    return tiles


def write_pmtiles(path: Path, tiles: dict[int, bytes], *, bounds: tuple, source_layer: str, name: str,
                  description: str, attribution: str, version: str, fields: dict[str, str]) -> None:
    """Deterministic PMTiles v3 archive (clustered, gzip tiles, MVT) with TileJSON-style metadata."""
    west, south, east, north = bounds
    e7 = lambda v: int(round(v * 1e7))  # noqa: E731
    header = {
        "tile_compression": Compression.GZIP, "tile_type": TileType.MVT,
        "min_lon_e7": e7(west), "min_lat_e7": e7(south), "max_lon_e7": e7(east), "max_lat_e7": e7(north),
        "center_zoom": 8, "center_lon_e7": e7((west + east) / 2), "center_lat_e7": e7((south + north) / 2),
    }
    metadata = {
        "name": name, "description": description, "version": version, "type": "overlay", "format": "pbf",
        "attribution": attribution, "minzoom": MIN_Z, "maxzoom": MAX_Z,
        "bounds": f"{west:.5f},{south:.5f},{east:.5f},{north:.5f}",
        "center": f"{(west + east) / 2:.5f},{(south + north) / 2:.5f},8",
        "vector_layers": [{"id": source_layer, "fields": fields, "minzoom": MIN_Z, "maxzoom": MAX_Z}],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with pmtiles_write(str(tmp)) as w:
        for tid in sorted(tiles):
            w.write_tile(tid, tiles[tid])
        w.finalize(header, metadata)
    os.replace(tmp, path)
