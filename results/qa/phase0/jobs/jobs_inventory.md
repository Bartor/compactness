# Zbiór miejsc pracy i ludności w wieku produkcyjnym (Goliszek): inwentaryzacja

Faza 0, raport generowany przez `pipeline/jobs_inventory.py`. Dane: Goliszek S. (IGiPZ PAN), *Spatially disaggregated working-age population and job estimates for seven Polish cities with a 2025 allocation horizon*, Mendeley Data, v1, doi:10.17632/mr9ywkgd9t.1, licencja CC BY 4.0, publikacja 2026-09-29.

## Pliki i format

| Plik | Warstwa | Geometria | Obiekty | Pola | Suma |
|---|---|---|---|---|---|
| `Jobs_2025_7_Cities.gpkg` | `jobs_2025shp` | MultiPolygon Z | 50 631 | `Id`, `Name_ALL`, `Jobs_25` | 3 252 262 miejsc pracy |
| `Workers_2025_7_Cities.gpkg` | `workers_2025shp` | MultiPolygon Z | 138 601 | `Id`, `Name_ALL`, `Workers_25` | 3 618 940 osób w wieku produkcyjnym |

- `Workers_25` to ludność w wieku produkcyjnym (kobiety 18-59, mężczyźni 18-64), **nie** zatrudnieni mieszkańcy; `Jobs_25` to miejsca pracy według lokalizacji zakładu (autor: „Workers_25 represents working-age population, not employed residents”). Wartości ułamkowe (alokacja proporcjonalna), zachowane bez zaokrąglania.
- `Name_ALL` zawiera nazwy miast bez polskich znaków (Gdansk, Krakow, Lodz, Poznan, Szczecin, Warsaw, Wroclaw). `Id` jest unikalny w obrębie miasta, ale w Jobs zakresy Id różnych miast nakładają się, a ten sam `Id` w plikach Jobs i Workers wskazuje różne geometrie (sprawdzone: 0 zgodnych par), więc nie jest kluczem łączenia plików. Łączyć trzeba geometrią.
- Warstwy zawierają tylko komórki z dodatnią wartością (autor: „Released layers contain polygons with positive allocated values”). Brak komórek = brak alokacji (0 albo poza zasięgiem danych wejściowych); tego z samych plików nie da się rozróżnić.
- Brak GZM i brak osobnych danych dla Gdyni (Trójmiasto: tylko Gdańsk). Brak przepływów OD (autor: „does not contain individual records or origin-destination commuting flows”).

## Układ współrzędnych i siatka

- CRS pliku: `ESRI:102173` (ESRI:102173, ETRS89 / Poland CS92, tożsamy z EPSG:2180). Do EPSG:2180 nie trzeba przeliczać.
- Komórki mają nominalnie 100 x 100 m. Po przeliczeniu do Mollweide (ESRI:54009) wierzchołki leżą na wielokrotnościach 100 m: 90% (x) i 88% (y) wierzchołków w Jobs; 89% i 88% w Workers. Pełne komórki mają dokładnie 10 000 m² w Mollweide: 86% (Jobs), 83% (Workers).
- **Wniosek: to siatka GHSL 100 m w Mollweide (ESRI:54009), przepisana do EPSG:2180** (w 2180 komórki są lekko zniekształcone, szerokość ok. 109-111 m zamiast 100 m, pole zachowane w Mollweide). Pozostałe wierzchołki to cięcia na granicach stref modeli ruchu: 11% komórek Jobs i 13% komórek Workers jest niepełnych (pole < 10 000 m²).
- Obiekty wieloczęściowe: 2% (Jobs) i 2% (Workers); największy obiekt Jobs ma 30 000 m², Workers 50 000 m² (kilka sąsiednich komórek scalonych w jeden obiekt MultiPolygon). **Do analizy nie traktować obiektu jako jednej komórki:** przed dopasowaniem do GHS-POP/siatki 250 m trzeba rasteryzować lub dzielić wg siatki, a wartość rozkładać proporcjonalnie do pola.
- Zgodność z siatką GHS-POP/GHS-BUILT-S R2023A (też 100 m Mollweide) jest więc zachowana, ale wartości dotyczą **epoki zabudowy 2025** (modelowanej), a nie 2020, której używamy do ludności (§3 briefu). Przy łączeniu z ludnością GHS-POP 2020 trzeba to wpisać w ograniczenia.

## Metoda wg autora (cytaty istotne dla interpretacji)

- „Source counts were supplied as attributes of transport-zone polygons.” Dane wejściowe to **strefy modeli ruchu / badań komunikacyjnych miast**, nie rejestr zatrudnienia.
- „We distributed the working-age population within each transport zone in proportion to residential volume, and jobs in proportion to non-residential volume.” Podział wewnątrz strefy wg kubatury zabudowy GHSL (GHS-BUILT-V): mieszkaniowej (całość minus niemieszkaniowa) dla ludności, **niemieszkaniowej dla miejsc pracy**. W obrębie strefy rozkład jest więc modelowany, nie obserwowany; wiarygodna jest wielkość strefy, nie pojedynczej komórki.
- „We applied no additional spatial masks or land-use exclusions.” Brak masek (np. lasów, wód): komórki mogą mieć wartości tam, gdzie GHSL ma kubaturę błędnie.
- „The dataset has a common 2025 allocation horizon, but its source counts do not represent a uniform observation year.” **Horyzont 2025 dotyczy epoki kubatury GHSL, nie roku danych o pracy/ludności.**
- Poznań: dane z 2019 zaalokowane wg kubatury 2020, potem zaktualizowane zmianą kubatury 2020-2025 „without renormalising the resulting estimates to the original zone totals”: sumy nie muszą zgadzać się ze źródłowymi.
- Łódź: „inputs refer to 2023”; Szczecin: „2025 forecast from the 2016 traffic study” (prognoza, nie stan faktyczny; tłumaczy to prawdopodobnie niską liczbę miejsc pracy względem ludności).
- „These assessments describe consistency with building capacity and spatial structure, rather than direct accuracy against observed population or employment counts.” Autor nie waliduje dokładności względem spisu/zatrudnienia. Wyniki traktować jako „estymaty alokacyjne”, nie pomiar.
- Dla Gdańska, Krakowa, Warszawy i Wrocławia opis zbioru nie podaje roku danych wejściowych (tylko ogólny horyzont 2025); trzeba go ustalić z manuskryptu towarzyszącego (nie jest dołączony do zbioru).

## Sumy i lata wejściowe per miasto

| Miasto | Miejsca pracy | Wiek produkcyjny | Miejsca pracy / ludność w w.p. | Lata wejściowe (wg autora) |
|---|---|---|---|---|
| Gdańsk | 235 656 | 215 091 | 1.10 | nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025) |
| Kraków | 294 608 | 480 058 | 0.61 | nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025) |
| Łódź | 299 571 | 457 829 | 0.65 | dane wejściowe z 2023 |
| Poznań | 346 243 | 305 088 | 1.13 | dane z 2019, aktualizowane do 2025 zmianą kubatury GHSL 2020-2025 |
| Szczecin | 125 018 | 371 441 | 0.34 | prognoza na 2025 z badania ruchu z 2016 |
| Warszawa | 1 506 972 | 1 343 650 | 1.12 | nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025) |
| Wrocław | 444 195 | 445 783 | 1.00 | nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025) |
| **Razem** | **3 252 262** | **3 618 940** | 0.90 | |

Sumy zgadzają się z opisem zbioru (ok. 3,25 mln miejsc pracy i 3,62 mln osób w wieku produkcyjnym).

## Zasięg przestrzenny

Odniesienie: URAU 2021 (GISCO), pliki w data/raw/boundaries: miasto (C) i FUA (F); results/web/fua.geojson jeszcze nie istnieje. Footprint = suma (dissolve) komórek z danymi; zapisany w `data/interim/jobs/footprints.gpkg` (EPSG:2180, warstwy `jobs`, `workers`, `union`). „W mieście” = środek komórki w granicy miasta (URAU „city”, generalizowana 1:100 000, więc granica przybliżona).

| Miasto | Pow. miasta (URAU) km² | Footprint Jobs km² | Footprint Workers km² | Bbox Jobs (km) | Praca: udział sumy w mieście | Ludność w.p.: udział sumy w mieście | Footprint (suma) poza miastem | Pokrycie miasta | Pokrycie FUA | Wniosek |
|---|---|---|---|---|---|---|---|---|---|---|
| Gdańsk | 261 | 51 | 138 | 32.5 x 18.0 | 100% | 100% | 1% | 58% | 10% | miasto (granice administracyjne) |
| Kraków | 326 | 68 | 222 | 28.7 x 16.3 | 100% | 100% | 0% | 70% | 7% | miasto (granice administracyjne) |
| Łódź | 293 | 63 | 204 | 21.6 x 19.2 | 100% | 100% | 0% | 71% | 8% | miasto (granice administracyjne) |
| Poznań | 262 | 47 | 151 | 21.1 x 21.9 | 100% | 100% | 0% | 60% | 7% | miasto (granice administracyjne) |
| Szczecin | 301 | 62 | 94 | 21.4 x 23.4 | 100% | 100% | 0% | 33% | 7% | miasto (granice administracyjne) |
| Warszawa | 517 | 152 | 363 | 27.3 x 29.2 | 100% | 100% | 0% | 73% | 4% | miasto (granice administracyjne) |
| Wrocław | 293 | 53 | 174 | 23.9 x 18.3 | 100% | 100% | 0% | 60% | 6% | miasto (granice administracyjne) |

Pokrycie = udział powierzchni miasta (FUA) przykryty footprintem (Jobs lub Workers). Footprint nie zawiera komórek o zerowej alokacji, więc pokrycie <100% w mieście oznacza tereny bez kubatury GHSL (lasy, wody, pola), a nie dziury w danych; to hipoteza, nie sprawdzono tego względem pokrycia terenu. Szczecin wyróżnia się niskim pokryciem miasta (ok. 1/3 powierzchni): zakres stref modelu ruchu z 2016 r. lub rozległe tereny niezabudowane w granicach miasta; do wyjaśnienia przed użyciem w dostępności.

Uwaga: **porównanie z FUA robione na surowych granicach URAU 2021 (GISCO)**, bo `results/web/fua.geojson` jeszcze nie istnieje; po jego pojawieniu się raport trzeba przeliczyć (`python -m pipeline.jobs_inventory`). Kolumna „Pokrycie FUA” dotyczy całego obszaru FUA, bez bufora 15 km.

### Interpretacja i konsekwencje

- Zasięg szerszy niż miasto (próg: >10% sumy lub powierzchni poza granicą miasta): brak.
- Zasięg ≈ miasto w granicach administracyjnych: Gdańsk, Kraków, Łódź, Poznań, Szczecin, Warszawa, Wrocław.
- Zbiór **nie obejmuje całych FUA** w żadnym z siedmiu miast: poza footprintem wynik dostępności do miejsc pracy to „brak danych”, nie 0 (§4.6 briefu). W szczególności dostępność miejsc pracy z gmin podmiejskich spoza footprintu jest nieobliczalna, a miejsca pracy leżące poza footprintem nie są wliczone do liczby osiągalnych w 30/45 min (**zaniżenie** w pobliżu granicy zasięgu).
- Kraków, Wrocław, Poznań, Łódź, Gdańsk, Szczecin i Warszawa mają różne lata danych i różny stopień modelowania (m.in. prognoza dla Szczecina); porównania **między miastami** wymagają adnotacji.
- Dane Goliszka służą tylko do wskaźników miejsc pracy (§4.6); ludność do miar gęstości pozostaje z NSP 2021 / GHS-POP 2020.
