# Wstępne pokrycie danymi GTFS (przystanki OSM ↔ GTFS)

Faza 0, krok `python -m pipeline.stop_coverage` (brief §6). **Wynik wstępny**: maska pokrycia właściwa powstaje w fazie 2. Dzień referencyjny rozkładów: **2026-11-25 (śr)**; stan OSM: **2026-11-22**; ludność: **NSP 2021** (siatka 1 km, stan 31.03.2021). GZM w wariancie granicy **fua_union** (prowizoryczny „suma czterech FUA”; decyzja Bartora w toku).

## W skrócie

- **Rdzenie są pokryte dobrze** (95–98% przystanków OSM w rdzeniu ma odpowiednik w GTFS, we wszystkich siedmiu
  aglomeracjach). Braki w rdzeniach to w dużej części przystanki z tagiem sieci miejskiej (np. ok. 90 przystanków
  „ZTM Warszawa” w Warszawie), czyli chwilowo nieobsługiwane, przesunięte albo nieaktualne w OSM, oraz pojedyncze
  przystanki przewoźników regionalnych (np. „MDA” w Krakowie). Żadne miasto-rdzeń nie wypada podejrzanie nisko.
- **Poza rdzeniem pokrycie jest bardzo nierówne**: GZM ok. 89% i Poznań ok. 79% (zarządy transportu obejmują
  większość gmin FUA), pozostałe pięć aglomeracji tylko 30–37%. W Warszawie, Krakowie, Łodzi, Trójmieście
  i we Wrocławiu feedy GTFS nie zawierają gminnych i prywatnych przewoźników podmiejskich.
- **Wstępnie**: przy progu 85% pokrycia gminy obszar pokryty obejmuje ok. 60–75% ludności FUA w pięciu „słabych”
  aglomeracjach, 87% w Poznaniu i 96% w GZM. Według reguły z §6 wyniki transportowe dla FUA Warszawy, Krakowa,
  Łodzi, Wrocławia i Trójmiasta będą oznaczone jako niepełne; do porównań trzeba będzie użyć wariantu „obszar
  pokryty” albo „rdzeń”.
- **Promień**: 50 m dla autobusu/tramwaju zostaje, ale z dopasowaniem pomocniczym po nazwie lub kodzie przystanku
  (do 200 m); dla kolei 200 m. Z dopasowaniem po nazwie wynik prawie nie zależy od promienia (zmiana o 1–2,5 pkt
  proc. między 30 a 150 m), więc wybór 50 m nie przesądza o wnioskach.

## Metoda

1. **GTFS.** Feedy przypisane aglomeracji w `config.yaml` plus `polish_trains` (dla Warszawy także `warsaw_wkd`).
   Przystanek GTFS jest „obsłużony”, jeśli w dniu referencyjnym zatrzymuje się na nim co najmniej jeden kurs
   (`calendar` + `calendar_dates`). Każdy przystanek dostaje zbiór klas tras, które go obsługują (`route_type`:
   autobus i trolejbus = autobus; tramwaj; kolej; metro; prom). Autobusy w `polish_trains` (`route_type` 3) to
   komunikacja zastępcza kolei (ZKA): obsługują stację kolejową, ale nie sieć autobusową. Stacje nadrzędne
   (`location_type` = 1, w `polish_trains` i `warsaw_ztm`) dziedziczą tryby i kursy swoich peronów, bo węzeł OSM
   `railway=station` leży w środku stacji, a punkty GTFS bywają peronami. Przystanki obecne w `stops.txt`, ale
   nieobsłużone w dniu ref., są trzymane osobno (kategoria „w feedzie, nieobsłużony”). Duplikaty kursów
   (GZM, SKM Warszawa) nie mają znaczenia dla obecności przystanku.
2. **OSM.** Przystanki po deduplikacji (`data/interim/osm/stops_dedup.parquet`, reguły w
   `results/qa/phase0/osm/osm_stops.md`) wewnątrz FUA. Kolej: perony OSM w promieniu 200 m od stacji OSM
   są wchłaniane przez stację (jedna stacja = jedna jednostka); perony „sieroce” (bez stacji w pobliżu) dostają
   tryb nieokreślony, bo przegląd pokazał, że to w dużej części perony tramwajowe i autobusowe oznaczone
   `railway=platform` (np. w Krakowie i Łodzi). Stacje kolei turystycznych, drezynowych, wąskotorowych,
   parkowej Maltanki i kolejki na Kamienną Górę są wyłączone z mianownika (reguła po nazwie i operatorze).
3. **Dopasowanie** w EPSG:2180 (KD-drzewo), z **zgodnością trybu**: przystanek autobusowy OSM tylko do autobusu
   lub trolejbusu GTFS, tramwajowy tylko do tramwaju, stacja kolejowa do kolei (także ZKA), metro do metra; peron
   o nieokreślonym trybie do czegokolwiek. Przystanek OSM ma odpowiednik, jeśli (a) obsłużony przystanek GTFS
   zgodnego trybu leży w promieniu odległości (50 m; kolej 200 m), albo (b) w promieniu 200 m (kolej
   500 m) leży obsłużony przystanek zgodnego trybu o tej samej znormalizowanej nazwie (bez numeru słupka i
   oznaczeń „nż”) albo o tym samym kodzie (`ref` w OSM = `stop_id`/`stop_code` w GTFS, kody ≥ 4 znaki).
4. **Maska (tryb „wszystkie”).** Przystanek tramwajowy, kolejowy lub metra, przy którym (≤ 50 m albo ta sama
   nazwa ≤ 200 m) jest obsłużony przystanek innego trybu, liczy się jako pokryty („zastępczy”): w dniu ref.
   na części tras tramwajowych w Krakowie i Łodzi tramwaj nie kursuje, a tuż przy przystankach są obsłużone
   przystanki autobusowe (wniosek z danych, zapewne autobusy zastępcze w czasie remontu; przyczyn nie
   sprawdzano). Obszar ma więc dane rozkładowe. Wskaźniki per tryb pozostają ścisłe.
5. **Kontrola przypadkowych dopasowań.** Dopasowanie po samej odległości powtórzone dla punktów OSM przesuniętych
   o losowy wektor (stałe ziarno; 200–400 m dla autobusu i tramwaju, 1000–1500 m dla kolei). Odsetek takich
   „trafień” pokazuje, ile dopasowań dany promień daje przypadkiem przy lokalnej gęstości przystanków GTFS.
6. **Agregacja.** Wskaźnik = % przystanków OSM z odpowiednikiem, per gmina (LAU 2021, przypisanie punktu do
   wielokąta; poza wielokątami 1:1M najbliższa gmina), per pierścień 1 km od centrum, per tryb; rdzeń = miasto(a)
   URAU (Trójmiasto + Sopot). Zawsze z liczbą przystanków (mianownik).

## Wybór promienia i wrażliwość

Badane promienie: 30 / 50 / 75 / 100 / 150 m (autobus, tramwaj) i 100 / 200 / 300 / 500 m (kolej).

- **Autobus.** Rozkład odległości do najbliższego przystanku GTFS jest wyraźnie dwumodalny: ostry szczyt poniżej
  ~20 m (ten sam słupek) i długi ogon setek metrów do kilometrów (przystanki bez odpowiednika). Między 50 a 150 m
  pokrycie po samej odległości rośnie o 2–7 pkt proc., ale kontrola przesunięcia pokazuje, że przypadkowe trafienia
  rosną tam z ~3% do ~20%: duża część „zysku” z większego promienia to łapanie sąsiedniego, innego przystanku.
  Przy 50 m odsetek przypadkowy wynosi ok. 2–4%. Część prawdziwych par jest jednak oddalona o 50–150 m (inne
  położenie słupka w OSM i w bazie przewoźnika, zwłaszcza w Poznaniu i Wrocławiu), dlatego dopasowanie
  pomocnicze po nazwie/kodzie do 200 m. Z nim pokrycie zmienia się między 30 a 150 m tylko o 1–2,5 pkt proc.
- **Tramwaj.** Węzeł `railway=tram_stop` leży na torze, punkt GTFS często przy krawędzi peronu: 30 m gubi 1–5 pkt
  proc. prawdziwych par, 50 m łapie prawie wszystko, a powyżej rośnie już głównie składnik przypadkowy.
- **Kolej.** Wbrew obawom z briefu punkty GTFS stacji (`polish_trains`: stacja nadrzędna i perony) leżą zwykle
  blisko węzła OSM: mediana kilkunastu metrów, pokrycie po odległości nasyca się przy 150–200 m; 300 i 500 m
  nic istotnego nie dodają, a zwiększają ryzyko przypisania stacji nieczynnej linii do czynnej stacji obok.
  Wyjątki (Rzozów Centrum, Żukowo, Borkowo, Rębiechowo: punkt GTFS 350–640 m od węzła OSM; w Żukowie i Borkowie
  w dniu ref. tylko ZKA) łapie dopasowanie po nazwie do 500 m. **Rekomendacja: 200 m + nazwa do 500 m**;
  wrażliwość w tabeli niżej (300 m daje ten sam wynik).
- **Rekomendacja ogólna:** zostawić `osm_gtfs_match_radius_m: 50` i dodać dopasowanie po nazwie/kodzie.

**autobus**: pokrycie FUA wg samej odległości (w nawiasie: dopasowania przypadkowe z kontroli przesunięcia); ostatnia kolumna: przy przyjętym promieniu z dopasowaniem po nazwie/kodzie.

| Aglomeracja | n | 30 m | 50 m | 75 m | 100 m | 150 m | 50 m + nazwa/kod |
|---|---|---|---|---|---|---|---|
| Warszawa | 11573 | 53,2% (1,3%) | 54,2% (3,2%) | 55,2% (6,5%) | 56,2% (10,0%) | 57,5% (19,2%) | **56,6%** |
| Kraków | 5764 | 52,8% (0,8%) | 54,0% (1,9%) | 55,4% (3,8%) | 56,2% (6,5%) | 57,3% (13,7%) | **56,3%** |
| Wrocław | 2693 | 64,0% (1,5%) | 67,0% (3,2%) | 68,5% (6,5%) | 69,6% (10,0%) | 71,3% (20,3%) | **70,5%** |
| Poznań | 3026 | 76,1% (1,2%) | 81,6% (3,1%) | 85,1% (5,7%) | 87,0% (10,0%) | 88,9% (21,4%) | **87,5%** |
| Łódź | 3052 | 58,9% (1,3%) | 60,4% (2,9%) | 61,6% (6,4%) | 62,5% (10,5%) | 63,5% (20,2%) | **62,8%** |
| Trójmiasto | 3525 | 65,1% (1,6%) | 66,2% (3,5%) | 67,2% (7,2%) | 67,9% (11,9%) | 69,1% (22,6%) | **68,1%** |
| GZM | 5509 | 91,3% (1,5%) | 93,1% (3,5%) | 94,0% (6,6%) | 94,6% (11,0%) | 95,2% (21,9%) | **94,8%** |

**tramwaj**: pokrycie FUA wg samej odległości (w nawiasie: dopasowania przypadkowe z kontroli przesunięcia); ostatnia kolumna: przy przyjętym promieniu z dopasowaniem po nazwie/kodzie.

| Aglomeracja | n | 30 m | 50 m | 75 m | 100 m | 150 m | 50 m + nazwa/kod |
|---|---|---|---|---|---|---|---|
| Warszawa | 854 | 92,5% (1,5%) | 97,2% (4,4%) | 98,2% (8,1%) | 98,4% (13,6%) | 99,1% (26,0%) | **99,1%** |
| Kraków | 503 | 86,1% (1,2%) | 88,9% (2,6%) | 91,3% (5,8%) | 91,5% (8,5%) | 92,6% (18,3%) | **91,5%** |
| Wrocław | 473 | 91,3% (1,3%) | 95,3% (2,5%) | 96,8% (6,6%) | 97,9% (10,1%) | 98,9% (25,2%) | **98,3%** |
| Poznań | 344 | 91,6% (1,7%) | 94,5% (5,2%) | 95,3% (9,9%) | 95,9% (16,0%) | 97,4% (28,5%) | **97,1%** |
| Łódź | 566 | 83,4% (1,1%) | 87,1% (3,5%) | 88,3% (7,8%) | 89,4% (11,1%) | 90,5% (23,9%) | **89,9%** |
| Trójmiasto | 351 | 94,9% (1,1%) | 96,0% (2,8%) | 96,9% (8,0%) | 97,4% (13,7%) | 97,7% (23,4%) | **96,0%** |
| GZM | 547 | 91,6% (0,9%) | 93,6% (1,6%) | 95,1% (3,8%) | 95,1% (7,7%) | 96,0% (17,6%) | **95,4%** |

**kolej**: pokrycie FUA wg samej odległości (w nawiasie: dopasowania przypadkowe z kontroli przesunięcia); ostatnia kolumna: przy przyjętym promieniu z dopasowaniem po nazwie/kodzie.

| Aglomeracja | n | 100 m | 200 m | 300 m | 500 m | 200 m + nazwa/kod |
|---|---|---|---|---|---|---|
| Warszawa | 207 | 97,1% (0,5%) | 98,6% (1,4%) | 98,6% (2,9%) | 98,6% (7,7%) | **98,6%** |
| Kraków | 73 | 93,2% (1,4%) | 94,5% (1,4%) | 94,5% (4,1%) | 95,9% (9,6%) | **95,9%** |
| Wrocław | 83 | 98,8% (0,0%) | 100,0% (0,0%) | 100,0% (2,4%) | 100,0% (4,8%) | **100,0%** |
| Poznań | 62 | 100,0% (1,6%) | 100,0% (1,6%) | 100,0% (1,6%) | 100,0% (1,6%) | **100,0%** |
| Łódź | 56 | 98,2% (0,0%) | 100,0% (1,8%) | 100,0% (1,8%) | 100,0% (7,1%) | **100,0%** |
| Trójmiasto | 62 | 87,1% (0,0%) | 88,7% (0,0%) | 88,7% (3,2%) | 93,5% (8,1%) | **93,5%** |
| GZM | 77 | 93,5% (0,0%) | 93,5% (0,0%) | 93,5% (0,0%) | 94,8% (0,0%) | **93,5%** |

Histogramy odległości: `nn_hist_<aglomeracja>.png`.

## Pokrycie: FUA, rdzeń, poza rdzeniem
Przyjęte promienie: 50 m (autobus, tramwaj, metro, peron nieokreślony), 200 m (kolej), plus dopasowanie po nazwie/kodzie. „Wszystkie” = maska (tramwaj/kolej z przystankiem zastępczym innego trybu liczone jako pokryte). W nawiasach liczba przystanków OSM (mianownik).

| Aglomeracja | tryb | FUA | rdzeń | poza rdzeniem | GTFS bez OSM |
|---|---|---|---|---|---|
| Warszawa | wszystkie | 59,9% (12 781) | 97,2% (5 016) | 35,8% (7 765) | 1,4% (101 z 7 153) |
| Warszawa | autobus | 56,6% (11 573) | 96,9% (4 043) | 34,9% (7 530) | 1,4% (88 z 6 220) |
| Warszawa | tramwaj | 99,1% (854) | 99,3% (852) | 0,0% (2) | 1,6% (10 z 630) |
| Warszawa | kolej | 98,6% (207) | 100,0% (55) | 98,0% (152) | 0,0% (0 z 265) |
| Kraków | wszystkie | 59,8% (6 419) | 96,1% (2 488) | 36,9% (3 931) | 2,5% (102 z 4 124) |
| Kraków | autobus | 56,3% (5 764) | 95,8% (1 919) | 36,5% (3 845) | 2,7% (100 z 3 701) |
| Kraków | tramwaj | 91,5% (503) | 91,5% (503) | – (0) | 0,0% (0 z 353) |
| Kraków | kolej | 95,9% (73) | 100,0% (27) | 93,5% (46) | 2,9% (2 z 70) |
| Wrocław | wszystkie | 71,1% (3 491) | 97,7% (2 006) | 35,2% (1 485) | 5,9% (153 z 2 576) |
| Wrocław | autobus | 70,5% (2 693) | 97,2% (1 500) | 37,0% (1 193) | 7,1% (146 z 2 044) |
| Wrocław | tramwaj | 98,3% (473) | 98,3% (473) | – (0) | 1,6% (7 z 447) |
| Wrocław | kolej | 100,0% (83) | 100,0% (30) | 100,0% (53) | 0,0% (0 z 85) |
| Poznań | wszystkie | 86,2% (3 770) | 94,9% (1 713) | 78,9% (2 057) | 10,2% (340 z 3 330) |
| Poznań | autobus | 87,5% (3 026) | 95,1% (1 236) | 82,3% (1 790) | 11,4% (339 z 2 964) |
| Poznań | tramwaj | 97,1% (344) | 97,1% (344) | – (0) | 0,3% (1 z 304) |
| Poznań | kolej | 100,0% (62) | 100,0% (13) | 100,0% (49) | 0,0% (0 z 62) |
| Łódź | wszystkie | 68,2% (3 756) | 96,3% (2 168) | 29,9% (1 588) | 2,8% (66 z 2 386) |
| Łódź | autobus | 62,8% (3 052) | 96,2% (1 633) | 24,5% (1 419) | 3,1% (58 z 1 865) |
| Łódź | tramwaj | 89,9% (566) | 88,6% (502) | 100,0% (64) | 1,7% (8 z 465) |
| Łódź | kolej | 100,0% (56) | 100,0% (22) | 100,0% (34) | 0,0% (0 z 56) |
| Trójmiasto | wszystkie | 71,1% (3 968) | 96,5% (2 307) | 35,8% (1 661) | 2,5% (69 z 2 793) |
| Trójmiasto | autobus | 68,1% (3 525) | 96,8% (1 895) | 34,8% (1 630) | 2,6% (64 z 2 487) |
| Trójmiasto | tramwaj | 96,0% (351) | 96,0% (351) | – (0) | 2,0% (5 z 248) |
| Trójmiasto | kolej | 93,5% (62) | 97,4% (38) | 87,5% (24) | 0,0% (0 z 58) |
| GZM | wszystkie | 94,7% (6 246) | 96,9% (4 466) | 89,2% (1 780) | 7,1% (481 z 6 802) |
| GZM | autobus | 94,8% (5 509) | 97,4% (3 775) | 89,2% (1 734) | 7,1% (426 z 6 013) |
| GZM | tramwaj | 95,4% (547) | 95,4% (540) | 100,0% (7) | 7,7% (55 z 717) |
| GZM | kolej | 93,5% (77) | 92,5% (53) | 95,8% (24) | 0,0% (0 z 72) |

„GTFS bez OSM” = obsłużone w dniu ref. przystanki GTFS w FUA (stacje nadrzędne zamiast peronów), przy których nie ma
przystanku OSM zgodnego trybu w tym samym promieniu (bez dopasowania po nazwie). To dolne oszacowanie braków OSM
(szczegóły niżej). Wskaźnik kolejowy liczony po wyłączeniu kolei turystycznych i peronów-sierot (te są w „wszystkie”
jako perony o nieokreślonym trybie).

### Dlaczego przystanek nie ma odpowiednika (wszystkie tryby, FUA)

| Aglomeracja | OSM | odległość | nazwa/kod | zastępczy | tylko inny tryb | w feedzie, nieobsł. w dniu ref. | brak w GTFS |
|---|---|---|---|---|---|---|---|
| Warszawa | 12 781 | 7 356 | 294 | 5 | 37 | 25 | 5 064 |
| Kraków | 6 419 | 3 657 | 149 | 35 | 7 | 0 | 2 571 |
| Wrocław | 3 491 | 2 365 | 111 | 6 | 15 | 0 | 994 |
| Poznań | 3 770 | 3 044 | 200 | 4 | 13 | 7 | 502 |
| Łódź | 3 756 | 2 425 | 95 | 42 | 35 | 49 | 1 110 |
| Trójmiasto | 3 968 | 2 741 | 72 | 8 | 16 | 11 | 1 120 |
| GZM | 6 246 | 5 786 | 106 | 24 | 5 | 0 | 325 |

## Pokrycie wg odległości od centrum (pasy 5 km, wszystkie tryby)

| Aglomeracja | 0–5 km | 5–10 km | 10–15 km | 15–20 km | 20–25 km | 25–30 km | 30–35 km | 35–40 km | ≥40 km |
|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 96% (1705) | 96% (2350) | 83% (1691) | 71% (1460) | 57% (1337) | 27% (1314) | 12% (1068) | 2% (596) | 4% (1260) |
| Kraków | 93% (1081) | 98% (1383) | 75% (1093) | 46% (1058) | 16% (777) | 6% (580) | 0% (303) | 1% (117) | 0% (27) |
| Wrocław | 97% (1117) | 92% (875) | 68% (617) | 42% (304) | 10% (195) | 5% (227) | 4% (83) | 0% (33) | 8% (40) |
| Poznań | 95% (1061) | 96% (945) | 95% (684) | 84% (540) | 58% (357) | 21% (121) | 10% (31) | 7% (30) | 0% (1) |
| Łódź | 97% (1171) | 88% (1132) | 49% (689) | 19% (332) | 7% (192) | 5% (150) | 6% (90) | – | – |
| Trójmiasto | 95% (724) | 91% (745) | 70% (491) | 61% (697) | 62% (542) | 68% (355) | 39% (195) | 14% (202) | 0% (17) |
| GZM | 96% (605) | 98% (1154) | 99% (1519) | 97% (1311) | 93% (640) | 92% (519) | 85% (266) | 50% (94) | 63% (138) |

Centra: Warszawa: Rondo Dmowskiego, Kraków: Rynek Główny, Wrocław: Rynek, Poznań: Stary Rynek, Łódź: pl. Wolności, Trójmiasto: Gdańsk Główny, GZM: Katowice Rynek. Trójmiasto i GZM są policentryczne; pierścienie od jednego centrum są tu tylko orientacyjne. Pełne dane (pierścienie 1 km, wszystkie tryby, promienie): `coverage_by_ring.csv`.

## Gminy

Pełna tabela: `coverage_by_gmina.csv` (wszystkie tryby, promienie, liczniki przyczyn, udział powierzchni gminy w FUA,
klasa gminy). Klasa gminy (wszystkie tryby): **dobrze** ≥ 80%, **słabo** < 40%,
pośrodku **mieszana**; gminy z mniej niż 10 przystankami OSM: **mało danych** (wskaźnik niemiarodajny).
Gminy o tej samej nazwie (miasto i gmina wiejska, np. Pabianice, Zgierz, Mińsk Mazowiecki) mają dopisek „(miasto)”
lub „(gmina wiejska)”: mniejsza powierzchniowo to miasto.

**Warszawa** (102 gmin z przystankami OSM; poniżej 10 przystanków: 14). Najsłabiej pokryte (≥ 10 przystanków):

| Gmina | OSM | pokrycie | brak w GTFS | udział pow. gminy w FUA |
|---|---|---|---|---|
| Żabia Wola | 210 | 0,0% | 210 | 100% |
| Tarczyn | 174 | 0,0% | 174 | 100% |
| Serock | 100 | 0,0% | 100 | 100% |
| Jakubów | 66 | 0,0% | 66 | 100% |
| Pułtusk | 66 | 0,0% | 66 | 99% |
| Dobre | 65 | 0,0% | 65 | 99% |
| Siennica | 64 | 0,0% | 64 | 100% |
| Zakroczym | 52 | 0,0% | 52 | 100% |
| Dąbrówka | 49 | 0,0% | 49 | 100% |
| Radziejowice | 49 | 0,0% | 49 | 99% |

**Kraków** (43 gmin z przystankami OSM; poniżej 10 przystanków: 5). Najsłabiej pokryte (≥ 10 przystanków):

| Gmina | OSM | pokrycie | brak w GTFS | udział pow. gminy w FUA |
|---|---|---|---|---|
| Myślenice | 191 | 0,0% | 191 | 99% |
| Gdów | 150 | 0,0% | 150 | 100% |
| Dobczyce | 94 | 0,0% | 94 | 99% |
| Siepraw | 65 | 0,0% | 65 | 100% |
| Sułkowice | 62 | 0,0% | 62 | 99% |
| Alwernia | 61 | 0,0% | 61 | 98% |
| Proszowice | 56 | 0,0% | 56 | 99% |
| Trzyciąż | 55 | 0,0% | 55 | 100% |
| Łapanów | 47 | 0,0% | 47 | 99% |
| Koniusza | 46 | 0,0% | 46 | 100% |

**Wrocław** (21 gmin z przystankami OSM; poniżej 10 przystanków: 1). Najsłabiej pokryte (≥ 10 przystanków):

| Gmina | OSM | pokrycie | brak w GTFS | udział pow. gminy w FUA |
|---|---|---|---|---|
| Zawonia | 22 | 0,0% | 22 | 100% |
| Oleśnica (gmina wiejska) | 58 | 1,7% | 53 | 99% |
| Trzebnica | 92 | 2,2% | 90 | 100% |
| Oleśnica (miasto) | 81 | 2,5% | 78 | 100% |
| Prusice | 32 | 3,1% | 31 | 100% |
| Oborniki Śląskie | 70 | 4,3% | 67 | 100% |
| Dobroszyce | 22 | 4,5% | 21 | 100% |
| Borów | 22 | 4,5% | 21 | 99% |
| Żmigród | 53 | 5,7% | 50 | 100% |
| Mietków | 16 | 6,2% | 15 | 99% |

**Poznań** (22 gmin z przystankami OSM; poniżej 10 przystanków: 3). Najsłabiej pokryte (≥ 10 przystanków):

| Gmina | OSM | pokrycie | brak w GTFS | udział pow. gminy w FUA |
|---|---|---|---|---|
| Stęszew | 61 | 6,6% | 57 | 99% |
| Łubowo | 42 | 7,1% | 39 | 99% |
| Pobiedziska | 115 | 9,6% | 104 | 100% |
| Nekla | 20 | 10,0% | 18 | 99% |
| Kostrzyn | 68 | 16,2% | 56 | 100% |
| Murowana Goślina | 83 | 75,9% | 20 | 99% |
| Mosina | 110 | 78,2% | 22 | 100% |
| Puszczykowo | 27 | 81,5% | 5 | 100% |
| Rokietnica | 102 | 88,2% | 12 | 99% |
| Kórnik | 241 | 88,4% | 28 | 100% |

**Łódź** (27 gmin z przystankami OSM; poniżej 10 przystanków: 2). Najsłabiej pokryte (≥ 10 przystanków):

| Gmina | OSM | pokrycie | brak w GTFS | udział pow. gminy w FUA |
|---|---|---|---|---|
| Pabianice (gmina wiejska) | 65 | 0,0% | 65 | 100% |
| Brójce | 47 | 0,0% | 47 | 99% |
| Tuszyn | 44 | 0,0% | 44 | 99% |
| Dalików | 41 | 0,0% | 41 | 99% |
| Dłutów | 27 | 0,0% | 27 | 100% |
| Łask | 107 | 2,8% | 103 | 99% |
| Koluszki | 72 | 6,9% | 65 | 100% |
| Ozorków (gmina wiejska) | 14 | 7,1% | 13 | 98% |
| Rokiciny | 39 | 7,7% | 35 | 99% |
| Dobroń | 23 | 8,7% | 21 | 100% |

**Trójmiasto** (22 gmin z przystankami OSM; poniżej 10 przystanków: 4). Najsłabiej pokryte (≥ 10 przystanków):

| Gmina | OSM | pokrycie | brak w GTFS | udział pow. gminy w FUA |
|---|---|---|---|---|
| Trąbki Wielkie | 104 | 0,0% | 104 | 100% |
| Przywidz | 69 | 0,0% | 69 | 99% |
| Stegna | 56 | 0,0% | 56 | 99% |
| Cedry Wielkie | 52 | 0,0% | 52 | 100% |
| Suchy Dąb | 14 | 0,0% | 14 | 100% |
| Pszczółki | 43 | 7,0% | 40 | 100% |
| Wejherowo (miasto) | 177 | 15,8% | 148 | 97% |
| Reda | 94 | 20,2% | 75 | 97% |
| Kolbudy | 83 | 24,1% | 63 | 100% |
| Pruszcz Gdański (gmina wiejska) | 153 | 30,1% | 107 | 100% |

**GZM** (43 gmin z przystankami OSM; poniżej 10 przystanków: 4). Najsłabiej pokryte (≥ 10 przystanków):

| Gmina | OSM | pokrycie | brak w GTFS | udział pow. gminy w FUA |
|---|---|---|---|---|
| Rudziniec | 101 | 21,8% | 79 | 99% |
| Miedźna | 40 | 25,0% | 30 | 98% |
| Sośnicowice | 55 | 60,0% | 22 | 99% |
| Łazy | 37 | 67,6% | 12 | 99% |
| Bieruń | 84 | 75,0% | 21 | 99% |
| Kobiór | 14 | 78,6% | 3 | 99% |
| Dąbrowa Górnicza | 418 | 93,3% | 28 | 100% |
| Chorzów | 245 | 93,9% | 15 | 100% |
| Wielowieś | 49 | 93,9% | 3 | 99% |
| Toszek | 69 | 94,2% | 4 | 99% |

## Kto brakuje: tagi `network` / `operator` przystanków bez odpowiednika

Przystanki OSM bez odpowiednika pogrupowane po tagu `network` (gdy brak: `operator`), znormalizowanym (wielkość liter,
cudzysłowy, formy prawne, kolejność wartości rozdzielonych `;`). Kolumny „w gminach słabo/dobrze pokrytych” rozdzielają
dwa różne zjawiska: brak odpowiednika **w gminie słabo pokrytej** (< 40%) to zwykle brakujący przewoźnik, a **w gminie
dobrze pokrytej** (≥ 80%) to raczej przystanek chwilowo nieobsługiwany, nieczynny, szkolny, przesunięty albo szum
mapowania. Pełna tabela: `unmatched_operators.csv`.

**Uwaga:** większość przystanków bez odpowiednika nie ma w OSM ani `network`, ani `operator` („brak tagu”); tagi
nazywają więc przewoźników tylko tam, gdzie mapujący je wpisali. Tagi liczbowe (np. „3, 16” w Wejherowie) to numery
linii wpisane w złe pole.

**Warszawa**

| tag (najczęstszy zapis) | bez odp. | z odp. | w gminach słabo pokrytych | w gminach dobrze pokrytych | gdzie |
|---|---|---|---|---|---|
| (brak tagu) | 3174 | 113 | 2687 | 84 | Błonie (203); Grodzisk Mazowiecki (203); Brwinów (154); Żabia Wola (134) |
| Grodziskie Przewozy Autobusowe | 262 | 16 | 244 | 12 | Grodzisk Mazowiecki (132); Żabia Wola (66); Błonie (35); Stare Babice (12) |
| PKS Grójec | 248 | 18 | 170 | 2 | Tarczyn (144); Prażmów (58); Chynów (25); Góra Kalwaria (16) |
| ZTM Warszawa | 227 | 6595 | 59 | 132 | Warszawa (90); Sulejówek (48); Wołomin (16); Piaseczno (9) |
| Nadwiślańska Komunikacja Autobusowa | 160 | 5 | 76 | 0 | Góra Kalwaria (56); Karczew (46); Józefów (14); Sobienie-Jeziory (10) |
| Bezpłatna Komunikacja Miejska Otwock | 79 | 2 | 70 | 0 | Otwock (70); Wiązowna (9) |
| Pruszkowska Komunikacja Miejska;Grodziskie Przewozy Autobusowe | 69 | 1 | 68 | 0 | Pruszków (67); Michałowice (1); Ożarów Mazowiecki (1) |
| Powiat Legionowski | 69 | 3 | 0 | 0 | Jabłonna (42); Nieporęt (23); Legionowo (4) |
| Pruszkowska Komunikacja Miejska | 68 | 0 | 57 | 0 | Pruszków (45); Michałowice (12); Ożarów Mazowiecki (7); Piastów (4) |
| Nowodworska Komunikacja Autobusowa | 66 | 7 | 65 | 0 | Nowy Dwór Mazowiecki (61); Pomiechówek (4); Wieliszew (1) |
| Powiat siedlecki | 50 | 0 | 50 | 0 | Kotuń (48); Mrozy (2) |
| UTJ Wołoszka | 46 | 0 | 46 | 0 | Celestynów (22); Osieck (17); Kołbiel (6); Sobienie-Jeziory (1) |

**Kraków**

| tag (najczęstszy zapis) | bez odp. | z odp. | w gminach słabo pokrytych | w gminach dobrze pokrytych | gdzie |
|---|---|---|---|---|---|
| (brak tagu) | 1330 | 184 | 1159 | 99 | Miechów (194); Wieliczka (114); Myślenice (105); Krzeszowice (100) |
| Małopolskie Linie Dowozowe | 871 | 21 | 840 | 25 | Wieliczka (144); Myślenice (86); Gdów (78); Drwinia (64) |
| Niepołomicka Komunikacja Gminna | 112 | 6 | 112 | 0 | Niepołomice (110); Biskupice (2) |
| KMK | 61 | 2287 | 6 | 16 | Skawina (39); Kraków (11); Krzeszowice (6); Zielonki (4) |
| MDA | 32 | 3 | 0 | 32 | Kraków (32) |
| Gmina Niepołomice | 30 | 4 | 30 | 0 | Niepołomice (30) |
| Niepołomicka Komunikacja Gminna;Małopolskie Linie Dowozowe | 30 | 1 | 30 | 0 | Niepołomice (28); Gdów (2) |
| KMK;Małopolskie Linie Dojazdowe | 24 | 71 | 0 | 0 | Skawina (24) |
| Komunikacja Miejska w Krakowie | 22 | 860 | 0 | 18 | Kraków (16); Skawina (4); Zabierzów (2) |
| Skawińska Komunikacja Gminna | 22 | 3 | 0 | 0 | Skawina (22) |
| Małopolskie Linie Dowozowe;Skawińska Komunikacja Gminna | 10 | 0 | 0 | 0 | Skawina (10) |
| Wielicka Spółka Transportowa;Małopolskie Linie Dowozowe | 6 | 0 | 6 | 0 | Wieliczka (6) |

**Wrocław**

| tag (najczęstszy zapis) | bez odp. | z odp. | w gminach słabo pokrytych | w gminach dobrze pokrytych | gdzie |
|---|---|---|---|---|---|
| (brak tagu) | 803 | 332 | 680 | 8 | Trzebnica (90); Oleśnica (miasto) (79); Kobierzyce (72); Siechnice (69) |
| Wrocław | 129 | 1988 | 52 | 35 | Siechnice (49); Długołęka (42); Wrocław (34); Kobierzyce (3) |
| Gmina Czernica | 24 | 75 | 0 | 0 | Czernica (24) |
| Siechnicka Komunikacja Publiczna | 20 | 4 | 18 | 2 | Siechnice (18); Wrocław (2) |
| Komunikacja Gminna | 7 | 0 | 7 | 0 | Kobierzyce (7) |
| ZDiUM Wrocław | 5 | 1 | 1 | 4 | Wrocław (4); Siechnice (1) |
| grabor sp. z o. o. spółka | 4 | 0 | 4 | 0 | Mietków (4) |
| Kobierzyce | 4 | 0 | 4 | 0 | Kobierzyce (4) |
| PKS | 3 | 0 | 3 | 0 | Siechnice (2); Żórawina (1) |
| Wrocław (komunikacja podmiejska) | 3 | 1 | 0 | 3 | Wrocław (3) |
| Gmina Kobierzyce | 2 | 1 | 2 | 0 | Kobierzyce (2) |
| Kącka Komunikacja Autobusowa | 2 | 0 | 0 | 0 | Kąty Wrocławskie (2) |

**Poznań**

| tag (najczęstszy zapis) | bez odp. | z odp. | w gminach słabo pokrytych | w gminach dobrze pokrytych | gdzie |
|---|---|---|---|---|---|
| (brak tagu) | 381 | 1388 | 200 | 136 | Pobiedziska (65); Stęszew (55); Poznań (51); Łubowo (39) |
| ZTM Poznań | 47 | 1553 | 0 | 46 | Poznań (30); Luboń (6); Tarnowo Podgórne (5); Komorniki (2) |
| UMiG Pobiedziska | 39 | 0 | 39 | 0 | Pobiedziska (39) |
| Kostrzyńska Komunikacja Publiczna | 19 | 0 | 19 | 0 | Kostrzyn (19) |
| KPP | 15 | 0 | 15 | 0 | Kostrzyn (15) |
| PKP | 5 | 1 | 0 | 5 | Poznań (5) |
| Swarzędz | 4 | 81 | 0 | 4 | Swarzędz (4) |
| Kórnickie Przedsiębiorstwo Autobusowe KOMBUS Sp. z o.o. | 3 | 39 | 0 | 3 | Kórnik (3) |
| PKS | 3 | 1 | 2 | 0 | Stęszew (2); Murowana Goślina (1) |
| Amazon | 2 | 0 | 0 | 2 | Tarnowo Podgórne (2) |
| PKP Polskie Linie Kolejowe | 2 | 53 | 0 | 2 | Poznań (2) |
| Kleszczewo | 1 | 38 | 0 | 1 | Kleszczewo (1) |

**Łódź**

| tag (najczęstszy zapis) | bez odp. | z odp. | w gminach słabo pokrytych | w gminach dobrze pokrytych | gdzie |
|---|---|---|---|---|---|
| (brak tagu) | 1170 | 1567 | 835 | 100 | Pabianice (miasto) (182); Zgierz (miasto) (121); Łask (104); Łódź (73) |
| Lokalny Transport Zbiorowy w Łodzi | 5 | 944 | 0 | 5 | Łódź (5) |
| Kasz-Bus | 4 | 0 | 4 | 0 | Koluszki (4) |
| MZK-Pabianice | 3 | 0 | 3 | 0 | Pabianice (miasto) (3) |
| Express-Bus | 2 | 0 | 0 | 2 | Łódź (2) |
| Markab/MUK Zgierz | 2 | 0 | 0 | 0 | Zgierz (miasto) (2) |
| MF Transport | 2 | 0 | 2 | 0 | Stryków (2) |
| WicherTravel | 2 | 0 | 0 | 0 | Wodzierady (2) |
| Express-Bus;Kasz-Bus | 1 | 0 | 1 | 0 | Stryków (1) |
| Rzgów Grodziska/Zielona | 1 | 0 | 0 | 0 | Rzgów (1) |
| Wicher Travel | 1 | 0 | 0 | 0 | Wodzierady (1) |
| Łask-Pabianice | 1 | 0 | 1 | 0 | Dobroń (1) |

**Trójmiasto**

| tag (najczęstszy zapis) | bez odp. | z odp. | w gminach słabo pokrytych | w gminach dobrze pokrytych | gdzie |
|---|---|---|---|---|---|
| (brak tagu) | 814 | 589 | 741 | 67 | Żukowo (188); Trąbki Wielkie (102); Pruszcz Gdański (gmina wiejska) (97); Przywidz (67) |
| MZK Wejherowo | 163 | 16 | 162 | 0 | Wejherowo (miasto) (93); Reda (69); Puck (1) |
| PKS Gdynia | 51 | 20 | 50 | 0 | Szemud (49); Wejherowo (gmina wiejska) (1); Wejherowo (miasto) (1) |
| ZKM Gdynia | 16 | 879 | 2 | 14 | Gdynia (9); Rumia (2); Sopot (2); Szemud (2) |
| ZTM Gdańsk | 16 | 1177 | 0 | 16 | Gdańsk (16) |
| Przewozy Autokarowe Albatros | 11 | 1 | 11 | 0 | Żukowo (11) |
| 6 | 5 | 0 | 5 | 0 | Wejherowo (miasto) (5) |
| MZK Wejherowo, PKS Gdynia | 5 | 0 | 5 | 0 | Wejherowo (miasto) (5) |
| 841 | 4 | 0 | 4 | 0 | Pruszcz Gdański (gmina wiejska) (4) |
| 16 | 2 | 0 | 2 | 0 | Wejherowo (miasto) (2) |
| 17 | 2 | 0 | 2 | 0 | Reda (2) |
| 3 | 2 | 0 | 2 | 0 | Wejherowo (miasto) (2) |

**GZM**

| tag (najczęstszy zapis) | bez odp. | z odp. | w gminach słabo pokrytych | w gminach dobrze pokrytych | gdzie |
|---|---|---|---|---|---|
| (brak tagu) | 269 | 2185 | 109 | 123 | Rudziniec (79); Miedźna (30); Dąbrowa Górnicza (24); Gliwice (22) |
| Transport GZM | 33 | 3650 | 0 | 29 | Sosnowiec (6); Chorzów (5); Bieruń (4); Katowice (4) |
| PKS Gliwice | 12 | 1 | 0 | 0 | Sośnicowice (12) |
| PKP Polskie Linie Kolejowe | 5 | 43 | 0 | 5 | Katowice (4); Dąbrowa Górnicza (1) |
| ZGKiM Sośnicowice | 4 | 0 | 0 | 0 | Sośnicowice (4) |
| ZPG Jedźmy Razem | 3 | 0 | 0 | 0 | Łazy (3) |
| PGKiM Łaziska Górne | 2 | 0 | 0 | 2 | Mikołów (2) |
| Górnośląskie Koleje Wąskotorowe | 1 | 0 | 0 | 1 | Bytom (1) |
| Przedsiębiorstwo Państwowej Komunikacji Samochodowej w Gliwicach | 1 | 0 | 0 | 1 | Gliwice (1) |

**Brakujący przewoźnicy (interpretacja; dostępność ich GTFS niesprawdzona):**

- **Warszawa:** Grodziskie Przewozy Autobusowe (Grodzisk Maz., Żabia Wola, Błonie), PKS Grójec (Tarczyn, Prażmów,
  Chynów), Nadwiślańska Komunikacja Autobusowa (Góra Kalwaria, Karczew), Bezpłatna Komunikacja Miejska w Otwocku,
  Pruszkowska Komunikacja Miejska, Nowodworska Komunikacja Autobusowa, linie powiatu legionowskiego i DKM Legionowo,
  UTJ Wołoszka, komunikacja w Pułtusku; bez tagów: Mińsk Maz., Błonie, Brwinów, Żyrardów, Milanówek, Serock.
  Te gminy mają kolej (KM, WKD, SKM: stacje dopasowane), brakuje dowozowych autobusów. Przystanki z tagiem
  „ZTM Warszawa” bez odpowiednika poza Warszawą (np. Sulejówek) to zapewne zlikwidowane lub zmienione linie ZTM
  (niesprawdzone).
- **Kraków:** Małopolskie Linie Dowozowe (ponad 800 przystanków: Wieliczka, Myślenice, Gdów, Drwinia), Niepołomicka
  i Skawińska Komunikacja Gminna, Wielicka Spółka Transportowa; „MDA” (Małopolskie Dworce Autobusowe) w Krakowie
  to przystanki linii regionalnych; bez tagów: Miechów, Krzeszowice, Myślenice, Dobczyce, Sułkowice
  (prywatni przewoźnicy busowi). Mobilis (ZTP) jest w danych i pokrywa gminy sąsiadujące z Krakowem.
- **Wrocław:** Siechnicka Komunikacja Publiczna, komunikacja gminna Czernicy i Kobierzyc; przystanki z tagiem
  „Wrocław” w Siechnicach i Długołęce bez odpowiednika (prawdopodobnie linie, które przeszły do innego organizatora;
  niesprawdzone); bez tagów: Oleśnica, Trzebnica, Oborniki Śl., Żmigród, Sobótka (autobusy prywatne; kolej KD jest).
- **Poznań:** ZTM Poznań obejmuje większość gmin FUA; braki: Pobiedziska (komunikacja gminy), Kostrzyn (Kostrzyńska
  Komunikacja Publiczna), Stęszew, Łubowo, Nekla.
- **Łódź:** brak **MZK Pabianice** i **MUK Zgierz** (komunikacja miejska dwóch miast po ok. 55–65 tys. mieszkańców;
  w danych są tylko linie MPK-Łódź, które tam dojeżdżają), a także Łask, Koluszki, Stryków, Tuszyn, Ksawerów, Brójce.
  To najpoważniejsza luka w zestawie: dotyczy miast, nie wsi.
- **Trójmiasto:** **MZK Wejherowo** (Wejherowo, Reda), PKS Gdynia (Szemud), Przewozy Autokarowe Albatros (Żukowo);
  bez tagów: Pruszcz Gdański (gmina wiejska), Trąbki Wielkie, Przywidz, Cedry Wielkie, Kolbudy, Stegna.
- **GZM:** feed ZTM GZM pokrywa prawie wszystko; luki tylko w gminach brzegowych: Rudziniec, Sośnicowice (PKS Gliwice,
  ZGKiM Sośnicowice), Miedźna (poza Metropolią, w FUA Tychów), Bieruń, Łazy (poza Metropolią; ZPG „Jedźmy Razem”).

## Kierunek odwrotny: przystanki GTFS bez przystanku OSM

Ile obsłużonych przystanków GTFS nie ma w pobliżu przystanku OSM (promienie jak wyżej, sama odległość). To ogranicza
zaufanie do OSM jako mianownika: tam, gdzie OSM gubi przystanki obsługiwane przez GTFS, gubi zapewne także przystanki
przewoźników spoza GTFS, więc pokrycie jest tam **zawyżone**. Kolumna „bez żadnego OSM” liczy przystanki bez
jakiegokolwiek przystanku OSM w promieniu (więc nie różnice w oznaczeniu trybu). Najwięcej braków: przedmieścia Poznania
(ok. 15% przystanków ZTM poza rdzeniem; połowa ponad 100 m od czegokolwiek w OSM) i Wrocławia (ok. 16% poza rdzeniem),
GZM (ok. 7%). W rdzeniach oraz w Warszawie, Krakowie, Łodzi i Trójmieście 1–6%. Kolej: prawie zero (2 stacje
w Krakowie).
Tabela: przyjęte promienie, sama odległość.

| Aglomeracja | tryb GTFS | obsłużone w dniu ref. | bez OSM zgodnego trybu | udział | bez żadnego OSM |
|---|---|---|---|---|---|
| GZM | autobus | 6013 | 426 | 7,1% | 414 |
| GZM | kolej | 71 | 0 | 0,0% | 0 |
| GZM | tramwaj | 717 | 55 | 7,7% | 46 |
| Kraków | autobus | 3701 | 100 | 2,7% | 43 |
| Kraków | kolej | 70 | 2 | 2,9% | 2 |
| Kraków | tramwaj | 353 | 0 | 0,0% | 0 |
| Łódź | autobus | 1865 | 58 | 3,1% | 53 |
| Łódź | kolej | 56 | 0 | 0,0% | 0 |
| Łódź | tramwaj | 465 | 8 | 1,7% | 5 |
| Poznań | autobus | 2964 | 339 | 11,4% | 334 |
| Poznań | kolej | 62 | 0 | 0,0% | 0 |
| Poznań | tramwaj | 304 | 1 | 0,3% | 1 |
| Trójmiasto | autobus | 2487 | 64 | 2,6% | 61 |
| Trójmiasto | kolej | 53 | 0 | 0,0% | 0 |
| Trójmiasto | tramwaj | 248 | 5 | 2,0% | 5 |
| Trójmiasto | ZKA (autobus zastępczy kolei) | 5 | 0 | 0,0% | 0 |
| Warszawa | autobus | 6220 | 88 | 1,4% | 86 |
| Warszawa | metro | 38 | 3 | 7,9% | 0 |
| Warszawa | kolej | 264 | 0 | 0,0% | 0 |
| Warszawa | tramwaj | 630 | 10 | 1,6% | 7 |
| Wrocław | autobus | 2044 | 146 | 7,1% | 142 |
| Wrocław | kolej | 83 | 0 | 0,0% | 0 |
| Wrocław | tramwaj | 447 | 7 | 1,6% | 3 |

## Ludność w obszarze pokrytym: pierwsze przybliżenie (WSTĘPNE)

Pierwsze przybliżenie: jaka część ludności FUA (NSP 2021, siatka 1 km, komórka przypisana do gminy i FUA wg centroidu)
mieszka na obszarze, który można uznać za pokryty danymi. Dwa warianty, oba **wstępne** (definicja maski należy do fazy 2):
- **gminy**: ludność gmin, w których pokrycie (wszystkie tryby) ≥ próg; progi 50%, 70%, 85%;
- **komórki**: ludność komórek 1 km, w których ≥ próg przystanków OSM w promieniu 1 km od centroidu ma odpowiednik
  (komórki bez żadnego przystanku OSM w 1 km są osobno i nie wchodzą do obszaru pokrytego).

| Aglomeracja | ludność FUA (NSP 2021) | w rdzeniu | gminy ≥50% | gminy ≥70% | gminy ≥85% | gminy bez przyst. OSM | komórki ≥50% | komórki ≥70% | komórki ≥85% | komórki bez przyst. OSM w 1 km |
|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 3 485 881 | 53,5% | 73,2% | 66,6% | 60,0% | 0,2% | 73,2% | 69,0% | 65,2% | 4,7% |
| Kraków | 1 411 779 | 56,2% | 71,1% | 67,3% | 65,6% | 0,3% | 72,8% | 69,1% | 65,2% | 3,4% |
| Wrocław | 1 011 966 | 66,6% | 78,5% | 74,5% | 68,5% | 0,0% | 77,5% | 75,8% | 72,6% | 3,4% |
| Poznań | 974 744 | 56,2% | 92,7% | 92,7% | 86,6% | 0,0% | 92,2% | 90,7% | 80,5% | 2,2% |
| Łódź | 1 044 086 | 63,8% | 68,3% | 67,4% | 65,7% | 0,0% | 75,3% | 69,7% | 66,0% | 5,2% |
| Trójmiasto | 1 089 730 | 69,0% | 77,7% | 77,7% | 75,0% | 0,0% | 82,5% | 81,1% | 76,1% | 1,3% |
| GZM | 2 057 054 | 79,9% | 98,7% | 97,5% | 96,3% | 0,0% | 98,3% | 97,6% | 94,9% | 0,5% |

Reguła z §6 (≥ ~85% ludności FUA w obszarze pokrytym) jest spełniona tylko w **GZM** i, przy progu gminnym do 85%
włącznie, w **Poznaniu** (w wariancie komórkowym przy progu 85% Poznań spada do ok. 80%). Dla Warszawy, Krakowa,
Łodzi, Wrocławia i Trójmiasta udział wynosi ok. 60–83% niezależnie od progu i wariantu: obszar pokryty to w praktyce
rdzeń plus gminy obsługiwane przez zarząd transportu miasta. Wybór progu (50 / 70 / 85%) zmienia wynik o 2–13 pkt
proc., wariant (gmina / komórka) o kilka punktów: o ocenie „niepełny” decyduje brak przewoźników, a nie parametr.

## Zaniżenie przez brak przewoźników podmiejskich

| Aglomeracja | ludność FUA w gminach z pokryciem < 50% | ludność FUA w gminach z pokryciem < 85% | przystanki OSM bez odp. w gminach słabo pokrytych | główni nazwani przewoźnicy bez GTFS (przystanki bez odp.) |
|---|---|---|---|---|
| Warszawa | 26,6% | 39,8% | 4 041 | Grodziskie Przewozy Autobusowe (262); PKS Grójec (248); Nadwiślańska Komunikacja Autobusowa (160); Bezpłatna Komunikacja Miejska Otwock (79) |
| Kraków | 28,7% | 34,2% | 2 198 | Małopolskie Linie Dowozowe (871); Niepołomicka Komunikacja Gminna (112); MDA (32); Gmina Niepołomice (30) |
| Wrocław | 21,4% | 31,5% | 772 | Siechnicka Komunikacja Publiczna (20); Komunikacja Gminna (7); ZDiUM Wrocław (5); grabor sp. z o. o. spółka (4) |
| Poznań | 7,3% | 13,4% | 275 | UMiG Pobiedziska (39); Kostrzyńska Komunikacja Publiczna (19); KPP (15); PKP (5) |
| Łódź | 31,7% | 34,3% | 846 | Kasz-Bus (4); MZK-Pabianice (3); Express-Bus (2); Markab/MUK Zgierz (2) |
| Trójmiasto | 22,3% | 25,0% | 1 033 | MZK Wejherowo (163); PKS Gdynia (51); Przewozy Autokarowe Albatros (11); MZK Wejherowo, PKS Gdynia (5) |
| GZM | 1,3% | 3,6% | 109 | PKS Gliwice (12); ZGKiM Sośnicowice (4); ZPG Jedźmy Razem (3); PGKiM Łaziska Górne (2) |

Systematycznie zaniżone (gdyby liczyć na całej FUA bez maski) byłyby: **Warszawa, Kraków, Łódź, Wrocław i Trójmiasto**.
W każdej z nich ok. 20–35% ludności FUA mieszka w gminach, gdzie mniej niż połowa przystanków OSM ma odpowiednik
w GTFS; tam miary z §4.5–4.7 widziałyby tylko kolej i linie zarządu transportu miasta, bez gminnych i prywatnych
autobusów. Skala zaniżenia samej miary (np. PNFT) nie jest jeszcze znana: brakujący przewoźnicy jeżdżą zwykle
rzadko, więc dla progu częstej komunikacji (≤ 10 min) strata może być mała, a dla dostępności (§4.6) i podaży
(wozokm na mieszkańca) duża. **Poznań** jest zaniżony nieznacznie (kilka gmin wschodnich), **GZM** praktycznie wcale.
Do porównań między aglomeracjami zostaje wariant „obszar pokryty” lub „rdzeń”, z adnotacją.

## Ograniczenia

1. **OSM jako mianownik jest niepełny i nierówny.** 1–16% obsłużonych przystanków GTFS nie ma odpowiednika w OSM
   (tabela wyżej). Gdzie OSM jest rzadszy, wskaźnik pokrycia jest zawyżony (brakuje także przystanków przewoźników
   spoza GTFS). Odwrotnie: OSM zawiera przystanki nieczynne, szkolne, zakładowe i prywatne bez oznaczenia; to zaniża
   wskaźnik w gminach dobrze pokrytych o kilka punktów.
2. **Jeden dzień.** Przystanek obsługiwany tylko w inne dni (weekend, sezon, wydarzenia, np. Gdańsk Stadion Expo)
   liczy się jako bez odpowiednika (kategoria „w feedzie, nieobsłużony”, gdy jest w `stops.txt`). Remonty w dniu ref.
   (tramwaje w Krakowie i Łodzi) obsłużono regułą „zastępczy” tylko w masce; w wskaźnikach tramwajowych zostają brakiem.
3. **Obecność, nie częstotliwość.** Przystanek z jednym kursem dziennie liczy się tak samo jak z dwustoma. Maska
   mówi, czy są dane, a nie czy jest dobra obsługa.
4. **Dopasowanie po nazwie** może połączyć przystanek z przeciwnym kierunkiem tego samego przystanku albo z przystankiem
   innego przewoźnika o tej samej nazwie po drugiej stronie ulicy. Dla maski (czy obszar ma dane) to nieszkodliwe;
   dla nazwania brakujących przewoźników lekko zaniża ich listę.
5. **Tagi przewoźników** są w OSM rzadkie (większość braków „bez tagu”); nazwy przewoźników w raporcie to próbka,
   nie inwentarz. Dostępność GTFS dla wymienionych przewoźników nie była sprawdzana.
6. **Filtr kolei turystycznych** działa po nazwie i operatorze; stacje nieczynnych linii bez znacznika `disused`
   zostają w mianowniku jako braki (w FUA fazy 1 to pojedyncze przypadki).
7. **Granice gmin LAU 2021 w skali 1:1M** są uogólnione: przystanki przy granicy gminy mogą trafić do sąsiedniej.
   Gminy brzegowe przecięte granicą FUA mają w tabeli udział powierzchni w FUA.
8. **GZM** w prowizorycznym wariancie „suma FUA”; wariant „Metropolia (41 gmin)” zmieniłby zestaw gmin brzegowych
   (np. Miedźna i Łazy wypadają, dochodzą inne gminy). Trójmiasto i GZM: pierścienie od jednego centrum są tylko
   orientacyjne.
9. **Ludność**: NSP 2021 (stan 31.03.2021) wobec rozkładów z 2026; nowe osiedla podmiejskie nie są w siatce.
   Wariant gminny jest zgrubny (gmina 30% pokryta, ale z pokrytym głównym miastem, wypada cała).
10. **Rozkłady**: PKM (Pomorska Kolej Metropolitalna) w `polish_trains` rusza dopiero od 13.12.2026, więc w dniu ref.
    część linii 201 obsługuje ZKA; to przypisane do kolei. Duplikaty kursów (GZM, SKM Warszawa) nie wpływają na wynik.

## Pliki

- `coverage_summary.csv`: aglomeracja × tryb × promień: liczba przystanków OSM, pokrycie FUA / rdzeń / poza rdzeniem
  (z nazwą/kodem i samą odległością), kontrola przypadku, pokrycie dowolnym trybem, GTFS bez OSM; `recommended` = przyjęty promień.
- `coverage_by_gmina.csv`, `coverage_by_ring.csv` (pierścienie 1 km): liczniki przyczyn i pokrycie przy wszystkich promieniach.
- `unmatched_operators.csv`: tagi przystanków bez odpowiednika, z rozbiciem na klasy gmin i listą gmin.
- `gtfs_without_osm.csv`: aglomeracja × feed × tryb × rdzeń/poza: przystanki GTFS bez OSM przy kolejnych promieniach.
- `population_coverage_preliminary.csv`: wstępne udziały ludności (wariant gminny i komórkowy).
- `map_<aglomeracja>.png`: przystanki OSM z odpowiednikiem / bez na tle gmin; `nn_hist_<aglomeracja>.png`: histogramy odległości.
- `_meta.json`: wejścia (manifest), promienie, wyłączone stacje kolei turystycznych, przypisanie feedów.

## Propozycje do `config.yaml`

- `osm_gtfs_match_radius_m: 50` (bez zmian; autobus, tramwaj, metro, perony o nieokreślonym trybie);
- nowe: `osm_gtfs_rail_match_radius_m: 200` (stacje kolejowe);
- nowe: `osm_gtfs_name_match_radius_m: {bus_tram: 200, rail: 500}` (dopasowanie pomocnicze po nazwie/kodzie);
- do decyzji przy masce w fazie 2: próg pokrycia gminy/komórki (50 / 70 / 85%) i wariant (gmina czy komórka 1 km).
Moduł czyta `osm_gtfs_rail_match_radius_m`, jeśli klucz istnieje; w przeciwnym razie używa 200 m.
