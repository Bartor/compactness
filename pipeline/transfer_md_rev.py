"""Sections of the Polish QA note for the revisions after the literature review (pipeline.transfer_md).

Kept apart from transfer_md.py so that the earlier sections stay as they were; the hand-written reading of the
numbers is in pipeline.transfer_text.REV."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline import transfer_ease as T
from pipeline import transfer_report as TR
from pipeline import transfer_walk as W
from pipeline.transfer_text import REV

PL = TR._pl
N = TR.NAMES
MODE_PL = {"bus": "autobus", "tram": "tramwaj", "rail": "kolej", "metro": "metro", "trolleybus": "trolejbus"}


def _v(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)) or (not isinstance(x, str) and pd.isna(x)):
        return "brak danych"
    return PL(float(x), d)


def _pct(x, d=0):
    return "brak danych" if x is None or pd.isna(x) else PL(float(x) * 100, d)


def _p(x):
    if x is None or pd.isna(x):
        return "brak danych"
    x = float(x)
    return "< 0,001" if x < 0.001 else PL(x, 3)


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def rules_items() -> list[str]:
    a, b, p = T.GTT_BAND["central"]
    return [
        "10. **Czekanie na przesiadkę (dodane po przeglądzie literatury).** Dla każdego ruchu (kierunek przyjazdu A × "
        "kierunek odjazdu B) i każdego rozkładowego przyjazdu A w oknie: czas od przyjazdu A plus dojścia do "
        "najbliższego odjazdu B w tym kierunku (obcięty do 60 min). Na ruch: średnia, mediana i 90. percentyl; na "
        "zespół: mediana i 90. percentyl ważone (każdy przyjazd A z wagą liczby odjazdów B w tym kierunku 6–20, więc "
        "ruch waży przyjazdy A × odjazdy B jak w sumie addytywnej) oraz średnia ważona kursami na tym samym zbiorze "
        "ruchów co suma addytywna. Czas przyjazdu A to przyjazd na pierwszy słupek linii w zespole, czas odjazdu B to "
        "odjazd z ostatniego; przy pełnych minutach w GTFS odjazd B w tej samej minucie co przyjazd A (po dojściu 0) "
        "liczy się jako złapany. Oczekiwane czekanie przy losowym przyjściu (reguła 6) zostaje bez zmian obok.",
        "11. **Uogólniony czas przesiadki (pasmo).** Dojście × a + czekanie × b + stała kara P, w minutach "
        "równoważnych jeździe, z typowej przesiadki 7–9 (składowe addytywne). Wariant niski: a = "
        f"{PL(T.GTT_BAND['low'][0], 2)}, b = {PL(T.GTT_BAND['low'][1], 2)}, P = {T.GTT_BAND['low'][2]:.0f} min; "
        f"środkowy: a = {PL(a, 2)}, b = {PL(b, 2)}, P = {p:.0f} min; wysoki: a = {PL(T.GTT_BAND['high'][0], 2)}, "
        f"b = {PL(T.GTT_BAND['high'][1], 2)}, P = {T.GTT_BAND['high'][2]:.0f} min. Źródła wag: Wardman 1998 (ITS "
        "Leeds WP 525: dojście 1,66, czekanie 1,47 minuty jazdy), Ortelli i in. 2026 (STRC: dojście 1,21, kara "
        "resztowa 5–9 min), Jara-Díaz i in. 2022 (zakres kary do planowania 13–18 min). To przeliczenie składowych "
        "według opublikowanych wag, nie nowy wskaźnik: pasmo stoi obok składowych i nie służy do układania węzłów w "
        "ranking.",
        "12. **Przejścia w skali AMPTI W6.** Każde przejście na dojściu dostaje klasę W6 (Czekała i Bryniarska, "
        "TMiR 6/2017: bezkolizyjne 100 %, z sygnalizacją bez kolizji ze skrętami 70 %, z kolizjami 50 %, zebra bez "
        "sygnalizacji 30 %, niewyznakowane 0 %) według tagów OSM (tabela w sekcji 15). Ruch: średnia z ocenionych "
        "przejść; zespół: średnia ważona kursami po ruchach z co najmniej jednym ocenionym przejściem. OSM nie mówi, "
        "czy sygnalizacja ma kolizje ze skrętami, więc są dwie wartości: z sygnalizacją jako 70 % i jako 50 %. Ruch bez "
        "żadnego przejścia nie ma oceny W6 (jest w zwykłej liczbie przejść jako 0).",
        f"13. **Ruchy „częste × częste”.** Ruch, w którym linia A w swoim kierunku przyjazdu i linia B w swoim kierunku "
        f"odjazdu kursują w godzinach 7–9 średnio co {T.FREQ_HEADWAYS[0]:.0f} min lub częściej (co najmniej 12 kursów "
        f"w 2 h); drugi próg {T.FREQ_HEADWAYS[1]:.0f} min (co najmniej 8 kursów). Udział liczony po ruchach, bez wag.",
        "14. **Test skomunikowań, wersja po przeglądzie.** (a) Test par z reguły 9 ograniczony do par, w których obie "
        "linie kursują średnio co ≥ 15 min (6–20): A na słupku wysiadania, B na słupku wsiadania; wynik po miastach, "
        "rodzajach środków i węzłach z jednostronnym testem dwumianowym wobec 10 % z przypadku. (b) Test pulsu w węźle: "
        f"odjazdy linii kursujących co ≥ 15 min złożone na cykl {T.PULSE_CYCLE_MIN} min (pełne minuty); statystyka = "
        f"udział odjazdów w najgęstszych {T.PULSE_BIN_MIN} kolejnych minutach; rozkład odniesienia = te same rozkłady "
        f"linii przesunięte każdy o losową liczbę minut ({T.PULSE_SIMS} losowań), więc jedna regularna linia ani kilka "
        f"niezależnych nie daje pulsu; puls, gdy wynik przekracza kwantyl {PL(T.PULSE_Q, 2)} odniesienia. Test nie "
        "wymaga dojścia ani czasu przyjazdu. (c) Kontrola dodatnia: oba testy w oknie nocnym 23:00–04:30 dla linii "
        "kursujących tam co 15–60 min.",
        f"15. **Szczegóły węzła na mapę.** Zespoły z co najmniej {T.DETAIL_MIN_DEP_H:.0f} odjazdami na godzinę (6–20), w "
        "FUA i w masce GTFS: słupki, drogi piesze najlepszej pary słupków każdego ruchu (geometria z sieci OSM z "
        "przejściami w klasach W6 i schodami), macierz ruchów i dziesięć najcięższych ruchów (`pipeline/transfer_detail.py`).",
    ]


def known_extension(kn: pd.DataFrame) -> list[str]:
    k = kn[kn.rule == "main"]
    rows = []
    for _, x in k.iterrows():
        if pd.isna(x.get("node_id")):
            rows.append([x.interchange, "nie znaleziono"] + [""] * 10)
            continue
        rows.append([x.interchange, _v(x.wait_w_am_min), _v(x.conn_wait_w_am_min), _v(x.conn_wait_am_median),
                     _v(x.conn_wait_am_p90), _v(x.gtt_low_am_min), _v(x.gtt_central_am_min), _v(x.gtt_high_am_min),
                     _v(x.crossings_w_mean), _v(x.w6_hi_mean, 0), _v(x.w6_lo_mean, 0), _pct(x.freq10_share)])
    return (["**Znane węzły po rewizjach** (7–9; czekanie losowe i na przesiadkę jako średnie ważone kursami na tym "
             "samym zbiorze ruchów, mediana i P90 czekania na przesiadkę ważone, pasmo uogólnionego czasu w minutach "
             "równoważnych jeździe, W6 przy sygnalizacji 70 % i 50 %):", ""]
            + table(["Węzeł", "Czekanie przy losowym przyjściu, min", "Czekanie na przesiadkę, średnia, min",
                     "Czekanie na przesiadkę, mediana, min", "Czekanie na przesiadkę, P90, min",
                     "Uogólniony czas: niski, min", "środkowy, min", "wysoki, min", "Przejścia na ruch, średnia",
                     "W6, % (sygn. 70)", "W6, % (sygn. 50)", "Ruchy częste × częste (≤ 10 min), %"], rows)
            + REV["known"] + [""])


def sections(ctx: dict) -> list[str]:
    cs, ot, rev, det = ctx["city"], ctx["osm"], ctx["rev"], ctx["detail"]

    def city(agg, dom="covered"):
        return cs[(cs.rule == "main") & (cs.agglomeration == agg) & (cs.domain == dom)].iloc[0]

    L = []
    # ---- 13 connection wait
    L += ["## 13. Czekanie na przesiadkę po rzeczywistym przyjeździe (rewizja 1)", "",
          "Reguła 10. Obszar pokryty, 20 zespołów z największą liczbą odjazdów, okno 7–9. Czekanie przy losowym "
          "przyjściu i na przesiadkę to średnie ważone kursami w zespole, potem średnia po zespołach; mediana i P90 to "
          "ważone wartości zespołu, potem mediana po zespołach.", ""]
    rows = []
    for agg in T.AGGS:
        v = city(agg)
        rows.append([N[agg], _v(v.top_add_walk_am), _v(v.top_add_wait_am), _v(v.top_conn_w_am),
                     _v(v.top_conn_delta_am, 2), _v(v.top_conn_med_am), _v(v.top_conn_p90_am)])
    L += table(["Aglomeracja", "Dojście, min", "Czekanie przy losowym przyjściu, min", "Czekanie na przesiadkę, min",
                "Różnica (przesiadka − losowe), min", "Czekanie na przesiadkę: mediana, min",
                "Czekanie na przesiadkę: P90, min"], rows)
    L += REV["conn"] + [""]
    # ---- 14 GTT band
    L += ["## 14. Uogólniony czas przesiadki: pasmo z opublikowanych wag (rewizja 2)", "",
          "Reguła 11. Z typowej przesiadki 7–9 w 20 największych zespołach (te same składowe co w sekcji 3, przed "
          "zaokrągleniem). Kolumny „× waga” pokazują, ile każda składowa wnosi w wariancie środkowym. Wartości nie są "
          "używane do układania węzłów ani miast w ranking.", ""]
    rows = []
    a, b, pen = T.GTT_BAND["central"]
    for agg in T.AGGS:
        v = city(agg)
        wk, wt = v.top_add_walk_am, v.top_add_wait_am
        rows.append([N[agg], _v(wk), _v(wt), _v(wk * a if wk is not None else None),
                     _v(wt * b if wt is not None else None), PL(pen, 0), _v(v.top_gtt_low_am), _v(v.top_gtt_central_am),
                     _v(v.top_gtt_high_am)])
    L += table(["Aglomeracja", "Dojście, min", "Czekanie, min", f"Dojście × {PL(a, 2)}", f"Czekanie × {PL(b, 2)}",
                "Kara P (środkowa), min", "Pasmo: niski, min równoważnych", "środkowy", "wysoki"], rows)
    L += REV["gtt"] + [""]
    # ---- 15 W6
    L += ["## 15. Przejścia w skali AMPTI W6 (rewizja 3)", "",
          "Przypisanie tagów OSM do klas W6 (reguła 12; `pipeline/transfer_walk.py`). Klasa przejścia wynika z tagów "
          "węzłów przejścia i przylegającej drogi `footway=crossing` razem, w tej kolejności:", ""]
    L += table(["Klasa", "W6, %", "Tagi OSM"], [
        ["bezkolizyjne (przejście podziemne, kładka)", "100",
         "ciąg krawędzi pieszych z `tunnel=*` (bez `building_passage`) na drodze; ciąg krawędzi z `bridge=*`, który w "
         "rzucie przecina jezdnię z grafu (chodnik na moście drogowym i kładka nad rzeką się nie liczą)"],
        ["z sygnalizacją", "70 lub 50",
         "`crossing=traffic_signals` / `pelican` / `toucan` / `pegasus`, `crossing:signals=yes`, "
         "`crossing_ref=pelican` / `toucan` / `puffin`, `highway=traffic_signals`"],
        ["zebra bez sygnalizacji", "30",
         "`crossing=marked` / `zebra` / `uncontrolled`, `crossing_ref=zebra`, `crossing:markings=*` inne niż `no`"],
        ["niewyznakowane", "0", "`crossing=unmarked` / `informal`, `crossing:markings=no`"],
        ["nieznane (bez oceny)", "—",
         "przejście przez jezdnię lub torowisko bez żadnej z tych wartości (węzeł bez tagu, `highway=crossing` bez "
         "wartości, przejazd kolejowy bez wartości)"]])
    L += ["Pokrycie: (a) w całym grafie pieszym: odsetek węzłów, w których osobno zmapowany chodnik przecina jezdnię, "
          "z tagiem węzła pozwalającym nadać klasę (bez tagów dróg `footway=crossing`, więc to dolna granica); "
          "(b) na dojściach (reguła główna, obszar pokryty, wszystkie ruchy): rozkład klas przejść.", ""]
    rows = []
    for _, x in ot.iterrows():
        rows.append([N[x.agglomeration], _v(x.share_footway_road_nodes_w6_class),
                     f"{int(x.paths_crossings_n):,}".replace(",", " "), _v(x.paths_x_grade_share),
                     _v(x.paths_x_signal_share), _v(x.paths_x_zebra_share), _v(x.paths_x_unmarked_share),
                     _v(x.paths_x_unknown_share), _v(x.paths_w6_scored_share)])
    L += table(["Aglomeracja", "Graf: węzły chodnik × jezdnia z klasą, %", "Dojścia: przejść (z bezkolizyjnymi)",
                "bezkolizyjne, %", "z sygnalizacją, %", "zebra, %", "niewyznakowane, %", "nieznane, %",
                "z klasą W6, %"], rows)
    rows = []
    for agg in T.AGGS:
        v = city(agg)
        rows.append([N[agg], _v(v.w6_hi, 0), _v(v.w6_lo, 0), _v(v.top_w6_hi, 0), _v(v.top_w6_lo, 0),
                     _v(v.top_cross_dir)])
    L += ["Wynik W6 (średnia po ruchach z ocenionym przejściem, ważona kursami; obszar pokryty i 20 największych "
          "zespołów, średnia wartości zespołów) obok zwykłej mediany liczby przejść:", ""]
    L += table(["Aglomeracja", "W6, %, sygnalizacja 70", "W6, %, sygnalizacja 50", "Top 20: W6, % (70)",
                "Top 20: W6, % (50)", "Top 20: przejścia na ruch, mediana"], rows)
    L += REV["w6"] + [""]
    # ---- 16 frequent pairs
    L += ["## 16. Ruchy „częste × częste” (rewizja 4)", "",
          "Reguła 13. Udział ruchów przesiadkowych (bez wag), w których obie linie kursują w swoich kierunkach w "
          "godzinach 7–9 średnio co 10 (15) min lub częściej; obszar pokryty i 20 największych zespołów.", ""]
    rows = []
    for agg in T.AGGS:
        v = city(agg)
        rows.append([N[agg], f"{int(v.movements_n):,}".replace(",", " ") if v.movements_n is not None else "brak danych",
                     _v(v.freq10_share), _v(v.freq15_share), _v(v.top_freq10_share), _v(v.top_freq15_share)])
    L += table(["Aglomeracja", "Ruchy", "Obie linie co ≤ 10 min, %", "Obie co ≤ 15 min, %", "Top 20: ≤ 10 min, %",
                "Top 20: ≤ 15 min, %"], rows)
    L += REV["freq"] + [""]
    # ---- 17 coordination
    L += ["## 17. Test skomunikowań po przeglądzie (rewizja 5)", "",
          "Reguła 14. (a) Pary, w których obie linie kursują co ≥ 15 min (6–20), obszar pokryty; „w najlepszych 10 %” "
          "= rzeczywisty rozkład daje krótsze czekanie niż co najmniej 90 % przesunięć; bez koordynacji ok. 10 %. "
          "p = jednostronny test dwumianowy (czy udział jest większy niż 10 %).", ""]
    mp = rev["mode_pairs"]
    rows = []
    for agg in T.AGGS:
        x = mp[(mp.agglomeration == agg) & (mp.mode_a == "all")]
        if x.empty:
            rows.append([N[agg], "0", "", "", "", "", ""])
            continue
        x = x.iloc[0]
        rows.append([N[agg], int(x.pairs), _v(x.top10_share), _p(x.p_value), int(x.candidates), _v(x.obs_wait_mean),
                     _v(x.rand_wait_mean)])
    L += table(["Aglomeracja", "Pary (obie linie co ≥ 15 min)", "W najlepszych 10 % przesunięć, %", "p",
                "Kandydaci (reguła 9)", "Czekanie rzeczywiste, średnia, min", "Czekanie przy losowym przyjściu, min"], rows)
    rows = []
    m2 = mp[(mp.mode_a != "all") & (mp.pairs >= 200)].assign(o=lambda d: d.agglomeration.map({a: i for i, a in enumerate(T.AGGS)})).sort_values(["o", "mode_a", "mode_b"])
    for _, x in m2.iterrows():
        rows.append([N[x.agglomeration], f"{MODE_PL.get(x.mode_a, x.mode_a)} → {MODE_PL.get(x.mode_b, x.mode_b)}",
                     int(x.pairs), _v(x.top10_share), _p(x.p_value)])
    L += ["Po rodzajach środków (tylko układy z co najmniej 200 parami; wszystkie w `timed_both15_mode_pairs.csv`):", ""]
    L += table(["Aglomeracja", "Przesiadka", "Pary", "W najlepszych 10 %, %", "p"], rows)
    n15 = rev["nodes15"]
    sig_n = n15[(n15.pairs >= 20)] if len(n15) else n15
    n_test = int(len(sig_n))
    hits = sig_n[sig_n.p_value < 0.001].sort_values(["p_value", "node_id"]) if n_test else sig_n
    L += [f"Węzły z co najmniej 20 parami takich linii: {n_test}; z udziałem istotnie większym niż 10 % (p < 0,001; przy "
          f"{n_test} testach przypadkiem ok. {PL(n_test * 0.001, 1)}): {len(hits)}.", ""]
    if len(hits):
        L += table(["Aglomeracja", "Węzeł", "Pary", "W najlepszych 10 %, %", "p"],
                   [[N[x.agglomeration], str(x["name"]), int(x.pairs), _v(x.top10_share), _p(x.p_value)]
                    for _, x in hits.head(15).iterrows()])
    pu = rev["pulse"]
    rows = []
    for agg in T.AGGS:
        r = [N[agg]]
        for win in ("day", "night"):
            x = pu[(pu.agglomeration == agg) & (pu.win == win)] if len(pu) else pu
            r += [int(len(x)), int(x.pulse.sum()) if len(x) else 0,
                  _v(x.pulse.mean() * 100 if len(x) else None)]
        rows.append(r)
    L += ["(b) Test pulsu w węźle (zespoły z co najmniej 20 odjazdami linii co ≥ 15 min i co najmniej dwiema takimi "
          "liniami; przy braku pulsu ok. 1 % zespołów przekracza próg przypadkiem):", ""]
    L += table(["Aglomeracja", "6–20: zespoły", "z pulsem", "%", "23–04:30: zespoły", "z pulsem", "%"], rows)
    if len(pu):
        top_n = pu[(pu.win == "night") & pu.pulse].sort_values(["n_dep", "agglomeration", "name"],
                                                                ascending=[False, True, True]).head(10)
        L += ["Noc, zespoły z pulsem o największej liczbie odjazdów:", ""]
        L += table(["Aglomeracja", "Zespół", "Odjazdy 23–04:30", "Linie", "Minuta pulsu (cykl 30 min)",
                    "Udział w 3 min, %", "Próg (kwantyl 0,99), %"],
                   [[N[x.agglomeration], str(x["name"]), int(x.n_dep), int(x.n_lines), f":{int(x.peak_minute):02d}",
                     _v(x.max_share * 100), _v(x.null_q * 100)] for _, x in top_n.iterrows()])
        top_d = pu[(pu.win == "day") & pu.pulse].sort_values(["n_dep", "agglomeration", "name"],
                                                              ascending=[False, True, True]).head(10)
        if len(top_d):
            L += ["Dzień, zespoły z pulsem o największej liczbie odjazdów:", ""]
            L += table(["Aglomeracja", "Zespół", "Odjazdy 6–20 (linie co ≥ 15 min)", "Linie", "Minuta pulsu",
                        "Udział w 3 min, %", "Próg, %"],
                       [[N[x.agglomeration], str(x["name"]), int(x.n_dep), int(x.n_lines), f":{int(x.peak_minute):02d}",
                         _v(x.max_share * 100), _v(x.null_q * 100)] for _, x in top_d.iterrows()])
    ng = rev["night"]
    if len(ng):
        allr = ng[ng["name"] == "(wszystkie)"]
        L += ["(c) Kontrola dodatnia, test par w nocy (pary linii nocnych co 15–60 min, okno 23:00–04:30):", ""]
        L += table(["Aglomeracja", "Pary", "W najlepszych 10 %, %", "p", "Czekanie rzeczywiste, min",
                    "Czekanie przy losowym przyjściu, min"],
                   [[N[x.agglomeration], int(x.pairs), _v(x.top10_share), _p(x.p_value), _v(x.obs_wait_mean),
                     _v(x.rand_wait_mean)] for _, x in allr.iterrows()])
        big = ng[(ng["name"] != "(wszystkie)") & (ng.pairs >= 100)].sort_values(["pairs", "name"], ascending=[False, True])
        if len(big):
            L += table(["Aglomeracja", "Zespół (noc)", "Pary", "W najlepszych 10 %, %", "p", "Czekanie rzeczywiste, min",
                        "Czekanie przy losowym przyjściu, min"],
                       [[N[x.agglomeration], str(x["name"]), int(x.pairs), _v(x.top10_share), _p(x.p_value),
                         _v(x.obs_wait_mean), _v(x.rand_wait_mean)] for _, x in big.head(10).iterrows()])
    L += REV["timed"] + [""]
    # ---- 18 detail export
    L += ["## 18. Szczegóły węzłów na mapę", "",
          f"Zespoły z co najmniej {T.DETAIL_MIN_DEP_H:.0f} odjazdami na godzinę 6–20 w FUA i w masce GTFS, z co najmniej "
          "jednym ruchem między liniami; plik na aglomerację `results/web/transfer_detail/<agg>.json` i indeks "
          "`index.json` (format w docstringu `pipeline/transfer_detail.py`).", ""]
    tot_n = sum(v["nodes"] for v in det.values())
    tot_b = sum(v["bytes"] for v in det.values())
    L += table(["Aglomeracja", "Zespoły", "Drogi piesze", "Ruchy w macierzach", "Rozmiar, MB"],
               [[N[a], det[a]["nodes"], det[a]["paths"], det[a]["movements"], PL(det[a]["bytes"] / 1e6, 2)]
                for a in T.AGGS if a in det] + [["Razem", tot_n, sum(v["paths"] for v in det.values()),
                                                 sum(v["movements"] for v in det.values()), PL(tot_b / 1e6, 2)]])
    L += REV["detail"] + [""]
    return L
