# ITDP „People Near Frequent Transport" (PNFT): dokładna definicja

Dostęp do źródeł: 2026-11-23. Wszystkie źródła poniżej są **pierwotne** (ITDP), chyba że zaznaczono inaczej.

## 1. Podsumowanie (parametry)

| Parametr | Wartość w Atlasie | Źródło |
|---|---|---|
| Dojście | **500 m po sieci pieszej OSM** (buforowanie po sieci od najbliższego węzła przystanku) + 100 m bufor absolutny, dziury < 10 000 m² wypełniane | metodologia, Indicator 7.3 i Appendix A1–A5 |
| Próg odstępu | **średni odstęp (mean headway) ≤ 10 min** (kod: `headway <= headwaylim`, `headwaylim = 10`; tekst metodologii mówi raz „every ten minutes or less", raz „less than ten minutes") | `funs/gtfs_parser.py` l. 111; `funs/pedestriansfirst.py` l. 161 |
| Okno godzin | **07:00–21:00** (`headway_start_time='07:00:00'`, `headway_end_time='21:00:00'`) | `funs/gtfs_parser.py` l. 94–95; metodologia: „throughout the day (7:00am to 9:00pm)" |
| Dzień | **dzień roboczy**: pierwszy tydzień ważności feedu, **pon–pt** (`get_first_week()[0:5]`), wynik uśredniony po 5 dniach | `funs/gtfs_parser.py` l. 88, 110 |
| Kierunki | **w kodzie kierunki NIE są rozdzielane** (`split_directions = False`). Opis publiczny („service in both directions", wpis ITDP z 2024-07-24) **nie ma odzwierciedlenia w kodzie** | `funs/gtfs_parser.py` l. 96 |
| Agregacja linii | **wszystkie linie i oba kierunki sumowane na `stop_id`** (jedna lista odjazdów z przystanku, odstępy między kolejnymi odjazdami) | gtfs_kit `compute_stop_stats` (poniżej) |
| Wielu przewoźników | każdy feed GTFS analizowany **osobno**; przystanki z różnych feedów nie są łączone (metodologia sama to przyznaje) | metodologia, Indicator 7.2 |
| Ludność | GHSL GHS-POP (wydanie 2022), siatka 1 km Mollweide, średnia gęstość × powierzchnia wielokąta | metodologia Appendix A6, „About data" |
| Granice | agglomeracje z GHS-UCDB (R2024A wg metodologii; „About data" mówi o wydaniu 2019 — **niespójność w źródle**), tylko > 500 tys. mieszk. | metodologia General Topic 1a; about_data |

## 2. Kluczowe ustalenia dla naszego projektu (do zapisania w RAPORT.md)

1. **Okno ITDP jest ustalone: 07:00–21:00** (brief §4.5 zakładał niejawne okno i fallback 6:00–20:00; fallback nie jest potrzebny, ale okno DG REGIO 6:00–20:00 różni się o 1 h od ITDP).
2. **Kierunki łączone.** Przystanek z dwoma kierunkami po 20 min (słupek na jednym przystanku, jeśli oba kierunki mają ten sam `stop_id`) wychodzi jako ~10 min. W praktyce zależy to od tego, czy feed ma osobne `stop_id` per kierunek (w polskich feedach zwykle tak: osobne słupki, więc efekt jest mniejszy, ale na pętlach, stacjach kolejowych i przystankach „parent" będzie widoczny). To jest rozbieżność między opisem a kodem; zalecam raportować wariant „zgodny z kodem" i wariant „per kierunek".
3. **Średni odstęp, nie liczba odjazdów w każdej godzinie.** Kod liczy średnią z różnic między kolejnymi odjazdami w oknie. Przystanek z 4 odjazdami o 7:00–8:00 i długą przerwą w środku dnia może przejść, choć w pustych godzinach nie jest „częsty"; nie ma wymogu równomierności. (Wniosek z kodu, nie z dokumentu.)
4. **Wartość odjazdów:** README repozytorium podaje „6 departures / hour or better" (= 10 min); strona `naindicators.itdp.org` (inny produkt ITDP, Ameryka Północna) mówi o „five departures per hour 7 a.m.–9 p.m." — to **nie jest** definicja Atlasu.
5. Próg „≤ 10" (kod) vs „< 10" (tekst metodologii, Indicator 7.2): różnica pomijalna, ale wartość graniczna 10,0 min przechodzi w kodzie.
6. Atlas bierze feedy „najnowsze" z Mobility Database (nie z dnia referencyjnego); okno pierwszego tygodnia ważności feedu, nie konkretnego dnia. Nasza replikacja na dniu referencyjnym nie będzie więc dokładnie porównywalna.
7. PNRT (kolejność odniesienia): 1 km po sieci od stacji metra / LRT (w tym tramwaj i „light rail" wg kategoryzacji ITDP) / BRT z oceną; kolej regionalna tylko gdy wskazana w `regionalrail.csv` lub ≤ 20 min w ciągu dnia; dane z Transit Explorer, nie z GTFS. **Uwaga:** ITDP kategoryzuje „light rail" i „tramway" jako LRT („We categorize 'light rail' and 'tramway' as LRT"), więc **w Atlasie tramwaje mogą wchodzić do PNRT** (o ile system jest w Transit Explorer). To zawęża różnicę wobec brief §4.5: nasz wariant „tylko szynowe" różni się od PNRT głównie kolejami i brakiem filtra „dedykowane pasy", ale nie tramwajem jako takim. Czy Transit Explorer klasyfikuje konkretne polskie sieci tramwajowe jako LRT: nie zweryfikowano.

## 3. Cytaty z kodu

Repozytorium: `https://github.com/ITDP/pedestriansfirst`, **commit `b124b7ffe04a61b27dc2a594ef06b793f44a8c0a`** (HEAD gałęzi `master` w dniu 2026-11-23; merge PR #1 z 2025-08-19 „New code for 2023/2024"). Pobrane przez `raw.githubusercontent.com/.../b124b7f.../<ścieżka>` (nie przez klon).

`funs/gtfs_parser.py`, l. 87–96 i 109–111 (wyliczenie statystyk przystanków):

```python
    try:
        days = feed.get_first_week()[0:5]
    ...
        stopstats = gk.stops.compute_stop_stats(feed, days,
                                      headway_start_time= '07:00:00',
                                      headway_end_time= '21:00:00',
                                      split_directions = False)
    ...
    for stop_id in stopstats.stop_id.unique():
        headway = stopstats.loc[stopstats['stop_id']==stop_id].mean_headway.mean()
        if headway <= headwaylim and headway != 0:
```

`funs/gtfs_parser.py`, l. 131: `def get_frequent_stops(hdc, year, folder_name, headwaylim = 20):` (domyślne 20 jest nadpisywane wywołaniem).

`funs/pedestriansfirst.py`, l. 161: `headway_threshold=10,#min`; l. 187: `'pnft': 500,` (słownik `distances`, bufory sieciowe w m); l. 336: `freq_stops, gtfs_wednesdays = get_frequent_stops(hdc = id_code, year = current_year, folder_name = folder_name, headwaylim = headway_threshold)`; l. 160: `buffer_dist=100,#buffer out from nodes, m`.

Biblioteka `gtfs_kit` (`mrcagney/gtfs_kit`, `gtfs_kit/stops.py`, gałąź master w dniu dostępu; wersja używana przez ITDP nie jest przypięta w repo — nie zweryfikowano): w `compute_stop_stats` odjazdy z `stop_times` łączone z `trips`, grupowane po `stop_id` (przy `split_directions=False`), `dtimes` = posortowane `departure_time` w `[headway_start, headway_end]`, `headways = dtimes[i+1] - dtimes[i]`, `mean_headway = np.mean(headways)/60`. Dlatego wszystkie linie i kierunki z jednego `stop_id` tworzą jedną sekwencję. `get_first_week` (`gtfs_kit/calendar.py`): „first Monday–Sunday week (or initial segment thereof) for which the given Feed is valid".

Opis w README (`README.md`, ten sam commit): „People Near Frequent Transit: the percentage of people living within 500m walking distance of frequent transit (6 departures / hour or better)."

Uwaga: `run_parallel_2024.py` zawiera komentarz `# VOLTAR PRO PADRAO!!!` przy `'pnft'` (lista testowanych wskaźników) — ślad po ręcznym wyborze podzbioru do obliczeń; nie wpływa na definicję.

## 4. Metodologia (tekst Atlasu)

Źródło pierwotne: pliki „About" aplikacji Atlasu, repo `https://github.com/ITDP/atlas`, commit `0afefe9426c89a484a5f0ad7afe0fcf001560bb7`, ścieżki `app/www/about/about_methodology.html` i `about_data.html` (dostęp 2026-11-23). Aplikacja pod `https://atlas.itdp.org/` (Shiny; sama strona nie wystawia tekstu bez sesji).

Indicator 7 (cytat, skrócony): „People Near Frequent Transport measures the percentage of an analysis area's population that lives within 500m of a public transport stop served by service that comes every ten minutes or less throughout the day (7:00am to 9:00pm) -- that is, service with average headways of ten minutes or less."

Indicator 7.2: „We load each GTFS file with the Python gtfs_kit library, and for each file we use the compute_stop_stats function to count the total number of scheduled departures at each stop between 7:00am and 9:00pm. We include all stops with an average (mean) headway of less than ten minutes." Dalej: metoda traktuje każdy feed osobno; autorzy przyznają, że dwóch przewoźników po 12 min na tym samym rogu da faktycznie 6 min, czego nie da się policzyć, bo przystanki nie mają wspólnych identyfikatorów.

Indicator 7.1: feedy z katalogu Mobility Database (`sources.csv`), wybierane po nakładaniu się bounding boxów (> 0,1%), pobierane „latest file".

Wpis blogowy ITDP z 2024-07-24 (`https://itdp.org/2024/07/24/our-cities-need-more-people-near-frequent-and-rapid-public-transport/`, wtórny wobec metodologii): „service in both directions" i „10 minutes or less between vehicles during weekday services" oraz 500 m. Pojęcie „both directions" występuje tylko tu; **kod go nie implementuje** (patrz §2.2).

## 5. Wartości Atlasu dla polskich obszarów miejskich

**Nie uzyskano.** Powody:
- `https://atlas.itdp.org/` to aplikacja Shiny; wartości są dostępne tylko interaktywnie (przycisk Download w widoku miasta/wskaźnika, pliki CSV/GPKG), a duże zestawy „na życzenie" (`data@itdp.org`, wg about_data). Nie ma publicznego pliku danych w repozytorium (setup.R pobiera tylko stary próbnik `releases/download/mvp1/sample_3.zip`, który nie jest wydaniem 2024).
- Wyszukiwarka i strony ITDP nie podają liczb dla polskich miast. Wiadomo (wtórne): Praga i Wrocław na czele rankingu „People Near Frequent Transport" w Atlasie (Bloomberg CityLab 2024-07-05, `https://www.bloomberg.com/news/articles/2024-07-05/prague-wroclaw-top-the-list-in-a-global-atlas-of-sustainable-transit`; strona zwróciła 403, więc potwierdzone tylko z wyników wyszukiwania; EU Urban Mobility Observatory: `https://urban-mobility-observatory.transport.ec.europa.eu/news-events/news/progress-car-free-transportation-options-prague-and-wroclaw-top-new-idtp-global-atlas-sustainable-2024-07-25_en`). Procentów nie ma.
- Rok danych: Atlas uruchomiono 15 maja 2024 (ITDP, webinar); GTFS „najnowsze" z Mobility Database w chwili obliczeń, ludność GHS-POP 2022 (about_data). Dokładny rok GTFS per miasto: nie zweryfikowano.
- Definicja granicy: agglomeracja = obiekt GHS-UCDB (Urban Centre, progi GHSL, > 500 tys.), nie FUA; dodatkowo poziomy administracyjne OSM (admin_level 4–11). Dla polskich miast oznacza to zwykle „urban centre" (rdzeń zabudowany), a nie funkcjonalny obszar miejski.

**Zalecenie:** odczytać ręcznie z `https://atlas.itdp.org/` (dla Warszawy, Krakowa, Wrocławia, Poznania, Łodzi, Gdańska/Trójmiasta, Katowic: PNFT i PNRT, z zapisaniem daty i nazwy agglomeracji z listy) albo napisać do `data@itdp.org`. Do raportu: nie wpisywać liczb z pamięci.
