"""QA of the accessibility step: results/qa/access/access.md (Polish), PNG maps and curves, check tables, _meta.

Called by pipeline.access_aggregate.main (python -m pipeline.access aggregate).  Every table is computed from the
finished units; units still running are listed as pending.  The hand-written observations (OBSERVATIONS) are dated
and refer to the run they were written for.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from pipeline import access_inputs as AI
from pipeline.access import AGGS_BY_SIZE, CFG, CHUNK, SCENARIOS, est_s_per_origin, unit_dir
from pipeline.access_aggregate import (CHARTS, DGREGIO, LAYERS, METHOD_DIFFS, METRICS, QA, dependence_cells,
                                       dependence_ratio_of_sums, domains, perf_cells, ratio_of_means, wmean)
from pipeline.boundaries import load_agglomeration
from pipeline.common import RESULTS, sig, write_meta

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

NAMES = {a: CFG["agglomerations"][a]["name"] for a in AGGS_BY_SIZE}
BINS = [0, 10, 20, 30, 40, 50, 60, 80, 100, 1e9]
COLS = ["#f7f4f9", "#e7e1ef", "#d4b9da", "#c994c7", "#df65b0", "#e7298a", "#ce1256", "#980043", "#67001f"]

# Observations written after the full run (2026-11-24, 98/98 units).  Hand-written: re-read after any re-run.
OBSERVATIONS = """\
Stan na 2026-11-24, po pełnym przebiegu (98 z 98 jednostek, 11 h 20 min routingu). Liczby dotyczą rdzeni miast, wszystkich feedów i siatki spisowej, o ile nie napisano inaczej.

- **GZM wyraźnie najniżej.** KZ 45 min: 36,1 wobec 51–59 w pozostałych miastach. Sprawdzono z wynikami fazy 2: GZM ma też najmniejszy udział mieszkańców rdzenia przy kursach co 10 min lub częściej (45,6 % wobec 59–80 %) i najbardziej rozproszoną ludność. W granicach urban centre (ta sama reguła obszaru dla każdego miasta, `qa/access_uc/access_uc.md`) GZM pozostaje ostatnie: 43,2 wobec 62–67 (stosunek średnich). Wynik zostaje.
- **Wrocław: wieczór lepszy niż szczyt poranny przy 45 min** (54,7 wobec 53,0); to jedyne takie miasto. Sprawdzono z rozkładami: rozkładowa prędkość komunikacyjna tramwajów we Wrocławiu to 16,1 km/h w szczytach i 18,0 km/h po 20:00, największa różnica z siedmiu miast (w pozostałych 0,1–1,3 km/h). Wynik zostaje.
- **Duże spadki poza szczytem.** Trójmiasto wieczorem przy 45 min: 55,4 → 46,3 (−9,1 pkt); GZM wieczorem −6,4 i w sobotę −7,3 pkt. W pozostałych miastach okna różnią się od szczytu porannego o najwyżej 6 pkt; sobota jest wszędzie najsłabsza albo druga od końca. Przyczyn spadków w Trójmieście i GZM nie sprawdzano.
- **Siatka ludności zmienia wynik bardziej niż oczekiwano.** Surowy GHSL obniża wynik rdzenia o 3–7 pkt w Krakowie, Poznaniu i Łodzi (Poznań, 45 min: 54,6 → 47,9; Łódź: 51,3 → 46,3; Kraków, 30 min: 31,6 → 28,0), a w Warszawie i Wrocławiu prawie go nie zmienia (do 0,8 pkt). To więcej niż różnice między miastami ze środka tabeli, więc ich kolejność zależy od wyboru siatki. Na próbie Wrocławia z 2026-11-23 tej wrażliwości nie było widać.
- **Limit przesiadek prawie nic nie zmienia.** Maksymalnie 2 przesiadki zamiast braku limitu: do 0,14 pkt (Warszawa, 45 min). Zgodne z próbą tras: mediana liczby przesiadek to 0 albo 1, a trzy i więcej przejazdów ma 1,5–10 % par.
- **Feedy nieoficjalne w rdzeniach prawie nic nie zmieniają.** Różnica między siecią ze wszystkimi feedami a samymi oficjalnymi: do 0,5 pkt (Łódź, 45 min); w Poznaniu, Trójmieście i GZM zero, bo listy feedów są tam takie same. Feedy nieoficjalne mają znaczenie dla stref podmiejskich i dla zasięgu maski pokrycia.
- **Reguła min(komunikacja, pieszo)** podnosi wynik rdzenia o 0,1–0,9 pkt (najwięcej w GZM przy 30 min).
- **Kontrola „wszystkie feedy ≥ oficjalne” nie przechodzi w sześciu miastach** (tabela w §8). W Warszawie dotyczy 730 z 88 926 komórek przy którymkolwiek progu; przy 30 min to 72 komórki, a mediana straty wynosi 0,17 %. Wynik główny rdzenia różni się między sieciami o 0,03 pkt. Przyczyny nie ustalono.
- **Porównanie z wyszukiwarką (§9).** 28 z 30 porównywalnych par mieści się w ±20 %. Dwa wyjątki to krótkie podróże (Łódź 16 wobec 11 min, Wrocław 20 wobec 16 min), w których tramwaj odjeżdża w minucie zapytania, a R5 jedzie następnym kursem. W GZM wyszukiwarka wybrała linię M1 tam, gdzie R5 pojechał autobusem i pociągiem: linia M1 jest w feedzie z tym samym odjazdem, R5 nie zdążył na kurs dwie minuty po godzinie zapytania. Dla jednej pary pod Wrocławiem (Morzęcin Wielki) wyszukiwarka nie zna linii gminnych, które są w naszym feedzie.
- **DG REGIO (§7).** Różnica 45-minutowa dla Poznania i Łodzi wynika głównie z innego obszaru (urban centre 2011), nie z braków w feedach; po odtworzeniu obszaru i metody zostaje reszta +4,5 pkt (Poznań) i +11,0 pkt (Łódź), której nie wyjaśniono. Pełny opis: `qa/access/dgregio/dgregio.md`.
- **Miejsca pracy.** Wskaźnik dla miejsc pracy liczony jest jako stosunek średnich, bo w komórkach z małą liczbą miejsc pracy w pobliżu stosunki pojedynczych komórek są niestabilne. Zbiór nie obejmuje GZM (brak danych, nie zero).
- **Próba tras.** `DetailedItineraries` przy oknie 1 min wyczerpywał pamięć R5, więc trasy w próbie liczono dla losowego 5-minutowego okna odjazdów; liczby przesiadek dotyczą najszybszej trasy w tym oknie.
- **Przesiadki a zasięg (dopisane 2026-11-24, wariant bez przesiadek, 105 ze 105 jednostek, §14).** Bez przesiadek KZ 30 w rdzeniach spada o 1,6–6,0 pkt, a KZ 45 o 10,2–24,5 pkt. Udział zasięgu, który wymaga przesiadki (średnia komórek, rdzeń): przy 30 min 7–17 %, przy 45 min 25–42 %; najwyżej w Warszawie, najniżej przy 30 min w GZM i Łodzi, przy 45 min we Wrocławiu i Łodzi. To nie przeczy wynikowi „maks. 2 przesiadki prawie nic nie zmienia”: druga i dalsze przesiadki są rzadkie, pierwsza ma znaczenie. Pojedyncze komórki z udziałem do 85 % sprawdzono: to komórki na skraju rdzenia Warszawy przy przystanku dowozowym, z których w 30 min osiąga się 106–340 tys. osób, a bez przesiadki mniej więcej połowę. Kontrole „bez przesiadek ≤ wynik główny” i „bez przesiadek ≥ sam spacer” (każda komórka, każdy próg): 0 naruszeń. Średnia komórek i stosunek sum różnią się wyraźnie tylko na obszarze pokrytym przy 30 min (Warszawa 11,5 wobec 17,8 %), bo komórki podmiejskie, w których komunikacja nic nie dodaje do spaceru, mają udział 0.
"""


PLANNER = QA / "od_pairs_planner.csv"     # journey-planner answers collected by hand (brief 7.4); an input


def f1(x, nd=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    return f"{x:.{nd}f}".replace(".", ",")


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---:" if pd.api.types.is_numeric_dtype(df[c]) else "---" for c in cols) + "|"]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def tp(c, net, scen, cut, dom, grid="census", weight=None, rom=False):
    u = c["units"].get((net, scen))
    if u is None:
        return None
    b = c["base"]
    kind = SCENARIOS[scen]["kind"]
    sel = dict(domains(b, c["agg"], kind, AI.mask_variant(net) if kind == "transit" else None)).get(dom)
    if sel is None:
        return None
    p, a, x = perf_cells(b, u, kind, weight or grid, cut)
    w = b[f"w_{grid}"].to_numpy(np.float64)
    return ratio_of_means(a, x, w, sel) if rom else wmean(p, w, sel)


# ------------------------------------------------------------------ tables
def headline(ctx) -> pd.DataFrame:
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        if agg not in ctx:
            continue
        c = ctx[agg]
        b = c["base"]
        w = b["w_census"].to_numpy()
        for dom in ("covered", "core", "fua"):
            cov = (w * b["in_mask_all"]).sum() / w.sum() if dom == "fua" else (
                (w * b["in_mask_all"] * b["in_core"]).sum() / (w * b["in_core"]).sum() if dom == "core" else None)
            rows.append({"Aglomeracja": NAMES[agg], "Obszar": {"covered": "pokryty", "core": "rdzeń", "fua": "FUA"}[dom],
                         "KZ 30": f1(tp(c, "all", "pt_am", 30, dom)), "KZ 45": f1(tp(c, "all", "pt_am", 45, dom)),
                         "KZ 30 (stos. średnich)": f1(tp(c, "all", "pt_am", 30, dom, rom=True)),
                         "KZ 45 (stos. średnich)": f1(tp(c, "all", "pt_am", 45, dom, rom=True)),
                         "Pieszo 30": f1(tp(c, "street", "walk", 30, dom)) if dom != "covered" else "",
                         "Rower 30 LTS 3": f1(tp(c, "street", "bike_lts3", 30, dom)) if dom != "covered" else "",
                         "Rower 30 LTS 4": f1(tp(c, "street", "bike_lts4", 30, dom)) if dom != "covered" else "",
                         "Ludność w masce": (f1(100 * cov) + " %" + (" (niepełne)" if cov < 0.85 else "")) if cov is not None else ""})
    return pd.DataFrame(rows)


def variants(ctx) -> pd.DataFrame:
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        if agg not in ctx:
            continue
        c = ctx[agg]
        for dom in ("covered", "core"):
            base30, base45 = tp(c, "all", "pt_am", 30, dom), tp(c, "all", "pt_am", 45, dom)

            def d(net, scen, cut, ref, grid="census"):
                v = tp(c, net, scen, cut, dom, grid)
                return None if v is None or ref is None else v - ref

            rows.append({"Aglomeracja": NAMES[agg], "Obszar": {"covered": "pokryty", "core": "rdzeń"}[dom],
                         "Bazowy KZ 30 / 45": f"{f1(base30)} / {f1(base45)}",
                         "Feedy oficjalne": f"{f1(d('official', 'pt_am', 30, base30), 2)} / {f1(d('official', 'pt_am', 45, base45), 2)}",
                         "10–14": f"{f1(d('all', 'pt_midday', 30, base30), 2)} / {f1(d('all', 'pt_midday', 45, base45), 2)}",
                         "20–22": f"{f1(d('all', 'pt_evening', 30, base30), 2)} / {f1(d('all', 'pt_evening', 45, base45), 2)}",
                         "Sobota 10–14": f"{f1(d('all', 'pt_saturday', 30, base30), 2)} / {f1(d('all', 'pt_saturday', 45, base45), 2)}",
                         "Maks. 2 przesiadki": f"{f1(d('all', 'pt_am_max3rides', 30, base30), 2)} / {f1(d('all', 'pt_am_max3rides', 45, base45), 2)}",
                         "Surowy GHSL": f"{f1(d('all', 'pt_am', 30, base30, 'raw'), 2)} / {f1(d('all', 'pt_am', 45, base45, 'raw'), 2)}"})
    return pd.DataFrame(rows)


def secondary(ctx) -> pd.DataFrame:
    """Official-feed windows (priority 5) and jobs."""
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        if agg not in ctx:
            continue
        c = ctx[agg]
        for dom in ("covered", "core", "fua"):
            r = {"Aglomeracja": NAMES[agg], "Obszar": {"covered": "pokryty", "core": "rdzeń", "fua": "FUA"}[dom]}
            for scen, lab in (("pt_am", "7–9"), ("pt_midday", "10–14"), ("pt_evening", "20–22"), ("pt_saturday", "sob.")):
                r[f"Oficjalne {lab} (30/45)"] = f"{f1(tp(c, 'official', scen, 30, dom))} / {f1(tp(c, 'official', scen, 45, dom))}"
            if agg in AI.JOBS_AGGS:
                r["Miejsca pracy: performance 30/45 (stos. średnich)"] = f"{f1(tp(c, 'all', 'pt_am', 30, dom, weight='jobs', rom=True))} / {f1(tp(c, 'all', 'pt_am', 45, dom, weight='jobs', rom=True))}"
                u = c["units"].get(("all", "pt_am"))
                if u is not None:
                    b = c["base"]
                    sel = dict(domains(b, agg, "transit", "all"))[dom]
                    w = b["w_census"].to_numpy()
                    r["Miejsca pracy osiągalne w 30/45 min"] = (f"{f1(wmean(u['acc_jobs_30'].to_numpy(np.float64), w, sel) / 1000, 0)} tys. / "
                                                               f"{f1(wmean(u['acc_jobs_45'].to_numpy(np.float64), w, sel) / 1000, 0)} tys.")
            else:
                r["Miejsca pracy: performance 30/45 (stos. średnich)"] = "brak danych (GZM)"
            rows.append(r)
    return pd.DataFrame(rows)


def centre_table(ctx) -> pd.DataFrame:
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        if agg not in ctx:
            continue
        c = ctx[agg]
        b = c["base"]
        for cen in AI.centres(agg):
            dom = cen["domain"]
            rows.append({"Aglomeracja": NAMES[agg], "Punkt": cen["name"], "Rodzaj": {"centre": "centrum", "hub": "węzeł"}.get(cen["kind"], "centrum dodatkowe"),
                         "Komórek ≤ 1 km": int(b[dom].sum()), "Ludność": f1(float(b.loc[b[dom], "w_census"].sum()), 0),
                         "KZ 30": f1(tp(c, "all", "pt_am", 30, dom)), "KZ 45": f1(tp(c, "all", "pt_am", 45, dom)),
                         "KZ 30 oficjalne": f1(tp(c, "official", "pt_am", 30, dom)),
                         "Pieszo 30": f1(tp(c, "street", "walk", 30, dom)),
                         "Rower 30 LTS 3 / 4": f"{f1(tp(c, 'street', 'bike_lts3', 30, dom))} / {f1(tp(c, 'street', 'bike_lts4', 30, dom))}"})
    return pd.DataFrame(rows)


def transfers_table(ctx) -> pd.DataFrame:
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        t = ctx.get(agg, {}).get("samples", {}).get("transfers")
        if t is None:
            continue
        ok = t[t["n_rides"].notna()]
        tr = ok[ok["n_rides"] >= 1]
        rows.append({"Aglomeracja": NAMES[agg], "Par w próbie": len(t), "Z itinerarium": len(ok),
                     "Pieszo najszybciej": f1(100 * (ok["n_rides"] == 0).mean()) + " %",
                     "Mediana przesiadek": f1(float(tr["transfers"].median()), 0) if len(tr) else "–",
                     "Średnia": f1(float(tr["transfers"].mean()), 2) if len(tr) else "–",
                     "0 / 1 / ≥2 przesiadki, %": " / ".join(f1(100 * x) for x in ((tr["transfers"] == 0).mean(),
                                                                                    (tr["transfers"] == 1).mean(),
                                                                                    (tr["transfers"] >= 2).mean())) if len(tr) else "–",
                     "Mediana czasu: itinerarium / regionalny, min": f"{f1(float(ok['total_min'].median()))} / {f1(float(ok['regional_min'].median()))}",
                     "Itinerarium dłuższe od czasu regionalnego o > 5 min": f1(100 * float(((ok['total_min'] - ok['regional_min']) > 5).mean())) + " %",
                     "Dojście pieszo > 12 min w itinerarium z przejazdem": f1(100 * float((tr["walk_min"] > 24).mean())) + " % (suma > 24 min)"})
    return pd.DataFrame(rows)


def dgregio_table(ctx) -> pd.DataFrame:
    """Our numbers next to DG REGIO, with what the data allow to attribute."""
    sens = {}
    p = QA / "sample_summary.json"
    if p.exists():
        s = json.loads(p.read_text(encoding="utf-8"))
        for k, v in s.items():
            if k.endswith("_all"):
                sens[k[:-4]] = v["performance"]
    rows = []
    for agg in ("warszawa", "poznan", "lodz", "wroclaw"):
        ref = DGREGIO["cities_chart_read"].get(agg)
        c = ctx.get(agg)
        for cut in (30, 45):
            r = {"Miasto": NAMES[agg], "Miara": f"KZ {cut} min", "DG REGIO (odczyt)": f1(ref[f"transit_{cut}"]) if ref else "brak w próbie DG REGIO"}
            if c is None or ("all", "pt_am") not in c["units"]:
                r["Nasz wynik"] = "oczekuje (pending)"
                rows.append(r)
                continue
            core = tp(c, "all", "pt_am", cut, "core")
            r["Nasz: FUA"] = f1(tp(c, "all", "pt_am", cut, "fua"))
            r["Nasz: rdzeń (główny)"] = f1(core)
            r["Rdzeń, cele tylko w rdzeniu"] = f1(tp(c, "all", "pt_am", cut, "core", weight="censuscore"))
            r["Rdzeń, stosunek średnich"] = f1(tp(c, "all", "pt_am", cut, "core", rom=True))
            r["Rdzeń bez reguły min(KZ, pieszo)"] = f1(perf_rule_off(c, cut))
            w5 = sens.get(agg, {}).get(f"walk5km_minus_1km_perf{cut}_subset")
            r["Dojście 5 km (próba 60 startów, FUA)"] = ("+" + f1(w5) if w5 is not None and w5 >= 0 else f1(w5)) if w5 is not None else "–"
            rows.append(r)
        for mode, scen, lab in (("walk", "walk", "Pieszo 30 min"), ("bike", "bike_lts3", "Rower 30 min LTS 3"), ("bike", "bike_lts4", "Rower 30 min LTS 4")):
            r = {"Miasto": NAMES[agg], "Miara": lab,
                 "DG REGIO (odczyt)": f1(ref[f"{mode}_30"]) if ref else "brak w próbie DG REGIO"}
            if c is None or ("street", scen) not in c["units"]:
                r["Nasz wynik"] = "oczekuje (pending)"
                rows.append(r)
                continue
            r["Nasz: FUA"] = f1(tp(c, "street", scen, 30, "fua"))
            r["Nasz: rdzeń (główny)"] = f1(tp(c, "street", scen, 30, "core"))
            r["Rdzeń, cele tylko w rdzeniu"] = f1(tp(c, "street", scen, 30, "core", weight="censuscore"))
            r["Rdzeń, stosunek średnich"] = f1(tp(c, "street", scen, 30, "core", rom=True))
            rows.append(r)
    return pd.DataFrame(rows).fillna("")


def perf_rule_off(c, cut):
    u = c["units"].get(("all", "pt_am"))
    if u is None or f"r5only_census_{cut}" not in u:
        return None
    b = c["base"]
    p, _, _ = perf_cells(b, u, "transit", "census", cut, col=f"r5only_census_{cut}")
    return wmean(p, b["w_census"].to_numpy(), b["in_core"].to_numpy())


def checks(ctx) -> pd.DataFrame:
    rows = []
    tol = 1e-3
    for agg in AGGS_BY_SIZE[::-1]:
        if agg not in ctx:
            continue
        c = ctx[agg]
        b, U = c["base"], c["units"]
        w = b["w_census"].to_numpy()

        def add(name, n_bad, n, note=""):
            rows.append({"Aglomeracja": NAMES[agg], "Kontrola": name, "Naruszenia": int(n_bad), "Komórek": int(n),
                         "Wynik": "OK" if n_bad == 0 else "UWAGA", "Uwagi": note})

        wk = U.get(("street", "walk"))
        for (net, scen), u in sorted(U.items()):
            kind = SCENARIOS[scen]["kind"]
            acc = np.stack([u[f"acc_census_{k}"].to_numpy(np.float64) for k in AI.CUTOFFS], axis=1)
            add(f"{net}/{scen}: osiągalni rosną z progiem 5→60 min", int((np.diff(acc, axis=1) < -tol).any(axis=1).sum()), len(u))
            p30 = perf_cells(b, u, kind, "census", 30)[0]
            fin = np.isfinite(p30)
            add(f"{net}/{scen}: performance 30 min w [0, 100]", int(((p30[fin] < 0) | (p30[fin] > 100)).sum()), int(fin.sum()),
                f"maks. {f1(np.nanmax(p30))}; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: "
                f"{int((u['n_reach60'] == 0).sum())} komórek, ludność {f1(float(w[(u['n_reach60'] == 0).to_numpy()].sum()), 0)}")
            if kind == "transit" and wk is not None:
                bad = 0
                for k in AI.CUTOFFS:
                    bad_k = u[f"acc_census_{k}"].to_numpy(np.float64) < wk[f"acc_census_{k}"].to_numpy(np.float64) * (1 - 1e-6) - tol
                    bad = bad | bad_k if isinstance(bad, np.ndarray) else bad_k
                add(f"{net}/{scen}: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg)", int(bad.sum()), len(u))
                if "r5only_census_30" in u:
                    lift = u["acc_census_30"].to_numpy(np.float64) - u["r5only_census_30"].to_numpy(np.float64)
                    add(f"{net}/{scen}: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5", int((lift < -tol).sum()), len(u),
                        f"podnosi osiągalnych w 30 min w {int((lift > tol).sum())} komórkach")
        for a, bb, lab in ((("street", "bike_lts4"), ("street", "bike_lts3"), "rower LTS 4 ≥ LTS 3"),
                           (("all", "pt_am"), ("all", "pt_am_max3rides"), "bez limitu przesiadek ≥ maks. 2 przesiadki"),
                           (("all", "pt_am"), ("all", "pt_am_direct"), "bez limitu przesiadek ≥ bez przesiadek"),
                           (("all", "pt_am"), ("official", "pt_am"), "wszystkie feedy ≥ oficjalne")):
            if a in U and bb in U:
                bad = np.zeros(len(b), bool)
                for k in AI.CUTOFFS:
                    bad |= U[a][f"acc_census_{k}"].to_numpy(np.float64) < U[bb][f"acc_census_{k}"].to_numpy(np.float64) - tol
                add(lab + " (osiągalni, każdy próg)", int(bad.sum()), len(b),
                    "" if not bad.any() else f"ludność komórek z naruszeniem: {f1(float(w[bad].sum()), 0)}")
    return pd.DataFrame(rows)


def dep(c, cut, dom, rom=False):
    """Transfer dependence (%) for a domain: mean of cell shares, or ratio of sums (rom)."""
    ud, um = c["units"].get(("all", "pt_am_direct")), c["units"].get(("all", "pt_am"))
    if ud is None or um is None:
        return None
    b = c["base"]
    sel = dict(domains(b, c["agg"], "transit", "all")).get(dom)
    w = b["w_census"].to_numpy(np.float64)
    d, ad, am = dependence_cells(ud, um, "census", cut)
    return dependence_ratio_of_sums(ad, am, w, sel) if rom else wmean(d, w, sel)


def direct_table(ctx) -> pd.DataFrame:
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        if agg not in ctx:
            continue
        c = ctx[agg]
        for dom in ("core", "covered"):
            r = {"Aglomeracja": NAMES[agg], "Obszar": {"covered": "pokryty", "core": "rdzeń"}[dom]}
            for cut in (30, 45):
                r[f"KZ {cut}: główny / bez przesiadek"] = f"{f1(tp(c, 'all', 'pt_am', cut, dom))} / {f1(tp(c, 'all', 'pt_am_direct', cut, dom))}"
                r[f"Wymaga przesiadki {cut} min, %: średnia komórek / stosunek sum"] = f"{f1(dep(c, cut, dom))} / {f1(dep(c, cut, dom, rom=True))}"
            rows.append(r)
    return pd.DataFrame(rows)


def direct_quantiles(ctx) -> pd.DataFrame:
    """Distribution of the cell shares (30 min, cells in the mask with population), for the map classes."""
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        c = ctx.get(agg)
        if c is None or ("all", "pt_am_direct") not in c["units"]:
            continue
        b = c["base"]
        d = dependence_cells(c["units"][("all", "pt_am_direct")], c["units"][("all", "pt_am")], "census", 30)[0]
        m = b["in_mask_all"].to_numpy() & np.isfinite(d) & (b["w_census"].to_numpy() > 0)
        v = d[m]
        r = {"Aglomeracja": NAMES[agg], "Komórek": int(m.sum())}
        for q in (10, 25, 50, 75, 90):
            r[f"p{q}"] = f1(float(np.percentile(v, q)))
        r["Komórek z udziałem 0"] = f1(100 * float((v <= 1e-6).mean())) + " %"
        rows.append(r)
    return pd.DataFrame(rows)


def timing(ctx) -> pd.DataFrame:
    rows = []
    for agg in AGGS_BY_SIZE:
        for f in sorted(AI.ACCESS_INT.glob(f"{agg}/*/*/manifest.json")):
            d = f.parent
            scen, net = d.name, d.parent.name
            ts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.time.json"))]
            if not ts:
                continue
            wall = sum(t["wall_s"] for t in ts)
            n = sum(t["n"] for t in ts)
            est = est_s_per_origin(agg, scen) * n if SCENARIOS[scen]["kind"] in ("transit", "walk", "bike") else None
            rows.append({"Aglomeracja": NAMES[agg], "Jednostka": f"{net}/{scen}", "Starty / wiersze": n,
                         "Czas routingu, s": f1(wall), "ms / start": f1(1000 * wall / max(n, 1), 2) if est is not None else "",
                         "Szacunek z benchmarku, s": f1(est) if est is not None else "",
                         "Zmierzony / szacunek": f1(wall / est, 2) if est else ""})
    return pd.DataFrame(rows)


def od_table(ctx) -> pd.DataFrame:
    rows = []
    for agg in AGGS_BY_SIZE[::-1]:
        t = ctx.get(agg, {}).get("samples", {}).get("odpairs")
        if t is None:
            continue
        for r in t.itertuples():
            rows.append({"Miasto": NAMES[agg], "Nr": r.pair, "Rodzaj": r.kind,
                         "Start (lon, lat)": f"{r.origin} ({r.origin_lon:.5f}, {r.origin_lat:.5f})",
                         "Cel (lon, lat)": f"{r.destination} ({r.destination_lon:.5f}, {r.destination_lat:.5f})",
                         "Odjazd": f"{r.day} {r.departure}",
                         "R5 o tej godzinie, min": f1(r.r5_transit_at_departure_min, 0),
                         "R5 mediana 7–9, min": f1(r.r5_transit_median_0709_min, 0),
                         "Pieszo, min": f1(r.r5_walk_only_min, 0),
                         "Trasa R5 (najszybsza o tej godzinie)": f"{f1(r.itinerary_total_min)} min: {r.itinerary}",
                         "_r5": r.r5_transit_at_departure_min})
    od = pd.DataFrame(rows)
    if od.empty:
        return od
    # journey-planner answers are collected by hand (brief 7.4) and kept next to the outputs
    cols = ["Wyszukiwarka", "Data zapytania", "Wyszukiwarka, min", "R5 do wyszukiwarki, %",
            "Linie w wyszukiwarce", "Uwagi"]
    if PLANNER.exists():
        pl = pd.read_csv(PLANNER).rename(columns={"Wyszukiwarka, min od podanej godziny": "_g",
                                                   "Linie w najszybszej trasie": "Linie w wyszukiwarce"})
        od = od.merge(pl[["Miasto", "Nr", "Wyszukiwarka", "Data zapytania", "_g", "Linie w wyszukiwarce", "Uwagi"]],
                      on=["Miasto", "Nr"], how="left")
        r5 = pd.to_numeric(od["_r5"], errors="coerce").round()
        g = pd.to_numeric(od["_g"], errors="coerce")
        asked = od["Wyszukiwarka"].notna()
        od["Wyszukiwarka, min"] = [f1(v, 0) if v == v else ("brak trasy" if a else "") for v, a in zip(g, asked)]
        od["R5 do wyszukiwarki, %"] = [f"{100 * (a / b - 1):+.0f}".replace("-", "−") if a == a and b == b and b > 0
                                       else "" for a, b in zip(r5, g)]
        for c in ("Wyszukiwarka", "Data zapytania", "Linie w wyszukiwarce", "Uwagi"):
            od[c] = od[c].fillna("")
        summary = planner_summary(r5, g, asked)
    else:
        summary = ""
        for c in cols:
            od[c] = ""
    od = od.drop(columns=[c for c in ("_r5", "_g") if c in od.columns])
    od.attrs["planner"] = summary
    return od


def planner_summary(r5: pd.Series, g: pd.Series, asked: pd.Series) -> str:
    ok = r5.notna() & g.notna() & (g > 0)
    if not ok.any():
        return ""
    d = 100 * (r5[ok] / g[ok] - 1)
    return (f"Wyszukiwarkę odpytano dla {int(asked.sum())} par, porównywalnych (obie strony znalazły trasę) jest "
            f"{int(ok.sum())}. W granicy ±20 % mieści się {int((d.abs() <= 20).sum())} par; R5 jest wolniejszy o więcej "
            f"niż 20 % w {int((d > 20).sum())}, szybszy o więcej niż 20 % w {int((d < -20).sum())}. Suma czasów R5 "
            f"do sumy czasów wyszukiwarki: {f1(float(r5[ok].sum() / g[ok].sum()), 3)}; mediana różnicy "
            f"{f1(float(d.median()), 1)} %. Każda różnica powyżej 20 % ma wyjaśnienie w kolumnie „Uwagi”.")


# ------------------------------------------------------------------ plots
def plot_map(agg: str, c: dict) -> str | None:
    b, U = c["base"], c["units"]
    panels = [(("all", "pt_am"), 30, True, "KZ + pieszo 30 min (7–9, wszystkie feedy)"),
              (("all", "pt_am"), 45, True, "KZ + pieszo 45 min"),
              (("street", "walk"), 30, False, "pieszo 30 min"),
              (("street", "bike_lts3"), 30, False, "rower 30 min, LTS ≤ 3")]
    if ("all", "pt_am") not in U:
        return None
    a = load_agglomeration(agg)
    x0, y0, x1, y1 = a["fua"].bounds
    nx_, ny_ = int(np.ceil((x1 - x0) / AI.CELL)) + 2, int(np.ceil((y1 - y0) / AI.CELL)) + 2
    ci = ((b.x - x0) // AI.CELL).astype(int).to_numpy()
    ri = ((y1 - b.y) // AI.CELL).astype(int).to_numpy()
    ext = (x0, x0 + nx_ * AI.CELL, y1 - ny_ * AI.CELL, y1)
    cmap = ListedColormap(COLS)
    norm = BoundaryNorm(BINS, cmap.N)
    asp = (y1 - y0) / (x1 - x0)
    fig, axs = plt.subplots(2, 2, figsize=(14, 14 * asp + 1.2))
    for ax, (key, cut, masked, title) in zip(axs.ravel(), panels):
        u = U.get(key)
        if u is None:
            ax.set_title(title + ": oczekuje", fontsize=9)
            ax.set_axis_off()
            continue
        kind = SCENARIOS[key[1]]["kind"]
        p = perf_cells(b, u, kind, "census", cut)[0]
        arr = np.full((ny_, nx_), np.nan)
        arr[ri, ci] = np.where(np.isfinite(p), p, np.nan)
        ax.imshow(arr, cmap=cmap, norm=norm, extent=ext, interpolation="nearest")
        if masked:   # cells outside the phase-2 coverage mask: grey + hatched ("brak danych"), as in frequent_qa
            out = np.zeros((ny_, nx_))
            om = ~b["in_mask_all"].to_numpy()
            out[ri[om], ci[om]] = 1
            arr[ri[om], ci[om]] = np.nan
            ax.imshow(arr, cmap=cmap, norm=norm, extent=ext, interpolation="nearest")
            ax.imshow(np.where(out > 0, 1.0, np.nan), cmap=ListedColormap(["#b0b0b0"]), extent=ext,
                      interpolation="nearest", alpha=0.8)
            xs = np.linspace(ext[0], ext[1], nx_); ys = np.linspace(ext[3], ext[2], ny_)
            ax.contourf(xs, ys, out, levels=[0.5, 1.5], colors="none", hatches=["////"])
        for geom, col, lw in ((a["fua"], "#333333", 0.8), (a["core"], "#1d4ed8", 1.0)):
            for g in getattr(geom, "geoms", [geom]):
                xx, yy = g.exterior.xy
                ax.plot(xx, yy, color=col, lw=lw)
        sel = b["in_mask_all"].to_numpy() if masked else np.ones(len(b), bool)
        v = wmean(p, b["w_census"].to_numpy(), sel)
        ax.set_title(f"{title}\nśrednia ważona ({'obszar pokryty' if masked else 'FUA'}): {f1(v)}", fontsize=9)
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_xticks([]); ax.set_yticks([])
    from matplotlib.patches import Patch
    lab = ["< 10", "10–20", "20–30", "30–40", "40–50", "50–60", "60–80", "80–100", "> 100"]
    hand = [Patch(color=COLS[i], label=lab[i]) for i in range(len(COLS))]
    hand.append(Patch(facecolor="#b0b0b0", hatch="////", label="poza maską GTFS: brak danych (KZ)"))
    fig.legend(handles=hand, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle(f"{NAMES[agg]}: transport performance komórek 250 m (ludność NSP 2021 / GHSL 2020; środa {CFG['reference_day']}; "
                 "niebieska linia: rdzeń). Szkic QA, nie grafika.", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    name = f"map_{agg}.png"
    fig.savefig(QA / name, dpi=90)
    plt.close(fig)
    return name


def plot_curves(ctx) -> str | None:
    aggs = [a for a in AGGS_BY_SIZE[::-1] if a in ctx]
    if not aggs:
        return None
    fig, axs = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    for ax, (key, title, dom) in zip(axs, ((("all", "pt_am"), "KZ + pieszo, obszar pokryty", "covered"),
                                           (("street", "walk"), "pieszo, FUA", "fua"),
                                           (("street", "bike_lts3"), "rower LTS ≤ 3, FUA", "fua"))):
        for agg in aggs:
            c = ctx[agg]
            if key not in c["units"]:
                continue
            ys = [tp(c, key[0], key[1], k, dom) for k in AI.CUTOFFS]
            ax.plot(AI.CUTOFFS, ys, marker="o", ms=3, label=NAMES[agg])
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("próg czasu, min (promień = prędkość × próg)")
        ax.grid(alpha=0.3)
    axs[0].set_ylabel("transport performance")
    axs[0].legend(fontsize=8)
    fig.suptitle("Krzywe performance względem progu czasu (ludność NSP 2021 / GHSL 2020). Szkic QA.", fontsize=10)
    fig.tight_layout()
    fig.savefig(QA / "curves.png", dpi=90)
    plt.close(fig)
    return "curves.png"


# ------------------------------------------------------------------ markdown
def write_md(ctx, status, size, pngs) -> None:
    st = pd.DataFrame(status)
    done = st[st.state == "done"]
    pend = st[st.state != "done"]
    L = []
    L.append("# Faza 3: dostępność i transport performance (§4.6)\n")
    L.append(f"Stan: {len(done)}/{len(st)} jednostek policzonych. Plik generuje `python -m pipeline.access aggregate` z tego, co "
             "jest gotowe; jednostki niepoliczone są wymienione na końcu jako „oczekuje”, a ich wyniki nie trafiają do tabel "
             "ani do `metrics_access.csv` (nie są zerami ani brakami danych). Kosztorys i benchmark: [`plan.md`](plan.md).\n")
    L.append("Daty: ludność NSP 2021 (31.03.2021) w układzie GHSL 2020 (wariant surowy GHSL 2020 obok); rozkłady środa "
             f"{CFG['reference_day']} i sobota {CFG['reference_saturday']} (feedy pobrane 2026-11-23); OSM {'2026-11-22'}; "
             "miejsca pracy Goliszek 2026 (horyzont 2025).\n")
    L.append("## 1. Metoda\n")
    L.append("""- **Starty:** każda komórka 250 m z ludnością (którakolwiek siatka) ze środkiem w FUA. **Cele i mianownik (proximity):** wszystkie komórki z ludnością w FUA + 15 km (ten sam zbiór), plus komórki z miejscami pracy bez ludności. Bez próbkowania.
- **Accessibility:** ludność (albo miejsca pracy) w komórkach, do których czas przejazdu ≤ próg. Zapisywane dla progów 5, 10, …, 60 min, więc krzywe nie wymagają ponownego routingu.
- **Proximity:** ludność w komórkach, których środek leży w linii prostej ≤ prędkość × próg od środka startu: 15 km/h dla komunikacji i roweru (7,5 km przy 30 min, 11,25 km przy 45 min), 5 km/h pieszo (2,5 km przy 30 min).
- **Performance komórki = accessibility / proximity × 100.** Wynik główny (brief): średnia stosunków po komórkach ważona ludnością komórki. Obok (`*_ratio_of_means`, tier `table`): stosunek średnich ważonych; różni się nawet o 10–15 pkt, bo komórki podmiejskie mają mały mianownik.
- **Komunikacja + pieszo:** R5 v7.5.1 (r5py 1.1.7), odjazdy co minutę w oknie, mediana (50. percentyl) z odjazdów, maks. 60 min podróży, pieszo 5 km/h, dojście i odejście ≤ 12 min (= 1 km) na odcinek, przesiadki piesze wg R5. **Reguła: komunikacja + pieszo nigdy nie jest gorsza od samego spaceru.** Limit dojścia 12 min ogranicza w R5 także podróż wyłącznie pieszą wewnątrz zapytania komunikacyjnego, więc dla każdej pary start–cel bierzemy min(czas R5 komunikacją, czas samego spaceru bez limitu 12 min, 5 km/h) **przed** zastosowaniem progów 30/45 min. Minimum ze stałą jest przemienne z medianą po odjazdach, więc to to samo, co mediana z minimum dla każdego odjazdu. Wariant bez tej reguły (`*_without_walk_rule`, tier `qa`) pokazuje jej wpływ.
- **Pieszo:** 5 km/h, do 60 min. **Rower:** 15 km/h, do 60 min, dwa warianty poziomu stresu ruchu R5: LTS ≤ 3 (domyślne r5py) i LTS ≤ 4; wybór wariantu głównego należy do właściciela, oba mają tier `table`. Samochodu nie liczono (brief §11).
- **Okna:** środa 7:00–9:00 (główne), 10:00–14:00, 20:00–22:00, sobota 10:00–14:00. **Max 2 przesiadki:** R5 `maxRides` = 3, okno 7–9, podawane jako różnica do wyniku głównego. **Bez przesiadek:** R5 `maxRides` = 1, okno 7–9, pozostałe parametry i reguła min(komunikacja, pieszo) jak w wyniku głównym (§14).
- **Feedy:** wariant „wszystkie” (główny) i „oficjalne”, osobne sieci R5. Wariant „sieć wspólnego biletu” jest odłożony (tabela taryf niepotwierdzona); kod przewiduje go jako kolejny wariant sieci (`fare_<nazwa>`), bez przeliczania czegokolwiek innego.
- **Maska pokrycia GTFS (§6):** maska fazy 2 dla tego samego wariantu feedów (`results/layers/frequent_cells.parquet`, w postaci poligonów `gtfs_coverage_mask.parquet`). W warstwie komórek wynik komunikacji poza maską to brak danych, nie 0. Wartości dla FUA i rdzenia obejmują wszystkie komórki (jak w fazie 2), mają `coverage_share` i oznaczenie „niepełne pokrycie GTFS”, gdy w masce jest < 85 % ludności; do porównań służy „obszar pokryty” i „rdzeń”. **Niekompletność po stronie celów** (miejsca obsługiwane tylko przez przewoźników bez GTFS) obniża dostępność także wewnątrz maski; maska tego nie usuwa. Pieszo i rower nie są maskowane.
- **Miejsca pracy** („miejsca pracy w granicach miasta”): zbiór Goliszek (IGiPZ PAN, CC BY 4.0) rozdzielony z komórek 100 m (część wieloczęściowych i niepełnych) na siatkę 250 m proporcjonalnie do pola przecięcia; sumy zgadzają się co do 1e-6. Zbiór obejmuje tylko miasta w granicach administracyjnych (w Trójmieście tylko Gdańsk, GZM brak → wynik pusty). Starty z całego FUA. Performance miejsc pracy to **stosunek średnich**: na skraju zasięgu zbioru mianownik (miejsca pracy w promieniu) wynosi kilka miejsc i stosunki komórek przekraczają 1000, więc średnia stosunków jest dla miejsc pracy bezużyteczna (zostaje jako kontrola `*_mean_of_ratios` dla startów w granicach miasta).
- **Z centrum:** średnia ważona ludnością po komórkach ≤ 1 km od centrum i osobno od węzła z `config.yaml`; w Trójmieście i GZM dla każdego centrum z `extra_centres`, z zastrzeżeniem z §11.
- **Liczby bezwzględne** („ludność osiągalna”, „miejsca pracy osiągalne”, `acc_*`, `prox_*`) mają tier `table` i oznaczenie, że mierzą wielkość miasta, a nie jakość transportu (§11).
- **Mediana liczby przesiadek:** routing regionalny R5 zwraca tylko czasy, więc liczba przesiadek pochodzi z **próby** par start–cel (start ważony ludnością, cel ważony ludnością wśród osiągalnych w 45 min, losowa minuta odjazdu 7:00–9:00) i najszybszego itinerarium r5py `DetailedItineraries` o tej minucie. Znane ograniczenie r5py: `DetailedItineraries` nie egzekwuje limitu dojścia 12 min tak jak routing regionalny.
- **Determinizm:** paczki 1 000 startów są zapisywane atomowo z podpisem wejść; ta sama paczka policzona drugi raz daje identyczne bajty (sprawdzone, sekcja 8). Wyniki zaokrąglone do 4 cyfr znaczących.
""")
    L.append("## 2. Wynik główny (środa 7–9, wszystkie feedy, siatka spisowa)\n")
    L.append("KZ = komunikacja zbiorowa + pieszo. Wartości to performance (0–100, może przekroczyć 100). „Obszar pokryty” = komórki w masce GTFS.\n")
    L.append(md_table(headline(ctx)) + "\n")
    L.append("## 3. Warianty (różnica do wyniku głównego, pkt; KZ 30 / KZ 45)\n")
    L.append(md_table(variants(ctx)) + "\n")
    L.append("„Feedy oficjalne” w wierszu „pokryty” liczone są na masce wariantu oficjalnego (mniejszej i bardziej miejskiej), więc tej różnicy nie należy czytać jako wpływu feedów; w wierszu „rdzeń” obszar jest ten sam.\n")
    L.append("## 4. Feedy oficjalne we wszystkich oknach i miejsca pracy\n")
    L.append(md_table(secondary(ctx)) + "\n")
    L.append("## 5. Z centrum (komórki ≤ 1 km)\n")
    L.append(md_table(centre_table(ctx)) + "\n")
    L.append("## 6. Liczba przesiadek (próba)\n")
    tt = transfers_table(ctx)
    L.append((md_table(tt) if len(tt) else "oczekuje") + "\n")
    L.append("Kolumna „dojście > 12 min” liczy itineraria z przejazdem, w których suma odcinków pieszych przekracza 24 min (dwa odcinki po 12 min), czyli przypadki, gdzie `DetailedItineraries` na pewno przekroczył limit regionalny.\n")
    L.append("## 7. Benchmark DG REGIO (§7.2)\n")
    L.append("DG REGIO: Poelman, Dijkstra, Ackermans (2020), WP 01/2020. Średnie próby 42 miast UE: KZ 30 = 24, KZ 45 = 57, pieszo 52, rower 75. "
             "Wartości miast odczytane z wykresów (±1 pkt). Wrocław nie jest w próbie DG REGIO; jego wiersze pokazują tylko rozkład naszych wariantów.\n")
    L.append(md_table(dgregio_table(ctx)) + "\n")
    L.append("**Różnice metodyczne:**\n\n" + "\n".join(f"- {m}" for m in METHOD_DIFFS) + "\n")
    L.append("**Przypisanie różnic (tylko to, na co pozwalają nasze dane):** kolumna „rdzeń” zbliża domenę startów do urban centre; "
             "„cele tylko w rdzeniu” ogranicza dodatkowo licznik i mianownik do celów w granicach miasta (przybliżenie domeny celów DG REGIO); "
             "„stosunek średnich” pokazuje wpływ sposobu agregacji; „bez reguły min” pokazuje, ile daje nieograniczony spacer; "
             "efekt dojścia 5 km pochodzi z próby 60 startów z `plan.md` (liczonej jeszcze bez reguły min, więc z regułą jest mniejszy). "
             "Wpływu roku rozkładów (2018/2026), roku ludności (2011/2021), poligonów Urban Atlas i średniej z 9 odjazdów nie da się wydzielić z naszych danych.\n")
    L.append("## 8. Kontrole wewnętrzne\n")
    ck = checks(ctx)
    L.append(md_table(ck) + "\n")
    L.append("Performance > 100 nie jest błędem: licznik liczy cele osiągalne także poza promieniem proximity (np. koleją), mianownik tylko te w promieniu.\n")
    L.append(DETERMINISM + "\n")
    L.append("## 9. Pary start–cel do porównania z wyszukiwarką (§7.4)\n")
    od = od_table(ctx)
    L.append("Porównywany jest czas **dla podanej godziny odjazdu** w środę "
             f"{CFG['reference_day']} (kolumna „R5 o tej godzinie”), nie mediana z okna: od tej godziny do najwcześniejszego "
             "przyjazdu, jaki pokazuje wyszukiwarka dla tego samego dnia i godziny (tryb komunikacji zbiorowej). Starty leżą "
             "przy przystankach, bo `DetailedItineraries` nie egzekwuje limitu dojścia 12 min. Odpowiedzi wyszukiwarki "
             "zebrano ręcznie i zapisano w `od_pairs_planner.csv` (data zapytania w tabeli). Różnica > 20 % wymaga "
             "wyjaśnienia (§7.4).\n")
    if len(od) and od.attrs.get("planner"):
        L.append(od.attrs["planner"] + "\n")
    L.append((md_table(od) if len(od) else "oczekuje") + "\n")
    L.append("## 10. Czas liczenia\n")
    tm = timing(ctx)
    L.append((md_table(tm) if len(tm) else "brak") + "\n")
    L.append(TIMING_NOTE + "\n")
    L.append("## 11. Co zaskoczyło i co wyszło przy sprawdzaniu\n")
    L.append(OBSERVATIONS + "\n")
    L.append("## 12. Pliki\n")
    L.append("- `results/metrics/metrics_access.csv` / `.json` (kolumny jak w innych krokach; JSON ma też `status` jednostek), scalane przez `pipeline.merge_metrics`.\n"
             "- `results/charts/access_performance.json`: per miasto KZ 30/45, pieszo, rower (oba LTS), krzywe 5–60 min, benchmark DG REGIO z różnicami metod.\n"
             f"- `results/layers/access_cells.parquet` ({size} MB): punkty środków komórek 250 m (EPSG:4326; komórka = kwadrat 250 m w EPSG:2180, `cell_id` = lewy dolny róg), performance KZ 30/45 (null poza maską i dla jednostek oczekujących), pieszo 30, rower 30 LTS 3 i 4, KZ 30 bez przesiadek i udział zasięgu wymagający przesiadki przy 30 i 45 min (null poza maską i tam, gdzie w wyniku głównym nikt nie jest osiągalny).\n"
             "- PNG: " + ", ".join(f"[`{p}`]({p})" for p in pngs) + ".\n"
             "- Dane pośrednie (poza gitem): `data/interim/access/<aglomeracja>/<sieć>/<scenariusz>/chunk_*.parquet`, log `data/interim/access/run.log`.\n")
    L.append("## 13. Stan jednostek\n")
    L.append(md_table(st.rename(columns={"agglomeration": "Aglomeracja", "priority": "Priorytet", "network": "Sieć",
                                         "scenario": "Scenariusz", "chunks_done": "Paczki gotowe",
                                         "chunks_total": "Paczki", "state": "Stan"})) + "\n")
    L.append("## 14. Ile zasięgu wymaga przesiadki (podróże bez przesiadek)\n")
    L.append("Wariant wyniku głównego (środa 7–9, wszystkie feedy) z co najwyżej jednym przejazdem, czyli bez przesiadek (R5 "
             "`maxRides` = 1); reguła min(komunikacja, pieszo) jak w wyniku głównym. **Udział zasięgu, który wymaga przesiadki** = "
             "(1 − osiągalni bez przesiadki / osiągalni w wyniku głównym) × 100; dla obszaru jako średnia udziałów komórek ważona "
             "ludnością oraz jako stosunek sum ważonych. Komórki, z których w wyniku głównym nikt nie jest osiągalny, są pomijane "
             "(brak danych). Czas rozkładowy, mediana z odjazdów co minutę, siatka spisowa.\n")
    dt_ = direct_table(ctx)
    L.append((md_table(dt_) if len(dt_) else "oczekuje") + "\n")
    L.append("Rozkład udziału w komórkach (30 min, komórki w masce z ludnością, %; percentyle bez ważenia ludnością):\n")
    dq = direct_quantiles(ctx)
    L.append((md_table(dq) if len(dq) else "oczekuje") + "\n")
    L.append("Kontrole (każda komórka, każdy próg 5–60 min; te same wiersze są w §8):\n")
    ckd = ck[ck["Kontrola"].str.contains("pt_am_direct|bez przesiadek", regex=True)] if len(ck) else ck
    L.append((md_table(ckd) if len(ckd) else "oczekuje") + "\n")
    if DIRECT_NOTE:
        L.append(DIRECT_NOTE + "\n")
    (QA / "access.md").write_text("\n".join(L), encoding="utf-8", newline="\n")


DIRECT_NOTE = (   # hand-written after the run (dated): what the transfer-dependence result says
    "**Odczyt (2026-11-24).** Przy 30 min przesiadka jest potrzebna do niewielkiej części zasięgu: w rdzeniach 7–17 % "
    "osiągalnej ludności (najwięcej Warszawa, najmniej GZM), bo w pół godziny większość celów leży przy jednej linii albo "
    "w zasięgu spaceru. Przy 45 min udział rośnie do 25–42 % i to przesiadki dają dużą część przyrostu między 30 a 45 min: "
    "bez nich KZ 45 w rdzeniu Warszawy spada z 58,8 do 34,3. Udział 0 w komórce zwykle nie oznacza dobrej linii "
    "bezpośredniej: w 71–90 % takich komórek (30 min; sprawdzono w Warszawie, GZM i Trójmieście) komunikacja nie dodaje "
    "nic do samego spaceru. Dlatego komórek z udziałem 0 jest 55–86 %, ale mieszka w nich tylko 10–22 % ludności.")

DETERMINISM = ("**Wznawialność i determinizm (test na Wrocławiu):** przebieg przerwano dwa razy: w trakcie próby przesiadek (po zmianie "
               "parametrów próby jej podpis się zmienił i jednostka została policzona od nowa, a 4 gotowe jednostki zostały pominięte) i w "
               "trakcie paczki 9/21 okna 10–14 (zabicie procesu). Po ponownym uruchomieniu tego samego polecenia pominięto 7 gotowych "
               "jednostek i 8 gotowych paczek, liczenie ruszyło od paczki 9; nie zostały pliki częściowe. Pięć paczek (pieszo, KZ 7–9, "
               "rower LTS 4, KZ oficjalne 7–9, sobota) policzono drugi raz w nowej JVM: pliki parquet są identyczne co do bajta "
               "(SHA-256), pamięć podręczna czasów pieszych też.")
TIMING_NOTE = ("Wrocław, wszystkie 14 jednostek: ok. 40 min routingu, z czego 20 min to próba przesiadek (200 par) i 1,6 min pary OD; "
               "same przebiegi regionalne 19 min wobec 20 min z kosztorysu `plan.md` (0,34 h bez sieci wspólnego biletu). Komunikacja "
               "wyszła 0,5–0,66 × szacunku z benchmarku (czasy pieszo są liczone raz i używane ponownie), pieszo do 60 min 1,2 ×, rower "
               "do 60 min 1,2 × (LTS 3) i 1,6 × (LTS 4) szacunku z przelicznikiem 3,0 / 3,6. `python -m pipeline.access status` "
               "przelicza resztę z tych współczynników; dla Warszawy niepewność jest największa.")


def write_qa(ctx: dict, rows: list[dict], status: list[dict], size, t0: float) -> None:
    QA.mkdir(parents=True, exist_ok=True)
    for agg, c in ctx.items():
        c["agg"] = agg
    pngs = []
    for agg in AGGS_BY_SIZE[::-1]:
        if agg in ctx:
            n = plot_map(agg, ctx[agg])
            if n:
                pngs.append(n)
    cv = plot_curves(ctx)
    if cv:
        pngs.append(cv)
    ck = checks(ctx)
    ck.to_csv(QA / "checks.csv", index=False, lineterminator="\n")
    od = od_table(ctx)
    if len(od):
        od.to_csv(QA / "od_pairs.csv", index=False, lineterminator="\n")
    for agg, c in ctx.items():
        t = c["samples"].get("transfers")
        if t is not None:
            t.to_csv(QA / f"transfers_sample_{agg}.csv", index=False, lineterminator="\n")
    write_md(ctx, status, size, pngs)
    inputs = ["osm_poland_pbf", "nsp2021_grid_1km_shp", "ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20",
              "urau_2021_100k_all", "lau_2021_01m", "jobs_Jobs_2025_7_Cities.gpkg"]
    from pipeline import gtfs_service as gs
    inputs += sorted({f"gtfs_{f}" for a in ctx for v in ("all", "official") for f in gs.feeds_for(a, v)})
    from pipeline.access import CODE_VERSION
    from pipeline.r5_env import R5_JAR_SHA256, R5_VERSION
    extra = {"timetable_dates": [CFG["reference_day"], CFG["reference_saturday"]], "code_version": CODE_VERSION,
             "r5": R5_VERSION, "r5_jar_sha256": R5_JAR_SHA256,
             "units_done": sum(r["state"] == "done" for r in status), "units_total": len(status),
             "pending": [f"{r['agglomeration']} {r['network']}/{r['scenario']}" for r in status if r["state"] != "done"]}
    outs = {QA: sorted(p.name for p in QA.iterdir() if p.name.startswith(("access", "map_", "curves", "checks", "od_pairs", "transfers_"))),
            METRICS: ["metrics_access.csv", "metrics_access.json"], CHARTS: ["access_performance.json"],
            LAYERS: ["access_cells.parquet"]}
    tmp = Path(tempfile.mkdtemp())
    for folder, files in outs.items():
        ex = {**extra, "outputs": files}
        if folder == LAYERS:
            ex["files"] = {"access_cells.parquet": {
                "crs": "EPSG:4326", "geometry": "centroid (point) of a 250 m EPSG:2180 cell; cell size 250 m; cell_id = "
                "E<x0>N<y0> lower-left corner in EPSG:2180",
                "rows": "populated cells (either grid) with centre in FUA",
                "columns": "tp_pt_am_30/45: transport performance by public transport + walk, Wednesday 07-09, all feeds, "
                           "census-scaled grid; null outside the GTFS coverage mask (no data) or while pending; "
                           "tp_walk_30; tp_bike_lts3_30 / tp_bike_lts4_30 (15 km/h, R5 level of traffic stress <= 3 / <= 4); "
                           "tp_pt_am_direct_30: as tp_pt_am_30 with at most one ride (no transfers); "
                           "transfer_dependence_30 / _45: 100 x (1 - reachable without transfer / reachable in pt_am), %, "
                           "null outside the mask or where nobody is reachable in pt_am",
                "size_mb": size}}
        write_meta(tmp, "access", inputs=inputs, started=t0, extra=ex)
        shutil.copyfile(tmp / "_meta.json", folder / "_meta_access.json")
    shutil.rmtree(tmp, ignore_errors=True)
