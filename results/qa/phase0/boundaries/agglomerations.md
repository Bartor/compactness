# Faza 0: aglomeracje, granice i ludność (tabela wstępna)

Wygenerowano: 2026-11-23 (`python -m pipeline.phase0_boundaries`). Granice: Eurostat GISCO Urban Audit 2021
(skala 100K) i LAU 2021; GZM w **wariancie (a)**: suma FUA przecinających się z Metropolią GZM
(decyzja właściciela z 2026-11-23, patrz `gzm_variants.md`).

## Granice

| Aglomeracja | Faza | Kody FUA | Kody rdzenia (URAU) | Pow. FUA km² | Pow. rdzenia km² | Pow. adm. gmin rdzenia km² | Gmin w FUA | Gmin w rdzeniu |
|---|---|---|---|---|---|---|---|---|
| GZM | 1 | PL010F PL055F PL061F PL070F | PL010C PL054C PL055C PL056C PL057C PL059C PL061C PL066C PL069C PL070C PL072C PL074C PL075C | 2 592 | 1 062 | 1 063 | 39 | 13 |
| Kraków | 1 | PL003F | PL003C | 3 345 | 326,4 | 326,8 | 40 | 1 |
| Łódź | 1 | PL002F | PL002C | 2 520 | 292,9 | 293,3 | 26 | 1 |
| Poznań | 1 | PL005F | PL005C | 2 279 | 261,7 | 261,9 | 19 | 1 |
| Trójmiasto | 1 | PL006F PL053F | PL006C PL053C | 1 918 | 413,2 | 414,1 | 19 | 3 |
| Warszawa | 1 | PL001F | PL001C | 9 296 | 516,7 | 517,2 | 97 | 1 |
| Wrocław | 1 | PL004F | PL004C | 3 107 | 292,5 | 292,8 | 21 | 1 |
| Białystok | 2 | PL011F | PL011C | 3 881 | 102,2 | 102,1 | 22 | 1 |
| Bydgoszcz–Toruń | 2 | PL008F PL013F | PL008C PL013C | 4 253 | 291,3 | 291,7 | 28 | 2 |
| Kielce | 2 | PL012F | PL012C | 2 327 | 109,5 | 109,7 | 21 | 1 |
| Lublin | 2 | PL009F | PL009C | 3 555 | 147,5 | 147,4 | 36 | 1 |
| Rzeszów | 2 | PL015F | PL015C | 1 944 | 126,6 | 126,6 | 23 | 1 |
| Szczecin | 2 | PL007F | PL007C | 1 362 | 300,8 | 300,6 | 8 | 1 |

Pola FUA i rdzenia liczone z geometrii URAU w EPSG:2180. „Pow. adm. gmin rdzenia” to suma pól `AREA_KM2` z LAU 2021
gmin zawartych (≥ 50 % powierzchni) w rdzeniu: dla porównania z polem granicy URAU (Warszawa ~517 km², Kraków ~327,
Wrocław ~293 to powierzchnie administracyjne, nie miara miasta; brief §2). Liczba gmin: jednostki LAU, których ≥ 50 %
powierzchni leży w danym obszarze. Rdzeń Trójmiasta = Gdańsk + Gdynia (miasta URAU) + Sopot (jednostka LAU; Sopot nie jest
miastem URAU). Rdzeń GZM = 13 miast URAU leżących w GZM. Rdzeń Bydgoszczy–Torunia = oba miasta.

## Ludność: NSP 2021 (siatka 1 km) kontra GHS-POP R2023A, epoka 2020

| Aglomeracja | NSP 2021 FUA | GHSL 2020 FUA | GHSL/NSP FUA | |różn.|>5% | NSP 2021 rdzeń | GHSL 2020 rdzeń | GHSL/NSP rdzeń | |różn.|>5% |
|---|---|---|---|---|---|---|---|---|
| GZM | 2 057 054 | 2 150 295 | 1,045 | nie | 1 643 705 | 1 738 107 | 1,057 | TAK |
| Kraków | 1 411 779 | 1 350 286 | 0,9564 | nie | 793 392 | 760 841 | 0,959 | nie |
| Łódź | 1 044 086 | 1 045 886 | 1,002 | nie | 665 696 | 670 405 | 1,007 | nie |
| Poznań | 974 744 | 926 610 | 0,9506 | nie | 547 682 | 527 922 | 0,9639 | nie |
| Trójmiasto | 1 089 730 | 1 064 838 | 0,9772 | nie | 752 435 | 736 930 | 0,9794 | nie |
| Warszawa | 3 485 881 | 3 334 987 | 0,9567 | nie | 1 865 105 | 1 785 716 | 0,9574 | nie |
| Wrocław | 1 011 966 | 939 076 | 0,928 | TAK | 673 906 | 634 111 | 0,9409 | TAK |
| Białystok | 448 491 | 462 842 | 1,032 | nie | 281 830 | 298 928 | 1,061 | TAK |
| Bydgoszcz–Toruń | 855 995 | 892 951 | 1,043 | nie | 510 653 | 545 377 | 1,068 | TAK |
| Kielce | 386 456 | 405 621 | 1,05 | nie | 179 303 | 193 979 | 1,082 | TAK |
| Lublin | 664 078 | 680 102 | 1,024 | nie | 322 635 | 332 983 | 1,032 | nie |
| Rzeszów | 459 020 | 458 745 | 0,9994 | nie | 185 929 | 211 037 | 1,135 | TAK |
| Szczecin | 512 051 | 524 618 | 1,025 | nie | 384 375 | 398 002 | 1,035 | nie |

Zasady przypisania:

- **NSP 2021:** komórka siatki 1 km (zmienna `RES`, ludność rezydująca ogółem; stan na 31,03,2021) należy do obszaru,
  jeśli jej **centroid** leży wewnątrz wielokąta (centroid-in-polygon, EPSG:2180).
- **GHSL:** wielokąt zagęszczony (250 m), przeliczony do Mollweide (ESRI:54009); z VRT czytane jest okno, a sumowane są
  komórki 100 m, których środek leży w wielokącie (`rasterio.features.geometry_mask`, `all_touched=False`); nodata pomijane.
- Stosunek GHSL/NSP odbiega od 1 także dlatego, że oba zbiory mają inną datę (2020 vs 31,03,2021), a siatka NSP sumuje się
  do ok. 37,0 mln (poniżej BDL), więc to pierwsze spojrzenie (brief §7,1), nie wynik kontroli. Odchylenie > 5 %
  oznaczono w kolumnach „|różn.|>5%”; wymaga opisu w RAPORT.md (porównanie rozkładu na 1 km, BDL: faza 1).
- Granice URAU (100K) i siatka nie pokrywają się dokładnie, więc na brzegu FUA wpływ centroidów jest rzędu kilku komórek.
