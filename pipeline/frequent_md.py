"""frequent.md (Polish) for pipeline.frequent: definitions as implemented, tables, checks, limits.

Narrative paragraphs that interpret numbers live in NARRATIVE (written after looking at the results; the
tables next to them are regenerated on every run).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline import frequent as F
from pipeline.common import INTERIM
from pipeline.frequent_qa import NAMES, f1, md_table

from pipeline.frequent_text import NARRATIVE  # noqa: E402  (Polish text, written after looking at the results)


def _eff_pivot(eff: pd.DataFrame, dom: str, T: int) -> pd.DataFrame:
    e = eff[(eff.domain == dom) & (eff.T_min == T)]
    p = e.pivot(index="agglomeration", columns="comparison", values="delta_pp")
    base = e.groupby("agglomeration").recommended_pct.first()
    order = ["siatka: GHSL surowy", "feedy: oficjalne (ta sama domena)", "feedy: oficjalne (własna maska)",
             "agregacja (i): wszystkie linie", "agregacja: jedna linia", "bez wymogu dwóch kierunków",
             "bez reguły partnera", "odległość euklidesowa", "komórka = środek"]
    out = pd.DataFrame({"aglomeracja": [NAMES[a] for a in F.AGGS], "wariant zalecany %": [f1(base[a]) for a in F.AGGS]})
    for c in order:
        out[c] = [("+" if p.at[a, c] > 0 else "") + f1(p.at[a, c]) for a in F.AGGS]
    return out


def _fmt(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(f1)
    return d


def write_md(results, t, sizes) -> None:
    pq = json.loads((INTERIM / "popgrid" / "qa.json").read_text(encoding="utf-8"))
    ws = json.loads((INTERIM / "walk" / "extract_stats.json").read_text(encoding="utf-8"))
    v, g = F.REC["feed_variant"], F.REC["population_grid"]
    L = []
    A = L.append
    A("# Ludność przy częstej komunikacji (faza 2, brief §4.5)\n")
    A(f"Krok `python -m pipeline.frequent` (wywołuje też `pipeline.frequent_qa` i `pipeline.frequent_md`); wejścia: "
      f"`pipeline.popgrid`, `pipeline.walk_network`, `pipeline.gtfs_service`, `pipeline.stop_coverage`. "
      f"**Rozkłady: środa {F.DAY}** (dzień referencyjny z `config.yaml`); **OSM: 2026-11-22**; **ludność: NSP 2021 "
      "(31.03.2021) na siatce 1 km, rozłożona wzorem GHSL 2020** (wariant zalecany) albo surowy GHSL 2020. "
      "Siedem aglomeracji fazy 1, FUA i rdzeń. Dane i liczby: `results/metrics/metrics_frequent.csv`, "
      "`results/charts/frequent_curve.json`, `frequent_rail.json`; warstwy: `results/layers/`; szkice: "
      "`results/qa/transit/frequent/`.\n")
    A("## W skrócie\n")
    A(NARRATIVE["summary"])
    A("\n**Krzywa w konfiguracji zalecanej** (odsetek ludności ≤ 500 m pieszo od zespołu przystanków ze średnim "
      "odstępem ≤ T min w obu kierunkach, 06:00–20:00, wariant (ii) „odcinek”, wszystkie feedy, siatka "
      "przeskalowana do NSP 2021). „Pokrycie” = udział ludności domeny w masce pokrycia GTFS; „niepełne” = pokrycie "
      "< 85 % (wynik zaniżony, nie do porównań).\n")
    A(md_table(_fmt(t["headline"])))
    A("\n![Krzywe i histogramy odstępów](frequent/headway_histograms.png)\n")

    # ---------------------------------------------------------------- definitions
    A("## 1. Definicje w postaci zaimplementowanej\n")
    A("### 1.1 Siatka ludności (`pipeline.popgrid`)\n")
    A(NARRATIVE["popgrid"].format(
        removed=f1(pq["persons_removed_census_zero"] / 1e3, 0), cells0=pq["cells_census_zero_ghsl_positive"],
        fb_b=pq["fallback_built_cells"], fb_bp=int(pq["fallback_built_persons"]), fb_u=pq["fallback_uniform_cells"],
        fb_up=int(pq["fallback_uniform_persons"]), c1=f"{pq['check1_max_abs_cell_error']:.1e}",
        mis=f1(100 * pq["check2_250m_vs_census"]["share_population_misplaced_across_census_edges"]),
        misraw=f1(100 * pq["check2_raw_for_comparison"]["share_population_misplaced_raw_vs_census"]),
        mre=f1(100 * pq["check2_250m_vs_census"]["mean_abs_rel_err_cells_ge_500"]),
        p95=f1(100 * pq["check2_250m_vs_census"]["p95_abs_rel_err_cells_ge_500"]),
        q05=f1(pq["factor_quantiles_populated"]["0.05"], 2), q50=f1(pq["factor_quantiles_populated"]["0.5"], 2),
        q95=f1(pq["factor_quantiles_populated"]["0.95"], 2)))
    rows = []
    for a in F.AGGS:
        for dom in ("fua", "core"):
            x = pq["check3_totals"][a][dom]
            rows.append({"aglomeracja": NAMES[a], "domena": F.DOM_LABEL[dom],
                         "NSP (środki komórek 1 km)": f"{x['census_centroid_rule']:,.0f}".replace(",", " "),
                         "NSP (ważone polem)": f"{x['census_area_weighted']:,.0f}".replace(",", " "),
                         "przeskalowana 250 m": f"{x['scaled_250m']:,.0f}".replace(",", " "),
                         "różnica vs NSP ważone %": f1(100 * x["scaled_vs_census_aw"], 2),
                         "surowy GHSL vs NSP %": f1(100 * x["raw_vs_census_aw"], 1)})
    A(md_table(pd.DataFrame(rows)))
    A("\n![Siatka surowa i przeskalowana](frequent/popgrid_windows.png)\n")

    A("### 1.2 Sieć piesza (`pipeline.walk_network`)\n")
    A(NARRATIVE["walk"])
    rows = []
    for a in F.AGGS:
        s = ws[a]
        rows.append({"aglomeracja": NAMES[a], "km sieci": f"{s['km_total']:,.0f}".replace(",", " "),
                     "w tym chodniki/ścieżki (footway+path+steps+pedestrian) km":
                         f"{sum(s['km_by_class'].get(k, 0) for k in ('footway', 'path', 'steps', 'pedestrian')):,.0f}".replace(",", " "),
                     "węzły": f"{s['nodes']:,}".replace(",", " "), "składowe": s["components"],
                     "największa składowa % km": f1(100 * s["largest_component_share_km"]),
                     "km w małych składowych (< 2 km, bez dociągania)": f1(s["km_in_small_components"], 0)})
    A(md_table(pd.DataFrame(rows)))
    A("\nDociąganie przystanków i punktów próbkowych:\n")
    A(md_table(t["snap"]))
    A("")
    A(NARRATIVE["cellrep"])

    A("### 1.3 Zespoły przystanków, odjazdy, kierunki, odstęp (`pipeline.frequent`)\n")
    A(NARRATIVE["defs"])
    A("\nStatus kierunkowy zespołów (two_way: oba kierunki na miejscu; paired: drugi kierunek u partnera ≤ 300 m; "
      "terminal: pętla / początek kursów; one_way: jeden kierunek bez partnera, odpada z miary „oba kierunki”), "
      "oraz kontrola dubli (ta sama linia, ten sam następny zespół, ta sama minuta odjazdu):\n")
    A(md_table(t["dirs"]))
    A("")
    A("### 1.4 Maska pokrycia GTFS (§6)\n")
    A(NARRATIVE["mask"])
    m = t["mask"]
    A(md_table(_fmt(m)))
    A("")
    A("### 1.5 Wariant w stylu kodu ITDP\n")
    A(NARRATIVE["itdp_def"])
    A("### 1.6 Wariant kolejowy i „tylko szynowe”\n")
    A(NARRATIVE["rail_def"])

    # ---------------------------------------------------------------- results
    A("## 2. Wpływ każdego wyboru\n")
    A(NARRATIVE["effects"])
    for dom, T in (("covered", 10), ("covered", 30), ("core", 10)):
        A(f"\n**Domena: {F.DOM_LABEL[dom]}, próg ≤ {T} min.** Różnica wariantu względem zalecanego, pkt proc. "
          "(pełna tabela dla wszystkich progów i domen: `frequent/effects.csv`).\n")
        A(md_table(_eff_pivot(t["effects"], dom, T)))
    A("\n### 2.1 Nasza definicja vs replika ITDP vs odległość w linii prostej (≤ 10 min)\n")
    A(md_table(t["itdp"]))
    A("")
    A(NARRATIVE["itdp_res"])

    A("## 3. Wariant kolejowy (klasy wzorowane na DG REGIO)\n")
    A(NARRATIVE["rail_res"])
    A(md_table(t["rail"]))
    A("")

    # ---------------------------------------------------------------- checks
    A("## 4. Kontrole\n")
    A("### 4.1 Znane miejsca\n")
    A(md_table(t["sanity"].fillna("brak danych")))
    A("")
    A(NARRATIVE["sanity"])
    A("### 4.2 Dziesięć zespołów o największej liczbie odjazdów (brief §7.3)\n")
    tc = t["top"].copy()
    show = tc.groupby("agglomeration").head(5)
    show = pd.DataFrame({"aglomeracja": [NAMES[a] for a in show.agglomeration], "zespół": show.name,
                         "słupki": show.n_stops, "odjazdy 06–20": show.departures_06_20,
                         "odj./h": [f1(x) for x in show.departures_per_h], "(i) min": [f1(x) for x in show.h_all_min],
                         "(ii) min": [f1(x) for x in show.h_seg_min], "linia min": [f1(x) for x in show.h_line_min],
                         "dubel %": [f1(100 * x) for x in show.same_minute_dup_share], "tryby": show.modes})
    A("Pięć pierwszych na aglomerację (pełna lista 10: `frequent/top10_clusters.csv`).\n")
    A(md_table(show))
    A("")
    A(NARRATIVE["top"])
    A("### 4.3 Mapy kontrolne\n")
    A(" ".join(f"[{NAMES[a]}](frequent/map_{a}.png)" for a in F.AGGS) + "\n")
    A(NARRATIVE["maps"])
    A("### 4.4 Powtarzalność\n")
    A(NARRATIVE["determinism"])

    A("## 5. Co zaskoczyło i co wyszło przy sprawdzeniu\n")
    A(NARRATIVE["surprises"])
    A("## 6. Ograniczenia\n")
    A(NARRATIVE["limits"])
    A("## 7. Propozycje do `config.yaml`\n")
    A(NARRATIVE["config"])
    A("## 8. Pliki i polecenia\n")
    A(NARRATIVE["files"].format(sizes=", ".join(f"`{k}` {f1(v_, 1)} MB" for k, v_ in sizes.items())))
    F.QA_MD.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


