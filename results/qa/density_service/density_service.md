# Gęstość zaludnienia a częstotliwość komunikacji

## Metoda

- Komórki 250 m z ludnością (siatka GHSL przeskalowana do NSP 2021), tylko wewnątrz maski pokrycia GTFS (wszystkie feedy, dzień 2026-11-25); komórki poza maską to brak danych, nie klasa i nie zero.
- Gęstość = ludność komórki / 0,0625 km². Klasy: D1 poniżej 2 500, D2 2 500–10 000, D3 od 10 000 os./km² (punkty podziału rampy gęstości na mapie).
- Kursy: najlepsza klasa odstępu w zasięgu 500 m pieszo po sieci OSM (średnia 6:00–20:00). S1: co 30 min, rzadziej lub brak; S2: co 15 lub 20 min; S3: co 5 lub 10 min.
- Udziały to odsetki ludności w masce w danej domenie (rdzeń albo obszar pokryty danymi w całym FUA); każda tabela sumuje się do 100 %. Gęsta zabudowa to D2 i D3.
- Korelacja rang: Spearman ważony ludnością (średnie rangi ważone, potem ważona korelacja Pearsona rang) między gęstością a klasą odstępu uporządkowaną od „> 30” do „5”; dodatnia oznacza, że gęstsze komórki mają lepszą komunikację.

## Główne wskaźniki

### Rdzeń

| Aglomeracja | Gęsta zabudowa bez kursów co ≤ 20 min (%) | Gęsta zabudowa z kursami co ≤ 10 min (%) | Korelacja rang | Pokrycie GTFS (% ludności) |
|---|---|---|---|---|
| Warszawa | 5,1 | 87,3 | 0,42 | 99,0 |
| Kraków | 8,0 | 74,9 | 0,37 | 96,5 |
| Wrocław | 10,0 | 83,6 | 0,46 | 97,9 |
| Poznań | 8,8 | 77,7 | 0,46 | 95,5 |
| Łódź | 9,6 | 80,0 | 0,45 | 96,6 |
| Trójmiasto | 12,8 | 67,2 | 0,35 | 95,9 |
| GZM | 22,8 | 54,3 | 0,42 | 97,9 |

### Obszar pokryty danymi

| Aglomeracja | Gęsta zabudowa bez kursów co ≤ 20 min (%) | Gęsta zabudowa z kursami co ≤ 10 min (%) | Korelacja rang | Pokrycie GTFS (% ludności) |
|---|---|---|---|---|
| Warszawa | 14,4 | 73,7 | 0,71 | 82,5 |
| Kraków | 11,2 | 72,2 | 0,70 | 78,8 |
| Wrocław | 12,6 | 80,3 | 0,66 | 79,6 |
| Poznań | 20,3 | 60,3 | 0,67 | 85,5 |
| Łódź | 16,2 | 69,9 | 0,67 | 89,2 |
| Trójmiasto | 18,3 | 56,2 | 0,45 | 83,2 |
| GZM | 24,6 | 51,2 | 0,51 | 95,1 |

## Tabele 3 × 3 (% ludności w masce)

Wiersze: gęstość (od najmniejszej), kolumny: kursy (od najgorszych do najlepszych).

### Rdzeń

**Warszawa**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 3,7 | 1,9 | 3,8 |
| 2 500–10 000 | 3,7 | 4,2 | 25,4 |
| ≥ 10 000 | 1,0 | 2,6 | 53,7 |

**Kraków**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 6,8 | 3,3 | 3,3 |
| 2 500–10 000 | 5,4 | 8,1 | 29,1 |
| ≥ 10 000 | 1,5 | 6,7 | 35,7 |

**Wrocław**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 5,2 | 1,7 | 5,0 |
| 2 500–10 000 | 7,6 | 5,0 | 35,0 |
| ≥ 10 000 | 1,2 | 0,6 | 38,6 |

**Poznań**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 7,3 | 3,8 | 4,1 |
| 2 500–10 000 | 6,8 | 8,0 | 33,2 |
| ≥ 10 000 | 0,6 | 3,4 | 32,7 |

**Łódź**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 7,3 | 2,9 | 3,9 |
| 2 500–10 000 | 6,5 | 5,7 | 28,2 |
| ≥ 10 000 | 1,7 | 3,2 | 40,5 |

**Trójmiasto**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 6,3 | 2,8 | 3,6 |
| 2 500–10 000 | 9,0 | 11,9 | 32,6 |
| ≥ 10 000 | 2,1 | 5,5 | 26,0 |

**GZM**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 11,9 | 4,0 | 3,0 |
| 2 500–10 000 | 14,8 | 12,1 | 23,9 |
| ≥ 10 000 | 3,7 | 6,5 | 20,2 |

### Obszar pokryty danymi

**Warszawa**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 21,6 | 3,0 | 2,9 |
| 2 500–10 000 | 9,3 | 5,9 | 18,0 |
| ≥ 10 000 | 1,2 | 2,7 | 35,5 |

**Kraków**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 31,0 | 3,6 | 2,4 |
| 2 500–10 000 | 5,9 | 5,8 | 20,8 |
| ≥ 10 000 | 1,1 | 4,6 | 24,7 |

**Wrocław**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 19,1 | 1,8 | 4,1 |
| 2 500–10 000 | 8,5 | 4,8 | 28,6 |
| ≥ 10 000 | 0,9 | 0,5 | 31,5 |

**Poznań**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 24,5 | 4,2 | 2,6 |
| 2 500–10 000 | 13,3 | 9,7 | 21,0 |
| ≥ 10 000 | 0,6 | 3,6 | 20,5 |

**Łódź**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 22,8 | 2,5 | 2,8 |
| 2 500–10 000 | 9,7 | 6,7 | 20,8 |
| ≥ 10 000 | 1,9 | 3,3 | 29,5 |

**Trójmiasto**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 10,2 | 3,1 | 2,9 |
| 2 500–10 000 | 13,1 | 14,9 | 26,6 |
| ≥ 10 000 | 2,2 | 6,4 | 20,5 |

**GZM**

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min |
|---|---|---|---|
| < 2 500 os./km² | 18,2 | 4,4 | 2,7 |
| 2 500–10 000 | 14,9 | 12,5 | 20,7 |
| ≥ 10 000 | 3,4 | 5,7 | 17,5 |

## Podział ludności na klasy (wszystkie aglomeracje razem)

### Rdzeń (6,76 mln mieszkańców w masce)

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min | Razem |
|---|---|---|---|---|
| < 2 500 os./km² | 7,0 | 2,9 | 3,7 | 13,6 |
| 2 500–10 000 | 8,0 | 7,9 | 28,0 | 43,9 |
| ≥ 10 000 | 1,9 | 4,2 | 36,4 | 42,5 |
| Razem | 16,9 | 15,0 | 68,1 | 100,0 |

### Obszar pokryty danymi (9,43 mln mieszkańców w masce)

| Gęstość | rzadziej niż co 20 min lub brak | co 11–20 min | co ≤ 10 min | Razem |
|---|---|---|---|---|
| < 2 500 os./km² | 21,1 | 3,3 | 2,9 | 27,2 |
| 2 500–10 000 | 10,8 | 8,5 | 21,2 | 40,4 |
| ≥ 10 000 | 1,7 | 3,9 | 26,8 | 32,4 |
| Razem | 33,6 | 15,6 | 50,8 | 100,0 |

