# Łatwość przesiadki w zespołach przystanków (warstwa dodatkowa, 2026-11-24)

Warstwa dodatkowa zatwierdzona przez właściciela 2026-11-24 (RAPORT §12.2). Opisuje, jak łatwo przesiąść się między liniami w zespole przystanków: ile trzeba przejść, przez ile jezdni, czy po schodach, ile średnio czekać na linię docelową i jak ważny jest węzeł. **Składowe są publikowane obok siebie i nie są łączone w jedną ocenę.**

Punkt odniesienia z literatury, nie specyfikacja: prace o „karze za przesiadkę” rozkładają koszt przesiadki na dojście, czekanie i resztę zależną od stacji i rodzaju ruchu (Guo i Wilson 2011, metro londyńskie; Iseki i Taylor, Transport Reviews, „Not all transfers are created equal”). Polska metoda AMPTI (Olszewski, Krukowska, Krukowski, TMiR 6/2014; stosowana w wytycznych ZTM Warszawa i w ocenach węzłów Krakowa) ocenia węzły wskaźnikami ilościowymi, ale część z nich (stan peronów, informacja, oświetlenie, monitoring, widoczność przystanków) wymaga audytu w terenie. **Ta warstwa to wariant własny, ograniczony do tego, co dają rozkłady i OpenStreetMap. Nie jest oceną AMPTI ani wskaźnikiem kary za przesiadkę** i nie nosi nazwy żadnej z tych metod.

Wszystkie czasy dojścia są z sieci pieszej OSM przy 5 km/h, bez czasu na światłach, schodach i w tłumie; czekanie jest rozkładowe, w pełnych minutach. Wynik nie mówi nic o punktualności, zatłoczeniu ani informacji dla pasażerów.

**Rewizje po przeglądzie literatury (2026-11-24):** czekanie na przesiadkę po rzeczywistym przyjeździe, pasmo uogólnionego czasu przesiadki z opublikowanych wag, przejścia w skali AMPTI W6, udział ruchów „częste × częste” i test skomunikowań ograniczony do linii rzadkich z kontrolą dodatnią; reguły 10–15, sekcje 13–18 i dodatkowa tabela w sekcji 4. Wcześniejsze kolumny i miary nie zmieniły definicji.

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
10. **Czekanie na przesiadkę (dodane po przeglądzie literatury).** Dla każdego ruchu (kierunek przyjazdu A × kierunek odjazdu B) i każdego rozkładowego przyjazdu A w oknie: czas od przyjazdu A plus dojścia do najbliższego odjazdu B w tym kierunku (obcięty do 60 min). Na ruch: średnia, mediana i 90. percentyl; na zespół: mediana i 90. percentyl ważone (każdy przyjazd A z wagą liczby odjazdów B w tym kierunku 6–20, więc ruch waży przyjazdy A × odjazdy B jak w sumie addytywnej) oraz średnia ważona kursami na tym samym zbiorze ruchów co suma addytywna. Czas przyjazdu A to przyjazd na pierwszy słupek linii w zespole, czas odjazdu B to odjazd z ostatniego; przy pełnych minutach w GTFS odjazd B w tej samej minucie co przyjazd A (po dojściu 0) liczy się jako złapany. Oczekiwane czekanie przy losowym przyjściu (reguła 6) zostaje bez zmian obok.
11. **Uogólniony czas przesiadki (pasmo).** Dojście × a + czekanie × b + stała kara P, w minutach równoważnych jeździe, z typowej przesiadki 7–9 (składowe addytywne). Wariant niski: a = 1,20, b = 1,47, P = 5 min; środkowy: a = 1,66, b = 1,47, P = 13 min; wysoki: a = 1,66, b = 1,47, P = 18 min. Źródła wag: Wardman 1998 (ITS Leeds WP 525: dojście 1,66, czekanie 1,47 minuty jazdy), Ortelli i in. 2026 (STRC: dojście 1,21, kara resztowa 5–9 min), Jara-Díaz i in. 2022 (zakres kary do planowania 13–18 min). To przeliczenie składowych według opublikowanych wag, nie nowy wskaźnik: pasmo stoi obok składowych i nie służy do układania węzłów w ranking.
12. **Przejścia w skali AMPTI W6.** Każde przejście na dojściu dostaje klasę W6 (Czekała i Bryniarska, TMiR 6/2017: bezkolizyjne 100 %, z sygnalizacją bez kolizji ze skrętami 70 %, z kolizjami 50 %, zebra bez sygnalizacji 30 %, niewyznakowane 0 %) według tagów OSM (tabela w sekcji 15). Ruch: średnia z ocenionych przejść; zespół: średnia ważona kursami po ruchach z co najmniej jednym ocenionym przejściem. OSM nie mówi, czy sygnalizacja ma kolizje ze skrętami, więc są dwie wartości: z sygnalizacją jako 70 % i jako 50 %. Ruch bez żadnego przejścia nie ma oceny W6 (jest w zwykłej liczbie przejść jako 0).
13. **Ruchy „częste × częste”.** Ruch, w którym linia A w swoim kierunku przyjazdu i linia B w swoim kierunku odjazdu kursują w godzinach 7–9 średnio co 10 min lub częściej (co najmniej 12 kursów w 2 h); drugi próg 15 min (co najmniej 8 kursów). Udział liczony po ruchach, bez wag.
14. **Test skomunikowań, wersja po przeglądzie.** (a) Test par z reguły 9 ograniczony do par, w których obie linie kursują średnio co ≥ 15 min (6–20): A na słupku wysiadania, B na słupku wsiadania; wynik po miastach, rodzajach środków i węzłach z jednostronnym testem dwumianowym wobec 10 % z przypadku. (b) Test pulsu w węźle: odjazdy linii kursujących co ≥ 15 min złożone na cykl 30 min (pełne minuty); statystyka = udział odjazdów w najgęstszych 3 kolejnych minutach; rozkład odniesienia = te same rozkłady linii przesunięte każdy o losową liczbę minut (1000 losowań), więc jedna regularna linia ani kilka niezależnych nie daje pulsu; puls, gdy wynik przekracza kwantyl 0,99 odniesienia. Test nie wymaga dojścia ani czasu przyjazdu. (c) Kontrola dodatnia: oba testy w oknie nocnym 23:00–04:30 dla linii kursujących tam co 15–60 min.
15. **Szczegóły węzła na mapę.** Zespoły z co najmniej 20 odjazdami na godzinę (6–20), w FUA i w masce GTFS: słupki, drogi piesze najlepszej pary słupków każdego ruchu (geometria z sieci OSM z przejściami w klasach W6 i schodami), macierz ruchów i dziesięć najcięższych ruchów (`pipeline/transfer_detail.py`).

## 3. Wyniki dla miast (reguła główna)

„Łatwe” = mediana dojścia między liniami ≤ 2 min; udział liczony po odjazdach 6–20 wszystkich zespołów przesiadkowych w obszarze. „Top 20” = 20 zespołów z największą liczbą odjazdów w obszarze. Obszar pokryty = zespoły w FUA i w masce GTFS. Wartości addytywne miasta to zwykła średnia wartości 20 zespołów, więc też się sumują; pozostałe kolumny „Top” to mediana median zespołów.

Pierwsze trzy kolumny wartości są addytywne: liczone na jednym zbiorze ruchów przesiadkowych z kierunkami (kierunek przyjazdu A × kierunek odjazdu B), które mają zarówno dojście, jak i czekanie na B w tym kierunku w oknie 7–9; każdy ruch ma wagę liczby kursów (przyjazdy A w tym kierunku × odjazdy B w tym kierunku, 6–20). Dojście i czekanie to średnie ważone, suma to średnia ważona sum, więc dojście + czekanie = suma. Pozostałe kolumny to mediany (po parach linii, potem po zespołach), a mediana sumy nie jest sumą median, dlatego tamte kolumny się nie sumują.

| Aglomeracja | Obszar | Top 20, 7–9, średnia ważona kursami: dojście, min | + czekanie, min | = przesiadka, min | To samo 6–20: dojście, min | + czekanie, min | = przesiadka, min | Zespoły | Odjazdy w zespołach „łatwych”, % | Odjazdy w zespołach z dojściem > 5 min, % | Top 20: dojście, mediana, min | Top 20: przejścia, mediana | Top 20: czekanie 7–9, mediana, min | Top 20: dojście + czekanie 7–9, mediana, min | Top 20: to samo, najlepsza para, ważone kursami, min | Top 20: pary bez schodów, % | Najlepsza para słupków: odjazdy w zespołach „łatwych”, % | Najlepsza para: top 20 dojście, min | Pary na tym samym słupku, % | Odjazdy zespołów w masce, % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | rdzeń | 2,5 | 5,6 | 8,1 | 2,5 | 6,7 | 9,2 | 1134 | 61,0 | 1,5 | 2,3 | 1,0 | 5,3 | 8,2 | 5,7 | 92 | 90,8 | 1,4 | 52 | 98,7 |
|  | pokryty | 2,5 | 5,6 | 8,1 | 2,5 | 6,7 | 9,2 | 2181 | 64,2 | 1,3 | 2,3 | 1,0 | 5,3 | 8,2 | 5,7 | 92 | 91,6 | 1,4 | 56 | 95,9 |
| Kraków | rdzeń | 2,1 | 8,2 | 10,3 | 2,1 | 9,3 | 11,4 | 538 | 74,1 | 0,4 | 2,0 | 1,0 | 7,6 | 9,8 | 7,5 | 100 | 96,9 | 0,4 | 44 | 95,8 |
|  | pokryty | 2,1 | 8,2 | 10,3 | 2,1 | 9,3 | 11,4 | 947 | 74,5 | 0,6 | 2,0 | 1,0 | 7,6 | 9,8 | 7,5 | 100 | 96,8 | 0,4 | 44 | 93,9 |
| Wrocław | rdzeń | 1,5 | 8,4 | 9,9 | 1,5 | 9,5 | 11,0 | 487 | 82,7 | 2,1 | 1,6 | 1,0 | 7,4 | 8,8 | 7,3 | 86 | 94,9 | 0,5 | 55 | 99,2 |
|  | pokryty | 1,5 | 8,4 | 9,9 | 1,5 | 9,5 | 11,0 | 579 | 82,8 | 2,1 | 1,6 | 1,0 | 7,4 | 8,8 | 7,3 | 86 | 94,9 | 0,5 | 56 | 98,0 |
| Poznań | rdzeń | 1,6 | 7,1 | 8,7 | 1,6 | 8,1 | 9,7 | 422 | 78,6 | 0,2 | 1,6 | 1,0 | 5,2 | 8,8 | 5,5 | 97 | 97,5 | 0,0 | 63 | 97,6 |
|  | pokryty | 1,6 | 7,1 | 8,7 | 1,6 | 8,1 | 9,7 | 786 | 79,2 | 0,6 | 1,6 | 1,0 | 5,2 | 8,8 | 5,5 | 97 | 96,8 | 0,0 | 68 | 95,6 |
| Łódź | rdzeń | 2,1 | 10,9 | 13,0 | 2,1 | 11,9 | 14,0 | 437 | 75,1 | 0,3 | 2,0 | 1,0 | 7,6 | 10,4 | 8,5 | 98 | 97,8 | 0,8 | 55 | 97,8 |
|  | pokryty | 2,1 | 10,9 | 13,0 | 2,1 | 11,9 | 14,0 | 647 | 75,7 | 0,2 | 2,0 | 1,0 | 7,6 | 10,4 | 8,5 | 98 | 97,7 | 0,8 | 53 | 96,4 |
| Trójmiasto | rdzeń | 2,9 | 10,5 | 13,4 | 2,9 | 11,9 | 14,8 | 566 | 61,1 | 3,3 | 2,7 | 1,0 | 10,7 | 13,0 | 10,2 | 90 | 92,9 | 0,5 | 57 | 98,0 |
|  | pokryty | 2,9 | 10,5 | 13,4 | 2,9 | 11,9 | 14,8 | 733 | 61,9 | 3,4 | 2,7 | 1,0 | 10,7 | 13,0 | 10,2 | 90 | 92,3 | 0,5 | 57 | 97,0 |
| GZM | rdzeń | 1,8 | 15,6 | 17,4 | 1,8 | 17,5 | 19,3 | 1478 | 81,9 | 1,1 | 1,5 | 0,5 | 15,0 | 17,3 | 15,0 | 92 | 97,0 | 0,2 | 72 | 97,5 |
|  | pokryty | 1,8 | 15,6 | 17,4 | 1,8 | 17,5 | 19,3 | 1961 | 83,1 | 1,0 | 1,5 | 0,5 | 15,0 | 17,3 | 15,0 | 92 | 97,2 | 0,2 | 73 | 96,8 |

**Czytanie krytyczne.**

- **Typowa przesiadka 7–9 (wartości addytywne, pierwsze trzy kolumny).** W 20 największych zespołach: dojście 1,5–2,9 min + czekanie 5,6–15,6 min = 8,1 min (Warszawa) do 17,4 min (GZM). Czekanie stanowi 69–90 % sumy. W Poznaniu i GZM średnia jest z 19 zespołów: jeden z 20 największych nie ma ruchu z dojściem i czekaniem w oknie. Średnie ważone wychodzą wyżej niż mediany w miastach z wieloma rzadkimi liniami (Łódź: czekanie 10,9 min wobec mediany 7,6): rozkład czekania jest prawoskośny, a waga „przyjazdy A × odjazdy B” nie usuwa rzadkich linii docelowych, bo częsta linia A daje dużą wagę także przesiadce na rzadką B (sprawdzono na Rondzie Rataje: mediana czekania w ruchach 14,9 min, średnia 16,8, średnia ważona 11,0). To zamierzone: suma ma się sumować, a mediana tego nie zapewnia.
- **Najlepsza para słupków nie różnicuje miast.** W wariancie zgodnym z zadaniem (najlepsza para słupków dla każdej pary linii, bez kierunków) 91–98 % odjazdów przypada na zespoły z medianą dojścia ≤ 2 min, a mediana dla 20 największych węzłów to 0,0–1,4 min. Powód sprawdzono w danych: 44–73 % par linii ma najlepszą parę na tym samym słupku, bo linie jadą wspólnym odcinkiem; przesiadka w tym samym kierunku jest wtedy możliwa, ale zwykle niepotrzebna. Dlatego miary główne korzystają z wariantu z kierunkami (reguła 4); wariant najlepszej pary jest w tabelach i w warstwie.
- **Czekanie decyduje bardziej niż dojście.** W 20 największych węzłach mediana dojścia z kierunkami to 1,5–2,7 min, a oczekiwane czekanie 7–9 to 5,2 min (Poznań) do 15,0 min (GZM). GZM ma najkrótsze dojścia (1,5 min) i najdłuższe czekanie; zgadza się to z §15.2 raportu (linie GZM kursują rzadko i rozchodzą się na węzłach).
- **Mediana zwykła a ważona.** Mediana po parach linii traktuje rzadką linię podmiejską tak samo jak tramwaj co 5 min. Mediana ważona liczbą kursów jest zwykle niższa, o 0–8 min (np. Kraków Główny: 17,3 min zwykła wobec 9,3 ważonej przy najlepszej parze). Obie są w warstwie; do porównań węzłów o różnym udziale kolei bezpieczniej czytać ważoną.
- **Warszawa i Trójmiasto mają najmniej odjazdów w zespołach „łatwych” (ok. 61–64 %).** Sprawdzono: w obu duże węzły to kompleksy wielopoziomowe (metro, SKM, dworce), gdzie dojście z kierunkami wynosi 2,3–3,8 min (Centrum 3,7; Dworzec Gdański 3,8; Gdańsk Główny 2,9; Gdynia Główna 2,9). Wynik zostaje.
- **Przejścia przez jezdnię.** Mediana 1 przejście na ruch w 20 największych węzłach wszystkich miast poza GZM (0,5). Przy najlepszej parze mediana wynosi 0, bo wspólny słupek nie wymaga przejścia.

**Kontrola addytywności (wbudowana; krok kończy się błędem, gdy nie przechodzi).** Dla każdego zespołu (reguła główna, oba okna) i każdego wiersza miejskiego (wszystkie reguły i obszary) sprawdzono, że dojście + czekanie = suma przed zaokrągleniem (tolerancja 1e-9 min): 9747 trójek zespołów i 84 trójek miejskich, błędów 0. Zaokrąglenie: w plikach (warstwa, CSV, metryki) składowe mają 4 cyfry znaczące, a suma jest publikowana jako suma zaokrąglonych składowych (wybrano to zamiast osobnego zaokrąglenia sumy), więc dodaje się dokładnie; może mieć jedną cyfrę więcej niż 4 znaczące (np. 2,621 + 9,793 = 12,414) i różni się od sumy niezaokrąglonej najwyżej o sumę błędów zaokrąglenia składowych (pół jednostki ostatniej cyfry każdej; największe odchylenie: 100 % tej granicy w zespołach, 93 % w miastach). W tej nocie składowe są zaokrąglone do 0,1 min, a suma to suma wydrukowanych składowych.

## 4. Znane węzły: kontrola

Dla każdego węzła wybrano zespół o największej liczbie odjazdów, którego nazwy pasują do wzorca i którego środek leży ≤ 600 m od punktu orientacyjnego (`transfer_report.KNOWN`). Wszystkie kolumny: `known_interchanges.csv`; pary linii: `pairs_known_interchanges.csv`.

Pierwsze trzy kolumny wartości są addytywne: liczone na jednym zbiorze ruchów przesiadkowych z kierunkami (kierunek przyjazdu A × kierunek odjazdu B), które mają zarówno dojście, jak i czekanie na B w tym kierunku w oknie 7–9; każdy ruch ma wagę liczby kursów (przyjazdy A w tym kierunku × odjazdy B w tym kierunku, 6–20). Dojście i czekanie to średnie ważone, suma to średnia ważona sum, więc dojście + czekanie = suma. Pozostałe kolumny to mediany (po parach linii, potem po zespołach), a mediana sumy nie jest sumą median, dlatego tamte kolumny się nie sumują.

| Miasto | Węzeł | 7–9, średnia ważona kursami: dojście, min | + czekanie, min | = przesiadka, min | Zespół (nazwa wiodąca) | Słupki | Rozpiętość, m | Środki | Linie | Pary | Odjazdy/h 6–20 | Dojście, najlepsza para: mediana, min | Dojście z kierunkami: mediana, min | Dojście z kierunkami: P90, min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | Centrum | 3,1 | 5,5 | 8,6 | Centrum | 13 | 388 | bus, metro, rail, tram | 29 | 804 | 313 | 1,8 | 3,6 | 4,3 |
| Warszawa | Dworzec Centralny | 3,1 | 7,3 | 10,4 | Dw. Centralny | 27 | 427 | bus, rail, tram | 39 | 1382 | 282 | 1,8 | 2,7 | 3,9 |
| Warszawa | Dworzec Wileński | 2,3 | 4,7 | 7,0 | Dw. Wileński | 10 | 337 | bus, metro, tram | 21 | 416 | 237 | 1,1 | 2,4 | 2,9 |
| Warszawa | Dworzec Gdański | 3,3 | 5,2 | 8,5 | Dw. Gdański | 22 | 585 | bus, metro, rail, tram | 16 | 219 | 161 | 2,7 | 3,8 | 6,2 |
| Kraków | Rondo Mogilskie | 2,4 | 6,1 | 8,5 | Rondo Mogilskie | 18 | 273 | bus, tram | 20 | 378 | 181 | 1,3 | 2,5 | 3,6 |
| Kraków | Dworzec Główny Zachód (Basztowa, Pawia) | 1,3 | 3,8 | 5,1 | Dworzec Główny Zachód | 6 | 153 | bus, tram | 9 | 70 | 52 | 1,5 | 1,7 | 1,8 |
| Kraków | Kraków Główny (kolej) | 3,2 | 13,3 | 16,5 | Kraków Główny | 27 | 532 | bus, rail, tram | 28 | 581 | 113 | 1,8 | 2,3 | 5,2 |
| Kraków | Rondo Grunwaldzkie | 1,7 | 10,2 | 11,9 | Rondo Grunwaldzkie | 13 | 250 | bus, tram | 33 | 1046 | 176 | 0,1 | 2,1 | 2,9 |
| Kraków | Podgórze SKA | 1,7 | 9,2 | 10,9 | Podgórze SKA | 13 | 206 | bus, rail, tram | 14 | 182 | 76 | 1,6 | 1,8 | 2,8 |
| Kraków | Borek Fałęcki | 2,4 | 14,7 | 17,1 | Borek Fałęcki | 6 | 202 | bus, tram | 25 | 596 | 50 | 0,0 | 2,4 | 3,1 |
| Wrocław | Galeria Dominikańska | 2,0 | 7,3 | 9,3 | GALERIA DOMINIKAŃSKA 05 | 13 | 357 | bus, tram | 25 | 596 | 150 | 1,9 | 2,4 | 3,6 |
| Wrocław | pl. Grunwaldzki | 1,3 | 7,2 | 8,5 | PL. GRUNWALDZKI | 16 | 291 | bus, tram | 23 | 500 | 157 | 0,6 | 1,5 | 3,9 |
| Wrocław | Dworzec Główny | 3,3 | 10,8 | 14,1 | DWORZEC GŁÓWNY | 30 | 524 | bus, rail, tram | 39 | 1390 | 172 | 5,5 | 6,2 | 8,5 |
| Poznań | Rondo Kaponiera | 2,3 | 6,1 | 8,4 | Rondo Kaponiera | 14 | 369 | bus, tram | 17 | 262 | 145 | 1,1 | 2,5 | 3,4 |
| Poznań | Poznań Główny / Dworzec Zachodni | 2,6 | 9,8 | 12,4 | Dworzec Zachodni | 33 | 653 | bus, rail, tram | 26 | 578 | 146 | 1,6 | 2,0 | 5,0 |
| Poznań | Rondo Rataje | 1,0 | 11,0 | 12,0 | Rondo Rataje | 6 | 162 | bus, tram | 22 | 448 | 80 | 0,0 | 1,1 | 1,9 |
| Łódź | Piotrkowska Centrum | 1,5 | 7,7 | 9,2 | Piotrkowska Centrum | 8 | 199 | tram | 13 | 150 | 101 | 0,0 | 1,8 | 1,8 |
| Łódź | Łódź Fabryczna | 2,3 | 11,6 | 13,9 | Narutowicza-pl. Dąbrowskiego | 24 | 562 | bus, rail, tram | 28 | 712 | 100 | 0,9 | 2,6 | 5,0 |
| Łódź | Łódź Kaliska | 2,1 | 11,0 | 13,1 | Włókniarzy-Mickiewicza (Dw. Ł. Kaliska) | 28 | 654 | bus, rail, tram | 23 | 494 | 119 | 0,8 | 2,2 | 4,6 |
| Trójmiasto | Gdańsk Główny | 2,7 | 12,2 | 14,9 | Dworzec Główny 01 | 21 | 289 | bus, rail, tram | 40 | 1496 | 194 | 1,5 | 2,9 | 3,9 |
| Trójmiasto | Gdańsk Wrzeszcz | 3,0 | 12,7 | 15,7 | Gdańsk Wrzeszcz | 15 | 455 | bus, rail, tram | 29 | 768 | 109 | 1,6 | 1,8 | 4,1 |
| Trójmiasto | Gdynia Główna | 4,4 | 11,5 | 15,9 | Gdynia Dworzec Gł. PKP - Hala 04 | 29 | 570 | bus, rail, trolleybus | 46 | 1954 | 207 | 2,0 | 2,9 | 6,5 |
| GZM | Katowice Rynek | 2,5 | 9,8 | 12,3 | Katowice Aleja Korfantego | 7 | 317 | bus, tram | 36 | 1216 | 146 | 1,9 | 2,0 | 3,8 |
| GZM | Katowice Dworzec | 2,4 | 14,7 | 17,1 | Katowice Dworzec | 19 | 417 | bus, rail | 50 | 2432 | 147 | 1,5 | 2,0 | 5,8 |
| GZM | Sosnowiec Główny | 1,0 | 16,8 | 17,8 | Sosnowiec Dworzec PKP | 8 | 111 | bus, rail, tram | 30 | 862 | 85 | 0,4 | 1,0 | 1,7 |

| Węzeł | Przejścia (z kierunkami): mediana | Przejścia z sygnalizacją, % | Ruchy ze schodami, % | Ruchy z dojściem bez schodów w OSM, % | Pary z tunelem, % | Czekanie 7–9: mediana, min | Dojście z kierunkami + czekanie 7–9: mediana, min | Najlepsza para + czekanie, ważone kursami, min | Średnia odległość między słupkami po sieci, m | Możliwe skomunikowania / pary sprawdzone |
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

**Znane węzły po rewizjach** (7–9; czekanie losowe i na przesiadkę jako średnie ważone kursami na tym samym zbiorze ruchów, mediana i P90 czekania na przesiadkę ważone, pasmo uogólnionego czasu w minutach równoważnych jeździe, W6 przy sygnalizacji 70 % i 50 %):

| Węzeł | Czekanie przy losowym przyjściu, min | Czekanie na przesiadkę, średnia, min | Czekanie na przesiadkę, mediana, min | Czekanie na przesiadkę, P90, min | Uogólniony czas: niski, min | środkowy, min | wysoki, min | Przejścia na ruch, średnia | W6, % (sygn. 70) | W6, % (sygn. 50) | Ruchy częste × częste (≤ 10 min), % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Centrum | 5,5 | 5,5 | 3,3 | 12,2 | 16,9 | 26,3 | 31,3 | 0,3 | 93 | 91 | 20 |
| Dworzec Centralny | 7,3 | 7,3 | 3,9 | 12,9 | 19,4 | 28,8 | 33,8 | 1,1 | 81 | 74 | 14 |
| Dworzec Wileński | 4,7 | 4,7 | 3,9 | 9,9 | 14,6 | 23,6 | 28,6 | 0,4 | 87 | 79 | 33 |
| Dworzec Gdański | 5,2 | 5,2 | 2,7 | 9,5 | 16,6 | 26,1 | 31,1 | 0,7 | 81 | 80 | 26 |
| Rondo Mogilskie | 6,1 | 6,0 | 4,9 | 12,5 | 16,8 | 25,8 | 30,8 | 1,1 | 34 | 34 | 6 |
| Dworzec Główny Zachód (Basztowa, Pawia) | 3,8 | 4,0 | 4,3 | 7,6 | 12,1 | 20,7 | 25,7 | 0,8 | 30 | 30 | 29 |
| Kraków Główny (kolej) | 13,3 | 13,8 | 7,9 | 40,7 | 28,4 | 37,9 | 42,9 | 0,5 | 77 | 77 | 0 |
| Rondo Grunwaldzkie | 10,2 | 10,2 | 6,9 | 20,0 | 22,0 | 30,8 | 35,8 | 1,4 | 70 | 50 | 1 |
| Podgórze SKA | 9,2 | 9,1 | 6,2 | 16,0 | 20,4 | 29,2 | 34,2 | 1,2 | 65 | 47 | 1 |
| Borek Fałęcki | 14,7 | 14,9 | 8,9 | 39,9 | 29,4 | 38,5 | 43,5 | 0,7 | 72 | 59 | 0 |
| Galeria Dominikańska | 7,3 | 7,1 | 6,0 | 11,5 | 18,1 | 27,1 | 32,1 | 0,9 | 82 | 72 | 1 |
| pl. Grunwaldzki | 7,2 | 7,1 | 6,4 | 12,4 | 17,2 | 25,8 | 30,8 | 0,6 | 82 | 70 | 0 |
| Dworzec Główny | 10,8 | 10,7 | 6,9 | 21,5 | 24,7 | 34,2 | 39,2 | 1,2 | 64 | 55 | 0 |
| Rondo Kaponiera | 6,1 | 6,0 | 5,6 | 11,3 | 16,6 | 25,7 | 30,7 | 1,1 | 68 | 63 | 30 |
| Poznań Główny / Dworzec Zachodni | 9,8 | 9,7 | 6,0 | 18,6 | 22,5 | 31,7 | 36,7 | 1,0 | 80 | 69 | 11 |
| Rondo Rataje | 11,0 | 11,0 | 6,5 | 25,9 | 22,4 | 30,9 | 35,9 | 0,9 | 66 | 48 | 4 |
| Piotrkowska Centrum | 7,7 | 7,9 | 7,8 | 13,8 | 18,1 | 26,8 | 31,8 | 0,9 | 62 | 46 | 0 |
| Łódź Fabryczna | 11,6 | 11,7 | 8,5 | 25,9 | 24,9 | 33,9 | 38,9 | 1,3 | 59 | 45 | 0 |
| Łódź Kaliska | 11,0 | 10,9 | 8,1 | 19,9 | 23,8 | 32,8 | 37,8 | 1,1 | 73 | 56 | 0 |
| Gdańsk Główny | 12,2 | 12,3 | 6,6 | 32,7 | 26,2 | 35,4 | 40,4 | 0,7 | 82 | 75 | 1 |
| Gdańsk Wrzeszcz | 12,7 | 12,7 | 6,9 | 33,8 | 27,3 | 36,6 | 41,6 | 1,9 | 50 | 47 | 1 |
| Gdynia Główna | 11,5 | 11,4 | 7,8 | 23,8 | 27,1 | 37,1 | 42,1 | 1,4 | 70 | 64 | 0 |
| Katowice Rynek | 9,8 | 9,5 | 8,1 | 20,1 | 22,3 | 31,5 | 36,5 | 1,7 | 65 | 48 | 1 |
| Katowice Dworzec | 14,7 | 14,7 | 11,7 | 28,1 | 29,5 | 38,6 | 43,6 | 0,6 | 74 | 71 | 0 |
| Sosnowiec Główny | 16,8 | 16,6 | 12,6 | 39,0 | 30,9 | 39,3 | 44,3 | 0,0 | 100 | 100 | 0 |

**Czytanie.** We wszystkich znanych węzłach czekanie na przesiadkę równa się czekaniu przy losowym przyjściu z dokładnością do 0,5 min, także na dworcach z liniami podmiejskimi (Kraków Główny 13,8 wobec 13,3 min, Katowice Dworzec 14,7 wobec 14,7). P90 przekracza 30 min na Krakowie Głównym, Borku Fałęckim, Gdańsku Głównym, Wrzeszczu i Sosnowcu Głównym: tam co dziesiąta przesiadka to czekanie na rzadką linię. Pasmo uogólnionego czasu wynosi od 12,1–25,7 min (Dworzec Główny Zachód w Krakowie) do 30,9–44,3 min (Sosnowiec Główny). Wysoki W6 w węzłach z przejściami podziemnymi (Centrum 93 %, Dworzec Wileński 87 %, Sosnowiec 100 %) i niski tam, gdzie przechodzi się po zebrach (Rondo Mogilskie 34 %, Dworzec Główny Zachód 30 %). Ruchów częste × częste (≤ 10 min) jest najwięcej w Warszawie (do 33 % na Dworcu Wileńskim) i na Rondzie Kaponiera (30 %).

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
- Po rewizjach: `timed_both15_mode_pairs.csv`, `timed_both15_nodes.csv`, `timed_night_control.csv`, `pulse_nodes.csv`; szczegóły węzłów `results/web/transfer_detail/`; kod `pipeline/transfer_detail.py`, `transfer_md_rev.py`.

## 13. Czekanie na przesiadkę po rzeczywistym przyjeździe (rewizja 1)

Reguła 10. Obszar pokryty, 20 zespołów z największą liczbą odjazdów, okno 7–9. Czekanie przy losowym przyjściu i na przesiadkę to średnie ważone kursami w zespole, potem średnia po zespołach; mediana i P90 to ważone wartości zespołu, potem mediana po zespołach.

| Aglomeracja | Dojście, min | Czekanie przy losowym przyjściu, min | Czekanie na przesiadkę, min | Różnica (przesiadka − losowe), min | Czekanie na przesiadkę: mediana, min | Czekanie na przesiadkę: P90, min |
|---|---|---|---|---|---|---|
| Warszawa | 2,5 | 5,6 | 5,6 | -0,01 | 4,0 | 10,6 |
| Kraków | 2,1 | 8,2 | 8,2 | -0,01 | 6,3 | 14,3 |
| Wrocław | 1,5 | 8,4 | 8,3 | -0,07 | 6,9 | 13,4 |
| Poznań | 1,6 | 7,1 | 7,1 | -0,05 | 6,0 | 12,7 |
| Łódź | 2,1 | 10,9 | 10,9 | 0,01 | 8,0 | 17,5 |
| Trójmiasto | 2,9 | 10,5 | 10,4 | -0,07 | 7,7 | 21,7 |
| GZM | 1,8 | 15,6 | 15,6 | -0,04 | 11,7 | 28,8 |

**Czytanie.** Czekanie po rzeczywistym przyjeździe linii dowożącej jest średnio takie samo jak czekanie przy losowym przyjściu: różnica w 20 największych węzłach wynosi od −0,07 do +0,01 min w każdym mieście. Rozkłady nie są więc ani skomunikowane, ani „rozjechane”: przyjazd linii dowożącej trafia w losowe miejsce odstępu linii odjazdowej. Sprawdzono, że to nie artefakt definicji: na tym samym zbiorze ruchów mediana czekania na przesiadkę jest wyraźnie niższa od średniej (Warszawa 4,0 wobec 5,6 min, GZM 11,7 wobec 15,6 min), a 90. percentyl prawie dwa razy wyższy (10,6–28,9 min), czyli rozkład jest prawoskośny tak, jak przy przyjściu losowym. Wniosek z sekcji 3 się nie zmienia: o długości przesiadki decyduje częstotliwość linii docelowej.
- P90 pokazuje to, czego średnia nie pokazuje: w Trójmieście i GZM co dziesiąta przesiadka w największych węzłach kosztuje ponad 21 i 28 min czekania, w Warszawie 10,6 min.
- Ograniczenie: czasy z rozkładu w pełnych minutach, bez opóźnień; przyjazd linii A to przyjazd na pierwszy słupek jej przejazdu przez zespół, odjazd B to odjazd z ostatniego, więc dla linii z dwoma słupkami w zespole czas może być przesunięty o 1–2 min.

## 14. Uogólniony czas przesiadki: pasmo z opublikowanych wag (rewizja 2)

Reguła 11. Z typowej przesiadki 7–9 w 20 największych zespołach (te same składowe co w sekcji 3, przed zaokrągleniem). Kolumny „× waga” pokazują, ile każda składowa wnosi w wariancie środkowym. Wartości nie są używane do układania węzłów ani miast w ranking.

| Aglomeracja | Dojście, min | Czekanie, min | Dojście × 1,66 | Czekanie × 1,47 | Kara P (środkowa), min | Pasmo: niski, min równoważnych | środkowy | wysoki |
|---|---|---|---|---|---|---|---|---|
| Warszawa | 2,5 | 5,6 | 4,2 | 8,3 | 13 | 16,3 | 25,5 | 30,5 |
| Kraków | 2,1 | 8,2 | 3,5 | 12,1 | 13 | 19,6 | 28,5 | 33,5 |
| Wrocław | 1,5 | 8,4 | 2,5 | 12,3 | 13 | 19,1 | 27,8 | 32,8 |
| Poznań | 1,6 | 7,1 | 2,7 | 10,5 | 13 | 17,5 | 26,2 | 31,2 |
| Łódź | 2,1 | 10,9 | 3,4 | 16,0 | 13 | 23,4 | 32,4 | 37,4 |
| Trójmiasto | 2,9 | 10,5 | 4,9 | 15,4 | 13 | 24,0 | 33,3 | 38,3 |
| GZM | 1,8 | 15,6 | 3,0 | 23,0 | 13 | 30,1 | 39,0 | 44,0 |

**Czytanie.** W 20 największych węzłach uogólniony czas przesiadki wynosi od 16,3–30,5 min (Warszawa) do 30,2–44,0 min równoważnych jeździe (GZM). Stała kara (5–18 min) jest tego samego rzędu co ważone czekanie (8–23 min), a ważone dojście dodaje tylko 2–5 min. Szerokość pasma (14 min w każdym mieście) wynika prawie w całości z niepewności kary, nie z danych o węzłach; różnica między miastami (do 14 min) to prawie w całości różnica czekania. Pasmo potwierdza wniosek przeglądu: czekanie, nie dojście, rozstrzyga porównanie miast.
- Kara jest jedna dla wszystkich ruchów (bez rozróżnienia autobus–tramwaj–kolej): Ortelli i in. 2026 pokazują, że kary zależne od środka mierzą głównie preferencję środka, a nie samą przesiadkę.
- Pasmo nie jest wskaźnikiem jakości węzła i nie służy do rankingu; dla dwóch węzłów o tym samym dojściu i czekaniu jest identyczne, bo kara nie zależy od węzła.

## 15. Przejścia w skali AMPTI W6 (rewizja 3)

Przypisanie tagów OSM do klas W6 (reguła 12; `pipeline/transfer_walk.py`). Klasa przejścia wynika z tagów węzłów przejścia i przylegającej drogi `footway=crossing` razem, w tej kolejności:

| Klasa | W6, % | Tagi OSM |
|---|---|---|
| bezkolizyjne (przejście podziemne, kładka) | 100 | ciąg krawędzi pieszych z `tunnel=*` (bez `building_passage`) na drodze; ciąg krawędzi z `bridge=*`, który w rzucie przecina jezdnię z grafu (chodnik na moście drogowym i kładka nad rzeką się nie liczą) |
| z sygnalizacją | 70 lub 50 | `crossing=traffic_signals` / `pelican` / `toucan` / `pegasus`, `crossing:signals=yes`, `crossing_ref=pelican` / `toucan` / `puffin`, `highway=traffic_signals` |
| zebra bez sygnalizacji | 30 | `crossing=marked` / `zebra` / `uncontrolled`, `crossing_ref=zebra`, `crossing:markings=*` inne niż `no` |
| niewyznakowane | 0 | `crossing=unmarked` / `informal`, `crossing:markings=no` |
| nieznane (bez oceny) | — | przejście przez jezdnię lub torowisko bez żadnej z tych wartości (węzeł bez tagu, `highway=crossing` bez wartości, przejazd kolejowy bez wartości) |

Pokrycie: (a) w całym grafie pieszym: odsetek węzłów, w których osobno zmapowany chodnik przecina jezdnię, z tagiem węzła pozwalającym nadać klasę (bez tagów dróg `footway=crossing`, więc to dolna granica); (b) na dojściach (reguła główna, obszar pokryty, wszystkie ruchy): rozkład klas przejść.

| Aglomeracja | Graf: węzły chodnik × jezdnia z klasą, % | Dojścia: przejść (z bezkolizyjnymi) | bezkolizyjne, % | z sygnalizacją, % | zebra, % | niewyznakowane, % | nieznane, % | z klasą W6, % |
|---|---|---|---|---|---|---|---|---|
| Warszawa | 75,6 | 105 183 | 22,4 | 41,8 | 30,4 | 2,5 | 2,9 | 97,1 |
| Kraków | 74,8 | 50 103 | 11,6 | 51,5 | 27,8 | 4,0 | 5,0 | 95,0 |
| Wrocław | 58,6 | 40 440 | 17,6 | 45,4 | 28,0 | 1,7 | 7,3 | 92,7 |
| Poznań | 78,9 | 19 222 | 15,9 | 38,3 | 36,0 | 4,6 | 5,2 | 94,8 |
| Łódź | 64,3 | 32 175 | 10,1 | 51,9 | 27,7 | 2,0 | 8,3 | 91,7 |
| Trójmiasto | 65,9 | 52 032 | 25,8 | 38,0 | 28,3 | 5,1 | 2,7 | 97,3 |
| GZM | 69,7 | 95 670 | 17,7 | 22,7 | 47,8 | 4,4 | 7,4 | 92,6 |

Wynik W6 (średnia po ruchach z ocenionym przejściem, ważona kursami; obszar pokryty i 20 największych zespołów, średnia wartości zespołów) obok zwykłej mediany liczby przejść:

| Aglomeracja | W6, %, sygnalizacja 70 | W6, %, sygnalizacja 50 | Top 20: W6, % (70) | Top 20: W6, % (50) | Top 20: przejścia na ruch, mediana |
|---|---|---|---|---|---|
| Warszawa | 70 | 57 | 73 | 61 | 1,0 |
| Kraków | 59 | 47 | 67 | 55 | 1,0 |
| Wrocław | 64 | 51 | 68 | 52 | 1,0 |
| Poznań | 61 | 50 | 61 | 49 | 1,0 |
| Łódź | 62 | 49 | 65 | 51 | 1,0 |
| Trójmiasto | 66 | 56 | 61 | 52 | 1,0 |
| GZM | 54 | 47 | 59 | 54 | 0,5 |

**Czytanie.** Tagi OSM pozwalają nadać klasę W6 92–97 % przejść na policzonych dojściach; w całym grafie pieszym 59–79 % węzłów, w których chodnik przecina jezdnię, ma tag klasy na samym węźle (Wrocław najniżej). Niewyznakowanych przejść na dojściach jest 2–5 %, nieznanych 3–8 %. Średni wynik W6 na dojściach to 54–70 % przy sygnalizacji liczonej jako 70 % i 47–57 % przy 50 %; najniżej w GZM, gdzie tylko 23 % przejść na dojściach ma sygnalizację (Kraków i Łódź 52 %), a 48 % to zebry.
- Udział przejść bezkolizyjnych (10–26 %) obejmuje przejścia podziemne i tunele stacji metra i kolei, którymi prowadzi najkrótsza droga; dlatego Warszawa Centrum ma W6 93 %, a Sosnowiec Główny 100 % (dojście tunelem pod torami, zero przejść w poziomie jezdni). Kładki nad torami nie są wykrywane (tory nie należą do grafu).
- Sprawdzono Rondo Mogilskie (W6 34 %): w drogach macierzy jest 14 przejść, wszystkie to zebry bez sygnalizacji przez torowisko i jezdnie na poziomie tramwajów; Rondo Grunwaldzkie (70 / 50 %): 18 przejść z sygnalizacją i 1 bez klasy. Zgodności z terenem nie sprawdzano.
- Ruch bez przejścia nie ma oceny W6, więc węzeł, w którym wszystkie przesiadki są na wspólnym słupku, ma W6 „brak danych” i 0 przejść: obie liczby trzeba czytać razem.

## 16. Ruchy „częste × częste” (rewizja 4)

Reguła 13. Udział ruchów przesiadkowych (bez wag), w których obie linie kursują w swoich kierunkach w godzinach 7–9 średnio co 10 (15) min lub częściej; obszar pokryty i 20 największych zespołów.

| Aglomeracja | Ruchy | Obie linie co ≤ 10 min, % | Obie co ≤ 15 min, % | Top 20: ≤ 10 min, % | Top 20: ≤ 15 min, % |
|---|---|---|---|---|---|
| Warszawa | 82 934 | 10,4 | 32,8 | 17,1 | 43,2 |
| Kraków | 43 242 | 1,2 | 24,5 | 2,5 | 35,4 |
| Wrocław | 30 441 | 0,1 | 28,3 | 0,2 | 38,5 |
| Poznań | 18 241 | 6,7 | 22,3 | 17,0 | 47,7 |
| Łódź | 27 090 | 0,0 | 17,2 | 0,0 | 24,4 |
| Trójmiasto | 36 946 | 0,7 | 6,7 | 1,1 | 8,4 |
| GZM | 105 180 | 0,1 | 1,2 | 0,2 | 2,2 |

**Czytanie.** Ruchów, w których obie linie kursują w szczycie co 10 min lub częściej, jest mało poza Warszawą (10,4 % ruchów, 17 % w 20 największych węzłach) i Poznaniem (6,7 %, 17 %); w Krakowie 1,2 %, we Wrocławiu, Łodzi, Trójmieście i GZM poniżej 1 %. Przy progu 15 min udział rośnie do 17–33 % w pięciu miastach, ale w Trójmieście (6,7 %) i GZM (1,2 %) zostaje mały. To jest ten zbiór przesiadek, który literatura (Walker, Mees, SNAMUTS) uważa za „tanie” i na którym opiera się sieć z przesiadkami.
- Próg 10 min jest ostry: linia co 10 min ma w oknie 7–9 dokładnie 12 kursów, więc jeden kurs mniej (np. co 10–11 min) wyklucza ruch. Wrocław (tramwaje zwykle co 12 min) i Łódź (co 12–15 min) mają przez to prawie zero; próg 15 min jest odporniejszy.
- Udział liczony po ruchach bez wag: rzadkie linie podmiejskie zwiększają mianownik, zwłaszcza w GZM (105 tys. ruchów).

## 17. Test skomunikowań po przeglądzie (rewizja 5)

Reguła 14. (a) Pary, w których obie linie kursują co ≥ 15 min (6–20), obszar pokryty; „w najlepszych 10 %” = rzeczywisty rozkład daje krótsze czekanie niż co najmniej 90 % przesunięć; bez koordynacji ok. 10 %. p = jednostronny test dwumianowy (czy udział jest większy niż 10 %).

| Aglomeracja | Pary (obie linie co ≥ 15 min) | W najlepszych 10 % przesunięć, % | p | Kandydaci (reguła 9) | Czekanie rzeczywiste, średnia, min | Czekanie przy losowym przyjściu, min |
|---|---|---|---|---|---|---|
| Warszawa | 25324 | 12,1 | < 0,001 | 479 | 25,2 | 26,1 |
| Kraków | 26713 | 11,2 | < 0,001 | 388 | 23,6 | 23,8 |
| Wrocław | 8903 | 12,8 | < 0,001 | 124 | 23,7 | 24,8 |
| Poznań | 10192 | 12,5 | < 0,001 | 84 | 26,0 | 26,6 |
| Łódź | 15471 | 12,7 | < 0,001 | 243 | 22,9 | 23,2 |
| Trójmiasto | 18424 | 12,5 | < 0,001 | 188 | 22,2 | 22,8 |
| GZM | 82287 | 11,5 | < 0,001 | 2122 | 25,8 | 26,6 |

Po rodzajach środków (tylko układy z co najmniej 200 parami; wszystkie w `timed_both15_mode_pairs.csv`):

| Aglomeracja | Przesiadka | Pary | W najlepszych 10 %, % | p |
|---|---|---|---|---|
| Warszawa | autobus → autobus | 20795 | 11,3 | < 0,001 |
| Warszawa | autobus → kolej | 1350 | 15,3 | < 0,001 |
| Warszawa | autobus → tramwaj | 433 | 22,4 | < 0,001 |
| Warszawa | kolej → autobus | 1055 | 13,5 | < 0,001 |
| Warszawa | kolej → kolej | 952 | 8,7 | 0,917 |
| Warszawa | tramwaj → autobus | 349 | 13,2 | 0,033 |
| Warszawa | tramwaj → tramwaj | 256 | 39,8 | < 0,001 |
| Kraków | autobus → autobus | 20943 | 11,0 | < 0,001 |
| Kraków | autobus → kolej | 467 | 12,2 | 0,068 |
| Kraków | autobus → tramwaj | 1891 | 13,3 | < 0,001 |
| Kraków | kolej → autobus | 354 | 16,4 | < 0,001 |
| Kraków | tramwaj → autobus | 1893 | 12,8 | < 0,001 |
| Kraków | tramwaj → tramwaj | 991 | 6,3 | 1,000 |
| Wrocław | autobus → autobus | 7869 | 12,7 | < 0,001 |
| Wrocław | autobus → kolej | 403 | 12,7 | 0,049 |
| Wrocław | kolej → autobus | 261 | 13,4 | 0,046 |
| Poznań | autobus → autobus | 9514 | 12,0 | < 0,001 |
| Poznań | autobus → kolej | 252 | 18,7 | < 0,001 |
| Łódź | autobus → autobus | 8674 | 14,1 | < 0,001 |
| Łódź | autobus → kolej | 451 | 15,1 | < 0,001 |
| Łódź | autobus → tramwaj | 1949 | 11,7 | 0,008 |
| Łódź | kolej → autobus | 321 | 14,3 | 0,009 |
| Łódź | tramwaj → autobus | 2011 | 14,6 | < 0,001 |
| Łódź | tramwaj → tramwaj | 1738 | 4,3 | 1,000 |
| Trójmiasto | autobus → autobus | 10342 | 12,8 | < 0,001 |
| Trójmiasto | autobus → kolej | 735 | 10,6 | 0,307 |
| Trójmiasto | autobus → tramwaj | 336 | 17,6 | < 0,001 |
| Trójmiasto | autobus → trolejbus | 2101 | 10,0 | 0,485 |
| Trójmiasto | kolej → autobus | 604 | 14,2 | < 0,001 |
| Trójmiasto | tramwaj → autobus | 335 | 19,7 | < 0,001 |
| Trójmiasto | trolejbus → autobus | 2143 | 15,1 | < 0,001 |
| Trójmiasto | trolejbus → trolejbus | 1337 | 5,6 | 1,000 |
| GZM | autobus → autobus | 69160 | 11,4 | < 0,001 |
| GZM | autobus → kolej | 1408 | 11,2 | 0,083 |
| GZM | autobus → tramwaj | 3252 | 12,4 | < 0,001 |
| GZM | autobus → trolejbus | 1443 | 11,9 | 0,010 |
| GZM | kolej → autobus | 1093 | 13,2 | < 0,001 |
| GZM | tramwaj → autobus | 3222 | 13,1 | < 0,001 |
| GZM | tramwaj → tramwaj | 510 | 5,7 | 1,000 |
| GZM | trolejbus → autobus | 1463 | 11,0 | 0,109 |
| GZM | trolejbus → trolejbus | 416 | 15,9 | < 0,001 |

Węzły z co najmniej 20 parami takich linii: 1876; z udziałem istotnie większym niż 10 % (p < 0,001; przy 1876 testach przypadkiem ok. 1,9): 40.

| Aglomeracja | Węzeł | Pary | W najlepszych 10 %, % | p |
|---|---|---|---|---|
| Warszawa | Dw. Wschodni (Kijowska) | 749 | 19,8 | < 0,001 |
| Trójmiasto | Dworzec Główny 01 | 798 | 17,0 | < 0,001 |
| Warszawa | Radzymin, PKP Radzymin | 40 | 45,0 | < 0,001 |
| GZM | Będzin Kościuszki | 689 | 16,5 | < 0,001 |
| Warszawa | Dw. Zachodni | 389 | 18,3 | < 0,001 |
| Trójmiasto | Obłuże Centrum 01 | 271 | 19,2 | < 0,001 |
| Warszawa | Królikarnia | 37 | 37,8 | < 0,001 |
| Wrocław | Broniewskiego | 191 | 20,4 | < 0,001 |
| Trójmiasto | Plac Solidarności 01 | 328 | 17,4 | < 0,001 |
| Wrocław | Bałtycka | 87 | 25,3 | < 0,001 |
| Poznań | Dworzec Zachodni | 114 | 22,8 | < 0,001 |
| GZM | Bytom Strzelców Bytomskich | 500 | 15,6 | < 0,001 |
| Trójmiasto | Gdynia Dworzec Gł. PKP - Hala 04 | 1267 | 13,3 | < 0,001 |
| Łódź | Narutowicza-pl. Dąbrowskiego | 586 | 15,0 | < 0,001 |
| GZM | Będzin Dworzec | 922 | 13,9 | < 0,001 |

(b) Test pulsu w węźle (zespoły z co najmniej 20 odjazdami linii co ≥ 15 min i co najmniej dwiema takimi liniami; przy braku pulsu ok. 1 % zespołów przekracza próg przypadkiem):

| Aglomeracja | 6–20: zespoły | z pulsem | % | 23–04:30: zespoły | z pulsem | % |
|---|---|---|---|---|---|---|
| Warszawa | 1946 | 13 | 0,7 | 421 | 24 | 5,7 |
| Kraków | 1011 | 9 | 0,9 | 39 | 1 | 2,6 |
| Wrocław | 514 | 5 | 1,0 | 143 | 11 | 7,7 |
| Poznań | 870 | 6 | 0,7 | 89 | 5 | 5,6 |
| Łódź | 728 | 3 | 0,4 | 153 | 6 | 3,9 |
| Trójmiasto | 699 | 5 | 0,7 | 54 | 2 | 3,7 |
| GZM | 2398 | 14 | 0,6 | 12 | 0 | 0,0 |

Noc, zespoły z pulsem o największej liczbie odjazdów:

| Aglomeracja | Zespół | Odjazdy 23–04:30 | Linie | Minuta pulsu (cykl 30 min) | Udział w 3 min, % | Próg (kwantyl 0,99), % |
|---|---|---|---|---|---|---|
| Warszawa | Dw. Centralny | 319 | 35 | :15 | 61,1 | 27,0 |
| Warszawa | Centrum | 248 | 22 | :18 | 35,1 | 27,4 |
| Warszawa | Metro Świętokrzyska | 208 | 17 | :18 | 38,9 | 28,4 |
| Wrocław | DWORZEC GŁÓWNY | 205 | 16 | :03 | 41,0 | 27,3 |
| Wrocław | DWORZEC AUTOBUSOWY | 193 | 14 | :19 | 31,1 | 25,4 |
| Łódź | Kościuszki-6 Sierpnia | 165 | 12 | :00 | 100,0 | 53,3 |
| Poznań | Most Teatralny | 152 | 11 | :00 | 50,0 | 36,2 |
| Warszawa | Pl. Zawiszy | 144 | 13 | :20 | 34,0 | 29,9 |
| Warszawa | Metro Ratusz Arsenał | 140 | 13 | :21 | 47,1 | 32,9 |
| Wrocław | Sanocka | 132 | 13 | :00 | 75,8 | 37,9 |

Dzień, zespoły z pulsem o największej liczbie odjazdów:

| Aglomeracja | Zespół | Odjazdy 6–20 (linie co ≥ 15 min) | Linie | Minuta pulsu | Udział w 3 min, % | Próg, % |
|---|---|---|---|---|---|---|
| Warszawa | Mińsk Mazowiecki /Dw. PKP/ | 327 | 25 | :28 | 28,4 | 26,0 |
| Kraków | Krowodrza Górka P+R | 302 | 11 | :00 | 31,5 | 30,1 |
| GZM | Józefowiec Liceum | 272 | 7 | :24 | 40,8 | 38,6 |
| GZM | Michałkowice Urząd Miasta | 267 | 6 | :24 | 35,6 | 32,2 |
| GZM | Mydlice Wolska | 245 | 8 | :10 | 24,5 | 24,1 |
| Łódź | Kopcińskiego-Narutowicza | 235 | 20 | :17 | 23,0 | 22,6 |
| Poznań | Karolin PKM | 214 | 8 | :13 | 17,8 | 17,3 |
| Trójmiasto | Nowolipie 01 | 209 | 5 | :17 | 25,4 | 24,4 |
| Warszawa | Bogatki | 189 | 6 | :17 | 26,5 | 24,9 |
| Warszawa | 11 Listopada | 184 | 7 | :04 | 29,9 | 29,3 |

(c) Kontrola dodatnia, test par w nocy (pary linii nocnych co 15–60 min, okno 23:00–04:30):

| Aglomeracja | Pary | W najlepszych 10 %, % | p | Czekanie rzeczywiste, min | Czekanie przy losowym przyjściu, min |
|---|---|---|---|---|---|
| Warszawa | 8171 | 31,9 | < 0,001 | 35,2 | 38,8 |
| Kraków | 351 | 54,1 | < 0,001 | 31,2 | 37,1 |
| Wrocław | 2512 | 36,8 | < 0,001 | 36,6 | 38,9 |
| Poznań | 660 | 31,5 | < 0,001 | 28,7 | 31,5 |
| Łódź | 1048 | 41,4 | < 0,001 | 27,4 | 37,3 |
| Trójmiasto | 340 | 20,0 | < 0,001 | 31,2 | 34,3 |
| GZM | 145 | 22,8 | < 0,001 | 27,9 | 48,0 |

| Aglomeracja | Zespół (noc) | Pary | W najlepszych 10 %, % | p | Czekanie rzeczywiste, min | Czekanie przy losowym przyjściu, min |
|---|---|---|---|---|---|---|
| Warszawa | Dw. Centralny | 1119 | 19,8 | < 0,001 | 29,5 | 31,7 |
| Warszawa | Centrum | 488 | 24,8 | < 0,001 | 32,1 | 36,2 |
| Warszawa | Metro Świętokrzyska | 339 | 37,8 | < 0,001 | 34,2 | 37,5 |
| Wrocław | DWORZEC GŁÓWNY | 228 | 51,3 | < 0,001 | 45,6 | 44,6 |
| Warszawa | Metro Młociny | 212 | 50,0 | < 0,001 | 41,3 | 49,5 |
| Warszawa | Emilii Plater | 209 | 29,7 | < 0,001 | 20,7 | 25,7 |
| Wrocław | DWORZEC AUTOBUSOWY | 199 | 20,6 | < 0,001 | 31,1 | 32,9 |
| Warszawa | Kijowska | 198 | 41,4 | < 0,001 | 33,6 | 49,5 |
| Warszawa | Metro Ratusz Arsenał | 168 | 45,2 | < 0,001 | 39,6 | 40,4 |
| Warszawa | Dw. Wileński | 139 | 33,1 | < 0,001 | 35,4 | 36,5 |

**Czytanie. Czy coś wykryto?** W dzień nie. (a) W parach linii kursujących co ≥ 15 min udział w najlepszych 10 % przesunięć wynosi 11,2–12,8 %, czyli 1–3 pkt proc. ponad przypadek. Przy dziesiątkach tysięcy par jest to „istotne” w teście dwumianowym, ale pary nie są niezależne (te same linie w wielu zespołach), a zysk praktycznie zerowy: średnie czekanie rzeczywiste jest o 0,2–1,1 min krótsze od czekania przy losowym przyjściu. Wysokie udziały tramwaj → tramwaj w Warszawie (40 %) i Poznaniu (50 %) dotyczą rzadkich kursów tramwajowych (czekanie losowe ok. 51–52 min: zjazdy do zajezdni, kursy wieczorne), a nie linii w ruchu; nie sprawdzono, ile to kursy przechodzące. (b) Test pulsu w dzień: 0,4–1,0 % zespołów, czyli tyle, ile daje przypadek przy progu 0,99; żadne z miast nie ma w dzień węzła z pulsem linii rzadkich.
- **Kontrola dodatnia działa.** W nocy test pulsu wskazuje węzły, w których linie nocne spotykają się o stałej minucie: Warszawa Dw. Centralny (61 % odjazdów w 3 minutach cyklu 30 min, o :15 i :45, wobec progu 27 %), Centrum i Metro Świętokrzyska; Wrocław Dworzec Główny i Dworzec Autobusowy; Łódź Kościuszki-6 Sierpnia; Poznań Most Teatralny i Rondo Kaponiera (o pełnej i pół godzinie). Test par w nocy też daje wyraźną nadwyżkę (20–54 % par w najlepszych 10 %, czekanie rzeczywiste 2–20 min krótsze od losowego). Detektor widzi więc puls, gdy puls istnieje; brak wyniku w dzień to brak koordynacji, nie słabość testu.
- **Dlaczego test par jest w nocy słabszy od testu pulsu.** Na Dworcu Centralnym rozkład koduje spotkanie jako przyjazd = odjazd w tej samej minucie (:15) na różnych słupkach, bez postoju; po dodaniu dojścia przyjeżdżający „spóźnia się” na odjazd, więc w teście par tylko 20 % par na Centralnym trafia do najlepszych 10 %. Test pulsu nie używa dojścia ani czasu przyjazdu, dlatego tę koordynację wykrywa. To ograniczenie danych GTFS (brak czasu postoju), nie sieci.
- Puls przenosi się wzdłuż tras: zespoły o stałym czasie jazdy od węzła pulsu też „pulsują” (np. Pl. Zawiszy, Metro Ratusz Arsenał w nocy). Lista: `pulse_nodes.csv`; nocne pary: `timed_night_control.csv`.

## 18. Szczegóły węzłów na mapę

Zespoły z co najmniej 20 odjazdami na godzinę 6–20 w FUA i w masce GTFS, z co najmniej jednym ruchem między liniami; plik na aglomerację `results/web/transfer_detail/<agg>.json` i indeks `index.json` (format w docstringu `pipeline/transfer_detail.py`).

| Aglomeracja | Zespoły | Drogi piesze | Ruchy w macierzach | Rozmiar, MB |
|---|---|---|---|---|
| Warszawa | 533 | 3892 | 13519 | 2,12 |
| Kraków | 218 | 1732 | 5637 | 0,86 |
| Wrocław | 225 | 1076 | 4977 | 0,66 |
| Poznań | 118 | 578 | 3035 | 0,39 |
| Łódź | 181 | 1179 | 4472 | 0,67 |
| Trójmiasto | 172 | 1266 | 4410 | 0,74 |
| GZM | 310 | 1848 | 9362 | 1,23 |
| Razem | 1757 | 11571 | 45412 | 6,66 |

Rozmiar plików mieści się w limicie 3 MB (największy: Warszawa). Drogi są zapisane tylko dla par słupków, które są najlepszą parą któregoś ruchu z macierzy (do 8 kierunków przyjazdu × 8 kierunków odjazdu, plus 10 najcięższych ruchów); geometria uproszczona z tolerancją 1,5 m. Na mapie nie sprawdzano wyglądu (brak podłączenia w `web/`, patrz `web/src/features/nodes/README.md`).

