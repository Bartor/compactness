# Próba tras: przesiadki, użycie węzłów, czas pieszo i czekania (walidacja)

Stan: 2026-11-24. Kod: `pipeline/trips_sample.py` (losowanie i routing), `pipeline/trips_analyse.py` (tabele i warstwa), `pipeline/trips_nik.py` (pary NIK), `pipeline/trips_md.py` (tabele w tej nocie). Liczby: CSV w tym katalogu; warstwa `results/layers/node_use.parquet`. Rozkłady: środa 2026-11-25 (feedy z 2026-11-23), sieć R5 „wszystkie feedy” z fazy 3 (kopia w `data/interim/trips/r5/`), OSM 2026-11-22.

Punkt 14 roadmapy i część punktu 4 („węzły wielkości według użycia”). Wcześniejsza próba fazy 3 (`qa/access/access.md` §6) miała 200 par na miasto i nie zapisywała miejsca przesiadki.

## 1. Metoda

- **Podróże.** Każda podróż to niezależne losowanie: komórka startowa 250 m z prawdopodobieństwem proporcjonalnym do liczby mieszkańców (siatka spisowa, komórki FUA, jak starty w fazie 3), szczelina odjazdu [7:00 + m, 7:00 + m + 5 min), m losowane równomiernie z 0–115. Cel: jedna komórka losowana proporcjonalnie do liczby mieszkańców (zbiór „mieszkańcy”) albo miejsc pracy (zbiór „miejsca pracy”, tylko tam, gdzie jest siatka Goliszek: bez GZM; w Trójmieście tylko Gdańsk) spośród komórek osiągalnych w 60 min według reguły fazy 3: min(mediana R5 komunikacją 7–9, sam spacer). Komórka startowa jest wyłączona. Cele: FUA + 15 km (zbiór celów fazy 3).
- **Liczebność:** 15 000 podróży „mieszkańcy” i 5 000 „miejsca pracy” na aglomerację. Próba jest samoważąca (każda podróż ma wagę 1), więc udziały to zwykłe proporcje z przedziałem Wilsona 95 %. Przy udziale ok. 50 % i ok. 12 000 podróży komunikacją połowa szerokości przedziału to ok. 0,9 pkt proc.; dla węzła z udziałem 1 % ok. 0,18 pkt proc.
- **Trasa.** R5 v7.5.1, zadanie regionalne do jednego celu z zapisem ścieżek (`includePathResults`): RAPTOR zwraca dla każdej minuty odjazdu w szczelinie najszybszą ścieżkę (przy równym czasie: mniej przejazdów). Bierzemy najszybszą minutę szczeliny (czas całkowity, potem liczba przejazdów, potem wcześniejsza minuta). Parametry jak w fazie 3: pieszo 5 km/h, dojście i odejście ≤ 12 min, do 8 przejazdów, wszystkie feedy; limit podróży 90 min (żeby szczelina wolniejsza od mediany 7–9 też dała trasę). Zapisujemy linie, przystanki wsiadania i wysiadania, przesiadki, dojście, czekanie i jazdę na każdym odcinku. Dla tras z k ≥ 2 przejazdami liczymy dodatkowo najszybszą trasę z co najwyżej 1, …, k−1 przejazdami (to samo zadanie z `maxRides`), żeby policzyć warianty z karą za przesiadkę.
- **Czemu nie `DetailedItineraries` (r5py).** Wcześniejsza próba trwała ok. 6 s na parę i wymagała 8–16 GB sterty; ścieżki z zadania regionalnego to ok. 0,05 s na podróż i ten sam RAPTOR, który liczy wyniki fazy 3. Przy okazji odpada znane ograniczenie `DetailedItineraries` (brak limitu dojścia 12 min).
- **Klasy podróży.** „KZ”: jest trasa z przejazdem i sam spacer nie jest szybszy (czas spaceru z pamięci podręcznej fazy 3, pełne minuty). „Pieszo szybciej”: spacer jest co najmniej tak szybki albo R5 zwraca tylko spacer, albo brak trasy KZ w 90 min, a cel jest w 60 min pieszo. „Bez trasy w szczelinie”: cel osiągalny w medianie 7–9, ale nie w tej szczelinie w 90 min.
- **Warianty udziału przesiadek.** A (główny): tylko podróże „KZ”. B: podróże „KZ” i „pieszo szybciej”, piesze liczone jako 0 przesiadek. C: każda podróż z trasą KZ, także gdy spacer jest szybszy (najbliżej zapytania w wyszukiwarce: użytkownik pyta o komunikację). Do tego: tylko cele ≤ 30 min i ≤ 45 min (warunkowanie losowania na podzbiorze celów daje losowanie proporcjonalne do mieszkańców w tym podzbiorze, więc to poprawne podpróby), oraz wybór trasy minimalizującej czas + kara 5 lub 10 min za przesiadkę (spośród najszybszych tras z ≤ 1, 2, 3 i 8 przejazdami, czyli frontu czas–przejazdy).
- **Węzły.** Przystanek → klaster 100 m fazy 2 (`frequent.clusters`) → zespół przystanków z `transfer_nodes.parquet` (pole `cluster_ids`); identyfikatory przystanków R5 i GTFS zgadzają się w 100 % (sprawdzone). Przesiadka to para (przystanek wysiadania przejazdu k, przystanek wsiadania przejazdu k+1). Gdy oba końce są w jednym zespole, przesiadka należy do niego; gdy w dwóch różnych, liczy się w obu (oznaczone w `data/interim/trips/transfer_events.csv`, kolumna `where`). Udział węzła = odsetek podróży KZ (wariant A, cele: mieszkańcy), które choć raz przesiadają się w tym zespole.
- **Czas podróży.** Pieszo = dojście + odejście + dojścia przy przesiadkach; czekanie = czekanie na pierwszy pojazd (po wyborze najlepszej minuty w szczelinie) + czekania przy przesiadkach; udziały to stosunek sum (przedziały: bootstrap, 500 powtórzeń, stałe ziarno). R5 dolicza 60 s zapasu na wsiadanie, więc każde czekanie przy przesiadce ma co najmniej 1 min.
- **Determinizm:** stałe ziarna (`SEED = 20261126` plus kod aglomeracji, zbioru i numer podróży), paczki po 500 podróży zapisywane atomowo z podpisem (`.sig`) wejść i kodu; ponowne policzenie zbioru „miejsca pracy” dla Trójmiasta po zmianie kodu dało te same liczności klas (3708 / 271 / 0 / 1021).

## 2. Próba i czas liczenia

<!-- TABLE:sample -->
| Aglomeracja | Cele ważone | Podróży | KZ (wariant A) | Pieszo szybciej | Bez trasy w szczelinie | Brak celu w 60 min | KZ, % podróży | Mediana odległości KZ, km | Routing, min | ms / podróż |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Warszawa | mieszkańcy | 15000 | 11701 | 3269 | 10 | 20 | 78,0 | 7,9 | 20 | 82 |
| Warszawa | miejsca pracy | 5000 | 3822 | 102 | 2 | 1074 | 76,4 | 8,6 | 8 | 91 |
| Kraków | mieszkańcy | 15000 | 10506 | 4470 | 19 | 5 | 70,0 | 6,3 | 13 | 52 |
| Kraków | miejsca pracy | 5000 | 3607 | 165 | 7 | 1221 | 72,1 | 6,5 | 4 | 50 |
| Łódź | mieszkańcy | 15000 | 12012 | 2969 | 17 | 2 | 80,1 | 5,8 | 9 | 36 |
| Łódź | miejsca pracy | 5000 | 4111 | 299 | 2 | 588 | 82,2 | 5,8 | 3 | 37 |
| GZM | mieszkańcy | 15000 | 13295 | 1686 | 13 | 6 | 88,6 | 6,4 | 17 | 69 |
| Wrocław | mieszkańcy | 15000 | 11049 | 3939 | 11 | 1 | 73,7 | 5,5 | 10 | 40 |
| Wrocław | miejsca pracy | 5000 | 3790 | 323 | 4 | 883 | 75,8 | 5,8 | 4 | 47 |
| Poznań | mieszkańcy | 15000 | 11964 | 3013 | 21 | 2 | 79,8 | 5,8 | 12 | 46 |
| Poznań | miejsca pracy | 5000 | 4171 | 223 | 5 | 601 | 83,4 | 6,1 | 4 | 51 |
| Trójmiasto | mieszkańcy | 15000 | 12196 | 2800 | 2 | 2 | 81,3 | 6,4 | 14 | 55 |
| Trójmiasto | miejsca pracy | 5000 | 3708 | 271 | 0 | 1021 | 74,2 | 7,4 | 4 | 44 |
<!-- /TABLE:sample -->

„Brak celu w 60 min” dotyczy głównie zbioru „miejsca pracy”: siatka miejsc pracy obejmuje tylko miasto centralne, a część startów nie ma w 60 min żadnej komórki z miejscami pracy. Te podróże są pominięte (nie są zerami).

## 3. Udział przesiadek a źródła zewnętrzne

**Wynik w skrócie.** W wariancie głównym (najszybsza trasa, cel losowany wśród wszystkich komórek osiągalnych w 60 min) bez przesiadki jedzie tylko 25–40 % podróży komunikacją (Warszawa 24,7 %, Wrocław 40,2 %), średnio 0,73–1,05 przesiadki. To znacznie mniej niż w obu źródłach zewnętrznych: Jakdojade 58–71 % bez przesiadki, WBR 2015 dla Warszawy 57,2 %. Różnica wynika głównie z dwóch decyzji metody, nie z sieci: (1) losowanie celu bez zaniku z odległością daje podróże dłuższe niż rzeczywiste (średnio 40–43 min komunikacją; w badaniu gdańskim GBR 2022 średnia podróż KZ to 36 min), a udział przesiadek rośnie szybko z długością podróży: dla celów ≤ 30 min bez przesiadki jedzie 72–88 %, dla ≤ 45 min 40–59 %; (2) trasa najszybsza bierze przesiadkę, która daje choćby minutę zysku. Gdy połączyć cele ≤ 45 min z karą 5 min za przesiadkę, udział bez przesiadki wynosi 58–74 % i leży blisko Jakdojade (różnica od −7 do +10 pkt proc.), a dla Warszawy blisko WBR 2015 (58,1 % wobec 57,2 %). To dopasowanie jest częściowo z wyboru parametrów (dwa progi sprawdzone, nie dopasowywane), więc nie należy go czytać jako potwierdzenia poziomu, tylko jako pokazanie, że poziom zależy od definicji.

**Kolejność miast.** W wariancie A najmniej przesiadek ma Wrocław (40,2 % bez przesiadki), potem Łódź, GZM, Kraków, Poznań, Trójmiasto, a najwięcej Warszawa (24,7 %). Jakdojade też ma Warszawę na końcu (58 %) i Wrocław wysoko (68 %), ale Trójmiasto i GZM na górze (71 %), a u nas Trójmiasto jest przedostatnie. W wariancie „cel ≤ 45 min + kara 5 min” kolejność to Łódź = Wrocław (73,9 %), GZM, Kraków = Poznań, Trójmiasto, Warszawa; Trójmiasto i Łódź są w tej porównaniu największymi odstępstwami (−7 i +10 pkt proc.). W Trójmieście ponad połowa przesiadek w próbie dotyczy kolei (SKM/PKM/Polregio: 52 % przesiadek ma koniec w pociągu), czyli najszybsze trasy łączą autobus z SKM, czego pasażerowie mogą unikać, jadąc wolniej bez przesiadki.

**Start w rdzeniu i poza nim.** Podróże zaczynające się poza rdzeniem (miastem centralnym) mają w wariancie A mniej przesiadek niż podróże z rdzenia (np. Wrocław 51,6 % wobec 38,3 % bez przesiadki). To skutek losowania w zasięgu 60 min: z przedmieść zasięg jest mały i obejmuje głównie cele wzdłuż jednej linii lub kolei, a z rdzenia także cele po drugiej stronie miasta.

**Cele ważone miejscami pracy** dają prawie te same udziały (różnice do 4 pkt proc.), mimo że miejsca pracy są bardziej skupione w centrum; w Warszawie i Trójmieście nieco więcej przesiadek, w Krakowie nieco mniej.

**Porównanie z próbą 200 par z fazy 3** (`qa/access/access.md` §6): tam 56–75 % bez przesiadki, ale cel był losowany w zasięgu 45 min, a `DetailedItineraries` nie ograniczało dojścia do 12 min (dłuższe dojście do linii bezpośredniej). Przy celu ≤ 45 min nasza próba daje 40–59 %; reszta różnicy jest zgodna co do kierunku z brakiem limitu dojścia i z błędem próby 200 par (±7 pkt proc.).

<!-- TABLE:shares -->
| Aglomeracja | Podróży KZ | 0 przesiadek, % (95 % CI) | 1, % | 2, % | ≥ 3, % | Średnio przesiadek | Jakdojade 2025: 0 / 1 / 2, % | Jakdojade: średnio | WBR 2015: bez przesiadki, % |
|---|---:|---|---|---|---|---|---|---:|---:|
| Warszawa | 11701 | 24,7 (23,9–25,5) | 48,1 (47,2–49,1) | 24,5 (23,7–25,3) | 2,6 (2,4–2,9) | 1,05 (1,04–1,07) | 58 / 33 / 8 | 0,52 | 57,2 |
| Kraków | 10506 | 35,4 (34,5–36,3) | 47,7 (46,8–48,7) | 15,7 (15,0–16,4) | 1,1 (0,9–1,4) | 0,83 (0,81–0,84) | 64 / 31 / 5 | 0,41 | – |
| Łódź | 12012 | 38,9 (38,0–39,7) | 46,5 (45,6–47,4) | 13,6 (12,9–14,2) | 1,1 (0,9–1,3) | 0,77 (0,76–0,78) | 64 / 32 / 5 | 0,41 | – |
| GZM | 13295 | 36,3 (35,5–37,1) | 49,5 (48,6–50,3) | 13,5 (12,9–14,1) | 0,8 (0,6–0,9) | 0,79 (0,78–0,80) | 71 / 25 / 4 | 0,35 | – |
| Wrocław | 11049 | 40,2 (39,3–41,1) | 47,5 (46,6–48,5) | 11,6 (11,0–12,2) | 0,6 (0,5–0,8) | 0,73 (0,71–0,74) | 68 / 28 / 3 | 0,35 | – |
| Poznań | 11964 | 34,6 (33,8–35,5) | 47,5 (46,6–48,4) | 16,5 (15,9–17,2) | 1,4 (1,2–1,6) | 0,85 (0,83–0,86) | 65 / 29 / 6 | 0,42 | – |
| Trójmiasto | 12196 | 32,1 (31,2–32,9) | 48,5 (47,6–49,4) | 18,1 (17,5–18,8) | 1,3 (1,1–1,5) | 0,89 (0,87–0,90) | 71 / 25 / 4 | 0,34 | – |
<!-- /TABLE:shares -->

### 3.1 Warianty: odsetek podróży bez przesiadki, %

<!-- TABLE:variants0 -->
| Aglomeracja | A: najszybsza, cel ≤ 60 min | B: z pieszymi jako 0 | C: każda trasa KZ | cel ≤ 30 min | cel ≤ 45 min | kara 5 min | kara 10 min | cel ≤ 45 min + kara 5 min | Jakdojade |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Warszawa | 24,7 | 41,1 | 26,6 | 71,6 (n=1459) | 40,4 (n=5200) | 35,9 | 40,5 | 58,1 (n=5200) | 58 |
| Kraków | 35,4 | 54,7 | 37,1 | 73,8 (n=1731) | 49,4 (n=5347) | 48,6 | 53,6 | 67,2 (n=5347) | 64 |
| Łódź | 38,9 | 51,0 | 40,4 | 80,7 (n=2105) | 56,2 (n=6227) | 53,3 | 59,3 | 73,9 (n=6227) | 64 |
| GZM | 36,3 | 43,5 | 37,3 | 87,9 (n=1560) | 58,6 (n=5500) | 45,2 | 50,3 | 69,8 (n=5500) | 71 |
| Wrocław | 40,2 | 55,9 | 41,9 | 79,8 (n=1986) | 53,8 (n=6234) | 56,6 | 62,8 | 73,9 (n=6234) | 68 |
| Poznań | 34,6 | 47,8 | 36,2 | 77,8 (n=1991) | 52,1 (n=6139) | 44,5 | 48,4 | 67,2 (n=6139) | 65 |
| Trójmiasto | 32,1 | 44,8 | 33,3 | 82,5 (n=1884) | 51,0 (n=6007) | 42,4 | 47,7 | 64,2 (n=6007) | 71 |
<!-- /TABLE:variants0 -->

### 3.2 Warianty: średnia liczba przesiadek

<!-- TABLE:variantsmean -->
| Aglomeracja | A: najszybsza, cel ≤ 60 min | B: z pieszymi jako 0 | C: każda trasa KZ | cel ≤ 30 min | cel ≤ 45 min | kara 5 min | kara 10 min | cel ≤ 45 min + kara 5 min | Jakdojade |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Warszawa | 1,05 | 0,82 | 1,02 | 0,30 (n=1459) | 0,72 (n=5200) | 0,76 | 0,66 | 0,44 (n=5200) | 0,52 |
| Kraków | 0,83 | 0,58 | 0,80 | 0,27 (n=1731) | 0,57 (n=5347) | 0,57 | 0,49 | 0,33 (n=5347) | 0,41 |
| Łódź | 0,77 | 0,62 | 0,75 | 0,20 (n=2105) | 0,49 (n=6227) | 0,52 | 0,43 | 0,27 (n=6227) | 0,41 |
| GZM | 0,79 | 0,70 | 0,77 | 0,12 (n=1560) | 0,45 (n=5500) | 0,62 | 0,53 | 0,31 (n=5500) | 0,35 |
| Wrocław | 0,73 | 0,54 | 0,70 | 0,21 (n=1986) | 0,51 (n=6234) | 0,46 | 0,38 | 0,27 (n=6234) | 0,35 |
| Poznań | 0,85 | 0,68 | 0,82 | 0,23 (n=1991) | 0,55 (n=6139) | 0,64 | 0,57 | 0,34 (n=6139) | 0,42 |
| Trójmiasto | 0,89 | 0,72 | 0,87 | 0,18 (n=1884) | 0,55 (n=6007) | 0,68 | 0,59 | 0,37 (n=6007) | 0,34 |
<!-- /TABLE:variantsmean -->

### 3.3 Start w rdzeniu i poza nim (wariant A)

<!-- TABLE:area -->
| Aglomeracja | Start w rdzeniu: n | 0 przesiadek, % | Średnio | Start poza rdzeniem: n | 0 przesiadek, % | Średnio |
|---|---:|---|---|---:|---|---|
| Warszawa | 7823 | 21,1 (20,2–22,1) | 1,11 (1,09–1,13) | 3878 | 31,9 (30,4–33,4) | 0,93 (0,91–0,96) |
| Kraków | 7975 | 32,4 (31,3–33,4) | 0,87 (0,85–0,89) | 2531 | 45,0 (43,1–47,0) | 0,69 (0,66–0,71) |
| Łódź | 8941 | 37,3 (36,3–38,3) | 0,79 (0,77–0,80) | 3071 | 43,3 (41,6–45,1) | 0,71 (0,69–0,74) |
| GZM | 11154 | 34,2 (33,4–35,1) | 0,82 (0,81–0,83) | 2141 | 47,0 (44,9–49,1) | 0,63 (0,60–0,65) |
| Wrocław | 9494 | 38,3 (37,4–39,3) | 0,75 (0,74–0,77) | 1555 | 51,6 (49,2–54,1) | 0,58 (0,54–0,61) |
| Poznań | 7878 | 33,0 (32,0–34,1) | 0,86 (0,85–0,88) | 4086 | 37,6 (36,1–39,1) | 0,82 (0,79–0,84) |
| Trójmiasto | 9538 | 31,2 (30,3–32,2) | 0,90 (0,88–0,91) | 2658 | 35,1 (33,3–36,9) | 0,84 (0,81–0,87) |
<!-- /TABLE:area -->

### 3.4 Cele ważone miejscami pracy (wariant A)

<!-- TABLE:jobs -->
| Aglomeracja | 0 przesiadek, cele: mieszkańcy | cele: miejsca pracy | Średnio: mieszkańcy | Średnio: miejsca pracy | n (miejsca pracy) |
|---|---|---|---|---|---:|
| Warszawa | 24,7 (23,9–25,5) | 21,0 (19,8–22,4) | 1,05 (1,04–1,07) | 1,10 (1,07–1,12) | 3822 |
| Kraków | 35,4 (34,5–36,3) | 37,3 (35,7–38,9) | 0,83 (0,81–0,84) | 0,79 (0,76–0,81) | 3607 |
| Łódź | 38,9 (38,0–39,7) | 37,9 (36,4–39,4) | 0,77 (0,76–0,78) | 0,79 (0,77–0,81) | 4111 |
| Wrocław | 40,2 (39,3–41,1) | 41,3 (39,7–42,8) | 0,73 (0,71–0,74) | 0,70 (0,68–0,73) | 3790 |
| Poznań | 34,6 (33,8–35,5) | 35,2 (33,8–36,7) | 0,85 (0,83–0,86) | 0,83 (0,81–0,85) | 4171 |
| Trójmiasto | 32,1 (31,2–32,9) | 28,6 (27,2–30,1) | 0,89 (0,87–0,90) | 0,92 (0,90–0,95) | 3708 |
<!-- /TABLE:jobs -->

### 3.5 Różnice definicji

- **WBR 2015 (Warszawa):** „57,2 % podróży komunikacją zbiorową odbywa się bez przesiadki” (synteza, s. 9). To deklaracje mieszkańców o rzeczywistych podróżach w ciągu doby, wszystkie cele i godziny, z rzeczywistym rozkładem długości podróży; podróże piesze nie są w mianowniku. Granica obszaru badania (Warszawa i gminy metropolii) różni się od naszej FUA, a sieć z 2015 r. nie miała m.in. drugiej linii metra w obecnym zasięgu. Do tej liczby najbliżej naszego wariantu A, ale nasz rozkład długości podróży jest inny.
- **Jakdojade 2025:** udziały podróży z 0, 1 i 2 przesiadkami wśród tras planowanych w aplikacji w październiku 2025 (ok. 90 mln zapytań). To trasy wybrane przez użytkowników (wybór z kilku propozycji, nie zawsze najszybszej), więc w praktyce zawierają karę za przesiadkę; populacja to użytkownicy aplikacji, nie wszyscy mieszkańcy; nie wiadomo, czy liczone są trasy wyszukane czy przejechane, ani jak liczone są zapytania z dojściem pieszym. Udziały 0 / 1 / 2 sumują się do 97–99 %, więc ≥ 3 przesiadki są albo pominięte, albo zaokrąglone. Do Jakdojade najbliżej wariant C (każda trasa KZ, także gdy spacer jest szybszy) z karą za przesiadkę.
- **Nasza próba:** trasa najszybsza w rozkładzie jednej środy, cele losowane wśród osiągalnych w 60 min proporcjonalnie do ludności (lub miejsc pracy), bez zaniku z odległością, tylko szczyt poranny. Podróże piesze: wariant A je wyklucza, wariant B liczy jako 0 przesiadek (to podnosi udział bez przesiadki o 7–19 pkt proc.), ale ani WBR, ani Jakdojade nie liczą pieszych jako podróży komunikacją.
- **Co z tego wynika:** sam udział przesiadek z losowej próby komórek nie jest dobrą miarą porównawczą z badaniem ruchu, dopóki cel nie jest losowany z rozkładem odległości z badania (np. macierz dojazdów NSP 2021). Porównanie kolejności miast i różnicy między wariantami jest bezpieczniejsze niż porównanie poziomu.

## 4. Liczba przejazdów, udział chodzenia i czekania (wariant A, cele: mieszkańcy)

<!-- TABLE:comp -->
| Aglomeracja | Podróży KZ | Średnio przejazdów | Średni czas, min | Pieszo, % czasu | Czekanie, % czasu | w tym na starcie | w tym przy przesiadkach | W pojeździe, % | Dojście przy przesiadce, % | Pieszo / czekanie / jazda, min |
|---|---:|---|---:|---|---|---:|---:|---|---:|---|
| Warszawa | 11701 | 2,05 (2,04–2,06) | 43,1 | 31,3 (31,1–31,6) | 16,6 (16,4–16,9) | 9,0 | 7,7 | 52,0 (51,7–52,3) | 5,4 | 13,5 / 7,2 / 22,4 |
| Kraków | 10506 | 1,83 (1,81–1,84) | 40,9 | 30,7 (30,4–30,9) | 17,9 (17,6–18,1) | 11,3 | 6,5 | 51,5 (51,2–51,8) | 3,3 | 12,5 / 7,3 / 21,0 |
| Łódź | 12012 | 1,77 (1,76–1,78) | 40,7 | 32,1 (31,9–32,3) | 17,5 (17,2–17,8) | 10,7 | 6,8 | 50,4 (50,1–50,7) | 4,3 | 13,1 / 7,1 / 20,5 |
| GZM | 13295 | 1,79 (1,78–1,80) | 43,1 | 30,3 (30,1–30,5) | 19,2 (19,0–19,4) | 11,4 | 7,8 | 50,5 (50,2–50,7) | 3,8 | 13,1 / 8,3 / 21,8 |
| Wrocław | 11049 | 1,73 (1,71–1,74) | 39,9 | 29,8 (29,6–30,1) | 15,8 (15,6–16,1) | 10,1 | 5,7 | 54,4 (54,0–54,7) | 3,2 | 11,9 / 6,3 / 21,7 |
| Poznań | 11964 | 1,85 (1,83–1,86) | 40,9 | 31,5 (31,3–31,7) | 19,8 (19,5–20,0) | 11,9 | 7,9 | 48,7 (48,5–49,0) | 4,1 | 12,9 / 8,1 / 19,9 |
| Trójmiasto | 12196 | 1,89 (1,87–1,90) | 41,5 | 32,6 (32,4–32,8) | 17,1 (16,9–17,3) | 9,0 | 8,1 | 50,4 (50,1–50,6) | 4,7 | 13,5 / 7,1 / 20,9 |
<!-- /TABLE:comp -->

Średnio podróż komunikacją w próbie to 1,73 (Wrocław) do 2,05 przejazdu (Warszawa) i 40–43 min od drzwi do drzwi. Mniej więcej połowa czasu to jazda (48,7–54,4 %), niemal jedna trzecia to chodzenie (29,8–32,6 %, czyli 12–13,5 min, głównie dojście i odejście; dojścia przy przesiadkach to tylko 3–5 % czasu), a 16–20 % to czekanie (6,3–8,3 min). Czekanie na pierwszy pojazd jest tu zaniżone, bo w każdej szczelinie 5 min bierzemy najlepszą minutę wyjścia; czekanie przy przesiadkach (5,7–7,9 % czasu, średnio 3,1–4,3 min na przesiadkę) jest rozkładowe i zawiera 1 min zapasu R5. Najdłużej się czeka w GZM (8,3 min) i Poznaniu (8,1 min), najkrócej we Wrocławiu (6,3 min). GZM na końcu zgadza się z warstwą przesiadek (RAPORT §20.1: najdłuższe czekanie w GZM), Poznań nie (w warstwie drugie najkrótsze czekanie): w próbie dominuje w Poznaniu czekanie na pierwszy pojazd (11,9 % czasu), czyli rzadkie linie podmiejskie na starcie, a nie przesiadki w mieście (nie sprawdzono dokładniej). Udział chodzenia jest wysoki, bo starty i cele to środki komórek 250 m, a dojście do 12 min jest dozwolone na każdym końcu; Jakdojade podaje 8–12 min dojścia do przystanku, co jest tego samego rzędu.

## 5. Użycie węzłów

<!-- TABLE:rank -->
| Aglomeracja | Zespołów | Z przesiadką w próbie | Spearman: odjazdy 7–9 a użycie | Wspólne w top 20 | Top 20 wg użycia: % przesiadek | Top 20 wg odjazdów: % przesiadek | Przesiadka w jednym zespole, % | Między dwoma zespołami, % | Poza zespołami lub jeden koniec, % |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| Warszawa | 2426 | 854 | 0,59 | 10 z 20 | 37,0 | 27,6 | 90,5 | 8,4 | 1,1 |
| Kraków | 1061 | 453 | 0,61 | 12 z 20 | 43,6 | 34,7 | 91,6 | 7,2 | 1,2 |
| Łódź | 695 | 390 | 0,68 | 9 z 20 | 50,0 | 38,5 | 84,0 | 14,0 | 2,0 |
| GZM | 2069 | 902 | 0,64 | 10 z 20 | 39,0 | 30,0 | 80,9 | 16,7 | 2,4 |
| Wrocław | 641 | 367 | 0,67 | 12 z 20 | 46,6 | 39,7 | 88,4 | 10,3 | 1,3 |
| Poznań | 867 | 422 | 0,56 | 10 z 20 | 61,5 | 42,4 | 89,2 | 9,0 | 1,8 |
| Trójmiasto | 781 | 390 | 0,55 | 12 z 20 | 63,7 | 40,7 | 92,2 | 7,1 | 0,7 |
<!-- /TABLE:rank -->

**Czy najbardziej obciążone odjazdami węzły są też najczęściej używane do przesiadek?** Częściowo. Korelacja rang (Spearman) między odjazdami 7–9 a liczbą podróży z przesiadką w zespole wynosi 0,55–0,68, a z 20 zespołów o największej liczbie odjazdów 9–12 jest też w top 20 według użycia. Największe węzły (Dworzec Główny we Wrocławiu, Dworzec Zachodni i Rondo Kaponiera w Poznaniu, Dworzec Główny w Gdańsku, Dw. Łódź Kaliska, Gliwice Centrum Przesiadkowe) są na górze obu list. Rozjazd ma dwie przyczyny:
- **wysoko w użyciu, nisko w odjazdach:** węzły kolej–autobus i pętle na skraju miasta, gdzie najszybsze trasy z przedmieść przesiadają się na pociąg lub tramwaj: Pruszków (390. miejsce według odjazdów, 11. według użycia), Rzeszotarskiej, PKP Włochy w Warszawie; Rumia Dworzec, Gdynia Chylonia, Pruszcz Gdański; Junikowo, Górczyn PKM, Dębiec PKM w Poznaniu; Łódź Widzew, Retkinia Kusocińskiego, Zgierz; Bytom Dworzec, Chebzie, Mikołów, Tychy Dworzec w GZM; Podgórze SKA, Czerwone Maki P+R w Krakowie;
- **wysoko w odjazdach, nisko w użyciu:** przystanki w centrum na ciągach, gdzie wiele linii jedzie tym samym korytarzem, więc przesiadka niewiele daje (Warszawa: Dw. Centralny 22., Pl. Zawiszy 23., Foksal 101.; Katowice Sądowa 490.; Kraków Bratysławska 197.; Gdańsk Kilińskiego 391.). W centrum Warszawy kilka sąsiednich zespołów (Centrum, Marszałkowska, Dw. Centralny, Metro Świętokrzyska, Krucza) prawdopodobnie dzieli między siebie przesiadki jednego obszaru, więc miejsce pojedynczego zespołu zależy od reguły zespołu (RAPORT §20.4); nie sprawdzono tego na mapie.

Najczęściej używane zespoły skupiają 4–7 % podróży komunikacją z przesiadką w nich (Łódź Kaliska 7,2 %, Poznań Dworzec Zachodni 6,3 %, Gdańsk Główny 6,2 %); top 20 według użycia to 37 % przesiadek w Warszawie i GZM (sieci rozproszone) i 62–64 % w Poznaniu i Trójmieście (kilka dominujących węzłów). 81–92 % przesiadek zaczyna się i kończy w jednym zespole; 7–17 % łączy dwa sąsiednie zespoły (najwięcej w GZM i Łodzi, gdzie zespoły są małe), 1–2 % ma koniec poza zespołami.

**Dojście i czekanie przy przesiadce w próbie** (średnio 1,6–2,3 min dojścia i 3,1–4,3 min czekania na przesiadkę) są dużo krótsze niż w warstwie przesiadek (czekanie 5,6–15,6 min): warstwa uśrednia wszystkie pary linii przy losowym momencie przyjazdu, a trasa najszybsza wybiera przesiadkę, która akurat dobrze pasuje w rozkładzie. Obie liczby są poprawne, ale odpowiadają na różne pytania: warstwa – „ile kosztuje przesiadka, jeśli muszę się tu przesiąść”, próba – „ile kosztują przesiadki, które sieć faktycznie podsuwa”.

**Warstwa `node_use.parquet`.** 8 540 zespołów (wszystkie z `transfer_nodes.parquet`), dla każdego: liczba podróży z przesiadką i zdarzeń przesiadki w próbie (cele: mieszkańcy, osobno miejsca pracy), udział w podróżach KZ z przedziałem Wilsona, udział we wszystkich przesiadkach, średnie dojście i czekanie z próby, miejsce według użycia i według odjazdów oraz ocena pewności: 540 zespołów ma ≥ 30 podróży („dobra”), 714 ma 10–29, 2 524 ma 1–9, 4 762 nie ma żadnej przesiadki w próbie (to nie znaczy, że nikt się tam nie przesiada; przy 11–13 tys. podróży KZ na miasto zespół z udziałem poniżej ok. 0,03 % zwykle nie trafi do próby).

### 5.1 Dwadzieścia najczęściej używanych zespołów

„Dojście / czekanie w próbie” to średnie z przesiadek w tym zespole w próbie (czekanie po najlepszym dopasowaniu w rozkładzie, z 1 min zapasu R5). „Warstwa” to średnie ważone kursami z `transfer_nodes.parquet` (wszystkie pary linii, losowy moment przyjazdu), więc czekanie z warstwy jest zwykle dłuższe: trasy najszybsze wybierają przesiadki dobrze skomunikowane.

#### Warszawa
<!-- TABLE:top_warszawa -->
| # | Zespół | Podróży z przesiadką | % podróży KZ (95 % CI) | % wszystkich przesiadek | Dojście w próbie, min | Czekanie w próbie, min | Warstwa: dojście, min | Warstwa: czekanie, min | Odjazdy/h 7–9 | Miejsce wg odjazdów |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Marszałkowska | 501 | 4,28 (3,93–4,66) | 4,1 | 1,9 | 2,4 | 2,4 | 4,1 | 317 | 3 |
| 2 | Dw. Wileński | 348 | 2,97 (2,68–3,30) | 2,8 | 3,1 | 2,5 | 2,3 | 4,7 | 280 | 5 |
| 3 | Metro Ratusz Arsenał | 346 | 2,96 (2,67–3,28) | 2,8 | 1,5 | 2,0 | 1,7 | 4,3 | 226 | 7 |
| 4 | Kijowska | 312 | 2,67 (2,39–2,97) | 2,5 | 3,1 | 2,4 | 3,9 | 6,5 | 304 | 4 |
| 5 | Centrum | 277 | 2,37 (2,11–2,66) | 2,3 | 4,3 | 2,2 | 3,1 | 5,5 | 360 | 1 |
| 6 | Dw. Gdański | 259 | 2,21 (1,96–2,50) | 2,1 | 2,2 | 2,2 | 3,3 | 5,2 | 183 | 16 |
| 7 | Metro Świętokrzyska | 248 | 2,12 (1,87–2,40) | 2,0 | 3,3 | 2,0 | 2,2 | 3,5 | 180 | 17 |
| 8 | Metro Wilanowska | 244 | 2,08 (1,84–2,36) | 2,0 | 2,8 | 2,3 | 2,1 | 4,9 | 142 | 37 |
| 9 | Dw. Zachodni | 219 | 1,87 (1,64–2,13) | 1,8 | 3,6 | 3,1 | 4,0 | 10,1 | 192 | 13 |
| 10 | Metro Młociny | 203 | 1,74 (1,51–1,99) | 1,6 | 1,5 | 2,5 | 2,1 | 6,5 | 132 | 47 |
| 11 | Pruszków | 197 | 1,68 (1,47–1,93) | 1,6 | 1,9 | 4,0 | – | – | 41 | 390 |
| 12 | Park Kaskada | 190 | 1,62 (1,41–1,87) | 1,5 | 2,1 | 2,5 | 3,0 | 5,1 | 168 | 20 |
| 13 | Dw. Wschodni (Kijowska) | 183 | 1,56 (1,35–1,80) | 1,5 | 3,3 | 2,8 | 3,2 | 13,2 | 134 | 46 |
| 14 | Rzeszotarskiej | 172 | 1,47 (1,27–1,70) | 1,4 | 4,5 | 3,0 | 4,9 | 6,6 | 40 | 396 |
| 15 | Bemowo | 160 | 1,37 (1,17–1,59) | 1,3 | 2,7 | 2,3 | 2,9 | 6,2 | 162 | 22 |
| 16 | PKP Włochy | 157 | 1,34 (1,15–1,57) | 1,3 | 2,3 | 3,5 | 3,1 | 8,8 | 92 | 118 |
| 17 | Metro Kondratowicza | 140 | 1,20 (1,01–1,41) | 1,1 | 1,3 | 2,4 | 1,7 | 6,3 | 140 | 40 |
| 18 | Żerań FSO | 139 | 1,19 (1,01–1,40) | 1,1 | 2,3 | 3,5 | 2,8 | 6,7 | 99 | 94 |
| 19 | Saska | 133 | 1,14 (0,96–1,34) | 1,1 | 1,2 | 2,3 | 2,2 | 5,4 | 208 | 9 |
| 20 | PKP WKD Al. Jerozolimskie | 130 | 1,11 (0,94–1,32) | 1,1 | 2,0 | 2,7 | 2,2 | 10,4 | 102 | 89 |
<!-- /TABLE:top_warszawa -->

#### Kraków
<!-- TABLE:top_krakow -->
| # | Zespół | Podróży z przesiadką | % podróży KZ (95 % CI) | % wszystkich przesiadek | Dojście w próbie, min | Czekanie w próbie, min | Warstwa: dojście, min | Warstwa: czekanie, min | Odjazdy/h 7–9 | Miejsce wg odjazdów |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Podgórze SKA | 316 | 3,01 (2,70–3,35) | 3,6 | 1,7 | 2,7 | 1,7 | 9,2 | 84 | 39 |
| 2 | Wiślicka | 284 | 2,70 (2,41–3,03) | 3,3 | 0,9 | 3,3 | 1,3 | 7,7 | 111 | 18 |
| 3 | Bieżanowska | 278 | 2,65 (2,36–2,97) | 3,2 | 2,1 | 2,6 | 2,2 | 6,6 | 150 | 8 |
| 4 | Rondo Grunwaldzkie | 272 | 2,59 (2,30–2,91) | 3,1 | 1,3 | 3,1 | 1,7 | 10,2 | 192 | 3 |
| 5 | Rondo Mogilskie | 268 | 2,55 (2,27–2,87) | 3,1 | 1,7 | 2,5 | 2,4 | 6,1 | 200 | 1 |
| 6 | Krowodrza Górka P+R | 235 | 2,24 (1,97–2,54) | 2,7 | 1,8 | 2,7 | 1,4 | 8,9 | 108 | 21 |
| 7 | Kraków Główny | 233 | 2,22 (1,95–2,52) | 2,7 | 2,8 | 3,4 | 3,2 | 13,3 | 122 | 14 |
| 8 | Nowy Kleparz | 203 | 1,93 (1,69–2,21) | 2,3 | 1,5 | 2,8 | 1,7 | 7,4 | 176 | 7 |
| 9 | Łagiewniki | 199 | 1,89 (1,65–2,17) | 2,3 | 1,5 | 3,3 | 1,4 | 10,0 | 84 | 37 |
| 10 | Rondo Matecznego | 197 | 1,88 (1,63–2,15) | 2,3 | 1,7 | 2,6 | 1,5 | 8,1 | 128 | 12 |
| 11 | Politechnika | 191 | 1,82 (1,58–2,09) | 2,2 | 1,5 | 2,6 | 1,1 | 5,8 | 177 | 6 |
| 12 | Plac Inwalidów | 168 | 1,60 (1,38–1,86) | 1,9 | 1,5 | 2,3 | 1,8 | 7,2 | 182 | 4 |
| 13 | Czerwone Maki P+R | 140 | 1,33 (1,13–1,57) | 1,6 | 0,8 | 3,4 | 0,9 | 14,1 | 52 | 111 |
| 14 | Starowiślna | 137 | 1,30 (1,10–1,54) | 1,6 | 1,7 | 2,6 | – | – | 138 | 10 |
| 15 | Muzeum Narodowe | 135 | 1,28 (1,09–1,52) | 1,6 | 1,7 | 2,9 | 1,8 | 8,1 | 194 | 2 |
| 16 | Bronowice SKA | 110 | 1,05 (0,87–1,26) | 1,3 | 2,3 | 3,1 | 3,8 | 10,9 | 146 | 9 |
| 17 | Rondo 308. Dywizjonu | 106 | 1,01 (0,83–1,22) | 1,2 | 2,0 | 3,0 | 1,8 | 7,9 | 62 | 75 |
| 18 | Łagiewniki SKA | 105 | 1,00 (0,83–1,21) | 1,2 | 2,6 | 2,7 | 2,8 | 14,0 | 67 | 64 |
| 19 | Borek Fałęcki | 104 | 0,99 (0,82–1,20) | 1,2 | 2,3 | 3,6 | 2,4 | 14,7 | 54 | 104 |
| 20 | Kuklińskiego | 102 | 0,97 (0,80–1,18) | 1,2 | 2,6 | 2,6 | 2,0 | 8,1 | 78 | 54 |
<!-- /TABLE:top_krakow -->

#### Łódź
<!-- TABLE:top_lodz -->
| # | Zespół | Podróży z przesiadką | % podróży KZ (95 % CI) | % wszystkich przesiadek | Dojście w próbie, min | Czekanie w próbie, min | Warstwa: dojście, min | Warstwa: czekanie, min | Odjazdy/h 7–9 | Miejsce wg odjazdów |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Włókniarzy-Mickiewicza (Dw. Ł. Kaliska) | 866 | 7,21 (6,76–7,69) | 9,4 | 3,2 | 3,3 | 2,1 | 11,0 | 124 | 1 |
| 2 | Limanowskiego-Woronicza | 348 | 2,90 (2,61–3,21) | 3,8 | 3,3 | 3,2 | 2,6 | 12,3 | 81 | 12 |
| 3 | Piotrkowska Centrum | 340 | 2,83 (2,55–3,14) | 3,7 | 1,7 | 2,4 | 1,5 | 7,7 | 104 | 2 |
| 4 | Mickiewicza-Żeromskiego | 316 | 2,63 (2,36–2,93) | 3,4 | 1,5 | 2,5 | 1,9 | 9,8 | 88 | 5 |
| 5 | Łódź Widzew | 280 | 2,33 (2,08–2,62) | 3,0 | 3,3 | 3,9 | 1,9 | 25,9 | 38 | 104 |
| 6 | Rzgowska-Dachowa | 255 | 2,12 (1,88–2,40) | 2,8 | 4,4 | 3,6 | 3,2 | 13,1 | 84 | 10 |
| 7 | Legionów-Włókniarzy | 223 | 1,86 (1,63–2,11) | 2,4 | 2,6 | 3,8 | 1,6 | 11,1 | 58 | 39 |
| 8 | Retkinia Kusocińskiego | 221 | 1,84 (1,61–2,10) | 2,4 | 5,8 | 5,4 | 0,0 | 14,7 | 10 | 416 |
| 9 | Śląska-Śląska 28 | 209 | 1,74 (1,52–1,99) | 2,3 | 5,1 | 3,8 | 6,2 | 28,2 | 26 | 178 |
| 10 | Narutowicza-pl. Dąbrowskiego | 203 | 1,69 (1,47–1,94) | 2,2 | 3,3 | 3,0 | 2,3 | 11,6 | 102 | 3 |
| 11 | Zachodnia-Lutomierska | 151 | 1,26 (1,07–1,47) | 1,6 | 2,0 | 2,9 | 1,7 | 8,5 | 78 | 16 |
| 12 | 1 Maja-pl. Kilińskiego (Zgierz) | 149 | 1,24 (1,06–1,46) | 1,6 | 1,0 | 6,0 | – | – | 32 | 135 |
| 12 | Pabianicka-Jana Pawła II | 149 | 1,24 (1,06–1,46) | 1,6 | 3,6 | 4,1 | 3,1 | 16,8 | 58 | 43 |
| 14 | Czechosłowacka-Edwarda NŻ | 143 | 1,19 (1,01–1,40) | 1,5 | 5,1 | 5,9 | – | – | 15 | 316 |
| 15 | Piłsudskiego-Śmigłego-Rydza | 141 | 1,17 (1,00–1,38) | 1,5 | 1,7 | 2,6 | 2,5 | 12,6 | 70 | 22 |
| 16 | Pabianicka-Rondo Lotników Lwowskich | 130 | 1,08 (0,91–1,28) | 1,4 | 2,5 | 2,4 | 1,9 | 12,1 | 87 | 7 |
| 17 | Aleksandrowska-Szparagowa | 128 | 1,07 (0,90–1,26) | 1,4 | 1,2 | 3,1 | 1,4 | 9,7 | 59 | 37 |
| 18 | Zgierz | 123 | 1,02 (0,86–1,22) | 1,3 | 3,2 | 5,5 | – | – | 17 | 279 |
| 18 | Kopcińskiego-Piłsudskiego | 123 | 1,02 (0,86–1,22) | 1,3 | 1,7 | 2,9 | 1,7 | 9,2 | 54 | 52 |
| 20 | Wojska Polskiego-Palki | 120 | 1,00 (0,84–1,19) | 1,3 | 1,5 | 3,0 | 1,9 | 14,7 | 80 | 14 |
<!-- /TABLE:top_lodz -->

#### GZM
<!-- TABLE:top_gzm -->
| # | Zespół | Podróży z przesiadką | % podróży KZ (95 % CI) | % wszystkich przesiadek | Dojście w próbie, min | Czekanie w próbie, min | Warstwa: dojście, min | Warstwa: czekanie, min | Odjazdy/h 7–9 | Miejsce wg odjazdów |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Bytom Dworzec | 488 | 3,67 (3,36–4,00) | 4,7 | 2,5 | 4,4 | 2,9 | 18,9 | 98 | 11 |
| 2 | Zabrze Goethego | 410 | 3,08 (2,80–3,39) | 3,9 | 3,2 | 4,8 | 2,6 | 17,6 | 96 | 12 |
| 3 | Gliwice Centrum Przesiadkowe | 408 | 3,07 (2,79–3,38) | 3,9 | 2,3 | 4,5 | 1,9 | 18,6 | 171 | 1 |
| 4 | Chorzów Batory Dworzec PKP | 304 | 2,29 (2,05–2,56) | 2,9 | 2,7 | 4,4 | 1,7 | 14,2 | 68 | 29 |
| 5 | Chebzie Pętla | 300 | 2,26 (2,02–2,52) | 2,9 | 3,2 | 4,6 | 3,2 | 14,3 | 53 | 44 |
| 6 | Katowice Dworzec | 247 | 1,86 (1,64–2,10) | 2,4 | 4,1 | 3,4 | 2,4 | 14,7 | 158 | 2 |
| 7 | Sosnowiec Dworzec PKP | 237 | 1,78 (1,57–2,02) | 2,3 | 2,1 | 3,5 | 1,0 | 16,8 | 90 | 15 |
| 8 | Katowice Chorzowska | 185 | 1,39 (1,21–1,60) | 1,8 | 2,7 | 3,1 | 2,0 | 14,0 | 134 | 5 |
| 9 | Katowice Aleja Korfantego | 183 | 1,38 (1,19–1,59) | 1,7 | 2,9 | 2,2 | 2,5 | 9,8 | 156 | 3 |
| 10 | Katowice Mickiewicza | 170 | 1,28 (1,10–1,48) | 1,6 | 3,8 | 3,2 | 1,4 | 11,7 | 64 | 31 |
| 11 | Katowice Sokolska | 164 | 1,23 (1,06–1,44) | 1,6 | 2,6 | 2,8 | 0,9 | 16,7 | 109 | 8 |
| 12 | Chorzów Rynek | 141 | 1,06 (0,90–1,25) | 1,3 | 1,2 | 2,9 | 0,8 | 11,6 | 78 | 22 |
| 13 | Mikołów Dworzec | 130 | 0,98 (0,82–1,16) | 1,2 | 0,7 | 5,6 | 1,2 | 23,8 | 46 | 66 |
| 14 | Dąbrowa Górnicza Centrum | 115 | 0,86 (0,72–1,04) | 1,1 | 2,1 | 4,7 | 0,9 | 19,3 | 92 | 14 |
| 15 | Katowice AWF | 108 | 0,81 (0,67–0,98) | 1,0 | 1,1 | 4,1 | 1,0 | 13,5 | 112 | 7 |
| 15 | Tychy Dworzec PKP | 108 | 0,81 (0,67–0,98) | 1,0 | 2,5 | 6,3 | 1,4 | 20,7 | 48 | 60 |
| 17 | Brynów Centrum Przesiadkowe | 107 | 0,80 (0,67–0,97) | 1,0 | 0,6 | 3,2 | 0,7 | 11,5 | 68 | 28 |
| 18 | Zawodzie Centrum Przesiadkowe | 105 | 0,79 (0,65–0,96) | 1,0 | 1,2 | 3,2 | 1,2 | 13,9 | 56 | 37 |
| 19 | Gliwice Politechnika | 92 | 0,69 (0,56–0,85) | 0,9 | 3,3 | 4,1 | 0,8 | 16,5 | 48 | 58 |
| 20 | Ruda Południowa | 88 | 0,66 (0,54–0,81) | 0,8 | 3,8 | 3,7 | 2,5 | 15,5 | 38 | 115 |
<!-- /TABLE:top_gzm -->

#### Wrocław
<!-- TABLE:top_wroclaw -->
| # | Zespół | Podróży z przesiadką | % podróży KZ (95 % CI) | % wszystkich przesiadek | Dojście w próbie, min | Czekanie w próbie, min | Warstwa: dojście, min | Warstwa: czekanie, min | Odjazdy/h 7–9 | Miejsce wg odjazdów |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | DWORZEC GŁÓWNY | 545 | 4,93 (4,54–5,35) | 6,8 | 4,2 | 3,0 | 3,3 | 10,8 | 192 | 1 |
| 2 | FAT | 307 | 2,78 (2,49–3,10) | 3,8 | 2,7 | 2,9 | 1,8 | 9,0 | 122 | 7 |
| 3 | Arkady (Capitol) | 270 | 2,44 (2,17–2,75) | 3,4 | 1,1 | 2,4 | 0,9 | 6,1 | 135 | 4 |
| 4 | PL. GRUNWALDZKI | 216 | 1,96 (1,71–2,23) | 2,7 | 1,2 | 3,0 | 1,3 | 7,2 | 174 | 2 |
| 5 | Kwiska | 214 | 1,94 (1,70–2,21) | 2,7 | 0,7 | 2,9 | 0,9 | 8,0 | 116 | 8 |
| 6 | Hallera | 212 | 1,92 (1,68–2,19) | 2,6 | 1,2 | 2,4 | 1,3 | 8,0 | 124 | 6 |
| 7 | GALERIA DOMINIKAŃSKA 05 | 203 | 1,84 (1,60–2,10) | 2,5 | 1,6 | 2,5 | 2,0 | 7,3 | 172 | 3 |
| 8 | Psie Pole (Rondo Lotników Polskich) | 192 | 1,74 (1,51–2,00) | 2,4 | 1,6 | 3,3 | 1,6 | 11,4 | 108 | 12 |
| 9 | DWORZEC AUTOBUSOWY | 166 | 1,50 (1,29–1,75) | 2,1 | 3,0 | 2,5 | 1,7 | 7,9 | 110 | 11 |
| 10 | DWORZEC NADODRZE | 157 | 1,42 (1,22–1,66) | 2,0 | 2,9 | 2,8 | 1,6 | 11,4 | 89 | 24 |
| 11 | Wejherowska (Hala Orbita) | 153 | 1,39 (1,18–1,62) | 1,9 | 1,4 | 3,3 | 1,2 | 8,5 | 88 | 28 |
| 12 | PL. JANA PAWŁA II 05 | 149 | 1,35 (1,15–1,58) | 1,9 | 1,2 | 2,4 | 1,5 | 6,8 | 128 | 5 |
| 13 | Bastion Sakwowy | 148 | 1,34 (1,14–1,57) | 1,8 | 1,5 | 2,5 | 1,2 | 7,4 | 114 | 9 |
| 14 | Wrocław Mikołajów (Zachodnia) | 135 | 1,22 (1,03–1,44) | 1,7 | 5,8 | 3,0 | 3,7 | 18,8 | 72 | 49 |
| 15 | KRZYKI | 132 | 1,20 (1,01–1,42) | 1,6 | 1,6 | 3,8 | 1,2 | 9,9 | 76 | 39 |
| 16 | LEŚNICA | 120 | 1,09 (0,91–1,30) | 1,5 | 1,2 | 4,3 | 0,8 | 12,7 | 42 | 140 |
| 17 | Pl. Orląt Lwowskich | 117 | 1,06 (0,88–1,27) | 1,5 | 1,4 | 2,4 | 1,4 | 7,0 | 106 | 14 |
| 18 | Kosmonautów (Szpital) | 104 | 0,94 (0,78–1,14) | 1,3 | 1,0 | 2,6 | 1,0 | 7,0 | 46 | 123 |
| 19 | Górnicza | 103 | 0,93 (0,77–1,13) | 1,3 | 1,1 | 3,6 | 1,2 | 8,6 | 78 | 38 |
| 20 | KROMERA | 100 | 0,91 (0,74–1,10) | 1,2 | 1,1 | 2,8 | 0,9 | 10,8 | 64 | 57 |
<!-- /TABLE:top_wroclaw -->

#### Poznań
<!-- TABLE:top_poznan -->
| # | Zespół | Podróży z przesiadką | % podróży KZ (95 % CI) | % wszystkich przesiadek | Dojście w próbie, min | Czekanie w próbie, min | Warstwa: dojście, min | Warstwa: czekanie, min | Odjazdy/h 7–9 | Miejsce wg odjazdów |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Dworzec Zachodni | 751 | 6,28 (5,86–6,73) | 7,4 | 3,3 | 3,2 | 2,6 | 9,8 | 162 | 1 |
| 2 | Rondo Śródka | 619 | 5,17 (4,79–5,58) | 6,1 | 1,3 | 4,1 | 1,4 | 10,3 | 96 | 9 |
| 3 | Rondo Kaponiera | 530 | 4,43 (4,08–4,81) | 5,2 | 3,0 | 2,6 | 2,3 | 6,1 | 160 | 2 |
| 4 | Górczyn PKM | 443 | 3,70 (3,38–4,06) | 4,4 | 2,7 | 4,1 | 3,3 | 13,6 | 50 | 51 |
| 5 | Ogrody | 425 | 3,55 (3,23–3,90) | 4,2 | 2,0 | 4,2 | 1,6 | 15,4 | 69 | 23 |
| 6 | Junikowo | 422 | 3,53 (3,21–3,87) | 4,2 | 1,3 | 3,8 | 0,7 | 15,0 | 35 | 104 |
| 7 | Aleje Solidarności | 386 | 3,23 (2,92–3,56) | 3,8 | 0,7 | 3,3 | 0,8 | 7,7 | 96 | 8 |
| 8 | Szymanowskiego | 357 | 2,98 (2,69–3,30) | 3,5 | 1,1 | 3,3 | 0,8 | 10,7 | 101 | 7 |
| 9 | Dębiec PKM | 288 | 2,41 (2,15–2,70) | 2,8 | 4,8 | 4,0 | 4,0 | 18,6 | 36 | 88 |
| 10 | Rondo Rataje | 248 | 2,07 (1,83–2,34) | 2,4 | 1,7 | 3,4 | 1,0 | 11,0 | 91 | 11 |
| 11 | Most Teatralny | 226 | 1,89 (1,66–2,15) | 2,2 | 2,1 | 2,8 | 1,6 | 5,0 | 131 | 4 |
| 12 | Traugutta | 214 | 1,79 (1,57–2,04) | 2,1 | 1,7 | 3,3 | 1,8 | 6,0 | 75 | 19 |
| 13 | Dębiec PKM | 202 | 1,69 (1,47–1,94) | 2,0 | 4,2 | 4,0 | 2,4 | 13,7 | 16 | 227 |
| 14 | Głogowska/Hetmańska | 199 | 1,66 (1,45–1,91) | 2,0 | 1,0 | 3,1 | 1,2 | 6,1 | 104 | 6 |
| 15 | Kórnicka | 191 | 1,60 (1,39–1,84) | 1,9 | 1,3 | 2,4 | 0,6 | 5,5 | 108 | 5 |
| 16 | Starołęka PKM | 190 | 1,59 (1,38–1,83) | 1,9 | 4,4 | 4,1 | 3,8 | 13,2 | 34 | 107 |
| 17 | Rondo Starołęka | 146 | 1,22 (1,04–1,43) | 1,4 | 1,6 | 2,3 | 0,7 | 5,1 | 73 | 22 |
| 18 | Kurpińskiego | 137 | 1,15 (0,97–1,35) | 1,4 | 1,1 | 2,9 | 1,8 | 8,4 | 64 | 30 |
| 19 | Franowo | 132 | 1,10 (0,93–1,31) | 1,3 | 1,3 | 4,5 | – | – | 25 | 136 |
| 20 | Garbary PKM | 126 | 1,05 (0,89–1,25) | 1,2 | 4,1 | 4,0 | 3,2 | 16,4 | 47 | 64 |
<!-- /TABLE:top_poznan -->

#### Trójmiasto
<!-- TABLE:top_trojmiasto -->
| # | Zespół | Podróży z przesiadką | % podróży KZ (95 % CI) | % wszystkich przesiadek | Dojście w próbie, min | Czekanie w próbie, min | Warstwa: dojście, min | Warstwa: czekanie, min | Odjazdy/h 7–9 | Miejsce wg odjazdów |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Dworzec Główny 01 | 761 | 6,24 (5,82–6,68) | 7,0 | 2,4 | 3,4 | 2,7 | 12,2 | 220 | 2 |
| 2 | Gdańsk Wrzeszcz | 654 | 5,36 (4,98–5,78) | 6,0 | 2,4 | 3,7 | 3,0 | 12,7 | 120 | 11 |
| 3 | Gdańsk Oliwa | 651 | 5,34 (4,95–5,75) | 6,0 | 3,3 | 3,8 | 4,9 | 14,1 | 78 | 28 |
| 4 | Gdynia Dworzec Gł. PKP - Hala 04 | 573 | 4,70 (4,34–5,09) | 5,3 | 2,4 | 3,2 | 4,4 | 11,5 | 236 | 1 |
| 5 | Rumia Dworzec PKP 04 | 465 | 3,81 (3,49–4,17) | 4,3 | 1,5 | 5,2 | 0,9 | 18,6 | 38 | 102 |
| 6 | Redłowo SKM - Park Technologiczny 01 | 438 | 3,59 (3,27–3,94) | 4,0 | 1,7 | 3,7 | 2,4 | 10,2 | 129 | 7 |
| 7 | Gdynia Chylonia | 367 | 3,01 (2,72–3,33) | 3,4 | 2,7 | 4,2 | 2,2 | 11,7 | 54 | 62 |
| 8 | Łostowice Świętokrzyska 01 | 352 | 2,89 (2,60–3,20) | 3,3 | 2,4 | 3,9 | 0,8 | 12,9 | 58 | 50 |
| 9 | Wzgórze Św. Maksymiliana SKM 01 | 351 | 2,88 (2,60–3,19) | 3,2 | 2,2 | 2,6 | 2,4 | 10,5 | 174 | 4 |
| 10 | Sopot | 288 | 2,36 (2,11–2,65) | 2,7 | 3,5 | 3,3 | 3,3 | 15,1 | 78 | 26 |
| 11 | Śródmieście SKM 01 | 282 | 2,31 (2,06–2,59) | 2,6 | 2,8 | 2,3 | 3,9 | 9,7 | 142 | 6 |
| 12 | Pruszcz Gdański Pruszcz Gdański Dworzec 01 | 275 | 2,25 (2,01–2,53) | 2,5 | 3,6 | 7,8 | – | – | 31 | 145 |
| 13 | Brama Wyżynna 01 | 264 | 2,17 (1,92–2,44) | 2,4 | 2,1 | 3,1 | 2,6 | 11,2 | 204 | 3 |
| 14 | Obłuże Centrum 01 | 207 | 1,70 (1,48–1,94) | 1,9 | 0,4 | 3,8 | 0,8 | 11,9 | 106 | 13 |
| 15 | Ujeścisko 01 | 193 | 1,58 (1,38–1,82) | 1,8 | 1,9 | 2,8 | 0,7 | 9,5 | 57 | 51 |
| 16 | Politechnika SKM 01 | 191 | 1,57 (1,36–1,80) | 1,8 | 2,1 | 2,8 | 3,7 | 6,6 | 126 | 8 |
| 17 | Galeria Bałtycka 01 | 151 | 1,24 (1,06–1,45) | 1,4 | 1,5 | 3,3 | 1,8 | 9,9 | 121 | 10 |
| 18 | Morska - Estakada 01 | 141 | 1,16 (0,98–1,36) | 1,3 | 3,0 | 3,8 | 4,1 | 8,4 | 104 | 14 |
| 18 | Stocznia SKM - Morska 01 | 141 | 1,16 (0,98–1,36) | 1,3 | 2,8 | 2,5 | 1,6 | 9,8 | 100 | 17 |
| 20 | Warneńska 01 | 139 | 1,14 (0,97–1,34) | 1,3 | 0,9 | 3,4 | 0,4 | 9,4 | 58 | 49 |
<!-- /TABLE:top_trojmiasto -->

## 6. Pary podmiejskie z kontroli NIK P/25/019

Co podaje NIK (Informacja o wynikach kontroli, s. 29, infografika 5 na s. 17): czasy z publicznie dostępnej aplikacji mapowej z planowaniem podróży w czasie rzeczywistym, notowane przez pięć dni w szczycie porannym (do miasta) i popołudniowym (z miasta), między urzędem gminy a „centrum miasta”; zapisywano dystans, godzinę oraz najkrótszy i najdłuższy czas. Infografika podaje jedną liczbę dla komunikacji i jedną dla samochodu na gminę, bez informacji, który to kierunek, dzień i czy to czas najkrótszy, czy najdłuższy. Punktu w centrum miasta NIK nie podaje.

Nasza strona: urząd gminy z OSM (obiekt `amenity=townhall` albo `office=government` z nazwą urzędu; identyfikatory w `pipeline/trips_nik.py` i w CSV), w mieście dwa warianty: centrum i węzeł z `config.yaml`. Rano: z gminy do miasta, odjazdy co minutę 7:00–9:00; po południu: z miasta do gminy 16:00–18:00. Parametry jak w fazie 3, limit 120 min. Podajemy najkrótszy, medianę i najdłuższy czas po minutach odjazdu.

<!-- TABLE:nik -->
| Gmina | Miasto | NIK: KZ, min | NIK: samochód, min | R5 rano do centrum: min / mediana / maks | Mediana R5 − NIK, min | R5 rano do węzła: mediana | R5 po południu z centrum: min / mediana / maks | Najszybsza trasa R5 rano (odjazd) | Punkt w gminie (OSM) |
|---|---|---:|---:|---|---:|---:|---|---|---|
| Łomianki | Warszawa | 59 | 41 | 53 / 60 / 66 | 0 | 58 | 49 / 52 / 58 | 150 + M1 (07:02) | Urząd Miasta i Gminy Łomianki, Warszawska 115 |
| Nadarzyn | Warszawa | 56 | 33 | 59 / 70 / 85 | 14 | 70 | 57 / 68 / 84 | 733 + 9 (08:09) | Urząd Gminy Nadarzyn, Mszczonowska 24 |
| Piaseczno | Warszawa | 51 | 46 | 43 / 58 / 66 | 7 | 56 | 45 / 56 / 62 | 727 + IC + 525 (07:17) | Urząd Miasta i Gminy Piaseczno, Kościuszki 5 |
| Marki | Warszawa | 34 | 40 | 43 / 47 / 55 | 13 | 46 | 46 / 49 / 54 | 140 + M2 + 16 (08:18) | Urząd Miasta Marki, al. Piłsudskiego 95 |
| Sulejówek | Warszawa | 32 | 42 | 33 / 42 / 58 | 10 | 40 | 34 / 43 / 58 | S2 (08:10) | Urząd Miasta Sulejówek, Dworcowa 55 |
| Wielka Wieś | Kraków | 40 | 21 | 43 / 50 / 57 | 10 | 48 | 42 / 50 / 57 | 310 + 502 (08:30) | Urząd Gminy Wielka Wieś, pl. Wspólnoty 1, Szyce (office=government) |
| Liszki | Kraków | 49 | 31 | 39 / 49 / 64 | 0 | 58 | 36 / 44 / 58 | 229 + 13 (08:11) | Urząd Gminy Liszki, Mały Rynek 2 (office=government) |
| Niepołomice | Kraków | 50 | 38 | 59 / 75 / 90 | 25 | 68 | 53 / 71 / 89 | A7 + K3P + 3 (08:33) | Ratusz, pl. Zwycięstwa 13, Niepołomice |
| Skawina | Kraków | 31 | 34 | 39 / 55 / 68 | 24 | 50 | 45 / 59 / 71 | K52P (07:14) | Urząd Miasta i Gminy Skawina, Rynek 1 (office=government) |
| Wieliczka | Kraków | 25 | 33 | 36 / 50 / 58 | 25 | 45 | 39 / 48 / 56 | SKA1 (07:06) | Urząd Miasta i Gminy, Powstania Warszawskiego 1, Wieliczka |
| Tarnowo Podgórne | Poznań | 46 | 29 | 65 / 76 / 89 | 30 | 63 | 63 / 74 / 86 | 812 + REG + 13 (08:29) | Urząd Gminy Tarnowo Podgórne, Poznańska 115 |
| Murowana Goślina | Poznań | 42 | 42 | 52 / 74 / 95 | 32 | 73 | 54 / 76 / 101 | PKM3 + 174 (07:05) | Urząd Miasta i Gminy Murowana Goślina, pl. Powstańców Wielkopolskich 9 |
| Swarzędz | Poznań | 26 | 26 | 40 / 48 / 58 | 22 | 52 | 36 / 48 / 59 | 401 + 5 (07:41) | Urząd Miasta i Gminy w Swarzędzu, Rynek 1 |
| Kórnik | Poznań | 37 | 36 | 50 / 64 / 90 | 28 | 65 | 54 / 70 / 93 | 501 + 8 (08:55) | Urząd Miasta i Gminy w Kórniku, pl. Niepodległości 1 |
| Stęszew | Poznań | 36 | 37 | 58 / 77 / 107 | 41 | 66 | 55 / 87 / 120 | PKM3 + 174 (07:14) | Urząd Miejski Gminy Stęszew (punkt OSM bez adresu) |
<!-- /TABLE:nik -->

Wszystkie 15 par udało się umiejscowić: urzędy gmin są w OSM (12 jako `amenity=townhall`, Wielka Wieś, Liszki i Skawina jako `office=government`; urząd gminy Wielka Wieś jest w Szycach). W Murowanej Goślinie OSM ma dwa obiekty urzędu (pl. Powstańców Wielkopolskich 9 i Poznańska 18, ok. 250 m od siebie); użyto pierwszego. Punkt w Stęszewie nie ma adresu w OSM. Wszystkie pary mają trasę R5 o każdej minucie 7–9 i 16–18. Odtworzone są więc punkty w gminach, nie punkty NIK w miastach, dni ani sposób wyboru liczby.

**Porównanie.** Najkrótszy czas R5 rano (gmina → centrum) jest średnio o 6,5 min dłuższy niż czas KZ z NIK (mediana różnicy 8,9 min; w granicy ±20 % 7 z 15 par; suma czasów R5 / NIK = 1,16). Mediana R5 z minut 7–9 jest dłuższa o 19 min średnio (mediana różnicy 22 min, suma 1,46), więc liczby NIK odpowiadają raczej najkorzystniejszemu momentowi wyjazdu niż typowemu. Różnice są uporządkowane geograficznie:
- **Warszawa:** zgodnie (najkrótszy R5 − NIK: mediana +0,7 min; Łomianki 53 wobec 59, Sulejówek 33 wobec 32, Nadarzyn 59 wobec 56, Piaseczno 43 wobec 51; tylko Marki 43 wobec 34);
- **Kraków:** R5 dłuższy o ok. 8 min (mediana), najbardziej Wieliczka (36 wobec 25) i Niepołomice (59 wobec 50); Liszki krótsze (39 wobec 49);
- **Poznań:** R5 dłuższy o 10–22 min nawet w najlepszej minucie (Stęszew 58 wobec 36, Tarnowo Podgórne 65 wobec 46, Swarzędz 40 wobec 26, Kórnik 50 wobec 37, Murowana Goślina 52 wobec 42). Wariant „do węzła” (Rondo Kaponiera) nie zmniejsza różnicy. Możliwe przyczyny (niesprawdzone): przewoźnicy podmiejscy bez GTFS w naszych danych (maska pokrycia GTFS w FUA Poznania obejmuje 85,5 % ludności), limit dojścia 12 min (aplikacja mapowa pozwala na dłuższe dojście do szybszej linii), inny punkt „centrum” w NIK, rozkłady z 2025 r.

NIK pokazuje, że KZ była szybsza od samochodu w 5 z 15 par; najkrótszy czas R5 jest krótszy od czasu samochodu NIK tylko w 2 parach (Sulejówek i Piaseczno). Wniosek NIK, że komunikacja zwykle przegrywa z samochodem poza osiami kolejowymi, nasze czasy wzmacniają, a nie osłabiają. Pełne wiersze (także po południu i do węzła): `nik_pairs.csv`.

## 7. Ograniczenia

- **Najszybsza trasa to nie zachowanie.** RAPTOR wybiera przesiadkę, jeśli daje choćby minutę zysku; ludzie częściej wybierają jazdę bez przesiadki kosztem kilku minut, znają rozkład i nie zawsze jadą o najlepszej minucie. Warianty z karą 5 i 10 min to przybliżenie, nie model wyboru.
- **Rozkład długości podróży jest narzucony przez losowanie.** Cel losowany proporcjonalnie do mieszkańców w zasięgu 60 min nie ma zaniku z odległością, więc dłuższe podróże są nadreprezentowane w stosunku do badań ruchu (pole zasięgu rośnie z kwadratem czasu). Podpróby „cel ≤ 30 / 45 min” pokazują, jak silnie wynik zależy od tej decyzji.
- **Rozkład, nie rzeczywistość.** Opóźnienia, zerwane przesiadki i tłok nie są ujęte (odchylenie od rozkładu 1,4–3,0 min według Jakdojade).
- **Szczelina 5 min z najlepszą minutą** skraca czekanie na pierwszy pojazd (pasażer „wychodzi na czas”); czekanie przy przesiadkach jest rozkładowe.
- **Spacer jako alternatywa** pochodzi z czasu pieszego fazy 3 w pełnych minutach (siatka 250 m, środek komórki), trasa KZ z R5 w sekundach.
- **Zespoły przystanków** dziedziczą ograniczenia warstwy przesiadek (RAPORT §20.4): podział Krakowa Głównego, zbyt szerokie zespoły dworcowe, jeden punkt na stację kolejową.
- **Zbiór „miejsca pracy”** obejmuje tylko miasta centralne (Trójmiasto: tylko Gdańsk; GZM: brak).
- **NIK:** inny dzień i rok (2025 wobec rozkładów 2026), aplikacja z danymi w czasie rzeczywistym, nieznany punkt w centrum i nieznany wybór liczby (najkrótsza czy najdłuższa, kierunek).

## 8. Nie zweryfikowano

- Nie porównano żadnej trasy z próby z wyszukiwarką (Google, Jakdojade); zgodność R5 z wyszukiwarką sprawdzono tylko na 30 parach fazy 3 (`qa/access/access.md` §9).
- Definicje Jakdojade (trasy wyszukane czy wybrane, czy z dojściem pieszym, co z ≥ 3 przesiadkami) – nieznane; liczby wzięte z notatki z przeglądu literatury, raportu nie otwierano ponownie.
- Granica obszaru i definicja „przesiadki” w WBR 2015 (czy zmiana pociągu KM na metro to przesiadka, czy dojście piesze między przystankami się liczy) – nie sprawdzono w pełnym raporcie.
- Dopasowanie wariantu „cel ≤ 45 min + kara 5 min” do Jakdojade i WBR może być przypadkowe; nie sprawdzono innych progów ani rozkładu odległości z badań ruchu.
- Rozbicie dojścia przy przesiadkach na pojedyncze przesiadki (z tabeli przejść R5) zgadza się z sumą R5 w 100 % tras z ≥ 3 przejazdami w granicy ±2 s na przejazd; nie sprawdzono, czy R5 nie ogranicza przejść długością (limit przejść R5 nie był zmieniany).
- Odtwarzalność bajt w bajt: sprawdzono tylko liczności klas po ponownym policzeniu zbioru „miejsca pracy” dla Trójmiasta, nie identyczność plików.
- Przypisanie przesiadek do zespołów, które są „między dwoma zespołami” (liczone w obu), może zawyżać użycie małych sąsiednich zespołów; nie sprawdzono na mapie.
- Pary NIK: punkt w centrum, dni pomiaru, wybór liczby (najkrótsza czy najdłuższa, kierunek) i narzędzie (prawdopodobnie Google Maps) – nieznane; obiekty urzędów z OSM nie były sprawdzane z adresami z BIP gmin; przyczyny różnic w Poznaniu (brak GTFS przewoźników podmiejskich, dojście > 12 min) nie były sprawdzane; trasy „PKM3 + 174” ze Stęszewa i z Murowanej Gośliny (ta sama nazwa linii w dwóch kierunkach) nie były sprawdzone w rozkładzie.
- Czy pasażerowie faktycznie przesiadają się w węzłach z listy top 20 (dane biletowe, liczenia) – brak danych; „użycie” to użycie przez trasy najszybsze z próby, nie liczba pasażerów.

## 9. Pliki

- `sample_summary.csv`: liczności klas podróży i czas liczenia.
- `transfer_shares.csv`: udziały 0 / 1 / 2 / ≥ 3 / ≥ 1 / ≥ 2 przesiadek z przedziałami Wilsona i średnia liczba przesiadek, dla zbiorów, wariantów i obszaru startu.
- `external_comparison.csv`: nasze warianty obok Jakdojade 2025 i WBR 2015.
- `trip_composition.csv`: przejazdy, czas, udział chodzenia, czekania (na starcie, przy przesiadkach) i jazdy z przedziałami bootstrap.
- `data/interim/trips/transfer_events.csv` (ok. 13 MB, poza repozytorium): każda przesiadka z próby (przystanki, tryby, dojście, czekanie, zespoły).
- `node_use_top20.csv`, `node_rank_comparison.csv`: węzły.
- `nik_pairs.csv`: pary NIK.
- `results/layers/node_use.parquet` (+ `_meta_node_use.json`): użycie każdego zespołu z `transfer_nodes.parquet`.
- Surowe podróże i odcinki: `data/interim/trips/<aglomeracja>/chunks/` (nie w repozytorium).
