# Kalendarz: dni referencyjne (faza 0)

Dostęp do źródeł: 2026-11-23. Dziś = 2026-11-23 (poniedziałek). Dni tygodnia policzone programowo.

## 1. Ferie zimowe 2027 i przerwy (rok szkolny 2026/2027)

Źródło **pierwotne**: MEN, „Ministerstwo Edukacji Narodowej ogłosiło kalendarz roku szkolnego 2026/2027" (komunikat z 19.05.2026), https://www.gov.pl/web/edukacja/ministerstwo-edukacji-narodowej-oglosilo-kalendarz-roku-szkolnego-20262027 (dostęp 2026-11-23). Potwierdzone zgodnie z drugim źródłem (wtórnym, portal oświatowy): https://www.portaloswiatowy.pl/komunikaty-men-i-cke/-ferie-zimowe-2027-terminy-na-rok-szkolny-20262027-26395.html. Podstawa prawna: rozporządzenie MEN w sprawie organizacji roku szkolnego (numeru Dz.U. nie sprawdzono).

| Termin ferii | Województwa | Nasze aglomeracje |
|---|---|---|
| **18–31 stycznia 2027** | dolnośląskie, łódzkie, opolskie, podkarpackie, podlaskie, śląskie | Wrocław, Łódź, GZM |
| **1–14 lutego 2027** | lubelskie, mazowieckie, pomorskie, świętokrzyskie | Warszawa, Trójmiasto |
| **15–28 lutego 2027** | kujawsko-pomorskie, lubuskie, małopolskie, warmińsko-mazurskie, wielkopolskie, zachodniopomorskie | Kraków, Poznań |

- **Zimowa przerwa świąteczna: 23–31 grudnia 2026** (MEN, jw.). Wiosenna przerwa świąteczna: 25–30 marca 2027. Zakończenie zajęć 25 czerwca 2027.
- **Zasady podziału:** komunikat MEN mówi o „trzech terminach w zależności od województwa". Portal oświatowy: „utrzymane zostaną trzy terminy" (czyli układ trzech tur obowiązywał już w 2025/2026). Czy w stosunku do 2024/2025 zmieniła się liczba tur lub zasada rotacji: **nie zweryfikowano** w źródle pierwotnym. Zasada rotacji grup w kolejnych latach: nie opisana na stronie gov.pl.
- Ferie dotyczą szkół; ruch w aglomeracjach spada także w tygodniach ferii innych województw (dojazdy na narty, wyjazdy), ale tego nie modelujemy.

## 2. Święta państwowe i ryzyka długich weekendów (2026-11-23 do 2027-03-31)

Źródło: Kodeks pracy (art. 130 §1 i ustawa o dniach wolnych od pracy); kalendarz święt policzony (Wielkanoc 2027 = 28 marca, algorytm gregoriański). **Wigilia 24 grudnia jest dniem ustawowo wolnym od pracy od 2025 r.** (potwierdzone w źródle wtórnym, m.in. zielonalinia.gov.pl / prasa, https://zielonalinia.gov.pl/niedziele-handlowe-w-2026-r/; nie czytano samej ustawy: nie zweryfikowano w źródle pierwotnym).

| Data | Dzień | Święto | Ryzyko |
|---|---|---|---|
| 2026-12-24 | czwartek | Wigilia | długi weekend cz–nd (24–27.12); 21–23.12 także obniżony ruch (przerwa szkolna od 23.12) |
| 2026-12-25 | piątek | Boże Narodzenie | |
| 2026-12-26 | sobota | drugi dzień Bożego Narodzenia | |
| 2027-01-01 | piątek | Nowy Rok | długi weekend pt–nd; rozkłady świąteczne 31.12 |
| 2027-01-06 | środa | Trzech Króli | **most**: cz 7.01 i pt 8.01 są często wolne; tydzień 4–8.01 nietypowy |
| 2027-03-28 | niedziela | Wielkanoc | |
| 2027-03-29 | poniedziałek | Poniedziałek Wielkanocny | długi weekend sb–pn; przerwa wiosenna 25–30.03; Wielka Sobota 27.03 |

Brak świąt państwowych między 2026-11-24 a 2026-12-23 oraz między 2027-01-07 a 2027-03-27. Mikołajki 6 grudnia 2026 to **niedziela** (nie święto). 8 grudnia nie jest świętem państwowym.

**Niedziele handlowe** (dotyczą tylko sobót/niedziel; źródło wtórne): w 2026 r. handel dozwolony m.in. 6, 13 i 20 grudnia (lista: 25.01, 29.03, 26.04, 28.06, 30.08, 6.12, 13.12, 20.12; https://www.bankier.pl/wiadomosc/Niedziele-handlowe-2026-Osiem-terminow-ktore-warto-zapisac-w-kalendarzu-9061388.html i https://zielonalinia.gov.pl/niedziele-handlowe-w-2026-r/); 27.12.2026 nie jest handlowa. **Lista niedziel handlowych na 2027: nie zweryfikowano.** Dla dni roboczych i sobót referencyjnych nie ma to znaczenia, ale grudniowe soboty (5, 12, 19.12) mają podwyższony ruch zakupowy.

## 3. Reguły oceny „czysty dzień"

Dzień jest **OK** dla województwa, gdy: nie jest świętem; nie wypada w 24.12–6.01; nie wypada w przerwie świątecznej szkół (23.12) ani wiosennej (25–30.03); nie sąsiaduje bezpośrednio ze świętem (dzień przed / po); nie wypada w feriach tego województwa. Inne wartości w komórkach: `ferie`, `święto`, `24.12–6.01`, `przerwa św. (23.12)`, `przerwa wiosenna`, `przy święcie`.

Uwagi niemodelowane: (1) tygodnie 14–17.12 to handel przedświąteczny; (2) pierwszy tydzień po feriach; (3) 31.03.2027 to pierwszy dzień po przerwie wiosennej (zaznaczony OK, ale ostrożnie); (4) ważność feedów GTFS (np. Wrocław, Poznań, GZM krótkie okna) może ograniczyć wybór: sprawdzić w fazie GTFS; (5) opcja „okno pierwszy tydzień feedu" w kodzie ITDP to inna logika (patrz itdp_pnft.md).

**Dni OK dla wszystkich 7 województw jednocześnie (wt–czw):** 2026-11-24, 2026-11-25, 2026-11-26, 2026-12-01, 2026-12-02, 2026-12-03, 2026-12-08, 2026-12-09, 2026-12-10, 2026-12-15, 2026-12-16, 2026-12-17, 2027-01-12, 2027-01-13, 2027-01-14, 2027-03-02, 2027-03-03, 2027-03-04, 2027-03-09, 2027-03-10, 2027-03-11, 2027-03-16, 2027-03-17, 2027-03-18, 2027-03-23, 2027-03-24, 2027-03-31

Bez dni w styczniu i lutym poza 12–14.01.2027: od 18.01 do 28.02 każdy dzień jest w feriach co najmniej jednego województwa z listy. W marcu 2027 wszystkie wt–czw z listy są czyste (poza 25–30.03 i 31.03 uwagą). **Najbezpieczniejsze wspólne okna:** 1–3.12.2026, 8–10.12.2026, 15–16.12.2026 (17.12 z uwagą), 12–14.01.2027, oraz marzec 2027 (2–4, 9–11, 16–18, 23–24.03).

## 4. Kandydaci: wtorki–czwartki

Zakres: 2026-11-24 do 2026-12-17 oraz od 2027-01-12 do 2027-03-31.

| Data | Dzień | mazowieckie | małopolskie | dolnośląskie | wielkopolskie | łódzkie | pomorskie | śląskie | Uwagi |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-24 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-11-25 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-11-26 | cz | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-01 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-02 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-03 | cz | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-08 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-09 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-10 | cz | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-15 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-16 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-17 | cz | OK | OK | OK | OK | OK | OK | OK | tydzień przed świętami (handel przedświąteczny) |
| 2027-01-12 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-01-13 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-01-14 | cz | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-01-19 | wt | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-01-20 | śr | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-01-21 | cz | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-01-26 | wt | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-01-27 | śr | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-01-28 | cz | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-02-02 | wt | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-03 | śr | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-04 | cz | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-09 | wt | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-10 | śr | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-11 | cz | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-16 | wt | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-02-17 | śr | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-02-18 | cz | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-02-23 | wt | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-02-24 | śr | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-02-25 | cz | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-03-02 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-03 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-04 | cz | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-09 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-10 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-11 | cz | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-16 | wt | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-17 | śr | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-18 | cz | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-23 | wt | OK | OK | OK | OK | OK | OK | OK | tydzień przed przerwą wiosenną (25–30.03) |
| 2027-03-24 | śr | OK | OK | OK | OK | OK | OK | OK | tydzień przed przerwą wiosenną (25–30.03) |
| 2027-03-25 | cz | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna |  |
| 2027-03-30 | wt | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna |  |
| 2027-03-31 | śr | OK | OK | OK | OK | OK | OK | OK |  |

## 5. Kandydaci: soboty

Zakres: 2026-11-28 do 2026-12-19 oraz od 2027-01-09 do 2027-03-31. Reguły jak wyżej (sobota w feriach liczona jako `ferie`).

| Data | Dzień | mazowieckie | małopolskie | dolnośląskie | wielkopolskie | łódzkie | pomorskie | śląskie | Uwagi |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-28 | sb | OK | OK | OK | OK | OK | OK | OK | sobota po Black Friday (27.11) |
| 2026-12-05 | sb | OK | OK | OK | OK | OK | OK | OK | wigilia Mikołajek (6.12 to niedziela) |
| 2026-12-12 | sb | OK | OK | OK | OK | OK | OK | OK |  |
| 2026-12-19 | sb | OK | OK | OK | OK | OK | OK | OK | tydzień przed świętami (handel przedświąteczny) |
| 2027-01-09 | sb | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-01-16 | sb | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-01-23 | sb | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-01-30 | sb | OK | OK | ferie | OK | ferie | OK | ferie |  |
| 2027-02-06 | sb | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-13 | sb | ferie | OK | OK | OK | OK | ferie | OK |  |
| 2027-02-20 | sb | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-02-27 | sb | OK | ferie | OK | ferie | OK | OK | OK |  |
| 2027-03-06 | sb | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-13 | sb | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-20 | sb | OK | OK | OK | OK | OK | OK | OK |  |
| 2027-03-27 | sb | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | przerwa wiosenna | Wielka Sobota |

**Soboty OK dla wszystkich 7 województw jednocześnie:** 2026-11-28, 2026-12-05, 2026-12-12, 2026-12-19, 2027-01-09, 2027-01-16, 2027-03-06, 2027-03-13, 2027-03-20. Soboty z uwagami o handlu: 5, 12 i 19.12 (okres przedświąteczny, niedziele handlowe obok), 28.11 (po Black Friday), 27.03 (Wielka Sobota, wyłączona jako przerwa wiosenna).

## 6. Rekomendacja robocza (do potwierdzenia przez właściciela)

Wspólny dzień roboczy dla wszystkich feedów, wt–czw: np. **wtorek 2026-12-01, środa 2026-12-02 lub czwartek 2026-12-03** (albo 8–10.12) oraz sobota **2026-12-05 lub 2026-12-12** (uwaga na niedziele handlowe obok). Wybór zależy od ważności i dat pobrania feedów (brief §5): sprawdzić w fazie GTFS. Alternatywa na styczeń: 12–14.01.2027, soboty 9 lub 16.01.2027.
