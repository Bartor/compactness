"""Hand-written Polish text of the transfer note (pipeline.transfer_md).

Numbers quoted in this file were read from the outputs of the run of 2026-11-24 (timetable 2026-11-25) and checked by
hand; the tables in the note are generated, so if a re-run changes them, re-read this text."""
import pandas as pd

INTRO = [
    "Warstwa dodatkowa zatwierdzona przez właściciela 2026-11-24 (RAPORT §12.2). Opisuje, jak łatwo przesiąść się "
    "między liniami w zespole przystanków: ile trzeba przejść, przez ile jezdni, czy po schodach, ile średnio czekać "
    "na linię docelową i jak ważny jest węzeł. **Składowe są publikowane obok siebie i nie są łączone w jedną ocenę.**",
    "",
    "Punkt odniesienia z literatury, nie specyfikacja: prace o „karze za przesiadkę” rozkładają koszt przesiadki na "
    "dojście, czekanie i resztę zależną od stacji i rodzaju ruchu (Guo i Wilson 2011, metro londyńskie; Iseki i "
    "Taylor, Transport Reviews, „Not all transfers are created equal”). Polska metoda AMPTI (Olszewski, Krukowska, "
    "Krukowski, TMiR 6/2014; stosowana w wytycznych ZTM Warszawa i w ocenach węzłów Krakowa) ocenia węzły wskaźnikami "
    "ilościowymi, ale część z nich (stan peronów, informacja, oświetlenie, monitoring, widoczność przystanków) wymaga "
    "audytu w terenie. **Ta warstwa to wariant własny, ograniczony do tego, co dają rozkłady i OpenStreetMap. Nie "
    "jest oceną AMPTI ani wskaźnikiem kary za przesiadkę** i nie nosi nazwy żadnej z tych metod.",
    "",
    "Wszystkie czasy dojścia są z sieci pieszej OSM przy 5 km/h, bez czasu na światłach, schodach i w tłumie; czekanie "
    "jest rozkładowe, w pełnych minutach. Wynik nie mówi nic o punktualności, zatłoczeniu ani informacji dla pasażerów.",
]

RULE_CHOICE = [
    "Dlaczego tak: klastry 100 m z kroku częstej komunikacji łączą tylko słupki tej samej ulicy i skrzyżowania; "
    "przystanki tramwaju, autobusu i wejścia na stację bywają 200–300 m od siebie (sprawdzone niżej na znanych "
    "węzłach). Próg 150 m łączy przystanki po przekątnej dużego skrzyżowania, 250 m dla kolei i metra łączy stację "
    "(w GTFS jeden punkt) z przystankami przed nią. Ograniczenie rozpiętości (pełne wiązanie) zapobiega łańcuchom w "
    "gęstym śródmieściu: bez niego cała oś Marszałkowskiej byłaby jednym zespołem. Nazwy przystanków nie są używane, "
    "bo w GTFS ten sam węzeł ma różne nazwy w różnych feedach (np. „DWORZEC GŁÓWNY” i „Wrocław Główny”).",
]

RULE_FAILS = [
    "**Jak reguła działa na znanych węzłach i gdzie zawodzi.**",
    "",
    "- Większość węzłów wychodzi tak, jak zna je pasażer: Rondo Mogilskie (18 słupków, 273 m), Rondo Grunwaldzkie, "
    "pl. Grunwaldzki, Galeria Dominikańska, Rondo Kaponiera, Piotrkowska Centrum, Katowice Rynek, Dworzec Wileński, "
    "Centrum z przystankiem Warszawa Śródmieście.",
    "- **Kraków, Dworzec Główny: dwa zespoły.** „Dworzec Główny Zachód” (Basztowa / Pawia, 6 słupków) i zespół "
    "„Kraków Główny” (stacja, Dworzec Główny Wschód, Uniwersytet Ekonomiczny, Muzeum AK; 27 słupków) dzieli ok. 330 m. "
    "Dla pasażera to jeden obszar przesiadkowy z tunelem pod torami. Reguła szeroka łączy je w jeden zespół (46 "
    "słupków), ale wtedy wyniki obu części się mieszają (tabela wyżej). To jest błąd reguły głównej, zostawiony jawnie.",
    "- **Wrocław, Dworzec Główny.** Stacja (jeden punkt GTFS dla 10 stanowisk) łączy się z dworcem autobusowym i "
    "tramwajami na Piłsudskiego (30 słupków, 524 m). Pierwsza wersja reguły (bez większej rozpiętości dla kolei) "
    "rozdzielała tramwaje i stację; to było niezgodne z rzeczywistością i zostało poprawione.",
    "- **Za szeroko: Warszawa Dworzec Gdański** (585 m) wciąga przystanek „Felińskiego”; **Poznań Główny / "
    "Dworzec Zachodni** (653 m) i **Łódź Kaliska** (654 m) to całe kompleksy dworcowe. Dojście w tych zespołach jest "
    "dłuższe, bo zespół obejmuje słupki, między którymi pasażer zwykle się nie przesiada.",
    "- **Niestabilność pełnego wiązania.** Przy regule szerokiej Gdańsk Główny ma 10 słupków (przy głównej 21), "
    "Łódź Kaliska 16 (przy głównej 28): większa składowa dzieli się w innym miejscu. Wynik węzła zależy więc od "
    "reguły bardziej niż wynik miasta.",
    "- **Wrażliwość miar miejskich.** Udział odjazdów w zespołach „łatwych” spada z 91–98 % (klastry 100 m) przez "
    "62–83 % (główna) do 48–67 % (szeroka). Kolejność miast jest podobna (Warszawa i Trójmiasto najniżej w obu "
    "wariantach z łączeniem), ale poziom zależy od reguły; liczby nie są wielkościami bezwzględnymi.",
]

STATIONS = (
    "Stacje kolei mają w feedzie ogólnopolskim jeden punkt na wszystkie stanowiska (np. Wrocław Główny: 10 "
    "`stop_id` w jednym punkcie), więc położenie peronów nie jest znane. Przesiadka kolej–kolej na takiej stacji ma "
    "dojście „brak danych” (kolumna `n_pairs_platform_unknown`), czekanie jest liczone. Przesiadka kolej–tramwaj lub "
    "kolej–autobus to dojście do punktu stacji (zwykle budynek lub środek peronów; przypięcie do sieci do 300 m), "
    "nie do konkretnego peronu: dla dużych stacji to dolna granica rzeczywistego dojścia o nieznanej wielkości. Metro "
    "warszawskie ma osobne punkty peronów, ale ich wejścia i poziomy są w OSM tak dokładne, jak je zmapowano."
)

TIMED = (
    "Dla linii docelowej kursującej średnio co ≥ 15 min (6–20, na wybranym słupku) porównano rzeczywiste czekanie "
    "pasażerów linii A (po dojściu) z tym samym czekaniem przy rozkładzie A przesuniętym o 1, 2, …, h−1 min. Para jest "
    "kandydatem, gdy rzeczywisty rozkład daje czekanie krótsze niż co najmniej 90 % przesunięć i najwyżej połowę "
    "czekania przy losowym przyjściu. Bez koordynacji ok. 10 % par mieści się w najlepszych 10 % przesunięć "
    "przypadkiem, więc pojedynczy kandydat nie dowodzi skomunikowania; liczy się nadwyżka ponad 10 % w skali miasta. "
    "Nie rozpoznaje się kursów przechodzących (ten sam pojazd zmienia numer linii), które wyglądają jak idealne "
    "skomunikowanie."
)

CRITICAL = {
    "cities": [
        "**Czytanie krytyczne.**",
        "",
        "- **Typowa przesiadka 7–9 (wartości addytywne, pierwsze trzy kolumny).** W 20 największych zespołach: dojście "
        "1,5–2,9 min + czekanie 5,6–15,6 min = 8,1 min (Warszawa) do 17,4 min (GZM). Czekanie stanowi 69–90 % sumy. W Poznaniu i GZM średnia jest z 19 zespołów: jeden z 20 największych nie ma ruchu z dojściem i czekaniem w oknie. "
        "Średnie ważone wychodzą wyżej niż mediany w miastach z wieloma rzadkimi liniami (Łódź: czekanie 10,9 min wobec "
        "mediany 7,6): rozkład czekania jest prawoskośny, a waga „przyjazdy A × odjazdy B” nie usuwa rzadkich linii "
        "docelowych, bo częsta linia A daje dużą wagę także przesiadce na rzadką B (sprawdzono na Rondzie Rataje: "
        "mediana czekania w ruchach 14,9 min, średnia 16,8, średnia ważona 11,0). To zamierzone: suma ma się sumować, "
        "a mediana tego nie zapewnia.",
        "- **Najlepsza para słupków nie różnicuje miast.** W wariancie zgodnym z zadaniem (najlepsza para słupków dla "
        "każdej pary linii, bez kierunków) 91–98 % odjazdów przypada na zespoły z medianą dojścia ≤ 2 min, a mediana "
        "dla 20 największych węzłów to 0,0–1,4 min. Powód sprawdzono w danych: 44–73 % par linii ma najlepszą parę na "
        "tym samym słupku, bo linie jadą wspólnym odcinkiem; przesiadka w tym samym kierunku jest wtedy możliwa, ale "
        "zwykle niepotrzebna. Dlatego miary główne korzystają z wariantu z kierunkami (reguła 4); wariant najlepszej "
        "pary jest w tabelach i w warstwie.",
        "- **Czekanie decyduje bardziej niż dojście.** W 20 największych węzłach mediana dojścia z kierunkami to "
        "1,5–2,7 min, a oczekiwane czekanie 7–9 to 5,2 min (Poznań) do 15,0 min (GZM). GZM ma najkrótsze dojścia "
        "(1,5 min) i najdłuższe czekanie; zgadza się to z §15.2 raportu (linie GZM kursują rzadko i rozchodzą się na "
        "węzłach).",
        "- **Mediana zwykła a ważona.** Mediana po parach linii traktuje rzadką linię podmiejską tak samo jak tramwaj co "
        "5 min. Mediana ważona liczbą kursów jest zwykle niższa, o 0–8 min (np. Kraków Główny: 17,3 min zwykła wobec 9,3 ważonej "
        "przy najlepszej parze). Obie są w warstwie; do porównań węzłów o różnym udziale kolei bezpieczniej czytać "
        "ważoną.",
        "- **Warszawa i Trójmiasto mają najmniej odjazdów w zespołach „łatwych” (ok. 61–64 %).** Sprawdzono: w obu "
        "duże węzły to kompleksy wielopoziomowe (metro, SKM, dworce), gdzie dojście z kierunkami wynosi 2,3–3,8 min "
        "(Centrum 3,7; Dworzec Gdański 3,8; Gdańsk Główny 2,9; Gdynia Główna 2,9). Wynik zostaje.",
        "- **Przejścia przez jezdnię.** Mediana 1 przejście na ruch w 20 największych węzłach wszystkich miast poza GZM "
        "(0,5). Przy najlepszej parze mediana wynosi 0, bo wspólny słupek nie wymaga przejścia.",
    ],
    "osm": [
        "**Czytanie.** Tagowanie jest nierówne: we Wrocławiu tylko 67 % węzłów, w których chodnik przecina jezdnię, ma "
        "jakikolwiek tag przejścia, w Poznaniu 85 %. Na policzonych dojściach odsetek jest wyższy (88–94 %), bo w "
        "centrach przejścia są mapowane staranniej. Udział przejść z sygnalizacją (35–59 %) zależy więc częściowo od "
        "tagowania; jest w warstwie, ale nie w miarach miejskich. 9–22 % długości dojść biegnie osią jezdni (chodnik "
        "nie zmapowany osobno, najwięcej w GZM i Warszawie): tam przejścia przez boczne ulice są niewidoczne, więc "
        "liczba przejść jest zaniżona.",
        "",
        "**Windy.** Od 8 % (Kraków) do 36 % (Wrocław) węzłów `highway=elevator` w grafie pieszym to ślepe końce: "
        "winda jest podpięta tylko do jednego poziomu. Brak dojścia bez schodów (np. Wrocław Dworzec Główny 48 % ruchów "
        "ze ścieżką bez schodów, Gdańsk Główny 43 %, Gdańsk Wrzeszcz 28 %) znaczy więc „nie znaleziono w OSM”, a nie "
        "„nie istnieje”. W okolicy Wrocławia Głównego 5 z 6 wind w grafie to ślepe końce.",
    ],
    "timed": [
        "**Czytanie.** W każdym mieście 11–14 % par mieści się w najlepszych 10 % przesunięć, czyli tylko 1–4 pkt proc. "
        "ponad to, co daje przypadek. Rozkład jednego dnia nie pokazuje więc systematycznego skomunikowania linii co "
        "≥ 15 min w żadnym mieście. Najwięcej kandydatów jest w GZM (2,5 % par sprawdzonych), także na Katowice "
        "Dworzec (94 z 2 079 par); nie sprawdzono, ile z nich to kursy przechodzące lub zdublowane linie. Lista "
        "kandydatów: `timed_connections_possible.csv`; wynik przybliżony, nie do publikacji jako „skomunikowania”.",
    ],
}

CHECKS = [
    "**Czytanie krytyczne znanych węzłów** (każda wartość, która zaskakiwała, została sprawdzona w danych przed "
    "pozostawieniem):",
    "",
    "- **Rondo Mogilskie:** dojście z kierunkami 2,5 min, 45 % ruchów po schodach, ale 100 % ma też drogę bez schodów. "
    "Zgadza się z opisem węzła w TMiR 6/2017 (tramwaje na dolnej płycie, wszędzie pochylnie, schody ruchome lub windy).",
    "- **Rondo Grunwaldzkie i Borek Fałęcki: najlepsza para 0,1 i 0,0 min.** Sprawdzono: większość par linii ma "
    "wspólny słupek (37 % i 54 % par). Wariant z kierunkami daje 2,1 i 2,4 min. Borek Fałęcki ma czekanie 7–9 23,5 min "
    "(mediana zwykła): większość z 25 linii to rzadko kursujące autobusy; ważona kursami 14,7 min.",
    "- **Wrocław, Dworzec Główny: dojście 6,2 min z kierunkami, P90 8,5 min, ruchy bez schodów 48 %.** Najdłuższe "
    "dojście wśród znanych węzłów. Sprawdzono: zespół obejmuje dworzec autobusowy na Suchej i tramwaje na "
    "Piłsudskiego po dwóch stronach stacji (średnia odległość między słupkami po sieci 498 m, w linii prostej 232 m). "
    "Brak drogi bez schodów wynika przynajmniej częściowo z niepołączonych wind w OSM (sekcja 7). Wynik dojścia "
    "zostaje; wynik „bez schodów” jest niepewny.",
    "- **Gdańsk Główny, Wrzeszcz, Gdynia Główna, Katowice Dworzec, Sosnowiec Główny: czekanie 7–9 13–21 min.** "
    "Sprawdzono: wśród linii docelowych dominują rzadkie linie podmiejskie i kolejowe (Gdynia Główna 46 linii, Katowice "
    "Dworzec 50). Mediana ważona jest niższa (9–16 min).",
    "- **Rondo Rataje (Poznań): 92 % par na wspólnym słupku.** W GTFS autobusy i tramwaje mają tu wspólne słupki; "
    "dojście z kierunkami 1,1 min. Układu w terenie nie sprawdzano.",
    "- **Piotrkowska Centrum: tylko tramwaj.** W zespole nie ma przystanków autobusowych (nie sprawdzano, gdzie "
    "zatrzymują się najbliższe autobusy); 13 linii tramwajowych, 79 % par na wspólnym słupku.",
    "- **Warszawa Centrum: 50 % ruchów z drogą bez schodów,** choć stacja metra ma windy. 20 węzłów windy w promieniu 400 m, "
    "z czego 6 to ślepe końce; nie rozstrzygnięto, czy brakuje windy, czy połączenia w OSM.",
    "- **Katowice Rynek: 36 linii, czekanie 15,0 min.** Sprawdzono: większość z 36 linii to autobusy kursujące w szczycie "
    "co ok. 30 min (czekanie 15 min), tramwaje mają 5,8–7,5 min; ważona kursami 9,4 min.",
]

SAMPLE = [
    "Plik `results/qa/access/transfers_sample_<agg>.csv` zawiera dla każdej z 200 par start–cel tylko liczbę "
    "przejazdów, przesiadek i minut pieszo, **bez miejsca przesiadki** (kolumny legs nie zapisano; nie ma ich też w "
    "`data/interim/access/<agg>/all/transfers_am/result.parquet`). Itinerariów z co najmniej jedną przesiadką jest "
    "41 (Łódź) do 64 (Warszawa) na miasto. Nawet z miejscem przesiadki dałoby to 0–3 przesiadki na węzeł, czyli nic "
    "poza listą „tu ktoś się przesiadł”. **Składowej „jak często najszybsze podróże przesiadają się w węźle” nie "
    "policzono.** Żeby ją policzyć, trzeba powtórzyć routing R5 z zapisem odcinków podróży i dużo większą próbą "
    "(rzędu 5–10 tys. par na miasto; koszt nieoszacowany). Znaczenie węzła opisują tu liczba linii, par i odjazdów.",
]

LIMITS = [
    "- **Brak wag pasażerskich.** Mediany są po parach linii (zwykła i ważona kursami), nie po przesiadających się "
    "pasażerach. AMPTI waży potokami z badań ankietowych; tych danych nie mamy.",
    "- **Czekanie rozkładowe, w pełnych minutach,** bez opóźnień, bez czasu postoju; przy częstych liniach różnica "
    "minuty to znaczna część wyniku.",
    "- **Dojście bez kar:** 5 km/h, bez czasu na światłach, schodach, windach i w tłumie; AMPTI mierzy czas w terenie "
    "(w Krakowie ok. 1 m/s z różnicami poziomów).",
    "- **OSM:** przejścia, schody, tunele i windy tylko tak, jak są zmapowane (sekcja 7). Dojście osią jezdni ukrywa "
    "przejścia; niepołączone windy ukrywają drogi bez schodów. Kładka (`bridge`) obejmuje też chodniki na mostach "
    "drogowych.",
    "- **Kolej:** perony nieznane (reguła 8). Dla przesiadek kolej–kolej dojście to brak danych.",
    "- **Zespół przystanków** to reguła geometryczna; wynik węzła zależy od niej (sekcja 6).",
    "- **Pary „równoległe”** usunięte regułą 80 % wspólnych zespołów; linie, które dzielą krótszy odcinek, liczą się "
    "jako para nawet tam, gdzie nikt się między nimi nie przesiada.",
    "- **Jeden dzień** (środa 2026-11-25), wszystkie feedy (28 nieoficjalnych, niesprawdzonych). Wariant feedów "
    "oficjalnych nie był liczony.",
    "- **Do czego nie używać:** do rankingu węzłów lub miast o podobnych wynikach, do oceny konkretnej przebudowy, "
    "jako zamiennika audytu AMPTI.",
]

NOT_VERIFIED = [
    "- Czy brak drogi bez schodów na dużych stacjach (Wrocław Główny, Gdańsk Główny i Wrzeszcz, Warszawa Centrum) to "
    "brak w OSM, czy w rzeczywistości.",
    "- Położenia peronów kolejowych i dojścia na perony; pary kolej–kolej mają dojście „brak danych”.",
    "- Kandydatów na skomunikowania (czy to kursy przechodzące, dublowane linie, czy rzeczywista koordynacja).",
    "- Zgodności sygnalizacji i rodzaju przejść z terenem.",
    "- Wariantu feedów oficjalnych i dni innych niż środa referencyjna.",
    "- Pozostałych prac AMPTI dla Krakowa: Baran i Bryniarska, TMiR 3/2022 i 7/2022 (Rondo Grunwaldzkie, Podgórze "
    "SKA) i pracy metodycznej z TMiR 6/2014 nie udało się pobrać (serwer yadda.icm.edu.pl odmawia dostępu, kopia na "
    "bibliotekanauki.pl pod sprawdzonym numerem to inny artykuł).",
    "- Wyniku dla „Kraków Główny” wobec oceny AMPTI węzła „Dworzec Główny” z 2015 r.: oceniany wtedy węzeł to "
    "przystanki przy Basztowej, Lubiczu, Westerplatte i Pawiej, a układ linii od 2015 r. się zmienił.",
]


# Reading of the revision sections (pipeline.transfer_md_rev); numbers from the run of 2026-11-24 (code version .3).
REV = {
    "conn": [
        "**Czytanie.** Czekanie po rzeczywistym przyjeździe linii dowożącej jest średnio takie samo jak czekanie przy "
        "losowym przyjściu: różnica w 20 największych węzłach wynosi od −0,07 do +0,01 min w każdym mieście. Rozkłady "
        "nie są więc ani skomunikowane, ani „rozjechane”: przyjazd linii dowożącej trafia w losowe miejsce odstępu linii "
        "odjazdowej. Sprawdzono, że to nie artefakt definicji: na tym samym zbiorze ruchów mediana czekania na przesiadkę "
        "jest wyraźnie niższa od średniej (Warszawa 4,0 wobec 5,6 min, GZM 11,7 wobec 15,6 min), a 90. percentyl "
        "prawie dwa razy wyższy (10,6–28,9 min), czyli rozkład jest prawoskośny tak, jak przy przyjściu losowym. "
        "Wniosek z sekcji 3 się nie zmienia: o długości przesiadki decyduje częstotliwość linii docelowej.",
        "- P90 pokazuje to, czego średnia nie pokazuje: w Trójmieście i GZM co dziesiąta przesiadka w największych "
        "węzłach kosztuje ponad 21 i 28 min czekania, w Warszawie 10,6 min.",
        "- Ograniczenie: czasy z rozkładu w pełnych minutach, bez opóźnień; przyjazd linii A to przyjazd na pierwszy "
        "słupek jej przejazdu przez zespół, odjazd B to odjazd z ostatniego, więc dla linii z dwoma słupkami w zespole "
        "czas może być przesunięty o 1–2 min.",
    ],
    "gtt": [
        "**Czytanie.** W 20 największych węzłach uogólniony czas przesiadki wynosi od 16,3–30,5 min (Warszawa) do "
        "30,2–44,0 min równoważnych jeździe (GZM). Stała kara (5–18 min) jest tego samego rzędu co ważone czekanie "
        "(8–23 min), a ważone dojście dodaje tylko 2–5 min. Szerokość pasma (14 min w każdym mieście) wynika prawie "
        "w całości z niepewności kary, nie z danych o węzłach; różnica między miastami (do 14 min) to prawie w całości "
        "różnica czekania. Pasmo potwierdza wniosek przeglądu: czekanie, nie dojście, rozstrzyga porównanie miast.",
        "- Kara jest jedna dla wszystkich ruchów (bez rozróżnienia autobus–tramwaj–kolej): Ortelli i in. 2026 pokazują, "
        "że kary zależne od środka mierzą głównie preferencję środka, a nie samą przesiadkę.",
        "- Pasmo nie jest wskaźnikiem jakości węzła i nie służy do rankingu; dla dwóch węzłów o tym samym dojściu i "
        "czekaniu jest identyczne, bo kara nie zależy od węzła.",
    ],
    "w6": [
        "**Czytanie.** Tagi OSM pozwalają nadać klasę W6 92–97 % przejść na policzonych dojściach; w całym grafie "
        "pieszym 59–79 % węzłów, w których chodnik przecina jezdnię, ma tag klasy na samym węźle (Wrocław najniżej). "
        "Niewyznakowanych przejść na dojściach jest 2–5 %, nieznanych 3–8 %. Średni wynik W6 na dojściach to 54–70 % "
        "przy sygnalizacji liczonej jako 70 % i 47–57 % przy 50 %; najniżej w GZM, gdzie tylko 23 % przejść na "
        "dojściach ma sygnalizację (Kraków i Łódź 52 %), a 48 % to zebry.",
        "- Udział przejść bezkolizyjnych (10–26 %) obejmuje przejścia podziemne i tunele stacji metra i kolei, którymi "
        "prowadzi najkrótsza droga; dlatego Warszawa Centrum ma W6 93 %, a Sosnowiec Główny 100 % (dojście tunelem pod "
        "torami, zero przejść w poziomie jezdni). Kładki nad torami nie są wykrywane (tory nie należą do grafu).",
        "- Sprawdzono Rondo Mogilskie (W6 34 %): w drogach macierzy jest 14 przejść, wszystkie to zebry bez sygnalizacji "
        "przez torowisko i jezdnie na poziomie tramwajów; Rondo Grunwaldzkie (70 / 50 %): 18 przejść z sygnalizacją i 1 "
        "bez klasy. Zgodności z terenem nie sprawdzano.",
        "- Ruch bez przejścia nie ma oceny W6, więc węzeł, w którym wszystkie przesiadki są na wspólnym słupku, ma W6 "
        "„brak danych” i 0 przejść: obie liczby trzeba czytać razem.",
    ],
    "freq": [
        "**Czytanie.** Ruchów, w których obie linie kursują w szczycie co 10 min lub częściej, jest mało poza Warszawą "
        "(10,4 % ruchów, 17 % w 20 największych węzłach) i Poznaniem (6,7 %, 17 %); w Krakowie 1,2 %, we Wrocławiu, "
        "Łodzi, Trójmieście i GZM poniżej 1 %. Przy progu 15 min udział rośnie do 17–33 % w pięciu miastach, ale w "
        "Trójmieście (6,7 %) i GZM (1,2 %) zostaje mały. To jest ten zbiór przesiadek, który literatura (Walker, Mees, "
        "SNAMUTS) uważa za „tanie” i na którym opiera się sieć z przesiadkami.",
        "- Próg 10 min jest ostry: linia co 10 min ma w oknie 7–9 dokładnie 12 kursów, więc jeden kurs mniej (np. co "
        "10–11 min) wyklucza ruch. Wrocław (tramwaje zwykle co 12 min) i Łódź (co 12–15 min) mają przez to prawie zero; "
        "próg 15 min jest odporniejszy.",
        "- Udział liczony po ruchach bez wag: rzadkie linie podmiejskie zwiększają mianownik, zwłaszcza w GZM (105 tys. "
        "ruchów).",
    ],
    "timed": [
        "**Czytanie. Czy coś wykryto?** W dzień nie. (a) W parach linii kursujących co ≥ 15 min udział w najlepszych "
        "10 % przesunięć wynosi 11,2–12,8 %, czyli 1–3 pkt proc. ponad przypadek. Przy dziesiątkach tysięcy par jest to "
        "„istotne” w teście dwumianowym, ale pary nie są niezależne (te same linie w wielu zespołach), a zysk "
        "praktycznie zerowy: średnie czekanie rzeczywiste jest o 0,2–1,1 min krótsze od czekania przy losowym przyjściu. "
        "Wysokie udziały tramwaj → tramwaj w Warszawie (40 %) i Poznaniu (50 %) dotyczą rzadkich kursów tramwajowych "
        "(czekanie losowe ok. 51–52 min: zjazdy do zajezdni, kursy wieczorne), a nie linii w ruchu; nie sprawdzono, ile to "
        "kursy przechodzące. (b) Test pulsu w dzień: 0,4–1,0 % zespołów, czyli tyle, ile daje przypadek przy progu 0,99; "
        "żadne z miast nie ma w dzień węzła z pulsem linii rzadkich.",
        "- **Kontrola dodatnia działa.** W nocy test pulsu wskazuje węzły, w których linie nocne spotykają się o stałej "
        "minucie: Warszawa Dw. Centralny (61 % odjazdów w 3 minutach cyklu 30 min, o :15 i :45, wobec progu 27 %), "
        "Centrum i Metro Świętokrzyska; Wrocław Dworzec Główny i Dworzec Autobusowy; Łódź Kościuszki-6 Sierpnia; Poznań "
        "Most Teatralny i Rondo Kaponiera (o pełnej i pół godzinie). Test par w nocy też daje wyraźną nadwyżkę (20–54 % "
        "par w najlepszych 10 %, czekanie rzeczywiste 2–20 min krótsze od losowego). Detektor widzi więc puls, gdy puls "
        "istnieje; brak wyniku w dzień to brak koordynacji, nie słabość testu.",
        "- **Dlaczego test par jest w nocy słabszy od testu pulsu.** Na Dworcu Centralnym rozkład koduje spotkanie jako "
        "przyjazd = odjazd w tej samej minucie (:15) na różnych słupkach, bez postoju; po dodaniu dojścia przyjeżdżający "
        "„spóźnia się” na odjazd, więc w teście par tylko 20 % par na Centralnym trafia do najlepszych 10 %. Test pulsu "
        "nie używa dojścia ani czasu przyjazdu, dlatego tę koordynację wykrywa. To ograniczenie danych GTFS (brak czasu "
        "postoju), nie sieci.",
        "- Puls przenosi się wzdłuż tras: zespoły o stałym czasie jazdy od węzła pulsu też „pulsują” (np. Pl. Zawiszy, "
        "Metro Ratusz Arsenał w nocy). Lista: `pulse_nodes.csv`; nocne pary: `timed_night_control.csv`.",
    ],
    "known": [
        "**Czytanie.** We wszystkich znanych węzłach czekanie na przesiadkę równa się czekaniu przy losowym przyjściu z "
        "dokładnością do 0,5 min, także na dworcach z liniami podmiejskimi (Kraków Główny 13,8 wobec 13,3 min, Katowice "
        "Dworzec 14,7 wobec 14,7). P90 przekracza 30 min na Krakowie Głównym, Borku Fałęckim, Gdańsku Głównym, "
        "Wrzeszczu i Sosnowcu Głównym: tam co dziesiąta przesiadka to czekanie na rzadką linię. Pasmo uogólnionego "
        "czasu wynosi od 12,1–25,7 min (Dworzec Główny Zachód w Krakowie) do 30,9–44,3 min (Sosnowiec Główny). "
        "Wysoki W6 w węzłach z przejściami podziemnymi (Centrum 93 %, Dworzec Wileński 87 %, Sosnowiec 100 %) i niski "
        "tam, gdzie przechodzi się po zebrach (Rondo Mogilskie 34 %, Dworzec Główny Zachód 30 %). Ruchów częste × "
        "częste (≤ 10 min) jest najwięcej w Warszawie (do 33 % na Dworcu Wileńskim) i na Rondzie Kaponiera (30 %).",
    ],
    "detail": [
        "Rozmiar plików mieści się w limicie 3 MB (największy: Warszawa). Drogi są zapisane tylko dla par słupków, "
        "które są najlepszą parą któregoś ruchu z macierzy (do 8 kierunków przyjazdu × 8 kierunków odjazdu, plus 10 "
        "najcięższych ruchów); geometria uproszczona z tolerancją 1,5 m. Na mapie nie sprawdzano wyglądu (brak "
        "podłączenia w `web/`, patrz `web/src/features/nodes/README.md`).",
    ],
}


def AMPTI(kn: pd.DataFrame) -> list[str]:
    def row(label):
        x = kn[(kn.interchange == label) & (kn.rule == "main")].iloc[0]
        return x

    m = row("Rondo Mogilskie")
    d = row("Dworzec Główny Zachód (Basztowa, Pawia)")
    b = row("Borek Fałęcki")

    def f(v, dd=0):
        return f"{float(v):.{dd}f}".replace(".", ",")

    return [
        "Źródło: Czekała K., Bryniarska Z., „Ocena wskaźnikowa wybranych węzłów przesiadkowych publicznego transportu "
        "zbiorowego w Krakowie”, Transport Miejski i Regionalny 6/2017, s. 5–10, tabela 5 (wersja AMPTI z 8 "
        "wskaźnikami; ankiety i audyt w kwietniu 2015 r.; plik w `data/raw/ampti_tmir/` z `SOURCE.json`). Porównywalny "
        "jest tylko wskaźnik W2 (zwartość węzła); W1 i W3–W8 wymagają audytu w terenie.",
        "",
        "| Węzeł | AMPTI 2015: średnia arytmetyczna odległość między przystankami, m | AMPTI: odległość ważona potokiem, m | AMPTI: czas ważony potokiem | Nasza średnia odległość między słupkami po sieci OSM, m | To samo w linii prostej, m | Nasze dojście z kierunkami, mediana, min | Nasze dojście, najlepsza para, mediana, min |",
        "|---|---|---|---|---|---|---|---|",
        f"| Rondo Mogilskie | 317,8 | 98,4 | 1:34 | {f(m.stops_mean_walk_m)} | {f(m.stops_mean_straight_m)} | {f(m.walk_dir_min_median, 1)} | {f(m.walk_min_median, 1)} |",
        f"| Dworzec Główny (2015: Basztowa, Lubicz, Westerplatte, Pawia; u nas „Dworzec Główny Zachód”) | 159,0 | 23,0 | 0:27 | {f(d.stops_mean_walk_m)} | {f(d.stops_mean_straight_m)} | {f(d.walk_dir_min_median, 1)} | {f(d.walk_min_median, 1)} |",
        f"| Borek Fałęcki | 186,0 | 197,7 | 3:00 | {f(b.stops_mean_walk_m)} | {f(b.stops_mean_straight_m)} | {f(b.walk_dir_min_median, 1)} | {f(b.walk_min_median, 1)} |",
        "",
        "- **Co jest porównywalne.** Średnia odległość między przystankami węzła: u nich między przystankami (stanowiskami "
        "oznaczonymi A1, T1, …) po drogach dojścia zmierzonych w terenie, u nas między słupkami GTFS po sieci OSM. "
        "Kolejność się zgadza: Mogilskie największe, Dworzec Główny i Borek Fałęcki mniejsze. Nasze wartości są niższe "
        "o 18–25 %: słupków jest więcej niż ich przystanków (Mogilskie: 18 wobec 9), więc więcej par leży blisko, a "
        "pochylnie i schody między poziomami są w OSM krótsze niż w pomiarze terenowym.",
        "- **Co nie jest porównywalne.** Wartości ważone potokiem pochodzą z 3 966 ankiet; my nie mamy potoków. Nasza "
        "mediana po parach linii z kierunkami (Mogilskie 2,5 min, Borek Fałęcki 2,4 min) jest bliższa ich czasom ważonym "
        "(1:34 i 3:00) niż mediana najlepszej pary, która w Borku wynosi 0 min, bo większość linii autobusowych ma tam "
        "wspólne stanowisko, a przesiadki tramwaj–autobus (główny potok wg ankiet) to mniejszość par linii.",
        "- **Różnica czasu.** Ankiety i audyt z 2015 r., sieć OSM z 2026 r., linie z rozkładu 2026; Dworzec Główny "
        "obsługiwało wtedy 13 linii, nasz zespół „Dworzec Główny Zachód” ma 9.",
        "- **Rondo Grunwaldzkie i Podgórze SKA** (Baran, Bryniarska, TMiR 3/2022 i 7/2022): tekstu nie udało się "
        "pobrać, porównania nie ma. Nasze wartości: Rondo Grunwaldzkie dojście z kierunkami "
        f"{f(row('Rondo Grunwaldzkie').walk_dir_min_median, 1)} min, średnia odległość między słupkami "
        f"{f(row('Rondo Grunwaldzkie').stops_mean_walk_m)} m; Podgórze SKA "
        f"{f(row('Podgórze SKA').walk_dir_min_median, 1)} min i {f(row('Podgórze SKA').stops_mean_walk_m)} m.",
    ]
