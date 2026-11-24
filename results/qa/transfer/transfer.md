# Łatwość przesiadki w zespołach przystanków (warstwa dodatkowa, 2026-11-24)

Warstwa dodatkowa zatwierdzona przez właściciela 2026-11-24 (RAPORT §12.2). Opisuje, jak łatwo przesiąść się między liniami w zespole przystanków: ile trzeba przejść, przez ile jezdni, czy po schodach, ile średnio czekać na linię docelową i jak ważny jest węzeł. **Składowe są publikowane obok siebie i nie są łączone w jedną ocenę.**

Punkt odniesienia z literatury, nie specyfikacja: prace o „karze za przesiadkę” rozkładają koszt przesiadki na dojście, czekanie i resztę zależną od stacji i rodzaju ruchu (Guo i Wilson 2011, metro londyńskie; Iseki i Taylor, Transport Reviews, „Not all transfers are created equal”). Polska metoda AMPTI (Olszewski, Krukowska, Krukowski, TMiR 6/2014; stosowana w wytycznych ZTM Warszawa i w ocenach węzłów Krakowa) ocenia węzły wskaźnikami ilościowymi, ale część z nich (stan peronów, informacja, oświetlenie, monitoring, widoczność przystanków) wymaga audytu w terenie. **Ta warstwa to wariant własny, ograniczony do tego, co dają rozkłady i OpenStreetMap. Nie jest oceną AMPTI ani wskaźnikiem kary za przesiadkę** i nie nosi nazwy żadnej z tych metod.

Wszystkie czasy dojścia są z sieci pieszej OSM przy 5 km/h, bez czasu na światłach, schodach i w tłumie; czekanie jest rozkładowe, w pełnych minutach. Wynik nie mówi nic o punktualności, zatłoczeniu ani informacji dla pasażerów.

## 1. Dane i daty

- Rozkłady: środa 2026-11-25, wszystkie feedy (wariant „all”), kursy po regułach `pipeline/gtfs_service.py` (deduplikacja, przycięcie kolei).
- Sieć piesza: OSM 2026-11-22, graf z `pipeline/walk_network.py`; tagi przejść, sygnalizacji, tuneli i kładek z tego samego pliku PBF (`pipeline/transfer_osm.py`, jedno przejście, wynik w `data/interim/transfer/`).
- Zespoły przystanków bazują na klastrach 100 m z kroku częstej komunikacji (`frequent.clusters`).
- Maska pokrycia GTFS: `results/layers/gtfs_coverage_mask.parquet`, wariant „all”. Zespół poza maską ma wszystkie składowe puste (brak danych), nigdy 0.
- Ludność nie jest używana; pola daty ludności w metrykach są puste.

## 2. Reguły (wszystkie ustalone w tym kroku)

1. **Zespół przystanków do przesiadki.** Klastry 100 m łączone, gdy najbliższe słupki dwóch klastrów są ≤ 150 m od siebie w linii prostej (≤ 250 m, jeśli jeden z klastrów ma odjazdy kolei lub metra). Grupa szersza niż 400 m (z koleją lub metrem: 600 m) między środkami klastrów jest dzielona metodą pełnego wiązania, więc zespół nie rozciąga się łańcuchem wzdłuż ulicy.
   Dlaczego tak: klastry 100 m z kroku częstej komunikacji łączą tylko słupki tej samej ulicy i skrzyżowania; przystanki tramwaju, autobusu i wejścia na stację bywają 200–300 m od siebie (sprawdzone niżej na znanych węzłach). Próg 150 m łączy przystanki po przekątnej dużego skrzyżowania, 250 m dla kolei i metra łączy stację (w GTFS jeden punkt) z przystankami przed nią. Ograniczenie rozpiętości (pełne wiązanie) zapobiega łańcuchom w gęstym śródmieściu: bez niego cała oś Marszałkowskiej byłaby jednym zespołem. Nazwy przystanków nie są używane, bo w GTFS ten sam węzeł ma różne nazwy w różnych feedach (np. „DWORZEC GŁÓWNY” i „Wrocław Główny”).
2. **Linia.** Feed + rodzaj środka + `route_short_name`. W feedzie kolejowym, gdzie `route_short_name` jest kategorią pociągu bez numeru (IC, TLK, EIP, ...), linią jest para stacji końcowych kursu. Linia liczy się w zespole, jeśli ma tam co najmniej 7 odjazdów (do wsiadania) albo przyjazdów (do wysiadania) w oknie 6–20, czyli średnio co najmniej jeden na 2 godziny.
3. **Para przesiadkowa.** Uporządkowana para (A przyjeżdża, B odjeżdża), A ≠ B. Pomijane są pary linii „równoległych”: jeśli co najmniej 80 % zespołów przystanków krótszej z nich (cały dzień) obsługuje też druga linia (warianty tej samej linii, kursy skrócone, linie o prawie wspólnej trasie).
4. **Dojście.** Dla każdej pary najlepsza para słupków (wysiadanie z A, wsiadanie do B) wg najkrótszej drogi po sieci pieszej OSM; 5 km/h, bez kary za przejścia i schody. Przystanki przypięte do najbliższej krawędzi sieci (do 150 m, stacje do 300 m), tak jak w kroku częstej komunikacji. Ten sam słupek = 0 min. Współczynnik wydłużenia = droga po sieci / odległość w linii prostej (tylko pary oddalone o ≥ 30 m). Mediana i 90. percentyl po parach.
   **Dojście z kierunkami (wariant dodany w tym kroku, podstawa miar głównych).** Najlepsza para słupków zwykle trafia na wspólny słupek dwóch linii jadących dalej tą samą ulicą, więc mediana wychodzi bliska 0 prawie wszędzie i nie różnicuje węzłów. Wariant z kierunkami bierze każdy główny kierunek przyjazdu A (poprzedni zespół na trasie, ≥ 20 % przyjazdów) i każdy główny kierunek odjazdu B (następny zespół); ruch jest pomijany, gdy B odjeżdża tam, dokąd A i tak jedzie dalej (przesiadka zbędna), albo wraca tam, skąd A przyjechała. Dla każdego ruchu najlepsza para słupków tego kierunku; wartość pary linii = średnia po ruchach (pasażer potrzebuje któregoś kierunku, nie wiadomo którego). Przejścia, schody i dojście bez schodów liczone tak samo po ruchach.
5. **Przeszkody na dojściu.** Przejście przez jezdnię lub torowisko: węzeł ścieżki leżący na jezdni (drogi od `residential` wzwyż, bez `service`) lub na torach tramwaju albo kolei, w którym ścieżka przecina, a nie biegnie wzdłuż (obie sąsiednie krawędzie ścieżki nie są jezdnią), albo węzeł z tagiem przejścia. Zdarzenia bliżej niż 40 m od siebie to jedno przejście (dwie jezdnie i torowisko). Sygnalizacja: `crossing=traffic_signals`, `crossing:signals=yes`, `highway=traffic_signals` na węźle lub ta sama wartość na drodze `footway=crossing`. Schody: `highway=steps` i schody ruchome; tunel: droga piesza z `tunnel=*` (bez `building_passage`); kładka: droga piesza z `bridge=*`, która nie jest jezdnią (chodnik zmapowany osobno na moście drogowym też się liczy). Dojście bez schodów: najkrótsza droga w sieci bez schodów (windy zmapowane jako węzeł przechodzą).
6. **Czekanie.** Oczekiwane czekanie na linię B dla pasażera przychodzącego w losowej chwili okna (7–9 i 6–20), z rzeczywistych godzin odjazdów B w zespole (próbkowanie co 30 s; czekanie obcięte do 60 min), osobno dla każdego kierunku (następny zespół na trasie) i uśrednione po głównych kierunkach B (≥ 20 % jej odjazdów). Przy kursach równomiernych to połowa odstępu; nieregularność je wydłuża. Rozkłady podają pełne minuty i nie mają czasu postoju, więc to nie jest precyzja skomunikowania co do minuty. Dojście + czekanie: suma dla pary, potem mediana po parach; obok mediana ważona liczbą kursów (przyjazdy A × odjazdy B), bo rzadkie linie liczą się w zwykłej medianie tak samo jak częste.
7. **Znaczenie węzła.** Linie, pary, odjazdy na godzinę (wszystkie linie, 6–20 i 7–9).
8. **Kolej i metro.** Stacje kolei mają w feedzie ogólnopolskim jeden punkt na wszystkie stanowiska (np. Wrocław Główny: 10 `stop_id` w jednym punkcie), więc położenie peronów nie jest znane. Przesiadka kolej–kolej na takiej stacji ma dojście „brak danych” (kolumna `n_pairs_platform_unknown`), czekanie jest liczone. Przesiadka kolej–tramwaj lub kolej–autobus to dojście do punktu stacji (zwykle budynek lub środek peronów; przypięcie do sieci do 300 m), nie do konkretnego peronu: dla dużych stacji to dolna granica rzeczywistego dojścia o nieznanej wielkości. Metro warszawskie ma osobne punkty peronów, ale ich wejścia i poziomy są w OSM tak dokładne, jak je zmapowano.
9. **Możliwe skomunikowania (przybliżone).** Dla linii docelowej kursującej średnio co ≥ 15 min (6–20, na wybranym słupku) porównano rzeczywiste czekanie pasażerów linii A (po dojściu) z tym samym czekaniem przy rozkładzie A przesuniętym o 1, 2, …, h−1 min. Para jest kandydatem, gdy rzeczywisty rozkład daje czekanie krótsze niż co najmniej 90 % przesunięć i najwyżej połowę czekania przy losowym przyjściu. Bez koordynacji ok. 10 % par mieści się w najlepszych 10 % przesunięć przypadkiem, więc pojedynczy kandydat nie dowodzi skomunikowania; liczy się nadwyżka ponad 10 % w skali miasta. Nie rozpoznaje się kursów przechodzących (ten sam pojazd zmienia numer linii), które wyglądają jak idealne skomunikowanie.

## 3. Wyniki dla miast (reguła główna)

„Łatwe” = mediana dojścia między liniami ≤ 2 min; udział liczony po odjazdach 6–20 wszystkich zespołów przesiadkowych w obszarze. „Top 20” = 20 zespołów z największą liczbą odjazdów w obszarze; wartość = mediana median węzłów. Obszar pokryty = zespoły w FUA i w masce GTFS.

| Aglomeracja | Obszar | Zespoły | Odjazdy w zespołach „łatwych”, % | Odjazdy w zespołach z dojściem > 5 min, % | Top 20: dojście, min | Top 20: przejścia | Top 20: czekanie 7–9, min | Top 20: dojście + czekanie 7–9, min | Top 20: to samo, najlepsza para, ważone kursami, min | Top 20: pary bez schodów, % | Najlepsza para słupków: odjazdy w zespołach „łatwych”, % | Najlepsza para: top 20 dojście, min | Pary na tym samym słupku, % | Odjazdy zespołów w masce, % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | rdzeń | 1134 | 61,0 | 1,5 | 2,3 | 1,0 | 5,3 | 8,2 | 5,7 | 92 | 90,8 | 1,4 | 52 | 98,7 |
|  | pokryty | 2181 | 64,2 | 1,3 | 2,3 | 1,0 | 5,3 | 8,2 | 5,7 | 92 | 91,6 | 1,4 | 56 | 95,9 |
| Kraków | rdzeń | 538 | 74,1 | 0,4 | 2,0 | 1,0 | 7,6 | 9,8 | 7,5 | 100 | 96,9 | 0,4 | 44 | 95,8 |
|  | pokryty | 947 | 74,5 | 0,6 | 2,0 | 1,0 | 7,6 | 9,8 | 7,5 | 100 | 96,8 | 0,4 | 44 | 93,9 |
| Wrocław | rdzeń | 487 | 82,7 | 2,1 | 1,6 | 1,0 | 7,4 | 8,8 | 7,3 | 86 | 94,9 | 0,5 | 55 | 99,2 |
|  | pokryty | 579 | 82,8 | 2,1 | 1,6 | 1,0 | 7,4 | 8,8 | 7,3 | 86 | 94,9 | 0,5 | 56 | 98,0 |
| Poznań | rdzeń | 422 | 78,6 | 0,2 | 1,6 | 1,0 | 5,2 | 8,8 | 5,5 | 97 | 97,5 | 0,0 | 63 | 97,6 |
|  | pokryty | 786 | 79,2 | 0,6 | 1,6 | 1,0 | 5,2 | 8,8 | 5,5 | 97 | 96,8 | 0,0 | 68 | 95,6 |
| Łódź | rdzeń | 437 | 75,1 | 0,3 | 2,0 | 1,0 | 7,6 | 10,4 | 8,5 | 98 | 97,8 | 0,8 | 55 | 97,8 |
|  | pokryty | 647 | 75,7 | 0,2 | 2,0 | 1,0 | 7,6 | 10,4 | 8,5 | 98 | 97,7 | 0,8 | 53 | 96,4 |
| Trójmiasto | rdzeń | 566 | 61,1 | 3,3 | 2,7 | 1,0 | 10,7 | 13,0 | 10,2 | 90 | 92,9 | 0,5 | 57 | 98,0 |
|  | pokryty | 733 | 61,9 | 3,4 | 2,7 | 1,0 | 10,7 | 13,0 | 10,2 | 90 | 92,3 | 0,5 | 57 | 97,0 |
| GZM | rdzeń | 1478 | 81,9 | 1,1 | 1,5 | 0,5 | 15,0 | 17,3 | 15,0 | 92 | 97,0 | 0,2 | 72 | 97,5 |
|  | pokryty | 1961 | 83,1 | 1,0 | 1,5 | 0,5 | 15,0 | 17,3 | 15,0 | 92 | 97,2 | 0,2 | 73 | 96,8 |

**Czytanie krytyczne.**

- **Najlepsza para słupków nie różnicuje miast.** W wariancie zgodnym z zadaniem (najlepsza para słupków dla każdej pary linii, bez kierunków) 91–98 % odjazdów przypada na zespoły z medianą dojścia ≤ 2 min, a mediana dla 20 największych węzłów to 0,0–1,4 min. Powód sprawdzono w danych: 44–73 % par linii ma najlepszą parę na tym samym słupku, bo linie jadą wspólnym odcinkiem; przesiadka w tym samym kierunku jest wtedy możliwa, ale zwykle niepotrzebna. Dlatego miary główne korzystają z wariantu z kierunkami (reguła 4); wariant najlepszej pary jest w tabelach i w warstwie.
- **Czekanie decyduje bardziej niż dojście.** W 20 największych węzłach mediana dojścia z kierunkami to 1,5–2,7 min, a oczekiwane czekanie 7–9 to 5,2 min (Poznań) do 15,0 min (GZM). GZM ma najkrótsze dojścia (1,5 min) i najdłuższe czekanie; zgadza się to z §15.2 raportu (linie GZM kursują rzadko i rozchodzą się na węzłach).
- **Mediana zwykła a ważona.** Mediana po parach linii traktuje rzadką linię podmiejską tak samo jak tramwaj co 5 min. Mediana ważona liczbą kursów jest zwykle niższa, o 0–8 min (np. Kraków Główny: 17,3 min zwykła wobec 9,3 ważonej przy najlepszej parze). Obie są w warstwie; do porównań węzłów o różnym udziale kolei bezpieczniej czytać ważoną.
- **Warszawa i Trójmiasto mają najmniej odjazdów w zespołach „łatwych” (ok. 61–64 %).** Sprawdzono: w obu duże węzły to kompleksy wielopoziomowe (metro, SKM, dworce), gdzie dojście z kierunkami wynosi 2,3–3,8 min (Centrum 3,7; Dworzec Gdański 3,8; Gdańsk Główny 2,9; Gdynia Główna 2,9). Wynik zostaje.
- **Przejścia przez jezdnię.** Mediana 1 przejście na ruch w 20 największych węzłach wszystkich miast poza GZM (0,5). Przy najlepszej parze mediana wynosi 0, bo wspólny słupek nie wymaga przejścia.

## 4. Znane węzły: kontrola

Dla każdego węzła wybrano zespół o największej liczbie odjazdów, którego nazwy pasują do wzorca i którego środek leży ≤ 600 m od punktu orientacyjnego (`transfer_report.KNOWN`). Wszystkie kolumny: `known_interchanges.csv`; pary linii: `pairs_known_interchanges.csv`.

| Miasto | Węzeł | Zespół (nazwa wiodąca) | Słupki | Rozpiętość, m | Środki | Linie | Pary | Odjazdy/h 6–20 | Dojście, najlepsza para: mediana, min | Dojście z kierunkami: mediana, min | Dojście z kierunkami: P90, min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | Centrum | Centrum | 13 | 388 | bus, metro, rail, tram | 29 | 804 | 313 | 1,8 | 3,6 | 4,3 |
| Warszawa | Dworzec Centralny | Dw. Centralny | 27 | 427 | bus, rail, tram | 39 | 1382 | 282 | 1,8 | 2,7 | 3,9 |
| Warszawa | Dworzec Wileński | Dw. Wileński | 10 | 337 | bus, metro, tram | 21 | 416 | 237 | 1,1 | 2,4 | 2,9 |
| Warszawa | Dworzec Gdański | Dw. Gdański | 22 | 585 | bus, metro, rail, tram | 16 | 219 | 161 | 2,7 | 3,8 | 6,2 |
| Kraków | Rondo Mogilskie | Rondo Mogilskie | 18 | 273 | bus, tram | 20 | 378 | 181 | 1,3 | 2,5 | 3,6 |
| Kraków | Dworzec Główny Zachód (Basztowa, Pawia) | Dworzec Główny Zachód | 6 | 153 | bus, tram | 9 | 70 | 52 | 1,5 | 1,7 | 1,8 |
| Kraków | Kraków Główny (kolej) | Kraków Główny | 27 | 532 | bus, rail, tram | 28 | 581 | 113 | 1,8 | 2,3 | 5,2 |
| Kraków | Rondo Grunwaldzkie | Rondo Grunwaldzkie | 13 | 250 | bus, tram | 33 | 1046 | 176 | 0,1 | 2,1 | 2,9 |
| Kraków | Podgórze SKA | Podgórze SKA | 13 | 206 | bus, rail, tram | 14 | 182 | 76 | 1,6 | 1,8 | 2,8 |
| Kraków | Borek Fałęcki | Borek Fałęcki | 6 | 202 | bus, tram | 25 | 596 | 50 | 0,0 | 2,4 | 3,1 |
| Wrocław | Galeria Dominikańska | GALERIA DOMINIKAŃSKA 05 | 13 | 357 | bus, tram | 25 | 596 | 150 | 1,9 | 2,4 | 3,6 |
| Wrocław | pl. Grunwaldzki | PL. GRUNWALDZKI | 16 | 291 | bus, tram | 23 | 500 | 157 | 0,6 | 1,5 | 3,9 |
| Wrocław | Dworzec Główny | DWORZEC GŁÓWNY | 30 | 524 | bus, rail, tram | 39 | 1390 | 172 | 5,5 | 6,2 | 8,5 |
| Poznań | Rondo Kaponiera | Rondo Kaponiera | 14 | 369 | bus, tram | 17 | 262 | 145 | 1,1 | 2,5 | 3,4 |
| Poznań | Poznań Główny / Dworzec Zachodni | Dworzec Zachodni | 33 | 653 | bus, rail, tram | 26 | 578 | 146 | 1,6 | 2,0 | 5,0 |
| Poznań | Rondo Rataje | Rondo Rataje | 6 | 162 | bus, tram | 22 | 448 | 80 | 0,0 | 1,1 | 1,9 |
| Łódź | Piotrkowska Centrum | Piotrkowska Centrum | 8 | 199 | tram | 13 | 150 | 101 | 0,0 | 1,8 | 1,8 |
| Łódź | Łódź Fabryczna | Narutowicza-pl. Dąbrowskiego | 24 | 562 | bus, rail, tram | 28 | 712 | 100 | 0,9 | 2,6 | 5,0 |
| Łódź | Łódź Kaliska | Włókniarzy-Mickiewicza (Dw. Ł. Kaliska) | 28 | 654 | bus, rail, tram | 23 | 494 | 119 | 0,8 | 2,2 | 4,6 |
| Trójmiasto | Gdańsk Główny | Dworzec Główny 01 | 21 | 289 | bus, rail, tram | 40 | 1496 | 194 | 1,5 | 2,9 | 3,9 |
| Trójmiasto | Gdańsk Wrzeszcz | Gdańsk Wrzeszcz | 15 | 455 | bus, rail, tram | 29 | 768 | 109 | 1,6 | 1,8 | 4,1 |
| Trójmiasto | Gdynia Główna | Gdynia Dworzec Gł. PKP - Hala 04 | 29 | 570 | bus, rail, trolleybus | 46 | 1954 | 207 | 2,0 | 2,9 | 6,5 |
| GZM | Katowice Rynek | Katowice Aleja Korfantego | 7 | 317 | bus, tram | 36 | 1216 | 146 | 1,9 | 2,0 | 3,8 |
| GZM | Katowice Dworzec | Katowice Dworzec | 19 | 417 | bus, rail | 50 | 2432 | 147 | 1,5 | 2,0 | 5,8 |
| GZM | Sosnowiec Główny | Sosnowiec Dworzec PKP | 8 | 111 | bus, rail, tram | 30 | 862 | 85 | 0,4 | 1,0 | 1,7 |

| Węzeł | Przejścia (z kierunkami): mediana | Przejścia z sygnalizacją, % | Ruchy ze schodami, % | Ruchy z dojściem bez schodów w OSM, % | Pary z tunelem, % | Czekanie 7–9: mediana, min | Dojście z kierunkami + czekanie 7–9, min | Najlepsza para + czekanie, ważone kursami, min | Średnia odległość między słupkami po sieci, m | Możliwe skomunikowania / pary sprawdzone |
|---|---|---|---|---|---|---|---|---|---|---|
| Centrum | 0,5 | 59 | 83 | 50 | 46 | 5,3 | 8,8 | 5,7 | 280 | 1 / 322 |
| Dworzec Centralny | 1,0 | 40 | 82 | 89 | 74 | 5,6 | 8,6 | 6,5 | 229 | 1 / 496 |
| Dworzec Wileński | 0,5 | 88 | 50 | 71 | 22 | 4,2 | 7,1 | 5,1 | 249 | 0 / 159 |
| Dworzec Gdański | 1,0 | 27 | 81 | 100 | 71 | 5,1 | 10,3 | 6,0 | 312 | 0 / 99 |
| Rondo Mogilskie | 1,0 | 0 | 45 | 100 | 22 | 7,5 | 9,8 | 7,5 | 242 | 8 / 283 |
| Dworzec Główny Zachód (Basztowa, Pawia) | 1,0 | 0 | 0 | 100 | 0 | 5,0 | 5,5 | 5,3 | 128 | 1 / 30 |
| Kraków Główny (kolej) | 0,5 | 33 | 76 | 100 | 67 | 15,0 | 24,2 | 9,3 | 346 | 4 / 361 |
| Rondo Grunwaldzkie | 1,5 | 100 | 16 | 100 | 0 | 12,0 | 13,8 | 7,6 | 166 | 17 / 918 |
| Podgórze SKA | 1,0 | 95 | 50 | 100 | 0 | 7,9 | 9,9 | 7,9 | 173 | 1 / 156 |
| Borek Fałęcki | 1,0 | 94 | 35 | 100 | 2 | 23,5 | 19,5 | 14,7 | 153 | 3 / 572 |
| Galeria Dominikańska | 1,0 | 73 | 60 | 100 | 45 | 6,0 | 8,9 | 7,6 | 232 | 1 / 234 |
| pl. Grunwaldzki | 1,0 | 96 | 0 | 100 | 9 | 7,1 | 8,5 | 6,9 | 180 | 1 / 215 |
| Dworzec Główny | 1,0 | 52 | 55 | 48 | 62 | 8,6 | 16,6 | 7,7 | 498 | 2 / 640 |
| Rondo Kaponiera | 1,0 | 31 | 56 | 79 | 48 | 5,1 | 8,3 | 7,5 | 269 | 4 / 122 |
| Poznań Główny / Dworzec Zachodni | 1,0 | 74 | 76 | 96 | 58 | 7,5 | 10,8 | 6,8 | 467 | 3 / 240 |
| Rondo Rataje | 1,0 | 72 | 0 | 100 | 0 | 15,2 | 16,3 | 5,2 | 146 | 1 / 348 |
| Piotrkowska Centrum | 1,0 | 100 | 0 | 100 | 0 | 7,5 | 9,3 | 7,5 | 114 | 4 / 119 |
| Łódź Fabryczna | 1,0 | 72 | 26 | 100 | 0 | 14,1 | 17,1 | 7,7 | 353 | 9 / 613 |
| Łódź Kaliska | 1,0 | 68 | 44 | 100 | 33 | 7,6 | 11,8 | 8,3 | 338 | 7 / 424 |
| Gdańsk Główny | 1,0 | 59 | 65 | 43 | 38 | 15,0 | 18,6 | 9,1 | 233 | 5 / 1087 |
| Gdańsk Wrzeszcz | 1,0 | 28 | 84 | 28 | 56 | 12,9 | 14,3 | 10,2 | 256 | 2 / 604 |
| Gdynia Główna | 1,0 | 42 | 66 | 100 | 52 | 12,9 | 16,6 | 11,1 | 305 | 12 / 1494 |
| Katowice Rynek | 1,0 | 72 | 0 | 100 | 0 | 15,0 | 12,2 | 9,4 | 204 | 34 / 1112 |
| Katowice Dworzec | 0,0 | 25 | 54 | 100 | 41 | 15,0 | 18,0 | 15,0 | 218 | 94 / 2079 |
| Sosnowiec Główny | 0,0 | brak danych | 74 | 54 | 44 | 21,0 | 20,9 | 15,9 | 122 | 13 / 817 |

**Czytanie krytyczne znanych węzłów** (każda wartość, która zaskakiwała, została sprawdzona w danych przed pozostawieniem):

- **Rondo Mogilskie:** dojście z kierunkami 2,5 min, 45 % ruchów po schodach, ale 100 % ma też drogę bez schodów. Zgadza się z opisem węzła w TMiR 6/2017 (tramwaje na dolnej płycie, wszędzie pochylnie, schody ruchome lub windy).
- **Rondo Grunwaldzkie i Borek Fałęcki: najlepsza para 0,1 i 0,0 min.** Sprawdzono: większość par linii ma wspólny słupek (37 % i 54 % par). Wariant z kierunkami daje 2,1 i 2,4 min. Borek Fałęcki ma czekanie 7–9 23,5 min (mediana zwykła): większość z 25 linii to rzadko kursujące autobusy; ważona kursami 14,7 min.
- **Wrocław, Dworzec Główny: dojście 6,2 min z kierunkami, P90 8,5 min, ruchy bez schodów 48 %.** Najdłuższe dojście wśród znanych węzłów. Sprawdzono: zespół obejmuje dworzec autobusowy na Suchej i tramwaje na Piłsudskiego po dwóch stronach stacji (średnia odległość między słupkami po sieci 498 m, w linii prostej 232 m). Brak drogi bez schodów wynika przynajmniej częściowo z niepołączonych wind w OSM (sekcja 7). Wynik dojścia zostaje; wynik „bez schodów” jest niepewny.
- **Gdańsk Główny, Wrzeszcz, Gdynia Główna, Katowice Dworzec, Sosnowiec Główny: czekanie 7–9 13–21 min.** Sprawdzono: wśród linii docelowych dominują rzadkie linie podmiejskie i kolejowe (Gdynia Główna 46 linii, Katowice Dworzec 50). Mediana ważona jest niższa (9–16 min).
- **Rondo Rataje (Poznań): 92 % par na wspólnym słupku.** W GTFS autobusy i tramwaje mają tu wspólne słupki; dojście z kierunkami 1,1 min. Układu w terenie nie sprawdzano.
- **Piotrkowska Centrum: tylko tramwaj.** W zespole nie ma przystanków autobusowych (nie sprawdzano, gdzie zatrzymują się najbliższe autobusy); 13 linii tramwajowych, 79 % par na wspólnym słupku.
- **Warszawa Centrum: 50 % ruchów z drogą bez schodów,** choć stacja metra ma windy. 20 węzłów windy w promieniu 400 m, z czego 6 to ślepe końce; nie rozstrzygnięto, czy brakuje windy, czy połączenia w OSM.
- **Katowice Rynek: 36 linii, czekanie 15,0 min.** Sprawdzono: większość z 36 linii to autobusy kursujące w szczycie co ok. 30 min (czekanie 15 min), tramwaje mają 5,8–7,5 min; ważona kursami 9,4 min.

## 5. Porównanie z oceną AMPTI dla Krakowa

Źródło: Czekała K., Bryniarska Z., „Ocena wskaźnikowa wybranych węzłów przesiadkowych publicznego transportu zbiorowego w Krakowie”, Transport Miejski i Regionalny 6/2017, s. 5–10, tabela 5 (wersja AMPTI z 8 wskaźnikami; ankiety i audyt w kwietniu 2015 r.; plik w `data/raw/ampti_tmir/` z `SOURCE.json`). Porównywalny jest tylko wskaźnik W2 (zwartość węzła); W1 i W3–W8 wymagają audytu w terenie.

| Węzeł | AMPTI 2015: średnia arytmetyczna odległość między przystankami, m | AMPTI: odległość ważona potokiem, m | AMPTI: czas ważony potokiem | Nasza średnia odległość między słupkami po sieci OSM, m | To samo w linii prostej, m | Nasze dojście z kierunkami, mediana, min | Nasze dojście, najlepsza para, mediana, min |
|---|---|---|---|---|---|---|---|
| Rondo Mogilskie | 317,8 | 98,4 | 1:34 | 242 | 149 | 2,5 | 1,3 |
| Dworzec Główny (2015: Basztowa, Lubicz, Westerplatte, Pawia; u nas „Dworzec Główny Zachód”) | 159,0 | 23,0 | 0:27 | 128 | 85 | 1,7 | 1,5 |
| Borek Fałęcki | 186,0 | 197,7 | 3:00 | 153 | 91 | 2,4 | 0,0 |

- **Co jest porównywalne.** Średnia odległość między przystankami węzła: u nich między przystankami (stanowiskami oznaczonymi A1, T1, …) po drogach dojścia zmierzonych w terenie, u nas między słupkami GTFS po sieci OSM. Kolejność się zgadza: Mogilskie największe, Dworzec Główny i Borek Fałęcki mniejsze. Nasze wartości są niższe o 18–25 %: słupków jest więcej niż ich przystanków (Mogilskie: 18 wobec 9), więc więcej par leży blisko, a pochylnie i schody między poziomami są w OSM krótsze niż w pomiarze terenowym.
- **Co nie jest porównywalne.** Wartości ważone potokiem pochodzą z 3 966 ankiet; my nie mamy potoków. Nasza mediana po parach linii z kierunkami (Mogilskie 2,5 min, Borek Fałęcki 2,4 min) jest bliższa ich czasom ważonym (1:34 i 3:00) niż mediana najlepszej pary, która w Borku wynosi 0 min, bo większość linii autobusowych ma tam wspólne stanowisko, a przesiadki tramwaj–autobus (główny potok wg ankiet) to mniejszość par linii.
- **Różnica czasu.** Ankiety i audyt z 2015 r., sieć OSM z 2026 r., linie z rozkładu 2026; Dworzec Główny obsługiwało wtedy 13 linii, nasz zespół „Dworzec Główny Zachód” ma 9.
- **Rondo Grunwaldzkie i Podgórze SKA** (Baran, Bryniarska, TMiR 3/2022 i 7/2022): tekstu nie udało się pobrać, porównania nie ma. Nasze wartości: Rondo Grunwaldzkie dojście z kierunkami 2,1 min, średnia odległość między słupkami 166 m; Podgórze SKA 1,8 min i 173 m.

## 6. Wrażliwość na regułę zespołu

Trzy reguły: główna; „klastry 100 m” (bez łączenia, czyli zespoły = klastry z kroku częstej komunikacji); „szeroka” (250 / 350 m łączenia, rozpiętość do 600 / 800 m). Obszar pokryty.

| Aglomeracja | Reguła | Zespoły | Odjazdy w zespołach „łatwych”, % | Top 20: dojście, min | Top 20: dojście + czekanie 7–9, min | Najlepsza para: odjazdy w zespołach „łatwych”, % | Pary na tym samym słupku, % |
|---|---|---|---|---|---|---|---|
| Warszawa | klastry 100 m | 3237 | 91,3 | 1,8 | 6,6 | 98,2 | 73 |
|  | główna | 2181 | 64,2 | 2,3 | 8,2 | 91,6 | 56 |
|  | szeroka | 1553 | 48,4 | 3,7 | 8,8 | 87,6 | 49 |
| Kraków | klastry 100 m | 1274 | 92,9 | 1,0 | 8,7 | 97,8 | 54 |
|  | główna | 947 | 74,5 | 2,0 | 9,8 | 96,8 | 44 |
|  | szeroka | 778 | 61,5 | 2,2 | 11,2 | 89,9 | 40 |
| Wrocław | klastry 100 m | 821 | 97,4 | 0,7 | 7,6 | 99,2 | 71 |
|  | główna | 579 | 82,8 | 1,6 | 8,8 | 94,9 | 56 |
|  | szeroka | 426 | 64,1 | 3,1 | 10,6 | 88,7 | 47 |
| Poznań | klastry 100 m | 1004 | 96,0 | 0,9 | 7,2 | 99,3 | 82 |
|  | główna | 786 | 79,2 | 1,6 | 8,8 | 96,8 | 68 |
|  | szeroka | 637 | 65,7 | 2,0 | 9,0 | 92,1 | 64 |
| Łódź | klastry 100 m | 875 | 98,0 | 1,0 | 8,8 | 98,8 | 66 |
|  | główna | 647 | 75,7 | 2,0 | 10,4 | 97,7 | 53 |
|  | szeroka | 496 | 61,0 | 1,9 | 11,7 | 94,2 | 48 |
| Trójmiasto | klastry 100 m | 1007 | 94,8 | 1,0 | 11,2 | 99,3 | 78 |
|  | główna | 733 | 61,9 | 2,7 | 13,0 | 92,3 | 57 |
|  | szeroka | 505 | 52,4 | 2,4 | 12,5 | 89,1 | 55 |
| GZM | klastry 100 m | 2393 | 95,4 | 0,9 | 16,8 | 99,6 | 84 |
|  | główna | 1961 | 83,1 | 1,5 | 17,3 | 97,2 | 73 |
|  | szeroka | 1572 | 66,5 | 1,7 | 19,8 | 94,7 | 65 |

Znane węzły: słupki / dojście z kierunkami (mediana, min) / dojście z kierunkami + czekanie 7–9 (min):

| Węzeł | klastry 100 m | główna | szeroka |
|---|---|---|---|
| Centrum | 2 / 1,8 / 6,7 | 13 / 3,6 / 8,8 | 20 / 3,9 / 9,0 |
| Dworzec Centralny | 4 / 2,7 / 6,8 | 27 / 2,7 / 8,6 | 27 / 2,7 / 8,6 |
| Dworzec Wileński | 3 / 2,0 / 6,6 | 10 / 2,4 / 7,1 | 19 / 2,5 / 7,1 |
| Dworzec Gdański | 5 / 2,0 / 5,0 | 22 / 3,8 / 10,3 | 26 / 3,8 / 9,8 |
| Rondo Mogilskie | 7 / 1,3 / 8,4 | 18 / 2,5 / 9,8 | 18 / 2,5 / 9,8 |
| Dworzec Główny Zachód (Basztowa, Pawia) | 3 / 0,4 / 4,1 | 6 / 1,7 / 5,5 | 46 / 4,6 / 14,3 |
| Kraków Główny (kolej) | 11 / 2,9 / 31,5 | 27 / 2,3 / 24,2 | 46 / 4,6 / 14,3 |
| Rondo Grunwaldzkie | 7 / 2,1 / 20,9 | 13 / 2,1 / 13,8 | 17 / 1,7 / 11,6 |
| Podgórze SKA | 5 / 0,8 / 8,2 | 13 / 1,8 / 9,9 | 19 / 1,9 / 10,2 |
| Borek Fałęcki | 5 / 0,0 / 27,6 | 6 / 2,4 / 19,5 | 12 / 2,4 / 21,0 |
| Galeria Dominikańska | 4 / 1,3 / 6,5 | 13 / 2,4 / 8,9 | 22 / 2,5 / 9,3 |
| pl. Grunwaldzki | 8 / 0,7 / 7,0 | 16 / 1,5 / 8,5 | 20 / 1,3 / 8,4 |
| Dworzec Główny | 5 / 0,7 / 6,8 | 30 / 6,2 / 16,6 | 42 / 6,2 / 20,0 |
| Rondo Kaponiera | 4 / 1,9 / 7,6 | 14 / 2,5 / 8,3 | 22 / 2,7 / 8,1 |
| Poznań Główny / Dworzec Zachodni | 2 / 0,6 / 5,7 | 33 / 2,0 / 10,8 | 33 / 2,0 / 10,8 |
| Rondo Rataje | 3 / 0,5 / 20,5 | 6 / 1,1 / 16,3 | 17 / 2,0 / 14,1 |
| Piotrkowska Centrum | 3 / 0,7 / 8,1 | 8 / 1,8 / 9,3 | 11 / 1,3 / 8,8 |
| Łódź Fabryczna | 4 / 0,8 / 10,5 | 24 / 2,6 / 17,1 | 21 / 3,8 / 17,7 |
| Łódź Kaliska | 4 / 1,2 / 8,9 | 28 / 2,2 / 11,8 | 16 / 1,6 / 9,9 |
| Gdańsk Główny | 10 / 2,0 / 14,4 | 21 / 2,9 / 18,6 | 10 / 1,9 / 15,1 |
| Gdańsk Wrzeszcz | 10 / 1,6 / 16,6 | 15 / 1,8 / 14,3 | 20 / 3,0 / 14,7 |
| Gdynia Główna | 2 / 0,7 / 13,6 | 29 / 2,9 / 16,6 | 34 / 3,5 / 16,1 |
| Katowice Rynek | 2 / brak danych / brak danych | 7 / 2,0 / 12,2 | 22 / 2,0 / 16,4 |
| Katowice Dworzec | 6 / 1,3 / 16,2 | 19 / 2,0 / 18,0 | 22 / 2,0 / 16,4 |
| Sosnowiec Główny | 5 / 1,0 / 19,0 | 8 / 1,0 / 20,9 | 11 / 1,0 / 23,4 |

**Jak reguła działa na znanych węzłach i gdzie zawodzi.**

- Większość węzłów wychodzi tak, jak zna je pasażer: Rondo Mogilskie (18 słupków, 273 m), Rondo Grunwaldzkie, pl. Grunwaldzki, Galeria Dominikańska, Rondo Kaponiera, Piotrkowska Centrum, Katowice Rynek, Dworzec Wileński, Centrum z przystankiem Warszawa Śródmieście.
- **Kraków, Dworzec Główny: dwa zespoły.** „Dworzec Główny Zachód” (Basztowa / Pawia, 6 słupków) i zespół „Kraków Główny” (stacja, Dworzec Główny Wschód, Uniwersytet Ekonomiczny, Muzeum AK; 27 słupków) dzieli ok. 330 m. Dla pasażera to jeden obszar przesiadkowy z tunelem pod torami. Reguła szeroka łączy je w jeden zespół (46 słupków), ale wtedy wyniki obu części się mieszają (tabela wyżej). To jest błąd reguły głównej, zostawiony jawnie.
- **Wrocław, Dworzec Główny.** Stacja (jeden punkt GTFS dla 10 stanowisk) łączy się z dworcem autobusowym i tramwajami na Piłsudskiego (30 słupków, 524 m). Pierwsza wersja reguły (bez większej rozpiętości dla kolei) rozdzielała tramwaje i stację; to było niezgodne z rzeczywistością i zostało poprawione.
- **Za szeroko: Warszawa Dworzec Gdański** (585 m) wciąga przystanek „Felińskiego”; **Poznań Główny / Dworzec Zachodni** (653 m) i **Łódź Kaliska** (654 m) to całe kompleksy dworcowe. Dojście w tych zespołach jest dłuższe, bo zespół obejmuje słupki, między którymi pasażer zwykle się nie przesiada.
- **Niestabilność pełnego wiązania.** Przy regule szerokiej Gdańsk Główny ma 10 słupków (przy głównej 21), Łódź Kaliska 16 (przy głównej 28): większa składowa dzieli się w innym miejscu. Wynik węzła zależy więc od reguły bardziej niż wynik miasta.
- **Wrażliwość miar miejskich.** Udział odjazdów w zespołach „łatwych” spada z 91–98 % (klastry 100 m) przez 62–83 % (główna) do 48–67 % (szeroka). Kolejność miast jest podobna (Warszawa i Trójmiasto najniżej w obu wariantach z łączeniem), ale poziom zależy od reguły; liczby nie są wielkościami bezwzględnymi.

## 7. Kompletność tagów OSM

Dwie miary: (a) w całym grafie pieszym aglomeracji: węzły, w których osobno zmapowany chodnik lub ścieżka przecina jezdnię (węzeł na jezdni z co najmniej dwiema krawędziami pieszymi), i jaki ich odsetek ma tag przejścia; odsetek węzłów `highway=crossing` z wartością `crossing=*`; (b) na policzonych dojściach (reguła główna, obszar pokryty): odsetek przejść z wartością `crossing=*` lub sygnalizacją i odsetek długości dojść prowadzonych osią jezdni.

| Aglomeracja | Węzły chodnik × jezdnia | z tagiem przejścia, % | z wartością crossing / sygnalizacją, % | Węzły highway=crossing | z crossing=*, % | Dojścia: przejścia z wartością, % | Dojścia: przejścia z sygnalizacją, % | Dojścia: długość osią jezdni, % | Windy (węzły) w grafie | Windy bez połączenia z drugim poziomem, % |
|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 41 979 | 81,5 | 70,3 | 55 309 | 81,3 | 94,3 | 58,7 | 21,0 | 478 | 20,9 |
| Kraków | 12 193 | 79,0 | 68,4 | 14 865 | 78,1 | 89,5 | 52,6 | 9,9 | 157 | 8,3 |
| Wrocław | 11 998 | 67,0 | 55,0 | 13 815 | 68,8 | 87,7 | 54,7 | 9,6 | 53 | 35,8 |
| Poznań | 12 753 | 84,5 | 76,5 | 20 563 | 86,3 | 93,5 | 41,2 | 15,7 | 34 | 14,7 |
| Łódź | 12 159 | 72,4 | 61,5 | 15 836 | 73,2 | 91,6 | 54,1 | 17,8 | 80 | 30,0 |
| Trójmiasto | 13 731 | 71,7 | 61,1 | 15 116 | 80,5 | 90,9 | 48,9 | 9,2 | 125 | 24,0 |
| GZM | 23 388 | 77,9 | 67,4 | 32 223 | 71,2 | 89,1 | 34,9 | 21,8 | 85 | 32,9 |

**Czytanie.** Tagowanie jest nierówne: we Wrocławiu tylko 67 % węzłów, w których chodnik przecina jezdnię, ma jakikolwiek tag przejścia, w Poznaniu 85 %. Na policzonych dojściach odsetek jest wyższy (88–94 %), bo w centrach przejścia są mapowane staranniej. Udział przejść z sygnalizacją (35–59 %) zależy więc częściowo od tagowania; jest w warstwie, ale nie w miarach miejskich. 9–22 % długości dojść biegnie osią jezdni (chodnik nie zmapowany osobno, najwięcej w GZM i Warszawie): tam przejścia przez boczne ulice są niewidoczne, więc liczba przejść jest zaniżona.

**Windy.** Od 8 % (Kraków) do 36 % (Wrocław) węzłów `highway=elevator` w grafie pieszym to ślepe końce: winda jest podpięta tylko do jednego poziomu. Brak dojścia bez schodów (np. Wrocław Dworzec Główny 48 % ruchów ze ścieżką bez schodów, Gdańsk Główny 43 %, Gdańsk Wrzeszcz 28 %) znaczy więc „nie znaleziono w OSM”, a nie „nie istnieje”. W okolicy Wrocławia Głównego 5 z 6 wind w grafie to ślepe końce.

## 8. Możliwe skomunikowania (przybliżone)

| Aglomeracja | Pary sprawdzone (linia B co ≥ 15 min) | Kandydaci | Kandydaci, % | Pary w najlepszych 10 % przesunięć, % |
|---|---|---|---|---|
| Warszawa | 37403 | 551 | 1,5 | 13,5 |
| Kraków | 30428 | 410 | 1,3 | 11,4 |
| Wrocław | 13490 | 134 | 1,0 | 13,1 |
| Poznań | 12276 | 89 | 0,7 | 12,6 |
| Łódź | 16881 | 251 | 1,5 | 12,9 |
| Trójmiasto | 21792 | 189 | 0,9 | 13,1 |
| GZM | 89389 | 2193 | 2,5 | 11,6 |

**Czytanie.** W każdym mieście 11–14 % par mieści się w najlepszych 10 % przesunięć, czyli tylko 1–4 pkt proc. ponad to, co daje przypadek. Rozkład jednego dnia nie pokazuje więc systematycznego skomunikowania linii co ≥ 15 min w żadnym mieście. Najwięcej kandydatów jest w GZM (2,5 % par sprawdzonych), także na Katowice Dworzec (94 z 2 079 par); nie sprawdzono, ile z nich to kursy przechodzące lub zdublowane linie. Lista kandydatów: `timed_connections_possible.csv`; wynik przybliżony, nie do publikacji jako „skomunikowania”.

## 9. Próba przesiadek z fazy 3

Plik `results/qa/access/transfers_sample_<agg>.csv` zawiera dla każdej z 200 par start–cel tylko liczbę przejazdów, przesiadek i minut pieszo, **bez miejsca przesiadki** (kolumny legs nie zapisano; nie ma ich też w `data/interim/access/<agg>/all/transfers_am/result.parquet`). Itinerariów z co najmniej jedną przesiadką jest 41 (Łódź) do 64 (Warszawa) na miasto. Nawet z miejscem przesiadki dałoby to 0–3 przesiadki na węzeł, czyli nic poza listą „tu ktoś się przesiadł”. **Składowej „jak często najszybsze podróże przesiadają się w węźle” nie policzono.** Żeby ją policzyć, trzeba powtórzyć routing R5 z zapisem odcinków podróży i dużo większą próbą (rzędu 5–10 tys. par na miasto; koszt nieoszacowany). Znaczenie węzła opisują tu liczba linii, par i odjazdów.

## 10. Ograniczenia

- **Brak wag pasażerskich.** Mediany są po parach linii (zwykła i ważona kursami), nie po przesiadających się pasażerach. AMPTI waży potokami z badań ankietowych; tych danych nie mamy.
- **Czekanie rozkładowe, w pełnych minutach,** bez opóźnień, bez czasu postoju; przy częstych liniach różnica minuty to znaczna część wyniku.
- **Dojście bez kar:** 5 km/h, bez czasu na światłach, schodach, windach i w tłumie; AMPTI mierzy czas w terenie (w Krakowie ok. 1 m/s z różnicami poziomów).
- **OSM:** przejścia, schody, tunele i windy tylko tak, jak są zmapowane (sekcja 7). Dojście osią jezdni ukrywa przejścia; niepołączone windy ukrywają drogi bez schodów. Kładka (`bridge`) obejmuje też chodniki na mostach drogowych.
- **Kolej:** perony nieznane (reguła 8). Dla przesiadek kolej–kolej dojście to brak danych.
- **Zespół przystanków** to reguła geometryczna; wynik węzła zależy od niej (sekcja 6).
- **Pary „równoległe”** usunięte regułą 80 % wspólnych zespołów; linie, które dzielą krótszy odcinek, liczą się jako para nawet tam, gdzie nikt się między nimi nie przesiada.
- **Jeden dzień** (środa 2026-11-25), wszystkie feedy (28 nieoficjalnych, niesprawdzonych). Wariant feedów oficjalnych nie był liczony.
- **Do czego nie używać:** do rankingu węzłów lub miast o podobnych wynikach, do oceny konkretnej przebudowy, jako zamiennika audytu AMPTI.

## 11. Nie zweryfikowano

- Czy brak drogi bez schodów na dużych stacjach (Wrocław Główny, Gdańsk Główny i Wrzeszcz, Warszawa Centrum) to brak w OSM, czy w rzeczywistości.
- Położenia peronów kolejowych i dojścia na perony; pary kolej–kolej mają dojście „brak danych”.
- Kandydatów na skomunikowania (czy to kursy przechodzące, dublowane linie, czy rzeczywista koordynacja).
- Zgodności sygnalizacji i rodzaju przejść z terenem.
- Wariantu feedów oficjalnych i dni innych niż środa referencyjna.
- Pozostałych prac AMPTI dla Krakowa: Baran i Bryniarska, TMiR 3/2022 i 7/2022 (Rondo Grunwaldzkie, Podgórze SKA) i pracy metodycznej z TMiR 6/2014 nie udało się pobrać (serwer yadda.icm.edu.pl odmawia dostępu, kopia na bibliotekanauki.pl pod sprawdzonym numerem to inny artykuł).
- Wyniku dla „Kraków Główny” wobec oceny AMPTI węzła „Dworzec Główny” z 2015 r.: oceniany wtedy węzeł to przystanki przy Basztowej, Lubiczu, Westerplatte i Pawiej, a układ linii od 2015 r. się zmienił.

## 12. Pliki i czas

- Warstwa: `results/layers/transfer_nodes.parquet` (8540 zespołów w FUA, EPSG:4326, punkt = średnia położeń słupków zespołu); opis pól w `results/layers/_meta_transfer.json`.
- Metryki: `results/metrics/metrics_transfer.csv` / `.json` (format pozostałych kroków; jeszcze nie w `metrics.csv`, bo `merge_metrics` nie został zmieniony).
- Tabele w tym katalogu: `known_interchanges.csv`, `known_interchanges_rules.csv`, `pairs_known_interchanges.csv`, `city_summary_rules.csv`, `osm_tag_completeness.csv`, `top_nodes.csv`, `timed_connections_possible.csv`.
- Kod: `pipeline/transfer_ease.py`, `transfer_osm.py`, `transfer_walk.py`, `transfer_report.py`, `transfer_md.py`, `transfer_text.py`; reguła `transfer_ease` w `Snakefile`.
- Czas obliczeń: w `_meta.json` tego katalogu (`seconds_per_agglomeration`, `duration_s`); nie w tej nocie, żeby była identyczna przy każdym przebiegu.

