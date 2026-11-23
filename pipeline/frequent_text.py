"""Polish narrative for results/qa/transit/frequent.md (used by pipeline.frequent_md).

Paragraphs that quote numbers were written after inspecting the run of 2026-11-23; the tables next to them are
regenerated on every run, so if inputs change, re-read the tables and update the text here.
"""
from __future__ import annotations

NARRATIVE: dict[str, str] = {}

NARRATIVE["popgrid"] = """\
**Po co.** Kontrola z fazy 1 (RAPORT §14.4) pokazała, że GHSL 2020 zaniża wielkie osiedla (do 35–60 % wartości
spisowej) i zawyża centra oraz tereny przemysłowe, czyli dokładnie miejsca, które różnią się obsługą komunikacją.
Dlatego wynik zalecany liczony jest na GHSL przeskalowanym do spisu.

**Metoda.** Komórki spisowe NSP 2021 (pole `RES`, ludność rezydująca, 31.03.2021) to siatka 1 km w EU LAEA
(EPSG:3035); siatka 250 m jest w EPSG:2180, więc kwadraty się nie pokrywają. Skalowanie jest robione na pikselach
źródłowych GHSL 100 m (Mollweide), a dopiero wynik jest sumowany do 250 m tym samym jądrem co w fazie 1
(GDAL `Resampling.sum`, dokładny transformator):

1. każdy piksel 100 m o środku w Polsce dzielony na 4 × 4 podpiksele; środek podpiksela rzutowany do EPSG:3035
   i przypisany komórce spisowej, w której leży (piksel na krawędzi dwóch komórek dzieli się między nie
   proporcjonalnie do pola, z rozdzielczością 1/16);
2. G_j = ludność GHSL przypisana komórce j, C_j = NSP; współczynnik C_j / G_j dla każdego podpiksela w j;
3. C_j = 0: ludność GHSL w tej komórce jest usuwana (łącznie {removed} tys. osób w {cells0} komórkach: huty,
   porty, lotniska, centra logistyczne, ale też komórki z zabudową nowszą niż spis);
4. C_j > 0 i G_j = 0: rezerwowo według powierzchni zabudowy GHS-BUILT-S 2020 ({fb_b} komórki, {fb_bp} osoby),
   a bez zabudowy równomiernie po 400 punktach komórki ({fb_u} komórek, {fb_up} osób): zaniedbywalne;
5. piksele poza Polską bez zmian (nie ma tam spisu).

**Kontrole.** (1) Suma przeskalowanych podpikseli w każdej komórce spisowej = C_j (maks. błąd {c1} osoby).
(2) Po zsumowaniu do 250 m i rozbiciu każdej komórki 250 m na 5 × 5 części przypisanych do komórek spisowych
{mis} % ludności „przesuwa się” przez krawędzie komórek spisowych (komórki 250 m przecinające krawędź mieszają dwa
współczynniki); dla porównania surowy GHSL różni się od spisu rozkładem o {misraw} % (indeks niepodobieństwa).
Średni błąd względny w komórkach spisowych ≥ 500 osób {mre} %, 95. percentyl {p95} %: to resztkowy błąd metody na
1 km. (3) Sumy per FUA zgodne ze spisem (tabela niżej; różnice to przypisanie komórek brzegowych, Trójmiasto
+0,65 % przez komórki przybrzeżne). (4) Okna 20 × 20 km: brak prążków; we współczynniku widać kwadraty 1 km
(rys. niżej, prawa kolumna), co jest cechą metody, a nie błędem. Współczynniki C_j / G_j w zamieszkanych
komórkach: 5. percentyl {q05}, mediana {q50}, 95. percentyl {q95}.

**Granice metody.** Poprawia poziom na 1 km, nie wzór wewnątrz komórki: jeśli GHSL w komórce osiedla umieścił
ludzi na dachach pobliskiej hali, przeskalowanie to powtórzy. Data: poziom NSP 31.03.2021, wzór GHSL 2020. Nie
koryguje migracji po 2021 r. ani nowych osiedli podmiejskich (następnym krokiem byłaby warstwa 6c, BDOT10k).
"""

NARRATIVE["walk"] = """\
**Reguła znaczników** (jeden przebieg pyosmium po `poland-latest.osm.pbf` z 2026-11-22, drogi z lokalizacjami
węzłów). Pieszo dostępne są `highway` = footway, path, pedestrian, steps, living_street, residential, service,
unclassified, tertiary(_link), secondary(_link), primary(_link), track, road, corridor, platform; trunk(_link)
tylko z chodnikiem (`sidewalk*` = yes/both/left/right) albo jawnym `foot`; cycleway, bridleway i motorway tylko
z jawnym `foot=yes/designated/permissive` (w Polsce zwykła droga dla rowerów jest zamknięta dla pieszych);
perony (`railway=platform`, `public_transport=platform`) jako ciągi piesze. Wyłączone: `foot=no/private/use_sidepath`,
`access=no/private` bez jawnego `foot`, wartości cyklu życia (construction, proposed…). Tunele i przejścia na
stacjach wchodzą tak, jak są zmapowane (footway / corridor / steps). Relacje (obszary piesze jako multipoligony)
nie są czytane: obszar pieszy zmapowany jako zamknięta droga jest przechodni po obwodzie, nie na przełaj.

**Graf.** Na aglomerację: drogi z co najmniej jednym węzłem w FUA + 3 km; krawędź = para kolejnych węzłów,
długość w EPSG:2180, bez kierunku. Do dociągania używane są tylko składowe spójne o długości ≥ 2 km (mniejsze to
zwykle luki w mapowaniu, które uwięziłyby punkt). Przystanki dociągane do najbliższej krawędzi do 150 m (stacje
kolei i metra do 300 m), punkty komórek do 300 m; krawędź jest dzielona w miejscu dociągnięcia, więc przystanek
i punkt na tej samej długiej krawędzi mają poprawną odległość wzdłuż niej. Odległość = dociągnięcie punktu +
sieć + dociągnięcie przystanku. Liczenie: Dijkstra z wielu źródeł naraz (`scipy.sparse.csgraph.dijkstra`,
`min_only`, odcięcie 500 m lub 1 km), osobno dla każdego zbioru „zespołów spełniających próg”. Kontrola na Łodzi
(2 250 par przystanków 200–1 500 m): stosunek odległości po sieci do prostej: mediana 1,23, 5.–95. percentyl
1,04–1,50, żaden poniżej 1.
"""

NARRATIVE["cellrep"] = """\
**Reprezentacja komórki 250 m.** Każda zamieszkana komórka FUA ma 3 × 3 punkty próbkowe (środki podkwadratów
83 m); ludność komórki liczy się w części równej udziałowi punktów w zasięgu (zakładamy równomierny rozkład w
komórce). Wariant „tylko środek komórki” jest w `metrics_frequent.csv` jako `…_centroid` i w kolumnie „komórka =
środek” tabel z rozdziału 2: zmienia wynik aglomeracji o mniej niż 1,5 pkt proc., bo błędy w obie strony się
znoszą; dla pojedynczych komórek na skraju zasięgu różnica jest pełna (0 albo 100 %), więc w wariancie zalecanym
zostaje 9 punktów. Punkty, których nie da się dociągnąć (> 300 m od sieci), liczą się jako poza zasięgiem; to
≤ 0,1 % ludności. „Nieprzyciągnięte przystanki w FUA” to pojedyncze słupki na nabrzeżach i w terenie bez dróg.
"""

NARRATIVE["defs"] = """\
1. **Kursy:** wyłącznie z warstwy usług `pipeline.gtfs_service` (`stop_times`, `active_trips`, `stops`) dla
   środy 2026-11-25, po jej deduplikacji (SKM Warszawa raz, duplikaty GZM usunięte, kolej przycięta do FUA +
   15 km). Moduł nie powiela tych reguł. Wersja reguł warstwy usług: `RULES_VERSION = 2026-11-24.4` (z regułą
   duplikatów blokowych GZM, 242 kursy, i z brakującymi współrzędnymi zamiast zerowych).
   **Słupki bez współrzędnych** są pomijane we wszystkich krokach przestrzennych (zespoły, kierunek, dociąganie,
   KD-drzewa): kurs „przejeżdża” przez nie, jakby ich nie było. Dotyczy to dwóch prawdziwych, obsługiwanych
   słupków w Łodzi, `lodz:3876` i `lodz:3877` na pl. Niepodległości (w źródle `stop_lat = stop_lon = 0`):
   387 zdarzeń, w tym 240 odjazdów 06–20. To lokalne zaniżenie: główny zespół pl. Niepodległości (5 słupków,
   642 odjazdy, (ii) 3,8 min) zostaje, więc klasa okolicznych komórek się nie zmienia, ale częstotliwość tego
   węzła jest o te odjazdy niższa. Zestawienie w tabeli dociągania (kolumna „słupki bez współrzędnych”).
2. **Zespół przystanków:** obsługiwane słupki (z kursami w którymkolwiek wariancie feedów) grupowane najpierw po
   `parent_station`, potem łączone **wiązaniem zupełnym** w promieniu 100 m (`stop_cluster_radius_m`): żadne
   dwie grupy w zespole nie są dalej niż 100 m od siebie, więc nie powstają łańcuchy wzdłuż ulicy. Słupki różnych
   feedów (np. stacja z `polish_trains` i przystanek miejski) łączą się tą samą regułą. Zespoły liczone raz, na
   zbiorze „all”, i używane w obu wariantach feedów.
3. **Wizyta i odjazd:** kolejne przystanki kursu w tym samym zespole to jedna wizyta; odjazd = wizyta, która nie
   jest ostatnią w kursie, z odjazdem w oknie 06:00–20:00 (koniec otwarty). Ostatnie wizyty to przyjazdy.
4. **Kierunek z geometrii, nie z `direction_id`** (w części feedów pole jest puste, a między feedami nie znaczy
   tego samego): azymut od poprzedniej do następnej wizyty kursu (dla pierwszego przystanku kursu: od tego
   przystanku do następnego). Oś zespołu = średni azymut jego najczęstszego odcinka (zespół → następny zespół).
   Odjazdy w granicach 90° od osi to kierunek A, pozostałe B.
5. **Średni odstęp** = 840 min / liczba odjazdów w oknie (średnia z dnia, jak DG REGIO; bez wymogu równomierności).
6. **Agregacje** (każda wymaga obu kierunków; odstęp zespołu = gorszy z dwóch kierunków):
   - **(i) „wszystkie linie”**: wszystkie odjazdy w kierunku zsumowane. Kilka rzadkich linii rozchodzących się
     zaraz za przystankiem liczy się jak jeden częsty korytarz.
   - **(ii) „odcinek” (zalecana)**: w każdym kierunku najczęstszy odcinek do następnego zespołu; linie jadące
     wspólnym pniem do następnego przystanku liczą się razem, linie rozchodzące się zaraz za przystankiem osobno.
     Wybrana, bo odpowiada odstępowi, jaki widzi pasażer jadący w konkretną stronę, i nie daje się zawyżyć
     rozchodzącym się liniom, a jednocześnie nie karze pni obsługiwanych przez kilka linii (co robi wariant
     „jedna linia”). Wada: linie przyspieszone omijające następny przystanek liczą się jako osobny odcinek.
   - „jedna linia”: najczęstsza pojedyncza linia (tryb + `route_short_name`) w kierunku, tylko do porównania;
     w polskich miastach częstotliwość robią nakładające się linie, więc ten wariant prawie zeruje progi 5–10 min.
   - „bez kierunków”: wszystkie odjazdy razem, bez wymogu dwóch kierunków; izoluje wpływ samej reguły kierunków.
7. **Zespoły jednokierunkowe.** Gdy zespół ma odjazdy tylko w jednym kierunku:
   - **pętla / początek kursów** (≥ 50 % odjazdów zaczyna tu kurs albo przyjazdy kończące kurs ≥ 50 % odjazdów):
     odstęp = odstęp jedynego kierunku;
   - **partner**: zespół ≤ 300 m dalej, który obsługuje co najmniej jedną z tych samych linii w kierunku
     przeciwnym do osi (przystanki przeciwnych kierunków dalej niż 100 m od siebie, ulice jednokierunkowe);
     odstęp = max(odstęp tutaj, odstęp przeciwnego kierunku u najlepszego partnera);
   - w przeciwnym razie zespół nie spełnia warunku „oba kierunki” (status one_way).
8. **Miara:** punkt próbkowy jest w zasięgu progu T, jeśli ≤ 500 m pieszo po sieci leży słupek należący do
   zespołu z odstępem ≤ T, który ma odjazdy w oknie. Wynik = ludność w zasięgu / ludność domeny. Domeny: FUA,
   rdzeń, „obszar pokryty” (komórki FUA w masce pokrycia danego wariantu feedów).
"""

NARRATIVE["mask"] = """\
**Definicja (komórka 250 m, nie gmina).** Dla każdej komórki brane są przystanki OSM w promieniu 1 km od jej
środka, pogrupowane w **miejsca** (słupki ≤ 100 m od siebie, wiązanie zupełne; dworzec autobusowy z 9
stanowiskami to jedno miejsce, nie dziewięć). Miejsce ma „dane” w udziale swoich słupków, które mają odpowiednik
GTFS w danym wariancie feedów (dopasowanie z fazy 0, `pipeline.stop_coverage`: 50 m / kolej 200 m + nazwa lub kod
do 200 / 500 m, z regułą „zastępczy”) albo są w feedzie, ale bez kursów w dniu referencyjnym (dane są, kursów
nie ma). Komórka jest w masce, jeśli średni udział miejsc z danymi ≥ 0,85, albo jeśli w promieniu 1 km nie ma
żadnego przystanku OSM (wtedy „brak komunikacji” jest informacją, nie brakiem danych; udział takiej ludności w
tabeli). Poza maską komórka ma wartość null („brak danych”), nigdy 0. Wynik dla całej FUA wlicza to, co wiadomo,
jest więc dolną granicą i ma flagę „niepełne pokrycie GTFS” przy pokryciu < 85 %.

**Dlaczego komórka, a nie gmina.** Brief §6 wymaga maski z przystanków („gmina z jedną linią ZTM nie może wyjść
jako pokryta”). Wariant gminny jest zgrubny w obie strony: gmina wiejska z dobrze pokrytym miastem gminnym wypada
w całości, a gmina z jedną dobrze pokrytą częścią wchodzi w całości. Promień 1 km jest szerszy niż zasięg miary
(500 m), żeby udział liczył się z kilku–kilkunastu miejsc, a nie z jednego. Próg 0,85 to ta sama liczba co próg
ludnościowy briefu; tabela pokazuje wrażliwość (0,5 / 0,7 / 0,85 / 0,95) i wariant gminny (ten sam udział liczony
na gminę). Maska jest liczona osobno dla wariantu feedów „official” i „all”.

**Pierwsza wersja maski** liczyła pojedyncze słupki i traktowała „w feedzie, bez kursów” jako brak danych.
Kontrola znanych miejsc wyrzuciła wtedy z maski komórkę Gdańska Głównego: 9 stanowisk dworca autobusowego (w
feedzie, bez kursów) i przystanki autokarowe przy Podwalu Grodzkim dawały 83 % zamiast ≥ 85 %. Po zmianie na
miejsca i uznaniu „w feedzie, bez kursów” za dane udział ludności rdzeni w masce wynosi 95,5–99 % (Poznań wzrósł
z 89 do 95,5 %), a udziały FUA zmieniły się o mniej niż 1 pkt proc.

Warstwa do mapy: `results/layers/gtfs_coverage_mask.parquet` (wszystkie komórki 250 m o środku w FUA, także
niezamieszkane, rozpuszczone w wielokąty per aglomeracja × wariant feedów × status).
"""

NARRATIVE["itdp_def"] = """\
**To nie jest wskaźnik ITDP**, tylko odtworzenie tego, co robi kod ITDP (`ITDP/pedestriansfirst`, commit
`b124b7f`, opis w RAPORT §9.1), na naszych danych, żeby było widać różnicę między „naszą definicją” a
„implementacją ITDP”. Zgodnie z kodem: dla każdego `stop_id` każdego feedu osobno (bez łączenia słupków w zespoły
i bez łączenia feedów) wszystkie wiersze `stop_times` z odjazdem 07:00–21:00 (oba końce włącznie, także
przyjazdy kończące kurs), wszystkie linie i oba kierunki w jednej sekwencji; odstęp = średnia z różnic między
kolejnymi odjazdami, czyli (ostatni − pierwszy) / (n − 1), a nie 840 / n; przystanek częsty, gdy
0 < odstęp ≤ 10 min; 500 m po sieci. Czego nie odtwarzamy: średniej z pon–pt pierwszego tygodnia feedu (mamy
jeden dzień); duplikatów (nasze kursy są po deduplikacji, ITDP liczyłby ok. 23 % zdublowanych kursów GZM dwa
razy); bufora +100 m wokół sieci i wypełniania dziur; ludności GHS-POP 1 km i granic GHS-UCDB. Skutek średniej z
przerw: przystanek z dwoma odjazdami w odstępie 5 min (i żadnymi innymi) przechodzi próg; takich przystanków jest
mało, ale to cecha kodu, nie naszej definicji.
"""

NARRATIVE["rail_def"] = """\
**Wariant kolejowy** (wzorowany na klasach DG REGIO, nie ich replika): zespoły z kursami kolei lub metra
(`route_class` rail / metro; WKD jest w klasie rail; autobusowa komunikacja zastępcza `is_replacement_bus`
wyłączona), odjazdy 06:00–20:00 ze wszystkich kierunków razem, podzielone przez 14 h = odjazdy na godzinę. Klasa
komórki = najlepsza stacja w zasięgu 1 km pieszo (`rail_station_radius_m`): > 10, 4–10, < 4 odjazdów/h, brak
stacji. Wynik główny wariantu: ludność ≤ 1 km od stacji z ≥ 4 odjazdami/h. Tramwaj tu nie wchodzi.

**„Tylko szynowe”** (tramwaj + metro + kolej, bez autobusów i ZKA): ta sama definicja co krzywa główna (500 m,
oba kierunki, agregacja (ii) i (i)), ograniczona do kursów szynowych. **To nie jest ITDP PNRT** (PNRT to 1 km
od metra, LRT lub BRT z oceną, z danych Transit Explorer); w tabelach pod własną nazwą (`freq_railbound_*`).
"""

NARRATIVE["summary"] = """\
- **Konfiguracja zalecana:** dojście 500 m po sieci pieszej OSM, zespoły przystanków 100 m, średni odstęp
  06:00–20:00 w środę 2026-11-25, **oba kierunki, agregacja (ii) „najczęstszy odcinek do następnego przystanku”**,
  **wszystkie feedy** (z nieoficjalnymi; maska liczona dla tego zbioru), **siatka GHSL przeskalowana do NSP 2021**,
  domena do porównań: **obszar pokryty danymi** (i rdzeń). Tylko te wiersze mają w `metrics_frequent.csv`
  `tier = main` (70 wierszy: 7 aglomeracji × 2 domeny × 5 progów).
- **Dlaczego „wszystkie feedy”:** w tym samym obszarze feedy nieoficjalne zmieniają wynik o 0–5 pkt proc.
  (najwięcej przy progu 30 min w Warszawie i Łodzi, bo dokładają rzadkie linie podmiejskie), a powiększają obszar
  pokryty: Warszawa 69 → 82,5 %, Łódź 71 → 89 % ludności FUA. Wariant oficjalny jest w tabeli obok, żeby było
  widać, ile zależy od danych nieweryfikowanych.
- **Wynik:** w rdzeniach przy progu ≤ 10 min od 46 % (GZM) do 80 % (Warszawa) mieszkańców; w obszarze pokrytym
  od 40 % (GZM) do 63 % (Wrocław). Przy ≤ 5 min różnice są największe (Warszawa 38,5 %, GZM 8,5 % obszaru
  pokrytego). GZM i Trójmiasto to układy wielobiegunowe; miara od centrum nie zależy, ale granice FUA są umowne.
- **Pokrycie:** wynik dla całej FUA jest niepełny (< 85 % ludności w masce) w Warszawie, Krakowie, Wrocławiu i
  Trójmieście; Poznań (85,5 %), Łódź (89 %) i GZM (95 %) mieszczą się w progu. Rdzenie 95,5–99 %.
- **Co najbardziej zmienia wynik** (pkt proc., ≤ 10 min, obszar pokryty): wymóg dwóch kierunków (+8 do +26 bez
  niego), sposób liczenia drugiego kierunku przy przystankach rozsuniętych > 100 m (−5 do −12 bez reguły
  partnera), odległość w linii prostej zamiast sieci (+9 do +14), agregacja (i) zamiast (ii) (+2 do +11, najwięcej
  w GZM), siatka surowa zamiast przeskalowanej (−1 do −7; zawsze w dół), feedy oficjalne w tym samym obszarze
  (0 do −3). Reprezentacja komórki (środek vs 9 punktów) < 1,5 pkt proc.
- **Kolej:** ≤ 1 km od stacji z ≥ 4 odjazdami/h mieszka 31 % (Warszawa, z metrem) i 27 % (Trójmiasto, SKM)
  ludności obszaru pokrytego, ale tylko 4,7–10,6 % w pozostałych pięciu aglomeracjach.
"""

NARRATIVE["effects"] = """\
Każda tabela pokazuje różnicę jednego wariantu względem konfiguracji zalecanej, przy pozostałych parametrach bez
zmian. Główne wnioski:

- **Siatka ludności — po raz pierwszy wybór siatki ma znaczenie.** Na surowym GHSL wynik jest niższy w każdym
  mieście i przy każdym progu w rdzeniach (do −9,4 pkt proc. w rdzeniu Łodzi przy ≤ 10 min; Poznań −7,8, Trójmiasto
  −8,2, Kraków i GZM −6,1, Wrocław −3,4, Warszawa −2,0). Mechanizm jest ten, który pokazała kontrola z fazy 1:
  GHSL zaniża wielkie osiedla (dobrze obsłużone tramwajem i autobusem) i dokłada ludzi w terenach przemysłowych,
  kolejowych i portowych (słabo obsłużonych). Spis przenosi ludzi tam, gdzie są przystanki. Łódź ma największy
  efekt, choć jej suma GHSL prawie równa się spisowi: liczy się rozkład, nie suma.
- **Feedy nieoficjalne:** w tej samej domenie (maska „all”) 0 do −5 pkt proc., głównie przy progach 20–30 min
  (rzadkie linie podmiejskie). Kolumna „własna maska” porównuje wyniki na różnych obszarach: obszar pokryty
  feedami oficjalnymi jest mniejszy i bardziej miejski, więc odsetek wychodzi wyższy (Warszawa +8,3, Łódź +9,8);
  tej kolumny nie należy czytać jako „feedy oficjalne dają lepszy wynik”.
- **Agregacja:** (i) „wszystkie linie” daje +2 do +11 pkt proc. przy ≤ 10 min, najwięcej w GZM (+10,8) i
  Trójmieście (+7,8), gdzie wiele linii rozchodzi się na węzłach; przy ≤ 30 min różnica spada do 0,5–2,7.
  „Jedna linia” zeruje próg ≤ 10 min we Wrocławiu i Poznaniu (pojedyncze linie jeżdżą tam co 10–15 min; częsty
  korytarz tworzą nakładające się linie), więc nie nadaje się na definicję.
- **Kierunki:** bez wymogu dwóch kierunków wynik rośnie o 8–26 pkt proc. (≤ 10 min). To nie tylko przystanki
  jednokierunkowe: liczenie odjazdów z obu kierunków razem podwaja częstotliwość (dwa kierunki po 20 min dają
  „10 min”). Reguła partnera (drugi kierunek u przystanku ≤ 300 m dalej z tą samą linią) dotyczy 22–42 % zespołów z
  odjazdami (Warszawa 2 794 z 6 583, Kraków 22 %); bez niej wynik spada o 5–17 pkt proc. Partnerzy leżą w medianie 134–141 m od siebie,
  a w Warszawie 83 % par ma tę samą nazwę zespołu przystankowego (ZTM numeruje słupki 01/02 po obu stronach
  skrzyżowania), więc to są te same przystanki rozsunięte na skrzyżowaniu, a nie przypadkowe pary.
- **Odległość:** bufor w linii prostej zawyża o 4–17 pkt proc.; stosunek odległości po sieci do prostej to
  mediana 1,23 (kontrola na Łodzi), czyli 500 m po sieci to ok. 400 m w prostej.
- **Reprezentacja komórki:** środek komórki zamiast 9 punktów zmienia wynik aglomeracji o −0,2 do +1,3 pkt proc.
"""

NARRATIVE["itdp_res"] = """\
Replika kodu ITDP (okno 07–21, średnia przerw, bez podziału na kierunki, per `stop_id`) wychodzi **wyżej** od
naszej definicji o 4–13 pkt proc. (rdzenie: Warszawa 84,5 vs 80,4; GZM 58,3 vs 45,6), a poniżej wariantu „bez
kierunków” na zespołach. Dwa efekty działają przeciwnie: brak wymogu kierunków podnosi wynik ITDP (polskie feedy
mają zwykle osobny `stop_id` na kierunek, więc efekt jest mniejszy niż przy wspólnych słupkach, ale na pętlach i
słupkach wspólnych dla obu kierunków działa), a brak łączenia słupków i feedów go obniża (linie zatrzymujące się na
sąsiednich słupkach jednego węzła nie sumują się). W linii prostej replika ITDP daje 75–95 % w rdzeniach. Wartości
Atlasu ITDP dla polskich miast nadal nie są znane (RAPORT §9.1), więc porównanie z Atlasem jest otwarte; nie
podawać żadnej z tych liczb jako „PNFT ITDP”.
"""

NARRATIVE["rail_res"] = """\
Klasa = najlepsza stacja kolei lub metra ≤ 1 km pieszo. Kolumny „> 10”, „4–10”, „< 4” i „brak stacji” sumują się
do 100 %. Ostatnia kolumna to wariant „tylko szynowe” (tramwaj + metro + kolej) z definicją krzywej głównej przy
≤ 10 min, pod własną nazwą (to nie ITDP PNRT).

Warszawa (metro: Metro Świętokrzyska 75,6 odjazdu/h, Warszawa Zachodnia 54/h) i Trójmiasto (SKM) są jedynymi
aglomeracjami, gdzie kolej jest szkieletem dla ponad jednej czwartej mieszkańców obszaru pokrytego (31 i 27 % przy
≥ 4/h). W Krakowie, Poznaniu, Wrocławiu i GZM to 4,7–9,1 %, w Łodzi 10,6 % (ŁKA; Łódź Widzew 17/h). We Wrocławiu i Poznaniu
więcej ludzi mieszka przy stacjach z < 4 odjazdami/h niż przy stacjach z ≥ 4/h: sieć stacji jest, ale rzadko
obsłużona. Przy klasach DG REGIO wariant kolejowy nie wycina już kolei aglomeracyjnej (KD, ŁKA, SKA), co robił
próg ≤ 10 min. „Tylko szynowe” jest najwyższe we Wrocławiu (39 % obszaru pokrytego) i najniższe w GZM (9 %), gdzie
większość częstych korytarzy jest autobusowa.
"""

NARRATIVE["sanity"] = """\
Wszystkie znane miejsca w centrach dają klasę ≤ 5 min (100 % punktów próbkowych), w tym Rynek we Wrocławiu i
Rynek Główny w Krakowie, które same są strefami pieszymi (przystanki przy pl. Nowy Targ i Poczcie Głównej w
zasięgu 500 m). Rzadkie przystanki (1–6 odjazdów na dobę, ≥ 1,5 km od zespołu z odstępem ≤ 30 min, wybrane
automatycznie, po dwa najludniejsze na aglomerację) mają klasę „> 30” albo leżą poza maską („brak danych”), nigdy
klasę częstą: arytmetycznie 6 odjazdów w 14 h daje średnio 140 min. Gdańsk Główny w pierwszej wersji maski wypadał
z maski — opis i poprawka w 1.4.
"""

NARRATIVE["top"] = """\
Kontrola z briefu §7.3: na szczycie listy są węzły tramwajowo-autobusowe (Marszałkowska, Politechnika w Krakowie,
pl. Grunwaldzki, Dworzec Główny w Gdańsku, Centrum Przesiadkowe w Gliwicach), 60–160 odjazdów/h w sumie. Udział
odjazdów zdublowanych (ta sama linia, ten sam następny przystanek, ta sama minuta) wynosi 0–0,1 % we wszystkich
aglomeracjach poza GZM (0,75 % wszystkich odjazdów; najwięcej w zespole Katowice Sądowa, 1,7 %). To resztka
duplikatów feedu GZM, których reguła dokładnych duplikatów warstwy usług nie łapie (kursy różniące się np.
`block_id` albo sekwencją przystanków); wpływ na wynik jest pomijalny (< 1 % odjazdów), ale jest zgłoszony
autorowi warstwy usług. Kolej nie dubluje się (SKM Warszawa tylko z `warsaw_ztm`).
"""

NARRATIVE["maps"] = """\
Mapy pokazują klasę komórki wg zasady „≥ 50 % punktów próbkowych w zasięgu” (ta sama zasada co w warstwie
`frequent_cells.parquet`), szarą szrafurą obszar poza maską. Częste korytarze widać jako pasma wzdłuż linii
tramwajowych i kolei (SKM w Trójmieście, WKD i linie KM pod Warszawą); obszary poza maską leżą tam, gdzie RAPORT §6.4
wskazał przewoźników bez GTFS (np. pas na południe i zachód od Warszawy, północ i południowy wschód FUA Krakowa,
południowy zachód Trójmiasta); nazw gmin z map nie odczytywano, więc to zgodność kierunków, nie weryfikacja
gmina po gminie.
"""

NARRATIVE["determinism"] = """\
`pipeline.popgrid`, `pipeline.walk_network` i `pipeline.frequent` uruchomione dwa razy od zera na tej samej
wersji warstwy usług: wszystkie pliki wynikowe (GeoTIFF, Parquet, CSV, JSON, GeoParquet, PNG, `frequent.md`)
identyczne co do bajta poza `_meta*.json` (czas uruchomienia). Wynik nie zależy od losowego ziarna haszowania
Pythona (sprawdzone `PYTHONHASHSEED` = 1 i 2). Jedna wcześniejsza para przebiegów różniła się w warstwie zespołów
i histogramie: między przebiegami przebudowano cache warstwy usług (nowa wersja reguł), więc to nie była
niedeterministyczność kodu. Liczby w CSV/JSON zaokrąglone do 4 cyfr znaczących, wiersze posortowane.
"""

NARRATIVE["surprises"] = """\
1. **Gdańsk Główny poza maską** (pierwsza wersja). Sprawdzenie: w promieniu 1 km 99 słupków OSM, z czego 17 bez
   danych — 9 stanowisk dworca autobusowego (w feedzie, bez kursów w środę) i przystanki autokarowe. To artefakt
   liczenia słupków, nie brak danych miejskich. **Poprawione** (miejsca 100 m, „w feedzie bez kursów” = dane).
2. **Reguła drugiego kierunku zmienia wynik o 5–17 pkt proc.** Sprawdzenie: odległości i nazwy par partnerów
   (mediana ok. 135 m, 83 % tej samej nazwy w Warszawie). **Zostaje** jako część definicji, z wariantem bez niej
   w tabeli.
3. **Pojedyncze linie prawie nigdy nie jeżdżą co ≤ 10 min** (Wrocław, Poznań: 0 % ludności przy „jednej linii”).
   Sprawdzenie: najczęstsza linia w top-10 zespołów ma 10–15 min (Wrocław pl. Grunwaldzki 10,4 min, Poznań
   Szymanowskiego 11,7 min). **Zostaje**; to argument za agregacją (ii), a nie (ii-linia).
4. **Surowy GHSL obniża wynik w każdym mieście**, najmocniej w Łodzi, gdzie suma GHSL równa się spisowi.
   Sprawdzenie: mechanizm zgodny z kontrolą fazy 1 (osiedla zaniżone, przemysł zawyżony); obraz współczynników w
   `popgrid_windows.png` (Nowa Huta: osiedla w górę, kombinat w dół). **Zostaje.**
5. **GZM ma najniższy wynik przy ≤ 5 i ≤ 10 min**, mimo najlepszego pokrycia danymi (95 %). Sprawdzenie:
   top-10 zespołów GZM ma 90–125 odjazdów/h (tyle co w innych miastach), ale najczęstsza pojedyncza linia ma
   10–20 min, a sieć jest rozproszona na wiele ośrodków; agregacja (i) dodaje tu najwięcej (+11), czyli wiele
   rzadkich linii rozchodzi się na węzłach. Resztkowe duplikaty kursów GZM (0,75 % odjazdów) za mało, by to
   wyjaśnić. **Zostaje.**
6. **Kraków ma tylko 6 % ludności obszaru pokrytego przy stacji z ≥ 4 odjazdami/h**, mniej niż Łódź (11 %).
   Sprawdzenie: stacje wewnętrzne są obsłużone gęsto (Kraków Główny 19,5/h, Grzegórzki i Zabłocie po 12,9/h,
   Płaszów 10,6/h), ale jest ich mało i leżą przy centrum lub w terenach poprzemysłowych, a dalsze przystanki SKA
   mają zwykle < 4/h. Wynik opisuje rozmieszczenie stacji względem mieszkańców, nie częstotliwość pociągów.
   **Zostaje.**
"""

NARRATIVE["limits"] = """\
- **Ludność 2020–2021, rozkłady 2026.** Nowe osiedla po 2021 r. (szczególnie podmiejskie) nie są w siatce.
- **Przeskalowanie poprawia tylko poziom na 1 km**; wzór wewnątrz komórki to nadal GHSL (z jego błędami).
- **Jeden dzień** (środa 2026-11-25); remonty w dniu referencyjnym (np. tramwaje w Krakowie i Łodzi zastąpione
  autobusami, RAPORT §6.3) wchodzą do wyniku tak, jak są w rozkładzie.
- **Średnia z okna** nie mówi o równomierności: korytarz z gęstym szczytem i dziurą w południe może przejść próg.
- **Kierunek z geometrii** może źle przypisać odjazdy na pętlach w kształcie litery U i na skrzyżowaniach, gdzie
  linie skręcają o ~90°; reguły pętli i partnera łagodzą, ale nie usuwają tego efektu.
- **Agregacja (ii)** rozdziela linie zwykłe i przyspieszone, jeśli te drugie omijają następny przystanek.
- **Sieć piesza OSM** bez relacji (place piesze na przełaj) i bez kontroli przejść przez tory / arterie poza tym,
  co jest zmapowane; stopnie i windy traktowane jak zwykłe odcinki.
- **Maska** zależy od kompletności OSM jako mianownika (RAPORT §6.5): gdzie OSM nie ma przystanków przewoźnika bez
  GTFS, maska jest zbyt optymistyczna; komórki bez przystanku OSM w 1 km są w masce z założenia.
- **Feedy nieoficjalne** (28 z 30 dodanych) nie były porównane z rozkładami przewoźników.
- **Replika ITDP** to jeden dzień, kursy po deduplikacji i nasza siatka, więc nie jest porównywalna 1:1 z Atlasem.
"""

NARRATIVE["config"] = """\
Proponowane klucze (dziś stałe w `pipeline/frequent.py`, `walk_network.py`; do decyzji właściciela):

```yaml
frequent:
  aggregation: segment            # (ii) najczęstszy odcinek do następnego przystanku; alternatywy: all_lines, line
  recommended_feed_variant: all
  pair_radius_m: 300              # partner dla zespołów jednokierunkowych
  terminal_share: 0.5             # zespół = pętla, gdy >= 50 % odjazdów zaczyna kurs / tyle samo przyjazdów kończy
  cell_sample_points: 9           # 3 x 3 punkty na komórkę 250 m
  stop_max_snap_m: {default: 150, rail: 300}
  point_max_snap_m: 300
  itdp_window: {start: "07:00", end: "21:00"}   # tylko dla repliki ITDP (RAPORT §12.1 pkt 14)
coverage_mask:
  unit: cell250
  radius_m: 1000
  place_merge_m: 100
  min_place_share: 0.85
  no_stop_cells: in_mask
  in_feed_not_served_counts_as_data: true
walk_network:
  buffer_m: 3000
  min_component_m: 2000
```
"""

NARRATIVE["files"] = """\
- Kod: `pipeline/popgrid.py`, `pipeline/walk_network.py`, `pipeline/frequent.py` (+ `frequent_qa.py`,
  `frequent_md.py`, `frequent_text.py`).
- Polecenia (z katalogu repo), czasy na tej maszynie: `python -m pipeline.popgrid` (ok. 3 min),
  `python -m pipeline.walk_network` (ok. 4,5 min, jeden przebieg po PBF), `python -m pipeline.frequent` (ok. 8 min;
  wymaga zbudowanych cache `pipeline.gtfs_service`); `python -m pipeline.frequent --report-only` przelicza tylko
  tabele, QA i ten plik z `data/interim/frequent/results.pkl`.
- Wyniki: `results/metrics/metrics_frequent.csv` / `.json` (kolumny jak `metrics.csv` + `feed_variant`,
  `population_grid`; `_meta_frequent.json` obok, bo `_meta.json` w tym katalogu należy do kroku gęstości),
  `results/charts/frequent_curve.json`, `frequent_rail.json` (+ `_meta_frequent.json`), warstwy w
  `results/layers/` ({sizes}; CRS EPSG:4326, opis w `_meta.json`), QA w `results/qa/transit/frequent/`.
- Pośrednie: `data/interim/popgrid/`, `data/interim/walk/`, `data/interim/frequent/results.pkl`.
"""
