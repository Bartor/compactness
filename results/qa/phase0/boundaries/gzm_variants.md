# GZM: dwa warianty granicy (decyzja właściciela, brief §2 i §12,1)

Stan na 2026-11-23. **Nie wybrano wariantu.** Do wyników tymczasowych użyto wariantu (a) i oznaczono je jako tymczasowe
(`config.yaml`: `gzm.boundary_variant: null`, w kodzie traktowane jak `fua_union`).

## Jak Eurostat dzieli konurbację (URAU 2021)

Konurbacja nie jest jedną FUA. W URAU 2021 jest tu **pięć osobnych FUA** (każda z własnym rdzeniem lub rdzeniami), a poza
Metropolią leżą kolejne (Rybnik, Jastrzębie-Zdrój, Bielsko-Biała, Częstochowa):

- **PL010F** Katowice (z Chorzowem, Mysłowicami, Siemianowicami, Świętochłowicami; miasta URAU w tej FUA: Katowice, Sosnowiec,
  Bytom, Ruda Śląska, Chorzów, Będzin, Mysłowice, Siemianowice Śląskie, Świętochłowice),
- **PL055F** Gliwice / Zabrze, **PL061F** Tychy, **PL070F** Dąbrowa Górnicza.
- **PL060F** Rybnik dotyka Metropolii tylko śladowo (patrz niżej).

Granica Metropolii GZM: suma **41 gmin członkowskich** z LAU 2021. Lista wg metropoliagzm.pl/metropolia-dzis (pięć
podregionów, „41 miast i gmin”), zgodna z pl.wikipedia.org (hasło Górnośląsko-Zagłębiowska Metropolia). Podstawa prawna: ustawa z 9,03,2017 o związku
metropolitalnym w województwie śląskim (Dz.U. 2017 poz. 730; tekst jedn. Dz.U. 2025 poz. 186) i rozporządzenie Rady Ministrów
z 26,06,2017 (Dz.U. 2017 poz. 1290), w mocy od 1,07,2017. Jaworzno **nie** należy do Metropolii. Lista w kodzie: `pipeline/boundaries.py`
(`GZM_GMINAS`). Uwaga: LAU 2021 pochodzi ze skali 1:1 mln, URAU ze skali 1:100 tys., więc na brzegach są drobne niezgodności
(stąd „ślad” Rybnika).

## Warianty: liczby

| Wariant | Powierzchnia km² | Liczba gmin | Ludność NSP 2021 | Ludność GHSL 2020 | GHSL vs NSP | Ludność LAU 2021 (BDL) |
|---|---|---|---|---|---|---|
| (a) suma FUA przecinających się z GZM, reguła ≥ 5 % pola FUA w GZM (PL010F, PL055F, PL061F, PL070F) | 2 592 | 39 | 2 057 054 | 2 150 295 | 4,5 % | 2 155 292 |
| (a′) wszystkie FUA dotykające GZM (dodatkowo PL060F Rybnik) | 2 877 | 46 | 2 258 716 | 2 363 791 | 4,7 % | 2 367 727 |
| (b) granica Metropolii GZM (41 gmin) | 2 551 | 41 | 2 129 249 | 2 221 625 | 4,3 % | 2 229 806 |

Różnica (a) minus (b): **404 km²** i **46 187 mieszkańców (NSP)** leżą w (a), poza GZM; gminy w (a), nie
będące członkami GZM (≥ 50 % powierzchni w (a)): Miedźna, Toszek, Wielowieś, Łazy.
Różnica (b) minus (a): **363 km²** i **118 382 mieszkańców (NSP)** leżą w GZM, poza (a); gminy GZM poza (a):
Mierzęcice, Ożarowice, Siewierz, Tarnowskie Góry, Łaziska Górne, Świerklaniec.

## FUA przecinające się z GZM: jaka część leży w Metropolii

| Kod | FUA | Pow. FUA km² | Pow. w GZM km² | Udział pola FUA w GZM | Ludność NSP FUA | Ludność NSP w GZM | Udział ludności NSP FUA w GZM | Udział ludności GHSL FUA w GZM | Udział w ludności GZM (NSP) |
|---|---|---|---|---|---|---|---|---|---|
| PL010F | Katowice Chorzów Mysłowice Siemianowice Śl Świętochłowice | 922 | 921 | 99,9% | 1 289 270 | 1 289 270 | 100,0% | 100,0% | 60,6% |
| PL055F | Gliwice / Zabrze | 1 026 | 808 | 78,7% | 446 773 | 432 236 | 96,7% | 96,9% | 20,3% |
| PL060F | Rybnik | 284 | 0 | 0,0% | 201 662 | 0 | 0,0% | 0,0% | 0,0% |
| PL061F | Tychy | 287 | 235 | 82,0% | 185 333 | 169 560 | 91,5% | 91,5% | 8,0% |
| PL070F | Dąbrowa Górnicza | 358 | 225 | 62,9% | 135 678 | 119 801 | 88,3% | 89,0% | 5,6% |

**Proponowana reguła nakładania:** FUA wchodzi do wariantu (a), jeśli co najmniej **5 %** jej pola leży w Metropolii.
Wynik jest odporny na wybór progu: każdy próg między ~1 % a ~60 % daje ten sam zestaw (cztery FUA); Rybnik (ślad rzędu 0,1 km²,
artefakt różnicy skal LAU/URAU) odpada, a pozostałe leżą w GZM w ≥ 60 % pola. Zwróć uwagę, że FUA Gliwice/Zabrze i Dąbrowa
Górnicza sięgają poza GZM, i te części wchodzą do (a).

## Kompromisy (opis neutralny)

**(a) suma FUA przecinających się z GZM**
- Spójna z pozostałymi aglomeracjami (wszędzie FUA Eurostatu; porównywalność definicji w całym zestawie i z innymi pracami opartymi na URAU).
- Obejmuje strefy dojazdów wokół rdzeni, w tym obszary poza Metropolią; nie zależy od członkostwa gmin w związku metropolitalnym,
  które jest decyzją polityczną i zmieniało się (Jaworzno nie przystąpiło; gminy mogą dołączać).
- Granica nie pokrywa się z żadną jednostką administracyjną; do tabel per gmina potrzebna jest reguła przypisania gmin do obszaru.
- Wynik jest „sumą kilku FUA”, więc część miar (np. rdzeń, ludność w FUA) zależy od tego, że Eurostat podzielił konurbację na kilka FUA (cztery w wariancie (a), łącznie 13 miast URAU).

**(b) granica Metropolii GZM (41 gmin)**
- Zgodna z jednostką, którą rozumieją odbiorcy w regionie, i z danymi administracyjnymi (BDL, GTFS ZTM GZM obejmuje te gminy).
- Granica = granice gmin, więc wprost sumuje się z tabelami gminnymi (BDL, LAU).
- Odcina część stref dojazdów i sąsiednie ośrodki powiązane funkcjonalnie, a także jest mniej porównywalna z innymi aglomeracjami
  (tam FUA, tu granica związku). Zawiera gminy o charakterze wiejskim (np. Zbrosławice, Rudziniec, Sośnicowice), których FUA nie obejmuje.
- Zmiana składu Metropolii zmienia obszar.

Dla obu wariantów obowiązuje bufor 15 km (FUA lub granica GZM + 15 km) jako domena celów, więc różnica wpływa głównie na
miary „na obszarze”, a w mniejszym stopniu na miary dostępności liczone na buforze.

Mapa: `gzm_variants.png`. Liczby: `gzm_variants.json`.
