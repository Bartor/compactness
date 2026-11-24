# Podaż, prędkość tramwajów i kontrola przystanków (faza 2, krok `supply`)

Dzień roboczy: **2026-11-25** (środa), sobota: **2026-11-28**. Rozkłady jazdy pobrane 2026-11-23; ludność: **NSP 2021, stan 2021-03-31** (siatka 1 km, ludność rezydująca, komórka należy do obszaru, gdy jej środek leży w obszarze). Każdy wynik liczony w dwóch wariantach zestawu feedów: `official` (feedy z briefu i dodatki od wydawcy) i `all` (wszystkie 42). Źródła liczb: pliki CSV w tym folderze; metryki w `results/metrics/metrics_supply.csv`.

## 1. Warstwa usługowa: które kursy się liczą (`pipeline/gtfs_service.py`)

Jedno miejsce, w którym zapada decyzja, które kursy dnia są liczone (API: `feeds_for`, `active_trips`, `stop_times`, `stops`). Reguły w kolejności stosowania:

1. **Konfiguracja** (`drop_routes` / `drop_agencies` w `config.yaml`, stosowane w `gtfs_io`): w tej chwili tylko linie 6 i 61 MUK Zgierz (te same kursy co w MPK Łódź), 148 kursów w dniu ref.
2. **SKM Warszawa** (`agency_id = SKM` w `polish_trains`) odrzucona: te same kursy są w `warsaw_ztm` (284 vs 284 kursów w dniu ref.; klucz linia + znormalizowana nazwa pierwszego przystanku + minuta odjazdu; zgodność 100 % i 100 % w drugą stronę). SKM Trójmiasto to osobna agencja (`SKMT`) i zostaje.
3. **Kolej ogólnopolska** (`polish_trains`, w konfiguracji `rail: true`): zostają kursy z co najmniej jednym przystankiem w FUA + 15 km danej aglomeracji. Zostaje cały kurs (wszystkie wiersze `stop_times`), kolumna `in_buffer` zaznacza przystanki w buforze. Pozostałe feedy nie są przycinane (każdy obsługuje jeden obszar).
4. **Dokładne duplikaty kursów w jednym feedzie**: to samo `route_id`, kierunek, `block_id`, pierwszy odjazd i ta sama sekwencja przystanków z tymi samymi czasami (przystanek porównywany po położeniu zaokrąglonym do 1 m, bo GZM powtarza rekordy przystanków pod innymi `stop_id` i nazwami, np. Zaborze Wolności / Poremba Wolności w tym samym punkcie), kursujące tego samego dnia (także pod różnymi `service_id`), inny `trip_id`. Zostaje kurs o najmniejszym `trip_id`.
   4b. **Duplikaty blokowe**: ta sama linia, kierunek, niepusty `block_id`, godzina pierwszego odjazdu i ostatniego przyjazdu oraz liczba przystanków, ale przystanki przesunięte (GZM: 242 pary, przystanek przesunięty do 350 m). Jeden pojazd (blok) nie przejedzie dwóch takich kursów, zostaje kurs o mniejszym `trip_id`.
5. **Duplikaty między feedami** w obrębie aglomeracji i wariantu: klucz linia (`route_short_name`) + znormalizowana nazwa pierwszego przystanku + minuta odjazdu. Kopię o niższym priorytecie (feed miejski przed `polish_trains`, oficjalny przed nieoficjalnym, potem kolejność w konfiguracji) odrzuca się tylko wtedy, gdy co najmniej 90 % (i co najmniej 3) kursów danej linii pasuje do feedu o wyższym priorytecie; odrzucane są wyłącznie kursy pasujące. Para poniżej progu jest tylko raportowana (`cross_feed_duplicates.csv`).
6. **`frequencies.txt`**: używa go tylko metro w `warsaw_ztm` (16 szablonów kursów); rozwijane na pojedyncze kursy (`<trip_id>~k`), czasy przesunięte o początek przejazdu.

Autobusy zastępcze kolei (`route_type` 3 w `polish_trains` i `warsaw_wkd`) mają `is_replacement_bus = True`: zostają w tabelach jako autobus, a miary kolejowe mają je wyłączać. Liczba kursów w dniu ref. i wariancie `all` jest ich Warszawa 151, Kraków 4, Wrocław 54, Poznań 0, Łódź 6, Trójmiasto 139, GZM 41 (podzbiór autobusów).

### 1.1 Kursy przed → po regułach (dzień roboczy, wariant `all`; pełna tabela per feed i sobota: `service_summary.csv`)

Wariant `official`, 2026-11-25:

| Aglomeracja | kursy surowe (po rozwinięciu `frequencies`) | − konfig. (Zgierz) | − SKM Warszawa | − poza FUA+15 km (kolej) | − dokładne duplikaty | − duplikaty blokowe | − między feedami | kursy po regułach |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GZM | 38 014 | 0 | 284 | 6 074 | 7 783 | 242 | 0 | 23 631 |
| Kraków | 25 342 | 0 | 284 | 6 578 | 0 | 0 | 0 | 18 480 |
| Łódź | 17 682 | 0 | 284 | 6 711 | 0 | 0 | 0 | 10 687 |
| Poznań | 19 527 | 0 | 284 | 6 556 | 0 | 0 | 0 | 12 687 |
| Trójmiasto | 20 090 | 0 | 284 | 6 345 | 0 | 0 | 0 | 13 461 |
| Warszawa | 43 248 | 0 | 284 | 5 706 | 0 | 0 | 0 | 37 258 |
| Wrocław | 20 302 | 0 | 284 | 6 388 | 0 | 0 | 0 | 13 630 |

Wariant `all`, 2026-11-25:

| Aglomeracja | kursy surowe (po rozwinięciu `frequencies`) | − konfig. (Zgierz) | − SKM Warszawa | − poza FUA+15 km (kolej) | − dokładne duplikaty | − duplikaty blokowe | − między feedami | kursy po regułach |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GZM | 38 014 | 0 | 284 | 6 074 | 7 783 | 242 | 0 | 23 631 |
| Kraków | 25 777 | 0 | 284 | 6 578 | 0 | 0 | 0 | 18 915 |
| Łódź | 19 462 | 148 | 284 | 6 711 | 0 | 0 | 0 | 12 319 |
| Poznań | 19 527 | 0 | 284 | 6 556 | 0 | 0 | 0 | 12 687 |
| Trójmiasto | 20 090 | 0 | 284 | 6 345 | 0 | 0 | 0 | 13 461 |
| Warszawa | 47 662 | 0 | 284 | 5 706 | 1 | 0 | 0 | 41 671 |
| Wrocław | 20 581 | 0 | 284 | 6 388 | 0 | 0 | 0 | 13 909 |

Sobota 2026-11-28, wariant `all`: GZM 19 527 → 14 625; Kraków 16 868 → 11 624; Łódź 14 094 → 8 613; Poznań 13 781 → 8 476; Trójmiasto 13 938 → 8 752; Warszawa 30 932 → 26 239; Wrocław 14 417 → 9 259.

Uwaga: „kursy surowe” obejmują kursy z `drop_routes` (Zgierz), żeby tabela się bilansowała; w `trips_raw` kolej to wszystkie 7 453 kursów ogólnopolskich.

### 1.2 Kontrole warstwy

- **GZM**: 8 025 z 30 561 kursów (26.3 %) usuniętych jako duplikaty (dokładnych: 7 783, blokowych: 242). Duplikaty różnią się `trip_id`, `shape_id` i (w części) rekordami przystanków o tym samym położeniu. W sobotę 2026-11-28 reguły nie znajdują duplikatów (przyczyny nie badano). Wcześniejszy test fazy 0 (ten sam `service_id`) znajdował 7 693 dokładnych duplikatów; reguła tutaj łapie także duplikaty pod różnymi `service_id` i rekordy przystanków pod różnymi identyfikatorami.
- **Kursy z jednym duplikatem poza GZM**: `warsaw_zakroczym` (ręcznie ułożony feed) 1 kurs (dwa `service_id`, identyczny przebieg i godzina).
- **Duplikaty między feedami**: po regule 1 (Zgierz) test (linia + pierwszy przystanek + minuta) nie znajduje żadnej pary w żadnej aglomeracji i wariancie (`cross_feed_duplicates.csv` jest pusty; odrzuconych par: 0). Kontrola uzupełniająca bez nazwy przystanku: ta sama linia i ta sama minuta w dwóch feedach zdarza się przypadkiem (np. linie 1-12 MZK Wejherowo i Gdańska, linie warszawskie ZTM i `warsaw_gpa`: 54 w Trójmieście, 590 w Warszawie, 76 w Łodzi, 7 we Wrocławiu, 1 w Krakowie), ale w żadnym z tych przypadków pierwsze przystanki nie leżą bliżej niż 150 m. Test wykrywa dublowanie: na sztucznie podwojonych liniach 6 i 61 z Łodzi odrzuca 220 z 220 kursów kopii.
- **Uwaga o fazie 0**: `duplicate_trips_check.csv` z fazy 0 podaje dla `warsaw_otwock` 197 kursów w dniu ref., a feed ma ich 138 (wg `service_dates` + `trip_stats`; przyczyny rozbieżności nie badano).

## 2. Wozokilometry (§4.7)

Metoda (`pipeline/supply_core.py`): odcinek = kolejne dwa przystanki kursu. Długość odcinka = odległość w linii prostej (EPSG:2180) przeskalowana tak, by suma odcinków kursu dawała długość kursu z kształtu trasy (`shapes`), jeśli stosunek kształtu do odległości między przystankami mieści się w [0,8; 2,0]; w przeciwnym razie (i bez kształtu) długość to odległość między przystankami. Odcinek z oboma przystankami w obszarze liczony w całości; z jednym końcem w obszarze: proporcjonalnie do długości linii prostej leżącej w obszarze; z oboma końcami poza obszarem: 0 (nawet gdy prosta zahacza o obszar). Godzina odcinka = godzina odjazdu z jego pierwszego przystanku (godziny 24-29 to kursy po północy dnia ruchu). Kolej ogólnopolska przycięta tak samo, autobusy zastępcze liczone jako autobus i pokazane osobno.

Obszary: **FUA** (dla Trójmiasta i GZM suma FUA wg konfiguracji) i **rdzeń** (miasta URAU; Trójmiasto: Gdańsk + Gdynia + Sopot). Ludność z siatki spisowej NSP 2021 (stan 2021-03-31). Pokrycie GTFS: udział ludności FUA mieszkającej w gminach o pokryciu przystanków ≥ 85 % (`population_coverage_preliminary.csv`, kolumna `gmina_pop_share_cov_ge_85`, stan po 42 feedach); dla rdzenia: udział przystanków OSM z odpowiednikiem w GTFS (nie ludności). Poniżej 0,85 wynik niesie flagę **„niepełne pokrycie GTFS”**. Dla wariantu `official` pokrycia osobno nie liczono (poza aglomeracjami, w których oba warianty mają te same feedy: Poznań, Trójmiasto, GZM), więc wartość jest pusta (null), a flaga zostaje.

| Aglomeracja | ludność FUA (NSP 2021) | ludność rdzenia | pokrycie FUA (ludność, ≥ 85 %) | pokrycie rdzenia (przystanki) |
|---|---:|---:|---:|---:|
| Warszawa | 3 485 881 | 1 865 105 | 0,778 | 0,972 |
| Kraków | 1 411 779 | 793 392 | 0,731 | 0,978 |
| Wrocław | 1 011 966 | 673 906 | 0,715 | 0,977 |
| Poznań | 974 744 | 547 682 | 0,866 | 0,949 |
| Łódź | 1 044 086 | 665 696 | 0,842 | 0,963 |
| Trójmiasto | 1 089 730 | 752 435 | 0,811 | 0,965 |
| GZM | 2 057 054 | 1 643 705 | 0,963 | 0,969 |

### 2.1 Wozokilometry na mieszkańca na dobę, FUA, dzień roboczy 2026-11-25

| Aglomeracja | wariant | razem | tramwaj | metro | kolej | autobus | trolejbus | prom | inne | w tym ZKA | wozkm razem | niepełne pokrycie |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Warszawa | official | 0,169 | 0,029 | 0,007 | 0,025 | 0,109 | – | – | – | 0,000 | 590 189 | tak |
| Warszawa | all | 0,193 | 0,029 | 0,007 | 0,025 | 0,132 | – | – | – | 0,000 | 671 095 | tak |
| Kraków | official | 0,184 | 0,038 | – | 0,016 | 0,130 | – | – | – | 0,000 | 259 619 | tak |
| Kraków | all | 0,188 | 0,038 | – | 0,016 | 0,134 | – | – | – | 0,000 | 265 079 | tak |
| Wrocław | official | 0,193 | 0,048 | – | 0,025 | 0,120 | – | – | – | 0,000 | 195 651 | tak |
| Wrocław | all | 0,200 | 0,048 | – | 0,025 | 0,127 | – | – | – | 0,000 | 202 404 | tak |
| Poznań | official | 0,177 | 0,041 | – | 0,023 | 0,113 | – | – | – | – | 172 647 | nie |
| Poznań | all | 0,177 | 0,041 | – | 0,023 | 0,113 | – | – | – | – | 172 647 | nie |
| Łódź | official | 0,150 | 0,041 | – | 0,018 | 0,091 | – | – | – | 0,000 | 156 344 | tak |
| Łódź | all | 0,171 | 0,041 | – | 0,018 | 0,112 | – | – | – | 0,000 | 178 221 | tak |
| Trójmiasto | official | 0,164 | 0,022 | – | 0,022 | 0,105 | 0,015 | – | – | 0,001 | 178 988 | tak |
| Trójmiasto | all | 0,164 | 0,022 | – | 0,022 | 0,105 | 0,015 | – | – | 0,001 | 178 988 | tak |
| GZM | official | 0,190 | 0,018 | – | 0,010 | 0,159 | 0,002 | – | – | 0,000 | 389 891 | nie |
| GZM | all | 0,190 | 0,018 | – | 0,010 | 0,159 | 0,002 | – | – | 0,000 | 389 891 | nie |

Jednostka: wozkm/mieszk./dobę (kolumna „wozkm razem”: wozkm/dobę). „–” = brak takiego trybu w feedach wariantu (nie zero). Sobota i godziny: `supply_vkm_summary.csv`, `supply_vkm_hourly.csv`, wykresy `vkm_hourly_<aglomeracja>.png`, `vkm_per_inhabitant.png`.

### 2.2 Wozokilometry na mieszkańca na dobę, rdzeń, dzień roboczy 2026-11-25

| Aglomeracja | wariant | razem | tramwaj | metro | kolej | autobus | trolejbus | prom | inne | w tym ZKA | wozkm razem | niepełne pokrycie |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Warszawa | official | 0,249 | 0,054 | 0,014 | 0,016 | 0,166 | – | – | – | 0,000 | 463 646 | nie |
| Warszawa | all | 0,250 | 0,054 | 0,014 | 0,016 | 0,167 | – | – | – | 0,000 | 465 611 | nie |
| Kraków | official | 0,243 | 0,068 | – | 0,010 | 0,165 | – | – | – | 0,000 | 192 969 | nie |
| Kraków | all | 0,243 | 0,068 | – | 0,010 | 0,165 | – | – | – | 0,000 | 192 969 | nie |
| Wrocław | official | 0,249 | 0,073 | – | 0,013 | 0,163 | – | – | – | 0,000 | 167 572 | nie |
| Wrocław | all | 0,250 | 0,073 | – | 0,013 | 0,164 | – | – | – | 0,000 | 168 501 | nie |
| Poznań | official | 0,209 | 0,073 | – | 0,012 | 0,124 | – | – | – | – | 114 418 | nie |
| Poznań | all | 0,209 | 0,073 | – | 0,012 | 0,124 | – | – | – | – | 114 418 | nie |
| Łódź | official | 0,206 | 0,061 | – | 0,011 | 0,134 | – | – | – | 0,000 | 137 275 | nie |
| Łódź | all | 0,209 | 0,061 | – | 0,011 | 0,137 | – | – | – | 0,000 | 139 273 | nie |
| Trójmiasto | official | 0,202 | 0,032 | – | 0,022 | 0,126 | 0,022 | – | – | 0,000 | 151 643 | nie |
| Trójmiasto | all | 0,202 | 0,032 | – | 0,022 | 0,126 | 0,022 | – | – | 0,000 | 151 643 | nie |
| GZM | official | 0,196 | 0,023 | – | 0,009 | 0,162 | 0,003 | – | – | 0,000 | 322 109 | nie |
| GZM | all | 0,196 | 0,023 | – | 0,009 | 0,162 | 0,003 | – | – | 0,000 | 322 109 | nie |

Jednostka: wozkm/mieszk./dobę (kolumna „wozkm razem”: wozkm/dobę). „–” = brak takiego trybu w feedach wariantu (nie zero). Sobota i godziny: `supply_vkm_summary.csv`, `supply_vkm_hourly.csv`, wykresy `vkm_hourly_<aglomeracja>.png`, `vkm_per_inhabitant.png`.

**Jak czytać.** Wozkm na mieszkańca FUA mieszają dwie rzeczy: gęstość sieci i luki w danych (§6). Dla Warszawy, Krakowa, Wrocławia, Łodzi i Trójmiasta pokrycie FUA jest poniżej 85 %, więc wartości FUA są zaniżone przez brak przewoźników podmiejskich; do porównań bardziej nadaje się rdzeń (pokrycie ≥ 95 %). Różnica `official` → `all` pokazuje wkład nieoficjalnych przepakowań (tylko podmiejskie autobusy).

Kontrola długości kursów: udział wozkm skalowanych z kształtu trasy to Warszawa 99.4 %, Kraków 88.8 %, Wrocław 99.8 %, Poznań 100.0 %, Łódź 89.2 %, Trójmiasto 98.6 %, GZM 99.8 %; liczba kursów z niewiarygodnym kształtem (stosunek poza [0,8; 2,0]): Warszawa 30, Kraków 0, Wrocław 0, Poznań 2, Łódź 525, Trójmiasto 62, GZM 1. Odcinki bez współrzędnych przystanku: Warszawa 0, Kraków 0, Wrocław 0, Poznań 0, Łódź 640, Trójmiasto 0, GZM 0. (`supply_vkm_diagnostics.csv`)

**Defekt danych Łódź (znaleziony przy kontroli długości).** W feedzie `lodz` przystanki 3876 i 3877 (Pl. Niepodległości) mają `stop_lat = stop_lon = 0`. `gtfs_io` liczył z nich odległości rzędu tysięcy km (np. linie nocne N3A, N4A: 12 000 km „odległości między przystankami”), co psuło kontrolę kształtu i długości kursów bez kształtu. Warstwa usługowa traktuje współrzędne (0, 0) jako brak (x, y = null) i przelicza `dist_stops_m` z pominięciem takiego przystanku; zmienia to `dist_m` tylko dwóch kursów bez kształtu (2 kursy 6 000 km → 0 m). Poza tym w Łodzi znaczna część kursów autobusowych ma kształt krótszy niż 80 % łańcucha przystanków (liczby w akapicie wyżej, `n_trips_shape_ratio_bad`); dla nich użyto odległości między przystankami, więc wozkm Łodzi są ustalone głównie z linii prostych (dolne ograniczenie, zaniżone o krzywiznę tras rzędu kilku procent).

### 2.3 Miejscokilometry

**Nie liczone.** GTFS nie podaje typu taboru ani pojemności, a w repozytorium i dostępnych źródłach nie ma wiarygodnej tabeli pojemności per tryb i miasto (tabor różni się linią i porą dnia: tramwaje 100-250 miejsc, autobusy 80-180, metro ok. 1 000 na pociąg). Przyjęcie jednej pojemności na tryb byłoby założeniem bez źródła i przesłaniałoby różnice między miastami, więc wariant pominięto. Propozycja dla konfiguracji: klucz `seat_capacity` {tryb: {miasto: miejsca}} z jawnym polem `source`; po jego uzupełnieniu miejscokilometry to wozkm × pojemność z `supply_vkm_summary.csv`.

## 3. Test anomalii (§5) na zdeduplikowanej usłudze

Wozkm dnia referencyjnego (cała długość kursów, po regułach 1-4 na poziomie feedu; dla kolei: kursy dotykające FUA + 15 km) kontra mediana wozkm dni roboczych (pon-pt, bez świąt i okresu 24.12-6.01) w okresie ważności feedu (dni z kursami). Dla soboty: mediana sobót. Próg 5 %. Reguła 5 (duplikaty między feedami) nie wchodzi do testu, bo jest zależna od dnia i znikoma (patrz 1.2).

**Dzień roboczy 2026-11-25:** 48 par (aglomeracja, feed); odchylenie w przedziale od -0,86 % do 1,75 %; powyżej 5 %: **0**.

**Sobota 2026-11-28:** 48 par (aglomeracja, feed); odchylenie w przedziale od -1,16 % do 0,99 %; powyżej 5 %: **0**.

Pełna tabela: `anomaly_test_dedup.csv`. Słabość testu (jak w fazie 0): mediana krótkich feedów pochodzi z tego samego 2-3-tygodniowego okna co dzień referencyjny, a dla feedów rocznych obejmuje wakacje i ferie; test nie wykryje feedu „feryjnego” w całym oknie. Liczba dni w medianie jest w kolumnie `n_days_median`.

## 4. Rozkładowa prędkość komunikacyjna tramwajów (§4.7, grafika 5 z §15)

Uwaga o nazwie: brief (§4.7) nazywa tę miarę prędkością eksploatacyjną. Liczona tu wielkość (długość kursu przez czas od pierwszego odjazdu do ostatniego przyjazdu, bez postojów na pętlach) to w polskiej praktyce prędkość komunikacyjna; prędkość eksploatacyjna obejmuje także postoje na pętlach i jest niższa. Od 2026-11-24 używamy nazwy „komunikacyjna”; definicja i liczby się nie zmieniły.

**To jest rozkładowa prędkość komunikacyjna z postojami na przystankach** = długość kursu / (ostatni przyjazd − pierwszy odjazd), z rozkładu jazdy. Nie jest to prędkość jazdy między przystankami ani prędkość rzeczywista (warstwa 6b odłożona).

Reguły (`pipeline/tram_speed.py`): wszystkie kursy tramwajowe dnia po deduplikacji. Długość z kształtu trasy; dla każdego kursu liczona też suma odległości w linii prostej między przystankami; gdy obie różnią się o więcej niż 15 % (flaga `length_disagree`) albo brak kształtu, w wyniku używana jest odległość między przystankami (dolne ograniczenie, więc prędkość lekko zaniżona). Wykluczone z każdej statystyki: kursy krótsze niż 1 km, krótsze niż 5 min, z mniej niż 3 przystankami (zjazdy do zajezdni, wyjazdy techniczne) oraz o prędkości poza 5-60 km/h (liczby w `tram_speed_excluded.csv`). Postój wewnątrz kursu dłuższy niż 120 s traktowany jest jako postój wyrównawczy; wynik główny go zawiera, wersja bez niego jest w CSV (`median_ex_layover_kmh`). Mediana ważona = mediana ważona długością kursu (wozkm). Żaden inny z 42 feedów nie ma linii tramwajowych.

Dzień roboczy 2026-11-25 (wersja `official` daje te same liczby, bo wszystkie sieci tramwajowe są w feedach oficjalnych):

| Miasto | kursy | linie | mediana kursów, km/h | mediana ważona wozkm | kwartyle kursów | zakres median linii (min-max) | wykluczone | kształt ≠ przystanki > 15 % | bez kształtu | mediana z odległości między przystankami | % kursów z postojem wyr. |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| GZM | 3 059 | 27 | 17,2 | 18,2 | 15,9 – 20,0 | 13,9 (l. T38) – 23,3 (l. T22) | 0 | 227 | 0 | 16,4 | 0,1 |
| Gdańsk | 1 542 | 10 | 18,0 | 18,0 | 17,5 – 18,4 | 17,0 (l. 5) – 19,7 (l. 7) | 0 | 22 | 0 | 16,7 | 0,0 |
| Kraków | 3 710 | 23 | 19,8 | 20,0 | 18,9 – 21,0 | 15,9 (l. 72) – 23,3 (l. 16) | 0 | 54 | 0 | 18,6 | 0,0 |
| Poznań | 3 557 | 20 | 19,5 | 20,1 | 17,7 – 22,9 | 15,9 (l. 17) – 27,1 (l. 14) | 12 | 0 | 0 | 18,9 | 0,0 |
| Warszawa | 7 123 | 26 | 18,6 | 18,6 | 17,7 – 19,5 | 15,3 (l. 31) – 25,0 (l. 2) | 16 | 13 | 0 | 17,9 | 0,0 |
| Wrocław | 4 164 | 24 | 16,3 | 16,6 | 15,4 – 17,6 | 13,3 (l. 8) – 19,1 (l. 10) | 4 | 3 | 0 | 15,6 | 0,0 |
| Łódź | 3 312 | 25 | 16,9 | 17,2 | 15,6 – 18,8 | 14,8 (l. 3) – 22,9 (l. P1) | 40 | 70 | 0 | 16,2 | 0,0 |

Wykresy: `tram_speed_per_city.png` (rozkład kursów), `tram_speed_per_line.png` (mediany i kwartyle linii), `tram_speed_hourly.png` (mediana wg godziny odjazdu); tabele: `tram_speed_per_line.csv`, `tram_speed_per_city.csv`, `tram_speed_hourly.csv`, kursy: `tram_speed_trips.csv`. Wykres JSON: `results/charts/tram_speed.json`.

**Zastrzeżenia.** (1) Prędkości rozkładowe zależą od tego, jak feed dzieli linię na kursy i gdzie przypisuje czasy przystankom (interpolacja); (2) porównanie miast zmienia się o 0,5-1 km/h zależnie od użycia kształtu lub linii prostej; (3) Trójmiasto to tylko Gdańsk, GZM to cała sieć Tramwajów Śląskich w feedzie (kilkanaście miast, długie linie międzymiastowe), więc to nie jest „miasto” w sensie rdzenia; (4) feedy nie opisują prędkości rzeczywistej.

### 4.1 Przystanki tramwajowe bez kursów tramwaju w dniu ref. (Kraków, Łódź)

Faza 0 wykazała w maskach pokrycia, że w Krakowie i Łodzi część przystanków tramwajowych OSM nie ma odpowiednika z kursem tramwaju (remonty, komunikacja zastępcza). Co pokazują feedy:

| Miasto | przystanki tramwajowe OSM w FUA bez przystanku tramwajowego z kursem w dniu ref. w promieniu 75 m | linie tramwajowe w feedzie bez kursów w dniu ref. |
|---|---:|---|
| GZM | 27 | T23 |
| Gdańsk | 11 | brak |
| Kraków | 44 | 62, 69 |
| Poznań | 16 | 202 |
| Warszawa | 15 | brak |
| Wrocław | 15 | 0 |
| Łódź | 66 | brak |

Przystanki z `stops.txt` feedów tramwajowych, które na pewno miały kursy tramwaju w innym dniu, a w dniu ref. nie: Warszawa 7 z 637; Kraków 0 z 353; Wrocław 0 z 447; Poznań 0 z 304; Łódź 0 z 465; Gdańsk 0 z 248; GZM 0 z 717. Czyli luka Krakowa i Łodzi **nie jest widoczna w kalendarzu feedu**: feed po prostu nie zawiera przystanków na odcinkach wyłączonych z ruchu (dla Krakowa feed ma w `routes.txt` linie tramwajowe bez kursów w dniu ref.: patrz tabela). To znaczy, że wyłączone odcinki są po stronie OSM, a prędkości powyżej dotyczą kursujących odcinków.

Linie autobusowe feedu, które w dniu ref. mijają (≤ 100 m) najwięcej tych przystanków (kandydaci na komunikację zastępczą, nie potwierdzone nazwą linii w feedzie), Kraków: 664 (31 z 44), 704 (31 z 44), 714 (31 z 44), 708 (30 z 44), 102 (7 z 44), 108 (4 z 44), 120 (4 z 44), 169 (4 z 44).

Linie autobusowe feedu, które w dniu ref. mijają (≤ 100 m) najwięcej tych przystanków (kandydaci na komunikację zastępczą, nie potwierdzone nazwą linii w feedzie), Łódź: 86 (15 z 66), 87A (14 z 66), 87B (14 z 66), 59 (13 z 66), 72A (13 z 66), 72B (13 z 66), P2 (12 z 66), N3A (11 z 66).

Lista przystanków: `tram_stops_osm_without_tram_service.csv`; kandydaci: `tram_gap_bus_candidates.csv`; linie z utraconymi przystankami w Warszawie (skrócone kursy): `tram_stops_unserved_by_line.csv`.

## 5. Dziesięć klastrów przystanków o największej liczbie odjazdów (§7.3)

Odjazdy 6:00-20:00 w dniu ref. (bez ostatniego przystanku kursu; autobusy zastępcze kolei pominięte), po deduplikacji, **suma po liniach i kierunkach** (nie odstęp). Przystanki klastrowane po położeniu w promieniu 100 m (`stop_cluster_radius_m`), bez względu na `parent_station` i feed. Klastrowanie zachłanne (lider = przystanek o największej liczbie odjazdów zabiera niezajęte przystanki w promieniu 100 m), bo łączenie przechodnie (single linkage) zlałoby przystanki co 80 m wzdłuż ulicy w jeden korytarz; kolumna `deps_single_linkage_component` w `top10_stops.csv` pokazuje, o ile większy byłby klaster przy łączeniu przechodnim. Pełna tabela: `top10_stops.csv`.

### Wariant `official`

| Aglomeracja | klastry (nazwa, odjazdów/h) |
|---|---|
| Warszawa | Ratusz Arsenał (173); Dw. Centralny (160); Marszałkowska (160); Krucza (146); Pl. Zawiszy (145); Pl. Na Rozdrożu (137); Rondo Waszyngtona (135); Rozbrat (132); Pl. Szembeka (128); Kino Femina (122) |
| Kraków | Politechnika (161); Jubilat (133); Plac Inwalidów (122); Konopnickiej (105); Bronowice SKA (102); Szpital Narutowicza (100); Krowodrza Górka P+R (98); Rondo Mogilskie (98); Teatr Słowackiego (92); Muzeum Narodowe (89) |
| Wrocław | PL. GRUNWALDZKI (135); Arkady (Capitol) (122); Kwiska (102); Pomorska (101); DWORZEC NADODRZE (100); PL. JANA PAWŁA II 06 (98); Strzegomska (Krzyżówka) (98); Pl. Orląt Lwowskich (95); Bastion Sakwowy (90); DWORZEC GŁÓWNY (87) |
| Poznań | Głogowska/Hetmańska (116); Kórnicka (95); Szymanowskiego (90); Aleje Solidarności (87); Rondo Rataje (82); Most Teatralny (77); Dworzec Zachodni (77); Wrocławska (72); Słowiańska (69); Bułgarska Enea Stadion (68) |
| Łódź | Mickiewicza-Żeromskiego (78); Włókniarzy-Mickiewicza (Dw. Ł. Kaliska) (78); Zachodnia-Limanowskiego (78); Zachodnia-Legionów (76); Bandurskiego-Dw. Łódź Kaliska (74); Zachodnia-Lutomierska (68); Kopcińskiego-Tuwima (68); Rzgowska-cm. Rzgowska (68); Śmigłego Rydza-Przybyszewskiego (64); Palki-Wojska Polskiego (64) |
| Trójmiasto | Dworzec Główny 01 (167); Brama Wyżynna 04 (118); Armii Krajowej 03 (92); Obłuże Centrum 01 (89); Wzgórze Św. Maksymiliana SKM 01 (87); Łostowice Świętokrzyska 04 (83); Centrum Nauki Experyment 02 (82); Galeria Bałtycka 05 (82); Morska - Estakada 01 (77); Wrzeszcz PKP 04 (74) |
| GZM | Katowice Dworzec (129); Gliwice Centrum Przesiadkowe (125); Katowice Sądowa (116); Brynów Centrum Przesiadkowe (115); Katowice AWF (102); Katowice Chorzowska (96); Katowice Plac Miarki (94); Dąbrowa Górnicza Centrum (86); Sosnowiec Dworzec PKP (84); Katowice Św. Jana (83) |

### Wariant `all`

| Aglomeracja | klastry (nazwa, odjazdów/h) |
|---|---|
| Warszawa | Ratusz Arsenał (173); Dw. Centralny (160); Marszałkowska (160); Krucza (146); Pl. Zawiszy (145); Pl. Na Rozdrożu (137); Rondo Waszyngtona (135); Rozbrat (132); Pl. Szembeka (128); Kino Femina (122) |
| Kraków | Politechnika (161); Jubilat (133); Plac Inwalidów (122); Konopnickiej (105); Bronowice SKA (102); Szpital Narutowicza (100); Krowodrza Górka P+R (98); Rondo Mogilskie (98); Teatr Słowackiego (92); Muzeum Narodowe (89) |
| Wrocław | PL. GRUNWALDZKI (135); Arkady (Capitol) (122); Kwiska (102); Pomorska (101); DWORZEC NADODRZE (100); PL. JANA PAWŁA II 06 (98); Strzegomska (Krzyżówka) (98); Pl. Orląt Lwowskich (95); Bastion Sakwowy (91); DWORZEC GŁÓWNY (87) |
| Poznań | Głogowska/Hetmańska (116); Kórnicka (95); Szymanowskiego (90); Aleje Solidarności (87); Rondo Rataje (82); Most Teatralny (77); Dworzec Zachodni (77); Wrocławska (72); Słowiańska (69); Bułgarska Enea Stadion (68) |
| Łódź | Zachodnia-Limanowskiego (81); Mickiewicza-Żeromskiego (78); Włókniarzy-Mickiewicza (Dw. Ł. Kaliska) (78); Zachodnia-Legionów (77); Bandurskiego-Dw. Łódź Kaliska (74); Zachodnia-Lutomierska (72); Kopcińskiego-Tuwima (69); Rzgowska-cm. Rzgowska (68); Palki-Wojska Polskiego (66); Śmigłego Rydza-Przybyszewskiego (64) |
| Trójmiasto | Dworzec Główny 01 (167); Brama Wyżynna 04 (118); Armii Krajowej 03 (92); Obłuże Centrum 01 (89); Wzgórze Św. Maksymiliana SKM 01 (87); Łostowice Świętokrzyska 04 (83); Centrum Nauki Experyment 02 (82); Galeria Bałtycka 05 (82); Morska - Estakada 01 (77); Wrzeszcz PKP 04 (74) |
| GZM | Katowice Dworzec (129); Gliwice Centrum Przesiadkowe (125); Katowice Sądowa (116); Brynów Centrum Przesiadkowe (115); Katowice AWF (102); Katowice Chorzowska (96); Katowice Plac Miarki (94); Dąbrowa Górnicza Centrum (86); Sosnowiec Dworzec PKP (84); Katowice Św. Jana (83) |

**Wnioski z kontroli.**

- Wszystkie dziesiątki to plausibilne węzły: pętle i centra przesiadkowe (Warszawa: Ratusz Arsenał z metrem M2, Dw. Centralny, Rondo Waszyngtona, Pl. Zawiszy; Kraków: Politechnika, Jubilat, Plac Inwalidów; Wrocław: Pl. Grunwaldzki, Arkady; Gliwice i Brynów Centrum Przesiadkowe w GZM). Maksimum to 173 odjazdy/h (Warszawa), w pozostałych aglomeracjach 116-167 odjazdów/h w pierwszym klastrze.
- **Metro i kolej łączą się z przystankami naziemnymi** (w podglądzie fazy 0 kolumny metro i kolej były puste): Ratusz Arsenał ma 608 odjazdów metra obok 1 564 tramwajów i 254 autobusów; Dw. Centralny łączy kolej (265 odjazdów) z autobusami; Pl. Zawiszy łączy przystanki ZTM, WKD i kolej. Metro samo nie dominuje: na Ratuszu Arsenał to 608 odjazdów w 14 h wobec 1 564 odjazdów tramwajów.
- **Duplikaty**: po zmianie klucza (linia + przystanek + minuta + przystanek końcowy kursu; sam kierunek nie wystarcza, bo linie ALD w Krakowie nie mają `direction_id`) nie zostaje żadne podejrzane zdublowanie powyżej progu 5 %. Wstępnie flagowane Kraków (Jubilat, Plac Inwalidów, Konopnickiej, Muzeum Narodowe, 5-8 %), Trójmiasto (Wrzeszcz PKP, 19 %) i GZM (Katowice Dworzec 8,6 %, Sosnowiec 7 %) były artefaktem klucza bez przystanku końcowego (sprawdzone na liniach ALD w Krakowie: dwa kursy tej samej linii w tej samej minucie na jednym słupku, bez `direction_id`, o różnych przystankach końcowych). Po zmianie klucza Wrzeszcz PKP i Katowice Dworzec spadają do 0 %; Katowice Sądowa (3,4 %) i Chorzowska (4,2 %) w GZM zostają poniżej progu, przyczyny nie zbadano.
- **Dworce kolejowe a promień klastra**: perony kolejowe `Gdańsk Główny` leżą 85 m od najbliższego przystanku miejskiego „Dworzec Główny”, a `Wrocław Główny` 193 m od najbliższego „DWORZEC GŁÓWNY”. W Gdańsku klaster zachłanny (promień liczony od lidera) nie zabrał peronów kolejowych (deps_rail = 0 w pierwszym klastrze), choć łączenie przechodnie by to zrobiło (kolumna `deps_single_linkage_component`, flaga w `top10_stops.csv`); we Wrocławiu dystans przekracza 100 m. To skutek wybranej reguły klastrowania, nie braku kursów; do miary częstotliwości kolej i przystanki miejskie węzła trzeba będzie łączyć świadomie. Kolej łączy się z miejskimi przystankami tam, gdzie punkty są bliżej (Warszawa Centralna, Ochota, Katowice, Sosnowiec, Gdańsk Wrzeszcz).
- **Trójmiasto**: pierwsza dziesiątka składa się z osobnych klastrów Gdańska i Gdyni (feedy nie są łączone w jeden przystanek); żaden klaster nie powstaje z przystanków obu feedów.

## 6. Ograniczenia, niespodzianki i co sprawdzono

- **Prędkość i wozkm to wielkości rozkładowe.** Brak opóźnień, odwołań, objazdów i prac drogowych.
- **Pokrycie**: wartości FUA Warszawy, Krakowa, Wrocławia, Łodzi i Trójmiasta oznaczone „niepełne pokrycie GTFS”; Poznań i GZM spełniają 85 %. Wyniki per mieszkaniec FUA nie nadają się do porównań bez tej flagi.
- **Wariant `official` i pokrycie**: współczynnik pokrycia policzono w fazie 0 dla 42 feedów; dla `official` (mniej feedów) pokrycie jest co najwyżej takie jak podane; w tabelach pole jest puste, a flaga zostaje.
- **Kolej a rdzeń**: kolej ogólnopolska jest przycinana odcinkami, więc długie odcinki podmiejskie dają wozkm proporcjonalne do długości linii prostej w obszarze; kursy dalekobieżne (IC) przecinające obszar są liczone tylko w części w obszarze.
- **Wozkm to kursy z przystankami, nie przebiegi techniczne**: dojazdy do zajezdni i kursy puste nie są w GTFS.
- **Dzień ruchu**: kursy po północy poprzedniego dnia ruchu nie są dodawane do dnia referencyjnego (kursy 24+ h dnia ref. są w godz. 24-29).
- **Siatka ludności NSP** przypisuje komórki po środku komórki; dla rdzeni wąskich (Sopot) wpływ na wozkm/mieszk. jest nieznany.
