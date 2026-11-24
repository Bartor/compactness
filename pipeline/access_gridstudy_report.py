"""Report for pipeline.access_gridstudy: decomposition tables, comparison with the grid study's own Polish values and
class means, results/qa/access/gridstudy/ and results/metrics/metrics_access_gridstudy.{csv,json}.

Row schema as metrics_access_uc (domain ``urban_centre``); comparison-only rows, tier ``table``; metric ids
``tp_gridstudy_*`` (ours) and ``tp_gridstudy_dgregio_*`` (DG REGIO's own value reconstructed from its viewer cells).
An agglomeration whose routing is unfinished gets no rows (listed as pending), never 0.
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

from pipeline import access_gridstudy as G
from pipeline import access_gridstudy_eu as E
from pipeline import access_uc as U
from pipeline.access_aggregate import GRID_LABEL, POP_DATE, source
from pipeline.access_uc_aggregate import FIELDS, NAMES, md
from pipeline.common import sig, write_json, write_meta

GRIDS = {"ghsl_census_scaled": "census", "ghsl_raw": "raw"}
DOMAIN = "urban_centre"
# grid study Table 1 (p. 3): population-weighted averages and min-max by urban-centre size class (30 min / 45 min)
CLASSES = [("50k-100k", 5e4, 1e5, 100, (15.4, 45.9, 90.1), (21.1, 53.1, 89.6)),
           ("100k-250k", 1e5, 2.5e5, 51, (26.6, 43.1, 83.1), (16.7, 56.7, 89.3)),
           ("250k-500k", 2.5e5, 5e5, 14, (23.8, 41.8, 63.7), (31.7, 63.3, 83.9)),
           ("500k-1m", 5e5, 1e6, 17, (24.8, 39.3, 56.8), (31.3, 59.8, 79.1)),
           ("1m-2.5m", 1e6, 2.5e6, 10, (26.0, 35.8, 47.1), (37.4, 59.5, 71.1)),
           ("2.5m+", 2.5e6, 1e12, 5, (20.4, 28.1, 38.7), (32.4, 44.5, 61.7))]
ALL = (15.4, 36.2, 90.1), (16.7, 53.9, 89.6)
EU_AGG = {v: k for k, v in E.PL.items()}

# variant key: (run, percentile, walk rule, destination domain, radii); chain from the published urban-centre value
STEPS = [
    ("s1", ("r_prod", "med", "w60", "uc", "our"), "Dostępność liczona tylko w promieniu 7,5 / 11,25 km (grid study liczy osiągalnych tylko w promieniu; my dotąd wszystkich osiągalnych)"),
    ("s2", ("r_prod", "med", "w60", "all", "our"), "Cele i mianownik bez ograniczenia do urban centre (wszystkie zaludnione komórki w promieniu)"),
    ("s3", ("r_prod", "med", "w60", "all", "grid"), "Promienie 8 / 12 km (16 km/h) zamiast 7,5 / 11,25 km"),
    ("s4", ("r_grid", "med", "w15", "all", "grid"), "Pieszo 4,8 km/h, dojście i odejście do 15 min, sam spacer do 1,2 km (zamiast 5 km/h, 12 min, spacer do 60 min)"),
    ("s5", ("r_peak", "min6", "w15", "all", "grid"), "Najkrótszy z 6 odjazdów co 5 min w 30-minutowym szczycie miasta zamiast mediany z 7:00–9:00 (reguła z pracy, s. 14–15)"),
]
ALT = ("s5b", ("r_grid", "low", "w15", "all", "grid"), "Wariant: najszybsza podróż w całym oknie 7:00–9:00 (percentyl 1 R5) zamiast kroku 5")
MAIN = STEPS[-1][1]
SINGLE = [
    ("radii", ("r_prod", "med", "w60", "all", "grid"), "tylko promienie 8 / 12 km"),
    ("walk", ("r_grid", "med", "w15", "all", "our"), "tylko limit pieszy grid study"),
    ("fast", ("r_prod", "low", "w60", "all", "our"), "tylko najszybsza podróż 7–9"),
]


def f1(x, nd=1, sign=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    return s.replace(".", ",").replace("-", "−")


def size_class(pop: float):
    for c in CLASSES:
        if c[1] <= pop < c[2]:
            return c
    return None


def published() -> dict:
    d = json.loads((U.METRICS / "metrics_access_uc.json").read_text(encoding="utf-8"))["metrics"]
    return {(r["agglomeration"], r["metric"], r["population_grid"]): r["value"] for r in d}


def load(agg: str) -> dict | None:
    pk = json.loads((G.OUT / "peaks.json").read_text(encoding="utf-8"))[agg]["peak_start_s"]
    runs = {}
    for r in G.RUNS:
        if not G.run_done(agg, r, pk if r == "r_peak" else None):
            return None
        runs[r] = pd.read_parquet(G.run_path(agg, r))
    return runs


def value(agg: str, runs: dict, P: pd.DataFrame, key, c: int, gw: str = "census", how: str = "rom", sel=None):
    run, pc, rule, dom, rk = key
    df = runs[run]
    o = G.origins(agg)
    assert (df["cell_id"].to_numpy() == o["cell_id"].to_numpy()).all()
    w = o[f"w_{gw}"].to_numpy(np.float64)
    acc = df[f"acc_{pc}_{rule}_{gw}_{dom}_{rk}{c}"].to_numpy(np.float64)
    prox = P[f"prox_{gw}_{dom}_{rk}{c}"].to_numpy(np.float64)
    m = (w > 0) & (prox > 0) & np.isfinite(acc)
    if sel is not None:
        m &= sel
    if how == "rom":
        return float(100 * (w[m] * acc[m]).sum() / (w[m] * prox[m]).sum())
    return float(100 * (w[m] * acc[m] / prox[m]).sum() / w[m].sum())


def walk_share(agg: str, runs: dict, key, c: int) -> float:
    run, pc, rule, dom, rk = key
    df = runs[run]
    w = G.origins(agg)["w_census"].to_numpy(np.float64)
    a = df[f"acc_{pc}_{rule}_census_{dom}_{rk}{c}"].to_numpy(np.float64)
    wo = df[f"walkonly_{pc}_census_{dom}_{rk}{c}"].to_numpy(np.float64)
    return float(100 * (w * wo).sum() / (w * a).sum())


def in_uc2011(agg: str) -> np.ndarray | None:
    """Origins (EPSG:2180 centres) inside the GEOSTAT 2011 urban centre analysed by the grid study (4 cities)."""
    if agg not in EU_AGG or not (E.RAWDIR / f"uc_{EU_AGG[agg]}.geojson").exists():
        return None
    import shapely
    g, _ = E.uc_polygon(EU_AGG[agg])
    o = G.origins(agg)
    x, y = U.TO3035.transform(o["x"].to_numpy(), o["y"].to_numpy())
    return shapely.contains_xy(g, np.asarray(x), np.asarray(y))


def eu_values() -> pd.DataFrame:
    p = G.OUT / "eu_city_values.csv"
    v = E.city_values()
    if len(v):
        v.to_csv(p, index=False, lineterminator="\n", float_format="%.6g")
    return v.set_index("agglomeration") if len(v) else v


def main(aggs: list[str] | None = None) -> None:
    t0 = time.time()
    aggs = aggs or G.AGGS
    G.QA.mkdir(parents=True, exist_ok=True)
    pub = published()
    eu = eu_values()
    cent = pd.read_csv(U.QA / "urban_centres.csv")
    peaks = json.loads((G.OUT / "peaks.json").read_text(encoding="utf-8"))
    res, pending, dec_rows, rows = {}, [], [], []
    allsteps = STEPS + [ALT]
    for agg in aggs:
        runs = load(agg)
        if runs is None:
            pending.append(agg)
            continue
        P = G.proximity(agg)
        r = {"steps": {}, "single": {}, "mor": {}, "raw": {}, "rawmor": {}, "uc11": {}, "walk": {}}
        sel = in_uc2011(agg)
        for c in (30, 45):
            r["pub", c] = pub.get((agg, f"tp_pt_am_{c}min_ratio_of_means", "ghsl_census_scaled"))
            for sid, key, _ in allsteps:
                r["steps"][sid, c] = value(agg, runs, P, key, c)
                r["mor"][sid, c] = value(agg, runs, P, key, c, how="mor")
                r["raw"][sid, c] = value(agg, runs, P, key, c, gw="raw")
                r["rawmor"][sid, c] = value(agg, runs, P, key, c, gw="raw", how="mor")
                if sid in ("s5", "s5b"):
                    r["walk"][sid, c] = walk_share(agg, runs, key, c)
                    if sel is not None:
                        r["uc11"][sid, c] = value(agg, runs, P, key, c, sel=sel)
                        r["uc11"][sid + "_mor", c] = value(agg, runs, P, key, c, how="mor", sel=sel)
            for sid, key, _ in SINGLE:
                r["single"][sid, c] = value(agg, runs, P, key, c) - r["steps"]["s2", c]
        if sel is not None:
            r["uc11_share"] = float(G.origins(agg)["w_census"].to_numpy()[sel].sum() / G.origins(agg)["w_census"].sum())
        inc = cent[(cent.agglomeration == agg) & cent.included].sort_values("population_2021_official", ascending=False)
        r["main_pop"] = int(inc.population_2021_official.iloc[0])
        r["main_name"] = inc.main_lau.iloc[0]
        r["n_centres"] = len(inc)
        res[agg] = r
        for c in (30, 45):
            dec_rows.append({"agglomeration": agg, "cutoff_min": c, "step": "s0", "value": r["pub", c], "change": None,
                             "label": "opublikowany wynik urban centre (metrics_access_uc, stosunek średnich)"})
            pv = r["pub", c]
            for sid, _, lab in STEPS:
                v = r["steps"][sid, c]
                dec_rows.append({"agglomeration": agg, "cutoff_min": c, "step": sid, "value": v, "change": v - pv, "label": lab})
                pv = v
            v = r["mor"]["s5", c]
            dec_rows.append({"agglomeration": agg, "cutoff_min": c, "step": "s6", "value": v, "change": v - pv,
                             "label": "agregacja jak DG REGIO: średnia wyników komórek ważona ludnością"})
            v = r["steps"]["s5b", c]
            dec_rows.append({"agglomeration": agg, "cutoff_min": c, "step": "s5b", "value": v, "change": v - r["steps"]["s4", c], "label": ALT[2]})
        # metric rows (comparison only)
        for grid, gw in GRIDS.items():
            for c in (30, 45):
                rad = 8 if c == 30 else 12
                base = (f"Transport performance KZ + pieszo, {c} min, wariant porównawczy z grid study DG REGIO: osiągalni w promieniu {rad} km / "
                        f"mieszkający w promieniu {rad} km × 100, cele także poza centrum, pieszo do 15 min / 1,2 km")
                for sid, mid, lab in (("s5", f"tp_gridstudy_pt_{c}min", base + f", najkrótszy z 6 odjazdów co 5 min w szczycie od {peaks[agg]['peak_start']}"),
                                      ("s5b", f"tp_gridstudy_fastest2h_pt_{c}min", base + ", najszybsza podróż w oknie 7:00–9:00")):
                    key = dict((s[0], s[1]) for s in allsteps)[sid]
                    rows.append(row(agg, mid, lab + " (średnia wyników komórek ważona ludnością, jak DG REGIO)", value(agg, runs, P, key, c, gw=gw, how="mor"), grid))
                    rows.append(row(agg, mid + "_ratio_of_means", lab + " (stosunek średnich ważonych)", value(agg, runs, P, key, c, gw=gw), grid))
        if agg in getattr(eu, "index", []):
            e = eu.loc[agg]
            for c in (30, 45):
                for how, suf, hl in (("mean_of_ratios", "", "średnia wyników komórek ważona ludnością, jak w pracy"),
                                     ("ratio_of_means", "_ratio_of_means", "stosunek średnich ważonych")):
                    rows.append({"agglomeration": agg, "domain": DOMAIN, "metric": f"tp_gridstudy_dgregio_{c}min{suf}",
                                 "label": f"Wartość DG REGIO (grid study, {c} min, promień {8 if c == 30 else 12} km) dla centrum {e['name']} (GEOSTAT 2011), "
                                          f"odtworzona z komórek 200 m przeglądarki DG REGIO ({hl})",
                                 "value": sig(float(e[f"{how}_{c}"])), "unit": "%", "grid": "JRC-GEOSTAT 2018, 200 m (EPSG:3035)",
                                 "source": "DG REGIO, Poelman i Ackermans, przeglądarka city_acc_grid (ArcGIS REST PublicTransport/city_acc_grid)",
                                 "population_date": "2018", "timetable_date": None, "coverage_share": None,
                                 "flag": "rozkłady 2019–2021 (data dla miasta niepodana); centrum GEOSTAT 2011, nie 2021", "tier": "table",
                                 "feed_variant": None, "population_grid": None})
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["population_grid"] or "", m["metric"]))
    write_json(G.METRICS / "metrics_access_gridstudy.json", {"generated_for_timetable_date": G.REF_DAY, "metrics": rows,
                                                            "status": [{"agglomeration": a, "state": "pending" if a in pending else "done"} for a in aggs]})
    with open(G.METRICS / "metrics_access_gridstudy.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})
    pd.DataFrame(dec_rows).to_csv(G.QA / "decomposition.csv", index=False, lineterminator="\n", float_format="%.4g")
    final = final_table(res, eu)
    final.to_csv(G.QA / "final.csv", index=False, lineterminator="\n", float_format="%.4g")
    runlog = [l[20:] for l in (G.OUT / "run.log").read_text(encoding="utf-8").splitlines()
              if "origins x" in l and "limit" not in l] if (G.OUT / "run.log").exists() else []
    write_md(res, eu, pending, runlog, peaks)
    extra = {"code_version": G.CODE_VERSION, "timetable_date": G.REF_DAY, "rows": len(rows), "pending": pending,
             "p_low": G.P_LOW, "peaks": {a: peaks[a]["peak_start"] for a in peaks}, "routing_log": runlog,
             "dgregio_source": {"pdf": E.PDF_URL, "viewer": E.VIEWER, "service": E.SERVICE}}
    write_meta(G.QA, "access_gridstudy", started=t0, extra={**extra, "outputs": sorted(p.name for p in G.QA.iterdir() if p.name != "_meta.json")})
    tmp = Path(tempfile.mkdtemp())
    write_meta(tmp, "access_gridstudy", started=t0, extra={**extra, "outputs": ["metrics_access_gridstudy.csv", "metrics_access_gridstudy.json"]})
    shutil.copyfile(tmp / "_meta.json", G.METRICS / "_meta_access_gridstudy.json")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"access_gridstudy: {len(rows)} rows; pending {pending}; {time.time() - t0:.0f} s")


def row(agg, metric, label, v, grid):
    return {"agglomeration": agg, "domain": DOMAIN, "metric": metric, "label": label, "value": sig(v), "unit": "%",
            "grid": GRID_LABEL[grid], "source": source("all", grid) + "; centra miejskie: Eurostat GISCO HDENS_CLST_2021",
            "population_date": POP_DATE[grid], "timetable_date": G.REF_DAY, "coverage_share": None,
            "flag": "wariant tylko do porównań z grid study DG REGIO; nie zastępuje wyniku głównego", "tier": "table",
            "feed_variant": "all", "population_grid": grid}


def final_table(res: dict, eu) -> pd.DataFrame:
    out = []
    for agg, r in res.items():
        cl = size_class(r["main_pop"])
        for c in (30, 45):
            k = 0 if c == 30 else 1
            e = eu.loc[agg] if agg in getattr(eu, "index", []) else None
            out.append({"agglomeration": agg, "cutoff_min": c, "published_uc_ratio_of_means": r["pub", c],
                        "gridstudy_mean_of_ratios": r["mor"]["s5", c], "gridstudy_ratio_of_means": r["steps"]["s5", c],
                        "gridstudy_uc2011_mean_of_ratios": r["uc11"].get(("s5_mor", c)), "gridstudy_uc2011_ratio_of_means": r["uc11"].get(("s5", c)),
                        "fastest2h_mean_of_ratios": r["mor"]["s5b", c], "fastest2h_ratio_of_means": r["steps"]["s5b", c],
                        "dgregio_own_mean_of_ratios": None if e is None else float(e[f"mean_of_ratios_{c}"]),
                        "dgregio_own_ratio_of_means": None if e is None else float(e[f"ratio_of_means_{c}"]),
                        "main_centre_pop_2021": r["main_pop"], "size_class": cl[0], "class_min": cl[4 + k][0],
                        "class_mean": cl[4 + k][1], "class_max": cl[4 + k][2], "all_197_mean": ALL[k][1]})
    return pd.DataFrame(out)


def write_md(res: dict, eu, pending: list, runlog: list, peaks: dict) -> None:
    L = []
    A = L.append
    present = [a for a in G.AGGS if a in res]
    A("# Wariant porównawczy z grid study DG REGIO (Poelman i Ackermans)")
    A("")
    A("Plik generuje `python -m pipeline.access_gridstudy report` (krok poboczny, tylko do porównań; wynik główny bez zmian). "
      "Liczby: `results/metrics/metrics_access_gridstudy.csv/json`, `decomposition.csv`, `final.csv`. Kod: `pipeline/access_gridstudy.py`, "
      "`access_gridstudy_report.py`, `access_gridstudy_eu.py`. Źródło: H. Poelman, L. Ackermans, „Assessing the performance of urban public transport "
      "using population grid data”, DG REGIO, PDF z ec.europa.eu (nagłówek Last-Modified 2023-02-08; w tekście daty brak), zapisany w `data/raw/dgregio_gridstudy/`.")
    A("")
    A("## 1. Odpowiedź w skrócie")
    A("")
    A(VERDICT)
    A("")
    A("## 2. Metoda grid study ustalona ze źródła")
    A("")
    A("Strony wg numeracji drukowanej PDF (16 stron).")
    A("")
    A(md(pd.DataFrame(METHOD, columns=["Element", "Grid study", "Strona"])))
    A("")
    A("**Różnice wobec opisu w zleceniu i w przeglądzie literatury.** Cele i mianownik *nie* są ograniczone do urban centre (ograniczone są tylko starty); "
      "osiągalni liczą się tylko w promieniu 8 / 12 km; okno to 30 minut (6 odjazdów co 5 min), a nie dwie godziny; limit 15 min dotyczy łącznego spaceru w podróży, "
      "nie każdego odcinka. Wynik miasta to średnia **wyników komórek** ważona ludnością, nie stosunek średnich: tekst (s. 15) mówi o „średnich ważonych … performance”, "
      "a odtworzona z komórek średnia wyników dla Warszawy (§3) równa się co do 0,1 pkt maksimum klasy 1–2,5 mln z tabeli 1 przy obu progach (47,1 i 71,1), "
      "czego stosunek średnich nie daje. Dlatego wartość porównawcza jest tu liczona tak samo (krok 6).")
    A("")
    A("## 3. Wartości grid study dla polskich centrów")
    A("")
    A("W pracy polskie wartości są tylko na mapach 1–2 i wykresach 5–10 (bez liczb w tekście, bez aneksu). Opisana w pracy przeglądarka (przyp. 7) jest pod starym adresem niedostępna (404), "
      "ale działa pod `" + E.VIEWER + "`. Jej warstwy to publiczna usługa ArcGIS REST `" + E.SERVICE + "`; zapytanie `identify` zwraca dokładną wartość komórki 200 m każdej warstwy "
      "(performance, dostępność, proximity, udział spaceru, ludność 2018). Zapytano o środek każdej komórki 200 m w czterech polskich centrach z listy przeglądarki "
      "(Warszawa, Kraków, Poznań, Łódź; Wrocławia, Gdańska, Gdyni i GZM w analizie nie ma) i policzono wartości miast z komórek. Bez logowania i bez obchodzenia zabezpieczeń; "
      "kopie odpowiedzi: `data/raw/dgregio_gridstudy/cells/`.")
    A("")
    if len(eu):
        t = []
        for agg, e in eu.iterrows():
            cl = size_class(float(e["pop2011_uc"]))
            t.append({"Centrum (GEOSTAT 2011)": e["name"], "Pow. km²": f"{e['area_km2']:.0f}", "Klasa (ludność 2011)": cl[0],
                      "Komórek 200 m (zapytano / z wartością)": f"{e['cells_fetched']} / {e['cells_with_value_30']}",
                      "Ludność 2018 w komórkach": f"{e['pop2018_cells']:,.0f}".replace(",", " "),
                      "KZ 30: średnia komórek (jak w pracy)": f1(e["mean_of_ratios_30"]), "KZ 30: stosunek średnich": f1(e["ratio_of_means_30"]),
                      "KZ 45: średnia komórek (jak w pracy)": f1(e["mean_of_ratios_45"]), "KZ 45: stosunek średnich": f1(e["ratio_of_means_45"]),
                      "Udział spaceru 30 / 45 (%)": f"{f1(e['walk_share_30'])} / {f1(e['walk_share_45'])}",
                      "Kontrola: max |dost./prox.×100 − perf.|": f"{max(e['max_abs_perf_check_30'], e['max_abs_perf_check_45']):.4f}"})
        A(md(pd.DataFrame(t)))
        A("")
        A("Kontrola spójności: w każdej komórce performance = dostępność / proximity × 100 (ostatnia kolumna), więc warstwy odczytano poprawnie. "
          "Komórki bez ludności zwracają brak wartości i nie wchodzą do średnich. Udział spaceru: część osiągalnej ludności dostępna samym spacerem (≤ 15 min).")
    else:
        A("Odczyt komórek niedokończony.")
    A("")
    A("## 4. Nasz wariant")
    A("")
    A("- **Starty:** zaludnione komórki 250 m centrów miejskich Eurostatu 2021 w FUA (domena `access_uc`, te same komórki i wagi). Gdzie centrów jest kilka, liczone są razem; grid study liczy każde osobno. "
      "Wariant ze startami tylko w centrum 2011 analizowanym przez DG REGIO: §6.")
    A("- **Cele i mianownik:** wszystkie zaludnione komórki 250 m w promieniu 8 / 12 km od startu, także poza centrum (siatka spisowa NSP 2021; surowy GHSL jako wariant). Własna komórka wliczona.")
    A("- **Routing:** R5 v7.5.1 na kopiach sieci produkcyjnych „wszystkie feedy”, środa " + G.REF_DAY + ". Trzy przebiegi na tych samych startach i celach: "
      "`r_prod` (pieszo 5 km/h, dojście i odejście ≤ 12 min, okno 7:00–9:00 co minutę, percentyle 1 i 50), "
      "`r_grid` (pieszo 4,8 km/h, dojście i odejście ≤ 15 min każde, to samo okno i percentyle), "
      "`r_peak` (jak `r_grid`, ale 6 pojedynczych odjazdów co 5 min w 30-minutowym szczycie miasta, minimum z 6). Promienie, domena celów i reguła spaceru zmieniane są przy zliczaniu, więc wszystkie kroki dotyczą tych samych wyszukiwań.")
    A("- **Szczyt 30-minutowy** (reguła z s. 14–15: początek godziny z największą liczbą odjazdów na przystankach centrum, start co pół godziny, 5:00–11:00; z naszych feedów 2026): "
      + "; ".join(f"{NAMES[a]} od {peaks[a]['peak_start']}" for a in G.AGGS if a in peaks) + ".")
    A("- **„Najszybsza” w oknie 2 h (wariant):** R5 nie przyjmuje percentyla 0; percentyl 1 ze 120 minut okna jest średnio o 0,52 min wolniejszy od minimum ze 120 pojedynczych odjazdów "
      "(równy w 48 % par, różnica najwyżej 1 min; jeden start w Poznaniu, ok. 3 900 celów; `python -m pipeline.access_gridstudy check`).")
    A("- **Spacer:** sam spacer z produkcyjnej pamięci spacerów (5 km/h) przeliczony na 4,8 km/h i dopuszczony do 15 min (1,2 km); w wariancie produkcyjnym do 60 min.")
    A("- **Kontrola odtworzenia:** przebieg `r_prod` (mediana, cele tylko w centrum) daje w próbie 100 startów w Poznaniu te same sumy osiągalnych na komórkę co opublikowany przebieg `access_uc` "
      "(45 min identycznie, 30 min różnica 0,007 % z jednej komórki).")
    A("")
    A("## 5. Dekompozycja: od opublikowanego wyniku urban centre do reguł grid study")
    A("")
    A("Siatka spisowa. Kroki 0–5 to stosunek średnich (jak wynik opublikowany), krok 6 zmienia tylko agregację na średnią wyników komórek (jak DG REGIO). "
      "Każdy krok zmienia jedną rzecz względem poprzedniego; w nawiasie zmiana w pkt.")
    A("")
    heads = {"s1": "1. Osiągalni tylko w promieniu", "s2": "2. Cele i mianownik poza UC", "s3": "3. Promienie 8/12 km",
             "s4": "4. Pieszo 15 min / 1,2 km", "s5": "5. Min z 6 odjazdów w szczycie 30 min"}
    for c in (30, 45):
        A(f"**KZ {c} min**")
        A("")
        t = []
        for agg in present:
            r = res[agg]
            d = {"Aglomeracja": NAMES[agg], "0. Opublikowany (UC)": f1(r["pub", c])}
            pv = r["pub", c]
            for sid, _, _ in STEPS:
                v = r["steps"][sid, c]
                d[heads[sid]] = f"{f1(v)} ({f1(v - pv, sign=True)})"
                pv = v
            v = r["mor"]["s5", c]
            d["6. Średnia wyników komórek"] = f"**{f1(v)}** ({f1(v - pv, sign=True)})"
            d["Wariant: najszybsza 7–9 zamiast kroku 5"] = f"{f1(r['steps']['s5b', c])} ({f1(r['steps']['s5b', c] - r['steps']['s4', c], sign=True)}); średnia komórek {f1(r['mor']['s5b', c])}"
            t.append(d)
        A(md(pd.DataFrame(t)))
        A("")
    A("Opis kroków:")
    A("")
    for sid, _, lab in STEPS:
        A(f"- {sid[1]}. {lab}.")
    A("- 6. Agregacja jak DG REGIO: średnia wyników komórek ważona ludnością zamiast stosunku średnich.")
    A(f"- {ALT[2]}.")
    A("")
    A("**Efekty pojedyncze** (każda zmiana osobno od kroku 2, te same starty, stosunek średnich; pkt). Suma efektów pojedynczych nie musi równać się łańcuchowi, bo efekty zależą od siebie (np. najszybsza podróż zyskuje więcej przy dłuższym dojściu).")
    A("")
    t = []
    for agg in present:
        r = res[agg]
        d = {"Aglomeracja": NAMES[agg]}
        for c in (30, 45):
            for sid, _, lab in SINGLE:
                d[f"KZ {c}: {lab}"] = f1(r["single"][sid, c], sign=True)
        t.append(d)
    A(md(pd.DataFrame(t)))
    A("")
    A("## 6. Wynik końcowy obok grid study")
    A("")
    A("Wartość porównawcza = krok 6 (reguły grid study, średnia wyników komórek). Klasa wielkości wg ludności największego centrum aglomeracji (Eurostat 2021), bo grid study liczy każde centrum osobno. "
      "Średnie klas i zakres min–max: tabela 1 pracy (s. 3), średnie ważone ludnością centrów; wszystkie 197 centrów: 36,2 (30 min) i 53,9 (45 min).")
    A("")
    for c in (30, 45):
        A(f"**KZ {c} min** (średnia wyników komórek; w nawiasie stosunek średnich)")
        A("")
        t = []
        for agg in present:
            r = res[agg]
            k = 0 if c == 30 else 1
            cl = size_class(r["main_pop"])
            e = eu.loc[agg] if agg in getattr(eu, "index", []) else None
            t.append({"Aglomeracja": NAMES[agg], "Opublikowany UC (stosunek średnich)": f1(r["pub", c]),
                      "Reguły grid study": f"**{f1(r['mor']['s5', c])}** ({f1(r['steps']['s5', c])})",
                      "To samo, starty tylko w centrum 2011": "–" if ("s5", c) not in r["uc11"] else f"{f1(r['uc11']['s5_mor', c])} ({f1(r['uc11']['s5', c])})",
                      "DG REGIO dla tego centrum": "brak w analizie" if e is None else f"**{f1(e[f'mean_of_ratios_{c}'])}** ({f1(e[f'ratio_of_means_{c}'])})",
                      "Różnica my − DG (centrum 2011)": "–" if (e is None or ("s5", c) not in r["uc11"]) else f1(r["uc11"]["s5_mor", c] - float(e[f"mean_of_ratios_{c}"]), sign=True),
                      "Klasa (największe centrum)": f"{cl[0]} ({cl[3]} centrów)", "Średnia klasy (min–max)": f"{f1(cl[4 + k][1])} ({f1(cl[4 + k][0])}–{f1(cl[4 + k][2])})",
                      "My − średnia klasy": f1(r["mor"]["s5", c] - cl[4 + k][1], sign=True)})
        A(md(pd.DataFrame(t)))
        A("")
    A("## 7. Wrażliwość i kontrole")
    A("")
    t = []
    for agg in present:
        r = res[agg]
        e = eu.loc[agg] if agg in getattr(eu, "index", []) else None
        t.append({"Aglomeracja": NAMES[agg],
                  "Surowy GHSL, krok 6: KZ 30 / 45": f"{f1(r['rawmor']['s5', 30])} / {f1(r['rawmor']['s5', 45])}",
                  "Najszybsza 7–9, średnia komórek: KZ 30 / 45": f"{f1(r['mor']['s5b', 30])} / {f1(r['mor']['s5b', 45])}",
                  "Udział ludności startów w centrum 2011": "–" if "uc11_share" not in r else f1(100 * r["uc11_share"]) + " %",
                  "Udział spaceru w dostępności, krok 5: 30 / 45 (%)": f"{f1(r['walk']['s5', 30])} / {f1(r['walk']['s5', 45])}",
                  "Udział spaceru, DG REGIO (%)": "–" if e is None else f"{f1(e['walk_share_30'])} / {f1(e['walk_share_45'])}"})
    A(md(pd.DataFrame(t)))
    A("")
    A("Udział spaceru w grid study dla wszystkich 197 centrów: 9,1 % (8 km) i 3,9 % (12 km), s. 6. Udział spaceru liczony jako stosunek sum (osiągalni pieszo / osiągalni), ważony ludnością startu.")
    A("")
    A("## 8. Ograniczenia i nie zweryfikowano")
    A("")
    for x in LIMITS:
        A(f"- {x}")
    A("")
    A("## 9. Co uruchomiono")
    A("")
    A("- Odczyt komórek DG REGIO: `python -m pipeline.access_gridstudy_eu fetch` (16 300 zapytań `identify`, 3 naraz, ok. 1 h) i `summary`.")
    A("- `python -m pipeline.access_gridstudy peak`, `check` (Poznań), `route` (jedna JVM, 4 wątki, `-Xmx 8G`, równolegle z innymi krokami na tej maszynie): " + ("; ".join(runlog) if runlog else "brak") + ".")
    A("- Oczekuje: " + (", ".join(NAMES[a] for a in pending) if pending else "nic") + ".")
    A("")
    (G.QA / "gridstudy.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


METHOD = [
    ("Jednostka", "urban centre (klaster komórek 1 km² ≥ 1500 os./km², ≥ 50 tys.) na siatce **GEOSTAT 2011**; 197 z 683 centrów UE", "s. 2, przyp. 5; s. 3"),
    ("Starty", "środki zaludnionych komórek 200 × 200 m w urban centre", "s. 2"),
    ("Cele", "środki zaludnionych komórek 200 m w promieniu 12 km (8 km) od startu, **także poza urban centre**", "s. 2, s. 15"),
    ("Mianownik (proximity)", "cała ludność w promieniu 12 km (45 min) lub 8 km (30 min), 16 km/h w linii prostej, **bez przycięcia do urban centre**", "s. 2, s. 13"),
    ("Ludność", "JRC-GEOSTAT 2018, siatka 100 m zsumowana do 200 m (zgodnie z siatką 1 km)", "s. 2 przyp. 4, s. 13"),
    ("Własna komórka", "wliczona do dostępności i do proximity", "s. 15"),
    ("Router", "OpenTripPlanner Analyst (OTPA) 1.5; punkty dociągnięte do sieci OSM (≤ 1000 m)", "s. 14"),
    ("Okno i reguła czasu", "odjazdy **co 5 min w 30-minutowym szczycie porannym**; start okna = pół godziny rozpoczynające godzinę z największą liczbą odjazdów na przystankach centrum; "
     "z ≤ 6 czasów bierze się **najkrótszy** („best available trip … fastest connection”)", "s. 2–3, s. 14–15"),
    ("Spacer", "łącznie (dojście + przesiadki + odejście) ≤ 15 min; sam spacer ≤ 1,2 km (prędkość niepodana; z tych liczb 4,8 km/h)", "s. 2, s. 15"),
    ("Odległość", "kryterium 8 / 12 km w linii prostej między punktami (EPSG:3035)", "s. 15"),
    ("Rozkłady", "dzień roboczy poza wakacjami; zwykle okres 2019–2021; daty dla miast niepodane", "s. 2"),
    ("Wynik miasta", "średnie ważone ludnością komórki startu: dostępności, proximity i performance", "s. 15"),
    ("Średnie w tabeli 1", "ważone ludnością centrów; 30 min: 36,2 (wszystkie), 39,3 (500 tys.–1 mln), 35,8 (1–2,5 mln); 45 min: 53,9, 59,8, 59,5", "s. 3"),
    ("Polskie centra", "„some major cities in … Poland”; wg listy przeglądarki: Warszawa, Kraków, Poznań, Łódź", "s. 3; lista przeglądarki"),
]

LIMITS = [
    "R5 ogranicza osobno dojście i odejście (po 15 min), nie łączny spacer w podróży; grid study ogranicza łączny spacer do 15 min. Nasz wariant dopuszcza więc dłuższe łączne dojścia: zawyża wynik wobec reguły z pracy (wielkości nie zmierzono).",
    "„Najszybsza” to percentyl 1 R5, średnio o 0,52 min wolniejszy od prawdziwego minimum (pomiar na jednym starcie); zaniża wynik kroku 4 nieznacznie.",
    "Inny router (R5 zamiast OTPA 1.5), inna sieć OSM i inna siatka ludności (250 m NSP 2021 zamiast 200 m JRC 2018); rozkłady 2026 zamiast 2019–2021.",
    "Domena startów: centra Eurostatu 2021, w czterech aglomeracjach łączone (grid study: centra 2011, każde osobno). Wariant ze startami w centrum 2011 obejmuje tylko część wspólną z naszą domeną.",
    "Sposób agregacji w grid study (średnia wyników komórek czy stosunek średnich) nie jest jednoznaczny w tekście; dla czterech miast liczymy oba z komórek DG REGIO, ale nie da się sprawdzić, którą wartość zawiera tabela 1.",
    "Wartości DG REGIO dla polskich centrów odtworzono z komórek przeglądarki; zgodności z wartościami na mapach 1–2 (klasy) nie sprawdzano wzrokowo.",
    "Szczyt 30-minutowy wyznaczono z naszych feedów 2026 (stop_times na przystankach centrum 2021), nie z danych DG REGIO.",
    "Udział spaceru w dostępności jest u nas 2–3 razy mniejszy niż w komórkach DG REGIO (np. Poznań 2,9 wobec 7,2 % przy 30 min). Liczymy cel jako „pieszy”, gdy sam spacer jest nie wolniejszy od podróży z komunikacją; DG REGIO może liczyć inaczej (np. każdy cel w zasięgu 15 min pieszo) albo mieć gęstszą sieć pieszą. Nie wyjaśniono.",
    "Wrocław, Trójmiasto i GZM nie są w analizie DG REGIO: dla nich jest tylko porównanie ze średnią klasy. Trójmiasto i GZM to u nas sumy kilku centrów; klasa wg największego centrum (Gdańsk, Katowice).",
    "W Łodzi domena 2021 obejmuje drugie, mniejsze centrum; wynik dla całej domeny (38,3 przy 30 min) jest wyższy niż dla startów w centrum 2011 (35,9). Porównanie z DG REGIO używa tej drugiej wartości.",
    "Różnica Warszawy wobec DG REGIO (ok. −8 pkt) jest niewyjaśniona; ten sam znak i podobna wielkość przy obu progach wskazują na różnicę danych lub sieci, nie na regułę czasu.",
    "Nie zweryfikowano: daty rozkładów DG REGIO dla polskich miast; czy dla polskich miast użyto kolei (PKP, SKM, WKD, KM); czy OTPA wlicza początkowe oczekiwanie; wpływu łącznego limitu spaceru.",
]

VERDICT = (
    "**Według reguł grid study polskie miasta wypadają przy średnich swoich klas wielkości: przy 30 min na poziomie średniej, przy 45 min powyżej (poza GZM).** "
    "Wartości porównawcze (średnia wyników komórek, jak w pracy; §6): KZ 30 = 36,1–41,7 (średnie klas 35,8–41,8; różnice od −3,2 w Poznaniu do +2,7 w Warszawie), "
    "KZ 45 = 61,6–67,0 w sześciu miastach (2,1–6,4 pkt powyżej średnich klas 59,5–63,3) i 53,8 w GZM (5,7 pkt poniżej średniej klasy 1–2,5 mln, w dolnej połowie jej zakresu 37,4–71,1). "
    "Odstęp od średnich klas, który przegląd literatury widział przy 30 min (rdzenie 24–34 wobec 35,8–39,3), wynikał więc z metody, a nie z gorszej komunikacji.\n\n"
    "**Wobec wartości DG REGIO dla tych samych centrów** (odtworzonych z komórek ich przeglądarki; §3), przy startach ograniczonych do centrum 2011: "
    "przy 45 min Kraków, Poznań i Łódź są w granicach 1,8–3,0 pkt powyżej DG REGIO, przy 30 min 2,2–3,9 pkt poniżej; Warszawa jest poniżej o ok. 8 pkt przy obu progach "
    "(DG REGIO: 47,1 i 71,1, maksimum klasy 1–2,5 mln). Czy przyczyną są rozkłady 2019–2021 (np. kolej), łączny limit spaceru, sieć piesza OTP czy sposób liczenia oczekiwania w OTPA, nie ustalono. "
    "Wariant „najszybsza podróż w całym oknie 7:00–9:00” (bez oczekiwania na start) przekracza wartości DG REGIO przy 45 min o 7–9 pkt w trzech miastach (cała domena), więc DG REGIO nie liczy go w ten sposób; "
    "reguła z pracy (najkrótszy z 6 odjazdów w 30-minutowym szczycie) pasuje lepiej.\n\n"
    "**Co zmienia wynik (dekompozycja, §5):** cele i mianownik poza centrum obniżają wynik o 1,6–3,6 pkt (30 min) i 3,8–10,8 pkt (45 min); promienie 8 / 12 km o 1,8–3,3 i 2,1–4,1; "
    "limit pieszy 15 min / 1,2 km o 0,9–1,4 i 0,2–1,1; najkrótszy z 6 odjazdów w szczycie zamiast mediany z dwóch godzin podnosi o 8,5–13,3 i 10,2–18,3 pkt (największy pojedynczy efekt, najsilniejszy w GZM); "
    "średnia wyników komórek zamiast stosunku średnich zmienia wynik o −2,9 do +2,5 pkt. Sama „najszybsza podróż” nie jest więc jedyną różnicą: kroki domeny i promieni działają w przeciwną stronę.\n\n"
    "Wniosek praktyczny: to wariant tylko do porównań z UE. Wynik główny (mediana, 7:00–9:00, stosunek średnich) zostaje bez zmian; różnice między polskimi miastami a średnimi UE w tym wariancie "
    "są tego samego rzędu co niepewność odtworzenia (Warszawa −8 pkt wobec DG REGIO przy tej samej metodzie), więc nie należy ich czytać jako rankingu."
)


if __name__ == "__main__":
    main()
