# Szkoły, szpitalne oddziały ratunkowe i grupy wieku (ROADMAP, punkt 13)

Stan: 2026-11-24. Kod: `pipeline/agegrid.py` (wiek), `pipeline/services.py` (rejestry, położenie placówek), `pipeline/access_services.py` (routing), `pipeline/access_services_aggregate.py` (tabele). Liczby: `metrics/metrics_services.csv` i `.json`; warstwa komórek: `layers/services_cells.parquet`; tabele kontrolne w tym katalogu.

Daty: ludność NSP 2021 (31.03.2021) w układzie GHSL 2020; grupy wieku NSP 2021 (31.03.2021); rejestry szkół i SOR: stan z 2026-11-24; rozkłady: środa 2026-11-25; OSM 2026-11-22.

## 1. Źródła i licencje

| Dane | Źródło | Licencja | Data | Położenie |
|---|---|---|---|---|
| Grupy wieku 0–14, 15–64, 65+ | GUS, NSP 2021, siatka 1 km (`GRID_NSP2021_RES`, pola `RES_0_14`, `RES_15_64`, `RES_65_`); ten sam plik co siatka ludności projektu, bez nowego pobierania | jak w manifeście (`nsp2021_grid_1km_shp`): usługa INSPIRE GUS bez warunków, cytować GUS | 31.03.2021 | kwadraty 1 km (EPSG:3035) |
| Szkoły ponadpodstawowe | RSPO (Rejestr Szkół i Placówek Oświatowych, MEN), interfejs JSON publicznej wyszukiwarki rspo.gov.pl, bez konta | na stronie nie podano; roczny wykaz tego rejestru w dane.gov.pl (zbiór 839) ma CC BY 4.0 | 2026-11-24 | współrzędne siedziby z rejestru (`hqGeotag`); sposób geokodowania nie jest opisany |
| SOR | RPRM (Rejestr Państwowego Ratownictwa Medycznego), publiczny eksport CSV z rprm.ezdrowie.gov.pl, jednostki „Szpitalny oddział ratunkowy”, status „Aktywna” | na stronie nie podano; wpis tego rejestru w dane.gov.pl (zbiór 1642) ma CC BY 4.0, ale jego plik jest z 2021-05-17, dlatego użyto eksportu bieżącego | 2026-11-24 | rejestr podaje tylko adres; punkt z OSM (niżej) |
| Położenie SOR, kontrola położenia szkół | OpenStreetMap, `poland-latest.osm.pbf` (już w projekcie) | ODbL | 2026-11-22 | adresy i obiekty `amenity=hospital/school` |

Usługa geokodowania GUGiK (`services.gugik.gov.pl/uug`, punkty adresowe PRG) odpowiedziała na jedno zapytanie próbne, potem zwracała „Request Rejected”. Nie ponawiano jej i nie obchodzono blokady; adresy SOR dopasowano do OSM. Do ewentualnej poprawki: pobrać ręcznie punkty adresowe PRG (geoportal.gov.pl, bezpłatnie) do `data/raw/prg_adresy/`.

Kopie surowe: `data/raw/rspo_secondary/` (bez nazwisk organów prowadzących, telefonów, e-maili i stron www, które usunięto przed zapisem), `data/raw/rprm_sor/`; w obu katalogach `SOURCE.json` z adresem, datą i sumą kontrolną.

## 2. Metoda

### 2.1 Grupy wieku na siatce 250 m

- Siatka spisowa podaje tylko trzy grupy: 0–14, 15–64 i 65+. Tych używamy; drobniejszego podziału (np. 15–19 dla szkół średnich) nie ma.
- GUS utajnia małe liczby: w 61 503 kwadratach 1 km (748 tys. mieszkańców, 2,0 % kraju) część grup jest pusta. Brakującą resztę (RES minus znane grupy) przypisujemy wprost, gdy brakuje jednej grupy, a przy kilku brakujących dzielimy ją w proporcji krajowej. W FUA dotyczy to od 0,4 do 0,9 % mieszkańców (Warszawa 31,7 tys., GZM 7,8 tys.).
- Komórkę 250 m dzielimy na 5 × 5 podkomórek, każdą przypisujemy do kwadratu 1 km, w którym leży; udział grupy w komórce to średni udział grupy w tych kwadratach. Liczba osób w grupie = ludność komórki (siatka przeskalowana do spisu) × udział. Suma trzech grup równa się ludności komórki (różnica < 10⁻¹² osoby).
- Wariant kontrolny: udział z kwadratu, w którym leży środek komórki.
- **Czego ta dezagregacja nie umie.** Wewnątrz kwadratu 1 km udział grupy jest wszędzie taki sam. Różnica między grupą a wszystkimi mieszkańcami bierze się więc wyłącznie z różnic między kwadratami. Dla każdego wyniku podajemy też zakres, jaki dałoby skrajne rozmieszczenie grupy wewnątrz kwadratów (cała grupa w najlepiej albo w najgorzej obsłużonych komórkach kwadratu). Ten zakres jest bardzo szeroki (np. 43–94 % przy 76 % wyniku), więc nie jest przedziałem niepewności, tylko granicą tego, co dane w ogóle wykluczają. **Reguła:** różnicę uznajemy za „nie do obrony”, gdy jest mniejsza niż 1 pkt albo gdy wariant środka komórki daje znak przeciwny; w tabelach oznacza to gwiazdka.
- Miary porównywane: ludność ≤ 500 m od kursów co ≤ 10 i ≤ 20 min (definicja główna fazy 2, udział punktów próbkowania komórki z `frequent`), transport performance komunikacją w 30 min (środa 7–9, stosunek średnich i średnia stosunków jak w fazie 3). Wartości „wszyscy” odtwarzają opublikowane liczby co do setnej (np. rdzeń Warszawy: 80,38 % i 35,69).

### 2.2 Placówki

- **Szkoły:** licea ogólnokształcące (typ 14), technika (16), szkoły branżowe I stopnia (93); kategoria „dzieci lub młodzież”; bez szkół specjalnych; nie zlikwidowane; z co najmniej jednym uczniem; ze współrzędnymi; bez szkół działających w zakładach poprawczych, schroniskach dla nieletnich i okręgowych ośrodkach wychowawczych (rozpoznawane po nazwie). W kraju: 5 421 szkół (2 417 liceów, 1 772 techników, 1 232 szkoły branżowe). Odpadło m.in. 1 134 szkół dla dorosłych, 619 specjalnych, 1 387 rekordów bez uczniów, 29 szkół w zamkniętych placówkach.
- **SOR:** 251 aktywnych jednostek w kraju, w tym 13 dziecięcych (z nazwy jednostki); dziecięce nie wchodzą do wyniku, bo nie przyjmują dorosłych. Adres jednostki dopasowano do OSM: obiekt z tym samym numerem domu, wspólnym słowem nazwy ulicy i tą samą miejscowością albo kodem pocztowym; przy kilku kandydatach wygrywa obiekt oznaczony jako szpital, potem najbliższy szpitalowi z OSM. Wymagana jest zgodność ostatniego słowa nazwy ulicy (zwykle nazwiska). Gdy adresu nie znaleziono: szpital z OSM w tej samej miejscowości, wybrany po słowach nazwy podmiotu innych niż ogólne („szpital”, „samodzielny”, „publiczny” itd.), z dużą wagą dla zgodnej nazwy ulicy (8 jednostek; w obszarach: Kraków ul. Jakubowskiego 2, Trzebnica, Wejherowo, Poddębice i SOR dziecięcy w Warszawie przy Żwirki i Wigury 63A). Bez położenia zostały 4 jednostki, wszystkie poza siedmioma obszarami (Olsztyn, Lubin, Nowy Targ, Brzeg).
- Placówka należy do aglomeracji, gdy leży w FUA + 15 km (zasięg sieci R5), więc najbliższa szkoła czy SOR może leżeć za granicą FUA.

### 2.3 Czas dojazdu

- Starty: wszystkie zamieszkane komórki 250 m FUA w masce pokrycia GTFS (wariant „wszystkie feedy”), czyli dokładnie komórki obszaru „pokrytego” z fazy 3: 163 815 komórek.
- Cele: punkty placówek (kilka placówek pod jednym punktem liczone raz; dotyczy 29 % szkół, zwykle zespołów szkół).
- R5 v7.5.1 na prywatnej kopii sieci produkcyjnej `all`: pieszo 5 km/h do 60 min; komunikacja + pieszo w środę 2026-11-25, odjazdy co minutę 7:00–9:00 (dla SOR także 20:00–22:00), mediana z odjazdów, dojście do przystanku do 12 min (1 km), najwyżej 8 przejazdów, do 60 min. Jak w produkcji, dla każdej pary start–placówka bierzemy min(komunikacja, pieszo), potem minimum po placówkach. Brak placówki w 60 min = brak czasu (liczony w „bez … w 60 min”).
- Ramka celów produkcji nie zmieniła się; to osobny krok.
- Udziały to odsetki mieszkańców (siatka przeskalowana do spisu) obszaru: „obszar pokryty” = komórki FUA w masce; „rdzeń” = komórki rdzenia w masce (pole `coverage_share` w metrykach podaje, jaką część ludności rdzenia to obejmuje).

## 3. Wyniki

Wszystkie odsetki to % mieszkańców obszaru (siatka spisowa). „Obszar pokryty” = komórki FUA w masce pokrycia GTFS; „rdzeń” = komórki rdzenia w masce. Komunikacja = komunikacja zbiorowa z dojściem pieszym, mediana z odjazdów co minutę w oknie, nigdy gorzej niż pieszo. Pełne wartości (z surowym GHSL, medianami i flagami): `metrics/metrics_services.csv`.

### 3.1 Placówki (główne zbiory)

| Aglomeracja | Szkoły w FUA + 15 km | w FUA | w rdzeniu | licea / technika / branżowe (FUA) | SOR w FUA + 15 km | w FUA | w rdzeniu |
|---|---|---|---|---|---|---|---|
| Warszawa | 610 | 442 | 260 | 299 / 92 / 51 | 26 | 15 | 10 |
| Kraków | 267 | 168 | 119 | 94 / 46 / 28 | 14 | 7 | 5 |
| Wrocław | 188 | 115 | 97 | 62 / 34 / 19 | 7 | 5 | 4 |
| Poznań | 202 | 128 | 104 | 80 / 29 / 19 | 11 | 5 | 4 |
| Łódź | 212 | 137 | 94 | 76 / 40 / 21 | 12 | 8 | 5 |
| Trójmiasto | 181 | 140 | 108 | 75 / 39 / 26 | 6 | 5 | 4 |
| GZM | 481 | 283 | 250 | 125 / 95 / 63 | 13 | 4 | 4 |

„FUA + 15 km” to wszystkie placówki, do których liczono dojazd. Liczba punktów jest mniejsza od liczby szkół, bo zespoły szkół mają jedną siedzibę.

### 3.2 Najbliższa szkoła ponadpodstawowa (środa 7:00–9:00)

| Aglomeracja | Obszar | ≤ 15 | ≤ 20 | ≤ 30 | ≤ 45 | bez szkoły w 60 min | mediana, min | pieszo ≤ 15 | pieszo ≤ 30 | 0–14: ≤ 20 | 0–14: ≤ 30 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | obszar pokryty | 62,3 | 74,6 | 85,1 | 90,8 | 6,5 | 12 | 59,1 | 79,5 | 70,0 | 82,7 |
|  | rdzeń | 78,5 | 90,8 | 98,2 | 99,5 | 0,4 | 9 | 74,3 | 92,8 | 87,5 | 97,5 |
| Kraków | obszar pokryty | 49,5 | 59,4 | 73,4 | 83,2 | 11,2 | 16 | 46,9 | 65,2 | 51,1 | 68,0 |
|  | rdzeń | 66,8 | 80,0 | 95,1 | 98,8 | 0,5 | 11 | 63,1 | 85,8 | 73,8 | 93,4 |
| Wrocław | obszar pokryty | 54,5 | 67,8 | 81,8 | 88,0 | 8,3 | 14 | 50,2 | 70,8 | 56,4 | 75,2 |
|  | rdzeń | 65,4 | 81,2 | 96,0 | 99,7 | 0,1 | 11 | 60,2 | 84,3 | 72,9 | 94,2 |
| Poznań | obszar pokryty | 57,1 | 65,6 | 78,9 | 89,0 | 5,6 | 13 | 55,5 | 71,4 | 56,2 | 71,0 |
|  | rdzeń | 79,8 | 87,7 | 97,2 | 99,5 | 0,1 | 9 | 77,4 | 91,2 | 84,6 | 96,1 |
| Łódź | obszar pokryty | 66,6 | 74,7 | 83,7 | 90,0 | 6,9 | 10 | 66,0 | 79,5 | 68,2 | 78,8 |
|  | rdzeń | 81,2 | 89,4 | 96,6 | 99,1 | 0,3 | 8 | 80,4 | 91,7 | 86,1 | 95,1 |
| Trójmiasto | obszar pokryty | 60,4 | 74,8 | 91,1 | 96,3 | 2,3 | 12 | 57,5 | 79,7 | 67,4 | 88,0 |
|  | rdzeń | 65,5 | 79,0 | 94,4 | 98,5 | 0,4 | 11 | 62,1 | 81,7 | 71,7 | 92,2 |
| GZM | obszar pokryty | 61,3 | 74,6 | 88,5 | 95,1 | 2,1 | 12 | 58,9 | 78,7 | 71,7 | 86,4 |
|  | rdzeń | 67,8 | 81,2 | 94,3 | 98,9 | 0,3 | 11 | 65,3 | 84,7 | 79,5 | 93,7 |

### 3.3 Najbliższy SOR dla dorosłych (środa 7:00–9:00 i 20:00–22:00)

| Aglomeracja | Obszar | 7–9: ≤ 30 | 7–9: ≤ 45 | 20–22: ≤ 30 | 20–22: ≤ 45 | bez SOR w 60 min, 7–9 | bez SOR w 60 min, 20–22 | mediana 7–9, min | pieszo ≤ 30 | 65+: ≤ 30 (7–9) | 65+: ≤ 45 (7–9) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | obszar pokryty | 52,4 | 73,7 | 48,7 | 71,4 | 16,7 | 19,2 | 29 | 29,0 | 58,5 | 76,7 |
|  | rdzeń | 74,8 | 96,8 | 70,0 | 95,9 | 0,8 | 0,9 | 23 | 40,5 | 79,5 | 97,7 |
| Kraków | obszar pokryty | 44,9 | 63,4 | 42,4 | 62,7 | 27,0 | 28,7 | 33 | 27,4 | 53,0 | 69,8 |
|  | rdzeń | 64,8 | 88,0 | 61,1 | 87,9 | 3,1 | 3,2 | 26 | 39,7 | 72,2 | 92,1 |
| Wrocław | obszar pokryty | 41,9 | 74,5 | 38,9 | 75,4 | 16,5 | 17,5 | 33 | 17,7 | 46,3 | 79,5 |
|  | rdzeń | 51,1 | 90,6 | 47,4 | 91,8 | 1,3 | 1,0 | 30 | 21,7 | 53,2 | 91,3 |
| Poznań | obszar pokryty | 47,1 | 66,6 | 45,6 | 63,0 | 20,2 | 24,4 | 32 | 26,2 | 57,0 | 76,1 |
|  | rdzeń | 74,8 | 94,6 | 72,5 | 92,3 | 1,1 | 1,6 | 25 | 41,4 | 78,4 | 95,9 |
| Łódź | obszar pokryty | 53,7 | 76,7 | 51,1 | 75,2 | 15,7 | 18,1 | 30 | 33,2 | 56,4 | 80,9 |
|  | rdzeń | 64,4 | 93,9 | 64,2 | 92,6 | 1,7 | 2,4 | 27 | 38,9 | 64,1 | 94,6 |
| Trójmiasto | obszar pokryty | 49,3 | 83,0 | 44,0 | 78,3 | 5,8 | 10,2 | 31 | 24,3 | 57,8 | 88,6 |
|  | rdzeń | 57,9 | 92,7 | 52,5 | 91,1 | 2,2 | 2,3 | 28 | 27,3 | 64,2 | 94,8 |
| GZM | obszar pokryty | 13,4 | 38,6 | 10,8 | 30,6 | 27,9 | 42,8 | 51 | 4,4 | 14,6 | 41,3 |
|  | rdzeń | 16,2 | 44,8 | 13,0 | 35,6 | 18,0 | 34,6 | 47 | 5,4 | 17,3 | 47,0 |

### 3.4 Grupy wieku: częsta komunikacja i transport performance

| Aglomeracja | Obszar | Kursy ≤ 10 min: wszyscy / 0–14 / 65+ | Kursy ≤ 20 min: wszyscy / 0–14 / 65+ | KZ 30, stosunek średnich: wszyscy / 0–14 / 65+ | KZ 30, średnia stosunków: wszyscy / 0–14 / 65+ |
|---|---|---|---|---|---|
| Warszawa | obszar pokryty | 55,2 / 49,4 / 60,9 | 66,7 / 62,3 / 70,9 | 34,2 / 32,0 / 36,4 | 28,4 / 26,2 / 30,9 |
|  | rdzeń | 80,4 / 76,5 / 84,5 | 89,5 / 87,3 / 91,7 | 35,7 / 33,8 / 37,5 | 33,9 / 31,9 / 36,0 |
| Kraków | obszar pokryty | 46,6 / 39,6 / 52,7 | 60,0 / 53,4 / 65,3 | 31,4 / 29,0 / 33,8 | 24,5 / 21,7 / 27,3 |
|  | rdzeń | 66,1 / 61,2 / 70,2 | 83,1 / 80,1 / 85,7 | 33,0 / 31,2 / 35,0 | 31,6 / 29,5 / 33,9 |
| Wrocław | obszar pokryty | 62,8 / 54,0 / 69,1 | 69,8 / 61,9 / 75,9 | 29,1 / 25,9 / 30,7 | 24,6 / 21,3 / 27,1 |
|  | rdzeń | 75,8 / 70,4 / 79,0 | 83,2 / 78,8 / 86,2 | 29,4 / 26,5 / 30,9 | 27,6 / 24,7 / 29,2 |
| Poznań | obszar pokryty | 42,5 / 33,9 / 51,2 | 60,1 / 51,3 / 68,8 | 29,2 / 26,7 / 30,4 | 24,2 / 21,4 / 26,6 |
|  | rdzeń | 66,0 / 62,6 / 69,0 | 82,6 / 80,0 / 84,8 | 31,7 / 30,2 / 32,0* | 30,0 / 28,3 / 30,6* |
| Łódź | obszar pokryty | 51,8 / 46,0 / 56,1 | 64,2 / 58,0 / 69,1 | 28,3 / 27,3* / 28,2* | 26,0 / 24,2 / 26,9* |
|  | rdzeń | 69,6 / 66,1 / 71,6 | 82,2 / 79,2 / 84,0 | 28,3 / 27,5* / 28,0* | 26,9 / 25,8 / 26,9* |
| Trójmiasto | obszar pokryty | 48,7 / 42,6 / 55,6 | 72,6 / 68,4 / 77,5 | 32,1 / 29,8 / 34,4 | 31,7 / 29,3 / 34,3 |
|  | rdzeń | 59,2 / 54,8 / 63,8 | 79,5 / 77,5 / 81,9 | 32,0 / 30,0 / 34,0 | 31,8 / 29,6 / 34,1 |
| GZM | obszar pokryty | 40,0 / 37,5 / 42,5 | 62,0 / 59,5 / 64,6 | 21,7 / 21,2* / 22,2* | 22,4 / 21,7* / 23,1* |
|  | rdzeń | 45,6 / 43,8 / 47,6 | 67,7 / 66,3 / 69,3 | 22,3 / 21,8* / 22,7* | 23,8 / 23,3* / 24,4* |

\* różnica względem wszystkich mieszkańców nie do obrony przy tej dezagregacji (< 1 pkt albo niezgodny znak wariantu „środek komórki”); † różnica odporna: wartość dla wszystkich leży poza zakresem, jaki grupa mogłaby mieć przy dowolnym rozmieszczeniu wewnątrz kwadratów 1 km.

### 3.5 Grupy wieku a szkoły i SOR

Różnica (grupa minus wszyscy, pkt proc.) dla wszystkich progów i okien: szkoły, dzieci 0–14: w rdzeniach od −10,4 do −0,1 (mediana −2,0), w obszarach pokrytych od −12,1 do −1,0 (mediana −5,1); SOR, osoby 65+: w rdzeniach od −0,5 do +7,8 (mediana +2,1), w obszarach pokrytych od +0,9 do +10,1 (mediana +5,4). Z 112 porównań 18 jest „nie do obrony” (prawie wszystkie to rdzenie przy progu 45 min, gdzie i tak prawie wszyscy mieszczą się w czasie), a 22 jest „odpornych” (wartość dla wszystkich leży poza zakresem możliwym przy dowolnym rozmieszczeniu grupy w kwadratach 1 km): m.in. szkoły w 15–20 min dla dzieci w obszarach pokrytych Wrocławia (−12,1 i −11,4) i Poznania (−9,5 i −9,4), SOR w 30–45 min dla osób 65+ w obszarach pokrytych Poznania (+9,9 i +9,5) i Krakowa (+8,0 i +6,3). Tabela: `services_age_check.csv` (kolumny `supported`, `robust`).

## 3a. Czytanie krytyczne (sprawdzone na danych)

- **Wzór wiekowy jest wszędzie ten sam i zgodny z budową miast.** Osoby 65+ częściej niż ogół mieszkają przy częstej komunikacji i bliżej SOR, dzieci 0–14 rzadziej przy częstej komunikacji i dalej od szkół ponadpodstawowych. To różnice między kwadratami 1 km: starsi mieszkają w starszych, gęstych osiedlach śródmiejskich i blokowych, rodziny z dziećmi częściej w nowych osiedlach na obrzeżach i w gminach podmiejskich. Wartości „wszyscy” odtwarzają opublikowane liczby fazy 2 i 3. W Łodzi i GZM różnice w transport performance są mniejsze niż 1 pkt i ich nie interpretujemy.
- **Szkoły leżą blisko, komunikacja dodaje niewiele przy krótkich czasach.** Mediana czasu do najbliższej szkoły to 8–11 min w rdzeniach; odsetek „≤ 15 min” komunikacją jest w rdzeniach tylko o 0,8–5,2 pkt wyższy niż pieszo. Przy 30 min różnica rośnie (np. rdzeń Krakowa 95,1 wobec 85,8 pieszo). Wynik dotyczy najbliższej szkoły, nie szkoły wybranej.
- **GZM przy SOR: wynik zależy od rejestru, nie od komunikacji.** Tylko 13,4 % mieszkańców obszaru pokrytego ma SOR w 30 min (mediana 51 min). Przyczyna leży w danych o placówkach: w FUA GZM rejestr RPRM ma tylko 4 SOR dla dorosłych (Sosnowiec, Katowice-Ochojec, Zabrze, Dąbrowa Górnicza) na 2 mln mieszkańców, a w całym woj. śląskim 13 (wszystkie wpisy z 2026-05-05). Porównanie z OSM wskazuje m.in. szpital Megrez w Tychach i szpital w Knurowie jako szpitale z `emergency=yes` bez SOR w rejestrze. **Liczb SOR dla GZM nie należy porównywać z innymi miastami**, dopóki kompletność rejestru nie zostanie sprawdzona.
- **Błędne położenia znalezione i poprawione przed publikacją.** Pierwsza wersja dopasowania adresów przyjmowała wspólne dowolne słowo nazwy ulicy; SOR Szpitala Uniwersyteckiego w Krakowie (ul. Macieja Jakubowskiego 2, Prokocim) trafił wtedy na inną ulicę z imieniem „Macieja” w północnym Krakowie, a SOR w Gdańsku (Smoluchowskiego 17) i Szpitala Praskiego w Warszawie przesunęły się o 2–4 km. Objaw: ok. 4 % mieszkańców rdzenia Krakowa „bez SOR w 60 min”, w tym komórki na Kurdwanowie. Po poprawce (musi się zgadzać ostatnie słowo nazwy ulicy) komórka na Kurdwanowie ma SOR w 23 min, a w rdzeniu Krakowa bez SOR w 60 min zostaje 3,1 % (południowo-wschodnie obrzeża, np. Rybitwy, gdzie także do szkoły jest 54 min). Trójmiasto, Kraków i Warszawę policzono ponownie.
- **Kraków i Poznań, obszar pokryty: 20–27 % bez SOR w 60 min.** To mieszkańcy gmin podmiejskich w masce (dla obu miast maska obejmuje dużą część FUA), z których najbliższy SOR leży w mieście albo w innym mieście powiatowym; przy rdzeniach te odsetki spadają do 1–3 %.
- **Wieczór** (20–22) obniża odsetek „SOR w 30 min” o 0,2–5,4 pkt (najwięcej Trójmiasto, potem rdzeń Warszawy), a w GZM udział bez SOR w 60 min rośnie z 27,9 do 42,8 %.
- **Kontrola położenia.** Szkoły: mediana odległości punktu RSPO od najbliższego obiektu szkolnego w OSM 34 m, 92 % w promieniu 250 m (2 117 szkół w siedmiu obszarach); 69 szkół dalej niż 500 m, z czego przejrzane przypadki to szkoły wiejskie nieopisane w OSM, z punktem we właściwej miejscowości. SOR: 99 % punktów w promieniu 250 m od szpitala w OSM (punkt i tak pochodzi z OSM, więc to tylko kontrola, czy adres leży na terenie szpitala).

## 4. Ograniczenia

- **Lista placówek.** RSPO to rejestr szkół, nie budynków: zespół szkół ma jedną siedzibę, a filie i drugie budynki nie mają osobnych punktów. Rejestr RPRM w woj. śląskim ma tylko 13 SOR dla dorosłych (wszystkie wpisy z datą 2026-05-05); w FUA GZM leżą 4. Możliwe, że część wpisów jest niekompletna albo czasowo nieaktywna; porównanie z OSM wskazuje m.in. szpital Megrez w Tychach (oznaczony w OSM `emergency=yes`, bez SOR w rejestrze). Wynik GZM dla SOR może więc być zaniżony; nie sprawdzono tego w innych źródłach.
- **Wejścia.** Punkt szkoły to współrzędne siedziby z rejestru, punkt SOR to adres szpitala dopasowany w OSM; wejście na oddział może leżeć kilkaset metrów dalej (duże kampusy szpitalne: UCK Gdańsk, szpital uniwersytecki w Krakowie-Prokocimiu).
- **Godziny pracy i pojemność.** SOR działa całą dobę; szkoły liczymy jako dostępne o każdej porze okna 7–9. Nie uwzględniamy liczby miejsc, obłożenia SOR ani tego, czy szkoła przyjmie ucznia.
- **Rejony i wybór szkoły.** Szkoły ponadpodstawowe nie mają rejonów, a uczniowie wybierają szkoły według profilu i wyników; najbliższa szkoła rzadko jest szkołą, do której się chodzi. Miara mówi o tym, jak daleko jest jakakolwiek szkoła tego poziomu, nie o rzeczywistych dojazdach uczniów.
- **SOR a ratownictwo.** Dojazd komunikacją do SOR dotyczy pacjentów zgłaszających się sami i odwiedzających; w stanach nagłych liczy się czas dojazdu karetki, którego tu nie mierzymy.
- **Grupy wieku.** Grupa 0–14 obejmuje dzieci młodsze niż uczniowie szkół średnich (15–19); spis nie daje drobniejszego podziału na siatce. Ograniczenia dezagregacji: §2.1.
- **Maska i feedy.** Starty tylko w masce pokrycia GTFS; braki przewoźników (głównie busy) zaniżają wynik także wewnątrz maski. Czasy z rozkładu, bez opóźnień (RAPORT §16.2).

## 5. Nie zweryfikowano

- Kompletności rejestru RPRM (zwłaszcza woj. śląskie) i tego, czy każda jednostka „Aktywna” rzeczywiście przyjmuje pacjentów.
- Sposobu, w jaki RSPO wyznacza współrzędne siedziby; zgodność z OSM sprawdzono tylko odległością (niżej).
- Położenia wejść na SOR i do szkół.
- Licencji danych pobranych przez interfejs rspo.gov.pl i eksport RPRM (strony jej nie podają; przyjęto licencję wpisów tych rejestrów w dane.gov.pl).
- Czasów dojazdu do szkół i SOR w wyszukiwarce połączeń (nie porównywano).
- Ręcznie przejrzano tylko SOR w siedmiu obszarach (lista w `facilities.parquet`) i najdalsze punkty szkół; pozostałe dopasowania adresów sprawdzono wyłącznie automatycznie.
- Czy szpitale z listy `sor_osm_crosscheck.csv` (OSM `emergency=yes`, bez SOR w rejestrze w promieniu 500 m) mają SOR, czy tylko izbę przyjęć.
