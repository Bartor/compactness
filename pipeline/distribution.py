"""Distribution outputs: who gets how much access, not only the city average (ROADMAP item 12, review rows 5-6).

    python -m pipeline.distribution

Reads only (nothing is routed): the per-origin sums of the finished phase-3 units through
pipeline.access_aggregate.load_unit / base_frame (data/interim/access/), the urban-centre caches of
pipeline.access_uc (data/interim/access_uc/, used only when their signatures match), the frequent-service metrics
(results/metrics/metrics_frequent.json) and cell classes (results/layers/frequent_cells.parquet), and the colour
classes of the map layers (results/web/catalog.json).

Definitions (census-scaled 250 m grid, all feeds, Wednesday 2026-11-25; Saturday 2026-11-28 for that window)
* performance of a cell = 100 x population reachable within T / population within the straight-line radius
  (15 km/h for transit and bike, 5 km/h for walking), as in pipeline.access_aggregate.  Transit values of cells
  outside the GTFS coverage mask are missing (not 0) and are left out of every distribution.
* domains: core = city proper (for transit: only cells in the mask; coverage_share gives the share kept),
  covered = cells in the mask (whole FUA), urban_centre = Eurostat 2021 urban centre(s) with origins, destinations
  and denominator restricted to the centre (pipeline.access_uc; 30 and 45 min only).
* "at least" curve: 100 x share of residents whose cell performance is >= x, x = 0, 1, ..., 100 (full file) or
  0, 2, ..., 100 (site file).  Headway curve: share of residents within 500 m walk of service at least every N
  minutes, N = 5, 10, 15, 20, 30, taken from metrics_frequent (freq_seg_net_le<N>min, the main-tier numbers) for
  core and covered; for the urban centre from the cell classes of frequent_cells (majority of sample points).
* reach curve: ratio of means (as DG REGIO) and population-weighted 25th / 50th / 75th percentile of the cell
  values ('lower' rule) for T = 5, 10, ..., 60 min; mean of ratios alongside.
* access floor: half of the seven-city median, where the seven-city median is the median of the seven core
  medians (each city counts once), rounded to a whole point; computed separately for 30 and 45 min, morning peak.
  The same floor is used for every city, domain and time window.  Sensitivity: 40 % and 60 % of the same median.
  Foster-Greer-Thorbecke indices: FGT0 = share of residents below the floor, FGT1 = mean shortfall as a share of
  the floor (0 above the floor), FGT2 = mean squared shortfall; FGT1 and FGT2 are printed x 100.
* Palma ratio (table tier): share of the population-weighted total of cell performance held by the 10 % of
  residents with the highest values divided by the share held by the 40 % with the lowest.  No Gini (review §
  "What to change": a headline Gini depends heavily on the indicator and assignment).

Outputs: results/charts/distribution.json (everything), results/web/charts.json (site subset),
results/metrics/metrics_distribution.{csv,json} (row schema of the other step files), results/qa/distribution/
distribution.md, and _meta_distribution.json in charts/, web/ and metrics/ (_meta.json in qa/distribution/).
"""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import access_inputs as AI
from pipeline import distribution_stats as S
from pipeline.access_aggregate import GRID_LABEL, POP_DATE, base_frame, load_unit, source
from pipeline.common import RESULTS, load_config, sha256_of, sig, write_json, write_meta

CFG = load_config()
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
NAMES = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
         "trojmiasto": "Trójmiasto", "gzm": "GZM"}
CHARTS = RESULTS / "charts"
WEB = RESULTS / "web"
METRICS = RESULTS / "metrics"
QA = RESULTS / "qa" / "distribution"
GRID = "ghsl_census_scaled"
CUTS = list(AI.CUTOFFS)                       # 5..60
HEAD = (30, 45)
X_FULL = list(range(0, 101))
X_WEB = list(range(0, 101, 2))
HEADWAY_N = [int(t) for t in CFG["headway_thresholds_min"]]
WINDOWS = ["pt_am", "pt_midday", "pt_evening", "pt_saturday"]
WIN_LABEL = {"pt_am": "szczyt poranny (środa 7:00–9:00)", "pt_midday": "południe (środa 10:00–14:00)",
             "pt_evening": "wieczór (środa 20:00–22:00)", "pt_saturday": "sobota 10:00–14:00"}
WIN_SHORT = {"pt_am": "7–9", "pt_midday": "południe", "pt_evening": "wieczór", "pt_saturday": "sobota"}
MODES = {"walk": "street", "bike_lts3": "street", "bike_lts4": "street"}
MODE_LABEL = {"pt_am": "komunikacja + pieszo", "walk": "pieszo", "bike_lts3": "rower, LTS ≤ 3",
              "bike_lts4": "rower, LTS ≤ 4"}
DOMAINS = ["core", "covered", "urban_centre"]
DOM_LABEL = {"core": "rdzeń", "covered": "obszar pokryty", "urban_centre": "centrum miejskie (urban centre)"}
FLOOR_FRACTIONS = (0.4, 0.5, 0.6)
FLOOR_MAIN = 0.5
SERIES_30 = ["pt_am_30", "pt_am_45", "walk_30", "bike_lts3_30", "bike_lts4_30"]
LAYER_MARKS = {"transport_performance_30": "pt_am_30", "frequent_transport": "headway"}
FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]
SRC_NOTE = "rozkład wartości komórek: pipeline.distribution"


def day_of(scen: str) -> str | None:
    if not scen.startswith("pt_"):
        return None
    return CFG["reference_saturday"] if scen == "pt_saturday" else CFG["reference_day"]


# ------------------------------------------------------------------ loading
def speed_of(scen: str) -> str:
    return "walk" if scen == "walk" else "fast"


def city_cells(agg: str) -> dict | None:
    """Per-cell performance arrays (NaN = missing) for every scenario and cutoff, weights and domain masks."""
    b = base_frame(agg)
    w = b["w_census"].to_numpy(np.float64)
    mask = b["in_mask_all"].to_numpy(bool)
    core = b["in_core"].to_numpy(bool)
    perf, rom_parts, pending = {}, {}, []
    for scen, net in [(s, "all") for s in WINDOWS] + list(MODES.items()):
        u = load_unit(agg, net, scen)
        if u is None:
            pending.append(f"{net}/{scen}")
            continue
        assert (u["cell_id"].to_numpy() == b["cell_id"].to_numpy()).all()
        for c in CUTS:
            acc = u[f"acc_census_{c}"].to_numpy(np.float64)
            prox = b[f"prox_census_{speed_of(scen)}_{c}"].to_numpy(np.float64)
            with np.errstate(divide="ignore", invalid="ignore"):
                p = np.where(prox > 0, 100.0 * acc / prox, np.nan)
            if scen.startswith("pt_"):
                perf[f"{scen}_{c}_unmasked"] = p
                p = np.where(mask, p, np.nan)
                acc = np.where(mask, acc, np.nan)
            perf[f"{scen}_{c}"] = p
            rom_parts[f"{scen}_{c}"] = (acc, prox)
    if not perf:
        return None
    return {"cell_id": b["cell_id"].to_numpy(), "w": w, "perf": perf, "rom": rom_parts, "pending": pending,
            "dom": {"core": core, "covered": mask}, "mask": mask, "core": core}


def _uc_cache(agg: str, name: str, sig_text: str) -> pd.DataFrame | None:
    from pipeline import access_uc as U
    p = U.OUT / agg / f"{name}.parquet"
    s = p.with_suffix(".sig")
    if p.exists() and s.exists() and s.read_text() == sig_text:
        return pd.read_parquet(p)
    return None


def uc_cells(agg: str) -> dict | None:
    """Urban-centre domain from the pipeline.access_uc caches (read only; None when a cache is stale or missing)."""
    from pipeline import access_uc as U
    u = U.uc_cells(agg)
    h = U.uc_hash(agg)
    prox = _uc_cache(agg, "proximity", h + "|prox1")
    man = AI.ACCESS_INT / agg / "street" / "walk" / "manifest.json"
    walk = _uc_cache(agg, "walk", h + "|" + json.loads(man.read_text(encoding="utf-8"))["signature"]) if man.exists() else None
    if prox is None:
        return None
    w = u["w_census"].to_numpy(np.float64)
    m = AI.mask(agg).set_index("cell_id").reindex(u["cell_id"])
    in_mask = m["in_mask_all"].fillna(False).astype(bool).to_numpy()
    perf, rom_parts, pending = {}, {}, []
    units = {s: pd.read_parquet(U.unit_path(agg, s)) if U.unit_done(agg, s) else None for s in ("pt_am", "bike_lts3", "bike_lts4")}
    units["walk"] = walk
    for scen, df in units.items():
        if df is None:
            pending.append(f"urban_centre/{scen}")
            continue
        assert (df["cell_id"].to_numpy() == u["cell_id"].to_numpy()).all()
        for c in (HEAD if scen == "pt_am" else (30,)):
            acc = df[f"acc_census_{c}"].to_numpy(np.float64)
            pr = prox[f"prox_census_{'walk' if scen == 'walk' else 'fast'}{c}"].to_numpy(np.float64)
            with np.errstate(divide="ignore", invalid="ignore"):
                p = np.where(pr > 0, 100.0 * acc / pr, np.nan)
            if scen == "pt_am":
                rom_parts[f"{scen}_{c}_unmasked"] = (acc, pr)     # the published urban-centre definition (check)
                p = np.where(in_mask, p, np.nan)
                acc = np.where(in_mask, acc, np.nan)
            perf[f"{scen}_{c}"] = p
            rom_parts[f"{scen}_{c}"] = (acc, pr)
    return {"cell_id": u["cell_id"].to_numpy(), "w": w, "perf": perf, "rom": rom_parts, "pending": pending,
            "mask": in_mask}


def frequent_curves() -> dict:
    """(agg, domain) -> [share <= N for N in HEADWAY_N] from metrics_frequent (main-tier rows)."""
    m = json.loads((METRICS / "metrics_frequent.json").read_text(encoding="utf-8"))["metrics"]
    idx = {(r["agglomeration"], r["domain"], r["metric"]): r for r in m
           if r.get("feed_variant") == "all" and r.get("population_grid") == GRID}
    out = {}
    for agg in AGGS:
        for dom in ("core", "covered"):
            vals = [idx.get((agg, dom, f"freq_seg_net_le{n}min"), {}).get("value") for n in HEADWAY_N]
            out[(agg, dom)] = vals
    return out


def headway_classes() -> pd.DataFrame:
    f = pd.read_parquet(RESULTS / "layers" / "frequent_cells.parquet",
                        columns=["agglomeration", "cell_id", "headway_class_all", "in_mask_all"])
    num = {str(n): float(n) for n in HEADWAY_N}
    num[">30"] = 999.0
    f["hw"] = f["headway_class_all"].map(num).astype(float)
    f.loc[~f["in_mask_all"].fillna(False).astype(bool), "hw"] = np.nan
    return f


def layer_marks() -> dict:
    cat = json.loads((WEB / "catalog.json").read_text(encoding="utf-8"))
    out = {}
    for lay in cat["layers"]:
        if lay["id"] in LAYER_MARKS and lay.get("ramp", {}).get("stops"):
            stops = lay["ramp"]["stops"]
            if lay["id"] == "frequent_transport":
                stops = HEADWAY_N            # class limits as labelled (co <= 5, 10, 15, 20, 30 min)
            out[lay["id"]] = {"series": LAYER_MARKS[lay["id"]], "stops": stops, "title": lay["title"],
                              "unit": lay.get("unit")}
    return out


# ------------------------------------------------------------------ statistics per domain
def r4(x):
    return None if x is None else sig(x)


def r4l(xs):
    return None if xs is None else [r4(x) for x in xs]


def summary(v, w, acc_prox=None) -> dict:
    d = {"p25": r4(S.wquantile(v, w, 0.25)), "p50": r4(S.wquantile(v, w, 0.5)), "p75": r4(S.wquantile(v, w, 0.75)),
         "mean_of_ratios": r4(S.wmean(v, w))}
    if acc_prox is not None:
        acc, prox = acc_prox
        d["ratio_of_means"] = r4(S.ratio_of_means(acc, prox, np.where(np.isfinite(v), w, 0.0)))
    return d


def floor_block(v, w, floors: dict, frac_main: float) -> dict:
    out = {"floors": []}
    for frac, z in sorted(floors.items()):
        e = {"fraction_of_median": frac, "floor": z, "fgt0": r4(_pct(S.fgt(v, w, z, 0))),
             "fgt1": r4(_pct(S.fgt(v, w, z, 1))), "fgt2": r4(_pct(S.fgt(v, w, z, 2)))}
        out["floors"].append(e)
        if frac == frac_main:
            out.update({"floor": z, "below_floor": e["fgt0"], "fgt1": e["fgt1"], "fgt2": e["fgt2"]})
    return out


def _pct(x):
    return None if x is None else 100.0 * x


def domain_stats(cells: dict, sel: np.ndarray, floors: dict, uc: bool) -> dict:
    w = np.where(sel, cells["w"], 0.0)
    perf = cells["perf"]
    out = {"population": r4(float(cells["w"][sel].sum())), "at_least": {}, "reach": {}, "time_of_day": {},
           "floor": {}, "palma": {}}
    # coverage: share of the domain's residents kept by the transit mask
    tot = float(cells["w"][sel].sum())
    out["coverage_share"] = r4(float(cells["w"][sel & cells["mask"]].sum()) / tot) if tot > 0 else None
    for key in sorted(perf):
        if key.endswith("_unmasked"):
            continue
        scen, c = key.rsplit("_", 1)
        c = int(c)
        if c in HEAD and (c == 30 or scen.startswith("pt_")):
            out["at_least"][key] = r4l(S.share_at_least(perf[key], w, X_FULL))
    if not uc:
        for scen in WINDOWS[:1] + list(MODES):
            if f"{scen}_30" not in perf:
                continue
            rows = {"ratio_of_means": [], "mean_of_ratios": [], "p25": [], "p50": [], "p75": []}
            for c in CUTS:
                s = summary(perf[f"{scen}_{c}"], w, cells["rom"][f"{scen}_{c}"])
                for k in rows:
                    rows[k].append(s[k])
            out["reach"][scen] = rows
    for scen in WINDOWS:
        for c in HEAD:
            key = f"{scen}_{c}"
            if key not in perf:
                continue
            s = summary(perf[key], w, cells["rom"][key])
            s.update(floor_block(perf[key], w, floors[c], FLOOR_MAIN))
            out["time_of_day"][key] = s
            if scen == "pt_am":
                out["floor"][str(c)] = {k: s[k] for k in ("floor", "below_floor", "fgt1", "fgt2", "floors")}
                out["palma"][str(c)] = r4(S.palma(perf[key], w))
    for scen in MODES:
        key = f"{scen}_30"
        if key in perf:
            out["time_of_day"].setdefault("modes", {})[key] = summary(perf[key], w, cells["rom"][key])
    return out


# ------------------------------------------------------------------ main
def compute() -> dict:
    t0 = time.time()
    cells, ucs = {}, {}
    for agg in AGGS:
        cells[agg] = city_cells(agg)
        try:
            ucs[agg] = uc_cells(agg)
        except Exception as e:          # the urban-centre variant is optional ("where cheap")
            print(f"{agg}: urban centre skipped ({e})", flush=True)
            ucs[agg] = None
        print(f"{agg}: loaded ({time.time() - t0:.0f} s)", flush=True)
    # floors: half of the median of the seven core medians, morning peak
    med = {}
    for c in HEAD:
        med[c] = {a: S.wquantile(cells[a]["perf"][f"pt_am_{c}"], np.where(cells[a]["core"], cells[a]["w"], 0.0), 0.5)
                  for a in AGGS if cells[a] and f"pt_am_{c}" in cells[a]["perf"]}
    ref = {c: float(np.median(list(med[c].values()))) for c in HEAD}
    floors = {c: {f: float(round(f * ref[c])) for f in FLOOR_FRACTIONS} for c in HEAD}
    hw_metrics = frequent_curves()
    hw = headway_classes()
    out_c = {}
    checks = []
    access_rows = {(r["agglomeration"], r["domain"], r["metric"]): r["value"]
                   for f in ("metrics_access.json", "metrics_access_uc.json")
                   for r in json.loads((METRICS / f).read_text(encoding="utf-8"))["metrics"]
                   if r.get("population_grid") == GRID and r.get("feed_variant") in ("all", None)}
    for agg in AGGS:
        cc = cells[agg]
        doms = {}
        if cc is not None:
            for dom in ("core", "covered"):
                d = domain_stats(cc, cc["dom"][dom], floors, uc=False)
                d["headway_at_most"] = hw_metrics.get((agg, dom))
                d["headway_source"] = "metrics_frequent: freq_seg_net_le<N>min (udział punktów próbkowania komórki)"
                doms[dom] = d
            # checks against metrics_access (unmasked core = the published definition; covered = masked)
            for dom, sel in (("core", cc["core"]), ("covered", cc["mask"])):
                for c in HEAD:
                    k = f"pt_am_{c}_unmasked" if dom == "core" else f"pt_am_{c}"
                    mine = S.wmean(cc["perf"][k], np.where(sel, cc["w"], 0.0))
                    pub = access_rows.get((agg, dom, f"tp_pt_am_{c}min"))
                    checks.append({"agglomeration": agg, "domain": dom, "metric": f"tp_pt_am_{c}min", "published": pub,
                                   "recomputed": r4(mine), "masked": r4(doms[dom]["time_of_day"][f"pt_am_{c}"]["mean_of_ratios"]),
                                   "ok": pub is not None and mine is not None and abs(pub - mine) <= 0.01 + 1e-3 * abs(pub)})
            # headway from the cell classes for the core, as a check of the class layer against the metric
            h = hw[hw["agglomeration"] == agg].set_index("cell_id").reindex(cc["cell_id"])
            hv = h["hw"].to_numpy(np.float64)
            doms["core"]["headway_at_most_classes"] = r4l(S.share_at_most(hv, np.where(cc["core"], cc["w"], 0.0), HEADWAY_N))
        uc = ucs.get(agg)
        if uc is not None:
            d = domain_stats(uc, np.ones(len(uc["w"]), bool), floors, uc=True)
            h = hw[hw["agglomeration"] == agg].set_index("cell_id").reindex(uc["cell_id"])
            d["headway_at_most"] = r4l(S.share_at_most(h["hw"].to_numpy(np.float64), uc["w"], HEADWAY_N))
            d["headway_source"] = "klasy komórek frequent_cells (klasa większości punktów próbkowania)"
            for c in HEAD:
                pub = access_rows.get((agg, "urban_centre", f"tp_pt_am_{c}min_ratio_of_means"))
                if f"pt_am_{c}_unmasked" not in uc["rom"]:
                    continue
                acc, pr = uc["rom"][f"pt_am_{c}_unmasked"]
                mine = S.ratio_of_means(acc, pr, uc["w"])
                checks.append({"agglomeration": agg, "domain": "urban_centre", "metric": f"tp_pt_am_{c}min_ratio_of_means",
                               "published": pub, "recomputed": r4(mine),
                               "masked": d["time_of_day"].get(f"pt_am_{c}", {}).get("ratio_of_means"),
                               "ok": None if pub is None else (mine is not None and abs(pub - mine) <= 0.01 + 1e-3 * abs(pub))})
            doms["urban_centre"] = d
        out_c[agg] = {"name": NAMES[agg], "polycentric": bool(CFG["agglomerations"][agg].get("polycentric", False)),
                      "domains": doms,
                      "pending": (cc["pending"] if cc else ["all units"]) + (uc["pending"] if uc else ["urban_centre"])}
    return {"cells": out_c, "medians": med, "ref": ref, "floors": floors, "checks": checks, "t0": t0}


def seven(out_c: dict, dom: str, path) -> dict:
    """Seven-city median and min / max of one value given by path(domain dict)."""
    vals = {a: path(out_c[a]["domains"][dom]) for a in AGGS if dom in out_c[a]["domains"]}
    vals = {a: v for a, v in vals.items() if v is not None}
    if not vals:
        return {}
    return {"median": r4(float(np.median(list(vals.values())))), "values": vals}


def build_full(res: dict) -> dict:
    out_c = res["cells"]
    return {
        "title": "Rozkład dostępu: odsetek mieszkańców z co najmniej X, krzywa zasięgu 5–60 min, minimalny zasięg (FGT)",
        "definition": __doc__.split("Definitions", 1)[1].split("Outputs:", 1)[0].strip(),
        "timetable_date": CFG["reference_day"], "timetable_date_saturday": CFG["reference_saturday"],
        "osm_date": "2026-11-22", "population_grid": GRID, "population_date": POP_DATE[GRID], "feed_variant": "all",
        "source": source("all", GRID) + "; " + SRC_NOTE,
        "x_performance": X_FULL, "cutoffs_min": CUTS, "headway_n_min": HEADWAY_N,
        "domains": {d: DOM_LABEL[d] for d in DOMAINS},
        "windows": {w: WIN_LABEL[w] for w in WINDOWS},
        "floor": {
            "rule": "połowa mediany siedmiu miast: mediana z siedmiu median rdzeni (mediana komórek ważona ludnością, "
                    "szczyt poranny, komórki w masce pokrycia GTFS), zaokrąglona do pełnego punktu",
            "reference_median": {str(c): r4(res["ref"][c]) for c in HEAD},
            "core_medians": {str(c): {a: r4(v) for a, v in sorted(res["medians"][c].items())} for c in HEAD},
            "floors": {str(c): {str(f): z for f, z in sorted(res["floors"][c].items())} for c in HEAD},
            "main_fraction": FLOOR_MAIN,
            "why": "analogia do względnych granic ubóstwa (40/50/60 % mediany dochodu w OECD i Eurostacie); próg wspólny "
                   "dla siedmiu miast, więc udział poniżej progu można porównywać; wrażliwość: 40 % i 60 % mediany",
        },
        "layer_marks": layer_marks(),
        "checks": res["checks"],
        "cities": out_c,
    }


def thin(xs, step=2):
    return None if xs is None else xs[::step]


def build_web(full: dict) -> dict:
    """Compact subset for the site: at-least curves every 2 points, reach curve, time of day, floors, headway."""
    cities = {}
    for agg, c in full["cities"].items():
        doms = {}
        for dom, d in c["domains"].items():
            e = {"population": d["population"], "coverage_share": d["coverage_share"],
                 "at_least": {k: thin(v) for k, v in d["at_least"].items() if k in SERIES_30},
                 "headway_at_most": d.get("headway_at_most"),
                 "floor": {k: {kk: vv for kk, vv in v.items()} for k, v in d["floor"].items()},
                 "palma": d["palma"],
                 "time_of_day": {k: {kk: v[kk] for kk in ("ratio_of_means", "mean_of_ratios", "p25", "p50", "p75", "below_floor")}
                                 for k, v in d["time_of_day"].items() if k != "modes"},
                 "modes": d["time_of_day"].get("modes", {})}
            if d["reach"]:
                e["reach"] = d["reach"]
            doms[dom] = e
        cities[agg] = {"name": c["name"], "polycentric": c["polycentric"], "domains": doms}
    return {
        "version": 1,
        "title": full["title"],
        "timetable_date": full["timetable_date"], "timetable_date_saturday": full["timetable_date_saturday"],
        "population_date": full["population_date"], "source": full["source"],
        "x_performance": X_WEB, "cutoffs_min": CUTS, "headway_n_min": HEADWAY_N,
        "domains": full["domains"], "windows": {w: WIN_SHORT[w] for w in WINDOWS},
        "series": {"pt_am_30": "komunikacja + pieszo, 30 min (7–9)", "pt_am_45": "komunikacja + pieszo, 45 min (7–9)",
                   "walk_30": "pieszo, 30 min", "bike_lts3_30": "rower, 30 min (LTS ≤ 3)",
                   "bike_lts4_30": "rower, 30 min (LTS ≤ 4)"},
        "floor": {k: full["floor"][k] for k in ("reference_median", "floors", "main_fraction")},
        "layer_marks": full["layer_marks"],
        "notes": [
            "Brak danych to null, nie zero. Komórki poza pokryciem rozkładów nie wchodzą do rozkładów komunikacji.",
            "Centrum miejskie: starty, cele i mianownik tylko w centrum miejskim, więc wartości nie porównuje się wprost z rdzeniem.",
            "Czas rozkładowy, bez opóźnień; ludność z siatki spisowej 2021 rozłożonej wzorem GHSL 2020.",
        ],
        "cities": cities,
    }


# ------------------------------------------------------------------ metric rows
def metric_rows(full: dict) -> list[dict]:
    rows = []
    fl = full["floor"]["floors"]
    for agg, c in full["cities"].items():
        for dom, d in c["domains"].items():
            cov = d.get("coverage_share")
            base_flag = {"core": "tylko komórki rdzenia w masce pokrycia GTFS (§6); coverage_share = udział ludności rdzenia w masce",
                         "covered": "tylko komórki w masce pokrycia GTFS (§6); coverage_share = 1",
                         "urban_centre": "starty, cele i mianownik tylko w centrum miejskim (pipeline.access_uc)"}[dom]

            def add(metric, label, value, unit, tier, scen="pt_am", flag=""):
                rows.append({"agglomeration": agg, "domain": dom, "metric": metric, "label": label,
                             "value": r4(value), "unit": unit, "grid": GRID_LABEL[GRID],
                             "source": source("all", GRID) + "; " + SRC_NOTE, "population_date": POP_DATE[GRID],
                             "timetable_date": day_of(scen), "coverage_share": r4(cov), "flag": "; ".join(x for x in [base_flag, flag] if x) or None,
                             "tier": tier, "feed_variant": "all", "population_grid": GRID})

            for scen in WINDOWS:
                for cut in HEAD:
                    s = d["time_of_day"].get(f"{scen}_{cut}")
                    if s is None:
                        continue
                    sfx = "" if scen == "pt_am" else f"_{scen[3:]}"
                    z = fl[str(cut)][str(FLOOR_MAIN)]
                    wl = WIN_LABEL[scen]
                    lab0 = (f"Odsetek mieszkańców poniżej minimalnego zasięgu: transport performance komunikacją + pieszo "
                            f"w {cut} min ({wl}) mniejszy niż {z:g} % (połowa mediany siedmiu miast)")
                    tier = "main" if (scen == "pt_am" and cut == 30 and dom in ("core", "covered")) else "table"
                    add(f"dist_below_floor_pt{sfx or '_am'}_{cut}min", lab0, s["below_floor"], "%", tier, scen)
                    if scen != "pt_am":
                        continue
                    add(f"dist_floor_pt_am_{cut}min", f"Próg minimalnego zasięgu {cut} min: połowa mediany siedmiu rdzeni "
                        f"({full['floor']['reference_median'][str(cut)]:g} %), zaokrąglona", z, "%", "table")
                    add(f"dist_fgt1_pt_am_{cut}min", f"Średni niedobór względem progu {z:g} % (FGT1 × 100): przeciętny brak do "
                        f"progu jako % progu, liczony na wszystkich mieszkańców ({cut} min, 7–9)", s["fgt1"], "% progu", "table")
                    add(f"dist_fgt2_pt_am_{cut}min", f"Kwadrat niedoboru względem progu {z:g} % (FGT2 × 100): jak FGT1, ale "
                        f"duże niedobory ważą więcej ({cut} min, 7–9)", s["fgt2"], "indeks × 100", "table")
                    for e in s["floors"]:
                        if e["fraction_of_median"] == FLOOR_MAIN:
                            continue
                        pc = int(round(100 * e["fraction_of_median"]))
                        add(f"dist_below_floor{pc}_pt_am_{cut}min",
                            f"Jak dist_below_floor_pt_am_{cut}min, ale próg {e['floor']:g} % ({pc} % mediany siedmiu miast; wrażliwość)",
                            e["fgt0"], "%", "table")
                    for q in ("p25", "p50", "p75"):
                        add(f"dist_{q}_pt_am_{cut}min",
                            f"{q[1:]}. percentyl transport performance komórek ważony ludnością ({cut} min, 7–9): "
                            f"{q[1:]} % mieszkańców ma wynik nie wyższy", s[q], "%", "table")
                    add(f"dist_palma_pt_am_{cut}min",
                        f"Wskaźnik Palmy ({cut} min, 7–9): udział 10 % mieszkańców o najlepszym zasięgu w sumie wyników / "
                        "udział 40 % o najsłabszym", d["palma"].get(str(cut)), "iloraz", "table",
                        flag="miara pomocnicza; bez współczynnika Giniego jako wyniku głównego")
    rows.sort(key=lambda m: (m["agglomeration"], m["feed_variant"] or "", m["population_grid"] or "", m["domain"], m["metric"]))
    return rows


def write_metrics(rows: list[dict]) -> None:
    METRICS.mkdir(parents=True, exist_ok=True)
    write_json(METRICS / "metrics_distribution.json", {"generated_for_timetable_date": CFG["reference_day"], "metrics": rows})
    with open(METRICS / "metrics_distribution.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


def write_metas(t0: float, sizes: dict) -> None:
    srcs = ["results/layers/frequent_cells.parquet", "results/metrics/metrics_frequent.json",
            "results/metrics/metrics_access.json", "results/metrics/metrics_access_uc.json", "results/web/catalog.json"]
    extra = {"outputs": sizes, "sources_sha256": {s: sha256_of(RESULTS.parent / s) for s in srcs},
             "routed_units": "data/interim/access/<agg>/{all/pt_am,pt_midday,pt_evening,pt_saturday; street/walk,bike_lts3,bike_lts4} "
                             "(read through pipeline.access_aggregate.load_unit); data/interim/access_uc/<agg>/ (read only)",
             "population_grid": GRID, "timetable_date": CFG["reference_day"], "timetable_date_saturday": CFG["reference_saturday"]}
    with tempfile.TemporaryDirectory() as tmp:
        write_meta(Path(tmp), "distribution", started=t0, extra=extra)
        for folder in (CHARTS, WEB, METRICS):
            shutil.copyfile(Path(tmp) / "_meta.json", folder / "_meta_distribution.json")
        QA.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(tmp) / "_meta.json", QA / "_meta.json")


def main() -> None:
    res = compute()
    full = build_full(res)
    write_json(CHARTS / "distribution.json", full)
    web = build_web(full)
    write_json(WEB / "charts.json", web)
    rows = metric_rows(full)
    write_metrics(rows)
    sizes = {p: round((RESULTS / p).stat().st_size / 1e3, 1) for p in
             ("charts/distribution.json", "web/charts.json", "metrics/metrics_distribution.csv", "metrics/metrics_distribution.json")}
    from pipeline.distribution_qa import write_qa
    write_qa(full, rows, sizes)
    sizes["qa/distribution/distribution.md"] = round((QA / "distribution.md").stat().st_size / 1e3, 1)
    write_metas(res["t0"], sizes)
    bad = [c for c in res["checks"] if c["ok"] is False]
    print(f"distribution: {len(rows)} metric rows, sizes kB {sizes}, failed checks {len(bad)}, {time.time() - res['t0']:.0f} s")
    for c in bad:
        print("  check failed:", c)


if __name__ == "__main__":
    main()
