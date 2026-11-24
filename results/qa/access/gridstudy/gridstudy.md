# Wariant porównawczy z grid study DG REGIO (Poelman i Ackermans)

Plik generuje `python -m pipeline.access_gridstudy report` (krok poboczny, tylko do porównań; wynik główny bez zmian). Liczby: `results/metrics/metrics_access_gridstudy.csv/json`, `decomposition.csv`, `final.csv`. Kod: `pipeline/access_gridstudy.py`, `access_gridstudy_report.py`, `access_gridstudy_eu.py`. Źródło: H. Poelman, L. Ackermans, „Assessing the performance of urban public transport using population grid data”, DG REGIO, PDF z ec.europa.eu (nagłówek Last-Modified 2023-02-08; w tekście daty brak), zapisany w `data/raw/dgregio_gridstudy/`.

## 1. Odpowiedź w skrócie

**Według reguł grid study polskie miasta wypadają przy średnich swoich klas wielkości: przy 30 min na poziomie średniej, przy 45 min powyżej (poza GZM).** Wartości porównawcze (średnia wyników komórek, jak w pracy; §6): KZ 30 = 36,1–41,7 (średnie klas 35,8–41,8; różnice od −3,2 w Poznaniu do +2,7 w Warszawie), KZ 45 = 61,6–67,0 w sześciu miastach (2,1–6,4 pkt powyżej średnich klas 59,5–63,3) i 53,8 w GZM (5,7 pkt poniżej średniej klasy 1–2,5 mln, w dolnej połowie jej zakresu 37,4–71,1). Odstęp od średnich klas, który przegląd literatury widział przy 30 min (rdzenie 24–34 wobec 35,8–39,3), wynikał więc z metody, a nie z gorszej komunikacji.

**Wobec wartości DG REGIO dla tych samych centrów** (odtworzonych z komórek ich przeglądarki; §3), przy startach ograniczonych do centrum 2011: przy 45 min Kraków, Poznań i Łódź są w granicach 1,8–3,0 pkt powyżej DG REGIO, przy 30 min 2,2–3,9 pkt poniżej; Warszawa jest poniżej o ok. 8 pkt przy obu progach (DG REGIO: 47,1 i 71,1, maksimum klasy 1–2,5 mln). Czy przyczyną są rozkłady 2019–2021 (np. kolej), łączny limit spaceru, sieć piesza OTP czy sposób liczenia oczekiwania w OTPA, nie ustalono. Wariant „najszybsza podróż w całym oknie 7:00–9:00” (bez oczekiwania na start) przekracza wartości DG REGIO przy 45 min o 7–9 pkt w trzech miastach (cała domena), więc DG REGIO nie liczy go w ten sposób; reguła z pracy (najkrótszy z 6 odjazdów w 30-minutowym szczycie) pasuje lepiej.

**Co zmienia wynik (dekompozycja, §5):** cele i mianownik poza centrum obniżają wynik o 1,6–3,6 pkt (30 min) i 3,8–10,8 pkt (45 min); promienie 8 / 12 km o 1,8–3,3 i 2,1–4,1; limit pieszy 15 min / 1,2 km o 0,9–1,4 i 0,2–1,1; najkrótszy z 6 odjazdów w szczycie zamiast mediany z dwóch godzin podnosi o 8,5–13,3 i 10,2–18,3 pkt (największy pojedynczy efekt, najsilniejszy w GZM); średnia wyników komórek zamiast stosunku średnich zmienia wynik o −2,9 do +2,5 pkt. Sama „najszybsza podróż” nie jest więc jedyną różnicą: kroki domeny i promieni działają w przeciwną stronę.

Wniosek praktyczny: to wariant tylko do porównań z UE. Wynik główny (mediana, 7:00–9:00, stosunek średnich) zostaje bez zmian; różnice między polskimi miastami a średnimi UE w tym wariancie są tego samego rzędu co niepewność odtworzenia (Warszawa −8 pkt wobec DG REGIO przy tej samej metodzie), więc nie należy ich czytać jako rankingu.

## 2. Metoda grid study ustalona ze źródła

Strony wg numeracji drukowanej PDF (16 stron).

| Element | Grid study | Strona |
|---|---|---|
| Jednostka | urban centre (klaster komórek 1 km² ≥ 1500 os./km², ≥ 50 tys.) na siatce **GEOSTAT 2011**; 197 z 683 centrów UE | s. 2, przyp. 5; s. 3 |
| Starty | środki zaludnionych komórek 200 × 200 m w urban centre | s. 2 |
| Cele | środki zaludnionych komórek 200 m w promieniu 12 km (8 km) od startu, **także poza urban centre** | s. 2, s. 15 |
| Mianownik (proximity) | cała ludność w promieniu 12 km (45 min) lub 8 km (30 min), 16 km/h w linii prostej, **bez przycięcia do urban centre** | s. 2, s. 13 |
| Ludność | JRC-GEOSTAT 2018, siatka 100 m zsumowana do 200 m (zgodnie z siatką 1 km) | s. 2 przyp. 4, s. 13 |
| Własna komórka | wliczona do dostępności i do proximity | s. 15 |
| Router | OpenTripPlanner Analyst (OTPA) 1.5; punkty dociągnięte do sieci OSM (≤ 1000 m) | s. 14 |
| Okno i reguła czasu | odjazdy **co 5 min w 30-minutowym szczycie porannym**; start okna = pół godziny rozpoczynające godzinę z największą liczbą odjazdów na przystankach centrum; z ≤ 6 czasów bierze się **najkrótszy** („best available trip … fastest connection”) | s. 2–3, s. 14–15 |
| Spacer | łącznie (dojście + przesiadki + odejście) ≤ 15 min; sam spacer ≤ 1,2 km (prędkość niepodana; z tych liczb 4,8 km/h) | s. 2, s. 15 |
| Odległość | kryterium 8 / 12 km w linii prostej między punktami (EPSG:3035) | s. 15 |
| Rozkłady | dzień roboczy poza wakacjami; zwykle okres 2019–2021; daty dla miast niepodane | s. 2 |
| Wynik miasta | średnie ważone ludnością komórki startu: dostępności, proximity i performance | s. 15 |
| Średnie w tabeli 1 | ważone ludnością centrów; 30 min: 36,2 (wszystkie), 39,3 (500 tys.–1 mln), 35,8 (1–2,5 mln); 45 min: 53,9, 59,8, 59,5 | s. 3 |
| Polskie centra | „some major cities in … Poland”; wg listy przeglądarki: Warszawa, Kraków, Poznań, Łódź | s. 3; lista przeglądarki |

**Różnice wobec opisu w zleceniu i w przeglądzie literatury.** Cele i mianownik *nie* są ograniczone do urban centre (ograniczone są tylko starty); osiągalni liczą się tylko w promieniu 8 / 12 km; okno to 30 minut (6 odjazdów co 5 min), a nie dwie godziny; limit 15 min dotyczy łącznego spaceru w podróży, nie każdego odcinka. Wynik miasta to średnia **wyników komórek** ważona ludnością, nie stosunek średnich: tekst (s. 15) mówi o „średnich ważonych … performance”, a odtworzona z komórek średnia wyników dla Warszawy (§3) równa się co do 0,1 pkt maksimum klasy 1–2,5 mln z tabeli 1 przy obu progach (47,1 i 71,1), czego stosunek średnich nie daje. Dlatego wartość porównawcza jest tu liczona tak samo (krok 6).

## 3. Wartości grid study dla polskich centrów

W pracy polskie wartości są tylko na mapach 1–2 i wykresach 5–10 (bez liczb w tekście, bez aneksu). Opisana w pracy przeglądarka (przyp. 7) jest pod starym adresem niedostępna (404), ale działa pod `https://ec.europa.eu/regional_policy/assets/scripts/map/regio-gis-maps/public_transport/city_acc_grid.html`. Jej warstwy to publiczna usługa ArcGIS REST `https://europa.eu/regiogis/rest/services/PublicTransport/city_acc_grid/MapServer`; zapytanie `identify` zwraca dokładną wartość komórki 200 m każdej warstwy (performance, dostępność, proximity, udział spaceru, ludność 2018). Zapytano o środek każdej komórki 200 m w czterech polskich centrach z listy przeglądarki (Warszawa, Kraków, Poznań, Łódź; Wrocławia, Gdańska, Gdyni i GZM w analizie nie ma) i policzono wartości miast z komórek. Bez logowania i bez obchodzenia zabezpieczeń; kopie odpowiedzi: `data/raw/dgregio_gridstudy/cells/`.

| Centrum (GEOSTAT 2011) | Pow. km² | Klasa (ludność 2011) | Komórek 200 m (zapytano / z wartością) | Ludność 2018 w komórkach | KZ 30: średnia komórek (jak w pracy) | KZ 30: stosunek średnich | KZ 45: średnia komórek (jak w pracy) | KZ 45: stosunek średnich | Udział spaceru 30 / 45 (%) | Kontrola: max |dost./prox.×100 − perf.| |
|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 309 | 1m-2.5m | 7725 / 5689 | 1 783 408 | 47,1 | 49,5 | 71,1 | 73,9 | 5,2 / 2,0 | 0.0000 |
| Kraków | 109 | 500k-1m | 2725 / 2058 | 673 897 | 43,0 | 43,6 | 63,3 | 63,4 | 8,1 / 3,8 | 0.0000 |
| Poznań | 117 | 500k-1m | 2925 / 2083 | 519 367 | 40,8 | 41,7 | 63,2 | 63,5 | 7,2 / 3,6 | 0.0000 |
| Łódź | 117 | 500k-1m | 2925 / 2169 | 641 048 | 38,1 | 39,0 | 63,5 | 63,7 | 9,1 / 4,1 | 0.0000 |

Kontrola spójności: w każdej komórce performance = dostępność / proximity × 100 (ostatnia kolumna), więc warstwy odczytano poprawnie. Komórki bez ludności zwracają brak wartości i nie wchodzą do średnich. Udział spaceru: część osiągalnej ludności dostępna samym spacerem (≤ 15 min).

## 4. Nasz wariant

- **Starty:** zaludnione komórki 250 m centrów miejskich Eurostatu 2021 w FUA (domena `access_uc`, te same komórki i wagi). Gdzie centrów jest kilka, liczone są razem; grid study liczy każde osobno. Wariant ze startami tylko w centrum 2011 analizowanym przez DG REGIO: §6.
- **Cele i mianownik:** wszystkie zaludnione komórki 250 m w promieniu 8 / 12 km od startu, także poza centrum (siatka spisowa NSP 2021; surowy GHSL jako wariant). Własna komórka wliczona.
- **Routing:** R5 v7.5.1 na kopiach sieci produkcyjnych „wszystkie feedy”, środa 2026-11-25. Trzy przebiegi na tych samych startach i celach: `r_prod` (pieszo 5 km/h, dojście i odejście ≤ 12 min, okno 7:00–9:00 co minutę, percentyle 1 i 50), `r_grid` (pieszo 4,8 km/h, dojście i odejście ≤ 15 min każde, to samo okno i percentyle), `r_peak` (jak `r_grid`, ale 6 pojedynczych odjazdów co 5 min w 30-minutowym szczycie miasta, minimum z 6). Promienie, domena celów i reguła spaceru zmieniane są przy zliczaniu, więc wszystkie kroki dotyczą tych samych wyszukiwań.
- **Szczyt 30-minutowy** (reguła z s. 14–15: początek godziny z największą liczbą odjazdów na przystankach centrum, start co pół godziny, 5:00–11:00; z naszych feedów 2026): Warszawa od 07:00; Kraków od 07:30; Wrocław od 06:30; Poznań od 07:00; Łódź od 06:30; Trójmiasto od 07:00; GZM od 06:30.
- **„Najszybsza” w oknie 2 h (wariant):** R5 nie przyjmuje percentyla 0; percentyl 1 ze 120 minut okna jest średnio o 0,52 min wolniejszy od minimum ze 120 pojedynczych odjazdów (równy w 48 % par, różnica najwyżej 1 min; jeden start w Poznaniu, ok. 3 900 celów; `python -m pipeline.access_gridstudy check`).
- **Spacer:** sam spacer z produkcyjnej pamięci spacerów (5 km/h) przeliczony na 4,8 km/h i dopuszczony do 15 min (1,2 km); w wariancie produkcyjnym do 60 min.
- **Kontrola odtworzenia:** przebieg `r_prod` (mediana, cele tylko w centrum) daje w próbie 100 startów w Poznaniu te same sumy osiągalnych na komórkę co opublikowany przebieg `access_uc` (45 min identycznie, 30 min różnica 0,007 % z jednej komórki).

## 5. Dekompozycja: od opublikowanego wyniku urban centre do reguł grid study

Siatka spisowa. Kroki 0–5 to stosunek średnich (jak wynik opublikowany), krok 6 zmienia tylko agregację na średnią wyników komórek (jak DG REGIO). Każdy krok zmienia jedną rzecz względem poprzedniego; w nawiasie zmiana w pkt.

**KZ 30 min**

| Aglomeracja | 0. Opublikowany (UC) | 1. Osiągalni tylko w promieniu | 2. Cele i mianownik poza UC | 3. Promienie 8/12 km | 4. Pieszo 15 min / 1,2 km | 5. Min z 6 odjazdów w szczycie 30 min | 6. Średnia wyników komórek | Wariant: najszybsza 7–9 zamiast kroku 5 |
|---|---|---|---|---|---|---|---|---|
| Warszawa | 37,3 | 36,9 (−0,4) | 35,3 (−1,6) | 32,0 (−3,3) | 30,6 (−1,4) | 39,7 (+9,0) | **38,5** (−1,2) | 45,1 (+14,5); średnia komórek 44,2 |
| Kraków | 36,7 | 36,7 (−0,0) | 34,2 (−2,6) | 31,3 (−2,8) | 30,2 (−1,1) | 38,9 (+8,8) | **38,5** (−0,5) | 45,5 (+15,3); średnia komórek 44,9 |
| Wrocław | 33,4 | 33,3 (−0,0) | 30,9 (−2,5) | 29,0 (−1,8) | 28,0 (−1,1) | 40,1 (+12,2) | **39,1** (−1,0) | 43,4 (+15,5); średnia komórek 42,6 |
| Poznań | 35,5 | 35,4 (−0,0) | 32,1 (−3,3) | 30,0 (−2,2) | 28,8 (−1,2) | 37,3 (+8,5) | **36,1** (−1,2) | 44,3 (+15,5); średnia komórek 43,0 |
| Łódź | 32,5 | 32,4 (−0,0) | 30,0 (−2,5) | 28,1 (−1,8) | 27,1 (−1,0) | 36,9 (+9,8) | **38,3** (+1,4) | 41,6 (+14,4); średnia komórek 43,2 |
| Trójmiasto | 37,1 | 36,7 (−0,4) | 33,1 (−3,6) | 30,9 (−2,2) | 29,9 (−1,0) | 40,8 (+11,0) | **41,7** (+0,8) | 47,7 (+17,9); średnia komórek 48,7 |
| GZM | 26,0 | 26,0 (−0,0) | 23,4 (−2,5) | 21,2 (−2,2) | 20,3 (−0,9) | 33,6 (+13,3) | **36,1** (+2,5) | 40,3 (+20,0); średnia komórek 42,6 |

**KZ 45 min**

| Aglomeracja | 0. Opublikowany (UC) | 1. Osiągalni tylko w promieniu | 2. Cele i mianownik poza UC | 3. Promienie 8/12 km | 4. Pieszo 15 min / 1,2 km | 5. Min z 6 odjazdów w szczycie 30 min | 6. Średnia wyników komórek | Wariant: najszybsza 7–9 zamiast kroku 5 |
|---|---|---|---|---|---|---|---|---|
| Warszawa | 65,1 | 63,3 (−1,8) | 59,6 (−3,8) | 55,5 (−4,1) | 54,4 (−1,1) | 64,5 (+10,2) | **61,6** (−2,9) | 70,7 (+16,3); średnia komórek 68,1 |
| Kraków | 64,4 | 64,4 (−0,0) | 56,7 (−7,6) | 54,5 (−2,3) | 53,7 (−0,8) | 64,4 (+10,6) | **64,1** (−0,3) | 72,1 (+18,3); średnia komórek 71,8 |
| Wrocław | 65,7 | 65,7 (−0,0) | 57,6 (−8,1) | 55,4 (−2,1) | 54,7 (−0,7) | 67,1 (+12,4) | **66,2** (−0,9) | 71,4 (+16,7); średnia komórek 70,6 |
| Poznań | 67,0 | 67,0 (−0,0) | 56,1 (−10,8) | 53,8 (−2,3) | 53,2 (−0,6) | 64,5 (+11,2) | **63,9** (−0,6) | 72,2 (+19,0); średnia komórek 71,7 |
| Łódź | 61,7 | 61,7 (−0,1) | 53,9 (−7,8) | 51,8 (−2,1) | 51,2 (−0,6) | 65,9 (+14,7) | **64,9** (−1,0) | 71,7 (+20,5); średnia komórek 70,9 |
| Trójmiasto | 66,7 | 63,7 (−3,0) | 55,8 (−7,9) | 53,6 (−2,2) | 53,4 (−0,2) | 66,0 (+12,5) | **67,0** (+1,0) | 72,5 (+19,0); średnia komórek 73,4 |
| GZM | 43,2 | 42,9 (−0,3) | 37,6 (−5,3) | 34,5 (−3,1) | 34,2 (−0,3) | 52,6 (+18,3) | **53,8** (+1,3) | 60,4 (+26,1); średnia komórek 61,6 |

Opis kroków:

- 1. Dostępność liczona tylko w promieniu 7,5 / 11,25 km (grid study liczy osiągalnych tylko w promieniu; my dotąd wszystkich osiągalnych).
- 2. Cele i mianownik bez ograniczenia do urban centre (wszystkie zaludnione komórki w promieniu).
- 3. Promienie 8 / 12 km (16 km/h) zamiast 7,5 / 11,25 km.
- 4. Pieszo 4,8 km/h, dojście i odejście do 15 min, sam spacer do 1,2 km (zamiast 5 km/h, 12 min, spacer do 60 min).
- 5. Najkrótszy z 6 odjazdów co 5 min w 30-minutowym szczycie miasta zamiast mediany z 7:00–9:00 (reguła z pracy, s. 14–15).
- 6. Agregacja jak DG REGIO: średnia wyników komórek ważona ludnością zamiast stosunku średnich.
- Wariant: najszybsza podróż w całym oknie 7:00–9:00 (percentyl 1 R5) zamiast kroku 5.

**Efekty pojedyncze** (każda zmiana osobno od kroku 2, te same starty, stosunek średnich; pkt). Suma efektów pojedynczych nie musi równać się łańcuchowi, bo efekty zależą od siebie (np. najszybsza podróż zyskuje więcej przy dłuższym dojściu).

| Aglomeracja | KZ 30: tylko promienie 8 / 12 km | KZ 30: tylko limit pieszy grid study | KZ 30: tylko najszybsza podróż 7–9 | KZ 45: tylko promienie 8 / 12 km | KZ 45: tylko limit pieszy grid study | KZ 45: tylko najszybsza podróż 7–9 |
|---|---|---|---|---|---|---|
| Warszawa | −3,3 | −1,5 | +16,0 | −4,1 | −1,2 | +16,6 |
| Kraków | −2,8 | −1,3 | +16,9 | −2,3 | −0,8 | +18,8 |
| Wrocław | −1,8 | −1,1 | +16,6 | −2,1 | −0,7 | +16,9 |
| Poznań | −2,2 | −1,2 | +16,7 | −2,3 | −0,6 | +19,3 |
| Łódź | −1,8 | −1,0 | +15,5 | −2,1 | −0,6 | +20,7 |
| Trójmiasto | −2,2 | −1,1 | +19,0 | −2,2 | −0,2 | +19,2 |
| GZM | −2,2 | −1,0 | +21,9 | −3,1 | −0,3 | +27,5 |

## 6. Wynik końcowy obok grid study

Wartość porównawcza = krok 6 (reguły grid study, średnia wyników komórek). Klasa wielkości wg ludności największego centrum aglomeracji (Eurostat 2021), bo grid study liczy każde centrum osobno. Średnie klas i zakres min–max: tabela 1 pracy (s. 3), średnie ważone ludnością centrów; wszystkie 197 centrów: 36,2 (30 min) i 53,9 (45 min).

**KZ 30 min** (średnia wyników komórek; w nawiasie stosunek średnich)

| Aglomeracja | Opublikowany UC (stosunek średnich) | Reguły grid study | To samo, starty tylko w centrum 2011 | DG REGIO dla tego centrum | Różnica my − DG (centrum 2011) | Klasa (największe centrum) | Średnia klasy (min–max) | My − średnia klasy |
|---|---|---|---|---|---|---|---|---|
| Warszawa | 37,3 | **38,5** (39,7) | 38,8 (40,0) | **47,1** (49,5) | −8,2 | 1m-2.5m (10 centrów) | 35,8 (26,0–47,1) | +2,7 |
| Kraków | 36,7 | **38,5** (38,9) | 39,4 (39,6) | **43,0** (43,6) | −3,6 | 500k-1m (17 centrów) | 39,3 (24,8–56,8) | −0,8 |
| Wrocław | 33,4 | **39,1** (40,1) | – | brak w analizie | – | 500k-1m (17 centrów) | 39,3 (24,8–56,8) | −0,2 |
| Poznań | 35,5 | **36,1** (37,3) | 36,9 (37,9) | **40,8** (41,7) | −3,9 | 500k-1m (17 centrów) | 39,3 (24,8–56,8) | −3,2 |
| Łódź | 32,5 | **38,3** (36,9) | 35,9 (36,5) | **38,1** (39,0) | −2,2 | 500k-1m (17 centrów) | 39,3 (24,8–56,8) | −1,0 |
| Trójmiasto | 37,1 | **41,7** (40,8) | – | brak w analizie | – | 250k-500k (14 centrów) | 41,8 (23,8–63,7) | −0,1 |
| GZM | 26,0 | **36,1** (33,6) | – | brak w analizie | – | 1m-2.5m (10 centrów) | 35,8 (26,0–47,1) | +0,3 |

**KZ 45 min** (średnia wyników komórek; w nawiasie stosunek średnich)

| Aglomeracja | Opublikowany UC (stosunek średnich) | Reguły grid study | To samo, starty tylko w centrum 2011 | DG REGIO dla tego centrum | Różnica my − DG (centrum 2011) | Klasa (największe centrum) | Średnia klasy (min–max) | My − średnia klasy |
|---|---|---|---|---|---|---|---|---|
| Warszawa | 65,1 | **61,6** (64,5) | 63,3 (65,4) | **71,1** (73,9) | −7,8 | 1m-2.5m (10 centrów) | 59,5 (37,4–71,1) | +2,1 |
| Kraków | 64,4 | **64,1** (64,4) | 65,2 (65,4) | **63,3** (63,4) | +1,9 | 500k-1m (17 centrów) | 59,8 (31,3–79,1) | +4,3 |
| Wrocław | 65,7 | **66,2** (67,1) | – | brak w analizie | – | 500k-1m (17 centrów) | 59,8 (31,3–79,1) | +6,4 |
| Poznań | 67,0 | **63,9** (64,5) | 65,0 (65,5) | **63,2** (63,5) | +1,8 | 500k-1m (17 centrów) | 59,8 (31,3–79,1) | +4,1 |
| Łódź | 61,7 | **64,9** (65,9) | 66,5 (66,7) | **63,5** (63,7) | +3,0 | 500k-1m (17 centrów) | 59,8 (31,3–79,1) | +5,1 |
| Trójmiasto | 66,7 | **67,0** (66,0) | – | brak w analizie | – | 250k-500k (14 centrów) | 63,3 (31,7–83,9) | +3,7 |
| GZM | 43,2 | **53,8** (52,6) | – | brak w analizie | – | 1m-2.5m (10 centrów) | 59,5 (37,4–71,1) | −5,7 |

## 7. Wrażliwość i kontrole

| Aglomeracja | Surowy GHSL, krok 6: KZ 30 / 45 | Najszybsza 7–9, średnia komórek: KZ 30 / 45 | Udział ludności startów w centrum 2011 | Udział spaceru w dostępności, krok 5: 30 / 45 (%) | Udział spaceru, DG REGIO (%) |
|---|---|---|---|---|---|
| Warszawa | 38,6 / 63,1 | 44,2 / 68,1 | 91,7 % | 2,0 / 0,7 | 5,2 / 2,0 |
| Kraków | 37,6 / 65,2 | 44,9 / 71,8 | 94,7 % | 2,8 / 1,1 | 8,1 / 3,8 |
| Wrocław | 39,8 / 66,8 | 42,6 / 70,6 | – | 2,7 / 1,2 | – |
| Poznań | 34,6 / 60,6 | 43,0 / 71,7 | 95,4 % | 2,9 / 1,2 | 7,2 / 3,6 |
| Łódź | 36,8 / 62,2 | 43,2 / 70,9 | 91,6 % | 3,3 / 1,3 | 9,1 / 4,1 |
| Trójmiasto | 42,1 / 67,3 | 48,7 / 73,4 | – | 3,3 / 1,4 | – |
| GZM | 33,6 / 51,5 | 42,6 / 61,6 | – | 3,4 / 1,2 | – |

Udział spaceru w grid study dla wszystkich 197 centrów: 9,1 % (8 km) i 3,9 % (12 km), s. 6. Udział spaceru liczony jako stosunek sum (osiągalni pieszo / osiągalni), ważony ludnością startu.

## 8. Ograniczenia i nie zweryfikowano

- R5 ogranicza osobno dojście i odejście (po 15 min), nie łączny spacer w podróży; grid study ogranicza łączny spacer do 15 min. Nasz wariant dopuszcza więc dłuższe łączne dojścia: zawyża wynik wobec reguły z pracy (wielkości nie zmierzono).
- „Najszybsza” to percentyl 1 R5, średnio o 0,52 min wolniejszy od prawdziwego minimum (pomiar na jednym starcie); zaniża wynik kroku 4 nieznacznie.
- Inny router (R5 zamiast OTPA 1.5), inna sieć OSM i inna siatka ludności (250 m NSP 2021 zamiast 200 m JRC 2018); rozkłady 2026 zamiast 2019–2021.
- Domena startów: centra Eurostatu 2021, w czterech aglomeracjach łączone (grid study: centra 2011, każde osobno). Wariant ze startami w centrum 2011 obejmuje tylko część wspólną z naszą domeną.
- Sposób agregacji w grid study (średnia wyników komórek czy stosunek średnich) nie jest jednoznaczny w tekście; dla czterech miast liczymy oba z komórek DG REGIO, ale nie da się sprawdzić, którą wartość zawiera tabela 1.
- Wartości DG REGIO dla polskich centrów odtworzono z komórek przeglądarki; zgodności z wartościami na mapach 1–2 (klasy) nie sprawdzano wzrokowo.
- Szczyt 30-minutowy wyznaczono z naszych feedów 2026 (stop_times na przystankach centrum 2021), nie z danych DG REGIO.
- Udział spaceru w dostępności jest u nas 2–3 razy mniejszy niż w komórkach DG REGIO (np. Poznań 2,9 wobec 7,2 % przy 30 min). Liczymy cel jako „pieszy”, gdy sam spacer jest nie wolniejszy od podróży z komunikacją; DG REGIO może liczyć inaczej (np. każdy cel w zasięgu 15 min pieszo) albo mieć gęstszą sieć pieszą. Nie wyjaśniono.
- Wrocław, Trójmiasto i GZM nie są w analizie DG REGIO: dla nich jest tylko porównanie ze średnią klasy. Trójmiasto i GZM to u nas sumy kilku centrów; klasa wg największego centrum (Gdańsk, Katowice).
- W Łodzi domena 2021 obejmuje drugie, mniejsze centrum; wynik dla całej domeny (38,3 przy 30 min) jest wyższy niż dla startów w centrum 2011 (35,9). Porównanie z DG REGIO używa tej drugiej wartości.
- Różnica Warszawy wobec DG REGIO (ok. −8 pkt) jest niewyjaśniona; ten sam znak i podobna wielkość przy obu progach wskazują na różnicę danych lub sieci, nie na regułę czasu.
- Nie zweryfikowano: daty rozkładów DG REGIO dla polskich miast; czy dla polskich miast użyto kolei (PKP, SKM, WKD, KM); czy OTPA wlicza początkowe oczekiwanie; wpływu łącznego limitu spaceru.

## 9. Co uruchomiono

- Odczyt komórek DG REGIO: `python -m pipeline.access_gridstudy_eu fetch` (16 300 zapytań `identify`, 3 naraz, ok. 1 h) i `summary`.
- `python -m pipeline.access_gridstudy peak`, `check` (Poznań), `route` (jedna JVM, 4 wątki, `-Xmx 8G`, równolegle z innymi krokami na tej maszynie): warszawa r_prod: 5797 origins x 1 searches in 757 s (131 ms/origin, 4 threads); warszawa r_grid: 5797 origins x 1 searches in 880 s (152 ms/origin, 4 threads); warszawa r_peak: 5797 origins x 6 searches in 609 s (105 ms/origin, 4 threads); krakow r_prod: 2069 origins x 1 searches in 125 s (61 ms/origin, 4 threads); krakow r_grid: 2069 origins x 1 searches in 151 s (73 ms/origin, 4 threads); krakow r_peak: 2069 origins x 6 searches in 137 s (66 ms/origin, 4 threads); wroclaw r_prod: 1962 origins x 1 searches in 74 s (38 ms/origin, 4 threads); wroclaw r_grid: 1962 origins x 1 searches in 90 s (46 ms/origin, 4 threads); wroclaw r_peak: 1962 origins x 6 searches in 82 s (42 ms/origin, 4 threads); poznan r_prod: 2039 origins x 1 searches in 64 s (31 ms/origin, 4 threads); poznan r_grid: 2039 origins x 1 searches in 67 s (33 ms/origin, 4 threads); poznan r_peak: 2039 origins x 6 searches in 70 s (34 ms/origin, 4 threads); lodz r_prod: 1936 origins x 1 searches in 68 s (35 ms/origin, 4 threads); lodz r_grid: 1936 origins x 1 searches in 72 s (37 ms/origin, 4 threads); lodz r_peak: 1936 origins x 6 searches in 81 s (42 ms/origin, 4 threads); trojmiasto r_prod: 1936 origins x 1 searches in 53 s (27 ms/origin, 4 threads); trojmiasto r_grid: 1936 origins x 1 searches in 59 s (30 ms/origin, 4 threads); trojmiasto r_peak: 1936 origins x 6 searches in 66 s (34 ms/origin, 4 threads); gzm r_prod: 5589 origins x 1 searches in 284 s (51 ms/origin, 4 threads); gzm r_grid: 5589 origins x 1 searches in 280 s (50 ms/origin, 4 threads); gzm r_peak: 5589 origins x 6 searches in 350 s (63 ms/origin, 4 threads).
- Oczekuje: nic.

