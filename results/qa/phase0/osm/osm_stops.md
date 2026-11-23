# Przystanki OSM (maska pokrycia GTFS): inwentaryzacja

Faza 0, generowane przez `pipeline/osm_stops.py` (ekstrakcja i deduplikacja) oraz `python -m pipeline.osm_stops --report` (ten raport). To wejście do maski pokrycia GTFS (§6 briefu); dopasowanie do przystanków GTFS jest osobnym, późniejszym krokiem.

## Dane

- Plik: `poland-latest.osm.pbf` (Geofabrik), 2.12 GB, licencja ODbL 1.0, pobrany 2026-11-23; **stan danych (znacznik replikacji z nagłówka PBF): 2026-11-22T21:20:48Z**; SHA-256 w `data/manifest.csv`.
- Jeden przebieg pyosmium po całym pliku (węzły i drogi; współrzędne dróg z indeksu lokalizacji węzłów). Obiekty ze znacznikami `highway`, `public_transport` lub `railway`, klasyfikowane jak niżej. Drogi (platformy jako obszary) sprowadzone do punktu = średnia współrzędnych wierzchołków.
- **Nie czytano relacji** (multipoligony peronów i stacji). Są rzadkie, ale ich brak lekko zaniża liczbę dużych stacji i peronów; stacje kolejowe są przeważnie węzłami lub zamkniętymi drogami.

### Reguły wyboru obiektów

| Obiekt | `kind` |
|---|---|
| `railway=tram_stop` | `tram` |
| `highway=bus_stop` | `bus` |
| `railway=station` lub `halt` (z `station=subway` albo `subway=yes`) | `rail_station` (`subway`) |
| `public_transport=station` | `subway` / `rail_station` / `bus` (dworzec autobusowy) / `tram` wg `station`, `train`, `subway`, `bus`, `tram`; bez trybu: `platform_unknown` |
| `public_transport=platform` | `tram=yes`: `tram`; `subway=yes`: `subway`; `train=yes` lub `railway=platform`: `rail_platform`; `light_rail=yes`: `tram`; `bus=yes` / `trolleybus=yes`: `bus`; `ferry=yes`: `ferry`; inaczej `platform_unknown` |

Pominięte: `public_transport=stop_position` (chyba że ma też jeden ze znaczników powyżej) oraz obiekty `disused` / `abandoned` / `construction` / `proposed` / `razed` (jako klucz albo wartość `highway` / `railway` / `public_transport`). Peronów niekomunikacyjnych nie da się w OSM wiarygodnie wykluczyć; `platform_unknown` zostaje jako osobna kategoria (tryb nieokreślony, część może nie być przystankami). Przystanki szkolne i prywatne (`access=private`) nie są filtrowane.

## Liczby krajowe (wg `kind`)

| Rodzaj | Surowe | Po deduplikacji | Usunięte | Bez nazwy (po dedup.) |
|---|---|---|---|---|
| autobus (`bus`) | 153738 | 133208 | 20530 | 25155 (18.9%) |
| tramwaj (`tram`) | 7983 | 4606 | 3377 | 136 (3.0%) |
| stacja kolejowa (`rail_station`) | 3339 | 3337 | 2 | 5 (0.1%) |
| peron kolejowy (`rail_platform`) | 5541 | 4690 | 851 | 820 (17.5%) |
| metro (`subway`) | 75 | 47 | 28 | 1 (2.1%) |
| prom (`ferry`) | 7 | 6 | 1 | 3 (50.0%) |
| peron, tryb nieznany (`platform_unknown`) | 13952 | 6134 | 7818 | 4875 (79.5%) |
| **Razem** | **184635** | **152028** | **32607** | **30995 (20.4%)** |

Podział wg znacznika źródłowego (surowe): `highway=bus_stop`: 139522, `public_transport=platform`: 36578, `railway=tram_stop`: 4267, `railway=halt`: 2063, `railway=station`: 1306, `public_transport=station`: 899.

Po dedup.: rekordy z `ref` 38.2%, z `operator` 23.9%, z `network` 32.2%.
Rozbicie wg województw (NUTS 2 z GISCO 2021; Mazowsze to w NUTS 2021 dwa regiony: stołeczny i regionalny) w `osm_stops_by_voivodeship_kind.csv`.

## Deduplikacja (promień 15 m)

OSM często opisuje jeden fizyczny przystanek podwójnie: słupek `highway=bus_stop` (węzeł) i peron `public_transport=platform` (węzeł lub obszar). Reguła:

1. Obiekty w EPSG:2180 szeregowane: słupki i stacje (`highway=bus_stop`, `railway=*`, `public_transport=station`) przed peronami-węzłami, te przed peronami-drogami; w grupie najpierw nazwane, potem wg `osm_id`.
2. Kolejno każdy jeszcze nieprzypisany obiekt jest **zalążkiem** i pochłania wszystkie nieprzypisane obiekty w promieniu 15 m, które (a) są **tego samego trybu** (autobus; tramwaj; kolej = stacja i peron kolejowy; metro; prom) albo są `platform_unknown` (pochłaniany przez dowolny tryb), oraz (b) **nie mają konfliktu nazw** (obie nazwy obecne i różne po `casefold`: nie łączymy).
3. Zalążki nie łączą się łańcuchowo, więc rząd przystanków co ok. 10 m nie zapada się w jeden punkt. Brakujące `name` / `ref` / `network` / `operator` zalążka są uzupełniane od pochłoniętych. Pozycja = pozycja zalążka; `n_merged` i `merged_ids` zapisują pochłonięte obiekty.

Efekt: **184635 → 152028** obiektów, usunięto **32607** (17.7%).

| Zalążek ← pochłonięty | Liczba |
|---|---|
| `highway=bus_stop <- highway=bus_stop` | 8183 |
| `highway=bus_stop <- public_transport=platform` | 19412 |
| `highway=bus_stop <- public_transport=station` | 64 |
| `public_transport=platform <- public_transport=platform` | 560 |
| `public_transport=station <- highway=bus_stop` | 54 |
| `public_transport=station <- public_transport=platform` | 75 |
| `public_transport=station <- public_transport=station` | 9 |
| `railway=halt <- public_transport=platform` | 598 |
| `railway=halt <- public_transport=station` | 1 |
| `railway=station <- public_transport=platform` | 178 |
| `railway=station <- railway=station` | 2 |
| `railway=tram_stop <- public_transport=platform` | 2969 |
| `railway=tram_stop <- public_transport=station` | 2 |
| `railway=tram_stop <- railway=tram_stop` | 500 |

Interpretacja: wiersze `… ← public_transport=platform` to właściwy efekt (podwójny opis jednego przystanku). Wiersze „słupek ← słupek” to dwa obiekty tego samego trybu i nazwy w odległości poniżej progu (np. dwa słupki jednego przystanku albo dwa kierunki na torowisku tramwajowym); dla maski pokrycia nie ma to znaczenia, ale **liczba po deduplikacji to liczba punktów-przystanków, nie słupków ani peronów**.

## Aglomeracje fazy 1

Obszar: wielokąty FUA z URAU 2021 (GISCO, `data/raw/boundaries`), bo `results/web/fua.geojson` jeszcze nie istniało w chwili uruchomienia; zamiast prostokątów użyto więc prawdziwych granic FUA (Trójmiasto = FUA Gdańsk PL006F, GZM = FUA Katowice PL010F; wariant GZM do decyzji).

| Aglomeracja | FUA km² | Razem (dedup.) | Razem (surowe) | autobus | tramwaj | stacja kolejowa | peron kolejowy | metro | prom | peron, tryb nieznany | Bez nazwy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 9296 | 13089 | 14268 | 11573 | 854 | 209 | 318 | 47 | 0 | 88 | 627 (4.8%) |
| Łódź | 2520 | 3837 | 6466 | 3052 | 566 | 58 | 121 | 0 | 0 | 40 | 144 (3.8%) |
| Kraków | 3345 | 6539 | 7405 | 5764 | 503 | 76 | 144 | 0 | 3 | 49 | 546 (8.3%) |
| Wrocław | 3107 | 3608 | 4235 | 2693 | 473 | 83 | 119 | 0 | 0 | 240 | 570 (15.8%) |
| Poznań | 2279 | 3872 | 6440 | 3026 | 344 | 68 | 120 | 0 | 0 | 314 | 398 (10.3%) |
| Trójmiasto | 1466 | 2695 | 3003 | 2209 | 351 | 53 | 76 | 0 | 0 | 6 | 236 (8.8%) |
| GZM | 922 | 3648 | 5713 | 3024 | 452 | 41 | 95 | 0 | 0 | 36 | 73 (2.0%) |

Wykresy kontrolne (przystanki po dedup. na tle granicy FUA): `qa_warszawa.png`, `qa_lodz.png`, `qa_krakow.png`, `qa_wroclaw.png`, `qa_poznan.png`, `qa_trojmiasto.png`, `qa_gzm.png`. Mają pokazać dziury (obszary bez przystanków, np. gminy ze słabo zmapowanym transportem) i skupiska artefaktów.

## Ograniczenia

- OSM jest uzupełniany ochotniczo: kompletność jest nierówna między gminami; brak przystanku w OSM może zawyżać późniejszy wskaźnik pokrycia.
- Przystanki obecne w OSM, a nieobecne w GTFS (przewoźnicy prywatni), to dokładnie sygnał dziur GTFS (§6 briefu); nie filtrowano po `operator`.
- Przystanki tymczasowe, objazdowe i szkolne nie są wydzielane.
- Dedup nie łączy przystanków różnych trybów (np. autobus i tramwaj przy wspólnym przystanku), co jest zamierzone.
