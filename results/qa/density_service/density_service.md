# Gęstość zaludnienia a częstotliwość komunikacji

## Metoda

- Komórki 250 m z ludnością (siatka GHSL przeskalowana do NSP 2021), tylko wewnątrz maski pokrycia GTFS (wszystkie feedy, dzień 2026-11-25); komórki poza maską to brak danych, nie klasa i nie zero.
- Gęstość = ludność komórki / 0,0625 km². Klasy: D1 poniżej 5 000, D2 5 000–10 000, D3 od 10 000 os./km² (punkty podziału rampy gęstości na mapie). Do 2026-11-24 granicą D1 było 2 500; zmieniono ją po przeglądzie literatury, bo 2 500 na komórkach 250 m obejmuje zwykłą zabudowę jednorodzinną (sekcja o wrażliwości niżej).
- Kursy: najlepsza klasa odstępu w zasięgu 500 m pieszo po sieci OSM (średnia 6:00–20:00). S1: co 30 min, rzadziej lub brak; S2: co 15 lub 20 min; S3: co 5 lub 10 min.
- Udziały to odsetki ludności w masce w danej domenie (rdzeń albo obszar pokryty danymi w całym FUA); każda tabela sumuje się do 100 %. Wskaźniki główne dotyczą mieszkańców komórek od 5 000 os./km² (D2 i D3).
- Korelacja rang: Spearman ważony ludnością (średnie rangi ważone, potem ważona korelacja Pearsona rang) między gęstością a klasą odstępu uporządkowaną od „> 30” do „5”; dodatnia oznacza, że gęstsze komórki mają lepszą komunikację.

## Główne wskaźniki

### Rdzeń

| Aglomeracja | ≥ 5 000 os./km², bez kursów co ≤ 20 min (%) | ≥ 5 000 os./km², kursy co ≤ 10 min (%) | Korelacja rang | Pokrycie GTFS (% ludności) |
|---|---|---|---|---|
| Warszawa | 3,3 | 90,3 | 0,42 | 99,0 |
| Kraków | 6,0 | 77,9 | 0,37 | 96,5 |
| Wrocław | 6,7 | 88,3 | 0,46 | 97,9 |
| Poznań | 5,2 | 84,7 | 0,46 | 95,5 |
| Łódź | 6,9 | 84,8 | 0,45 | 96,6 |
| Trójmiasto | 10,0 | 70,7 | 0,35 | 95,9 |
| GZM | 18,0 | 59,4 | 0,42 | 97,9 |

### Obszar pokryty danymi

| Aglomeracja | ≥ 5 000 os./km², bez kursów co ≤ 20 min (%) | ≥ 5 000 os./km², kursy co ≤ 10 min (%) | Korelacja rang | Pokrycie GTFS (% ludności) |
|---|---|---|---|---|
| Warszawa | 7,4 | 82,2 | 0,71 | 82,5 |
| Kraków | 7,2 | 77,1 | 0,70 | 78,8 |
| Wrocław | 7,3 | 87,7 | 0,66 | 79,6 |
| Poznań | 11,8 | 72,4 | 0,67 | 85,5 |
| Łódź | 10,1 | 77,4 | 0,67 | 89,2 |
| Trójmiasto | 13,4 | 61,6 | 0,45 | 83,2 |
| GZM | 19,3 | 57,0 | 0,51 | 95,1 |

## Wrażliwość na próg gęstości

Te same dwa wskaźniki („bez kursów co ≤ 20 min” i „z kursami co ≤ 10 min” w zasięgu 500 m), policzone dla mieszkańców komórek 250 m o gęstości co najmniej T os./km², dla pięciu progów T. Przy T = 5 000 liczby są równe wskaźnikom głównym; próg 2 500 był progiem głównym do 2026-11-24 i zostaje jako wariant. Mapa i tabele 3 × 3 używają klas 5 000 / 10 000.

Skąd progi (jednostki się różnią, więc to punkty orientacyjne, nie równoważniki):

- 1 500: Eurostat, komórka centrum miejskiego w stopniu urbanizacji (komórki 1 km);
- 2 500: dawny próg tej warstwy (25 mieszkańców na ha w komórce 250 m; na siatce 1 km to mniej więcej 2 000);
- 5 000: próg główny od 2026-11-24; 50 mieszkańców na ha, częsta i atrakcyjna obsługa autobusowa wg Angela i in. (2011, za Oroszem), liczone na obwodach spisowych USA; 30 na ha to tam próg „podstawowej” obsługi autobusowej;
- 7 500: rząd wielkości progu opłacalności tramwaju/LRT wg Guerry i Cervero (2011), ok. 30 osób (mieszkańcy i miejsca pracy) na akr brutto wokół stacji; tu liczymy tylko mieszkańców;
- 10 000: górna klasa gęstości tej warstwy (100 na ha).

Progi z literatury dotyczą jednostek większych niż komórka 250 m (obwody spisowe, całe obszary), które zawierają ulice, parki i działki niemieszkalne. Komórka 250 m bywa prawie w całości mieszkaniowa, więc ta sama gęstość „obszarowa” daje w niej wyższą liczbę. Próg 2 500 na komórkach 250 m był więc łagodny: obejmował także zwykłą zabudowę jednorodzinną (25–40 mieszkańców na ha). Dlatego od 2026-11-24 wskaźniki główne i mapa używają progu 5 000.

### Rdzeń

**Bez kursów co ≤ 20 min w zasięgu 500 m, % mieszkańców komórek ≥ T**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 6,3 | 5,1 | 3,3 | 2,3 | 1,7 |
| Kraków | 9,5 | 8,0 | 6,0 | 5,5 | 3,5 |
| Wrocław | 11,3 | 10,0 | 6,7 | 3,9 | 2,9 |
| Poznań | 10,9 | 8,8 | 5,2 | 2,2 | 1,8 |
| Łódź | 11,2 | 9,6 | 6,9 | 5,6 | 3,8 |
| Trójmiasto | 14,1 | 12,8 | 10,0 | 7,0 | 6,3 |
| GZM | 25,4 | 22,8 | 18,0 | 14,6 | 12,2 |

**Z kursami co ≤ 10 min w zasięgu 500 m, % mieszkańców komórek ≥ T**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 85,6 | 87,3 | 90,3 | 92,9 | 93,8 |
| Kraków | 72,5 | 74,9 | 77,9 | 79,2 | 81,2 |
| Wrocław | 81,8 | 83,6 | 88,3 | 93,0 | 95,6 |
| Poznań | 74,5 | 77,7 | 84,7 | 89,0 | 88,9 |
| Łódź | 77,4 | 80,0 | 84,8 | 86,9 | 89,1 |
| Trójmiasto | 65,5 | 67,2 | 70,7 | 75,6 | 77,3 |
| GZM | 51,5 | 54,3 | 59,4 | 63,2 | 66,5 |

**Mieszkańcy komórek ≥ T, % ludności w masce**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 95,1 | 90,7 | 79,8 | 68,2 | 57,3 |
| Kraków | 92,1 | 86,5 | 73,2 | 58,9 | 43,9 |
| Wrocław | 93,6 | 88,0 | 71,3 | 55,8 | 40,4 |
| Poznań | 91,6 | 84,7 | 66,8 | 53,0 | 36,7 |
| Łódź | 91,8 | 85,9 | 72,2 | 59,5 | 45,5 |
| Trójmiasto | 92,9 | 87,2 | 72,4 | 53,7 | 33,7 |
| GZM | 89,2 | 81,1 | 63,1 | 46,8 | 30,4 |

**Mieszkańcy komórek ≥ T, tys.**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 1754 | 1673 | 1473 | 1258 | 1057 |
| Kraków | 703 | 661 | 558 | 450 | 335 |
| Wrocław | 616 | 579 | 469 | 367 | 266 |
| Poznań | 476 | 440 | 347 | 276 | 191 |
| Łódź | 591 | 553 | 465 | 383 | 293 |
| Trójmiasto | 665 | 624 | 518 | 384 | 241 |
| GZM | 1439 | 1309 | 1018 | 755 | 490 |

### Obszar pokryty danymi

**Bez kursów co ≤ 20 min w zasięgu 500 m, % mieszkańców komórek ≥ T**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 18,4 | 14,4 | 7,4 | 4,3 | 3,0 |
| Kraków | 16,2 | 11,2 | 7,2 | 6,1 | 3,8 |
| Wrocław | 16,4 | 12,6 | 7,3 | 4,1 | 2,9 |
| Poznań | 26,2 | 20,3 | 11,8 | 4,8 | 2,5 |
| Łódź | 19,5 | 16,2 | 10,1 | 7,7 | 5,5 |
| Trójmiasto | 20,2 | 18,3 | 13,4 | 9,2 | 7,7 |
| GZM | 28,2 | 24,6 | 19,3 | 15,5 | 12,9 |

**Z kursami co ≤ 10 min w zasięgu 500 m, % mieszkańców komórek ≥ T**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 69,1 | 73,7 | 82,2 | 87,8 | 90,1 |
| Kraków | 66,5 | 72,2 | 77,1 | 78,9 | 81,1 |
| Wrocław | 75,9 | 80,3 | 87,7 | 92,8 | 95,6 |
| Poznań | 54,2 | 60,3 | 72,4 | 81,3 | 82,9 |
| Łódź | 66,0 | 69,9 | 77,4 | 81,6 | 84,9 |
| Trójmiasto | 54,3 | 56,2 | 61,6 | 68,0 | 70,3 |
| GZM | 47,6 | 51,2 | 57,0 | 61,6 | 65,8 |

**Mieszkańcy komórek ≥ T, % ludności w masce**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 80,0 | 72,6 | 58,6 | 47,8 | 39,5 |
| Kraków | 70,4 | 63,0 | 51,8 | 41,2 | 30,5 |
| Wrocław | 82,4 | 74,9 | 58,7 | 45,8 | 33,0 |
| Poznań | 79,3 | 68,8 | 49,3 | 36,4 | 24,7 |
| Łódź | 78,7 | 71,9 | 57,9 | 46,2 | 34,7 |
| Trójmiasto | 90,1 | 83,8 | 66,6 | 47,6 | 29,2 |
| GZM | 83,8 | 74,8 | 57,0 | 41,7 | 26,6 |

**Mieszkańcy komórek ≥ T, tys.**

| Aglomeracja | ≥ 1 500 | ≥ 2 500 | ≥ 5 000 | ≥ 7 500 | ≥ 10 000 |
|---|---|---|---|---|---|
| Warszawa | 2302 | 2090 | 1685 | 1377 | 1135 |
| Kraków | 783 | 700 | 576 | 458 | 339 |
| Wrocław | 663 | 603 | 473 | 368 | 266 |
| Poznań | 661 | 573 | 411 | 303 | 206 |
| Łódź | 731 | 669 | 538 | 430 | 323 |
| Trójmiasto | 821 | 764 | 607 | 434 | 266 |
| GZM | 1640 | 1463 | 1116 | 816 | 520 |

Jak czytać:

- Rdzeń: udział bez kursów co ≤ 20 min wynosi 6,3–25,4 % przy 1 500 i 3,3–18,0 % przy 5 000. Kolejność miast od najgorszego: przy 2 500 GZM, Trójmiasto, Wrocław, Łódź, Poznań, Kraków, Warszawa; przy 5 000 GZM, Trójmiasto, Łódź, Wrocław, Kraków, Poznań, Warszawa.
- Obszar pokryty danymi: udział bez kursów co ≤ 20 min wynosi 16,2–28,2 % przy 1 500 i 7,2–19,3 % przy 5 000. Kolejność miast od najgorszego: przy 2 500 GZM, Poznań, Trójmiasto, Łódź, Warszawa, Wrocław, Kraków; przy 5 000 GZM, Trójmiasto, Poznań, Łódź, Warszawa, Wrocław, Kraków.
- W każdej aglomeracji i domenie im wyższy próg, tym mniejszy udział mieszkańców bez kursów co ≤ 20 min: gęstsze komórki są lepiej obsługiwane, zgodnie z dodatnią korelacją rang. Wynik przy dawnym progu 2 500 obejmuje więc także mieszkańców komórek o gęstości 25–50 na ha, czyli prawdopodobnie w dużej części zabudowy jednorodzinnej (typu zabudowy w tych komórkach nie sprawdzano), gdzie literatura nie oczekuje częstej komunikacji.
- Mieszkańcy, nie miejsca pracy: progi Guerry i Cervero oraz Newmana i Kenworthy'ego liczą też miejsca pracy, więc porównanie z nimi jest tylko orientacyjne.

## Tabele 3 × 3 (% ludności w masce)

Wiersze: gęstość (od najmniejszej), kolumny: kursy (od najgorszych do najlepszych).

### Rdzeń

**Warszawa**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 5,6 | 3,7 | 10,8 |
| 5 000–10 000 | 1,7 | 2,4 | 18,4 |
| ≥ 10 000 | 1,0 | 2,6 | 53,7 |

**Kraków**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 9,3 | 6,4 | 11,1 |
| 5 000–10 000 | 2,9 | 5,1 | 21,3 |
| ≥ 10 000 | 1,5 | 6,7 | 35,7 |

**Wrocław**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 9,3 | 3,8 | 15,6 |
| 5 000–10 000 | 3,6 | 2,9 | 24,4 |
| ≥ 10 000 | 1,2 | 0,6 | 38,6 |

**Poznań**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 11,3 | 8,5 | 13,4 |
| 5 000–10 000 | 2,8 | 3,3 | 23,9 |
| ≥ 10 000 | 0,6 | 3,4 | 32,7 |

**Łódź**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 10,5 | 5,8 | 11,4 |
| 5 000–10 000 | 3,2 | 2,8 | 20,7 |
| ≥ 10 000 | 1,7 | 3,2 | 40,5 |

**Trójmiasto**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 10,2 | 6,3 | 11,1 |
| 5 000–10 000 | 5,1 | 8,4 | 25,1 |
| ≥ 10 000 | 2,1 | 5,5 | 26,0 |

**GZM**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 19,0 | 8,4 | 9,5 |
| 5 000–10 000 | 7,7 | 7,7 | 17,3 |
| ≥ 10 000 | 3,7 | 6,5 | 20,2 |

### Obszar pokryty danymi

**Warszawa**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 27,7 | 5,5 | 8,3 |
| 5 000–10 000 | 3,1 | 3,4 | 12,6 |
| ≥ 10 000 | 1,2 | 2,7 | 35,5 |

**Kraków**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 34,4 | 5,9 | 8,0 |
| 5 000–10 000 | 2,6 | 3,5 | 15,2 |
| ≥ 10 000 | 1,1 | 4,6 | 24,7 |

**Wrocław**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 24,3 | 4,2 | 12,8 |
| 5 000–10 000 | 3,4 | 2,4 | 20,0 |
| ≥ 10 000 | 0,9 | 0,5 | 31,5 |

**Poznań**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 32,6 | 9,7 | 8,4 |
| 5 000–10 000 | 5,2 | 4,2 | 15,2 |
| ≥ 10 000 | 0,6 | 3,6 | 20,5 |

**Łódź**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 28,5 | 5,3 | 8,3 |
| 5 000–10 000 | 4,0 | 3,9 | 15,3 |
| ≥ 10 000 | 1,9 | 3,3 | 29,5 |

**Trójmiasto**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 16,6 | 7,8 | 9,0 |
| 5 000–10 000 | 6,7 | 10,3 | 20,5 |
| ≥ 10 000 | 2,2 | 6,4 | 20,5 |

**GZM**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 5 000 os./km² | 25,6 | 9,0 | 8,4 |
| 5 000–10 000 | 7,5 | 7,9 | 15,0 |
| ≥ 10 000 | 3,4 | 5,7 | 17,5 |

## Podział ludności na klasy (wszystkie aglomeracje razem)

### Rdzeń (6,76 mln mieszkańców w masce)

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min | Razem |
|---|---|---|---|---|
| < 5 000 os./km² | 11,0 | 6,0 | 11,3 | 28,3 |
| 5 000–10 000 | 4,0 | 4,8 | 20,4 | 29,2 |
| ≥ 10 000 | 1,9 | 4,2 | 36,4 | 42,5 |
| Razem | 16,9 | 15,0 | 68,1 | 100,0 |

### Obszar pokryty danymi (9,43 mln mieszkańców w masce)

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min | Razem |
|---|---|---|---|---|
| < 5 000 os./km² | 27,2 | 6,7 | 8,7 | 42,7 |
| 5 000–10 000 | 4,6 | 5,0 | 15,3 | 24,9 |
| ≥ 10 000 | 1,7 | 3,9 | 26,8 | 32,4 |
| Razem | 33,6 | 15,6 | 50,8 | 100,0 |

