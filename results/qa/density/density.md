# Faza 1: miary gęstości (§4.1–4.4) i kontrola GHSL vs NSP (§7.1)

Wygenerowano: 2026-11-24 (`python -m pipeline.density_qa`; liczby z `pipeline.grid250`, `pipeline.density`,
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

- **Dane:** siatka 100 m przeskalowana do spisu (patrz 1.6). Pierścienie 1 km są za drobne na samą siatkę spisową 1 km.
- **Odległość:** od środka piksela do centrum z `config.yaml`, w EPSG:2180. Pierścienie [k, k+1) km.
- **Gęstość pierścienia:** ludność / pole komórek pierścienia w domenie (lasy i wody wewnątrz domeny wliczone).
  Osobno podajemy pole zamieszkane (komórki z ludnością > 0) w plikach `data/interim/density/*_profile_*.csv`.
- **Wariant (i) „fua”:** tylko komórki o środku w FUA; udział w ludności FUA (ta sama siatka 100 m). Pierścienie sięgają do najdalszej
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
- **Licznik:** tylko ludność siatki 100 m (1.6) z komórek maski; odległość od środka komórki do centrum w EPSG:2180.
- **Wartość „brak danych”:** gdy maska obejmuje < 5 % ludności domeny. Przy progu 50 % maska ma kilka km² wokół
  rynku i ρ traci sens; surowa wartość jest w nawiasie w tabelach.
- **Wariant „do najbliższego z N centrów”** (GZM, Trójmiasto, Bydgoszcz–Toruń; inna miara): odległość do najbliższego
  centrum, mianownik ⅔R jak w ρ (dosłownie wg briefu). Pomocniczo podajemy wariant z mianownikiem dla N równych kół
  (⅔·√(A/(Nπ))).

### 1.5 Gini i η (§4.4, tylko QA)

- **Domeny (stałe):** maska z §4.3 przy progu roboczym 20 % oraz koło 10 km wokół centrum
  (komórki w Polsce). Rozdzielczość 100 m (siatka z 1.6).
- **Wzory wg Volpati i Barthelemy (2018), arXiv:1804.00855:**
  - Gini: wzór (1) na liczbach ludności komórek, normalizowany przez G_max = (n−1)/n (wzory 2–3);
  - hotspoty: komórki powyżej wartości LouBar, czyli miejsca, w którym styczna do krzywej Lorenza w F = 1 przecina oś;
  - η: wzór (6), średnia odległość między hotspotami / średnia odległość między wszystkimi komórkami domeny.
- **Uproszczenie obliczeniowe:** obie średnie liczymy na stałej próbie losowej (ziarno 0, maks. 4000 komórek),
  żeby uniknąć ~10¹⁰ par.
- Próg LouBar i rozdzielczość są zapisane przy każdej liczbie (tabela 8, `metrics_density.csv`, kolumna `flag`).

### 1.6 Siatka ludności miar 100 m (od 2026-11-24)

- **Wynik główny:** profile, r50, gradient Clarka, ρ, Gini i η liczymy na tej samej siatce, którą faza 2 zbudowała dla
  częstej komunikacji: GHS-POP 100 m przeskalowany tak, żeby każda komórka spisowa 1 km sumowała się do NSP 2021
  (`pipeline.popgrid.scale_100m`). Używamy jej w rozdzielczości 100 m, przed agregacją do 250 m, bo maska zabudowy
  i odległości są w 100 m; dzięki temu różnica między wariantami to wyłącznie ludność. Kontrola: ta siatka zsumowana
  do 250 m tym samym jądrem GDAL co w `pipeline.popgrid` różni się od `pop_ghsl_census_scaled_250m_epsg2180.tif`
  najwyżej o 0,0001 osoby na komórkę (zaokrąglenie float32).
- **Poziom spisowy, rozkład modelowy:** na poziomie 1 km liczby są spisowe; wewnątrz komórki 1 km ludność jest
  rozłożona wzorem GHSL. Komórki spisowe z zerową ludnością tracą ludność, którą GHSL umieścił w zakładach i portach.
- **Wariant kontrolny:** surowy GHS-POP 2020, liczony tym samym kodem; w `metrics_density.csv` wiersze z
  `population_grid` = `ghsl_raw` i poziomem `qa`. Wiersze, które istnieją w obu wariantach, mają wypełnioną kolumnę
  `population_grid`; pozostałe (siatka spisowa 1 km, pola masek, GHSL 250 m) mają ją pustą. Porównanie: sekcja 5a.
- **Daty:** NSP 2021 (31.03.2021), wzór wewnątrz komórek z GHSL epoki 2020.

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

Tabela 3. Profil (siatka 100 m przeskalowana do NSP 2021; wariant z surowym GHSL w sekcji 5a).

- r50: promień, w którym mieszka 50 % ludności;
- udział do 10 km: (i) w ludności FUA, (ii) w ludności do 40 km;
- Clark: tylko tabela/QA;
- ostatnie kolumny: maksymalna różnica krzywej skumulowanej względem NSP 1 km na krokach 2, 5, …, 40 km.

| Aglomeracja | r50 (i) FUA, km | r50 (ii), km | udział do 10 km (i) | udział do 10 km (ii) | gęstość 0–1 km | Clark b, 1/km | Clark D0 | R² | maks. różnica względem NSP 1 km (i), pp | (ii), pp |
|---|---|---|---|---|---|---|---|---|---|---|
| GZM * | 13,07 | 17,22 | 34,7 % | 24,3 % | 7 929 | 0,09399 | 4 054 | 0,8578 | 0,7227 | 0,5326 |
| Kraków | 7,814 | 12,10 | 57,5 % | 46,0 % | 6 816 | 0,1702 | 5 810 | 0,8778 | 1,004 | 0,8328 |
| Łódź | 6,106 | 8,088 | 67,7 % | 56,8 % | 12 556 | 0,2086 | 6 488 | 0,9227 | 1,409 | 1,189 |
| Poznań | 6,630 | 9,431 | 66,8 % | 52,3 % | 7 261 | 0,1842 | 5 090 | 0,8981 | 0,3663 | 0,2971 |
| Trójmiasto * | 12,06 | 16,60 | 44,3 % | 37,2 % | 3 690 | 0,1095 | 2 926 | 0,7338 | 1,059 | 0,7776 |
| Warszawa | 11,10 | 9,994 | 45,5 % | 50,0 % | 9 918 | 0,1622 | 12 118 | 0,9642 | 0,4138 | 0,4386 |
| Wrocław | 6,125 | 7,930 | 66,1 % | 55,6 % | 8 428 | 0,2042 | 5 736 | 0,8741 | 2,302 | 1,921 |
| Białystok | 4,239 | 4,872 | 75,0 % | 66,6 % | 8 553 | 0,2187 | 2 120 | 0,7324 | 1,151 | 1,085 |
| Bydgoszcz–Toruń * | 18,75 | 12,32 | 36,5 % | 42,5 % | 8 669 | 0,1731 | 2 095 | 0,7731 | 1,386 | 1,692 |
| Kielce | 7,899 | 21,36 | 56,3 % | 32,9 % | 6 583 | 0,1452 | 1 180 | 0,7035 | 1,511 | 0,8550 |
| Lublin | 6,912 | 10,03 | 56,5 % | 49,9 % | 5 296 | 0,1623 | 2 130 | 0,6712 | 1,308 | 1,153 |
| Rzeszów | 8,797 | 21,46 | 53,5 % | 30,1 % | 5 446 | 0,1313 | 1 413 | 0,7204 | 0,7939 | 0,4510 |
| Szczecin | 4,761 | 7,763 | 79,0 % | 60,3 % | 10 953 | 0,1975 | 3 047 | 0,7758 | 1,486 | 1,119 |

Tabela 4. Kontrola krzywej skumulowanej (i) spisem: udział ludności FUA w promieniu r, siatka 100 m / NSP 1 km (%).

| Aglomeracja | do 2 km: siatka 100 m / NSP, % | do 5 km: siatka 100 m / NSP, % | do 10 km: siatka 100 m / NSP, % | do 20 km: siatka 100 m / NSP, % | do 30 km: siatka 100 m / NSP, % |
|---|---|---|---|---|---|
| GZM * | 3,6 / 3,6 | 10,2 / 9,9 | 34,7 / 34,0 | 79,8 / 79,6 | 95,7 / 95,6 |
| Kraków | 6,0 / 5,5 | 26,9 / 25,9 | 57,5 / 57,4 | 78,1 / 78,1 | 95,3 / 95,2 |
| Łódź | 11,6 / 10,2 | 36,9 / 36,1 | 67,7 / 67,5 | 89,4 / 89,3 | 98,1 / 98,1 |
| Poznań | 6,3 / 6,2 | 38,2 / 38,5 | 66,8 / 67,0 | 90,1 / 90,3 | 98,5 / 98,5 |
| Trójmiasto * | 4,1 / 3,7 | 22,0 / 23,0 | 44,3 / 44,4 | 70,7 / 71,0 | 91,0 / 91,5 |
| Warszawa | 2,9 / 3,2 | 17,2 / 17,7 | 45,5 / 45,7 | 70,7 / 70,6 | 83,4 / 83,4 |
| Wrocław | 12,8 / 10,5 | 39,3 / 38,9 | 66,1 / 66,0 | 83,3 / 83,4 | 95,6 / 95,6 |
| Białystok | 19,5 / 20,7 | 57,5 / 57,8 | 75,0 / 74,8 | 83,8 / 83,8 | 94,1 / 94,1 |
| Bydgoszcz–Toruń * | 11,4 / 10,1 | 27,7 / 27,6 | 36,5 / 36,0 | 51,2 / 51,0 | 63,0 / 63,0 |
| Kielce | 18,2 / 16,7 | 44,3 / 44,2 | 56,3 / 56,4 | 82,7 / 82,8 | 96,1 / 96,1 |
| Lublin | 9,7 / 11,0 | 42,7 / 42,2 | 56,5 / 56,8 | 73,6 / 73,6 | 93,8 / 93,8 |
| Rzeszów | 13,5 / 14,3 | 37,2 / 37,3 | 53,5 / 53,8 | 83,8 / 84,0 | 99,2 / 99,2 |
| Szczecin | 17,7 / 19,1 | 52,4 / 52,4 | 79,0 / 79,1 | 95,4 / 95,8 | 99,9 / 99,9 |

Krzywe są monotoniczne z konstrukcji (sumy skumulowane nieujemnych liczb). W wariancie (i) każda kończy się na 100,0 %
(sprawdzone w `density_qa`, asercja).

Na siatce przeskalowanej różnica wynosi najwyżej 2,302 pp (Wrocław). Resztę tłumaczy sposób
liczenia, nie źródło: spis przypisujemy do pierścienia według centroidu komórki 1 km, a siatkę 100 m według środka
piksela, a krok 2 km jest porównywalny z rozmiarem komórki spisowej. Na surowym GHSL różnice sięgały
4,473 pp poza Rzeszowem i 7,355 pp w Rzeszowie,
gdzie GHSL koncentruje ludność w centrum bardziej niż spis (patrz §7.1, rdzeń Rzeszowa +13,5 %).

**Rekomendacja wariantu na grafikę: (ii) bez granic, jako liczba osób w promieniu r (oś Y w tysiącach lub milionach),
dla pięciu jednocentrowych aglomeracji fazy 1.** Uzasadnienie:

1. **Wariant (i) zmienia ranking przez rysunek granicy FUA, nie przez formę miasta.** Duża FUA Warszawy (9 296 km²,
   sięga poza 40 km) daje jej najniższy udział do 10 km (45,5 % w (i)),
   choć w (ii) jest 4. miejsce z 5 (50,0 %). Mała FUA Szczecina działa
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

Tabela 5. **ρ (FUA) dla każdego progu z `built_up_threshold_sensitivity`**, pole maski i udział ludności FUA
w masce (siatka przeskalowana do NSP). To tabela do decyzji o progu (brief §12.4). Próg roboczy: 20 %.

| Aglomeracja | ρ FUA, ≥ 10 % | ρ FUA, ≥ 20 % | ρ FUA, ≥ 30 % | ρ FUA, ≥ 50 % | maska ≥ 10 %: km² / udział ludności FUA | maska ≥ 20 %: km² / udział ludności FUA | maska ≥ 30 %: km² / udział ludności FUA | maska ≥ 50 %: km² / udział ludności FUA |
|---|---|---|---|---|---|---|---|---|
| GZM * | 1,657 | 2,102 | 2,918 | brak danych (11,64) | 446 / 88 % | 264 / 69 % | 120 / 34 % | 6 / 1 % |
| Kraków | 1,323 | 1,442 | 1,868 | brak danych (7,064) | 395 / 81 % | 133 / 52 % | 46 / 26 % | 3 / 1 % |
| Łódź | 1,192 | 1,391 | 1,841 | brak danych (4,400) | 267 / 86 % | 130 / 67 % | 62 / 39 % | 1 / 1 % |
| Poznań | 1,184 | 1,330 | 1,630 | brak danych (4,538) | 245 / 82 % | 151 / 67 % | 77 / 41 % | 2 / 1 % |
| Trójmiasto * | 2,413 | 3,077 | 4,223 | brak danych (11,49) | 235 / 89 % | 141 / 72 % | 73 / 43 % | 5 / 1 % |
| Warszawa | 1,171 | 1,406 | 1,649 | brak danych (4,317) | 865 / 86 % | 446 / 69 % | 195 / 41 % | 3 / 0 % |
| Wrocław | 1,102 | 1,287 | 1,583 | brak danych (4,208) | 176 / 74 % | 111 / 63 % | 60 / 40 % | 3 / 2 % |
| Białystok | 1,081 | 1,240 | 1,511 | brak danych (4,860) | 82 / 72 % | 51 / 62 % | 28 / 43 % | 1 / 0 % |
| Bydgoszcz–Toruń * | 4,097 | 5,290 | 6,620 | brak danych (31,20) | 186 / 72 % | 83 / 53 % | 50 / 39 % | 3 / 1 % |
| Kielce | 1,525 | 1,448 | 1,545 | brak danych (6,293) | 122 / 70 % | 48 / 47 % | 16 / 25 % | 0 / 0 % |
| Lublin | 1,413 | 1,402 | 1,810 | brak danych (5,860) | 180 / 70 % | 60 / 47 % | 32 / 29 % | 0 / 0 % |
| Rzeszów | 1,647 | 1,645 | 1,579 | brak danych (4,553) | 182 / 74 % | 59 / 42 % | 20 / 20 % | 2 / 1 % |
| Szczecin | 1,532 | 1,670 | 1,718 | brak danych (3,984) | 98 / 86 % | 57 / 68 % | 20 / 29 % | 3 / 2 % |

Tabela 5a. ρ dla rdzenia (ta sama maska ograniczona do rdzenia).

| Aglomeracja | ρ rdzeń, ≥ 10 % | ρ rdzeń, ≥ 20 % | ρ rdzeń, ≥ 30 % | ρ rdzeń, ≥ 50 % | udział ludności rdzenia w masce ≥ 10 % | udział ludności rdzenia w masce ≥ 20 % | udział ludności rdzenia w masce ≥ 30 % | udział ludności rdzenia w masce ≥ 50 % |
|---|---|---|---|---|---|---|---|---|
| GZM * | 1,774 | 2,176 | 3,019 | brak danych (11,64) | 93 % | 77 % | 40 % | 1 % |
| Kraków | 1,168 | 1,402 | 1,860 | brak danych (7,064) | 95 % | 78 % | 45 % | 1 % |
| Łódź | 1,046 | 1,224 | 1,547 | brak danych (4,400) | 96 % | 83 % | 50 % | 1 % |
| Poznań | 1,059 | 1,224 | 1,547 | brak danych (4,501) | 96 % | 84 % | 54 % | 1 % |
| Trójmiasto * | 2,345 | 2,776 | 3,670 | brak danych (11,52) | 95 % | 79 % | 49 % | 1 % |
| Warszawa | 1,094 | 1,256 | 1,593 | brak danych (4,326) | 97 % | 87 % | 58 % | 1 % |
| Wrocław | 1,152 | 1,326 | 1,648 | brak danych (4,208) | 96 % | 85 % | 56 % | 3 % |
| Białystok | 1,108 | 1,249 | 1,538 | brak danych (4,860) | 97 % | 88 % | 64 % | 1 % |
| Bydgoszcz–Toruń * | 4,747 | 5,339 | 6,539 | brak danych (31,20) | 97 % | 84 % | 62 % | 2 % |
| Kielce | 1,038 | 1,196 | 1,544 | brak danych (6,293) | 97 % | 84 % | 52 % | 0 % |
| Lublin | 1,069 | 1,244 | 1,585 | brak danych (5,860) | 95 % | 82 % | 52 % | 0 % |
| Rzeszów | 1,030 | 1,195 | 1,526 | brak danych (4,553) | 93 % | 76 % | 46 % | 3 % |
| Szczecin | 1,356 | 1,569 | 1,684 | brak danych (3,879) | 92 % | 78 % | 36 % | 2 % |

Tabela 6. Ranking miast jednocentrowych według ρ FUA przy każdym progu i zgodność rankingów.

| Próg | Miasta jednocentrowe od najniższego ρ FUA |
|---|---|
| ≥ 10 % | Białystok 1,081, Wrocław 1,102, Warszawa 1,171, Poznań 1,184, Łódź 1,192, Kraków 1,323, Lublin 1,413, Kielce 1,525, Szczecin 1,532, Rzeszów 1,647 |
| ≥ 20 % | Białystok 1,240, Wrocław 1,287, Poznań 1,330, Łódź 1,391, Lublin 1,402, Warszawa 1,406, Kraków 1,442, Kielce 1,448, Rzeszów 1,645, Szczecin 1,670 |
| ≥ 30 % | Białystok 1,511, Kielce 1,545, Rzeszów 1,579, Wrocław 1,583, Poznań 1,630, Warszawa 1,649, Szczecin 1,718, Lublin 1,810, Łódź 1,841, Kraków 1,868 |
| ≥ 50 % | brak danych |

| Progi | Miast | Korelacja Spearmana rankingów ρ FUA |
|---|---|---|
| 10 % vs 20 % | 10 | 0,8909 |
| 10 % vs 30 % | 10 | 0,1758 |
| 20 % vs 30 % | 10 | 0,2000 |

**Jak czytać wartości:**

- **ρ > 1 wszędzie (każda aglomeracja, domena i próg z wartością).** To nie jest błąd liczenia; sprawdzone (sekcja 8). Maska jest
  „netto”: zawiera tylko komórki 100 m z wysokim udziałem powierzchni budynków. W polskich miastach parki, doliny rzek,
  tereny kolejowe i luźna zabudowa blokowa wypadają z maski. Pole A jest więc małe w stosunku do rozpiętości miasta, a
  maska ma kształt gwiazdy (pasma wzdłuż dróg), nie koła. Dla kształtu niekołowego średnia odległość od centrum jest
  większa niż ⅔R nawet przy równomiernej gęstości.
- **Porównanie z Bertaudem i Malpezzim (2003): sekcja 4a.** Dla rdzenia przy progu 10 %, czyli przy terenie
  zabudowanym najbliższym ich definicji, ρ Warszawy i Krakowa jest bliskie ich wartościom z lat 90.; wartości FUA przy
  20 % są wyższe z konstrukcji (maska netto, cała FUA).
- **Próg zmienia poziom ρ i, powyżej 20 %, także kolejność miast:**
  - 10 %: maska 82–865 km², 70–89 % ludności FUA;
  - 20 %: 48–446 km², 42–72 %;
  - 30 %: 16–195 km², tylko 20–43 %;
  - 50 %: 0–6 km² i < 5 % ludności, więc ρ to „brak danych”;
  - ranking miast jednocentrowych przy 10 % i 20 % jest zgodny (Spearman 0,8909),
    przy 30 % się rozsypuje (Spearman z 20 %: 0,2000). Maska 30 % to głównie
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
| GZM * | 3,539 (84 km²) | 2,161 (219 km²) | 2,095 (242 km²) | 2,102 (264 km²) | 2,076 (281 km²) | 2,073 (284 km²) | 2,071 (290 km²) | 2,8 % |
| Kraków | 1,975 (30 km²) | 1,434 (87 km²) | 1,439 (115 km²) | 1,442 (133 km²) | 1,490 (147 km²) | 1,545 (160 km²) | 1,696 (183 km²) | 0,0 % |
| Łódź | 1,310 (57 km²) | 1,418 (114 km²) | 1,395 (127 km²) | 1,391 (130 km²) | 1,469 (139 km²) | 1,467 (141 km²) | 1,526 (162 km²) | 0,0 % |
| Poznań | 1,773 (42 km²) | 1,252 (125 km²) | 1,299 (145 km²) | 1,330 (151 km²) | 1,430 (172 km²) | 1,430 (176 km²) | 1,511 (196 km²) | 0,0 % |
| Trójmiasto * | 3,249 (63 km²) | 2,781 (96 km²) | 3,347 (119 km²) | 3,077 (141 km²) | 3,055 (145 km²) | 3,031 (148 km²) | 3,008 (151 km²) | 5,6 % |
| Warszawa | 1,477 (107 km²) | 1,482 (187 km²) | 1,261 (375 km²) | 1,406 (446 km²) | 1,410 (492 km²) | 1,422 (520 km²) | 1,424 (531 km²) | 0,2 % |
| Wrocław | 1,325 (38 km²) | 1,278 (85 km²) | 1,266 (92 km²) | 1,287 (111 km²) | 1,284 (117 km²) | 1,347 (123 km²) | 1,461 (148 km²) | 0,0 % |
| Białystok | 1,146 (22 km²) | 1,225 (43 km²) | 1,206 (48 km²) | 1,240 (51 km²) | 1,265 (54 km²) | 1,271 (55 km²) | 1,306 (59 km²) | 0,0 % |
| Bydgoszcz–Toruń * | 6,956 (48 km²) | 5,454 (72 km²) | 5,347 (81 km²) | 5,290 (83 km²) | 5,195 (96 km²) | 4,904 (108 km²) | 4,660 (133 km²) | 0,0 % |
| Kielce | 1,269 (21 km²) | 1,204 (27 km²) | 1,271 (40 km²) | 1,448 (48 km²) | 1,625 (57 km²) | 1,696 (60 km²) | 1,918 (70 km²) | 0,0 % |
| Lublin | 1,309 (36 km²) | 1,230 (49 km²) | 1,409 (58 km²) | 1,402 (60 km²) | 1,400 (63 km²) | 1,424 (67 km²) | 1,874 (94 km²) | 0,0 % |
| Rzeszów | 1,222 (24 km²) | 1,225 (33 km²) | 1,310 (48 km²) | 1,645 (59 km²) | 1,699 (67 km²) | 1,717 (69 km²) | 2,050 (83 km²) | 2,0 % |
| Szczecin | 1,350 (28 km²) | 1,329 (39 km²) | 1,321 (41 km²) | 1,670 (57 km²) | 1,672 (59 km²) | 1,666 (60 km²) | 1,830 (66 km²) | 0,9 % |

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
| GZM * | 9 | 0,4848 | 0,5658 | 0,6855 | brak danych (2,015) | 1,697 | 3,460 |
| Trójmiasto * | 3 | 1,142 | 1,390 | 1,853 | brak danych (4,029) | 2,408 | 6,201 |
| Bydgoszcz–Toruń * | 2 | 1,149 | 1,227 | 1,440 | brak danych (3,030) | 1,736 | 4,209 |

- **GZM:** ρ jednocentrowe (2,102 przy 20 %) mierzy przede wszystkim to, że Katowice nie są jedynym
  centrum. Wariant do najbliższego z 9 centrów spada poniżej 1. Na grafiki tylko wariant opisany jako inna miara albo
  wcale.
- **Trójmiasto:** wynik z wyraźnym zastrzeżeniem. Miasto jest liniowe (ok. 35 km wzdłuż brzegu), a koło o polu maski
  wychodzi w morze. ρ = 3,077 przy centrum Gdańsk Główny.
- **Bydgoszcz–Toruń:** ρ ok. 5 to artefakt dwóch ośrodków odległych o ok. 42 km (oba miasta w masce, zarodki przy obu
  centrach). Do tabel tylko wariant N centrów.

## 4a. Porównanie z Bertaudem i Malpezzim (2003)

Tabela B. Warszawa i Kraków: wartości z tabeli 1 Bertauda i Malpezziego (2003; dane z lat 90.) i wartości projektu.
W nawiasach wariant z surowym GHSL. Gradient Bertauda i Malpezziego podajemy jako wartość dodatnią (u nich −0,170 i
−0,174 na km), tak jak b w modelu Clarka.

| Miasto | B&M ρ | ρ rdzeń 10 % (surowy GHSL) | ρ rdzeń 20 % | ρ FUA 20 % | B&M gradient, 1/km | Clark b FUA (surowy) | B&M teren zabudowany, km² | maska rdzenia 10 %, km² | B&M os./ha zabudowy | os./ha w masce rdzenia 10 % (surowy) | B&M ludność | ludność w masce rdzenia 10 % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 0,99 | 1,094 (1,054) | 1,256 | 1,406 | 0,170 | 0,162 (0,166) | 235 | 266 | 70 | 68 (65) | 1 639 675 | 1 810 980 |
| Kraków | 1,18 | 1,168 (1,178) | 1,402 | 1,442 | 0,174 | 0,170 (0,168) | 112 | 134 | 65 | 56 (54) | 730 600 | 751 015 |

**Różnice definicji:**

- **Dekada:** ludność miast z lat 90. (Warszawa 1,64 mln, Kraków 0,73 mln) wobec NSP 2021 rozłożonego wzorem GHSL 2020.
- **Teren zabudowany:** Bertaud i Malpezzi liczą gęstość w obwodach spisowych netto, po odjęciu tylko dużych terenów
  niezabudowanych (duże parki, jeziora, pasy zieleni, tereny górzyste). Nasza maska to komórki 100 m z co najmniej 10 % powierzchni pod
  budynkami (GHS-BUILT-S), spójne z centrum; przy 20 % wypada z niej znacznie więcej terenu.
- **Obszar:** u nich miasto (zabudowa miasta), u nas rdzeń URAU (granica miasta) albo FUA.
- **Gradient:** u nich obwody zabudowy miasta, u nas pierścienie 1–25 km całej FUA; ich centrum to CBD, nasze to
  centrum z `config.yaml`.
- **Próba:** zbierana miasto po mieście przez ok. dekadę, nie zharmonizowana.

**Wynik:** przy definicji najbliższej ich terenowi zabudowanemu (rdzeń, próg 10 %) ρ Warszawy wynosi
1,094 wobec 0,99, a Krakowa 1,168 wobec 1,18; pole maski
(266 i 134 km²) i liczba mieszkańców na hektar
zabudowy (68 i 56) są tego samego rzędu co
u nich (235 i 112 km², 70 i 65 os./ha). Gradienty Clarka (0,162 i 0,170 na km)
różnią się od ich wartości o kilka tysięcznych. Zgodność jest wskazówką, nie dowodem: inne dane, inna dekada, inny
obszar dopasowania gradientu. Wartości FUA przy progu 20 % (Warszawa 1,406, Kraków
1,442) są wyższe z konstrukcji i nie należy ich zestawiać z liczbami Bertauda i Malpezziego.

## 4b. Wrażliwość ρ i r50 na wybór centrum

Trzy centra: centrum z `config.yaml`, ratusz miasta rdzenia (OSM `amenity=townhall`, stan 2026-11-22; miasto
rdzenia to pierwsze miasto URAU z listy, czyli Katowice, Gdańsk, Bydgoszcz w aglomeracjach wielomiejskich) i środek
ciężkości ludności rdzenia (siatka przeskalowana, cały rdzeń URAU, w GZM 13 miast, w Trójmieście trzy, w
Bydgoszczy–Toruniu dwa). Maska zabudowy jest ta sama dla trzech centrów (zarodki z `config.yaml`), zmieniają się
tylko odległości. Reguła wyboru ratusza: obiekt z `townhall:type=city`, jeżeli jest jeden; inaczej jedyny o nazwie
„Urząd Miasta / Urząd Miejski / Magistrat”, który nie jest urzędem dzielnicy ani wydziałem; inaczej wybór ręczny.

Tabela C1. Centra i odległości od centrum z `config.yaml`.

| Aglomeracja | Centrum z config.yaml | Ratusz (OSM) | Wybór ratusza | config–ratusz, km | config–środek ciężkości, km | Środek ciężkości (lat, lon) |
|---|---|---|---|---|---|---|
| GZM * | Katowice Rynek | Urząd Miasta Katowice (way/202209404) | ręcznie | 0,14 | 4,58 | 50,2797, 18,9657 |
| Kraków | Rynek Główny | Urząd Miasta Krakowa (node/4017203772) | ręcznie | 0,31 | 2,05 | 50,0575, 19,9652 |
| Łódź | pl. Wolności | Urząd Miasta Łodzi (node/1880701425) | ręcznie | 1,38 | 1,60 | 51,7631, 19,4617 |
| Poznań | Stary Rynek | Urząd Miasta Poznania (relation/5442363) | ręcznie | 0,26 | 1,14 | 52,4088, 16,9175 |
| Trójmiasto * | Gdańsk Główny | Urząd Miejski w Gdańsku (node/14330910588) | townhall:type=city | 0,50 | 8,58 | 54,4175, 18,5652 |
| Warszawa | Rondo Dmowskiego | Urząd Miasta Stołecznego Warszawy (way/29388083) | nazwa | 1,67 | 0,30 | 52,2320, 21,0140 |
| Wrocław | Rynek | Urząd Miejski (way/101131393) | nazwa | 0,05 | 1,05 | 51,1113, 17,0171 |
| Białystok | Rynek Kościuszki | Urząd Miejski w Białymstoku (way/548685792) | ręcznie | 0,92 | 0,95 | 53,1339, 23,1449 |
| Bydgoszcz–Toruń * | Bydgoszcz, Stary Rynek | Urząd Miasta Bydgoszczy (way/88520891) | ręcznie | 0,09 | 17,07 | 53,0907, 18,2500 |
| Kielce | Rynek | Urząd Miasta Kielce (node/6588785827) | ręcznie | 0,10 | 0,53 | 50,8745, 20,6261 |
| Lublin | pl. Litewski | Urząd Miasta Lublin (way/66264120) | nazwa | 0,39 | 1,08 | 51,2407, 22,5500 |
| Rzeszów | Rynek | Ratusz Miejski (way/149933478) | townhall:type=city | 0,08 | 0,88 | 50,0309, 21,9983 |
| Szczecin | Brama Portowa | Urząd Miasta Szczecin (relation/537297) | townhall:type=city | 1,53 | 0,94 | 53,4278, 14,5628 |

Wybory ręczne (siedziby prezydentów według wiedzy ogólnej, nie sprawdzane w BIP):

- GZM: townhall:type=city ma punkt 'Biuro Obsługi Mieszkańców'; wybrano budynek Urzędu Miasta Katowice, ul. Młyńska 4 (ok. 80 m dalej)
- Kraków: 3 obiekty 'Urząd Miasta Krakowa'; wybrano pl. Wszystkich Świętych 3 (Pałac Wielopolskich, siedziba prezydenta), pozostałe to budynki urzędu (al. Powstania Warszawskiego, os. Zgody)
- Łódź: 3 obiekty z nazwą UMŁ; wybrano ul. Piotrkowska 104 (siedziba prezydenta); Piotrkowska 175 i pl. Komuny Paryskiej to inne budynki urzędu
- Poznań: 3 obiekty 'Urząd Miasta Poznania'; wybrano pl. Kolegiacki 17 (siedziba prezydenta); Ratusz na Starym Rynku to muzeum
- Białystok: 2 obiekty Urzędu Miejskiego; wybrano ul. Słonimska 1 (siedziba prezydenta), drugi to departament obsługi mieszkańców
- Bydgoszcz–Toruń: townhall:type=city ma oddział ul. Gawędy 5 (Fordon, ok. 10 km od centrum); wybrano ul. Jezuicka 1 (Ratusz, Stary Rynek)
- Kielce: kilka budynków 'Urząd Miasta Kielce'; wybrano Rynek 1 (siedziba prezydenta)

Tabela C2. ρ i r50 dla trzech centrów (kolejno: config / ratusz / środek ciężkości) i rozrzut (maks. − min.).

| Aglomeracja | ρ FUA 20 %: config / ratusz / środek | ρ rdzeń 10 % | ρ rdzeń 20 % | r50 (i) FUA, km | r50 rdzeń, km | rozrzut ρ FUA 20 % | rozrzut ρ rdzeń 10 % | rozrzut r50 FUA, km |
|---|---|---|---|---|---|---|---|---|
| GZM * | 2,102 / 2,100 / 1,953 | 1,774 / 1,773 / 1,679 | 2,176 / 2,175 / 2,039 | 13,07 / 13,06 / 12,75 | 11,83 / 11,86 / 11,70 | 0,1487 | 0,09446 | 0,32 |
| Kraków | 1,442 / 1,442 / 1,381 | 1,168 / 1,171 / 1,111 | 1,402 / 1,407 / 1,336 | 7,814 / 7,807 / 7,296 | 5,149 / 5,118 / 4,797 | 0,06097 | 0,05940 | 0,52 |
| Łódź | 1,391 / 1,354 / 1,359 | 1,046 / 1,004 / 1,004 | 1,224 / 1,169 / 1,169 | 6,106 / 5,868 / 5,872 | 4,545 / 4,089 / 4,066 | 0,03692 | 0,04243 | 0,24 |
| Poznań | 1,330 / 1,330 / 1,300 | 1,059 / 1,064 / 1,020 | 1,224 / 1,230 / 1,170 | 6,630 / 6,686 / 6,431 | 3,928 / 3,897 / 3,922 | 0,03012 | 0,04395 | 0,25 |
| Trójmiasto * | 3,077 / 3,095 / 2,546 | 2,345 / 2,368 / 1,897 | 2,776 / 2,805 / 2,253 | 12,06 / 12,00 / 10,65 | 6,843 / 6,929 / 8,435 | 0,5495 | 0,4713 | 1,41 |
| Warszawa | 1,406 / 1,420 / 1,407 | 1,094 / 1,108 / 1,095 | 1,256 / 1,274 / 1,256 | 11,10 / 11,29 / 11,09 | 6,492 / 6,341 / 6,471 | 0,01434 | 0,01368 | 0,20 |
| Wrocław | 1,287 / 1,287 / 1,291 | 1,152 / 1,152 / 1,145 | 1,326 / 1,326 / 1,320 | 6,125 / 6,132 / 6,070 | 4,219 / 4,217 / 4,095 | 0,004090 | 0,006983 | 0,06 |
| Białystok | 1,240 / 1,335 / 1,205 | 1,108 / 1,217 / 1,063 | 1,249 / 1,378 / 1,195 | 4,239 / 4,747 / 3,970 | 2,991 / 3,223 / 2,733 | 0,1299 | 0,1544 | 0,78 |
| Bydgoszcz–Toruń * | 5,290 / 5,302 / 5,740 | 4,747 / 4,759 / 4,996 | 5,339 / 5,353 / 5,924 | 18,75 / 18,75 / 22,46 | 7,650 / 7,639 / 18,59 | 0,4504 | 0,2488 | 3,71 |
| Kielce | 1,448 / 1,445 / 1,441 | 1,038 / 1,034 / 1,026 | 1,196 / 1,191 / 1,182 | 7,899 / 7,884 / 7,819 | 2,406 / 2,390 / 2,366 | 0,007051 | 0,01163 | 0,08 |
| Lublin | 1,402 / 1,412 / 1,387 | 1,069 / 1,095 / 1,031 | 1,244 / 1,276 / 1,200 | 6,912 / 6,926 / 6,945 | 3,072 / 3,133 / 3,096 | 0,02478 | 0,06412 | 0,03 |
| Rzeszów | 1,645 / 1,644 / 1,663 | 1,030 / 1,024 / 1,002 | 1,195 / 1,188 / 1,171 | 8,797 / 8,791 / 8,750 | 2,657 / 2,640 / 2,659 | 0,01890 | 0,02718 | 0,05 |
| Szczecin | 1,670 / 1,588 / 1,727 | 1,356 / 1,307 / 1,399 | 1,569 / 1,510 / 1,631 | 4,761 / 4,294 / 5,219 | 3,661 / 3,068 / 3,932 | 0,1383 | 0,09156 | 0,93 |

- **Odległość centrum od środka ciężkości ludności** w miastach jednocentrowych wynosi
  0,3–2,1 km;
  największa: Kraków 2,1 km, Łódź 1,6 km, Poznań 1,1 km.
  Bertaud i Malpezzi wymieniają Kraków jako miasto z CBD przesuniętym względem środka ciężkości ludności.
- **Rozrzut ρ FUA (20 %)** w miastach jednocentrowych: 0,004090–0,1383. To tyle, ile
  dzielą sąsiednie miasta w rankingu (tabela 6), więc kolejność miast o podobnym ρ zależy od wyboru centrum; różnice
  większe niż rozrzut są na wybór centrum odporne.
- **Aglomeracje wielomiejskie:** środek ciężkości rdzenia GZM, Trójmiasta i Bydgoszczy–Torunia leży między miastami
  (dla Bydgoszczy–Torunia ok. 17 km od Starego Rynku w Bydgoszczy); te wartości pokazują tylko, że ρ jednocentrowe nie ma
  tam sensu.

## 5. Gini i η (§4.4, tylko QA, nie na grafiki)

Tabela 8. Gini znormalizowany (G/Gmax) i η. Rozdzielczość 100 m; domeny stałe: maska ≥ 20 % oraz
koło 10 km.

| Aglomeracja | G/Gmax maska | η maska | próg LouBar maska, os./km² | hotspoty | komórki | G/Gmax koło 10 km | η koło | próg LouBar koło | hotspoty |
|---|---|---|---|---|---|---|---|---|---|
| GZM * | 0,5138 | 0,8481 | 11 834 | 3323 | 26429 | 0,7656 | 0,8489 | 11 086 | 1665 |
| Kraków | 0,5476 | 0,4807 | 14 961 | 1127 | 13298 | 0,7636 | 0,6480 | 14 424 | 1253 |
| Łódź | 0,5359 | 0,6300 | 13 367 | 1366 | 12979 | 0,7837 | 0,5752 | 12 951 | 1371 |
| Poznań | 0,5312 | 0,4596 | 10 184 | 1689 | 15123 | 0,7668 | 0,5607 | 10 183 | 1694 |
| Trójmiasto * | 0,5040 | 0,7800 | 12 484 | 1555 | 14066 | 0,8284 | 0,6425 | 11 178 | 1254 |
| Warszawa | 0,5322 | 0,4453 | 13 780 | 4636 | 44562 | 0,6575 | 0,8168 | 15 430 | 3071 |
| Wrocław | 0,5289 | 0,4949 | 12 980 | 1250 | 11107 | 0,8071 | 0,5337 | 12 703 | 1317 |
| Białystok | 0,4957 | 0,5582 | 9 717 | 914 | 5148 | 0,8679 | 0,3844 | 8 840 | 1099 |
| Bydgoszcz–Toruń * | 0,5394 | 0,8464 | 11 909 | 1125 | 8311 | 0,8890 | 0,4273 | 10 783 | 773 |
| Kielce | 0,5285 | 0,3409 | 9 361 | 561 | 4827 | 0,8873 | 0,3188 | 8 718 | 668 |
| Lublin | 0,5126 | 0,8176 | 10 482 | 900 | 5974 | 0,8397 | 0,4758 | 9 340 | 1075 |
| Rzeszów | 0,4566 | 0,3013 | 7 056 | 620 | 5880 | 0,8097 | 0,3069 | 6 052 | 793 |
| Szczecin | 0,5420 | 0,6856 | 13 797 | 638 | 5669 | 0,8742 | 0,5371 | 12 510 | 744 |

- Gini w kole jest wyższy niż w masce, bo koło zawiera tereny niezamieszkane. To dokładnie efekt, przed którym brief
  ostrzega przy liczeniu na FUA.
- η w masce: najwyższe dla GZM 0,8481, Bydgoszcz–Toruń 0,8464, Lublin 0,8176, Trójmiasto 0,7800. Aglomeracje policentryczne lub liniowe są w czołówce, co
  odpowiada policentryczności. Wśród miast jednocentrowych najniższe η: Rzeszów 0,3013, Kielce 0,3409, Warszawa 0,4453 (hotspoty skupione); najwyższe: Szczecin 0,6856, Lublin 0,8176.
- Wartości zależą od progu LouBar i rozdzielczości (zapisane w tabeli), więc służą tylko do opisu w RAPORT.md.
- **Gini zależy od siatki ludności bardziej niż pozostałe miary:** po przeskalowaniu do spisu G/Gmax w masce wynosi
  0,4566–0,5476 wobec 0,3977–0,4830 na surowym GHSL. Przeskalowanie zeruje ludność
  komórek spisowych bez mieszkańców (zakłady, porty, tereny usługowe) i podnosi blokowiska, a wewnątrz komórki 1 km
  stosuje jeden współczynnik, co daje skoki na granicach komórek. Gini nie powinien więc wychodzić poza QA.

## 5a. Siatka ludności: surowy GHSL a siatka przeskalowana do NSP 2021

Tabela V1. Miary 100 m na surowym GHS-POP 2020 → na siatce przeskalowanej (zmiana względna). Maska zabudowy i
centra bez zmian.

| Aglomeracja | ρ FUA 10 % | ρ FUA 20 % | ρ rdzeń 10 % | ρ rdzeń 20 % | r50 (i) FUA, km | r50 rdzeń, km | Clark b, 1/km | G/Gmax maska | η maska |
|---|---|---|---|---|---|---|---|---|---|
| GZM * | 1,675 → 1,657 (−1,1 %) | 2,123 → 2,102 (−1,0 %) | 1,800 → 1,774 (−1,5 %) | 2,204 → 2,176 (−1,3 %) | 13,10 → 13,07 (−0,3 %) | 11,81 → 11,83 (+0,2 %) | 0,08246 → 0,09399 (+14,0 %) | 0,4077 → 0,5138 (+26,0 %) | 0,7682 → 0,8481 (+10,4 %) |
| Kraków | 1,348 → 1,323 (−1,9 %) | 1,455 → 1,442 (−0,9 %) | 1,178 → 1,168 (−0,8 %) | 1,392 → 1,402 (+0,7 %) | 8,553 → 7,814 (−8,6 %) | 5,010 → 5,149 (+2,8 %) | 0,1684 → 0,1702 (+1,0 %) | 0,4403 → 0,5476 (+24,4 %) | 0,4245 → 0,4807 (+13,2 %) |
| Łódź | 1,201 → 1,192 (−0,8 %) | 1,386 → 1,391 (+0,3 %) | 1,046 → 1,046 (−0,0 %) | 1,207 → 1,224 (+1,3 %) | 6,420 → 6,106 (−4,9 %) | 4,358 → 4,545 (+4,3 %) | 0,2125 → 0,2086 (−1,8 %) | 0,4127 → 0,5359 (+29,8 %) | 0,5797 → 0,6300 (+8,7 %) |
| Poznań | 1,165 → 1,184 (+1,6 %) | 1,320 → 1,330 (+0,8 %) | 1,107 → 1,059 (−4,3 %) | 1,261 → 1,224 (−2,9 %) | 7,018 → 6,630 (−5,5 %) | 4,172 → 3,928 (−5,8 %) | 0,1878 → 0,1842 (−1,9 %) | 0,4394 → 0,5312 (+20,9 %) | 0,4337 → 0,4596 (+6,0 %) |
| Trójmiasto * | 2,450 → 2,413 (−1,5 %) | 3,138 → 3,077 (−2,0 %) | 2,365 → 2,345 (−0,9 %) | 2,816 → 2,776 (−1,4 %) | 12,85 → 12,06 (−6,2 %) | 7,322 → 6,843 (−6,5 %) | 0,1065 → 0,1095 (+2,9 %) | 0,3977 → 0,5040 (+26,8 %) | 0,9026 → 0,7800 (−13,6 %) |
| Warszawa | 1,167 → 1,171 (+0,4 %) | 1,397 → 1,406 (+0,6 %) | 1,054 → 1,094 (+3,9 %) | 1,205 → 1,256 (+4,2 %) | 10,96 → 11,10 (+1,2 %) | 6,323 → 6,492 (+2,7 %) | 0,1665 → 0,1622 (−2,6 %) | 0,4830 → 0,5322 (+10,2 %) | 0,3729 → 0,4453 (+19,4 %) |
| Wrocław | 1,049 → 1,102 (+5,1 %) | 1,227 → 1,287 (+4,9 %) | 1,109 → 1,152 (+3,9 %) | 1,270 → 1,326 (+4,4 %) | 5,902 → 6,125 (+3,8 %) | 4,010 → 4,219 (+5,2 %) | 0,2061 → 0,2042 (−0,9 %) | 0,4743 → 0,5289 (+11,5 %) | 0,4407 → 0,4949 (+12,3 %) |
| Białystok | 1,042 → 1,081 (+3,7 %) | 1,218 → 1,240 (+1,9 %) | 1,110 → 1,108 (−0,2 %) | 1,257 → 1,249 (−0,6 %) | 4,109 → 4,239 (+3,2 %) | 2,960 → 2,991 (+1,0 %) | 0,2117 → 0,2187 (+3,3 %) | 0,4172 → 0,4957 (+18,8 %) | 0,5946 → 0,5582 (−6,1 %) |
| Bydgoszcz–Toruń * | 4,046 → 4,097 (+1,3 %) | 5,182 → 5,290 (+2,1 %) | 4,668 → 4,747 (+1,7 %) | 5,241 → 5,339 (+1,9 %) | 19,10 → 18,75 (−1,8 %) | 6,236 → 7,650 (+22,7 %) | 0,1768 → 0,1731 (−2,1 %) | 0,4077 → 0,5394 (+32,3 %) | 0,8173 → 0,8464 (+3,6 %) |
| Kielce | 1,505 → 1,525 (+1,3 %) | 1,461 → 1,448 (−0,9 %) | 1,067 → 1,038 (−2,8 %) | 1,222 → 1,196 (−2,2 %) | 7,524 → 7,899 (+5,0 %) | 2,426 → 2,406 (−0,9 %) | 0,1488 → 0,1452 (−2,4 %) | 0,4177 → 0,5285 (+26,5 %) | 0,3457 → 0,3409 (−1,4 %) |
| Lublin | 1,407 → 1,413 (+0,4 %) | 1,381 → 1,402 (+1,6 %) | 1,064 → 1,069 (+0,5 %) | 1,225 → 1,244 (+1,5 %) | 6,976 → 6,912 (−0,9 %) | 3,173 → 3,072 (−3,2 %) | 0,1590 → 0,1623 (+2,1 %) | 0,4039 → 0,5126 (+26,9 %) | 0,7504 → 0,8176 (+9,0 %) |
| Rzeszów | 1,545 → 1,647 (+6,7 %) | 1,517 → 1,645 (+8,4 %) | 0,9367 → 1,030 (+9,9 %) | 1,131 → 1,195 (+5,6 %) | 7,684 → 8,797 (+14,5 %) | 2,483 → 2,657 (+7,0 %) | 0,1203 → 0,1313 (+9,2 %) | 0,4739 → 0,4566 (−3,7 %) | 0,2939 → 0,3013 (+2,5 %) |
| Szczecin | 1,542 → 1,532 (−0,6 %) | 1,676 → 1,670 (−0,4 %) | 1,283 → 1,356 (+5,7 %) | 1,499 → 1,569 (+4,7 %) | 4,597 → 4,761 (+3,6 %) | 3,473 → 3,661 (+5,4 %) | 0,1776 → 0,1975 (+11,2 %) | 0,4299 → 0,5420 (+26,1 %) | 0,5346 → 0,6856 (+28,2 %) |

Tabela V2. Kolejność miast jednocentrowych według ρ FUA, oba warianty.

| Próg | Surowy GHSL | Przeskalowany do NSP | Kolejność |
|---|---|---|---|
| ≥ 10 % | Białystok, Wrocław, Poznań, Warszawa, Łódź, Kraków, Lublin, Kielce, Szczecin, Rzeszów | Białystok, Wrocław, Warszawa, Poznań, Łódź, Kraków, Lublin, Kielce, Szczecin, Rzeszów | zmiana (Spearman 0,9879) |
| ≥ 20 % | Białystok, Wrocław, Poznań, Lublin, Łódź, Warszawa, Kraków, Kielce, Rzeszów, Szczecin | Białystok, Wrocław, Poznań, Łódź, Lublin, Warszawa, Kraków, Kielce, Rzeszów, Szczecin | zmiana (Spearman 0,9879) |
| ≥ 30 % | Kielce, Rzeszów, Białystok, Wrocław, Warszawa, Szczecin, Poznań, Lublin, Łódź, Kraków | Białystok, Kielce, Rzeszów, Wrocław, Poznań, Warszawa, Szczecin, Lublin, Łódź, Kraków | zmiana (Spearman 0,9273) |

Tabela V3. Stwierdzenia z RAPORT.md §14 i tej notatki policzone na obu siatkach.

| Stwierdzenie (RAPORT §14 / ta notatka) | Surowy GHSL | Przeskalowany do NSP | Inny wynik (także liczbowo)? |
|---|---|---|---|
| Udział ludności FUA w masce ≥ 10 % (zakres 13 aglomeracji) | 69–89 % | 70–89 % | tak |
| Udział ludności FUA w masce ≥ 20 % (zakres 13 aglomeracji) | 46–73 % | 42–72 % | tak |
| Udział ludności FUA w masce ≥ 30 % (zakres 13 aglomeracji) | 24–46 % | 20–43 % | tak |
| Korelacja rang ρ FUA, progi 10 % i 20 % (miasta jednocentrowe) | 0,9030 | 0,8909 | tak |
| Korelacja rang ρ FUA, progi 20 % i 30 % | -0,09091 | 0,2000 | tak |
| Kolejność miast jednocentrowych wg ρ FUA, 10 % (od najniższego) | Białystok, Wrocław, Poznań, Warszawa, Łódź, Kraków, Lublin, Kielce, Szczecin, Rzeszów | Białystok, Wrocław, Warszawa, Poznań, Łódź, Kraków, Lublin, Kielce, Szczecin, Rzeszów | tak |
| Kolejność miast jednocentrowych wg ρ FUA, 20 % (od najniższego) | Białystok, Wrocław, Poznań, Lublin, Łódź, Warszawa, Kraków, Kielce, Rzeszów, Szczecin | Białystok, Wrocław, Poznań, Łódź, Lublin, Warszawa, Kraków, Kielce, Rzeszów, Szczecin | tak |
| ρ < 1 (wyjątki od „ρ > 1 prawie wszędzie”) | Rzeszów rdzeń 10 % (0,9367) | brak | tak |
| Warszawa: ρ FUA 20 % przy tolerancji luki 0–1 400 m | 1,234–1,433 | 1,261–1,482 | tak |
| GZM: ρ do najbliższego z 9 centrów, 20 % | 0,5951 | 0,5658 | tak |
| Bydgoszcz–Toruń: ρ FUA 20 % | 5,182 | 5,290 | tak |
| Warszawa: udział do 10 km, wariant (i) FUA (5 miast jednocentrowych fazy 1) | 46,3 %, miejsce 5 z 5 (1 = najwyższy udział) | 45,5 %, miejsce 5 z 5 (1 = najwyższy udział) | tak |
| Warszawa: udział do 10 km, wariant (ii) bez granic | 51,3 %, miejsce 4 z 5 (1 = najwyższy udział) | 50,0 %, miejsce 4 z 5 (1 = najwyższy udział) | tak |
| Maks. różnica krzywej skumulowanej względem NSP 1 km, (i), bez Rzeszowa | 4,473 pp | 2,302 pp | tak |
| To samo, Rzeszów | 7,355 pp | 0,7939 pp | tak |
| η w masce: dwie najwyższe wartości | Trójmiasto, Bydgoszcz–Toruń | GZM, Bydgoszcz–Toruń | tak |
| η w masce, miasta jednocentrowe: trzy najniższe | Rzeszów, Kielce, Warszawa | Rzeszów, Kielce, Warszawa | nie |
| Clark b: kolejność 5 miast jednocentrowych fazy 1 (od najbardziej stromego) | Łódź, Wrocław, Poznań, Kraków, Warszawa | Łódź, Wrocław, Poznań, Kraków, Warszawa | nie |
| r50 (i) FUA: kolejność 5 miast jednocentrowych fazy 1 (od najmniejszego) | Wrocław, Łódź, Poznań, Kraków, Warszawa | Łódź, Wrocław, Poznań, Kraków, Warszawa | tak |

## 5b. Stopień urbanizacji (DEGURBA) na siatce spisowej 1 km

Tabela D. Udział ludności FUA i rdzenia (NSP 2021, komórki 1 km o środku w obszarze) w komórkach centrum miejskiego,
skupiska miejskiego (poza centrum) i wiejskich. Klasyfikacja na całej krajowej siatce spisowej według reguł Eurostatu
(DEGURBA poziom 1, wydanie 2021), w uproszczeniu: centrum miejskie = komórki ≥ 1 500 os./km² połączone krawędziami,
skupisko ≥ 50 000 mieszkańców, potem wypełnienie luk (komórka z ≥ 5 z 8 sąsiadów w centrum dołącza); skupisko miejskie
= komórki ≥ 300 os./km² połączone także narożnikami, ≥ 5 000 mieszkańców, bez komórek centrum. Bez reguły 50 % zabudowy
i bez podziału na gęste i półgęste skupiska.

| Aglomeracja | FUA: centrum miejskie | FUA: skupisko miejskie | FUA: wiejskie | rdzeń: centrum miejskie | rdzeń: skupisko | rdzeń: wiejskie |
|---|---|---|---|---|---|---|
| GZM * | 64,8 % | 26,8 % | 8,4 % | 81,0 % | 16,4 % | 2,6 % |
| Kraków | 50,1 % | 26,0 % | 23,9 % | 88,6 % | 9,8 % | 1,6 % |
| Łódź | 62,6 % | 21,7 % | 15,6 % | 90,3 % | 6,5 % | 3,2 % |
| Poznań | 54,9 % | 31,9 % | 13,2 % | 89,2 % | 9,6 % | 1,2 % |
| Trójmiasto * | 52,5 % | 37,5 % | 10,0 % | 75,6 % | 23,0 % | 1,5 % |
| Warszawa | 57,5 % | 26,1 % | 16,4 % | 91,9 % | 7,6 % | 0,5 % |
| Wrocław | 56,5 % | 24,9 % | 18,6 % | 84,4 % | 14,7 % | 0,9 % |
| Białystok | 60,3 % | 15,5 % | 24,2 % | 94,1 % | 5,4 % | 0,5 % |
| Bydgoszcz–Toruń * | 53,7 % | 18,6 % | 27,7 % | 88,5 % | 9,6 % | 1,9 % |
| Kielce | 38,0 % | 13,1 % | 48,9 % | 81,9 % | 15,1 % | 3,0 % |
| Lublin | 44,4 % | 19,2 % | 36,4 % | 91,3 % | 6,4 % | 2,3 % |
| Rzeszów | 31,1 % | 30,0 % | 38,9 % | 76,8 % | 20,8 % | 2,4 % |
| Szczecin | 55,3 % | 33,4 % | 11,3 % | 72,0 % | 25,4 % | 2,6 % |

**Kontrola z Eurostatem (HDENS_CLST_2021, centra miejskie 2021):** w Polsce nasze centra miejskie obejmują
28,0 % ludności siatki, Eurostatu 28,2 %; komórek: 2 214 i
2 249, wspólnych 2 194 (indeks Jaccarda 0,9669). Ludność komórek tylko
w naszych centrach: 9 455, tylko w centrach Eurostatu: 93 175.

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
- Surowy GHSL dawał krzywe skumulowane różniące się od spisu o 3–4 pp poza Rzeszowem; od 2026-11-24 miary 100 m
  liczymy na siatce przeskalowanej do spisu (1.6, 5a).
- Na poziomie komórek GHSL przesuwa ludność z blokowisk do centrów i stref przemysłowych. To trzeba opisać przy warstwie
  250 m i przy dostępności, gdzie GHSL wyznacza pochodzenia (§4.6).
- Warstwa 6c (BDOT10k, brief §13) jest właściwym lekarstwem.

## 7. Ograniczenia

- **Siatka 100 m to spis na 1 km i model wewnątrz komórki.** Profile, ρ, Gini i η mają poziom spisowy w każdej
  komórce 1 km, ale rozkład wewnątrz komórki dziedziczy błędy GHSL opisane w §6 (np. ludność na dachach hal obok
  blokowiska w tej samej komórce). PWD 250 m (`pwdens_ghsl_250m`) pozostaje na surowym GHSL.
- **ρ zależy od trzech decyzji metodycznych:** progu (tabela 5), reguły spójności (tabela 7) i centrum (sekcja 4b).
  Z literaturą (Bertaud i Malpezzi) porównywalny jest tylko rdzeń przy progu 10 % (sekcja 4a).
- **Daty się nie pokrywają:** GHSL to epoka 2020, NSP stan 31.03.2021, granice 2021. Migracje po 2021 r. i nowe
  osiedla nie są uwzględnione.
- **Rdzenie** to granice URAU (miasto). Dla GZM to 13 miast, dla Trójmiasta trzy.
- **Wariant (ii) profilu** pomija ludność za granicą państwa (Szczecin).
- **Gini i η liczone na próbie** maks. 4000 komórek (stałe ziarno). Błąd próbkowania średniej odległości
  szacujemy na < 1 %, ale tego nie mierzono.
- **Centra punktowe** z `config.yaml`. Wrażliwość na centrum: sekcja 4b (ratusz z OSM, środek ciężkości ludności).

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
     Warszawy jest 582 km² zabudowy z 76 % ludności według surowego GHSL).

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
8. **Przejście na siatkę przeskalowaną do spisu (2026-11-24) mało zmienia ρ i gradient Clarka:** ρ zwykle o
   1–5 % (Rzeszów do 10 %), gradient Clarka w pięciu jednocentrowych miastach fazy 1 o 1–3 % (GZM +14 %, Szczecin
   +11 %, Rzeszów +9 %), r50 o 1–9 % (Rzeszów +15 %, rdzeń Bydgoszczy–Torunia +23 %); tabela V1. Gini rośnie w 12
   aglomeracjach o 10–32 %, w Rzeszowie spada o 4 % (sekcja 5). Jedyny przypadek ρ < 1
   (rdzeń Rzeszowa przy 10 % na surowym GHSL) znika: GHSL zawyżał ludność centrum Rzeszowa (§6.2). Kolejność miast
   według ρ zmienia się tylko między miastami o prawie równych wartościach (tabela V2). **Zostaje; wynik główny na
   siatce przeskalowanej.**
9. **Tag `townhall:type=city` w OSM bywa na niewłaściwym obiekcie:** w Bydgoszczy na oddziale urzędu w Fordonie
   (ok. 10 km od centrum), w Katowicach na punkcie obsługi mieszkańców. Dlatego siedem ratuszy wybrano ręcznie
   (sekcja 4b). **Zostaje, z listą wyborów.**

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
  `data/interim/density/` (w tym `ghs_pop_census_scaled_100m_moll.tif`, `*_profile_*_raw.csv`, `townhalls_osm.csv`).
- Kod centrów (ratusze z OSM): `pipeline/density_centres.py`.
- BDL: `data/raw/bdl/*.json`, w manifeście jako `bdl_nsp2021_resident_gmina`, `bdl_nsp2021_national_gmina`.
- Polecenia (w tej kolejności): `python -m pipeline.grid250`, `python -m pipeline.density`,
  `python -m pipeline.density_control`, `python -m pipeline.density_qa`.
