# Izochrony z wyliczonych punktów („skąd dojadę”)

Kod: `pipeline/isochrones.py` (isochrones-2026-11-24.1); pliki dla strony: `results/web/isochrones/<aglomeracja>.json`; tabele: `results/qa/isochrones/origins.csv`, `checks.csv`, `polygons.csv`; obrazy kontrolne `hub_<aglomeracja>.png` (pasma z węzła odczytane z pliku strony, linia przerywana: pieszo, szare kropki: wszystkie punkty startu).

## Metoda

- **Punkty startu.** Centrum i węzeł z `config.yaml` (w GZM i Trójmieście także wszystkie centra dodatkowe), 30 zespołów przystanków o największej liczbie odjazdów na godzinę w ciągu doby (warstwa łatwości przesiadki, z pominięciem leżących bliżej niż 300 m od centrum lub węzła) oraz regularna siatka: bloki 1 km w zamieszkanej części rdzenia miasta i 2 km na pozostałym obszarze FUA pokrytym danymi GTFS (blok liczy się, gdy mieszka w nim co najmniej 100 osób; punkt to środek najludniejszej komórki 250 m bloku). Tam, gdzie plik przekroczyłby ok. 4 MB, siatkę rozrzedzono (tabela niżej).
- **Czasy.** R5 v7.5.1 z parametrami wyniku głównego (`pipeline.access.make_task`): komunikacja + pieszo, środa 2026-11-25, mediana z odjazdów co minutę w oknie 7:00–9:00 (rano) i 20:00–22:00 (wieczorem), pieszo 5 km/h, dojście i odejście do 12 min, wszystkie feedy; w każdej komórce min(komunikacja, sam spacer), jak w wyniku głównym. Cele: wszystkie komórki 250 m obszaru FUA + 15 km z centrum w Polsce (oraz każda zamieszkana komórka, także nadmorska), również niezamieszkane (żeby izochrona nie miała dziur w parkach).
- **Wielokąty.** Komórki z czasem ≤ 15, 30, 45, 60 min (pieszo ≤ 15, 30) połączone w wielokąty, uproszczone o 50 m, współrzędne do 5 miejsc po przecinku (zapis „encoded polyline”). Pasma są narastające.
- **Mieszkańcy.** Siatka NSP 2021 na wzorze GHSL 2020 (250 m); podawane narastająco i w samym paśmie.

## Punkty, rozmiary, czas liczenia

| Aglomeracja | Punktów | węzeł / centra / przystanki / siatka | Siatka (rdzeń / reszta), km | Komórek celu | Plik, MB | Routing, s (4 wątki) |
|---|---:|---|---|---:|---:|---:|
| Trójmiasto | 427 | 1 / 2 / 30 / 394 | 1 / 2 | 82 128 | 2,95 | 46 |
| Poznań | 507 | 1 / 1 / 30 / 475 | 1 / 2 | 104 641 | 3,36 | 46 |
| Wrocław | 523 | 1 / 1 / 30 / 491 | 1 / 2 | 127 615 | 3,32 | 43 |
| Łódź | 689 | 1 / 1 / 30 / 657 | 1 / 2 | 108 925 | 3,65 | 53 |
| Kraków | 455 | 1 / 1 / 30 / 423 | 1 / 5 | 133 720 | 3,91 | 32 |
| GZM | 470 | 1 / 8 / 30 / 431 | 2 / 3 | 119 449 | 3,89 | 102 |
| Warszawa | 397 | 1 / 1 / 30 / 365 | 2 / 7 | 324 361 | 3,89 | 73 |

Wierzchołki na wielokąt pasma (wszystkie miasta): am 15 min: średnio 30, najwięcej 154; am 30 min: średnio 110, najwięcej 560; am 45 min: średnio 263, najwięcej 1 266; am 60 min: średnio 496, najwięcej 2 408; evening 15 min: średnio 28, najwięcej 118; evening 30 min: średnio 97, najwięcej 520; evening 45 min: średnio 224, najwięcej 1 164; evening 60 min: średnio 416, najwięcej 2 198; walk 15 min: średnio 24, najwięcej 50; walk 30 min: średnio 56, najwięcej 86.

## Kontrole

Porównanie z wynikiem fazy 3: liczba osiągalnych mieszkańców z punktu węzła (i centrum) i z komórki 250 m, w której ten punkt leży, w produkcyjnym przebiegu (start ze środka komórki, ten sam silnik i parametry, cele tylko w komórkach zamieszkanych). To porównanie jest informacyjne: punkt węzła leży do ok. 175 m od środka komórki i R5 dowiązuje go do innego odcinka ulicy, co przy 15 i 30 min potrafi zmienić wynik o kilkadziesiąt procent. Ścisłą kontrolą są punkty siatki, które startują dokładnie ze środka komórki, tak jak przebieg produkcyjny (wiersze „punkty siatki”). Transport performance z punktu porównano z opublikowaną średnią komórek ≤ 1 km od punktu (`metrics.csv`, domena hub_1km / centre_1km), także informacyjnie: to nie ta sama wielkość (średnia po ok. 50 komórkach).

| Aglomeracja | Kontrola | Nasze | Odniesienie | Stosunek | Wynik |
|---|---|---:|---:|---:|---|
| Trójmiasto | liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty) (0 naruszeń) |  |  |  | zgodne |
| Trójmiasto | komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano) (0 naruszeń) |  |  |  | zgodne |
| Trójmiasto | hub: osiągalni rano do 15 min vs wynik produkcyjny komórki E476750N721250 (inny punkt startu niż środek komórki) | 21 751,0 | 22 786,2 | 0,95 | informacyjnie |
| Trójmiasto | hub: osiągalni rano do 30 min vs wynik produkcyjny komórki E476750N721250 (inny punkt startu niż środek komórki) | 268 296,0 | 288 468,6 | 0,93 | informacyjnie |
| Trójmiasto | hub: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E476750N721250 (inny punkt startu niż środek komórki) | 213 843,0 | 223 702,5 | 0,96 | informacyjnie |
| Trójmiasto | hub: osiągalni rano do 45 min vs wynik produkcyjny komórki E476750N721250 (inny punkt startu niż środek komórki) | 540 791,0 | 551 285,1 | 0,98 | informacyjnie |
| Trójmiasto | hub: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E476750N721250 (inny punkt startu niż środek komórki) | 496 172,0 | 501 922,6 | 0,99 | informacyjnie |
| Trójmiasto | hub: osiągalni rano do 60 min vs wynik produkcyjny komórki E476750N721250 (inny punkt startu niż środek komórki) | 746 469,0 | 759 885,1 | 0,98 | informacyjnie |
| Trójmiasto | hub: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 65,2 | 39,7 | 1,64 | informacyjnie |
| Trójmiasto | hub: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 101,1 | 81,4 | 1,24 | informacyjnie |
| Trójmiasto | punkty siatki (am): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (394 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,0 | 0,5 |  | zgodne |
| Trójmiasto | punkty siatki (evening): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (394 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,0 | 0,5 |  | zgodne |
| Trójmiasto | pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy) (0 punktów z komórką dalej) |  |  |  | zgodne |
| Poznań | liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty) (0 naruszeń) |  |  |  | zgodne |
| Poznań | komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano) (0 naruszeń) |  |  |  | zgodne |
| Poznań | hub: osiągalni rano do 15 min vs wynik produkcyjny komórki E358000N506500 (inny punkt startu niż środek komórki) | 76 546,0 | 66 941,9 | 1,14 | informacyjnie |
| Poznań | hub: osiągalni rano do 30 min vs wynik produkcyjny komórki E358000N506500 (inny punkt startu niż środek komórki) | 378 238,0 | 371 873,2 | 1,02 | informacyjnie |
| Poznań | hub: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E358000N506500 (inny punkt startu niż środek komórki) | 376 613,0 | 367 777,9 | 1,02 | informacyjnie |
| Poznań | hub: osiągalni rano do 45 min vs wynik produkcyjny komórki E358000N506500 (inny punkt startu niż środek komórki) | 548 447,0 | 546 284,6 | 1,00 | informacyjnie |
| Poznań | hub: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E358000N506500 (inny punkt startu niż środek komórki) | 533 840,0 | 533 356,5 | 1,00 | informacyjnie |
| Poznań | hub: osiągalni rano do 60 min vs wynik produkcyjny komórki E358000N506500 (inny punkt startu niż środek komórki) | 697 574,0 | 699 232,6 | 1,00 | informacyjnie |
| Poznań | hub: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 68,8 | 51,5 | 1,34 | informacyjnie |
| Poznań | hub: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 80,0 | 73,5 | 1,09 | informacyjnie |
| Poznań | centre: osiągalni rano do 15 min vs wynik produkcyjny komórki E359500N506500 (inny punkt startu niż środek komórki) | 27 270,0 | 27 828,1 | 0,98 | informacyjnie |
| Poznań | centre: osiągalni rano do 30 min vs wynik produkcyjny komórki E359500N506500 (inny punkt startu niż środek komórki) | 274 085,0 | 277 705,8 | 0,99 | informacyjnie |
| Poznań | centre: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E359500N506500 (inny punkt startu niż środek komórki) | 249 372,0 | 249 962,0 | 1,00 | informacyjnie |
| Poznań | centre: osiągalni rano do 45 min vs wynik produkcyjny komórki E359500N506500 (inny punkt startu niż środek komórki) | 495 048,0 | 500 018,4 | 0,99 | informacyjnie |
| Poznań | centre: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E359500N506500 (inny punkt startu niż środek komórki) | 477 399,0 | 482 107,5 | 0,99 | informacyjnie |
| Poznań | centre: osiągalni rano do 60 min vs wynik produkcyjny komórki E359500N506500 (inny punkt startu niż środek komórki) | 645 628,0 | 647 533,8 | 1,00 | informacyjnie |
| Poznań | centre: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 52,0 | 51,5 | 1,01 | informacyjnie |
| Poznań | centre: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 71,1 | 71,6 | 0,99 | informacyjnie |
| Poznań | punkty siatki (am): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (475 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 0,3 |  | zgodne |
| Poznań | punkty siatki (evening): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (475 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 0,3 |  | zgodne |
| Poznań | pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy) (0 punktów z komórką dalej) |  |  |  | zgodne |
| Wrocław | liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty) (0 naruszeń) |  |  |  | zgodne |
| Wrocław | komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano) (0 naruszeń) |  |  |  | zgodne |
| Wrocław | hub: osiągalni rano do 15 min vs wynik produkcyjny komórki E362750N361750 (inny punkt startu niż środek komórki) | 19 743,0 | 55 206,2 | 0,36 | informacyjnie |
| Wrocław | hub: osiągalni rano do 30 min vs wynik produkcyjny komórki E362750N361750 (inny punkt startu niż środek komórki) | 254 367,0 | 340 998,0 | 0,75 | informacyjnie |
| Wrocław | hub: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E362750N361750 (inny punkt startu niż środek komórki) | 257 452,0 | 349 653,5 | 0,74 | informacyjnie |
| Wrocław | hub: osiągalni rano do 45 min vs wynik produkcyjny komórki E362750N361750 (inny punkt startu niż środek komórki) | 556 038,0 | 601 686,9 | 0,92 | informacyjnie |
| Wrocław | hub: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E362750N361750 (inny punkt startu niż środek komórki) | 554 342,0 | 600 391,5 | 0,92 | informacyjnie |
| Wrocław | hub: osiągalni rano do 60 min vs wynik produkcyjny komórki E362750N361750 (inny punkt startu niż środek komórki) | 674 905,0 | 694 066,3 | 0,97 | informacyjnie |
| Wrocław | hub: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 43,4 | 48,1 | 0,90 | informacyjnie |
| Wrocław | hub: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 78,1 | 78,1 | 1,00 | informacyjnie |
| Wrocław | centre: osiągalni rano do 15 min vs wynik produkcyjny komórki E362250N362000 (inny punkt startu niż środek komórki) | 27 630,0 | 30 425,0 | 0,91 | informacyjnie |
| Wrocław | centre: osiągalni rano do 30 min vs wynik produkcyjny komórki E362250N362000 (inny punkt startu niż środek komórki) | 290 153,0 | 291 890,2 | 0,99 | informacyjnie |
| Wrocław | centre: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E362250N362000 (inny punkt startu niż środek komórki) | 299 134,0 | 295 978,9 | 1,01 | informacyjnie |
| Wrocław | centre: osiągalni rano do 45 min vs wynik produkcyjny komórki E362250N362000 (inny punkt startu niż środek komórki) | 575 610,0 | 573 626,2 | 1,00 | informacyjnie |
| Wrocław | centre: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E362250N362000 (inny punkt startu niż środek komórki) | 572 797,0 | 570 117,9 | 1,00 | informacyjnie |
| Wrocław | centre: osiągalni rano do 60 min vs wynik produkcyjny komórki E362250N362000 (inny punkt startu niż środek komórki) | 681 313,0 | 682 324,8 | 1,00 | informacyjnie |
| Wrocław | centre: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 49,6 | 51,3 | 0,97 | informacyjnie |
| Wrocław | centre: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 80,4 | 79,1 | 1,02 | informacyjnie |
| Wrocław | punkty siatki (am): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (491 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 0,6 |  | zgodne |
| Wrocław | punkty siatki (evening): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (491 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 0,6 |  | zgodne |
| Wrocław | pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy) (0 punktów z komórką dalej) |  |  |  | zgodne |
| Łódź | liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty) (0 naruszeń) |  |  |  | zgodne |
| Łódź | komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano) (0 naruszeń) |  |  |  | zgodne |
| Łódź | hub: osiągalni rano do 15 min vs wynik produkcyjny komórki E531500N432500 (inny punkt startu niż środek komórki) | 58 121,0 | 48 101,2 | 1,21 | informacyjnie |
| Łódź | hub: osiągalni rano do 30 min vs wynik produkcyjny komórki E531500N432500 (inny punkt startu niż środek komórki) | 387 672,0 | 368 900,2 | 1,05 | informacyjnie |
| Łódź | hub: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E531500N432500 (inny punkt startu niż środek komórki) | 371 661,0 | 360 457,9 | 1,03 | informacyjnie |
| Łódź | hub: osiągalni rano do 45 min vs wynik produkcyjny komórki E531500N432500 (inny punkt startu niż środek komórki) | 628 541,0 | 615 444,9 | 1,02 | informacyjnie |
| Łódź | hub: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E531500N432500 (inny punkt startu niż środek komórki) | 605 563,0 | 599 951,2 | 1,01 | informacyjnie |
| Łódź | hub: osiągalni rano do 60 min vs wynik produkcyjny komórki E531500N432500 (inny punkt startu niż środek komórki) | 749 030,0 | 731 423,0 | 1,02 | informacyjnie |
| Łódź | hub: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 63,4 | 43,6 | 1,45 | informacyjnie |
| Łódź | hub: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 86,8 | 78,2 | 1,11 | informacyjnie |
| Łódź | centre: osiągalni rano do 15 min vs wynik produkcyjny komórki E531250N434500 (inny punkt startu niż środek komórki) | 51 617,0 | 51 617,0 | 1,00 | informacyjnie |
| Łódź | centre: osiągalni rano do 30 min vs wynik produkcyjny komórki E531250N434500 (inny punkt startu niż środek komórki) | 252 219,0 | 249 661,4 | 1,01 | informacyjnie |
| Łódź | centre: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E531250N434500 (inny punkt startu niż środek komórki) | 247 540,0 | 246 626,8 | 1,00 | informacyjnie |
| Łódź | centre: osiągalni rano do 45 min vs wynik produkcyjny komórki E531250N434500 (inny punkt startu niż środek komórki) | 555 383,0 | 555 382,7 | 1,00 | informacyjnie |
| Łódź | centre: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E531250N434500 (inny punkt startu niż środek komórki) | 539 990,0 | 539 929,5 | 1,00 | informacyjnie |
| Łódź | centre: osiągalni rano do 60 min vs wynik produkcyjny komórki E531250N434500 (inny punkt startu niż środek komórki) | 710 619,0 | 710 514,9 | 1,00 | informacyjnie |
| Łódź | centre: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 41,6 | 37,1 | 1,12 | informacyjnie |
| Łódź | centre: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 73,4 | 69,7 | 1,05 | informacyjnie |
| Łódź | punkty siatki (am): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (657 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 1,1 |  | zgodne |
| Łódź | punkty siatki (evening): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (657 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 1,1 |  | zgodne |
| Łódź | pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy) (0 punktów z komórką dalej) |  |  |  | zgodne |
| Kraków | liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty) (0 naruszeń) |  |  |  | zgodne |
| Kraków | komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano) (0 naruszeń) |  |  |  | zgodne |
| Kraków | hub: osiągalni rano do 15 min vs wynik produkcyjny komórki E567750N245000 (inny punkt startu niż środek komórki) | 44 907,0 | 30 839,6 | 1,46 | informacyjnie |
| Kraków | hub: osiągalni rano do 30 min vs wynik produkcyjny komórki E567750N245000 (inny punkt startu niż środek komórki) | 410 141,0 | 340 470,5 | 1,20 | informacyjnie |
| Kraków | hub: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E567750N245000 (inny punkt startu niż środek komórki) | 359 367,0 | 306 211,1 | 1,17 | informacyjnie |
| Kraków | hub: osiągalni rano do 45 min vs wynik produkcyjny komórki E567750N245000 (inny punkt startu niż środek komórki) | 740 711,0 | 719 137,5 | 1,03 | informacyjnie |
| Kraków | hub: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E567750N245000 (inny punkt startu niż środek komórki) | 714 436,0 | 690 310,2 | 1,03 | informacyjnie |
| Kraków | hub: osiągalni rano do 60 min vs wynik produkcyjny komórki E567750N245000 (inny punkt startu niż środek komórki) | 861 348,0 | 847 445,1 | 1,02 | informacyjnie |
| Kraków | hub: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 59,2 | 42,8 | 1,39 | informacyjnie |
| Kraków | hub: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 87,6 | 80,8 | 1,08 | informacyjnie |
| Kraków | centre: osiągalni rano do 15 min vs wynik produkcyjny komórki E567000N244000 (inny punkt startu niż środek komórki) | 28 301,0 | 27 431,1 | 1,03 | informacyjnie |
| Kraków | centre: osiągalni rano do 30 min vs wynik produkcyjny komórki E567000N244000 (inny punkt startu niż środek komórki) | 249 394,0 | 234 144,0 | 1,07 | informacyjnie |
| Kraków | centre: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E567000N244000 (inny punkt startu niż środek komórki) | 227 300,0 | 216 722,2 | 1,05 | informacyjnie |
| Kraków | centre: osiągalni rano do 45 min vs wynik produkcyjny komórki E567000N244000 (inny punkt startu niż środek komórki) | 682 110,0 | 682 816,8 | 1,00 | informacyjnie |
| Kraków | centre: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E567000N244000 (inny punkt startu niż środek komórki) | 665 614,0 | 667 635,9 | 1,00 | informacyjnie |
| Kraków | centre: osiągalni rano do 60 min vs wynik produkcyjny komórki E567000N244000 (inny punkt startu niż środek komórki) | 827 293,0 | 828 254,4 | 1,00 | informacyjnie |
| Kraków | centre: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 36,5 | 40,4 | 0,90 | informacyjnie |
| Kraków | centre: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 80,0 | 80,9 | 0,99 | informacyjnie |
| Kraków | punkty siatki (am): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (423 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,0 | 0,3 |  | zgodne |
| Kraków | punkty siatki (evening): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (423 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,0 | 0,3 |  | zgodne |
| Kraków | pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy) (0 punktów z komórką dalej) |  |  |  | zgodne |
| GZM | liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty) (0 naruszeń) |  |  |  | zgodne |
| GZM | komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano) (0 naruszeń) |  |  |  | zgodne |
| GZM | hub: osiągalni rano do 15 min vs wynik produkcyjny komórki E501500N265750 (inny punkt startu niż środek komórki) | 40 879,0 | 45 037,6 | 0,91 | informacyjnie |
| GZM | hub: osiągalni rano do 30 min vs wynik produkcyjny komórki E501500N265750 (inny punkt startu niż środek komórki) | 213 820,0 | 214 453,6 | 1,00 | informacyjnie |
| GZM | hub: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E501500N265750 (inny punkt startu niż środek komórki) | 185 687,0 | 183 998,1 | 1,01 | informacyjnie |
| GZM | hub: osiągalni rano do 45 min vs wynik produkcyjny komórki E501500N265750 (inny punkt startu niż środek komórki) | 674 993,0 | 666 584,7 | 1,01 | informacyjnie |
| GZM | hub: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E501500N265750 (inny punkt startu niż środek komórki) | 566 492,0 | 557 517,8 | 1,02 | informacyjnie |
| GZM | hub: osiągalni rano do 60 min vs wynik produkcyjny komórki E501500N265750 (inny punkt startu niż środek komórki) | 1 300 578,0 | 1 276 473,5 | 1,02 | informacyjnie |
| GZM | hub: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 46,7 | 36,1 | 1,30 | informacyjnie |
| GZM | hub: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 82,9 | 68,2 | 1,22 | informacyjnie |
| GZM | punkty siatki (am): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (431 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,0 | 0,4 |  | zgodne |
| GZM | punkty siatki (evening): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (431 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,0 | 0,4 |  | zgodne |
| GZM | pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy) (0 punktów z komórką dalej) |  |  |  | zgodne |
| Warszawa | liczba mieszkańców rośnie z czasem (wszystkie punkty i warianty) (0 naruszeń) |  |  |  | zgodne |
| Warszawa | komunikacja + pieszo nie gorsza niż pieszo (15 i 30 min, rano) (0 naruszeń) |  |  |  | zgodne |
| Warszawa | hub: osiągalni rano do 15 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 89 915,0 | 71 408,2 | 1,26 | informacyjnie |
| Warszawa | hub: osiągalni rano do 30 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 939 569,0 | 865 990,7 | 1,08 | informacyjnie |
| Warszawa | hub: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 888 397,0 | 811 301,0 | 1,10 | informacyjnie |
| Warszawa | hub: osiągalni rano do 45 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 1 707 764,0 | 1 673 470,5 | 1,02 | informacyjnie |
| Warszawa | hub: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 1 657 284,0 | 1 622 837,0 | 1,02 | informacyjnie |
| Warszawa | hub: osiągalni rano do 60 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 2 180 401,0 | 2 151 855,0 | 1,01 | informacyjnie |
| Warszawa | hub: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 80,2 | 57,3 | 1,40 | informacyjnie |
| Warszawa | hub: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (hub_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 97,0 | 88,3 | 1,10 | informacyjnie |
| Warszawa | centre: osiągalni rano do 15 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 84 771,0 | 71 408,2 | 1,19 | informacyjnie |
| Warszawa | centre: osiągalni rano do 30 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 902 917,0 | 865 990,7 | 1,04 | informacyjnie |
| Warszawa | centre: osiągalni wieczorem do 30 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 859 494,0 | 811 301,0 | 1,06 | informacyjnie |
| Warszawa | centre: osiągalni rano do 45 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 1 699 942,0 | 1 673 470,5 | 1,02 | informacyjnie |
| Warszawa | centre: osiągalni wieczorem do 45 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 1 645 493,0 | 1 622 837,0 | 1,01 | informacyjnie |
| Warszawa | centre: osiągalni rano do 60 min vs wynik produkcyjny komórki E637250N486750 (inny punkt startu niż środek komórki) | 2 157 139,0 | 2 151 855,0 | 1,00 | informacyjnie |
| Warszawa | centre: transport performance 30 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 77,7 | 56,9 | 1,36 | informacyjnie |
| Warszawa | centre: transport performance 45 min z punktu vs opublikowana średnia komórek ≤ 1 km (centre_1km) (inna wielkość: jeden punkt wobec średniej ok. 50 komórek) | 96,5 | 88,0 | 1,10 | informacyjnie |
| Warszawa | punkty siatki (am): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (365 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 1,0 |  | zgodne |
| Warszawa | punkty siatki (evening): osiągalni do 15–60 min = wynik produkcyjny tej samej komórki (365 punktów; kolumny: 95. centyl i maksimum różnicy względnej w %) | 0,1 | 1,0 |  | zgodne |
| Warszawa | pieszo 30 min: żadna komórka dalej niż 2,5 km w linii prostej (+ dowiązanie do ulicy) (0 punktów z komórką dalej) |  |  |  | zgodne |

Niezgodnych kontroli: 0 z 35 rozstrzygniętych.

## Ograniczenia

- Strona pokazuje izochronę **najbliższego wyliczonego punktu**, a nie klikniętego miejsca; karta podaje nazwę punktu i odległość od kliknięcia. Między punktami siatki (1–4 km) czas dojścia do przystanku może się wyraźnie różnić.
- Czasy rozkładowe (jeden dzień, środa), nie rzeczywiste: bez opóźnień i korków (RAPORT §16.2).
- Mediana z odjazdów co minutę: połowa odjazdów w oknie daje czas dłuższy niż pokazany.
- Komórki poza maską pokrycia GTFS są celami jak każde inne: brak kursów w danych wygląda tam jak brak zasięgu.
- Komórka liczy się w całości, gdy osiągnięto jej środek; granica wielokąta ma dokładność ok. 250 m (plus uproszczenie 50 m).
- Mieszkańcy z lat 2020–2021, rozkłady z 2026 r.

## Nie zweryfikowano

- Wyglądu na mapie (warstwy nie są jeszcze podłączone do strony) ani czasu wczytania plików na telefonie.
- Izochron z pojedynczych punktów nie porównano z wyszukiwarką połączeń (poza kontrolą fazy 3 dla par start–cel).
- Przyczyny różnic między punktem węzła lub centrum a środkiem jego komórki 250 m (tabela kontroli, wiersze informacyjne) nie badano; najpewniej R5 dowiązuje oba punkty do różnych odcinków ulic. Dotyczy to też każdego zespołu przystanków: jego punkt to środek zespołu, a nie konkretny peron.
