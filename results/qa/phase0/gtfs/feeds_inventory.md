# Inwentaryzacja feedów GTFS (faza 0)

Stan na 2026-11-23; pliki pobrane dziś, hasze w `data/manifest.csv`. Ważność liczona z `calendar.txt` + `calendar_dates.txt` (dni, w których jest co najmniej jeden kurs), a nie z `feed_info.txt`. Pełne dane: `feeds_inventory.csv`.

## Ważność i skala

| Feed | Wydawca | feed_info (od–do) | Pierwszy–ostatni dzień kursowania | Dni | Agencje | Trasy | Przystanki | Kursy |
|---|---|---|---|---:|---:|---:|---:|---:|
| `gdansk` | ZTM w Gdańsku | nan–20261207 | 2026-11-23 – 2026-12-07 | 15 | 1 | 93 | 1606 | 95669 |
| `gdynia` | Zarząd Dróg i Zieleni w Gdyni (ZKM Gdynia timetables) | brak | 2026-11-23 – 2027-01-29 | 68 | 8 | 93 | 1151 | 9802 |
| `gzm` | ZTM GZM (mirror of the extended version from otwartedane.metropoliagzm.pl) | 20261108–20261108 | 2026-11-08 – 2026-11-28 | 21 | 1 | 492 | 7761 | 65209 |
| `krakow_bus` | ZTP Kraków | 20261114–20280131 | 2026-11-14 – 2028-01-31 | 327 | 1 | 161 | 2984 | 65307 |
| `krakow_mobilis` | ZTP Kraków (suburban lines operated by Mobilis) | 20261118–20280131 | 2026-11-18 – 2028-01-31 | 323 | 1 | 33 | 765 | 17476 |
| `krakow_tram` | ZTP Kraków | nan–nan | 2026-11-21 – 2027-02-19 | 91 | 1 | 25 | 355 | 15321 |
| `lodz` | Miasto Łódź, portal Otwarte dane (MPK-Łódź) | 20261122–20261231 | 2026-11-22 – 2026-12-31 | 40 | 1 | 134 | 2391 | 24158 |
| `polish_trains` | PKP PLK data repackaged by M. Kuranowski (mkuran.pl) | 20261123–20261223 | 2026-11-21 – 2026-12-23 | 33 | 13 | 211 | 12421 | 29910 |
| `poznan` | ZTM Poznań | 20261124–20261205 | 2026-11-24 – 2026-12-05 | 12 | 14 | 220 | 3358 | 51150 |
| `warsaw_wkd` | Warszawska Kolej Dojazdowa (mkuran.pl) | brak | 2025-12-14 – 2026-12-12 | 364 | 1 | 2 | 60 | 3702 |
| `warsaw_ztm` | ZTM Warszawa (unofficial repackaging by M. Kuranowski, mkuran.pl) | brak | 2026-11-23 – 2026-12-23 | 31 | 1 | 322 | 7280 | 284395 |
| `wroclaw` | Urząd Miejski Wrocławia, Wydział Transportu (Wrocław Open Data) | 20261123–20261206 | 2026-11-23 – 2026-12-06 | 14 | 6 | 137 | 2493 | 42546 |

## Trasy wg rodzaju (route_type rozszerzone sprowadzone do klas)

| Feed | tramwaj | metro | kolej | autobus | trolejbus | prom | inne | surowe route_type |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `gdansk` | 10 | 0 | 0 | 83 | 0 | 0 | 0 | 700:83;900:10 |
| `gdynia` | 0 | 0 | 0 | 77 | 16 | 0 | 0 | 700:77;800:16 |
| `gzm` | 28 | 0 | 0 | 456 | 8 | 0 | 0 | 0:28;11:8;3:456 |
| `krakow_bus` | 0 | 0 | 0 | 161 | 0 | 0 | 0 | 3:161 |
| `krakow_mobilis` | 0 | 0 | 0 | 33 | 0 | 0 | 0 | 3:33 |
| `krakow_tram` | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 900:25 |
| `lodz` | 26 | 0 | 0 | 108 | 0 | 0 | 0 | 0:26;3:108 |
| `polish_trains` | 0 | 0 | 164 | 47 | 0 | 0 | 0 | 2:164;3:47 |
| `poznan` | 21 | 0 | 0 | 199 | 0 | 0 | 0 | 0:21;3:199 |
| `warsaw_wkd` | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 2:1;3:1 |
| `warsaw_ztm` | 26 | 2 | 5 | 289 | 0 | 0 | 0 | 0:26;1:2;2:5;3:289 |
| `wroclaw` | 25 | 0 | 0 | 112 | 0 | 0 | 0 | 0:25;3:112 |

## Kompletność pól

| Feed | shapes.txt | kursy z kształtem % | shape_dist w shapes % | shape_dist w stop_times % | frequencies | parent_station % | direction_id % | block_id % | strefa czasowa |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
| `gdansk` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `gdynia` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `gzm` | tak | 100.0 | 0.0 | 100.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `krakow_bus` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `krakow_mobilis` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `krakow_tram` | tak | 100.0 | 0.0 | 100.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `lodz` | tak | 99.7 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `polish_trains` | tak | 95.1 | 100.0 | 98.1 | nie (0) | 100.0 | 51.9 | 0.0 | Europe/Warsaw |
| `poznan` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `warsaw_wkd` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `warsaw_ztm` | tak | 100.0 | 100.0 | 100.0 | tak (16) | 0.6 | 100.0 | 100.0 | Europe/Warsaw |
| `wroclaw` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |

`parent_station %` liczone dla przystanków-słupków (`location_type=0`). `frequencies (n)` = liczba kursów opisanych przez `frequencies.txt`; takie kursy są rozwijane do liczby odjazdów.

## Licencje i pobranie

| Feed | Licencja (wg wydawcy) | Pobrano | URL |
|---|---|---|---|
| `gdansk` | CC BY 4.0 (Creative Commons Attribution) | 2026-11-23T18:19:06+01:00 | https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/30e783e4-2bec-4a7d-bb22-ee3e3b26ca96/download/gtfsgoogle.zip |
| `gdynia` | CC BY 4.0 (Creative Commons Attribution) | 2026-11-23T18:19:08+01:00 | https://api.zdiz.gdynia.pl/pt/gtfs.zip |
| `gzm` | CC BY 4.0 | 2026-11-23T18:19:11+01:00 | https://github.com/TransportGZM-GTFS-mirror/TransportGZM-GTFS-extended-ver/releases/latest/download/TransportGZM-GTFS.zip |
| `krakow_bus` | CC BY 4.0 | 2026-11-23T18:18:57+01:00 | https://gtfs.ztp.krakow.pl/GTFS_KRK_A.zip |
| `krakow_mobilis` | CC BY 4.0 | 2026-11-23T18:36:52+01:00 | https://gtfs.ztp.krakow.pl/GTFS_KRK_M.zip |
| `krakow_tram` | CC BY 4.0 | 2026-11-23T18:18:58+01:00 | https://gtfs.ztp.krakow.pl/GTFS_KRK_T.zip |
| `lodz` | open licence of the Łódź open-data portal (attribution required; licence name not stated on the dataset page) | 2026-11-23T18:19:04+01:00 | https://otwarte.miasto.lodz.pl/wp-content/uploads/2025/06/GTFS.zip |
| `polish_trains` | PKP PLK public-sector data usage terms + Koleje Mazowieckie public-sector data usage terms | 2026-11-23T18:19:13+01:00 | https://mkuran.pl/gtfs/polish_trains.zip |
| `poznan` | ZTM Poznań terms of use (Zasady korzystania z danych) | 2026-11-23T18:19:02+01:00 | https://www.ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile |
| `warsaw_wkd` | CC0 1.0 | 2026-11-23T18:18:55+01:00 | https://mkuran.pl/gtfs/wkd.zip |
| `warsaw_ztm` | ZTM Warszawa data usage terms + ODbL for bus shapes (OSM); attribution: ZTM Warszawa, Mikołaj Kuranowski, OpenStreetMap contributors | 2026-11-23T18:18:52+01:00 | https://mkuran.pl/gtfs/warsaw.zip |
| `wroclaw` | CC0 1.0 | 2026-11-23T18:24:42+01:00 | https://open-data.cui.wroclaw.pl/hdb/download/164/ |

## Wykryte defekty

- `krakow_bus`: 2 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 117 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `krakow_mobilis`: 2 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 117 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
