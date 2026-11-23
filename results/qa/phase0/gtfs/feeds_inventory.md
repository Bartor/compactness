# Inwentaryzacja feedów GTFS (faza 0)

Stan na 2026-11-23; pliki pobrane dziś, hasze w `data/manifest.csv`. Ważność liczona z `calendar.txt` + `calendar_dates.txt` (dni, w których jest co najmniej jeden kurs), a nie z `feed_info.txt`. Pełne dane: `feeds_inventory.csv`.

## Ważność i skala

| Feed | Wydawca | feed_info (od–do) | Pierwszy–ostatni dzień kursowania | Dni | Agencje | Trasy | Przystanki | Kursy |
|---|---|---|---|---:|---:|---:|---:|---:|
| `gdansk` | ZTM w Gdańsku | nan–20261207 | 2026-11-23 – 2026-12-07 | 15 | 1 | 93 | 1606 | 95669 |
| `gdynia` | Zarząd Dróg i Zieleni w Gdyni (ZKM Gdynia timetables) | brak | 2026-11-23 – 2027-01-29 | 68 | 8 | 93 | 1151 | 9802 |
| `gzm` | ZTM GZM (mirror of the extended version from otwartedane.metropoliagzm.pl) | 20261108–20261108 | 2026-11-08 – 2026-11-28 | 21 | 1 | 492 | 7761 | 65209 |
| `krakow_ald` | Koleje Małopolskie (autobusowe linie dowozowe ALD / Małopolskie Linie Dowozowe) | 20261123–20271231 | 2026-11-23 – 2027-12-31 | 401 | 1 | 70 | 6650 | 2545 |
| `krakow_bus` | ZTP Kraków | 20261114–20280131 | 2026-11-14 – 2028-01-31 | 327 | 1 | 161 | 2984 | 65307 |
| `krakow_mobilis` | ZTP Kraków (suburban lines operated by Mobilis) | 20261118–20280131 | 2026-11-18 – 2028-01-31 | 323 | 1 | 33 | 765 | 17476 |
| `krakow_niepolomice` | Gmina Niepołomice (via zbiorkom.live) | 20261123–20261224 | 2026-11-23 – 2026-12-24 | 32 | 1 | 5 | 244 | 248 |
| `krakow_skawina` | Urząd Miasta i Gminy Skawina via files.girlc.at | 20261115–20261128 | 2026-11-15 – 2026-11-28 | 14 | 1 | 11 | 236 | 3630 |
| `krakow_tram` | ZTP Kraków | nan–nan | 2026-11-21 – 2027-02-19 | 91 | 1 | 25 | 355 | 15321 |
| `lodz` | Miasto Łódź, portal Otwarte dane (MPK-Łódź) | 20261122–20261231 | 2026-11-22 – 2026-12-31 | 40 | 1 | 134 | 2391 | 24158 |
| `lodz_aleksandrow` | Urząd Miejski Aleksandrów Łódzki via files.girlc.at | 20261115–20261128 | 2026-11-15 – 2026-11-28 | 14 | 1 | 4 | 152 | 840 |
| `lodz_lka_bus` | Łódzka Kolej Aglomeracyjna, buses (M. Kasznia repackaging) | brak | 2026-03-08 – 2026-12-12 | 280 | 1 | 52 | 454 | 1263 |
| `lodz_pabianice` | MZK Pabianice (via zbiorkom.live) | 20261123–20261222 | 2026-11-23 – 2026-12-22 | 30 | 1 | 14 | 261 | 866 |
| `lodz_strykow` | Urząd Miejski Stryków via files.girlc.at | 20261115–20261128 | 2026-11-16 – 2026-11-27 | 10 | 1 | 7 | 179 | 430 |
| `lodz_suburban_qbx` | QBX Timetables (community GitHub repository): 6 private carriers around Łódź | 20261115–20271231 | 2026-11-15 – 2027-12-31 | 412 | 11 | 20 | 709 | 672 |
| `lodz_zgierz` | MUK Zgierz (via zbiorkom.live) | 20261123–20261222 | 2026-11-23 – 2026-12-22 | 30 | 1 | 9 | 298 | 581 |
| `polish_trains` | PKP PLK data repackaged by M. Kuranowski (mkuran.pl) | 20261123–20261223 | 2026-11-21 – 2026-12-23 | 33 | 13 | 211 | 12421 | 29910 |
| `poznan` | ZTM Poznań | 20261124–20261205 | 2026-11-24 – 2026-12-05 | 12 | 14 | 220 | 3358 | 51150 |
| `trojmiasto_wejherowo` | MZK Wejherowo (M. Kuranowski, mkuran.pl) | 20260901–20261231 | 2026-09-01 – 2026-12-31 | 122 | 1 | 18 | 385 | 2074 |
| `warsaw_czosnow` | Urząd Gminy Czosnów (A. Dubis, feed.gtfs.cc) | 20251214–20271214 | 2025-01-01 – 2029-12-26 | 773 | 1 | 8 | 92 | 65 |
| `warsaw_dabrowka` | Urząd Gminy Dąbrówka via files.girlc.at | 20261115–20261128 | 2026-11-15 – 2026-11-28 | 14 | 1 | 4 | 87 | 452 |
| `warsaw_gpa` | Grodziskie Przewozy Autobusowe (via zbiorkom.live) | 20261123–20271231 | 2026-11-23 – 2027-12-31 | 404 | 1 | 64 | 1781 | 3422 |
| `warsaw_halinow` | Gmina Halinów via files.girlc.at | 20261115–20261128 | 2026-11-16 – 2026-11-27 | 10 | 1 | 6 | 153 | 850 |
| `warsaw_lomianki` | Komunikacja Miejska Łomianki via files.girlc.at | 20261115–20261128 | 2026-11-16 – 2026-11-28 | 12 | 1 | 3 | 82 | 860 |
| `warsaw_minsk` | Miasto Mińsk Mazowiecki (via zbiorkom.live) | 20261122–20261222 | 2026-11-22 – 2026-12-22 | 31 | 1 | 4 | 120 | 236 |
| `warsaw_nowy_dwor` | Nowodworska Komunikacja Autobusowa (UM Nowy Dwór Mazowiecki) via files.girlc.at | 20261115–20261128 | 2026-11-15 – 2026-11-28 | 14 | 1 | 5 | 87 | 792 |
| `warsaw_otwock` | OZEC / BKM Otwock via files.girlc.at | 20261120–20261203 | 2026-11-20 – 2026-12-03 | 14 | 1 | 7 | 91 | 1548 |
| `warsaw_powiat_minski` | PGZTPPM Mińsk Mazowiecki (powiat miński) via files.girlc.at | 20261115–20261128 | 2026-11-15 – 2026-11-28 | 14 | 1 | 16 | 619 | 3566 |
| `warsaw_powiat_nowodworski` | Powiat Nowodworski via files.girlc.at | 20261115–20261128 | 2026-11-15 – 2026-11-28 | 14 | 1 | 3 | 122 | 252 |
| `warsaw_pruszkow` | Miasto Pruszków, PKM (via zbiorkom.live) | 20261123–20271231 | 2026-11-23 – 2027-12-31 | 404 | 1 | 10 | 166 | 794 |
| `warsaw_radzymin` | Urząd Miasta i Gminy Radzymin via files.girlc.at | 20261115–20261128 | 2026-11-15 – 2026-11-28 | 14 | 2 | 11 | 218 | 2688 |
| `warsaw_sulejowek` | UM Sulejówek / Urząd Gminy Wiązowna via files.girlc.at | 20261115–20261128 | 2026-11-16 – 2026-11-27 | 10 | 2 | 3 | 81 | 1000 |
| `warsaw_wieliszew` | Gmina Wieliszew via files.girlc.at | 20261119–20261202 | 2026-11-19 – 2026-12-02 | 14 | 1 | 3 | 142 | 512 |
| `warsaw_wkd` | Warszawska Kolej Dojazdowa (mkuran.pl) | brak | 2025-12-14 – 2026-12-12 | 364 | 1 | 2 | 60 | 3702 |
| `warsaw_zabki` | Miasto Ząbki via files.girlc.at | 20261121–20261204 | 2026-11-21 – 2026-12-04 | 14 | 1 | 5 | 126 | 239 |
| `warsaw_zakroczym` | Komunikacja Gminna Zakroczym (A. Dubis, feed.gtfs.cc) | 20260101–20261231 | 2025-01-01 – 2026-12-31 | 344 | 1 | 3 | 63 | 48 |
| `warsaw_ztm` | ZTM Warszawa (unofficial repackaging by M. Kuranowski, mkuran.pl) | brak | 2026-11-23 – 2026-12-23 | 31 | 1 | 322 | 7280 | 284395 |
| `warsaw_zyrardow` | Żyrardowskie Przewozy Autobusowe (M. Minkowski, GitHub) | 20260915–20271231 | 2026-09-15 – 2027-12-31 | 473 | 1 | 10 | 130 | 286 |
| `wroclaw` | Urząd Miejski Wrocławia, Wydział Transportu (Wrocław Open Data) | 20261123–20261206 | 2026-11-23 – 2026-12-06 | 14 | 6 | 137 | 2493 | 42546 |
| `wroclaw_oborniki` | OLKA Oborniki Śląskie (A. Dubis, feed.gtfs.cc) | 20260107–20271231 | 2025-12-25 – 2027-12-30 | 506 | 1 | 5 | 82 | 24 |
| `wroclaw_olesnica` | Urząd Gminy Oleśnica via files.girlc.at | 20261115–20261128 | 2026-11-16 – 2026-11-27 | 10 | 1 | 9 | 163 | 1190 |
| `wroclaw_polbus` | POLBUS-PKS Sp. z o.o. via files.girlc.at | 20261120–20261203 | 2026-11-20 – 2026-12-03 | 14 | 1 | 21 | 349 | 1536 |

## Trasy wg rodzaju (route_type rozszerzone sprowadzone do klas)

| Feed | tramwaj | metro | kolej | autobus | trolejbus | prom | inne | surowe route_type |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `gdansk` | 10 | 0 | 0 | 83 | 0 | 0 | 0 | 700:83;900:10 |
| `gdynia` | 0 | 0 | 0 | 77 | 16 | 0 | 0 | 700:77;800:16 |
| `gzm` | 28 | 0 | 0 | 456 | 8 | 0 | 0 | 0:28;11:8;3:456 |
| `krakow_ald` | 0 | 0 | 0 | 70 | 0 | 0 | 0 | 3:70 |
| `krakow_bus` | 0 | 0 | 0 | 161 | 0 | 0 | 0 | 3:161 |
| `krakow_mobilis` | 0 | 0 | 0 | 33 | 0 | 0 | 0 | 3:33 |
| `krakow_niepolomice` | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 3:5 |
| `krakow_skawina` | 0 | 0 | 0 | 11 | 0 | 0 | 0 | 3:11 |
| `krakow_tram` | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 900:25 |
| `lodz` | 26 | 0 | 0 | 108 | 0 | 0 | 0 | 0:26;3:108 |
| `lodz_aleksandrow` | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 3:4 |
| `lodz_lka_bus` | 0 | 0 | 0 | 52 | 0 | 0 | 0 | 3:52 |
| `lodz_pabianice` | 0 | 0 | 0 | 14 | 0 | 0 | 0 | 3:14 |
| `lodz_strykow` | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 3:7 |
| `lodz_suburban_qbx` | 0 | 0 | 0 | 20 | 0 | 0 | 0 | 3:20 |
| `lodz_zgierz` | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 3:9 |
| `polish_trains` | 0 | 0 | 164 | 47 | 0 | 0 | 0 | 2:164;3:47 |
| `poznan` | 21 | 0 | 0 | 199 | 0 | 0 | 0 | 0:21;3:199 |
| `trojmiasto_wejherowo` | 0 | 0 | 0 | 18 | 0 | 0 | 0 | 3:18 |
| `warsaw_czosnow` | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 3:8 |
| `warsaw_dabrowka` | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 3:4 |
| `warsaw_gpa` | 0 | 0 | 0 | 64 | 0 | 0 | 0 | 3:64 |
| `warsaw_halinow` | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 3:6 |
| `warsaw_lomianki` | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 3:3 |
| `warsaw_minsk` | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 3:4 |
| `warsaw_nowy_dwor` | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 3:5 |
| `warsaw_otwock` | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 3:7 |
| `warsaw_powiat_minski` | 0 | 0 | 0 | 16 | 0 | 0 | 0 | 3:16 |
| `warsaw_powiat_nowodworski` | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 3:3 |
| `warsaw_pruszkow` | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 3:10 |
| `warsaw_radzymin` | 0 | 0 | 0 | 11 | 0 | 0 | 0 | 3:11 |
| `warsaw_sulejowek` | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 3:3 |
| `warsaw_wieliszew` | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 3:3 |
| `warsaw_wkd` | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 2:1;3:1 |
| `warsaw_zabki` | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 3:5 |
| `warsaw_zakroczym` | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 3:3 |
| `warsaw_ztm` | 26 | 2 | 5 | 289 | 0 | 0 | 0 | 0:26;1:2;2:5;3:289 |
| `warsaw_zyrardow` | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 3:10 |
| `wroclaw` | 25 | 0 | 0 | 112 | 0 | 0 | 0 | 0:25;3:112 |
| `wroclaw_oborniki` | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 3:5 |
| `wroclaw_olesnica` | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 3:9 |
| `wroclaw_polbus` | 0 | 0 | 0 | 21 | 0 | 0 | 0 | 3:21 |

## Kompletność pól

| Feed | shapes.txt | kursy z kształtem % | shape_dist w shapes % | shape_dist w stop_times % | frequencies | parent_station % | direction_id % | block_id % | strefa czasowa |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
| `gdansk` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `gdynia` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `gzm` | tak | 100.0 | 0.0 | 100.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `krakow_ald` | nie | 0.0 |  | 100.0 | nie (0) | 100.0 | 0.0 | 100.0 | Europe/Warsaw |
| `krakow_bus` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `krakow_mobilis` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `krakow_niepolomice` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 32.3 | Europe/Warsaw |
| `krakow_skawina` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `krakow_tram` | tak | 100.0 | 0.0 | 100.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `lodz` | tak | 99.7 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 100.0 | Europe/Warsaw |
| `lodz_aleksandrow` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `lodz_lka_bus` | tak | 0.0 | 0.0 | 0.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `lodz_pabianice` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `lodz_strykow` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `lodz_suburban_qbx` | tak | 0.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `lodz_zgierz` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 7.9 | Europe/Warsaw |
| `polish_trains` | tak | 95.1 | 100.0 | 98.1 | nie (0) | 100.0 | 51.9 | 0.0 | Europe/Warsaw |
| `poznan` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `trojmiasto_wejherowo` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `warsaw_czosnow` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 0.0 | 100.0 | Europe/Warsaw |
| `warsaw_dabrowka` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_gpa` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 3.8 | Europe/Warsaw |
| `warsaw_halinow` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_lomianki` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_minsk` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 9.7 | Europe/Warsaw |
| `warsaw_nowy_dwor` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_otwock` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_powiat_minski` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_powiat_nowodworski` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_pruszkow` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `warsaw_radzymin` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_sulejowek` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_wieliszew` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_wkd` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `warsaw_zabki` | nie | 0.0 |  | 0.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_zakroczym` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `warsaw_ztm` | tak | 100.0 | 100.0 | 100.0 | tak (16) | 0.6 | 100.0 | 100.0 | Europe/Warsaw |
| `warsaw_zyrardow` | tak | 100.0 | 100.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `wroclaw` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 100.0 | 0.0 | Europe/Warsaw |
| `wroclaw_oborniki` | tak | 100.0 | 0.0 | 0.0 | nie (0) | 0.0 | 0.0 | 100.0 | Europe/Warsaw |
| `wroclaw_olesnica` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |
| `wroclaw_polbus` | tak | 100.0 | 100.0 | 100.0 | nie (0) | 0.0 | 0.0 | 0.0 | Europe/Warsaw |

`parent_station %` liczone dla przystanków-słupków (`location_type=0`). `frequencies (n)` = liczba kursów opisanych przez `frequencies.txt`; takie kursy są rozwijane do liczby odjazdów.

## Licencje i pobranie

| Feed | Licencja (wg wydawcy) | Pobrano | URL |
|---|---|---|---|
| `gdansk` | CC BY 4.0 (Creative Commons Attribution) | 2026-11-23T18:19:06+01:00 | https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/30e783e4-2bec-4a7d-bb22-ee3e3b26ca96/download/gtfsgoogle.zip |
| `gdynia` | CC BY 4.0 (Creative Commons Attribution) | 2026-11-23T18:19:08+01:00 | https://api.zdiz.gdynia.pl/pt/gtfs.zip |
| `gzm` | CC BY 4.0 | 2026-11-23T18:19:11+01:00 | https://github.com/TransportGZM-GTFS-mirror/TransportGZM-GTFS-extended-ver/releases/latest/download/TransportGZM-GTFS.zip |
| `krakow_ald` | CC BY 4.0 (per transitous / Atlas catalogues; not checked on the publisher page, which returns 403 to scripts) | 2026-11-23T19:32:14+01:00 | https://kolejemalopolskie.com.pl/rozklady_jazdy/ald-gtfs.zip |
| `krakow_bus` | CC BY 4.0 | 2026-11-23T18:18:57+01:00 | https://gtfs.ztp.krakow.pl/GTFS_KRK_A.zip |
| `krakow_mobilis` | CC BY 4.0 | 2026-11-23T18:36:52+01:00 | https://gtfs.ztp.krakow.pl/GTFS_KRK_M.zip |
| `krakow_niepolomice` | MIT (zbiorkom.live repackaging; operator terms not stated) | 2026-11-23T19:32:17+01:00 | https://api.zbiorkom.live/api6-open/krakow/gtfs/NIEPOLOMICE |
| `krakow_skawina` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:16+01:00 | https://files.girlc.at/gtfs/skawina.zip |
| `krakow_tram` | CC BY 4.0 | 2026-11-23T18:18:58+01:00 | https://gtfs.ztp.krakow.pl/GTFS_KRK_T.zip |
| `lodz` | open licence of the Łódź open-data portal (attribution required; licence name not stated on the dataset page) | 2026-11-23T18:19:04+01:00 | https://otwarte.miasto.lodz.pl/wp-content/uploads/2025/06/GTFS.zip |
| `lodz_aleksandrow` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:20+01:00 | https://files.girlc.at/gtfs/aleksandrow_lodzki.zip |
| `lodz_lka_bus` | CC-BY-4.0 (kasznia.net repackaging per transitous; operator terms not stated) | 2026-11-23T19:32:23+01:00 | https://gtfs.kasznia.net/static/sanitized/lka_bus.zip |
| `lodz_pabianice` | MIT (zbiorkom.live repackaging; operator terms not stated) | 2026-11-23T19:32:18+01:00 | https://api.zbiorkom.live/api6-open/lodz/gtfs/PABIANICE |
| `lodz_strykow` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:22+01:00 | https://files.girlc.at/gtfs/strykow.zip |
| `lodz_suburban_qbx` | no licence stated (Mobility Database mdb-3477 lists none) | 2026-11-23T19:32:25+01:00 | https://raw.githubusercontent.com/qbx-tt/gtfs-lodz-suburban/main/gtfs-lodz-suburban.zip |
| `lodz_zgierz` | MIT (zbiorkom.live repackaging; operator terms not stated) | 2026-11-23T19:32:26+01:00 | https://api.zbiorkom.live/api6-open/lodz/gtfs/ZGIERZ |
| `polish_trains` | PKP PLK public-sector data usage terms + Koleje Mazowieckie public-sector data usage terms | 2026-11-23T18:19:13+01:00 | https://mkuran.pl/gtfs/polish_trains.zip |
| `poznan` | ZTM Poznań terms of use (Zasady korzystania z danych) | 2026-11-23T18:19:02+01:00 | https://www.ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile |
| `trojmiasto_wejherowo` | CC0 1.0 (stated on mkuran.pl/gtfs) | 2026-11-23T19:32:28+01:00 | https://mkuran.pl/gtfs/wejherowo.zip |
| `warsaw_czosnow` | MIT (feed.gtfs.cc catalogue entry; operator terms not stated) | 2026-11-23T19:32:07+01:00 | https://feed.gtfs.cc/czosnow/gtfs.zip |
| `warsaw_dabrowka` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:10+01:00 | https://files.girlc.at/gtfs/dabrowka.zip |
| `warsaw_gpa` | MIT (zbiorkom.live repackaging; operator terms not stated) | 2026-11-23T19:31:45+01:00 | https://api.zbiorkom.live/api6-open/warsaw/gtfs/GPA |
| `warsaw_halinow` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:31:59+01:00 | https://files.girlc.at/gtfs/halinow.zip |
| `warsaw_lomianki` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:31:55+01:00 | https://files.girlc.at/gtfs/lomianki.zip |
| `warsaw_minsk` | MIT (zbiorkom.live repackaging; operator terms not stated) | 2026-11-23T19:31:49+01:00 | https://api.zbiorkom.live/api6-open/warsaw/gtfs/MINSK |
| `warsaw_nowy_dwor` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:02+01:00 | https://files.girlc.at/gtfs/nowy_dwor_mazowiecki.zip |
| `warsaw_otwock` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:31:52+01:00 | https://files.girlc.at/gtfs/otwock.zip |
| `warsaw_powiat_minski` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:31:50+01:00 | https://files.girlc.at/gtfs/powiat_minski.zip |
| `warsaw_powiat_nowodworski` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:03+01:00 | https://files.girlc.at/gtfs/powiat_nowodworski.zip |
| `warsaw_pruszkow` | MIT (zbiorkom.live repackaging; operator terms not stated) | 2026-11-23T19:31:47+01:00 | https://api.zbiorkom.live/api6-open/warsaw/gtfs/PRUSZKOW |
| `warsaw_radzymin` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:31:54+01:00 | https://files.girlc.at/gtfs/radzymin.zip |
| `warsaw_sulejowek` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:05+01:00 | https://files.girlc.at/gtfs/sulejowek.zip |
| `warsaw_wieliszew` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:00+01:00 | https://files.girlc.at/gtfs/wieliszew.zip |
| `warsaw_wkd` | CC0 1.0 | 2026-11-23T18:18:55+01:00 | https://mkuran.pl/gtfs/wkd.zip |
| `warsaw_zabki` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:31:57+01:00 | https://files.girlc.at/gtfs/zabki.zip |
| `warsaw_zakroczym` | MIT (feed.gtfs.cc catalogue entry; operator terms not stated) | 2026-11-23T19:32:08+01:00 | https://feed.gtfs.cc/zakroczym/gtfs.zip |
| `warsaw_ztm` | ZTM Warszawa data usage terms + ODbL for bus shapes (OSM); attribution: ZTM Warszawa, Mikołaj Kuranowski, OpenStreetMap contributors | 2026-11-23T18:18:52+01:00 | https://mkuran.pl/gtfs/warsaw.zip |
| `warsaw_zyrardow` | CC0-1.0 (Mobility Database entry; operator terms not stated) | 2026-11-23T19:32:12+01:00 | https://github.com/minkowskimaciej/zyrardow/raw/main/zyrardow.zip |
| `wroclaw` | CC0 1.0 | 2026-11-23T18:24:42+01:00 | https://open-data.cui.wroclaw.pl/hdb/download/164/ |
| `wroclaw_oborniki` | MIT (feed.gtfs.cc catalogue entry; operator terms not stated) | 2026-11-23T19:32:32+01:00 | https://feed.gtfs.cc/oborniki-slaskie/gtfs.zip |
| `wroclaw_olesnica` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:30+01:00 | https://files.girlc.at/gtfs/olesnica.zip |
| `wroclaw_polbus` | CC0-1.0 (girlc.at repackaging; operator terms not stated) | 2026-11-23T19:32:29+01:00 | https://files.girlc.at/gtfs/polbus.zip |

## Wykryte defekty

- `krakow_bus`: 2 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 117 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `krakow_mobilis`: 2 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 117 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `lodz_strykow`: 4 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 4 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `warsaw_czosnow`: 3 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 0 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `warsaw_halinow`: 4 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 4 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `warsaw_lomianki`: 2 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 2 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `warsaw_sulejowek`: 4 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 4 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
- `wroclaw_olesnica`: 4 service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; przez to 4 dat nie ma żadnych kursów (w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.
