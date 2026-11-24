# Faza 3: dostępność i transport performance (§4.6)

Stan: 98/98 jednostek policzonych. Plik generuje `python -m pipeline.access aggregate` z tego, co jest gotowe; jednostki niepoliczone są wymienione na końcu jako „oczekuje”, a ich wyniki nie trafiają do tabel ani do `metrics_access.csv` (nie są zerami ani brakami danych). Kosztorys i benchmark: [`plan.md`](plan.md).

Daty: ludność NSP 2021 (31.03.2021) w układzie GHSL 2020 (wariant surowy GHSL 2020 obok); rozkłady środa 2026-11-25 i sobota 2026-11-28 (feedy pobrane 2026-11-23); OSM 2026-11-22; miejsca pracy Goliszek 2026 (horyzont 2025).

## 1. Metoda

- **Starty:** każda komórka 250 m z ludnością (którakolwiek siatka) ze środkiem w FUA. **Cele i mianownik (proximity):** wszystkie komórki z ludnością w FUA + 15 km (ten sam zbiór), plus komórki z miejscami pracy bez ludności. Bez próbkowania.
- **Accessibility:** ludność (albo miejsca pracy) w komórkach, do których czas przejazdu ≤ próg. Zapisywane dla progów 5, 10, …, 60 min, więc krzywe nie wymagają ponownego routingu.
- **Proximity:** ludność w komórkach, których środek leży w linii prostej ≤ prędkość × próg od środka startu: 15 km/h dla komunikacji i roweru (7,5 km przy 30 min, 11,25 km przy 45 min), 5 km/h pieszo (2,5 km przy 30 min).
- **Performance komórki = accessibility / proximity × 100.** Wynik główny (brief): średnia stosunków po komórkach ważona ludnością komórki. Obok (`*_ratio_of_means`, tier `table`): stosunek średnich ważonych; różni się nawet o 10–15 pkt, bo komórki podmiejskie mają mały mianownik.
- **Komunikacja + pieszo:** R5 v7.5.1 (r5py 1.1.7), odjazdy co minutę w oknie, mediana (50. percentyl) z odjazdów, maks. 60 min podróży, pieszo 5 km/h, dojście i odejście ≤ 12 min (= 1 km) na odcinek, przesiadki piesze wg R5. **Reguła: komunikacja + pieszo nigdy nie jest gorsza od samego spaceru.** Limit dojścia 12 min ogranicza w R5 także podróż wyłącznie pieszą wewnątrz zapytania komunikacyjnego, więc dla każdej pary start–cel bierzemy min(czas R5 komunikacją, czas samego spaceru bez limitu 12 min, 5 km/h) **przed** zastosowaniem progów 30/45 min. Minimum ze stałą jest przemienne z medianą po odjazdach, więc to to samo, co mediana z minimum dla każdego odjazdu. Wariant bez tej reguły (`*_without_walk_rule`, tier `qa`) pokazuje jej wpływ.
- **Pieszo:** 5 km/h, do 60 min. **Rower:** 15 km/h, do 60 min, dwa warianty poziomu stresu ruchu R5: LTS ≤ 3 (domyślne r5py) i LTS ≤ 4; wybór wariantu głównego należy do właściciela, oba mają tier `table`. Samochodu nie liczono (brief §11).
- **Okna:** środa 7:00–9:00 (główne), 10:00–14:00, 20:00–22:00, sobota 10:00–14:00. **Max 2 przesiadki:** R5 `maxRides` = 3, okno 7–9, podawane jako różnica do wyniku głównego.
- **Feedy:** wariant „wszystkie” (główny) i „oficjalne”, osobne sieci R5. Wariant „sieć wspólnego biletu” jest odłożony (tabela taryf niepotwierdzona); kod przewiduje go jako kolejny wariant sieci (`fare_<nazwa>`), bez przeliczania czegokolwiek innego.
- **Maska pokrycia GTFS (§6):** maska fazy 2 dla tego samego wariantu feedów (`results/layers/frequent_cells.parquet`, w postaci poligonów `gtfs_coverage_mask.parquet`). W warstwie komórek wynik komunikacji poza maską to brak danych, nie 0. Wartości dla FUA i rdzenia obejmują wszystkie komórki (jak w fazie 2), mają `coverage_share` i oznaczenie „niepełne pokrycie GTFS”, gdy w masce jest < 85 % ludności; do porównań służy „obszar pokryty” i „rdzeń”. **Niekompletność po stronie celów** (miejsca obsługiwane tylko przez przewoźników bez GTFS) obniża dostępność także wewnątrz maski; maska tego nie usuwa. Pieszo i rower nie są maskowane.
- **Miejsca pracy** („miejsca pracy w granicach miasta”): zbiór Goliszek (IGiPZ PAN, CC BY 4.0) rozdzielony z komórek 100 m (część wieloczęściowych i niepełnych) na siatkę 250 m proporcjonalnie do pola przecięcia; sumy zgadzają się co do 1e-6. Zbiór obejmuje tylko miasta w granicach administracyjnych (w Trójmieście tylko Gdańsk, GZM brak → wynik pusty). Starty z całego FUA. Performance miejsc pracy to **stosunek średnich**: na skraju zasięgu zbioru mianownik (miejsca pracy w promieniu) wynosi kilka miejsc i stosunki komórek przekraczają 1000, więc średnia stosunków jest dla miejsc pracy bezużyteczna (zostaje jako kontrola `*_mean_of_ratios` dla startów w granicach miasta).
- **Z centrum:** średnia ważona ludnością po komórkach ≤ 1 km od centrum i osobno od węzła z `config.yaml`; w Trójmieście i GZM dla każdego centrum z `extra_centres`, z zastrzeżeniem z §11.
- **Liczby bezwzględne** („ludność osiągalna”, „miejsca pracy osiągalne”, `acc_*`, `prox_*`) mają tier `table` i oznaczenie, że mierzą wielkość miasta, a nie jakość transportu (§11).
- **Mediana liczby przesiadek:** routing regionalny R5 zwraca tylko czasy, więc liczba przesiadek pochodzi z **próby** par start–cel (start ważony ludnością, cel ważony ludnością wśród osiągalnych w 45 min, losowa minuta odjazdu 7:00–9:00) i najszybszego itinerarium r5py `DetailedItineraries` o tej minucie. Znane ograniczenie r5py: `DetailedItineraries` nie egzekwuje limitu dojścia 12 min tak jak routing regionalny.
- **Determinizm:** paczki 1 000 startów są zapisywane atomowo z podpisem wejść; ta sama paczka policzona drugi raz daje identyczne bajty (sprawdzone, sekcja 8). Wyniki zaokrąglone do 4 cyfr znaczących.

## 2. Wynik główny (środa 7–9, wszystkie feedy, siatka spisowa)

KZ = komunikacja zbiorowa + pieszo. Wartości to performance (0–100, może przekroczyć 100). „Obszar pokryty” = komórki w masce GTFS.

| Aglomeracja | Obszar | KZ 30 | KZ 45 | KZ 30 (stos. średnich) | KZ 45 (stos. średnich) | Pieszo 30 | Rower 30 LTS 3 | Rower 30 LTS 4 | Ludność w masce |
|---|---|---|---|---|---|---|---|---|---|
| Warszawa | pokryty | 28,4 | 47,1 | 34,2 | 58,1 |  |  |  |  |
| Warszawa | rdzeń | 33,9 | 58,8 | 35,7 | 61,4 | 66,4 | 45,2 | 52,4 | 99,0 % |
| Warszawa | FUA | 26,9 | 43,0 | 33,5 | 56,4 | 66,0 | 43,4 | 55,6 | 82,5 % (niepełne) |
| Kraków | pokryty | 24,5 | 39,5 | 31,4 | 49,3 |  |  |  |  |
| Kraków | rdzeń | 31,6 | 52,8 | 33,0 | 54,2 | 64,8 | 48,4 | 53,4 | 96,5 % |
| Kraków | FUA | 22,0 | 34,4 | 30,5 | 47,6 | 60,7 | 36,2 | 48,7 | 78,8 % (niepełne) |
| Łódź | pokryty | 26,0 | 41,6 | 28,3 | 48,5 |  |  |  |  |
| Łódź | rdzeń | 26,9 | 51,3 | 28,3 | 52,1 | 69,1 | 53,7 | 64,8 | 96,6 % |
| Łódź | FUA | 25,3 | 39,6 | 27,8 | 47,2 | 68,8 | 47,9 | 64,4 | 89,2 % |
| GZM | pokryty | 22,4 | 33,0 | 21,7 | 34,2 |  |  |  |  |
| GZM | rdzeń | 23,8 | 36,1 | 22,3 | 35,8 | 67,1 | 45,3 | 60,9 | 97,9 % |
| GZM | FUA | 21,9 | 32,2 | 21,6 | 33,9 | 67,5 | 41,3 | 58,9 | 95,1 % |
| Wrocław | pokryty | 24,6 | 45,5 | 29,1 | 52,4 |  |  |  |  |
| Wrocław | rdzeń | 27,6 | 53,0 | 29,4 | 54,5 | 65,4 | 58,5 | 70,2 | 97,9 % |
| Wrocław | FUA | 24,5 | 40,7 | 28,5 | 49,8 | 66,9 | 48,3 | 66,9 | 79,6 % (niepełne) |
| Poznań | pokryty | 24,2 | 40,1 | 29,2 | 47,4 |  |  |  |  |
| Poznań | rdzeń | 30,0 | 54,6 | 31,7 | 55,6 | 64,9 | 61,8 | 69,6 | 95,5 % |
| Poznań | FUA | 23,6 | 37,2 | 28,8 | 46,2 | 66,3 | 51,9 | 65,5 | 85,5 % |
| Trójmiasto | pokryty | 31,7 | 52,8 | 32,1 | 53,6 |  |  |  |  |
| Trójmiasto | rdzeń | 31,8 | 55,4 | 32,0 | 54,6 | 69,1 | 50,4 | 65,5 | 95,9 % |
| Trójmiasto | FUA | 28,3 | 46,0 | 30,7 | 50,1 | 68,4 | 47,1 | 64,3 | 83,2 % (niepełne) |

## 3. Warianty (różnica do wyniku głównego, pkt; KZ 30 / KZ 45)

| Aglomeracja | Obszar | Bazowy KZ 30 / 45 | Feedy oficjalne | 10–14 | 20–22 | Sobota 10–14 | Maks. 2 przesiadki | Surowy GHSL |
|---|---|---|---|---|---|---|---|---|
| Warszawa | pokryty | 28,4 / 47,1 | 0,60 / 2,01 | -2,17 / -3,95 | -2,44 / -4,18 | -3,62 / -6,67 | -0,00 / -0,10 | -0,43 / 0,45 |
| Warszawa | rdzeń | 33,9 / 58,8 | -0,03 / -0,25 | -2,45 / -3,35 | -2,70 / -3,35 | -4,11 / -6,11 | -0,00 / -0,14 | -0,84 / 0,48 |
| Kraków | pokryty | 24,5 / 39,5 | 0,43 / 0,94 | -1,30 / -2,10 | -1,67 / -1,35 | -2,83 / -4,09 | -0,00 / -0,04 | -2,38 / -1,55 |
| Kraków | rdzeń | 31,6 / 52,8 | -0,00 / -0,01 | -1,57 / -2,22 | -2,15 / -1,20 | -3,66 / -4,64 | -0,00 / -0,05 | -3,59 / -2,52 |
| Łódź | pokryty | 26,0 / 41,6 | -1,37 / 4,30 | -0,69 / -1,43 | -1,96 / -2,82 | -2,72 / -4,59 | -0,00 / -0,03 | -2,24 / -3,21 |
| Łódź | rdzeń | 26,9 / 51,3 | -0,12 / -0,49 | -0,52 / -1,05 | -1,51 / -2,34 | -2,89 / -4,99 | -0,00 / -0,04 | -2,86 / -5,01 |
| GZM | pokryty | 22,4 / 33,0 | 0,00 / 0,00 | -1,40 / -2,42 | -3,29 / -6,11 | -3,65 / -7,06 | -0,00 / -0,02 | -2,40 / -2,60 |
| GZM | rdzeń | 23,8 / 36,1 | 0,00 / 0,00 | -1,36 / -2,32 | -3,44 / -6,41 | -3,73 / -7,28 | -0,00 / -0,02 | -2,98 / -3,56 |
| Wrocław | pokryty | 24,6 / 45,5 | 0,52 / 1,70 | -0,92 / -1,08 | 0,03 / 1,08 | -1,10 / -1,05 | -0,00 / -0,02 | 0,55 / 0,48 |
| Wrocław | rdzeń | 27,6 / 53,0 | -0,03 / -0,08 | -0,94 / -0,95 | 0,22 / 1,73 | -1,25 / -0,89 | -0,00 / -0,03 | 0,52 / 0,10 |
| Poznań | pokryty | 24,2 / 40,1 | 0,00 / 0,00 | -1,53 / -2,28 | -2,06 / -2,74 | -2,95 / -4,99 | -0,00 / -0,04 | -2,15 / -3,80 |
| Poznań | rdzeń | 30,0 / 54,6 | 0,00 / 0,00 | -1,77 / -2,25 | -2,22 / -2,32 | -3,24 / -4,88 | -0,00 / -0,05 | -3,34 / -6,72 |
| Trójmiasto | pokryty | 31,7 / 52,8 | 0,00 / 0,00 | -1,92 / -3,17 | -5,44 / -9,94 | -4,24 / -7,90 | -0,00 / -0,05 | 0,05 / -0,30 |
| Trójmiasto | rdzeń | 31,8 / 55,4 | 0,00 / 0,00 | -1,74 / -2,80 | -5,00 / -9,07 | -4,05 / -7,27 | -0,00 / -0,05 | -2,06 / -2,81 |

„Feedy oficjalne” w wierszu „pokryty” liczone są na masce wariantu oficjalnego (mniejszej i bardziej miejskiej), więc tej różnicy nie należy czytać jako wpływu feedów; w wierszu „rdzeń” obszar jest ten sam.

## 4. Feedy oficjalne we wszystkich oknach i miejsca pracy

| Aglomeracja | Obszar | Oficjalne 7–9 (30/45) | Oficjalne 10–14 (30/45) | Oficjalne 20–22 (30/45) | Oficjalne sob. (30/45) | Miejsca pracy: performance 30/45 (stos. średnich) | Miejsca pracy osiągalne w 30/45 min |
|---|---|---|---|---|---|---|---|
| Warszawa | pokryty | 29,0 / 49,1 | 26,9 / 45,8 | 26,6 / 45,8 | 25,5 / 43,4 | 38,5 / 67,5 | 169 tys. / 504 tys. |
| Warszawa | rdzeń | 33,8 / 58,5 | 31,4 / 55,2 | 31,1 / 55,3 | 29,7 / 52,6 | 39,1 / 69,3 | 260 tys. / 764 tys. |
| Warszawa | FUA | 26,3 / 41,4 | 24,5 / 38,1 | 24,3 / 38,0 | 23,4 / 36,1 | 38,0 / 66,2 | 140 tys. / 422 tys. |
| Kraków | pokryty | 24,9 / 40,4 | 23,7 / 38,3 | 23,3 / 39,2 | 22,1 / 36,4 | 34,7 / 62,4 | 48 tys. / 127 tys. |
| Kraków | rdzeń | 31,6 / 52,8 | 30,1 / 50,6 | 29,5 / 51,6 | 28,0 / 48,1 | 36,0 / 66,7 | 71 tys. / 183 tys. |
| Kraków | FUA | 21,9 / 34,3 | 20,8 / 32,5 | 20,5 / 33,1 | 19,5 / 30,8 | 34,7 / 61,5 | 40 tys. / 105 tys. |
| Łódź | pokryty | 24,7 / 45,9 | 24,1 / 44,9 | 23,3 / 44,0 | 22,1 / 41,6 | 31,6 / 58,9 | 51 tys. / 127 tys. |
| Łódź | rdzeń | 26,8 / 50,8 | 26,2 / 49,8 | 25,3 / 48,8 | 23,9 / 46,0 | 31,7 / 62,7 | 72 tys. / 179 tys. |
| Łódź | FUA | 24,0 / 38,3 | 23,5 / 37,0 | 22,9 / 36,2 | 21,9 / 34,3 | 30,8 / 57,2 | 46 tys. / 116 tys. |
| GZM | pokryty | 22,4 / 33,0 | 21,0 / 30,6 | 19,1 / 26,9 | 18,7 / 26,0 | brak danych (GZM) | nan |
| GZM | rdzeń | 23,8 / 36,1 | 22,5 / 33,8 | 20,4 / 29,7 | 20,1 / 28,8 | brak danych (GZM) | nan |
| GZM | FUA | 21,9 / 32,2 | 20,5 / 29,8 | 18,7 / 26,3 | 18,3 / 25,3 | brak danych (GZM) | nan |
| Wrocław | pokryty | 25,2 / 47,2 | 24,2 / 46,1 | 25,2 / 48,4 | 24,0 / 46,2 | 32,3 / 60,2 | 83 tys. / 208 tys. |
| Wrocław | rdzeń | 27,6 / 52,9 | 26,6 / 52,0 | 27,8 / 54,7 | 26,3 / 52,1 | 32,4 / 62,2 | 100 tys. / 250 tys. |
| Wrocław | FUA | 24,5 / 40,5 | 23,7 / 39,5 | 24,5 / 41,3 | 23,6 / 39,6 | 31,6 / 57,7 | 67 tys. / 168 tys. |
| Poznań | pokryty | 24,2 / 40,1 | 22,7 / 37,8 | 22,2 / 37,4 | 21,3 / 35,1 | 33,9 / 57,4 | 62 tys. / 147 tys. |
| Poznań | rdzeń | 30,0 / 54,6 | 28,2 / 52,4 | 27,8 / 52,3 | 26,8 / 49,8 | 36,7 / 67,2 | 97 tys. / 224 tys. |
| Poznań | FUA | 23,6 / 37,2 | 22,1 / 35,0 | 21,6 / 34,5 | 20,8 / 32,4 | 33,6 / 56,5 | 55 tys. / 131 tys. |
| Trójmiasto | pokryty | 31,7 / 52,8 | 29,8 / 49,6 | 26,2 / 42,9 | 27,4 / 44,9 | 32,1 / 57,3 | 28 tys. / 72 tys. |
| Trójmiasto | rdzeń | 31,8 / 55,4 | 30,1 / 52,6 | 26,8 / 46,3 | 27,8 / 48,1 | 31,8 / 58,2 | 35 tys. / 90 tys. |
| Trójmiasto | FUA | 28,3 / 46,0 | 26,6 / 43,2 | 23,6 / 37,3 | 24,6 / 39,1 | 31,1 / 54,6 | 24 tys. / 62 tys. |

## 5. Z centrum (komórki ≤ 1 km)

| Aglomeracja | Punkt | Rodzaj | Komórek ≤ 1 km | Ludność | KZ 30 | KZ 45 | KZ 30 oficjalne | Pieszo 30 | Rower 30 LTS 3 / 4 |
|---|---|---|---:|---|---|---|---|---|---|
| Warszawa | Rondo Dmowskiego | centrum | 51 | 31910 | 56,9 | 88,0 | 56,9 | 67,9 | 49,0 / 57,3 |
| Warszawa | Metro Centrum | węzeł | 50 | 31134 | 57,3 | 88,3 | 57,3 | 68,2 | 48,8 / 57,1 |
| Kraków | Rynek Główny | centrum | 50 | 21184 | 40,4 | 80,9 | 40,4 | 70,2 | 57,8 / 61,8 |
| Kraków | Kraków Główny | węzeł | 50 | 15814 | 42,8 | 80,8 | 42,8 | 62,3 | 57,6 / 61,6 |
| Łódź | pl. Wolności | centrum | 47 | 36450 | 37,1 | 69,6 | 37,1 | 74,2 | 63,9 / 73,8 |
| Łódź | Piotrkowska Centrum | węzeł | 51 | 26323 | 43,6 | 78,2 | 43,5 | 66,0 | 72,1 / 80,9 |
| GZM | Katowice Rynek | centrum | 50 | 24598 | 36,1 | 68,2 | 36,1 | 76,2 | 49,6 / 56,9 |
| GZM | Gliwice Rynek | centrum dodatkowe | 51 | 23530 | 45,5 | 66,2 | 45,5 | 79,1 | 67,5 / 75,9 |
| GZM | Sosnowiec centrum | centrum dodatkowe | 49 | 28003 | 29,7 | 49,1 | 29,7 | 77,4 | 57,2 / 68,3 |
| GZM | Bytom Rynek | centrum dodatkowe | 50 | 31613 | 28,4 | 46,8 | 28,4 | 84,7 | 34,7 / 66,1 |
| GZM | Zabrze centrum | centrum dodatkowe | 50 | 22813 | 36,1 | 45,6 | 36,1 | 80,6 | 51,8 / 62,7 |
| GZM | Tychy centrum | centrum dodatkowe | 50 | 26381 | 70,1 | 54,3 | 70,1 | 82,5 | 78,5 / 81,4 |
| GZM | Chorzów Rynek | centrum dodatkowe | 52 | 25369 | 27,4 | 50,2 | 27,4 | 71,0 | 44,5 / 52,3 |
| GZM | Dąbrowa Górnicza centrum | centrum dodatkowe | 50 | 20496 | 36,3 | 53,7 | 36,3 | 73,3 | 57,0 / 68,5 |
| GZM | Ruda Śląska (Nowy Bytom) | centrum dodatkowe | 50 | 9589 | 17,6 | 39,0 | 17,6 | 54,2 | 35,6 / 51,7 |
| Wrocław | Rynek | centrum | 50 | 27049 | 51,3 | 79,1 | 51,3 | 73,3 | 78,2 / 86,0 |
| Wrocław | Galeria Dominikańska | węzeł | 51 | 26371 | 48,1 | 78,1 | 48,1 | 72,7 | 75,8 / 85,0 |
| Poznań | Stary Rynek | centrum | 52 | 23188 | 51,5 | 71,6 | 51,5 | 66,9 | 82,0 / 84,9 |
| Poznań | Rondo Kaponiera | węzeł | 51 | 24520 | 51,5 | 73,5 | 51,5 | 69,4 | 79,1 / 83,3 |
| Trójmiasto | Gdańsk Główny | centrum | 49 | 11050 | 39,7 | 81,4 | 39,7 | 69,8 | 62,3 / 73,9 |
| Trójmiasto | Gdynia Główna | centrum dodatkowe | 47 | 12999 | 61,2 | 102,5 | 61,2 | 74,9 | 44,4 / 65,5 |
| Trójmiasto | Sopot | centrum dodatkowe | 50 | 17830 | 36,8 | 76,7 | 36,8 | 80,7 | 46,2 / 60,0 |

## 6. Liczba przesiadek (próba)

| Aglomeracja | Par w próbie | Z itinerarium | Pieszo najszybciej | Mediana przesiadek | Średnia | 0 / 1 / ≥2 przesiadki, % | Mediana czasu: itinerarium / regionalny, min | Itinerarium dłuższe od czasu regionalnego o > 5 min | Dojście pieszo > 12 min w itinerarium z przejazdem |
|---|---:|---:|---|---|---|---|---|---|---|
| Warszawa | 200 | 200 | 27,5 % | 0 | 0,52 | 55,9 / 36,6 / 7,6 | 32,1 / 35,0 | 1,5 % | 4,8 % (suma > 24 min) |
| Kraków | 200 | 200 | 32,0 % | 0 | 0,49 | 55,9 / 39,0 / 5,1 | 31,4 / 34,0 | 1,0 % | 9,6 % (suma > 24 min) |
| Łódź | 200 | 200 | 23,0 % | 0 | 0,29 | 73,4 / 24,7 / 1,9 | 29,5 / 31,0 | 1,0 % | 5,8 % (suma > 24 min) |
| GZM | 200 | 200 | 15,5 % | 0 | 0,28 | 75,1 / 21,9 / 3,0 | 29,6 / 35,0 | 3,5 % | 8,3 % (suma > 24 min) |
| Wrocław | 200 | 200 | 29,5 % | 0 | 0,38 | 63,8 / 34,0 / 2,1 | 32,6 / 35,0 | 1,5 % | 9,2 % (suma > 24 min) |
| Poznań | 200 | 200 | 27,0 % | 0 | 0,46 | 58,9 / 36,3 / 4,8 | 31,1 / 34,0 | 2,5 % | 11,6 % (suma > 24 min) |
| Trójmiasto | 200 | 200 | 19,5 % | 0 | 0,43 | 60,9 / 35,4 / 3,7 | 32,5 / 36,0 | 1,0 % | 8,7 % (suma > 24 min) |

Kolumna „dojście > 12 min” liczy itineraria z przejazdem, w których suma odcinków pieszych przekracza 24 min (dwa odcinki po 12 min), czyli przypadki, gdzie `DetailedItineraries` na pewno przekroczył limit regionalny.

## 7. Benchmark DG REGIO (§7.2)

DG REGIO: Poelman, Dijkstra, Ackermans (2020), WP 01/2020. Średnie próby 42 miast UE: KZ 30 = 24, KZ 45 = 57, pieszo 52, rower 75. Wartości miast odczytane z wykresów (±1 pkt). Wrocław nie jest w próbie DG REGIO; jego wiersze pokazują tylko rozkład naszych wariantów.

| Miasto | Miara | DG REGIO (odczyt) | Nasz: FUA | Nasz: rdzeń (główny) | Rdzeń, cele tylko w rdzeniu | Rdzeń, stosunek średnich | Rdzeń bez reguły min(KZ, pieszo) | Dojście 5 km (próba 60 startów, FUA) |
|---|---|---|---|---|---|---|---|---|
| Warszawa | KZ 30 min | 31,0 | 26,9 | 33,9 | 35,8 | 35,7 | 33,7 | +2,8 |
| Warszawa | KZ 45 min | 62,0 | 43,0 | 58,8 | 62,5 | 61,4 | 58,7 | +4,2 |
| Warszawa | Pieszo 30 min | 49,0 | 66,0 | 66,4 | 66,9 | 67,5 |  |  |
| Warszawa | Rower 30 min LTS 3 | 70,5 | 43,4 | 45,2 | 46,5 | 45,3 |  |  |
| Warszawa | Rower 30 min LTS 4 | 70,5 | 55,6 | 52,4 | 53,6 | 52,3 |  |  |
| Poznań | KZ 30 min | 26,0 | 23,6 | 30,0 | 32,4 | 31,7 | 29,5 | +2,8 |
| Poznań | KZ 45 min | 75,0 | 37,2 | 54,6 | 64,7 | 55,6 | 54,4 | +3,1 |
| Poznań | Pieszo 30 min | 43,0 | 66,3 | 64,9 | 65,9 | 66,9 |  |  |
| Poznań | Rower 30 min LTS 3 | 81,0 | 51,9 | 61,8 | 64,7 | 64,0 |  |  |
| Poznań | Rower 30 min LTS 4 | 81,0 | 65,5 | 69,6 | 71,8 | 71,2 |  |  |
| Łódź | KZ 30 min | 25,5 | 25,3 | 26,9 | 27,7 | 28,3 | 26,4 | +2,7 |
| Łódź | KZ 45 min | 75,0 | 39,6 | 51,3 | 56,4 | 52,1 | 51,1 | +3,4 |
| Łódź | Pieszo 30 min | 54,0 | 68,8 | 69,1 | 69,4 | 70,1 |  |  |
| Łódź | Rower 30 min LTS 3 | 81,0 | 47,9 | 53,7 | 55,1 | 55,9 |  |  |
| Łódź | Rower 30 min LTS 4 | 81,0 | 64,4 | 64,8 | 65,7 | 66,1 |  |  |
| Wrocław | KZ 30 min | brak w próbie DG REGIO | 24,5 | 27,6 | 28,4 | 29,4 | 27,2 | +1,8 |
| Wrocław | KZ 45 min | brak w próbie DG REGIO | 40,7 | 53,0 | 57,1 | 54,5 | 52,8 | +1,9 |
| Wrocław | Pieszo 30 min | brak w próbie DG REGIO | 66,9 | 65,4 | 65,8 | 67,7 |  |  |
| Wrocław | Rower 30 min LTS 3 | brak w próbie DG REGIO | 48,3 | 58,5 | 59,6 | 62,0 |  |  |
| Wrocław | Rower 30 min LTS 4 | brak w próbie DG REGIO | 66,9 | 70,2 | 70,9 | 72,8 |  |  |

**Różnice metodyczne:**

- Domena: DG REGIO liczy starty i cele tylko w urban centre; tu starty w FUA (oraz rdzeń, obszar pokryty), cele i mianownik w FUA + 15 km.
- Dojście: OTP w DG REGIO do 5 km pieszo; tu 1 km (12 min przy 5 km/h) na dojście i odejście, przy czym podróż czysto piesza jest bez limitu (min(komunikacja, pieszo)).
- Czas: DG REGIO średnia z 9 odjazdów co 15 min w 2-godzinnym szczycie; tu mediana z odjazdów co minutę 7:00–9:00.
- Rozkłady: DG REGIO 2018; tu środa 2026-11-25 (sobota 2026-11-28).
- Ludność: DG REGIO 2011 na poligonach Urban Atlas 2012; tu NSP 2021 rozłożony wzorem GHSL 2020 na komórki 250 m (wariant surowy GHSL obok).
- Router: OpenTripPlanner 1.2.0 wobec Conveyal R5 v7.5.1; prędkość roweru i LTS w DG REGIO nieopisane (tu 15 km/h i LTS ≤ 3 albo ≤ 4).
- Wartości DG REGIO odczytane z wykresów (rys. 7, 9, 10), dokładność ok. ±1 pkt; agregacja po komórkach nieopisana wprost.

**Przypisanie różnic (tylko to, na co pozwalają nasze dane):** kolumna „rdzeń” zbliża domenę startów do urban centre; „cele tylko w rdzeniu” ogranicza dodatkowo licznik i mianownik do celów w granicach miasta (przybliżenie domeny celów DG REGIO); „stosunek średnich” pokazuje wpływ sposobu agregacji; „bez reguły min” pokazuje, ile daje nieograniczony spacer; efekt dojścia 5 km pochodzi z próby 60 startów z `plan.md` (liczonej jeszcze bez reguły min, więc z regułą jest mniejszy). Wpływu roku rozkładów (2018/2026), roku ludności (2011/2021), poligonów Urban Atlas i średniej z 9 odjazdów nie da się wydzielić z naszych danych.

## 8. Kontrole wewnętrzne

| Aglomeracja | Kontrola | Naruszenia | Komórek | Wynik | Uwagi |
|---|---|---:|---:|---|---|
| Warszawa | all/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | all/pt_am: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 88,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | all/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | all/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88250 komórkach |
| Warszawa | all/pt_am_max3rides: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | all/pt_am_max3rides: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 88,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | all/pt_am_max3rides: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | all/pt_am_max3rides: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88250 komórkach |
| Warszawa | all/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | all/pt_evening: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 81,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | all/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | all/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88409 komórkach |
| Warszawa | all/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | all/pt_midday: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 83,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | all/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | all/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88381 komórkach |
| Warszawa | all/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | all/pt_saturday: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 80,5; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | all/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | all/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88437 komórkach |
| Warszawa | official/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | official/pt_am: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 88,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | official/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | official/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88253 komórkach |
| Warszawa | official/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | official/pt_evening: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 81,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | official/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | official/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88408 komórkach |
| Warszawa | official/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | official/pt_midday: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 83,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | official/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | official/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88380 komórkach |
| Warszawa | official/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | official/pt_saturday: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 80,5; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | official/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | official/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 88926 | OK | podnosi osiągalnych w 30 min w 88436 komórkach |
| Warszawa | street/bike_lts3: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | street/bike_lts3: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 87,7; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | street/bike_lts4: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | street/bike_lts4: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 95,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | street/walk: osiągalni rosną z progiem 5→60 min | 0 | 88926 | OK |  |
| Warszawa | street/walk: performance 30 min w [0, 100] | 0 | 88926 | OK | maks. 99,9; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Warszawa | rower LTS 4 ≥ LTS 3 (osiągalni, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | bez limitu przesiadek ≥ maks. 2 przesiadki (osiągalni, każdy próg) | 0 | 88926 | OK |  |
| Warszawa | wszystkie feedy ≥ oficjalne (osiągalni, każdy próg) | 730 | 88926 | UWAGA | ludność komórek z naruszeniem: 57440 |
| Kraków | all/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | all/pt_am: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 64,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | all/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | all/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37581 komórkach |
| Kraków | all/pt_am_max3rides: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | all/pt_am_max3rides: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 64,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | all/pt_am_max3rides: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | all/pt_am_max3rides: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37581 komórkach |
| Kraków | all/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | all/pt_evening: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 62,1; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | all/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | all/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37634 komórkach |
| Kraków | all/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | all/pt_midday: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 61,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | all/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | all/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37605 komórkach |
| Kraków | all/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | all/pt_saturday: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 59,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | all/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | all/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37665 komórkach |
| Kraków | official/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | official/pt_am: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 64,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | official/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | official/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37581 komórkach |
| Kraków | official/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | official/pt_evening: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 62,1; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | official/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | official/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37634 komórkach |
| Kraków | official/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | official/pt_midday: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 61,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | official/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | official/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37605 komórkach |
| Kraków | official/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | official/pt_saturday: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 59,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | official/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 37817 | OK |  |
| Kraków | official/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 37817 | OK | podnosi osiągalnych w 30 min w 37665 komórkach |
| Kraków | street/bike_lts3: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | street/bike_lts3: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 72,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | street/bike_lts4: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | street/bike_lts4: performance 30 min w [0, 100] | 0 | 37817 | OK | maks. 79,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | street/walk: osiągalni rosną z progiem 5→60 min | 0 | 37817 | OK |  |
| Kraków | street/walk: performance 30 min w [0, 100] | 0 | 37813 | OK | maks. 96,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Kraków | rower LTS 4 ≥ LTS 3 (osiągalni, każdy próg) | 0 | 37817 | OK |  |
| Kraków | bez limitu przesiadek ≥ maks. 2 przesiadki (osiągalni, każdy próg) | 0 | 37817 | OK |  |
| Kraków | wszystkie feedy ≥ oficjalne (osiągalni, każdy próg) | 20 | 37817 | UWAGA | ludność komórek z naruszeniem: 835 |
| Łódź | all/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | all/pt_am: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 69,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | all/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | all/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26096 komórkach |
| Łódź | all/pt_am_max3rides: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | all/pt_am_max3rides: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 69,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | all/pt_am_max3rides: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | all/pt_am_max3rides: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26096 komórkach |
| Łódź | all/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | all/pt_evening: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 66,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | all/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | all/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26148 komórkach |
| Łódź | all/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | all/pt_midday: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 68,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | all/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | all/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26106 komórkach |
| Łódź | all/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | all/pt_saturday: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 67,1; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | all/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | all/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26170 komórkach |
| Łódź | official/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | official/pt_am: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 60,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | official/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | official/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26096 komórkach |
| Łódź | official/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | official/pt_evening: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 59,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | official/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | official/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26148 komórkach |
| Łódź | official/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | official/pt_midday: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 60,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | official/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | official/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26109 komórkach |
| Łódź | official/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | official/pt_saturday: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 59,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | official/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 26274 | OK |  |
| Łódź | official/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 26274 | OK | podnosi osiągalnych w 30 min w 26170 komórkach |
| Łódź | street/bike_lts3: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | street/bike_lts3: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 83,7; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | street/bike_lts4: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | street/bike_lts4: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 91,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | street/walk: osiągalni rosną z progiem 5→60 min | 0 | 26274 | OK |  |
| Łódź | street/walk: performance 30 min w [0, 100] | 0 | 26274 | OK | maks. 98,3; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Łódź | rower LTS 4 ≥ LTS 3 (osiągalni, każdy próg) | 0 | 26274 | OK |  |
| Łódź | bez limitu przesiadek ≥ maks. 2 przesiadki (osiągalni, każdy próg) | 0 | 26274 | OK |  |
| Łódź | wszystkie feedy ≥ oficjalne (osiągalni, każdy próg) | 159 | 26274 | UWAGA | ludność komórek z naruszeniem: 2278 |
| GZM | all/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | all/pt_am: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 77,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | all/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | all/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24806 komórkach |
| GZM | all/pt_am_max3rides: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | all/pt_am_max3rides: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 77,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | all/pt_am_max3rides: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | all/pt_am_max3rides: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24806 komórkach |
| GZM | all/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | all/pt_evening: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 76,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | all/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | all/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24817 komórkach |
| GZM | all/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | all/pt_midday: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 77,3; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | all/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | all/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24808 komórkach |
| GZM | all/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | all/pt_saturday: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 74,7; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | all/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | all/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24819 komórkach |
| GZM | official/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | official/pt_am: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 77,6; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | official/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | official/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24806 komórkach |
| GZM | official/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | official/pt_evening: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 76,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | official/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | official/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24817 komórkach |
| GZM | official/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | official/pt_midday: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 77,3; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | official/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | official/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24808 komórkach |
| GZM | official/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | official/pt_saturday: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 74,7; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | official/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 24869 | OK |  |
| GZM | official/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 24869 | OK | podnosi osiągalnych w 30 min w 24819 komórkach |
| GZM | street/bike_lts3: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | street/bike_lts3: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 89,1; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | street/bike_lts4: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | street/bike_lts4: performance 30 min w [0, 100] | 0 | 24869 | OK | maks. 93,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | street/walk: osiągalni rosną z progiem 5→60 min | 0 | 24869 | OK |  |
| GZM | street/walk: performance 30 min w [0, 100] | 0 | 24868 | OK | maks. 100,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| GZM | rower LTS 4 ≥ LTS 3 (osiągalni, każdy próg) | 0 | 24869 | OK |  |
| GZM | bez limitu przesiadek ≥ maks. 2 przesiadki (osiągalni, każdy próg) | 0 | 24869 | OK |  |
| GZM | wszystkie feedy ≥ oficjalne (osiągalni, każdy próg) | 1 | 24869 | UWAGA | ludność komórek z naruszeniem: 3 |
| Wrocław | all/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | all/pt_am: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | all/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | all/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20089 komórkach |
| Wrocław | all/pt_am_max3rides: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | all/pt_am_max3rides: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | all/pt_am_max3rides: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | all/pt_am_max3rides: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20089 komórkach |
| Wrocław | all/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | all/pt_evening: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | all/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | all/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20096 komórkach |
| Wrocław | all/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | all/pt_midday: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | all/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | all/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20097 komórkach |
| Wrocław | all/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | all/pt_saturday: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | all/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | all/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20098 komórkach |
| Wrocław | official/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | official/pt_am: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | official/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | official/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20089 komórkach |
| Wrocław | official/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | official/pt_evening: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | official/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | official/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20096 komórkach |
| Wrocław | official/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | official/pt_midday: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | official/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | official/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20097 komórkach |
| Wrocław | official/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | official/pt_saturday: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 69,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | official/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | official/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 20153 | OK | podnosi osiągalnych w 30 min w 20098 komórkach |
| Wrocław | street/bike_lts3: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | street/bike_lts3: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 85,7; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | street/bike_lts4: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | street/bike_lts4: performance 30 min w [0, 100] | 0 | 20153 | OK | maks. 92,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | street/walk: osiągalni rosną z progiem 5→60 min | 0 | 20153 | OK |  |
| Wrocław | street/walk: performance 30 min w [0, 100] | 0 | 20149 | OK | maks. 100,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Wrocław | rower LTS 4 ≥ LTS 3 (osiągalni, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | bez limitu przesiadek ≥ maks. 2 przesiadki (osiągalni, każdy próg) | 0 | 20153 | OK |  |
| Wrocław | wszystkie feedy ≥ oficjalne (osiągalni, każdy próg) | 26 | 20153 | UWAGA | ludność komórek z naruszeniem: 416 |
| Poznań | all/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | all/pt_am: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 68,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | all/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | all/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 18994 komórkach |
| Poznań | all/pt_am_max3rides: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | all/pt_am_max3rides: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 68,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | all/pt_am_max3rides: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | all/pt_am_max3rides: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 18994 komórkach |
| Poznań | all/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | all/pt_evening: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 67,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | all/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | all/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 19032 komórkach |
| Poznań | all/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | all/pt_midday: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 65,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | all/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | all/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 19026 komórkach |
| Poznań | all/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | all/pt_saturday: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 64,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | all/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | all/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 19041 komórkach |
| Poznań | official/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | official/pt_am: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 68,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | official/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | official/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 18994 komórkach |
| Poznań | official/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | official/pt_evening: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 67,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | official/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | official/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 19032 komórkach |
| Poznań | official/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | official/pt_midday: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 65,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | official/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | official/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 19026 komórkach |
| Poznań | official/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | official/pt_saturday: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 64,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | official/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 19201 | OK |  |
| Poznań | official/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 19201 | OK | podnosi osiągalnych w 30 min w 19041 komórkach |
| Poznań | street/bike_lts3: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | street/bike_lts3: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 86,8; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | street/bike_lts4: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | street/bike_lts4: performance 30 min w [0, 100] | 0 | 19201 | OK | maks. 97,3; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | street/walk: osiągalni rosną z progiem 5→60 min | 0 | 19201 | OK |  |
| Poznań | street/walk: performance 30 min w [0, 100] | 0 | 19195 | OK | maks. 100,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 18 komórek, ludność 0 |
| Poznań | rower LTS 4 ≥ LTS 3 (osiągalni, każdy próg) | 0 | 19201 | OK |  |
| Poznań | bez limitu przesiadek ≥ maks. 2 przesiadki (osiągalni, każdy próg) | 0 | 19201 | OK |  |
| Poznań | wszystkie feedy ≥ oficjalne (osiągalni, każdy próg) | 2 | 19201 | UWAGA | ludność komórek z naruszeniem: 15 |
| Trójmiasto | all/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_am: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 85,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | all/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17478 komórkach |
| Trójmiasto | all/pt_am_max3rides: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_am_max3rides: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 85,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | all/pt_am_max3rides: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_am_max3rides: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17478 komórkach |
| Trójmiasto | all/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_evening: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 76,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | all/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17516 komórkach |
| Trójmiasto | all/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_midday: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 81,5; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | all/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17490 komórkach |
| Trójmiasto | all/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_saturday: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 73,5; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | all/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | all/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17504 komórkach |
| Trójmiasto | official/pt_am: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_am: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 85,4; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | official/pt_am: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_am: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17478 komórkach |
| Trójmiasto | official/pt_evening: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_evening: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 76,0; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | official/pt_evening: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_evening: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17516 komórkach |
| Trójmiasto | official/pt_midday: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_midday: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 81,5; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | official/pt_midday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_midday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17490 komórkach |
| Trójmiasto | official/pt_saturday: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_saturday: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 73,5; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | official/pt_saturday: KZ + pieszo ≥ sam spacer (każda komórka, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | official/pt_saturday: reguła min(KZ, pieszo) nigdy nie obniża wyniku R5 | 0 | 17561 | OK | podnosi osiągalnych w 30 min w 17504 komórkach |
| Trójmiasto | street/bike_lts3: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | street/bike_lts3: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 84,7; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | street/bike_lts4: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | street/bike_lts4: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 94,2; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | street/walk: osiągalni rosną z progiem 5→60 min | 0 | 17561 | OK |  |
| Trójmiasto | street/walk: performance 30 min w [0, 100] | 0 | 17561 | OK | maks. 98,3; > 100 to cele dalej niż promień (szybki środek transportu); 0 linkowania: 0 komórek, ludność 0 |
| Trójmiasto | rower LTS 4 ≥ LTS 3 (osiągalni, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | bez limitu przesiadek ≥ maks. 2 przesiadki (osiągalni, każdy próg) | 0 | 17561 | OK |  |
| Trójmiasto | wszystkie feedy ≥ oficjalne (osiągalni, każdy próg) | 0 | 17561 | OK |  |

Performance > 100 nie jest błędem: licznik liczy cele osiągalne także poza promieniem proximity (np. koleją), mianownik tylko te w promieniu.

**Wznawialność i determinizm (test na Wrocławiu):** przebieg przerwano dwa razy: w trakcie próby przesiadek (po zmianie parametrów próby jej podpis się zmienił i jednostka została policzona od nowa, a 4 gotowe jednostki zostały pominięte) i w trakcie paczki 9/21 okna 10–14 (zabicie procesu). Po ponownym uruchomieniu tego samego polecenia pominięto 7 gotowych jednostek i 8 gotowych paczek, liczenie ruszyło od paczki 9; nie zostały pliki częściowe. Pięć paczek (pieszo, KZ 7–9, rower LTS 4, KZ oficjalne 7–9, sobota) policzono drugi raz w nowej JVM: pliki parquet są identyczne co do bajta (SHA-256), pamięć podręczna czasów pieszych też.

## 9. Pary start–cel do porównania z wyszukiwarką (§7.4)

Porównywany jest czas **dla podanej godziny odjazdu** w środę 2026-11-25 (kolumna „R5 o tej godzinie”), nie mediana z okna: od tej godziny do najwcześniejszego przyjazdu, jaki pokazuje wyszukiwarka dla tego samego dnia i godziny (tryb komunikacji zbiorowej). Starty leżą przy przystankach, bo `DetailedItineraries` nie egzekwuje limitu dojścia 12 min. Odpowiedzi wyszukiwarki zebrano ręcznie i zapisano w `od_pairs_planner.csv` (data zapytania w tabeli). Różnica > 20 % wymaga wyjaśnienia (§7.4).

Wyszukiwarkę odpytano dla 31 par, porównywalnych (obie strony znalazły trasę) jest 30. W granicy ±20 % mieści się 28 par; R5 jest wolniejszy o więcej niż 20 % w 2, szybszy o więcej niż 20 % w 0. Suma czasów R5 do sumy czasów wyszukiwarki: 0,982; mediana różnicy -1,9 %. Każda różnica powyżej 20 % ma wyjaśnienie w kolumnie „Uwagi”.

| Miasto | Nr | Rodzaj | Start (lon, lat) | Cel (lon, lat) | Odjazd | R5 o tej godzinie, min | R5 mediana 7–9, min | Pieszo, min | Trasa R5 (najszybsza o tej godzinie) | Wyszukiwarka | Data zapytania | Linie w wyszukiwarce | Uwagi | Wyszukiwarka, min | R5 do wyszukiwarki, % |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Warszawa | 1 | do węzła, start 1,5–5 km od centrum | Rakowiec (przystanek warsaw_ztm:403302) (20.98434, 52.19899) | Metro Centrum (węzeł z config.yaml) (21.01070, 52.23020) | 2026-11-25 07:35 | 23 | 23 | 55 | 22,0 min: WALK 0.1 min | BUS 504 (Rakowiec -> Pl. Zawiszy) 10.0 min (czekanie 1.0 min) | WALK 3.4 min (czekanie 0.9 min) | RAIL R1 (Warszawa Ochota -> Warszawa Śródmieście) 2.1 min (czekanie 1.2 min) | WALK 3.4 min | Google Maps | 2026-11-24 | 175 | odjazd 07:35 | 22 | +5 |
| Warszawa | 2 | do węzła, start 5–12 km | Suchy Las (przystanek warsaw_ztm:430801) (20.88481, 52.18585) | Metro Centrum (węzeł z config.yaml) (21.01070, 52.23020) | 2026-11-25 07:50 | 42 | 39 | – | 37,5 min: WALK 16.1 min | RAIL R1 (Warszawa Ursus -> Warszawa Śródmieście) 14.5 min (czekanie 3.4 min) | WALK 3.4 min | Google Maps | 2026-11-24 | 207 + R1 | odjazd 07:59; pieszo + R1 odjazd 07:55 z tym samym przyjazdem | 43 | −2 |
| Warszawa | 3 | do węzła, start > 12 km | Piastów Al. Piłsudskiego 02 (przystanek warsaw_gpa:piastow-al-pilsudskiego02-tubvd) (20.83538, 52.19297) | Metro Centrum (węzeł z config.yaml) (21.01070, 52.23020) | 2026-11-25 08:05 | 49 | 44 | – | 44,4 min: WALK 20.2 min | RAIL S1 (Piastów -> Warszawa Śródmieście) 19.0 min (czekanie 1.8 min) | WALK 3.4 min | Google Maps | 2026-11-24 | 716 + S1 | odjazd 08:08 | 50 | −2 |
| Warszawa | 4 | styczna (przystanek–przystanek, 3–10 km od centrum) | Metro Kondratowicza (przystanek warsaw_ztm:114608) (21.05090, 52.29114) | Znana (przystanek warsaw_ztm:510406) (20.92586, 52.23408) | 2026-11-25 08:20 | 41 | 43 | – | 41,6 min: WALK 2.9 min | SUBWAY M2 (1146M -> 5030M) 27.0 min (czekanie 1.1 min) | WALK 2.5 min (czekanie 0.9 min) | BUS 129 (Metro Księcia Janusza -> Znana) 3.0 min (czekanie 2.5 min) | WALK 1.6 min | Google Maps | 2026-11-24 | M2 + 190 | odjazd 08:29; R5 (41 min) przesiada się z M2 na autobus 129 z 2,5 min zapasu – tej przesiadki Google nie proponuje | 51 | −20 |
| Kraków | 1 | do węzła, start 1,5–5 km od centrum | Rusznikarska (przystanek krakow_bus:18454) (19.92637, 50.08379) | Kraków Główny (węzeł z config.yaml) (19.94790, 50.06840) | 2026-11-25 07:35 | 17 | 17 | 36 | 16,3 min: WALK 7.2 min | TRAM 15 (Bratysławska -> Dworzec Główny Tunel) 7.0 min (czekanie 1.0 min) | WALK 1.1 min | Google Maps | 2026-11-24 | 7 | odjazd 07:37; linia 15 przyjazd 07:53 | 17 | +0 |
| Kraków | 2 | do węzła, start 5–12 km | Brzezie Kluczwody (przystanek krakow_bus:12613) (19.82184, 50.12924) | Kraków Główny (węzeł z config.yaml) (19.94790, 50.06840) | 2026-11-25 07:50 | 45 | 52 | – | 45,7 min: WALK 1.5 min | BUS 288 (Brzezie Kluczwody -> Bronowice SKA) 19.0 min (czekanie 1.0 min) | WALK 9.2 min (czekanie 0.8 min) | RAIL SKA3 (Kraków Bronowice -> Kraków Główny) 6.2 min (czekanie 3.8 min) | WALK 4.2 min | Google Maps | 2026-11-24 | 288 + SKA3 | odjazd 07:50 | 43 | +5 |
| Kraków | 3 | do węzła, start > 12 km | Biały Kościół Dolina Kluczwody (przystanek krakow_bus:13937) (19.82677, 50.16814) | Kraków Główny (węzeł z config.yaml) (19.94790, 50.06840) | 2026-11-25 08:05 | 52 | 52 | – | 50,2 min: WALK 0.0 min | BUS 310 (Biały Kościół Dolina Kluczwody -> Rondo Ofiar Katynia) 18.0 min (czekanie 4.0 min) | WALK 2.5 min (czekanie 1.0 min) | BUS 168 (Rondo Ofiar Katynia -> Krowodrza Górka P+R) 9.0 min (czekanie 1.4 min) | WALK 0.9 min (czekanie 1.0 min) | TRAM 7 (Krowodrza Górka P+R -> Dworzec Główny Tunel) 8.0 min (czekanie 3.0 min) | WALK 1.1 min | Google Maps | 2026-11-24 | 310 + 168 + 15 | odjazd 08:14 | 54 | −4 |
| Kraków | 4 | styczna (przystanek–przystanek, 3–10 km od centrum) | Stella-Sawickiego (przystanek krakow_mobilis:14) (20.00359, 50.07653) | Zarzecze (przystanek krakow_bus:18275) (19.88678, 50.07599) | 2026-11-25 08:20 | 48 | 46 | 118 | 43,2 min: WALK 0.1 min | BUS 129 (Stella-Sawickiego -> Wiślicka) 6.0 min (czekanie 1.1 min) | BUS 172 (Wiślicka -> Bronowice SKA) 26.0 min (czekanie 4.0 min) | BUS 501 (Bronowice SKA -> Zarzecze) 1.0 min (czekanie 3.0 min) | WALK 2.0 min | Google Maps | 2026-11-24 | 15 + SKA3 | odjazd 08:26; opcje autobusowe przyjazd 09:12 | 50 | −4 |
| Łódź | 1 | do węzła, start 1,5–5 km od centrum | Karolewska-Włókniarzy (przystanek lodz:1673) (19.43544, 51.75855) | Piotrkowska Centrum (węzeł z config.yaml) (19.45730, 51.75940) | 2026-11-25 07:35 | 16 | 14 | 21 | 14,2 min: WALK 6.1 min | TRAM 12 (Bandurskiego-Dw. Łódź Kaliska -> Piotrkowska Centrum) 6.0 min (czekanie 1.1 min) | WALK 1.1 min | Google Maps | 2026-11-24 | 13 | odjazd 07:35 (tramwaj odjeżdża w minucie zapytania; R5 nie zdąża na ten kurs i jedzie linią 12) | 11 | +45 |
| Łódź | 2 | do węzła, start 5–12 km | Wojska Polskiego-Krótka (Aleksandrów) (przystanek lodz:1922) (19.31234, 51.81771) | Piotrkowska Centrum (węzeł z config.yaml) (19.45730, 51.75940) | 2026-11-25 07:50 | 64 | 57 | – | 61,0 min: WALK 4.9 min | BUS 78 (Wojska Polskiego-Bratoszewskiego (Aleks. -> Rydzowa-Aleksandrowska) 11.0 min (czekanie 6.2 min) | WALK 0.8 min (czekanie 1.0 min) | TRAM 2 (Aleksandrowska-Szparagowa -> Kościuszki-Mickiewicza) 30.0 min (czekanie 5.2 min) | WALK 2.0 min | Google Maps | 2026-11-24 | 78 + 8 | odjazd 08:00 | 64 | +0 |
| Łódź | 3 | do węzła, start > 12 km | Pabianice Łaska / Węglowa (przystanek lodz_pabianice:pabianice-laska-weglowa-bswrv) (19.33038, 51.66192) | Piotrkowska Centrum (węzeł z config.yaml) (19.45730, 51.75940) | 2026-11-25 08:05 | 46 | 46 | – | 43,1 min: WALK 6.2 min | RAIL Ł (Pabianice -> Łódź Kaliska) 15.0 min (czekanie 6.8 min) | WALK 5.1 min (czekanie 0.8 min) | TRAM 12 (Bandurskiego-Dw. Łódź Kaliska -> Piotrkowska Centrum) 6.0 min (czekanie 2.1 min) | WALK 1.1 min | Google Maps | 2026-11-24 | Ł + 8 | odjazd 08:16 | 49 | −6 |
| Łódź | 4 | styczna (przystanek–przystanek, 3–10 km od centrum) | Śmigłego Rydza-Zbiorcza (przystanek lodz:497) (19.48825, 51.75778) | Aleksandrowska-Szczecińska (przystanek lodz:1766) (19.36885, 51.80281) | 2026-11-25 08:20 | 47 | 46 | – | 42,5 min: WALK 0.9 min | TRAM 13 (Śmigłego Rydza-Zbiorcza -> Aleksandrowska-Szczecińska) 38.0 min (czekanie 2.1 min) | WALK 1.5 min | Google Maps | 2026-11-24 | 13 | odjazd 08:28 | 46 | +2 |
| GZM | 1 | do węzła, start 1,5–5 km od centrum | Dąb Kościół (przystanek gzm:481) (18.99413, 50.27155) | Katowice Rynek (węzeł z config.yaml) (19.02160, 50.25940) | 2026-11-25 07:35 | 21 | 17 | 33 | 16,3 min: WALK 3.2 min | TRAM T11 (Dąb Kościół -> Katowice Rynek) 10.0 min (czekanie 1.9 min) | WALK 1.2 min | Google Maps | 2026-11-24 | 11 | odjazd 07:41 | 21 | +0 |
| GZM | 2 | do węzła, start 5–12 km | Wirek Katowicka (przystanek gzm:3289) (18.88103, 50.27147) | Katowice Rynek (węzeł z config.yaml) (19.02160, 50.25940) | 2026-11-25 07:50 | 57 | 51 | – | 53,8 min: WALK 1.5 min | TRAM T9 (Wirek Katowicka -> Świętochłowice Mijanka) 14.0 min (czekanie 1.1 min) | WALK 6.5 min (czekanie 0.9 min) | BUS M24 (Świętochłowice Żołnierska -> Katowice Aleja Korfantego) 21.0 min (czekanie 5.6 min) | WALK 3.2 min | Google Maps | 2026-11-24 | 9 + M3 | odjazd 07:55 | 60 | −5 |
| GZM | 3 | do węzła, start > 12 km | Guido Przychodnia (przystanek gzm:8657) (18.78355, 50.28940) | Katowice Rynek (węzeł z config.yaml) (19.02160, 50.25940) | 2026-11-25 08:05 | 42 | 44 | – | 43,3 min: WALK 7.2 min | BUS 23 (Zabrze de Gaullea Ślęczka -> Zabrze Plac Dworcowy [tech]) 10.0 min (czekanie 1.1 min) | WALK 1.2 min (czekanie 1.1 min) | RAIL IC (Zabrze -> Katowice) 15.5 min (czekanie 1.1 min) | WALK 6.0 min | Google Maps | 2026-11-24 | M1 | odjazd 08:07 z przystanku Zabrze Rondo Sybiraków (66 m od startu); linia M1 jest w naszym feedzie z tym samym odjazdem – R5 nie zdąża na kurs 2 min po godzinie zapytania i jedzie autobusem 23 i pociągiem (42 min); mediana 7–9 (44 min) odpowiada jeździe M1 | 35 | +20 |
| GZM | 4 | styczna (przystanek–przystanek, 3–10 km od centrum) | Giszowiec Adama (przystanek gzm:10528) (19.07264, 50.21931) | Zgoda Wiśniowa (przystanek gzm:13008) (18.92566, 50.28292) | 2026-11-25 08:20 | 68 | 66 | – | 63,6 min: WALK 0.0 min | BUS 108 (Giszowiec Adama -> Nikiszowiec Szyb Pułaski) 7.0 min (czekanie 1.0 min) | BUS 674 (Nikiszowiec Szyb Pułaski -> Katowice Dworzec) 23.0 min (czekanie 2.0 min) | WALK 1.8 min (czekanie 1.1 min) | RAIL S1 (Katowice -> Świętochłowice) 9.5 min (czekanie 2.1 min) | WALK 16.1 min | Google Maps | 2026-11-24 | 920 + 672 + KŚ S1 | odjazd 08:22 | 66 | +3 |
| Wrocław | 1 | do węzła, start 1,5–5 km od centrum | Grabiszyńska (przystanek wroclaw:943) (17.01234, 51.10225) | Galeria Dominikańska (węzeł z config.yaml) (17.04030, 51.10830) | 2026-11-25 07:35 | 20 | 24 | 32 | 18,7 min: WALK 1.2 min | TRAM 11 (Grabiszyńska -> GALERIA DOMINIKAŃSKA 01) 12.0 min (czekanie 1.1 min) | WALK 4.4 min | Google Maps | 2026-11-24 | 5 | odjazd 07:35 (tramwaj odjeżdża w minucie zapytania; R5 potrzebuje 1 min dojścia i jedzie następnym kursem); druga opcja 07:38–07:52 linią 11 | 16 | +25 |
| Wrocław | 2 | do węzła, start 5–12 km | Ciechocińska (przystanek wroclaw:85) (16.88406, 51.15276) | Galeria Dominikańska (węzeł z config.yaml) (17.04030, 51.10830) | 2026-11-25 07:50 | 64 | 60 | – | 60,4 min: WALK 0.0 min | BUS 101 (Ciechocińska -> Stabłowicka) 6.0 min (czekanie 3.0 min) | WALK 2.5 min (czekanie 1.0 min) | RAIL D2 (Wrocław Pracze -> Wrocław Główny) 13.6 min (czekanie 12.9 min) | WALK 8.8 min (czekanie 0.7 min) | TRAM 5 (DWORZEC GŁÓWNY -> GALERIA DOMINIKAŃSKA 07) 5.0 min (czekanie 1.5 min) | WALK 5.3 min | Google Maps | 2026-11-24 | 923 + 10 albo 101 + 10 | odjazd 07:58 lub 07:59 | 62 | +3 |
| Wrocław | 3 | do węzła, start > 12 km | Morzęcin Wielki (przystanek wroclaw_oborniki:118-01) (16.89746, 51.32880) | Galeria Dominikańska (węzeł z config.yaml) (17.04030, 51.10830) | 2026-11-25 08:05 | 75 | – | – | 81,7 min: WALK 0.1 min | BUS Linia 3A (Morzęcin Wielki -> Oborniki Śląskie-Dworzec) 10.0 min (czekanie 1.1 min) | WALK 0.9 min (czekanie 1.1 min) | RAIL REG P (Oborniki Śląskie -> Wrocław Mikołajów) 13.5 min (czekanie 20.5 min) | WALK 4.9 min (czekanie 1.0 min) | TRAM 21 (Wrocław Mikołajów (Zachodnia) -> PL. JANA PAWŁA II 06) 5.0 min (czekanie 3.1 min) | WALK 20.6 min | Google Maps | 2026-11-24 |  | Google nie zwraca trasy komunikacją (linii gminnych Obornik Śląskich nie ma w danych Google) | brak trasy |  |
| Wrocław | 4 | styczna (przystanek–przystanek, 3–10 km od centrum) | Lutosławskiego (przystanek wroclaw:5706) (17.05494, 51.06220) | Hermanowska (przystanek wroclaw:197) (16.95584, 51.12233) | 2026-11-25 08:20 | 56 | 54 | – | 55,9 min: WALK 0.0 min | BUS 148 (Lutosławskiego -> Wrocław Nowy Dwór (P+R)) 44.0 min (czekanie 3.0 min) | WALK 8.8 min | Google Maps | 2026-11-24 | 145 + 136 | odjazd 08:22; opcja 148 + 122 przyjazd 09:18 | 57 | −2 |
| Wrocław | 5 | para z r5_benchmark (plan.md 4.2) | Kozanów (przy przystanku KOZANÓW Dokerska) (16.96400, 51.14200) | Rynek (17.03200, 51.11000) | 2026-11-25 08:35 | 33 | 35 | 81 | 30,9 min: WALK 1.5 min | TRAM 12 (KOZANÓW (Dokerska) -> Zamkowa) 23.0 min (czekanie 1.1 min) | WALK 5.3 min | Google Maps | 2026-11-24 | 12 | odjazd 08:38 | 34 | −3 |
| Wrocław | 6 | para z r5_benchmark (plan.md 4.2) | Jagodno (przy JAGODNO P+R) (17.06000, 51.05450) | pl. Grunwaldzki (17.06360, 51.11180) | 2026-11-25 07:40 | 43 | 44 | 93 | 41,8 min: WALK 8.6 min | RAIL D3 (Iwiny -> Wrocław Główny) 5.4 min (czekanie 1.1 min) | WALK 8.8 min (czekanie 0.8 min) | BUS 146 (DWORZEC GŁÓWNY (Dworcowa) -> PL. GRUNWALDZKI) 9.0 min (czekanie 4.4 min) | WALK 3.7 min | Google Maps | 2026-11-24 | 110 + 16 | odjazd 07:43; Google nie pokazuje wariantu pociągiem D3 z Iwin | 48 | −10 |
| Wrocław | 7 | para z r5_benchmark (plan.md 4.2) | Siechnice, stacja (17.15300, 51.03500) | Wrocław Główny (17.03650, 51.09830) | 2026-11-25 08:10 | 71 | 47 | – | 61,6 min: WALK 33.9 min | RAIL D5 (Święta Katarzyna -> Wrocław Główny) 10.0 min (czekanie 12.2 min) | WALK 5.5 min | Google Maps | 2026-11-24 | 800 + 80 | odjazd 08:16; pociąg D7 08:52–09:20 | 63 | +13 |
| Poznań | 1 | do węzła, start 1,5–5 km od centrum | Malinowa (przystanek poznan:3674) (16.91099, 52.36959) | Rondo Kaponiera (węzeł z config.yaml) (16.91260, 52.40810) | 2026-11-25 07:35 | 26 | 29 | 63 | 25,8 min: WALK 9.4 min | RAIL PKM3 (Poznań Dębiec -> Poznań Główny) 5.1 min (czekanie 1.0 min) | WALK 10.3 min | Google Maps | 2026-11-24 | 603 + 6 | odjazd 07:36; Google nie pokazuje wariantu pociągiem PKM3 z Poznania Dębca (R5: 26 min) | 32 | −19 |
| Poznań | 2 | do węzła, start 5–12 km | Przeźmierowo/Kościelna (przystanek poznan:1939) (16.78506, 52.42686) | Rondo Kaponiera (węzeł z config.yaml) (16.91260, 52.40810) | 2026-11-25 07:50 | 41 | 48 | – | 41,2 min: WALK 2.3 min | BUS 822 (Przeźmierowo/Kościelna -> Ogrody) 21.0 min (czekanie 1.1 min) | WALK 2.2 min (czekanie 0.9 min) | TRAM 18 (Ogrody -> Rondo Kaponiera) 10.0 min (czekanie 1.9 min) | WALK 1.8 min | Google Maps | 2026-11-24 | 822 + 9 | odjazd 07:52 | 43 | −5 |
| Poznań | 3 | do węzła, start > 12 km | Chyby/Szkolna (przystanek poznan:4421) (16.76735, 52.45692) | Rondo Kaponiera (węzeł z config.yaml) (16.91260, 52.40810) | 2026-11-25 08:05 | 75 | 59 | – | 85,0 min: WALK 20.9 min | BUS 822 (Baranowo/Uniwersytet Przyrodniczy -> Ogrody) 28.0 min (czekanie 5.1 min) | WALK 2.2 min (czekanie 0.9 min) | TRAM 8 (Ogrody -> Żeromskiego) 2.0 min (czekanie 1.9 min) | WALK 24.0 min | Google Maps | 2026-11-24 | 822 + 9 | odjazd 08:33; opcja 822 + 8 przyjazd 09:25 | 79 | −5 |
| Poznań | 4 | styczna (przystanek–przystanek, 3–10 km od centrum) | Unii Lubelskiej (przystanek poznan:3889) (16.94982, 52.37204) | Piękna (przystanek poznan:3809) (16.87618, 52.41765) | 2026-11-25 08:20 | 47 | 45 | 108 | 43,7 min: WALK 8.7 min | TRAM 97 (Rondo Żegrze -> Rondo Starołęka) 2.0 min (czekanie 1.4 min) | WALK 2.7 min (czekanie 0.9 min) | TRAM 7 (Rondo Starołęka -> Ogrody) 20.0 min (czekanie 1.3 min) | WALK 6.6 min | Google Maps | 2026-11-24 | 11 + 7 | odjazd 08:24 | 48 | −2 |
| Trójmiasto | 1 | do węzła, start 1,5–5 km od centrum | Rejenta 01 (przystanek gdansk:1113) (18.60550, 54.34235) | Gdańsk Główny (węzeł z config.yaml) (18.64400, 54.35560) | 2026-11-25 07:35 | 27 | 27 | 43 | 25,1 min: WALK 13.6 min | TRAM 11 (Chałubińskiego 01 -> Dworzec PKS 01) 9.0 min (czekanie 1.0 min) | WALK 1.6 min | Google Maps | 2026-11-24 | 11 | odjazd 07:37 | 29 | −7 |
| Trójmiasto | 2 | do węzła, start 5–12 km | Karczemki Szkoła 01 (przystanek gdansk:1561) (18.51074, 54.35249) | Gdańsk Główny (węzeł z config.yaml) (18.64400, 54.35560) | 2026-11-25 07:50 | 56 | 55 | – | 52,9 min: WALK 0.0 min | BUS 268 (Karczemki Szkoła 01 -> Szczęśliwa 01) 7.0 min (czekanie 1.0 min) | BUS 168 (Szczęśliwa 01 -> Emaus 01) 20.0 min (czekanie 3.0 min) | WALK 3.0 min (czekanie 1.0 min) | TRAM 10 (Siedlce 01 -> Dworzec Główny 01) 11.0 min (czekanie 4.0 min) | WALK 2.8 min | Google Maps | 2026-11-24 | 120 + 810 | odjazd 08:01 | 57 | −2 |
| Trójmiasto | 3 | do węzła, start > 12 km | Janowo SKM - Sobieskiego 06 (przystanek gdynia:40362) (18.40610, 54.55692) | Gdańsk Główny (węzeł z config.yaml) (18.64400, 54.35560) | 2026-11-25 08:05 | 68 | 61 | – | 72,5 min: WALK 5.7 min | RAIL S1 (Rumia Janowo -> Gdańsk Stocznia) 47.7 min (czekanie 5.9 min) | WALK 13.2 min | Google Maps | 2026-11-24 | 173 + S1 | odjazd 08:19; R5 (68 min) jedzie S1 z Rumi Janowa do Gdańska Stoczni i dochodzi pieszo; przyczyna różnicy niesprawdzona | 80 | −15 |
| Trójmiasto | 4 | styczna (przystanek–przystanek, 3–10 km od centrum) | Wrzeszcz PKP 01 (przystanek gdansk:314) (18.60508, 54.38132) | Kolorowa 01 (przystanek gdansk:14721) (18.60241, 54.31174) | 2026-11-25 08:20 | 52 | 43 | 110 | 46,4 min: WALK 1.1 min | BUS 162 (Wrzeszcz PKP 04 -> Łostowice Świętokrzyska 06) 25.0 min (czekanie 1.0 min) | WALK 19.2 min | Google Maps | 2026-11-24 | SKM + 289 | odjazd 08:40; tramwaj 6 + 289 odjazd 08:22 z tym samym przyjazdem | 52 | +0 |

## 10. Czas liczenia

| Aglomeracja | Jednostka | Starty / wiersze | Czas routingu, s | ms / start | Szacunek z benchmarku, s | Zmierzony / szacunek |
|---|---|---:|---|---|---|---|
| Trójmiasto | all/odpairs | 4 | 57,6 |  |  |  |
| Trójmiasto | all/pt_am | 17561 | 47,4 | 2,70 | 77,5 | 0,61 |
| Trójmiasto | all/pt_am_max3rides | 17561 | 46,6 | 2,65 | 72,2 | 0,64 |
| Trójmiasto | all/pt_evening | 17561 | 46,4 | 2,64 | 78,9 | 0,59 |
| Trójmiasto | all/pt_midday | 17561 | 65,3 | 3,72 | 114,7 | 0,57 |
| Trójmiasto | all/pt_saturday | 17561 | 62,6 | 3,57 | 112,0 | 0,56 |
| Trójmiasto | all/transfers_am | 200 | 1230,3 |  |  |  |
| Trójmiasto | official/pt_am | 17561 | 47,7 | 2,71 | 77,5 | 0,61 |
| Trójmiasto | official/pt_evening | 17561 | 47,9 | 2,73 | 78,9 | 0,61 |
| Trójmiasto | official/pt_midday | 17561 | 69,5 | 3,96 | 114,7 | 0,61 |
| Trójmiasto | official/pt_saturday | 17561 | 64,8 | 3,69 | 112,0 | 0,58 |
| Trójmiasto | street/bike_lts3 | 17561 | 138,5 | 7,89 | 116,3 | 1,19 |
| Trójmiasto | street/bike_lts4 | 17561 | 250,5 | 14,26 | 139,6 | 1,79 |
| Trójmiasto | street/walk | 17561 | 31,5 | 1,79 | 26,0 | 1,21 |
| Poznań | all/odpairs | 4 | 47,4 |  |  |  |
| Poznań | all/pt_am | 19201 | 77,4 | 4,03 | 112,3 | 0,69 |
| Poznań | all/pt_am_max3rides | 19201 | 77,5 | 4,03 | 116,0 | 0,67 |
| Poznań | all/pt_evening | 19201 | 75,7 | 3,94 | 119,4 | 0,63 |
| Poznań | all/pt_midday | 19201 | 103,9 | 5,41 | 152,0 | 0,68 |
| Poznań | all/pt_saturday | 19201 | 101,2 | 5,27 | 148,1 | 0,68 |
| Poznań | all/transfers_am | 200 | 1035,4 |  |  |  |
| Poznań | official/pt_am | 19201 | 77,4 | 4,03 | 112,3 | 0,69 |
| Poznań | official/pt_evening | 19201 | 77,4 | 4,03 | 119,4 | 0,65 |
| Poznań | official/pt_midday | 19201 | 106,8 | 5,56 | 152,0 | 0,70 |
| Poznań | official/pt_saturday | 19201 | 102,5 | 5,34 | 148,1 | 0,69 |
| Poznań | street/bike_lts3 | 19201 | 184,2 | 9,59 | 139,7 | 1,32 |
| Poznań | street/bike_lts4 | 19201 | 265,6 | 13,83 | 167,6 | 1,58 |
| Poznań | street/walk | 19201 | 32,4 | 1,69 | 49,0 | 0,66 |
| Wrocław | all/odpairs | 7 | 98,2 |  |  |  |
| Wrocław | all/pt_am | 20153 | 68,1 | 3,38 | 102,6 | 0,66 |
| Wrocław | all/pt_am_max3rides | 20153 | 59,1 | 2,93 | 91,4 | 0,65 |
| Wrocław | all/pt_evening | 20153 | 65,4 | 3,24 | 98,7 | 0,66 |
| Wrocław | all/pt_midday | 20153 | 92,7 | 4,60 | 148,8 | 0,62 |
| Wrocław | all/pt_saturday | 20153 | 88,5 | 4,39 | 140,0 | 0,63 |
| Wrocław | all/transfers_am | 200 | 1188,0 |  |  |  |
| Wrocław | official/pt_am | 20153 | 50,8 | 2,52 | 102,6 | 0,50 |
| Wrocław | official/pt_evening | 20153 | 49,6 | 2,46 | 98,7 | 0,50 |
| Wrocław | official/pt_midday | 20153 | 68,6 | 3,40 | 148,8 | 0,46 |
| Wrocław | official/pt_saturday | 20153 | 65,5 | 3,25 | 140,0 | 0,47 |
| Wrocław | street/bike_lts3 | 20153 | 192,3 | 9,54 | 158,1 | 1,22 |
| Wrocław | street/bike_lts4 | 20153 | 308,4 | 15,31 | 189,7 | 1,63 |
| Wrocław | street/walk | 20153 | 37,2 | 1,85 | 31,1 | 1,20 |
| GZM | all/odpairs | 4 | 58,9 |  |  |  |
| GZM | all/pt_am | 24869 | 223,1 | 8,97 | 380,5 | 0,59 |
| GZM | all/pt_am_max3rides | 24869 | 215,8 | 8,68 | 288,3 | 0,75 |
| GZM | all/pt_evening | 24869 | 230,6 | 9,27 | 343,0 | 0,67 |
| GZM | all/pt_midday | 24869 | 369,1 | 14,84 | 498,2 | 0,74 |
| GZM | all/pt_saturday | 24869 | 348,8 | 14,03 | 490,0 | 0,71 |
| GZM | all/transfers_am | 200 | 1176,2 |  |  |  |
| GZM | official/pt_am | 24869 | 246,0 | 9,89 | 380,5 | 0,65 |
| GZM | official/pt_evening | 24869 | 325,8 | 13,10 | 343,0 | 0,95 |
| GZM | official/pt_midday | 24869 | 381,8 | 15,35 | 498,2 | 0,77 |
| GZM | official/pt_saturday | 24869 | 487,5 | 19,60 | 490,0 | 0,99 |
| GZM | street/bike_lts3 | 24869 | 283,2 | 11,39 | 231,7 | 1,22 |
| GZM | street/bike_lts4 | 24869 | 532,3 | 21,40 | 278,0 | 1,91 |
| GZM | street/walk | 24869 | 59,1 | 2,38 | 71,1 | 0,83 |
| Łódź | all/odpairs | 4 | 56,7 |  |  |  |
| Łódź | all/pt_am | 26274 | 111,0 | 4,22 | 177,5 | 0,63 |
| Łódź | all/pt_am_max3rides | 26274 | 112,0 | 4,26 | 157,2 | 0,71 |
| Łódź | all/pt_evening | 26274 | 109,3 | 4,16 | 180,8 | 0,60 |
| Łódź | all/pt_midday | 26274 | 148,5 | 5,65 | 221,8 | 0,67 |
| Łódź | all/pt_saturday | 26274 | 144,9 | 5,52 | 211,7 | 0,68 |
| Łódź | all/transfers_am | 200 | 1303,8 |  |  |  |
| Łódź | official/pt_am | 26274 | 61,3 | 2,33 | 177,5 | 0,35 |
| Łódź | official/pt_evening | 26274 | 89,0 | 3,39 | 180,8 | 0,49 |
| Łódź | official/pt_midday | 26274 | 110,9 | 4,22 | 221,8 | 0,50 |
| Łódź | official/pt_saturday | 26274 | 111,0 | 4,22 | 211,7 | 0,52 |
| Łódź | street/bike_lts3 | 26274 | 235,0 | 8,94 | 170,5 | 1,38 |
| Łódź | street/bike_lts4 | 26274 | 380,9 | 14,50 | 204,6 | 1,86 |
| Łódź | street/walk | 26274 | 48,1 | 1,83 | 59,5 | 0,81 |
| Kraków | all/odpairs | 4 | 55,9 |  |  |  |
| Kraków | all/pt_am | 37817 | 255,9 | 6,77 | 482,5 | 0,53 |
| Kraków | all/pt_am_max3rides | 37817 | 278,8 | 7,37 | 392,0 | 0,71 |
| Kraków | all/pt_evening | 37817 | 263,0 | 6,95 | 516,9 | 0,51 |
| Kraków | all/pt_midday | 37817 | 390,4 | 10,32 | 700,7 | 0,56 |
| Kraków | all/pt_saturday | 37817 | 385,9 | 10,20 | 586,3 | 0,66 |
| Kraków | all/transfers_am | 200 | 1207,1 |  |  |  |
| Kraków | official/pt_am | 37817 | 249,2 | 6,59 | 482,5 | 0,52 |
| Kraków | official/pt_evening | 37817 | 348,0 | 9,20 | 516,9 | 0,67 |
| Kraków | official/pt_midday | 37817 | 538,1 | 14,23 | 700,7 | 0,77 |
| Kraków | official/pt_saturday | 37817 | 463,4 | 12,25 | 586,3 | 0,79 |
| Kraków | street/bike_lts3 | 37817 | 302,5 | 8,00 | 273,0 | 1,11 |
| Kraków | street/bike_lts4 | 37817 | 425,7 | 11,26 | 327,6 | 1,30 |
| Kraków | street/walk | 37817 | 83,2 | 2,20 | 138,0 | 0,60 |
| Warszawa | all/odpairs | 4 | 59,2 |  |  |  |
| Warszawa | all/pt_am | 88926 | 987,3 | 11,10 | 2003,5 | 0,49 |
| Warszawa | all/pt_am_max3rides | 88926 | 995,3 | 11,19 | 1638,6 | 0,61 |
| Warszawa | all/pt_evening | 88926 | 1023,6 | 11,51 | 1981,7 | 0,52 |
| Warszawa | all/pt_midday | 88926 | 1589,8 | 17,88 | 2757,6 | 0,58 |
| Warszawa | all/pt_saturday | 88926 | 1491,3 | 16,77 | 2537,1 | 0,59 |
| Warszawa | all/transfers_am | 200 | 1248,9 |  |  |  |
| Warszawa | official/pt_am | 88926 | 603,9 | 6,79 | 2003,5 | 0,30 |
| Warszawa | official/pt_evening | 88926 | 632,0 | 7,11 | 1981,7 | 0,32 |
| Warszawa | official/pt_midday | 88926 | 1015,9 | 11,42 | 2757,6 | 0,37 |
| Warszawa | official/pt_saturday | 88926 | 760,3 | 8,55 | 2537,1 | 0,30 |
| Warszawa | street/bike_lts3 | 88926 | 1005,3 | 11,30 | 1289,1 | 0,78 |
| Warszawa | street/bike_lts4 | 88926 | 1337,6 | 15,04 | 1546,9 | 0,86 |
| Warszawa | street/walk | 88926 | 294,1 | 3,31 | 545,3 | 0,54 |

Wrocław, wszystkie 14 jednostek: ok. 40 min routingu, z czego 20 min to próba przesiadek (200 par) i 1,6 min pary OD; same przebiegi regionalne 19 min wobec 20 min z kosztorysu `plan.md` (0,34 h bez sieci wspólnego biletu). Komunikacja wyszła 0,5–0,66 × szacunku z benchmarku (czasy pieszo są liczone raz i używane ponownie), pieszo do 60 min 1,2 ×, rower do 60 min 1,2 × (LTS 3) i 1,6 × (LTS 4) szacunku z przelicznikiem 3,0 / 3,6. `python -m pipeline.access status` przelicza resztę z tych współczynników; dla Warszawy niepewność jest największa.

## 11. Co zaskoczyło i co wyszło przy sprawdzaniu

Stan na 2026-11-24, po pełnym przebiegu (98 z 98 jednostek, 11 h 20 min routingu). Liczby dotyczą rdzeni miast, wszystkich feedów i siatki spisowej, o ile nie napisano inaczej.

- **GZM wyraźnie najniżej.** KZ 45 min: 36,1 wobec 51–59 w pozostałych miastach. Sprawdzono z wynikami fazy 2: GZM ma też najmniejszy udział mieszkańców rdzenia przy kursach co 10 min lub częściej (45,6 % wobec 59–80 %) i najbardziej rozproszoną ludność. W granicach urban centre (ta sama reguła obszaru dla każdego miasta, `qa/access_uc/access_uc.md`) GZM pozostaje ostatnie: 43,2 wobec 62–67 (stosunek średnich). Wynik zostaje.
- **Wrocław: wieczór lepszy niż szczyt poranny przy 45 min** (54,7 wobec 53,0); to jedyne takie miasto. Sprawdzono z rozkładami: rozkładowa prędkość komunikacyjna tramwajów we Wrocławiu to 16,1 km/h w szczytach i 18,0 km/h po 20:00, największa różnica z siedmiu miast (w pozostałych 0,1–1,3 km/h). Wynik zostaje.
- **Duże spadki poza szczytem.** Trójmiasto wieczorem przy 45 min: 55,4 → 46,3 (−9,1 pkt); GZM wieczorem −6,4 i w sobotę −7,3 pkt. W pozostałych miastach okna różnią się od szczytu porannego o najwyżej 6 pkt; sobota jest wszędzie najsłabsza albo druga od końca. Przyczyn spadków w Trójmieście i GZM nie sprawdzano.
- **Siatka ludności zmienia wynik bardziej niż oczekiwano.** Surowy GHSL obniża wynik rdzenia o 3–7 pkt w Krakowie, Poznaniu i Łodzi (Poznań, 45 min: 54,6 → 47,9; Łódź: 51,3 → 46,3; Kraków, 30 min: 31,6 → 28,0), a w Warszawie i Wrocławiu prawie go nie zmienia (do 0,8 pkt). To więcej niż różnice między miastami ze środka tabeli, więc ich kolejność zależy od wyboru siatki. Na próbie Wrocławia z 2026-11-23 tej wrażliwości nie było widać.
- **Limit przesiadek prawie nic nie zmienia.** Maksymalnie 2 przesiadki zamiast braku limitu: do 0,14 pkt (Warszawa, 45 min). Zgodne z próbą tras: mediana liczby przesiadek to 0 albo 1, a trzy i więcej przejazdów ma 1,5–10 % par.
- **Feedy nieoficjalne w rdzeniach prawie nic nie zmieniają.** Różnica między siecią ze wszystkimi feedami a samymi oficjalnymi: do 0,5 pkt (Łódź, 45 min); w Poznaniu, Trójmieście i GZM zero, bo listy feedów są tam takie same. Feedy nieoficjalne mają znaczenie dla stref podmiejskich i dla zasięgu maski pokrycia.
- **Reguła min(komunikacja, pieszo)** podnosi wynik rdzenia o 0,1–0,9 pkt (najwięcej w GZM przy 30 min).
- **Kontrola „wszystkie feedy ≥ oficjalne” nie przechodzi w sześciu miastach** (tabela w §8). W Warszawie dotyczy 730 z 88 926 komórek przy którymkolwiek progu; przy 30 min to 72 komórki, a mediana straty wynosi 0,17 %. Wynik główny rdzenia różni się między sieciami o 0,03 pkt. Przyczyny nie ustalono.
- **Porównanie z wyszukiwarką (§9).** 28 z 30 porównywalnych par mieści się w ±20 %. Dwa wyjątki to krótkie podróże (Łódź 16 wobec 11 min, Wrocław 20 wobec 16 min), w których tramwaj odjeżdża w minucie zapytania, a R5 jedzie następnym kursem. W GZM wyszukiwarka wybrała linię M1 tam, gdzie R5 pojechał autobusem i pociągiem: linia M1 jest w feedzie z tym samym odjazdem, R5 nie zdążył na kurs dwie minuty po godzinie zapytania. Dla jednej pary pod Wrocławiem (Morzęcin Wielki) wyszukiwarka nie zna linii gminnych, które są w naszym feedzie.
- **DG REGIO (§7).** Różnica 45-minutowa dla Poznania i Łodzi wynika głównie z innego obszaru (urban centre 2011), nie z braków w feedach; po odtworzeniu obszaru i metody zostaje reszta +4,5 pkt (Poznań) i +11,0 pkt (Łódź), której nie wyjaśniono. Pełny opis: `qa/access/dgregio/dgregio.md`.
- **Miejsca pracy.** Wskaźnik dla miejsc pracy liczony jest jako stosunek średnich, bo w komórkach z małą liczbą miejsc pracy w pobliżu stosunki pojedynczych komórek są niestabilne. Zbiór nie obejmuje GZM (brak danych, nie zero).
- **Próba tras.** `DetailedItineraries` przy oknie 1 min wyczerpywał pamięć R5, więc trasy w próbie liczono dla losowego 5-minutowego okna odjazdów; liczby przesiadek dotyczą najszybszej trasy w tym oknie.


## 12. Pliki

- `results/metrics/metrics_access.csv` / `.json` (kolumny jak w innych krokach; JSON ma też `status` jednostek), scalane przez `pipeline.merge_metrics`.
- `results/charts/access_performance.json`: per miasto KZ 30/45, pieszo, rower (oba LTS), krzywe 5–60 min, benchmark DG REGIO z różnicami metod.
- `results/layers/access_cells.parquet` (7.33 MB): punkty środków komórek 250 m (EPSG:4326; komórka = kwadrat 250 m w EPSG:2180, `cell_id` = lewy dolny róg), performance KZ 30/45 (null poza maską i dla jednostek oczekujących), pieszo 30, rower 30 LTS 3 i 4.
- PNG: [`map_warszawa.png`](map_warszawa.png), [`map_krakow.png`](map_krakow.png), [`map_lodz.png`](map_lodz.png), [`map_gzm.png`](map_gzm.png), [`map_wroclaw.png`](map_wroclaw.png), [`map_poznan.png`](map_poznan.png), [`map_trojmiasto.png`](map_trojmiasto.png), [`curves.png`](curves.png).
- Dane pośrednie (poza gitem): `data/interim/access/<aglomeracja>/<sieć>/<scenariusz>/chunk_*.parquet`, log `data/interim/access/run.log`.

## 13. Stan jednostek

| Aglomeracja | Priorytet | Sieć | Scenariusz | Paczki gotowe | Paczki | Stan |
|---|---:|---|---|---:|---:|---|
| warszawa | 1 | street | walk | 89 | 89 | done |
| warszawa | 1 | all | pt_am | 89 | 89 | done |
| warszawa | 1 | street | bike_lts3 | 89 | 89 | done |
| warszawa | 1 | street | bike_lts4 | 89 | 89 | done |
| warszawa | 1 | all | transfers_am | 1 | 1 | done |
| warszawa | 1 | all | odpairs | 1 | 1 | done |
| warszawa | 2 | official | pt_am | 89 | 89 | done |
| warszawa | 3 | all | pt_midday | 89 | 89 | done |
| warszawa | 3 | all | pt_evening | 89 | 89 | done |
| warszawa | 3 | all | pt_saturday | 89 | 89 | done |
| warszawa | 4 | all | pt_am_max3rides | 89 | 89 | done |
| warszawa | 5 | official | pt_midday | 89 | 89 | done |
| warszawa | 5 | official | pt_evening | 89 | 89 | done |
| warszawa | 5 | official | pt_saturday | 89 | 89 | done |
| krakow | 1 | street | walk | 38 | 38 | done |
| krakow | 1 | all | pt_am | 38 | 38 | done |
| krakow | 1 | street | bike_lts3 | 38 | 38 | done |
| krakow | 1 | street | bike_lts4 | 38 | 38 | done |
| krakow | 1 | all | transfers_am | 1 | 1 | done |
| krakow | 1 | all | odpairs | 1 | 1 | done |
| krakow | 2 | official | pt_am | 38 | 38 | done |
| krakow | 3 | all | pt_midday | 38 | 38 | done |
| krakow | 3 | all | pt_evening | 38 | 38 | done |
| krakow | 3 | all | pt_saturday | 38 | 38 | done |
| krakow | 4 | all | pt_am_max3rides | 38 | 38 | done |
| krakow | 5 | official | pt_midday | 38 | 38 | done |
| krakow | 5 | official | pt_evening | 38 | 38 | done |
| krakow | 5 | official | pt_saturday | 38 | 38 | done |
| wroclaw | 1 | street | walk | 21 | 21 | done |
| wroclaw | 1 | all | pt_am | 21 | 21 | done |
| wroclaw | 1 | street | bike_lts3 | 21 | 21 | done |
| wroclaw | 1 | street | bike_lts4 | 21 | 21 | done |
| wroclaw | 1 | all | transfers_am | 1 | 1 | done |
| wroclaw | 1 | all | odpairs | 1 | 1 | done |
| wroclaw | 2 | official | pt_am | 21 | 21 | done |
| wroclaw | 3 | all | pt_midday | 21 | 21 | done |
| wroclaw | 3 | all | pt_evening | 21 | 21 | done |
| wroclaw | 3 | all | pt_saturday | 21 | 21 | done |
| wroclaw | 4 | all | pt_am_max3rides | 21 | 21 | done |
| wroclaw | 5 | official | pt_midday | 21 | 21 | done |
| wroclaw | 5 | official | pt_evening | 21 | 21 | done |
| wroclaw | 5 | official | pt_saturday | 21 | 21 | done |
| poznan | 1 | street | walk | 20 | 20 | done |
| poznan | 1 | all | pt_am | 20 | 20 | done |
| poznan | 1 | street | bike_lts3 | 20 | 20 | done |
| poznan | 1 | street | bike_lts4 | 20 | 20 | done |
| poznan | 1 | all | transfers_am | 1 | 1 | done |
| poznan | 1 | all | odpairs | 1 | 1 | done |
| poznan | 2 | official | pt_am | 20 | 20 | done |
| poznan | 3 | all | pt_midday | 20 | 20 | done |
| poznan | 3 | all | pt_evening | 20 | 20 | done |
| poznan | 3 | all | pt_saturday | 20 | 20 | done |
| poznan | 4 | all | pt_am_max3rides | 20 | 20 | done |
| poznan | 5 | official | pt_midday | 20 | 20 | done |
| poznan | 5 | official | pt_evening | 20 | 20 | done |
| poznan | 5 | official | pt_saturday | 20 | 20 | done |
| lodz | 1 | street | walk | 27 | 27 | done |
| lodz | 1 | all | pt_am | 27 | 27 | done |
| lodz | 1 | street | bike_lts3 | 27 | 27 | done |
| lodz | 1 | street | bike_lts4 | 27 | 27 | done |
| lodz | 1 | all | transfers_am | 1 | 1 | done |
| lodz | 1 | all | odpairs | 1 | 1 | done |
| lodz | 2 | official | pt_am | 27 | 27 | done |
| lodz | 3 | all | pt_midday | 27 | 27 | done |
| lodz | 3 | all | pt_evening | 27 | 27 | done |
| lodz | 3 | all | pt_saturday | 27 | 27 | done |
| lodz | 4 | all | pt_am_max3rides | 27 | 27 | done |
| lodz | 5 | official | pt_midday | 27 | 27 | done |
| lodz | 5 | official | pt_evening | 27 | 27 | done |
| lodz | 5 | official | pt_saturday | 27 | 27 | done |
| trojmiasto | 1 | street | walk | 18 | 18 | done |
| trojmiasto | 1 | all | pt_am | 18 | 18 | done |
| trojmiasto | 1 | street | bike_lts3 | 18 | 18 | done |
| trojmiasto | 1 | street | bike_lts4 | 18 | 18 | done |
| trojmiasto | 1 | all | transfers_am | 1 | 1 | done |
| trojmiasto | 1 | all | odpairs | 1 | 1 | done |
| trojmiasto | 2 | official | pt_am | 18 | 18 | done |
| trojmiasto | 3 | all | pt_midday | 18 | 18 | done |
| trojmiasto | 3 | all | pt_evening | 18 | 18 | done |
| trojmiasto | 3 | all | pt_saturday | 18 | 18 | done |
| trojmiasto | 4 | all | pt_am_max3rides | 18 | 18 | done |
| trojmiasto | 5 | official | pt_midday | 18 | 18 | done |
| trojmiasto | 5 | official | pt_evening | 18 | 18 | done |
| trojmiasto | 5 | official | pt_saturday | 18 | 18 | done |
| gzm | 1 | street | walk | 25 | 25 | done |
| gzm | 1 | all | pt_am | 25 | 25 | done |
| gzm | 1 | street | bike_lts3 | 25 | 25 | done |
| gzm | 1 | street | bike_lts4 | 25 | 25 | done |
| gzm | 1 | all | transfers_am | 1 | 1 | done |
| gzm | 1 | all | odpairs | 1 | 1 | done |
| gzm | 2 | official | pt_am | 25 | 25 | done |
| gzm | 3 | all | pt_midday | 25 | 25 | done |
| gzm | 3 | all | pt_evening | 25 | 25 | done |
| gzm | 3 | all | pt_saturday | 25 | 25 | done |
| gzm | 4 | all | pt_am_max3rides | 25 | 25 | done |
| gzm | 5 | official | pt_midday | 25 | 25 | done |
| gzm | 5 | official | pt_evening | 25 | 25 | done |
| gzm | 5 | official | pt_saturday | 25 | 25 | done |
