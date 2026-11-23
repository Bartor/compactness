"""The four map layers: source data -> class grid -> catalog entry (brief §8, §14.4).

A layer is read from the committed layer parquets (or the phase-1 population grid), every populated
250 m cell is put into a ramp class, and the class grid goes to pipeline.tiles_core.  The ``v`` property of
the tiles is a representative value inside the class, chosen so that the web's ``step`` expression over the
catalog ramp picks the class colour.  No-data features carry no ``v``.
"""
from __future__ import annotations

import glob
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio import features
from rasterio.transform import Affine

from pipeline.common import INTERIM, RESULTS
from pipeline.tiles_core import BLOCK, CELL, FIRST_CLASS, NODATA, ClassGrid

LAYERS_DIR = RESULTS / "layers"
POPGRID = INTERIM / "popgrid"
CELL_KM2 = CELL * CELL / 1e6
POP_DATE = "2021-03-31 (NSP 2021, wzór GHSL 2020)"

ATTR_DENSITY = "GUS NSP 2021, JRC GHSL"
ATTR_TRANSIT = "wydawcy GTFS (lista w „O danych”), © współtwórcy OpenStreetMap, GUS, JRC GHSL"

# Ramps.  The first colour is the one below the first stop (rampClasses in web/src/ramp.js).
DENSITY_STOPS = [500, 1000, 2500, 5000, 10000, 20000]
DENSITY_REPS = [250, 750, 1750, 3750, 7500, 15000, 25000]
DENSITY_COLORS = ["#F5E1A4", "#F0C36D", "#E39A3B", "#C9701E", "#9E4A12", "#702C0A", "#431A06"]

HEADWAY_CLASSES = ["5", "10", "15", "20", "30", ">30"]
HEADWAY_V = [5, 10, 15, 20, 30, 60]
HEADWAY_STOPS = [10, 15, 20, 30, 60]
HEADWAY_COLORS = ["#16348F", "#1D4ED8", "#4F78DE", "#7FA3E3", "#AAC4EA", "#D3E0F3"]
HEADWAY_LABELS = ["co ≤ 5 min", "co ≤ 10 min", "co ≤ 15 min", "co ≤ 20 min", "co ≤ 30 min",
                  "rzadziej niż co 30 min lub brak"]

PERF_STOPS = [10, 20, 30, 40, 50, 60]
PERF_REPS = [5, 15, 25, 35, 45, 55, 65]
PERF_COLORS = ["#D6E3F5", "#ADC6EC", "#84A8E3", "#5B89DA", "#3569D5", "#1D4ED8", "#16348F"]


@dataclass
class Built:
    grid: ClassGrid
    aggs: list[str]                         # agglomeration index (grid.agg - 1) -> id
    props: dict[int, dict]                  # class code -> feature properties
    classes: list[dict]                     # report: code, label, v
    extra: dict = field(default_factory=dict)


@dataclass
class Layer:
    id: str
    source_layer: str
    file_prefix: str
    load: Callable
    describe: Callable                      # (cfg, built, names) -> catalog entry


# ------------------------------------------------------------------ helpers
def _parse_ll(ids: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """cell_id 'E<x0>N<y0>' (lower-left corner in EPSG:2180) -> x0, y0."""
    p = ids.str.extract(r"^E(\d+)N(\d+)$").astype("int64")
    return p[0].to_numpy(), p[1].to_numpy()


def _ramp_codes(values: np.ndarray, stops: list[float]) -> np.ndarray:
    return (np.searchsorted(stops, values, side="right") + FIRST_CLASS).astype(np.uint8)


def _grid(xll, yll, code, agg_names: list[str], agg_col) -> tuple[ClassGrid, list[str]]:
    aggs = sorted(set(agg_names))
    idx = {a: i for i, a in enumerate(aggs)}
    return ClassGrid.from_cells(xll, yll, code, np.array([idx[a] for a in agg_col], np.uint8)), aggs


def _classes(labels: list[str], reps: list[int]) -> tuple[dict, list[dict]]:
    props = {FIRST_CLASS + i: {"v": v} for i, v in enumerate(reps)}
    classes = [{"code": FIRST_CLASS + i, "label": lab, "v": v} for i, (lab, v) in enumerate(zip(labels, reps))]
    return props, classes


def _density_labels() -> list[str]:
    s = DENSITY_STOPS
    nf = lambda v: f"{v:,}".replace(",", " ")  # noqa: E731
    return ([f"< {nf(s[0])}"] + [f"{nf(a)}–{nf(b)}" for a, b in zip(s, s[1:])] + [f"≥ {nf(s[-1])}"])


def _perf_labels() -> list[str]:
    s = PERF_STOPS
    return [f"< {s[0]}"] + [f"{a}–{b}" for a, b in zip(s, s[1:])] + [f"≥ {s[-1]}"]


# ------------------------------------------------------------------ loaders
def load_density(cfg) -> Built | None:
    files = sorted(glob.glob(str(POPGRID / "cells_*.parquet")))
    if not files:
        return None
    parts = []
    for fn in files:
        agg = Path(fn).stem[len("cells_"):]
        d = pd.read_parquet(fn, columns=["cell_id", "pop_ghsl_census_scaled", "in_fua"])
        d = d[d.in_fua & (d.pop_ghsl_census_scaled > 0)].copy()
        d["ag"] = agg
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    xll, yll = _parse_ll(d.cell_id)
    dens = d.pop_ghsl_census_scaled.to_numpy() / CELL_KM2
    code = _ramp_codes(dens, DENSITY_STOPS)
    grid, aggs = _grid(xll, yll, code, list(d["ag"].unique()), d["ag"])
    props, classes = _classes(_density_labels(), DENSITY_REPS)
    return Built(grid, aggs, props, classes, {"cells": int(len(d))})


def load_frequent(cfg) -> Built | None:
    fn = LAYERS_DIR / "frequent_cells.parquet"
    if not fn.exists():
        return None
    d = pd.read_parquet(fn, columns=["agglomeration", "cell_id", "pop_census_scaled", "headway_class_all", "in_mask_all"])
    n_all = len(d)
    d = d[d.pop_census_scaled > 0].reset_index(drop=True)
    xll, yll = _parse_ll(d.cell_id)
    code = np.full(len(d), NODATA, np.uint8)
    mask = d.in_mask_all.to_numpy(bool)
    lab = d.headway_class_all
    bad = set(lab[mask].dropna().unique()) - set(HEADWAY_CLASSES)
    if bad or lab[mask].isna().any():
        raise ValueError(f"frequent_cells: unexpected headway classes {bad} / missing inside the mask")
    for i, c in enumerate(HEADWAY_CLASSES):
        code[mask & (lab == c).to_numpy()] = FIRST_CLASS + i
    grid, aggs = _grid(xll, yll, code, list(d.agglomeration.unique()), d.agglomeration)
    props, classes = _classes(HEADWAY_LABELS, HEADWAY_V)
    props[NODATA] = {}
    classes.insert(0, {"code": NODATA, "label": "brak danych GTFS", "v": None})
    return Built(grid, aggs, props, classes, {"cells": int(len(d)), "dropped_zero_pop": n_all - len(d)})


def load_performance(cfg) -> Built | None:
    fn = LAYERS_DIR / "access_cells.parquet"
    if not fn.exists():
        return None
    d = pd.read_parquet(fn, columns=["agglomeration", "cell_id", "pop_census_scaled", "in_mask_all", "tp_pt_am_30"])
    have = sorted(d.loc[d.in_mask_all & d.tp_pt_am_30.notna(), "agglomeration"].unique())
    d = d[d.agglomeration.isin(have) & (d.pop_census_scaled > 0)].reset_index(drop=True)
    if d.empty:
        return None
    xll, yll = _parse_ll(d.cell_id)
    val = d.tp_pt_am_30.to_numpy(np.float64)
    ok = d.in_mask_all.to_numpy(bool) & ~np.isnan(val)
    code = np.full(len(d), NODATA, np.uint8)
    code[ok] = _ramp_codes(val[ok], PERF_STOPS)
    grid, aggs = _grid(xll, yll, code, list(d.agglomeration.unique()), d.agglomeration)
    props, classes = _classes(_perf_labels(), PERF_REPS)
    props[NODATA] = {}
    classes.insert(0, {"code": NODATA, "label": "brak danych GTFS", "v": None})
    return Built(grid, aggs, props, classes, {"cells": int(len(d)), "present": aggs})


def load_mask(cfg) -> Built | None:
    fn = LAYERS_DIR / "gtfs_coverage_mask.parquet"
    if not fn.exists():
        return None
    g = gpd.read_parquet(fn)
    # The file declares EPSG:2180 but holds lon/lat degrees (pipeline.frequent.mask_polygons reprojects the
    # values and keeps the old CRS label): trust the numbers, not the label.
    if not (g.total_bounds[2] < 180 and g.total_bounds[3] < 90):
        raise ValueError("gtfs_coverage_mask.parquet: expected lon/lat coordinates")
    g = g.set_crs(4326, allow_override=True)
    g = g[(g.feed_variant == "all") & (g.status_code == 3)].to_crs(2180)
    aggs = sorted(g.agglomeration.unique())
    xmin, ymin, xmax, ymax = g.total_bounds
    span = int(CELL * BLOCK)
    x0 = int(np.floor(xmin / span) * span)
    y1 = int(np.ceil(ymax / span) * span)
    w = int(np.ceil((xmax - x0) / CELL)) + 1
    h = int(np.ceil((y1 - ymin) / CELL)) + 1
    ras = features.rasterize(
        [(geom, aggs.index(a) + 1) for geom, a in zip(g.geometry, g.agglomeration)],
        out_shape=(h, w), transform=Affine(CELL, 0, x0, 0, -CELL, y1), fill=0, dtype="uint8", all_touched=False)
    rows, cols = np.nonzero(ras)
    xll = x0 + cols * int(CELL)
    yll = y1 - (rows + 1) * int(CELL)
    grid = ClassGrid.from_cells(xll, yll, np.full(len(rows), NODATA, np.uint8), ras[rows, cols] - 1)
    area_src = {a: float(g[g.agglomeration == a].area.sum() / 1e6) for a in aggs}
    return Built(grid, aggs, {NODATA: {}}, [{"code": NODATA, "label": "brak danych GTFS", "v": None}],
                 {"cells": int(len(rows)), "source_area_km2": area_src})


# ------------------------------------------------------------------ catalog entries
def _base(cfg, title, attribution, note, **kw) -> dict:
    return {"status": "ready", "title": title, "attribution": attribution, "note": note,
            "population_date": None, "timetable_date": None, **kw}


def describe_density(cfg, built: Built, names: dict, url: str) -> dict:
    note = ("Komórki 250 m w granicach FUA; ludność ze spisu NSP 2021 rozłożona wzorem GHSL 2020. "
            "Komórki bez ludności nie są rysowane: to rzeczywiste zero, a nie brak danych. "
            "Kolor oznacza przedział gęstości, nie wartość komórki; przy większości komórek gęstość jest "
            f"poniżej {DENSITY_STOPS[0]} os./km².")
    return _base(cfg, "Gęstość zaludnienia 250 m (NSP 2021)", ATTR_DENSITY, note, kind="choropleth", type="pmtiles",
                 url=url, source_layer="density250", property="v", unit="os./km²", has_nodata=False,
                 population_date=POP_DATE,
                 ramp={"stops": DENSITY_STOPS, "colors": DENSITY_COLORS})


def describe_frequent(cfg, built: Built, names: dict, url: str) -> dict:
    day = cfg["reference_day"]
    note = ("Najlepszy odstęp między kursami (średnia 6:00–20:00, dzień roboczy) przy zespole przystanków w zasięgu "
            "500 m pieszo po sieci OSM; kolor oznacza klasę, w której leży co najmniej połowa punktów próbkowania "
            "komórki. Komórki poza pokryciem danych GTFS są kreskowane jako brak danych, nie jako brak komunikacji. "
            "Wszystkie feedy, w tym nieoficjalne. Rysowane są komórki z ludnością.")
    return _base(cfg, "Zasięg częstej komunikacji", ATTR_TRANSIT, note, kind="choropleth", type="pmtiles", url=url,
                 source_layer="frequent", property="v", unit="odstęp między kursami", has_nodata=True,
                 population_date=POP_DATE, timetable_date=day,
                 ramp={"stops": HEADWAY_STOPS, "colors": HEADWAY_COLORS, "labels": HEADWAY_LABELS})


def describe_performance(cfg, built: Built, names: dict, url: str, expected: list[str]) -> dict:
    day = cfg["reference_day"]
    present = built.extra["present"]
    pending = [names.get(a, a) for a in expected if a not in present]
    note = ("Odsetek ludności z okolicy (promień odpowiadający 15 km/h, 7,5 km), który można osiągnąć w 30 min "
            "komunikacją i pieszo; środa 7:00–9:00, mediana z odjazdów co minutę; wartości w %. "
            "Komórki poza pokryciem danych GTFS są kreskowane jako brak danych. Wszystkie feedy, w tym nieoficjalne. "
            "Rysowane są komórki z ludnością.")
    if pending:
        done = ", ".join(names.get(a, a) for a in present)
        note += f" Policzono: {done}. W trakcie obliczeń: {', '.join(pending)}."
    return _base(cfg, "Transport performance 30 min", ATTR_TRANSIT, note, kind="choropleth", type="pmtiles", url=url,
                 source_layer="performance30", property="v", unit="% ludności osiągalnej w 30 min",
                 has_nodata=True, population_date=POP_DATE, timetable_date=day,
                 ramp={"stops": PERF_STOPS, "colors": PERF_COLORS})


def describe_mask(cfg, built: Built, names: dict, url: str) -> dict:
    day = cfg["reference_day"]
    note = ("Obszar FUA, w którym nie da się ocenić komunikacji: w promieniu 1 km od środka komórki mniej niż 85 % "
            "przystanków z OpenStreetMap ma odpowiednik w rozkładach GTFS (brak feedu albo luki w nim), więc brak "
            "kursów na mapie nie oznacza ich braku w rzeczywistości. Komórki bez żadnego przystanku w promieniu 1 km "
            "mają dane i nie są kreskowane. Wszystkie feedy, w tym nieoficjalne.")
    return _base(cfg, "Brak danych GTFS", ATTR_TRANSIT, note, kind="mask", type="pmtiles", url=url,
                 source_layer="gtfs_nodata", legend="obszar bez danych o rozkładach (GTFS)", timetable_date=day)
