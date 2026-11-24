"""Aggregate the urban-centre variant (pipeline.access_uc) into metrics_access_uc.* and results/qa/access_uc/.

Row schema and conventions are those of metrics_access (pipeline.access_aggregate): domain id ``urban_centre``,
metric ids tp_<scenario>_<cutoff>min (+ _ratio_of_means), feed_variant ``all`` for transit and empty for walk /
bike, both population grids (census-scaled is the panel variant), values to 4 significant digits, sorted.
An agglomeration whose routing is not finished gets no rows for that scenario (listed as pending), never 0.
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
from pipeline import access_uc as U
from pipeline.access_aggregate import COV_MIN, FLAG_DEST, FLAG_SIZE, GRID_LABEL, GRIDS, POP_DATE, source
from pipeline.common import sig, write_json, write_meta

NAMES = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
         "trojmiasto": "Trójmiasto", "gzm": "GZM"}
DOMAIN = "urban_centre"
DOM_TEXT = "centrum miejskie (urban centre, Eurostat 2021)"
FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]
KIND = {"pt_am": "transit", "walk": "walk", "bike_lts3": "bike", "bike_lts4": "bike"}
SPEED = {"transit": "fast", "walk": "walk", "bike": "fast"}
MODE_LAB = {"pt_am": "komunikacją zbiorową + pieszo", "walk": "pieszo (5 km/h)",
            "bike_lts3": "rowerem (15 km/h, poziom stresu LTS ≤ 3)", "bike_lts4": "rowerem (15 km/h, poziom stresu LTS ≤ 4)"}


def mor(acc, prox, w):
    m = (w > 0) & (prox > 0) & np.isfinite(acc)
    return None if w[m].sum() <= 0 else float(100 * (w[m] * acc[m] / prox[m]).sum() / w[m].sum())


def rom(acc, prox, w):
    m = (w > 0) & np.isfinite(acc)
    den = (w[m] * prox[m]).sum()
    return None if den <= 0 else float(100 * (w[m] * acc[m]).sum() / den)


def prox_frame(agg: str) -> pd.DataFrame:
    """Proximity on the domain (cached with the domain hash)."""
    from pipeline.access_dgregio import proximity
    p = U.OUT / agg / "proximity.parquet"
    s = p.with_suffix(".sig")
    h = U.uc_hash(agg) + "|prox1"
    if p.exists() and s.exists() and s.read_text() == h:
        return pd.read_parquet(p)
    u = U.uc_cells(agg)
    df = proximity(u, u, U.RADII).reset_index(drop=True)
    df.insert(0, "cell_id", u["cell_id"].to_numpy())
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    s.write_text(h)
    return df


def walk_frame(agg: str) -> pd.DataFrame:
    p = U.OUT / agg / "walk.parquet"
    s = p.with_suffix(".sig")
    h = U.uc_hash(agg) + "|" + json.loads((AI.ACCESS_INT / agg / "street" / "walk" / "manifest.json").read_text(encoding="utf-8"))["signature"]
    if p.exists() and s.exists() and s.read_text() == h:
        return pd.read_parquet(p)
    df = U.walk_unit(agg)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    s.write_text(h)
    return df


def load_units(agg: str) -> tuple[dict, list[str]]:
    units, pending = {}, []
    for scen in U.SCENARIOS:
        if U.unit_done(agg, scen):
            units[scen] = pd.read_parquet(U.unit_path(agg, scen))
        else:
            pending.append(scen)
    units["walk"] = walk_frame(agg)
    return units, pending


def city_rows(agg: str, units: dict, cent: pd.DataFrame) -> tuple[list[dict], dict]:
    u = U.uc_cells(agg)
    P = prox_frame(agg)
    assert (P["cell_id"].to_numpy() == u["cell_id"].to_numpy()).all()
    m = AI.mask(agg).set_index("cell_id").reindex(u["cell_id"])
    in_mask = m["in_mask_all"].fillna(False).astype(bool).to_numpy()
    inc = cent[cent.included]
    multi = len(inc) > 1
    names = ", ".join(f"{r.main_lau} ({r.population_2021_official:,})".replace(",", " ") for r in inc.itertuples())
    dom_flag = f"suma {len(inc)} centrów miejskich w FUA: {names}" if multi else ""
    src_uc = "; centra miejskie: Eurostat GISCO HDENS_CLST_2021"
    rows, summ = [], {}

    def add(metric, label, value, unit, grid, feed, tier, flag="", cov=None, day=None, src=None):
        rows.append({"agglomeration": agg, "domain": DOMAIN, "metric": metric, "label": label,
                     "value": sig(value) if value is not None else None, "unit": unit,
                     "grid": GRID_LABEL[grid] if grid else None, "source": src,
                     "population_date": POP_DATE[grid] if grid else None, "timetable_date": day,
                     "coverage_share": sig(cov) if cov is not None else None, "flag": flag or None, "tier": tier,
                     "feed_variant": feed, "population_grid": grid})

    area = int(inc.cells_1km_in_fua.sum())
    add("area", f"Powierzchnia: {DOM_TEXT}, komórki 1 km w FUA", float(area), "km²", None, None, "table",
        "; ".join(x for x in [f"centra: {names}", "obszar = suma centrów w FUA (DG REGIO liczy każde centrum osobno)" if multi else ""] if x),
        src="Eurostat GISCO HDENS_CLST_2021 (centra miejskie na siatce spisowej 2021)")
    summ["area"] = area
    fr = U.frame(agg)
    core_w = fr.loc[fr["in_core"], "w_census"]
    summ["core_outside_uc"] = float(fr.loc[fr["in_core"] & ~fr["in_uc"], "w_census"].sum() / core_w.sum())
    for grid, gw in U_GRIDS.items():
        w = u[f"w_{gw}"].to_numpy(np.float64)
        add("population_census" if gw == "census" else "population_ghsl",
            f"Ludność: {DOM_TEXT} (komórki 250 m w centrum i w FUA)", float(w.sum()), "os.", grid, None, "table", dom_flag,
            src=source(None, grid).split(";")[1].strip() + src_uc)
        cov = float(w[in_mask].sum() / w.sum())
        if gw == "census":
            summ["population"], summ["coverage"] = float(w.sum()), cov
        for scen, df in sorted(units.items()):
            kind = KIND[scen]
            assert (df["cell_id"].to_numpy() == u["cell_id"].to_numpy()).all()
            feed = "all" if kind == "transit" else None
            day = U.REF_DAY if kind == "transit" else None
            flag, cv = dom_flag, None
            if kind == "transit":
                cv = cov
                if cov < COV_MIN:
                    flag = "; ".join(x for x in [f"niepełne pokrycie GTFS: {cov * 100:.1f} % ludności ({DOM_TEXT}) w masce (< 85 %); "
                                                 "wynik zaniżony", dom_flag] if x)
            src = source(feed, grid) + src_uc
            heads = (30, 45) if kind == "transit" else (30,)
            for c in heads:
                acc = df[f"acc_{gw}_{c}"].to_numpy(np.float64)
                rk = {"transit": f"fast{c}", "bike": "fast30", "walk": "walk30"}[kind]
                prox = P[f"prox_{gw}_{rk}"].to_numpy(np.float64)
                r_km = AI.radius_m(SPEED[kind], c) / 1000
                win = ", środa 7:00–9:00" if kind == "transit" else ""
                lab = (f"Transport performance {MODE_LAB[scen]}, {c} min{win}: osiągalni / mieszkający ≤ {r_km:g} km × 100 "
                       f"(średnia komórek ważona ludnością); starty, cele i mianownik tylko w: {DOM_TEXT}")
                main = gw == "census" and kind in ("transit", "walk")
                v1, v2 = mor(acc, prox, w), rom(acc, prox, w)
                add(f"tp_{scen}_{c}min", lab, v1, "%", grid, feed, "main" if main else "table", flag, cv, day, src)
                add(f"tp_{scen}_{c}min_ratio_of_means", f"Jak tp_{scen}_{c}min, ale stosunek średnich ważonych (Σ w·osiągalni / Σ w·bliscy × 100)",
                    v2, "%", grid, feed, "table", flag, cv, day, src)
                add(f"acc_pop_{scen}_{c}min", f"Ludność osiągalna {MODE_LAB[scen]} w {c} min{win} w obrębie: {DOM_TEXT} (średnia ważona ludnością)",
                    float((w * acc).sum() / w.sum()), "os.", grid, feed, "table", "; ".join(x for x in [FLAG_SIZE, flag] if x), cv, day, src)
                if gw == "census":
                    summ[(scen, c)] = (v1, v2)
                if scen in ("pt_am", "walk"):
                    add(f"prox_pop_{SPEED[kind]}_{c}min", f"Ludność mieszkająca ≤ {r_km:g} km od komórki w obrębie: {DOM_TEXT} (mianownik, średnia ważona)",
                        float((w * prox).sum() / w.sum()), "os.", grid, None, "table", FLAG_SIZE, src=source(None, grid) + src_uc)
    return rows, summ


U_GRIDS = {"ghsl_census_scaled": "census", "ghsl_raw": "raw"}
assert set(U_GRIDS) == set(GRIDS)


def core_values() -> dict:
    d = json.loads((U.METRICS / "metrics_access.json").read_text(encoding="utf-8"))["metrics"]
    out = {}
    for r in d:
        if r["domain"] == "core" and r["population_grid"] == "ghsl_census_scaled" and r["feed_variant"] in ("all", None):
            out[(r["agglomeration"], r["metric"])] = r["value"]
    return out


def f1(x, nd=1):
    return "–" if x is None else f"{x:.{nd}f}".replace(".", ",")


def write_md(summ: dict, cent: pd.DataFrame, pending: dict, runlog: list[str]) -> None:
    core = core_values()
    L = []
    A = L.append
    A("# Transport performance w centrach miejskich (urban centres), 7 aglomeracji")
    A("")
    A("Plik generuje `python -m pipeline.access_uc aggregate`. Wyniki: `results/metrics/metrics_access_uc.csv/json`, domena `urban_centre`.")
    A("")
    A("## 1. Po co i jak")
    A("")
    A("Wyniki produkcyjne liczone są dla rdzenia (granice miasta) i FUA, a te obszary mają w różnych miastach bardzo różną wielkość i zabudowę. "
      "Tu wszystkie miasta porównujemy na tym samym rodzaju obszaru: **centrum miejskim** (urban centre) w definicji Eurostatu, czyli zwartym skupisku komórek 1 km² "
      "o gęstości ≥ 1500 os./km² i ≥ 50 tys. mieszkańców. Warstwa: **Eurostat GISCO `HDENS_CLST_2021`**, wydana 2024-11-19, zbudowana na siatce spisowej 2021 "
      "(oficjalna, aktualna ludność); warstwa 2011 służy tylko do benchmarku DG REGIO (`results/qa/access/dgregio/`).")
    A("")
    A("- **Domena:** suma wszystkich centrów, których ponad połowa komórek 1 km leży w FUA aglomeracji; starty, cele i mianownik (proximity) tylko w tej domenie. "
      "Komórka 250 m należy do domeny, gdy jej środek leży w komórce 1 km centrum i w FUA. Gdzie centrów jest kilka (Warszawa, Łódź, Trójmiasto, GZM), "
      "liczymy je łącznie jako jeden obszar; **DG REGIO traktuje każde centrum jako osobne miasto**, więc dla tych aglomeracji wyniki nie są wprost porównywalne z ich metodą.")
    A("- **Metoda produkcyjna** (`access.md` §1), zmienia się tylko domena: R5 v7.5.1, środa " + U.REF_DAY + ", odjazdy co minutę 7:00–9:00, mediana, dojście i odejście ≤ 1 km, "
      "pieszo 5 km/h, reguła min(komunikacja, sam spacer), wszystkie feedy, siatka 250 m przeskalowana do NSP 2021; rower 15 km/h, LTS ≤ 3 i ≤ 4. "
      "Czasy spaceru z produkcyjnej pamięci spacerów; komunikacja i rower policzone osobno na kopiach sieci produkcyjnych, na pełnym zbiorze komórek każdego centrum (bez próbkowania).")
    A("- **Agregacja:** średnia stosunków komórek ważona ludnością (wynik główny) i stosunek średnich (wariant tabelaryczny).")
    A("- **Pokrycie GTFS:** udział ludności domeny w masce pokrycia fazy 2 (wariant „wszystkie”); poniżej 85 % wynik dostaje flagę „niepełne pokrycie GTFS”. "
      "Wynik miasta obejmuje wszystkie komórki domeny (jak wiersze FUA i rdzenia w `metrics_access`); warstwy komórek tu nie ma.")
    A("")
    A("## 2. Centra miejskie w aglomeracjach")
    A("")
    t = cent.copy()
    t["Aglomeracja"] = t.agglomeration.map(NAMES)
    t = t[["Aglomeracja", "main_lau", "population_2021_official", "cells_1km", "cells_1km_in_fua", "included", "lau_cells"]]
    t.columns = ["Aglomeracja", "Centrum (gmina z największą liczbą komórek)", "Ludność 2021 (Eurostat)", "Komórek 1 km", "W FUA", "W domenie", "Gminy (liczba komórek)"]
    t["Ludność 2021 (Eurostat)"] = t["Ludność 2021 (Eurostat)"].map(lambda x: f"{x:,}".replace(",", " "))
    t["W domenie"] = t["W domenie"].map({True: "tak", False: "nie"})
    A(md(t))
    A("")
    A("## 3. Wyniki: rdzeń (produkcja) i centrum miejskie")
    A("")
    rows = []
    for agg in U.AGGS:
        s = summ.get(agg)
        if not s:
            continue
        r = {"Aglomeracja": NAMES[agg], "Pow. km²": s["area"], "Ludność (NSP 2021, 250 m)": f"{s['population']:,.0f}".replace(",", " "),
             "Ludność miasta (rdzenia) poza UC": f1(100 * s["core_outside_uc"]) + " %",
             "Pokrycie GTFS": f1(100 * s["coverage"]) + " %" + (" (niepełne)" if s["coverage"] < 0.85 else "")}
        for key, lab in ((("pt_am", 30), "KZ 30"), (("pt_am", 45), "KZ 45"), (("walk", 30), "Pieszo 30"),
                         (("bike_lts3", 30), "Rower LTS 3"), (("bike_lts4", 30), "Rower LTS 4")):
            cm = core.get((agg, f"tp_{key[0]}_{key[1]}min"))
            v = s.get(key)
            r[lab + ": rdzeń → UC"] = f"{f1(cm)} → {f1(v[0]) if v else 'oczekuje'}"
        rows.append(r)
    A("Średnia stosunków komórek (wynik główny). „Rdzeń” to wynik produkcyjny z `metrics_access` (starty w mieście, cele i mianownik w FUA + 15 km).")
    A("")
    A(md(pd.DataFrame(rows)))
    A("")
    rows = []
    for agg in U.AGGS:
        s = summ.get(agg)
        if not s:
            continue
        r = {"Aglomeracja": NAMES[agg]}
        for key, lab in ((("pt_am", 30), "KZ 30"), (("pt_am", 45), "KZ 45"), (("walk", 30), "Pieszo 30"),
                         (("bike_lts3", 30), "Rower LTS 3"), (("bike_lts4", 30), "Rower LTS 4")):
            cm = core.get((agg, f"tp_{key[0]}_{key[1]}min_ratio_of_means"))
            v = s.get(key)
            r[lab + ": rdzeń → UC"] = f"{f1(cm)} → {f1(v[1]) if v else 'oczekuje'}"
        rows.append(r)
    A("Stosunek średnich (wariant tabelaryczny):")
    A("")
    A(md(pd.DataFrame(rows)))
    A("")
    A("## 4. Co zmienia się w kolejności miast")
    A("")
    rk = []
    for key, lab in ((("pt_am", 30), "KZ 30"), (("pt_am", 45), "KZ 45"), (("walk", 30), "Pieszo 30"), (("bike_lts4", 30), "Rower LTS 4")):
        c_ = {a: core.get((a, f"tp_{key[0]}_{key[1]}min")) for a in U.AGGS}
        u_ = {a: (summ.get(a, {}).get(key) or (None,))[0] for a in U.AGGS}
        if any(v is None for v in u_.values()) or any(v is None for v in c_.values()):
            A(f"- {lab}: niepełne dane (oczekuje), ranking pominięty.")
            continue
        oc = sorted(U.AGGS, key=lambda a: -c_[a])
        ou = sorted(U.AGGS, key=lambda a: -u_[a])
        A(f"- **{lab}.** Rdzeń: " + " > ".join(f"{NAMES[a]} {f1(c_[a])}" for a in oc) + ". Centrum miejskie: "
          + " > ".join(f"{NAMES[a]} {f1(u_[a])}" for a in ou) + ".")
        for a in U.AGGS:
            rk.append({"miara": lab, "agglomeration": a, "core": c_[a], "urban_centre": u_[a], "rank_core": oc.index(a) + 1, "rank_uc": ou.index(a) + 1})
    if rk:
        pd.DataFrame(rk).to_csv(U.QA / "ranking.csv", index=False, lineterminator="\n", float_format="%.4g")
    if rk:
        R = pd.DataFrame(rk)
        for lab, g in R.groupby("miara", sort=False):
            ch = g[g.rank_core != g.rank_uc]
            txt = "; ".join(f"{NAMES[r.agglomeration]} {r.rank_core} → {r.rank_uc}" for r in ch.itertuples()) or "bez zmian"
            A(f"- Zmiany miejsc, {lab} (rdzeń → centrum): {txt}.")
    A("")
    A("## 5. Stan i zastrzeżenia")
    A("")
    pend = [f"{NAMES[a]}: {', '.join(p)}" for a, p in pending.items() if p]
    A("- Oczekuje (routing niedokończony, brak wierszy): " + ("; ".join(pend) if pend else "nic") + ".")
    A("- Czasy routingu (6 wątków, `-Xmx 8G`, jedna JVM, równolegle z produkcyjnym `pipeline.access run`): " + "; ".join(runlog) + ".")
    big = [f"{NAMES[a]} {summ[a]['area']} km²" for a in U.AGGS if a in summ and summ[a]["area"] > 250]
    small = [summ[a]["area"] for a in U.AGGS if a in summ and summ[a]["area"] <= 250]
    if big and small:
        A(f"- Wielkość domeny nadal się różni: {', '.join(big)} wobec {min(small)}–{max(small)} km² w pozostałych miastach. "
          "W małym, zwartym centrum promień 11,25 km obejmuje prawie całą jego ludność, więc KZ 45 zbliża się tam do „odsetka całego centrum osiągalnego w 45 min” "
          "i jest wyższy niż w dużym centrum przy tej samej jakości komunikacji; porównania KZ 45 między dużymi i małymi centrami czytać ostrożnie (benchmark DG REGIO, §6).")
    A("- Centra wielobiegunowe są łączone w jedną domenę; podróże między nimi (np. Gdańsk–Gdynia, Katowice–Gliwice) liczą się do wyniku, jeśli mieszczą się w progu, a mianownik obejmuje tylko ludność centrów.")
    out = cent[cent.included & (cent.cells_1km_in_fua < cent.cells_1km)]
    for r in out.itertuples():
        A(f"- {NAMES[r.agglomeration]}: centrum {r.main_lau} ma {r.cells_1km - r.cells_1km_in_fua} z {r.cells_1km} komórek 1 km poza FUA; te komórki nie są używane.")
    excl = cent[~cent.included]
    A("- Centra tylko częściowo w FUA (≤ połowa komórek) i pominięte: " + (", ".join(f"{NAMES[r.agglomeration]}: {r.main_lau}" for r in excl.itertuples()) or "brak") + ".")
    A("- Pokrycie GTFS liczone na masce fazy 2; braki przewoźników po stronie celów obniżają wynik także wewnątrz maski.")
    A("")
    (U.QA / "access_uc.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def main(aggs: list[str] | None = None) -> None:
    t0 = time.time()
    aggs = aggs or U.AGGS
    U.QA.mkdir(parents=True, exist_ok=True)
    all_rows, summ, pending, cents = [], {}, {}, []
    for agg in aggs:
        cent = U.clusters(agg)
        cents.append(cent)
        units, pend = load_units(agg)
        pending[agg] = pend
        r, s = city_rows(agg, units, cent)
        all_rows += r
        summ[agg] = s
    cent = pd.concat(cents, ignore_index=True)
    cent.to_csv(U.QA / "urban_centres.csv", index=False, lineterminator="\n")
    rows = sorted(all_rows, key=lambda m: (m["agglomeration"], m["feed_variant"] or "", m["population_grid"] or "", m["domain"], m["metric"]))
    status = [{"agglomeration": a, "scenario": s, "state": "pending" if s in pending[a] else "done"} for a in aggs for s in [*U.SCENARIOS, "walk"]]
    write_json(U.METRICS / "metrics_access_uc.json", {"generated_for_timetable_date": U.REF_DAY, "metrics": rows, "status": status})
    with open(U.METRICS / "metrics_access_uc.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})
    runlog = [l[20:] for l in (U.OUT / "run.log").read_text(encoding="utf-8").splitlines() if "origins in" in l] if (U.OUT / "run.log").exists() else []
    write_md(summ, cent, pending, runlog)
    extra = {"code_version": U.CODE_VERSION, "timetable_date": U.REF_DAY, "rows": len(rows),
             "urban_centre_layer": {"path": "data/raw/eurostat_hdens_2021/HDENS-CLST-2021.zip",
                                    "url": json.loads((U.RAW / "eurostat_hdens_2021" / "SOURCE.json").read_text(encoding="utf-8"))["url"],
                                    "licence": "Eurostat GISCO download rules, (c) European Union, re-use with attribution"},
             "pending": {a: p for a, p in pending.items() if p}, "routing_log": runlog}
    write_meta(U.QA, "access_uc", started=t0, extra={**extra, "outputs": sorted(p.name for p in U.QA.iterdir() if p.name != "_meta.json")})
    tmp = Path(tempfile.mkdtemp())
    write_meta(tmp, "access_uc", started=t0, extra={**extra, "outputs": ["metrics_access_uc.csv", "metrics_access_uc.json"]})
    shutil.copyfile(tmp / "_meta.json", U.METRICS / "_meta_access_uc.json")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"access_uc: {len(rows)} rows; pending {sum(len(p) for p in pending.values())} units; {time.time() - t0:.0f} s")
