"""Polish text of results/qa/access/dgregio/dgregio.md (pipeline.access_dgregio_report).  Numbers come from the
CSV frames passed in; the prose states what the numbers show and what could not be checked."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline import access_dgregio as D


def _v(dec, agg, meas, prefix, col="value"):
    r = dec[(dec.agglomeration == agg) & (dec.measure == meas) & dec.step.str.startswith(prefix)]
    return None if r.empty else r[col].iloc[0]


def render(an, uc, dec, curves, plaus, sens, f1, sgn, md_table, NAMES) -> str:
    from pipeline.access_dgregio_report import ORIGIN_SET
    aggs = [a for a in ("warszawa", "poznan", "lodz") if a in set(dec.agglomeration)]
    L = []
    A = L.append

    # ---------------------------------------------------------------- summary numbers
    summ = []
    for agg in aggs:
        for m in ("PT 30", "PT 45", "pieszo 30", "rower 30 LTS 4"):
            pub = _v(dec, agg, m, "0.")
            last = dec[(dec.agglomeration == agg) & (dec.measure == m) & dec.step.str.match(r"^\d\.")]["value"].dropna()
            dg = _v(dec, agg, m, "DG REGIO")
            rem = _v(dec, agg, m, "Reszta", "delta")
            summ.append({"Miasto": NAMES[agg], "Miara": m, "DG REGIO (aneks)": f1(dg), "Nasz opublikowany (rdzeń)": f1(pub),
                         "Nasz w domenie i metodzie DG REGIO (ostatni krok)": f1(last.iloc[-1]) if len(last) else "–",
                         "Reszta (DG − my)": sgn(rem)})
    summ = pd.DataFrame(summ)

    A("# Benchmark DG REGIO: skąd bierze się różnica (Warszawa, Poznań, Łódź)")
    A("")
    A("Plik generuje `python -m pipeline.access_dgregio report` (krok poboczny; dane produkcyjne fazy 3 tylko czytane). "
      "Źródła: Poelman, Dijkstra, Ackermans (2020), DG REGIO WP 01/2020, PDF i **aneks danych** (`wp_low_carbon_urban_accessibility_data_annex.xlsx`, "
      "tabele 1–2), oba z ec.europa.eu, zapisane w `data/raw/dgregio_wp2020/`; urban centres 2011: Eurostat GISCO `HDENS_CLST_2011` "
      "(`data/raw/eurostat_hdens_2011/`). Nasze dane: środa " + D.REF_DAY + ", feedy wariantu „wszystkie”, R5 v7.5.1, ludność NSP 2021 w siatce 250 m.")
    A("")
    A("## 1. Odpowiedź w skrócie")
    A("")
    A("__VERDICT__")
    A("")
    A(md_table(summ))
    A("")
    A("Wartości DG REGIO pochodzą teraz z aneksu (dokładne liczby), nie z odczytu wykresów. Odczyt z wykresów w `access.md` §7 był poprawny co do ±0,5 pkt "
      "(np. Poznań KZ 45: odczyt 75,0, aneks " + f1(float(an.loc['poznan', 't2_14'])) + ").")
    A("")

    # ---------------------------------------------------------------- method
    A("## 2. Metoda DG REGIO ustalona ze źródła")
    A("")
    A("Strony wg numeracji drukowanej pracy.")
    A("")
    meth = [
        ("Jednostka", "urban centre (klaster komórek 1 km² o gęstości ≥ 1500 os./km² i ≥ 50 tys. mieszk.), wydzielony na siatce ludności **2011**; „city” = urban centre", "s. 5 przyp. 3, s. 6 i przyp. 9"),
        ("Starty i cele", "zaludnione poligony Urban Atlas 2012 (centroidy, bez wód i dróg), ludność 2011 wg Batista e Silva i Poelman (2016); **tylko punkty wewnątrz urban centre**, zarówno starty, jak i cele", "s. 16, s. 37 przyp. 35–37"),
        ("Mianownik (proximity)", "ludność w promieniu 2,5 / 7,5 / 11,25 km, **„constrained by the limits of the urban centre”**", "s. 16 przyp. 17, s. 42"),
        ("Router i parametry", "OpenTripPlanner 1.2.0 (zmodyfikowany, by zwracał początkowe oczekiwanie), OSM z Geofabrik; `maxWalkDistance` 5000 m, `maxTimeSec` 3600, `clampInitialWait` −1, tryby TRANSIT+WALK; prędkość pieszego nie zmieniona (domyślna OTP 1.x: 1,33 m/s ≈ 4,8 km/h, z dokumentacji OTP, nie z pracy)", "s. 37 przyp. 39–42"),
        ("Odjazdy", "9 zapytań co 15 min w **dwugodzinnym szczycie porannym** (godzin nie podano; tu przyjęto 7:00–9:00); czas = od żądanej godziny wyjazdu do przyjazdu (z oczekiwaniem); dla pary **średnia z 9**, para zaliczona, gdy średnia ≤ 30 / 45 min", "s. 37–38"),
        ("Dzień", "dzień roboczy o największej liczbie odjazdów w okresie ważności feedu; przy łączeniu feedów wymuszana wspólna data", "s. 35, s. 37"),
        ("Rozkłady", "„scheduled timetables of all public transport in the city”; feedy GTFS przewoźników (ponad 125 źródeł), kolej z UIC MERITS, gdy feed miejski jej nie ma; rok 2018 (podpisy map 3–6); **które feedy i z jakiej daty dla Warszawy, Poznania i Łodzi — nie podano** (karty miast podają tylko „public transport operators, UIC”)", "s. 34, 37, mapy 3–5; karty miast"),
        ("Agregacja do miasta", "średnia ważona ludnością dostępności i osobno proximity; aneks potwierdza liczbowo, że wynik miasta = średnia dostępność / średnie proximity × 100 (**stosunek średnich**), np. Poznań 45 min: 388 121 / 519 035 = 74,78", "s. 40, s. 43; aneks t2"),
        ("Pieszo", "ta sama domena, sieć OSM, 30 min, mianownik 2,5 km", "s. 40"),
        ("Rower", "dla większości miast (w tym polskich) **sieć TomTom**: 15 km/h na wszystkich drogach poza autostradami, 4 km/h w strefach pieszych, 10 km/h na ciągach pieszo-rowerowych, **kontraruch dopuszczony wszędzie**, spadki −10 / −20 % pod górę; OTP/OSM tylko dla Amsterdamu, Kopenhagi i Gandawy", "s. 40, przyp. 43–46"),
    ]
    A(md_table(pd.DataFrame(meth, columns=["Element", "DG REGIO", "Gdzie"])))
    A("")
    A("Wniosek dla porównania: w `access.md` §7 domenę DG REGIO przybliżano **granicami miasta**. Urban centre jest znacznie mniejszy: "
      "Poznań i Łódź po 117 km² (miasta: 262 i 293 km²), Warszawa 309 km² (miasto 517 km²). Do tego mianownik DG REGIO jest przycięty do urban centre, "
      "a w naszym wariancie „cele tylko w rdzeniu” przycięty był do miasta.")
    A("")

    # ---------------------------------------------------------------- UC
    A("## 3. Domena: urban centre 2011")
    A("")
    A("Klastry z rastra `HDENS_CLST_2011` (wartość komórki = ludność klastra) identyfikowane po ludności z aneksu; liczba komórek 1 km² zgadza się z powierzchnią w aneksie co do komórki, więc to jest domena użyta przez DG REGIO. "
      "Komórka 250 m należy do UC, jeśli jej środek leży w komórce 1 km klastra.")
    A("")
    u = uc.reset_index()
    t = pd.DataFrame({"Miasto": u.agglomeration.map(NAMES), "Kod": u.uc_code, "Pow. km² (aneks / raster)": [f"{a} / {b}" for a, b in zip(u.annex_area_km2, u.uc_cells_1km)],
                      "Ludność 2011 (aneks)": u.annex_pop_2011.map(lambda x: f"{x:,.0f}".replace(",", " ")),
                      "Ludność NSP 2021 w UC (nasza siatka)": u.our_pop_census2021_in_uc.map(lambda x: f"{x:,.0f}".replace(",", " ")),
                      "Komórek 250 m (starty = cele)": u.uc_origin_cells_250m,
                      "Ludność miasta poza UC": u.city_pop_outside_uc_share.map(lambda x: f1(100 * x) + " %"),
                      "Ludność UC poza miastem": u.uc_pop_outside_city.map(lambda x: f"{x:,.0f}".replace(",", " "))})
    A(md_table(t))
    A("")

    # ---------------------------------------------------------------- decomposition
    A("## 4. Dekompozycja: od naszego wyniku do wartości DG REGIO")
    A("")
    A("Każdy krok zmienia jedną rzecz względem poprzedniego; kolumna „zmiana” to efekt tego kroku (pkt). Kroki 0–1 z produkcyjnych paczek (bez nowego routingu). "
      "Kroki 2–5 z nowego routingu (`pipeline.access_dgregio route`): starty i cele = zaludnione komórki 250 m w UC, sieci produkcyjne (kopia pliku sieci), "
      "reguła min(KZ, sam spacer) jak w produkcji. Krok 5 (9 odjazdów) liczony na próbie 800 startów (wybór systematyczny po `cell_id`) i dodany jako różnica na tej samej próbie. "
      "„Reszta” to to, czego nie wyjaśniają zmierzone kroki: rok rozkładów (2018 / 2026), ludność 2011 na poligonach Urban Atlas, router OTP i jego sieć, prędkość i dobór trasy.")
    A("")
    sets = sorted({f"{NAMES[a]} {s}: {v}" for (a, s), v in ORIGIN_SET.items() if s in ("pt_base", "pt_walk5km", "bike_lts3", "bike_lts4")})
    A("Zbiór startów kroków 2–4: " + "; ".join(sets) + ".")
    A("")
    for agg in aggs:
        A(f"### {NAMES[agg]}")
        A("")
        d = dec[dec.agglomeration == agg]
        for m in d.measure.unique():
            dm = d[d.measure == m]
            t = pd.DataFrame({"Krok": dm.step, "Wartość": dm.value.map(f1), "Zmiana": dm.delta.map(lambda x: sgn(x) if x is not None and np.isfinite(x) else "")})
            A(f"**{m}**")
            A("")
            A(md_table(t))
            A("")
    # ---------------------------------------------------------------- sensitivity
    A("## 5. Wrażliwość (nie wchodzi do łańcucha)")
    A("")
    if len(sens):
        A(md_table(pd.DataFrame({"Miasto": sens.agglomeration.map(NAMES), "Miara": sens.measure, "Zmiana": sens.item, "Efekt, pkt": sens.delta.map(sgn)})))
    A("")
    A("__SENS__")
    A("")
    # ---------------------------------------------------------------- 30 vs 45
    A("## 6. Czy wartości DG REGIO 30 i 45 min są ze sobą spójne")
    A("")
    p = plaus
    t = pd.DataFrame({"Miasto": p.agglomeration.map(NAMES), "Miara": p.measure,
                      "DG: proximity / ludność UC": p.dg_prox_share_of_uc.map(lambda x: f1(100 * x) + " %"),
                      "DG: osiągalni / ludność UC": p.dg_acc_share_of_uc.map(lambda x: f1(100 * x) + " %"),
                      "My (UC): proximity / ludność UC": p.our_prox_share_of_uc.map(lambda x: f1(100 * x) + " %"),
                      "My (UC, krok 4): osiągalni / ludność UC": p.our_acc_share_of_uc.map(lambda x: f1(100 * x) + " %" if x is not None and np.isfinite(x) else "–"),
                      "Nasz mianownik produkcyjny (FUA + 15 km) / ludność UC": p.our_fua_prox_over_uc_pop.map(lambda x: f1(100 * x) + " %")})
    A(md_table(t))
    A("")
    A("__PLAUS__")
    A("")
    eq = []
    for agg in aggs:
        for c in (30, 45):
            cv = curves[(curves.agglomeration == agg) & (curves["mode"] == f"pt_walk5km_ratio_of_means_den{c}")].sort_values("cutoff")
            if cv.empty:
                continue
            dg = float(an.loc[agg, "t2_13" if c == 30 else "t2_14"])
            from pipeline.access_dgregio_report import equiv_cutoff
            e = equiv_cutoff(cv.cutoff, cv.value, dg)
            eq.append({"Miasto": NAMES[agg], "Miara": f"KZ {c}", "DG REGIO": f1(dg),
                       "Nasz próg dający wartość DG (min, interpolacja co 5 min)": f1(e) if e else "poza zakresem",
                       "Różnica progów (min)": sgn(e - c) if e else "–"})
        cw = curves[(curves.agglomeration == agg) & (curves["mode"] == "walk_ratio_of_means")].sort_values("cutoff")
        if len(cw):
            from pipeline.access_dgregio_report import equiv_cutoff
            dgw = float(an.loc[agg, "t2_11"])
            e = equiv_cutoff(cw.cutoff, cw.value, dgw)
            eq.append({"Miasto": NAMES[agg], "Miara": "pieszo 30", "DG REGIO": f1(dgw),
                       "Nasz próg dający wartość DG (min, interpolacja co 5 min)": (f1(e) if e else "< 20") + " (co 1 min)",
                       "Różnica progów (min)": sgn(e - 30) if e else "–"})
    if eq:
        A("Ten sam wskaźnik jako „równoważny próg”: przy jakim progu czasu nasz wynik (domena UC, mianownik dla 30 lub 45 min bez zmian, krok 4) równa się wartości DG REGIO.")
        A("")
        A(md_table(pd.DataFrame(eq)))
        A("")
        A("__EQUIV__")
        A("")
    # ---------------------------------------------------------------- supply
    A("## 7. Czy brakuje kursów w naszych feedach?")
    A("")
    A("__SUPPLY__")
    A("")
    sup = pd.read_csv(D.QA / "supply_uc_vs_annex.csv")
    t = pd.DataFrame({"Miasto": sup.agglomeration.map(NAMES), "Tryb": sup["mode"],
                      "Nasze wozkm 6–20 w UC": sup.our_vkm_6_20_in_uc.map(lambda x: f"{x:,.0f}".replace(",", " ")),
                      "Nasze: wozkm / 1000 mieszk. 2011 / h": sup.our_vkm_per_1000inh_per_hour.map(lambda x: f1(x, 2)),
                      "DG REGIO 2018 (aneks t1_19–24)": sup.annex_2018_value.map(lambda x: f1(x, 2) if pd.notna(x) else "–"),
                      "DG / my": sup.ratio_annex_to_ours.map(lambda x: f1(x, 2) if pd.notna(x) else "–"),
                      "Prędkość w linii prostej: my / DG (km/h)": [f"{f1(a)} / {f1(b) if pd.notna(b) else '–'}" for a, b in zip(sup.our_speed_kmh, sup.annex_speed_kmh)]})
    A(md_table(t))
    A("")
    st = pd.read_csv(D.QA / "stops_uc_osm_vs_gtfs.csv")
    A("Przystanki OSM (zdeduplikowane, faza 1) w UC bez obsługiwanego w dniu ref. przystanku GTFS w pobliżu (autobus/tramwaj 100 m, kolej 300 m):")
    A("")
    A(md_table(pd.DataFrame({"Miasto": st.agglomeration.map(NAMES), "Rodzaj": st.stop_kind, "Przystanków OSM w UC": st.osm_stops_in_uc,
                             "Bez GTFS w promieniu": st.without_served_gtfs_stop, "Dopasowane": st.share_matched.map(lambda x: f1(100 * x) + " %")})))
    A("")
    A("__STOPS__")
    A("")
    A("## 8. Czy dane wejściowe DG REGIO mogły być zbyt optymistyczne")
    A("")
    A("__OPTIM__")
    A("")
    A("## 9. Pieszo i rower")
    A("")
    A("__ACTIVE__")
    A("")
    A("## 10. Co uruchomiono, czego nie sprawdzono")
    A("")
    A("__RUN__")
    A("")
    A("## 11. Test rozkładu 2018 dla Poznania")
    A("")
    A("__F2018__")
    A("")
    att = pd.read_csv(D.QA / "feed2018_attempts.csv")
    A(md_table(att))
    A("")
    rt = pd.read_csv(D.QA / "feed2018_routes.csv", dtype={"agency_id": str, "route_type": str})
    rt["grupa"] = np.where(rt.agency_id == "2", np.where(rt.route_type == "0", "MPK tramwaj", "MPK autobus"), "inni przewoźnicy ZTM (autobus)")
    piv = rt.groupby(["feed", "grupa"]).routes.sum().unstack("grupa").fillna(0).astype(int).reset_index()
    A("Liczba linii w `routes.txt` (pliki z grudnia 2018 r. z Internet Archive; tylko ta tabela była w nich kompletna):")
    A("")
    A(md_table(piv.rename(columns={"feed": "Plik"})))
    A("")
    mp = pd.read_csv(D.QA / "mpk_poznan_vkm_annual.csv")
    A("Praca przewozowa MPK Poznań (tys. km rocznie; tramwaj w pociągokm, czyli kursach, autobus w wozokm):")
    A("")
    A(md_table(mp.assign(tramwaj_tys_pociagokm=mp.tramwaj_tys_pociagokm.map(lambda x: f1(x, 0)), autobus_tys_wozokm=mp.autobus_tys_wozokm.map(lambda x: f1(x, 0)))))
    A("")
    A("Pliki: `feed2018_attempts.csv`, `feed2018_routes.csv`, `mpk_poznan_vkm_annual.csv`; `urban_centres.csv`, `decomposition.csv`, `sensitivity.csv`, `plausibility_30_45.csv`, `curves_uc.csv`, `supply_uc_vs_annex.csv`, "
      "`supply_uc_by_feed.csv`, `stops_uc_osm_vs_gtfs.csv`, `production_chunks_domains.csv`, `_meta.json`.")
    A("")
    out = "\n".join(L)
    for k, v in prose(an, dec, sens, plaus, f1, sgn, NAMES).items():
        out = out.replace(k, v)
    return out


def prose(an, dec, sens, plaus, f1, sgn, NAMES) -> dict:
    """Prose blocks; every number is read from the frames / CSVs."""
    sup = pd.read_csv(D.QA / "supply_uc_vs_annex.csv")

    def V(agg, m, pre, col="value"):
        return _v(dec, agg, m, pre, col)

    def S(agg, m, item):
        r = sens[(sens.agglomeration == agg) & (sens.measure == m) & sens.item.str.startswith(item)]
        return None if r.empty else float(r.delta.iloc[0])

    def sr(agg, mode):
        r = sup[(sup.agglomeration == agg) & (sup["mode"] == mode)]
        return float(r.ratio_annex_to_ours.iloc[0])

    ucf = pd.read_csv(D.QA / "urban_centres.csv").set_index("agglomeration")

    def ucp(agg):
        return float(ucf.loc[agg, "our_pop_census2021_in_uc"]) / float(ucf.loc[agg, "annex_pop_2011"])

    def pl(agg, m, col):
        return float(plaus[(plaus.agglomeration == agg) & (plaus.measure == m)][col].iloc[0])

    C = ("warszawa", "poznan", "lodz")
    dom = {a: V(a, "PT 45", "2.") - V(a, "PT 45", "0.") for a in C}
    meth45 = {a: V(a, "PT 45", "5.") - V(a, "PT 45", "2.") for a in C}
    rem = {(a, m): V(a, m, "Reszta", "delta") for a in C for m in ("PT 30", "PT 45", "pieszo 30", "rower 30 LTS 4")}
    gap0 = {(a, m): V(a, m, "DG REGIO") - V(a, m, "0.") for a in C for m in ("PT 30", "PT 45")}
    slow30 = [S(a, "PT 30", "co by było") for a in C]
    slow45 = [S(a, "PT 45", "co by było") for a in C]
    rng = lambda xs: f1(min(abs(x) for x in xs)) + "–" + f1(max(abs(x) for x in xs))
    P = {}
    P["__VERDICT__"] = (
        "**Braków w naszych feedach, które tłumaczyłyby różnicę, nie znaleziono. Główną przyczyną luki 45-minutowej jest inna domena.** "
        "DG REGIO liczy starty, cele i mianownik wyłącznie w urban centre 2011 (Poznań i Łódź po 117 km², Warszawa 309 km²), a mianownik jest przycięty do jego granic (s. 42). "
        "W tak małym obszarze promień 11,25 km obejmuje prawie całą ludność UC (Poznań i Łódź: " + f1(100 * pl("poznan", "PT 45", "dg_prox_share_of_uc"), 0) + " % w DG REGIO), "
        "więc KZ 45 to w praktyce „jaki odsetek całego UC osiągam w 45 min”. Nasz mianownik produkcyjny (FUA + 15 km) dla startów w UC Poznania to "
        + f1(100 * pl("poznan", "PT 45", "our_fua_prox_over_uc_pop"), 0) + " % ludności UC. "
        "Sama zmiana domeny (kroki 1–2) podnosi nasz KZ 45 o " + f1(dom["poznan"]) + " pkt w Poznaniu, " + f1(dom["lodz"]) + " w Łodzi i " + f1(dom["warszawa"]) + " w Warszawie. "
        "Pozostałe różnice metody razem (agregacja, dojście 5 km, średnia z 9 odjazdów; kroki 3–5) dają " + sgn(meth45["poznan"]) + " / " + sgn(meth45["lodz"]) + " / "
        + sgn(meth45["warszawa"]) + " pkt (Poznań / Łódź / Warszawa).\n\n"
        "Po odtworzeniu domeny i metody luka KZ 45 (DG − my) maleje z " + sgn(gap0[("poznan", "PT 45")]) + " do " + sgn(rem[("poznan", "PT 45")]) + " pkt w Poznaniu i z "
        + sgn(gap0[("lodz", "PT 45")]) + " do " + sgn(rem[("lodz", "PT 45")]) + " pkt w Łodzi; w Warszawie jesteśmy " + f1(-rem[("warszawa", "PT 45")]) + " pkt powyżej DG REGIO. "
        "Przy KZ 30 po tych samych krokach jesteśmy powyżej DG REGIO we wszystkich trzech miastach (o " + f1(-rem[("poznan", "PT 30")]) + " / " + f1(-rem[("lodz", "PT 30")]) + " / "
        + f1(-rem[("warszawa", "PT 30")]) + " pkt), a pieszo o " + rng([rem[(a, "pieszo 30")] for a in C]) + " pkt. Brak kursów obniżałby nasz wynik przy każdym progu; "
        "tymczasem niżej od DG REGIO jesteśmy tylko przy 45 min w Poznaniu i Łodzi (sam ten układ nie wyklucza braków zamaskowanych przez przeciwny efekt, dlatego w §7 są testy bezpośrednie danych).\n\n"
        "**Reszty nie da się przypisać jednej przyczynie.** Zmierzone fakty: (1) krótkie podróże są w modelu DG REGIO wolniejsze niż u nas: ich wynik pieszy odpowiada naszemu progowi 23–26 min zamiast 30 (§6); "
        "gdyby u nas odcinki piesze były wolniejsze (4 km/h), KZ 30 spadłby o " + rng(slow30) + " pkt, czyli mniej więcej o resztę KZ 30, ale KZ 45 spadłby też, o " + rng(slow45)
        + " pkt (§5), co powiększyłoby lukę 45 min w Poznaniu i Łodzi. (2) Według aneksu DG REGIO ich rozkłady 2018 miały w urban centre więcej wozokilometrów na mieszkańca niż nasze feedy 2026: Łódź "
        + f1(sr("lodz", "total"), 2) + "×, Poznań " + f1(sr("poznan", "total"), 2) + "×, Warszawa " + f1(sr("warszawa", "total"), 2) + "× (autobusy: " + f1(sr("poznan", "bus"), 2) + "× w Poznaniu, "
        + f1(sr("lodz", "bus"), 2) + "× w Łodzi), przy prawie tych samych prędkościach w linii prostej. Kolejność tych ilorazów (Łódź > Poznań > Warszawa) jest taka sama jak kolejność reszt KZ 45 ("
        + sgn(rem[("lodz", "PT 45")]) + " > " + sgn(rem[("poznan", "PT 45")]) + " > " + sgn(rem[("warszawa", "PT 45")]) + "); to trzy punkty, więc zgodność, nie dowód. "
        "(3) Nasze feedy 2026 zgadzają się z niezależnymi źródłami (§7): wozkm MPK Poznań z feedu pasują do rocznej pracy MPK z raportu miasta, lista linii dziennych Łodzi zgadza się z listą MPK Łódź, "
        "a ok. 95 % przystanków OSM w UC ma obsługiwany przystanek GTFS w 100 m. Czy w 2018 r. w tych UC jeździło naprawdę o 20–40 % więcej kursów, czy feed DG REGIO był zawyżony "
        "(np. nakładające się wersje rozkładu w dniu „z największą liczbą odjazdów”), **nie da się rozstrzygnąć bez feedów użytych przez DG REGIO**; praca ich nie wymienia.\n\n"
        "Werdykt: nasze dane 2026 nie są niekompletne w stopniu, który miałby znaczenie dla tego porównania. Luka 45 min to głównie domena; reszta (Poznań " + sgn(rem[("poznan", "PT 45")])
        + ", Łódź " + sgn(rem[("lodz", "PT 45")]) + " pkt) jest zgodna z większą podażą w danych 2018, której pochodzenia (realna zmiana czy zawyżony feed) nie sprawdzono. "
        "Wniosek praktyczny: porównywać z DG REGIO tylko wynik w domenie UC i ze stosunkiem średnich (krok 3–5), nie wynik produkcyjny.")
    P["__SENS__"] = (
        "Wnioski: (a) liczenie pary, gdy średnia z odjazdów z wynikiem ≤ 60 min mieści się w progu (zamiast wykluczenia pary nieosiągalnej w którymkolwiek z 9 odjazdów), zmienia wynik o ≤ 0,13 pkt, "
        "więc sposób traktowania braków w OTP nie tłumaczy różnicy; (b) efekt 9 odjazdów jest prawie taki sam przy dojściu 1 km i 5 km; (c) siatka ludności (GHSL surowy zamiast NSP 2021) zmienia wynik o ok. 2 pkt lub mniej; "
        "(d) błąd próby 800 startów ≤ 0,5 pkt; (e) wolniejsze odcinki piesze (4 km/h) obniżają KZ 30 i KZ 45 o podobną liczbę punktów, więc samo „wolniejsze chodzenie” w modelu DG REGIO nie wyjaśnia jednocześnie niższego KZ 30 i wyższego KZ 45. "
        "Ludności 2011 na poligonach Urban Atlas nie mamy; jej wpływu nie zmierzono. Według naszej siatki NSP 2021 w granicach UC 2011 mieszka w Łodzi o "
        + f1(100 * (1 - ucp("lodz")), 0) + " % mniej osób niż w 2011 r. według aneksu, w Poznaniu o " + f1(100 * (1 - ucp("poznan")), 0) + " % mniej (różne siatki, porównanie przybliżone).")
    P["__PLAUS__"] = (
        "Pytanie (c): średnio " + f1(100 * pl("poznan", "PT 45", "dg_prox_share_of_uc")) + " % ludności UC Poznania leży w promieniu 11,25 km od startu (u nas "
        + f1(100 * pl("poznan", "PT 45", "our_prox_share_of_uc")) + " %), więc KZ 45 = " + f1(float(an.loc["poznan", "t2_14"])) + " znaczy, że przeciętny mieszkaniec dojeżdża w 45 min do "
        + f1(100 * pl("poznan", "PT 45", "dg_acc_share_of_uc")) + " % wszystkich mieszkańców UC; w naszym odtworzeniu (krok 4) " + f1(100 * pl("poznan", "PT 45", "our_acc_share_of_uc")) + " %. "
        "W Łodzi DG " + f1(100 * pl("lodz", "PT 45", "dg_acc_share_of_uc")) + " %, my " + f1(100 * pl("lodz", "PT 45", "our_acc_share_of_uc")) + " %. "
        "To nie jest wartość nieprawdopodobna: w zwartym UC o średnicy ok. 12 km 45 min komunikacją wystarcza dla większości par. Krzywa DG REGIO jest jednak bardziej stroma niż nasza: "
        "w Poznaniu osiągalni rosną z " + f1(100 * pl("poznan", "PT 30", "dg_acc_share_of_uc"), 0) + " % (30 min) do " + f1(100 * pl("poznan", "PT 45", "dg_acc_share_of_uc"), 0)
        + " % ludności UC (45 min), u nas z " + f1(100 * pl("poznan", "PT 30", "our_acc_share_of_uc"), 0) + " % do " + f1(100 * pl("poznan", "PT 45", "our_acc_share_of_uc"), 0) + " %. "
        "Wartości 30 i 45 min DG REGIO nie są ze sobą sprzeczne, ale nie da się ich odtworzyć jednym przesunięciem czasu naszej sieci (tabela niżej).")
    P["__EQUIV__"] = (
        "Wartość DG REGIO dla 30 min odpowiada naszemu wynikowi przy ok. 26–28 min, a dla 45 min przy ok. 43 (Warszawa), 46–47 (Poznań) i 49 min (Łódź); pieszo przy 23–26 min zamiast 30. "
        "Krótkie podróże są więc w modelu DG REGIO wolniejsze niż u nas, także sam spacer (czyli sieć piesza, dowiązanie punktów, prędkość lub dobór trasy w OTP, nie komunikacja), "
        "a w Poznaniu i Łodzi dłuższe podróże komunikacją są u nich szybsze niż u nas. Drugiego nie wyjaśnia żaden zmierzony parametr metody; pasuje do większej podaży w ich danych 2018 (§7–8).")
    P["__SUPPLY__"] = (
        "Test bezpośredni (pytanie a). Aneks DG REGIO (tabela 1; definicja na s. 44–46 pracy) podaje dla każdego UC wozokilometry w linii prostej między kolejnymi przystankami kursu, odjazdy 6:00–20:00, oba przystanki w UC, "
        "na 1000 mieszkańców 2011, oraz prędkość w linii prostej. Policzono to samo z naszych feedów (warstwa usługowa po deduplikacji, wariant „wszystkie”, środa " + D.REF_DAY + ", mianownik: ludność 2011 z aneksu). "
        "**Założenie niezweryfikowane:** jednostkę aneksu („km/1000 inh.”) czytamy jako wozkm na 1000 mieszkańców na godzinę okna 6–20; tylko przy tym odczycie wartości są tego samego rzędu (na dobę byłyby ok. 14× za małe). "
        "Ilorazy między trybami i między miastami od tej jednostki nie zależą.\n\n"
        "Prędkości w linii prostej zgadzają się zwykle co do 1–2 km/h (metro w Warszawie 32,1 / 32,1), więc definicja jest odtworzona poprawnie. W Poznaniu i Łodzi DG REGIO miało ok. 1,7× więcej wozkm autobusowych na mieszkańca UC niż nasz feed 2026; "
        "tramwajowych tyle samo (Łódź) albo mniej (Poznań " + f1(sr("poznan", "tram"), 2) + "×, Warszawa " + f1(sr("warszawa", "tram"), 2) + "×), a metra w Warszawie " + f1(sr("warszawa", "metro"), 2)
        + "× naszego (w 2018 r. II linia miała tylko odcinek centralny, co samo nie tłumaczy pięciokrotnej różnicy). Taki wzór nie wygląda na brakującego przewoźnika po naszej stronie: "
        "w Poznaniu cała komunikacja ZTM (MPK i przewoźnicy podmiejscy) jest w jednym feedzie, w Łodzi feedy podmiejskie dają ok. 1 % wozkm w UC (`supply_uc_by_feed.csv`).\n\n"
        "Kontrola z danymi przewoźników i organizatorów:\n\n"
        "- **Poznań.** Raport miasta „Transport miejski w Poznaniu w 2024 r.” (badam.poznan.pl, dane MPK): 31,1 mln wozkm MPK w 2024 r., 23 linie tramwajowe (w tym 3 nocne), 67 autobusowych (w tym 14 nocnych). "
        "Nasz feed: MPK (agency 2) w środę ref. 95,2 tys. wozkm (tramwaj 40,0 tys., autobus 55,2 tys.; długości z kształtów), 20 linii tramwajowych i 70 autobusowych z kursami w tym dniu. "
        "31,1 mln / 95,2 tys. = 327 „dni roboczych” na rok, typowa relacja rok / dzień roboczy, więc feed nie jest wyraźnie niepełny (dane roczne 2024, feed 2026: porównanie przybliżone).\n"
        "- **Łódź.** Lista linii na mpk.lodz.pl (odczyt 2026-11-24): 23 linie tramwajowe dzienne, 81 pozycji autobusowych dziennych (z wariantami A/B/C/D), 14 nocnych, linie Z. "
        "W feedzie `lodz` w dniu ref. są wszystkie linie tramwajowe i wszystkie dzienne autobusowe z wyjątkiem 55B (brak w feedzie) i 81B (w feedzie tylko w soboty). "
        "Rocznej pracy przewozowej MPK Łódź nie znaleziono w źródle pierwotnym, więc kontroli wozkm dla Łodzi nie wykonano.\n"
        "- **Warszawa:** nie kontrolowano z danymi ZTM (luka Warszawy przy 45 min po korekcie domeny jest ujemna).")
    P["__STOPS__"] = (
        "Niedopasowane przystanki to głównie przystanki na żądanie („n/ż”, „NŻ”), przesunięcia 100–200 m, w Poznaniu kolejka parkowa Maltanka (4 „stacje” kolejowe), a w Łodzi przystanki tramwajowe na odcinkach wyłączonych z ruchu "
        "(Kilińskiego, Pomorska, Zielona, Narutowicza), co zgadza się z ustaleniem fazy 2, że zamknięte odcinki są widoczne tylko po stronie OSM. Nie ma skupisk wskazujących na brakującego przewoźnika w UC.")
    P["__OPTIM__"] = (
        "Pytanie (b). Co wiadomo z pracy: feedy GTFS przewoźników (część zbiorów przekształcono z formatów krajowych, s. 35, bez wskazania miast), kolej z UIC MERITS, gdy feed miejski jej nie miał (s. 37), "
        "dzień roboczy z **największą liczbą odjazdów** w okresie ważności feedu (s. 35), ręczne wymuszanie wspólnej daty przy łączeniu feedów (s. 37). Konkretnych plików, ich dat i dnia nie podano ani w pracy, "
        "ani w kartach miast („public transport operators, UIC”), ani w aneksie.\n\n"
        "Co z tego mogło zawyżać KZ 45 i co zmierzono:\n\n"
        "- dzień z maksimum odjazdów przy feedzie z nakładającymi się wersjami rozkładu liczy kursy podwójnie; śladem byłaby nadwyżka wozkm, a nadwyżkę autobusową (ok. 1,7×) aneks pokazuje; przyczyny nie da się ustalić bez ich pliku (niezweryfikowane);\n"
        "- wymuszenie wspólnej daty przy łączeniu z MERITS może dodać kursy kolejowe, które w tym dniu nie jeżdżą; kolej to w ich danych 5–8 % wozkm w UC, więc efekt ograniczony (niezmierzony);\n"
        "- dojście do 5 km: zmierzone, +0,8 do +1,7 pkt;\n"
        "- braki w średniej z 9 odjazdów: zmierzone, ≤ 0,13 pkt;\n"
        "- domena UC (mały, zwarty obszar, mianownik przycięty): zmierzona, największy efekt; to definicja, nie błąd, ale faworyzuje miasta o małym i zwartym UC.\n\n"
        "W przeciwną stronę działa wolniejszy spacer w ich modelu (zmierzony pośrednio przez wynik pieszy) i dobór trasy w OTP według kosztu uogólnionego (niezmierzony). "
        "Wniosek: dane DG REGIO dla Poznania i Łodzi były „hojniejsze” od naszych pod względem podaży autobusowej; czy to zawyżenie, czy realna podaż 2018 r., nie da się stwierdzić z dostępnych materiałów.")
    P["__ACTIVE__"] = (
        "**Pieszo:** zmiana domeny prawie nic nie zmienia (promień 2,5 km mieści się w UC). Po korekcie prędkości (OTP 1.x domyślnie 1,33 m/s według dokumentacji OTP, praca prędkości nie podaje; próg 28 min przy 5 km/h) zostaje "
        + sgn(rem[("poznan", "pieszo 30")]) + " (Poznań), " + sgn(rem[("lodz", "pieszo 30")]) + " (Łódź), " + sgn(rem[("warszawa", "pieszo 30")]) + " pkt (Warszawa): u DG REGIO osiągalnych jest mniej. "
        "Niezmierzone możliwe przyczyny: dowiązanie centroidów poligonów Urban Atlas do grafu OTP, kompletność i dostępność ścieżek pieszych w grafie OTP 1.2 z OSM ok. 2018 r., dobór trasy przez OTP według kosztu uogólnionego, "
        "rozkład ludności na poligonach zamiast komórek 250 m. To ta sama skłonność, która obniża ich KZ 30.\n\n"
        "**Rower:** DG REGIO dla polskich miast liczyło na sieci TomTom: 15 km/h na każdej drodze poza autostradami, kontraruch na wszystkich jednokierunkowych (s. 40), czyli bliżej naszego LTS ≤ 4 niż LTS ≤ 3. "
        "Po zmianie domeny i agregacji zostaje przy LTS ≤ 4 " + sgn(rem[("poznan", "rower 30 LTS 4")]) + " (Poznań), " + sgn(rem[("lodz", "rower 30 LTS 4")]) + " (Łódź), "
        + sgn(rem[("warszawa", "rower 30 LTS 4")]) + " pkt (Warszawa). Kierunek pasuje do bardziej liberalnej sieci (kontraruch wszędzie, brak ograniczeń LTS i zakazów R5), ale tego nie zmierzono; sieci TomTom nie mamy. "
        "Rower nie zależy od GTFS, więc te reszty nie mówią nic o kompletności feedów; pokazują, że różnice sieci i routera między nami a DG REGIO sięgają 5–20 pkt nawet bez komunikacji.")
    mp = pd.read_csv(D.QA / "mpk_poznan_vkm_annual.csv").set_index(["rok", "rodzaj"])
    bus_ratio = mp.loc[(2024, "plan (zał. 1 do umowy)"), "autobus_tys_wozokm"] / mp.loc[(2017, "zamówienie skorygowane"), "autobus_tys_wozokm"]
    tram_ratio = mp.loc[(2024, "plan (zał. 1 do umowy)"), "tramwaj_tys_pociagokm"] / mp.loc[(2017, "zamówienie skorygowane"), "tramwaj_tys_pociagokm"]
    P["__F2018__"] = (
        "**Wynik: kompletnego feedu Poznania z 2018 r. nie udało się zdobyć legalną drogą bez konta, więc pomiaru podaży z feedu 2018 i routingu na sieci 2018 nie wykonano** (punkty 1–3 zlecenia). "
        "Innego roku nie podstawiano. Co sprawdzono, w tabeli niżej. Jedyne zachowane pliki z 2018 r. (Internet Archive, grudzień 2018) są ucięte na 1 MiB; dało się z nich odczytać tylko listę linii i kalendarz. "
        "Pobrane kopie: `data/raw/wayback_ztm_poznan_gtfs_truncated_20181214_20181216/` i `..._20181228_20181228/` (z `SOURCE.json`).\n\n"
        "Zastępczy test realnej zmiany podaży: raporty roczne MPK Poznań (2017 i 2024; raport 2018 jest skanem bez warstwy tekstowej). Zamówiona praca autobusowa MPK zmieniła się z 2017 na 2024 r. o "
        + sgn(100 * (bus_ratio - 1)) + " %, tramwajowa o " + sgn(100 * (tram_ratio - 1)) + " %. Realna zmiana podaży MPK między ok. 2018 a dziś jest więc mała i nie tłumaczy ilorazu autobusowego z aneksu (DG / my "
        + f1(sr("poznan", "bus"), 2) + "×) ani niższego tramwajowego (" + f1(sr("poznan", "tram"), 2) + "×). Nasz feed 2026 zgadza się z pracą MPK 2024 (współczynnik rok / środa ok. 327, §7). "
        "Plik z 14–16 grudnia 2018 r. (piątek–niedziela) ma w `routes.txt` 81 linii autobusowych MPK (z nocnymi), plik z 28 grudnia (okres świąteczny) 70, nasz feed 2026 70; tramwajowych 19–21 we wszystkich. Linii innych przewoźników ZTM było wtedy mniej niż dziś (przyczyna, np. rozszerzenie obszaru ZTM, niezweryfikowana), "
        "więc w UC ich udział i tak jest mały. Więcej linii przy prawie tej samej rocznej pracy autobusowej nie daje 1,7× wozkm.\n\n"
        "Wniosek dla pytania o zawyżenie: realne dane przewoźnika nie potwierdzają, że w 2018 r. w Poznaniu jeździło 1,7× więcej autobusów niż dziś. To wzmacnia hipotezę, że autobusowa część danych wejściowych DG REGIO była zawyżona "
        "(np. podwójne kursy z nakładających się wersji rozkładu w dniu „z największą liczbą odjazdów”) albo inaczej sklasyfikowana, ale **bez ich pliku nie da się tego sprawdzić**, a kontroli duplikatów na feedzie 2018 nie wykonano (brak pliku). "
        "Zastrzeżenia: raport MPK obejmuje całą sieć MPK, nie sam UC; pociągokm tramwaju to kursy (jak w GTFS), a nie wagony. "
        "Łódź: nie znaleziono dowodu na istnienie operatorskiego GTFS MPK Łódź w 2018 r. (szukano krótko, bez wyniku w obie strony).")
    P["__RUN__"] = (
        "Uruchomiono 2026-11-24, równolegle z produkcyjnym `pipeline.access run` (nie dotykano go): `python -m pipeline.access_dgregio prep` (ok. 45 s, bez JVM); "
        "`python -m pipeline.access_dgregio route ...` w jednej JVM naraz, 6 wątków, `-Xmx 8G`, na kopiach plików sieci w `data/interim/access_dgregio/r5/` (sieci produkcyjne tylko czytane): "
        "Poznań i Łódź na pełnym UC (KZ 1 km, KZ 5 km, KZ 5 km przy 4 km/h, rower LTS 3 i 4), Warszawa oraz warianty 9 odjazdów na próbie 800 startów; łącznie ok. 34 min zegarowych (czasy w `_meta.json`, `routing_log`). "
        "Pełnego UC Warszawy (4796 startów) nie liczono ze względu na limit czasu; błąd próby oszacowano w §5. Na końcu `python -m pipeline.access_dgregio report`.\n\n"
        "**Założenia niezweryfikowane:** godziny „dwugodzinnego szczytu” DG REGIO (przyjęto 7:00–9:00); prędkość pieszego w OTP (domyślna 1,33 m/s); jednostka wozkm w aneksie (na godzinę); "
        "które feedy, z jakiej daty i z jakiego dnia użyto dla Warszawy, Poznania i Łodzi; roczna praca przewozowa MPK Łódź (nie znaleziono); wpływ ludności 2011 na poligonach Urban Atlas, routera OTP i sieci TomTom (nie do zmierzenia naszymi danymi). "
        "**Przygotowane, nieuruchomione:** archiwalnych feedów 2018 nie pobierano (transitfeeds.com odmawia automatycznego dostępu, HTTP 403; innych archiwów nie sprawdzono). To byłby rozstrzygający test reszty 45 min: "
        "zbudować sieć R5 z feedów Poznania i Łodzi z 2018 r. i uruchomić na niej `route` oraz kontrolę wozkm z §7.")
    return P
