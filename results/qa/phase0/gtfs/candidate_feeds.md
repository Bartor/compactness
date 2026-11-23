# Kandydaci na dodatkowe feedy GTFS (faza 0)

Stan na 2026-11-23: **dziennik decyzji**. W sekcji A żaden feed nie wszedł do `config.yaml` (kolej jest w `polish_trains`); w sekcji B dodano 30 feedów autobusowych (B.1), odrzucono 15 (B.2), a dla pozostałych przewoźników nie znaleziono feedu (B.3). Wcześniej do konfiguracji trafił tylko `krakow_mobilis` (oficjalny, trzeci feed ZTP Kraków: 33 trasy podmiejskie, CC BY 4.0).
Kolumna „Sprawdzono” w sekcji A = odpowiedź serwera 2026-11-23 (HTTP 200 i data modyfikacji; zawartości nie analizowano). Decyzje dla kolei: status w ostatnim zdaniu tej sekcji.
Źródła zestawienia: katalog `public-transport/transitous` (`feeds/pl.json`), Transitland Atlas (`feeds/*.dmfr.json`), strony wydawców. Licencje poniżej to te z katalogów (transitous/atlas); dla agregatorów typu `zbiorkom.live` i `files.girlc.at` oznaczają licencję **powtórnej publikacji**, a nie warunki pierwotnego organizatora, więc przed użyciem trzeba je sprawdzić.

## A. Kolej regionalna: własne feedy przewoźników

`polish_trains.zip` (PKP PLK, przepakowany przez mkuran.pl) **zawiera już**: Koleje Mazowieckie (KM), SKM Warszawa, SKM Trójmiasto, Koleje Śląskie (KŚ), Koleje Dolnośląskie (KD), Koleje Małopolskie (KMŁ), Koleje Wielkopolskie (KW; linie PKM1–PKM5 = Poznańska Kolej Metropolitalna), Łódzka Kolej Aglomeracyjna (ŁKA), PolRegio, PKP Intercity, Arriva RP, RegioJet, Leo Express. **Nie zawiera**: WKD (jest w `warsaw_wkd`). PKM Trójmiasto (Pomorska Kolej Metropolitalna) to w feedzie linie PolRegio `PR_PM_*`, kursujące dopiero od 13.12.2026 (zmiana rozkładu). Własne feedy przewoźników mają sens tylko tam, gdzie są dokładniejsze (przystanki, kształty) albo zawierają autobusy tych przewoźników.

| Przewoźnik | URL | Co obejmuje | W `polish_trains`? | Licencja (katalog) | Sprawdzono |
|---|---|---|---|---|---|
| SKM Trójmiasto | https://www.skm.pkp.pl/gtfs-mi-kpd.zip | SKM Gdańsk–Gdynia–Wejherowo i regionalne w Pomorskiem | tak (agencja `SKMT`) | CC BY 4.0 (https://bip.skm.pkp.pl/otwarte-dane) | 200, 15 MB, mod. 2026-11-22 |
| Koleje Śląskie | https://koleje-ks.pl/gtfs/2025-2026.zip | cała siatka KŚ (GZM, Rybnik, Bielsko) | tak (`KS`) | CC0 | 200, 2,5 MB, mod. 2026-11-06 |
| Koleje Małopolskie (kolej) | https://kolejemalopolskie.com.pl/rozklady_jazdy/kml-ska-gtfs.zip | SKA Kraków i regionalne | tak (`KML`) | CC BY 4.0 (dane.gov.pl, zbiór 3083) | 200, 0,4 MB, mod. 2026-11-20 |
| Koleje Małopolskie, linie ALD | https://kolejemalopolskie.com.pl/rozklady_jazdy/ald-gtfs.zip | autobusowe linie dowozowe do SKA (komunikacja podmiejska) | **nie** (w `polish_trains` tylko kolej i ZKA) | CC BY 4.0 | 200, 0,9 MB, mod. 2026-11-23 |
| Koleje Dolnośląskie | https://kd.kiedyprzyjedzie.pl/gtfs/kd_transitland/google_transit.zip | KD, aglomeracja wrocławska | tak (`KD`) | CC0 | **HTTP 401** (wymaga autoryzacji/przeglądarki; do pobrania ręcznie) |
| Koleje Wielkopolskie (w tym PKM Poznań) | http://ws.kolejewlkp.pl:83/gtfs_kw.zip | KW, PKM Poznań | tak (`KW`) | warunki BIP KW (nie CC) | 200, 0,6 MB, mod. 2026-11-23; HTTP bez TLS |
| Łódzka Kolej Aglomeracyjna | https://kolej-lka.pl/pliki/pn0e6eg45qcl4hd5/gtfs-2025-2026/zip/ | ŁKA | tak (`LKA`) | CC0 | 200, 0,5 MB, mod. 2026-11-03 (URL zawiera rok rozkładu: zmieni się) |
| ŁKA, autobusy zastępcze/dowozowe | https://gtfs.kasznia.net/static/sanitized/lka_bus.zip | autobusy ŁKA | **nie** | CC-BY-4.0 (przepakowanie) | 200, mod. 2026-11-23 |
| Koleje Mazowieckie | (brak własnego feedu) | KM, SKM Warszawa | tak | zob. warunki KM (mkuran.pl) | n/d |
| Warszawska Kolej Dojazdowa | https://mkuran.pl/gtfs/wkd.zip | WKD (już w configu jako `warsaw_wkd`) | nie, osobno | CC0 | 200 |

Decyzja: kolej regionalna dla 7 aglomeracji zostaje w `polish_trains` (osobne feedy kolejowe: odrzucone jako duplikaty; KD odrzucony dodatkowo przez HTTP 401). Autobusy KMŁ ALD i ŁKA **dodane** (`krakow_ald`, `lodz_lka_bus`, patrz B.1).

## B. Autobusy podmiejskie i gminne: dziennik decyzji (stan 2026-11-23)

Kryteria dodania (zadanie fazy 0): (1) pobieranie skryptem bez omijania logowania ani zabezpieczeń; (2) licencja lub warunki pozwalają na użycie (brak licencji = „nie podano”, feed używalny do agregatów, ale oznaczony); (3) kursy w dniu referencyjnym śr 2026-11-25; (4) walidator bez błędów psujących `trips`/`stop_times`; (5) brak duplikacji z feedem już użytym (test jak w `rail_overlap.md`: ta sama linia + nazwa przystanku początkowego + minuta odjazdu; pomocniczo: nazwa + minuta oraz położenie przystanku początkowego (siatka ok. 100 m) + minuta, bo nazwy bywają zapisane inaczej). Odsetki to udział kursów kandydata z dnia 25.11 mających odpowiednik w pozostałych feedach. Wszystkie feedy nie-oficjalne (`files.girlc.at`, `api.zbiorkom.live`, `feed.gtfs.cc`, `kasznia.net`, GitHub) są **repackagerami**: podana licencja (CC0 / MIT / CC-BY) to licencja przepakowania z katalogów transitous i Mobility Database, **nie** warunki organizatora transportu, których nie udało się znaleźć (strony wydawców: KMŁ i girlc.at zwracają 403 dla skryptów). Okna ważności feedów girlc.at są kroczące (ok. 2 tygodnie; większość kończy się 28.11), więc raw zachowuje wersję z dnia pobrania. Wszystkie kursy dnia ref. i soboty 28.11 pochodzą z jednego okna, bez przesunięć tygodnia.

Kolumny: kursy = liczba kursów w dniu 25.11 / w sobotę 28.11; błędy = ERROR walidatora MobilityData 8.0.1 (`validator_summary.csv`).

### B.1 Dodane do `config.yaml` (30 feedów)

| id feedu | Przewoźnik / gmina | Aglomeracja | Źródło (URL) | Licencja | Kursy 25.11 / 28.11 | Błędy walid. | Nakładanie | Uwagi |
|---|---|---|---|---|---:|---:|---|---|
| `krakow_ald` | Koleje Małopolskie, linie dowozowe ALD (Małopolskie Linie Dowozowe) | Kraków | https://kolejemalopolskie.com.pl/rozklady_jazdy/ald-gtfs.zip (oficjalny) | CC BY 4.0 wg katalogów (nie sprawdzono na stronie wydawcy) | 1309 / 698 | 0 | < 4 % wg położenia+minuty z `krakow_*` i `polish_trains`; 0 % wg linii | 70 tras w całej Małopolsce. Kopia zbiorkom.live (`MLD`) ma identyczne 1309 kursów: odrzucona na rzecz oficjalnej |
| `krakow_skawina` | UMiG Skawina | Kraków | https://files.girlc.at/gtfs/skawina.zip | CC0 (girlc.at; warunki gminy nie podano) | 304 / 151 | 0 | 6,6 % nazwa+minuta z `krakow_bus` (przypadek; 0 % wg linii) | okno do 28.11 |
| `krakow_niepolomice` | Gmina Niepołomice | Kraków | https://api.zbiorkom.live/api6-open/krakow/gtfs/NIEPOLOMICE | MIT (zbiorkom.live; warunki gminy nie podano) | 131 / 74 | 0 | 2 % z `krakow_bus` (przypadek) | okno 23.11–24.12 |
| `lodz_pabianice` | MZK Pabianice | Łódź | https://api.zbiorkom.live/api6-open/lodz/gtfs/PABIANICE | MIT (zbiorkom.live) | 500 / 259 | 0 | 0 % | okno do 22.12 |
| `lodz_zgierz` | MUK Zgierz | Łódź | https://api.zbiorkom.live/api6-open/lodz/gtfs/ZGIERZ | MIT (zbiorkom.live) | 447 (299 po filtrze) / 269 (185 po filtrze) | 0 | **33 %**: linie 6 i 61 to te same kursy co linie 6 i 61 MPK Łódź (identyczne minuty odjazdu, 148 kursów) | **filtr `drop_routes: [ZGIERZ6, ZGIERZ61]`** (kursy liczone raz, w `lodz`) |
| `lodz_aleksandrow` | UM Aleksandrów Łódzki | Łódź | https://files.girlc.at/gtfs/aleksandrow_lodzki.zip | CC0 (girlc.at) | 76 / 22 | 0 | 0 % | |
| `lodz_strykow` | UM Stryków | Łódź | https://files.girlc.at/gtfs/strykow.zip | CC0 (girlc.at) | 43 / 0 | 0 | 0 % | brak soboty |
| `lodz_lka_bus` | ŁKA, autobusy | Łódź | https://gtfs.kasznia.net/static/sanitized/lka_bus.zip | CC-BY-4.0 (repackaging M. Kasznia) | 299 / 250 | 0 | 0–1 % | ważny do 12.12; nie ma go w `polish_trains` |
| `lodz_suburban_qbx` | 6 prywatnych przewoźników wokół Łodzi (społeczność QBX) | Łódź | https://raw.githubusercontent.com/qbx-tt/gtfs-lodz-suburban/main/gtfs-lodz-suburban.zip | **nie podano** | 415 / 172 | 0 | 0 % | **niska pewność**: zbiór ręczny, bez daty aktualizacji i licencji (Mobility Database mdb-3477) |
| `trojmiasto_wejherowo` | MZK Wejherowo | Trójmiasto | https://mkuran.pl/gtfs/wejherowo.zip | CC0 1.0 (podana na mkuran.pl) | 677 / 425 | 0 | 1,5 % nazwa+minuta z `gdynia`, 0 % wg linii | ważny do 31.12 |
| `warsaw_gpa` | Grodziskie Przewozy Autobusowe | Warszawa | https://api.zbiorkom.live/api6-open/warsaw/gtfs/GPA | MIT (zbiorkom.live) | 2142 / 1132 | 0 | 0 % wg linii; 3,6 % nazwa+minuta i 1,5 % położenie+minuta z `warsaw_ztm` (przypadek) | linie numerowane jak ZTM, ale to inne kursy |
| `warsaw_pruszkow` | Miasto Pruszków (PKM) | Warszawa | https://api.zbiorkom.live/api6-open/warsaw/gtfs/PRUSZKOW | MIT (zbiorkom.live) | 474 / 235 | 0 | < 1 % | |
| `warsaw_minsk` | Miasto Mińsk Mazowiecki | Warszawa | https://api.zbiorkom.live/api6-open/warsaw/gtfs/MINSK | MIT (zbiorkom.live) | 168 / 57 | 0 | 0 % | |
| `warsaw_powiat_minski` | PGZTPPM Mińsk Maz. (powiat miński) | Warszawa | https://files.girlc.at/gtfs/powiat_minski.zip | CC0 (girlc.at) | 325 / 79 | 0 | 0 % (także względem `warsaw_minsk`) | |
| `warsaw_otwock` | OZEC / BKM Otwock | Warszawa | https://files.girlc.at/gtfs/otwock.zip | CC0 (girlc.at) | 138 / 48 | 3 | 0 % | błędy: zdublowane wiersze `routes.txt` (M1, M3) i zły telefon agencji; `trips`/`stop_times` bez zmian |
| `warsaw_radzymin` | UMiG Radzymin | Warszawa | https://files.girlc.at/gtfs/radzymin.zip | CC0 (girlc.at) | 245 / 75 | 0 | 0 % | |
| `warsaw_lomianki` | KM Łomianki | Warszawa | https://files.girlc.at/gtfs/lomianki.zip | CC0 (girlc.at) | 84 / 10 | 0 | 0 % | |
| `warsaw_zabki` | Miasto Ząbki | Warszawa | https://files.girlc.at/gtfs/zabki.zip | CC0 (girlc.at) | 139 / 65 | 0 | 22 % nazwa+minuta z `warsaw_ztm`, ale 0 % wg linii (wspólny, ruchliwy przystanek początkowy; linie różne: z1… vs 190, L46) | bez filtra |
| `warsaw_halinow` | Gmina Halinów | Warszawa | https://files.girlc.at/gtfs/halinow.zip | CC0 (girlc.at) | 85 / 0 | 0 | 0 % | brak soboty |
| `warsaw_wieliszew` | Gmina Wieliszew | Warszawa | https://files.girlc.at/gtfs/wieliszew.zip | CC0 (girlc.at) | 48 / 8 | 0 | 0 % | |
| `warsaw_nowy_dwor` | Nowodworska KA (UM Nowy Dwór Maz.) | Warszawa | https://files.girlc.at/gtfs/nowy_dwor_mazowiecki.zip | CC0 (girlc.at) | 66 / 33 | 0 | 0 % | |
| `warsaw_powiat_nowodworski` | Powiat Nowodworski | Warszawa | https://files.girlc.at/gtfs/powiat_nowodworski.zip | CC0 (girlc.at) | 18 / 18 | 0 | 0 % | |
| `warsaw_sulejowek` | UM Sulejówek / Gmina Wiązowna | Warszawa | https://files.girlc.at/gtfs/sulejowek.zip | CC0 (girlc.at) | 100 / 0 | 0 | 0 % | brak soboty |
| `warsaw_czosnow` | Gmina Czosnów | Warszawa | https://feed.gtfs.cc/czosnow/gtfs.zip | MIT (katalog transitous) | 56 / 7 | 0 | 0 % | feed ręczny (A. Dubis), stały wzorzec tygodniowy 2025–2029 |
| `warsaw_zakroczym` | Komunikacja Gminna Zakroczym | Warszawa | https://feed.gtfs.cc/zakroczym/gtfs.zip | MIT (katalog transitous) | 44 / 8 | 50 | 0 % | błędy: zdublowane `service_id` w `calendar.txt`; kursy i czasy nietknięte |
| `warsaw_dabrowka` | Gmina Dąbrówka | Warszawa | https://files.girlc.at/gtfs/dabrowka.zip | CC0 (girlc.at) | 42 / 8 | 0 | 0 % | |
| `warsaw_zyrardow` | Żyrardowskie Przewozy Autobusowe | Warszawa | https://github.com/minkowskimaciej/zyrardow/raw/main/zyrardow.zip | CC0 (Mobility Database) | 240 / 117 | 0 | 0 % | feed społecznościowy z GitHuba |
| `wroclaw_polbus` | POLBUS-PKS | Wrocław | https://files.girlc.at/gtfs/polbus.zip | CC0 (girlc.at) | 136 / 46 | 22 | 5,9 % położenie+minuta, 0 % wg linii | błędy: zdublowane wiersze `routes.txt` i znaki nowej linii w nazwach przystanków |
| `wroclaw_olesnica` | Gmina Oleśnica | Wrocław | https://files.girlc.at/gtfs/olesnica.zip | CC0 (girlc.at) | 119 / 0 | 0 | 0 % (12 % z Polbus: wspólny przystanek, inne linie) | brak soboty |
| `wroclaw_oborniki` | OLKA Oborniki Śląskie | Wrocław | https://feed.gtfs.cc/oborniki-slaskie/gtfs.zip | MIT (katalog transitous) | 24 / 0 | 0 | 0 % | feed ręczny; brak soboty |

Uwagi do tabeli: (a) liczba kursów w kolumnie to liczba `trip_id` aktywnych w danym dniu wg `calendar`+`calendar_dates` (test własny, zgodny z `service_by_day.csv`); kursy po filtrze/deduplikacji zgodne z `service_by_day.csv`. (b) Nakładanie liczone względem wszystkich 12 dotychczasowych feedów oraz wzajemnie między kandydatami (jedyne pary > 3 %: `olesnica`/`polbus` i Tczew/gmina Tczew, patrz niżej; wszystkie bez zgodności linii). (c) Walidator: żaden z feedów nie ma błędów w `trips.txt`/`stop_times.txt`; błędy dotyczą `routes.txt`, `calendar.txt`, `agency.txt`, `stops.txt` (nazwa). (d) Kod uwzględniający filtr `drop_routes`/`drop_agencies`: `pipeline/gtfs_io.py` (`trip_stats`, `stop_events`; wszystkie moduły czytają feed przez te funkcje). Moduły, które czytają `stop_times.txt` bezpośrednio z zipa (`gtfs_inventory`: kontrola `shape_dist_traveled`), filtra nie stosują; wpływa to tylko na statystyki jakości.

### B.2 Odrzucone

| Kandydat | URL | Licencja (katalog) | Powód |
|---|---|---|---|
| Gdynia zbiorkom.live | https://api.zbiorkom.live/api6-open/tricity/gtfs/GDYNIA | MIT | duplikat `gdynia`: te same kursy ZKM Gdynia (4911 kursów, zgodność wg położenia+minuty 100 %), oficjalny feed już jest |
| MPK Łódź zbiorkom.live | https://api.zbiorkom.live/api6-open/lodz/gtfs/default | MIT | duplikat `lodz` (10 081 kursów, 99,6 % zgodności wg położenia+minuty) |
| Małopolskie Linie Dowozowe zbiorkom.live | https://api.zbiorkom.live/api6-open/mld/gtfs/MLD | MIT | to samo co `krakow_ald` (identyczne 1309 kursów); wybrany oficjalny |
| Kombus Kórnik | https://api.zbiorkom.live/api6-open/poznan/gtfs/KOMBUS | MIT | już w `poznan` jako agencja: 66,8 % kursów pokrywa się (linia+przystanek+minuta) |
| Kombus Środa Wlkp. | https://kasmar00.github.io/gtfs-sroda-wlkp/latest.zip | CC-BY-4.0 | gmina Środa poza FUA Poznania (1 przystanek OSM w FUA) |
| PKS Poznań | http://pksonline.pl/download/pkspoznan.zip | CC0 (katalog) | **nie da się pobrać**: HTTP przekierowuje na HTTPS, a połączenie HTTPS jest odrzucane (błąd TLS/połączenia); nie obchodzono (weryfikacja certyfikatu nie została wyłączona). Do ponownej próby po poprawie po stronie PKS |
| Tczew (miasto) | https://files.girlc.at/gtfs/tczew.zip | CC0 | Tczew poza FUA Trójmiasta (brak gminy w wynikach pokrycia); zdublowane wiersze `routes.txt` podwajają kursy w naiwnym złączeniu |
| Gmina Tczew | https://api.zbiorkom.live/api6-open/tczew/gtfs/GMINATCZEW | MIT | jw. (10 % zgodności z feedem miasta Tczew, ale poza FUA i tak bez znaczenia) |
| Wielicka Komunikacja Wewnątrzgminna | http://gtfs.pyrfekt.com/feeds/wieliczka_gtfs.zip | CC BY-NC-SA 4.0 | okno 2018-12-28..2019-06-30: brak kursów 25.11; licencja NC |
| Chrzanów (ZKKM) | https://data.odt.org.pl/gtfs/zkkm-gtfs.zip | MIT | gmina poza FUA Krakowa; 586 kursów, brak nakładania |
| Olkusz | https://data.odt.org.pl/gtfs/olkusz-gtfs.zip | MIT | poza FUA Krakowa |
| RPK Bochnia | https://api.odt.org.pl/feed/21/GTFS_RPKBochnia.zip | MIT | Bochnia ma 1 przystanek OSM w FUA |
| Sochaczew | https://files.girlc.at/gtfs/sochaczew.zip | CC0 | poza FUA Warszawy (brak w wynikach pokrycia) |
| Plusbus | https://files.girlc.at/gtfs/plusbus.zip | CC0 | linia dalekobieżna Mazowsze–Podlasie, 20 przystanków, 22 kursy |
| TRiBUS | https://files.girlc.at/gtfs/tribus.zip | CC0 | Warmia i Mazury, poza wszystkimi aglomeracjami |

### B.3 Nie znaleziono feedu (stan wyszukiwania 2026-11-23)

Sprawdzono: transitous `feeds/pl.json`, Mobility Database (`feeds_v2.csv`), Atlas (tylko Gdynia, Wrocław, Poznań, Kraków), `mkuran.pl/gtfs`, wyszukiwanie WWW. Brak GTFS dla: PKS Grójec, Nadwiślańska Komunikacja Autobusowa (NKA), komunikacja gminna Legionowa, Błonia, Brwinowa (część gmin ma jednak pokrycie dzięki `warsaw_gpa`), PKS Gdynia, Albatros (Żukowo), gmin Pruszcz Gdański, Kolbudy, Trąbki Wielkie, Przywidz, Cedry Wielkie, Szemud, Siechnice, Czernica, Kobierzyce, Trzebnica, Żmigród (linie aglomeracyjne Wrocławia: nie sprawdzono, czy są w feedzie `wroclaw`), Pobiedziska, Kostrzyn, Stęszew, Łask, Krzeszowice, Wieliczka (jedyny feed z 2019 r.), Miechów, Słomniki, Pułtusk, Serock. Wyszukiwarka WWW daje słabe wyniki dla stron gminnych; brak feedu w katalogach nie dowodzi, że gmina go nie publikuje.

### B.4 Inne ustalenia

- Zmiana w `gtfs_io.trip_stats`: feedy bez kolumn `direction_id`/`shape_id`/`block_id` w `trips.txt` powodowały `KeyError` (nowe feedy girlc.at i feed.gtfs.cc ich nie mają); kolumny są uzupełniane pustymi. Zdublowane wiersze `routes.txt` (Tczew, Polbus, Otwock) nie podwajają już kursów w złączeniu z trasami.
- `gtfs_inventory.run_reference` nie nadpisuje już `reference_day`/`reference_saturday` z `config.yaml`; raport wymienia feedy bez kursów w tych dniach (sobota: `warsaw_halinow`, `warsaw_sulejowek`, `lodz_strykow`, `wroclaw_olesnica`, `wroclaw_oborniki`: brak soboty w rozkładzie, nie błąd).

## C. PKS i przewoźnicy dalekobieżni

Brak ogólnopolskiego feedu PKS. Katalogi zawierają pojedyncze: PKS Poznań (wyżej), PKS Nova (Podlaskie), PKS Opoczno, PKS Kalisz. Dla 7 aglomeracji sens ma tylko PKS Poznań. Krajowy Punkt Dostępu (MMTIS) nie daje kompletnego zbioru (brief §3). FlixBus/Arriva busy: poza zakresem.

## D. Pozostałe uwagi

- `warsaw_ztm` (mkuran.pl) to nieoficjalne przepakowanie danych ZTM; oficjalne dane ZTM Warszawa dostępne są w ZTM FTP/api.um.warszawa.pl, ale wymagają logowania (nie sprawdzano). Licencja mkuran.pl: warunki ZTM + ODbL dla kształtów busów z OSM.
- Wydawcy publikujący pod stałym URL nadpisują plik (Łódź, Poznań), więc `data/raw/gtfs/<feed>/<data>/` jest jedyną gwarancją odtwarzalności. Wrocław zmienia numer zasobu co tydzień (`/hdb/download/<n>/`), co obsługuje `resolve: wroclaw_cui` w `pipeline/fetch_gtfs.py`.
