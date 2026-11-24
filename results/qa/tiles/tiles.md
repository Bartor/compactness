# Kafle mapy (faza 4)

Dzień referencyjny rozkładów: 2026-11-25; ludność: NSP 2021 (31.03.2021) rozłożona wzorem GHSL 2020. Kafle MVT, zoomy 4–12 (powyżej MapLibre powiększa kafel z z12), extent 4096, bufor 64, gzip; jeden plik PMTiles na warstwę, jedna klasa wartości = jeden obiekt w kafelku.

## Rozmiary

| Plik | Rozmiar (MB) | Kafli | Warstwa |
|---|---|---|---|
| `density250_nsp2021.pmtiles` | 3,00 | 2417 | Gęstość zaludnienia 250 m (NSP 2021) |
| `density_service_2026-11-25.pmtiles` | 1,34 | 1424 | Gęstość × częstotliwość komunikacji |
| `frequent_2026-11-25.pmtiles` | 1,38 | 1424 | Zasięg częstej komunikacji |
| `gtfs_nodata_2026-11-25.pmtiles` | 0,37 | 1315 | Brak danych GTFS |
| `transfer_dep30_2026-11-25.pmtiles` | 1,59 | 1424 | Zasięg 30 min wymagający przesiadki |
| `performance30_2026-11-25.pmtiles` | 1,52 | 1424 | Transport performance 30 min |
| **razem `tiles/`** | **9,20** | | |

Ostrzeżenia o rozmiarze: brak (żaden plik nie przekracza 50 MB, katalog nie przekracza 200 MB).

## Jak powstały kafle

- Komórki 250 m (EPSG:2180) trafiają do klas rampy kolorów, a sąsiednie komórki tej samej klasy są łączone w wielokąty (`rasterio.features.shapes`, łączność 4) osobno dla okna siatki pod każdym kafelkiem. Krawędzie są zagęszczane do 250 m, rzutowane do EPSG:3857, przycinane do kafla z buforem 64 jednostek i przyciągane do siatki 4096.
- Obiekt niesie jedną liczbę `v`: wartość reprezentatywna klasy (nie wartość komórki), taka, że wyrażenie `step` w aplikacji wybiera kolor klasy. Obiekty bez `v` to brak danych (kreskowane), nigdy zero.
- Zoomy poniżej 9: siatka jest grubiona blokami 2^(9-z) komórek, a klasa bloku to dominanta narysowanych komórek (remis wygrywa brak danych). Blok jest rysowany, gdy narysowano w nim choć jedną komórkę, więc obszar FUA pozostaje widoczny na z5–z7, ale na z4–z8 brzegi są poszerzone o do pół bloku (od 500 m na z8 do 16 km na z4).
- Komórki bez ludności nie są rysowane (rzeczywiste zero, nie brak danych); warstwy tranzytowe rysują tylko komórki z ludnością > 0 w siatce przeskalowanej do spisu (komórki z samą ludnością surową GHSL pomijamy).

## Warstwy

### Gęstość zaludnienia 250 m (NSP 2021) (`density_250m`)

- Plik `density250_nsp2021.pmtiles`, 3,00 MB, SHA-256 `6f644d001f21740ad77dd0859ff042ab4c3fc3cf89d50d19fc5d66bcd582d9f2`.
- Aglomeracje w pliku (13): Białystok, Bydgoszcz–Toruń, GZM, Kielce, Kraków, Łódź, Lublin, Poznań, Rzeszów, Szczecin, Trójmiasto, Warszawa, Wrocław.
- Narysowanych komórek 250 m: 356031.
- Nagłówek: MVT, kafle GZIP, katalogi GZIP, clustered=True, zoomy 4–12, zakres [14.19277, 49.6951, 24.1307, 54.54745], środek [19.16173, 52.12128, 8], kafli adresowanych 2417 (unikalnych 2417); warstwy wektorowe w metadanych: density250.

| Zoom | Kafli | Bajtów razem | Największy kafel (B) |
|---|---|---|---|
| 4 | 2 | 1009 | 755 |
| 5 | 2 | 2163 | 1811 |
| 6 | 6 | 7885 | 4043 |
| 7 | 12 | 32995 | 7234 |
| 8 | 30 | 131443 | 12843 |
| 9 | 74 | 484173 | 36324 |
| 10 | 180 | 558330 | 15728 |
| 11 | 510 | 733266 | 6653 |
| 12 | 1601 | 1041981 | 2418 |

Kontrola przypisania na z12: sprawdzono 356031 narysowanych komórek (środek komórki w kafelku); nie pokryte przez żaden obiekt: 0, pokryte obiektem innej klasy: 0; komórki niezaludnione pokryte obiektem: 0; obiekty o niedozwolonej własności: 0.

Powierzchnia klas na z12 (km², suma po aglomeracjach): kafle (przycięte do granic kafla bez bufora) wobec komórek źródłowych.

| Klasa | Komórki źródłowe (km²) | Kafle (km²) | Różnica (%) |
|---|---|---|---|
| < 500 | 17772,12 | 17763,83 | -0,047 |
| 500–1 000 | 1804,87 | 1804,76 | -0,007 |
| 1 000–2 500 | 1325,69 | 1325,72 | +0,003 |
| 2 500–5 000 | 620,06 | 620,06 | +0,000 |
| 5 000–10 000 | 461,12 | 461,11 | -0,004 |
| 10 000–20 000 | 246,25 | 246,26 | +0,004 |
| ≥ 20 000 | 21,81 | 21,81 | -0,041 |

Największa różnica po aglomeracji (klasy o powierzchni ≥ 1 km², pełna tabela w `area_check.csv`): Białystok 0,062 %, Bydgoszcz–Toruń 0,049 %, GZM 0,049 %, Kielce 0,052 %, Kraków 0,037 %, Łódź 0,048 %, Lublin 0,041 %, Poznań 0,051 %, Rzeszów 0,044 %, Szczecin 0,059 %, Trójmiasto 0,044 %, Warszawa 0,045 %, Wrocław 0,061 %.

### Gęstość × częstotliwość komunikacji (`density_service`)

- Plik `density_service_2026-11-25.pmtiles`, 1,34 MB, SHA-256 `d60b305687902b10a46134cde1ecb9cce0d62d31fe5ca1efe3893344fd390a5e`.
- Aglomeracje w pliku (7): GZM, Kraków, Łódź, Poznań, Trójmiasto, Warszawa, Wrocław.
- Narysowanych komórek 250 m: 228755.
- Pominięto 6046 komórek bez ludności w siatce przeskalowanej do spisu (są w źródle, bo mają ludność surową GHSL).
- Nagłówek: MVT, kafle GZIP, katalogi GZIP, clustered=True, zoomy 4–12, zakres [16.36653, 49.74768, 22.34871, 54.61437], środek [19.35762, 52.18102, 8], kafli adresowanych 1424 (unikalnych 1424); warstwy wektorowe w metadanych: density_service.

| Zoom | Kafli | Bajtów razem | Największy kafel (B) |
|---|---|---|---|
| 4 | 2 | 1271 | 1207 |
| 5 | 1 | 3111 | 3111 |
| 6 | 4 | 12141 | 7903 |
| 7 | 9 | 30531 | 7902 |
| 8 | 21 | 78990 | 11633 |
| 9 | 40 | 199891 | 19249 |
| 10 | 98 | 229219 | 7994 |
| 11 | 299 | 313367 | 3715 |
| 12 | 950 | 467579 | 1563 |

Kontrola przypisania na z12: sprawdzono 228755 narysowanych komórek (środek komórki w kafelku); nie pokryte przez żaden obiekt: 0, pokryte obiektem innej klasy: 0; komórki niezaludnione pokryte obiektem: 0; obiekty o niedozwolonej własności: 0.

Powierzchnia klas na z12 (km², suma po aglomeracjach): kafle (przycięte do granic kafla bez bufora) wobec komórek źródłowych.

| Klasa | Komórki źródłowe (km²) | Kafle (km²) | Różnica (%) |
|---|---|---|---|
| brak danych GTFS | 4360,00 | 4358,48 | -0,035 |
| ≥ 5 000 os./km², kursy rzadziej niż co 20 min lub brak | 77,25 | 77,25 | -0,004 |
| ≥ 5 000 os./km², co 11–20 min | 94,62 | 94,62 | -0,003 |
| ≥ 5 000 os./km², co ≤ 10 min | 371,19 | 371,18 | -0,001 |
| < 5 000 os./km², co ≤ 20 min | 856,12 | 856,11 | -0,002 |
| < 5 000 os./km², rzadziej lub brak | 8538,00 | 8534,54 | -0,041 |

Największa różnica po aglomeracji (klasy o powierzchni ≥ 1 km², pełna tabela w `area_check.csv`): GZM 0,040 %, Kraków 0,045 %, Łódź 0,039 %, Poznań 0,042 %, Trójmiasto 0,042 %, Warszawa 0,042 %, Wrocław 0,054 %.

### Zasięg częstej komunikacji (`frequent_transport`)

- Plik `frequent_2026-11-25.pmtiles`, 1,38 MB, SHA-256 `6c1ff8f3c8a7738e82a7416eef4b0b493b2c5db8c90798c354e75b0a583cc783`.
- Aglomeracje w pliku (7): GZM, Kraków, Łódź, Poznań, Trójmiasto, Warszawa, Wrocław.
- Narysowanych komórek 250 m: 228755.
- Pominięto 6046 komórek bez ludności w siatce przeskalowanej do spisu (są w źródle, bo mają ludność surową GHSL).
- Nagłówek: MVT, kafle GZIP, katalogi GZIP, clustered=True, zoomy 4–12, zakres [16.36653, 49.74768, 22.34871, 54.61437], środek [19.35762, 52.18102, 8], kafli adresowanych 1424 (unikalnych 1424); warstwy wektorowe w metadanych: frequent.

| Zoom | Kafli | Bajtów razem | Największy kafel (B) |
|---|---|---|---|
| 4 | 2 | 1242 | 1185 |
| 5 | 1 | 3072 | 3072 |
| 6 | 4 | 12294 | 8041 |
| 7 | 9 | 32825 | 8497 |
| 8 | 21 | 84629 | 12890 |
| 9 | 40 | 207169 | 21027 |
| 10 | 98 | 236927 | 8724 |
| 11 | 299 | 321590 | 3777 |
| 12 | 950 | 475190 | 1487 |

Kontrola przypisania na z12: sprawdzono 228755 narysowanych komórek (środek komórki w kafelku); nie pokryte przez żaden obiekt: 0, pokryte obiektem innej klasy: 0; komórki niezaludnione pokryte obiektem: 0; obiekty o niedozwolonej własności: 0.

Powierzchnia klas na z12 (km², suma po aglomeracjach): kafle (przycięte do granic kafla bez bufora) wobec komórek źródłowych.

| Klasa | Komórki źródłowe (km²) | Kafle (km²) | Różnica (%) |
|---|---|---|---|
| brak danych GTFS | 4360,00 | 4358,48 | -0,035 |
| co ≤ 5 min | 341,31 | 341,31 | +0,001 |
| co ≤ 10 min | 435,88 | 435,88 | +0,000 |
| co ≤ 15 min | 270,63 | 270,61 | -0,006 |
| co ≤ 20 min | 274,12 | 274,12 | -0,003 |
| co ≤ 30 min | 353,81 | 353,78 | -0,009 |
| rzadziej niż co 30 min lub brak | 8261,44 | 8258,00 | -0,042 |

Największa różnica po aglomeracji (klasy o powierzchni ≥ 1 km², pełna tabela w `area_check.csv`): GZM 0,040 %, Kraków 0,034 %, Łódź 0,041 %, Poznań 0,044 %, Trójmiasto 0,042 %, Warszawa 0,043 %, Wrocław 0,055 %.

### Brak danych GTFS (`gtfs_nodata`)

- Plik `gtfs_nodata_2026-11-25.pmtiles`, 0,37 MB, SHA-256 `e53bddf056d0ef45199f1a38ae727a4f7ba93a02c5d90b7907877a534cf2dc35`.
- Aglomeracje w pliku (7): GZM, Kraków, Łódź, Poznań, Trójmiasto, Warszawa, Wrocław.
- Narysowanych komórek 250 m: 106967.
- Powierzchnia wielokątów źródłowych (km²): GZM 340,5, Kraków 1141,6, Łódź 411,7, Poznań 584,4, Trójmiasto 820,2, Warszawa 2476,8, Wrocław 910,3.
- Nagłówek: MVT, kafle GZIP, katalogi GZIP, clustered=True, zoomy 4–12, zakres [16.35493, 49.75217, 22.34871, 54.61412], środek [19.35182, 52.18314, 8], kafli adresowanych 1315 (unikalnych 1315); warstwy wektorowe w metadanych: gtfs_nodata.

| Zoom | Kafli | Bajtów razem | Największy kafel (B) |
|---|---|---|---|
| 4 | 2 | 493 | 433 |
| 5 | 1 | 1379 | 1379 |
| 6 | 4 | 5018 | 3263 |
| 7 | 9 | 10878 | 2859 |
| 8 | 21 | 22241 | 3058 |
| 9 | 38 | 43233 | 3761 |
| 10 | 96 | 54094 | 1302 |
| 11 | 288 | 86345 | 641 |
| 12 | 856 | 146447 | 366 |

Kontrola przypisania na z12: sprawdzono 106967 narysowanych komórek (środek komórki w kafelku); nie pokryte przez żaden obiekt: 0, pokryte obiektem innej klasy: 0; komórki niezaludnione pokryte obiektem: 0; obiekty o niedozwolonej własności: 0.

Powierzchnia klas na z12 (km², suma po aglomeracjach): kafle (przycięte do granic kafla bez bufora) wobec komórek źródłowych.

| Klasa | Komórki źródłowe (km²) | Kafle (km²) | Różnica (%) |
|---|---|---|---|
| brak danych GTFS | 6685,44 | 6683,61 | -0,027 |

Największa różnica po aglomeracji (klasy o powierzchni ≥ 1 km², pełna tabela w `area_check.csv`): GZM 0,037 %, Kraków 0,026 %, Łódź 0,031 %, Poznań 0,032 %, Trójmiasto 0,022 %, Warszawa 0,026 %, Wrocław 0,029 %.

### Zasięg 30 min wymagający przesiadki (`transfer_dependence_30`)

- Plik `transfer_dep30_2026-11-25.pmtiles`, 1,59 MB, SHA-256 `a5dd48ccc7bbbc619fd4c16591504fdcd7e410e641b9d8afdd373d516bda2aeb`.
- Aglomeracje w pliku (7): GZM, Kraków, Łódź, Poznań, Trójmiasto, Warszawa, Wrocław.
- Narysowanych komórek 250 m: 228755.
- Nagłówek: MVT, kafle GZIP, katalogi GZIP, clustered=True, zoomy 4–12, zakres [16.36653, 49.74768, 22.34871, 54.61437], środek [19.35762, 52.18102, 8], kafli adresowanych 1424 (unikalnych 1424); warstwy wektorowe w metadanych: transfer_dep30.

| Zoom | Kafli | Bajtów razem | Największy kafel (B) |
|---|---|---|---|
| 4 | 2 | 1327 | 1264 |
| 5 | 1 | 3238 | 3238 |
| 6 | 4 | 12722 | 8268 |
| 7 | 9 | 31914 | 8182 |
| 8 | 21 | 85625 | 12946 |
| 9 | 40 | 247822 | 28393 |
| 10 | 98 | 281640 | 13583 |
| 11 | 299 | 377322 | 6284 |
| 12 | 950 | 546598 | 2334 |

Kontrola przypisania na z12: sprawdzono 228755 narysowanych komórek (środek komórki w kafelku); nie pokryte przez żaden obiekt: 0, pokryte obiektem innej klasy: 0; komórki niezaludnione pokryte obiektem: 0; obiekty o niedozwolonej własności: 0.

Powierzchnia klas na z12 (km², suma po aglomeracjach): kafle (przycięte do granic kafla bez bufora) wobec komórek źródłowych.

| Klasa | Komórki źródłowe (km²) | Kafle (km²) | Różnica (%) |
|---|---|---|---|
| brak danych | 4360,00 | 4358,48 | -0,035 |
| < 1 % | 7959,94 | 7956,57 | -0,042 |
| 1–5 % | 612,31 | 612,23 | -0,013 |
| 5–10 % | 511,06 | 511,05 | -0,003 |
| 10–20 % | 543,06 | 543,05 | -0,003 |
| 20–30 % | 213,00 | 212,99 | -0,003 |
| ≥ 30 % | 97,81 | 97,81 | -0,006 |

Największa różnica po aglomeracji (klasy o powierzchni ≥ 1 km², pełna tabela w `area_check.csv`): GZM 0,041 %, Kraków 0,034 %, Łódź 0,040 %, Poznań 0,044 %, Trójmiasto 0,043 %, Warszawa 0,043 %, Wrocław 0,058 %.

### Transport performance 30 min (`transport_performance_30`)

- Plik `performance30_2026-11-25.pmtiles`, 1,52 MB, SHA-256 `5e113088443b87b2977464babd4fc2b9593124a8071bc4938892227dfd303df3`.
- Aglomeracje w pliku (7): GZM, Kraków, Łódź, Poznań, Trójmiasto, Warszawa, Wrocław.
- Narysowanych komórek 250 m: 228755.
- Nagłówek: MVT, kafle GZIP, katalogi GZIP, clustered=True, zoomy 4–12, zakres [16.36653, 49.74768, 22.34871, 54.61437], środek [19.35762, 52.18102, 8], kafli adresowanych 1424 (unikalnych 1424); warstwy wektorowe w metadanych: performance30.

| Zoom | Kafli | Bajtów razem | Największy kafel (B) |
|---|---|---|---|
| 4 | 2 | 1343 | 1281 |
| 5 | 1 | 3825 | 3825 |
| 6 | 4 | 14279 | 9340 |
| 7 | 9 | 34367 | 9195 |
| 8 | 21 | 86771 | 13653 |
| 9 | 40 | 229477 | 25621 |
| 10 | 98 | 263926 | 11286 |
| 11 | 299 | 356217 | 6264 |
| 12 | 950 | 523096 | 2379 |

Kontrola przypisania na z12: sprawdzono 228755 narysowanych komórek (środek komórki w kafelku); nie pokryte przez żaden obiekt: 0, pokryte obiektem innej klasy: 0; komórki niezaludnione pokryte obiektem: 0; obiekty o niedozwolonej własności: 0.

Powierzchnia klas na z12 (km², suma po aglomeracjach): kafle (przycięte do granic kafla bez bufora) wobec komórek źródłowych.

| Klasa | Komórki źródłowe (km²) | Kafle (km²) | Różnica (%) |
|---|---|---|---|
| brak danych GTFS | 4360,00 | 4358,48 | -0,035 |
| < 10 | 7408,06 | 7404,86 | -0,043 |
| 10–20 | 1287,19 | 1286,96 | -0,018 |
| 20–30 | 633,56 | 633,53 | -0,006 |
| 30–40 | 345,50 | 345,49 | -0,004 |
| 40–50 | 166,31 | 166,32 | +0,005 |
| 50–60 | 58,25 | 58,24 | -0,012 |
| ≥ 60 | 38,31 | 38,31 | -0,005 |

Największa różnica po aglomeracji (klasy o powierzchni ≥ 1 km², pełna tabela w `area_check.csv`): GZM 0,041 %, Kraków 0,034 %, Łódź 0,042 %, Poznań 0,060 %, Trójmiasto 0,044 %, Warszawa 0,045 %, Wrocław 0,058 %.

## Transfer na typową wizytę

Pierwsza wizyta, jedna warstwa wartości, okno 1440 × 900 px na jednej aglomeracji przy zoomach 8, 10, 11, 12 (kafle 512 px, bajty skompresowane tak, jak je odczyta przeglądarka). Stałe: aplikacja po gzip 736 kB, `catalog.json` 4 kB, `fua.geojson` 75 kB, `attributions.json` 2 kB, `metrics.json` 27 kB (razem 845 kB); do tego 16 kB nagłówka i katalogu PMTiles na plik. Podkład OpenFreeMap idzie z ich serwerów, nie z limitu Pages.

| Warstwa | Aglomeracja | Kafle (kB) | Razem wizyta (kB) | Wizyt w 100 GB/mies. |
|---|---|---|---|---|
| Gęstość zaludnienia 250 m (NSP 2021) | Warszawa | 226 | 1071 | 93401 |
| Gęstość × częstotliwość komunikacji | Warszawa | 140 | 985 | 101542 |
| Zasięg częstej komunikacji | Warszawa | 148 | 993 | 100696 |
| Brak danych GTFS | Warszawa | 43 | 887 | 112699 |
| Zasięg 30 min wymagający przesiadki | Warszawa | 180 | 1024 | 97625 |
| Transport performance 30 min | Warszawa | 169 | 1014 | 98617 |

Powtórna wizyta czyta aplikację i dane z pamięci podręcznej przeglądarki, więc kosztuje tylko kafle, o ile ich pliki się nie zmieniły. Kolejna warstwa tej samej aglomeracji dodaje swoje kafle (i 16 kB katalogu). To oszacowanie z jednego położenia okna, nie pomiar ruchu.

