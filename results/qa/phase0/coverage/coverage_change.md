# Zmiana pokrycia GTFS po dodaniu feedów podmiejskich (faza 0)

Stan: 2026-11-23, dzień referencyjny 2026-11-25 (śr). „Przed” = `coverage_summary.csv` z `HEAD` (12 feedów, zob. `results/RAPORT.md` §6); „po” = ten sam moduł (`python -m pipeline.stop_coverage`, bez zmian metody) po dodaniu 30 feedów z `candidate_feeds.md`. Mianownik (przystanki OSM, stan 2026-11-22) jest ten sam, więc zmiany wynikają wyłącznie z nowych danych GTFS. Wskaźnik mierzy obecność przystanku w danych, nie liczbę kursów.

## 1. Pokrycie przystanków OSM (%): przed → po

| Aglomeracja | tryb | FUA | rdzeń | poza rdzeniem | przystanków OSM poza rdzeniem |
|---|---|---|---|---|---:|
| Warszawa | wszystkie | 59 9 → **81 0** | 97 2 → 97 2 | 35 8 → **70 6** | 7 765 |
| Kraków | wszystkie | 59 8 → **80 1** | 96 1 → 97 8 | 36 9 → **69 0** | 3 931 |
| Wrocław | wszystkie | 71 1 → **77 9** | 97 7 → 97 7 | 35 1 → **51 2** | 1 485 |
| Poznań | wszystkie | 86 2 → **86 2** | 94 9 → 94 9 | 78 8 → **78 8** | 2 057 |
| Łódź | wszystkie | 68 2 → **89 1** | 96 3 → 96 3 | 29 9 → **79 3** | 1 588 |
| Trójmiasto | wszystkie | 71 1 → **76 4** | 96 5 → 96 5 | 35 8 → **48 5** | 1 661 |
| GZM | wszystkie | 94 7 → **94 7** | 96 9 → 96 9 | 89 2 → **89 2** | 1 780 |
| Warszawa | autobus | 56 6 → **79 8** | 96 9 → 97 0 | 34 9 → **70 6** | 7 530 |
| Kraków | autobus | 56 3 → **78 8** | 95 8 → 97 9 | 36 5 → **69 3** | 3 845 |
| Wrocław | autobus | 70 5 → **78 5** | 97 2 → 97 2 | 37 0 → **54 9** | 1 193 |
| Poznań | autobus | 87 5 → **87 5** | 95 1 → 95 1 | 82 3 → **82 3** | 1 790 |
| Łódź | autobus | 62 8 → **87 4** | 96 2 → 96 2 | 24 4 → **77 2** | 1 419 |
| Trójmiasto | autobus | 68 1 → **74 1** | 96 8 → 96 8 | 34 8 → **47 7** | 1 630 |
| GZM | autobus | 94 8 → **94 8** | 97 4 → 97 4 | 89 2 → **89 2** | 1 734 |

Rdzenie praktycznie się nie zmieniły (nowe feedy są podmiejskie); GZM i Poznań bez zmian (nie dodano dla nich nic: Poznań: PKS Poznań niepobieralny, Kombus Kórnik już w `poznan`, Środa Wlkp. poza FUA).

## 2. Ludność FUA w gminach o pokryciu ≥ próg (%): przed → po

Jak w `results/RAPORT.md` §6.2 (NSP 2021, siatka 1 km, wariant gminny).

| Aglomeracja | próg 50 % | próg 70 % | próg 85 % |
|---|---|---|---|
| Warszawa | 73,2 → **89,3** | 66,5 → **83,2** | 60,0 → **77,8** |
| Kraków | 71,1 → **90,2** | 67,3 → **79,7** | 65,6 → **73,1** |
| Wrocław | 78,5 → **86,4** | 74,5 → **79,0** | 68,5 → **71,5** |
| Poznań | 92,7 → **92,7** | 92,7 → **92,7** | 86,6 → **86,6** |
| Łódź | 68,3 → **95,4** | 67,4 → **91,5** | 65,7 → **84,2** |
| Trójmiasto | 77,7 → **83,9** | 77,7 → **83,9** | 75,0 → **81,2** |
| GZM | 98,7 → **98,7** | 97,5 → **97,5** | 96,3 → **96,3** |

Reguła briefu §6 (≥ ok. 85 % ludności FUA w obszarze pokrytym przy progu 85 %) jest teraz spełniona w: Poznań, GZM. Wciąż poniżej: Warszawa (77,8 %), Kraków (73,1 %), Wrocław (71,5 %), Łódź (84,2 %), Trójmiasto (81,2 %). Wariant komórkowy: `population_coverage_preliminary.csv`.

## 3. Gminy, które się zmieniły (≥ 10 przystanków OSM, wszystkie tryby)

Największe zyski (pokrycie przed → po, liczba przystanków OSM).

**Warszawa** (40 gmin z przyrostem ≥ 15 pkt proc.): Mińsk Mazowiecki (miasto) 1,6 → 97,6 (126); Grodzisk Mazowiecki 1,5 → 97,4 (340); Żabia Wola 0,0 → 95,2 (210); Brwinów 2,5 → 96,8 (158); Baranów 1,5 → 95,6 (68); Jaktorów 6,9 → 100,0 (29); Błonie 1,2 → 92,5 (241); Kampinos 0,0 → 89,2 (37); Milanówek 5,1 → 89,8 (98); Żyrardów 1,0 → 84,6 (104); Sulejówek 18,6 → 97,9 (97); Pruszków 11,2 → 90,0 (160); Podkowa Leśna 21,4 → 100,0 (14); Halinów 19,1 → 96,8 (126).

**Kraków** (23 gmin z przyrostem ≥ 15 pkt proc.): Igołomia-Wawrzeńczyce 0,0 → 92,1 (38); Nowe Brzesko 0,0 → 91,2 (34); Drwinia 2,9 → 92,9 (70); Koszyce 0,0 → 71,4 (21); Sułoszowa 0,0 → 69,2 (39); Niepołomice 28,4 → 93,0 (285); Trzyciąż 0,0 → 63,6 (55); Gdów 0,0 → 55,3 (150); Dobczyce 0,0 → 55,3 (94); Myślenice 0,0 → 54,4 (191); Alwernia 0,0 → 54,1 (61); Sułkowice 0,0 → 53,2 (62); Siepraw 0,0 → 49,2 (65); Kłaj 3,4 → 50,0 (58).

**Wrocław** (7 gmin z przyrostem ≥ 15 pkt proc.): Dobroszyce 4,5 → 90,9 (22); Oborniki Śląskie 4,3 → 87,1 (70); Oleśnica (gmina wiejska) 1,7 → 75,9 (58); Sobótka 7,0 → 69,8 (43); Oleśnica (miasto) 2,5 → 42,0 (81); Zawonia 0,0 → 36,4 (22); Kobierzyce 31,8 → 55,0 (129).

**Łódź** (21 gmin z przyrostem ≥ 15 pkt proc.): Pabianice (gmina wiejska) 0,0 → 100,0 (65); Brójce 0,0 → 91,5 (47); Koluszki 6,9 → 88,9 (72); Tuszyn 0,0 → 81,8 (44); Dłutów 0,0 → 81,5 (27); Pabianice (miasto) 16,3 → 96,4 (221); Zgierz (gmina wiejska) 13,0 → 69,6 (46); Rzgów 40,0 → 96,5 (85); Zgierz (miasto) 40,0 → 90,7 (205); Ozorków (gmina wiejska) 7,1 → 57,1 (14); Ksawerów 18,8 → 64,6 (48); Dalików 0,0 → 43,9 (41); Stryków 38,3 → 81,5 (81); Rogów 17,6 → 58,8 (17).

**Trójmiasto** (2 gmin z przyrostem ≥ 15 pkt proc.): Wejherowo (miasto) 15,8 → 93,8 (177); Reda 20,2 → 97,9 (94).

## 4. Co nadal brakuje

Gminy z ≥ 10 przystankami OSM i pokryciem poniżej 40 % po dodaniu feedów (pokrycie, liczba przystanków OSM):

- **Warszawa** (33 gmin, razem 1292 przystanków OSM): Tarczyn 3,4 (174); Kotuń 2,5 (119); Serock 0,0 (100); Pułtusk 0,0 (66); Dobre 18,5 (65); Siennica 35,9 (64); Karczew 11,3 (62); Mrozy 16,1 (62); Celestynów 7,3 (55); Pilawa 5,6 (36); Łochów 11,8 (34); Kołbiel 6,2 (32); Jadów 6,7 (30); Chynów 13,3 (30); Sobienie-Jeziory 0,0 (29); Małkinia Górna 7,1 (28) …
- **Kraków** (7 gmin, razem 618 przystanków OSM): Miechów 1,5 (203); Krzeszowice 37,7 (146); Brzeźnica 6,5 (93); Słomniki 36,2 (58); Łapanów 10,6 (47); Koniusza 37,0 (46); Gołcza 20,0 (25)
- **Wrocław** (8 gmin, razem 475 przystanków OSM): Siechnice 15,8 (165); Trzebnica 2,2 (92); Żórawina 28,8 (73); Żmigród 5,7 (53); Prusice 3,1 (32); Borów 4,5 (22); Zawonia 36,4 (22); Mietków 6,2 (16)
- **Poznań** (5 gmin, razem 306 przystanków OSM): Pobiedziska 9,6 (115); Kostrzyn 16,2 (68); Stęszew 6,6 (61); Łubowo 7,1 (42); Nekla 10,0 (20)
- **Łódź** (2 gmin, razem 130 przystanków OSM): Łask 19,6 (107); Dobroń 26,1 (23)
- **Trójmiasto** (10 gmin, razem 1042 przystanków OSM): Żukowo 32,3 (297); Szemud 39,8 (171); Pruszcz Gdański (gmina wiejska) 30,1 (153); Trąbki Wielkie 0,0 (104); Kolbudy 24,1 (83); Przywidz 0,0 (69); Stegna 0,0 (56); Cedry Wielkie 0,0 (52); Pszczółki 7,0 (43); Suchy Dąb 0,0 (14)
- **GZM** (2 gmin, razem 141 przystanków OSM): Rudziniec 21,8 (101); Miedźna 25,0 (40)

Przewoźnicy i obszary, dla których **nie znaleziono feedu** (szczegóły w `candidate_feeds.md`): Warszawa: PKS Grójec (Tarczyn), Nadwiślańska Komunikacja Autobusowa (Karczew, Celestynów i okolice), Serock, Pułtusk, Legionowo (gmina ma 72 % bez osobnego feedu); Kraków: Miechów, Krzeszowice (38 %), Słomniki, Wieliczka (jedyny znaleziony feed pochodzi z 2019 r.); Łódź: Łask (20 %); Trójmiasto: PKS Gdynia, Pruszcz Gdański (gmina wiejska), Żukowo (Albatros), Szemud, Kolbudy, Trąbki Wielkie, Przywidz, Cedry Wielkie; Wrocław: Siechnice, Czernica, Kobierzyce (linie aglomeracyjne organizowane przez Wrocław; osobnego feedu nie znaleziono, nie sprawdzono, czy są w feedzie `wroclaw`), Trzebnica, Żmigród, Żórawina; Poznań: PKS Poznań (feed istnieje, ale serwer nie wydaje pliku po HTTPS), Pobiedziska, Kostrzyn, Stęszew, Łubowo. Gminy Błonie, Brwinów, Myślenice, Dobczyce, Koluszki, Tuszyn i Brójce zyskały pokrycie z feedów GPA (Grodziskie Przewozy Autobusowe), ALD i `lodz_suburban_qbx`/`lodz_lka_bus`, mimo że nie były to cele szukania.

## 5. Zastrzeżenia

- Większość nowych feedów to nieoficjalne eksporty (`files.girlc.at`, `api.zbiorkom.live`) o oknach ważności ok. 2–4 tygodni; licencje podane w katalogach dotyczą przepakowania, a nie warunków organizatora. Pełna lista i uwagi: `candidate_feeds.md` i `config.yaml`.
- Feedy `warsaw_czosnow`, `warsaw_zakroczym`, `wroclaw_oborniki` są ręcznie przygotowane (stały wzorzec tygodniowy), `lodz_suburban_qbx` to zbiór społecznościowy bez licencji i daty aktualizacji.
- Zysk w Krakowie pochodzi głównie z linii dowozowych Kolei Małopolskich (`krakow_ald`, 70 tras w całej Małopolsce): to oficjalny feed, ale jako linie dowozowe do kolei nie musi dawać gęstej oferty (nie sprawdzano; miary z fazy 2 pokażą częstotliwość). Nie rozbito zysku na pojedyncze feedy, więc przypisanie przyrostu konkretnym feedom (np. Łódź: `lodz_lka_bus` czy `lodz_suburban_qbx`) jest niezweryfikowane.
- Pokrycie wzrosło mechanicznie także tam, gdzie feed ma jeden kurs dziennie; do analiz dostępności potrzebna będzie maska z progiem minimalnej obsługi (faza 2).
