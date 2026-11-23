# Faza 3 (dostępność, §4.6): przygotowanie, pomiar kosztu i plan liczenia

Stan: 2026-11-23. To jest **plan z kosztorysem, nie wynik**. Pełne liczenie nie zostało uruchomione; liczby z próby (sekcja 4) służą tylko do kontroli rzędu wielkości.

Pliki obok: [`benchmark.csv`](benchmark.csv) (czasy routingu), [`networks.csv`](networks.csv) (budowa sieci R5), [`cost_estimate.csv`](cost_estimate.csv) (koszt per element, miasto i siatka startów), [`sample_summary.json`](sample_summary.json) (wyniki próby, wrażliwości, pary OD), [`_meta.json`](_meta.json). Kod: `pipeline/r5_inputs.py`, `pipeline/r5_env.py`, `pipeline/r5_benchmark.py`.

## 1. Narzędzia i ustawienia

| Co | Wersja / wartość |
|---|---|
| r5py | 1.1.7 (dopisane do `requirements.txt`) |
| R5 | v7.5.1-r5py (jar w `.tools/r5-v7.5.1-r5py-all.jar`, SHA-256 `d50be106…d89be7`, zgodny z r5py) |
| Java | Temurin 21.0.13.1 z `.tools/jdk21`; JPype 1.7.1 |
| Sprzęt | 24 wątki logiczne, 64 GB RAM; routing na 20 wątkach, `-Xmx` 24 GB |

**JVM na Windows.** JPype szuka JVM najpierw w `JAVA_HOME`, potem w rejestrze; systemowa Java 15 nie uruchomi R5. `pipeline/r5_env.py` ustawia `JAVA_HOME` na `.tools/jdk21` przed importem r5py i przekazuje r5py opcje przez `sys.argv` (`--max-memory`, `--r5-classpath`, `--temporary-directory`), bo r5py czyta je przy imporcie. Jar R5 leży w `.tools`, nie w `%LOCALAPPDATA%/r5py`: tamtejszy cache r5py kasuje pliki starsze niż dwa tygodnie. Sieć R5 jest zapisywana w `data/interim/r5/<aglomeracja>/net_<wariant>/` i przebudowywana, gdy zmieni się podpis plików wejściowych (r5py rozpoznaje kopie wejść tylko po nazwie pliku, więc bez tego mógłby użyć starej kopii).

**Parametry R5 a brief i DG REGIO**

| Brief / DG REGIO | Ustawienie R5 (r5py) | Uwagi |
|---|---|---|
| okno 7:00–9:00, mediana z odjazdów co minutę | `fromTime` 25 200, `toTime` 32 400, `percentiles=[50]` | R5 (range-RAPTOR) liczy każdą minutę okna. Częstotliwości (`frequencies.txt`, metro w Warszawie) są zapisane jako zwykłe kursy, więc R5 nie losuje rozkładów i wynik jest deterministyczny |
| max czas 60 min | `maxTripDurationMinutes` 60 | |
| „max dojście 1 km” | `maxWalkTime` 12 min przy 5 km/h | R5 ogranicza dojście i odejście czasem, osobno dla każdego odcinka. Przesiadki piesze między przystankami R5 liczy po sieci, do 1 km. **Ten sam limit obcina też podróż wyłącznie pieszą** w zapytaniu „komunikacja + pieszo”, więc cel 1,5 km dalej jest osiągalny tylko z przejazdem |
| pieszo 30 min / 2,5 km | tylko WALK, 5 km/h, `max_time` 30 | 5 i 15 km/h wynikają z promieni proximity w briefie. Prędkości DG REGIO nie sprawdzono |
| rower 30 min / 7,5 km | tylko BICYCLE, 15 km/h, LTS ≤ 3 (domyślne r5py) | LTS bardzo zmienia wynik (sekcja 4.3) |
| max 2 przesiadki | `maxRides` 3 | |
| DG REGIO: OTP 1.2, 9 odjazdów co 15 min, średnia, dojście do 5 km | — | różnice opisane w RAPORT §9.2; wariant z dojściem 5 km zmierzono jako wrażliwość |

**Dostępność bez tabeli OD.** r5py 1.1.7 nie ma estymatora dostępności, a `TravelTimeMatrix` buduje ramkę pandas dla każdego startu. `r5_benchmark` woła `TravelTimeComputer` R5 bezpośrednio, w puli wątków. Wektor czasów (int, minuty, jeden na cel) od razu zamienia na sumy ludności przy progach i zachowuje tylko agregaty. „Wiersze na start” w terminologii `TravelTimeMatrix` to zawsze liczba wszystkich celów (np. 176 641 w Warszawie). Osiągalnych celów w 60 min było średnio ok. 1,6 tys. (Wrocław) do kilku tysięcy (`reachable_per_origin` w `benchmark.csv`).

## 2. Wejścia R5 (zbudowane)

**OSM** (pyosmium, jeden przebieg po PBF Polski z lokalizacjami węzłów). Region to FUA + 15 km + 3 km marginesu. Zachowane są całe drogi z `highway` oraz perony, ze wszystkimi węzłami (`BackReferenceWriter`) i tagami węzłów; relacji nie ma, bo R5 używa ich tylko do zakazów skrętu dla samochodów. Przebieg po PBF trwa 165–181 s niezależnie od liczby aglomeracji (2 w jednym przebiegu: 165 s, 5: 181 s), uzupełnianie węzłów 14–39 s na aglomerację.

| Aglomeracja | Drogi | PBF, MB |
|---|---:|---:|
| Warszawa | 780 562 | 45,5 |
| GZM | 522 883 | 33,2 |
| Kraków | 475 054 | 29,5 |
| Wrocław | 307 028 | 20,2 |
| Trójmiasto | 295 400 | 18,6 |
| Poznań | 231 085 | 15,0 |
| Łódź | 227 941 | 14,2 |

**GTFS** (`data/interim/r5/<agg>/gtfs_<wariant>/<feed>.zip`). Każdy zip zawiera jeden feed źródłowy, a jego `feed_id` to nazwa feedu, więc identyfikatory nie kolidują między feedami. Kursy są dokładnie te, które `gtfs_service.active_trips` zostawia w środę 2026-11-25 albo w sobotę 2026-11-28. Kalendarz to trzy sztuczne serwisy w `calendar_dates.txt` (WED, SAT, WED_SAT), więc kurs jedzie w R5 w danym dniu wtedy i tylko wtedy, gdy warstwa kursów zostawia go w tym dniu. Bez `shapes`, `block_id` i `parent_station`.

- Walidacja: dla wszystkich 7 aglomeracji i obu wariantów liczba kursów w zipach w obu dniach zgadza się z `active_trips` per feed (`gtfs_<wariant>_validation.csv`). Dla 7 sieci (wszystkie aglomeracje, wariant „wszystkie”, oraz Wrocław i Warszawa „oficjalne”) sprawdzono też, co R5 faktycznie wczytał (kursy aktywne w danym dniu wg R5, per feed): zgodność pełna.
- Łódź: przystanki 3876/3877 (0,0) usunięte razem z 670 wierszami `stop_times`. Trzy kursy zostały przez to z mniej niż dwoma przystankami i wypadły: 2 w środę, 1 w sobotę. Są policzone osobno.
- R5 nie zgłosił żadnego ostrzeżenia ani błędu GTFS. Niepodpięte do sieci ulic są tylko przystanki spoza FUA + 15 km: kolej z całej Polski, w Krakowie także 1 576 przystanków regionalnego `krakow_ald`, w Łodzi 124 przystanki dwóch feedów podmiejskich. Sprawdzono: wewnątrz FUA + 15 km nie ma ani jednego niepodpiętego przystanku (Kraków, Łódź, Warszawa, Wrocław).

**Budowa sieci R5** (`networks.csv`):

| Sieć | Czas budowy, s | Szczyt sterty JVM, GB | Szczyt RSS, GB | Sieć (Kryo), MB | Katalog cache, MB |
|---|---:|---:|---:|---:|---:|
| Warszawa, wszystkie | 55 | 6,2 | 9,3 | 496 | 639 |
| Warszawa, oficjalne | 48 | 6,2 | 11,2 | 444 | 585 |
| Kraków | 29 | 2,6 | 7,7 | 261 | 350 |
| GZM | 30 | 2,7 | 6,5 | 230 | 329 |
| Wrocław, wszystkie / oficjalne | 22 / 21 | 1,7 / 1,5 | 5,9 / 5,3 | 173 / 167 | 233 / 227 |
| Łódź | 20 | 3,1 | 6,6 | 181 | 225 |
| Trójmiasto | 20 | 1,5 | 5,3 | 153 | 209 |
| Poznań | 16 | 1,9 | 4,4 | 114 | 161 |

Wczytanie gotowej sieci z cache zajmuje 2–4 s. Sieci oficjalne dla pięciu pozostałych aglomeracji nie były budowane; ścieżka kodu jest ta sama.

## 3. Czas routingu

Mierzone na 20 wątkach przy niczym innym uruchomionym (R5 używa 15–19 rdzeni; jeden wątek: 0,05–0,26 s/start). Koszt pełnego przebiegu liczę z **próby jednostajnej** 200 komórek FUA, bo pełny przebieg odwiedza każdą komórkę raz. Próba ważona ludnością jest ok. 1,6–2 razy droższa na start, bo częściej trafia w gęste centra.

| Aglomeracja | Starty 250 m (komórki FUA z ludnością) | Bloki 500 m | Cele (FUA + 15 km) | Komunikacja 7–9, s/start | Pieszo, s/start | Rower, s/start |
|---|---:|---:|---:|---:|---:|---:|
| Warszawa | 88 926 | 28 845 | 176 641 | 0,0225 | 0,0026 | 0,0049 |
| Kraków | 37 817 | 11 540 | 83 079 | 0,0128 | 0,0016 | 0,0024 |
| Łódź | 26 274 | 8 394 | 63 316 | 0,0068 | 0,0010 | 0,0021 |
| GZM | 24 869 | 7 693 | 63 422 | 0,0153 | 0,0012 | 0,0031 |
| Wrocław | 20 153 | 7 082 | 42 553 | 0,0051 | 0,0007 | 0,0027 |
| Poznań | 19 201 | 6 441 | 46 627 | 0,0058 | 0,0009 | 0,0025 |
| Trójmiasto | 17 561 | 5 686 | 40 751 | 0,0044 | 0,0007 | 0,0020 |
| **Razem** | **234 801** | **75 681** | | | | |

Mnożniki względem okna 7–9 (te same 60 startów, średnio po miastach): 10–14 ok. 1,35, 20–22 ok. 1,0, sobota 10–14 ok. 1,3, max 3 przejazdy ok. 0,9. Okno 10–14 ma dwa razy więcej minut, ale nie jest dwa razy droższe.

Determinizm: ta sama próba policzona dwa razy daje w każdym z 7 miast identyczne czasy, bit w bit.

### 3.1 Koszt per element §4.6 (godziny routingu, 20 wątków, siatka startów 250 m / 500 m; cele zawsze 250 m)

| Element | Przebiegi | Warszawa | Kraków | GZM | Łódź | Wrocław | Poznań | Trójmiasto | **Razem 250 m** | **Razem 500 m** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Komunikacja 7–9 | × 2 warianty feedów | 1,11 | 0,27 | 0,21 | 0,10 | 0,06 | 0,06 | 0,04 | **1,85** | 0,59 |
| Komunikacja 10–14 | × 2 | 1,53 | 0,39 | 0,28 | 0,12 | 0,08 | 0,09 | 0,06 | **2,55** | 0,82 |
| Komunikacja 20–22 | × 2 | 1,10 | 0,29 | 0,19 | 0,10 | 0,06 | 0,07 | 0,04 | **1,84** | 0,59 |
| Sobota 10–14 | × 2 | 1,41 | 0,33 | 0,27 | 0,12 | 0,08 | 0,08 | 0,06 | **2,35** | 0,75 |
| Max 2 przesiadki (7–9) | × 2 | 0,91 | 0,22 | 0,16 | 0,09 | 0,05 | 0,07 | 0,04 | **1,53** | 0,49 |
| Sieć wspólnego biletu (7–9) | 1–2 sieci (RAPORT §8) | 0,56 | 0,27 | 0,11 | 0,10 | 0,06 | 0,06 | 0,02 | **1,17** | 0,37 |
| Pieszo | × 1 | 0,06 | 0,02 | 0,01 | 0,01 | 0,00 | 0,01 | 0,00 | **0,11** | 0,03 |
| Rower (LTS 3) | × 1 | 0,12 | 0,03 | 0,02 | 0,02 | 0,02 | 0,01 | 0,01 | **0,22** | 0,07 |
| Dwie siatki ludności | 0 (te same czasy, inne wagi) | | | | | | | | 0 | 0 |
| Miejsca pracy (6 miast, bez GZM) | 0 (te same czasy, inne wagi) + rasteryzacja zbioru Goliszek do 250 m (~10 min) | | | | | | | | ≈ 0,2 | ≈ 0,2 |
| Z centrum (komórki ≤ 1 km od centrum i od węzła) | ~50–100 startów × wszystkie przebiegi | | | | | | | | < 0,05 | < 0,05 |
| **Razem routing** | | **6,8** | **1,8** | **1,25** | **0,65** | **0,40** | **0,44** | **0,29** | **≈ 11,6** | **≈ 3,7** |

Do tego budowa sieci: 7 × 2 warianty + 11 sieci wspólnego biletu, razem ok. 25 × 20–55 s, czyli ok. 15 min. Wycinki OSM już są (4 min).

**Dysk.** Sieci z cache: ok. 2,1 GB na wariant feedów (7 miast) + ok. 2,5 GB na sieci wspólnego biletu, razem ok. 7 GB w `data/interim/r5` (teraz 2,8 GB). Wyniki: zamiast macierzy OD (Warszawa: 89 tys. × 177 tys. czasów to ok. 31 GB na jeden przebieg, nie zapisywać) proponuję zapisywać na start **skumulowaną krzywą** ludności (dwie siatki, a w 6 miastach także miejsca pracy) osiągalną w minutach 0–60. Wtedy dowolny próg da się policzyć bez ponownego routingu. Wariant A: ok. 2,2 GB w `data/interim/access` (nie do gita); do repo trafiają tylko agregaty i warstwa 250 m dla okna głównego (pojedyncze MB).

## 4. Kontrola na próbie (200 losowań ważonych ludnością spisową na miasto)

Średnia z losowań jest nieobciążonym estymatorem średniej ważonej ludnością (Hansen–Hurwitz); SE z bootstrapu. Wariant „wszystkie feedy”, siatka przeskalowana do spisu, okno 7–9. To **nie są wyniki**: próba jest mała, a kilka parametrów czeka na decyzję (sekcja 7).

### 4.1 Performance, FUA i rdzeń (miasto)

| Aglomeracja | KZ 30 (FUA) | KZ 45 (FUA) | Pieszo 30 | Rower 30 | KZ 30 rdzeń | KZ 45 rdzeń | Pieszo rdzeń | Rower rdzeń |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Warszawa | 24,0 ± 1,3 | 40,3 ± 2,1 | 63,5 | 42,2 | 33,8 | 58,8 | 62,4 | 44,2 |
| Kraków | 19,7 ± 1,2 | 33,4 ± 2,0 | 58,5 | 35,3 | 31,6 | 54,6 | 62,5 | 48,1 |
| Wrocław | 21,4 ± 1,1 | 39,1 ± 1,8 | 65,3 | 48,3 | 26,7 | 52,0 | 63,4 | 56,2 |
| Poznań | 20,2 ± 1,1 | 35,6 ± 1,9 | 64,3 | 50,7 | 27,5 | 52,6 | 61,4 | 58,8 |
| Łódź | 23,5 ± 1,1 | 40,2 ± 1,8 | 67,0 | 47,4 | 27,2 | 52,3 | 67,3 | 52,9 |
| Trójmiasto | 27,7 ± 1,3 | 46,3 ± 2,0 | 67,6 | 44,9 | 31,9 | 55,4 | 68,5 | 49,1 |
| GZM | 21,4 ± 1,3 | 30,5 ± 1,2 | 66,1 | 39,6 | 24,4 | 35,0 | 65,8 | 44,6 |

(KZ = komunikacja zbiorowa + pieszo; „rdzeń” = losowania z komórek w granicach miasta, 104–159 na miasto, czyli bez SE.)

**Porównanie z DG REGIO (tylko rząd wielkości).** DG REGIO liczy starty i cele wyłącznie w urban centre, więc bliżej mu do naszego „rdzenia”.

| Warszawa | Nasza próba, rdzeń | DG REGIO (odczyt z wykresu) |
|---|---:|---:|
| KZ 30 min | 33,8 | ok. 31 |
| KZ 45 min | 58,8 | ok. 62 |
| Pieszo 30 min | 62,4 | ok. 49 |
| Rower 30 min | 44,2 (LTS 3); ok. 54 przy LTS 4 | ok. 70,5 |

Poznań i Łódź w rdzeniu: KZ 30: 27,5 i 27,2 (DG REGIO ok. 26 i 25,5); KZ 45: 52,6 i 52,3 (DG REGIO ok. 75 i 75). Komunikacja przy 30 min zgadza się co do rzędu wielkości. Przy 45 min Poznań i Łódź wychodzą wyraźnie niżej niż w DG REGIO. Prawdopodobne przyczyny: inny mianownik (nasze cele i proximity obejmują FUA + 15 km, a nie samo urban centre) i limit dojścia 1 km wobec 5 km w OTP. Nie sprawdzono, która z nich przeważa. Pieszo wychodzi wyżej niż w DG REGIO, rower niżej. Rower zależy głównie od ograniczenia LTS: R5 przy LTS ≤ 3 nie wpuszcza roweru na ulice o dużym ruchu bez infrastruktury, a DG REGIO takiego ograniczenia nie opisuje.

### 4.2 Pary OD do porównania z wyszukiwarką (§7.4; Wrocław, środa 2026-11-25)

R5, mediana z odjazdów 7:00–9:00 (kwartyle w nawiasie) i najszybsza trasa przy wyjściu ok. 8:00. Wyszukiwarki nie odpytywano.

| Para (WGS84) | R5: mediana (p25–p75) | Trasa R5 ok. 8:00 |
|---|---|---|
| Kozanów, przy przystanku KOZANÓW (Dokerska) (16,9640; 51,1420) → Rynek (17,0320; 51,1100) | 35 min (32–37) | pieszo 1,5 → tramwaj 12 KOZANÓW (Dokerska) → PL. JANA PAWŁA II 19 min → autobus 132 → Rynek 3 min → pieszo 6,9; razem 36,5 min |
| Jagodno, przy JAGODNO (P+R) (17,0600; 51,0545) → pl. Grunwaldzki (17,0636; 51,1118) | 44 min (42–46) | pieszo 3,9 → autobus N do GALERIA DOMINIKAŃSKA 26 min → autobus D do PL. GRUNWALDZKI 6 min → pieszo 3,9; razem 42,9 min |
| Siechnice, stacja (17,1530; 51,0350) → Wrocław Główny (17,0365; 51,0983) | 47 min (37–57) | pieszo 11,6 → pociąg D7 Siechnice → Wrocław Główny 11,2 min → pieszo 5,5; razem 29,5 min |

W trzeciej parze mediana (47 min) jest znacznie dłuższa niż najlepsza trasa (29,5 min), bo pociągi kursują rzadko, a mediana z 120 minut odjazdu zawiera czekanie. To zamierzona cecha miary. Przy porównaniu z wyszukiwarką trzeba porównywać trasę o konkretnej godzinie, nie medianę. Uwaga techniczna: `DetailedItineraries` w r5py nie egzekwuje limitu dojścia 12 min tak jak routing regionalny (we wcześniejszej wersji pary z punktu 1,3 km od przystanku pokazał dojście 16 min, a macierz czasów dała brak połączenia), dlatego punkty startu leżą przy przystankach.

### 4.3 Wrażliwości (te same 60 startów, średnia różnica performance w pkt)

| Zmiana | Wpływ |
|---|---|
| Rower LTS 4 zamiast LTS 3 | **+9,6 do +17,3** (największa) |
| Średnia ze stosunków (brief) vs stosunek średnich (FUA, KZ 30) | stosunek średnich od −0,5 do +9,8 pkt względem średniej ze stosunków (Warszawa 32,9 wobec 24,0); przy KZ 45 od +2 do +15 pkt |
| Dojście do 5 km (jak OTP w DG REGIO) zamiast 1 km | +1,8 do +2,8 (KZ 30), +1,9 do +4,2 (KZ 45); koszt ×1,2–1,8 |
| Okno 10–14 wobec 7–9 | −0,7 do −1,9 (KZ 30) |
| Okno 20–22 | −0,2 do −5,2 |
| Sobota 10–14 | −1,0 do −4,0 |
| Max 2 przesiadki | od −0,02 do −0,07 (KZ 45); przy 60 min trzeci przejazd prawie nigdy nie pomaga |
| Limit podróży 45 zamiast 60 min | −1,7 do −2,7 przy KZ 45 i tylko ok. 5 % oszczędności. Przyczyny nie wyjaśniono (spodziewany brak zmiany); zostaje 60 min |
| Surowy GHSL zamiast siatki spisowej | −2,7 do +1,9 |
| Feedy oficjalne zamiast wszystkich | Warszawa −2,0 (KZ 30) / −2,9 (KZ 45); Wrocław −0,8 / −1,3 |

### 4.4 Stabilność przy próbkowaniu i przy starcie z 500 m

- **Próbkowanie startów** (losowanie ważone ludnością, SE średniej miejskiej z bootstrapu, przeskalowane 1/√n): przy n = 200 SE wynosi 1,1–1,3 pkt (KZ 30) i 1,2–2,2 pkt (KZ 45). Przy n = 2 000: 0,34–0,42 i 0,38–0,68. Przy n = 5 000: 0,21–0,26 i 0,24–0,43. Pieszo i rower podobnie (0,22–0,32 przy n = 5 000).
- **Start z centroidu bloku 500 m** (ważonego ludnością; cele dalej 250 m) zamiast z czterech komórek 250 m, 30 losowych bloków na miasto. Różnica w bloku: mediana 0,8–1,9 pkt, 90. percentyl 3,0–5,5 pkt (KZ 30) i 2,2–6,8 pkt (KZ 45). Średnia ważona ludnością (obciążenie poziomu miejskiego): od −0,85 do +1,1 pkt (KZ 30) i od −1,1 do +1,0 pkt (KZ 45). Przy 30 blokach ta średnia sama jest niepewna (jej błędu nie szacowano), więc wniosek to tylko: obciążenie poziomu rzędu 1 pkt, znak różny w różnych miastach.
- Wniosek: starty 500 m zmieniają poziom miasta o ≤ ~1 pkt, co jest porównywalne z różnicą między siatkami ludności. Różnice między oknami (−1 do −5 pkt) też mają ten rząd wielkości, więc **okna trzeba porównywać na tej samej siatce startów**. Wtedy obciążenie w dużej mierze się znosi.

## 5. Trzy warianty zakresu

| | Zakres | Routing | Dysk (interim) | Czego brak / co traci |
|---|---|---:|---:|---|
| **A** | Wszystko z §4.6: 4 okna × 2 warianty feedów, max 2 przesiadki × 2, sieci wspólnego biletu, pieszo, rower, obie siatki, miejsca pracy, z centrum; starty 250 m | **≈ 11,6 h** + 15 min sieci + 10 min miejsca pracy ≈ **12 h** | ≈ 7 GB sieci + 2,2 GB krzywych | nic; mapy dla każdego okna |
| **B (rekomendowany)** | Okno 7–9 na 250 m dla obu wariantów feedów + pieszo + rower (250 m); okna 10–14, 20–22 i sobota **na starcie 500 m** (cele 250 m), oba warianty, **plus okno 7–9 też na 500 m** jako baza do porównań okien; max 2 przesiadki i sieć wspólnego biletu na 500 m; miejsca pracy, siatki i z centrum jak w A | 1,85 + 0,33 + 0,59 (7–9 na 500 m) + 2,16 (okna) + 0,49 + 0,37 ≈ **5,8 h** + 25 min | ≈ 7 GB + 1,0 GB | poziomy okien pobocznych i wariantów ±~1 pkt na poziomie miasta, w bloku do 3–7 pkt (p90); mapy okien pobocznych w 500 m. Wynik główny (7–9, oba warianty, pieszo, rower) bez strat |
| **C (pierwszy wynik)** | Okno 7–9, wszystkie feedy, KZ + pieszo + rower, **2 000 startów** na miasto losowanych z wagą ludności | ok. **5 min** (próba ważona jest droższa na start: Σ ok. 0,11 s × 2 000 dla KZ) | < 0,1 GB | SE 0,3–0,7 pkt na poziomie miasta, brak mapy. Wariant „C+”: to samo na pełnej siatce 250 m (mapa okna głównego) to ok. **1,3 h** (0,93 h KZ + 0,33 h pieszo i rower) |

**Rekomendacja: najpierw C+ (ok. 1,3 h, jeden wieczór), potem B.**

- C+ daje mapę i wynik główny na pełnej siatce, z którymi można rozstrzygnąć otwarte decyzje (LTS roweru, sposób agregacji, limit dojścia) przed drogimi przebiegami.
- B kosztuje połowę A, a różnica w precyzji dotyczy tylko miar pobocznych. Jeśli właścicielowi zależy na mapach wszystkich okien w 250 m, A to tylko ok. 6 h więcej, czyli jedna noc.
- Uwaga do kosztorysu: koszt routingu jest mały w porównaniu z obawą „wiele godzin”. Warszawa to 59 % całości (A: 6,8 h z 11,6), a z niej okno 10–14 i sobota to 2,9 h. Na tym tnie wariant B.

## 6. Wznawialność i co zostawić uruchomione

**Proponowany krok** `python -m pipeline.access --scope C+|B|A [--aggs …]` (jeszcze nienapisany), reguła Snakemake `access` per aglomeracja:

1. Jednostka pracy: (aglomeracja, sieć, scenariusz, paczka 1 000 startów posortowanych po `cell_id`). Paczka w Warszawie trwa ok. 23 s (7–9) do 31 s (10–14), w innych miastach kilka sekund.
2. Każda paczka zapisuje parquet z krzywymi do pliku tymczasowego i robi atomowe `os.replace` do `data/interim/access/<agg>/<scenariusz>/chunk_<nnnnn>.parquet`. Obok jest `manifest.json` z podpisem (podpis wejść R5 + parametry + wersje r5py/R5). Po restarcie paczki z poprawnym podpisem są pomijane, niekompletnych plików nie ma.
3. Kolejność: miasto po mieście, w mieście najpierw okno główne, potem warianty. Agregacja do `results/` dopiero po skompletowaniu paczek miasta. Sieć z cache wczytuje się w 2–4 s, więc wznowienie kosztuje start JVM, wczytanie sieci i przerwaną paczkę: **poniżej minuty**.
4. Jeden proces Javy na raz (`-Xmx` 16 GB wystarczy: szczyt sterty w routingu do ok. 10 GB w Krakowie, w budowie 6,2 GB w Warszawie), 20 wątków. Komputer pozostaje używalny do lekkiej pracy.

**Właściciel musi:** zostawić komputer podłączony do zasilania, z wyłączonym usypianiem i hibernacją na czas przebiegu (ustawienia zasilania Windows, zmienia je właściciel), nie uruchamiać równolegle innych ciężkich obliczeń i uruchomić jedno polecenie w terminalu. Postęp idzie do logu (paczki gotowe / wszystkie, szacowany czas do końca). Przerwanie (Ctrl+C, zanik prądu) jest bezpieczne; to samo polecenie wznawia pracę.

## 7. Do decyzji i nie zweryfikowano

**Decyzje przed liczeniem:**

1. Zakres (A / B / C+).
2. Rower: LTS 3 (domyślne r5py, ostrożne) czy LTS 4 (bliżej DG REGIO; +10–17 pkt).
3. Agregacja performance: średnia ze stosunków ważona ludnością (brief) czy stosunek średnich (różnica do 15 pkt). Proponuję raportować oba, a główny wybrać przed publikacją.
4. Limit dojścia 1 km (brief) zostaje? Obcina też podróże czysto piesze w miarze KZ (+2–4 pkt przy 5 km). Prędkość pieszo 5 km/h przyjęto z promieni briefu.

**Nie zweryfikowano:**

- **Integracja taryfowa**: tabela z RAPORT §8 nie jest potwierdzona przez właściciela. Liczba sieci w kosztorysie (11) wynika z propozycji (wariant ścisły i szeroki w Krakowie, Wrocławiu, Poznaniu i Łodzi). Mapowanie agencji i ograniczenie kolei do stacji w obszarze biletu nie jest zaimplementowane; R5 nie zna stref, więc każda sieć to osobny zestaw zipów i osobna budowa.
- **Miejsca pracy**: tylko miasta w granicach administracyjnych, bez GZM, w Trójmieście tylko Gdańsk (RAPORT §7). Liczba osiągalnych miejsc pracy poza zasięgiem zbioru jest zaniżona, a starty spoza zasięgu dają „brak danych”. Rasteryzacja do 250 m nie została zrobiona.
- **Trójmiasto i GZM**: miara „z centrum” z jednego punktu wymaga zastrzeżenia (§11). Proponuję liczyć ją dla każdego centrum z `extra_centres`, co kosztuje pomijalnie mało. Obie aglomeracje to sumy kilku FUA.
- **Mediana liczby przesiadek** (brief): nie zmierzono. Routing regionalny R5 zwraca tylko czasy. Potrzebny zapis ścieżek R5 albo próba `DetailedItineraries`; koszt nieznany.
- Maska pokrycia GTFS (§6): wynik KZ poza maską to „brak danych”. W planie nie wycina to kosztu, bo routing i tak idzie z każdej komórki.
- Czasy zmierzono na pustej maszynie; przy innej pracy w tle będą dłuższe. Mnożniki okien są z 60 startów na miasto.
- Pary OD nie porównane z Jakdojade ani Google (zadanie dla człowieka). Wartości DG REGIO są odczytane z wykresów (±1 pkt).
- Nie budowano sieci „oficjalne” dla Krakowa, Poznania, Łodzi, Trójmiasta i GZM (zipy są zbudowane i zwalidowane). Ani sieci, ani zipów nie zbudowano dla sieci wspólnego biletu.
- Daty: ludność NSP 2021 / GHSL 2020; rozkłady 2026-11-25 i 2026-11-28 (pobrane 2026-11-23); OSM 2026-11-22.
