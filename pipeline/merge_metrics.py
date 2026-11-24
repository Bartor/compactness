"""Merge the per-step metric tables and cut the subset shown in the map's details panel.

Inputs  (one pair per step, all in results/metrics/)
* metrics_density.csv/json   phase 1
* metrics_supply.csv/json    phase 2 (extra column feed_variant)
* metrics_frequent.csv/json  phase 2 (extra columns feed_variant, population_grid)
* metrics_density_service.csv/json  density x service frequency (feed_variant, population_grid)
* metrics_access.csv/json    phase 3 (feed_variant empty for walk / bike, which do not depend on the feeds)
* metrics_access_uc.csv/json phase 3 on the urban-centre domain (domain "urban_centre"; same conventions)
* metrics_transfer.csv/json  ease of transfer in stop areas (no population grid; feed_variant "all")
* metrics_distribution.csv/json  distribution of cell values: share below the access floor, FGT, percentiles
* metrics_speed.csv/json     scheduled speeds by time band, slow tram stretches (feed_variant all / official)
* metrics_form.csv/json      urban form: Angel's indices, polycentricity, Eurostat 2021 urban-centre shares,
                             residents by 250 m density class (no feed variant)

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
import re
import time
import unicodedata

from pipeline.common import RESULTS, load_config, write_json, write_meta

METRICS = RESULTS / "metrics"
WEB = RESULTS / "web"
STEPS = ["density", "supply", "frequent", "density_service", "access", "access_uc", "transfer", "distribution", "form", "speed"]
ACCESS_STEPS = ("access", "access_uc")

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
PANEL[("city_tram_network", "tram_speed_median")] = (1, "Prędkość komunikacyjna tramwajów (mediana kursów)")
# scheduled speeds by time band and slow stretches (pipeline.speed_report)
PANEL[("city_tram_network", "tram_speed_sched_am_peak")] = (2, "Prędkość tramwajów w szczycie porannym (7–9)")
PANEL[("city_tram_network", "tram_speed_sched_evening")] = (3, "Prędkość tramwajów wieczorem (20–23)")
PANEL[("city_tram_network", "tram_vkm_share_below15_am_peak")] = (4, "Jazda tramwajów poniżej 15 km/h w szczycie")
PANEL[("city_tram_network", "tram_time_above_free_running_s_per_km_am_peak")] = (
    5, "Czas tramwajów ponad jazdę swobodną w szczycie (model)")
# frequent transit (tier "main"): population within 500 m of service at least every N minutes
for _dom in ("core", "covered"):
    for _i, (_n, _s) in enumerate(_FREQ):
        PANEL[(_dom, f"freq_seg_net_le{_n}min")] = (200 + _i, f"Ludność ≤ 500 m od przystanku z kursami co ≤ {_s} min")
    PANEL[(_dom, "rail_ge4dph_net_1km")] = (210, "Ludność ≤ 1 km od stacji kolei lub metra z ≥ 4 odjazdami/h")
# density x service frequency (tier "main"): residents of cells >= 5 000 /km2 without frequent service, rank correlation
for _dom in ("core", "covered"):
    PANEL[(_dom, "dxs_dense_underserved_share")] = (
        220, "Mieszkańcy komórek ≥ 5 000 os./km² bez kursów co ≤ 20 min w zasięgu 500 m")
    PANEL[(_dom, "dxs_rank_correlation")] = (221, "Korelacja rang: gęstość a częstotliwość kursów")
    # ease of transfer (pipeline.transfer_ease): walking between lines by direction, and walk + wait at the
    # 20 busiest stop areas
    PANEL[(_dom, "transfer_dep_share_walkdir_le2min")] = (230, "Odjazdy w węzłach z dojściem między liniami ≤ 2 min")
    # additive trio: walk + wait = total (trip-weighted means over one set of movements, 20 busiest stop areas)
    PANEL[(_dom, "transfer_top20_walkwait_w_am_mean_min")] = (
        231, "Typowa przesiadka w 20 największych węzłach, 7–9: dojście + czekanie")
    PANEL[(_dom, "transfer_top20_walk_w_am_mean_min")] = (232, "w tym dojście między liniami")
    PANEL[(_dom, "transfer_top20_wait_w_am_mean_min")] = (233, "w tym czekanie na drugą linię")
    # share of the 30 / 45 min reach that needs a transfer (ratio of sums), with the reach of direct trips below
    PANEL[(_dom, "transfer_dependence_pt_am_30min_ratio_of_sums")] = (234, "Zasięg 30 min wymagający przesiadki")
    PANEL[(_dom, "tp_pt_am_direct_30min")] = (235, "zasięg w 30 min bez przesiadek")
    PANEL[(_dom, "transfer_dependence_pt_am_45min_ratio_of_sums")] = (236, "Zasięg 45 min wymagający przesiadki")
    PANEL[(_dom, "tp_pt_am_direct_45min")] = (237, "zasięg w 45 min bez przesiadek")
# accessibility (phase 3): transport performance, Wednesday 07-09, all feeds, census-scaled grid.  Headline: the
# ratio of means (as DG REGIO), directly followed by the mean of per-cell ratios as the value for a typical resident.
_TYP = "dla typowego mieszkańca"
_TP = [("tp_pt_am_30min", "Zasięg komunikacją + pieszo, 30 min (7–9)"),
       ("tp_pt_am_45min", "Zasięg komunikacją + pieszo, 45 min (7–9)"),
       ("tp_walk_30min", "Zasięg pieszo, 30 min"),
       ("tp_bike_lts3_30min", "Zasięg rowerem, 30 min (LTS ≤ 3)"),
       ("tp_bike_lts4_30min", "Zasięg rowerem, 30 min (LTS ≤ 4)")]
_TP_DOMAINS = {"tp_pt_am_30min": ("covered", "core"), "tp_pt_am_45min": ("covered", "core")}
for _i, (_m, _lab) in enumerate(_TP):
    for _dom in _TP_DOMAINS.get(_m, ("fua", "core")):
        PANEL[(_dom, f"{_m}_ratio_of_means")] = (300 + 2 * _i, _lab)
        PANEL[(_dom, _m)] = (301 + 2 * _i, f"{_lab}, {_TYP}")
# the same five measures on the urban-centre domain (pipeline.access_uc): origins, destinations and denominator
# restricted to the Eurostat 2021 urban centre(s) in the FUA
_UC = "centrum miejskie (urban centre, Eurostat 2021)"
for _i, (_m, _lab) in enumerate(_TP):
    PANEL[("urban_centre", f"{_m}_ratio_of_means")] = (400 + 2 * _i, f"{_lab}, {_UC}")
    PANEL[("urban_centre", _m)] = (401 + 2 * _i, f"{_lab}, {_UC}, {_TYP}")
# time of day (core; the site shows them in their own block, next to the morning peak)
for _i, (_w, _wl) in enumerate((("midday", "południe"), ("evening", "wieczór"), ("saturday", "sobota"))):
    PANEL[("core", f"tp_pt_{_w}_30min")] = (320 + 2 * _i, f"Zasięg komunikacją + pieszo, 30 min ({_wl})")
    PANEL[("core", f"tp_pt_{_w}_45min")] = (321 + 2 * _i, f"Zasięg komunikacją + pieszo, 45 min ({_wl})")
# distribution (pipeline.distribution): residents below the access floor (half of the seven-city median), with the
# mean shortfall, and the quartiles of the cell values; core and covered, Wednesday 07-09
for _dom in ("core", "covered"):
    PANEL[(_dom, "dist_below_floor_pt_am_30min")] = (340, "Mieszkańcy poniżej minimalnego zasięgu, 30 min")
    PANEL[(_dom, "dist_fgt1_pt_am_30min")] = (341, "średni niedobór do progu (FGT1)")
    PANEL[(_dom, "dist_below_floor_pt_am_45min")] = (342, "Mieszkańcy poniżej minimalnego zasięgu, 45 min")
    PANEL[(_dom, "dist_p25_pt_am_30min")] = (343, "Zasięg 30 min: co czwarty mieszkaniec ma nie więcej niż")
    PANEL[(_dom, "dist_p75_pt_am_30min")] = (344, "Zasięg 30 min: co czwarty mieszkaniec ma co najmniej")
PANEL[("core", "dist_below_floor_pt_evening_30min")] = (345, "Poniżej minimalnego zasięgu 30 min, wieczór")
PANEL[("core", "dist_below_floor_pt_saturday_30min")] = (346, "Poniżej minimalnego zasięgu 30 min, sobota")
# urban form additions (pipeline.form_extra): density classes, Eurostat urban centres, polycentricity
for _dom in ("fua", "core"):
    PANEL[(_dom, "share_residents_ge5000")] = (110, "Mieszkańcy komórek o gęstości ≥ 5 000 os./km²")
    PANEL[(_dom, "median_resident_density_250m")] = (111, "Gęstość wokół typowego mieszkańca (komórka 250 m)")
    PANEL[(_dom, "degurba2021_share_urban_centre")] = (112, "Mieszkańcy centrów miejskich (Eurostat 2021)")
PANEL[("fua", "poly_eta_mask_t20")] = (113, "Rozproszenie skupisk gęstości η")
PANEL[("fua", "hotspots_n")] = (114, "Skupiska gęstości ≥ 10 000 os./km²")
PANEL[("fua", "hotspots_largest_share")] = (115, "Udział największego skupiska gęstości")
# from the centres (cells within 1 km of the centre, the hub and every extra centre): added in centre_panel(),
# because the domains are read from metrics_access and the labels from config.yaml
CENTRE_METRICS = ("tp_pt_am_30min", "tp_pt_am_45min")


def _slug(name: str) -> str:
    """The domain suffix pipeline.access_inputs.centres() gives a centre name."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def centre_panel(rows: list[dict]) -> dict[tuple[str, str], tuple[int, str]]:
    """Panel entries for the centre domains present in the access rows: hub_1km, centre_1km, centre_1km_<name>."""
    names = {}
    for a in load_config()["agglomerations"].values():
        for e in a.get("extra_centres", []):
            names[f"centre_1km_{_slug(e['name'])}"] = e["name"]
    doms = sorted({r["domain"] for r in rows if r["step"] == "access" and r["metric"] in CENTRE_METRICS
                   and re.fullmatch(r"(hub_1km|centre_1km)(_.+)?", r["domain"] or "")})
    out = {}
    for d in doms:
        if d == "centre_1km":
            lab, o = "z centrum (komórki ≤ 1 km)", 500
        elif d == "hub_1km":
            lab, o = "z węzła przesiadkowego (komórki ≤ 1 km)", 502
        else:
            lab, o = f"z centrum: {names.get(d, d[len('centre_1km_'):])} (komórki ≤ 1 km)", 504
        for k, m in enumerate(CENTRE_METRICS):     # one label for both: the site shows 30 and 45 min as columns
            out[(d, m)] = (o + k, lab)
    return out


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
        street_only = r["step"] in ACCESS_STEPS and r["feed_variant"] is None    # walk / bike: no feed variant
        if r["step"] not in ("density", "form") and r["feed_variant"] != PANEL_FEED_VARIANT and not street_only:
            continue
        if r["step"] in ("frequent", "density_service", *ACCESS_STEPS) and r["population_grid"] != PANEL_POP_GRID:
            continue
        # density: the 100 m measures exist on two population grids; only the census-scaled one is shown
        if r["step"] in ("density", "form") and r["population_grid"] not in (None, PANEL_POP_GRID):
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
    PANEL.update(centre_panel(rows))
    panel = panel_subset(rows)
    keys = [(r["agglomeration"], r["domain"], r["metric"]) for r in panel]
    if len(keys) != len(set(keys)):
        raise SystemExit("merge_metrics: the panel subset has more than one row for an (agglomeration, domain, metric)")
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
