# Weryfikacja centrów i węzłów względem OSM (Nominatim)

Każda współrzędna z `config.yaml` porównana z wynikiem wyszukiwania Nominatim (OSM) dla podanego zapytania; odległość w EPSG:2180. Próg zgłoszenia: > 150 m od pierwszego wyniku. **Config nie został zmieniony**; propozycje to wyniki OSM, do zatwierdzenia przez właściciela. Nominatim zwraca zwykle punkt lub środek obiektu (plac, stacja), więc dla placów i rynków odchylenia ~100–200 m mogą być zwykłą różnicą między „środkiem obiektu” a punktem, który ktoś miał na myśli.

| Aglomeracja | Rola | Nazwa w config | Config (lon, lat) | Zapytanie | Wynik OSM | OSM (lon, lat) | Odległość m | Uwaga |
|---|---|---|---|---|---|---|---|---|
| warszawa | centre | Rondo Dmowskiego | 21.0118, 52.2297 | Rondo Dmowskiego, Warszawa | Rondo Romana Dmowskiego, Centrum, Śródmieście Północne, Śródmieście, W (highway/secondary) | 21.0122, 52.2300 | 39 | ok |
| warszawa | hub | Metro Centrum / Warszawa Centralna | 21.0107, 52.2302 | Metro Centrum, Warszawa | Metro Centrum, Patelnia, Żelazna Brama, Śródmieście Północne, Śródmieś (building/transportation) | 21.0104, 52.2305 | 38 | ok |
| krakow | centre | Rynek Główny | 19.9373, 50.0617 | Rynek Główny, Kraków | Rynek Główny, Stare Miasto, Kraków, województwo małopolskie, 31-042, P (place/square) | 19.9371, 50.0615 | 26 | ok |
| krakow | hub | Kraków Główny / Dworzec Główny | 19.9468, 50.067 | Kraków Główny | Kraków Główny, Świętego Rafała Kalinowskiego, Wesoła, Stare Miasto, Kr (railway/station) | 19.9479, 50.0684 | 176 | PONAD PRÓG |
| wroclaw | centre | Rynek | 17.032, 51.11 | Rynek, Wrocław | Rynek, Dzielnica Czterech Wyznań, Stare Miasto, Wrocław, województwo d (highway/pedestrian) | 17.0307, 51.1100 | 93 | ok |
| wroclaw | hub | Galeria Dominikańska | 17.0403, 51.1083 | Galeria Dominikańska, Wrocław | Galeria Dominikańska, 3, plac Dominikański, Ostrów Tumski, Stare Miast (shop/mall) | 17.0405, 51.1084 | 24 | ok |
| poznan | centre | Stary Rynek | 16.9342, 52.4083 | Stary Rynek, Poznań | Stary Rynek, Garbary, Chwaliszewo, Stare Miasto, Poznań, województwo w (place/square) | 16.9336, 52.4083 | 41 | ok |
| poznan | hub | Rondo Kaponiera | 16.9126, 52.4081 | Rondo Kaponiera, Poznań | Rondo Kaponiera, Jeżyce, Poznań, województwo wielkopolskie, 60-829, Po (highway/tertiary) | 16.9120, 52.4078 | 48 | ok |
| lodz | centre | pl. Wolności | 19.4547, 51.7769 | plac Wolności, Łódź | Plac Wolności, Centrum, Łódź-Śródmieście, Łódź, województwo łódzkie, 9 (place/square) | 19.4547, 51.7768 | 13 | ok |
| lodz | hub | Piotrkowska Centrum | 19.4573, 51.7594 | Piotrkowska Centrum, Łódź | Piotrkowska Centrum, Aleja Adama Mickiewicza, Centrum, Łódź-Śródmieści (building/roof) | 19.4571, 51.7592 | 24 | ok |
| trojmiasto | centre | Gdańsk Główny | 18.644, 54.3556 | Gdańsk Główny | Gdańsk Główny, 2, Podwale Grodzkie, Grodzisko, Stare Miasto, Śródmieśc (railway/station) | 18.6442, 54.3564 | 94 | ok |
| trojmiasto | hub | Gdańsk Główny | 18.644, 54.3556 | Gdańsk Główny | Gdańsk Główny, 2, Podwale Grodzkie, Grodzisko, Stare Miasto, Śródmieśc (railway/station) | 18.6442, 54.3564 | 94 | ok |
| trojmiasto | extra | Gdynia Główna | 18.5297, 54.5208 | Gdynia Główna | Gdynia Główna, Morska, Działki Leśne, Gdynia, województwo pomorskie, 8 (railway/station) | 18.5268, 54.5218 | 216 | PONAD PRÓG |
| trojmiasto | extra | Sopot | 18.562, 54.4405 | Sopot dworzec | Sopot Centrum, 7, Dworcowa, Sopot Dolny, Sopot, województwo pomorskie, (building/public) | 18.5622, 54.4415 | 115 | ok |
| gzm | centre | Katowice Rynek | 19.0216, 50.2594 | Rynek, Katowice | Rynek (Plac Kwiatowy), Śródmieście, Katowice, Górnośląsko-Zagłębiowska (highway/pedestrian) | 19.0216, 50.2590 | 47 | ok |
| gzm | hub | Katowice Rynek | 19.0216, 50.2594 | Rynek, Katowice | Rynek (Plac Kwiatowy), Śródmieście, Katowice, Górnośląsko-Zagłębiowska (highway/pedestrian) | 19.0216, 50.2590 | 47 | ok |
| gzm | extra | Gliwice Rynek | 18.6657, 50.2945 | Rynek, Gliwice | Rynek, Stare Miasto, Śródmieście, Gliwice, Górnośląsko-Zagłębiowska Me (highway/pedestrian) | 18.6661, 50.2940 | 59 | ok |
| gzm | extra | Sosnowiec centrum | 19.1275, 50.278 | Sosnowiec Główny | Sosnowiec Główny, 3 Maja, Śródmieście, Sosnowiec, Górnośląsko-Zagłębio (railway/station) | 19.1264, 50.2790 | 132 | ok |
| gzm | extra | Bytom Rynek | 18.921, 50.348 | Rynek, Bytom | Rynek, Śródmieście, Bytom, Górnośląsko-Zagłębiowska Metropolia, wojewó (highway/pedestrian) | 18.9234, 50.3470 | 208 | PONAD PRÓG |
| gzm | extra | Zabrze centrum | 18.786, 50.305 | Plac Warszawski, Zabrze | Plac Warszawski, Osiedle Barbary, Małe Zabrze, Śródmieście, Zabrze, Gó (place/square) | 18.7883, 50.3038 | 213 | PONAD PRÓG |
| gzm | extra | Tychy centrum | 18.987, 50.124 | plac Baczyńskiego, Tychy | Metrorower, Plac Krzysztofa Kamila Baczyńskiego, Osiedle B, Śródmieści (amenity/bicycle_rental) | 18.9837, 50.1261 | 330 | PONAD PRÓG |
| gzm | extra | Chorzów Rynek | 18.954, 50.297 | Rynek, Chorzów | Rynek, Centrum, Chorzów, Górnośląsko-Zagłębiowska Metropolia, wojewódz (highway/pedestrian) | 18.9536, 50.2979 | 103 | ok |
| gzm | extra | Dąbrowa Górnicza centrum | 19.185, 50.324 | plac Wolności, Dąbrowa Górnicza | Plac Wolności, Śródmieście, Dąbrowa Górnicza, Górnośląsko-Zagłębiowska (highway/pedestrian) | 19.1883, 50.3255 | 287 | PONAD PRÓG |
| gzm | extra | Ruda Śląska (Nowy Bytom) | 18.876, 50.288 | Nowy Bytom, Ruda Śląska | Nowy Bytom, Ruda Śląska, Górnośląsko-Zagłębiowska Metropolia, wojewódz (boundary/administrative) | 18.8740, 50.2869 | 185 | PONAD PRÓG |
| szczecin | centre | Brama Portowa | 14.5494, 53.425 | Brama Portowa, Szczecin | Brama Portowa, 5, Plac Brama Portowa, Nowe Miasto, Śródmieście, Szczec (building/monument) | 14.5504, 53.4250 | 68 | ok |
| bydgoszcz_torun | centre | Bydgoszcz, Stary Rynek | 18.0003, 53.122 | Stary Rynek, Bydgoszcz | Stary Rynek, Stare Miasto, Dzielnica Muzyczna, Stare Miasto, Bocianowo (highway/pedestrian) | 18.0003, 53.1220 | 4 | ok |
| bydgoszcz_torun | extra | Toruń, Rynek Staromiejski | 18.6045, 53.0104 | Rynek Staromiejski, Toruń | Rynek Staromiejski, Stare Miasto, Toruń, województwo kujawsko-pomorski (highway/pedestrian) | 18.6037, 53.0105 | 54 | ok |
| lublin | centre | pl. Litewski | 22.56, 51.2481 | plac Litewski, Lublin | Plac Litewski, Śródmieście, Lublin, województwo lubelskie, Polska (place/square) | 22.5596, 51.2484 | 40 | ok |
| rzeszow | centre | Rynek | 22.005, 50.0375 | Rynek, Rzeszów | Rynek, Baldachówka, Śródmieście, Rzeszów, województwo podkarpackie, Po (place/square) | 22.0050, 50.0375 | 3 | ok |
| kielce | centre | Rynek | 20.6335, 50.8703 | Rynek, Kielce | Rynek, Śródmieście, Kielce, województwo świętokrzyskie, Polska (highway/pedestrian) | 20.6321, 50.8716 | 170 | PONAD PRÓG |
| bialystok | centre | Rynek Kościuszki | 23.1589, 53.1325 | Rynek Kościuszki, Białystok | Rynek Kościuszki, Centrum, Białystok, województwo podlaskie, 15-091, P (highway/pedestrian) | 23.1610, 53.1323 | 140 | ok |

## Pozycje powyżej progu i propozycje poprawek

- **krakow / hub / Kraków Główny / Dworzec Główny**: 176 m od wyniku OSM; propozycja `lon: 19.9479, lat: 50.0684` (Kraków Główny, Świętego Rafała Kalinowskiego, Wesoła, Stare Miasto, Kraków, woje). Do oceny, czy wynik OSM oddaje zamierzony punkt.
- **trojmiasto / extra / Gdynia Główna**: 216 m od wyniku OSM; propozycja `lon: 18.5268, lat: 54.5218` (Gdynia Główna, Morska, Działki Leśne, Gdynia, województwo pomorskie, 81-324, Pol). Do oceny, czy wynik OSM oddaje zamierzony punkt.
- **gzm / extra / Bytom Rynek**: 208 m od wyniku OSM; propozycja `lon: 18.9234, lat: 50.3470` (Rynek, Śródmieście, Bytom, Górnośląsko-Zagłębiowska Metropolia, województwo śląs). Do oceny, czy wynik OSM oddaje zamierzony punkt.
- **gzm / extra / Zabrze centrum**: 213 m od wyniku OSM; propozycja `lon: 18.7883, lat: 50.3038` (Plac Warszawski, Osiedle Barbary, Małe Zabrze, Śródmieście, Zabrze, Górnośląsko-). Do oceny, czy wynik OSM oddaje zamierzony punkt.
- **gzm / extra / Tychy centrum**: 330 m od wyniku OSM; propozycja `lon: 18.9837, lat: 50.1261` (Metrorower, Plac Krzysztofa Kamila Baczyńskiego, Osiedle B, Śródmieście, Tychy, ). Do oceny, czy wynik OSM oddaje zamierzony punkt.
- **gzm / extra / Dąbrowa Górnicza centrum**: 287 m od wyniku OSM; propozycja `lon: 19.1883, lat: 50.3255` (Plac Wolności, Śródmieście, Dąbrowa Górnicza, Górnośląsko-Zagłębiowska Metropoli). Do oceny, czy wynik OSM oddaje zamierzony punkt.
- **gzm / extra / Ruda Śląska (Nowy Bytom)**: 185 m od wyniku OSM; propozycja `lon: 18.8740, lat: 50.2869` (Nowy Bytom, Ruda Śląska, Górnośląsko-Zagłębiowska Metropolia, województwo śląski). Do oceny, czy wynik OSM oddaje zamierzony punkt.
- **kielce / centre / Rynek**: 170 m od wyniku OSM; propozycja `lon: 20.6321, lat: 50.8716` (Rynek, Śródmieście, Kielce, województwo świętokrzyskie, Polska). Do oceny, czy wynik OSM oddaje zamierzony punkt.

Uwagi: (1) hub Warszawy opisany jako „Metro Centrum / Warszawa Centralna” zweryfikowano jako stację metra Centrum (38 m); sama stacja kolejowa Warszawa Centralna leży ok. 540 m dalej na zachód (21,0032; 52,2288), więc nazwa hubu jest dwuznaczna. (2) Białystok (140 m) i Sosnowiec (132 m) są tuż pod progiem. (3) Wyniki dla ulic pieszych (rynki) to punkt na linii ulicy wg OSM, nie środek placu.

