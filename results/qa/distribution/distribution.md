# Rozkład dostępu: kto ma jaki zasięg, nie tylko średnia miasta

Krok `pipeline.distribution` (2026-11-24). Rozkłady: środa 2026-11-25 (sobota 2026-11-28), OSM 2026-11-22, ludność: 2021-03-31 (NSP 2021, wzór GHSL 2020), siatka 250 m, wszystkie feedy. Nic nie jest liczone od nowa w routingu: krok czyta sumy z fazy 3 (`data/interim/access/`, `data/interim/access_uc/`) i wyniki fazy 2.

Pliki: `results/charts/distribution.json` (wszystko), `results/web/charts.json` (wycinek dla strony), `results/metrics/metrics_distribution.csv/.json` (wiersze jak w innych krokach), ten plik.

## 1. Co liczymy

- **Wartość komórki** to transport performance z fazy 3: ludność osiągalna w czasie T ÷ ludność w promieniu odpowiadającym 15 km/h (pieszo 5 km/h) × 100. Każdy mieszkaniec dostaje wartość swojej komórki 250 m.
- **Krzywa „co najmniej X”**: jaki odsetek mieszkańców ma wynik co najmniej X (X = 0, 1, …, 100). Krzywa zastępuje jeden arbitralny próg i pokazuje cały rozkład; liczona dla komunikacji (30 i 45 min, cztery pory), pieszo i rowerem w obu wariantach LTS (30 min).
- **Częstotliwość**: odsetek mieszkańców w zasięgu 500 m pieszo od kursów co najmniej co N min (N = 5, 10, 15, 20, 30). Dla rdzenia i obszaru pokrytego są to te same liczby co w `metrics_frequent` (udział punktów próbkowania komórki); dla centrum miejskiego – z klas komórek (klasa większości punktów).
- **Krzywa zasięgu 5–60 min**: stosunek średnich (jak DG REGIO) i pasmo kwartyli komórek ważonych ludnością (25., 50. i 75. percentyl; percentyl „dolny”: najmniejsza wartość, przy której skumulowany udział ludności osiąga q).
- **Minimalny zasięg** (próg) i wskaźniki Fostera–Greera–Thorbeckego: FGT0 = odsetek mieszkańców poniżej progu; FGT1 = średni niedobór do progu jako % progu, liczony na wszystkich mieszkańców (powyżej progu 0); FGT2 = to samo z kwadratem niedoboru (duże braki ważą więcej), × 100. Wskaźnik Palmy jako miara pomocnicza. Bez współczynnika Giniego (przegląd literatury, §21 raportu).
- **Obszary**: rdzeń (miasto w granicach administracyjnych; dla komunikacji tylko komórki w masce pokrycia GTFS, udział zachowanej ludności podany), obszar pokryty (komórki FUA w masce), centrum miejskie (urban centre, starty, cele i mianownik tylko w centrum, §17.5 raportu; tylko 30 i 45 min). Komórki poza maską to brak danych, nie zero, i nie wchodzą do rozkładów komunikacji.

## 2. Próg minimalnego zasięgu

**Reguła:** połowa mediany siedmiu miast. Mediana siedmiu miast to mediana z siedmiu median rdzeni (mediana komórek ważona ludnością, szczyt poranny), więc każde miasto liczy się raz, a Warszawa nie przeważa. Wynik zaokrąglony do pełnego punktu. Ten sam próg obowiązuje we wszystkich miastach, obszarach i porach dnia, więc odsetki poniżej progu można porównywać.

**Dlaczego tak.** To odpowiednik względnej granicy ubóstwa (50 % mediany dochodu w OECD; 40 % i 60 % jako warianty, 60 % w Eurostacie). Próg bezwzględny (np. „co najmniej 20 % okolicy w 30 min”) nie ma oparcia w literaturze dla tej miary, a próg względem mediany własnego miasta karałby miasta wyrównane i nie pozwalałby porównywać. Połowa mediany oznacza wynik, przy którym mieszkaniec osiąga w danym czasie najwyżej połowę tego, co typowy mieszkaniec rdzenia w typowym z siedmiu miast. To wybór normatywny, nie wynik badań; dlatego obok są dwa inne progi.

| Aglomeracja | Mediana rdzenia, 30 min, % | Mediana rdzenia, 45 min, % |
|---|---|---|
| Warszawa | 34,2 | 60,4 |
| Kraków | 33,0 | 54,9 |
| Wrocław | 27,6 | 56,6 |
| Poznań | 31,2 | 60,9 |
| Łódź | 28,4 | 53,9 |
| Trójmiasto | 32,4 | 55,5 |
| GZM | 20,8 | 35,7 |
| **mediana siedmiu miast** | **31,2** | **55,5** |

Progi: **30 min: 16 %** (40 % mediany: 12, 60 %: 19); **45 min: 28 %** (40 %: 22, 60 %: 33).

## 3. Wynik: mieszkańcy poniżej progu (szczyt poranny)

**30 min, próg 16 %.** FGT0 = odsetek mieszkańców poniżej progu, FGT1 i FGT2 × 100.

| Aglomeracja | Rdzeń: FGT0, % | Rdzeń: FGT1 | Rdzeń: FGT2 | Pokryty: FGT0, % | Pokryty: FGT1 | Pokryty: FGT2 | Centrum miejskie: FGT0, % |
|---|---|---|---|---|---|---|---|
| Warszawa | 9,4 | 3,83 | 2,29 | 26,9 | 14,04 | 9,22 | 7,6 |
| Kraków | 13,8 | 6,52 | 4,18 | 36,5 | 21,17 | 14,46 | 5,5 |
| Wrocław | 18,2 | 6,21 | 3,08 | 29,7 | 14,45 | 9,26 | 9,4 |
| Poznań | 19,8 | 8,62 | 4,88 | 37,9 | 18,16 | 10,97 | 14,8 |
| Łódź | 15,2 | 6,36 | 3,94 | 25,9 | 14,40 | 10,21 | 5,8 |
| Trójmiasto | 14,7 | 5,21 | 2,73 | 17,5 | 7,10 | 4,13 | 9,0 |
| GZM | 30,1 | 10,39 | 5,41 | 35,3 | 13,96 | 8,01 | 18,9 |

**45 min, próg 28 %.** FGT0 = odsetek mieszkańców poniżej progu, FGT1 i FGT2 × 100.

| Aglomeracja | Rdzeń: FGT0, % | Rdzeń: FGT1 | Rdzeń: FGT2 | Pokryty: FGT0, % | Pokryty: FGT1 | Pokryty: FGT2 | Centrum miejskie: FGT0, % |
|---|---|---|---|---|---|---|---|
| Warszawa | 6,4 | 2,42 | 1,50 | 26,5 | 15,03 | 10,81 | 4,2 |
| Kraków | 9,6 | 4,01 | 2,55 | 34,8 | 22,63 | 17,14 | 2,5 |
| Wrocław | 10,3 | 2,80 | 1,30 | 25,7 | 14,50 | 10,81 | 3,5 |
| Poznań | 11,4 | 4,12 | 2,37 | 40,6 | 20,53 | 13,44 | 7,2 |
| Łódź | 9,2 | 3,82 | 2,41 | 30,9 | 16,59 | 12,03 | 5,8 |
| Trójmiasto | 9,6 | 3,90 | 2,24 | 15,8 | 7,09 | 4,40 | 2,2 |
| GZM | 30,2 | 9,15 | 4,42 | 38,5 | 14,66 | 8,55 | 15,8 |

Jak czytać FGT1: wartość 5 oznacza, że gdyby rozdzielić brakujący zasięg po równo na wszystkich mieszkańców, każdemu brakowałoby 5 % progu. Wartości centrum miejskiego liczone są z innym mianownikiem (tylko centrum), a próg pochodzi z rdzeni; porównywać je można tylko między miastami, nie z rdzeniem.

## 4. Wrażliwość na próg

| Aglomeracja | Rdzeń 30 min: 12 / 16 / 19 | Pokryty 30 min | Rdzeń 45 min: 22 / 28 / 33 | Pokryty 45 min |
|---|---|---|---|---|
| Warszawa | 6,1 / 9,4 / 12,5 | 21,5 / 26,9 / 30,6 | 3,9 / 6,4 / 9,1 | 21,9 / 26,5 / 30,9 |
| Kraków | 10,3 / 13,8 / 17,9 | 31,5 / 36,5 / 40,4 | 6,3 / 9,6 / 14,3 | 31,0 / 34,8 / 39,4 |
| Wrocław | 10,2 / 18,2 / 23,1 | 21,6 / 29,7 / 34,1 | 4,8 / 10,3 / 15,8 | 20,0 / 25,7 / 30,6 |
| Poznań | 14,6 / 19,8 / 22,7 | 30,1 / 37,9 / 42,2 | 6,6 / 11,4 / 15,1 | 32,5 / 40,6 / 44,9 |
| Łódź | 9,8 / 15,2 / 23,5 | 20,6 / 25,9 / 32,8 | 5,9 / 9,2 / 12,4 | 23,8 / 30,9 / 35,2 |
| Trójmiasto | 9,0 / 14,7 / 19,4 | 11,6 / 17,5 / 22,3 | 6,7 / 9,6 / 12,5 | 11,9 / 15,8 / 19,4 |
| GZM | 17,1 / 30,1 / 42,1 | 22,2 / 35,3 / 46,9 | 16,8 / 30,2 / 42,6 | 24,5 / 38,5 / 50,9 |

- 30 min, rdzenie: korelacja rang kolejności miast między progiem 40 % a 50 % mediany 0,79, między 60 % a 50 % 0,86; najwięcej mieszkańców poniżej progu 50 %: GZM, Poznań.
- 45 min, rdzenie: korelacja rang kolejności miast między progiem 40 % a 50 % mediany 0,64, między 60 % a 50 % 0,96; najwięcej mieszkańców poniżej progu 50 %: GZM, Poznań.

## 5. Krzywa zasięgu 5–60 min (rdzeń, komunikacja, szczyt poranny)

Stosunek średnich, w nawiasie kwartyle komórek (25. / 50. / 75. percentyl), %.

| Aglomeracja | 15 min | 30 min | 45 min | 60 min |
|---|---|---|---|---|
| Warszawa | 14,8 (9,5 / 14,1 / 19,3) | 35,8 (25,3 / 34,2 / 42,1) | 61,6 (47,8 / 60,4 / 72,2) | 79,1 (71,2 / 82,3 / 89,0) |
| Kraków | 13,9 (8,0 / 12,5 / 18,2) | 33,3 (22,8 / 33,0 / 42,5) | 53,7 (41,9 / 54,9 / 64,5) | 72,0 (68,6 / 76,3 / 81,2) |
| Wrocław | 13,5 (9,0 / 13,3 / 17,9) | 29,7 (19,9 / 27,6 / 36,3) | 55,0 (39,5 / 56,6 / 68,2) | 71,2 (64,5 / 75,5 / 81,5) |
| Poznań | 12,9 (7,8 / 12,3 / 16,6) | 31,9 (20,3 / 31,2 / 40,3) | 55,9 (44,6 / 60,9 / 68,6) | 70,5 (67,3 / 74,2 / 78,4) |
| Łódź | 14,0 (8,2 / 13,7 / 19,2) | 28,6 (20,0 / 28,4 / 35,3) | 52,8 (42,9 / 53,9 / 64,2) | 71,3 (69,2 / 74,8 / 78,4) |
| Trójmiasto | 14,5 (9,4 / 14,2 / 20,0) | 32,6 (21,8 / 32,4 / 42,3) | 55,6 (42,4 / 55,5 / 71,5) | 76,0 (62,8 / 78,9 / 91,0) |
| GZM | 13,8 (8,1 / 12,7 / 19,1) | 22,4 (14,6 / 20,8 / 29,0) | 35,9 (25,8 / 35,7 / 46,9) | 51,1 (40,6 / 51,2 / 61,1) |

Wartości dla 5 i 10 min są w danych, ale nie należy ich czytać jako wyniku sieci: w tak krótkim czasie i promieniu (1,25 km dla 5 min) dużą część i licznika, i mianownika stanowi własna komórka mieszkańca, więc krzywa zaczyna się od ok. 10 % i bywa niemonotoniczna (np. pieszo wynik przy 5 min jest wyższy niż przy 10 min). Krzywą warto czytać od 15 min.

## 6. Pory dnia (rdzeń)

| Aglomeracja | Poniżej progu 16 %, 30 min: 7–9 / południe / wieczór / sobota | Poniżej progu 28 %, 45 min | Stosunek średnich, 30 min | Stosunek średnich, 45 min |
|---|---|---|---|---|
| Warszawa | 9,4 / 11,1 / 10,9 / 13,2 | 6,4 / 8,0 / 7,4 / 10,4 | 35,8 / 33,2 / 32,9 / 31,6 | 61,6 / 58,2 / 58,2 / 55,7 |
| Kraków | 13,8 / 15,8 / 17,4 / 19,2 | 9,6 / 11,9 / 11,6 / 14,9 | 33,3 / 31,7 / 31,2 / 29,6 | 53,7 / 51,5 / 52,6 / 49,1 |
| Wrocław | 18,2 / 19,4 / 20,0 / 21,3 | 10,3 / 10,1 / 9,3 / 11,5 | 29,7 / 28,8 / 30,2 / 28,6 | 55,0 / 54,1 / 56,9 / 54,2 |
| Poznań | 19,8 / 21,4 / 21,9 / 24,3 | 11,4 / 13,0 / 12,3 / 15,1 | 31,9 / 30,1 / 29,7 / 28,7 | 55,9 / 53,6 / 53,6 / 51,0 |
| Łódź | 15,2 / 15,9 / 16,9 / 19,3 | 9,2 / 10,4 / 10,6 / 12,9 | 28,6 / 28,1 / 27,1 / 25,7 | 52,8 / 51,8 / 50,5 / 47,9 |
| Trójmiasto | 14,7 / 16,7 / 20,2 / 18,0 | 9,6 / 9,4 / 14,2 / 11,7 | 32,6 / 31,0 / 27,7 / 28,7 | 55,6 / 53,1 / 47,2 / 48,8 |
| GZM | 30,1 / 35,4 / 45,9 / 47,0 | 30,2 / 35,4 / 48,4 / 50,4 | 22,4 / 21,1 / 18,7 / 18,6 | 35,9 / 33,5 / 29,0 / 28,4 |

Próg jest stały (z poranka), więc wzrost odsetka poza szczytem pokazuje, ilu mieszkańców spada poniżej minimum, gdy kursów jest mniej. Stosunek średnich różni się od tabeli §17.2 raportu o kilka dziesiątych punktu, bo tu rdzeń obejmuje tylko komórki w masce pokrycia.

## 7. Częstotliwość: odsetek mieszkańców z kursami co najmniej co N min (rdzeń)

| Aglomeracja | co ≤ 5 min, % | co ≤ 10 min, % | co ≤ 15 min, % | co ≤ 20 min, % | co ≤ 30 min, % | kontrola: z klas komórek (5 … 30) |
|---|---|---|---|---|---|---|
| Warszawa | 58,8 | 80,4 | 87,5 | 89,5 | 90,6 | 60,5 / 82,9 / 89,8 / 91,7 / 92,7 |
| Kraków | 44,0 | 66,0 | 72,4 | 83,1 | 85,0 | 45,1 / 68,1 / 74,7 / 86,2 / 88,2 |
| Wrocław | 51,4 | 75,8 | 81,1 | 83,2 | 86,0 | 53,2 / 78,6 / 83,8 / 86,0 / 88,8 |
| Poznań | 34,8 | 66,0 | 75,2 | 82,6 | 85,9 | 36,3 / 70,0 / 78,9 / 85,2 / 88,4 |
| Łódź | 35,0 | 69,6 | 73,0 | 82,2 | 87,5 | 36,0 / 72,6 / 75,9 / 84,5 / 90,1 |
| Trójmiasto | 25,3 | 59,2 | 71,7 | 79,5 | 81,6 | 26,7 / 62,3 / 74,9 / 82,5 / 84,6 |
| GZM | 10,1 | 45,6 | 59,2 | 67,7 | 75,4 | 10,4 / 47,0 / 61,0 / 69,7 / 77,8 |

Wartości z klas komórek są o 1–3 pkt wyższe, bo komórka dostaje klasę, w której leży co najmniej połowa jej punktów próbkowania, a metryka liczy udział punktów. Wykres na stronie używa liczb z `metrics_frequent`.

## 8. Wskaźnik Palmy (miara pomocnicza)

| Aglomeracja | Rdzeń 30 | Rdzeń 45 | Pokryty 30 | Pokryty 45 |
|---|---|---|---|---|
| Warszawa | 0,70 | 0,53 | 1,21 | 1,07 |
| Kraków | 0,72 | 0,57 | 1,66 | 1,54 |
| Wrocław | 0,77 | 0,56 | 1,11 | 0,95 |
| Poznań | 0,85 | 0,51 | 1,47 | 1,35 |
| Łódź | 0,67 | 0,54 | 1,20 | 1,07 |
| Trójmiasto | 0,82 | 0,68 | 0,92 | 0,78 |
| GZM | 1,23 | 0,70 | 1,35 | 0,85 |

Udział 10 % mieszkańców o najlepszym zasięgu w sumie wyników ÷ udział 40 % o najsłabszym. Przy równym rozkładzie 0,25. Miara zależy od tego, gdzie leżą granice obszaru, i nie jest wynikiem głównym.

## 9. Kontrole

- Średnia stosunków przeliczona tu z sum fazy 3 zgadza się z `metrics_access` / `metrics_access_uc` w 42 z 42 porównań (rdzeń i obszar pokryty: średnia stosunków 30 i 45 min; centrum miejskie: stosunek średnich; tolerancja 0,01 pkt + 0,1 %). Kontrola używa definicji z tamtych kroków (rdzeń z komórkami spoza maski); rozkłady w tym kroku pomijają komórki spoza maski.
- Pominięcie komórek rdzenia spoza maski podnosi średnią stosunków rdzenia o 0,13–1,15 pkt.
- Krzywe „co najmniej X” są nierosnące, a odsetek przy X = 0 wynosi 100 % (sprawdzane testami `pipeline/tests/test_distribution.py`, funkcje w `pipeline/distribution_stats.py`).

## 10. Co z tego wynika, czytane krytycznie

- **GZM** ma najwięcej mieszkańców rdzenia poniżej progu 30 min (30,1 %, Warszawa 9,4 %), a wieczorem i w sobotę odsetek rośnie do 45,9 i 47,0 %. Zgadza się to ze spadkami poza szczytem z §17.2 raportu, których przyczyny nie ustalono.
- **Górny ogon GZM to Tychy, nie lepsza obsługa.** 5,4 % mieszkańców rdzenia GZM ma wynik 30 min co najmniej 60 % (we Wrocławiu 0,5 %). Sprawdzone 2026-11-24 na sumach fazy 3: 99 % tych mieszkańców mieszka w prostokącie obejmującym Tychy (50,06–50,17° N, 18,88–19,06° E; prostokąt, nie granica gminy). W promieniu 7,5 km od tych komórek mieszka ok. 140 tys. osób (mediana), wobec ok. 270 tys. dla typowej komórki rdzenia GZM, więc mały mianownik daje wysoki stosunek. To cecha miary względnej, nie dowód lepszej sieci; prawdopodobnie podnosi też wskaźnik Palmy GZM (najwyższy z rdzeni), czego osobno nie sprawdzano.
- **Warszawa** ma najmniej mieszkańców rdzenia poniżej progu, także poza szczytem; jej pasmo kwartyli przy 30 min (25,3–42,1) jest przesunięte w górę, nie węższe niż w innych miastach.
- **Obszar pokryty** ma wszędzie więcej mieszkańców poniżej progu niż rdzeń; przy 30 min najwięcej Poznań (37,9 %) i Kraków (36,5 %). Najmniejsza różnica rdzeń–obszar pokryty: Trójmiasto (2,9 pkt); tam rdzeń i obszar pokryty mają też prawie ten sam wynik średni (§17.1).
- **Wybór progu.** Przy każdym z trzech progów najgorzej wypada GZM, ale kolejność środka tabeli się zmienia (korelacja rang z progiem głównym 0,64–0,96, §4), a poziomy zależą od progu wyraźnie: przy 30 min między progiem 12 a 19 % odsetek rośnie o ponad 10 pkt w: Wrocław, Łódź, Trójmiasto, GZM. Odsetek poniżej progu nadaje się do pokazania, gdzie jest problem, nie do rankingu miast o zbliżonych wartościach.

## 11. Ograniczenia

- Próg jest normatywny i względny: przesuwa się, gdy zmienią się mediany miast. Nie mówi, jaki zasięg jest „wystarczający” dla konkretnej potrzeby.
- Jednostką jest komórka 250 m, nie osoba: wszyscy mieszkańcy komórki dostają tę samą wartość, więc rozkład jest węższy niż rozkład podróży rzeczywistych osób.
- Brak cech społeczno-ekonomicznych: to rozkład przestrzenny, nie rozkład według grup ludności (§16.3 raportu).
- Wszystkie zastrzeżenia fazy 3: rozkład jazdy zamiast rzeczywistości (5–15 % zawyżenia w literaturze), wybór siatki ludności (3–7 pkt), granice obszaru (§16.2, §17.8). Wariantu z surowym GHSL tu nie liczono.
- Centrum miejskie: tylko 30 i 45 min, bez pór dnia i bez krzywej 5–60 min (pamięć podręczna `access_uc` ma mianownik tylko dla tych dwóch progów).
- Krzywa częstotliwości dla rdzenia i obszaru pokrytego ma tylko pięć punktów (progi fazy 2), więc na wykresie jest schodkowa.

## 12. Rozmiary plików

| Plik | kB |
|---|---|
| charts/distribution.json | 483,8 |
| metrics/metrics_distribution.csv | 301,2 |
| metrics/metrics_distribution.json | 439,7 |
| web/charts.json | 206,7 |

Wierszy metryk: 504 (w tym `main`: 14).
