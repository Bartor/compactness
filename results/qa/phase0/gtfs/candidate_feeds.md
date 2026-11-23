# Kandydaci na dodatkowe feedy GTFS (faza 0)

Stan na 2026-11-23. **Żaden z poniższych nie jest w `config.yaml`**; do głównej konfiguracji trafił tylko `krakow_mobilis` (oficjalny, trzeci feed ZTP Kraków: 33 trasy podmiejskie operatora Mobilis/R&G PLUS, CC BY 4.0, ten sam wydawca co `krakow_bus`/`krakow_tram`).
Kolumna „Sprawdzono” = odpowiedź serwera na żądanie 2026-11-23 (HTTP 200 i data modyfikacji; zawartości nie analizowano, poza `krakow_mobilis`). Pliki kandydatów nie są pobrane do `data/raw/`; po decyzji wchodzą przez `pipeline/fetch_gtfs.py` i `config.yaml`.
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

Wniosek: kolej regionalna dla 7 aglomeracji jest pokryta przez `polish_trains`; osobne feedy mają dodać tylko autobusy tych przewoźników (KMŁ ALD, ŁKA bus), o ile uznamy je za część podaży podmiejskiej.

## B. Autobusy podmiejskie i gminne (luki z §3 i §6)

| Aglomeracja | Kandydat | URL | Co dodaje | Licencja (katalog) | Sprawdzono |
|---|---|---|---|---|---|
| Kraków | **ZTP Kraków, Mobilis (`GTFS_KRK_M`)** (już w configu) | https://gtfs.ztp.krakow.pl/GTFS_KRK_M.zip | 33 podmiejskie trasy autobusowe | CC BY 4.0 | pobrany |
| Kraków | Skawina | https://files.girlc.at/gtfs/skawina.zip | komunikacja gminna Skawiny | CC0 (przepakowanie) | 200, mod. 2026-11-15 |
| Kraków | Niepołomice | https://api.zbiorkom.live/api6-open/krakow/gtfs/NIEPOLOMICE | gmina Niepołomice | MIT (przepakowanie) | 200, 2026-11-23 |
| Kraków | Koleje Małopolskie ALD | zob. A | autobusy dowozowe | CC BY 4.0 | 200 |
| Wrocław | Polbus | https://files.girlc.at/gtfs/polbus.zip | przewoźnik podmiejski pod Wrocławiem | CC0 (przepakowanie) | 200, mod. 2026-11-20 |
| Wrocław | Oleśnica | https://files.girlc.at/gtfs/olesnica.zip | komunikacja miejska/gminna Oleśnicy | CC0 | 200, mod. 2026-11-14 |
| Wrocław | Oborniki Śląskie | https://feed.gtfs.cc/oborniki-slaskie/gtfs.zip | gmina | MIT | nie sprawdzono |
| Poznań | PKS Poznań | http://pksonline.pl/download/pkspoznan.zip | linie regionalne PKS | CC0 (katalog) | 200, 4 MB, mod. 2026-11-23 (HTTP) |
| Poznań | Kombus Kórnik, Środa Wlkp. | https://api.zbiorkom.live/api6-open/poznan/gtfs/KOMBUS, https://kasmar00.github.io/gtfs-sroda-wlkp/latest.zip | Kombus Kórnik jest już agencją w feedzie ZTM Poznań (duplikat); Środa Wlkp. to nowa gmina | MIT / CC-BY-4.0 | 200 |
| Łódź | Zgierz, Pabianice, Aleksandrów Łódzki, Stryków | https://api.zbiorkom.live/api6-open/lodz/gtfs/ZGIERZ, `.../PABIANICE`, https://files.girlc.at/gtfs/aleksandrow_lodzki.zip, https://files.girlc.at/gtfs/strykow.zip | komunikacja gminna wokół Łodzi (część linii MPK Łódź dojeżdża do Zgierza, Pabianic: ryzyko duplikatów) | MIT / CC0 (przepakowanie) | 200 |
| Łódź | Lodz Suburban & Regional Bus (społecznościowy) | https://raw.githubusercontent.com/qbx-tt/gtfs-lodz-suburban/main/gtfs-lodz-suburban.zip | zbiór podmiejskich i regionalnych autobusów (Mobility Database mdb-3477) | nieznana | 200, 0,1 MB, brak daty modyfikacji |
| Trójmiasto | Tczew | https://files.girlc.at/gtfs/tczew.zip | komunikacja miejska Tczewa (na skraju aglomeracji) | CC0 | 200, mod. 2026-11-17 |
| Trójmiasto | Wejherowo, Rumia, Reda | Transitland Atlas `f-u3sy-wejherowo` | komunikacja miejska Wejherowa (URL w katalogu Atlas; zbiorkom.live zwraca 404 dla tego identyfikatora) | do sprawdzenia | nie sprawdzono (brak URL) |
| Trójmiasto | Gdynia zbiorkom.live | https://api.zbiorkom.live/api6-open/tricity/gtfs/GDYNIA | zaktualizowana kopia feedu ZKM (do porównania z `gdynia`) | MIT (przepakowanie) | 200, 3,5 MB |
| GZM | Rybnik, Jastrzębie-Zdrój | https://api.zbiorkom.live/api6-open/rybnik/gtfs/default, `.../JASTRZEBIE` | miasta poza obszarem GZM, ale w sąsiedztwie FUA Katowice (jeśli wariant szerszy) | MIT (przepakowanie) | 200 |
| GZM | Bielsko-Biała | https://files.girlc.at/gtfs/bielsko_biala.zip | poza GZM; tylko jeśli FUA Bielsko-Biała wejdzie do któregoś wariantu | CC0 | 200 |
| GZM | pliki dobowe z portalu GZM | https://otwartedane.metropoliagzm.pl/en/dataset/rozklady-jazdy-i-lokalizacja-przystankow-gtfs-wersja-rozszerzona | oficjalne źródło mirrora: 7 plików dobowych (po ok. 11 MB) generowanych codziennie; mirror na GitHubie jest nieaktualny od 8.11 | CC BY 4.0 | API CKAN dostępne (CC BY) |
| Warszawa | Pruszków, Grodziskie Przewozy Autobusowe, Mińsk Maz., Łomianki, Ząbki i inne | https://api.zbiorkom.live/api6-open/warsaw/gtfs/PRUSZKOW, `.../GPA`, `.../MINSK`, https://files.girlc.at/gtfs/lomianki.zip, https://files.girlc.at/gtfs/zabki.zip | gminne linie wokół Warszawy. **Uwaga**: wiele z nich ZTM Warszawa już uwzględnia (linie aglomeracyjne), więc ryzyko dublowania z `warsaw_ztm`; wymaga testu jak w `rail_overlap.md` | MIT / CC0 (przepakowanie) | 200 |

## C. PKS i przewoźnicy dalekobieżni

Brak ogólnopolskiego feedu PKS. Katalogi zawierają pojedyncze: PKS Poznań (wyżej), PKS Nova (Podlaskie), PKS Opoczno, PKS Kalisz. Dla 7 aglomeracji sens ma tylko PKS Poznań. Krajowy Punkt Dostępu (MMTIS) nie daje kompletnego zbioru (brief §3). FlixBus/Arriva busy: poza zakresem.

## D. Pozostałe uwagi

- `warsaw_ztm` (mkuran.pl) to nieoficjalne przepakowanie danych ZTM; oficjalne dane ZTM Warszawa dostępne są w ZTM FTP/api.um.warszawa.pl, ale wymagają logowania (nie sprawdzano). Licencja mkuran.pl: warunki ZTM + ODbL dla kształtów busów z OSM.
- Wydawcy publikujący pod stałym URL nadpisują plik (Łódź, Poznań), więc `data/raw/gtfs/<feed>/<data>/` jest jedyną gwarancją odtwarzalności. Wrocław zmienia numer zasobu co tydzień (`/hdb/download/<n>/`), co obsługuje `resolve: wroclaw_cui` w `pipeline/fetch_gtfs.py`.
