# Zwartość i potencjał transportowy polskich aglomeracji: brief dla agenta (Claude Code)

Przygotowano 23.11.2026 dla Bartosza Rajczyka. Cel końcowy to seria grafik na Facebooka (styl wg `claude/styleguide.md` w projekcie „Grafiki na social media”) oraz, jako produkt uboczny, przeglądalna mapa. **Agent liczy dane i robi wykresy kontrolne. Grafik do publikacji nie robi**, bo te powstają osobno na kanwie Design.

**Historia zmian (23.11.2026):**
- dodana faza 6, czyli warstwy dodatkowe (§13);
- dodany model repo i buildu (§14): liczenie lokalnie, wyniki w repo, CI tylko do deployu na GitHub Pages;
- poprawki po recenzji eksperckiej:
  - główny wynik dostępności to *transport performance* DG REGIO, a nie liczba bezwzględna (§4.6);
  - rower i pieszo są obowiązkowym punktem odniesienia;
  - poprawiona definicja ρ (§4.3), usunięty indeks Angela;
  - Gini i η liczone na stałej domenie i tylko do kontroli (§4.4);
  - PNFT liczone ze średniej z dnia, z wariantem kolejowym (§4.5);
  - maska pokrycia GTFS liczona z przystanków OSM (§6);
  - dodane okna poza szczytem, wykluczenie ferii i test anomalii rozkładu (§5);
  - kontrole z walidacją zewnętrzną zamiast założonego wyniku (§7);
  - dodane miary podaży i prędkości rozkładowej (§4.7);
  - miejsca pracy ze zbioru IGiPZ PAN zamiast przybliżenia z kubatury;
- wycięte: Rejestr Cen Nieruchomości, projekcja GHSL 2025, ogólnopolska warstwa gęstości. Faza 2 miast tylko w zakresie gęstości.

---

## 1. Co ma powstać

1. **Pipeline (Python) z krokiem budowania uruchamianym lokalnie** (§14), który dla każdej aglomeracji liczy miary z §4.
2. **Tabela miar per aglomeracja** (`results/metrics/metrics.csv` + `.json`). Każda liczba ma kolumny: źródło, data danych ludności, data rozkładu, siatka, domena.
3. **Warstwy** (GeoParquet, jeśli małe) i **kafle PMTiles** do mapy.
4. **Dane pod wykresy** (`results/charts/*.json`) i szkice PNG z matplotlib, tylko do kontroli (`results/qa/`).
5. **Mapa statyczna** na GitHub Pages (MapLibre GL + PMTiles). Dopiero w ostatniej fazie.
6. **`results/RAPORT.md`**: co policzono, jakie dane w jakiej wersji, co odrzucono i dlaczego, pokrycie GTFS, wyniki kontroli z §7.

## 2. Zakres geograficzny

**Faza 1 (pełny zakres):** Warszawa, Kraków, Wrocław, Poznań, Łódź, Trójmiasto, GZM.
**Faza 2 (tylko miary gęstości z §4.1–4.3, bez GTFS):** Szczecin, Bydgoszcz–Toruń, Lublin, Rzeszów, Kielce, Białystok.

**Granice:**
- Podstawa: **FUA z Eurostat Urban Audit 2021** (GISCO, `URAU` 2021, poziom FUA), czyli miasto + strefa dojazdów. Dodatkowo **rdzeń** (poziom `CITIES` / granica gminy).
- **Nie licz niczego na samych granicach administracyjnych** jako wyniku głównego. Powierzchnie gmin (Warszawa ~517 km², Kraków ~327, Wrocław ~293) mierzą przebieg granicy, a nie miasto.
- **GZM**: sprawdź, jak Eurostat dzieli konurbację (Katowice i ewentualne osobne FUA dla Gliwic, Rybnika, Bielska). Zaproponuj dwa warianty: (a) suma FUA przecinających się z Metropolią GZM, (b) granica Metropolii GZM (41 gmin). **Zatrzymaj się i zapytaj Bartora**, zanim zaczniesz fazy 2–3.
- **Trójmiasto**: sprawdź, czy jedna FUA (Gdańsk) obejmuje Gdynię i Sopot. Miasto jest liniowe i nadmorskie, więc wszystkie miary względem jednego centrum wymagają zastrzeżenia (§11).
- **Efekt krawędzi**: cele podróży i populacja „sąsiedztwa” zawsze z **FUA + bufor 15 km** (GHSL jest wszędzie), żeby mieszkańcy przy granicy FUA nie wypadali gorzej tylko dlatego, że cele leżą za nią (§4.6).

## 3. Dane

| Co | Źródło | Uwagi |
|---|---|---|
| Ludność, **1 km (główna dla miar gęstości)** | **NSP 2021, siatka 1 km** (GUS, Portal Geostatystyczny, ATOM `geo.stat.gov.pl/atom-web/atom/PD`; równoważnie Eurostat Census GRID 2021) | Dane spisowe. Podstawa dla §4.1–4.4. |
| Ludność, **100 m (dla dostępności i warstw)** | **GHS-POP R2023A** (JRC), **epoka 2020**. Mirror COG: `source.coop/nlebovits/ghsl` albo `s3://jrc-ghsl/ghs-pop/` (no-sign-request) | Dane modelowane (rozdział według kubatury zabudowy). Mollweide (EPSG:54009) → EPSG:2180. Zgodność z NSP 2021 sprawdzić (§7.1). Projekcji 2025 nie używać. |
| Teren zabudowany | **GHS-BUILT-S** (udział powierzchni zabudowanej, 100 m) | Do maski netto w §4.3–4.4. |
| **Miejsca pracy** | **Goliszek S. (IGiPZ PAN), „Spatially disaggregated working-age population and job estimates for seven Polish cities…”, Mendeley Data, v1, 29.09.2026, doi:10.17632/mr9ywkgd9t.1, CC BY 4.0** | Siatka 100 m. Gdańsk, Kraków, Łódź, Poznań, Szczecin, Warszawa, Wrocław; **brak GZM**. Liczby ze stref modeli ruchu, rozdzielone kubaturą niemieszkalną GHSL. Lata wejściowe różne per miasto, zasięg przestrzenny (miasto czy szerzej) do sprawdzenia w fazie 0. |
| Granice FUA | **GISCO Urban Audit 2021** (`gisco-services.ec.europa.eu/distribution/v2/urau/`) | |
| Sieć piesza i rowerowa; przystanki | **OSM**, PBF dla Polski (Geofabrik), przycięty `osmium extract` do FUA + bufor 15 km | R5 czyta PBF bezpośrednio. Przystanki OSM do maski pokrycia (§6). |
| Rozkłady (GTFS) | tabela niżej | |

**GTFS, stan rozpoznany 23.11.2026 (agent musi każdy feed pobrać i zweryfikować):**

| Aglomeracja | Feed | Uwagi |
|---|---|---|
| Warszawa | `mkuran.pl/gtfs/warsaw.zip` (nieoficjalny, z danych ZTM; zawiera m.in. metro i SKM) + `mkuran.pl/gtfs/wkd.zip` | Licencja: warunki ZTM Warszawa + ODbL dla kształtów busów. |
| Kraków | ZTP: `gtfs.ztp.krakow.pl/GTFS_KRK_A.zip` (autobusy) **i** `GTFS_KRK_T.zip` (tramwaje) | Dwa feedy do scalenia. Duży udział prywatnych przewoźników podmiejskich bez GTFS (§6). |
| Wrocław | UM Wrocław, otwarte dane (MPK + linie podmiejskie, m.in. DLA, Siechnice) | Ważność ~2 tygodnie: pobierać tuż przed liczeniem. |
| Poznań | ZTM: `ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile` | Okno ważności bywa kilkudniowe. |
| Łódź | MPK Łódź (zweryfikować URL) | |
| Trójmiasto | ZTM Gdańsk + ZKM Gdynia (osobne feedy) | |
| GZM | ZTM GZM, „wersja rozszerzona” z `otwartedane.metropoliagzm.pl`; stabilny mirror: `github.com/TransportGZM-GTFS-mirror/TransportGZM-GTFS-extended-ver/releases/latest/download/TransportGZM-GTFS.zip` | Feed bywa jednodniowy (start = end), więc data referencyjna musi wypaść w jego dniu. |
| Kolej (cała Polska) | `mkuran.pl/gtfs/polish_trains.zip` (z danych PKP PLK; wg mkuran.pl obejmuje m.in. SKM Trójmiasto, ŁKA, KMŁ, KD, KŚ, KM; zweryfikować) | **Deduplikacja** z feedami miejskimi (np. SKM w feedzie Warszawy): nie liczyć kursów podwójnie. Osobne feedy przewoźników (KMŁ, KD, KŚ) tylko, jeśli polish_trains czegoś nie ma. |

Pomocne katalogi przy szukaniu brakujących feedów: Mobility Database, Transitland, repo `public-transport/transitous` (`feeds/pl.json`).

**Znane dziury:** podmiejskie autobusy gminne i prywatni przewoźnicy w większości nie mają GTFS. Krajowy Punkt Dostępu (MMTIS) nie daje kompletnego zbioru. Konsekwencje w §6.

## 4. Miary

Każda miara liczona dla **FUA** i **rdzenia**, z zapisaną siatką i domeną. Wyniki gęstościowe zależą od rozmiaru komórki (MAUP), więc **nie porównywać liczb z różnych siatek**.

### 4.1 Gęstość ważona populacją („experienced density”)
`PWD = Σ(pᵢ · dᵢ) / Σ pᵢ`. **Główna wersja: siatka spisowa 1 km.** Pomocniczo GHSL 250 m. Dla kontrastu gęstość brutto (ludność / pole FUA). Odporna na granice. Kandydat na grafikę nr 1.

### 4.2 Profil gęstości
- Pierścienie co 1 km od centrum (do 40 km): ludność, pole zamieszkane, gęstość, **udział skumulowany**. **Na grafiki idzie krzywa skumulowana**, nie pojedynczy parametr.
- Gradient Clarka `D(r) = D₀ · e^(−b·r)` (regresja log-liniowa na pierścieniach 1–25 km, pierwszy km osobno) tylko do tabeli i QA, z R².
- **GZM i Trójmiasto osobnym panelem** (policentryczność, pierścienie nad morzem).
- Centra: stałe współrzędne w `config.yaml` (Warszawa: Rondo Dmowskiego; Kraków: Rynek Główny; Wrocław: Rynek; Poznań: Stary Rynek; Łódź: pl. Wolności; Trójmiasto: Gdańsk Główny; GZM: Katowice Rynek). Bartor może je zmienić.

### 4.3 Indeks dyspersji Bertauda ρ
Źródło: Bertaud & Malpezzi (2003).
`ρ = [Σ(pᵢ · distᵢ) / Σpᵢ] / (⅔ · R)`, gdzie R to promień koła o polu równym **terenowi zabudowanemu netto**.
- **Interpretacja:** ρ = 1 oznacza walec o **równomiernej** gęstości na kole. To nie jest optimum. Miasta z gęstością malejącą od centrum mają ρ < 1, a większe ρ oznacza ludność dalej od centrum niż przy równomiernym rozkładzie.
- **Maska terenu zabudowanego:** komórki GHS-BUILT-S 100 m z udziałem zabudowy ≥ X% (próg w configu, zaproponować i opisać), spójne z rdzeniem, bez wód. Nie używać GHS-SMOD (definiowany progiem ludności, obejmuje parki). **Licznik tylko z ludności w tej masce.**
- **GZM:** wariant z odległością do *najbliższego* z N centrów (lista w configu), oznaczony jako inna miara. **Trójmiasto:** wynik z zastrzeżeniem.

### 4.4 Gini i η (Volpati & Barthelemy 2018): tylko QA
- Liczyć **na stałej domenie** (maska z §4.3 albo koło o stałym promieniu), nie na FUA. Inaczej Gini mierzy głównie udział terenów niezamieszkanych w FUA.
- Gini normalizować przez G_max. η zależy od progu (LouBar) i rozdzielczości, więc zapisać oba.
- **Na grafiki nie idą.** Służą do kontroli i opisu policentryczności w RAPORT.md.

### 4.5 Ludność przy częstej komunikacji (PNFT i warianty)
**Wariant ITDP (PNFT).** Potwierdzone elementy definicji ITDP: dojście 500 m, obsługa w obu kierunkach, odstęp ≤ 10 min, dzień roboczy. **Okno godzin ITDP nie jest jawnie opisane:** sprawdzić w kodzie / metodologii Atlasu i zapisać w RAPORT.md. Jeśli się nie da, przyjąć **średnią częstotliwość 6:00–20:00** (jak DG REGIO) i to opisać.
- Dojście **po sieci pieszej OSM**. Bufor euklidesowy tylko jako wariant kontrolny.
- Częstotliwość per przystanek (grupa słupków / `parent_station`; słupki w promieniu ~100 m scalić) i per kierunek, **po deduplikacji kursów z różnych feedów**. **Uwaga:** suma linii w klastrze może zliczyć kilka rzadkich, rozchodzących się linii jako „częsty korytarz”. Policzyć też wariant „najczęstsza pojedyncza relacja” i opisać różnicę.
- **Krzywa zamiast jednej liczby:** odsetek ludności przy progach odstępu 5 / 10 / 15 / 20 / 30 min. Kandydat na grafikę.

**Wariant kolejowy (wzorowany na klasach DG REGIO).** Ludność ≤ 1 km od stacji kolei lub metra z **≥ 4 odjazdami/h**, w klasach < 4 / 4–10 / > 10 odjazdów/h (6:00–20:00). Bez niego próg ≤ 10 min wycina prawie całą kolej aglomeracyjną (KD, KMŁ, ŁKA) i krzywdzi miasta, w których szkieletem jest kolej.

**Nazewnictwo:** wariant „tylko szynowe” (tramwaj + metro + kolej) **to nie jest ITDP PNRT**. PNRT to 1 km od metra, LRT lub BRT. Na wykresach i w tabeli używać własnej nazwy.

Wynik: % ludności FUA i rdzenia, tylko w obszarze pokrytym danymi (§6). Warstwa „zasięg” do mapy.

### 4.6 Dostępność: *transport performance* (główny wynik)
Metoda wg Poelman, Dijkstra & Ackermans, *Sustainable and inclusive urban transport* (DG REGIO, WP 01/2020):
- **Accessibility**: ludność osiągalna w 30 / 45 min komunikacją + pieszo.
- **Proximity**: ludność w linii prostej w promieniu odpowiadającym 15 km/h: **7,5 km (30 min)** i **11,25 km (45 min)**.
- **Transport performance = accessibility / proximity × 100**, uśrednione po komórkach z wagą ludności.
- Średnie dla miast UE w tym raporcie: **24 (30 min) i 57 (45 min)**. Warszawa, Łódź i Poznań są w zbiorze, więc to gotowy benchmark (z adnotacją o innej metodzie i roku).

Dlaczego tak: liczba bezwzględna „mieszkańców osiągalnych w 30 min” mierzy głównie wielkość miasta, a odsetek ludności FUA zależy od rysunku granic. Performance oddziela jakość transportu od formy miasta.

**Parametry:**
- Narzędzie: **r5py** (Conveyal R5; wymaga **Java 21**).
- Pochodzenia i cele: centroidy komórek 250 m z ludnością > 0 (GHSL 2020). **Domena celów i proximity: FUA + bufor 15 km**, ta sama dla licznika i mianownika. DG REGIO ogranicza cele do urban centre; ta różnica musi być opisana przy benchmarku.
- **Okna:** 7:00–9:00 (główne) oraz **10:00–14:00, 20:00–22:00 i sobota 10:00–14:00**. Wynik = mediana z odjazdów co minutę (`time_window`). Max dojście 1 km, max czas 60 min.
- **Przesiadki:** raportować medianę liczby przesiadek; wariant z max 2 przesiadkami.
- **Integracja taryfowa:** R5 traktuje przesiadkę między przewoźnikami jako darmową. Przygotować tabelę integracji biletowej per aglomeracja (wspólny bilet: którzy przewoźnicy, czy kolej), **zweryfikować per miasto**, i policzyć wariant „tylko sieć objęta wspólnym biletem”.
- **Punkty odniesienia (obowiązkowe):** performance **pieszo** (30 min, promień 2,5 km) i **rowerem** (30 min, promień 7,5 km; R5 bike). Rower nie zależy od dziur w GTFS, więc to uczciwy punkt odniesienia. **Samochodu nie liczyć**: R5 nie zna korków.
- **Miejsca pracy** (7 miast, bez GZM): dodatkowo performance i liczba miejsc pracy osiągalnych w 30 / 45 min, ze zbioru Goliszek (§3). Zasięg przestrzenny zbioru sprawdzić; poza nim „brak danych”.
- **Z centrum:** nie startować z jednego punktu (Rynek w Krakowie i Wrocławiu to strefy piesze z kilkuminutowym dojściem do przystanku). Uśredniać po komórkach w promieniu 1 km od centrum albo startować z głównego węzła (w configu).
- Liczyć osobno per FUA (przycięty PBF + feedy tej aglomeracji + kolej).

### 4.7 Podaż i prędkość rozkładowa (z GTFS, od razu)
- **Wozokilometry na mieszkańca** (dzień referencyjny) per tryb i per godzina; wariant miejscokilometry, jeśli da się przypisać pojemność taboru (opisać założenia).
- **Rozkładowa prędkość eksploatacyjna tramwajów** z `stop_times` + długość z `shapes` (albo dopasowania do OSM): per linia, per miasto, rozkład godzinowy. Daje porównanie od razu, bez czekania na archiwum GTFS-RT (6b), które potem pokaże prędkość rzeczywistą.

## 5. Dzień referencyjny i powtarzalność

- Jeden **dzień roboczy (wt–czw) wspólny dla wszystkich feedów**, **poza świętami, okresem 24.12–6.01 i feriami zimowymi** w województwie danej aglomeracji (terminy ferii różnią się między województwami, więc sprawdzić w kalendarzu MEN). Jeśli feedy nie mają wspólnego dnia (krótkie okna: Wrocław, Poznań, GZM), dopuszczalny jest ten sam dzień tygodnia w różnych tygodniach, **z jawną adnotacją**.
- **Test anomalii:** wozokilometry w dniu referencyjnym vs mediana wozokilometrów dni roboczych w okresie ważności feedu. Odchylenie > 5% wyjaśnić (rozkład feryjny, objazdy, remont).
- Każdy pobrany plik zostaje w `data/raw/` z datą pobrania, URL i SHA-256 w `data/manifest.csv`, bo feedy znikają.
- Na każdym feedzie **MobilityData gtfs-validator**, liczba błędów do raportu. Sprawdzić, czy w dniu referencyjnym są kursy.
- **Rozjazd dat danych:** ludność 2020–2021, rozkłady 2026. Brakuje migracji po 2022 r. i nowych osiedli podmiejskich. **Każdy wynik i każda grafika podaje obie daty.**

## 6. Pokrycie danych: zasada uczciwości

To kluczowe dla wiarygodności profilu (styleguide §1: „uczciwość ponad efekt”).
- **Maska pokrycia GTFS liczona z przystanków, nie z gmin.** Przystanki z OSM (`highway=bus_stop`, `public_transport=platform`, `railway=tram_stop`, stacje) dopasować do przystanków GTFS w promieniu ~50 m. Wskaźnik pokrycia = % przystanków OSM z odpowiednikiem w GTFS, **per gmina i per pierścień od centrum**. Gmina z jedną linią ZTM nie może wyjść jako „pokryta”.
- Poza maską wynik transportowy to **„brak danych”**, nigdy 0.
- W `metrics.csv` dla miar z §4.5–4.7 podać **% ludności FUA w obszarze pokrytym**. Jeśli < ~85%, wynik oznaczyć jako niepełny, a do porównań używać wariantu „obszar pokryty” albo „rdzeń”.
- Opisać w RAPORT.md, które miasta są systematycznie zaniżone przez brak przewoźników podmiejskich.
- Na mapie obszar bez danych wyraźnie wyróżniony (szrafura / szary), z podpisem.

## 7. Kontrole przed oddaniem

**Zasada:** odchylenie od oczekiwań **uruchamia kontrolę danych**, a nie jest błędem z definicji. Wynik, który przeszedł kontrolę, zostaje, nawet jeśli zaskakuje.

1. **GHSL vs NSP 2021:** suma ludności GHSL 2020 per FUA i rdzeń vs NSP 2021 (siatka 1 km i BDL). Odchylenie > 5% opisać. Porównać rozkład na 1 km (korelacja, największe różnice).
2. **Walidacja zewnętrzna:**
   - PNFT porównać z wartościami z Atlasu ITDP, z adnotacją o innych granicach i danych;
   - performance porównać z raportem DG REGIO 2020;
   - duże rozbieżności wyjaśnić w RAPORT.md.
3. **Częstotliwość:** 10 przystanków o najwyższej liczbie kursów/h w każdym mieście. Duplikaty kolejowe i błędy scalania wyjdą tu od razu.
4. **Dostępność:** 3–5 par OD na miasto porównać z wyszukiwarką połączeń (Jakdojade / Google) w tym samym dniu i godzinie. Różnica > 20% → wyjaśnić.
5. **Trafność (jeśli są dane):** zestawienie performance i PNFT z udziałem komunikacji w podróżach z Kompleksowych Badań Ruchu poszczególnych miast. Lata i metodyki różnią się, więc wyłącznie jako opis, bez regresji.
6. Wykresy kontrolne PNG dla każdej miary i miasta w `results/qa/`.

## 8. Mapa (faza ostatnia)

- MapLibre GL JS + PMTiles (tippecanoe albo `pmtiles` CLI), statyczny katalog na **GitHub Pages** (§14.4).
- Warstwy (tylko w FUA): gęstość 250 m, zasięg częstej komunikacji (§4.5), performance 30 min (§4.6), maska „brak danych”, granice FUA. Panel z tabelą miar po kliknięciu w FUA.
- Wygląd zgodny ze styleguide: fonty **Schibsted Grotesk + Newsreader**, tło `#F1EFE9`, podkład wg §8.3 (ląd `#ECE9E2`, woda `#C9D6E0`, ulice białe), transport zbiorowy `#1D4ED8`. Skala sekwencyjna, jednobarwna, bez tęczy. Atrybucje: © współtwórcy OpenStreetMap, JRC GHSL, GUS, IGiPZ PAN (Goliszek), wydawcy GTFS (wg `attributions.txt`). Przy każdej warstwie daty danych (§5).
- Bez kickera nad tytułem i bez emoji (styleguide §1).

## 9. Kolejność pracy i punkty zatrzymania

| Faza | Zakres | Stop / raport |
|---|---|---|
| **0. Inwentaryzacja** | Pobierz granice FUA, siatkę NSP 2021, GHSL, GHS-BUILT-S, zbiór Goliszek, wszystkie feedy z §3. Tabela: feed → ważność, liczba tras, błędy walidatora, kursy w kandydackim dniu referencyjnym (z uwzględnieniem ferii), wstępne pokrycie przystanków (§6). Zasięg zbioru miejsc pracy. Tabela integracji taryfowej. | **STOP**: pokaż tabele, warianty GZM i proponowany dzień referencyjny; czekaj na decyzję Bartora. |
| **1. Gęstość** | §4.1–4.4 dla fazy 1 + kontrola §7.1. Bez GTFS. | Raport + QA. Wyniki mogą od razu iść na grafiki. |
| **2. Częsta komunikacja i podaż** | §4.5, §4.7 | Raport + top-10 przystanków + test anomalii. |
| **3. Dostępność** | §4.6 | Raport + pary OD z §7.4 + benchmark §7.2. |
| **4. Mapa** | §8 | Lokalny podgląd. |
| **5. Faza 2 miast** | tylko §4.1–4.3 | — |
| **6. Warstwy dodatkowe** | §13, każda osobno | **STOP przed każdą warstwą**: krótki plan (dane, zakres, koszt) i zgoda Bartora. |

Wyjątek: **kolektor GTFS-RT (6b) uruchomić od razu po fazie 0**, bo archiwum potrzebuje tygodni. Uruchomienie kolektora nie wymaga zgody; analiza zebranych danych już tak.

## 10. Technikalia

- Python 3.12+, `uv` lub `venv`; biblioteki: `rasterio`, `rioxarray`, `geopandas`, `shapely`, `pyproj`, `r5py`, `gtfs-kit` lub `partridge`, `osmium`, `pyarrow`, `matplotlib`. Java 21 dla R5 (`-Xmx` dopasowany do RAM; Warszawa z koleją potrzebuje kilku GB).
- Struktura i sposób uruchamiania: §14.
- Wszystkie odległości w EPSG:2180.
- Kod i komentarze po angielsku, `RAPORT.md` po polsku.

## 11. Czego nie robić / nie twierdzić

- Nie liczyć gęstości na granicach gmin jako wyniku głównego.
- Nie porównywać miar liczonych na różnych siatkach.
- Nie wpisywać 0 tam, gdzie nie ma GTFS.
- Nie podawać ρ, gradientu Clarka ani profilu jednocentrowego dla **GZM i Trójmiasta** bez wyraźnego zastrzeżenia.
- Nie dawać na grafiki Gini, η ani samego b Clarka.
- Nie nazywać wariantu „tylko szynowe” wskaźnikiem ITDP PNRT, a wskaźnika usług (6e) wskaźnikiem ITDP *People Near Services*.
- Nie podawać liczby bezwzględnej „mieszkańców w 30 min” jako miary jakości transportu (to miara wielkości miasta).
- Nie liczyć dostępności samochodem z R5 (brak korków).
- Nie twierdzić, że GHSL to dane spisowe.
- Nie podawać wyników bez dat ludności i rozkładu.
- Nie generować grafik „do publikacji”. Tylko dane i szkice QA.

## 12. Decyzje dla Bartora (agent pyta, nie zgaduje)

1. Wariant granicy GZM (§2).
2. Współrzędne centrów i węzłów (§4.2, §4.6). Agent proponuje, Bartor zatwierdza.
3. Dzień referencyjny (z feriami per województwo), jeśli feedy nie mają wspólnego dnia.
4. Próg udziału zabudowy w masce terenu zabudowanego (§4.3).
5. Tabela integracji taryfowej (§4.6): agent przygotowuje, Bartor potwierdza.
6. Czy mapa ma być publicznie linkowana od początku (repo i strona na GitHub Pages są publiczne z definicji, ale można jej nie linkować, dopóki nie przejdzie kontroli z §7).
7. Zgoda na każdą warstwę fazy 6 (§13). Gdzie ma działać kolektor GTFS-RT (która maszyna, czy może działać 24/7).
8. Scraping RWDZ i wniosek o dane SEWIK: tylko po decyzji Bartora.
9. Hosting ustalony: GitHub Pages, repo publiczne, PMTiles w repo (§14). Do decyzji: podkład zewnętrzny (OpenFreeMap) czy własny wycinek; własna domena (np. subdomena bartor.net przez CNAME) czy `*.github.io`.

## 13. Faza 6: warstwy dodatkowe

Każda warstwa to osobny krok buildu z własnym wpisem w `data/manifest.csv` i sekcją w RAPORT.md. Wspólne zasady: dane łączyć z siatką 250 m / FUA z faz 1–3; każdą liczbę opisać źródłem i datą; braki danych to „brak danych”, nie 0 (§6). **Nie rozszerzać zakresu poza opisany niżej bez pytania.**

### 6a. Dojazdy do pracy: macierz przepływów NSP 2021 + macierz czasu przejazdu
- **Źródła:** GUS, „Macierz przepływów ludności związanych z zatrudnieniem – NSP 2021” (XLSX, 31.01.2024); GUS, statystyka eksperymentalna „Oszacowanie czasu przejazdu i odległości pomiędzy gminami w Polsce w 2021 roku”. Granice gmin z PRG (GUGiK).
- **Wynik:** per aglomeracja liczba dojeżdżających do rdzenia, zasięg (gminy z ≥ X% pracujących dojeżdżających do rdzenia), średni czas i odległość dojazdu ważone przepływem; mapa przepływów.
- **Zastosowanie dodatkowe:** porównanie granic FUA z rzeczywistym zasięgiem dojazdów, czyli argument przy wyborze granic GZM (§2).
- **Uwagi:**
  - dane gminne, tylko pracownicy najemni, bez trybu dojazdu;
  - **dojazdy wewnątrz rdzenia są niewidoczne**;
  - sprawdzić i opisać, jakim trybem GUS liczył czasy przejazdu (prawdopodobnie drogowy, bez korków);
  - niczego nie twierdzić o podziale zadań przewozowych.

### 6b. Prędkość i punktualność rzeczywista: archiwum GTFS-Realtime
- **Źródła:** feedy pozycji pojazdów / trip updates tam, gdzie są: Warszawa (`mkuran.pl/gtfs/warsaw/vehicles.pb`), Kraków (ZTP), GZM, Szczecin, Wrocław (otwarte dane MPK / UM; zweryfikować format). Pozostałe sprawdzić w fazie 0.
- **Kolektor:** lekki proces pobierający co 20–30 s do dziennych plików Parquet (pozycja, trip_id, route_id, czas), działający nieprzerwanie, z logiem przerw. **Uruchomić zaraz po fazie 0.** Cel: min. 4 pełne tygodnie robocze.
- **Wynik (po zebraniu, za zgodą):** rzeczywista prędkość eksploatacyjna per linia tramwajowa i miasto, porównanie z prędkością rozkładową (§4.7), punktualność, odcinki najwolniejsze.
- **Uwagi:** różna częstotliwość odświeżania i jakość feedów; okresy remontów i objazdów wykluczyć albo opisać; nie mieszać prędkości eksploatacyjnej (z postojami) z prędkością na odcinkach.

### 6c. Zabudowa: BDOT10k / EGiB jako korekta GHSL
- **Źródła:** BDOT10k (GUGiK, budynki: funkcja, liczba kondygnacji), ewentualnie budynki EGiB (KIEG). Siatka NSP 2021 1 km jako kontrola.
- **Metoda:** dasymetryczne rozprowadzenie ludności z siatki 1 km na budynki mieszkalne proporcjonalnie do powierzchni zabudowy × liczba kondygnacji, potem agregacja do 250 m.
- **Wynik:** alternatywna siatka 250 m; powtórzenie §4.5–4.6 i tabela różnic względem GHSL. Jeśli różnice są istotne, Bartor decyduje, którą siatkę uznać za główną.
- **Uwagi:** budynki mieszane i akademiki zaburzają wynik; opisać reguły klasyfikacji.

### 6d. Kierunki rozwoju: pozwolenia (RWDZ) i plany ogólne
- **Źródła:** GUNB RWDZ (wyszukiwarka publiczna z mapą `wyszukiwarka.gunb.gov.pl`, warstwa także w Geoportalu, moduł Planowanie Przestrzenne). Plany ogólne gmin z Rejestru Urbanistycznego / Geoportalu (GML).
- **Najpierw sprawdzić:**
  - czy RWDZ da się pobrać hurtowo (API, WFS, zrzut na dane.gov.pl);
  - czy zawiera **liczbę mieszkań**, a nie tylko obiekty.
  Jeśli dostęp jest tylko przez mapę, **zapytać Bartora przed scrapingiem**.
- **Wynik:** odsetek nowych mieszkań (pozwolenia + zgłoszenia, ostatnie 3–5 lat) powstających poza zasięgiem częstej komunikacji (§4.5) i według performance (§4.6), per FUA. Z planów ogólnych: powierzchnia stref dopuszczających intensywną zabudowę mieszkaniową w zasięgu vs poza zasięgiem częstej komunikacji. Najmocniejszy potencjalny wątek publicystyczny, więc kontrola jakości tym ważniejsza.
- **Uwagi:** pozwolenie ≠ realizacja, podawać jako „wydane pozwolenia / zgłoszenia”. Plany ogólne: stan przyjęcia różny per gmina, więc tabela pokrycia jest obowiązkowa.

### 6e. Skutki i otoczenie: hałas, wypadki, zieleń, usługi
- **Hałas:** wziąć **dane END raportowane do EEA** (liczba mieszkańców w strefach Lden, aglomeracje > 100 tys.) zamiast liczyć od nowa z map. Drogi i tramwaje osobno. Opisać rundę i metodykę (CNOSSOS-EU) per miasto.
- **Wypadki:** SEWIK: publiczne są agregaty Policji. Sprawdzić, czy któreś miasto publikuje dane punktowe; jeśli nie, **przygotować dla Bartora projekt wniosku o udostępnienie informacji publicznej** (wypadki z pieszymi i rowerzystami, lokalizacja, data, skutki, 5 lat). Nie szukać nieoficjalnych kopii.
- **Zieleń:** Copernicus Urban Atlas 2021 (pokrycie terenu, warstwa drzew ulicznych; FlatGeobuf per FUA) → udział ulic z drzewami, zieleń publiczna w zasięgu 300 m.
- **Usługi podstawowe** (wzorowane na ITDP *People Near Services*, ale z inną definicją, więc pod własną nazwą): RSPO (szkoły podstawowe, przedszkola), rejestr podmiotów leczniczych (POZ), OSM (sklepy spożywcze, apteki). % ludności z kompletem usług w zasięgu 1 km pieszo po sieci. Kompletność OSM sprawdzić na próbie 2–3 dzielnic per miasto.
- **Wynik:** po jednej porównywalnej liczbie na miasto per temat + warstwa na mapę.

### Kolejność proponowana
6b (kolektor, od razu) → 6a → 6d → 6c → 6e. Bartor może zmienić kolejność.

## 14. Repo, build i deploy

**Zasada:** całe liczenie odbywa się **lokalnie, w kroku budowania uruchamianym ręcznie**, a wyniki trafiają do repo jak artefakty. GitHub Actions **nie liczy niczego**: robi tylko deploy webui (i ewentualnie szybkie sprawdzenia, §14.5).

### 14.1 Struktura

```
config.yaml              # FUA, centra, węzły, dzień referencyjny, okna, progi, wersje źródeł
pipeline/                # kod Pythona: moduły per krok
Snakefile  (albo Makefile/justfile, §14.2)
data/
  manifest.csv           # COMMIT: URL, data pobrania, SHA-256, licencja każdego źródła
  raw/  interim/         # NIE commitować (.gitignore): pobrane dane i pośrednie
results/                 # COMMIT: wyniki obliczeń
  metrics/               # metrics.csv, metrics.json (+ per faza)
  charts/                # JSON pod wykresy
  layers/                # GeoParquet warstw (tylko małe, §14.3)
  qa/                    # wykresy kontrolne PNG + raport walidatora GTFS
  RAPORT.md
tiles/                   # COMMIT: PMTiles (rozmiary pilnowane, §14.3)
web/                     # webui (MapLibre), statyczne; czyta results/ i tiles/
collector/               # kolektor GTFS-RT (6b), osobny proces, osobne dane
.github/workflows/deploy.yml
```

### 14.2 Krok budowania (lokalnie)
- Orkiestracja z **śledzeniem zależności**: rekomendowany **Snakemake** (reguły = kroki z §9/§13, jawne wejścia/wyjścia, przelicza tylko to, co się zmieniło). Alternatywa: `make`/`just` z plikami-stemplami z hashem wejść. Agent wybiera i uzasadnia w RAPORT.md.
- Komendy (przykład): `snakemake fetch`, `snakemake density`, `snakemake frequent`, `snakemake access FUA=wroclaw`, `snakemake extra_commute`, `snakemake tiles`, `snakemake all`.
- **Zmiana `config.yaml` albo nowej wersji feedu → przeliczenie tylko zależnych kroków.** Dostępność liczona per FUA, żeby nowy feed Poznania nie przeliczał Warszawy.
- Każdy krok zapisuje `_meta.json`: git SHA, hashe wejść z manifestu, data uruchomienia, czas trwania. Wynik bez `_meta.json` jest niekompletny.
- Wyniki deterministyczne: stałe seedy, posortowane wyjścia, stała precyzja liczb (np. 4 cyfry znaczące), żeby diff w gicie pokazywał prawdziwe zmiany.
- Commit wyników to osobny commit („results: <krok>, <data referencyjna>”). **Agent nie commituje ani nie pushuje bez polecenia.**

### 14.3 Co do gita, a co nie
- **Do gita:** kod, config, `data/manifest.csv`, `results/`, `tiles/`. Cel: repo poniżej ~500 MB.
- **Nie do gita:** surowe dane (`data/raw`, `data/interim`: odtwarzalne z manifestu), sieci R5, PBF-y, archiwum GTFS-RT, GeoParquety > ~20 MB.
- **PMTiles commitowane wprost.** Przy zakresie FUA pliki powinny mieć pojedyncze MB do kilkudziesięciu MB. Bez Git LFS i bez Release.
- Krok `tiles` wypisuje tabelę rozmiarów i **ostrzega**, gdy plik > 50 MB (próg ostrzeżenia GitHuba) albo suma `tiles/` > 200 MB. GitHub twardo odrzuca pliki > 100 MB.
- Historia rośnie z każdą wersją kafli: przebudowywać je tylko przy realnej zmianie danych. Jeśli `git count-objects -vH` pokaże repo > ~700 MB, agent zgłasza to i proponuje przeniesienie kafli do GitHub Release.
- **Licencje:** przed wrzuceniem czegokolwiek do publicznego repo sprawdzić warunki źródła (warunki ZTM Warszawa dla danych pochodnych, ODbL dla OSM, CC BY 4.0 dla zbioru Goliszek: atrybucja). Wyniki zagregowane zwykle są OK; surowych feedów nie redystrybuować.

### 14.4 Deploy na GitHub Pages (jedyne zadanie CI)

**Hosting na GitHub Pages, deploy przez własny workflow Actions** (`actions/upload-pages-artifact` + `actions/deploy-pages`), nie z gałęzi `gh-pages`. Workflow składa stronę z plików obecnych w repo; niczego nie liczy ani nie pobiera z zewnątrz.

- **Wyzwalacz:** push do `main`, gdy zmieni się `web/**`, `results/**` albo `tiles/**`; plus `workflow_dispatch`.
- **Kroki:** checkout → złożenie `site/` z `web/`, potrzebnych plików z `results/` i `tiles/` → upload artefaktu → deploy. Webui najlepiej czysty statyczny HTML/JS; jeśli bundler, to tylko szybki `npm ci && npm run build`.
- Workflow nie instaluje GDAL, Javy, R5 ani Pythona do obliczeń. Jeśli ich potrzebuje, liczenie przeciekło do CI.

**Limity GitHub Pages** (dokumentacja GitHub, XI 2026):
- strona ≤ 1 GB;
- deploy ≤ 10 min;
- miękki limit transferu 100 GB/mies.;
- na darmowym planie tylko z publicznego repo.

**Kafle:**
- Warstwy tylko w granicach FUA, jeden plik PMTiles na warstwę dla wszystkich FUA; podział per FUA dopiero po przekroczeniu progu ostrzeżenia.
- Atrybuty ograniczone do tego, co webui pokazuje; maxzoom dobrany do rozdzielczości (250 m → z12–13).
- **Podkład:** zewnętrzne darmowe kafle wektorowe bez klucza (np. OpenFreeMap, schemat OpenMapTiles) z własnym stylem wg styleguide §8.3. Alternatywa przy niestabilności: własny wycinek obszarów FUA (Protomaps basemap, `pmtiles extract`), z rozmiarem przedstawionym Bartorowi przed commitem.

**Przed pierwszym publicznym linkiem sprawdzić:**
- **Range requests:** GitHub Pages je obsługuje, ale na początku 2026 był błąd z Firefoksem (odpowiedzi 416 przy dalszych offsetach), według reprodukcji `bdon/ghpages-firefox-range-bug` naprawiony w marcu 2026. Przetestować w Firefoksie, Chrome i Safari (iOS), wynik do RAPORT.md.
- **Transfer:** oszacować transfer na typową wizytę i ile wizyt mieści się w 100 GB/mies. URL bazowy kafli w jednym miejscu konfiguracji, żeby w razie viralowego posta przełączyć kafle na Cloudflare R2 bez zmian w kodzie.
- **Cache:** nazwy plików PMTiles z wersją danych (np. `density250_2026-12-01.pmtiles`).

### 14.5 Opcjonalne lekkie sprawdzenia w CI (tylko za zgodą)
- Lint i testy jednostkowe na małych danych testowych (`tests/fixtures/`, kilka KB), limit joba 5 min.
- Walidacja schematu `results/metrics/metrics.json` i obecności `_meta.json`.
Żadnych pobrań danych źródłowych w CI.

### 14.6 Kolektor GTFS-RT
Nie jest częścią buildu ani CI. Osobny proces na maszynie Bartora (lub małym VPS-ie, do decyzji), zapisujący do katalogu poza repo. Build czyta z tego katalogu (ścieżka w `config.yaml`) i commituje tylko zagregowane wyniki.

## 15. Rekomendowane pierwsze grafiki (z faz 1–3)

1. **Gęstość ważona populacją** na spisowej siatce 1 km, FUA. Odporna na granice, dane spisowe.
2. **Skumulowany profil ludności według odległości od centrum.** GZM i Trójmiasto osobnym panelem. Pokazuje formę miasta bez jednej sztucznej liczby.
3. **Krzywa częstej komunikacji:** odsetek ludności przy progach 5–30 min (średnia 6–20, tylko obszar pokryty) + wariant kolejowy. Nie zależy od jednego progu, sprawdzalna względem ITDP.
4. **Transport performance 30 i 45 min:** komunikacja vs rower vs pieszo. Neutralna względem wielkości miasta, zgodna z metodą UE.
5. **Rozkładowa prędkość eksploatacyjna tramwajów** per miasto. Prosta, porównywalna, niezależna od dziur w feedach podmiejskich.

## Literatura i źródła metod (do RAPORT.md i stopek grafik)

- Clark C. (1951), *Urban Population Densities*, JRSS A.
- Bertaud A., Malpezzi S. (2003), *The Spatial Distribution of Population in 48 World Cities: Implications for Economies in Transition*.
- Volpati V., Barthelemy M. (2018), *The spatial organization of the population density in cities*, arXiv:1804.00855.
- Poelman H., Dijkstra L., Ackermans L. (2020), *How many people can you reach by public transport, bicycle or on foot in European cities? Measuring urban accessibility for low-carbon modes*, DG REGIO Working Paper 01/2020 (`ec.europa.eu/regional_policy/sources/work/012020_low_carbon_urban.pdf`).
- Poelman H., Dijkstra L. (2015), *Measuring access to public transport in European cities*, DG REGIO Working Paper 01/2015 (`ec.europa.eu/regional_policy/sources/work/2015_01_publ_transp.pdf`).
- ITDP (2024), *Atlas of Sustainable City Transport*, wskaźnik People Near Frequent Transport.
- Goliszek S. (2026), *Spatially disaggregated working-age population and job estimates for seven Polish cities with a 2025 allocation horizon*, Mendeley Data v1, doi:10.17632/mr9ywkgd9t.1.
- Schiavina M. i in., *GHS-POP R2023A*, JRC, doi:10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE.
- GUS, NSP 2021: siatka 1 km; macierz przepływów ludności związanych z zatrudnieniem.
