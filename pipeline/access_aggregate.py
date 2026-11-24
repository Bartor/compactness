"""Aggregate the per-origin accessibility sums of pipeline.access into results (brief §4.6).

    python -m pipeline.access aggregate

Works on whatever units are finished; a unfinished unit is listed as "pending" (metrics JSON ``status``, chart
and layer ``_meta``) and produces no rows, never null or 0 results.

Definitions
* performance of origin cell i = 100 x accessibility_i / proximity_i, where accessibility = population (or jobs)
  of destination cells reachable within the cutoff and proximity = population (or jobs) of destination cells whose
  centre lies within the straight-line radius speed x cutoff of the origin centre (15 km/h for public transport
  and bicycle: 7.5 km at 30 min, 11.25 km at 45 min; 5 km/h for walking: 2.5 km at 30 min).  Destinations and the
  proximity domain are the same set (populated cells in FUA + 15 km).
* headline (brief): mean of the cell ratios weighted by the origin cell's population ("mean of ratios"); also the
  ratio of the population-weighted means of accessibility and proximity ("ratio of means", tier table).
* domains: fua (all origin cells), core (city proper), covered (transit only: cells in the phase-2 GTFS coverage
  mask of the same feed variant), centre_1km / hub_1km / centre_1km_<name> (cells within 1 km of the configured
  centre, hub and, in polycentric agglomerations, every extra centre).
* coverage honesty (brief §6): transit values of cells outside the mask are null in the cell layer; FUA and core
  aggregates include every cell (as phase 2 does) and carry coverage_share and the "niepełne pokrycie GTFS" flag
  below 0.85.  Walk and bike are not masked.
* jobs ("miejsca pracy w granicach miasta"): the opportunity set is the city proper (Goliszek 2026; Gdańsk only
  in Trójmiasto; GZM not covered -> null).  Origins anywhere in the FUA.  Jobs performance is the ratio of means
  (sum of population-weighted reachable jobs / sum of population-weighted jobs within the radius): near the edge
  of the data the proximity is a handful of jobs and cell ratios exceed 1000, so the mean of ratios is unusable
  (kept as a qa row for origins in the city proper).
* transfer dependence (2026-11-24): scenario pt_am_direct is pt_am with at most one ride (no transfers).  Per cell,
  100 x (1 - accessibility(direct) / accessibility(pt_am)) = the share of the population reachable within the cutoff
  that cannot be reached without changing lines; null where the pt_am accessibility is 0 or missing.  Per domain:
  population-weighted mean of the cell shares, and 100 x (1 - sum w*acc(direct) / sum w*acc(pt_am)) ("ratio of sums").
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import access_inputs as AI
from pipeline.access import AGGS_BY_SIZE, CFG, SCENARIOS, UNITS, chunk_path, n_chunks, unit_dir, unit_state
from pipeline.common import RESULTS, sig, write_json

METRICS = RESULTS / "metrics"
CHARTS = RESULTS / "charts"
LAYERS = RESULTS / "layers"
QA = RESULTS / "qa" / "access"
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
GRIDS = {"ghsl_census_scaled": "census", "ghsl_raw": "raw"}
GRID_LABEL = {"ghsl_census_scaled": "GHSL 250 m przeskalowany do NSP 2021 (EPSG:2180)",
              "ghsl_raw": "GHSL 250 m (EPSG:2180)"}
POP_DATE = {"ghsl_census_scaled": "2021-03-31 (NSP 2021, wzór GHSL 2020)", "ghsl_raw": "2020 (GHSL, model)"}
COV_MIN = float(CFG["coverage_min_share"])
REC = {"network": "all", "grid": "ghsl_census_scaled", "scenario": "pt_am"}
WIN_LABEL = {"pt_am": "środa 7:00–9:00", "pt_midday": "środa 10:00–14:00", "pt_evening": "środa 20:00–22:00",
             "pt_saturday": "sobota 10:00–14:00", "pt_am_max3rides": "środa 7:00–9:00, maks. 2 przesiadki",
             "pt_am_direct": "środa 7:00–9:00, bez przesiadek (jeden przejazd)"}
DOM_LABEL = {"fua": "FUA", "core": "rdzeń", "covered": "obszar pokryty danymi"}
SPEED = {"transit": "fast", "bike": "fast", "walk": "walk"}
FLAG_SIZE = "liczba bezwzględna: mierzy głównie wielkość miasta, nie jakość transportu (brief §11)"
FLAG_DEST = ("braki przewoźników w feedach po stronie celów zaniżają wynik także wewnątrz maski")
OSM_DATE = "2026-11-22"


# ------------------------------------------------------------------ loading
def load_unit(agg: str, net: str, scen: str) -> pd.DataFrame | None:
    done, tot = unit_state(agg, net, scen)
    if done < tot:
        return None
    d = unit_dir(agg, net, scen)
    return pd.concat([pd.read_parquet(chunk_path(d, k, scen)) for k in range(tot)], ignore_index=True)


def base_frame(agg: str) -> pd.DataFrame:
    o = AI.origins(agg)[["cell_id", "x", "y", "w_census", "w_raw", "in_core"]].copy()
    p = AI.proximity(agg)
    assert (p["cell_id"].to_numpy() == o["cell_id"].to_numpy()).all()
    o = pd.concat([o, p.drop(columns="cell_id")], axis=1)
    m = AI.mask(agg).set_index("cell_id").reindex(o["cell_id"])
    for v in ("official", "all"):
        o[f"in_mask_{v}"] = m[f"in_mask_{v}"].fillna(False).astype(bool).to_numpy()
    for c in AI.centres(agg):
        o[c["domain"]] = np.hypot(o["x"] - c["x"], o["y"] - c["y"]).to_numpy() <= 1000.0
    return o


def unit_status(aggs) -> list[dict]:
    rows = []
    for agg in aggs:
        for pr, net, scens in UNITS:
            for s in scens:
                done, tot = unit_state(agg, net, s)
                rows.append({"agglomeration": agg, "priority": pr, "network": net, "scenario": s,
                             "chunks_done": done, "chunks_total": tot,
                             "state": "done" if done == tot else ("partial" if done else "pending")})
    return rows


# ------------------------------------------------------------------ per-cell performance
def perf_cells(b: pd.DataFrame, u: pd.DataFrame, kind: str, w: str, c: int, col: str | None = None) -> tuple:
    """(performance per cell, accessibility, proximity) for weight w at cutoff c."""
    acc = u[col or f"acc_{w}_{c}"].to_numpy(np.float64)
    prox = b[f"prox_{w}_{SPEED[kind]}_{c}"].to_numpy(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        perf = np.where(prox > 0, 100.0 * acc / prox, np.nan)
    return perf, acc, prox


def wmean(v: np.ndarray, w: np.ndarray, sel: np.ndarray) -> float | None:
    m = sel & np.isfinite(v) & (w > 0)
    if w[m].sum() <= 0:
        return None
    return float((v[m] * w[m]).sum() / w[m].sum())


def ratio_of_means(acc, prox, w, sel) -> float | None:
    m = sel & (w > 0) & np.isfinite(acc)
    den = (prox[m] * w[m]).sum()
    return None if den <= 0 else float(100.0 * (acc[m] * w[m]).sum() / den)


def dependence_cells(ud: pd.DataFrame, um: pd.DataFrame, wk: str, c: int) -> tuple:
    """(share in %, acc direct, acc main) per cell: 100 x (1 - acc_direct / acc_main); NaN where acc_main is 0 / NaN."""
    ad = ud[f"acc_{wk}_{c}"].to_numpy(np.float64)
    am = um[f"acc_{wk}_{c}"].to_numpy(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        dep = np.where(am > 0, 100.0 * (1.0 - ad / am), np.nan)
    return dep, ad, am


def dependence_ratio_of_sums(ad, am, w, sel) -> float | None:
    """100 x (1 - sum w*acc_direct / sum w*acc_main) over the selected cells with both values."""
    m = sel & (w > 0) & np.isfinite(ad) & np.isfinite(am)
    den = (am[m] * w[m]).sum()
    return None if den <= 0 else float(100.0 * (1.0 - (ad[m] * w[m]).sum() / den))


# ------------------------------------------------------------------ metrics
class Rows:
    def __init__(self, agg: str):
        self.agg, self.rows = agg, []

    def add(self, dom, metric, label, value, unit, grid, feed, tier, flag="", cov=None, day=None, src=None):
        self.rows.append({
            "agglomeration": self.agg, "domain": dom, "metric": metric, "label": label,
            "value": sig(value) if value is not None else None, "unit": unit,
            "grid": GRID_LABEL[grid] if grid else None, "source": src or source(feed, grid),
            "population_date": POP_DATE[grid] if grid else None, "timetable_date": day,
            "coverage_share": sig(cov) if cov is not None else None, "flag": flag or None, "tier": tier,
            "feed_variant": feed, "population_grid": grid})


def source(feed, grid) -> str:
    pop = "NSP 2021 + GHSL 2020" if grid == "ghsl_census_scaled" else "GHSL 2020"
    if feed is None:
        return f"R5 v7.5.1 (r5py 1.1.7), OSM {OSM_DATE}; ludność: {pop}"
    return (f"R5 v7.5.1 (r5py 1.1.7); GTFS ({'wszystkie feedy' if feed == 'all' else 'feedy oficjalne'}, warstwa kursów "
            f"pipeline.gtfs_service); OSM {OSM_DATE}; ludność: {pop}")


def domains(b: pd.DataFrame, agg: str, kind: str, mv: str | None) -> list[tuple[str, np.ndarray]]:
    out = [("fua", np.ones(len(b), bool)), ("core", b["in_core"].to_numpy())]
    if kind == "transit":
        out.append(("covered", b[f"in_mask_{mv}"].to_numpy()))
    for c in AI.centres(agg):
        out.append((c["domain"], b[c["domain"]].to_numpy()))
    return out


def cov_share(b, sel, w, mv) -> float | None:
    den = w[sel].sum()
    return None if den <= 0 else float(w[sel & b[f"in_mask_{mv}"].to_numpy()].sum() / den)


def centre_label(agg: str, dom: str) -> str:
    for c in AI.centres(agg):
        if c["domain"] == dom:
            return {"centre": "centrum", "hub": "węzeł"}.get(c["kind"], "centrum") + f" {c['name']}"
    return dom


def scen_label(scen: str) -> tuple[str, str]:
    s = SCENARIOS[scen]
    if s["kind"] == "transit":
        return "komunikacją zbiorową + pieszo", WIN_LABEL[scen]
    if s["kind"] == "walk":
        return "pieszo (5 km/h)", ""
    return f"rowerem (15 km/h, poziom stresu LTS ≤ {s['lts']})", ""


def metric_rows(agg: str, b: pd.DataFrame, units: dict, samples: dict) -> list[dict]:
    R = Rows(agg)
    poly = bool(CFG["agglomerations"][agg].get("polycentric"))
    has_jobs = agg in AI.JOBS_AGGS
    for (net, scen), u in sorted(units.items()):
        kind = SCENARIOS[scen]["kind"]
        if kind not in ("transit", "walk", "bike"):
            continue
        feed = net if kind == "transit" else None
        mv = AI.mask_variant(net) if kind == "transit" else None
        mode_lab, win = scen_label(scen)
        day = None
        if kind == "transit":
            day = CFG["reference_saturday"] if scen == "pt_saturday" else CFG["reference_day"]
        stem = scen if kind == "transit" else scen
        cuts = (15, 30, 45, 60)
        head = (30, 45) if kind == "transit" else (30,)
        for grid, gw in GRIDS.items():
            w = b[f"w_{gw}"].to_numpy(np.float64)
            for dom, sel in domains(b, agg, kind, mv):
                cov = None
                flag = ""
                if kind == "transit":
                    cov = cov_share(b, np.ones(len(b), bool) if dom == "covered" else sel, w, mv)
                    if dom == "covered":
                        flag = "tylko komórki w masce pokrycia GTFS (§6); coverage_share = udział ludności FUA w masce; " + FLAG_DEST
                    elif cov is not None and cov < COV_MIN:
                        flag = (f"niepełne pokrycie GTFS: {cov * 100:.1f} % ludności ({DOM_LABEL.get(dom, dom)}) w masce "
                                "(< 85 %); wynik zaniżony, do porównań 'obszar pokryty' lub 'rdzeń'")
                is_centre = dom not in ("fua", "core", "covered")
                if is_centre:
                    cl = "komórki ≤ 1 km od punktu " + centre_label(agg, dom)
                    flag = "; ".join(x for x in [flag, cl, "układ wielobiegunowy: miara z jednego centrum tylko z zastrzeżeniem (§11)" if poly else ""] if x)
                for c in cuts:
                    perf, acc, prox = perf_cells(b, u, kind, "census" if gw == "census" else "raw", c)
                    r = AI.radius_m(SPEED[kind], c) / 1000
                    lab = f"Transport performance {mode_lab}, {c} min{', ' + win if win else ''}: osiągalni / mieszkający ≤ {r:g} km × 100 (średnia komórek ważona ludnością)"
                    main = (c in head and gw == "census" and not is_centre and
                            ((kind == "transit" and scen == "pt_am" and net == "all" and dom in ("covered", "core")) or
                             (kind == "walk" and dom in ("fua", "core"))))
                    tier = "main" if main else ("table" if c in head else "qa")
                    if is_centre and c not in head:
                        continue
                    R.add(dom, f"tp_{stem}_{c}min", lab, wmean(perf, w, sel), "%", grid, feed, tier, flag, cov, day)
                    if c in head and not is_centre:
                        R.add(dom, f"tp_{stem}_{c}min_ratio_of_means",
                              f"Jak tp_{stem}_{c}min, ale stosunek średnich ważonych (Σ w·osiągalni / Σ w·bliscy × 100)",
                              ratio_of_means(acc, prox, w, sel), "%", grid, feed, "table", flag, cov, day)
                        R.add(dom, f"acc_pop_{stem}_{c}min",
                              f"Ludność osiągalna {mode_lab} w {c} min{', ' + win if win else ''} (średnia ważona ludnością)",
                              wmean(acc, w, sel), "os.", grid, feed, "table", "; ".join(x for x in [FLAG_SIZE, flag] if x), cov, day)
                    if kind == "transit" and c in head and gw == "census" and not is_centre and f"r5only_census_{c}" in u:
                        p2, _, _ = perf_cells(b, u, kind, "census", c, col=f"r5only_census_{c}")
                        R.add(dom, f"tp_{stem}_{c}min_without_walk_rule",
                              f"Jak tp_{stem}_{c}min, ale bez reguły min(komunikacja, pieszo): sam wynik R5 z limitem dojścia 12 min (kontrola)",
                              wmean(p2, w, sel), "%", grid, feed, "qa", flag, cov, day)
                # max 2 transfers as a difference to the main result
                if scen == "pt_am_max3rides" and ("all" if net == "all" else net, "pt_am") in units and not is_centre:
                    um = units[(net, "pt_am")]
                    for c in head:
                        p3, _, _ = perf_cells(b, u, kind, gw, c)
                        pm, _, _ = perf_cells(b, um, kind, gw, c)
                        a, m_ = wmean(p3, w, sel), wmean(pm, w, sel)
                        R.add(dom, f"tp_pt_am_max3rides_minus_main_{c}min",
                              f"Zmiana transport performance {c} min (7:00–9:00) po ograniczeniu do maks. 2 przesiadek (3 przejazdów), pkt",
                              None if a is None or m_ is None else a - m_, "pkt", grid, feed, "table", flag, cov, day)
                # transfer dependence: share of the pt_am reach that needs at least one transfer
                if scen == "pt_am_direct" and (net, "pt_am") in units:
                    um = units[(net, "pt_am")]
                    dflag = "; ".join(x for x in [flag, "komórki bez osiągalnej ludności w scenariuszu głównym pominięte (brak danych)"] if x)
                    for c in head:
                        dep, ad, am = dependence_cells(u, um, gw, c)
                        R.add(dom, f"transfer_dependence_pt_am_{c}min",
                              f"Udział zasięgu, który wymaga przesiadki: odsetek ludności osiągalnej komunikacją + pieszo w {c} min "
                              "(środa 7:00–9:00), której nie da się osiągnąć bez przesiadki (średnia komórek ważona ludnością)",
                              wmean(dep, w, sel), "%", grid, feed, "table", dflag, cov, day)
                        if not is_centre:
                            R.add(dom, f"transfer_dependence_pt_am_{c}min_ratio_of_sums",
                                  f"Jak transfer_dependence_pt_am_{c}min, ale ze stosunku sum ważonych: (1 − Σ w·osiągalni bez przesiadki / Σ w·osiągalni) × 100",
                                  dependence_ratio_of_sums(ad, am, w, sel), "%", grid, feed, "table", dflag, cov, day)
                # proximity (window-independent) once per kind, absolute, size measure
                if scen in ("pt_am", "walk") and (kind != "transit" or net == "all") and not is_centre:
                    for c in head:
                        _, _, prox = perf_cells(b, u, kind, gw, c)
                        R.add(dom, f"prox_pop_{SPEED[kind]}_{c}min",
                              f"Ludność mieszkająca ≤ {AI.radius_m(SPEED[kind], c) / 1000:g} km od komórki (mianownik performance, średnia ważona)",
                              wmean(prox, w, sel), "os.", grid, None, "table", FLAG_SIZE)
                # jobs
                if kind == "transit" and scen == "pt_am" and not is_centre:
                    for c in head:
                        jl = "miejsca pracy w granicach miasta" + (" (tylko Gdańsk)" if agg == "trojmiasto" else "")
                        if has_jobs:
                            pj, aj, xj = perf_cells(b, u, kind, "jobs", c)
                            # ratio of means: cells at the edge of the jobs data have a proximity of a few jobs, and
                            # their cell ratios explode (> 1000), so the mean of ratios is not usable for jobs
                            vj, va = ratio_of_means(aj, xj, w, sel), wmean(aj, w, sel)
                            vmr = wmean(pj, w, sel & b["in_core"].to_numpy())
                            jf = "; ".join(x for x in [flag, "zbiór Goliszek 2026 (CC BY 4.0), horyzont 2025; cele tylko w granicach miasta; "
                                                       "stosunek średnich (średnia stosunków niestabilna przy małym mianowniku)"] if x)
                        else:
                            vj = va = vmr = None
                            jf = "brak danych: zbiór Goliszek nie obejmuje GZM"
                        R.add(dom, f"tp_jobs_{stem}_{c}min",
                              f"Transport performance – {jl}: Σ w·osiągalne komunikacją + pieszo w {c} min / Σ w·w promieniu {AI.radius_m('fast', c) / 1000:g} km × 100 ({win})",
                              vj, "%", grid, feed, "table", jf, cov, day)
                        if dom == "core":
                            R.add(dom, f"tp_jobs_{stem}_{c}min_mean_of_ratios",
                                  f"Jak tp_jobs_{stem}_{c}min, ale średnia stosunków komórek (tylko starty w granicach miasta; kontrola)",
                                  vmr, "%", grid, feed, "qa", jf, cov, day)
                        R.add(dom, f"acc_jobs_{stem}_{c}min",
                              f"Liczba miejsc pracy ({jl}) osiągalnych komunikacją + pieszo w {c} min ({win}), średnia ważona ludnością",
                              va, "miejsc pracy", grid, feed, "table", "; ".join(x for x in [FLAG_SIZE, jf] if x), cov, day)
    # transfers (sample)
    t = samples.get("transfers")
    if t is not None and len(t):
        ok = t[t["n_rides"].notna()]
        tr = ok[ok["n_rides"] >= 1]
        n = len(t)
        fl = (f"próba: {n} par OD (start ważony ludnością, cel ważony ludnością wśród osiągalnych w 45 min), {len(tr)} z "
              "przejazdem; r5py DetailedItineraries nie egzekwuje limitu dojścia 12 min; minuta odjazdu losowa 7:00–9:00")
        for dom, sel in (("fua", np.ones(len(t), bool)), ("core", t["o_in_core"].to_numpy(bool))):
            okd = ok[sel[t["n_rides"].notna().to_numpy()]] if len(ok) else ok
            trd = okd[okd["n_rides"] >= 1]
            day = CFG["reference_day"]
            g = "ghsl_census_scaled"
            R.add(dom, "transfers_median_pt_am", "Mediana liczby przesiadek w podróżach komunikacją (próba par OD, 7:00–9:00)",
                  float(np.median(trd["transfers"])) if len(trd) else None, "przesiadki", g, "all", "table", fl, None, day)
            R.add(dom, "transfers_mean_pt_am", "Średnia liczba przesiadek w podróżach komunikacją (próba par OD, 7:00–9:00)",
                  float(trd["transfers"].mean()) if len(trd) else None, "przesiadki", g, "all", "table", fl, None, day)
            for k, lab in ((0, "bez przesiadki"), (1, "z 1 przesiadką"), (2, "z ≥ 2 przesiadkami")):
                v = (trd["transfers"] >= 2).mean() if k == 2 else (trd["transfers"] == k).mean()
                R.add(dom, f"transfers_share_{k}{'plus' if k == 2 else ''}_pt_am",
                      f"Udział podróży komunikacją {lab} (próba par OD)", 100 * float(v) if len(trd) else None, "%", g,
                      "all", "table", fl, None, day)
            R.add(dom, "transfers_share_walk_only_pt_am",
                  "Udział par OD, dla których najszybciej jest pieszo (próba, cel osiągalny w 45 min)",
                  100 * float((okd["n_rides"] == 0).mean()) if len(okd) else None, "%", g, "all", "table", fl, None, day)
            R.add(dom, "transfers_sample_n", "Liczba par OD w próbie przesiadek (z wynikiem itinerarium)",
                  float(len(okd)), "par", g, "all", "qa", fl, None, day)
    return R.rows


# ------------------------------------------------------------------ outputs
FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]


def write_metrics(rows: list[dict], status: list[dict]) -> None:
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["feed_variant"] or "", m["population_grid"] or "",
                                       m["domain"], m["metric"]))
    METRICS.mkdir(parents=True, exist_ok=True)
    write_json(METRICS / "metrics_access.json", {"generated_for_timetable_date": CFG["reference_day"], "metrics": rows,
                                                 "status": status})
    with open(METRICS / "metrics_access.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


def city_summary(agg, b, units) -> dict:
    """Headline numbers per city for the chart (census-scaled grid)."""
    w = b["w_census"].to_numpy(np.float64)
    out = {}

    def tp(net, scen, c, dom):
        u = units.get((net, scen))
        if u is None:
            return None
        kind = SCENARIOS[scen]["kind"]
        sel = dict(domains(b, agg, kind, AI.mask_variant(net) if kind == "transit" else None))[dom]
        return sig(wmean(perf_cells(b, u, kind, "census", c)[0], w, sel))

    for dom in ("covered", "core", "fua"):
        out[dom] = {
            "transit_30": tp("all", "pt_am", 30, dom), "transit_45": tp("all", "pt_am", 45, dom),
            "transit_30_official": tp("official", "pt_am", 30, dom) if dom != "covered" else None,
            "transit_45_official": tp("official", "pt_am", 45, dom) if dom != "covered" else None,
            "walk_30": tp("street", "walk", 30, dom) if dom != "covered" else None,
            "bike_lts3_30": tp("street", "bike_lts3", 30, dom) if dom != "covered" else None,
            "bike_lts4_30": tp("street", "bike_lts4", 30, dom) if dom != "covered" else None,
            "coverage_share_pct": sig(100 * cov_share(b, b["in_core"].to_numpy() if dom == "core" else np.ones(len(b), bool), w, "all")),
            "curve_transit": [tp("all", "pt_am", c, dom) for c in AI.CUTOFFS],
            "curve_walk": [tp("street", "walk", c, dom) for c in AI.CUTOFFS] if dom != "covered" else None,
            "curve_bike_lts3": [tp("street", "bike_lts3", c, dom) for c in AI.CUTOFFS] if dom != "covered" else None,
        }
    return out


DGREGIO = {"eu_average": {"transit_30": 24, "transit_45": 57, "walk_30": 52, "bike_30": 75},
           "cities_chart_read": {"warszawa": {"transit_30": 31, "transit_45": 62, "walk_30": 49, "bike_30": 70.5},
                                 "poznan": {"transit_30": 26, "transit_45": 75, "walk_30": 43, "bike_30": 81},
                                 "lodz": {"transit_30": 25.5, "transit_45": 75, "walk_30": 54, "bike_30": 81}}}
METHOD_DIFFS = [
    "Domena: DG REGIO liczy starty i cele tylko w urban centre; tu starty w FUA (oraz rdzeń, obszar pokryty), cele i mianownik w FUA + 15 km.",
    "Dojście: OTP w DG REGIO do 5 km pieszo; tu 1 km (12 min przy 5 km/h) na dojście i odejście, przy czym podróż czysto piesza jest bez limitu (min(komunikacja, pieszo)).",
    "Czas: DG REGIO średnia z 9 odjazdów co 15 min w 2-godzinnym szczycie; tu mediana z odjazdów co minutę 7:00–9:00.",
    "Rozkłady: DG REGIO 2018; tu środa 2026-11-25 (sobota 2026-11-28).",
    "Ludność: DG REGIO 2011 na poligonach Urban Atlas 2012; tu NSP 2021 rozłożony wzorem GHSL 2020 na komórki 250 m (wariant surowy GHSL obok).",
    "Router: OpenTripPlanner 1.2.0 wobec Conveyal R5 v7.5.1; prędkość roweru i LTS w DG REGIO nieopisane (tu 15 km/h i LTS ≤ 3 albo ≤ 4).",
    "Wartości DG REGIO odczytane z wykresów (rys. 7, 9, 10), dokładność ok. ±1 pkt; agregacja po komórkach nieopisana wprost.",
]


def write_chart(summ: dict, status: list[dict]) -> None:
    out = {
        "title": "Transport performance: odsetek ludności mieszkającej w pobliżu, który można osiągnąć w 30 / 45 min",
        "definition": ("Performance komórki = ludność osiągalna w czasie T / ludność w linii prostej w promieniu "
                       "odpowiadającym 15 km/h (komunikacja, rower) albo 5 km/h (pieszo) × 100; średnia po komórkach "
                       "z ludnością ważona ludnością (brief §4.6, Poelman, Dijkstra i Ackermans 2020). Komunikacja: "
                       "mediana z odjazdów co minutę 7:00–9:00 w środę 2026-11-25, dojście ≤ 1 km, maks. 60 min, "
                       "czas = min(komunikacja + pieszo, sam spacer)."),
        "timetable_date": CFG["reference_day"], "osm_date": OSM_DATE,
        "population_grid": REC["grid"], "population_date": POP_DATE[REC["grid"]], "feed_variant": REC["network"],
        "cutoffs_min": AI.CUTOFFS,
        "recommended_domain": "covered (komunikacja), fua i core (pieszo, rower)",
        "bike_lts_note": "Rower w dwóch wariantach poziomu stresu ruchu (LTS ≤ 3: domyślne r5py; LTS ≤ 4); wybór wariantu głównego należy do właściciela (różnica +10 do +17 pkt).",
        "caveats": [
            "Rozkłady 2026, ludność 2020–2021.",
            "Poza maską pokrycia GTFS wynik komunikacji to 'brak danych'; FUA przy pokryciu < 85 % jest zaniżona.",
            "Braki przewoźników po stronie celów zaniżają wynik komunikacji także wewnątrz maski.",
            "Trójmiasto i GZM: układy wielobiegunowe; miara performance nie zależy od centrum, granice FUA są umowne.",
            "Liczba osiągalnych mieszkańców w wartościach bezwzględnych mierzy wielkość miasta, nie jakość transportu.",
        ],
        "benchmark_dgregio": {**DGREGIO, "source": "Poelman, Dijkstra, Ackermans (2020), DG REGIO WP 01/2020, doi:10.2776/021137; "
                                                    "wartości miast odczytane z wykresów (±1 pkt)",
                              "method_differences": METHOD_DIFFS,
                              "comparable_domain": "core (najbliżej urban centre); patrz qa/access/access.md"},
        "cities": {a: {"name": CFG["agglomerations"][a]["name"],
                       "polycentric": bool(CFG["agglomerations"][a].get("polycentric", False)), "domains": s}
                   for a, s in sorted(summ.items())},
        "pending_units": [f"{r['agglomeration']} {r['network']}/{r['scenario']}" for r in status if r["state"] != "done"],
    }
    write_json(CHARTS / "access_performance.json", out)


def cell_layer(agg: str, b: pd.DataFrame, units: dict) -> pd.DataFrame:
    w = b["w_census"].to_numpy(np.float64)
    d = pd.DataFrame({"agglomeration": agg, "cell_id": b["cell_id"].to_numpy(),
                      "pop_census_scaled": [sig(x, 4) for x in w], "in_core": b["in_core"].to_numpy(),
                      "in_mask_all": b["in_mask_all"].to_numpy()})

    def col(net, scen, c, masked):
        u = units.get((net, scen))
        if u is None:
            return np.full(len(b), np.nan, np.float32)
        p = perf_cells(b, u, SCENARIOS[scen]["kind"], "census", c)[0]
        if masked:
            p = np.where(b["in_mask_all"].to_numpy(), p, np.nan)
        return np.array([np.nan if not np.isfinite(x) else sig(x, 3) for x in p], dtype=np.float32)

    d["tp_pt_am_30"] = col("all", "pt_am", 30, True)
    d["tp_pt_am_45"] = col("all", "pt_am", 45, True)
    d["tp_walk_30"] = col("street", "walk", 30, False)
    d["tp_bike_lts3_30"] = col("street", "bike_lts3", 30, False)
    d["tp_bike_lts4_30"] = col("street", "bike_lts4", 30, False)
    d["tp_pt_am_direct_30"] = col("all", "pt_am_direct", 30, True)
    for c in (30, 45):
        ud, um = units.get(("all", "pt_am_direct")), units.get(("all", "pt_am"))
        if ud is None or um is None:
            dep = np.full(len(b), np.nan)
        else:
            dep = np.where(b["in_mask_all"].to_numpy(), dependence_cells(ud, um, "census", c)[0], np.nan)
        d[f"transfer_dependence_{c}"] = np.array([np.nan if not np.isfinite(x) else sig(x, 3) for x in dep], dtype=np.float32)
    lon, lat = AI.TO4326.transform(b["x"].to_numpy(), b["y"].to_numpy())
    d["lon"], d["lat"] = np.round(lon, 6), np.round(lat, 6)
    return d


def write_layer(parts: list[pd.DataFrame]) -> float:
    import geopandas as gpd
    LAYERS.mkdir(parents=True, exist_ok=True)
    d = pd.concat(parts, ignore_index=True).sort_values(["agglomeration", "cell_id"]).reset_index(drop=True)
    g = gpd.GeoDataFrame(d.drop(columns=["lon", "lat"]), geometry=gpd.points_from_xy(d["lon"], d["lat"]), crs="EPSG:4326")
    g.to_parquet(LAYERS / "access_cells.parquet", index=False)
    return round((LAYERS / "access_cells.parquet").stat().st_size / 1e6, 2)


def load_samples(agg: str) -> dict:
    out = {}
    for scen, key in (("transfers_am", "transfers"), ("odpairs", "odpairs")):
        u = load_unit(agg, "all", scen)
        if u is not None:
            out[key] = u
    return out


def main() -> None:
    t0 = time.time()
    status = unit_status(AGGS)
    rows, summ, layers, ctx = [], {}, [], {}
    for agg in AGGS:
        units = {}
        for pr, net, scens in UNITS:
            for s in scens:
                if SCENARIOS[s]["kind"] in ("transit", "walk", "bike"):
                    u = load_unit(agg, net, s)
                    if u is not None:
                        units[(net, s)] = u
        samples = load_samples(agg)
        if not units and not samples:
            continue
        b = base_frame(agg)
        for u in units.values():
            assert (u["cell_id"].to_numpy() == b["cell_id"].to_numpy()).all()
        rows += metric_rows(agg, b, units, samples)
        summ[agg] = city_summary(agg, b, units)
        layers.append(cell_layer(agg, b, units))
        ctx[agg] = {"base": b, "units": units, "samples": samples}
        print(f"{agg}: {len(units)} routed units, samples {sorted(samples)}", flush=True)
    write_metrics(rows, status)
    write_chart(summ, status)
    size = write_layer(layers) if layers else None
    from pipeline.access_qa import write_qa
    write_qa(ctx, rows, status, size, t0)
    print(f"aggregate: {len(rows)} metric rows, {sum(r['state'] == 'done' for r in status)}/{len(status)} units done, "
          f"layer {size} MB, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
