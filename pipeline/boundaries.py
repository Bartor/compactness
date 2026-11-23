"""Agglomeration geometries for later pipeline steps (all in EPSG:2180).

    from pipeline.boundaries import load_agglomeration
    a = load_agglomeration("wroclaw")
    a["fua"], a["core"], a["buffered"]      # shapely geometries in EPSG:2180

Sources: Eurostat GISCO URAU 2021 (100K scale) and LAU 2021 (see pipeline/fetch_boundaries.py).
URAU codes come from ``config.yaml`` (``agglomerations.<id>.fua_codes`` / ``city_codes``).

Special cases
* Trojmiasto: Sopot is not a URAU city; it lies inside FUA Gdansk (PL006F).  The core is
  Gdansk + Gdynia (URAU cities) + the LAU unit Sopot.
* GZM: ``boundary_variant`` in config is ``fua_union`` (FUAs listed in ``fua_codes``, which
  intersect Metropolis GZM; the default, provisional) or ``metropolis`` (union of the 41
  member gminas of Metropolia GZM dissolved from LAU).  ``null`` falls back to ``fua_union``
  with a warning.  The core is the same in both variants (URAU cities listed in ``city_codes``).
"""
from __future__ import annotations

import functools
import unicodedata
import warnings
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from pipeline.common import CRS_METRIC, RAW, load_config

BOUNDARIES = RAW / "boundaries"
URAU_FILE = BOUNDARIES / "URAU_RG_100K_2021_3035.gpkg"
LAU_FILE = BOUNDARIES / "LAU_RG_01M_2021_3035.gpkg"
EDGE_BUFFER_M = 15_000

# Member gminas of Metropolia GZM (41).  Source: metropoliagzm.pl/metropolia-dzis/ (five
# subregions, "41 miast i gmin"); same list on pl.wikipedia.org "Gornoslasko-Zaglebiowska
# Metropolia"; legal basis: ustawa z 9 III 2017 o zwiazku metropolitalnym w woj. slaskim
# (Dz.U. 2017 poz. 730; consolidated text Dz.U. 2025 poz. 186), regulation of 26 VI 2017
# (Dz.U. 2017 poz. 1290), in force from 1 VII 2017.  Jaworzno is NOT a member.
GZM_GMINAS = [
    "Będzin", "Bieruń", "Bobrowniki", "Bojszowy", "Bytom", "Chełm Śląski", "Chorzów", "Czeladź",
    "Dąbrowa Górnicza", "Gierałtowice", "Gliwice", "Imielin", "Katowice", "Knurów", "Kobiór",
    "Lędziny", "Łaziska Górne", "Mierzęcice", "Mikołów", "Mysłowice", "Ożarowice",
    "Piekary Śląskie", "Pilchowice", "Psary", "Pyskowice", "Radzionków", "Ruda Śląska",
    "Rudziniec", "Siemianowice Śląskie", "Siewierz", "Sławków", "Sosnowiec", "Sośnicowice",
    "Świerklaniec", "Świętochłowice", "Tarnowskie Góry", "Tychy", "Wojkowice", "Wyry", "Zabrze",
    "Zbrosławice",
]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


@functools.lru_cache(maxsize=1)
def load_urau() -> gpd.GeoDataFrame:
    """All Polish URAU 2021 units (cities 'C' and FUAs 'F') in EPSG:2180."""
    g = gpd.read_file(URAU_FILE, where="CNTR_CODE = 'PL'").to_crs(CRS_METRIC)
    g["URAU_NAME"] = g["URAU_NAME"].map(_norm)
    return g.sort_values("URAU_CODE").reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def load_lau() -> gpd.GeoDataFrame:
    """Polish LAU 2021 (gminas) in EPSG:2180 (1:1M scale geometry; POP_2021, AREA_KM2 attributes)."""
    g = gpd.read_file(LAU_FILE, where="CNTR_CODE = 'PL'").to_crs(CRS_METRIC)
    g["LAU_NAME"] = g["LAU_NAME"].map(_norm)
    return g.sort_values("LAU_ID").reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def gzm_gminas() -> gpd.GeoDataFrame:
    """LAU units of the 41 GZM member gminas.  Name clashes resolved by distance to Katowice."""
    lau = load_lau()
    kat = lau[lau.LAU_NAME == "Katowice"].geometry.iloc[0].centroid
    rows = []
    for name in GZM_GMINAS:
        c = lau[lau.LAU_NAME == name].copy()
        if c.empty:
            raise RuntimeError(f"GZM gmina not found in LAU: {name}")
        c["d"] = c.geometry.centroid.distance(kat)
        rows.append(c.sort_values("d").iloc[[0]].drop(columns="d"))
    out = gpd.GeoDataFrame(pd.concat(rows), crs=lau.crs)
    if len(out) != 41 or out.LAU_ID.nunique() != 41:
        raise RuntimeError("expected 41 distinct GZM gminas")
    return out


def gzm_boundary() -> BaseGeometry:
    """Metropolia GZM boundary: union of the 41 member gminas (LAU 2021)."""
    return unary_union(gzm_gminas().geometry.values)


def _union(codes: list[str]) -> BaseGeometry:
    u = load_urau().set_index("URAU_CODE")
    missing = [c for c in codes if c not in u.index]
    if missing:
        raise KeyError(f"URAU codes not found: {missing}")
    return unary_union(u.loc[codes].geometry.values)


def load_agglomeration(agg_id: str, boundary_variant: str | None = None) -> dict[str, Any]:
    """Return dict(id, name, phase, fua, core, buffered, fua_codes, city_codes, variant).

    Geometries are shapely objects in EPSG:2180; ``buffered`` = FUA + 15 km (config
    ``edge_buffer_km``).  ``boundary_variant`` overrides the GZM config switch.
    """
    cfg = load_config()
    a = cfg["agglomerations"][agg_id]
    fua_codes, city_codes = list(a.get("fua_codes") or []), list(a.get("city_codes") or [])
    if not fua_codes:
        raise ValueError(f"{agg_id}: fua_codes empty in config.yaml (run phase-0 boundaries)")
    variant = None
    fua = _union(fua_codes)
    core = _union(city_codes) if city_codes else None
    if agg_id == "trojmiasto":
        sopot = load_lau()
        sopot = sopot[sopot.LAU_NAME == "Sopot"].geometry
        core = unary_union([core, *sopot.values]) if core is not None else sopot.iloc[0]
    if agg_id == "gzm":
        variant = boundary_variant or a.get("boundary_variant")
        if variant is None:
            warnings.warn("gzm.boundary_variant is null in config.yaml: using provisional 'fua_union'")
            variant = "fua_union"
        if variant == "metropolis":
            fua = gzm_boundary()
        elif variant != "fua_union":
            raise ValueError(f"unknown GZM boundary_variant {variant!r}")
    buf_m = float(cfg.get("edge_buffer_km", 15)) * 1000
    return {
        "id": agg_id, "name": a["name"], "phase": a["phase"],
        "fua": fua, "core": core, "buffered": fua.buffer(buf_m),
        "fua_codes": fua_codes, "city_codes": city_codes, "variant": variant,
    }


def all_agglomeration_ids() -> list[str]:
    return list(load_config()["agglomerations"])
