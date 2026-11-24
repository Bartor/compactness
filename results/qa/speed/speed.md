# Rozkładowa prędkość komunikacyjna: linie, obszary, odcinki tramwajowe

Rozkłady: środa 2026-11-25 i sobota 2026-11-28 (feedy pobrane 2026-11-23); OSM 2026-11-22; ludność NSP 2021 w układzie GHSL 2020 (tylko do grup gęstości w części 2). Kod: `pipeline/speed_core.py`, `speed_tables.py`, `speed_areas.py` (+ `speed_areas_out.py`), `tram_stretches.py` (+ `tram_stretches_out.py`), `speed_osm.py`, `speed_report.py`, `speed_text.py`.

**Co to jest.** Rozkładowa prędkość komunikacyjna: długość drogi pojazdu podzielona przez czas z rozkładu jazdy,
z postojami na przystankach. To nie jest prędkość rzeczywista (opóźnienia, korki i punktualność nie są w danych)
ani prędkość jazdy między przystankami. Każda liczba w tej nocie i w plikach pochodzi z rozkładów na środę
2026-11-25 albo sobotę 2026-11-28.

Trzy części na jednej podstawie danych: (1) tabele prędkości linii według typu dnia i pasma godzin, wszystkie środki;
(2) prędkość w obszarach (bloki 1 km); (3) sieć tramwajowa podzielona na odcinki wzdłuż toru, z atrybutami z OSM
i szacunkiem, ile czasu rozkład daje ponad swobodną jazdę. Kolejność w nocie: 1, 3, 2.

## 0. Pasma godzin i dni

Pasma (klucz `speed_time_bands` w `config.yaml`, jedno miejsce dla wszystkich części):

| Dni robocze (środa) | Godziny | Sobota (pasma weekendowe) | Godziny |
|---|---|---|---|
| noc | 23–05 | noc | 23–05 |
| wczesny ranek | 05–07 | rano | 05–09 |
| szczyt poranny | 07–09 | dzień | 09–18 |
| międzyszczyt | 09–15 | wieczór | 18–23 |
| szczyt popołudniowy | 15–18 | | |
| wczesny wieczór | 18–20 | | |
| wieczór | 20–23 | | |

- Kurs należy do pasma godziny **pierwszego odjazdu** (tabele linii i miast, część 1). Przejazd między dwoma
  przystankami należy do pasma godziny **odjazdu z pierwszego z nich** (obszary i odcinki, części 2 i 3), bo opisuje,
  kiedy pojazd jest w danym miejscu. Godziny po 24:00 liczone są modulo 24 h.
- Szczyt poranny 07–09 i wieczór (20–22 zawiera się w 20–23) są zgodne z oknami `time_windows` używanymi w fazach 2–3.
- **Niedziela: nie dodano.** Feed `gzm` kończy ważność 2026-11-28, więc w niedzielę 2026-11-29 nie ma w nim ani
  jednego kursu (GZM w całości bez danych). Poza nim feedy nieoficjalne kończące się 2026-11-28:
  `warsaw_powiat_minski`, `warsaw_radzymin`, `warsaw_lomianki`, `warsaw_nowy_dwor`, `warsaw_powiat_nowodworski`,
  `warsaw_dabrowka`, `krakow_skawina`, `lodz_aleksandrow` (oraz `warsaw_halinow`, `warsaw_sulejowek`, `lodz_strykow`,
  `wroclaw_olesnica`, `wroclaw_oborniki`, które w weekendy nie mają kursów). Niedziela 2026-11-22 też nie przechodzi:
  feedy `warsaw_ztm`, `wroclaw`, `poznan`, `gdansk`, `gdynia` zaczynają się 2026-11-23. Pozostałe oficjalne feedy
  tramwajowe pokrywają 2026-11-29; niedzielę można dodać po następnym pobraniu feedu GZM.

## Podstawa: przejazdy między przystankami

Jedna tabela dla wszystkich części (`pipeline/speed_core.py`, pamięć podręczna `data/interim/speed/hops_*`): wiersz =
pojazd jadący z przystanku do następnego przystanku tego samego kursu. Kursy z warstwy `gtfs_service` (wariant
„wszystkie feedy”, deduplikacja z §15.1 raportu); każdy wiersz pamięta feed, więc feedy nieoficjalne można odfiltrować
albo oznaczyć.

- **Czas** przejazdu = przyjazd na następny przystanek − odjazd z przystanku. Rozkłady podają pełne minuty i nie mają
  osobnych postojów, więc postój na przystanku jest wliczony w czas przejazdu.
- **Długość**: wzdłuż kształtu trasy (`shapes`) między rzutami obu przystanków na ten kształt. Rzutowanie: kandydatami
  są lokalne minima odległości przystanku od kształtu w promieniu 80 m (metro i kolej: 250 / 300 m, bo stacja to jeden
  punkt); spośród kandydatów wybierany jest ciąg o najmniejszej sumie odległości, w którym położenie wzdłuż kształtu
  nie maleje (pętle i linie wracające tą samą ulicą). Gdy przystanek jest dalej niż próg (np. feed `lodz`: kształty
  pomijają pętle końcowe), tylko przejazdy z jego udziałem dostają odległość w linii prostej; gdy kształtu brak albo
  przejazd po kształcie wychodzi krótszy niż w linii prostej, także linia prosta. Pole `len_src` mówi, która długość
  została użyta.
- Rzutowanie liczy się raz na wzorzec (feed, kształt, ciąg przystanków): 1 000–3 300 wzorców na aglomerację i dzień.

## 1. Prędkość linii (wszystkie środki)

Plik do przeglądania: [`../../tables/speed_lines.csv`](../../tables/speed_lines.csv) (+ `speed_lines.json` w układzie
linia → dzień → pasmo). Wiersz = aglomeracja × środek × feed × linia × dzień × pasmo (plus „cała doba”).

Reguły:
- prędkość = suma długości kursów / suma czasów rozkładowych kursów linii rozpoczętych w paśmie; obok mediana
  prędkości kursów;
- długość kursu = suma długości przejazdów; czas = ostatni przyjazd − pierwszy odjazd; kursy kolejowe feedu
  ogólnopolskiego są przycięte do przejazdów z oboma przystankami w FUA + 15 km (miejska część kursu dalekobieżnego);
- pominięte (licznik w `tables/speed_excluded_trips.csv`): komunikacja zastępcza kolei, przystanek bez położenia,
  długość < 1 km, czas < 5 min, mniej niż 3 przystanki, prędkość poza 5–60 km/h (tramwaj, trolejbus), 5–80 (autobus,
  metro), 5–160 (kolej) – progi jak w `tram_speed.py`;
- odstęp w paśmie = długość pasma / liczba kursów kierunku z większą liczbą kursów (`direction_id`); gdy linia nie ma
  `direction_id`, długość pasma / (kursy / 2), z adnotacją w `headway_rule`;
- średnia odległość między przystankami = długość / liczba przejazdów;
- `share_trips_fallback` = udział kursów z choć jednym przejazdem liczonym w linii prostej; `flag` oznacza feedy
  nieoficjalne („feed nieoficjalny, niezweryfikowany”), linie bez kształtów (prędkość zaniżona) i pasma z mniej niż
  3 kursami.

### 1.1 Tramwaje według pasm (km/h, suma długości / suma czasu)

| Miasto | śr. noc 23–05 | śr. wczesny ranek 05–07 | śr. szczyt poranny 07–09 | śr. międzyszczyt 09–15 | śr. szczyt popołudniowy 15–18 | śr. wczesny wieczór 18–20 | śr. wieczór 20–23 | śr. doba |
|---|---|---|---|---|---|---|---|---|
| Warszawa | 19,1 | 18,7 | 18,5 | 18,6 | 18,5 | 18,8 | 19,1 | 18,7 |
| Kraków | 20,3 | 20,1 | 20,0 | 19,9 | 20,0 | 19,9 | 20,1 | 20,0 |
| Wrocław | 17,3 | 16,4 | 16,2 | 16,3 | 16,0 | 16,7 | 17,9 | 16,5 |
| Poznań | 22,0 | 20,0 | 19,8 | 19,8 | 19,7 | 19,9 | 20,8 | 20,0 |
| Łódź | 17,5 | 17,2 | 17,1 | 17,1 | 17,2 | 17,3 | 17,6 | 17,2 |
| Gdańsk | 18,0 | 17,9 | 17,8 | 17,7 | 17,8 | 17,7 | 17,9 | 17,8 |
| GZM | 20,2 | 18,0 | 18,0 | 18,0 | 18,0 | 18,1 | 18,3 | 18,3 |

| Miasto | sob. noc 23–05 | sob. rano 05–09 | sob. dzień 09–18 | sob. wieczór 18–23 | sob. doba |
|---|---|---|---|---|---|
| Warszawa | 19,1 | 19,1 | 19,0 | 19,2 | 19,1 |
| Kraków | 19,5 | 20,3 | 20,2 | 20,2 | 20,2 |
| Wrocław | 17,9 | 17,9 | 17,4 | 17,6 | 17,6 |
| Poznań | 22,6 | 20,7 | 20,0 | 20,4 | 20,3 |
| Łódź | 17,3 | 17,3 | 17,4 | 17,5 | 17,4 |
| Gdańsk | 18,1 | 17,6 | 17,6 | 17,8 | 17,7 |
| GZM | 20,3 | 18,0 | 18,2 | 18,1 | 18,4 |

Liczby kursów w pasmach: `tables/speed_city_mode_band.csv`. W paśmie nocnym jest najmniej kursów tramwajowych (69–396 w środę), więc ta kolumna jest najmniej pewna.

### 1.2 Szczyt a wieczór (środa)

| Aglomeracja | Środek | Szczyt 07–09 | Międzyszczyt 09–15 | Szczyt 15–18 | Wieczór 20–23 | Wieczór − szczyt poranny | Sobota 09–18 |
|---|---|---|---|---|---|---|---|
| Warszawa | tramwaj | 18,5 | 18,6 | 18,5 | 19,1 | 0,6 | 19,0 |
| Warszawa | autobus | 21,8 | 22,5 | 21,6 | 24,6 | 2,8 | 22,9 |
| Warszawa | metro | 33,1 | 33,1 | 33,1 | 33,1 | 0,0 | 33,1 |
| Kraków | tramwaj | 20,0 | 19,9 | 20,0 | 20,1 | 0,0 | 20,2 |
| Kraków | autobus | 24,4 | 24,6 | 24,0 | 26,6 | 2,2 | 25,9 |
| Wrocław | tramwaj | 16,2 | 16,3 | 16,0 | 17,9 | 1,7 | 17,4 |
| Wrocław | autobus | 20,5 | 20,6 | 20,0 | 23,4 | 2,9 | 21,5 |
| Poznań | tramwaj | 19,8 | 19,8 | 19,7 | 20,8 | 1,0 | 20,0 |
| Poznań | autobus | 23,5 | 23,3 | 22,7 | 25,3 | 1,8 | 23,2 |
| Łódź | tramwaj | 17,1 | 17,1 | 17,2 | 17,6 | 0,5 | 17,4 |
| Łódź | autobus | 21,4 | 21,1 | 21,5 | 21,9 | 0,6 | 21,9 |
| Trójmiasto | tramwaj | 17,8 | 17,7 | 17,8 | 17,9 | 0,1 | 17,6 |
| Trójmiasto | autobus | 21,9 | 21,9 | 21,2 | 24,4 | 2,5 | 22,8 |
| Trójmiasto | trolejbus | 19,9 | 19,4 | 18,8 | 21,3 | 1,5 | 20,3 |
| GZM | tramwaj | 18,0 | 18,0 | 18,0 | 18,3 | 0,3 | 18,2 |
| GZM | autobus | 24,5 | 24,4 | 24,5 | 26,8 | 2,3 | 25,8 |
| GZM | trolejbus | 21,6 | 21,5 | 21,6 | 23,8 | 2,3 | 21,3 |

**Odczyt.** Tramwaje we Wrocławiu mają największą różnicę między szczytem a wieczorem (16,2 wobec 17,9 km/h, +1,7 km/h);
w Poznaniu +1,0, w Warszawie +0,6, w Łodzi +0,5, w GZM +0,3, w Krakowie i Gdańsku praktycznie zero. Rozkłady
Krakowa i Gdańska mają więc te same czasy przez cały dzień, a Wrocławia i Poznania – osobne czasy na szczyt.
Autobusy mają różnicę 1,8–2,9 km/h we wszystkich miastach poza Łodzią (+0,6). Metro i kolej nie zmieniają się w ciągu
dnia. Różnica pokazuje, ile rozkład zakłada na korki i wymianę pasażerów w szczycie; nie mówi, jak jest naprawdę.

### 1.3 Kolej i feedy bez kształtów tras

| Aglomeracja | Środek | Kursy | Prędkość, km/h | Kursy z odcinkami w linii prostej | Kształt / linia prosta (kursy z kształtem) | Udział wozokm feedów nieoficjalnych |
|---|---|---|---|---|---|---|
| Warszawa | autobus | 31230 | 22,9 | 0,7 % | 1,09 | 17,9 % |
| Warszawa | metro | 1255 | 33,1 | 0,0 % | 1,02 | 0,0 % |
| Warszawa | kolej | 1757 | 54,3 | 0,0 % | 1,04 | 0,0 % |
| Warszawa | tramwaj | 7123 | 18,7 | 0,0 % | 1,04 | 0,0 % |
| Kraków | autobus | 14583 | 25,2 | 11,4 % | 1,11 | 2,6 % |
| Kraków | kolej | 472 | 50,5 | 0,0 % | 1,04 | 0,0 % |
| Kraków | tramwaj | 3710 | 20,0 | 0,0 % | 1,06 | 0,0 % |
| Wrocław | autobus | 8800 | 21,3 | 1,5 % | 1,10 | 5,6 % |
| Wrocław | kolej | 605 | 60,9 | 0,0 % | 1,03 | 0,0 % |
| Wrocław | tramwaj | 4164 | 16,5 | 0,0 % | 1,03 | 0,0 % |
| Poznań | autobus | 8462 | 23,9 | 1,0 % | 1,12 | 0,0 % |
| Poznań | kolej | 533 | 61,1 | 0,0 % | 1,03 | 0,0 % |
| Poznań | tramwaj | 3557 | 20,0 | 0,0 % | 1,04 | 0,0 % |
| Łódź | autobus | 8062 | 21,7 | 45,9 % | 1,10 | 23,4 % |
| Łódź | kolej | 416 | 56,4 | 0,0 % | 1,05 | 0,0 % |
| Łódź | tramwaj | 3312 | 17,2 | 47,0 % | 1,04 | 0,0 % |
| Trójmiasto | autobus | 9581 | 22,4 | 0,0 % | 1,11 | 0,0 % |
| Trójmiasto | kolej | 685 | 45,8 | 0,0 % | 1,03 | 0,0 % |
| Trójmiasto | tramwaj | 1542 | 17,8 | 0,0 % | 1,05 | 0,0 % |
| Trójmiasto | trolejbus | 1328 | 19,8 | 0,0 % | 1,06 | 0,0 % |
| GZM | autobus | 18962 | 25,1 | 4,5 % | 1,15 | 0,0 % |
| GZM | kolej | 918 | 53,7 | 0,0 % | 1,07 | 0,0 % |
| GZM | tramwaj | 3059 | 18,3 | 9,7 % | 1,05 | 0,0 % |
| GZM | trolejbus | 480 | 22,1 | 0,0 % | 1,11 | 0,0 % |

**Co robi brak kształtów.** Bez `shapes` długość liczona jest odcinkami prostymi między przystankami, a to zaniża
długość, więc i prędkość, mniej więcej o czynnik z kolumny „kształt / linia prosta” (dla autobusów 1,09–1,16, dla
tramwajów 1,03–1,07). Bez kształtów są: `krakow_ald` (oficjalny, ok. 18 % przejazdów autobusowych Krakowa),
`warsaw_zabki`, `lodz_lka_bus`, `lodz_suburban_qbx` (nieoficjalne) oraz autobusy komunikacji zastępczej
w `polish_trains` (pominięte). Ich wiersze w `speed_lines.csv` mają adnotację; prędkość tych linii jest dolnym
oszacowaniem. W porównaniach autobusów między miastami Kraków jest przez to zaniżony o ok. 1–2 % (18 % przejazdów
× ok. 10 %).

### 1.4 Kontrola: mediany tramwajów z `qa/transit/tram_speed_per_city.csv`

| Miasto | Dzień | Opublikowana mediana | Ponowne uruchomienie tram_speed | Ta warstwa (mediana kursów) | Kursy (opubl. / tu) | 95. centyl różnicy na kurs |
|---|---|---|---|---|---|---|
| Warszawa | środa | 18,60 | 18,60 | 18,60 | 7123 / 7123 | 0,04 |
| Warszawa | sobota | 18,94 | 18,94 | 18,94 | 4250 / 4250 | 0,04 |
| Kraków | środa | 19,84 | 19,84 | 19,84 | 3710 / 3710 | 0,01 |
| Kraków | sobota | 19,95 | 19,95 | 19,95 | 2221 / 2221 | 0,01 |
| Wrocław | środa | 16,27 | 16,27 | 16,22 | 4164 / 4164 | 0,15 |
| Wrocław | sobota | 17,47 | 17,47 | 17,41 | 2900 / 2900 | 0,16 |
| Poznań | środa | 19,49 | 19,49 | 19,49 | 3557 / 3557 | 0,06 |
| Poznań | sobota | 19,99 | 19,99 | 19,99 | 2615 / 2615 | 0,06 |
| Łódź | środa | 16,92 | 16,92 | 16,96 | 3312 / 3312 | 0,46 |
| Łódź | sobota | 17,20 | 17,20 | 17,19 | 2312 / 2312 | 0,44 |
| Gdańsk | środa | 18,01 | 18,01 | 17,78 | 1542 / 1542 | 0,67 |
| Gdańsk | sobota | 17,97 | 17,97 | 17,77 | 1080 / 1080 | 0,67 |
| GZM | środa | 17,23 | 17,23 | 17,42 | 3059 / 3059 | 3,17 |
| GZM | sobota | 17,18 | 17,18 | 17,56 | 2455 / 2455 | 3,17 |

Ponowne uruchomienie `tram_speed.tram_trips` daje opublikowane mediany co do setnej i te same liczby kursów.
Mediany tej warstwy różnią się o −0,25 do +0,2 km/h, bo długość liczona jest inaczej: tutaj wzdłuż kształtu między
pierwszym a ostatnim przystankiem, w `tram_speed` cała długość kształtu, a przy niezgodności z odcinkami prostymi
większej niż 15 % – odcinki proste. Największe różnice na pojedynczych kursach są w GZM (95. centyl 3,2 km/h): tam
`tram_speed` przechodzi na odcinki proste, a ta warstwa zachowuje kształt na pozostałych przejazdach. Liczby kursów
są identyczne we wszystkich miastach, więc zbiór kursów jest ten sam.

### 1.5 Wcześniejsze szybkie spojrzenie (hipoteza) a ta warstwa

| Aglomeracja | Grupa kursów | Kursy | Odcinki proste × 1,04 | Kształt trasy |
|---|---|---|---|---|
| Warszawa | szczyty 07-09 + 15-17 | 1911 | 18,5 | 18,5 |
| Warszawa | po 20:00 | 774 | 19,2 | 19,2 |
| Kraków | szczyty 07-09 + 15-17 | 955 | 19,5 | 20,0 |
| Kraków | po 20:00 | 374 | 19,6 | 20,1 |
| Wrocław | szczyty 07-09 + 15-17 | 957 | 16,1 | 16,1 |
| Wrocław | po 20:00 | 599 | 18,0 | 18,0 |
| Poznań | szczyty 07-09 + 15-17 | 906 | 19,7 | 19,8 |
| Poznań | po 20:00 | 407 | 20,8 | 20,9 |
| Łódź | szczyty 07-09 + 15-17 | 722 | 17,2 | 17,1 |
| Łódź | po 20:00 | 478 | 17,8 | 17,7 |
| Trójmiasto | szczyty 07-09 + 15-17 | 424 | 17,5 | 17,8 |
| Trójmiasto | po 20:00 | 129 | 17,6 | 18,0 |
| GZM | szczyty 07-09 + 15-17 | 651 | 17,7 | 18,0 |
| GZM | po 20:00 | 391 | 18,5 | 18,8 |

Szybkie spojrzenie (16,1 w szczytach wobec 18,0 km/h po 20:00 we Wrocławiu, największa różnica z siedmiu miast)
**potwierdza się** przy właściwej geometrii: 16,1 wobec 18,0 km/h; przy pasmach z tej noty 16,2 (07–09) wobec 17,9
(20–23). Odcinki proste × 1,04 dawały prawie to samo (różnica 0–0,5 km/h, największa w Krakowie i Gdańsku, gdzie
kształt jest o 5–7 % dłuższy od linii prostej). Hipoteza o centrum Wrocławia (część 2) też się potwierdza.

### 1.6 Porównanie z opublikowanymi zestawieniami

Znalezione samodzielnie (wyszukiwarka, 2026-11-24), oba oparte na raporcie portalu Puls Gdańska liczonym z rozkładów:
- bankier.pl, 11.05.2021 („Polskie tramwaje nie są demonami prędkości”), średnie całodobowe: Poznań 20,8, Warszawa 18,9,
  Kraków 18,8, GOP 18,6, Wrocław 17,8, Gdańsk 17,1, Łódź 15,6 km/h;
- antyweb.pl, 25.07.2022 („Prędkość tramwajów w Polsce”, raport Pulsu Gdańska za 2022 r.): Poznań 19,85, Warszawa 19,33,
  Kraków 19,21, GOP 17,86, Gdańsk 17,48, Łódź 16,86, Wrocław 16,65 km/h; w szczycie Wrocław 15,87, poza szczytem 17,51.

Ta warstwa (cała doba, środa): Kraków 20,0, Poznań 20,0, Warszawa 18,7, GZM 18,3, Gdańsk 17,8, Łódź 17,2, Wrocław 16,5.
Kolejność jest podobna do zestawienia z 2022 r. (Wrocław i Łódź na końcu, Poznań i Kraków na początku, Warszawa
pośrodku), poziomy różnią się o mniej niż 1 km/h (Kraków +0,8, Warszawa −0,6). Różnica Wrocławia między szczytem a resztą
dnia (ok. 1,6 km/h w 2022 r.) jest tego samego rzędu co tutaj. Nie sprawdzono, jak raport definiuje średnią (po liniach
czy po kursach) ani z jakich dat są rozkłady; liczby z artykułów odczytano narzędziem do pobierania stron, nie
z samego raportu.

## 3. Odcinki sieci tramwajowej

Pliki: [`../../tables/tram_stretches.csv`](../../tables/tram_stretches.csv) (wiersz = odcinek × kierunek),
`tram_stretch_bands.csv` (to samo w układzie długim: odcinek × kierunek × dzień × pasmo, pod scenariusze),
`tram_stretch_stop_pairs.csv` (para przystanków GTFS → odcinek, kierunek, numer krawędzi), `tram_stretch_stops.csv`
(miejsca przystankowe odcinka po kolei z identyfikatorami słupków), warstwa `layers/tram_stretches.parquet`.

**Reguła odcinka** (stałe w `pipeline/tram_stretches.py`):
1. Miejsca przystankowe: słupki tramwajowe o tej samej znormalizowanej nazwie w promieniu 300 m albo dowolne słupki
   w promieniu 40 m są jednym miejscem, chyba że jakiś kurs jedzie bezpośrednio z jednego do drugiego (dwa przystanki
   o tej samej nazwie przed i za rondem zostają osobno – inaczej przejazd przez rondo by znikał).
2. Graf miejsc: krawędź tam, gdzie kurs jedzie z miejsca do miejsca bez innego przystanku.
3. Granice odcinków: miejsca o stopniu różnym od 2 (rozgałęzienia obsługi, krańce), miejsca, gdzie zaczyna lub kończy
   co najmniej 20 kursów albo 5 % przejeżdżających, oraz 10 najbardziej obsługiwanych miejsc miasta.
4. Łańcuchy między granicami dłuższe niż 14 min (2 × 7 min, średni czas środowy) są dzielone na przystankach na
   części po ok. 7 min. Część krótsza niż **5 min** albo z jednym przejazdem jest łączona z sąsiednią: przez granicę
   stopnia 2 albo przez rozgałęzienie w stronę sąsiada, na którego przechodzi co najmniej połowa kursów z krótkiej
   części. Odcinek może więc przechodzić przez rozgałęzienie, przez które jedzie większość jego kursów. Gdy połączyć
   się nie da, odcinek zostaje z `below_min = true`: jego prędkość jest w plikach, ale nie wchodzi do rankingów ani do
   udziału „wolnych” wozokilometrów (udział takich odcinków podany osobno).
5. **Dlaczego 5 minut.** Czasy są w pełnych minutach, więc czas odcinka jest obarczony zaokrągleniem na jego dwóch
   końcach: przy dwóch niezależnych błędach ±0,5 min odchylenie standardowe ok. 0,41 min, czyli ok. 8 % przy 5 min
   (±1,4 km/h przy 17 km/h) i ok. 6 % przy 7 min. Krócej błąd rośnie szybko (20 % przy 2 min). Kontrola w 3.1 pokazuje,
   że linie na wspólnym torze mają zwykle identyczne czasy, więc więcej linii tego błędu nie zmniejsza – trzeba
   dłuższego odcinka.
6. Identyfikator: `stretch_id` = `<miasto>-<8 znaków skrótu SHA-1 uporządkowanych kluczy miejsc>`, kierunek A (od
   miejsca o mniejszym kluczu) lub B; `stretch_dir_id` = oba razem. Klucz miejsca = znormalizowana nazwa + środek
   w siatce 100 m, więc identyfikatory są stałe, dopóki nie zmienią się przystanki i reguła.
7. Prędkość odcinka w paśmie = suma długości / suma czasów wszystkich przejazdów na jego krawędziach (kursy
   przejeżdżające tylko część odcinka liczą się w tej części); czas rozkładowy = długość reprezentatywna (suma median
   długości krawędzi) / prędkość.

Geometria: dla każdej krawędzi najczęstszy kawałek kształtu GTFS, sklejone; dopasowanie do toru OSM: punkty co 10 m
wzdłuż odcinka do najbliższego toru `railway=tram` w promieniu 15 m.

| Miasto | Przystanki (słupki) | Miejsca | Odcinki | Odcinki × kierunki | Mediana długości, m | Przejazdy poza odcinkami | Dopasowanie do toru OSM (mediana / 10. centyl) | Odległość od toru, m (mediana) | W jezdni | Wydzielone | Bez dopasowania |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 608 | 278 | 78 | 141 | 2 092 | 0,0 % | 100 % / 92 % | 1,4 | 7,1 % | 91,0 % | 1,9 % |
| Kraków | 352 | 163 | 38 | 74 | 2 514 | 0,3 % | 100 % / 100 % | 0,0 | 14,6 % | 84,9 % | 0,5 % |
| Wrocław | 447 | 213 | 61 | 116 | 1 975 | 0,3 % | 100 % / 92 % | 1,4 | 28,1 % | 69,4 % | 2,5 % |
| Poznań | 303 | 144 | 44 | 80 | 1 825 | 0,0 % | 100 % / 94 % | 1,2 | 14,4 % | 83,9 % | 1,7 % |
| Łódź | 464 | 255 | 86 | 144 | 1 712 | 0,0 % | 100 % / 83 % | 1,0 | 18,9 % | 72,2 % | 8,9 % |
| Gdańsk | 245 | 125 | 32 | 57 | 2 199 | 0,0 % | 100 % / 100 % | 1,0 | 9,7 % | 89,6 % | 0,7 % |
| GZM | 712 | 365 | 74 | 137 | 2 390 | 0,0 % | 100 % / 90 % | 1,3 | 20,0 % | 77,0 % | 2,9 % |

Dopasowanie do toru OSM: w każdym mieście mediana odcinków ma 100 % punktów w promieniu 15 m od toru, mediana odległości
0–1,5 m (kształty GTFS biegną po torach). Najsłabiej Łódź (10. centyl 83 %, 9 % długości bez dopasowania: kształty
`lodz` miejscami skracają łuki i pętle) i GZM (3 %). Przejazdy niewchodzące do żadnego odcinka: 0–1,6 % (krawędzie
występujące tylko w sobotę albo przejazdy między słupkami jednego miejsca). Odcinki: 32 (Gdańsk) do 86 (Łódź),
mediana długości 1,7–2,4 km, 5–7 przystanków.

### 3.1 Zaokrąglenie do minut: kontrola

| Czas odcinka (śr. 09–15) | Odcinki × kierunki z ≥ 2 liniami | Z różnicą czasu między liniami | Średni rozrzut, min |
|---|---|---|---|
| < 3 min | 35 | 0,0 % | 0,00 |
| 3-5 min | 34 | 8,8 % | 0,03 |
| 5-8 min | 120 | 11,7 % | 0,04 |
| 8-12 min | 91 | 12,1 % | 0,09 |
| >= 12 min | 39 | 0,0 % | 0,00 |

Linie jadące tym samym odcinkiem w tej samej godzinie mają w 88–100 % przypadków **identyczny** czas rozkładowy
(średni rozrzut 0,03–0,09 min). Błąd zaokrąglenia jest więc wspólny dla wszystkich linii odcinka (planista nadaje
czasy przejazdu odcinkom, nie liniom) i nie maleje z liczbą linii ani kursów; jedyną obroną jest długość odcinka.
Stąd próg 5 min, a nie próg liczby kursów. Kontrola nie mierzy samego błędu (nie znamy „prawdziwego” czasu), pokazuje
tylko, że uśrednianie po liniach go nie usuwa.

### 3.2 Torowisko w jezdni czy wydzielone: reguła i sprawdzenie

**Reguła** (kawałki toru OSM do 20 m): „w jezdni”, gdy oba węzły odcinka toru należą do jednej drogi (tor narysowany na
osi jezdni), gdy tor ma `embedded=yes`, gdy w promieniu 10 m jest droga z `embedded_rails=tram`, albo gdy oś jezdni
(drogi od residential w górę, living_street, busway) jest bliżej niż 4,5 m (3 m przy drodze jednokierunkowej, czyli
zwykle jednej jezdni z dwóch); „w strefie pieszej” – te same testy spełnione przez `highway=pedestrian`; „wydzielone” –
wszystko inne. Tag `embedded_rails` ma 743 dróg w obszarze, `embedded=yes` 330 odcinków torów, więc głównym testem
jest geometria.

**Sprawdzenie na 16 odcinkach w pięciu miastach** (`stretches/separation_probe.csv`: najbliższa ulica, jej tagi,
odległość toru od osi; ocena według wiedzy o tych ulicach, nie w terenie):

| Miasto | Odcinek (ulica) | W jezdni wg reguły | Ocena |
|---|---|---|---|
| Kraków | Filharmonia → Teatr Słowackiego (Basztowa) | 97 % | zgodne: tory w jezdni |
| Kraków | Plac Bohaterów Getta → Starowiślna | 63 % | zgodne: Starowiślna w jezdni, most osobno |
| Kraków | Plac Bohaterów Getta → Łagiewniki SKA (Kalwaryjska) | 41 % | zgodne: północna część w jezdni, dalej wydzielone |
| Kraków | Filharmonia → Stradom (Dietla) | 47 % | prawdopodobnie zgodne: pas zieleni na Dietla wydzielony, dojazdy w jezdni |
| Kraków | al. Pokoju; al. Andersa | 1 % | zgodne: torowisko w pasie dzielącym |
| Warszawa | Al. Jerozolimskie, Marszałkowska, Grójecka, Okopowa, Targowa | 1–3 % | zgodne: torowiska wydzielone |
| Warszawa | Dw. Wschodni → Kawęczyńska | 47 % | zgodne: Kawęczyńska w jezdni |
| Łódź | Piotrkowska (Kościuszki-Mickiewicza → Przybyszewskiego) | 87 % | zgodne: południowa Piotrkowska w jezdni |
| Łódź | Zgierska; Legionów | 93 %; 100 % | zgodne |
| Łódź | al. Kościuszki, al. Śmigłego-Rydza | 1–3 % | zgodne: torowiska wydzielone |
| Wrocław | Pomorska; Renoma → Rynek (Podwale, Świdnicka) | 59 %; 70 % | zgodne |
| Wrocław | Legnicka (Pl. Orląt → Mikołajów) | 20 % | zgodne w przybliżeniu: Legnicka głównie z torowiskiem w pasie dzielącym |
| Wrocław | Arkady → Oławska (Świdnicka) | 19 % | **prawdopodobnie błąd**: na Świdnickiej tramwaj jeździ w jezdni; tory narysowane obok osi szerokiej ulicy |
| Poznań | Rondo Kaponiera → Święty Marcin | 3 % | **niepewne**: po przebudowie ulica z ograniczonym ruchem i torem w jezdni wspólnej; reguła daje „wydzielone” |
| GZM | Chorzów Rynek → Świętochłowice (Wolności) | 79 % | zgodne: tory w jezdni |
| GZM | granica Bytom–Świętochłowice → Łagiewniki (Bytomska) | 0 % przy odległości od osi 1,8 m | **niewyjaśnione**: sonda widzi oś drogi 1,8 m od kształtu, klasyfikacja toru OSM jej nie widzi |

Wniosek: reguła dobrze rozpoznaje torowiska wydzielone w pasie dzielącym i tory na osi wąskich ulic; **zaniża udział
jazdy w jezdni na szerokich ulicach**, gdzie tory narysowano kilka metrów od osi narysowanej jedną linią (Świdnicka
we Wrocławiu, prawdopodobnie Święty Marcin w Poznaniu). Udziały w jezdni (Warszawa 7 %, Gdańsk 10 %, Kraków i Poznań
14–15 %, Łódź 19 %, GZM 20 %, Wrocław 28 % długości) są więc dolnym oszacowaniem; kolejność miast wydaje się wiarygodna.

### 3.3 Zapas rozkładowy (model jazdy swobodnej)

**Model jazdy swobodnej** dla przejazdu o długości d: rozpędzanie ze stałym przyspieszeniem do limitu, jazda z
limitem, hamowanie; gdy przejazd jest za krótki, by osiągnąć limit, trójkątny przebieg prędkości; do tego postój na
przystanku. Czas swobodny odcinka = suma po krawędziach (mediana długości krawędzi). **Zapas = czas rozkładowy − czas
swobodny**; zapas na km = zapas / długość; zapas na skrzyżowanie = zapas / liczba skrzyżowań z drogą (tylko jako
liczba pochodna, z zastrzeżeniem poniżej).

| Parametr | Wartość główna | Wrażliwość | Skąd |
|---|---|---|---|
| przyspieszenie średnie 0 → limit | 1,0 m/s² | 0,7 / 1,3 | założenie; nowe tramwaje niskopodłogowe mają przyspieszenie rozruchu ok. 1,0–1,3 m/s² (dane producentów, nie zweryfikowano), średnie do 50 km/h jest niższe |
| hamowanie służbowe | 1,0 m/s² | 0,8 / 1,3 | założenie; hamowanie służbowe tramwajów 1,0–1,5 m/s², nagłe powyżej 2,5 m/s² (nie zweryfikowano) |
| limit prędkości | 50 km/h | 40 / 60 / 70 | założenie; w miastach tramwaje jeżdżą zwykle z limitem 30–50 km/h, na torowiskach wydzielonych do 60–70 km/h; limitów z OSM (`maxspeed` na torach) nie użyto, bo są rzadko podane |
| postój na przystanku | 20 s | 10 / 30 | założenie; GTFS nie podaje postojów |
| łuki (wariant) | bez ograniczenia | przyspieszenie boczne 0,65 m/s² | założenie; promień z geometrii kształtu GTFS |

Model jest celowo prosty i „optymistyczny”: tramwaj zawsze rusza i hamuje jak najszybciej, nigdy nie czeka.
**Zapas miesza wszystko, czego model nie zawiera:** czekanie na sygnalizacji, ograniczenia prędkości (rozjazdy, łuki,
skrzyżowania, odcinki w złym stanie), jazdę we wspólnym ruchu i za innym tramwajem, dłuższą wymianę pasażerów niż
20 s i rezerwy wpisane w rozkład. **Nie jest to pomiar strat na sygnalizacji** i „zapas na skrzyżowanie” nie mówi,
ile kosztuje jedno skrzyżowanie; to tylko zapas odcinka podzielony przez liczbę skrzyżowań, przydatny do
porównywania odcinków podobnego typu.

Udział zapasu w czasie rozkładowym, szczyt poranny w środę (odcinki ≥ 5 min):

| Wariant | Warszawa | Kraków | Wrocław | Poznań | Łódź | Gdańsk | GZM | Min. korelacja rang z głównym | Min. wspólnych w top 10 | Maks. udział odcinków z ujemnym zapasem |
|---|---|---|---|---|---|---|---|---|---|---|
| główny | 28 % | 25 % | 35 % | 23 % | 36 % | 30 % | 28 % | 1,00 | 10 | 16 % |
| przysp. 0,7 m/s² | 25 % | 22 % | 32 % | 20 % | 33 % | 27 % | 24 % | 0,99 | 9 | 20 % |
| przysp. 1,3 m/s² | 30 % | 27 % | 37 % | 25 % | 37 % | 31 % | 29 % | 1,00 | 9 | 6 % |
| hamowanie 0,8 m/s² | 27 % | 24 % | 33 % | 21 % | 34 % | 28 % | 26 % | 0,99 | 9 | 16 % |
| hamowanie 1,3 m/s² | 30 % | 27 % | 37 % | 25 % | 37 % | 31 % | 29 % | 1,00 | 9 | 6 % |
| limit 40 km/h | 22 % | 18 % | 30 % | 16 % | 30 % | 24 % | 22 % | 1,00 | 9 | 24 % |
| limit 60 km/h | 32 % | 29 % | 38 % | 26 % | 38 % | 33 % | 31 % | 0,99 | 9 | 4 % |
| limit 70 km/h | 33 % | 31 % | 39 % | 28 % | 40 % | 34 % | 32 % | 0,99 | 9 | 4 % |
| postój 10 s | 39 % | 36 % | 45 % | 34 % | 45 % | 40 % | 38 % | 0,99 | 9 | 3 % |
| postój 30 s | 18 % | 15 % | 25 % | 12 % | 26 % | 19 % | 17 % | 0,97 | 8 | 29 % |
| łuki: 0,65 m/s² | 19 % | 16 % | 22 % | 6 % | 25 % | 14 % | 7 % | 0,81 | 6 | 36 % |

**Odczyt.** Poziom zapasu zależy od parametrów (postój 10–30 s zmienia udział o ok. ±10 pkt proc.), ale **kolejność
odcinków prawie nie** (korelacja rang ≥ 0,98 dla wszystkich wariantów poza łukami, w top 10 zostaje 8–10 tych samych
odcinków). Rankingi zapasu są więc odporne na wybór parametrów, liczby bezwzględne nie. Ujemny zapas (rozkład szybszy
niż model) mają głównie szybkie torowiska wydzielone (PST w Poznaniu 34 km/h, Pleszów w Krakowie 34–36 km/h, trasy
do Franowa, Miłostowa, Żerania): tam realny limit jest wyższy niż 50 km/h, co wariant 70 km/h potwierdza (Poznań bez
ujemnych). Wariant z łukami mocno zmienia wynik (GZM i Poznań: udział zapasu spada do ok. 6 %, ok. 35 % odcinków
ujemnych), bo promienie z kształtów GTFS są zaszumione; tego wariantu nie należy używać, dopóki promienie nie będą
liczone na torach OSM.

### 3.4 Miasta: prędkość na odcinkach i udział wolnych odcinków (środa)

| Miasto | Pasmo | Prędkość, km/h | Wozokm < 12 km/h | < 15 km/h | < 18 km/h | Zapas / czas rozkładowy | Wozokm na odcinkach < 5 min |
|---|---|---|---|---|---|---|---|
| Warszawa | szczyt poranny 07–09 | 18,6 | 3,8 % | 13,9 % | 36,2 % | 28,5 % | 7,3 % |
| Warszawa | międzyszczyt 09–15 | 18,8 | 3,2 % | 12,6 % | 34,9 % | 27,3 % | 7,5 % |
| Warszawa | wieczór 20–23 | 19,3 | 1,7 % | 12,3 % | 31,7 % | 25,2 % | 7,4 % |
| Kraków | szczyt poranny 07–09 | 20,1 | 0,3 % | 5,9 % | 24,3 % | 25,4 % | 7,0 % |
| Kraków | międzyszczyt 09–15 | 20,0 | 0,3 % | 6,2 % | 25,7 % | 25,8 % | 6,9 % |
| Kraków | wieczór 20–23 | 20,1 | 0,3 % | 6,3 % | 26,2 % | 25,4 % | 7,3 % |
| Wrocław | szczyt poranny 07–09 | 16,2 | 8,4 % | 34,5 % | 65,0 % | 35,1 % | 6,8 % |
| Wrocław | międzyszczyt 09–15 | 16,4 | 5,9 % | 32,7 % | 64,2 % | 34,1 % | 6,9 % |
| Wrocław | wieczór 20–23 | 17,9 | 3,3 % | 20,3 % | 44,5 % | 28,4 % | 7,1 % |
| Poznań | szczyt poranny 07–09 | 19,7 | 0,1 % | 5,7 % | 29,4 % | 23,0 % | 13,0 % |
| Poznań | międzyszczyt 09–15 | 19,8 | 0,1 % | 5,7 % | 29,4 % | 23,0 % | 13,0 % |
| Poznań | wieczór 20–23 | 20,6 | 0,1 % | 3,9 % | 24,7 % | 19,2 % | 13,0 % |
| Łódź | szczyt poranny 07–09 | 17,3 | 3,4 % | 21,9 % | 44,5 % | 35,5 % | 12,3 % |
| Łódź | międzyszczyt 09–15 | 17,3 | 3,5 % | 21,9 % | 48,1 % | 35,6 % | 12,4 % |
| Łódź | wieczór 20–23 | 17,7 | 2,1 % | 16,6 % | 44,1 % | 33,9 % | 12,7 % |
| Gdańsk | szczyt poranny 07–09 | 17,9 | 1,7 % | 8,2 % | 54,7 % | 29,8 % | 5,0 % |
| Gdańsk | międzyszczyt 09–15 | 17,7 | 2,0 % | 9,7 % | 55,1 % | 29,8 % | 5,2 % |
| Gdańsk | wieczór 20–23 | 17,8 | 1,5 % | 11,5 % | 51,4 % | 29,2 % | 4,9 % |
| GZM | szczyt poranny 07–09 | 18,2 | 1,3 % | 12,6 % | 47,4 % | 27,5 % | 4,5 % |
| GZM | międzyszczyt 09–15 | 18,1 | 1,2 % | 12,7 % | 47,8 % | 27,7 % | 4,5 % |
| GZM | wieczór 20–23 | 18,2 | 1,7 % | 14,9 % | 47,1 % | 27,5 % | 3,7 % |

### 3.5 Najwolniejsze odcinki i największy zapas na km, szczyt poranny w środę

Ranking: odcinki co najmniej 5-minutowe (`below_min = false`) z co najmniej 8 kursami w paśmie 07–09; dwie listy po 10:
najniższa prędkość i największy zapas na km. Kolumny OSM: udział długości w jezdni, skrzyżowania z drogą (w nawiasie
z sygnalizacją w promieniu 35 m), przejścia dla pieszych przez tor dalej niż 30 m od skrzyżowania, rozjazdy.

**Wrocław: najniższa prędkość**

| # | Odcinek | Linie | Długość, m | km/h 07–09 | km/h 20–23 | Zapas, min/km | W jezdni | Skrzyżowania (z sygn.) | Przejścia poza skrzyż. | Rozjazdy |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Opera → GALERIA DOMINIKAŃSKA | 3, 6, 17 | 794 | 9,5 | 9,5 | 3,67 | 56 % | 4 (2) | 0 | 11 |
| 2 | Mosty Pomorskie → Opera | 3, 5, 7, 10, 11, 12, 13, 18, 24 | 1 595 | 9,8 | 10,6 | 3,48 | 19 % | 8 (6) | 3 | 14 |
| 3 | Oławska → Arkady (Capitol) | 6, 7, 13, 19, 20, 24 | 935 | 9,9 | 9,9 | 5,04 | 32 % | 4 (4) | 3 | 5 |
| 4 | Pl. Wróblewskiego → Oławska | 3, 5 | 1 277 | 10,0 | 13,3 | 3,92 | 29 % | 7 (6) | 2 | 14 |
| 5 | Świdnicka → DWORZEC GŁÓWNY | 10, 12, 18 | 1 199 | 10,2 | 13,6 | 4,30 | 32 % | 6 (3) | 1 | 9 |
| 6 | Rynek → Renoma | 5, 6, 7, 13, 24 | 870 | 10,4 | 10,4 | 3,25 | 83 % | 5 (3) | 1 | 5 |
| 7 | Oławska → Pomorska | 3, 5, 7, 18, 24 | 1 496 | 10,5 | 10,5 | 2,62 | 73 % | 6 (5) | 6 | 3 |
| 8 | Oławska → Pl. Wróblewskiego | 3, 5 | 1 126 | 10,6 | 14,2 | 4,39 | 22 % | 4 (3) | 0 | 8 |
| 9 | Zajezdnia OŁBIN → Pl. Bema | 1, 2, 3, 4, 6, 8, 9, 10, 11, 12, 13, 16, 17, 19, 23 | 1 120 | 10,7 | 16,7 | 2,42 | 71 % | 10 (3) | 0 | 9 |
| 10 | Arkady (Capitol) → Oławska | 3, 6, 7, 10, 12, 13, 17, 18, 19, 20, 24 | 1 017 | 10,9 | 10,9 | 2,07 | 19 % | 7 (4) | 3 | 10 |



**Wrocław: największy zapas na km**

| # | Odcinek | Linie | Długość, m | km/h 07–09 | km/h 20–23 | Zapas, min/km | W jezdni | Skrzyżowania (z sygn.) | Przejścia poza skrzyż. | Rozjazdy |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Oławska → Arkady (Capitol) | 6, 7, 13, 19, 20, 24 | 935 | 9,9 | 9,9 | 5,04 | 32 % | 4 (4) | 3 | 5 |
| 2 | Oławska → Pl. Wróblewskiego | 3, 5 | 1 126 | 10,6 | 14,2 | 4,39 | 22 % | 4 (3) | 0 | 8 |
| 3 | Świdnicka → DWORZEC GŁÓWNY | 10, 12, 18 | 1 199 | 10,2 | 13,6 | 4,30 | 32 % | 6 (3) | 1 | 9 |
| 4 | Pl. Wróblewskiego → Arkady (Capitol) | 3, 4, 16, 19 | 1 904 | 11,0 | 14,6 | 4,02 | 34 % | 11 (6) | 3 | 4 |
| 5 | Pl. Wróblewskiego → Oławska | 3, 5 | 1 277 | 10,0 | 13,3 | 3,92 | 29 % | 7 (6) | 2 | 14 |
| 6 | Opera → GALERIA DOMINIKAŃSKA | 3, 6, 17 | 794 | 9,5 | 9,5 | 3,67 | 56 % | 4 (2) | 0 | 11 |
| 7 | Mosty Pomorskie → Opera | 3, 5, 7, 10, 11, 12, 13, 18, 24 | 1 595 | 9,8 | 10,6 | 3,48 | 19 % | 8 (6) | 3 | 14 |
| 8 | Rynek → Renoma | 5, 6, 7, 13, 24 | 870 | 10,4 | 10,4 | 3,25 | 83 % | 5 (3) | 1 | 5 |
| 9 | Zajezdnia GAJ → Arkady (Capitol) | 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 22, 23 | 1 622 | 12,4 | 15,5 | 3,06 | 3 % | 5 (5) | 3 | 9 |
| 10 | Gajowa → Kościuszki | 16 | 1 427 | 11,9 | 15,9 | 3,04 | 90 % | 9 (4) | 0 | 6 |



**Kraków: najniższa prędkość**

| # | Odcinek | Linie | Długość, m | km/h 07–09 | km/h 20–23 | Zapas, min/km | W jezdni | Skrzyżowania (z sygn.) | Przejścia poza skrzyż. | Rozjazdy |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Łagiewniki → Lipińskiego | 11, 17, 22 | 976 | 11,2 | 11,4 | 1,85 | 2 % | 6 (4) | 5 | 10 |
| 2 | Plac Bohaterów Getta → Starowiślna | 3, 17, 74 | 1 411 | 12,5 | 12,6 | 2,41 | 63 % | 10 (1) | 3 | 9 |
| 3 | Stradom → Filharmonia | 1, 3, 12, 13, 18, 22, 70, 71, 74, 78 | 1 677 | 13,3 | 13,0 | 1,97 | 35 % | 13 (1) | 5 | 7 |
| 4 | Starowiślna → Plac Bohaterów Getta | 3, 17, 74 | 1 349 | 13,6 | 13,7 | 1,96 | 69 % | 9 (1) | 3 | 8 |
| 5 | Stary Kleparz → Dworzec Towarowy | 5, 18, 75 | 1 406 | 14,0 | 14,1 | 1,89 | 74 % | 14 (5) | 1 | 6 |
| 6 | Filharmonia → Stradom | 1, 3, 12, 13, 18, 22, 70, 71, 74, 78 | 1 639 | 14,2 | 14,3 | 1,65 | 47 % | 14 (0) | 5 | 8 |
| 7 | Plac Bohaterów Getta → Łagiewniki SKA | 17, 70, 76, 78 | 3 574 | 15,3 | 17,7 | 2,31 | 41 % | 20 (8) | 4 | 9 |
| 8 | Stradom → Podgórze SKA | 13, 70, 76, 78 | 2 166 | 16,0 | 15,9 | 1,51 | 78 % | 19 (4) | 2 | 5 |
| 9 | Rondo Mogilskie → Poczta Główna | 3, 5, 12, 14, 72, 74, 78 | 1 639 | 16,0 | 15,8 | 1,52 | 66 % | 12 (2) | 1 | 5 |
| 10 | Filharmonia → Teatr Słowackiego | 5, 14, 18, 72, 74, 75, 78 | 1 586 | 16,0 | 15,9 | 1,48 | 97 % | 13 (0) | 1 | 6 |



**Kraków: największy zapas na km**

| # | Odcinek | Linie | Długość, m | km/h 07–09 | km/h 20–23 | Zapas, min/km | W jezdni | Skrzyżowania (z sygn.) | Przejścia poza skrzyż. | Rozjazdy |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Plac Bohaterów Getta → Starowiślna | 3, 17, 74 | 1 411 | 12,5 | 12,6 | 2,41 | 63 % | 10 (1) | 3 | 9 |
| 2 | Plac Bohaterów Getta → Łagiewniki SKA | 17, 70, 76, 78 | 3 574 | 15,3 | 17,7 | 2,31 | 41 % | 20 (8) | 4 | 9 |
| 3 | Łagiewniki → Borek Fałęcki | 7, 22, 78 | 2 408 | 17,0 | 16,9 | 2,13 | 2 % | 7 (4) | 8 | 7 |
| 4 | Stradom → Filharmonia | 1, 3, 12, 13, 18, 22, 70, 71, 74, 78 | 1 677 | 13,3 | 13,0 | 1,97 | 35 % | 13 (1) | 5 | 7 |
| 5 | Starowiślna → Plac Bohaterów Getta | 3, 17, 74 | 1 349 | 13,6 | 13,7 | 1,96 | 69 % | 9 (1) | 3 | 8 |
| 6 | Stary Kleparz → Dworzec Towarowy | 5, 18, 75 | 1 406 | 14,0 | 14,1 | 1,89 | 74 % | 14 (5) | 1 | 6 |
| 7 | Łagiewniki → Lipińskiego | 11, 17, 22 | 976 | 11,2 | 11,4 | 1,85 | 2 % | 6 (4) | 5 | 10 |
| 8 | Filharmonia → Stradom | 1, 3, 12, 13, 18, 22, 70, 71, 74, 78 | 1 639 | 14,2 | 14,3 | 1,65 | 47 % | 14 (0) | 5 | 8 |
| 9 | Rondo Mogilskie → Poczta Główna | 3, 5, 12, 14, 72, 74, 78 | 1 639 | 16,0 | 15,8 | 1,52 | 66 % | 12 (2) | 1 | 5 |
| 10 | Stradom → Podgórze SKA | 13, 70, 76, 78 | 2 166 | 16,0 | 15,9 | 1,51 | 78 % | 19 (4) | 2 | 5 |



**Łódź: najniższa prędkość**

| # | Odcinek | Linie | Długość, m | km/h 07–09 | km/h 20–23 | Zapas, min/km | W jezdni | Skrzyżowania (z sygn.) | Przejścia poza skrzyż. | Rozjazdy |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Gdańska-Legionów → Nowomiejska-Północna | 15, 17, 45 | 699 | 7,0 | 8,4 | 4,96 | 100 % | 2 (1) | 5 | 4 |
| 2 | Nowomiejska-Północna → Gdańska-Legionów | 15, 17, 45 | 728 | 7,6 | 7,6 | 5,69 | 74 % | 3 (2) | 0 | 2 |
| 3 | Limanowskiego-Zachodnia → Wojska Polskiego-Franciszkańska | Z1 | 1 078 | 9,2 | 10,8 | 3,72 | 93 % | 5 (3) | 5 | 3 |
| 4 | Wojska Polskiego-Franciszkańska → Limanowskiego-Zachodnia | Z1 | 1 075 | 9,5 | 10,8 | 3,57 | 62 % | 5 (3) | 4 | 3 |
| 5 | Piotrkowska-Brzeźna → Kościuszki-Mickiewicza | 2, 3, 6, 7, 11 | 895 | 10,7 | 10,7 | 3,13 | 66 % | 4 (3) | 5 | 0 |
| 6 | Rodziny Poznańskich-Dw. Łódź Fabryczna → Kopcińskiego-Narutowicza | 3, 4, 6, 9, 19 | 1 236 | 11,5 | 11,5 | 4,38 | 31 % | 5 (3) | 4 | 2 |
| 7 | Włókniarzy-Karolewska (Dw. Ł. Kaliska) → Żeromskiego-Kopernika | 6, 12, 13, 16, 18, Z1 | 1 200 | 11,6 | 11,6 | 3,44 | 67 % | 6 (3) | 2 | 3 |
| 8 | pl. Niepodległości → Niższa-Broniewskiego | 1, 2, 5, 6, 7, 11, 13, 16 | 2 418 | 11,8 | 13,3 | 2,93 | 10 % | 13 (9) | 9 | 7 |
| 9 | Zachodnia-Próchnika → Gdańska-Struga | 7, 15, 17, 45 | 1 809 | 11,8 | 13,5 | 2,77 | 86 % | 8 (6) | 12 | 3 |
| 10 | Żeromskiego-Kopernika → Włókniarzy-Karolewska (Dw. Ł. Kaliska) | 6, 12, 13, 16, 18, Z1 | 1 269 | 12,7 | 15,2 | 2,19 | 88 % | 8 (4) | 5 | 6 |



**Łódź: największy zapas na km**

| # | Odcinek | Linie | Długość, m | km/h 07–09 | km/h 20–23 | Zapas, min/km | W jezdni | Skrzyżowania (z sygn.) | Przejścia poza skrzyż. | Rozjazdy |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Nowomiejska-Północna → Gdańska-Legionów | 15, 17, 45 | 728 | 7,6 | 7,6 | 5,69 | 74 % | 3 (2) | 0 | 2 |
| 2 | Gdańska-Legionów → Nowomiejska-Północna | 15, 17, 45 | 699 | 7,0 | 8,4 | 4,96 | 100 % | 2 (1) | 5 | 4 |
| 3 | Rodziny Poznańskich-Dw. Łódź Fabryczna → Kopcińskiego-Narutowicza | 3, 4, 6, 9, 19 | 1 236 | 11,5 | 11,5 | 4,38 | 31 % | 5 (3) | 4 | 2 |
| 4 | Limanowskiego-Zachodnia → Wojska Polskiego-Franciszkańska | Z1 | 1 078 | 9,2 | 10,8 | 3,72 | 93 % | 5 (3) | 5 | 3 |
| 5 | Wojska Polskiego-Franciszkańska → Limanowskiego-Zachodnia | Z1 | 1 075 | 9,5 | 10,8 | 3,57 | 62 % | 5 (3) | 4 | 3 |
| 6 | Włókniarzy-Karolewska (Dw. Ł. Kaliska) → Żeromskiego-Kopernika | 6, 12, 13, 16, 18, Z1 | 1 200 | 11,6 | 11,6 | 3,44 | 67 % | 6 (3) | 2 | 3 |
| 7 | Piotrkowska-Brzeźna → Kościuszki-Mickiewicza | 2, 3, 6, 7, 11 | 895 | 10,7 | 10,7 | 3,13 | 66 % | 4 (3) | 5 | 0 |
| 8 | pl. Niepodległości → Niższa-Broniewskiego | 1, 2, 5, 6, 7, 11, 13, 16 | 2 418 | 11,8 | 13,3 | 2,93 | 10 % | 13 (9) | 9 | 7 |
| 9 | Kościuszki-Mickiewicza → Zachodnia-Legionów | 2, 3, 6, 7, 11, 17, 19, 45 | 2 020 | 13,7 | 13,7 | 2,86 | 3 % | 10 (8) | 3 | 6 |
| 10 | Pabianicka- ET-2 → Konstantynowska-Krakowska | 43 | 8 191 | 13,9 | 13,8 | 2,85 | 0 % | 2 (2) | 2 | 4 |



**Czytanie krytyczne** (sprawdzone na przejazdach w danych):
- **Wrocław**: cała dziesiątka najwolniejszych leży w ścisłym centrum (Opera, Galeria Dominikańska, Oławska, Świdnicka,
  Kazimierza Wielkiego, pl. Wróblewskiego), 9,5–11 km/h w szczycie, z gęstą siecią rozjazdów (3–14) i 4–10 skrzyżowaniami
  na 0,8–1,6 km. To spójne z tezą o wolnym centrum. Zaskakujący jest „Zajezdnia Ołbin → pl. Bema” (15 linii): 10,7 km/h
  w szczycie wobec 16,7 wieczorem – rozkład zakłada tu duże korki w szczycie; pozostaje w rankingu.
- **Kraków**: najwolniejsze są Łagiewniki (węzeł z 10 rozjazdami; przejazd Borsucza → Lipińskiego 310 m w 2 min),
  Starowiślna i Stradom–Filharmonia (Dietla, ok. 115 kursów w szczycie). Prędkości 11–16 km/h, wyższe niż we Wrocławiu.
- **Łódź**: na czele są odcinki o podejrzanie niskiej prędkości: Gdańska-Legionów ↔ Nowomiejska (7–7,6 km/h; przejazdy
  291 m w 3 min i 216 m w 2 min przez pl. Wolności) oraz dwa odcinki linii Z1. Z1 to linia zastępcza (litera Z), więc
  te odcinki opisują objazd z okresu robót, nie stałą sieć. Odcinki przez pl. Wolności zostawiono, bo rozkład naprawdę
  daje tam takie czasy, ale **nie należy ich traktować jako stanu stałego bez sprawdzenia robót w listopadzie
  2026 r.** (nie sprawdzono).
- **Przejazdy postojowe na pętlach usunięto**: w pierwszej wersji na czele list były „Łagiewnicka-Murarska → Rondo
  Powstańców 1863r.” w Łodzi (3 km/h: 35 m między słupkami pętli w 4 min) i „Al. Lotników → Metro Wilanowska”
  w Warszawie (183 m w 4 min). Reguła `speed_core.terminal_shuffle` pomija teraz przejazd otwierający lub zamykający
  kurs między dwoma przystankami o tej samej nazwie.
- Odcinki przy krańcach z jednym kursem co 10–15 min (8–10 kursów w paśmie) są w rankingach, ale ich wartość opiera się
  na jednym rozkładzie jednej linii.
- Kolumna „W jezdni” jest dolnym oszacowaniem (3.2): na Świdnickiej we Wrocławiu zaniżona.

Rankingi wszystkich siedmiu miast: `stretches/ranking_am_peak.csv`.

### 3.6 Odcinki autobusowe i trolejbusowe (nakładka „prędkość linii” na mapę)

Ta sama reguła odcinków zastosowana do autobusów i trolejbusów feedów oficjalnych z kształtami tras
(`layers/bus_stretches.parquet`, `tables/bus_stretches.csv`, te same kolumny co dla tramwajów; kolumny OSM, czasu
swobodnego i zapasu są puste, bo model jazdy i dopasowanie do toru dotyczą tramwajów). Pominięte: `krakow_ald` (brak
kształtów) i feedy nieoficjalne. Kolumna `geometry_quality` mówi, czy geometria odcinka pochodzi z kształtu
(`share_hops_shape`). Metro i kolej: jedna geometria na linię (najczęstszy wzorzec przystanków w środę, przycięty do
FUA + 15 km) z prędkością linii z części 1 (`layers/rail_metro_lines.parquet`); dla kolei „linia” to
`route_short_name` feedu (często kategoria pociągu, np. wspólna dla wielu relacji), więc to tylko przybliżenie.

Jakość metody dla autobusów:

| Aglomeracja | Środek | Odcinki × kierunki | Krótsze niż 5 min | Ich udział w wozokm | Wozokm z geometrią z kształtu |
|---|---|---|---|---|---|
| GZM | autobus | 2697 | 35,6 % | 16,6 % | 95,1 % |
| GZM | trolejbus | 40 | 35,0 % | 14,3 % | 100,0 % |
| Kraków | autobus | 797 | 27,1 % | 14,0 % | 99,7 % |
| Łódź | autobus | 815 | 41,1 % | 23,6 % | 85,3 % |
| Poznań | autobus | 1056 | 36,9 % | 16,3 % | 98,9 % |
| Trójmiasto | autobus | 891 | 42,1 % | 19,5 % | 100,0 % |
| Trójmiasto | trolejbus | 68 | 39,7 % | 17,6 % | 100,0 % |
| Warszawa | autobus | 1723 | 37,5 % | 18,1 % | 100,0 % |
| Wrocław | autobus | 671 | 39,2 % | 20,4 % | 99,6 % |

**Odczyt.** Metoda przenosi się na autobusy z zastrzeżeniem: 27–42 % odcinków × kierunków (14–24 % wozokilometrów) jest
krótszych niż 5 min, bo sieć autobusowa ma znacznie więcej rozgałęzień niż tramwajowa, a linie rozchodzą się co kilka
przystanków. Te odcinki są w warstwie z `below_min = true` i powinny być rysowane jako „niepewne” albo pomijane.
Wspólne korytarze (wiele linii na jednej ulicy) nie są problemem: odcinek zbiera wszystkie linie, które nim jadą.
Geometria pochodzi z kształtów w 85–100 % wozokilometrów (Łódź najniżej, bo kształty `lodz` pomijają pętle).

## 2. Prędkość w obszarach (bloki 1 km)

Warstwa: `layers/speed_areas.parquet`, wiersz = blok 1 km z kursami tramwaju lub autobusu (środek w FUA), kolumny
`speed_<środek>_<dzień>_<pasmo>` i `trav_<…>` (liczba przejazdów).

- **Miara**: suma drogi przejechanej w bloku / suma czasu rozkładowego przypisanego do bloku. Czas przejazdu między
  przystankami dzieli się między bloki proporcjonalnie do długości drogi w każdym z nich (stała prędkość w obrębie
  przejazdu). Tylko przejazdy z drogą z kształtu trasy; pozostałe są pominięte i policzone.
- **Jednostka: blok 1 km** = 4 × 4 komórki siatki projektu (EPSG:2180, krawędzie na wielokrotnościach 1000 m),
  `block_id` = `E<x>N<y>` lewego dolnego rogu, więc każda komórka 250 m należy do jednego bloku. Komórkę 250 m
  tramwaj przejeżdża w niecałą minutę, poniżej rozdzielczości rozkładu; blok 1 km to 2–3 przystanki i ok. 3 min
  jazdy, czyli kilka czasów przejazdu.
- **Kiedy wartość jest podawana**: co najmniej **20 przejazdów** w paśmie i co najmniej **2 linie**; inaczej null.
  Próg przejazdów chroni przed wartościami z kilku kursów; próg linii przed blokiem opisanym jednym rozkładem.
  Błąd zaokrąglenia w bloku jest jednak systematyczny (linie mają zwykle te same czasy, 3.1), rzędu 10–15 % dla bloku
  przejeżdżanego w 3 min; mapa bloków nadaje się do wzorców, nie do porównań bloków różniących się o 1–2 km/h.
- **Porównanie miast** zamiast pierścieni wokół jednego węzła (dla GZM i Trójmiasta bez sensu): bloki według
  (a) gęstości zaludnienia bloku (siatka przeskalowana do spisu) i (b) odległości od najbliższego z centrów
  aglomeracji z `config.yaml` (centrum, węzeł i centra dodatkowe; jak w wariancie ρ do najbliższego centrum).
  Pierścienie wokół jednego węzła są policzone tylko do porównania z szybkim spojrzeniem.

Szczyt poranny w środę:

| Aglomeracja | Środek | Bloki z kursami | Bloki z wartością | Wozokm w blokach z wartością | Mediana bloków, km/h |
|---|---|---|---|---|---|
| GZM | autobus | 1568 | 952 | 93,4 % | 27,0 |
| GZM | tramwaj | 178 | 104 | 81,7 % | 19,5 |
| Kraków | autobus | 908 | 413 | 89,8 % | 27,6 |
| Kraków | tramwaj | 85 | 84 | 99,8 % | 21,6 |
| Łódź | autobus | 564 | 248 | 89,9 % | 22,2 |
| Łódź | tramwaj | 108 | 74 | 94,5 % | 18,0 |
| Poznań | autobus | 890 | 402 | 86,9 % | 27,5 |
| Poznań | tramwaj | 57 | 56 | 99,5 % | 20,9 |
| Trójmiasto | autobus | 510 | 319 | 93,7 % | 23,0 |
| Trójmiasto | tramwaj | 51 | 48 | 98,2 % | 18,6 |
| Warszawa | autobus | 2497 | 1021 | 89,6 % | 26,3 |
| Warszawa | tramwaj | 121 | 117 | 99,2 % | 21,1 |
| Wrocław | autobus | 811 | 249 | 87,4 % | 22,4 |
| Wrocław | tramwaj | 79 | 79 | 100,0 % | 19,1 |

Przejazdy pominięte, bo ich droga nie jest znana (środa):

| Aglomeracja | Środek | Przejazdy pominięte (odcinek w linii prostej) | Ich udział w długości |
|---|---|---|---|
| GZM | autobus | 1,4 % | 2,0 % |
| GZM | tramwaj | 4,4 % | 4,4 % |
| Kraków | autobus | 17,9 % | 21,3 % |
| Kraków | tramwaj | 0,0 % | 0,0 % |
| Łódź | autobus | 10,7 % | 19,4 % |
| Łódź | tramwaj | 3,1 % | 3,1 % |
| Poznań | autobus | 0,2 % | 0,3 % |
| Poznań | tramwaj | 0,0 % | 0,0 % |
| Trójmiasto | autobus | 0,0 % | 0,0 % |
| Trójmiasto | tramwaj | 0,0 % | 0,0 % |
| Warszawa | autobus | 0,6 % | 0,6 % |
| Warszawa | tramwaj | 0,0 % | 0,0 % |
| Wrocław | autobus | 0,2 % | 0,4 % |
| Wrocław | tramwaj | 0,0 % | 0,0 % |

**Tramwaj, szczyt poranny w środę, według gęstości zaludnienia bloku (os./km²), km/h**

| Aglomeracja | < 1 000 | 1 000–2 500 | 2 500–5 000 | 5 000–10 000 | ≥ 10 000 |
|---|---|---|---|---|---|
| GZM | 23,2 | 18,9 | 18,5 | 18,3 | 14,4 |
| Kraków | 26,1 | 23,2 | 19,8 | 19,2 | 20,6 |
| Łódź | 18,8 | 19,4 | 19,1 | 16,5 | 16,6 |
| Poznań | 26,7 | 22,4 | 21,3 | 18,8 | 19,1 |
| Trójmiasto | 21,3 | 19,7 | 16,8 | 17,6 | 18,6 |
| Warszawa | 25,7 | 24,5 | 19,0 | 18,2 | 17,7 |
| Wrocław | 21,4 | 21,0 | 18,7 | 14,9 | 14,3 |

**Autobus, szczyt poranny w środę, według gęstości zaludnienia bloku (os./km²), km/h**

| Aglomeracja | < 1 000 | 1 000–2 500 | 2 500–5 000 | 5 000–10 000 | ≥ 10 000 |
|---|---|---|---|---|---|
| GZM | 30,9 | 25,7 | 23,2 | 20,4 | 17,4 |
| Kraków | 31,0 | 24,8 | 21,4 | 19,7 | 18,4 |
| Łódź | 27,3 | 20,3 | 18,4 | 17,3 | 15,4 |
| Poznań | 32,1 | 24,2 | 20,9 | 17,4 | 16,1 |
| Trójmiasto | 28,8 | 23,0 | 20,9 | 18,6 | 18,1 |
| Warszawa | 31,3 | 22,9 | 22,0 | 18,6 | 17,4 |
| Wrocław | 29,2 | 22,2 | 19,6 | 16,4 | 15,3 |

**Tramwaj, szczyt poranny w środę, według odległości od najbliższego centrum, km/h**

| Aglomeracja | 0–1,5 km | 1,5–3 km | 3–6 km | 6–10 km | > 10 km |
|---|---|---|---|---|---|
| GZM | 16,0 | 18,4 | 22,2 | 16,2 | brak danych |
| Kraków | 16,7 | 20,2 | 20,6 | 24,9 | 35,6 |
| Łódź | 14,6 | 17,7 | 19,4 | 20,9 | 20,3 |
| Poznań | 16,8 | 19,8 | 24,3 | brak danych | brak danych |
| Trójmiasto | 16,9 | 17,4 | 18,7 | brak danych | brak danych |
| Warszawa | 16,3 | 15,9 | 19,6 | 21,4 | 25,5 |
| Wrocław | 12,5 | 16,2 | 19,1 | 23,7 | 29,4 |

**Autobus, szczyt poranny w środę, według odległości od najbliższego centrum, km/h**

| Aglomeracja | 0–1,5 km | 1,5–3 km | 3–6 km | 6–10 km | > 10 km |
|---|---|---|---|---|---|
| GZM | 18,2 | 24,6 | 25,1 | 28,4 | 31,1 |
| Kraków | 17,7 | 19,7 | 21,6 | 25,9 | 30,8 |
| Łódź | 13,2 | 16,3 | 20,3 | 24,2 | 24,8 |
| Poznań | 14,9 | 17,3 | 21,9 | 26,2 | 31,4 |
| Trójmiasto | 18,6 | 21,2 | 21,3 | 25,1 | 23,7 |
| Warszawa | 15,8 | 18,9 | 19,3 | 20,3 | 26,2 |
| Wrocław | 13,4 | 16,3 | 20,0 | 22,1 | 30,1 |

**Tramwaj, szczyt poranny w środę, według odległości od jednego węzła (tylko do porównania z szybkim spojrzeniem), km/h**

| Aglomeracja | 0–1,5 km | 1,5–3 km | 3–6 km | 6–10 km | > 10 km |
|---|---|---|---|---|---|
| GZM | 14,8 | 16,2 | 20,7 | 18,0 | 20,0 |
| Kraków | 18,1 | 18,6 | 20,3 | 24,7 | 35,6 |
| Łódź | 15,4 | 16,0 | 18,8 | 21,0 | 20,0 |
| Poznań | 16,3 | 19,6 | 23,2 | 27,8 | brak danych |
| Trójmiasto | 16,9 | 17,8 | 19,1 | 17,0 | brak danych |
| Warszawa | 16,3 | 15,9 | 19,6 | 21,4 | 25,5 |
| Wrocław | 12,6 | 15,5 | 19,1 | 22,9 | 27,5 |

**Autobus, szczyt poranny w środę, według odległości od jednego węzła (tylko do porównania z szybkim spojrzeniem), km/h**

| Aglomeracja | 0–1,5 km | 1,5–3 km | 3–6 km | 6–10 km | > 10 km |
|---|---|---|---|---|---|
| GZM | 15,8 | 24,1 | 23,8 | 23,9 | 25,5 |
| Kraków | 17,9 | 18,8 | 21,5 | 25,2 | 30,8 |
| Łódź | 13,8 | 14,6 | 19,4 | 24,4 | 24,1 |
| Poznań | 13,7 | 16,3 | 21,0 | 26,5 | 30,9 |
| Trójmiasto | 16,3 | 19,6 | 19,7 | 22,7 | 23,3 |
| Warszawa | 15,8 | 18,9 | 19,2 | 20,3 | 26,2 |
| Wrocław | 13,5 | 15,8 | 20,0 | 21,8 | 29,6 |

**Odczyt.**
- **Gęstość**: we wszystkich miastach autobusy zwalniają monotonicznie z gęstością (ok. 31 km/h w blokach < 1 000 os./km²,
  15–18 km/h powyżej 10 000). Tramwaje słabiej: w Krakowie, Poznaniu i Warszawie 18–21 km/h w najgęstszych blokach,
  a we **Wrocławiu 14,3–14,9 km/h już od 5 000 os./km²** i w GZM 14,4 w najgęstszych blokach (centra Katowic, Chorzowa,
  Bytomia).
- **Najbliższe centrum**: w promieniu 1,5 km od najbliższego centrum tramwaj jedzie 14,6–16,8 km/h w sześciu
  aglomeracjach i **12,5 km/h we Wrocławiu**; wieczorem Wrocław 14,0. W GZM grupa „6–10 km” jest wolniejsza niż „3–6 km”,
  bo obejmuje centra mniejszych miast, których nie ma w `config.yaml` jako centrów (np. Siemianowice, Świętochłowice).
- **Hipoteza z szybkiego spojrzenia potwierdza się**: wokół węzła (Galeria Dominikańska, 1,5 km) tramwaj we Wrocławiu
  12,6 km/h w szczycie porannym, w pozostałych miastach 14,8–18,1; dalej od centrum Wrocław dogania (19–29 km/h).
- Bloki z wartością obejmują 82–100 % tramwajowych i 87–94 % autobusowych wozokilometrów w szczycie; brak wartości
  dotyczy głównie bloków z jedną linią na obrzeżach.

## 4. Kontrole

- Mediany tramwajów z `qa/transit/tram_speed_per_city.csv` odtworzone (1.4).
- Każdy krok uruchomiono dwa razy; wszystkie pliki CSV, JSON i Parquet są identyczne co do bajta (poza `_meta*.json`,
  które zapisują czas uruchomienia).
- Rzutowanie przystanków na kształty: 96–100 % przejazdów tramwajowych ma długość z kształtu (wyjątek: krańcówki
  `lodz` i `gzm`, 3–4 %).
- Dopasowanie odcinków do toru OSM i reguła torowiska w jezdni: 3.2.

## 5. Pliki

| Plik | MB |
|---|---|
| tables/speed_lines.csv | 5,25 |
| tables/speed_lines.json | 4,36 |
| tables/tram_stretches.csv | 0,70 |
| tables/tram_stretch_bands.csv | 1,15 |
| tables/tram_stretch_stop_pairs.csv | 0,23 |
| tables/tram_stretch_stops.csv | 0,36 |
| tables/bus_stretches.csv | 6,25 |
| layers/tram_stretches.parquet | 1,19 |
| layers/bus_stretches.parquet | 10,91 |
| layers/rail_metro_lines.parquet | 0,47 |
| layers/speed_areas.parquet | 1,13 |
| metrics/metrics_speed.csv | 0,05 |
| metrics/metrics_speed.json | 0,07 |

## 6. Ograniczenia

- Wszystko z rozkładu jazdy; rzeczywiste prędkości mogą być niższe (opóźnienia) albo wyższe (rezerwy rozkładu).
- Rozdzielczość minutowa: pojedynczy przejazd między przystankami jest szumem; wiarygodne są odcinki ≥ 5 min, sumy
  po wielu przejazdach i bloki z wieloma liniami.
- Feedy nieoficjalne (autobusy podmiejskie) są w tabelach linii i w blokach autobusowych, oznaczone, niezweryfikowane.
- Długość z kształtu GTFS: kształty autobusów w `warsaw_ztm` wywiedziono z OSM; kształty innych feedów od
  wydawców. Jakość kształtów sprawdzono tylko pośrednio (rzuty przystanków, dopasowanie do torów OSM).
- Torowisko w jezdni czy wydzielone: wniosek z geometrii OSM (3.2), nie ze stanu faktycznego.
- Model jazdy swobodnej jest prosty; zapas nie jest pomiarem strat na sygnalizacji.
- Jeden dzień roboczy i jedna sobota, bez niedzieli (GZM); rozkłady z okresu remontów pokazują stan na ten dzień.

## 7. Nie zweryfikowano

- Parametrów modelu jazdy (przyspieszenie, hamowanie, limity, postoje) z danymi przewoźników ani z pomiarem.
- Rzeczywistych limitów prędkości na torach (OSM `maxspeed` na torach tramwajowych jest rzadki; nie użyto).
- Reguły „torowisko w jezdni” poza przykładami z 3.2; w szczególności odcinków, gdzie tor biegnie środkiem ulicy
  narysowanej jedną linią, ale jest oddzielony krawężnikiem (reguła uzna je za jezdnię).
- Liczby skrzyżowań z sygnalizacją dla tramwaju (sygnalizator w promieniu 35 m może dotyczyć innej jezdni).
- Wariantu z łukami: promienie z kształtów GTFS są zaszumione (zagęszczone punkty, skróty na rozjazdach).
- Zestawień prędkości z innych źródeł (1.6) co do definicji i dat rozkładów.
- Zgodności feedów nieoficjalnych z rozkładami przewoźników.
- Przyczyn pojedynczych wolnych odcinków (remonty, objazdy, przystanki na żądanie) poza tymi opisanymi w 3.5.
