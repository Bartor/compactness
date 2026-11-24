# Benchmark DG REGIO: skąd bierze się różnica (Warszawa, Poznań, Łódź)

Plik generuje `python -m pipeline.access_dgregio report` (krok poboczny; dane produkcyjne fazy 3 tylko czytane). Źródła: Poelman, Dijkstra, Ackermans (2020), DG REGIO WP 01/2020, PDF i **aneks danych** (`wp_low_carbon_urban_accessibility_data_annex.xlsx`, tabele 1–2), oba z ec.europa.eu, zapisane w `data/raw/dgregio_wp2020/`; urban centres 2011: Eurostat GISCO `HDENS_CLST_2011` (`data/raw/eurostat_hdens_2011/`). Nasze dane: środa 2026-11-25, feedy wariantu „wszystkie”, R5 v7.5.1, ludność NSP 2021 w siatce 250 m.

## 1. Odpowiedź w skrócie

**Braków w naszych feedach, które tłumaczyłyby różnicę, nie znaleziono. Główną przyczyną luki 45-minutowej jest inna domena.** DG REGIO liczy starty, cele i mianownik wyłącznie w urban centre 2011 (Poznań i Łódź po 117 km², Warszawa 309 km²), a mianownik jest przycięty do jego granic (s. 42). W tak małym obszarze promień 11,25 km obejmuje prawie całą ludność UC (Poznań i Łódź: 98 % w DG REGIO), więc KZ 45 to w praktyce „jaki odsetek całego UC osiągam w 45 min”. Nasz mianownik produkcyjny (FUA + 15 km) dla startów w UC Poznania to 127 % ludności UC. Sama zmiana domeny (kroki 1–2) podnosi nasz KZ 45 o 14,5 pkt w Poznaniu, 11,4 w Łodzi i 6,5 w Warszawie. Pozostałe różnice metody razem (agregacja, dojście 5 km, średnia z 9 odjazdów; kroki 3–5) dają +1,2 / +1,1 / +0,7 pkt (Poznań / Łódź / Warszawa).

Po odtworzeniu domeny i metody luka KZ 45 (DG − my) maleje z +20,1 do +4,5 pkt w Poznaniu i z +23,5 do +11,0 pkt w Łodzi; w Warszawie jesteśmy 4,3 pkt powyżej DG REGIO. Przy KZ 30 po tych samych krokach jesteśmy powyżej DG REGIO we wszystkich trzech miastach (o 9,8 / 6,3 / 6,2 pkt), a pieszo o 9,1–17,5 pkt. Brak kursów obniżałby nasz wynik przy każdym progu; tymczasem niżej od DG REGIO jesteśmy tylko przy 45 min w Poznaniu i Łodzi (sam ten układ nie wyklucza braków zamaskowanych przez przeciwny efekt, dlatego w §7 są testy bezpośrednie danych).

**Reszty nie da się przypisać jednej przyczynie.** Zmierzone fakty: (1) krótkie podróże są w modelu DG REGIO wolniejsze niż u nas: ich wynik pieszy odpowiada naszemu progowi 23–26 min zamiast 30 (§6); gdyby u nas odcinki piesze były wolniejsze (4 km/h), KZ 30 spadłby o 7,5–9,6 pkt, czyli mniej więcej o resztę KZ 30, ale KZ 45 spadłby też, o 8,9–11,4 pkt (§5), co powiększyłoby lukę 45 min w Poznaniu i Łodzi. (2) Według aneksu DG REGIO ich rozkłady 2018 miały w urban centre więcej wozokilometrów na mieszkańca niż nasze feedy 2026: Łódź 1,44×, Poznań 1,23×, Warszawa 1,06× (autobusy: 1,67× w Poznaniu, 1,70× w Łodzi), przy prawie tych samych prędkościach w linii prostej. Kolejność tych ilorazów (Łódź > Poznań > Warszawa) jest taka sama jak kolejność reszt KZ 45 (+11,0 > +4,5 > −4,3); to trzy punkty, więc zgodność, nie dowód. (3) Nasze feedy 2026 zgadzają się z niezależnymi źródłami (§7): wozkm MPK Poznań z feedu pasują do rocznej pracy MPK z raportu miasta, lista linii dziennych Łodzi zgadza się z listą MPK Łódź, a ok. 95 % przystanków OSM w UC ma obsługiwany przystanek GTFS w 100 m. Czy w 2018 r. w tych UC jeździło naprawdę o 20–40 % więcej kursów, czy feed DG REGIO był zawyżony (np. nakładające się wersje rozkładu w dniu „z największą liczbą odjazdów”), **nie da się rozstrzygnąć bez feedów użytych przez DG REGIO**; praca ich nie wymienia.

Werdykt: nasze dane 2026 nie są niekompletne w stopniu, który miałby znaczenie dla tego porównania. Luka 45 min to głównie domena; reszta (Poznań +4,5, Łódź +11,0 pkt) jest zgodna z większą podażą w danych 2018, której pochodzenia (realna zmiana czy zawyżony feed) nie sprawdzono. Wniosek praktyczny: porównywać z DG REGIO tylko wynik w domenie UC i ze stosunkiem średnich (krok 3–5), nie wynik produkcyjny.

| Miasto | Miara | DG REGIO (aneks) | Nasz opublikowany (rdzeń) | Nasz w domenie i metodzie DG REGIO (ostatni krok) | Reszta (DG − my) |
|---|---|---|---|---|---|
| Warszawa | PT 30 | 30,9 | 33,9 | 37,1 | −6,2 |
| Warszawa | PT 45 | 61,7 | 58,8 | 66,0 | −4,3 |
| Warszawa | pieszo 30 | 49,0 | 66,4 | 61,1 | −12,1 |
| Warszawa | rower 30 LTS 4 | 70,4 | 52,4 | 53,8 | +16,6 |
| Poznań | PT 30 | 26,3 | 30,0 | 36,1 | −9,8 |
| Poznań | PT 45 | 74,8 | 54,6 | 70,3 | +4,5 |
| Poznań | pieszo 30 | 43,0 | 64,9 | 60,4 | −17,5 |
| Poznań | rower 30 LTS 4 | 81,4 | 69,6 | 75,9 | +5,6 |
| Łódź | PT 30 | 25,4 | 26,9 | 31,7 | −6,3 |
| Łódź | PT 45 | 74,8 | 51,3 | 63,8 | +11,0 |
| Łódź | pieszo 30 | 54,3 | 69,1 | 63,4 | −9,1 |
| Łódź | rower 30 LTS 4 | 81,1 | 64,8 | 69,0 | +12,1 |

Wartości DG REGIO pochodzą teraz z aneksu (dokładne liczby), nie z odczytu wykresów. Odczyt z wykresów w `access.md` §7 był poprawny co do ±0,5 pkt (np. Poznań KZ 45: odczyt 75,0, aneks 74,8).

## 2. Metoda DG REGIO ustalona ze źródła

Strony wg numeracji drukowanej pracy.

| Element | DG REGIO | Gdzie |
|---|---|---|
| Jednostka | urban centre (klaster komórek 1 km² o gęstości ≥ 1500 os./km² i ≥ 50 tys. mieszk.), wydzielony na siatce ludności **2011**; „city” = urban centre | s. 5 przyp. 3, s. 6 i przyp. 9 |
| Starty i cele | zaludnione poligony Urban Atlas 2012 (centroidy, bez wód i dróg), ludność 2011 wg Batista e Silva i Poelman (2016); **tylko punkty wewnątrz urban centre**, zarówno starty, jak i cele | s. 16, s. 37 przyp. 35–37 |
| Mianownik (proximity) | ludność w promieniu 2,5 / 7,5 / 11,25 km, **„constrained by the limits of the urban centre”** | s. 16 przyp. 17, s. 42 |
| Router i parametry | OpenTripPlanner 1.2.0 (zmodyfikowany, by zwracał początkowe oczekiwanie), OSM z Geofabrik; `maxWalkDistance` 5000 m, `maxTimeSec` 3600, `clampInitialWait` −1, tryby TRANSIT+WALK; prędkość pieszego nie zmieniona (domyślna OTP 1.x: 1,33 m/s ≈ 4,8 km/h, z dokumentacji OTP, nie z pracy) | s. 37 przyp. 39–42 |
| Odjazdy | 9 zapytań co 15 min w **dwugodzinnym szczycie porannym** (godzin nie podano; tu przyjęto 7:00–9:00); czas = od żądanej godziny wyjazdu do przyjazdu (z oczekiwaniem); dla pary **średnia z 9**, para zaliczona, gdy średnia ≤ 30 / 45 min | s. 37–38 |
| Dzień | dzień roboczy o największej liczbie odjazdów w okresie ważności feedu; przy łączeniu feedów wymuszana wspólna data | s. 35, s. 37 |
| Rozkłady | „scheduled timetables of all public transport in the city”; feedy GTFS przewoźników (ponad 125 źródeł), kolej z UIC MERITS, gdy feed miejski jej nie ma; rok 2018 (podpisy map 3–6); **które feedy i z jakiej daty dla Warszawy, Poznania i Łodzi — nie podano** (karty miast podają tylko „public transport operators, UIC”) | s. 34, 37, mapy 3–5; karty miast |
| Agregacja do miasta | średnia ważona ludnością dostępności i osobno proximity; aneks potwierdza liczbowo, że wynik miasta = średnia dostępność / średnie proximity × 100 (**stosunek średnich**), np. Poznań 45 min: 388 121 / 519 035 = 74,78 | s. 40, s. 43; aneks t2 |
| Pieszo | ta sama domena, sieć OSM, 30 min, mianownik 2,5 km | s. 40 |
| Rower | dla większości miast (w tym polskich) **sieć TomTom**: 15 km/h na wszystkich drogach poza autostradami, 4 km/h w strefach pieszych, 10 km/h na ciągach pieszo-rowerowych, **kontraruch dopuszczony wszędzie**, spadki −10 / −20 % pod górę; OTP/OSM tylko dla Amsterdamu, Kopenhagi i Gandawy | s. 40, przyp. 43–46 |

Wniosek dla porównania: w `access.md` §7 domenę DG REGIO przybliżano **granicami miasta**. Urban centre jest znacznie mniejszy: Poznań i Łódź po 117 km² (miasta: 262 i 293 km²), Warszawa 309 km² (miasto 517 km²). Do tego mianownik DG REGIO jest przycięty do urban centre, a w naszym wariancie „cele tylko w rdzeniu” przycięty był do miasta.

## 3. Domena: urban centre 2011

Klastry z rastra `HDENS_CLST_2011` (wartość komórki = ludność klastra) identyfikowane po ludności z aneksu; liczba komórek 1 km² zgadza się z powierzchnią w aneksie co do komórki, więc to jest domena użyta przez DG REGIO. Komórka 250 m należy do UC, jeśli jej środek leży w komórce 1 km klastra.

| Miasto | Kod | Pow. km² (aneks / raster) | Ludność 2011 (aneks) | Ludność NSP 2021 w UC (nasza siatka) | Komórek 250 m (starty = cele) | Ludność miasta poza UC | Ludność UC poza miastem |
|---|---|---|---|---|---|---|---|
| Warszawa | GEOSTAT11_171 | 309 / 309 | 1 722 513 | 1 836 368 | 4796 | 10,8 % | 173 075 |
| Poznań | GEOSTAT11_178 | 117 / 117 | 532 166 | 512 717 | 1824 | 12,6 % | 36 670 |
| Łódź | GEOSTAT11_229 | 117 / 117 | 682 389 | 606 329 | 1858 | 9,0 % | 5 |

## 4. Dekompozycja: od naszego wyniku do wartości DG REGIO

Każdy krok zmienia jedną rzecz względem poprzedniego; kolumna „zmiana” to efekt tego kroku (pkt). Kroki 0–1 z produkcyjnych paczek (bez nowego routingu). Kroki 2–5 z nowego routingu (`pipeline.access_dgregio route`): starty i cele = zaludnione komórki 250 m w UC, sieci produkcyjne (kopia pliku sieci), reguła min(KZ, sam spacer) jak w produkcji. Krok 5 (9 odjazdów) liczony na próbie 800 startów (wybór systematyczny po `cell_id`) i dodany jako różnica na tej samej próbie. „Reszta” to to, czego nie wyjaśniają zmierzone kroki: rok rozkładów (2018 / 2026), ludność 2011 na poligonach Urban Atlas, router OTP i jego sieć, prędkość i dobór trasy.

Zbiór startów kroków 2–4: Poznań bike_lts3: pełny UC; Poznań bike_lts4: pełny UC; Poznań pt_base: pełny UC; Poznań pt_walk5km: pełny UC; Warszawa bike_lts3: próba 800 startów; Warszawa bike_lts4: próba 800 startów; Warszawa pt_base: próba 800 startów; Warszawa pt_walk5km: próba 800 startów; Łódź bike_lts3: pełny UC; Łódź bike_lts4: pełny UC; Łódź pt_base: pełny UC; Łódź pt_walk5km: pełny UC.

### Warszawa

**PT 30**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany: starty w mieście (rdzeń), cele i mianownik FUA + 15 km, średnia stosunków | 33,9 |  |
| 1. Starty tylko w urban centre 2011 (cele i mianownik bez zmian) | 35,0 | +1,1 |
| 2. Cele i mianownik też tylko w urban centre (nowy routing, parametry produkcyjne) | 37,8 | +2,8 |
| 3. Agregacja jak DG REGIO: stosunek średnich ważonych | 38,2 | +0,5 |
| 4. Dojście i odejście do 5 km (OTP maxWalkDistance 5000 m) zamiast 1 km | 38,7 | +0,4 |
| 5. Średnia z 9 odjazdów co 15 min 7:00–9:00 zamiast mediany z odjazdów co minutę (różnica z próby 800 startów) | 37,1 | −1,6 |
| DG REGIO (aneks, tabela 2) | 30,9 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | −6,2 |

**PT 45**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany: starty w mieście (rdzeń), cele i mianownik FUA + 15 km, średnia stosunków | 58,8 |  |
| 1. Starty tylko w urban centre 2011 (cele i mianownik bez zmian) | 60,3 | +1,5 |
| 2. Cele i mianownik też tylko w urban centre (nowy routing, parametry produkcyjne) | 65,3 | +5,0 |
| 3. Agregacja jak DG REGIO: stosunek średnich ważonych | 66,9 | +1,6 |
| 4. Dojście i odejście do 5 km (OTP maxWalkDistance 5000 m) zamiast 1 km | 67,7 | +0,8 |
| 5. Średnia z 9 odjazdów co 15 min 7:00–9:00 zamiast mediany z odjazdów co minutę (różnica z próby 800 startów) | 66,0 | −1,7 |
| DG REGIO (aneks, tabela 2) | 61,7 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | −4,3 |

**pieszo 30**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany (rdzeń, cele FUA + 15 km, średnia stosunków) | 66,4 |  |
| 1. Starty tylko w urban centre | 68,1 | +1,6 |
| 2. Cele i mianownik tylko w urban centre (czasy z produkcyjnej pamięci spacerów) | 68,9 | +0,9 |
| 3. Stosunek średnich | 68,6 | −0,3 |
| 4. Prędkość 4,8 km/h (OTP domyślnie 1,33 m/s): próg 28 min przy 5 km/h | 61,1 | −7,5 |
| DG REGIO (aneks, tabela 2) | 49,0 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | −12,1 |

**rower 30 LTS 3**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany, LTS ≤ 3 | 45,2 |  |
| 1. Starty tylko w urban centre | 46,5 | +1,4 |
| 2. Cele i mianownik tylko w urban centre (nowy routing) | 48,8 | +2,3 |
| 3. Stosunek średnich | 47,2 | −1,7 |
| DG REGIO (aneks, tabela 2) | 70,4 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +23,3 |

**rower 30 LTS 4**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany, LTS ≤ 4 | 52,4 |  |
| 1. Starty tylko w urban centre | 53,3 | +0,9 |
| 2. Cele i mianownik tylko w urban centre (nowy routing) | 55,2 | +1,9 |
| 3. Stosunek średnich | 53,8 | −1,3 |
| DG REGIO (aneks, tabela 2) | 70,4 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +16,6 |

### Poznań

**PT 30**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany: starty w mieście (rdzeń), cele i mianownik FUA + 15 km, średnia stosunków | 30,0 |  |
| 1. Starty tylko w urban centre 2011 (cele i mianownik bez zmian) | 31,5 | +1,5 |
| 2. Cele i mianownik też tylko w urban centre (nowy routing, parametry produkcyjne) | 35,0 | +3,5 |
| 3. Agregacja jak DG REGIO: stosunek średnich ważonych | 36,6 | +1,6 |
| 4. Dojście i odejście do 5 km (OTP maxWalkDistance 5000 m) zamiast 1 km | 37,4 | +0,8 |
| 5. Średnia z 9 odjazdów co 15 min 7:00–9:00 zamiast mediany z odjazdów co minutę (różnica z próby 800 startów) | 36,1 | −1,3 |
| DG REGIO (aneks, tabela 2) | 26,3 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | −9,8 |

**PT 45**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany: starty w mieście (rdzeń), cele i mianownik FUA + 15 km, średnia stosunków | 54,6 |  |
| 1. Starty tylko w urban centre 2011 (cele i mianownik bez zmian) | 56,6 | +1,9 |
| 2. Cele i mianownik też tylko w urban centre (nowy routing, parametry produkcyjne) | 69,1 | +12,5 |
| 3. Agregacja jak DG REGIO: stosunek średnich ważonych | 69,9 | +0,8 |
| 4. Dojście i odejście do 5 km (OTP maxWalkDistance 5000 m) zamiast 1 km | 71,4 | +1,5 |
| 5. Średnia z 9 odjazdów co 15 min 7:00–9:00 zamiast mediany z odjazdów co minutę (różnica z próby 800 startów) | 70,3 | −1,1 |
| DG REGIO (aneks, tabela 2) | 74,8 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +4,5 |

**pieszo 30**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany (rdzeń, cele FUA + 15 km, średnia stosunków) | 64,9 |  |
| 1. Starty tylko w urban centre | 67,3 | +2,4 |
| 2. Cele i mianownik tylko w urban centre (czasy z produkcyjnej pamięci spacerów) | 68,2 | +0,9 |
| 3. Stosunek średnich | 68,2 | −0,0 |
| 4. Prędkość 4,8 km/h (OTP domyślnie 1,33 m/s): próg 28 min przy 5 km/h | 60,4 | −7,7 |
| DG REGIO (aneks, tabela 2) | 43,0 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | −17,5 |

**rower 30 LTS 3**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany, LTS ≤ 3 | 61,8 |  |
| 1. Starty tylko w urban centre | 64,4 | +2,7 |
| 2. Cele i mianownik tylko w urban centre (nowy routing) | 68,8 | +4,4 |
| 3. Stosunek średnich | 70,3 | +1,5 |
| DG REGIO (aneks, tabela 2) | 81,4 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +11,1 |

**rower 30 LTS 4**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany, LTS ≤ 4 | 69,6 |  |
| 1. Starty tylko w urban centre | 71,2 | +1,6 |
| 2. Cele i mianownik tylko w urban centre (nowy routing) | 74,5 | +3,3 |
| 3. Stosunek średnich | 75,9 | +1,4 |
| DG REGIO (aneks, tabela 2) | 81,4 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +5,6 |

### Łódź

**PT 30**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany: starty w mieście (rdzeń), cele i mianownik FUA + 15 km, średnia stosunków | 26,9 |  |
| 1. Starty tylko w urban centre 2011 (cele i mianownik bez zmian) | 28,6 | +1,7 |
| 2. Cele i mianownik też tylko w urban centre (nowy routing, parametry produkcyjne) | 30,5 | +1,9 |
| 3. Agregacja jak DG REGIO: stosunek średnich ważonych | 31,4 | +0,8 |
| 4. Dojście i odejście do 5 km (OTP maxWalkDistance 5000 m) zamiast 1 km | 32,2 | +0,9 |
| 5. Średnia z 9 odjazdów co 15 min 7:00–9:00 zamiast mediany z odjazdów co minutę (różnica z próby 800 startów) | 31,7 | −0,5 |
| DG REGIO (aneks, tabela 2) | 25,4 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | −6,3 |

**PT 45**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany: starty w mieście (rdzeń), cele i mianownik FUA + 15 km, średnia stosunków | 51,3 |  |
| 1. Starty tylko w urban centre 2011 (cele i mianownik bez zmian) | 54,3 | +3,0 |
| 2. Cele i mianownik też tylko w urban centre (nowy routing, parametry produkcyjne) | 62,7 | +8,4 |
| 3. Agregacja jak DG REGIO: stosunek średnich ważonych | 63,2 | +0,5 |
| 4. Dojście i odejście do 5 km (OTP maxWalkDistance 5000 m) zamiast 1 km | 64,9 | +1,7 |
| 5. Średnia z 9 odjazdów co 15 min 7:00–9:00 zamiast mediany z odjazdów co minutę (różnica z próby 800 startów) | 63,8 | −1,1 |
| DG REGIO (aneks, tabela 2) | 74,8 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +11,0 |

**pieszo 30**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany (rdzeń, cele FUA + 15 km, średnia stosunków) | 69,1 |  |
| 1. Starty tylko w urban centre | 70,6 | +1,5 |
| 2. Cele i mianownik tylko w urban centre (czasy z produkcyjnej pamięci spacerów) | 71,2 | +0,7 |
| 3. Stosunek średnich | 70,9 | −0,4 |
| 4. Prędkość 4,8 km/h (OTP domyślnie 1,33 m/s): próg 28 min przy 5 km/h | 63,4 | −7,4 |
| DG REGIO (aneks, tabela 2) | 54,3 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | −9,1 |

**rower 30 LTS 3**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany, LTS ≤ 3 | 53,7 |  |
| 1. Starty tylko w urban centre | 55,9 | +2,2 |
| 2. Cele i mianownik tylko w urban centre (nowy routing) | 58,6 | +2,6 |
| 3. Stosunek średnich | 60,0 | +1,5 |
| DG REGIO (aneks, tabela 2) | 81,1 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +21,1 |

**rower 30 LTS 4**

| Krok | Wartość | Zmiana |
|---|---|---|
| 0. Nasz wynik opublikowany, LTS ≤ 4 | 64,8 |  |
| 1. Starty tylko w urban centre | 66,2 | +1,4 |
| 2. Cele i mianownik tylko w urban centre (nowy routing) | 68,0 | +1,7 |
| 3. Stosunek średnich | 69,0 | +1,0 |
| DG REGIO (aneks, tabela 2) | 81,1 |  |
| Reszta niewyjaśniona (DG REGIO − ostatni krok) | – | +12,1 |

## 5. Wrażliwość (nie wchodzi do łańcucha)

| Miasto | Miara | Zmiana | Efekt, pkt |
|---|---|---|---|
| Warszawa | PT 30 | krok 1 na pełnym UC zamiast próby (błąd próby) | −0,3 |
| Warszawa | PT 30 | 9 odjazdów: para liczona przy brakach (średnia tylko z odjazdów z wynikiem ≤ 60 min) zamiast wykluczenia | +0,0 |
| Warszawa | PT 30 | 9 odjazdów przy dojściu 1 km (zamiast 5 km), ta sama próba | −1,6 |
| Warszawa | PT 30 | co by było, gdyby: odcinki piesze 4 km/h zamiast 5 km/h (krok 4, te same starty) | −9,6 |
| Warszawa | PT 30 | siatka ludności GHSL 2020 surowa zamiast NSP 2021 (krok 4) | +0,7 |
| Warszawa | PT 45 | krok 1 na pełnym UC zamiast próby (błąd próby) | −0,4 |
| Warszawa | PT 45 | 9 odjazdów: para liczona przy brakach (średnia tylko z odjazdów z wynikiem ≤ 60 min) zamiast wykluczenia | +0,0 |
| Warszawa | PT 45 | 9 odjazdów przy dojściu 1 km (zamiast 5 km), ta sama próba | −1,8 |
| Warszawa | PT 45 | co by było, gdyby: odcinki piesze 4 km/h zamiast 5 km/h (krok 4, te same starty) | −11,4 |
| Warszawa | PT 45 | siatka ludności GHSL 2020 surowa zamiast NSP 2021 (krok 4) | +2,0 |
| Poznań | PT 30 | krok 4: próba 800 startów zamiast pełnego UC (błąd próby) | +0,1 |
| Poznań | PT 45 | krok 4: próba 800 startów zamiast pełnego UC (błąd próby) | +0,1 |
| Poznań | PT 30 | 9 odjazdów: para liczona przy brakach (średnia tylko z odjazdów z wynikiem ≤ 60 min) zamiast wykluczenia | +0,0 |
| Poznań | PT 30 | 9 odjazdów przy dojściu 1 km (zamiast 5 km), ta sama próba | −1,3 |
| Poznań | PT 30 | co by było, gdyby: odcinki piesze 4 km/h zamiast 5 km/h (krok 4, te same starty) | −8,8 |
| Poznań | PT 30 | siatka ludności GHSL 2020 surowa zamiast NSP 2021 (krok 4) | +0,6 |
| Poznań | PT 45 | 9 odjazdów: para liczona przy brakach (średnia tylko z odjazdów z wynikiem ≤ 60 min) zamiast wykluczenia | +0,0 |
| Poznań | PT 45 | 9 odjazdów przy dojściu 1 km (zamiast 5 km), ta sama próba | −1,2 |
| Poznań | PT 45 | co by było, gdyby: odcinki piesze 4 km/h zamiast 5 km/h (krok 4, te same starty) | −8,9 |
| Poznań | PT 45 | siatka ludności GHSL 2020 surowa zamiast NSP 2021 (krok 4) | −0,9 |
| Łódź | PT 30 | krok 4: próba 800 startów zamiast pełnego UC (błąd próby) | −0,2 |
| Łódź | PT 45 | krok 4: próba 800 startów zamiast pełnego UC (błąd próby) | −0,2 |
| Łódź | PT 30 | 9 odjazdów: para liczona przy brakach (średnia tylko z odjazdów z wynikiem ≤ 60 min) zamiast wykluczenia | +0,0 |
| Łódź | PT 30 | 9 odjazdów przy dojściu 1 km (zamiast 5 km), ta sama próba | −0,4 |
| Łódź | PT 30 | co by było, gdyby: odcinki piesze 4 km/h zamiast 5 km/h (krok 4, te same starty) | −7,5 |
| Łódź | PT 30 | siatka ludności GHSL 2020 surowa zamiast NSP 2021 (krok 4) | +0,0 |
| Łódź | PT 45 | 9 odjazdów: para liczona przy brakach (średnia tylko z odjazdów z wynikiem ≤ 60 min) zamiast wykluczenia | +0,1 |
| Łódź | PT 45 | 9 odjazdów przy dojściu 1 km (zamiast 5 km), ta sama próba | −1,0 |
| Łódź | PT 45 | co by było, gdyby: odcinki piesze 4 km/h zamiast 5 km/h (krok 4, te same starty) | −9,5 |
| Łódź | PT 45 | siatka ludności GHSL 2020 surowa zamiast NSP 2021 (krok 4) | −0,1 |

Wnioski: (a) liczenie pary, gdy średnia z odjazdów z wynikiem ≤ 60 min mieści się w progu (zamiast wykluczenia pary nieosiągalnej w którymkolwiek z 9 odjazdów), zmienia wynik o ≤ 0,13 pkt, więc sposób traktowania braków w OTP nie tłumaczy różnicy; (b) efekt 9 odjazdów jest prawie taki sam przy dojściu 1 km i 5 km; (c) siatka ludności (GHSL surowy zamiast NSP 2021) zmienia wynik o ok. 2 pkt lub mniej; (d) błąd próby 800 startów ≤ 0,5 pkt; (e) wolniejsze odcinki piesze (4 km/h) obniżają KZ 30 i KZ 45 o podobną liczbę punktów, więc samo „wolniejsze chodzenie” w modelu DG REGIO nie wyjaśnia jednocześnie niższego KZ 30 i wyższego KZ 45. Ludności 2011 na poligonach Urban Atlas nie mamy; jej wpływu nie zmierzono. Według naszej siatki NSP 2021 w granicach UC 2011 mieszka w Łodzi o 11 % mniej osób niż w 2011 r. według aneksu, w Poznaniu o 4 % mniej (różne siatki, porównanie przybliżone).

## 6. Czy wartości DG REGIO 30 i 45 min są ze sobą spójne

| Miasto | Miara | DG: proximity / ludność UC | DG: osiągalni / ludność UC | My (UC): proximity / ludność UC | My (UC, krok 4): osiągalni / ludność UC | Nasz mianownik produkcyjny (FUA + 15 km) / ludność UC |
|---|---|---|---|---|---|---|
| Warszawa | PT 30 | 41,6 % | 12,8 % | 37,7 % | 14,6 % | 40,7 % |
| Warszawa | PT 45 | 68,8 % | 42,4 % | 65,4 % | 44,4 % | 73,6 % |
| Poznań | PT 30 | 81,3 % | 21,4 % | 77,8 % | 29,1 % | 89,3 % |
| Poznań | PT 45 | 97,5 % | 72,9 % | 97,0 % | 69,2 % | 127,0 % |
| Łódź | PT 30 | 79,8 % | 20,3 % | 77,3 % | 24,9 % | 84,2 % |
| Łódź | PT 45 | 97,4 % | 72,9 % | 97,2 % | 63,1 % | 118,2 % |

Pytanie (c): średnio 97,5 % ludności UC Poznania leży w promieniu 11,25 km od startu (u nas 97,0 %), więc KZ 45 = 74,8 znaczy, że przeciętny mieszkaniec dojeżdża w 45 min do 72,9 % wszystkich mieszkańców UC; w naszym odtworzeniu (krok 4) 69,2 %. W Łodzi DG 72,9 %, my 63,1 %. To nie jest wartość nieprawdopodobna: w zwartym UC o średnicy ok. 12 km 45 min komunikacją wystarcza dla większości par. Krzywa DG REGIO jest jednak bardziej stroma niż nasza: w Poznaniu osiągalni rosną z 21 % (30 min) do 73 % ludności UC (45 min), u nas z 29 % do 69 %. Wartości 30 i 45 min DG REGIO nie są ze sobą sprzeczne, ale nie da się ich odtworzyć jednym przesunięciem czasu naszej sieci (tabela niżej).

Ten sam wskaźnik jako „równoważny próg”: przy jakim progu czasu nasz wynik (domena UC, mianownik dla 30 lub 45 min bez zmian, krok 4) równa się wartości DG REGIO.

| Miasto | Miara | DG REGIO | Nasz próg dający wartość DG (min, interpolacja co 5 min) | Różnica progów (min) |
|---|---|---|---|---|
| Warszawa | KZ 30 | 30,9 | 27,6 | −2,4 |
| Warszawa | KZ 45 | 61,7 | 43,3 | −1,7 |
| Warszawa | pieszo 30 | 49,0 | 24,6 (co 1 min) | −5,4 |
| Poznań | KZ 30 | 26,3 | 26,2 | −3,8 |
| Poznań | KZ 45 | 74,8 | 46,5 | +1,5 |
| Poznań | pieszo 30 | 43,0 | 23,1 (co 1 min) | −6,9 |
| Łódź | KZ 30 | 25,4 | 27,2 | −2,8 |
| Łódź | KZ 45 | 74,8 | 48,9 | +3,9 |
| Łódź | pieszo 30 | 54,3 | 25,5 (co 1 min) | −4,5 |

Wartość DG REGIO dla 30 min odpowiada naszemu wynikowi przy ok. 26–28 min, a dla 45 min przy ok. 43 (Warszawa), 46–47 (Poznań) i 49 min (Łódź); pieszo przy 23–26 min zamiast 30. Krótkie podróże są więc w modelu DG REGIO wolniejsze niż u nas, także sam spacer (czyli sieć piesza, dowiązanie punktów, prędkość lub dobór trasy w OTP, nie komunikacja), a w Poznaniu i Łodzi dłuższe podróże komunikacją są u nich szybsze niż u nas. Drugiego nie wyjaśnia żaden zmierzony parametr metody; pasuje do większej podaży w ich danych 2018 (§7–8).

## 7. Czy brakuje kursów w naszych feedach?

Test bezpośredni (pytanie a). Aneks DG REGIO (tabela 1; definicja na s. 44–46 pracy) podaje dla każdego UC wozokilometry w linii prostej między kolejnymi przystankami kursu, odjazdy 6:00–20:00, oba przystanki w UC, na 1000 mieszkańców 2011, oraz prędkość w linii prostej. Policzono to samo z naszych feedów (warstwa usługowa po deduplikacji, wariant „wszystkie”, środa 2026-11-25, mianownik: ludność 2011 z aneksu). **Założenie niezweryfikowane:** jednostkę aneksu („km/1000 inh.”) czytamy jako wozkm na 1000 mieszkańców na godzinę okna 6–20; tylko przy tym odczycie wartości są tego samego rzędu (na dobę byłyby ok. 14× za małe). Ilorazy między trybami i między miastami od tej jednostki nie zależą.

Prędkości w linii prostej zgadzają się zwykle co do 1–2 km/h (metro w Warszawie 32,1 / 32,1), więc definicja jest odtworzona poprawnie. W Poznaniu i Łodzi DG REGIO miało ok. 1,7× więcej wozkm autobusowych na mieszkańca UC niż nasz feed 2026; tramwajowych tyle samo (Łódź) albo mniej (Poznań 0,68×, Warszawa 0,53×), a metra w Warszawie 0,19× naszego (w 2018 r. II linia miała tylko odcinek centralny, co samo nie tłumaczy pięciokrotnej różnicy). Taki wzór nie wygląda na brakującego przewoźnika po naszej stronie: w Poznaniu cała komunikacja ZTM (MPK i przewoźnicy podmiejscy) jest w jednym feedzie, w Łodzi feedy podmiejskie dają ok. 1 % wozkm w UC (`supply_uc_by_feed.csv`).

Kontrola z danymi przewoźników i organizatorów:

- **Poznań.** Raport miasta „Transport miejski w Poznaniu w 2024 r.” (badam.poznan.pl, dane MPK): 31,1 mln wozkm MPK w 2024 r., 23 linie tramwajowe (w tym 3 nocne), 67 autobusowych (w tym 14 nocnych). Nasz feed: MPK (agency 2) w środę ref. 95,2 tys. wozkm (tramwaj 40,0 tys., autobus 55,2 tys.; długości z kształtów), 20 linii tramwajowych i 70 autobusowych z kursami w tym dniu. 31,1 mln / 95,2 tys. = 327 „dni roboczych” na rok, typowa relacja rok / dzień roboczy, więc feed nie jest wyraźnie niepełny (dane roczne 2024, feed 2026: porównanie przybliżone).
- **Łódź.** Lista linii na mpk.lodz.pl (odczyt 2026-11-24): 23 linie tramwajowe dzienne, 81 pozycji autobusowych dziennych (z wariantami A/B/C/D), 14 nocnych, linie Z. W feedzie `lodz` w dniu ref. są wszystkie linie tramwajowe i wszystkie dzienne autobusowe z wyjątkiem 55B (brak w feedzie) i 81B (w feedzie tylko w soboty). Rocznej pracy przewozowej MPK Łódź nie znaleziono w źródle pierwotnym, więc kontroli wozkm dla Łodzi nie wykonano.
- **Warszawa:** nie kontrolowano z danymi ZTM (luka Warszawy przy 45 min po korekcie domeny jest ujemna).

| Miasto | Tryb | Nasze wozkm 6–20 w UC | Nasze: wozkm / 1000 mieszk. 2011 / h | DG REGIO 2018 (aneks t1_19–24) | DG / my | Prędkość w linii prostej: my / DG (km/h) |
|---|---|---|---|---|---|---|
| Warszawa | bus | 180 506 | 7,49 | 10,00 | 1,34 | 17,6 / 17,9 |
| Warszawa | metro | 20 619 | 0,86 | 0,16 | 0,19 | 32,1 / 32,1 |
| Warszawa | rail | 15 033 | 0,62 | 1,03 | 1,66 | 43,2 / 31,5 |
| Warszawa | tram | 76 565 | 3,17 | 1,68 | 0,53 | 17,9 / 16,6 |
| Warszawa | total | 292 723 | 12,14 | 12,88 | 1,06 | 18,9 / 18,4 |
| Poznań | bus | 32 857 | 4,41 | 7,35 | 1,67 | 16,2 / 16,4 |
| Poznań | rail | 1 864 | 0,25 | 0,55 | 2,21 | 47,0 / 44,8 |
| Poznań | tram | 29 760 | 3,99 | 2,72 | 0,68 | 18,8 / 17,8 |
| Poznań | total | 64 480 | 8,65 | 10,62 | 1,23 | 17,6 / 17,3 |
| Łódź | bus | 43 407 | 4,54 | 7,72 | 1,70 | 15,6 / 15,7 |
| Łódź | rail | 3 065 | 0,32 | 0,53 | 1,65 | 49,8 / 41,3 |
| Łódź | tram | 28 458 | 2,98 | 3,07 | 1,03 | 16,3 / 13,8 |
| Łódź | total | 74 929 | 7,84 | 11,32 | 1,44 | 16,4 / 15,6 |

Przystanki OSM (zdeduplikowane, faza 1) w UC bez obsługiwanego w dniu ref. przystanku GTFS w pobliżu (autobus/tramwaj 100 m, kolej 300 m):

| Miasto | Rodzaj | Przystanków OSM w UC | Bez GTFS w promieniu | Dopasowane |
|---|---|---|---|---|
| Warszawa | bus/tram | 4283 | 206 | 95,2 % |
| Warszawa | rail | 48 | 0 | 100,0 % |
| Poznań | bus/tram | 1433 | 75 | 94,8 % |
| Poznań | rail | 14 | 4 | 71,4 % |
| Łódź | bus/tram | 1643 | 61 | 96,3 % |
| Łódź | rail | 15 | 0 | 100,0 % |

Niedopasowane przystanki to głównie przystanki na żądanie („n/ż”, „NŻ”), przesunięcia 100–200 m, w Poznaniu kolejka parkowa Maltanka (4 „stacje” kolejowe), a w Łodzi przystanki tramwajowe na odcinkach wyłączonych z ruchu (Kilińskiego, Pomorska, Zielona, Narutowicza), co zgadza się z ustaleniem fazy 2, że zamknięte odcinki są widoczne tylko po stronie OSM. Nie ma skupisk wskazujących na brakującego przewoźnika w UC.

## 8. Czy dane wejściowe DG REGIO mogły być zbyt optymistyczne

Pytanie (b). Co wiadomo z pracy: feedy GTFS przewoźników (część zbiorów przekształcono z formatów krajowych, s. 35, bez wskazania miast), kolej z UIC MERITS, gdy feed miejski jej nie miał (s. 37), dzień roboczy z **największą liczbą odjazdów** w okresie ważności feedu (s. 35), ręczne wymuszanie wspólnej daty przy łączeniu feedów (s. 37). Konkretnych plików, ich dat i dnia nie podano ani w pracy, ani w kartach miast („public transport operators, UIC”), ani w aneksie.

Co z tego mogło zawyżać KZ 45 i co zmierzono:

- dzień z maksimum odjazdów przy feedzie z nakładającymi się wersjami rozkładu liczy kursy podwójnie; śladem byłaby nadwyżka wozkm, a nadwyżkę autobusową (ok. 1,7×) aneks pokazuje; przyczyny nie da się ustalić bez ich pliku (niezweryfikowane);
- wymuszenie wspólnej daty przy łączeniu z MERITS może dodać kursy kolejowe, które w tym dniu nie jeżdżą; kolej to w ich danych 5–8 % wozkm w UC, więc efekt ograniczony (niezmierzony);
- dojście do 5 km: zmierzone, +0,8 do +1,7 pkt;
- braki w średniej z 9 odjazdów: zmierzone, ≤ 0,13 pkt;
- domena UC (mały, zwarty obszar, mianownik przycięty): zmierzona, największy efekt; to definicja, nie błąd, ale faworyzuje miasta o małym i zwartym UC.

W przeciwną stronę działa wolniejszy spacer w ich modelu (zmierzony pośrednio przez wynik pieszy) i dobór trasy w OTP według kosztu uogólnionego (niezmierzony). Wniosek: dane DG REGIO dla Poznania i Łodzi były „hojniejsze” od naszych pod względem podaży autobusowej; czy to zawyżenie, czy realna podaż 2018 r., nie da się stwierdzić z dostępnych materiałów.

## 9. Pieszo i rower

**Pieszo:** zmiana domeny prawie nic nie zmienia (promień 2,5 km mieści się w UC). Po korekcie prędkości (OTP 1.x domyślnie 1,33 m/s według dokumentacji OTP, praca prędkości nie podaje; próg 28 min przy 5 km/h) zostaje −17,5 (Poznań), −9,1 (Łódź), −12,1 pkt (Warszawa): u DG REGIO osiągalnych jest mniej. Niezmierzone możliwe przyczyny: dowiązanie centroidów poligonów Urban Atlas do grafu OTP, kompletność i dostępność ścieżek pieszych w grafie OTP 1.2 z OSM ok. 2018 r., dobór trasy przez OTP według kosztu uogólnionego, rozkład ludności na poligonach zamiast komórek 250 m. To ta sama skłonność, która obniża ich KZ 30.

**Rower:** DG REGIO dla polskich miast liczyło na sieci TomTom: 15 km/h na każdej drodze poza autostradami, kontraruch na wszystkich jednokierunkowych (s. 40), czyli bliżej naszego LTS ≤ 4 niż LTS ≤ 3. Po zmianie domeny i agregacji zostaje przy LTS ≤ 4 +5,6 (Poznań), +12,1 (Łódź), +16,6 pkt (Warszawa). Kierunek pasuje do bardziej liberalnej sieci (kontraruch wszędzie, brak ograniczeń LTS i zakazów R5), ale tego nie zmierzono; sieci TomTom nie mamy. Rower nie zależy od GTFS, więc te reszty nie mówią nic o kompletności feedów; pokazują, że różnice sieci i routera między nami a DG REGIO sięgają 5–20 pkt nawet bez komunikacji.

## 10. Co uruchomiono, czego nie sprawdzono

Uruchomiono 2026-11-24, równolegle z produkcyjnym `pipeline.access run` (nie dotykano go): `python -m pipeline.access_dgregio prep` (ok. 45 s, bez JVM); `python -m pipeline.access_dgregio route ...` w jednej JVM naraz, 6 wątków, `-Xmx 8G`, na kopiach plików sieci w `data/interim/access_dgregio/r5/` (sieci produkcyjne tylko czytane): Poznań i Łódź na pełnym UC (KZ 1 km, KZ 5 km, KZ 5 km przy 4 km/h, rower LTS 3 i 4), Warszawa oraz warianty 9 odjazdów na próbie 800 startów; łącznie ok. 34 min zegarowych (czasy w `_meta.json`, `routing_log`). Pełnego UC Warszawy (4796 startów) nie liczono ze względu na limit czasu; błąd próby oszacowano w §5. Na końcu `python -m pipeline.access_dgregio report`.

**Założenia niezweryfikowane:** godziny „dwugodzinnego szczytu” DG REGIO (przyjęto 7:00–9:00); prędkość pieszego w OTP (domyślna 1,33 m/s); jednostka wozkm w aneksie (na godzinę); które feedy, z jakiej daty i z jakiego dnia użyto dla Warszawy, Poznania i Łodzi; roczna praca przewozowa MPK Łódź (nie znaleziono); wpływ ludności 2011 na poligonach Urban Atlas, routera OTP i sieci TomTom (nie do zmierzenia naszymi danymi). **Przygotowane, nieuruchomione:** archiwalnych feedów 2018 nie pobierano (transitfeeds.com odmawia automatycznego dostępu, HTTP 403; innych archiwów nie sprawdzono). To byłby rozstrzygający test reszty 45 min: zbudować sieć R5 z feedów Poznania i Łodzi z 2018 r. i uruchomić na niej `route` oraz kontrolę wozkm z §7.

## 11. Test rozkładu 2018 dla Poznania

**Wynik: kompletnego feedu Poznania z 2018 r. nie udało się zdobyć legalną drogą bez konta, więc pomiaru podaży z feedu 2018 i routingu na sieci 2018 nie wykonano** (punkty 1–3 zlecenia). Innego roku nie podstawiano. Co sprawdzono, w tabeli niżej. Jedyne zachowane pliki z 2018 r. (Internet Archive, grudzień 2018) są ucięte na 1 MiB; dało się z nich odczytać tylko listę linii i kalendarz. Pobrane kopie: `data/raw/wayback_ztm_poznan_gtfs_truncated_20181214_20181216/` i `..._20181228_20181228/` (z `SOURCE.json`).

Zastępczy test realnej zmiany podaży: raporty roczne MPK Poznań (2017 i 2024; raport 2018 jest skanem bez warstwy tekstowej). Zamówiona praca autobusowa MPK zmieniła się z 2017 na 2024 r. o −6,7 %, tramwajowa o +3,1 %. Realna zmiana podaży MPK między ok. 2018 a dziś jest więc mała i nie tłumaczy ilorazu autobusowego z aneksu (DG / my 1,67×) ani niższego tramwajowego (0,68×). Nasz feed 2026 zgadza się z pracą MPK 2024 (współczynnik rok / środa ok. 327, §7). Plik z 14–16 grudnia 2018 r. (piątek–niedziela) ma w `routes.txt` 81 linii autobusowych MPK (z nocnymi), plik z 28 grudnia (okres świąteczny) 70, nasz feed 2026 70; tramwajowych 19–21 we wszystkich. Linii innych przewoźników ZTM było wtedy mniej niż dziś (przyczyna, np. rozszerzenie obszaru ZTM, niezweryfikowana), więc w UC ich udział i tak jest mały. Więcej linii przy prawie tej samej rocznej pracy autobusowej nie daje 1,7× wozkm.

Wniosek dla pytania o zawyżenie: realne dane przewoźnika nie potwierdzają, że w 2018 r. w Poznaniu jeździło 1,7× więcej autobusów niż dziś. To wzmacnia hipotezę, że autobusowa część danych wejściowych DG REGIO była zawyżona (np. podwójne kursy z nakładających się wersji rozkładu w dniu „z największą liczbą odjazdów”) albo inaczej sklasyfikowana, ale **bez ich pliku nie da się tego sprawdzić**, a kontroli duplikatów na feedzie 2018 nie wykonano (brak pliku). Zastrzeżenia: raport MPK obejmuje całą sieć MPK, nie sam UC; pociągokm tramwaju to kursy (jak w GTFS), a nie wagony. Łódź: nie znaleziono dowodu na istnienie operatorskiego GTFS MPK Łódź w 2018 r. (szukano krótko, bez wyniku w obie strony).

| źródło | adres | wynik |
|---|---|---|
| ZTM Poznań, lista plików GTFS (otwarte-dane/gtfsfiles) | https://www.ztm.poznan.pl/otwarte-dane/gtfsfiles/ | lista obejmuje 483 pliki, najstarszy 20230101_20230104.zip; brak plików z 2018 r. |
| ZTM Poznań, getGTFSFile z nazwą pliku z 2018 r. | https://www.ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile/?file=20181214_20181216.zip | serwer zwraca bieżący feed (feed_info 20261124–20261205) niezależnie od nazwy; pobrany plik usunięto |
| Internet Archive, indeks CDX adresów getGTFSFile | web.archive.org/cdx/search/cdx?url=ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile* | 617 zarchiwizowanych plików, z 2018 r. tylko 3: 20181214_20181216, 20181224_20181225, 20181228_20181228 (pierwsze kopie z 2019 r.) |
| Internet Archive, kopie plików z grudnia 2018 r. | web.archive.org/web/<ts>id_/…getGTFSFile/?file=… | każda kopia ucięta przez archiwum na 1 MiB: kompletne są agency, calendar, routes (i w 20181228 shapes, stops); stop_times i trips brak, więc wozkm i routing niemożliwe; to samo dla sprawdzonych plików z 2019 r. |
| transitfeeds.com (OpenMobilityData) i jego magazyn S3 | https://transitfeeds.com/p/ztm-poznan/731 | HTTP 403 z wyzwaniem Cloudflare (ochrona przed botami, nie obchodzono); listing S3 openmobilitydata-data: AccessDenied; brak kopii w Internet Archive |
| Mobility Database | https://mobilitydatabase.org/feeds/gtfs/mdb-982 | historia tylko od ok. 2024 r. według strony katalogu (nie sprawdzano API wymagającego konta) |

Liczba linii w `routes.txt` (pliki z grudnia 2018 r. z Internet Archive; tylko ta tabela była w nich kompletna):

| Plik | MPK autobus | MPK tramwaj | inni przewoźnicy ZTM (autobus) |
|---|---|---|---|
| 20181214_20181216 | 81 | 20 | 48 |
| 20181228_20181228 | 70 | 19 | 43 |
| 2026 (pipeline, ważny od 20261124) | 70 | 21 | 128 |

Praca przewozowa MPK Poznań (tys. km rocznie; tramwaj w pociągokm, czyli kursach, autobus w wozokm):

| rok | rodzaj | tramwaj_tys_pociagokm | autobus_tys_wozokm | źródło |
|---|---|---|---|---|
| 2017 | plan (zał. 1 do umowy) | 12037 | 19287 | MPK Poznań, raport roczny 2017, s. 14 PDF |
| 2017 | zamówienie skorygowane | 11779 | 19343 | MPK Poznań, raport roczny 2017, s. 14 PDF |
| 2024 | plan (zał. 1 do umowy) | 12142 | 18050 | MPK Poznań, raport roczny 2024, s. 18 i 20 PDF |
| 2024 | wykonanie | 11984 | 17898 | MPK Poznań, raport roczny 2024, s. 18 i 20 PDF |

Pliki: `feed2018_attempts.csv`, `feed2018_routes.csv`, `mpk_poznan_vkm_annual.csv`; `urban_centres.csv`, `decomposition.csv`, `sensitivity.csv`, `plausibility_30_45.csv`, `curves_uc.csv`, `supply_uc_vs_annex.csv`, `supply_uc_by_feed.csv`, `stops_uc_osm_vs_gtfs.csv`, `production_chunks_domains.csv`, `_meta.json`.
