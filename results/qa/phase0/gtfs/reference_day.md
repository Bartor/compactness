# Dzień referencyjny: propozycja i test anomalii (faza 0)

Stan na 2026-11-23. Dane: `service_by_day.csv` (kursy, wozokilometry z długości `shapes` w EPSG:2180, a gdy kurs nie ma kształtu: suma odległości po prostej między kolejnymi przystankami; udział tej metody w `service_by_day.csv`). Wartości w tabelach to **po usunięciu dokładnych duplikatów kursów** (kolumny `*_dedup`; dotyczy `gzm`, patrz niżej).

## Rekomendacja

- **Dzień roboczy ustalony w `config.yaml`: 2026-11-25 (śr)**; sobota: 2026-11-28. Propozycja poniżej NIE zmienia tej decyzji; kursy w tym dniu ma 42/42 feedów (wszystkie). W sobotę bez kursów: `warsaw_halinow`, `warsaw_sulejowek`, `lodz_strykow`, `wroclaw_olesnica`, `wroclaw_oborniki`.
- Wspólne dni wt–czw (poza świętami i 24.12–6.01), tylko informacyjnie: 2026-11-24, 2026-11-25.
- Wspólne soboty, tylko informacyjnie: brak.

Uwaga: ograniczeniem wspólnego dnia jest najkrótsze okno ważności (patrz tabela niżej). Feedy wygasają, a raw zostaje w `data/raw/gtfs/` z datą pobrania i SHA-256; po zmianie feedów dzień trzeba wyznaczyć ponownie (`python -m pipeline.gtfs_inventory reference`).

## Defekty feedów wpływające na wybór dnia

- `gzm`: 15117 kursów (23.18 %) to dokładne duplikaty (to samo `service_id`, linia, kierunek, przystanki i czasy, inne `trip_id`; ten sam `block_id`). Wygląda to na sklejenie kilku dobowych plików ZTM GZM w jeden zip. Wozokilometry i kursy w tabelach to wartości po usunięciu duplikatów (`*_dedup`); surowe wartości są w `service_by_day.csv`.
- `krakow_bus`: 2 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 117 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `krakow_mobilis`: 2 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 117 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `lodz_strykow`: 4 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 4 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `warsaw_czosnow`: 3 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 0 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `warsaw_halinow`: 4 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 4 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `warsaw_lomianki`: 2 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 2 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `warsaw_sulejowek`: 4 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 4 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `wroclaw_olesnica`: 4 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 4 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.

## Kandydaci: dni robocze (wt–czw)

Pierwsze 14 kandydatów (wt–czw, po wyłączeniu świąt i okresu 24.12–6.01; ferie zimowe przypadają w styczniu–lutym, więc nie dotyczą dat z listopada–grudnia).

Liczba kursów (z uwzględnieniem `frequencies.txt`); „–” = dzień poza ważnością feedu.

| Data | dzień | feedy z kursami | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` | `warsaw_gpa` | `warsaw_pruszkow` | `warsaw_minsk` | `warsaw_powiat_minski` | `warsaw_otwock` | `warsaw_radzymin` | `warsaw_lomianki` | `warsaw_zabki` | `warsaw_halinow` | `warsaw_wieliszew` | `warsaw_nowy_dwor` | `warsaw_powiat_nowodworski` | `warsaw_sulejowek` | `warsaw_czosnow` | `warsaw_zakroczym` | `warsaw_dabrowka` | `warsaw_zyrardow` | `krakow_ald` | `krakow_skawina` | `krakow_niepolomice` | `lodz_pabianice` | `lodz_aleksandrow` | `lodz_strykow` | `lodz_lka_bus` | `lodz_suburban_qbx` | `lodz_zgierz` | `trojmiasto_wejherowo` | `wroclaw_polbus` | `wroclaw_olesnica` | `wroclaw_oborniki` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-24 | wt | 42/42 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 911 | 22 868 | 7 455 | 2 142 | 474 | 168 | 325 | 138 | 245 | 84 | 139 | 85 | 48 | 66 | 18 | 100 | 56 | 44 | 42 | 240 | 1 309 | 304 | 131 | 500 | 76 | 43 | 299 | 415 | 299 | 677 | 134 | 119 | 24 |
| 2026-11-25 | śr | 42/42 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 911 | 22 868 | 7 453 | 2 142 | 474 | 168 | 325 | 138 | 245 | 84 | 139 | 85 | 48 | 66 | 18 | 100 | 56 | 44 | 42 | 240 | 1 309 | 304 | 131 | 500 | 76 | 43 | 299 | 415 | 299 | 677 | 136 | 119 | 24 |
| 2026-11-26 | czw | 40/42 | 35 614 | 192 | – | 3 710 | – | 12 849 | 12 074 | 10 229 | 7 049 | 4 911 | 22 868 | 7 459 | 2 142 | 474 | 168 | 325 | 138 | 245 | 84 | 139 | 85 | 48 | 66 | 18 | 100 | 56 | 44 | 42 | 240 | 1 309 | 304 | 131 | 500 | 76 | 43 | 299 | 415 | 299 | 677 | 136 | 119 | 24 |
| 2026-12-01 | wt | 29/42 | 35 507 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 914 | – | 7 423 | 2 142 | 474 | 168 | – | 138 | – | – | 139 | – | 48 | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | 299 | 415 | 299 | 677 | 134 | – | 24 |
| 2026-12-02 | śr | 29/42 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 914 | – | 7 421 | 2 142 | 474 | 168 | – | 138 | – | – | 139 | – | 48 | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | 299 | 415 | 299 | 677 | 136 | – | 24 |
| 2026-12-03 | czw | 26/42 | 35 614 | 192 | – | 3 710 | – | 12 849 | 12 074 | 10 229 | 7 049 | 4 914 | – | 7 424 | 2 142 | 474 | 168 | – | 138 | – | – | 139 | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | 299 | 415 | 299 | 677 | 136 | – | 24 |
| 2026-12-08 | wt | 22/42 | 35 507 | 192 | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 421 | 2 142 | 474 | 168 | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | 299 | 415 | 299 | 677 | – | – | 24 |
| 2026-12-09 | śr | 22/42 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 424 | 2 142 | 474 | 168 | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | 299 | 415 | 299 | 677 | – | – | 24 |
| 2026-12-10 | czw | 20/42 | 35 614 | 192 | – | 3 710 | – | – | – | 10 229 | – | 4 914 | – | 7 389 | 2 142 | 474 | 168 | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | 299 | 415 | 299 | 677 | – | – | 24 |
| 2026-12-15 | wt | 20/42 | 35 507 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 566 | 2 142 | 474 | 168 | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | – | 415 | 299 | 677 | – | – | 24 |
| 2026-12-16 | śr | 20/42 | 35 603 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 564 | 2 142 | 474 | 168 | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | – | 415 | 299 | 677 | – | – | 24 |
| 2026-12-17 | czw | 18/42 | 35 614 | – | – | 3 710 | – | – | – | 10 229 | – | 4 914 | – | 7 570 | 2 142 | 474 | 168 | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | – | 415 | 299 | 677 | – | – | 24 |
| 2026-12-22 | wt | 20/42 | 35 507 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 584 | 2 142 | 474 | 168 | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | 500 | – | – | – | 415 | 299 | 677 | – | – | 24 |
| 2026-12-23 | śr | 17/42 | 35 603 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 587 | 2 048 | 460 | – | – | – | – | – | – | – | – | – | – | – | 56 | 44 | – | 240 | 1 309 | – | 131 | – | – | – | – | 405 | – | 637 | – | – | 24 |

Wozokilometry (tys. km):

| Data | dzień | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` | `warsaw_gpa` | `warsaw_pruszkow` | `warsaw_minsk` | `warsaw_powiat_minski` | `warsaw_otwock` | `warsaw_radzymin` | `warsaw_lomianki` | `warsaw_zabki` | `warsaw_halinow` | `warsaw_wieliszew` | `warsaw_nowy_dwor` | `warsaw_powiat_nowodworski` | `warsaw_sulejowek` | `warsaw_czosnow` | `warsaw_zakroczym` | `warsaw_dabrowka` | `warsaw_zyrardow` | `krakow_ald` | `krakow_skawina` | `krakow_niepolomice` | `lodz_pabianice` | `lodz_aleksandrow` | `lodz_strykow` | `lodz_lka_bus` | `lodz_suburban_qbx` | `lodz_zgierz` | `trojmiasto_wejherowo` | `wroclaw_polbus` | `wroclaw_olesnica` | `wroclaw_oborniki` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-24 | wt | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.0 | 401.9 | 736.3 | 48.7 | 4.5 | 2.0 | 8.2 | 1.8 | 4.1 | 0.7 | 2.4 | 1.0 | 1.0 | 1.2 | 0.4 | 0.7 | 1.0 | 1.2 | 1.2 | 2.5 | 44.8 | 3.2 | 2.3 | 4.6 | 1.3 | 0.9 | 6.5 | 10.6 | 3.6 | 7.6 | 4.4 | 2.1 | 0.8 |
| 2026-11-25 | śr | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.0 | 401.9 | 736.3 | 48.7 | 4.5 | 2.0 | 8.2 | 1.8 | 4.1 | 0.7 | 2.4 | 1.0 | 1.0 | 1.2 | 0.4 | 0.7 | 1.0 | 1.2 | 1.2 | 2.5 | 44.8 | 3.2 | 2.3 | 4.6 | 1.3 | 0.9 | 6.5 | 10.6 | 3.6 | 7.6 | 4.3 | 2.1 | 0.8 |
| 2026-11-26 | czw | 515.4 | 6.0 | – | 54.3 | – | 170.0 | 150.8 | 146.5 | 85.2 | 63.0 | 401.9 | 736.3 | 48.7 | 4.5 | 2.0 | 8.2 | 1.8 | 4.1 | 0.7 | 2.4 | 1.0 | 1.0 | 1.2 | 0.4 | 0.7 | 1.0 | 1.2 | 1.2 | 2.5 | 44.8 | 3.2 | 2.3 | 4.6 | 1.3 | 0.9 | 6.5 | 10.6 | 3.6 | 7.6 | 4.3 | 2.1 | 0.8 |
| 2026-12-01 | wt | 514.7 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.1 | – | 736.3 | 48.7 | 4.5 | 2.0 | – | 1.8 | – | – | 2.4 | – | 1.0 | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | 6.5 | 10.6 | 3.6 | 7.6 | 4.4 | – | 0.8 |
| 2026-12-02 | śr | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.1 | – | 736.2 | 48.7 | 4.5 | 2.0 | – | 1.8 | – | – | 2.4 | – | 1.0 | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | 6.5 | 10.6 | 3.6 | 7.6 | 4.3 | – | 0.8 |
| 2026-12-03 | czw | 515.4 | 6.0 | – | 54.3 | – | 170.0 | 150.8 | 146.5 | 85.2 | 63.1 | – | 736.2 | 48.7 | 4.5 | 2.0 | – | 1.8 | – | – | 2.4 | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | 6.5 | 10.6 | 3.6 | 7.6 | 4.3 | – | 0.8 |
| 2026-12-08 | wt | 514.7 | 6.0 | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 736.3 | 48.7 | 4.5 | 2.0 | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | 6.5 | 10.6 | 3.6 | 7.6 | – | – | 0.8 |
| 2026-12-09 | śr | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 736.3 | 48.7 | 4.5 | 2.0 | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | 6.5 | 10.6 | 3.6 | 7.6 | – | – | 0.8 |
| 2026-12-10 | czw | 515.4 | 6.0 | – | 54.3 | – | – | – | 146.5 | – | 63.1 | – | 736.0 | 48.7 | 4.5 | 2.0 | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | 6.5 | 10.6 | 3.6 | 7.6 | – | – | 0.8 |
| 2026-12-15 | wt | 514.7 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 776.8 | 48.7 | 4.5 | 2.0 | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | – | 10.6 | 3.6 | 7.6 | – | – | 0.8 |
| 2026-12-16 | śr | 515.3 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 776.7 | 48.7 | 4.5 | 2.0 | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | – | 10.6 | 3.6 | 7.6 | – | – | 0.8 |
| 2026-12-17 | czw | 515.4 | – | – | 54.3 | – | – | – | 146.5 | – | 63.1 | – | 777.6 | 48.7 | 4.5 | 2.0 | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | – | 10.6 | 3.6 | 7.6 | – | – | 0.8 |
| 2026-12-22 | wt | 514.7 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 778.8 | 48.7 | 4.5 | 2.0 | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | 4.6 | – | – | – | 10.6 | 3.6 | 7.6 | – | – | 0.8 |
| 2026-12-23 | śr | 515.3 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 778.7 | 47.4 | 4.4 | – | – | – | – | – | – | – | – | – | – | – | 1.0 | 1.2 | – | 2.5 | 44.8 | – | 2.3 | – | – | – | – | 10.5 | – | 7.1 | – | – | 0.8 |

## Kandydaci: soboty

Soboty bez świąt i bez okresu 24.12–6.01.

Liczba kursów (z uwzględnieniem `frequencies.txt`); „–” = dzień poza ważnością feedu.

| Data | dzień | feedy z kursami | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` | `warsaw_gpa` | `warsaw_pruszkow` | `warsaw_minsk` | `warsaw_powiat_minski` | `warsaw_otwock` | `warsaw_radzymin` | `warsaw_lomianki` | `warsaw_zabki` | `warsaw_halinow` | `warsaw_wieliszew` | `warsaw_nowy_dwor` | `warsaw_powiat_nowodworski` | `warsaw_sulejowek` | `warsaw_czosnow` | `warsaw_zakroczym` | `warsaw_dabrowka` | `warsaw_zyrardow` | `krakow_ald` | `krakow_skawina` | `krakow_niepolomice` | `lodz_pabianice` | `lodz_aleksandrow` | `lodz_strykow` | `lodz_lka_bus` | `lodz_suburban_qbx` | `lodz_zgierz` | `trojmiasto_wejherowo` | `wroclaw_polbus` | `wroclaw_olesnica` | `wroclaw_oborniki` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-28 | sob | 37/42 | 23 116 | 123 | 6 140 | 2 221 | 1 791 | 8 578 | 7 988 | 7 329 | 4 687 | 3 033 | 13 734 | 5 793 | 1 132 | 235 | 57 | 79 | 48 | 75 | 10 | 65 | – | 8 | 33 | 18 | – | 7 | 8 | 8 | 117 | 698 | 151 | 74 | 259 | 22 | – | 250 | 172 | 185 | 425 | 46 | – | – |
| 2026-12-05 | sob | 24/42 | 23 116 | 123 | 6 140 | 2 221 | 1 791 | 8 578 | 7 988 | 7 329 | 4 687 | 3 033 | – | 5 839 | 1 132 | 235 | 57 | – | – | – | – | – | – | – | – | – | – | 7 | 8 | – | 117 | 698 | – | 74 | 259 | – | – | 250 | 172 | 185 | 425 | – | – | – |
| 2026-12-12 | sob | 21/42 | 23 116 | 123 | 6 140 | 2 221 | 1 791 | – | – | 7 329 | – | 3 033 | – | 5 781 | 1 132 | 235 | 57 | – | – | – | – | – | – | – | – | – | – | 7 | 8 | – | 117 | 698 | – | 74 | 259 | – | – | 250 | 172 | 185 | 425 | – | – | – |
| 2026-12-19 | sob | 19/42 | 23 116 | – | 6 140 | 2 221 | 1 791 | – | – | 7 329 | – | 3 033 | – | 6 041 | 1 132 | 235 | 57 | – | – | – | – | – | – | – | – | – | – | 7 | 8 | – | 117 | 698 | – | 74 | 259 | – | – | – | 172 | 185 | 425 | – | – | – |
| 2027-01-09 | sob | 10/42 | – | – | 6 140 | 2 221 | 1 791 | – | – | – | – | 3 033 | – | – | 1 138 | 235 | – | – | – | – | – | – | – | – | – | – | – | 7 | – | – | 117 | 698 | – | – | – | – | – | – | 172 | – | – | – | – | – |
| 2027-01-16 | sob | 10/42 | – | – | 6 140 | 2 221 | 1 791 | – | – | – | – | 3 033 | – | – | 1 138 | 235 | – | – | – | – | – | – | – | – | – | – | – | 7 | – | – | 117 | 698 | – | – | – | – | – | – | 172 | – | – | – | – | – |

Wozokilometry (tys. km):

| Data | dzień | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` | `warsaw_gpa` | `warsaw_pruszkow` | `warsaw_minsk` | `warsaw_powiat_minski` | `warsaw_otwock` | `warsaw_radzymin` | `warsaw_lomianki` | `warsaw_zabki` | `warsaw_halinow` | `warsaw_wieliszew` | `warsaw_nowy_dwor` | `warsaw_powiat_nowodworski` | `warsaw_sulejowek` | `warsaw_czosnow` | `warsaw_zakroczym` | `warsaw_dabrowka` | `warsaw_zyrardow` | `krakow_ald` | `krakow_skawina` | `krakow_niepolomice` | `lodz_pabianice` | `lodz_aleksandrow` | `lodz_strykow` | `lodz_lka_bus` | `lodz_suburban_qbx` | `lodz_zgierz` | `trojmiasto_wejherowo` | `wroclaw_polbus` | `wroclaw_olesnica` | `wroclaw_oborniki` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-28 | sob | 338.6 | 3.8 | 78.1 | 33.7 | 20.2 | 115.6 | 97.9 | 101.8 | 59.4 | 40.6 | 240.7 | 650.5 | 25.1 | 2.5 | 0.7 | 2.2 | 0.4 | 1.1 | 0.1 | 0.9 | – | 0.2 | 0.4 | 0.4 | – | 0.2 | 0.3 | 0.2 | 1.3 | 24.7 | 1.6 | 1.3 | 2.4 | 0.4 | – | 5.5 | 4.5 | 2.2 | 4.8 | 1.6 | – | – |
| 2026-12-05 | sob | 338.6 | 3.8 | 78.1 | 33.7 | 20.2 | 115.6 | 97.9 | 101.8 | 59.4 | 40.6 | – | 650.1 | 25.1 | 2.5 | 0.7 | – | – | – | – | – | – | – | – | – | – | 0.2 | 0.3 | – | 1.3 | 24.7 | – | 1.3 | 2.4 | – | – | 5.5 | 4.5 | 2.2 | 4.8 | – | – | – |
| 2026-12-12 | sob | 338.6 | 3.8 | 78.1 | 33.7 | 20.2 | – | – | 101.8 | – | 40.6 | – | 639.9 | 25.1 | 2.5 | 0.7 | – | – | – | – | – | – | – | – | – | – | 0.2 | 0.3 | – | 1.3 | 24.7 | – | 1.3 | 2.4 | – | – | 5.5 | 4.5 | 2.2 | 4.8 | – | – | – |
| 2026-12-19 | sob | 338.6 | – | 78.1 | 33.7 | 20.2 | – | – | 101.8 | – | 40.6 | – | 691.6 | 25.1 | 2.5 | 0.7 | – | – | – | – | – | – | – | – | – | – | 0.2 | 0.3 | – | 1.3 | 24.7 | – | 1.3 | 2.4 | – | – | – | 4.5 | 2.2 | 4.8 | – | – | – |
| 2027-01-09 | sob | – | – | 78.1 | 33.7 | 20.2 | – | – | – | – | 40.6 | – | – | 25.2 | 2.5 | – | – | – | – | – | – | – | – | – | – | – | 0.2 | – | – | 1.3 | 24.7 | – | – | – | – | – | – | 4.5 | – | – | – | – | – |
| 2027-01-16 | sob | – | – | 78.1 | 33.7 | 20.2 | – | – | – | – | 40.6 | – | – | 25.2 | 2.5 | – | – | – | – | – | – | – | – | – | – | – | 0.2 | – | – | 1.3 | 24.7 | – | – | – | – | – | – | 4.5 | – | – | – | – | – |

## Ważność feedów

| Feed | pierwszy dzień | ostatni dzień | dni roboczych (pn–pt, bez świąt) w ważności |
|---|---|---|---:|
| `warsaw_ztm` | 2026-11-23 | 2026-12-23 | 23 |
| `warsaw_wkd` | 2025-12-14 | 2026-12-12 | 251 |
| `krakow_bus` | 2026-11-14 | 2028-01-31 | 188 |
| `krakow_tram` | 2026-11-21 | 2027-02-19 | 61 |
| `krakow_mobilis` | 2026-11-18 | 2028-01-31 | 186 |
| `wroclaw` | 2026-11-23 | 2026-12-06 | 10 |
| `poznan` | 2026-11-24 | 2026-12-05 | 9 |
| `lodz` | 2026-11-22 | 2026-12-31 | 27 |
| `gdansk` | 2026-11-23 | 2026-12-07 | 11 |
| `gdynia` | 2026-11-23 | 2027-01-29 | 46 |
| `gzm` | 2026-11-08 | 2026-11-28 | 14 |
| `polish_trains` | 2026-11-21 | 2026-12-23 | 23 |
| `warsaw_gpa` | 2026-11-23 | 2027-12-31 | 280 |
| `warsaw_pruszkow` | 2026-11-23 | 2027-12-31 | 280 |
| `warsaw_minsk` | 2026-11-22 | 2026-12-22 | 22 |
| `warsaw_powiat_minski` | 2026-11-15 | 2026-11-28 | 10 |
| `warsaw_otwock` | 2026-11-20 | 2026-12-03 | 10 |
| `warsaw_radzymin` | 2026-11-15 | 2026-11-28 | 10 |
| `warsaw_lomianki` | 2026-11-16 | 2026-11-28 | 10 |
| `warsaw_zabki` | 2026-11-21 | 2026-12-04 | 10 |
| `warsaw_halinow` | 2026-11-16 | 2026-11-27 | 10 |
| `warsaw_wieliszew` | 2026-11-19 | 2026-12-02 | 10 |
| `warsaw_nowy_dwor` | 2026-11-15 | 2026-11-28 | 10 |
| `warsaw_powiat_nowodworski` | 2026-11-15 | 2026-11-28 | 10 |
| `warsaw_sulejowek` | 2026-11-16 | 2026-11-27 | 10 |
| `warsaw_czosnow` | 2025-01-01 | 2029-12-26 | 504 |
| `warsaw_zakroczym` | 2025-01-01 | 2026-12-31 | 233 |
| `warsaw_dabrowka` | 2026-11-15 | 2026-11-28 | 10 |
| `warsaw_zyrardow` | 2026-09-15 | 2027-12-31 | 328 |
| `krakow_ald` | 2026-11-23 | 2027-12-31 | 279 |
| `krakow_skawina` | 2026-11-15 | 2026-11-28 | 10 |
| `krakow_niepolomice` | 2026-11-23 | 2026-12-24 | 23 |
| `lodz_pabianice` | 2026-11-23 | 2026-12-22 | 22 |
| `lodz_aleksandrow` | 2026-11-15 | 2026-11-28 | 10 |
| `lodz_strykow` | 2026-11-16 | 2026-11-27 | 10 |
| `lodz_lka_bus` | 2026-03-08 | 2026-12-12 | 196 |
| `lodz_suburban_qbx` | 2026-11-15 | 2027-12-31 | 285 |
| `lodz_zgierz` | 2026-11-23 | 2026-12-22 | 22 |
| `trojmiasto_wejherowo` | 2026-09-01 | 2026-12-31 | 85 |
| `wroclaw_polbus` | 2026-11-20 | 2026-12-03 | 10 |
| `wroclaw_olesnica` | 2026-11-16 | 2026-11-27 | 10 |
| `wroclaw_oborniki` | 2025-12-25 | 2027-12-30 | 504 |

## Test anomalii: dzień roboczy 2026-11-25

Wozokilometry w dniu referencyjnym vs mediana wozokilometrów (dni robocze pn–pt bez świąt) w okresie ważności feedu; odchylenie > 5 % jest oznaczone i wyjaśnione.

| Feed | km w dniu ref. | mediana km | n dni w medianie | min–max w oknie | odchylenie | flaga | wyjaśnienie |
|---|---:|---:|---:|---|---:|---|---|
| `warsaw_ztm` | 515 300 | 515 400 | 23 | 514 700–516 200 | -0.0 % | nie |  |
| `warsaw_wkd` | 5 970 | 5 970 | 251 | 2 837–6 049 | +0.0 % | nie |  |
| `krakow_bus` | 132 000 | 132 000 | 188 | 132 000–132 300 | +0.0 % | nie |  |
| `krakow_tram` | 54 270 | 54 270 | 61 | 54 270–54 940 | +0.0 % | nie |  |
| `krakow_mobilis` | 29 920 | 29 920 | 186 | 29 920–29 960 | +0.0 % | nie |  |
| `wroclaw` | 170 000 | 170 000 | 10 | 170 000–170 100 | +0.0 % | nie |  |
| `poznan` | 150 800 | 150 800 | 9 | 150 500–151 000 | +0.0 % | nie |  |
| `lodz` | 146 500 | 146 500 | 27 | 146 500–146 500 | +0.0 % | nie |  |
| `gdansk` | 85 160 | 85 160 | 11 | 85 090–85 160 | +0.0 % | nie |  |
| `gdynia` | 63 030 | 63 060 | 46 | 63 030–63 060 | -0.0 % | nie |  |
| `gzm` | 401 900 | 401 900 | 14 | 401 900–401 900 | +0.0 % | nie |  |
| `polish_trains` | 736 300 | 737 500 | 23 | 736 000–780 800 | -0.2 % | nie |  |
| `warsaw_gpa` | 48 730 | 48 730 | 280 | 47 350–48 730 | +0.0 % | nie |  |
| `warsaw_pruszkow` | 4 474 | 4 474 | 280 | 4 370–4 474 | +0.0 % | nie |  |
| `warsaw_minsk` | 1 984 | 1 984 | 22 | 1 984–1 984 | +0.0 % | nie |  |
| `warsaw_powiat_minski` | 8 153 | 8 153 | 10 | 8 153–8 153 | +0.0 % | nie |  |
| `warsaw_otwock` | 1 827 | 1 827 | 10 | 1 827–1 827 | +0.0 % | nie |  |
| `warsaw_radzymin` | 4 112 | 4 112 | 10 | 4 112–4 112 | +0.0 % | nie |  |
| `warsaw_lomianki` | 729 | 729 | 10 | 729–729 | +0.0 % | nie |  |
| `warsaw_zabki` | 2 364 | 2 364 | 10 | 2 364–2 381 | +0.0 % | nie |  |
| `warsaw_halinow` | 978 | 978 | 10 | 978–978 | +0.0 % | nie |  |
| `warsaw_wieliszew` | 986 | 986 | 10 | 986–986 | +0.0 % | nie |  |
| `warsaw_nowy_dwor` | 1 243 | 1 243 | 10 | 1 243–1 243 | +0.0 % | nie |  |
| `warsaw_powiat_nowodworski` | 411 | 411 | 10 | 411–411 | +0.0 % | nie |  |
| `warsaw_sulejowek` | 698 | 698 | 10 | 698–698 | +0.0 % | nie |  |
| `warsaw_czosnow` | 1 011 | 1 011 | 504 | 1 011–1 011 | +0.0 % | nie |  |
| `warsaw_zakroczym` | 1 221 | 1 221 | 233 | 270–1 221 | +0.0 % | nie |  |
| `warsaw_dabrowka` | 1 159 | 1 159 | 10 | 1 159–1 159 | +0.0 % | nie |  |
| `warsaw_zyrardow` | 2 472 | 2 472 | 328 | 2 472–2 472 | +0.0 % | nie |  |
| `krakow_ald` | 44 820 | 44 820 | 279 | 44 820–44 820 | +0.0 % | nie |  |
| `krakow_skawina` | 3 174 | 3 174 | 10 | 3 174–3 174 | +0.0 % | nie |  |
| `krakow_niepolomice` | 2 286 | 2 286 | 23 | 2 286–2 286 | +0.0 % | nie |  |
| `lodz_pabianice` | 4 616 | 4 616 | 22 | 4 616–4 616 | +0.0 % | nie |  |
| `lodz_aleksandrow` | 1 289 | 1 289 | 10 | 1 289–1 289 | +0.0 % | nie |  |
| `lodz_strykow` | 930 | 930 | 10 | 930–930 | +0.0 % | nie |  |
| `lodz_lka_bus` | 6 490 | 6 378 | 196 | 5 877–6 788 | +1.7 % | nie |  |
| `lodz_suburban_qbx` | 10 580 | 10 580 | 285 | 9 410–10 580 | +0.0 % | nie |  |
| `lodz_zgierz` | 3 597 | 3 597 | 22 | 3 597–3 597 | +0.0 % | nie |  |
| `trojmiasto_wejherowo` | 7 581 | 7 581 | 85 | 7 092–7 581 | +0.0 % | nie |  |
| `wroclaw_polbus` | 4 329 | 4 329 | 10 | 4 329–4 366 | +0.0 % | nie |  |
| `wroclaw_olesnica` | 2 093 | 2 093 | 10 | 2 093–2 093 | +0.0 % | nie |  |
| `wroclaw_oborniki` | 753 | 753 | 504 | 753–753 | +0.0 % | nie |  |

## Test anomalii: sobota 2026-11-28

Wozokilometry w dniu referencyjnym vs mediana wozokilometrów (soboty bez świąt) w okresie ważności feedu; odchylenie > 5 % jest oznaczone i wyjaśnione.

| Feed | km w dniu ref. | mediana km | n dni w medianie | min–max w oknie | odchylenie | flaga | wyjaśnienie |
|---|---:|---:|---:|---|---:|---|---|
| `warsaw_ztm` | 338 600 | 338 600 | 4 | 338 600–338 600 | +0.0 % | nie |  |
| `warsaw_wkd` | 3 763 | 3 763 | 51 | 1 166–3 795 | +0.0 % | nie |  |
| `krakow_bus` | 78 080 | 78 080 | 60 | 78 080–78 130 | +0.0 % | nie |  |
| `krakow_tram` | 33 680 | 33 680 | 12 | 33 680–33 680 | +0.0 % | nie |  |
| `krakow_mobilis` | 20 180 | 20 180 | 59 | 20 180–20 180 | +0.0 % | nie |  |
| `wroclaw` | 115 600 | 115 600 | 2 | 115 600–115 600 | +0.0 % | nie |  |
| `poznan` | 97 850 | 97 850 | 2 | 97 850–97 850 | +0.0 % | nie |  |
| `lodz` | 101 800 | 101 800 | 4 | 101 800–101 800 | +0.0 % | nie |  |
| `gdansk` | 59 440 | 59 440 | 2 | 59 440–59 440 | +0.0 % | nie |  |
| `gdynia` | 40 580 | 40 580 | 8 | 40 580–40 580 | +0.0 % | nie |  |
| `gzm` | 240 700 | 240 700 | 3 | 240 700–240 700 | +0.0 % | nie |  |
| `polish_trains` | 650 500 | 650 100 | 5 | 12 660–691 600 | +0.1 % | nie |  |
| `warsaw_gpa` | 25 070 | 25 230 | 54 | 25 070–25 230 | -0.6 % | nie |  |
| `warsaw_pruszkow` | 2 465 | 2 465 | 54 | 1 665–2 465 | +0.0 % | nie |  |
| `warsaw_minsk` | 668 | 668 | 4 | 668–668 | +0.0 % | nie |  |
| `warsaw_powiat_minski` | 2 237 | 2 237 | 2 | 2 237–2 237 | +0.0 % | nie |  |
| `warsaw_otwock` | 365 | 365 | 2 | 365–365 | +0.0 % | nie |  |
| `warsaw_radzymin` | 1 137 | 1 137 | 2 | 1 137–1 137 | +0.0 % | nie |  |
| `warsaw_lomianki` | 134 | 134 | 2 | 134–134 | +0.0 % | nie |  |
| `warsaw_zabki` | 950 | 950 | 2 | 950–950 | +0.0 % | nie |  |
| `warsaw_halinow` | nan | nan | 0 | – | +nan % | nie |  |
| `warsaw_wieliszew` | 180 | 180 | 2 | 180–180 | +0.0 % | nie |  |
| `warsaw_nowy_dwor` | 447 | 447 | 2 | 447–447 | +0.0 % | nie |  |
| `warsaw_powiat_nowodworski` | 411 | 411 | 2 | 411–411 | +0.0 % | nie |  |
| `warsaw_sulejowek` | nan | nan | 0 | – | +nan % | nie |  |
| `warsaw_czosnow` | 218 | 218 | 101 | 218–218 | +0.0 % | nie |  |
| `warsaw_zakroczym` | 270 | 270 | 45 | 270–270 | +0.0 % | nie |  |
| `warsaw_dabrowka` | 235 | 235 | 2 | 235–235 | +0.0 % | nie |  |
| `warsaw_zyrardow` | 1 285 | 1 285 | 64 | 1 285–1 285 | +0.0 % | nie |  |
| `krakow_ald` | 24 650 | 24 650 | 54 | 24 650–24 650 | +0.0 % | nie |  |
| `krakow_skawina` | 1 569 | 1 569 | 2 | 1 569–1 569 | +0.0 % | nie |  |
| `krakow_niepolomice` | 1 348 | 1 348 | 4 | 1 348–1 348 | +0.0 % | nie |  |
| `lodz_pabianice` | 2 411 | 2 411 | 4 | 2 411–2 411 | +0.0 % | nie |  |
| `lodz_aleksandrow` | 360 | 360 | 2 | 360–360 | +0.0 % | nie |  |
| `lodz_strykow` | nan | nan | 0 | – | +nan % | nie |  |
| `lodz_lka_bus` | 5 506 | 5 506 | 39 | 4 646–6 296 | +0.0 % | nie |  |
| `lodz_suburban_qbx` | 4 522 | 4 522 | 55 | 4 522–4 522 | +0.0 % | nie |  |
| `lodz_zgierz` | 2 187 | 2 187 | 4 | 2 187–2 187 | +0.0 % | nie |  |
| `trojmiasto_wejherowo` | 4 768 | 4 768 | 16 | 4 768–4 768 | +0.0 % | nie |  |
| `wroclaw_polbus` | 1 643 | 1 643 | 2 | 1 643–1 643 | +0.0 % | nie |  |
| `wroclaw_olesnica` | nan | nan | 0 | – | +nan % | nie |  |
| `wroclaw_oborniki` | nan | nan | 0 | – | +nan % | nie |  |

## Metoda i ograniczenia

- Święta: 1.01, 6.01, Wielkanoc i poniedziałek, 1.05, 3.05, Zielone Świątki, Boże Ciało, 15.08, 1.11, 11.11, 24.12 (od 2025 r.), 25.12, 26.12.
- Mediana dla feedów o długiej ważności (Kraków, WKD, rozkład kolejowy) obejmuje okresy wakacyjne i feryjne, więc jest tylko przybliżeniem „typowego dnia”; dla feedów 2–3-tygodniowych mediana pochodzi z tego samego okna co dzień referencyjny.
- Test nie wykrywa, że cały feed jest „feryjny” lub objazdowy w całym oknie: do tego potrzebne jest porównanie z poprzednim rozkładem (archiwum `data/raw/gtfs/`).

