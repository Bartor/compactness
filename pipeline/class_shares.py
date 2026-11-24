"""Residents and cells per colour class of every grid value layer (for the web legend and charts).

    python -m pipeline.class_shares

For each ready ``choropleth`` layer of results/web/catalog.json that pipeline.tiles builds, the class of every drawn
250 m cell is the one the tile loaders of pipeline.tiles_layers give it (the loaders are called, not copied), and the
residents are the census-scaled population of the cell (pop_ghsl_census_scaled of data/interim/popgrid).  Per
agglomeration, and for the key "all" (the layer's whole coverage), for the whole functional area ("fua") and for the
core city ("core"): residents and number of cells per class in ramp order, plus residents and cells of the no-data
cells where the layer draws them.

Writes results/web/class_shares.json (sorted keys, populations rounded to whole people, LF) and
results/web/_meta_class_shares.json.  The cell counts are checked against results/qa/tiles/stats.json: the area of
every class of every agglomeration there (km2, from the same class grid) must equal cells x 0.0625 km2.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import tiles as T
from pipeline.common import RESULTS, load_config, write_meta
from pipeline.tiles_core import CELL, FIRST_CLASS, NODATA

WEB = RESULTS / "web"
QA_STATS = RESULTS / "qa" / "tiles" / "stats.json"
POPGRID = T.TL.POPGRID
CELL_KM2 = CELL * CELL / 1e6
OUT = WEB / "class_shares.json"
SOURCES = ["results/layers/frequent_cells.parquet", "results/layers/access_cells.parquet",
           "data/interim/popgrid/cells_*.parquet", "results/web/catalog.json"]


def _ll(ids: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    p = ids.str.extract(r"^E(\d+)N(\d+)$").astype("int64")
    return p[0].to_numpy(), p[1].to_numpy()


def population_rasters(grid, aggs: list[str]) -> tuple[np.ndarray, np.ndarray, int]:
    """Residents and core flag laid on the class grid, plus the number of drawn cells with no population row."""
    pop = np.zeros(grid.codes.shape, np.float64)
    core = np.zeros(grid.codes.shape, bool)
    seen = np.zeros(grid.codes.shape, bool)
    h, w = grid.codes.shape
    for agg in aggs:
        fn = POPGRID / f"cells_{agg}.parquet"
        d = pd.read_parquet(fn, columns=["cell_id", "pop_ghsl_census_scaled", "in_fua", "in_core"])
        d = d[d.in_fua]
        xll, yll = _ll(d.cell_id)
        col = (xll - int(grid.x0)) // int(CELL)
        row = (int(grid.y1) - yll) // int(CELL) - 1
        ok = (row >= 0) & (row < h) & (col >= 0) & (col < w)
        row, col, d = row[ok], col[ok], d[ok]
        mine = grid.agg[row, col] == aggs.index(agg) + 1      # a cell belongs to the agglomeration the layer drew it for
        row, col, d = row[mine], col[mine], d[mine]
        pop[row, col] = d.pop_ghsl_census_scaled.to_numpy()
        core[row, col] = d.in_core.to_numpy(bool)
        seen[row, col] = True
    unmatched = int(((grid.codes > 0) & ~seen).sum())
    return pop, core, unmatched


def tally(codes: np.ndarray, pop: np.ndarray, sel: np.ndarray, classes: list[int], has_nodata: bool) -> dict:
    """Residents and cells per class (ramp order) of the cells in `sel`."""
    c = codes[sel]
    p = pop[sel]
    n = max(classes) + 1
    cells = np.bincount(c, minlength=max(n, NODATA + 1))
    people = np.bincount(c, weights=p, minlength=max(n, NODATA + 1))
    return {
        "pop": [int(round(people[k])) for k in classes],
        "cells": [int(cells[k]) for k in classes],
        "nodata_pop": int(round(people[NODATA])) if has_nodata else None,
        "nodata_cells": int(cells[NODATA]) if has_nodata else None,
    }


def add(a: dict, b: dict) -> dict:
    """Sum of two tallies (exact: integers are summed before rounding is lost only per agglomeration)."""
    out = {"pop": [x + y for x, y in zip(a["pop"], b["pop"])], "cells": [x + y for x, y in zip(a["cells"], b["cells"])]}
    for k in ("nodata_pop", "nodata_cells"):
        out[k] = None if a[k] is None else a[k] + b[k]
    return out


def layer_shares(layer, cfg: dict, entry: dict) -> tuple[dict, dict] | None:
    built = layer.load(cfg)
    if built is None:
        return None
    classes = sorted(c["code"] for c in built.classes if c["code"] != NODATA)
    if len(classes) != len(entry["ramp"]["colors"]) or classes != list(range(FIRST_CLASS, FIRST_CLASS + len(classes))):
        raise ValueError(f"{layer.id}: classes of the loader do not match the catalog ramp")
    has_nodata = any(c["code"] == NODATA for c in built.classes)
    pop, core, unmatched = population_rasters(built.grid, built.aggs)
    codes = built.grid.codes
    out: dict[str, dict] = {}
    for i, agg in enumerate(built.aggs):
        in_agg = built.grid.agg == i + 1
        out[agg] = {"fua": tally(codes, pop, in_agg, classes, has_nodata),
                    "core": tally(codes, pop, in_agg & core, classes, has_nodata)}
    out["all"] = {k: _sum_all([out[a][k] for a in built.aggs]) for k in ("fua", "core")}
    return out, {"cells": int(built.extra["cells"]), "unmatched_cells": unmatched, "classes": classes}


def _sum_all(parts: list[dict]) -> dict:
    total = parts[0]
    for p in parts[1:]:
        total = add(total, p)
    return total


def check_against_tiles(layer_id: str, shares: dict, classes: list[int], has_nodata: bool, stats: dict) -> dict:
    """Cells per class of every agglomeration x 0.0625 km2 against the area the tile build verified (source_km2)."""
    s = stats.get(layer_id)
    if not s:
        return {"compared": 0, "note": "layer not in results/qa/tiles/stats.json"}
    compared = 0
    worst = 0.0
    problems = []
    for row in s["verify"]["area"]:
        agg, code = row["agg"], row["code"]
        k = classes.index(code) if code in classes else None
        fua = shares[agg]["fua"]
        cells = fua["cells"][k] if k is not None else (fua["nodata_cells"] if code == NODATA else None)
        if cells is None:
            problems.append(f"{agg} code {code}: class not in output")
            continue
        diff = abs(cells * CELL_KM2 - row["source_km2"])
        worst = max(worst, diff)
        compared += 1
        if diff > 0.0015:          # source_km2 is rounded to 1e-3 km2
            problems.append(f"{agg} code {code}: {cells} cells = {cells * CELL_KM2:.3f} km2, stats {row['source_km2']}")
    total_stats = s.get("cells")
    total_out = sum(shares[a]["fua"]["cells"][k] for a in shares if a != "all" for k in range(len(classes)))
    total_out += sum(shares[a]["fua"]["nodata_cells"] or 0 for a in shares if a != "all")
    if total_stats is not None and total_out != total_stats:
        problems.append(f"total cells {total_out} != stats {total_stats}")
    return {"compared": compared, "max_abs_diff_km2": round(worst, 4), "total_cells": total_out,
            "total_cells_stats": total_stats, "problems": problems}


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    cat = json.loads((WEB / "catalog.json").read_text(encoding="utf-8"))
    stats = json.loads(QA_STATS.read_text(encoding="utf-8")) if QA_STATS.exists() else {}
    table = T.layer_table(cfg)
    layers: dict[str, dict] = {}
    checks: dict[str, dict] = {}
    for entry in cat["layers"]:
        if entry.get("kind") != "choropleth" or entry.get("status") != "ready" or entry["id"] not in table:
            continue
        print(f"[{entry['id']}]")
        got = layer_shares(table[entry["id"]], cfg, entry)
        if got is None:
            print("  source data missing: skipped")
            continue
        shares, info = got
        layers[entry["id"]] = shares
        has_nodata = shares["all"]["fua"]["nodata_pop"] is not None
        checks[entry["id"]] = check_against_tiles(entry["id"], shares, info["classes"], has_nodata, stats)
        checks[entry["id"]]["unmatched_cells"] = info["unmatched_cells"]
        c = checks[entry["id"]]
        print(f"  {len(shares) - 1} agglomerations; cells vs stats.json: {c['compared']} class areas compared, "
              f"max diff {c.get('max_abs_diff_km2')} km2, problems {len(c.get('problems', []))}, "
              f"cells without a population row {info['unmatched_cells']}")
    bad = {k: v["problems"] for k, v in checks.items() if v.get("problems")}
    if bad:
        raise RuntimeError(f"cell counts differ from results/qa/tiles/stats.json: {bad}")
    doc = {"generated": dt.date.today().isoformat(), "layers": layers}
    OUT.write_text(json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n",
                   encoding="utf-8", newline="\n")
    with tempfile.TemporaryDirectory() as tmp:
        write_meta(Path(tmp), "class_shares", started=t0,
                   extra={"sources": SOURCES, "layers": sorted(layers), "checks": checks,
                          "outputs": ["../web/class_shares.json"]})
        shutil.copyfile(Path(tmp) / "_meta.json", WEB / "_meta_class_shares.json")
    print(f"wrote {OUT.relative_to(RESULTS.parent)}: {OUT.stat().st_size / 1e3:.0f} kB, {len(layers)} layers")


if __name__ == "__main__":
    main()
