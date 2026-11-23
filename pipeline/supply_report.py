"""Writes results/qa/transit/supply.md (Polish) from the tables of the transit step."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline import gtfs_service as gs
from pipeline.common import RESULTS, sig

QA = RESULTS / "qa" / "transit"
AGG_PL = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
          "trojmiasto": "Trójmiasto", "gzm": "GZM"}
MODES = ["tram", "metro", "rail", "bus", "trolleybus", "ferry", "other"]
MODE_PL = {"tram": "tramwaj", "metro": "metro", "rail": "kolej", "bus": "autobus", "trolleybus": "trolejbus", "ferry": "prom",
           "other": "inne", "total": "razem", "bus_replacement": "w tym autobusy zastępcze kolei"}


def _f(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")


def _i(x):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{int(round(x)):,}".replace(",", " ")


def table(rows: list[list], header: list[str], align: str | None = None) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---:" if (align or "l" * len(header))[i] == "r" else "---"
                                                          for i in range(len(header))) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def skm_check(day: str) -> tuple[int, int, float, float]:
    d = pd.Timestamp(day)
    p = gs._active_in_feed("polish_trains", d)
    p = p[p["agency_id"] == "SKM"]
    z = gs._active_in_feed("warsaw_ztm", d)
    z = z[z["route_class"] == "rail"]
    for df in (p, z):
        df["k"] = df["route_short_name"].astype(str) + "|" + df["first_stop_key"].astype(str) + "|" + (df["first_dep_s"] // 60).astype(int).astype(str)
    return len(p), len(z), float(p["k"].isin(set(z["k"])).mean()), float(z["k"].isin(set(p["k"])).mean())


def write_report(*, summ: pd.DataFrame, hourly: pd.DataFrame, diag: pd.DataFrame, anomaly: pd.DataFrame, tram: dict, top: dict,
                 days: dict) -> None:
    ref, sat = days["weekday"], days["saturday"]
    L: list[str] = []
    A = L.append
    ss = pd.read_csv(QA / "service_summary.csv")
    cf = pd.read_csv(QA / "cross_feed_duplicates.csv")
    A("# Podaż, prędkość tramwajów i kontrola przystanków (faza 2, krok `supply`)")
    A("")
    A(f"Dzień roboczy: **{ref}** (środa), sobota: **{sat}**. Rozkłady jazdy pobrane 2026-11-23; ludność: **NSP 2021, stan 2021-03-31** (siatka 1 km, ludność rezydująca, komórka należy do obszaru, gdy jej środek leży w obszarze). "
      "Każdy wynik liczony w dwóch wariantach zestawu feedów: `official` (feedy z briefu i dodatki od wydawcy) i `all` (wszystkie 42). "
      "Źródła liczb: pliki CSV w tym folderze; metryki w `results/metrics/metrics_supply.csv`.")
    A("")
    A("## 1. Warstwa usługowa: które kursy się liczą (`pipeline/gtfs_service.py`)")
    A("")
    A("Jedno miejsce, w którym zapada decyzja, które kursy dnia są liczone (API: `feeds_for`, `active_trips`, `stop_times`, `stops`). Reguły w kolejności stosowania:")
    A("")
    A("1. **Konfiguracja** (`drop_routes` / `drop_agencies` w `config.yaml`, stosowane w `gtfs_io`): w tej chwili tylko linie 6 i 61 MUK Zgierz (te same kursy co w MPK Łódź), 148 kursów w dniu ref.")
    n_skm, n_z, m1, m2 = skm_check(ref)
    A(f"2. **SKM Warszawa** (`agency_id = SKM` w `polish_trains`) odrzucona: te same kursy są w `warsaw_ztm` ({n_skm} vs {n_z} kursów w dniu ref.; klucz linia + znormalizowana nazwa pierwszego przystanku + minuta odjazdu; zgodność {m1 * 100:.0f} % i {m2 * 100:.0f} % w drugą stronę). "
      "SKM Trójmiasto to osobna agencja (`SKMT`) i zostaje.")
    A("3. **Kolej ogólnopolska** (`polish_trains`, w konfiguracji `rail: true`): zostają kursy z co najmniej jednym przystankiem w FUA + 15 km danej aglomeracji. Zostaje cały kurs (wszystkie wiersze `stop_times`), kolumna `in_buffer` zaznacza przystanki w buforze. Pozostałe feedy nie są przycinane (każdy obsługuje jeden obszar).")
    A("4. **Dokładne duplikaty kursów w jednym feedzie**: to samo `route_id`, kierunek, `block_id`, pierwszy odjazd i ta sama sekwencja przystanków z tymi samymi czasami (przystanek porównywany po położeniu zaokrąglonym do 1 m, bo GZM powtarza rekordy przystanków pod innymi `stop_id` i nazwami, np. Zaborze Wolności / Poremba Wolności w tym samym punkcie), kursujące tego samego dnia (także pod różnymi `service_id`), inny `trip_id`. Zostaje kurs o najmniejszym `trip_id`.")
    A("   4b. **Duplikaty blokowe**: ta sama linia, kierunek, niepusty `block_id`, godzina pierwszego odjazdu i ostatniego przyjazdu oraz liczba przystanków, ale przystanki przesunięte (GZM: 242 pary, przystanek przesunięty do 350 m). Jeden pojazd (blok) nie przejedzie dwóch takich kursów, zostaje kurs o mniejszym `trip_id`.")
    A("5. **Duplikaty między feedami** w obrębie aglomeracji i wariantu: klucz linia (`route_short_name`) + znormalizowana nazwa pierwszego przystanku + minuta odjazdu. Kopię o niższym priorytecie (feed miejski przed `polish_trains`, oficjalny przed nieoficjalnym, potem kolejność w konfiguracji) odrzuca się tylko wtedy, gdy co najmniej 90 % (i co najmniej 3) kursów danej linii pasuje do feedu o wyższym priorytecie; odrzucane są wyłącznie kursy pasujące. Para poniżej progu jest tylko raportowana (`cross_feed_duplicates.csv`).")
    A("6. **`frequencies.txt`**: używa go tylko metro w `warsaw_ztm` (16 szablonów kursów); rozwijane na pojedyncze kursy (`<trip_id>~k`), czasy przesunięte o początek przejazdu.")
    A("")
    A("Autobusy zastępcze kolei (`route_type` 3 w `polish_trains` i `warsaw_wkd`) mają `is_replacement_bus = True`: zostają w tabelach jako autobus, a miary kolejowe mają je wyłączać. Liczba kursów w dniu ref. i wariancie `all` jest ich "
      + ", ".join(f"{AGG_PL[a]} {_i(gs.active_trips(a, ref, 'all')['is_replacement_bus'].sum())}" for a in gs.PHASE1) + " (podzbiór autobusów).")
    A("")
    A("### 1.1 Kursy przed → po regułach (dzień roboczy, wariant `all`; pełna tabela per feed i sobota: `service_summary.csv`)")
    A("")
    for variant in gs.VARIANTS:
        t = ss[(ss["feed"] == "RAZEM") & (ss["day"] == ref) & (ss["variant"] == variant)]
        rows = [[AGG_PL[r.agglomeration], _i(r.trips_raw), _i(r.dropped_config_routes_agencies), _i(r.dropped_agency_rule), _i(r.dropped_outside_buffer),
                 _i(r.dropped_exact_duplicates), _i(r.dropped_block_duplicates), _i(r.dropped_cross_feed), _i(r.trips_final)]
                for r in t.itertuples()]
        A(f"Wariant `{variant}`, {ref}:")
        A("")
        A(table(rows, ["Aglomeracja", "kursy surowe (po rozwinięciu `frequencies`)", "− konfig. (Zgierz)", "− SKM Warszawa", "− poza FUA+15 km (kolej)", "− dokładne duplikaty", "− duplikaty blokowe", "− między feedami", "kursy po regułach"], "lrrrrrrrr"))
        A("")
    t = ss[(ss["feed"] == "RAZEM") & (ss["day"] == sat) & (ss["variant"] == "all")]
    A(f"Sobota {sat}, wariant `all`: " + "; ".join(f"{AGG_PL[r.agglomeration]} {_i(r.trips_raw)} → {_i(r.trips_final)}" for r in t.itertuples()) + ".")
    A("")
    A("Uwaga: „kursy surowe” obejmują kursy z `drop_routes` (Zgierz), żeby tabela się bilansowała; w `trips_raw` kolej to wszystkie 7 453 kursów ogólnopolskich.")
    A("")
    A("### 1.2 Kontrole warstwy")
    A("")
    g = ss[(ss["feed"] == "gzm") & (ss["day"] == ref) & (ss["variant"] == "all")].iloc[0]
    A(f"- **GZM**: {_i(g.dropped_exact_duplicates + g.dropped_block_duplicates)} z {_i(g.trips_raw)} kursów ({(g.dropped_exact_duplicates + g.dropped_block_duplicates) / g.trips_raw * 100:.1f} %) usuniętych jako duplikaty (dokładnych: {_i(g.dropped_exact_duplicates)}, blokowych: {_i(g.dropped_block_duplicates)}). "
      "Duplikaty różnią się `trip_id`, `shape_id` i (w części) rekordami przystanków o tym samym położeniu. W sobotę 2026-11-28 reguły nie znajdują duplikatów (przyczyny nie badano). Wcześniejszy test fazy 0 (ten sam `service_id`) znajdował 7 693 dokładnych duplikatów; reguła tutaj łapie także duplikaty pod różnymi `service_id` i rekordy przystanków pod różnymi identyfikatorami.")
    A("- **Kursy z jednym duplikatem poza GZM**: `warsaw_zakroczym` (ręcznie ułożony feed) 1 kurs (dwa `service_id`, identyczny przebieg i godzina).")
    n_pairs = int(cf[(cf["dropped"] == True)].shape[0]) if len(cf) else 0
    A(f"- **Duplikaty między feedami**: po regule 1 (Zgierz) test (linia + pierwszy przystanek + minuta) nie znajduje żadnej pary w żadnej aglomeracji i wariancie (`cross_feed_duplicates.csv` jest pusty; odrzuconych par: {n_pairs}). Kontrola uzupełniająca bez nazwy przystanku: ta sama linia i ta sama minuta w dwóch feedach zdarza się przypadkiem (np. linie 1-12 MZK Wejherowo i Gdańska, linie warszawskie ZTM i `warsaw_gpa`: 54 w Trójmieście, 590 w Warszawie, 76 w Łodzi, 7 we Wrocławiu, 1 w Krakowie), ale w żadnym z tych przypadków pierwsze przystanki nie leżą bliżej niż 150 m. Test wykrywa dublowanie: na sztucznie podwojonych liniach 6 i 61 z Łodzi odrzuca 220 z 220 kursów kopii.")
    A("- **Uwaga o fazie 0**: `duplicate_trips_check.csv` z fazy 0 podaje dla `warsaw_otwock` 197 kursów w dniu ref., a feed ma ich 138 (wg `service_dates` + `trip_stats`; przyczyny rozbieżności nie badano).")
    A("")

    # ---- supply
    A("## 2. Wozokilometry (§4.7)")
    A("")
    A("Metoda (`pipeline/supply_core.py`): odcinek = kolejne dwa przystanki kursu. Długość odcinka = odległość w linii prostej (EPSG:2180) przeskalowana tak, by suma odcinków kursu dawała długość kursu z kształtu trasy (`shapes`), jeśli stosunek kształtu do odległości między przystankami mieści się w [0,8; 2,0]; w przeciwnym razie (i bez kształtu) długość to odległość między przystankami. Odcinek z oboma przystankami w obszarze liczony w całości; z jednym końcem w obszarze: proporcjonalnie do długości linii prostej leżącej w obszarze; z oboma końcami poza obszarem: 0 (nawet gdy prosta zahacza o obszar). Godzina odcinka = godzina odjazdu z jego pierwszego przystanku (godziny 24-29 to kursy po północy dnia ruchu). Kolej ogólnopolska przycięta tak samo, autobusy zastępcze liczone jako autobus i pokazane osobno.")
    A("")
    A("Obszary: **FUA** (dla Trójmiasta i GZM suma FUA wg konfiguracji) i **rdzeń** (miasta URAU; Trójmiasto: Gdańsk + Gdynia + Sopot). Ludność z siatki spisowej NSP 2021 (stan 2021-03-31). Pokrycie GTFS: udział ludności FUA mieszkającej w gminach o pokryciu przystanków ≥ 85 % (`population_coverage_preliminary.csv`, kolumna `gmina_pop_share_cov_ge_85`, stan po 42 feedach); dla rdzenia: udział przystanków OSM z odpowiednikiem w GTFS (nie ludności). Poniżej 0,85 wynik niesie flagę **„niepełne pokrycie GTFS”**. Dla wariantu `official` pokrycia osobno nie liczono (poza aglomeracjami, w których oba warianty mają te same feedy: Poznań, Trójmiasto, GZM), więc wartość jest pusta (null), a flaga zostaje.")
    A("")
    pop_rows = []
    for a in gs.PHASE1:
        s = summ[(summ.agglomeration == a) & (summ.day_type == "weekday") & (summ.variant == "all") & (summ["mode"] == "total")]
        pf = s[s.domain == "fua"].iloc[0]
        pc = s[s.domain == "core"].iloc[0]
        pop_rows.append([AGG_PL[a], _i(pf.population), _i(pc.population), _f(pf.coverage_share, 3), _f(pc.coverage_share, 3)])
    A(table(pop_rows, ["Aglomeracja", "ludność FUA (NSP 2021)", "ludność rdzenia", "pokrycie FUA (ludność, ≥ 85 %)", "pokrycie rdzenia (przystanki)"], "lrrrr"))
    A("")
    for dom, dname in (("fua", "FUA"), ("core", "rdzeń")):
        A(f"### 2.{1 if dom == 'fua' else 2} Wozokilometry na mieszkańca na dobę, {dname}, dzień roboczy {ref}")
        A("")
        rows = []
        for a in gs.PHASE1:
            for variant in gs.VARIANTS:
                s = summ[(summ.agglomeration == a) & (summ.day_type == "weekday") & (summ.variant == variant) & (summ.domain == dom)].set_index("mode")
                row = [AGG_PL[a], variant]
                for m in ["total"] + MODES + ["bus_replacement"]:
                    row.append(_f(s.loc[m, "vkm_per_inhabitant"], 3) if m in s.index else "–")
                row.append(_i(s.loc["total", "vkm"]))
                fl = s.loc["total", "flag"]
                row.append("tak" if isinstance(fl, str) and fl else "nie")
                rows.append(row)
        A(table(rows, ["Aglomeracja", "wariant", "razem"] + [MODE_PL[m] for m in MODES] + ["w tym ZKA", "wozkm razem", "niepełne pokrycie"], "ll" + "r" * 11))
        A("")
        A("Jednostka: wozkm/mieszk./dobę (kolumna „wozkm razem”: wozkm/dobę). „–” = brak takiego trybu w feedach wariantu (nie zero). Sobota i godziny: `supply_vkm_summary.csv`, `supply_vkm_hourly.csv`, wykresy `vkm_hourly_<aglomeracja>.png`, `vkm_per_inhabitant.png`.")
        A("")
    A("**Jak czytać.** Wozkm na mieszkańca FUA mieszają dwie rzeczy: gęstość sieci i luki w danych (§6). Dla Warszawy, Krakowa, Wrocławia, Łodzi i Trójmiasta pokrycie FUA jest poniżej 85 %, więc wartości FUA są zaniżone przez brak przewoźników podmiejskich; do porównań bardziej nadaje się rdzeń (pokrycie ≥ 95 %). Różnica `official` → `all` pokazuje wkład nieoficjalnych przepakowań (tylko podmiejskie autobusy).")
    A("")
    dg = diag[(diag.variant == "all") & (diag.day_type == "weekday")]
    A("Kontrola długości kursów: udział wozkm skalowanych z kształtu trasy to " + ", ".join(
        f"{AGG_PL[r.agglomeration]} {r.km_scaled_by_shape / (r.km_scaled_by_shape + r.km_scaled_by_stops) * 100:.1f} %" for r in dg.itertuples())
      + "; liczba kursów z niewiarygodnym kształtem (stosunek poza [0,8; 2,0]): "
      + ", ".join(f"{AGG_PL[r.agglomeration]} {int(r.n_trips_shape_ratio_bad)}" for r in dg.itertuples())
      + ". Odcinki bez współrzędnych przystanku: " + ", ".join(f"{AGG_PL[r.agglomeration]} {int(r.n_seg_nocoord)}" for r in dg.itertuples()) + ". (`supply_vkm_diagnostics.csv`)")
    A("")
    A("**Defekt danych Łódź (znaleziony przy kontroli długości).** W feedzie `lodz` przystanki 3876 i 3877 (Pl. Niepodległości) mają `stop_lat = stop_lon = 0`. `gtfs_io` liczył z nich odległości rzędu tysięcy km (np. linie nocne N3A, N4A: 12 000 km „odległości między przystankami”), co psuło kontrolę kształtu i długości kursów bez kształtu. Warstwa usługowa traktuje współrzędne (0, 0) jako brak (x, y = null) i przelicza `dist_stops_m` z pominięciem takiego przystanku; zmienia to `dist_m` tylko dwóch kursów bez kształtu (2 kursy 6 000 km → 0 m). Poza tym w Łodzi znaczna część kursów autobusowych ma kształt krótszy niż 80 % łańcucha przystanków (liczby w akapicie wyżej, `n_trips_shape_ratio_bad`); dla nich użyto odległości między przystankami, więc wozkm Łodzi są ustalone głównie z linii prostych (dolne ograniczenie, zaniżone o krzywiznę tras rzędu kilku procent).")
    A("")
    A("### 2.3 Miejscokilometry")
    A("")
    A("**Nie liczone.** GTFS nie podaje typu taboru ani pojemności, a w repozytorium i dostępnych źródłach nie ma wiarygodnej tabeli pojemności per tryb i miasto (tabor różni się linią i porą dnia: tramwaje 100-250 miejsc, autobusy 80-180, metro ok. 1 000 na pociąg). Przyjęcie jednej pojemności na tryb byłoby założeniem bez źródła i przesłaniałoby różnice między miastami, więc wariant pominięto. Propozycja dla konfiguracji: klucz `seat_capacity` {tryb: {miasto: miejsca}} z jawnym polem `source`; po jego uzupełnieniu miejscokilometry to wozkm × pojemność z `supply_vkm_summary.csv`.")
    A("")

    # ---- anomaly
    A("## 3. Test anomalii (§5) na zdeduplikowanej usłudze")
    A("")
    A("Wozkm dnia referencyjnego (cała długość kursów, po regułach 1-4 na poziomie feedu; dla kolei: kursy dotykające FUA + 15 km) kontra mediana wozkm dni roboczych (pon-pt, bez świąt i okresu 24.12-6.01) w okresie ważności feedu (dni z kursami). Dla soboty: mediana sobót. Próg 5 %. Reguła 5 (duplikaty między feedami) nie wchodzi do testu, bo jest zależna od dnia i znikoma (patrz 1.2).")
    A("")
    for dname, day, title in (("weekday", ref, "dzień roboczy"), ("saturday", sat, "sobota")):
        a = anomaly[anomaly.day_type == dname]
        big = a[a["flag_gt5pct"] == True]
        A(f"**{title.capitalize()} {day}:** {len(a)} par (aglomeracja, feed); odchylenie w przedziale od {_f(a['deviation_pct'].min(), 2)} % do {_f(a['deviation_pct'].max(), 2)} %; powyżej 5 %: **{len(big)}**.")
        A("")
        if len(big):
            A(table([[AGG_PL[r.agglomeration], r.feed, _f(r.vkm_day, 0), _f(r.vkm_median, 0), _i(r.n_days_median), _f(r.deviation_pct, 1), f"{r.validity_first} … {r.validity_last}"] for r in big.itertuples()],
                    ["Aglomeracja", "feed", "wozkm dnia", "mediana", "dni w medianie", "odch. %", "ważność"], "llrrrrl"))
            A("")
    A("Pełna tabela: `anomaly_test_dedup.csv`. Słabość testu (jak w fazie 0): mediana krótkich feedów pochodzi z tego samego 2-3-tygodniowego okna co dzień referencyjny, a dla feedów rocznych obejmuje wakacje i ferie; test nie wykryje feedu „feryjnego” w całym oknie. Liczba dni w medianie jest w kolumnie `n_days_median`.")
    A("")

    # ---- tram
    pc = tram["per_city"]
    pl = tram["per_line"]
    A("## 4. Rozkładowa prędkość eksploatacyjna tramwajów (§4.7, grafika 5 z §15)")
    A("")
    A("**To jest rozkładowa prędkość eksploatacyjna z postojami na przystankach** = długość kursu / (ostatni przyjazd − pierwszy odjazd), z rozkładu jazdy. Nie jest to prędkość jazdy między przystankami ani prędkość rzeczywista (warstwa 6b odłożona).")
    A("")
    A("Reguły (`pipeline/tram_speed.py`): wszystkie kursy tramwajowe dnia po deduplikacji. Długość z kształtu trasy; dla każdego kursu liczona też suma odległości w linii prostej między przystankami; gdy obie różnią się o więcej niż 15 % (flaga `length_disagree`) albo brak kształtu, w wyniku używana jest odległość między przystankami (dolne ograniczenie, więc prędkość lekko zaniżona). Wykluczone z każdej statystyki: kursy krótsze niż 1 km, krótsze niż 5 min, z mniej niż 3 przystankami (zjazdy do zajezdni, wyjazdy techniczne) oraz o prędkości poza 5-60 km/h (liczby w `tram_speed_excluded.csv`). Postój wewnątrz kursu dłuższy niż 120 s traktowany jest jako postój wyrównawczy; wynik główny go zawiera, wersja bez niego jest w CSV (`median_ex_layover_kmh`). Mediana ważona = mediana ważona długością kursu (wozkm). Żaden inny z 42 feedów nie ma linii tramwajowych.")
    A("")
    for variant in ("all",):
        c = pc[(pc.variant == variant) & (pc.day_type == "weekday")]
        l = pl[(pl.variant == variant) & (pl.day_type == "weekday")]
        rows = []
        for r in c.itertuples():
            ll = l[l.city == r.city]
            lo, hi = ll.loc[ll["median_kmh"].idxmin()], ll.loc[ll["median_kmh"].idxmax()]
            rows.append([r.city, _i(r.n_trips), _i(r.n_lines), _f(r.median_kmh, 1), _f(r.wmedian_vkm_kmh, 1), f"{_f(r.q1_kmh, 1)} – {_f(r.q3_kmh, 1)}",
                         f"{_f(lo.median_kmh, 1)} (l. {lo.line}) – {_f(hi.median_kmh, 1)} (l. {hi.line})", _i(r.n_excluded), _i(r.n_length_disagree), _i(r.n_no_shape),
                         _f(r.median_stops_only_kmh, 1), _f(100 * r.share_trips_with_layover, 1)])
        A(f"Dzień roboczy {ref} (wersja `official` daje te same liczby, bo wszystkie sieci tramwajowe są w feedach oficjalnych):")
        A("")
        A(table(rows, ["Miasto", "kursy", "linie", "mediana kursów, km/h", "mediana ważona wozkm", "kwartyle kursów", "zakres median linii (min-max)", "wykluczone", "kształt ≠ przystanki > 15 %", "bez kształtu", "mediana z odległości między przystankami", "% kursów z postojem wyr."], "lrrrrrlrrrrr"))
        A("")
    A("Wykresy: `tram_speed_per_city.png` (rozkład kursów), `tram_speed_per_line.png` (mediany i kwartyle linii), `tram_speed_hourly.png` (mediana wg godziny odjazdu); tabele: `tram_speed_per_line.csv`, `tram_speed_per_city.csv`, `tram_speed_hourly.csv`, kursy: `tram_speed_trips.csv`. Wykres JSON: `results/charts/tram_speed.json`.")
    A("")
    A("**Zastrzeżenia.** (1) Prędkości rozkładowe zależą od tego, jak feed dzieli linię na kursy i gdzie przypisuje czasy przystankom (interpolacja); (2) porównanie miast zmienia się o 0,5-1 km/h zależnie od użycia kształtu lub linii prostej; (3) Trójmiasto to tylko Gdańsk, GZM to cała sieć Tramwajów Śląskich w feedzie (kilkanaście miast, długie linie międzymiastowe), więc to nie jest „miasto” w sensie rdzenia; (4) feedy nie opisują prędkości rzeczywistej.")
    A("")
    A("### 4.1 Przystanki tramwajowe bez kursów tramwaju w dniu ref. (Kraków, Łódź)")
    A("")
    A("Faza 0 wykazała w maskach pokrycia, że w Krakowie i Łodzi część przystanków tramwajowych OSM nie ma odpowiednika z kursem tramwaju (remonty, komunikacja zastępcza). Co pokazują feedy:")
    A("")
    gap = tram["gap"]
    inact = tram["inactive"].set_index("city")["tram_routes_without_trips_on_day"]
    rows = []
    for city, g in gap.groupby("city"):
        rows.append([city, _i(len(g)), inact.get(city, "") or "brak"])
    A(table(rows, ["Miasto", "przystanki tramwajowe OSM w FUA bez przystanku tramwajowego z kursem w dniu ref. w promieniu 75 m", "linie tramwajowe w feedzie bez kursów w dniu ref."], "lrl"))
    A("")
    un = tram["unserved"]
    A("Przystanki z `stops.txt` feedów tramwajowych, które na pewno miały kursy tramwaju w innym dniu, a w dniu ref. nie: " + "; ".join(f"{r.city} {int(r.tram_stops_unserved_on_day)} z {int(r.tram_stops_all_dates)}" for r in un.itertuples()) + ". "
      "Czyli luka Krakowa i Łodzi **nie jest widoczna w kalendarzu feedu**: feed po prostu nie zawiera przystanków na odcinkach wyłączonych z ruchu (dla Krakowa feed ma w `routes.txt` linie tramwajowe bez kursów w dniu ref.: patrz tabela). To znaczy, że wyłączone odcinki są po stronie OSM, a prędkości powyżej dotyczą kursujących odcinków.")
    A("")
    cand = tram["replacement"]
    for city in ("Kraków", "Łódź"):
        c = cand[(cand.city == city)].head(8)
        if len(c):
            A(f"Linie autobusowe feedu, które w dniu ref. mijają (≤ 100 m) najwięcej tych przystanków (kandydaci na komunikację zastępczą, nie potwierdzone nazwą linii w feedzie), {city}: "
              + ", ".join(f"{r.bus_line} ({int(r.gap_stops_within_100m)} z {int(r.gap_stops_total)})" for r in c.itertuples()) + ".")
            A("")
    A("Lista przystanków: `tram_stops_osm_without_tram_service.csv`; kandydaci: `tram_gap_bus_candidates.csv`; linie z utraconymi przystankami w Warszawie (skrócone kursy): `tram_stops_unserved_by_line.csv`.")
    A("")

    # ---- top stops
    t = top["table"]
    A("## 5. Dziesięć klastrów przystanków o największej liczbie odjazdów (§7.3)")
    A("")
    A("Odjazdy 6:00-20:00 w dniu ref. (bez ostatniego przystanku kursu; autobusy zastępcze kolei pominięte), po deduplikacji, **suma po liniach i kierunkach** (nie odstęp). Przystanki klastrowane po położeniu w promieniu 100 m (`stop_cluster_radius_m`), bez względu na `parent_station` i feed. Klastrowanie zachłanne (lider = przystanek o największej liczbie odjazdów zabiera niezajęte przystanki w promieniu 100 m), bo łączenie przechodnie (single linkage) zlałoby przystanki co 80 m wzdłuż ulicy w jeden korytarz; kolumna `deps_single_linkage_component` w `top10_stops.csv` pokazuje, o ile większy byłby klaster przy łączeniu przechodnim. Pełna tabela: `top10_stops.csv`.")
    A("")
    for variant in gs.VARIANTS:
        A(f"### Wariant `{variant}`")
        A("")
        rows = []
        for a in gs.PHASE1:
            tt = t[(t.agglomeration == a) & (t.variant == variant)]
            rows.append([AGG_PL[a], "; ".join(f"{r['name'].split(' / ')[0]} ({r.departures_per_hour:.0f})" for _, r in tt.iterrows())])
        A(table(rows, ["Aglomeracja", "klastry (nazwa, odjazdów/h)"]))
        A("")
    A("**Wnioski z kontroli.**")
    A("")
    A("- Wszystkie dziesiątki to plausibilne węzły: pętle i centra przesiadkowe (Warszawa: Ratusz Arsenał z metrem M2, Dw. Centralny, Rondo Waszyngtona, Pl. Zawiszy; Kraków: Politechnika, Jubilat, Plac Inwalidów; Wrocław: Pl. Grunwaldzki, Arkady; Gliwice i Brynów Centrum Przesiadkowe w GZM). Maksimum to 173 odjazdy/h (Warszawa), w pozostałych aglomeracjach 116-167 odjazdów/h w pierwszym klastrze.")
    A("- **Metro i kolej łączą się z przystankami naziemnymi** (w podglądzie fazy 0 kolumny metro i kolej były puste): Ratusz Arsenał ma 608 odjazdów metra obok 1 564 tramwajów i 254 autobusów; Dw. Centralny łączy kolej (265 odjazdów) z autobusami; Pl. Zawiszy łączy przystanki ZTM, WKD i kolej. Metro samo nie dominuje: na Ratuszu Arsenał to 608 odjazdów w 14 h wobec 1 564 odjazdów tramwajów.")
    A("- **Duplikaty**: po zmianie klucza (linia + przystanek + minuta + przystanek końcowy kursu; sam kierunek nie wystarcza, bo linie ALD w Krakowie nie mają `direction_id`) nie zostaje żadne podejrzane zdublowanie powyżej progu 5 %. Wstępnie flagowane Kraków (Jubilat, Plac Inwalidów, Konopnickiej, Muzeum Narodowe, 5-8 %), Trójmiasto (Wrzeszcz PKP, 19 %) i GZM (Katowice Dworzec 8,6 %, Sosnowiec 7 %) były artefaktem klucza bez przystanku końcowego (sprawdzone na liniach ALD w Krakowie: dwa kursy tej samej linii w tej samej minucie na jednym słupku, bez `direction_id`, o różnych przystankach końcowych). Po zmianie klucza Wrzeszcz PKP i Katowice Dworzec spadają do 0 %; Katowice Sądowa (3,4 %) i Chorzowska (4,2 %) w GZM zostają poniżej progu, przyczyny nie zbadano.")
    A("- **Dworce kolejowe a promień klastra**: perony kolejowe `Gdańsk Główny` leżą 85 m od najbliższego przystanku miejskiego „Dworzec Główny”, a `Wrocław Główny` 193 m od najbliższego „DWORZEC GŁÓWNY”. W Gdańsku klaster zachłanny (promień liczony od lidera) nie zabrał peronów kolejowych (deps_rail = 0 w pierwszym klastrze), choć łączenie przechodnie by to zrobiło (kolumna `deps_single_linkage_component`, flaga w `top10_stops.csv`); we Wrocławiu dystans przekracza 100 m. To skutek wybranej reguły klastrowania, nie braku kursów; do miary częstotliwości kolej i przystanki miejskie węzła trzeba będzie łączyć świadomie. Kolej łączy się z miejskimi przystankami tam, gdzie punkty są bliżej (Warszawa Centralna, Ochota, Katowice, Sosnowiec, Gdańsk Wrzeszcz).")
    A("- **Trójmiasto**: pierwsza dziesiątka składa się z osobnych klastrów Gdańska i Gdyni (feedy nie są łączone w jeden przystanek); żaden klaster nie powstaje z przystanków obu feedów.")
    A("")

    A("## 6. Ograniczenia, niespodzianki i co sprawdzono")
    A("")
    A("- **Prędkość i wozkm to wielkości rozkładowe.** Brak opóźnień, odwołań, objazdów i prac drogowych.")
    A("- **Pokrycie**: wartości FUA Warszawy, Krakowa, Wrocławia, Łodzi i Trójmiasta oznaczone „niepełne pokrycie GTFS”; Poznań i GZM spełniają 85 %. Wyniki per mieszkaniec FUA nie nadają się do porównań bez tej flagi.")
    A("- **Wariant `official` i pokrycie**: współczynnik pokrycia policzono w fazie 0 dla 42 feedów; dla `official` (mniej feedów) pokrycie jest co najwyżej takie jak podane; w tabelach pole jest puste, a flaga zostaje.")
    A("- **Kolej a rdzeń**: kolej ogólnopolska jest przycinana odcinkami, więc długie odcinki podmiejskie dają wozkm proporcjonalne do długości linii prostej w obszarze; kursy dalekobieżne (IC) przecinające obszar są liczone tylko w części w obszarze.")
    A("- **Wozkm to kursy z przystankami, nie przebiegi techniczne**: dojazdy do zajezdni i kursy puste nie są w GTFS.")
    A("- **Dzień ruchu**: kursy po północy poprzedniego dnia ruchu nie są dodawane do dnia referencyjnego (kursy 24+ h dnia ref. są w godz. 24-29).")
    A("- **Siatka ludności NSP** przypisuje komórki po środku komórki; dla rdzeni wąskich (Sopot) wpływ na wozkm/mieszk. jest nieznany.")
    (QA / "supply.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
