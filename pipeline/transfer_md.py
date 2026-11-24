"""Polish QA note of the transfer-ease step: results/qa/transfer/transfer.md (pipeline.transfer_ease)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline import transfer_ease as T
from pipeline import transfer_report as TR
from pipeline import transfer_walk as W
from pipeline.transfer_text import (AMPTI, CHECKS, CRITICAL, INTRO, LIMITS, NOT_VERIFIED, SAMPLE, STATIONS, TIMED,
                                    RULE_CHOICE, RULE_FAILS)

PL = TR._pl
N = TR.NAMES


def _v(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)) or (not isinstance(x, str) and pd.isna(x)):
        return "brak danych"
    return PL(float(x), d)


def _pct(x, d=0):
    return "brak danych" if x is None or pd.isna(x) else PL(float(x) * 100, d)


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def write_md(ctx: dict) -> None:
    cs, kn, ot, tm = ctx["city"], ctx["known"], ctx["osm"], ctx["timed"]
    main = ctx["tabs"]["nodes"]["main"]
    L = ["# Łatwość przesiadki w zespołach przystanków (warstwa dodatkowa, 2026-11-24)", ""]
    L += INTRO + [""]
    L += ["## 1. Dane i daty", "",
          f"- Rozkłady: środa {T.DAY}, wszystkie feedy (wariant „all”), kursy po regułach `pipeline/gtfs_service.py` "
          "(deduplikacja, przycięcie kolei).",
          "- Sieć piesza: OSM 2026-11-22, graf z `pipeline/walk_network.py`; tagi przejść, sygnalizacji, tuneli i kładek "
          "z tego samego pliku PBF (`pipeline/transfer_osm.py`, jedno przejście, wynik w `data/interim/transfer/`).",
          "- Zespoły przystanków bazują na klastrach 100 m z kroku częstej komunikacji (`frequent.clusters`).",
          "- Maska pokrycia GTFS: `results/layers/gtfs_coverage_mask.parquet`, wariant „all”. Zespół poza maską ma "
          "wszystkie składowe puste (brak danych), nigdy 0.",
          "- Ludność nie jest używana; pola daty ludności w metrykach są puste.", ""]
    L += ["## 2. Reguły (wszystkie ustalone w tym kroku)", ""]
    r = T.RULES["main"]
    L += [f"1. **Zespół przystanków do przesiadki.** Klastry 100 m łączone, gdy najbliższe słupki dwóch klastrów są "
          f"≤ {r['link_m']:.0f} m od siebie w linii prostej (≤ {r['link_rail_m']:.0f} m, jeśli jeden z klastrów ma "
          f"odjazdy kolei lub metra). Grupa szersza niż {r['dmax_m']:.0f} m (z koleją lub metrem: "
          f"{r['dmax_rail_m']:.0f} m) między środkami klastrów jest dzielona metodą pełnego wiązania, więc zespół nie "
          "rozciąga się łańcuchem wzdłuż ulicy."] + ["   " + x for x in RULE_CHOICE]
    L += [f"2. **Linia.** Feed + rodzaj środka + `route_short_name`. W feedzie kolejowym, gdzie `route_short_name` jest "
          "kategorią pociągu bez numeru (IC, TLK, EIP, ...), linią jest para stacji końcowych kursu. Linia liczy się w "
          f"zespole, jeśli ma tam co najmniej {T.MIN_LINE_EVENTS} odjazdów (do wsiadania) albo przyjazdów (do "
          "wysiadania) w oknie 6–20, czyli średnio co najmniej jeden na 2 godziny.",
          f"3. **Para przesiadkowa.** Uporządkowana para (A przyjeżdża, B odjeżdża), A ≠ B. Pomijane są pary linii "
          f"„równoległych”: jeśli co najmniej {T.PARALLEL_SHARE * 100:.0f} % zespołów przystanków krótszej z nich (cały dzień) "
          "obsługuje też druga linia (warianty tej samej linii, kursy skrócone, linie o prawie wspólnej trasie).",
          "4. **Dojście.** Dla każdej pary najlepsza para słupków (wysiadanie z A, wsiadanie do B) wg najkrótszej drogi "
          f"po sieci pieszej OSM; {T.WALK_KMH:.0f} km/h, bez kary za przejścia i schody. Przystanki przypięte do najbliższej "
          f"krawędzi sieci (do {T.STOP_MAX_SNAP_M['default']:.0f} m, stacje do {T.STOP_MAX_SNAP_M['rail']:.0f} m), tak jak w "
          f"kroku częstej komunikacji. Ten sam słupek = 0 min. Współczynnik wydłużenia = droga po sieci / odległość w "
          f"linii prostej (tylko pary oddalone o ≥ {T.DETOUR_MIN_STRAIGHT_M:.0f} m). Mediana i 90. percentyl po parach.",
          "   **Dojście z kierunkami (wariant dodany w tym kroku, podstawa miar głównych).** Najlepsza para słupków "
          "zwykle trafia na wspólny słupek dwóch linii jadących dalej tą samą ulicą, więc mediana wychodzi bliska 0 "
          "prawie wszędzie i nie różnicuje węzłów. Wariant z kierunkami bierze każdy główny kierunek przyjazdu A "
          f"(poprzedni zespół na trasie, ≥ {T.MAIN_DIR_SHARE * 100:.0f} % przyjazdów) i każdy główny kierunek odjazdu B "
          "(następny zespół); ruch jest pomijany, gdy B odjeżdża tam, dokąd A i tak jedzie dalej (przesiadka zbędna), "
          "albo wraca tam, skąd A przyjechała. Dla każdego ruchu najlepsza para słupków tego kierunku; wartość pary "
          "linii = średnia po ruchach (pasażer potrzebuje któregoś kierunku, nie wiadomo którego). Przejścia, schody i "
          "dojście bez schodów liczone tak samo po ruchach.",
          f"5. **Przeszkody na dojściu.** Przejście przez jezdnię lub torowisko: węzeł ścieżki leżący na jezdni "
          "(drogi od `residential` wzwyż, bez `service`) lub na torach tramwaju albo kolei, w którym ścieżka przecina, a "
          "nie biegnie wzdłuż (obie sąsiednie krawędzie ścieżki nie są jezdnią), albo węzeł z tagiem przejścia. Zdarzenia "
          f"bliżej niż {W.GROUP_GAP_M:.0f} m od siebie to jedno przejście (dwie jezdnie i torowisko). Sygnalizacja: "
          "`crossing=traffic_signals`, `crossing:signals=yes`, `highway=traffic_signals` na węźle lub ta sama wartość na "
          "drodze `footway=crossing`. Schody: `highway=steps` i schody ruchome; tunel: droga piesza z `tunnel=*` (bez "
          "`building_passage`); kładka: droga piesza z `bridge=*`, która nie jest jezdnią (chodnik zmapowany osobno na "
          "moście drogowym też się liczy). Dojście bez schodów: najkrótsza droga w sieci bez schodów (windy zmapowane jako "
          "węzeł przechodzą).",
          f"6. **Czekanie.** Oczekiwane czekanie na linię B dla pasażera przychodzącego w losowej chwili okna (7–9 i "
          f"6–20), z rzeczywistych godzin odjazdów B w zespole (próbkowanie co {T.WAIT_STEP_S} s; czekanie obcięte do "
          f"{T.WAIT_CAP_MIN:.0f} min), osobno dla każdego kierunku (następny zespół na trasie) i uśrednione po głównych "
          f"kierunkach B (≥ {T.MAIN_DIR_SHARE * 100:.0f} % jej odjazdów). Przy kursach równomiernych to połowa odstępu; "
          "nieregularność je wydłuża. Rozkłady podają pełne minuty i nie mają czasu postoju, więc to nie jest precyzja "
          "skomunikowania co do minuty. Dojście + czekanie: suma dla pary, potem mediana po parach; obok mediana ważona "
          "liczbą kursów (przyjazdy A × odjazdy B), bo rzadkie linie liczą się w zwykłej medianie tak samo jak częste.",
          "7. **Znaczenie węzła.** Linie, pary, odjazdy na godzinę (wszystkie linie, 6–20 i 7–9).",
          "8. **Kolej i metro.** " + STATIONS,
          "9. **Możliwe skomunikowania (przybliżone).** " + TIMED, ""]
    # ---- city table
    L += ["## 3. Wyniki dla miast (reguła główna)", "",
          f"„Łatwe” = mediana dojścia między liniami ≤ {TR.WALK_EASY_MIN:.0f} min; udział liczony po odjazdach 6–20 "
          f"wszystkich zespołów przesiadkowych w obszarze. „Top {TR.TOPN}” = {TR.TOPN} zespołów z największą liczbą "
          "odjazdów w obszarze; wartość = mediana median węzłów. Obszar pokryty = zespoły w FUA i w masce GTFS.", ""]
    rows = []
    for agg in T.AGGS:
        for dom in ("core", "covered"):
            v = cs[(cs.rule == "main") & (cs.agglomeration == agg) & (cs.domain == dom)].iloc[0]
            rows.append([N[agg] if dom == "core" else "", "rdzeń" if dom == "core" else "pokryty", int(v.nodes_n),
                         _v(v.dep_share_walkdir_le2), _v(v.dep_share_walkdir_gt5), _v(v.top_walk_dir),
                         _v(v.top_cross_dir), _v(v.top_wait_am), _v(v.top_ww_dir_am), _v(v.top_ww_am_w),
                         _v(v.top_stepfree_share, 0), _v(v.dep_share_walk_le2), _v(v.top_walk),
                         _v(v.same_stop_share, 0), _v(v.coverage * 100 if v.coverage is not None else None, 1)])
    L += table(["Aglomeracja", "Obszar", "Zespoły", "Odjazdy w zespołach „łatwych”, %",
                "Odjazdy w zespołach z dojściem > 5 min, %", f"Top {TR.TOPN}: dojście, min", f"Top {TR.TOPN}: przejścia",
                f"Top {TR.TOPN}: czekanie 7–9, min", f"Top {TR.TOPN}: dojście + czekanie 7–9, min",
                f"Top {TR.TOPN}: to samo, najlepsza para, ważone kursami, min", f"Top {TR.TOPN}: pary bez schodów, %",
                "Najlepsza para słupków: odjazdy w zespołach „łatwych”, %", f"Najlepsza para: top {TR.TOPN} dojście, min",
                "Pary na tym samym słupku, %", "Odjazdy zespołów w masce, %"], rows)
    L += CRITICAL["cities"] + [""]
    # ---- known interchanges
    L += ["## 4. Znane węzły: kontrola", "",
          "Dla każdego węzła wybrano zespół o największej liczbie odjazdów, którego nazwy pasują do wzorca i którego "
          f"środek leży ≤ {TR.KNOWN_RADIUS_M:.0f} m od punktu orientacyjnego (`transfer_report.KNOWN`). Wszystkie kolumny: "
          "`known_interchanges.csv`; pary linii: `pairs_known_interchanges.csv`.", ""]
    k = kn[kn.rule == "main"]
    rows, rows2 = [], []
    for _, x in k.iterrows():
        if pd.isna(x.get("node_id")):
            rows.append([N[x.agglomeration], x.interchange, "nie znaleziono"] + [""] * 9)
            rows2.append([x.interchange, "nie znaleziono"] + [""] * 9)
            continue
        rows.append([N[x.agglomeration], x.interchange, str(x["name"]), int(x.n_stops), _v(x.diameter_m, 0),
                     x.modes.replace(",", ", "), int(x.n_lines), int(x.n_pairs), _v(x.dep_per_h_day, 0),
                     _v(x.walk_min_median), _v(x.walk_dir_min_median), _v(x.walk_dir_min_p90)])
        rows2.append([x.interchange, _v(x.crossings_dir_median, 1), _pct(x.crossings_signal_share), _pct(x.steps_dir_share),
                      _pct(x.stepfree_dir_share), _pct(x.tunnel_pair_share), _v(x.wait_am_median),
                      _v(x.walkwait_dir_am_median), _v(x.walkwait_am_median_w), _v(x.stops_mean_walk_m, 0),
                      f"{int(x.timed_pairs)} / {int(x.timed_pairs_checked)}"])
    L += table(["Miasto", "Węzeł", "Zespół (nazwa wiodąca)", "Słupki", "Rozpiętość, m", "Środki", "Linie", "Pary",
                "Odjazdy/h 6–20", "Dojście, najlepsza para: mediana, min", "Dojście z kierunkami: mediana, min",
                "Dojście z kierunkami: P90, min"], rows)
    L += table(["Węzeł", "Przejścia (z kierunkami): mediana", "Przejścia z sygnalizacją, %", "Ruchy ze schodami, %",
                "Ruchy z dojściem bez schodów w OSM, %", "Pary z tunelem, %", "Czekanie 7–9: mediana, min",
                "Dojście z kierunkami + czekanie 7–9, min", "Najlepsza para + czekanie, ważone kursami, min",
                "Średnia odległość między słupkami po sieci, m", "Możliwe skomunikowania / pary sprawdzone"], rows2)
    L += CHECKS + [""]
    # ---- AMPTI
    L += ["## 5. Porównanie z oceną AMPTI dla Krakowa", ""] + AMPTI(kn) + [""]
    # ---- sensitivity
    L += ["## 6. Wrażliwość na regułę zespołu", "",
          "Trzy reguły: główna; „klastry 100 m” (bez łączenia, czyli zespoły = klastry z kroku częstej komunikacji); "
          f"„szeroka” ({T.RULES['wide']['link_m']:.0f} / {T.RULES['wide']['link_rail_m']:.0f} m łączenia, rozpiętość "
          f"do {T.RULES['wide']['dmax_m']:.0f} / {T.RULES['wide']['dmax_rail_m']:.0f} m). Obszar pokryty.", ""]
    rows = []
    for agg in T.AGGS:
        for rn, lab in (("clusters100", "klastry 100 m"), ("main", "główna"), ("wide", "szeroka")):
            v = cs[(cs.rule == rn) & (cs.agglomeration == agg) & (cs.domain == "covered")].iloc[0]
            rows.append([N[agg] if rn == "clusters100" else "", lab, int(v.nodes_n), _v(v.dep_share_walkdir_le2),
                         _v(v.top_walk_dir), _v(v.top_ww_dir_am), _v(v.dep_share_walk_le2), _v(v.same_stop_share, 0)])
    L += table(["Aglomeracja", "Reguła", "Zespoły", "Odjazdy w zespołach „łatwych”, %", f"Top {TR.TOPN}: dojście, min",
                f"Top {TR.TOPN}: dojście + czekanie 7–9, min", "Najlepsza para: odjazdy w zespołach „łatwych”, %",
                "Pary na tym samym słupku, %"], rows)
    rows = []
    for lab in [x[1] for x in TR.KNOWN]:
        rr = []
        for rn in ("clusters100", "main", "wide"):
            x = kn[(kn.interchange == lab) & (kn.rule == rn)].iloc[0]
            rr += ["—" if pd.isna(x.get("node_id")) else
                   f"{int(x.n_stops)} / {_v(x.walk_dir_min_median)} / {_v(x.walkwait_dir_am_median)}"]
        rows.append([lab] + rr)
    L += ["Znane węzły: słupki / dojście z kierunkami (mediana, min) / dojście z kierunkami + czekanie 7–9 (min):", ""]
    L += table(["Węzeł", "klastry 100 m", "główna", "szeroka"], rows)
    L += RULE_FAILS + [""]
    # ---- OSM tags
    L += ["## 7. Kompletność tagów OSM", "",
          "Dwie miary: (a) w całym grafie pieszym aglomeracji: węzły, w których osobno zmapowany chodnik lub ścieżka "
          "przecina jezdnię (węzeł na jezdni z co najmniej dwiema krawędziami pieszymi), i jaki ich odsetek ma tag "
          "przejścia; odsetek węzłów `highway=crossing` z wartością `crossing=*`; (b) na policzonych dojściach "
          "(reguła główna, obszar pokryty): odsetek przejść z wartością `crossing=*` lub sygnalizacją i odsetek długości "
          "dojść prowadzonych osią jezdni.", ""]
    rows = []
    for _, x in ot.iterrows():
        rows.append([N[x.agglomeration], f"{int(x.footway_road_nodes):,}".replace(",", " "),
                     _v(x.share_footway_road_nodes_tagged), _v(x.share_footway_road_nodes_with_value),
                     f"{int(x.highway_crossing_nodes):,}".replace(",", " "), _v(x.share_highway_crossing_with_value),
                     _v(x.paths_crossing_value_share), _v(x.paths_crossing_signal_share), _v(x.paths_road_centerline_share),
                     f"{int(x.elevator_nodes)}", _v(x.share_elevator_dead_end)])
    L += table(["Aglomeracja", "Węzły chodnik × jezdnia", "z tagiem przejścia, %", "z wartością crossing / sygnalizacją, %",
                "Węzły highway=crossing", "z crossing=*, %", "Dojścia: przejścia z wartością, %",
                "Dojścia: przejścia z sygnalizacją, %", "Dojścia: długość osią jezdni, %", "Windy (węzły) w grafie",
                "Windy bez połączenia z drugim poziomem, %"], rows)
    L += CRITICAL["osm"] + [""]
    # ---- timed
    L += ["## 8. Możliwe skomunikowania (przybliżone)", ""]
    tt = []
    for R in ctx["results"]:
        t = R["rules"]["main"]["timed"]
        tt.append([N[R["agg"]], len(t), int(t.timed.sum()) if len(t) else 0,
                   _v(t.timed.mean() * 100 if len(t) else None), _v((t["rank"] <= 0.1).mean() * 100 if len(t) else None)])
    L += table(["Aglomeracja", "Pary sprawdzone (linia B co ≥ 15 min)", "Kandydaci", "Kandydaci, %",
                "Pary w najlepszych 10 % przesunięć, %"], tt)
    L += CRITICAL["timed"] + [""]
    # ---- sample of phase 3
    L += ["## 9. Próba przesiadek z fazy 3", ""] + SAMPLE + [""]
    L += ["## 10. Ograniczenia", ""] + LIMITS + [""]
    L += ["## 11. Nie zweryfikowano", ""] + NOT_VERIFIED + [""]
    L += ["## 12. Pliki i czas", "",
          f"- Warstwa: `results/layers/transfer_nodes.parquet` ({ctx['n_layer']} zespołów w FUA, EPSG:4326, punkt = średnia "
          "położeń słupków zespołu); opis pól w `results/layers/_meta_transfer.json`.",
          "- Metryki: `results/metrics/metrics_transfer.csv` / `.json` (format pozostałych kroków; jeszcze nie w "
          "`metrics.csv`, bo `merge_metrics` nie został zmieniony).",
          "- Tabele w tym katalogu: `known_interchanges.csv`, `known_interchanges_rules.csv`, "
          "`pairs_known_interchanges.csv`, `city_summary_rules.csv`, `osm_tag_completeness.csv`, `top_nodes.csv`, "
          "`timed_connections_possible.csv`.",
          "- Kod: `pipeline/transfer_ease.py`, `transfer_osm.py`, `transfer_walk.py`, `transfer_report.py`, "
          "`transfer_md.py`, `transfer_text.py`; reguła `transfer_ease` w `Snakefile`.",
          "- Czas obliczeń: w `_meta.json` tego katalogu (`seconds_per_agglomeration`, `duration_s`); nie w tej "
          "nocie, żeby była identyczna przy każdym przebiegu.", ""]
    T.QA.mkdir(parents=True, exist_ok=True)
    (T.QA / "transfer.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
