# Transport performance w centrach miejskich (urban centres), 7 aglomeracji

Plik generuje `python -m pipeline.access_uc aggregate`. Wyniki: `results/metrics/metrics_access_uc.csv/json`, domena `urban_centre`.

## 1. Po co i jak

Wyniki produkcyjne liczone są dla rdzenia (granice miasta) i FUA, a te obszary mają w różnych miastach bardzo różną wielkość i zabudowę. Tu wszystkie miasta porównujemy na tym samym rodzaju obszaru: **centrum miejskim** (urban centre) w definicji Eurostatu, czyli zwartym skupisku komórek 1 km² o gęstości ≥ 1500 os./km² i ≥ 50 tys. mieszkańców. Warstwa: **Eurostat GISCO `HDENS_CLST_2021`**, wydana 2024-11-19, zbudowana na siatce spisowej 2021 (oficjalna, aktualna ludność); warstwa 2011 służy tylko do benchmarku DG REGIO (`results/qa/access/dgregio/`).

- **Domena:** suma wszystkich centrów, których ponad połowa komórek 1 km leży w FUA aglomeracji; starty, cele i mianownik (proximity) tylko w tej domenie. Komórka 250 m należy do domeny, gdy jej środek leży w komórce 1 km centrum i w FUA. Gdzie centrów jest kilka (Warszawa, Łódź, Trójmiasto, GZM), liczymy je łącznie jako jeden obszar; **DG REGIO traktuje każde centrum jako osobne miasto**, więc dla tych aglomeracji wyniki nie są wprost porównywalne z ich metodą.
- **Metoda produkcyjna** (`access.md` §1), zmienia się tylko domena: R5 v7.5.1, środa 2026-11-25, odjazdy co minutę 7:00–9:00, mediana, dojście i odejście ≤ 1 km, pieszo 5 km/h, reguła min(komunikacja, sam spacer), wszystkie feedy, siatka 250 m przeskalowana do NSP 2021; rower 15 km/h, LTS ≤ 3 i ≤ 4. Czasy spaceru z produkcyjnej pamięci spacerów; komunikacja i rower policzone osobno na kopiach sieci produkcyjnych, na pełnym zbiorze komórek każdego centrum (bez próbkowania).
- **Agregacja:** średnia stosunków komórek ważona ludnością (wynik główny) i stosunek średnich (wariant tabelaryczny).
- **Pokrycie GTFS:** udział ludności domeny w masce pokrycia fazy 2 (wariant „wszystkie”); poniżej 85 % wynik dostaje flagę „niepełne pokrycie GTFS”. Wynik miasta obejmuje wszystkie komórki domeny (jak wiersze FUA i rdzenia w `metrics_access`); warstwy komórek tu nie ma.

## 2. Centra miejskie w aglomeracjach

| Aglomeracja | Centrum (gmina z największą liczbą komórek) | Ludność 2021 (Eurostat) | Komórek 1 km | W FUA | W domenie | Gminy (liczba komórek) |
|---|---|---|---|---|---|---|
| Warszawa | Warszawa | 1 821 750 | 327 | 327 | tak | Warszawa 277; Marki 14; Pruszków 14; Ząbki 8; Piastów 6; Michałowice 6; Stare Babice 2 |
| Warszawa | Warszawa | 71 711 | 11 | 11 | tak | Warszawa 11 |
| Warszawa | Legionowo | 55 930 | 17 | 17 | tak | Legionowo 12; Jabłonna 5 |
| Warszawa | Kobyłka | 53 548 | 17 | 17 | tak | Kobyłka 10; Wołomin 7 |
| Kraków | Kraków | 706 924 | 132 | 132 | tak | Kraków 130; Zielonki 2 |
| Wrocław | Wrocław | 573 339 | 126 | 126 | tak | Wrocław 125; Kobierzyce 1 |
| Poznań | Poznań | 535 302 | 131 | 131 | tak | Poznań 114; Luboń 9; Suchy Las 4; Komorniki 3; Dopiewo 1 |
| Łódź | Łódź | 601 217 | 111 | 111 | tak | Łódź 111 |
| Łódź | Pabianice | 52 900 | 11 | 11 | tak | Pabianice 11 |
| Trójmiasto | Gdańsk | 449 978 | 100 | 98 | tak | Gdańsk 90; Sopot 6; Kolbudy 1; Pruszcz Gdański 1 |
| Trójmiasto | Gdynia | 125 048 | 30 | 29 | tak | Gdynia 29 |
| GZM | Katowice | 1 079 190 | 299 | 299 | tak | Katowice 70; Sosnowiec 39; Ruda Śląska 35; Bytom 30; Zabrze 27; Chorzów 27; Siemianowice Śląskie 17; Dąbrowa Górnicza 15; Czeladź 13; Świętochłowice 13; Będzin 11; Gliwice 2 |
| GZM | Gliwice | 111 455 | 25 | 25 | tak | Gliwice 25 |
| GZM | Tychy | 106 888 | 20 | 20 | tak | Tychy 20 |
| GZM | Mysłowice | 62 950 | 17 | 17 | tak | Mysłowice 10; Sosnowiec 5; Katowice 2 |

## 3. Wyniki: rdzeń (produkcja) i centrum miejskie

Średnia stosunków komórek (wynik główny). „Rdzeń” to wynik produkcyjny z `metrics_access` (starty w mieście, cele i mianownik w FUA + 15 km).

| Aglomeracja | Pow. km² | Ludność (NSP 2021, 250 m) | Ludność miasta (rdzenia) poza UC | Pokrycie GTFS | KZ 30: rdzeń → UC | KZ 45: rdzeń → UC | Pieszo 30: rdzeń → UC | Rower LTS 3: rdzeń → UC | Rower LTS 4: rdzeń → UC |
|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 372 | 1 997 146 | 8,6 % | 93,4 % | 33,9 → 37,1 | 58,8 → 62,8 | 66,4 → 68,7 | 45,2 → 50,0 | 52,4 → 56,3 |
| Kraków | 132 | 703 352 | 11,7 % | 96,4 % | 31,6 → 36,2 | 52,8 → 63,7 | 64,8 → 68,2 | 48,5 → 55,7 | 53,4 → 59,6 |
| Wrocław | 126 | 571 432 | 15,6 % | 97,4 % | 27,6 → 31,9 | 53,0 → 64,8 | 65,4 → 66,8 | 58,5 → 66,4 | 70,2 → 76,0 |
| Poznań | 131 | 534 162 | 10,6 % | 95,4 % | 30,0 → 33,5 | 54,6 → 65,9 | 64,9 → 67,6 | 61,8 → 67,5 | 69,6 → 73,4 |
| Łódź | 122 | 651 330 | 10,2 % | 97,8 % | 26,9 → 35,5 | 51,3 → 60,3 | 69,0 → 72,9 | 53,7 → 61,8 | 64,8 → 70,3 |
| Trójmiasto | 127 | 569 743 | 24,9 % | 97,6 % | 31,8 → 41,2 | 55,4 → 71,5 | 69,1 → 71,1 | 50,4 → 63,1 | 65,5 → 74,8 |
| GZM | 361 | 1 355 317 | 19,5 % | 98,8 % | 23,8 → 30,6 | 36,1 → 46,5 | 67,1 → 69,2 | 45,3 → 54,3 | 60,9 → 66,3 |

Stosunek średnich (wariant tabelaryczny):

| Aglomeracja | KZ 30: rdzeń → UC | KZ 45: rdzeń → UC | Pieszo 30: rdzeń → UC | Rower LTS 3: rdzeń → UC | Rower LTS 4: rdzeń → UC |
|---|---|---|---|---|---|
| Warszawa | 35,7 → 37,3 | 61,4 → 65,1 | 67,5 → 68,4 | 45,3 → 47,1 | 52,3 → 53,8 |
| Kraków | 33,0 → 36,7 | 54,2 → 64,4 | 67,7 → 69,2 | 51,1 → 56,8 | 55,7 → 60,7 |
| Wrocław | 29,4 → 33,4 | 54,5 → 65,7 | 67,7 → 68,6 | 62,0 → 68,4 | 72,8 → 77,8 |
| Poznań | 31,7 → 35,5 | 55,6 → 67,0 | 66,9 → 67,9 | 64,0 → 69,2 | 71,2 → 74,9 |
| Łódź | 28,3 → 32,4 | 52,1 → 61,7 | 70,1 → 71,6 | 55,9 → 60,6 | 66,2 → 69,4 |
| Trójmiasto | 32,0 → 37,1 | 54,5 → 66,7 | 69,4 → 70,6 | 53,1 → 63,1 | 67,3 → 74,3 |
| GZM | 22,3 → 26,0 | 35,8 → 43,2 | 68,4 → 69,7 | 44,5 → 50,2 | 59,7 → 62,8 |

## 4. Co zmienia się w kolejności miast

- **KZ 30.** Rdzeń: Warszawa 33,9 > Trójmiasto 31,8 > Kraków 31,6 > Poznań 30,0 > Wrocław 27,6 > Łódź 26,9 > GZM 23,8. Centrum miejskie: Trójmiasto 41,2 > Warszawa 37,1 > Kraków 36,2 > Łódź 35,5 > Poznań 33,5 > Wrocław 31,9 > GZM 30,6.
- **KZ 45.** Rdzeń: Warszawa 58,8 > Trójmiasto 55,4 > Poznań 54,6 > Wrocław 53,0 > Kraków 52,8 > Łódź 51,3 > GZM 36,1. Centrum miejskie: Trójmiasto 71,5 > Poznań 65,9 > Wrocław 64,8 > Kraków 63,7 > Warszawa 62,8 > Łódź 60,3 > GZM 46,5.
- **Pieszo 30.** Rdzeń: Trójmiasto 69,1 > Łódź 69,0 > GZM 67,1 > Warszawa 66,4 > Wrocław 65,4 > Poznań 64,9 > Kraków 64,8. Centrum miejskie: Łódź 72,9 > Trójmiasto 71,1 > GZM 69,2 > Warszawa 68,7 > Kraków 68,2 > Poznań 67,6 > Wrocław 66,8.
- **Rower LTS 4.** Rdzeń: Wrocław 70,2 > Poznań 69,6 > Trójmiasto 65,5 > Łódź 64,8 > GZM 60,9 > Kraków 53,4 > Warszawa 52,4. Centrum miejskie: Wrocław 76,0 > Trójmiasto 74,8 > Poznań 73,4 > Łódź 70,3 > GZM 66,3 > Kraków 59,6 > Warszawa 56,3.
- Zmiany miejsc, KZ 30 (rdzeń → centrum): Warszawa 1 → 2; Wrocław 5 → 6; Poznań 4 → 5; Łódź 6 → 4; Trójmiasto 2 → 1.
- Zmiany miejsc, KZ 45 (rdzeń → centrum): Warszawa 1 → 5; Kraków 5 → 4; Wrocław 4 → 3; Poznań 3 → 2; Trójmiasto 2 → 1.
- Zmiany miejsc, Pieszo 30 (rdzeń → centrum): Kraków 7 → 5; Wrocław 5 → 7; Łódź 2 → 1; Trójmiasto 1 → 2.
- Zmiany miejsc, Rower LTS 4 (rdzeń → centrum): Poznań 2 → 3; Trójmiasto 3 → 2.

## 5. Stan i zastrzeżenia

- Oczekuje (routing niedokończony, brak wierszy): nic.
- Czasy routingu (6 wątków, `-Xmx 8G`, jedna JVM, równolegle z produkcyjnym `pipeline.access run`): warszawa pt_am: 5797 origins in 344 s (59 ms/origin, 6 threads); krakow pt_am: 2069 origins in 67 s (32 ms/origin, 6 threads); wroclaw pt_am: 1962 origins in 36 s (19 ms/origin, 6 threads); poznan pt_am: 2039 origins in 35 s (17 ms/origin, 6 threads); lodz pt_am: 1936 origins in 42 s (22 ms/origin, 6 threads); trojmiasto pt_am: 1936 origins in 36 s (19 ms/origin, 6 threads); gzm pt_am: 5589 origins in 193 s (35 ms/origin, 6 threads); warszawa bike_lts4: 5797 origins in 950 s (164 ms/origin, 6 threads); krakow bike_lts4: 2069 origins in 226 s (109 ms/origin, 6 threads); wroclaw bike_lts4: 1962 origins in 261 s (133 ms/origin, 6 threads); poznan bike_lts4: 2039 origins in 255 s (125 ms/origin, 6 threads); lodz bike_lts4: 1936 origins in 259 s (134 ms/origin, 6 threads); trojmiasto bike_lts4: 1936 origins in 176 s (91 ms/origin, 6 threads); gzm bike_lts4: 5589 origins in 486 s (87 ms/origin, 6 threads); warszawa bike_lts3: 5797 origins in 874 s (151 ms/origin, 6 threads); krakow bike_lts3: 2069 origins in 232 s (112 ms/origin, 6 threads); wroclaw bike_lts3: 1962 origins in 226 s (115 ms/origin, 6 threads); poznan bike_lts3: 2039 origins in 210 s (103 ms/origin, 6 threads); lodz bike_lts3: 1936 origins in 218 s (113 ms/origin, 6 threads); trojmiasto bike_lts3: 1936 origins in 148 s (77 ms/origin, 6 threads); gzm bike_lts3: 5589 origins in 292 s (52 ms/origin, 6 threads).
- Wielkość domeny nadal się różni: Warszawa 372 km², GZM 361 km² wobec 122–132 km² w pozostałych miastach. W małym, zwartym centrum promień 11,25 km obejmuje prawie całą jego ludność, więc KZ 45 zbliża się tam do „odsetka całego centrum osiągalnego w 45 min” i jest wyższy niż w dużym centrum przy tej samej jakości komunikacji; porównania KZ 45 między dużymi i małymi centrami czytać ostrożnie (benchmark DG REGIO, §6).
- Centra wielobiegunowe są łączone w jedną domenę; podróże między nimi (np. Gdańsk–Gdynia, Katowice–Gliwice) liczą się do wyniku, jeśli mieszczą się w progu, a mianownik obejmuje tylko ludność centrów.
- Trójmiasto: centrum Gdańsk ma 2 z 100 komórek 1 km poza FUA; te komórki nie są używane.
- Trójmiasto: centrum Gdynia ma 1 z 30 komórek 1 km poza FUA; te komórki nie są używane.
- Centra tylko częściowo w FUA (≤ połowa komórek) i pominięte: brak.
- Pokrycie GTFS liczone na masce fazy 2; braki przewoźników po stronie celów obniżają wynik także wewnątrz maski.

