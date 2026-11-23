# Faza 1: miary gęstości (§4.1–4.4) i kontrola GHSL vs NSP (§7.1)

Wygenerowano: 2026-11-23 (`python -m pipeline.density_qa`; liczby z `pipeline.grid250`, `pipeline.density`,
`pipeline.density_control`). Wszystkie liczby w tym pliku są przepisywane przez kod z plików pośrednich, więc zgadzają się z
`results/metrics/metrics_density.csv` (po scaleniu: `metrics.csv`). Daty danych: **ludność NSP 2021 stan na 31.03.2021** (ludność rezydująca), **GHSL epoka 2020**
(dane modelowane, nie spisowe). Rozkładów jazdy ta faza nie używa (`timetable_date` = brak). Granice: Eurostat URAU 2021, GZM
w wariancie (a) (suma czterech FUA), Trójmiasto jako suma dwóch FUA. Aglomeracje oznaczone * są policentryczne lub liniowe
(GZM, Trójmiasto, Bydgoszcz–Toruń): miary jednocentrowe podajemy dla nich wyłącznie z zastrzeżeniem (brief §11).

## 1. Metoda w wersji wykonanej

Każdą regułę, której brief nie przesądza, trzeba było doprecyzować. Poniżej wszystkie takie decyzje.

### 1.1 Gęstość ważona populacją (PWD, §4.1)

- **Wzór:** gęstość ważona populacją: Σ pᵢ·dᵢ / Σ pᵢ, gdzie dᵢ = pᵢ / pole komórki i.
- **Siatka główna:** NSP 2021, siatka 1 km (EU LAEA, EPSG:3035, kody `CRS3035RES1000mN…E…`), pole `RES` (ludność rezydująca).
- **Przypisanie do domeny (FUA, rdzeń):** komórka należy do obszaru, gdy jej **centroid** (EPSG:2180) leży wewnątrz
  wielokąta, jak w fazie 0.
- **Pole komórki:** własne pole komórki w EPSG:3035 (układ równopolowy, natywny dla siatki). Dla komórek pełnych to dokładnie
  1 km²; dla przyciętych granicą państwa lub brzegiem morza jest mniejsze (w kraju 4 241 takich komórek z 28 753 osobami).
  W EPSG:2180 pola pełnych komórek różnią się od 1 km² o 0,02–0,2 % przez zniekształcenie odwzorowania, dlatego nie liczymy
  pola w EPSG:2180.
- **Sprawdzenie, czy wybór coś zmienia:** (a) pole nominalne 1 km² dla każdej komórki; (b) komórki przecięte granicą
  domeny ważone udziałem swojego pola w domenie, zamiast reguły centroidu. Największa zmiana PWD w którejkolwiek
  aglomeracji i domenie: **0,65 %**. Wybór nie wpływa na wynik w sposób istotny (tabela 2).
- **Pomocniczo, GHSL 250 m:** siatka 250 m w EPSG:2180 (patrz 1.2), komórka o środku w obszarze, d = p / 0,0625 km².
  Liczba jest z innej siatki i innego źródła, więc **nie porównujemy jej z PWD 1 km** (MAUP).
- **Kontrola źródła:** GHSL zsumowany do tych samych komórek spisowych 1 km (PWD „GHSL 1 km”). To oddziela różnicę
  źródła od różnicy siatki.
- **Gęstość brutto:** ludność NSP (reguła centroidu) / pole wielokąta w EPSG:3035. Służy tylko do kontrastu i zależy od
  rysunku granicy.

### 1.2 Siatka GHSL 250 m (produkt wielokrotnego użytku)

- **Plik:** `data/interim/grid250/ghs_pop_2020_250m_epsg2180.tif`, float32, nodata −1 (morze, poza źródłem).
- **Zasięg:** 2768 × 2576 komórek, EPSG:2180, krawędzie komórek w wielokrotnościach 250 m.
  Obejmuje Polskę i wszystkie FUA + 15 km.
- **Metoda:** z GHS-POP 100 m (Mollweide) przez `rasterio.warp.reproject` z `Resampling.sum` i `tolerance=0`.
  Przy domyślnym przybliżonym transformatorze GDAL (`tolerance=0.125` piksela) wynik miał względem dokładnej referencji
  dipole ±100 osób na komórkę (RMSE ok. 19 osób). Po przejściu na transformator dokładny:
  - RMSE: 0,2645 % średniej zamieszkanej komórki;
  - maks. różnica: 8,038 osoby;
  - referencja: okno 30 × 30 km w centrum Warszawy, każdy piksel źródła podzielony na 20 × 20 podpikseli;
  - różnica sum w oknie: -0,007025 osoby na 2 122 970.
- **Naiwne przypisanie środków pikseli** daje w tym samym oknie RMSE 33,09 %, czyli prążki.
  Obraz: `grid250_moire_warszawa.png`.
- **Sumy:** różnica 250 m względem 100 m (obie liczone regułą „środek komórki w wielokącie”) wynosi maks. 0,035 % na FUA
  i 0,23 % na rdzeń. Ta różnica to w całości przypisanie komórek brzegowych, nie utrata ludności.
- **Maska Polski:** `poland_mask_250m_epsg2180.tif`, środek komórki w komórce siatki spisowej.
- **Tabele zamieszkanych komórek:** `cells_<aglomeracja>.parquet`, z flagami FUA, rdzeń, bufor i Polska; to przyszłe
  pochodzenia dla dostępności (§4.6).

### 1.3 Profil gęstości (§4.2)

- **Dane:** GHS-POP 100 m. Pierścienie 1 km są za drobne na siatkę spisową 1 km, a GHSL to dane modelowane.
- **Odległość:** od środka piksela do centrum z `config.yaml`, w EPSG:2180. Pierścienie [k, k+1) km.
- **Gęstość pierścienia:** ludność / pole komórek pierścienia w domenie (lasy i wody wewnątrz domeny wliczone).
  Osobno podajemy pole zamieszkane (komórki z ludnością > 0) w plikach `data/interim/density/*_profile_*.csv`.
- **Wariant (i) „fua”:** tylko komórki o środku w FUA; udział w ludności FUA (GHSL). Pierścienie sięgają do najdalszej
  komórki FUA, więc krzywa kończy się na 100 %. Warszawa i inne duże FUA sięgają dalej niż 40 km: wtedy udział przy
  40 km jest mniejszy od 100 %.
- **Wariant (ii) „free”, bez granic:** wszystkie komórki o środku w Polsce w promieniu r. Udział liczony w ludności do
  40 km; w pliku jest też liczba bezwzględna. Ludność za granicą państwa jest pominięta (dotyczy Szczecina). Przy dużym r
  wchodzą sąsiednie ośrodki.
- **Kontrola spisem:** ta sama krzywa z komórek NSP 1 km (centroid), co 5 km (oraz 2 km), w obu wariantach (tabela 4).
- **Gradient Clarka:**
  - model: ln D = ln D0 − b·r, MNK na pierścieniach [1,2) … [24,25) km wariantu (i), z ludnością > 0 i co najmniej
    1 km² pola w domenie;
  - pierwszy kilometr podany osobno;
  - wynik tylko do tabel i QA (tier `table`/`qa`), nie na grafiki (brief §11).
- **GZM, Trójmiasto, Bydgoszcz–Toruń:** dodatkowy wariant „do najbliższego z N centrów” (centrum + `extra_centres`).
  To **inna miara**: osobne serie `*_nearest`, osobny plik wykresu.

### 1.4 Indeks dyspersji Bertauda ρ (§4.3)

- **Wzór:** ρ = [Σ pᵢ·distᵢ / Σ pᵢ] / (⅔·R), gdzie R = √(A/π), A = pole maski terenu zabudowanego netto.
- **Interpretacja (brief §4.3):** ρ = 1 oznacza walec o **równomiernej** gęstości na kole o polu A. To nie jest optimum.
  Miasta z gęstością malejącą od centrum mają ρ < 1; większe ρ oznacza ludność dalej od centrum niż przy równomiernym
  rozkładzie.
- **Maska, reguła precyzyjna:**
  1. Komórki GHS-BUILT-S 100 m (Mollweide; pole 0,01 km², odwzorowanie równopolowe) z udziałem zabudowy
     (wartość / 10 000 m²) ≥ X, środek komórki w domenie FUA. GHS-SMOD nie jest używany.
  2. **Spójność z rdzeniem:**
     - zarodki: komórki maski w promieniu 1 km od któregokolwiek centrum z `config.yaml` (centrum + `extra_centres`);
       gdyby żadna się nie kwalifikowała, promień rośnie co 1 km do 5 km (użyte promienie w tym przebiegu: 1 000 m);
     - łączność: 8-sąsiedztwo po dylatacji maski dyskiem o promieniu 3 komórek. Do maski wchodzą tylko oryginalne
       komórki ≥ X z klastrów zawierających zarodek. W efekcie **przerwa do ok. 600 m** w zabudowie (rzeka, tory,
       szeroka arteria) nie rozcina miasta.
     - Wybór 600 m: przy 200 m Wisła odcina w Warszawie całą Pragę, a Odra i Dąbie w Szczecinie Prawobrzeże. Już
       przy 600 m dołączają pojedyncze miasteczka połączone pasmem zabudowy (Police, Łańcut), a przy ≥ 1 km wiele
       wsi. Wrażliwość ρ na tę regułę: tabela 7.
  3. **Wody:** brief każe wyłączyć wody, ale osobnej warstwy wód nie używamy. Komórki wodne mają ~0 m² zabudowy, więc
     odpadają przy każdym progu z listy.
  4. **Domena:** FUA. Tabela 7 pokazuje, jaka część klastra wychodzi poza FUA, gdy tę samą regułę puścić na FUA + 15 km.
  5. **Rdzeń:** ta sama maska ograniczona do komórek o środku w rdzeniu.
- **Licznik:** tylko ludność GHS-POP 100 m z komórek maski; odległość od środka komórki do centrum w EPSG:2180.
- **Wartość „brak danych”:** gdy maska obejmuje < 5 % ludności domeny. Przy progu 50 % maska ma kilka km² wokół
  rynku i ρ traci sens; surowa wartość jest w nawiasie w tabelach.
- **Wariant „do najbliższego z N centrów”** (GZM, Trójmiasto, Bydgoszcz–Toruń; inna miara): odległość do najbliższego
  centrum, mianownik ⅔R jak w ρ (dosłownie wg briefu). Pomocniczo podajemy wariant z mianownikiem dla N równych kół
  (⅔·√(A/(Nπ))).

### 1.5 Gini i η (§4.4, tylko QA)

- **Domeny (stałe):** maska z §4.3 przy progu roboczym 20 % oraz koło 10 km wokół centrum
  (komórki w Polsce). Rozdzielczość 100 m (GHS-POP).
- **Wzory wg Volpati i Barthelemy (2018), arXiv:1804.00855:**
  - Gini: wzór (1) na liczbach ludności komórek, normalizowany przez G_max = (n−1)/n (wzory 2–3);
  - hotspoty: komórki powyżej wartości LouBar, czyli miejsca, w którym styczna do krzywej Lorenza w F = 1 przecina oś;
  - η: wzór (6), średnia odległość między hotspotami / średnia odległość między wszystkimi komórkami domeny.
- **Uproszczenie obliczeniowe:** obie średnie liczymy na stałej próbie losowej (ziarno 0, maks. 4000 komórek),
  żeby uniknąć ~10¹⁰ par.
- Próg LouBar i rozdzielczość są zapisane przy każdej liczbie (tabela 8, `metrics_density.csv`, kolumna `flag`).

## 2. Wyniki: gęstość ważona populacją (§4.1)

Tabela 1. PWD na siatce spisowej 1 km i gęstość brutto (os./km²; NSP 2021-03-31). Kolumny GHSL 250 m są z innej siatki
i nie porównuje się ich z PWD 1 km.

| Aglomeracja | Faza | Ludność FUA (NSP) | PWD FUA | PWD rdzeń | Brutto FUA | Brutto rdzeń | PWD GHSL 250 m FUA | PWD GHSL 250 m rdzeń |
|---|---|---|---|---|---|---|---|---|
| GZM * | 1 | 2 057 054 | 4 809 | 5 466 | 792 | 1 546 | 5 758 | 6 393 |
| Kraków | 1 | 1 411 779 | 4 580 | 7 505 | 421 | 2 427 | 4 524 | 7 004 |
| Łódź | 1 | 1 044 086 | 5 711 | 7 658 | 414 | 2 270 | 5 605 | 7 292 |
| Poznań | 1 | 974 744 | 4 421 | 6 538 | 427 | 2 091 | 4 656 | 6 557 |
| Trójmiasto * | 1 | 1 089 730 | 4 749 | 5 872 | 567 | 1 819 | 5 599 | 6 443 |
| Warszawa | 1 | 3 485 881 | 5 910 | 9 103 | 375 | 3 606 | 6 399 | 9 871 |
| Wrocław | 1 | 1 011 966 | 5 220 | 7 159 | 325 | 2 302 | 6 039 | 7 991 |
| Białystok | 2 | 448 491 | 4 733 | 6 999 | 116 | 2 760 | 5 244 | 7 432 |
| Bydgoszcz–Toruń * | 2 | 855 995 | 4 461 | 6 761 | 201 | 1 751 | 4 772 | 6 826 |
| Kielce | 2 | 386 456 | 3 140 | 6 397 | 166 | 1 635 | 3 069 | 5 610 |
| Lublin | 2 | 664 078 | 3 634 | 5 976 | 187 | 2 188 | 3 978 | 6 390 |
| Rzeszów | 2 | 459 020 | 2 087 | 4 377 | 236 | 1 468 | 3 103 | 5 697 |
| Szczecin | 2 | 512 051 | 6 506 | 7 810 | 376 | 1 279 | 6 681 | 7 951 |

Wielkości są zgodne z oczekiwaniami. PWD dużych miast na siatce 1 km wynosi kilka tysięcy os./km², od kilku do
kilkunastu razy więcej niż gęstość brutto FUA:

- Warszawa: rdzeń 9 103, FUA 5 910
  vs brutto FUA 375;
- PWD rdzenia > PWD FUA w każdej aglomeracji;
- GZM ma najmniejszą różnicę rdzeń–FUA, co pasuje do konurbacji bez wyraźnego śródmieścia.

Tabela 2. Odporność PWD na definicję pola komórki i przypisania (os./km²).

| Aglomeracja | Domena | PWD (główna) | pole nominalne 1 km² | różnica | komórki brzegowe ważone polem | różnica | komórki przecięte granicą obszaru | komórki przycięte granicą państwa | PWD z GHSL na tych samych komórkach | różnica |
|---|---|---|---|---|---|---|---|---|---|---|
| GZM * | FUA | 4 809 | 4 809 | 0,00 % | 4 809 | -0,00 % | 492 | 0 | 4 085 | -15,1 % |
| GZM * | CORE | 5 466 | 5 466 | 0,00 % | 5 470 | 0,08 % | 370 | 0 | 4 606 | -15,7 % |
| Kraków | FUA | 4 580 | 4 580 | 0,00 % | 4 577 | -0,06 % | 488 | 0 | 3 405 | -25,7 % |
| Kraków | CORE | 7 505 | 7 505 | 0,00 % | 7 514 | 0,13 % | 132 | 0 | 5 416 | -27,8 % |
| Łódź | FUA | 5 711 | 5 711 | 0,00 % | 5 710 | -0,02 % | 458 | 0 | 4 341 | -24,0 % |
| Łódź | CORE | 7 658 | 7 658 | 0,00 % | 7 654 | -0,05 % | 109 | 0 | 5 755 | -24,8 % |
| Poznań | FUA | 4 421 | 4 421 | 0,00 % | 4 424 | 0,06 % | 405 | 0 | 3 474 | -21,4 % |
| Poznań | CORE | 6 538 | 6 538 | 0,00 % | 6 522 | -0,25 % | 119 | 0 | 5 024 | -23,2 % |
| Trójmiasto * | FUA | 4 749 | 4 749 | -0,00 % | 4 742 | -0,17 % | 412 | 12 | 3 960 | -16,6 % |
| Trójmiasto * | CORE | 5 872 | 5 872 | -0,00 % | 5 870 | -0,03 % | 204 | 8 | 4 579 | -22,0 % |
| Warszawa | FUA | 5 910 | 5 910 | 0,00 % | 5 910 | 0,01 % | 1395 | 0 | 4 987 | -15,6 % |
| Warszawa | CORE | 9 103 | 9 103 | 0,00 % | 9 101 | -0,02 % | 149 | 0 | 7 769 | -14,7 % |
| Wrocław | FUA | 5 220 | 5 220 | 0,00 % | 5 220 | 0,02 % | 480 | 0 | 4 443 | -14,9 % |
| Wrocław | CORE | 7 159 | 7 159 | 0,00 % | 7 171 | 0,17 % | 112 | 0 | 6 025 | -15,8 % |
| Białystok | FUA | 4 733 | 4 733 | 0,00 % | 4 734 | 0,01 % | 559 | 7 | 3 904 | -17,5 % |
| Białystok | CORE | 6 999 | 6 999 | 0,00 % | 6 993 | -0,09 % | 63 | 0 | 5 679 | -18,9 % |
| Bydgoszcz–Toruń * | FUA | 4 461 | 4 461 | 0,00 % | 4 461 | -0,00 % | 600 | 0 | 3 477 | -22,1 % |
| Bydgoszcz–Toruń * | CORE | 6 761 | 6 761 | 0,00 % | 6 774 | 0,20 % | 181 | 0 | 5 197 | -23,1 % |
| Kielce | FUA | 3 140 | 3 140 | 0,00 % | 3 137 | -0,08 % | 432 | 0 | 2 327 | -25,9 % |
| Kielce | CORE | 6 397 | 6 397 | 0,00 % | 6 439 | 0,65 % | 70 | 0 | 4 529 | -29,2 % |
| Lublin | FUA | 3 634 | 3 634 | 0,00 % | 3 635 | 0,02 % | 520 | 0 | 3 036 | -16,5 % |
| Lublin | CORE | 5 976 | 5 976 | 0,00 % | 5 958 | -0,30 % | 84 | 0 | 5 097 | -14,7 % |
| Rzeszów | FUA | 2 087 | 2 087 | 0,00 % | 2 088 | 0,05 % | 359 | 0 | 2 405 | 15,2 % |
| Rzeszów | CORE | 4 377 | 4 377 | 0,00 % | 4 360 | -0,38 % | 78 | 0 | 4 621 | 5,6 % |
| Szczecin | FUA | 6 506 | 6 506 | 0,00 % | 6 515 | 0,14 % | 301 | 5 | 5 202 | -20,0 % |
| Szczecin | CORE | 7 810 | 7 810 | 0,00 % | 7 771 | -0,49 % | 150 | 0 | 6 408 | -17,9 % |

PWD z GHSL na tych samych komórkach 1 km jest systematycznie niższe od spisowego (o 15–29 %), z wyjątkiem Rzeszowa.
GHSL wygładza szczyty gęstości: rozdziela ludność według kubatury zabudowy, także niemieszkalnej (patrz §7.1).

## 3. Wyniki: profil gęstości (§4.2)

Tabela 3. Profil (GHS-POP 2020 100 m).

- r50: promień, w którym mieszka 50 % ludności;
- udział do 10 km: (i) w ludności FUA, (ii) w ludności do 40 km;
- Clark: tylko tabela/QA;
- ostatnie kolumny: maksymalna różnica krzywej skumulowanej GHSL względem NSP 1 km na krokach 2, 5, …, 40 km.

| Aglomeracja | r50 (i) FUA, km | r50 (ii), km | udział do 10 km (i) | udział do 10 km (ii) | gęstość 0–1 km | Clark b, 1/km | Clark D0 | R² | maks. różnica GHSL–NSP (i), pp | (ii), pp |
|---|---|---|---|---|---|---|---|---|---|---|
| GZM * | 13,10 | 17,40 | 35,1 % | 24,6 % | 10 825 | 0,08246 | 3 700 | 0,8304 | 1,122 | 0,9763 |
| Kraków | 8,553 | 12,71 | 55,1 % | 43,3 % | 13 770 | 0,1684 | 5 483 | 0,8889 | 3,465 | 2,635 |
| Łódź | 6,420 | 8,331 | 67,0 % | 55,9 % | 14 343 | 0,2125 | 6 898 | 0,9376 | 2,525 | 2,055 |
| Poznań | 7,018 | 9,345 | 67,9 % | 52,8 % | 11 602 | 0,1878 | 5 025 | 0,9157 | 3,270 | 2,761 |
| Trójmiasto * | 12,85 | 16,93 | 42,1 % | 35,1 % | 7 787 | 0,1065 | 2 791 | 0,7551 | 3,128 | 2,582 |
| Warszawa | 10,96 | 9,744 | 46,3 % | 51,3 % | 15 134 | 0,1665 | 12 000 | 0,9571 | 1,144 | 1,407 |
| Wrocław | 5,902 | 7,897 | 66,9 % | 55,4 % | 12 733 | 0,2061 | 5 099 | 0,8522 | 4,473 | 3,554 |
| Białystok | 4,109 | 4,820 | 74,2 % | 65,6 % | 9 566 | 0,2117 | 1 851 | 0,6809 | 2,344 | 2,728 |
| Bydgoszcz–Toruń * | 19,10 | 12,89 | 39,1 % | 44,4 % | 10 126 | 0,1768 | 2 310 | 0,7971 | 3,028 | 2,687 |
| Kielce | 7,524 | 22,55 | 57,3 % | 32,6 % | 8 767 | 0,1488 | 1 290 | 0,7342 | 2,083 | 1,665 |
| Lublin | 6,976 | 10,08 | 56,4 % | 49,7 % | 8 742 | 0,1590 | 2 054 | 0,6522 | 1,495 | 1,449 |
| Rzeszów | 7,684 | 22,55 | 55,2 % | 30,0 % | 7 515 | 0,1203 | 1 105 | 0,5465 | 7,355 | 3,288 |
| Szczecin | 4,597 | 7,760 | 77,0 % | 58,4 % | 14 097 | 0,1776 | 2 759 | 0,8245 | 3,523 | 2,964 |

Tabela 4. Kontrola krzywej skumulowanej (i) spisem: udział ludności FUA w promieniu r, GHSL / NSP (%).

| Aglomeracja | do 2 km: GHSL / NSP, % | do 5 km: GHSL / NSP, % | do 10 km: GHSL / NSP, % | do 20 km: GHSL / NSP, % | do 30 km: GHSL / NSP, % |
|---|---|---|---|---|---|
| GZM * | 3,9 / 3,6 | 9,3 / 9,9 | 35,1 / 34,0 | 78,9 / 79,6 | 95,2 / 95,6 |
| Kraków | 9,0 / 5,5 | 28,2 / 25,9 | 55,1 / 57,4 | 77,2 / 78,1 | 94,8 / 95,2 |
| Łódź | 12,7 / 10,2 | 38,0 / 36,1 | 67,0 / 67,5 | 89,2 / 89,3 | 98,2 / 98,1 |
| Poznań | 8,8 / 6,2 | 35,3 / 38,5 | 67,9 / 67,0 | 90,3 / 90,3 | 98,5 / 98,5 |
| Trójmiasto * | 6,8 / 3,7 | 23,8 / 23,0 | 42,1 / 44,4 | 69,8 / 71,0 | 90,4 / 91,5 |
| Warszawa | 4,0 / 3,2 | 18,8 / 17,7 | 46,3 / 45,7 | 69,6 / 70,6 | 82,4 / 83,4 |
| Wrocław | 14,9 / 10,5 | 41,9 / 38,9 | 66,9 / 66,0 | 81,9 / 83,4 | 94,9 / 95,6 |
| Białystok | 19,2 / 20,7 | 58,2 / 57,8 | 74,2 / 74,8 | 81,5 / 83,8 | 93,2 / 94,1 |
| Bydgoszcz–Toruń * | 11,4 / 10,1 | 27,9 / 27,6 | 39,1 / 36,0 | 50,8 / 51,0 | 63,1 / 63,0 |
| Kielce | 18,7 / 16,7 | 44,1 / 44,2 | 57,3 / 56,4 | 82,2 / 82,8 | 95,8 / 96,1 |
| Lublin | 11,3 / 11,0 | 42,4 / 42,2 | 56,4 / 56,8 | 72,1 / 73,6 | 93,3 / 93,8 |
| Rzeszów | 16,6 / 14,3 | 44,6 / 37,3 | 55,2 / 53,8 | 82,8 / 84,0 | 99,2 / 99,2 |
| Szczecin | 20,4 / 19,1 | 54,1 / 52,4 | 77,0 / 79,1 | 94,3 / 95,8 | 99,9 / 99,9 |

Krzywe są monotoniczne z konstrukcji (sumy skumulowane nieujemnych liczb). W wariancie (i) każda kończy się na 100,0 %
(sprawdzone w `density_qa`, asercja).

Zgodność GHSL ze spisem w kształcie krzywej jest dobra: różnice do ok. 3–4 pp. Odstają dwa przypadki:

- **Rzeszów, różnica 7,355 pp przy 5 km:** GHSL koncentruje ludność
  w centrum Rzeszowa bardziej niż spis (patrz §7.1, rdzeń Rzeszowa +13,5 %);
- **pierwsze 2 km:** krok 2 km jest porównywalny z rozmiarem komórki spisowej, więc różnica tam jest częściowo
  artefaktem przypisania komórek 1 km do pierścienia.

**Rekomendacja wariantu na grafikę: (ii) bez granic, jako liczba osób w promieniu r (oś Y w tysiącach lub milionach),
dla pięciu jednocentrowych aglomeracji fazy 1.** Uzasadnienie:

1. **Wariant (i) zmienia ranking przez rysunek granicy FUA, nie przez formę miasta.** Duża FUA Warszawy (9 296 km²,
   sięga poza 40 km) daje jej najniższy udział do 10 km (46,3 % w (i)),
   choć w (ii) jest w środku stawki (51,3 %). Mała FUA Szczecina działa
   odwrotnie. Brief (§2) każe unikać wyników, które mierzą przebieg granicy.
2. **Wariant (ii) da się sprawdzić spisem** bez żadnej granicy. Różnice z NSP 1 km są tu mniejsze niż w (i).
3. **Udział w (ii) wymaga arbitralnego mianownika** (ludność do 40 km), który w miastach otoczonych gęstą wsią
   (Rzeszów, Kielce: r50 ok. 22 km) mierzy region, a nie miasto. Liczba bezwzględna nie ma tego problemu, a kształt
   krzywej nadal widać.

Jeżeli grafika ma pokazać udział (jak w briefie), proponujemy (ii) z mianownikiem „do 40 km” z adnotacją albo (i)
z wyraźną informacją, że udział zależy od zasięgu FUA. Dane obu wariantów są w `results/charts/profile_cumulative_*.json`.
GZM, Trójmiasto i Bydgoszcz–Toruń idą osobnym panelem (osobny plik), z wariantem „do najbliższego z N centrów”
oznaczonym jako inna miara.

## 4. Wyniki: indeks dyspersji Bertauda ρ (§4.3)

Tabela 5. **ρ (FUA) dla każdego progu z `built_up_threshold_sensitivity`**, pole maski i udział ludności FUA (GHSL)
w masce. To tabela do decyzji o progu (brief §12.4). Próg roboczy: 20 %.

| Aglomeracja | ρ FUA, ≥ 10 % | ρ FUA, ≥ 20 % | ρ FUA, ≥ 30 % | ρ FUA, ≥ 50 % | maska ≥ 10 %: km² / udział ludności FUA | maska ≥ 20 %: km² / udział ludności FUA | maska ≥ 30 %: km² / udział ludności FUA | maska ≥ 50 %: km² / udział ludności FUA |
|---|---|---|---|---|---|---|---|---|
| GZM * | 1,675 | 2,123 | 2,976 | brak danych (12,62) | 446 / 88 % | 264 / 69 % | 120 / 36 % | 6 / 1 % |
| Kraków | 1,348 | 1,455 | 1,846 | brak danych (6,100) | 395 / 81 % | 133 / 52 % | 46 / 27 % | 3 / 1 % |
| Łódź | 1,201 | 1,386 | 1,809 | brak danych (4,363) | 267 / 86 % | 130 / 67 % | 62 / 40 % | 1 / 1 % |
| Poznań | 1,165 | 1,320 | 1,636 | brak danych (4,842) | 245 / 81 % | 151 / 67 % | 77 / 42 % | 2 / 1 % |
| Trójmiasto * | 2,450 | 3,138 | 4,300 | brak danych (12,60) | 235 / 89 % | 141 / 73 % | 73 / 46 % | 5 / 2 % |
| Warszawa | 1,167 | 1,397 | 1,602 | brak danych (4,041) | 865 / 85 % | 446 / 68 % | 195 / 41 % | 3 / 1 % |
| Wrocław | 1,049 | 1,227 | 1,531 | brak danych (3,895) | 176 / 74 % | 111 / 62 % | 60 / 41 % | 3 / 2 % |
| Białystok | 1,042 | 1,218 | 1,519 | brak danych (5,666) | 82 / 72 % | 51 / 63 % | 28 / 44 % | 1 / 1 % |
| Bydgoszcz–Toruń * | 4,046 | 5,182 | 6,526 | brak danych (33,13) | 186 / 72 % | 83 / 52 % | 50 / 38 % | 3 / 2 % |
| Kielce | 1,505 | 1,461 | 1,505 | brak danych (7,158) | 122 / 70 % | 48 / 48 % | 16 / 26 % | 0 / 0 % |
| Lublin | 1,407 | 1,381 | 1,763 | brak danych (5,467) | 180 / 69 % | 60 / 47 % | 32 / 31 % | 0 / 0 % |
| Rzeszów | 1,545 | 1,517 | 1,507 | brak danych (4,749) | 182 / 76 % | 59 / 46 % | 20 / 24 % | 2 / 1 % |
| Szczecin | 1,542 | 1,676 | 1,633 | brak danych (3,987) | 98 / 85 % | 57 / 66 % | 20 / 30 % | 3 / 3 % |

Tabela 5a. ρ dla rdzenia (ta sama maska ograniczona do rdzenia).

| Aglomeracja | ρ rdzeń, ≥ 10 % | ρ rdzeń, ≥ 20 % | ρ rdzeń, ≥ 30 % | ρ rdzeń, ≥ 50 % | udział ludności rdzenia w masce ≥ 10 % | udział ludności rdzenia w masce ≥ 20 % | udział ludności rdzenia w masce ≥ 30 % | udział ludności rdzenia w masce ≥ 50 % |
|---|---|---|---|---|---|---|---|---|
| GZM * | 1,800 | 2,204 | 3,080 | brak danych (12,62) | 93 % | 76 % | 42 % | 1 % |
| Kraków | 1,178 | 1,392 | 1,832 | brak danych (6,100) | 94 % | 78 % | 47 % | 2 % |
| Łódź | 1,046 | 1,207 | 1,509 | brak danych (4,363) | 95 % | 82 % | 52 % | 1 % |
| Poznań | 1,107 | 1,261 | 1,566 | brak danych (4,831) | 96 % | 83 % | 56 % | 2 % |
| Trójmiasto * | 2,365 | 2,816 | 3,747 | brak danych (12,64) | 95 % | 80 % | 53 % | 3 % |
| Warszawa | 1,054 | 1,205 | 1,514 | brak danych (4,045) | 97 % | 87 % | 59 % | 1 % |
| Wrocław | 1,109 | 1,270 | 1,573 | brak danych (3,895) | 96 % | 84 % | 57 % | 3 % |
| Białystok | 1,110 | 1,257 | 1,556 | brak danych (5,666) | 97 % | 88 % | 65 % | 1 % |
| Bydgoszcz–Toruń * | 4,668 | 5,241 | 6,458 | brak danych (33,13) | 96 % | 82 % | 62 % | 2 % |
| Kielce | 1,067 | 1,222 | 1,507 | brak danych (7,158) | 96 % | 83 % | 53 % | 0 % |
| Lublin | 1,064 | 1,225 | 1,544 | brak danych (5,467) | 95 % | 83 % | 57 % | 0 % |
| Rzeszów | 0,9367 | 1,131 | 1,493 | brak danych (4,749) | 95 % | 80 % | 50 % | 3 % |
| Szczecin | 1,283 | 1,499 | 1,636 | brak danych (3,978) | 92 % | 77 % | 38 % | 3 % |

Tabela 6. Ranking miast jednocentrowych według ρ FUA przy każdym progu i zgodność rankingów.

| Próg | Miasta jednocentrowe od najniższego ρ FUA |
|---|---|
| ≥ 10 % | Białystok 1,042, Wrocław 1,049, Poznań 1,165, Warszawa 1,167, Łódź 1,201, Kraków 1,348, Lublin 1,407, Kielce 1,505, Szczecin 1,542, Rzeszów 1,545 |
| ≥ 20 % | Białystok 1,218, Wrocław 1,227, Poznań 1,320, Lublin 1,381, Łódź 1,386, Warszawa 1,397, Kraków 1,455, Kielce 1,461, Rzeszów 1,517, Szczecin 1,676 |
| ≥ 30 % | Kielce 1,505, Rzeszów 1,507, Białystok 1,519, Wrocław 1,531, Warszawa 1,602, Szczecin 1,633, Poznań 1,636, Lublin 1,763, Łódź 1,809, Kraków 1,846 |
| ≥ 50 % | brak danych |

| Progi | Miast | Korelacja Spearmana rankingów ρ FUA |
|---|---|---|
| 10 % vs 20 % | 10 | 0,9030 |
| 10 % vs 30 % | 10 | -0,09091 |
| 20 % vs 30 % | 10 | -0,09091 |

**Jak czytać wartości:**

- **ρ > 1 prawie wszędzie; wyjątki (ρ < 1): Rzeszów core przy 10 %.** To nie jest błąd liczenia; sprawdzone (sekcja 8). Maska jest
  „netto”: zawiera tylko komórki 100 m z wysokim udziałem powierzchni budynków. W polskich miastach parki, doliny rzek,
  tereny kolejowe i luźna zabudowa blokowa wypadają z maski. Pole A jest więc małe w stosunku do rozpiętości miasta, a
  maska ma kształt gwiazdy (pasma wzdłuż dróg), nie koła. Dla kształtu niekołowego średnia odległość od centrum jest
  większa niż ⅔R nawet przy równomiernej gęstości.
- **Poziom ρ nie jest porównywalny z wartościami Bertauda i Malpezziego (2003)**, którzy liczyli teren zabudowany
  inaczej (z map i zdjęć, z małymi terenami otwartymi). Nie sprawdzaliśmy ich liczb dla polskich miast.
- **Próg zmienia poziom ρ i, powyżej 20 %, także kolejność miast:**
  - 10 %: maska 82–865 km², 69–89 % ludności FUA;
  - 20 %: 48–446 km², 46–73 %;
  - 30 %: 16–195 km², tylko 24–46 %;
  - 50 %: 0–6 km² i < 5 % ludności, więc ρ to „brak danych”;
  - ranking miast jednocentrowych przy 10 % i 20 % jest zgodny (Spearman 0,9030),
    przy 30 % się rozsypuje (Spearman z 20 %: -0,09091). Maska 30 % to głównie
    śródmieścia i strefy przemysłowe, a nie miejsca, gdzie mieszka większość ludzi.
- **Rekomendacja agenta (do decyzji właściciela):** próg 10 % albo 20 %, nie 30 % ani 50 %. 10 % obejmuje większość
  mieszkańców, więc licznik ρ opiera się na typowym mieszkańcu, a nie na wybranej części. Kolejność przy 10 % i 20 % jest
  w przybliżeniu ta sama, więc wybór między nimi zmienia głównie poziom.
- **Rdzeń:** ρ rdzenia jest zwykle nieco niższe niż ρ FUA. Maska rdzenia obejmuje
  76–97 % jego ludności przy progach 10–20 %.

Tabela 7. Wrażliwość ρ FUA (próg 20 %) na tolerancję luki w regule spójności (w nawiasie: pole maski) oraz
część klastra, która wyszłaby poza FUA przy domenie FUA + 15 km.

| Aglomeracja | luka ≤ 0 m | luka ≤ 200 m | luka ≤ 400 m | luka ≤ 600 m | luka ≤ 800 m | luka ≤ 1000 m | luka ≤ 1400 m | część klastra poza FUA (FUA + 15 km) |
|---|---|---|---|---|---|---|---|---|
| GZM * | 3,444 (84 km²) | 2,180 (219 km²) | 2,112 (242 km²) | 2,123 (264 km²) | 2,092 (281 km²) | 2,090 (284 km²) | 2,086 (290 km²) | 2,8 % |
| Kraków | 1,582 (30 km²) | 1,407 (87 km²) | 1,437 (115 km²) | 1,455 (133 km²) | 1,506 (147 km²) | 1,564 (160 km²) | 1,746 (183 km²) | 0,0 % |
| Łódź | 1,262 (57 km²) | 1,399 (114 km²) | 1,389 (127 km²) | 1,386 (130 km²) | 1,465 (139 km²) | 1,464 (141 km²) | 1,537 (162 km²) | 0,0 % |
| Poznań | 1,702 (42 km²) | 1,284 (125 km²) | 1,304 (145 km²) | 1,320 (151 km²) | 1,421 (172 km²) | 1,422 (176 km²) | 1,504 (196 km²) | 0,0 % |
| Trójmiasto * | 3,378 (63 km²) | 2,815 (96 km²) | 3,423 (119 km²) | 3,138 (141 km²) | 3,108 (145 km²) | 3,083 (148 km²) | 3,058 (151 km²) | 5,6 % |
| Warszawa | 1,419 (107 km²) | 1,433 (187 km²) | 1,234 (375 km²) | 1,397 (446 km²) | 1,404 (492 km²) | 1,423 (520 km²) | 1,427 (531 km²) | 0,2 % |
| Wrocław | 1,257 (38 km²) | 1,224 (85 km²) | 1,217 (92 km²) | 1,227 (111 km²) | 1,224 (117 km²) | 1,291 (123 km²) | 1,418 (148 km²) | 0,0 % |
| Białystok | 1,192 (22 km²) | 1,231 (43 km²) | 1,202 (48 km²) | 1,218 (51 km²) | 1,227 (54 km²) | 1,227 (55 km²) | 1,263 (59 km²) | 0,0 % |
| Bydgoszcz–Toruń * | 6,805 (48 km²) | 5,322 (72 km²) | 5,235 (81 km²) | 5,182 (83 km²) | 5,104 (96 km²) | 4,817 (108 km²) | 4,610 (133 km²) | 0,0 % |
| Kielce | 1,199 (21 km²) | 1,186 (27 km²) | 1,313 (40 km²) | 1,461 (48 km²) | 1,611 (57 km²) | 1,681 (60 km²) | 1,927 (70 km²) | 0,0 % |
| Lublin | 1,280 (36 km²) | 1,211 (49 km²) | 1,388 (58 km²) | 1,381 (60 km²) | 1,376 (63 km²) | 1,396 (67 km²) | 1,896 (94 km²) | 0,0 % |
| Rzeszów | 1,210 (24 km²) | 1,126 (33 km²) | 1,155 (48 km²) | 1,517 (59 km²) | 1,555 (67 km²) | 1,563 (69 km²) | 1,904 (83 km²) | 2,0 % |
| Szczecin | 1,299 (28 km²) | 1,262 (39 km²) | 1,258 (41 km²) | 1,676 (57 km²) | 1,675 (59 km²) | 1,680 (60 km²) | 1,845 (66 km²) | 0,9 % |

Reguła spójności przesuwa ρ o kilka do kilkudziesięciu procent, a kolejność miast nie jest na nią w pełni odporna.
To druga, obok progu, decyzja metodyczna. Co dołącza między 400 a 600 m (sprawdzone na mapie maski):

- **Szczecin:** Prawobrzeże (część miasta, za Odrą i Dąbiem), ale też miasto Police na północy.
- **Rzeszów:** Łańcut, ok. 17 km na wschód, połączony pasmem zabudowy wzdłuż drogi.
- **Kielce:** kilka wsi.

Żadna pojedyncza wartość nie jest dobra dla wszystkich miast: przy 400 m Wisła w Warszawie jest już „przekroczona”,
ale Prawobrzeże Szczecina jeszcze nie. Przy 600 m dochodzą osobne miasteczka połączone zabudową wzdłuż dróg.
Rekomendacja: 600 m (uzasadnienie w 1.4), z tą wadą opisaną przy wyniku.

Część klastra poza FUA jest mała: do ok. 3 % w GZM i ok. 6 % w Trójmieście, poniżej 2 % gdzie indziej. Domena FUA
obcina więc niewiele, ale nie nic.

Tabela 7a. Wariant „do najbliższego z N centrów” (inna miara; nie porównywać z ρ jednocentrowym).

| Aglomeracja | Liczba centrów | ρ do najbliższego, ≥ 10 % | ρ do najbliższego, ≥ 20 % | ρ do najbliższego, ≥ 30 % | ρ do najbliższego, ≥ 50 % | wariant N kół, ≥ 20 % | średnia odległość do najbliższego centrum, km (≥ 20 %) |
|---|---|---|---|---|---|---|---|
| GZM * | 9 | 0,5052 | 0,5951 | 0,7517 | brak danych (2,253) | 1,785 | 3,639 |
| Trójmiasto * | 3 | 1,125 | 1,371 | 1,817 | brak danych (3,841) | 2,374 | 6,115 |
| Bydgoszcz–Toruń * | 2 | 1,116 | 1,146 | 1,356 | brak danych (3,453) | 1,621 | 3,930 |

- **GZM:** ρ jednocentrowe (2,123 przy 20 %) mierzy przede wszystkim to, że Katowice nie są jedynym
  centrum. Wariant do najbliższego z 9 centrów spada poniżej 1. Na grafiki tylko wariant opisany jako inna miara albo
  wcale.
- **Trójmiasto:** wynik z wyraźnym zastrzeżeniem. Miasto jest liniowe (ok. 35 km wzdłuż brzegu), a koło o polu maski
  wychodzi w morze. ρ = 3,138 przy centrum Gdańsk Główny.
- **Bydgoszcz–Toruń:** ρ ok. 5 to artefakt dwóch ośrodków odległych o ok. 42 km (oba miasta w masce, zarodki przy obu
  centrach). Do tabel tylko wariant N centrów.

## 5. Gini i η (§4.4, tylko QA, nie na grafiki)

Tabela 8. Gini znormalizowany (G/Gmax) i η. Rozdzielczość 100 m; domeny stałe: maska ≥ 20 % oraz
koło 10 km.

| Aglomeracja | G/Gmax maska | η maska | próg LouBar maska, os./km² | hotspoty | komórki | G/Gmax koło 10 km | η koło | próg LouBar koło | hotspoty |
|---|---|---|---|---|---|---|---|---|---|
| GZM * | 0,4077 | 0,7682 | 10 226 | 3520 | 26429 | 0,7340 | 0,8961 | 10 312 | 1781 |
| Kraków | 0,4403 | 0,4245 | 10 387 | 1680 | 13298 | 0,7186 | 0,5652 | 9 590 | 2015 |
| Łódź | 0,4127 | 0,5797 | 9 589 | 1666 | 12979 | 0,7209 | 0,4978 | 9 246 | 1674 |
| Poznań | 0,4394 | 0,4337 | 7 647 | 1822 | 15123 | 0,7117 | 0,5458 | 7 584 | 1858 |
| Trójmiasto * | 0,3977 | 0,9026 | 9 997 | 1772 | 14066 | 0,7771 | 0,6174 | 8 247 | 1510 |
| Warszawa | 0,4830 | 0,3729 | 11 277 | 5159 | 44562 | 0,6171 | 0,7314 | 13 115 | 3500 |
| Wrocław | 0,4743 | 0,4407 | 9 559 | 1765 | 11107 | 0,7805 | 0,4842 | 9 260 | 1889 |
| Białystok | 0,4172 | 0,5946 | 9 348 | 949 | 5148 | 0,8570 | 0,3989 | 8 813 | 1126 |
| Bydgoszcz–Toruń * | 0,4077 | 0,8173 | 8 966 | 1646 | 8311 | 0,8572 | 0,4006 | 8 474 | 1229 |
| Kielce | 0,4177 | 0,3457 | 6 963 | 881 | 4827 | 0,8642 | 0,3271 | 6 440 | 1052 |
| Lublin | 0,4039 | 0,7504 | 8 839 | 1130 | 5974 | 0,8132 | 0,4626 | 7 977 | 1348 |
| Rzeszów | 0,4739 | 0,2939 | 7 664 | 801 | 5880 | 0,8381 | 0,3052 | 7 091 | 951 |
| Szczecin | 0,4299 | 0,5346 | 11 170 | 743 | 5669 | 0,8481 | 0,3835 | 10 243 | 861 |

- Gini w kole jest wyższy niż w masce, bo koło zawiera tereny niezamieszkane. To dokładnie efekt, przed którym brief
  ostrzega przy liczeniu na FUA.
- η w masce: najwyższe dla Bydgoszczy–Torunia (dwa ośrodki) i Trójmiasta, wysokie dla GZM. Odpowiada to
  policentryczności. Wśród miast jednocentrowych najniższe η: Rzeszów 0,2939, Kielce 0,3457, Warszawa 0,3729 (hotspoty skupione); najwyższe: Białystok 0,5946, Lublin 0,7504.
- Wartości zależą od progu LouBar i rozdzielczości (zapisane w tabeli), więc służą tylko do opisu w RAPORT.md.

## 6. Kontrola §7.1: GHSL 2020 vs NSP 2021 vs BDL

### 6.1 Sumy krajowe

| Wielkość | Ludność | Uwagi |
|---|---|---|
| Siatka NSP 2021 1 km (`RES`), suma | 37 019 327 | ludność rezydująca, 31.03.2021 |
| BDL NSP 2021, ludność rezydująca, suma gmin (zm. 1644331) | 37 019 327 | zgodna z siatką co do osoby |
| BDL NSP 2021, ludność ogółem (def. krajowa), suma gmin (zm. 1639271) | 38 036 118 | 31.03.2021 |
| GHS-POP 2020, komórki 250 m o środku w Polsce | 38 471 100 | epoka 2020, model |
| GHS-POP 2020 zsumowany do komórek NSP 1 km | 38 589 595 | zawiera ludność zagraniczną w komórkach przyciętych granicą |
| to samo, bez komórek przyciętych | 38 371 882 |  |

- **Siatka NSP to ludność rezydująca.** Jej suma jest równa co do osoby sumie gmin z BDL dla zmiennej „ludność
  rezydująca” NSP 2021. To potwierdza ustalenie z RAPORT §4.1 bezpośrednio z BDL.
- **GHSL 2020 jest skalibrowany powyżej obu definicji:**
  - 38,47 mln w Polsce (komórki 250 m);
  - o ok. 1,1 % ponad ludność wg definicji krajowej (38,04 mln);
  - o 3,9 % ponad ludność rezydującą.
- **Część każdego „GHSL > NSP” to więc różnica poziomu, nie rozkładu.** Do poziomu ludności krajowej dochodzi ok. 1 %
  z kalibracji GHSL. Hipoteza, której nie sprawdzono w dokumentacji JRC: GHSL jest skalibrowany do szacunku ludności
  Polski na 2020 r. sprzed rewizji spisowej (GUS podawał ok. 38,3 mln na 31.12.2020).

### 6.2 Rozkład różnicy na czynniki per FUA i rdzeń

Ten sam obszar, gminy przypisane regułą ≥ 50 % pola (LAU 2021). Rozkład:
GHSL/NSP = (c) GHSL/BDL krajowa × (b) BDL krajowa/BDL rezydująca × (a) BDL rezydująca/siatka.

- **(a) przypisanie:** gminy w całości vs komórki według centroidu;
- **(b) czysty efekt definicji:** ten sam spis, ta sama data;
- **(c) reszta:** model GHSL, data 2020 vs 31.03.2021 i dane wejściowe GHSL.

Zmiennej BDL 72305 (stan 31.12.2020) nie pobrano: zapora GUS zablokowała anonimowe API po ok. 90 zapytaniach
(HTTP 500, „Strona została zablokowana ze względów bezpieczeństwa”).

Tabela 9. Sumy i czynniki.

| Aglomeracja | Domena | Gmin | NSP siatka | BDL rezydująca | BDL krajowa | GHSL 2020 | GHSL/NSP | (a) BDL rez./siatka | (b) krajowa/rez. | (c) GHSL/krajowa | |GHSL/NSP−1| > 5 % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Białystok | FUA | 22 | 448 491 | 448 414 | 469 637 | 462 842 | 1,032 | 0,9998 | 1,047 | 0,9855 | nie |
| Białystok | CORE | 1 | 281 830 | 282 306 | 294 242 | 298 928 | 1,061 | 1,002 | 1,042 | 1,016 | TAK |
| Bydgoszcz–Toruń | FUA | 28 | 855 995 | 855 866 | 879 636 | 892 951 | 1,043 | 0,9998 | 1,028 | 1,015 | nie |
| Bydgoszcz–Toruń | CORE | 2 | 510 653 | 521 755 | 535 939 | 545 377 | 1,068 | 1,022 | 1,027 | 1,018 | TAK |
| GZM | FUA | 39 | 2 057 054 | 2 056 342 | 2 100 836 | 2 150 295 | 1,045 | 0,9997 | 1,022 | 1,024 | nie |
| GZM | CORE | 13 | 1 643 705 | 1 648 821 | 1 684 184 | 1 738 107 | 1,057 | 1,003 | 1,021 | 1,032 | TAK |
| Kielce | FUA | 21 | 386 456 | 386 783 | 400 189 | 405 621 | 1,050 | 1,001 | 1,035 | 1,014 | nie |
| Kielce | CORE | 1 | 179 303 | 179 807 | 186 894 | 193 979 | 1,082 | 1,003 | 1,039 | 1,038 | TAK |
| Kraków | FUA | 40 | 1 411 779 | 1 411 716 | 1 434 491 | 1 350 286 | 0,9564 | 1,0000 | 1,016 | 0,9413 | nie |
| Kraków | CORE | 1 | 793 392 | 790 279 | 800 653 | 760 841 | 0,9590 | 0,9961 | 1,013 | 0,9503 | nie |
| Łódź | FUA | 26 | 1 044 086 | 1 042 726 | 1 053 727 | 1 045 886 | 1,002 | 0,9987 | 1,011 | 0,9926 | nie |
| Łódź | CORE | 1 | 665 696 | 665 259 | 670 642 | 670 405 | 1,007 | 0,9993 | 1,008 | 0,9996 | nie |
| Lublin | FUA | 36 | 664 078 | 663 533 | 684 608 | 680 102 | 1,024 | 0,9992 | 1,032 | 0,9934 | nie |
| Lublin | CORE | 1 | 322 635 | 324 568 | 334 681 | 332 983 | 1,032 | 1,006 | 1,031 | 0,9949 | nie |
| Poznań | FUA | 19 | 974 744 | 974 797 | 980 543 | 926 610 | 0,9506 | 1,000 | 1,006 | 0,9450 | nie |
| Poznań | CORE | 1 | 547 682 | 541 782 | 546 859 | 527 922 | 0,9639 | 0,9892 | 1,009 | 0,9654 | nie |
| Rzeszów | FUA | 23 | 459 020 | 459 878 | 478 096 | 458 745 | 0,9994 | 1,002 | 1,040 | 0,9595 | nie |
| Rzeszów | CORE | 1 | 185 929 | 188 643 | 195 871 | 211 037 | 1,135 | 1,015 | 1,038 | 1,077 | TAK |
| Szczecin | FUA | 8 | 512 051 | 512 877 | 521 156 | 524 618 | 1,025 | 1,002 | 1,016 | 1,007 | nie |
| Szczecin | CORE | 1 | 384 375 | 391 404 | 396 168 | 398 002 | 1,035 | 1,018 | 1,012 | 1,005 | nie |
| Trójmiasto | FUA | 19 | 1 089 730 | 1 095 741 | 1 117 892 | 1 064 838 | 0,9772 | 1,006 | 1,020 | 0,9525 | nie |
| Trójmiasto | CORE | 3 | 752 435 | 747 697 | 764 206 | 736 930 | 0,9794 | 0,9937 | 1,022 | 0,9643 | nie |
| Warszawa | FUA | 97 | 3 485 881 | 3 488 311 | 3 483 828 | 3 334 987 | 0,9567 | 1,001 | 0,9987 | 0,9573 | nie |
| Warszawa | CORE | 1 | 1 865 105 | 1 864 679 | 1 860 281 | 1 785 716 | 0,9574 | 0,9998 | 0,9976 | 0,9599 | nie |
| Wrocław | FUA | 21 | 1 011 966 | 1 011 381 | 1 018 677 | 939 076 | 0,9280 | 0,9994 | 1,007 | 0,9219 | TAK |
| Wrocław | CORE | 1 | 673 906 | 669 564 | 672 929 | 634 111 | 0,9409 | 0,9936 | 1,005 | 0,9423 | TAK |

Wykres: `summary_control.png`.

**Wyjaśnienie odchyleń > 5 %** (flaga z fazy 0: Wrocław FUA i rdzeń, rdzenie GZM, Bydgoszczy–Torunia, Rzeszowa, Kielc,
Białegostoku):

- **Wrocław (FUA 0,9280, rdzeń
  0,9409).**
  - Definicja niczego tu nie wyjaśnia (b ≈ 1,007): Wrocław ma prawie tyle samo mieszkańców wg obu definicji.
  - Cała różnica to (c): GHSL ma o ok. 8 % mniej ludzi niż oficjalna liczba wg definicji krajowej.
  - Ten sam znak, słabiej, mają Kraków, Poznań, Trójmiasto i Warszawa (c = 0,92–0,96). Są to miasta i strefy
    podmiejskie, które najszybciej rosły w latach 2011–2021.
  - Wyjaśnienie prawdopodobne, niesprawdzone w dokumentacji JRC: dane wejściowe GHS-POP dla Polski to liczby gminne z
    wcześniejszego okresu, przeniesione na 2020; nie oddają napływu do dużych miast. Wynik nie jest błędem przypisania
    (a ≈ 1).
- **Rdzenie GZM, Bydgoszczy–Torunia, Kielc, Białegostoku (GHSL/NSP 1,06–1,08).** Dwa składniki:
  - (b) = 1,02–1,04: ludność wg definicji krajowej przewyższa rezydującą. To regiony z emigracją; osoby długo
    przebywające za granicą liczą się w definicji krajowej, nie w rezydującej.
  - (c) = 1,00–1,04: niewielka nadwyżka modelu.
  - Po uwzględnieniu definicji odchylenia mieszczą się w 5 % (poza Rzeszowem).
  - W Bydgoszczy–Toruniu i Szczecinie część różnicy rdzenia to (a) = 1,02. Granica URAU rdzenia i komórki siatki
    przy brzegu nie pokrywają się: komórki o centroidzie tuż za granicą miasta.
- **Rdzeń Rzeszowa (GHSL/NSP 1,135):** (b) 1,038 × (c) 1,077 × (a) 1,015. Nadwyżka modelu jest skupiona w centrum.
  Kilka komórek w śródmieściu i na północnym wschodzie miasta ma w GHSL 2–4 razy więcej ludzi niż w spisie
  (współrzędne w `control_top_cells.csv`). To zgodne z mechanizmem kubatury niemieszkalnej opisanym niżej.
  Zabudowy w tych komórkach nie oglądano. FUA Rzeszowa jako całość się zgadza (0,999), więc model przesuwa ludność
  z okolicy do miasta, a nie ją dodaje.

### 6.3 Porównanie na komórkach 1 km

Tabela 10. Korelacja i indeks niepodobieństwa D = ½ Σ |gᵢ/G − nᵢ/N| (udział ludności, który trzeba by przesunąć, żeby
oba rozkłady były identyczne; niezależny od różnicy poziomu).

| Aglomeracja | Domena | Komórki | Pearson | Pearson log(1+x) | Spearman | Indeks niepodobieństwa D |
|---|---|---|---|---|---|---|
| Białystok | FUA | 3875 | 0,9212 | 0,9314 | 0,9127 | 20,3 % |
| Białystok | CORE | 102 | 0,8692 | 0,8945 | 0,9195 | 20,8 % |
| Bydgoszcz–Toruń | FUA | 4253 | 0,9095 | 0,9075 | 0,9001 | 21,0 % |
| Bydgoszcz–Toruń | CORE | 290 | 0,8759 | 0,8303 | 0,8754 | 23,3 % |
| GZM | FUA | 2601 | 0,8952 | 0,8916 | 0,9013 | 20,4 % |
| GZM | CORE | 1062 | 0,8757 | 0,8372 | 0,8800 | 21,0 % |
| Kielce | FUA | 2331 | 0,8690 | 0,9387 | 0,9454 | 19,5 % |
| Kielce | CORE | 112 | 0,8297 | 0,8890 | 0,8921 | 25,5 % |
| Kraków | FUA | 3339 | 0,8707 | 0,9227 | 0,9245 | 19,0 % |
| Kraków | CORE | 327 | 0,8144 | 0,7311 | 0,8300 | 23,1 % |
| Łódź | FUA | 2522 | 0,8725 | 0,9170 | 0,9143 | 22,4 % |
| Łódź | CORE | 290 | 0,8187 | 0,8289 | 0,8682 | 24,7 % |
| Lublin | FUA | 3552 | 0,8775 | 0,9486 | 0,9505 | 19,7 % |
| Lublin | CORE | 145 | 0,7927 | 0,8946 | 0,8855 | 23,9 % |
| Poznań | FUA | 2287 | 0,8747 | 0,9100 | 0,9104 | 22,7 % |
| Poznań | CORE | 263 | 0,8233 | 0,8575 | 0,9161 | 23,7 % |
| Rzeszów | FUA | 1943 | 0,8811 | 0,9445 | 0,9518 | 19,1 % |
| Rzeszów | CORE | 126 | 0,8330 | 0,8418 | 0,8971 | 23,2 % |
| Szczecin | FUA | 1361 | 0,9112 | 0,8808 | 0,8566 | 21,9 % |
| Szczecin | CORE | 296 | 0,9205 | 0,8699 | 0,8920 | 19,6 % |
| Trójmiasto | FUA | 1922 | 0,8507 | 0,8885 | 0,8891 | 23,7 % |
| Trójmiasto | CORE | 412 | 0,7836 | 0,8067 | 0,8236 | 26,4 % |
| Warszawa | FUA | 9313 | 0,9387 | 0,9362 | 0,9314 | 16,9 % |
| Warszawa | CORE | 515 | 0,9137 | 0,8341 | 0,9036 | 16,2 % |
| Wrocław | FUA | 3113 | 0,9343 | 0,9161 | 0,9084 | 17,0 % |
| Wrocław | CORE | 291 | 0,9069 | 0,8899 | 0,9239 | 16,5 % |

- **Korelacja na komórkach 1 km jest wysoka** (Pearson 0,78–0,94), ale **D wynosi 16–26 %.** Na poziomie
  pojedynczych kilometrów GHSL i spis rozmieszczają różnie co szóstą do co czwartej osoby.
- Ta różnica jest dużo większa niż różnica sum. To mierzy jakość GHSL jako warstwy 250 m i jako pochodzeń dla
  dostępności, a nie sum dla FUA.
- Komórki przycięte granicą państwa praktycznie nie wpływają na D (kolumna `dissimilarity_unclipped` w
  `control_cells.csv`).

Tabela 11. Wybrane komórki o największej różnicy (pełna lista: `control_top_cells.csv`; po 10 bezwzględnych i 10
względnych na aglomerację).

| Aglomeracja | Rodzaj | Środek komórki (lat, lon) | Gmina | NSP 2021 | GHSL 2020 | GHSL − NSP |
|---|---|---|---|---|---|---|
| Warszawa | bezwzględna | 52.1615, 21.0751 | Warszawa | 16 943 | 7 442 | -9 501 |
| Warszawa | bezwzględna | 52.3183, 20.951 | Warszawa | 12 688 | 5 207 | -7 481 |
| Warszawa | bezwzględna | 52.3933, 20.9251 | Legionowo | 13 566 | 6 291 | -7 275 |
| Warszawa | względna | 52.3041, 21.0069 | Warszawa | 0 | 1 938 | 1 938 |
| Warszawa | względna | 52.171, 20.9737 | Warszawa | 0 | 1 666 | 1 666 |
| Kraków | bezwzględna | 50.0612, 19.9425 | Kraków | 5 662 | 14 946 | 9 284 |
| Kraków | bezwzględna | 50.0919, 20.0055 | Kraków | 14 408 | 5 861 | -8 547 |
| Kraków | bezwzględna | 50.0704, 20.0433 | Kraków | 14 219 | 5 888 | -8 331 |
| Kraków | względna | 50.0756, 20.0868 | Kraków | 0 | 5 338 | 5 338 |
| Kraków | względna | 50.0845, 20.0887 | Kraków | 0 | 4 496 | 4 496 |
| Wrocław | bezwzględna | 51.1088, 17.0305 | Wrocław | 7 016 | 15 513 | 8 497 |
| Wrocław | bezwzględna | 51.0811, 17.0406 | Wrocław | 14 234 | 7 599 | -6 635 |
| Wrocław | bezwzględna | 51.1258, 17.0474 | Wrocław | 18 641 | 12 287 | -6 354 |
| Wrocław | względna | 51.1024, 16.9865 | Wrocław | 0 | 3 068 | 3 068 |
| Wrocław | względna | 51.0415, 16.9486 | Kobierzyce | 0 | 1 513 | 1 513 |
| Poznań | bezwzględna | 52.4052, 16.9254 | Poznań | 9 074 | 17 784 | 8 710 |
| Poznań | bezwzględna | 52.4061, 16.9108 | Poznań | 2 469 | 10 058 | 7 589 |
| Poznań | bezwzględna | 52.4508, 16.9178 | Poznań | 12 444 | 4 954 | -7 490 |
| Poznań | względna | 52.4029, 17.1171 | Swarzędz | 1 | 1 379 | 1 378 |
| Poznań | względna | 52.3179, 17.0297 | Kórnik | 0 | 666 | 666 |
| Łódź | bezwzględna | 51.7384, 19.4913 | Łódź | 14 327 | 5 163 | -9 164 |
| Łódź | bezwzględna | 51.7466, 19.3907 | Łódź | 14 261 | 5 642 | -8 619 |
| Łódź | bezwzględna | 51.7988, 19.4163 | Łódź | 309 | 8 402 | 8 093 |
| Łódź | względna | 51.7438, 19.5363 | Łódź | 0 | 5 501 | 5 501 |
| Łódź | względna | 51.745, 19.522 | Łódź | 0 | 5 207 | 5 207 |
| Trójmiasto | bezwzględna | 54.3582, 18.5812 | Gdańsk | 11 153 | 3 843 | -7 310 |
| Trójmiasto | bezwzględna | 54.3474, 18.734 | Gdańsk | 0 | 7 292 | 7 292 |
| Trójmiasto | bezwzględna | 54.4216, 18.5789 | Gdańsk | 12 522 | 5 353 | -7 169 |
| Trójmiasto | względna | 54.3474, 18.734 | Gdańsk | 0 | 7 292 | 7 292 |
| Trójmiasto | względna | 54.3707, 18.6614 | Gdańsk | 0 | 4 923 | 4 923 |
| GZM | bezwzględna | 50.2769, 18.9824 | Katowice | 10 522 | 3 127 | -7 395 |
| GZM | bezwzględna | 50.3226, 19.2036 | Dąbrowa Górnicza | 11 012 | 4 431 | -6 581 |
| GZM | bezwzględna | 50.1321, 18.9831 | Tychy | 2 130 | 8 491 | 6 361 |
| GZM | względna | 50.3426, 19.2926 | Dąbrowa Górnicza | 0 | 4 120 | 4 120 |
| GZM | względna | 50.3348, 19.2769 | Dąbrowa Górnicza | 0 | 3 110 | 3 110 |

**Prawdopodobne przyczyny** (rozpoznane po współrzędnych; nie weryfikowane w terenie ani na ortofotomapie):

1. **GHSL >> NSP w strefach przemysłowych, portowych i usługowych**, gdzie NSP ma 0 mieszkańców. Przykłady:
   - kombinat ArcelorMittal w Nowej Hucie (do 5 300 osób na komórkę w GHSL);
   - Huta Katowice w Dąbrowie Górniczej;
   - Huta Warszawa na Bielanach i rejon lotniska Okęcie;
   - rafineria w Gdańsku i tereny stoczniowo-portowe nad Martwą Wisłą; port i stocznia w Gdyni;
   - strefy przemysłowe Widzewa i Olechowa w Łodzi;
   - Bielany Wrocławskie (Kobierzyce, centra handlowe i logistyka);
   - parki logistyczne pod Poznaniem (Swarzędz, Kórnik, Komorniki).

   GHS-POP rozdziela ludność według objętości zabudowy, a wielkie hale i zakłady mają dużą objętość.
2. **GHSL >> NSP w ścisłych centrach:**
   - Stare Miasto w Krakowie (14 946 vs 5 662);
   - Rynek we Wrocławiu;
   - Śródmieście Warszawy;
   - Stary Rynek w Poznaniu.

   Biura, handel, hotele i urzędy to kubatura bez mieszkańców.
3. **GHSL << NSP w wielkich osiedlach blokowych:**
   - Ursynów i osiedla na północy Warszawy (52,32° N, 20,95° E); Legionowo, Ząbki, Piaseczno;
   - Bieńczyce i Mistrzejowice (Nowa Huta) w Krakowie;
   - Zaspa i Przymorze w Gdańsku;
   - Retkinia i Widzew Wschód w Łodzi;
   - Winogrady i Piątkowo w Poznaniu;
   - Tysiąclecie w Katowicach;
   - osiedla Tychów i Dąbrowy Górniczej.

   GHSL daje tam zwykle 35–60 % ludności spisowej. Model kubaturowy nie oddaje gęstości zaludnienia wysokich bloków.
   W Ząbkach i Piasecznie dochodzi prawdopodobnie zabudowa nowsza niż dane wejściowe GHSL (niesprawdzone).
4. **Koszary, akademiki i więzienia nie pojawiły się wśród największych różnic** w aglomeracjach fazy 1. Nie
   szukaliśmy ich celowo.
5. **Komórki przycięte brzegiem lub granicą:** pojedyncze przypadki na wybrzeżu Gdańska i w Szczecinie. GHSL liczy
   tam cały kwadrat.

**Wniosek dla projektu:**

- PWD i krzywe skumulowane liczymy na spisie, jak przewiduje brief.
- GHSL jest wystarczający do profilu 1 km i krzywej skumulowanej: różnice w krzywej do 3–4 pp poza Rzeszowem.
- Na poziomie komórek GHSL przesuwa ludność z blokowisk do centrów i stref przemysłowych. To trzeba opisać przy warstwie
  250 m i przy dostępności, gdzie GHSL wyznacza pochodzenia (§4.6).
- Warstwa 6c (BDOT10k, brief §13) jest właściwym lekarstwem.

## 7. Ograniczenia

- **GHS-POP to model.** Wszystkie wyniki 100 m i 250 m (profile, ρ, Gini, η, PWD 250 m) dziedziczą błędy opisane w §6:
  ludność w strefach przemysłowych, niedoszacowanie blokowisk, poziom ok. 1 % powyżej definicji krajowej.
- **ρ zależy od dwóch decyzji metodycznych:** progu (tabela 5) i reguły spójności (tabela 7). Jego poziom nie jest
  porównywalny z literaturą.
- **Daty się nie pokrywają:** GHSL to epoka 2020, NSP stan 31.03.2021, granice 2021. Migracje po 2021 r. i nowe
  osiedla nie są uwzględnione.
- **Rdzenie** to granice URAU (miasto). Dla GZM to 13 miast, dla Trójmiasta trzy.
- **Wariant (ii) profilu** pomija ludność za granicą państwa (Szczecin).
- **Gini i η liczone na próbie** maks. 4000 komórek (stałe ziarno). Błąd próbkowania średniej odległości
  szacujemy na < 1 %, ale tego nie mierzono.
- **Centra punktowe** z `config.yaml`. ρ i profil są wrażliwe na położenie centrum o kilkaset metrów; tego nie badano.

## 8. Co zaskoczyło i co wyszło przy sprawdzeniu

1. **Prążki w siatce 250 m.**
   - Pierwsza wersja (domyślne ustawienia GDAL) miała względem dokładnej referencji dipole ±100 osób na komórkę.
   - Kontrola: podział pikseli na 10 × 10 i 20 × 20 podpikseli (te dwie referencje różnią się między sobą o RMSE
     1,7 osoby).
   - Przyczyna: przybliżony transformator współrzędnych GDAL. Po `tolerance=0` różnica spadła do poziomu szumu
     referencji. **Poprawione.**
2. **ρ > 1 wszędzie.** Kontrole:
   - mapa maski Warszawy (przy luce 200 m klaster kończył się na Wiśle, stąd zmiana reguły na 600 m);
   - wrażliwość na lukę 0–1 400 m: ρ Warszawy stabilne około 1,4;
   - rozkład wartości GHS-BUILT-S (dane w m² na komórkę 0–10 000, zgodnie z dokumentacją; przy progu 20 % w FUA
     Warszawy jest 582 km² zabudowy z 76 % ludności).

   Wynik zostaje: to cecha maski netto (patrz §4), nie błąd. **Zostaje z zastrzeżeniem.**
3. **Maska przy progu 50 % jest prawie pusta** (0–2 km²). Komórka 100 m z połową powierzchni pod dachami to w
   Polsce rzadkość poza zwartymi kwartałami śródmieść. ρ = „brak danych”. **Zostaje.**
4. **Szczecin ma najwyższe PWD FUA (6 506), wyższe niż Warszawa (5 910).** Kontrole:
   - najgęstsza komórka spisowa w kraju leży w śródmieściu Szczecina (14,539° E, 53,429° N): 26 043 osoby na km²;
   - sąsiednie komórki mają do 11 758 osób, GHSL w tej samej komórce 22 411. Oba źródła się zgadzają, więc to nie
     artefakt spisu (np. adresy zbiorcze);
   - mała FUA (1 362 km², 75 % ludności w rdzeniu) nie rozcieńcza wyniku przedmieściami tak jak w Warszawie.

   **Zostaje.** Pokazuje też, że PWD FUA mierzy częściowo udział rdzenia w FUA.
5. **GHSL ma 38,5 mln mieszkańców Polski**, więcej niż obie definicje GUS. Kontrola: dwa niezależne rachunki
   (komórki 250 m o środku w Polsce; komórki spisowe 1 km bez przyciętych) dają 38,47 i 38,37 mln. Różnica 0,26 %
   to komórki brzegowe. **Zostaje jako fakt o źródle.**
6. **Wrocław GHSL −7 %** nie wynika z definicji ludności: BDL pokazuje b ≈ 1,007. To różnica modelu (patrz 6.2).
7. **GHSL ma ludność w kombinatach i portach** (5 300 osób w komórce huty w Nowej Hucie). Kontrola: NSP = 0 w tych
   komórkach. **Zostaje jako fakt o źródle**, opisany przy warstwie 250 m.

## 9. Pliki

- Wyniki:
  - `results/metrics/metrics_density.csv` i `.json` (scalone z innymi krokami w `metrics.csv`): format długi; `tier`: `main` (na grafikę), `table`, `qa`;
  - `results/charts/pwdens.json`;
  - `results/charts/profile_cumulative_monocentric.json`, `profile_cumulative_polycentric.json`.
- QA:
  - `results/qa/density/{pwdens,profile,mask,gini,control}_<aglomeracja>.png`;
  - `summary_*.png`, `grid250_moire_warszawa.png`;
  - `control_*.csv`.
- Pośrednie: `data/interim/grid250/` (siatka 250 m, maska Polski, `cells_*.parquet`, `qa.json`),
  `data/interim/density/`.
- BDL: `data/raw/bdl/*.json`, w manifeście jako `bdl_nsp2021_resident_gmina`, `bdl_nsp2021_national_gmina`.
- Polecenia (w tej kolejności): `python -m pipeline.grid250`, `python -m pipeline.density`,
  `python -m pipeline.density_control`, `python -m pipeline.density_qa`.
