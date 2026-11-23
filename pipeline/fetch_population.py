"""Download population and built-up data: NSP 2021 1 km grid (GUS) and GHSL R2023A tiles.

* NSP 2021 grid: GUS Portal Geostatystyczny ATOM feed (PD.GRID.2021, shapefile in EPSG:2180).
* GHS-POP / GHS-BUILT-S R2023A, epoch 2020, 100 m, Mollweide (EPSG:54009) tiles covering
  Poland + 20 km margin.  Tiles are selected from the GHSL tiling schema (18 rows x 36
  columns, 1000 km x 1000 km, origin top-left at x=-18041000, y=9000000) and the schema is
  verified against the opened rasters.  Never the 2025 projection.

Run: python -m pipeline.fetch_population
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
import rasterio
import requests
from shapely.geometry import box
from shapely.ops import unary_union

from pipeline.common import INTERIM, RAW, USER_AGENT, download, write_json

NSP_FEED = ("https://geo.stat.gov.pl/atom-web/atom/PD?spatial_dataset_identifier_code=PD.GRID.2021"
            "&spatial_dataset_identifier_namespace=http://geo.stat.gov.pl/id/dataset/PL.ZIPGUS.2827")
GHSL_BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
PRODUCTS = {
    "ghs_pop": ("GHS_POP_GLOBE_R2023A/GHS_POP_E2020_GLOBE_R2023A_54009_100/V1-0/tiles/",
                "GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0"),
    "ghs_built_s": ("GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100/V1-0/tiles/",
                    "GHS_BUILT_S_E2020_GLOBE_R2023A_54009_100_V1_0"),
}
GHSL_LICENSE = "CC BY 4.0 (JRC GHSL, European Commission)"
TILE_M = 1_000_000
ORIGIN_X, ORIGIN_Y = -18_041_000, 9_000_000
MARGIN_M = 20_000
MOLLWEIDE = "ESRI:54009"
GHSL_DIR = RAW / "ghsl"
NSP_DIR = RAW / "nsp2021"


def tile_box(row: int, col: int):
    x0 = ORIGIN_X + (col - 1) * TILE_M
    y1 = ORIGIN_Y - (row - 1) * TILE_M
    return box(x0, y1 - TILE_M, x0 + TILE_M, y1)


def poland_area_mollweide():
    lau = gpd.read_file(RAW / "boundaries" / "LAU_RG_01M_2021_3035.gpkg", where="CNTR_CODE = 'PL'")
    poly = unary_union(lau.geometry.values)
    return gpd.GeoSeries([poly], crs=lau.crs).buffer(MARGIN_M).to_crs(MOLLWEIDE).iloc[0]


def needed_tiles() -> list[tuple[int, int]]:
    area = poland_area_mollweide()
    return [(r, c) for r in range(1, 19) for c in range(1, 37) if tile_box(r, c).intersects(area)]


def fetch_nsp() -> Path:
    r = requests.get(NSP_FEED, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"
    m = re.search(r'<link href="([^"]*GRID_NSP2021_RES\.zip)"', r.text)
    if not m:
        raise RuntimeError("NSP 2021 SHP entry not found in the ATOM feed")
    url = m.group(1).replace("&amp;", "&")
    dest = download(
        "nsp2021_grid_1km_shp", url, NSP_DIR / "GRID_NSP2021_RES.zip",
        license="GUS INSPIRE service: no access or use conditions (feed 'rights' field); cite GUS NSP 2021",
        source="GUS Portal Geostatystyczny, ATOM PD.GRID.2021 (siatka 1 km, rezydenci, EPSG:2180)",
        data_date="2021-03-31", notes="NSP 2021 reference date 31 March 2021; residents",
    )
    ex = NSP_DIR / "extracted"
    if not ex.exists():
        ex.mkdir(parents=True)
        with zipfile.ZipFile(dest) as z:
            for n in z.namelist():  # data only; refuse path traversal
                if ".." in n or n.startswith("/"):
                    raise RuntimeError(f"unsafe zip member {n}")
            z.extractall(ex)
    return dest


def fetch_ghsl() -> dict[str, list[Path]]:
    tiles = needed_tiles()
    paths: dict[str, list[Path]] = {}
    for key, (sub, prefix) in PRODUCTS.items():
        paths[key] = []
        for row, col in tiles:
            name = f"{prefix}_R{row}_C{col}.zip"
            dest = download(f"{key}_2020_R{row}_C{col}", GHSL_BASE + sub + name, GHSL_DIR / key / name,
                            license=GHSL_LICENSE, source=f"JRC GHSL {key.upper()} R2023A E2020 100 m Mollweide",
                            data_date="2020", timeout=600)
            tif = GHSL_DIR / key / name.replace(".zip", ".tif")
            if not tif.exists():
                with zipfile.ZipFile(dest) as z:
                    member = [n for n in z.namelist() if n.lower().endswith(".tif")]
                    assert len(member) == 1, z.namelist()
                    tif.write_bytes(z.read(member[0]))
            paths[key].append(tif)
    return paths


def verify_and_vrt(paths: dict[str, list[Path]]) -> dict:
    info: dict = {}
    for key, tifs in paths.items():
        rows, bounds, sizes = [], [], []
        for tif in tifs:
            m = re.search(r"_R(\d+)_C(\d+)\.tif$", tif.name)
            row, col = int(m.group(1)), int(m.group(2))
            with rasterio.open(tif) as src:
                exp = tile_box(row, col).bounds
                ok = all(abs(a - b) < 1 for a, b in zip(src.bounds, exp))
                rows.append({"tile": f"R{row}_C{col}", "crs": (src.crs.to_string()[:40] if src.crs else None),
                             "res": list(src.res), "size": [src.width, src.height], "nodata": src.nodata,
                             "dtype": src.dtypes[0], "bounds_match_schema": ok})
                bounds.append(src.bounds)
                sizes.append((src.width, src.height))
                crs_wkt, dtype, nodata = src.crs.to_wkt(), src.dtypes[0], src.nodata
        info[key] = rows
        x0 = min(b.left for b in bounds)
        x1 = max(b.right for b in bounds)
        y0 = min(b.bottom for b in bounds)
        y1 = max(b.top for b in bounds)
        W, H = round((x1 - x0) / 100), round((y1 - y0) / 100)
        gdt = {"uint8": "Byte", "float32": "Float32", "float64": "Float64", "int32": "Int32", "uint32": "UInt32", "uint16": "UInt16", "int16": "Int16"}[dtype]
        parts = []
        for t, b, (w, h) in zip(tifs, bounds, sizes):
            parts.append(
                f'<SimpleSource><SourceFilename relativeToVRT="1">{t.name}</SourceFilename><SourceBand>1</SourceBand>'
                f'<SrcRect xOff="0" yOff="0" xSize="{w}" ySize="{h}"/>'
                f'<DstRect xOff="{round((b.left - x0) / 100)}" yOff="{round((y1 - b.top) / 100)}" xSize="{w}" ySize="{h}"/></SimpleSource>')
        nd = f"<NoDataValue>{nodata}</NoDataValue>" if nodata is not None else ""
        vrt = GHSL_DIR / key / f"{key}_2020_poland.vrt"
        vrt.write_text(
            f'<VRTDataset rasterXSize="{W}" rasterYSize="{H}"><SRS>{escape(crs_wkt)}</SRS>'
            f'<GeoTransform>{x0}, 100, 0, {y1}, 0, -100</GeoTransform>'
            f'<VRTRasterBand dataType="{gdt}" band="1">{nd}\n' + "\n".join(parts) + "\n</VRTRasterBand></VRTDataset>\n",
            encoding="utf-8")
        with rasterio.open(vrt) as v:
            info[key + "_vrt"] = {"path": vrt.relative_to(RAW.parent.parent).as_posix(), "size": [v.width, v.height],
                                  "res": list(v.res), "nodata": v.nodata, "crs": bool(v.crs)}
    return info


def main() -> None:
    fetch_nsp()
    paths = fetch_ghsl()
    info = verify_and_vrt(paths)
    write_json(INTERIM / "population" / "ghsl_tiles.json", info)
    print(sorted({r["tile"] for r in info["ghs_pop"]}))
    print("tiles not matching schema:", [r for k in PRODUCTS for r in info[k] if not r["bounds_match_schema"]])
    print(info["ghs_pop"][0], info["ghs_pop_vrt"], info["ghs_built_s"][0])


if __name__ == "__main__":
    main()
