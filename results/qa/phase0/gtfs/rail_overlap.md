# Nakładanie się kolei (`polish_trains`) z feedami miejskimi: pierwsze spojrzenie

Dzień odniesienia: **2026-11-25** (śr). Kursy liczone na ten dzień; „kursy” = rozwinięte `frequencies.txt` (w feedach kolejowych brak).

## 1. Co naprawdę zawiera `polish_trains.zip`

| agency_id | Przewoźnik | kursy kolejowe (route_type 2) | kursy ZKA/autobus (route_type 3) | wozokm (tys.) |
|---|---|---:|---:|---:|
| AR | Arriva RP | 176 | 50 | 10.4 |
| IC | PKP Intercity | 526 | 20 | 275.3 |
| KD | Koleje Dolnośląskie | 685 | 115 | 53.7 |
| KM | Koleje Mazowieckie | 977 | 151 | 65.3 |
| KML | Koleje Małopolskie | 201 | 3 | 11.2 |
| KS | Koleje Śląskie | 608 | 23 | 32.5 |
| KW | Koleje Wielkopolskie | 470 | 10 | 39.0 |
| LEO | Leo Express | 9 | 0 | 5.4 |
| LKA | Łódzka Kolej Aglomeracyjna | 323 | 6 | 22.7 |
| PR | PolRegio | 2312 | 272 | 197.9 |
| RJ | RegioJet | 4 | 0 | 2.3 |
| SKM | SKM Warszawa | 284 | 0 | 11.3 |
| SKMT | PKP SKM Trójmiasto | 228 | 0 | 9.2 |

Oczekiwane przez brief: SKM Trójmiasto (jest), ŁKA (jest), KMŁ (jest), KD (jest), KŚ (jest), KM (jest). Dodatkowo w feedzie: SKM Warszawa (`SKM`), Koleje Wielkopolskie (`KW`, linie PKM1–PKM5 = Poznańska Kolej Metropolitalna), PolRegio, PKP Intercity, Arriva RP, RegioJet, Leo Express. **Brak WKD** (osobny feed `warsaw_wkd`).

**Pomorska Kolej Metropolitalna (PKM Gdańsk)** nie ma własnej agencji: kursy jeździ PolRegio jako trasa `PR_PM_R11, PR_PM_R12, PR_PM_R13, PR_PM_R14, PR_PM_R20, PR_PM_R3, PR_PM_R7, PR_PM_RE3, PR_PM_RE7, PR_PM_S2` (348 kursów w feedzie; w dniu ref. 0; dni kursowania 2026-12-13 – 2026-12-23). Linia startuje wraz ze zmianą rozkładu w grudniu, więc w listopadowym dniu referencyjnym jej nie ma. Przy filtrowaniu po agencji trzeba ją wyciągnąć po `route_id`, nie po `agency_id`.

## 2. Przewoźnicy kolejowi w aglomeracjach (kursy, które zatrzymują się na przystanku w promieniu 25 km od centrum)

| Aglomeracja | AR | IC | KD | KM | KML | KS | KW | LEO | LKA | PR | RJ | SKM | SKMT | razem |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Warszawa | 0 | 254 | 0 | 740 | 0 | 0 | 0 | 8 | 0 | 24 | 2 | 284 | 0 | 1312 |
| Kraków | 0 | 172 | 0 | 0 | 201 | 16 | 0 | 9 | 0 | 146 | 2 | 0 | 0 | 546 |
| Wrocław | 0 | 124 | 471 | 0 | 0 | 0 | 0 | 0 | 0 | 64 | 0 | 0 | 0 | 659 |
| Poznań | 0 | 146 | 0 | 0 | 0 | 0 | 349 | 0 | 0 | 88 | 0 | 0 | 0 | 583 |
| Łódź | 0 | 77 | 0 | 0 | 0 | 0 | 2 | 0 | 281 | 60 | 0 | 0 | 0 | 420 |
| Trójmiasto | 0 | 106 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 319 | 0 | 0 | 228 | 653 |
| GZM | 0 | 149 | 0 | 0 | 66 | 498 | 0 | 6 | 0 | 159 | 2 | 0 | 0 | 880 |

## 3. Kandydaci na dublowanie: trasy szynowe w feedach miejskich

| Feed | route_id | nazwa | klasa | kursy w dniu ref. |
|---|---|---|---|---:|
| `warsaw_ztm` | M1 | M1 Kabaty – Młociny | metro | 712 |
| `warsaw_ztm` | M2 | M2 Bemowo – Bródno | metro | 543 |
| `warsaw_ztm` | S1 | S1 Otwock – Pruszków | rail | 82 |
| `warsaw_ztm` | S2 | S2 Warszawa Lotnisko Chopina – Sulejówek Miłosna | rail | 83 |
| `warsaw_ztm` | S3 | S3 Legionowo – Warszawa Lotnisko Chopina | rail | 39 |
| `warsaw_ztm` | S4 | S4 Piaseczno – Zegrze Południowe | rail | 40 |
| `warsaw_ztm` | S40 | S40 Piaseczno – Radzymin | rail | 40 |
| `warsaw_wkd` | A | WKD Warszawska Kolej Dojazdowa | rail | 192 |

## 4. Test dublowania: SKM Warszawa w `warsaw_ztm` vs agencja `SKM` w `polish_trains`

- `warsaw_ztm`: 284 kursów kolejowych (linie S1, S2, S3, S4, S40) w dniu ref.; `polish_trains`/SKM: 284 kursów (linie S1, S2, S3, S4, S40).
- Dopasowanie kursu: ta sama linia + ta sama (znormalizowana) nazwa przystanku początkowego + ta sama minuta odjazdu: **100.0 %** kursów `warsaw_ztm` ma odpowiednik w `polish_trains`.
- Luźniejszy klucz (przystanek początkowy + minuta, bez linii): 100.0 %.
- Wniosek: to ten sam rozkład SKM Warszawa podany dwukrotnie; kursy należy liczyć raz.

## 5. Proponowana reguła deduplikacji

1. Jedna jednostka zliczania: kurs (trip) w dniu referencyjnym; klucz dopasowania między feedami = (linia, znormalizowana nazwa przystanku początkowego w promieniu 100 m, minuta odjazdu z przystanku początkowego).
2. **SKM Warszawa**: zostawić wersję z `warsaw_ztm` (linie S1–S4, S40; przystanki zgodne z siecią ZTM i strefami biletowymi, kształty), a agencję `SKM` z `polish_trains` odrzucić przed zliczaniem (filtr po `agency_id`). Linie M1/M2 są tylko w `warsaw_ztm`.
3. **Pozostała kolej regionalna** (KM, KŚ, KD, KMŁ, ŁKA, SKM Trójmiasto, KW/PKM, PolRegio, IC): jedyne źródło to `polish_trains`; ich kursy są liczone raz, po przycięciu do FUA + bufor.
4. **WKD** pochodzi wyłącznie z `warsaw_wkd` (brak w `polish_trains`).
5. Autobusowa komunikacja zastępcza (route_type 3, „ZKA”) w `polish_trains` wyłączyć z miar „kolejowych” (to nie kolej; kursy zastępcze są doraźne).
6. Reguła ogólna dla przyszłych feedów: jeśli ten sam kurs (klucz z pkt 1) występuje w feedzie miejskim i kolejowym, wygrywa feed miejski; każdy odrzucony kurs trafia do `results/qa/` z liczbą odrzuconych na aglomerację.

