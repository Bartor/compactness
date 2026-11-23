"""Merge the per-step metric tables and cut the subset shown in the map's details panel.

Inputs  (one pair per step, all in results/metrics/)
* metrics_density.csv/json   phase 1
* metrics_supply.csv/json    phase 2 (extra column feed_variant)
* metrics_frequent.csv/json  phase 2 (extra columns feed_variant, population_grid)
* metrics_access.csv/json    phase 3 (feed_variant empty for walk / bike, which do not depend on the feeds)

Outputs
* results/metrics/metrics.csv + metrics.json   union of all steps, columns COLUMNS, deterministic sort;
  values are kept exactly as the steps wrote them (4 significant digits), missing = null / empty, never 0
* results/web/metrics.json                     panel subset (PANEL below), same JSON shape; this is the only
  metrics file shipped to the site
* results/metrics/_meta.json                   step files with their sha256

Run:  python -m pipeline.merge_metrics   (idempotent; fails on duplicate keys)
"""
from __future__ import annotations

import csv
import hashlib
import json
import time

from pipeline.common import RESULTS, write_json, write_meta

METRICS = RESULTS / "metrics"
WEB = RESULTS / "web"
STEPS = ["density", "supply", "frequent", "access"]

COLUMNS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
           "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid", "step"]
KEY = ("agglomeration", "domain", "metric", "feed_variant", "population_grid")

# ---------------------------------------------------------------------------------------------------------
# Panel subset: (domain, metric id) -> (order, short Polish label).  Rows within a domain are listed in this
# order.  Only the preferred variant is kept: feed_variant "all" (supply, frequent) and the census-scaled
# GHSL grid (frequent).  Anything not listed here is not shipped to the site.
# ---------------------------------------------------------------------------------------------------------
PANEL_FEED_VARIANT = "all"
PANEL_POP_GRID = "ghsl_census_scaled"

_FREQ = [(5, "5"), (10, "10"), (15, "15"), (20, "20"), (30, "30")]
PANEL: dict[tuple[str, str], tuple[int, str]] = {}
for _dom in ("fua", "core"):
    _o = {"fua": 100, "core": 100}[_dom]
    PANEL[(_dom, "area")] = (_o + 1, "Powierzchnia")
    PANEL[(_dom, "population_census")] = (_o + 2, "Ludność (spis 2021)")
    PANEL[(_dom, "density_gross")] = (_o + 3, "Gęstość brutto")
    PANEL[(_dom, "pwdens_census_1km")] = (_o + 4, "Gęstość ważona populacją (spis, siatka 1 km)")
    PANEL[(_dom, "rho_t20")] = (_o + 5, "Indeks Bertauda ρ (zabudowa ≥ 20 %)")
    PANEL[(_dom, "rho_nearest_t20")] = (_o + 6, "Indeks Bertauda ρ do najbliższego centrum (≥ 20 %)")
    PANEL[(_dom, "profile_r50_km")] = (_o + 7, "Promień obejmujący połowę ludności")
    # supply: vehicle-km per inhabitant per day, all modes
    PANEL[(_dom, "vkm_per_cap_day_total")] = (_o + 8, "Wozokilometry na mieszkańca na dobę (wszystkie środki)")
# supply: tram operating speed of the city's tram network (its own domain)
PANEL[("city_tram_network", "tram_speed_median")] = (1, "Prędkość eksploatacyjna tramwajów (mediana kursów)")
# frequent transit (tier "main"): population within 500 m of service at least every N minutes
for _dom in ("core", "covered"):
    for _i, (_n, _s) in enumerate(_FREQ):
        PANEL[(_dom, f"freq_seg_net_le{_n}min")] = (200 + _i, f"Ludność ≤ 500 m od przystanku z kursami co ≤ {_s} min")
    PANEL[(_dom, "rail_ge4dph_net_1km")] = (210, "Ludność ≤ 1 km od stacji kolei lub metra z ≥ 4 odjazdami/h")
# accessibility (phase 3): transport performance, Wednesday 07-09, all feeds, census-scaled grid
for _dom in ("covered", "core"):
    PANEL[(_dom, "tp_pt_am_30min")] = (300, "Transport performance komunikacją + pieszo, 30 min (7–9)")
    PANEL[(_dom, "tp_pt_am_45min")] = (301, "Transport performance komunikacją + pieszo, 45 min (7–9)")
for _dom in ("fua", "core"):
    PANEL[(_dom, "tp_walk_30min")] = (310, "Transport performance pieszo, 30 min")
    PANEL[(_dom, "tp_bike_lts3_30min")] = (311, "Transport performance rowerem, 30 min (LTS ≤ 3)")
    PANEL[(_dom, "tp_bike_lts4_30min")] = (312, "Transport performance rowerem, 30 min (LTS ≤ 4)")


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(v):
    """'' and NaN-like -> None; everything else untouched."""
    if v == "" or (isinstance(v, float) and v != v):
        return None
    return v


def load_step(step: str) -> tuple[list[dict], str | None]:
    raw = json.loads((METRICS / f"metrics_{step}.json").read_text(encoding="utf-8"))
    gen = None
    if isinstance(raw, dict):
        gen = raw.get("generated")
        raw = raw["metrics"]
    rows = []
    for r in raw:
        row = {c: clean(r.get(c)) for c in COLUMNS if c != "step"}
        extra = set(r) - set(COLUMNS)
        if extra:
            raise SystemExit(f"metrics_{step}.json: unexpected columns {sorted(extra)}")
        row["step"] = step
        rows.append(row)
    return rows, gen


def sort_key(r: dict):
    return tuple(r[k] or "" for k in KEY) + (r["step"],)


def check_duplicates(rows: list[dict]) -> None:
    seen: dict[tuple, str] = {}
    dup = []
    for r in rows:
        k = tuple(r[c] for c in KEY)
        if k in seen:
            dup.append((k, seen[k], r["step"]))
        seen[k] = r["step"]
    if dup:
        lines = "\n".join(f"  {k} ({a} / {b})" for k, a, b in dup[:20])
        raise SystemExit(f"merge_metrics: {len(dup)} duplicate keys {KEY}:\n{lines}")


def panel_subset(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        spec = PANEL.get((r["domain"], r["metric"]))
        if spec is None or r["tier"] == "qa":
            continue
        street_only = r["step"] == "access" and r["feed_variant"] is None    # walk / bike: no feed variant
        if r["step"] != "density" and r["feed_variant"] != PANEL_FEED_VARIANT and not street_only:
            continue
        if r["step"] in ("frequent", "access") and r["population_grid"] != PANEL_POP_GRID:
            continue
        out.append((spec[0], {**r, "label": spec[1]}))
    out.sort(key=lambda t: (t[1]["agglomeration"], t[1]["domain"], t[0]))
    return [r for _, r in out]


def write_all(rows: list[dict], generated: str, panel: list[dict]) -> None:
    write_json(METRICS / "metrics.json", {"generated": generated, "metrics": rows})
    with open(METRICS / "metrics.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else r[k]) for k in COLUMNS})
    WEB.mkdir(parents=True, exist_ok=True)
    write_json(WEB / "metrics.json", {"generated": generated, "metrics": panel})


def main() -> None:
    t0 = time.time()
    rows, gens, counts = [], [], {}
    for step in STEPS:
        r, g = load_step(step)
        rows += r
        counts[step] = len(r)
        if g:
            gens.append(g)
    check_duplicates(rows)
    rows.sort(key=sort_key)
    panel = panel_subset(rows)
    missing = sorted(set(PANEL) - {(r["domain"], r["metric"]) for r in panel})
    if missing:
        print(f"note: panel ids without rows: {missing}")
    generated = max(gens) if gens else ""
    write_all(rows, generated, panel)
    files = {}
    for step in STEPS:
        for ext in ("csv", "json"):
            p = METRICS / f"metrics_{step}.{ext}"
            files[p.name] = sha256(p)
    write_meta(METRICS, "merge_metrics", started=t0,
               extra={"step_files": files, "rows": counts, "rows_total": len(rows), "rows_panel": len(panel),
                      "outputs": ["metrics.csv", "metrics.json", "../web/metrics.json"]})
    print(f"merged {counts} -> {len(rows)} rows; panel subset {len(panel)} rows")


if __name__ == "__main__":
    main()
