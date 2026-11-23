# Benchmark DG REGIO: Poelman, Dijkstra, Ackermans (WP 01/2020)

Źródło pierwotne: H. Poelman, L. Dijkstra, L. Ackermans, *How many people can you reach by public transport, bicycle or on foot in European cities? Measuring urban accessibility for low-carbon modes*, DG REGIO Working Paper 01/2020, doi:10.2776/021137. PDF: https://ec.europa.eu/regional_policy/sources/work/012020_low_carbon_urban.pdf (pobrany i przeczytany lokalnie 2026-11-23; 54 strony PDF, numeracja drukowana = numer strony PDF minus 2). Brief nazywa pracę „Sustainable and inclusive urban transport"; **faktyczny tytuł jest inny** (powyżej), warto poprawić w RAPORT.md.

Dodatkowe materiały (karty miast, „city fact sheets"; przypis 15 w pracy → https://ec.europa.eu/regional_policy/en/information/maps/low-carbon-urban-accessibility): **nie sprawdzono** w tej sesji, więc dokładne wartości liczbowe per miasto nie zostały odczytane z tabeli. Praca zawiera tylko wykresy słupkowe, bez tabeli i bez aneksu z danymi. Wszystkie wartości dla miast poniżej są **odczytane z wykresów** (pomiar pikseli na renderze 3x; dokładność około ±1 pkt).

## 1. Metoda (z tekstu pracy)

| Element | Wartość | Gdzie |
|---|---|---|
| Próba | **42 miasta** (urban centres), głównie stolice; „calculations limited to a group of 42 cities" | s. 16 |
| Jednostka miasta | **urban centre** (Degree of Urbanisation), nie FUA; w przyp. 3: „city" = „urban centre". Wcześniej: „EU-OECD Functional Urban Area definition for urban centres" (wstęp, s. 5) | s. 5 |
| Pochodzenia i cele | **zaludnione polygony Urban Atlas 2012** (centroidy; bez wody i dróg), ludność **2011** (oszacowanie na polygon wg Batista e Silva & Poelman 2016); **cele ograniczone do urban centre** | Metodologia, s. 37 |
| Siatka | **nie siatka regularna**: polygony Urban Atlas (nieregularne bloki). Siatka 1 km² (GEOSTAT) użyta tylko dla wskaźnika SDG 11.2.1 i gęstości ważonej | s. 6, 30, 37 |
| Router | **OpenTripPlanner 1.2.0** (zmodyfikowany, by zwracał czas początkowego oczekiwania) + OSM (pbf z Geofabrik) | s. 37, przyp. 39–42 |
| Parametry OTP | `maxWalkDistance: 5000`, `maxTimeSec: 3600`, `clampInitialWait: -1`, tryby TRANSIT+WALK, `dateTime` dobrany ręcznie per feed | przyp. 41, s. 37 |
| Okno czasowe | **9 odjazdów co 15 min w ciągu dwugodzinnego szczytu porannego**; godzin dokładnie nie podano (nie zweryfikowano w tekście) | s. 37 |
| Agregacja czasu | dla pary OD **średnia z 9 przebiegów** (nie mediana); czas całkowity = dojście + oczekiwanie + jazda + przesiadki + dojście; para zaliczona, jeśli średnia ≤ 30 lub ≤ 45 min | s. 37–38 |
| Dzień | dzień roboczy o **maksymalnej liczbie odjazdów** w okresie ważności feedu (unika świąt/ferii); feedy łączone wymuszoną wspólną datą | s. 35, 37 |
| Rok rozkładów | **2018** (mapy: „Public transport departures in urban centres, 2018"); rok per miasto nie podany | mapy 3–6 |
| Dojście max | w OTP 5000 m (limit techniczny, nie realne ograniczenie czasu 30/45 min); w analizie częstotliwości: 500 m do przystanku bus/tram, 1 km do metra/kolei | s. 35, przyp. 41 |
| Proximity | promień odpowiadający prędkości **15 km/h** (30 min = **7,5 km**, 45 min = **11,25 km**), rower: 30 min = 7,5 km; pieszo **5 km/h**, 30 min = **2,5 km** (przyp. 17) | s. 16, przyp. 17 |
| Performance | accessible population / neighbouring population × 100; średnia ważona ludnością? **Nie podano wprost w tekście** (nie zweryfikowano, jak agregowano po komórkach) | s. 16 |
| Częstotliwość odjazdów (osobny wskaźnik) | odjazdy **6:00–20:00**, dzień roboczy; klasy: < 4 / 4–10 / > 10 odjazdów/h, osobno bus+tram (500 m) i kolej+metro (1 km) | s. 34–35 |
| Kolej w GTFS | gdy brak w feedach miejskich: feed zbudowany z UIC MERITS; przy poważnych wątpliwościach co do kompletności analizy nie wykonano | s. 34 |
| Rower | OTP/inna sieć OSM; z wyłączeniem dróg zakazanych; contraflow dopuszczony; korekta nachyleń | s. 19–20 |

Różnice względem naszego wariantu (do opisu przy benchmarku): (1) cele tylko w urban centre, u nas FUA + bufor 15 km (więc mianownik i licznik są szersze); (2) ludność 2011 z polygonów UA vs nasze GHSL 2020 w siatce 250 m; (3) średnia z 9 przebiegów w 2 h vs nasza mediana z minutowych odjazdów w oknach 7–9 itd.; (4) rok rozkładów 2018 vs 2026; (5) max dojście 5 km (OTP) vs nasz 1 km; (6) kolej z UIC MERITS może być spójna lub niepełna w polskich miastach: nie zweryfikowano.

## 2. Średnie (cała próba 42 miast)

| Miara | Średnia | Min – max | Strona |
|---|---|---|---|
| PT performance 30 min | **24** | 12 (Greater Manchester) – 48 (Luksemburg) | s. 16, rys. 7 |
| PT performance 45 min | **57** | 31 (Ateny) – 97 (Kaunas) | s. 16–18, rys. 7 |
| Pieszo 30 min (promień 2,5 km) | **52** | 43 (Dublin) – 61 (Tallinn) | s. 19, rys. 9 |
| Rower 30 min (promień 7,5 km) | **75** | wg wykresu ok. 59–98 | s. 19, rys. 10 |

## 3. Wartości dla polskich miast w próbie

W próbie są **trzy** polskie miasta: **Warszawa, Poznań, Łódź** (nie ma Krakowa, Wrocławia, Gdańska ani Katowic). Wartości **odczytane z wykresów** (rys. 7, 9, 10), przybliżone ±1:

| Miasto | PT 30 min | PT 45 min | Pieszo 30 min | Rower 30 min | Rysunki / strony |
|---|---|---|---|---|---|
| Warszawa | ok. 31 | ok. 62 | ok. 49 | ok. 70,5 | rys. 7 (s. 17), rys. 9 (s. 20), rys. 10 (s. 21) |
| Poznań | ok. 26 | ok. 75 | ok. 43 | ok. 81 | tamże |
| Łódź | ok. 25,5 | ok. 75 | ok. 54 | ok. 81 | tamże |

Obserwacje (z odczytu, nie z tekstu): Warszawa ma najwyższy wynik PT 30 min z trzech, ale najniższy PT 45 min; Poznań i Łódź mają wysokie 45 min względem średniej 57. Poznań ma jedną z najniższych wartości pieszych w próbie (ok. 43, tuż nad Dublinem; wykres kończy listę kolejnością Manchester, Poznań, Dublin).

Fakty z tekstu dla Warszawy: Warszawa wymieniona wśród miast (obok Wiednia, Madrytu, Kopenhagi, Barcelony), w których „half of the population has access to at least 50 departures an hour" w dzień roboczy (sekcja 1.2, mediana odjazdów w zasięgu pieszym, Map 3; numer strony nie zweryfikowany); Map 2 „Warsaw: typology of public transport frequencies"; mapy 9–13 pokazują Warszawę: czas dojazdu z centrum, ludność osiągalna w 30 min PT i rowerem, ludność w promieniu 7,5 km, performance 30 min).

## 4. Uwagi do porównania

- Porównywać **tylko rząd wielkości i kolejność**, nie wartości absolutne: inne granice (urban centre), inna ludność (2011), inny router i uśrednianie.
- Spodziewane różnice kierunkowe: nasze cele w FUA+15 km i mianownik 7,5/11,25 km obejmują więcej zabudowy rozproszonej (obniża performance), a rozkłady 2026 i 1 km maks. dojścia obniżają dostępność w stosunku do OTP z 5 km.
- Źródło wtórne nie było używane. Brak publicznie dostępnego pliku z danymi liczbowymi w samej pracy; **do sprawdzenia**: karty miast z linku w przyp. 15 (mogą podawać dokładne wartości dla Warszawy, Poznania, Łodzi).
