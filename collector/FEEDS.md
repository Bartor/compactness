# Przegląd feedów czasu rzeczywistego (stan: 2026-11-23)

Każdy feed sprawdzony realnymi zapytaniami (5 pobrań co ~18 s + 4-minutowy przebieg kolektora). Rejestr maszynowy: `feeds.yaml`.
Żadnych kluczy ani rejestracji nie używano; feedy wymagające klucza byłyby oznaczone „needs key” i wyłączone (żaden z badanych nie wymagał).

| Miasto | Id | URL | Format | Odświeżanie (obserwowane) | Pojazdów | `trip_id` / `route_id` | Włączony |
|---|---|---|---|---|---|---|---|
| Warszawa | `warsaw` | `https://mkuran.pl/gtfs/warsaw/vehicles.pb` | GTFS-RT PB, tylko VehiclePositions (wszystkie rodzaje) | nowy zrzut przy każdym pobraniu co ~18 s; pozycje pojazdów co ~10–20 s | ~1910 | trip_id 100%; route_id **puste** (wyciągane z trip_id `RRRR-MM-DD:<linia>:<brygada>:…`) | tak, 30 s |
| Kraków – tramwaje | `krakow_t` | `https://gtfs.ztp.krakow.pl/VehiclePositions_T.pb` (+ `TripUpdates_T.pb`) | GTFS-RT PB | ~10–20 s | ~215 | trip_id 100% (225/228 w GTFS_KRK_T); route_id **puste**, brak `speed` | tak, 20 s |
| Kraków – autobusy aglom. | `krakow_a` | `…/VehiclePositions_A.pb` (+ TU) | GTFS-RT PB | ~10–20 s | ~92 | trip_id i route_id 100% (106/106 w GTFS_KRK_A) | tak, 30 s |
| Kraków – autobusy MPK | `krakow_m` | `…/VehiclePositions_M.pb` (+ TU) | GTFS-RT PB | ~10–20 s | ~116 | trip_id i route_id 100% (125/125) | tak, 30 s |
| Poznań | `poznan` | `https://www.ztm.poznan.pl/pl/dla-deweloperow/getGtfsRtFile/?file=vehicle_positions.pb` (+ `trip_updates.pb`) | GTFS-RT PB | ~10–20 s (nagłówek zmienia się co 10–20 s) | ~491 | trip_id i route_id 100%; brak `speed`; join ze statycznym GTFS niesprawdzony | tak, 20 s |
| Szczecin | `szczecin` | `https://www.zditm.szczecin.pl/storage/gtfs/gtfs-rt-vehicles.pb` (+ `gtfs-rt-trips.pb`) | GTFS-RT PB (adres z `realtime_feeds.txt` w GTFS); dodatkowo JSON `https://www.zditm.szczecin.pl/api/v2/vehicles` (nieużywany) | ~10 s | ~232 (70 tramwajów) | trip_id 99%, **join 208/208** z `trips.txt`; route_id **puste** (route_id w GTFS = numer linii, dostępny przez trips.txt) | tak, 20 s |
| Gdańsk | `gdansk` | `https://ckan2.multimediagdansk.pl/gpsPositions?v=2` | **własny JSON** (nie GTFS-RT), adapter `gdansk-json` | `Cache-Control: max-age=20`; `lastUpdate` co ~20 s | ~294 | `tripId` to numer kursu w obrębie linii (nie globalny trip_id; join = routeId + tripId, niesprawdzony), `routeId` 100% | tak, 20 s |
| GZM | `gzm` | `https://gtfsrt.transportgzm.pl:5443/gtfsrt/gzm` | GTFS-RT PB, **tylko TripUpdates** (~1000 kursów z opóźnieniami) | nagłówek zmienia się przy każdym pobraniu | 0 pozycji | trip_id tak, route_id puste | **nie** (brak pozycji; do włączenia ręcznie dla punktualności) |
| Wrocław | `wroclaw` | – | niezweryfikowany | – | – | – | nie |
| Łódź | `lodz` | – | brak znalezionego publicznego feedu | – | – | – | nie |
| Gdynia | `gdynia` | – | brak znalezionego publicznego feedu (tylko statyczny GTFS) | – | – | – | nie |

## Licencje i warunki

- **Warszawa:** pozycje pochodzą z Urzędu m.st. Warszawy (nie z ZTM), licencja *Warsaw Open Data Project Usage Terms* (api.um.warszawa.pl); wymagane podanie „Miasto Stołeczne Warszawa”, daty pobrania (z nagłówka feedu) i linku http://api.um.warszawa.pl. Mkuran zaznacza, że niektóre trip_id mogą nie występować w statycznym GTFS. Statyczny GTFS zgodny z tymi trip_id: `https://mkuran.pl/gtfs/warsaw.zip` (nieprzetestowany join, plik 107 MB).
- **Kraków:** CC BY 4.0, ZTP w Krakowie (https://gtfs.ztp.krakow.pl/). Serwis czasem ma przerwy techniczne (23.11.2026 komunikat o pracach 9:00–16:00) i komunikat „Brak danych GTFS-RT dla grupy…” – to trafi do `gaps.jsonl`.
- **Szczecin:** CC0 1.0; limit 100 zapytań/min/IP; prośba o identyfikowalny User-Agent (kolektor ustawia `gtfs-rt-archiver/x.y`); wymagane respektowanie `ETag`/`Cache-Control` (kolektor wysyła `If-None-Match`).
- **Gdańsk:** CC BY (Otwarty Gdańsk / ZTM Gdańsk, https://ckan.multimediagdansk.pl/dataset/tristar).
- **Poznań:** licencji nie udało się zweryfikować (strona `ztm.poznan.pl/pl/dla-deweloperow` zwraca 404 pod adresami, które próbowano; sam plik .pb działa bez klucza). Do sprawdzenia przez właściciela przed publikacją wyników.
- **GZM:** feed pochodzi od ZTM GZM (CC BY dla statycznego GTFS na otwartedane.metropoliagzm.pl); warunki samego feedu RT niezweryfikowane (adres znaleziony przez wyszukiwarkę, działa bez klucza).

## Czego nie udało się zweryfikować

- **Wrocław:** `opendata.cui.wroclaw.pl`/`www.wroclaw.pl/open-data` zwraca HTTP 403 (WAF FortiADC) dla zapytań ze skryptu, a `mpk.wroc.pl` jest nieosiągalny z tej maszyny. Format (GTFS-RT vs JSON CKAN datastore) nieznany. Nie obchodzono blokady.
- **Łódź, Gdynia:** wyszukiwanie nie wykazało publicznego feedu pozycji. (Strony Transitland blokowane przez Cloudflare.)
- **GZM:** nie znaleziono ścieżki z pozycjami pojazdów (próbowano kilku wariantów pod `/gtfsrt/`), adres jest podobno niestabilny (Transitland: zmienia się codziennie).
- Join trip_id ze statycznym GTFS sprawdzono dla Szczecina i Krakowa; Warszawa, Poznań i Gdańsk nie.
- Prawdziwe częstotliwości odświeżania w nocy i w weekendy – pomiar tylko z wieczoru dnia roboczego.
- Brak `speed` w Warszawie, Krakowie-T i Poznaniu: prędkość rzeczywistą trzeba liczyć z kolejnych pozycji.
