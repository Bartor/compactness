"""Hand-written parts of results/qa/speed/speed.md (Polish).  Static method text first; the readings of the results
(checked by hand against the 2026-11-25 / 2026-11-28 outputs) are at the end and must be re-read when data change."""

INTRO = """
**Co to jest.** Rozkładowa prędkość komunikacyjna: długość drogi pojazdu podzielona przez czas z rozkładu jazdy,
z postojami na przystankach. To nie jest prędkość rzeczywista (opóźnienia, korki i punktualność nie są w danych)
ani prędkość jazdy między przystankami. Każda liczba w tej nocie i w plikach pochodzi z rozkładów na środę
2026-11-25 albo sobotę 2026-11-28.

Trzy części na jednej podstawie danych: (1) tabele prędkości linii według typu dnia i pasma godzin, wszystkie środki;
(2) prędkość w obszarach (bloki 1 km); (3) sieć tramwajowa podzielona na odcinki wzdłuż toru, z atrybutami z OSM
i szacunkiem z modelu, ile czasu rozkład daje ponad swobodną jazdę. Kolejność w nocie: 1, 3, 2.

**Stałe klasy prędkości** we wszystkich wynikach (mapa, tabele, podsumowania miast), te same dla każdego miasta:
poniżej 12, 12–15, 15–18, 18–22, 22–26, 26 km/h i więcej (wartość na granicy należy do wyższej klasy;
`speed_core.CLASS_BREAKS`).
"""

BANDS = """
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
"""

FOUNDATION = """
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
"""

PART1_RULES = """
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
"""

FALLBACK = """
**Co robi brak kształtów.** Bez `shapes` długość liczona jest odcinkami prostymi między przystankami, a to zaniża
długość, więc i prędkość, mniej więcej o czynnik z kolumny „kształt / linia prosta” (dla autobusów 1,09–1,16, dla
tramwajów 1,03–1,07). Bez kształtów są: `krakow_ald` (oficjalny, ok. 18 % przejazdów autobusowych Krakowa),
`warsaw_zabki`, `lodz_lka_bus`, `lodz_suburban_qbx` (nieoficjalne) oraz autobusy komunikacji zastępczej
w `polish_trains` (pominięte). Ich wiersze w `speed_lines.csv` mają adnotację; prędkość tych linii jest dolnym
oszacowaniem. W porównaniach autobusów między miastami Kraków jest przez to zaniżony o ok. 1–2 % (18 % przejazdów
× ok. 10 %).
"""

CHECK_READING = """
Ponowne uruchomienie `tram_speed.tram_trips` daje opublikowane mediany co do setnej i te same liczby kursów.
Mediany tej warstwy różnią się o −0,25 do +0,2 km/h, bo długość liczona jest inaczej: tutaj wzdłuż kształtu między
pierwszym a ostatnim przystankiem, w `tram_speed` cała długość kształtu, a przy niezgodności z odcinkami prostymi
większej niż 15 % – odcinki proste. Największe różnice na pojedynczych kursach są w GZM (95. centyl 3,2 km/h): tam
`tram_speed` przechodzi na odcinki proste, a ta warstwa zachowuje kształt na pozostałych przejazdach. Liczby kursów
są identyczne we wszystkich miastach, więc zbiór kursów jest ten sam.
"""

STRETCH_RULE = """
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
8. **Przedział zaokrąglenia ±1 min** przy każdej prędkości odcinka (kolumny `speed_lo_kmh_*`, `speed_hi_kmh_*`):
   długość / (czas + 1 min) do długości / (czas − 1 min); przy czasie do 1 min bez górnej granicy. To granica
   najgorszego przypadku (oba końce zaokrąglone w tę samą stronę), szersza niż odchylenie z punktu 5. Odcinki
   krótsze niż 5 min nadal mają `below_min = true` i są na mapie rysowane linią przerywaną.

Geometria: dla każdej krawędzi najczęstszy kawałek kształtu GTFS, sklejone; dopasowanie do toru OSM: punkty co 10 m
wzdłuż odcinka do najbliższego toru `railway=tram` w promieniu 15 m.
"""

KINEMATICS = """
**Co to jest.** Czas ponad jazdę swobodną = czas rozkładowy odcinka − czas jazdy swobodnej z prostego modelu,
podawany w **sekundach na kilometr** i zawsze z przedziałem. Jest to **liczba z modelu, nie pomiar**. Wcześniej
nazywana tu „zapasem”; nazwa zmieniona po przeglądzie literatury, bo w publikacjach „padding” liczy się względem
najlepszego czasu zmierzonego (AVL), nie względem modelu.

**Model jazdy swobodnej** dla przejazdu o długości d: rozpędzanie ze stałym przyspieszeniem do limitu, jazda z
limitem, hamowanie; gdy przejazd jest za krótki, by osiągnąć limit, trójkątny przebieg prędkości; do tego postój na
przystanku. Czas swobodny odcinka = suma po krawędziach (mediana długości krawędzi).

| Parametr | Wartość środkowa | Przedział publikowany | Wrażliwość (tylko w tej nocie) | Skąd |
|---|---|---|---|---|
| przyspieszenie średnie 0 → limit | 1,0 m/s² | – | 0,7 / 1,3 | założenie; specyfikacja przetargowa Tramwajów Śląskich podaje 1,1 m/s² rozruchu (fragment w wyszukiwarce, nie otwarto) |
| hamowanie służbowe | 1,0 m/s² | – | 0,8 / 1,3 | założenie; ta sama specyfikacja: 1,14 m/s² (nie otwarto) |
| limit prędkości tam, gdzie OSM nie podaje `maxspeed` | 50 km/h | 40 / 50 / 70 km/h | 40 / 60 / 70 | założenie |
| limit z OSM | `maxspeed` toru `railway=tram`, 30–100 km/h | – | wariant „bez maxspeed z OSM” | OSM 2026-11-22 |
| postój na przystanku | 20 s | 10 / 20 / 30 s | 10 / 30 | założenie; GTFS nie podaje postojów |

- **Limit z OSM**: punkty co 10 m wzdłuż odcinka dostają `maxspeed` dopasowanego toru; limit odcinka to średnia
  harmoniczna (równoważna czasowo) z `maxspeed` tam, gdzie jest, i z limitu założonego gdzie indziej. Wartości poniżej
  30 km/h (rozjazdy, łuki, pętle) są pomijane: na skrzyżowaniach najbliższym torem bywa tor skrętny, więc dopasowanie
  przypisywało je odcinkom jadącym prosto (w Krakowie dawało to medianę limitu ok. 35 km/h).
- **Przedział** = najmniejsza i największa wartość z 9 kombinacji postój 10 / 20 / 30 s × limit 40 / 50 / 70 km/h
  (limit tylko tam, gdzie OSM go nie podaje). Dolna granica jest obcinana do 0.
- **Rozkład szybszy niż model** (czas rozkładowy krótszy niż czas swobodny przy wartościach środkowych): odcinek ma
  `faster_than_model = true` i **nie ma wartości** – nie podajemy ujemnych liczb. Tak jest głównie na szybkich
  torowiskach wydzielonych, gdzie rzeczywisty limit jest wyższy niż 50 km/h, a OSM go nie podaje.
- **Wariant z ograniczeniem na łukach usunięto** z publikowanych wyników: promienie liczone z kształtów GTFS są
  zaszumione (zmieniał ranking najbardziej ze wszystkich wariantów).
- W mieście: suma czasu rozkładowego minus suma czasu swobodnego po wszystkich przejazdach odcinków ≥ 5 min,
  podzielona przez wozokilometry (tu odcinki szybsze niż model obniżają średnią; to suma czasów, nie lista odcinków).

Model jest celowo prosty i „optymistyczny”: tramwaj zawsze rusza i hamuje jak najszybciej, nigdy nie czeka.
**Czas ponad jazdę swobodną miesza wszystko, czego model nie zawiera:** czekanie na sygnalizacji, ograniczenia
prędkości (rozjazdy, łuki, skrzyżowania, odcinki w złym stanie), jazdę we wspólnym ruchu i za innym tramwajem,
dłuższą wymianę pasażerów niż postój z modelu i rezerwy wpisane w rozkład. Badania francuskie (Wu, McDonald i in.)
przypisują postojom 22–27 % czasu jazdy tramwaju, a sygnalizacji 7–8 %, więc znaczna część tej wielkości to zwykłe
postoje i geometria toru. **Nie jest to pomiar strat na sygnalizacji.** Poprzednia liczba pochodna „zapas na
skrzyżowanie” nie jest już publikowana.
"""

RANK_RULE = """
Ranking: odcinki co najmniej 5-minutowe (`below_min = false`) z co najmniej 8 kursami w paśmie 07–09; dwie listy po 10:
najniższa prędkość (z przedziałem ±1 min) i największy czas ponad jazdę swobodną w s/km (z przedziałem z modelu;
odcinki szybsze niż model nie wchodzą do tej listy). Kolumny OSM: udział długości w jezdni, skrzyżowania z drogą (w nawiasie
z sygnalizacją w promieniu 35 m), przejścia dla pieszych przez tor dalej niż 30 m od skrzyżowania, rozjazdy.
"""

AREA_RULES = """
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
"""

CHECKS = """
## 4. Kontrole

- Mediany tramwajów z `qa/transit/tram_speed_per_city.csv` odtworzone (1.4).
- Każdy krok uruchomiono dwa razy; wszystkie pliki CSV, JSON i Parquet są identyczne co do bajta (poza `_meta*.json`,
  które zapisują czas uruchomienia).
- Rzutowanie przystanków na kształty: 96–100 % przejazdów tramwajowych ma długość z kształtu (wyjątek: krańcówki
  `lodz` i `gzm`, 3–4 %).
- Dopasowanie odcinków do toru OSM i reguła torowiska w jezdni: 3.2.
- Kontrola metodą Pulsu Gdańska (jeden kurs linii po 15:00 i po 21:00): 1.6.
- Pliki mapy: rozmiary w 5; funkcje strony (`web/src/features/speed`) mają testy jednostkowe, ale nakładka nie jest
  jeszcze podłączona do mapy, więc jej wyglądu nie oglądano.
"""

BUS_STRETCHES = """
### 3.6 Odcinki autobusowe i trolejbusowe (nakładka „prędkość linii” na mapę)

Ta sama reguła odcinków zastosowana do autobusów i trolejbusów feedów oficjalnych z kształtami tras
(`layers/bus_stretches.parquet`, `tables/bus_stretches.csv`, te same kolumny co dla tramwajów poza kolumnami modelu
jazdy, które dotyczą tylko tramwajów; kolumny OSM są puste). Pominięte: `krakow_ald` (brak
kształtów) i feedy nieoficjalne. Kolumna `geometry_quality` mówi, czy geometria odcinka pochodzi z kształtu
(`share_hops_shape`). Metro i kolej: jedna geometria na linię (najczęstszy wzorzec przystanków w środę, przycięty do
FUA + 15 km) z prędkością linii z części 1 (`layers/rail_metro_lines.parquet`); dla kolei „linia” to
`route_short_name` feedu (często kategoria pociągu, np. wspólna dla wielu relacji), więc to tylko przybliżenie.

Jakość metody dla autobusów:
"""

LIMITS = """
## 6. Ograniczenia

- Wszystko z rozkładu jazdy; rzeczywiste prędkości mogą być niższe (opóźnienia) albo wyższe (rezerwy rozkładu).
- Rozdzielczość minutowa: pojedynczy przejazd między przystankami jest szumem; wiarygodne są odcinki ≥ 5 min, sumy
  po wielu przejazdach i bloki z wieloma liniami.
- Feedy nieoficjalne (autobusy podmiejskie) są w tabelach linii i w blokach autobusowych, oznaczone, niezweryfikowane.
- Długość z kształtu GTFS: kształty autobusów w `warsaw_ztm` wywiedziono z OSM; kształty innych feedów od
  wydawców. Jakość kształtów sprawdzono tylko pośrednio (rzuty przystanków, dopasowanie do torów OSM).
- Torowisko w jezdni czy wydzielone: wniosek z geometrii OSM (3.2), nie ze stanu faktycznego.
- Model jazdy swobodnej jest prosty; czas ponad jazdę swobodną nie jest pomiarem strat na sygnalizacji, a jego
  poziom zależy od założonego postoju (przedział w tabelach).
- Jeden dzień roboczy i jedna sobota, bez niedzieli (GZM); rozkłady z okresu remontów pokazują stan na ten dzień.
"""

UNVERIFIED = """
## 7. Nie zweryfikowano

- Parametrów modelu jazdy (przyspieszenie, hamowanie, limity, postoje) z danymi przewoźników ani z pomiarem.
- Limitów prędkości z OSM (`maxspeed`): oznaczenie jest nierówne między miastami (3.3), wartości nie porównano
  z instrukcjami przewoźników; wartości poniżej 30 km/h pominięto z powodu dopasowania na skrzyżowaniach.
- Reguły „torowisko w jezdni” poza przykładami z 3.2; w szczególności odcinków, gdzie tor biegnie środkiem ulicy
  narysowanej jedną linią, ale jest oddzielony krawężnikiem (reguła uzna je za jezdnię).
- Liczby skrzyżowań z sygnalizacją dla tramwaju (sygnalizator w promieniu 35 m może dotyczyć innej jezdni).
- Ograniczeń na łukach (wariant usunięty; promienie z kształtów GTFS są zaszumione).
- Zestawienia Pulsu Gdańska (1.6) poza artykułem: wag średniej, długości linii organizatorów i doboru linii
  (np. linii zastępczych) nie sprawdzono; liczby z 2023 r. przepisano z notatek przeglądu literatury.
- Definicji „prędkość eksploatacyjna” w źródle pierwotnym (1.7).
- Zgodności feedów nieoficjalnych z rozkładami przewoźników.
- Wyglądu nakładki prędkości na mapie i jej działania w przeglądarce (niepodłączona; tylko testy jednostkowe).
- Przyczyn pojedynczych wolnych odcinków (remonty, objazdy, przystanki na żądanie) poza tymi opisanymi w 3.5.
"""

# ---------------------------------------------------------------- readings of the results (filled after the run)
RANK_CITIES = ("krakow", "lodz")

GAP_READING = """
**Odczyt.** Tramwaje we Wrocławiu mają największą różnicę między szczytem a wieczorem (16,2 wobec 17,9 km/h, +1,7 km/h);
w Poznaniu +1,0, w Warszawie +0,6, w Łodzi +0,5, w GZM +0,3, w Krakowie i Gdańsku praktycznie zero. Rozkłady
Krakowa i Gdańska mają więc te same czasy przez cały dzień, a Wrocławia i Poznania – osobne czasy na szczyt.
Autobusy mają różnicę 1,8–2,9 km/h we wszystkich miastach poza Łodzią (+0,6). Metro i kolej nie zmieniają się w ciągu
dnia. Różnica pokazuje, ile rozkład zakłada na korki i wymianę pasażerów w szczycie; nie mówi, jak jest naprawdę.
"""

QUICK_READING = """
Szybkie spojrzenie (16,1 w szczytach wobec 18,0 km/h po 20:00 we Wrocławiu, największa różnica z siedmiu miast)
**potwierdza się** przy właściwej geometrii: 16,1 wobec 18,0 km/h; przy pasmach z tej noty 16,2 (07–09) wobec 17,9
(20–23). Odcinki proste × 1,04 dawały prawie to samo (różnica 0–0,5 km/h, największa w Krakowie i Gdańsku, gdzie
kształt jest o 5–7 % dłuższy od linii prostej). Hipoteza o centrum Wrocławia (część 2) też się potwierdza.
"""

PUBLISHED = """
### 1.6 Porównanie z opublikowanymi zestawieniami i kontrola „metodą Pulsu Gdańska”

Znalezione samodzielnie (wyszukiwarka, 2026-11-24), oba oparte na raporcie portalu Puls Gdańska liczonym z rozkładów:
- bankier.pl, 11.05.2021 („Polskie tramwaje nie są demonami prędkości”), średnie całodobowe: Poznań 20,8, Warszawa 18,9,
  Kraków 18,8, GOP 18,6, Wrocław 17,8, Gdańsk 17,1, Łódź 15,6 km/h;
- antyweb.pl, 25.07.2022 („Prędkość tramwajów w Polsce”, raport Pulsu Gdańska za 2022 r.): Poznań 19,85, Warszawa 19,33,
  Kraków 19,21, GOP 17,86, Gdańsk 17,48, Łódź 16,86, Wrocław 16,65 km/h; w szczycie Wrocław 15,87, poza szczytem 17,51.

Raport Pulsu Gdańska za 2023 r. (pulsgdanska.pl, 25.07.2023, rozkłady z 30.05.2023; przeczytany w całości przy
przeglądzie literatury) opisuje metodę: dla każdej linii pierwszy kurs w dzień roboczy na trasie podstawowej po 15:00
(„szczyt”) i po 21:00 („poza szczytem”), długości linii od organizatorów, średnia z obu (wagi niepodane), bez linii
nocnych, weekendowych i turystycznych. **Kontrola tą metodą** (`qa/speed/tables/puls_style_lines.csv`,
`puls_style_city.csv`): w środę 2026-11-25, w oficjalnym feedzie tramwajowym miasta, dla każdej linii trasa
podstawowa = najczęstsza para przystanek początkowy → końcowy, pierwszy kurs tej trasy odjeżdżający o 15:00 lub
później i o 21:00 lub później; średnia linii = średnia obu; miasto = zwykła średnia po liniach. Pominięte linie
nocne (bez odjazdu 06–20); linia bez kursu po 21:00 liczy się tylko w średniej „15:00”. Długość: nasza, wzdłuż
kształtu trasy (nie od organizatora).
"""

MATCH_READING = """
Dopasowanie do toru OSM: w każdym mieście mediana odcinków ma 100 % punktów w promieniu 15 m od toru, mediana odległości
0–1,5 m (kształty GTFS biegną po torach). Najsłabiej Łódź (10. centyl 83 %, 9 % długości bez dopasowania: kształty
`lodz` miejscami skracają łuki i pętle) i GZM (3 %). Przejazdy niewchodzące do żadnego odcinka: 0–1,6 % (krawędzie
występujące tylko w sobotę albo przejazdy między słupkami jednego miejsca). Odcinki: 32 (Gdańsk) do 86 (Łódź),
mediana długości 1,7–2,4 km, 5–7 przystanków.
"""

ROUNDING_READING = """
Linie jadące tym samym odcinkiem w tej samej godzinie mają w 88–100 % przypadków **identyczny** czas rozkładowy
(średni rozrzut 0,03–0,09 min). Błąd zaokrąglenia jest więc wspólny dla wszystkich linii odcinka (planista nadaje
czasy przejazdu odcinkom, nie liniom) i nie maleje z liczbą linii ani kursów; jedyną obroną jest długość odcinka.
Stąd próg 5 min, a nie próg liczby kursów. Kontrola nie mierzy samego błędu (nie znamy „prawdziwego” czasu), pokazuje
tylko, że uśrednianie po liniach go nie usuwa.
"""

SEPARATION = """
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
"""

SENS_READING = """
**Odczyt.** Wartości środkowe w szczycie porannym: Kraków i Poznań ok. 42–44 s/km, Warszawa, GZM i Gdańsk 54–59,
Łódź 73, Wrocław 77 s/km. **Poziom zależy przede wszystkim od założonego postoju** (10 s: 62–99 s/km, 30 s:
23–55 s/km) i w drugiej kolejności od limitu prędkości; dlatego publikujemy przedział (postój 10–30 s × limit
40–70 km/h): np. Wrocław 44–107, Kraków 25–64 s/km. **Kolejność odcinków prawie się nie zmienia** (korelacja rang
z wariantem środkowym ≥ 0,97, w top 10 zostaje 8–10 tych samych odcinków), więc listy w 3.5 są odporne na wybór
parametrów, a liczby bezwzględne nie. Kolejność miast też jest stała we wszystkich wariantach (Wrocław i Łódź
najwyżej, Kraków i Poznań najniżej). Wrocław: 77 s/km w szczycie porannym wobec 56 wieczorem; model i geometria są
te same, więc różnica pochodzi wyłącznie z rozkładu, który w szczycie daje dłuższe czasy przejazdu.

**Rozkład szybszy niż model**: 0–8 % odcinków w wariancie środkowym. W szczycie porannym (odcinki ≥ 5 min) są to
w Poznaniu Franowo – os. Czecha i Kórnicka – Piaśnicka Rynek (8 % wozokilometrów, wieczorem 15 %), w Krakowie
Plac Centralny – Fort Mogiła – Pleszów i Nowy Bieżanów (5 %), w Warszawie Żerań FSO – rondo Starzyńskiego i Winnica –
Mehoffera; wszystkie 25–36 km/h z rozkładu. Bez `maxspeed` z OSM udział rośnie do 16 % odcinków (Kraków), bo OSM
podaje tam 60–70 km/h. Przy postoju 30 s takich odcinków jest do 27 %.
"""

MAXSPEED_READING = """
**`maxspeed` na torach**: oznaczenie jest bardzo nierówne. Kraków ma `maxspeed` na całym torowisku, Gdańsk na 92 %,
Warszawa na 33 %, Poznań na 17 %, GZM na 12 %, Wrocław na 8 %, Łódź na żadnym. Część wartości to ograniczenia
rozjazdów i pętli (5–25 km/h; w Krakowie stanowią ok. 26 % długości torów), których nie używamy (3.3). Limit z OSM
zmienia wynik głównie w Krakowie i Gdańsku; w pozostałych miastach model opiera się na założeniu 50 km/h
(przedział 40–70).
"""

RANK_READING = """
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
- Lista „największy czas ponad jazdę swobodną” pokrywa się w dużej części z listą najwolniejszych; przedziały
  w nawiasach są szerokie (zwykle ±20–30 s/km), ale kolejność w obrębie miasta jest stała (3.3).
"""

AREA_READING = """
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
"""

BUS_READING = """
**Odczyt.** Metoda przenosi się na autobusy z zastrzeżeniem: 27–42 % odcinków × kierunków (14–24 % wozokilometrów) jest
krótszych niż 5 min, bo sieć autobusowa ma znacznie więcej rozgałęzień niż tramwajowa, a linie rozchodzą się co kilka
przystanków. Te odcinki są w warstwie z `below_min = true` i powinny być rysowane jako „niepewne” albo pomijane.
Wspólne korytarze (wiele linii na jednej ulicy) nie są problemem: odcinek zbiera wszystkie linie, które nim jadą.
Geometria pochodzi z kształtów w 85–100 % wozokilometrów (Łódź najniżej, bo kształty `lodz` pomijają pętle).
"""

DEFINITIONS = """
### 1.7 Nazwy prędkości: co udało się sprawdzić

Szukano (2026-11-24, wyszukiwarka i pobieranie stron) definicji w źródle pierwotnym. Wynik:
- **Prędkość komunikacyjna** (zwana też handlową) = długość trasy / czas przejazdu **z postojami na przystankach
  pośrednich**; **prędkość techniczna** = bez czasu postojów na przystankach. Tak opisują je artykuły w „Transporcie
  Miejskim i Regionalnym” (np. Oskarbski, TMiR 5/2016; Wołek, TMiR 2/2016), ale widziane **tylko jako fragmenty
  w wynikach wyszukiwania**: plik PDF Wołka zwrócił błąd 403, a innego PDF (Politechnika Warszawska, „Miasto
  i Transport”) nie dało się odczytać (skompresowany tekst, brak narzędzia do PDF w środowisku). Strony nie sprawdzono.
- **Prędkość eksploatacyjna**: nie znaleziono definicji w źródle pierwotnym (podręcznik Wyszomirskiego czy Rudnickiego,
  norma). Wyszukiwarka streściła jeden niezidentyfikowany wynik jako wyliczenie składników „czasu eksploatacyjnego”
  (jazda, postoje na przystankach pośrednich i na dworcach, postoje i przejazdy techniczne na pętlach), co zgadza się
  z opisem w raporcie (§15.3: eksploatacyjna obejmuje postoje na pętlach), ale **nie jest to cytat ze źródła**.
  W innych znalezionych tekstach termin oznacza „maksymalną prędkość eksploatacyjną” pojazdu, czyli co innego.
- Wniosek: nazwa „rozkładowa prędkość komunikacyjna” dla tego, co tu liczymy (z postojami na przystankach, bez postojów
  na pętlach), jest zgodna ze wszystkimi znalezionymi opisami; twierdzenie o prędkości eksploatacyjnej z pętlami
  pozostaje bez cytatu ze źródła pierwotnego.
"""

CLASSES = """
Klasy są stałe i jednakowe dla wszystkich miast: poniżej 12, 12–15, 15–18, 18–22, 22–26, 26 km/h i więcej. Te same
granice mają kolory na mapie (`results/web/speed`), kolumny `speed_class_*` w tabelach odcinków i `speed_class`
w tabeli linii. W kolumnie „ponad jazdę swobodną” wartość środkowa i przedział z modelu (3.3).
"""

WEB = """
**Pliki mapy** (`python -m pipeline.speed_web`, `results/web/speed/`): odcinki tramwajowe wszystkich miast w jednym
pliku, odcinki autobusowe i trolejbusowe po jednym pliku na aglomerację, metro i kolej w jednym pliku, tabela linii
`lines.json`. Geometria uproszczona do ok. 5 m, współrzędne do 5 miejsc po przecinku; właściwości krótkie
(`v_w_am` = prędkość w środę 07–09, `t_` = kursy na godzinę, `a_` / `al_` / `ah_` = czas ponad jazdę swobodną
w s/km: środek / dół / góra, `fm_` = rozkład szybszy niż model, `c` = klasy we wszystkich pasmach); brak wartości
= brak pola, nigdy 0. Opis pól: nagłówek `pipeline/speed_web.py`.
"""

PULS_READING = """
**Odczyt.** Liczone metodą Pulsu, nasze wartości z 2026 r. różnią się od Pulsu 2023 o −0,2 do +0,9 km/h (średnia),
w Warszawie, Wrocławiu, Poznaniu, GZM i Gdańsku o nie więcej niż 0,2 km/h. **Różnica Poznania z wcześniejszego
porównania (19,5 wobec 20,5 km/h) znika** (20,4 wobec 20,5): wynikała z metody, bo Puls liczy każdą linię raz,
a szybkie linie PST (14: 27–30 km/h, 15, 16, 12) ważą tam tyle co wolne linie śródmiejskie. Większe różnice
zostają w Łodzi (+0,9) i Krakowie (+0,8); w Łodzi rozkład 2026 obejmuje linię zastępczą Z1 i inne trasy niż w maju
2023 r.; przyczyny różnicy w Krakowie nie sprawdzono (z 23 linii tylko 18 ma kurs trasy podstawowej po 21:00). Różnica Wrocławia między 15:00 a 21:00 (15,8 wobec 17,7 km/h)
jest tego samego rzędu co w raporcie (16,2 wobec 17,6). Na tych samych rozkładach metoda Pulsu daje od −0,2 (GZM)
do +0,4 km/h (Poznań) więcej niż suma długości przez sumę czasu wszystkich kursów doby. Długości są nasze, nie od
organizatorów; rozkłady są z innego roku.
"""
