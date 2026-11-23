# Dzień referencyjny: propozycja i test anomalii (faza 0)

Stan na 2026-11-23. Dane: `service_by_day.csv` (kursy, wozokilometry z długości `shapes` w EPSG:2180, a gdy kurs nie ma kształtu: suma odległości po prostej między kolejnymi przystankami; udział tej metody w `service_by_day.csv`). Wartości w tabelach to **po usunięciu dokładnych duplikatów kursów** (kolumny `*_dedup`; dotyczy `gzm`, patrz niżej).

## Rekomendacja

- **Dzień roboczy (wt–czw): 2026-11-25 (śr)**: jeden wspólny dzień dla wszystkich 12 feedów (każdy ma tego dnia kursy). Kandydat wybrany spośród wspólnych dni wt–czw o najmniejszym średnim odchyleniu wozokilometrów od mediany dni roboczych w ważności feedu (remis: środa).
- **Sobota: 2026-11-28** (wspólna dla wszystkich feedów).
- Wspólne dni wt–czw (poza świętami i 24.12–6.01): 2026-11-24, 2026-11-25.
- Wspólne soboty: 2026-11-28.

Uwaga: ograniczeniem wspólnego dnia jest najkrótsze okno ważności (patrz tabela niżej). Feedy wygasają, a raw zostaje w `data/raw/gtfs/` z datą pobrania i SHA-256; po zmianie feedów dzień trzeba wyznaczyć ponownie (`python -m pipeline.gtfs_inventory reference`).

## Defekty feedów wpływające na wybór dnia

- `gzm`: 15117 kursów (23.18 %) to dokładne duplikaty (to samo `service_id`, linia, kierunek, przystanki i czasy, inne `trip_id`; ten sam `block_id`). Wygląda to na sklejenie kilku dobowych plików ZTM GZM w jeden zip. Wozokilometry i kursy w tabelach to wartości po usunięciu duplikatów (`*_dedup`); surowe wartości są w `service_by_day.csv`.
- `krakow_bus`: 2 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 117 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.
- `krakow_mobilis`: 2 `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc 117 dat (czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.

## Kandydaci: dni robocze (wt–czw)

Pierwsze 14 kandydatów (wt–czw, po wyłączeniu świąt i okresu 24.12–6.01; ferie zimowe przypadają w styczniu–lutym, więc nie dotyczą dat z listopada–grudnia).

Liczba kursów (z uwzględnieniem `frequencies.txt`); „–” = dzień poza ważnością feedu.

| Data | dzień | feedy z kursami | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-24 | wt | 12/12 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 911 | 22 868 | 7 455 |
| 2026-11-25 | śr | 12/12 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 911 | 22 868 | 7 453 |
| 2026-11-26 | czw | 10/12 | 35 614 | 192 | – | 3 710 | – | 12 849 | 12 074 | 10 229 | 7 049 | 4 911 | 22 868 | 7 459 |
| 2026-12-01 | wt | 11/12 | 35 507 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 914 | – | 7 423 |
| 2026-12-02 | śr | 11/12 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | 12 849 | 12 074 | 10 229 | 7 049 | 4 914 | – | 7 421 |
| 2026-12-03 | czw | 9/12 | 35 614 | 192 | – | 3 710 | – | 12 849 | 12 074 | 10 229 | 7 049 | 4 914 | – | 7 424 |
| 2026-12-08 | wt | 8/12 | 35 507 | 192 | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 421 |
| 2026-12-09 | śr | 8/12 | 35 603 | 192 | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 424 |
| 2026-12-10 | czw | 6/12 | 35 614 | 192 | – | 3 710 | – | – | – | 10 229 | – | 4 914 | – | 7 389 |
| 2026-12-15 | wt | 7/12 | 35 507 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 566 |
| 2026-12-16 | śr | 7/12 | 35 603 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 564 |
| 2026-12-17 | czw | 5/12 | 35 614 | – | – | 3 710 | – | – | – | 10 229 | – | 4 914 | – | 7 570 |
| 2026-12-22 | wt | 7/12 | 35 507 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 584 |
| 2026-12-23 | śr | 7/12 | 35 603 | – | 10 280 | 3 710 | 2 590 | – | – | 10 229 | – | 4 914 | – | 7 587 |

Wozokilometry (tys. km):

| Data | dzień | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-24 | wt | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.0 | 401.9 | 736.3 |
| 2026-11-25 | śr | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.0 | 401.9 | 736.3 |
| 2026-11-26 | czw | 515.4 | 6.0 | – | 54.3 | – | 170.0 | 150.8 | 146.5 | 85.2 | 63.0 | 401.9 | 736.3 |
| 2026-12-01 | wt | 514.7 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.1 | – | 736.3 |
| 2026-12-02 | śr | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | 170.0 | 150.8 | 146.5 | 85.2 | 63.1 | – | 736.2 |
| 2026-12-03 | czw | 515.4 | 6.0 | – | 54.3 | – | 170.0 | 150.8 | 146.5 | 85.2 | 63.1 | – | 736.2 |
| 2026-12-08 | wt | 514.7 | 6.0 | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 736.3 |
| 2026-12-09 | śr | 515.3 | 6.0 | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 736.3 |
| 2026-12-10 | czw | 515.4 | 6.0 | – | 54.3 | – | – | – | 146.5 | – | 63.1 | – | 736.0 |
| 2026-12-15 | wt | 514.7 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 776.8 |
| 2026-12-16 | śr | 515.3 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 776.7 |
| 2026-12-17 | czw | 515.4 | – | – | 54.3 | – | – | – | 146.5 | – | 63.1 | – | 777.6 |
| 2026-12-22 | wt | 514.7 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 778.8 |
| 2026-12-23 | śr | 515.3 | – | 132.0 | 54.3 | 29.9 | – | – | 146.5 | – | 63.1 | – | 778.7 |

## Kandydaci: soboty

Soboty bez świąt i bez okresu 24.12–6.01.

Liczba kursów (z uwzględnieniem `frequencies.txt`); „–” = dzień poza ważnością feedu.

| Data | dzień | feedy z kursami | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-28 | sob | 12/12 | 23 116 | 123 | 6 140 | 2 221 | 1 791 | 8 578 | 7 988 | 7 329 | 4 687 | 3 033 | 13 734 | 5 793 |
| 2026-12-05 | sob | 11/12 | 23 116 | 123 | 6 140 | 2 221 | 1 791 | 8 578 | 7 988 | 7 329 | 4 687 | 3 033 | – | 5 839 |
| 2026-12-12 | sob | 8/12 | 23 116 | 123 | 6 140 | 2 221 | 1 791 | – | – | 7 329 | – | 3 033 | – | 5 781 |
| 2026-12-19 | sob | 7/12 | 23 116 | – | 6 140 | 2 221 | 1 791 | – | – | 7 329 | – | 3 033 | – | 6 041 |
| 2027-01-09 | sob | 4/12 | – | – | 6 140 | 2 221 | 1 791 | – | – | – | – | 3 033 | – | – |
| 2027-01-16 | sob | 4/12 | – | – | 6 140 | 2 221 | 1 791 | – | – | – | – | 3 033 | – | – |

Wozokilometry (tys. km):

| Data | dzień | `warsaw_ztm` | `warsaw_wkd` | `krakow_bus` | `krakow_tram` | `krakow_mobilis` | `wroclaw` | `poznan` | `lodz` | `gdansk` | `gdynia` | `gzm` | `polish_trains` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-28 | sob | 338.6 | 3.8 | 78.1 | 33.7 | 20.2 | 115.6 | 97.9 | 101.8 | 59.4 | 40.6 | 240.7 | 650.5 |
| 2026-12-05 | sob | 338.6 | 3.8 | 78.1 | 33.7 | 20.2 | 115.6 | 97.9 | 101.8 | 59.4 | 40.6 | – | 650.1 |
| 2026-12-12 | sob | 338.6 | 3.8 | 78.1 | 33.7 | 20.2 | – | – | 101.8 | – | 40.6 | – | 639.9 |
| 2026-12-19 | sob | 338.6 | – | 78.1 | 33.7 | 20.2 | – | – | 101.8 | – | 40.6 | – | 691.6 |
| 2027-01-09 | sob | – | – | 78.1 | 33.7 | 20.2 | – | – | – | – | 40.6 | – | – |
| 2027-01-16 | sob | – | – | 78.1 | 33.7 | 20.2 | – | – | – | – | 40.6 | – | – |

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

## Metoda i ograniczenia

- Święta: 1.01, 6.01, Wielkanoc i poniedziałek, 1.05, 3.05, Zielone Świątki, Boże Ciało, 15.08, 1.11, 11.11, 24.12 (od 2025 r.), 25.12, 26.12.
- Mediana dla feedów o długiej ważności (Kraków, WKD, rozkład kolejowy) obejmuje okresy wakacyjne i feryjne, więc jest tylko przybliżeniem „typowego dnia”; dla feedów 2–3-tygodniowych mediana pochodzi z tego samego okna co dzień referencyjny.
- Test nie wykrywa, że cały feed jest „feryjny” lub objazdowy w całym oknie: do tego potrzebne jest porównanie z poprzednim rozkładem (archiwum `data/raw/gtfs/`).

