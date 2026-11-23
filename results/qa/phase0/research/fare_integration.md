# Integracja taryfowa: tabela per aglomeracja (brief §4.6)

Dostęp do źródeł: 2026-11-23. Wersja CSV: `fare_integration.csv` (te same wiersze, kolumny wg briefu). Legenda wiarygodności: **P** = dokument/strona organizatora lub przewoźnika (w tym portal miasta), **W** = wtórne (prasa, dokument gminy sąsiedniej, wyniki wyszukiwarki). „Zweryfikowano: tak" oznacza, że treść strony/dokumentu została odczytana w tej sesji i jest bieżąca lub datowana na 2025–2026; „nie" = dane częściowe, stare albo tylko z wyszukiwarki.

Ogólna uwaga: wszystkie konstrukcje są **częściowe**: bilet miejski honorowany na kolei obejmuje zwykle tylko bilety okresowe/czasowe i tylko wybrany obszar. R5 traktuje przesiadkę jako darmową niezależnie od biletu, więc wariant „sieć objęta wspólnym biletem" musi uwzględniać zakres obszarowy i typ biletu.

## 1. Warszawa

- **Organizator:** ZTM Warszawa (autobusy, tramwaje, metro). Źródło: https://warszawa19115.pl/-/wspolny-bilet-ztm-km-wkd (P, portal miasta; strona ZTM nie otwarta). Zweryfikowano: częściowo.
- **Wspólny Bilet ZTM-KM-WKD:** bilety **okresowe** ZTM (24-godzinne, 3-dniowe, weekendowe, 30-dniowe, 90-dniowe, seniorskie, dla dzieci z rodzin 3+) ważne w pociągach **Kolei Mazowieckich** i **WKD**; **nie** 20-minutowe i **nie** jednorazowe przesiadkowe 75/90 min (wyjątek: odcinek lotniskowy Lotnisko Chopina – Warszawa Płudy na linii KM RL).
- **Zakres KM:** w obszarze stref 1/2 ZTM, ograniczony m.in. stacjami: Sulejówek Miłosna, Otwock Śródborów, Zalesie Górne, Pruszków, Płochocin, Legionowo Przystanek, Legionowo Piaski, Zagościniec; stacje graniczne strefy 1: Warszawa Wola Grzybowska, Falenica, Jeziorki, Ursus Niedźwiadek, Gołąbki, Zacisze-Wilno, Mokry Ług. W pociągach przyspieszonych bilet ważny do ostatniej stacji strefy 1; strefa 2 zależy od postoju. Nie ważny w KM dalekobieżnych (Słoneczny, Dragon) i specjalnych.
- **Zakres WKD:** tylko Warszawa Śródmieście WKD – Opacz (cała strefa 1).
- **SKM:** odcinki lotniskowe S2 (Lotnisko Chopina – Wschodnia) i S3 (Lotnisko Chopina – Płudy) akceptują wszystkie bilety KM obejmujące stację docelową. Czy standardowy bilet ZTM jest ważny na wszystkich liniach SKM (S1, S9 itd.): **nie zweryfikowano** (wyniki niejednoznaczne). Należy sprawdzić, jakie linie ma w GTFS Koleje Mazowieckie / SKM.
- Bilet musi być aktywowany przed jazdą (kasowanie w ZTM, bramki metra, walidatory KM RL).

## 2. Kraków

Źródła: https://krakow.pl/komunikacja/14904,artykul,rodzaje-biletow.html (P, aktualizacja 2021-03-18: nieaktualne), https://krakow.pl/aktualnosci/273870,26,komunikat,od_1_sierpnia_nowy_bilet_metropolitalny.html (P, 2023).
- **Bilet WSPÓLNY 70-minutowy** (strefy I–III + KMŁ): nieograniczone przesiadki między pojazdami miejskimi i pociągami **Kolei Małopolskich (KMŁ)**, ale kolej tylko na odcinkach: Kraków Olszanica – Wieliczka Rynek Kopalnia oraz przystanki Kraków Batowice, Lubocza, Nowa Huta (stan 2021). Zakres obecny: nie zweryfikowano.
- **Zintegrowany Bilet** (okresowy): bilet miejski strefa I lub I–III + relacja kolejowa KMŁ/Polregio (II klasa pociągów regionalnych), cena = suma. Karta MKA / iMKA.
- **Bilet metropolitalny (od 2023-08-01):** okresowy, strefy I, I+II, I+II+III; bilet autobusowo-tramwajowy uprawnia też do kolei w gminach z porozumieniem; w komunikacie wymienieni KMŁ, Polregio i Koleje Śląskie. Lista gmin: nie podana.
- **Taryfa Aglomeracyjna Kraków** (KMŁ + Polregio, bilety strefowe, w tym 24 h): dokumenty z 2020–2022 znalezione w wyszukiwarce; nieaktualne, nie zweryfikowano.
- Wniosek: dla Krakowa jedyna **jednorazowa** integracja z koleją to 70-minutowy bilet WSPÓLNY na wąskich odcinkach; reszta to bilety okresowe. SKA/KMŁ w GTFS: sprawdzić nazwy agencji.

## 3. Wrocław

Źródła: https://www.wroclaw.pl/komunikacja/pociag-wroclaw-urbancard-czy-mozna-umowa-przedluzona-do-2030-roku (P, 2025-12-08) i https://www.wroclaw.pl/komunikacja/pociagiem-po-wroclawiu-na-urbancard-jeden-bilet-wystarczy-zasady (P, 2024). Zweryfikowano: tak.
- Bilety MPK Wrocław (Urbancard) ważne w pociągach **Kolei Dolnośląskich** i **Polregio** między stacjami/przystankami z „Wrocław" w nazwie oraz **Iwiny** (Jagodno), **od 2024-08-01**; umowa na **2026–2030** (ok. 241,7 mln zł, płaci Wrocław), podpisana 2025-12-08.
- **Typy biletów:** czasowe 24/48/72/168 h; okresowe imienne 7/30/60/90/180/365 dni + semestralne; okazicielskie 30/60/90 dni; pracownicze. Jednorazowych nie wymieniono. Bilet ograniczony do 2 linii nie uprawnia do kolei (2024).
- Poza granicami miasta KD nie honorują biletów MPK (nie zweryfikowano dla 2026). Wspomniano deklarację „wspólnego biletu aglomeracyjnego" Wrocławskiego Obszaru Metropolitalnego: brak szczegółów.

## 4. Poznań

Źródło: warunki taryfowe oferty BUS-TRAMWAJ-KOLEJ obowiązujące od 2024-12-15, https://polregio.pl/media/25932/warunki-taryfowe-oferty-bus-tramwaj-kolej-ważne-od-15122024.pdf (P, dokument przewoźnika, przeczytany lokalnie). Nowszej wersji (2026) nie znaleziono. Zweryfikowano: tak (stan XII 2024).
- **BTK:** miesięczny imienny bilet na pociągi KW i Polregio REGIO + komunikację ZTM Poznań (strefy A, B, C) + opcjonalnie MPK Gniezno. Siedem stref kolejowych A–G (do Wągrowca, Trzemeszna, Słupcy, Jarocina, Starego Bojanowa, Grodziska Wlkp., Nowego Tomyśla, Mokrza, Tarnowa Rogozińskiego); nie wydawany tylko na strefę kolejową A i strefę A ZTM.
- **Honorowanie w kolejowej strefie A** (Poznań w granicach miasta + Kiekrz): okresowe bilety sieciowe stref A ZTM zakodowane na PEKA/ELS/ELD/ELNA/aplikacji PEKA. Czasowe i jednorazowe: nie (nie wymienione).

## 5. Łódź

Źródła: https://lka.lodzkie.pl/wba-wspolny-bilet-aglomeracyjny/ (P, ŁKA), https://lka.lodzkie.pl/Honorowanie-biletow-komunikacji-miejskiej-w-Lodzi/ (P, bez daty, wpisy do XII 2025), https://www.intercity.pl/.../aglomeracja-lodzka-2026.html (P, PKP IC). Zweryfikowano: tak.
- **WBA (Wspólny Bilet Aglomeracyjny):** miesięczny; ważny w pociągach **ŁKA i ŁKA Sprinter** (oraz Polregio wg warunków Polregio od 2025-03-01: dokument nie czytany) oraz w komunikacji miejskiej Łodzi (strefy 1–2) i miast aglomeracji (Pabianice, Zgierz, Łask, Zduńska Wola, Sieradz, Stryków, Głowno, Łowicz); od **2025-12-14** nie honorowany w PKP Intercity. Zmiana oferty od 2026-09-01 (GazetaPrawna): **nie zweryfikowano**.
- **Bilety MPK-Łódź w ŁKA:** honorowane tylko w obszarze stacji **Łódź Lublinek, Radogoszcz Zachód/Wschód, Arturówek, Andrzejów**; nie bilety kupione w automacie i powiązane z kartą płatniczą ani płatności zbliżeniowe. Bilety strefowe ŁKA honorowane w pojazdach MPK w granicach Łodzi.
- Nie ma jednego „Lokalnego Transportu Zbiorowego" w odczytanych źródłach; brief używa tej nazwy: nie zweryfikowano.

## 6. Trójmiasto

Źródła: https://www.zukowo.pl/files/docs/wykaz_honrowanych_biletow.pdf (W: wykaz Gminy Żukowo od 2026-04-01), https://www.mzkzg.org/ (P, treść niepełna), https://systemfala.pl/... (wyniki wyszukiwania; strony zwracały 404). Zweryfikowano: częściowo.
- **MZKZG:** komunalny (ZTM Gdańsk + ZKM Gdynia + MZK Wejherowo) oraz **kolejowo-komunalny** (SKM + POLREGIO + jeden/dwóch/wszyscy organizatorzy) w wersjach **24 h, 72 h, 30-dniowy**; wariant miesięczny Gdańsk–Sopot i Gdynia–Sopot tylko na terenie tych miast. Ceny 24 h kolejowo-komunalnych: 48, 56 zł itd. (nie jednorazowe).
- **FALA** to system elektronicznego biletu/karty (sprzedaż biletów okresowych MZKZG); w Gdańsku bezpłatne przejazdy SKM/PKM/Polregio w granicach miasta dla posiadaczy Gdańskiej Karty Mieszkańca z imiennym biletem okresowym ZTM (wg wyszukiwarki; nie zweryfikowano po 2025-05-31).
- PKM, bilet jednorazowy z koleją i dokładne strefy: **nie zweryfikowano**.

## 7. GZM

Źródło: https://www.metropoliaztm.pl/en/s/bilety (P, ZTM GZM, bieżące, bez daty). Zweryfikowano: tak (zakres), nie (daty zmian).
- **Metrobilet:** Metro 24 h: wszystkie linie **Kolei Śląskich i Polregio** w GZM (w tym Tarnowskie Góry – Pyrzowice); 30-dniowe: Miasto 30 (gmina z min. 2 stacjami), 2 Miasta 30, Obszar 30 (3–6 sąsiednich gmin), **Sieć 30** (wszystkie linie KŚ i Polregio w GZM); 30-dniowe także PKP Intercity na tych samych trasach. Polregio: bilet w aplikacji Transport GZM. Jednorazowe z koleją: nie stwierdzono (dane z 2019 o bilecie 6 h wydawanym przez KŚ: nie zweryfikowano).
- MAX (miesięczne KŚ, bez komunikacji miejskiej): ten sam zakres kolejowy co Metrobilet.

## 8. Propozycja „sieci objętej wspólnym biletem" dla wariantu routingu

**Propozycja do potwierdzenia przez właściciela.** Nazwy agencji GTFS i dokładne identyfikatory należy zmapować w fazie GTFS (nie sprawdzano GTFS). Zasada: wariant „wspólny bilet" zachowuje agencje miejskie + te przewoźniki kolejowi, których bilet okresowy/czasowy organizatora jest ważny, a kolej ogranicza do stacji w obszarze ważności (filtr stref/stacji), bo R5 nie zna stref taryfowych.

| Aglomeracja | Zachować | Ograniczenie obszarowe kolei | Wyłączyć |
|---|---|---|---|
| Warszawa | ZTM (bus, tram, metro), Koleje Mazowieckie (osobowe/aglomeracyjne), WKD (Śródmieście–Opacz), SKM | KM w obszarze stref 1/2 ZTM (granice z listy powyżej) | KM dalekobieżne, przyspieszone poza strefą 1, WKD poza Opaczem, PKP IC, Polregio |
| Kraków | MPK Kraków (+Mobilis), KMŁ | wariant „metropolitalny": KMŁ w granicach stref I–III jako przybliżenie biletu okresowego; wariant ścisły dla biletu jednorazowego: tylko odcinki 70-min | PKP IC, KMŁ poza strefą III |
| Wrocław | MPK Wrocław, KD i Polregio | tylko stacje z „Wrocław" w nazwie + Iwiny | KD/Polregio poza miastem, PKP IC |
| Poznań | ZTM Poznań, KW, Polregio | wariant podstawowy: kolej tylko w kolejowej strefie A (miasto + Kiekrz); wariant BTK: strefy A–C ZTM i strefy kolejowe A–G (bilet miesięczny) | PKP IC; KW/Polregio poza strefami BTK |
| Łódź | MPK-Łódź, ŁKA (ŁKA, Sprinter), Polregio | wariant podstawowy: kolej tylko na stacjach Lublinek–Radogoszcz–Arturówek–Andrzejów; wariant WBA: ŁKA i Polregio w strefach WBA (aglomeracja) | PKP IC (od 2025-12-14), pociągi dalekobieżne |
| Trójmiasto | ZTM Gdańsk, ZKM Gdynia, MZK Wejherowo (opcjonalnie), SKM, PKM, Polregio | SKM/Polregio w obszarze MZKZG (wariant kolejowo-komunalny; do doprecyzowania strefy) | PKP IC |
| GZM | ZTM GZM, Koleje Śląskie, Polregio | wariant „Sieć 30": cały obszar GZM (KŚ + Polregio w granicach GZM) | PKP IC (poza trasą z biletem 30-dniowym), pociągi poza GZM |

Uwagi do decyzji: (1) dla Krakowa, Poznania, Wrocławia i Łodzi kolej zintegrowana jest tylko bilety okresowe/czasowe i/lub na wąskim obszarze, więc wariant „bilet jednorazowy" i „bilet okresowy" dają różne sieci; zaproponować dwa warianty (ścisły: jednorazowy/czasowy; szeroki: okresowy). (2) Każdą agencję w feedach (nazwy w GTFS) uzgodnić z właścicielem w fazie 1.
