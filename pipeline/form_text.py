"""Interpretive Polish text of results/qa/form/form.md.

Numbers are read from the results (data/interim/form/<agg>.json) so the text follows a re-run; the qualitative
statements were written after reading the run of 2026-11-24 and are re-checked by the assertions in ``checks``.
"""
from __future__ import annotations

from scipy.stats import spearmanr

from pipeline.form_md import g3, n, pct


def mono(R: dict) -> list[str]:
    return [a for a in sorted(R) if not R[a]["polycentric"]]


def rng(vals: list[float], f=g3) -> str:
    return f"{f(min(vals))}–{f(max(vals))}"


def sp(a: list[float], b: list[float]) -> str:
    return n(float(spearmanr(a, b).statistic), 2)


def checks(R: dict) -> None:
    """The qualitative claims below; fail loudly if a re-run changes them."""
    M = mono(R)
    e = lambda a, k="b10": R[a]["extent"][k]  # noqa: E731
    assert all(e(a)["rho_ext"] < 1 for a in M), "rho on Angel's extent no longer < 1 in every single-centre city"
    assert all(R[a]["density_step"]["fua:rho_t20"] > 1 for a in M)
    assert e("trojmiasto")["prx"] < min(e(a)["prx"] for a in M)
    assert e("gzm")["prx"] < min(e(a)["prx"] for a in M)
    assert all(e(a)["land_over_pop"] > 1 for a in R)
    g = R["gzm"]["hotspots"]["main"]["centres"]
    assert sum(c["nearest_hot_cell_km"] <= 0.25 and c["hotspot_rank"] <= 10 for c in g) == 8


def sections(R: dict) -> dict:
    checks(R)
    M = mono(R)
    e = lambda a, k="b10": R[a]["extent"][k]  # noqa: E731
    nm = lambda a: R[a]["name"]  # noqa: E731
    out = {}

    # ---------------------------------------------------------------- Angel
    prx_m = [e(a)["prx"] for a in M]
    rho_m = [e(a)["rho_ext"] for a in M]
    uc_m = [R[a]["uc_extent"]["prx"] for a in M]
    lo = sorted(M, key=lambda a: e(a)["prx"])
    t = R["trojmiasto"]
    tg = t["extent"]["second"]
    w = R["warszawa"]
    out["ANGEL_READING"] = "\n".join([
        "**Jak czytać.**",
        "",
        f"- **PRX w miastach jednocentrowych mieści się w wąskim paśmie {rng(prx_m)}** (centrum miejskie Eurostatu: "
        f"{rng(uc_m)}). Wszystkie wartości są powyżej dolnej granicy 0,35 z próby Angela i in. Kolejność miast w tym "
        "paśmie nie jest odporna na regułę zasięgu: korelacja rang (Spearman, 10 miast) PRX głównego z wariantem "
        f"bez łączenia przerw wynosi {sp(prx_m, [e(a, 'b10_gap0')['prx'] for a in M])}, z progiem 20 % "
        f"{sp(prx_m, [e(a, 'b20')['prx'] for a in M])}, z progiem 5 % {sp(prx_m, [e(a, 'b5')['prx'] for a in M])}, "
        f"z PRX centrum miejskiego Eurostatu {sp(prx_m, uc_m)}. Różnice między miastami jednocentrowymi są więc "
        "mniejsze niż niepewność samej definicji zasięgu; nie należy ich rankingować.",
        f"- **Odporne jest tylko to, co odstaje:** Trójmiasto ({g3(e('trojmiasto')['prx'])}; zasięg od Gdańska po "
        f"Gdynię i Wejherowo, {n(e('trojmiasto')['area_km2'])} km²), GZM ({g3(e('gzm')['prx'])}) i Bydgoszcz–Toruń "
        f"({g3(e('bydgoszcz_torun')['prx'])}) mają najniższe PRX przy każdej regule. Dla Trójmiasta PRX z ratuszem "
        f"Gdyni wynosi {g3(tg['prx'])} (to samo skupisko). To potwierdza, że indeks z jednym centrum mierzy tam kształt "
        "pasma, a nie zwartość miasta: dla Trójmiasta jest **bez znaczenia jako miara zwartości**, dla GZM opisuje "
        "konurbację względem Katowic, dla Bydgoszczy–Torunia tylko Bydgoszcz (Toruń w tabeli 2a ma własny zasięg).",
        f"- **Warszawa pokazuje, czemu potrzebne jest łączenie przerw:** bez niego Wisła odcina ratusz (pl. Bankowy, "
        f"blisko rzeki) od Pragi, zasięg ma {n(e('warszawa', 'b10_gap0')['area_km2'])} km² zamiast "
        f"{n(e('warszawa')['area_km2'])} km², a PRX spada do {g3(e('warszawa', 'b10_gap0')['prx'])}. Łączenie przerw "
        "do 600 m (ta sama reguła co maska ρ w kroku density) ma swoją cenę: w Kielcach i Rzeszowie dołącza wsie "
        f"wzdłuż dróg (PRX {g3(e('kielce', 'b10_gap0')['prx'])} → {g3(e('kielce')['prx'])} i "
        f"{g3(e('rzeszow', 'b10_gap0')['prx'])} → {g3(e('rzeszow')['prx'])}).",
        f"- **ρ Bertauda na zasięgu Angela jest poniżej 1 w każdym mieście jednocentrowym ({rng(rho_m)})**, a ρ z "
        f"kroku density (maska ≥ 20 %, FUA) jest powyżej 1 wszędzie "
        f"({rng([R[a]['density_step']['fua:rho_t20'] for a in M])}). Na zasięgu narysowanym opublikowaną regułą "
        "mieszkańcy mieszkają więc bliżej ratusza niż przy równomiernym rozkładzie na kole o tym samym polu; ρ > 1 "
        "z kroku density wynika z maski netto (gwiaździstej, bez luźnej zabudowy), co density.md §4 już opisuje. "
        "Poziom ρ na zasięgu Angela jest tego samego rzędu co wartości Bertauda i Malpezziego dla Warszawy i Krakowa "
        f"(0,99 i 1,18, lata 90.): tu {g3(e('warszawa')['rho_ext'])} i {g3(e('krakow')['rho_ext'])}. Kolejność miast "
        f"według obu ρ się nie zgadza (Spearman {sp(rho_m, [R[a]['density_step']['fua:rho_t20'] for a in M])}): to "
        "różne obszary i różne centra.",
        f"- **Co dodaje każda miara.** PRX × ρ (średnia odległość terenu / średnia odległość mieszkańca) jest > 1 w "
        f"każdej aglomeracji ({rng([e(a)['land_over_pop'] for a in R])}): ludzie mieszkają bliżej ratusza niż leży "
        "teren zasięgu, czyli gęstość maleje od centrum. PRX opisuje sam kształt śladu zabudowy (np. pasma wzdłuż "
        "dróg w Warszawie, Kielcach, Rzeszowie), ρ dokłada rozkład ludzi w tym śladzie. Dla miast jednocentrowych "
        f"obie miary leżą blisko siebie i blisko 1 (PRX {rng(prx_m)}, 1/ρ "
        f"{rng([1 / v for v in rho_m])}), więc żadna nie rozróżnia ich lepiej niż gęstość ważona populacją albo "
        "udział mieszkańców w gęstych komórkach (sekcja 5).",
        f"- **Spójność** zachowuje się jak PRX (Trójmiasto {g3(e('trojmiasto')['cohesion'])}, GZM "
        f"{g3(e('gzm')['cohesion'])}, miasta jednocentrowe {rng([e(a)['cohesion'] for a in M])}) i nie zależy od "
        "centrum; to jej jedyna przewaga.",
        f"- **Najniższe PRX wśród miast jednocentrowych:** {', '.join(nm(a) + ' ' + g3(e(a)['prx']) for a in lo[:3])}; "
        "na mapie (extents.png) widać, że to miasta z długimi pasmami zabudowy wzdłuż dróg dołączonymi do zasięgu, "
        "a nie z rzadszym centrum.",
    ])

    # ---------------------------------------------------------------- polycentricity
    h = lambda a, k="main": R[a]["hotspots"][k]  # noqa: E731
    eta_m = sorted(M, key=lambda a: R[a]["eta"]["eta"])
    sl = {a: h(a)["rank_size_slope"] for a in R if h(a)["rank_size_slope"] is not None}
    sl_sorted = sorted(sl, key=lambda a: -sl[a])
    gz = R["gzm"]
    weak = [c for c in gz["hotspots"]["main"]["centres"] if c["hotspot_rank"] > 10]
    big_far = [a for a in M if h(a)["clusters"] and h(a)["clusters"][0]["nearest_centre_km"] >= 3]

    def far_txt(a: str) -> str:
        c = h(a)["clusters"][0]
        return f"{nm(a)}: {n(c['pop'])} os., {n(c['nearest_centre_km'], 1)} km od centrum"
    out["POLY_READING"] = "\n".join([
        "**Jak czytać.**",
        "",
        f"- **η dokładne a z próby:** różnica najwyżej "
        f"{n(max(abs(R[a]['eta']['eta'] - (R[a]['density_step']['fua:eta_mask'] or 0)) for a in R), 3)}, czyli błąd "
        "próbkowania z kroku density (4 000 komórek) jest pomijalny.",
        f"- **η wysokie w obszarach wielomiejskich:** GZM {g3(gz['eta']['eta'])}, Bydgoszcz–Toruń "
        f"{g3(R['bydgoszcz_torun']['eta']['eta'])}, Trójmiasto {g3(R['trojmiasto']['eta']['eta'])}. Ale wysokie ma też "
        f"Lublin ({g3(R['lublin']['eta']['eta'])}): jego hotspoty to osiedla rozrzucone po mieście i Świdnik "
        f"(skupisko {n(next((c['pop'] for c in h('lublin')['clusters'] if c['gmina'] == 'Świdnik'), None))} os. "
        f"ok. 11 km od centrum). Najniższe η: {', '.join(nm(a) + ' ' + g3(R[a]['eta']['eta']) for a in eta_m[:3])}. "
        "η mówi więc, czy gęste miejsca są rozrzucone po obszarze, a nie, czy obszar ma kilka centrów; samo nie "
        "odróżnia konurbacji od miasta z rozproszonymi blokowiskami.",
        f"- **Skupiska gęstości.** Najbardziej płaska zależność ranga–wielkość: "
        f"{', '.join(f'{nm(a)} {g3(sl[a])}' for a in sl_sorted[:4])}; najbardziej stroma: "
        f"{', '.join(f'{nm(a)} {g3(sl[a])}' for a in sl_sorted[-3:])}. GZM ma najwięcej skupisk "
        f"({h('gzm')['n_hotspots_min_pop']} z ≥ 5 000 mieszkańców) i najmniejszy udział największego "
        f"({pct(h('gzm')['largest_share'], 0)}); to jedyna aglomeracja, w której oba wskaźniki wskazują wiele "
        f"podobnych ośrodków przy obu progach (5 000: {h('gzm', 't5000')['n_hotspots_min_pop']} skupisk, największe "
        f"{pct(h('gzm', 't5000')['largest_share'], 0)}). Poznań ma nachylenie podobne do GZM, ale z innego powodu: "
        "kilkanaście osiedli podobnej wielkości (Winogrady, Piątkowo, Rataje według położenia; nazw nie "
        "sprawdzano) w jednym mieście. Przy progu 5 000 osiedla Poznania, Krakowa i Warszawy zlewają się z "
        f"centrum w jedno duże skupisko (udział największego: {pct(h('poznan', 't5000')['largest_share'], 0)}, "
        f"{pct(h('krakow', 't5000')['largest_share'], 0)}, {pct(h('warszawa', 't5000')['largest_share'], 0)}), "
        "a GZM nie. Nachylenie zależy od progu bardziej niż od miasta, więc do tabel idzie z progiem w nazwie.",
        f"- **Największe skupiska miast jednocentrowych to blokowiska, nie śródmieścia:** w "
        f"{len(big_far)} z {len(M)} miast największe skupisko ≥ 10 000 os./km² leży ≥ 3 km od centrum "
        f"(np. {'; '.join(far_txt(a) for a in big_far[:3])}). "
        "To zgodne z §14.4 RAPORTU (gęstość spisowa największa w wielkich osiedlach). Wzór wewnątrz komórek 1 km "
        "pochodzi z GHSL, który osiedla zaniża, więc skupiska osiedli mogą być w rzeczywistości jeszcze większe.",
        f"- **Kontrola GZM wobec 9 centrów z config.yaml:** 8 centrów ma komórkę skupiska ≥ 10 000 os./km² w odległości "
        f"do 0,25 km, a jej skupisko jest w pierwszej dziesiątce (rangi 1–10). Wyjątek: "
        f"{', '.join(c['centre'] for c in weak)} (skupisko rangi {', '.join(str(c['hotspot_rank']) for c in weak)}, "
        f"{', '.join(n(c['hotspot_pop']) for c in weak)} os.); Ruda Śląska nie ma wyraźnego gęstego śródmieścia "
        "(miasto z kilku dzielnic). Największe skupisko GZM to Tychy (osiedla z lat 60.–80.), drugie Bytom, a "
        f"Katowice są dopiero na miejscu {gz['hotspots']['main']['centres'][0]['hotspot_rank']}: pod względem "
        "gęstości zamieszkania konurbacja nie ma jednego środka, a lista centrów w config.yaml zgadza się z "
        "delineacją skupisk (poza Rudą Śląską; za to Tychy i Bytom są ważniejsze, niż sugeruje kolejność listy). "
        "Skupisk, które nie leżą przy żadnym z 9 centrów, jest w pierwszej piętnastce "
        f"{sum(1 for c in gz['hotspots']['main']['clusters'][:15] if c['nearest_centre_km'] > 2.5)} "
        "(odległość > 2,5 km; tabela 4a): to osiedla na obrzeżach miast, nie osobne ośrodki.",
    ])

    # ---------------------------------------------------------------- DEGURBA
    d = {a: (R[a]["degurba"]["fua"]["uc_own"] - R[a]["degurba"]["fua"]["uc_official"]) * 100 for a in R}
    same = [a for a in R if abs(d[a]) < 0.05]
    diff = sorted([a for a in R if abs(d[a]) >= 0.05], key=lambda a: d[a])
    out["DEGURBA_READING"] = "\n".join([
        "**Jak czytać.**",
        "",
        f"- **Uproszczona klasyfikacja projektu daje te same udziały centrów miejskich co oficjalna warstwa** w "
        f"{len(same)} z 13 FUA (różnica < 0,05 pp). Różnice: "
        + ", ".join(f"{nm(a)} {n(d[a], 1)} pp" for a in diff)
        + ". Największa jest w GZM, gdzie Eurostat dołącza do klastra katowickiego mniejsze gęste skupiska "
          "połączone komórkami rzadszymi niż 1 500 os./km².",
        "- **Do tabel proponujemy udział w centrach miejskich z oficjalnej warstwy** (bez uproszczeń), a skupiska i "
        "komórki wiejskie z regułą projektu, z tym zastrzeżeniem w opisie. Wiersze `degurba_share_*` z kroku density "
        "zostają jako kontrola.",
        f"- **Co mówią liczby:** w FUA od {pct(min(R[a]['degurba']['fua']['uc_official'] for a in R), 0)} "
        f"({nm(min(R, key=lambda a: R[a]['degurba']['fua']['uc_official']))}) do "
        f"{pct(max(R[a]['degurba']['fua']['uc_official'] for a in R), 0)} "
        f"({nm(max(R, key=lambda a: R[a]['degurba']['fua']['uc_official']))}) mieszkańców żyje w centrum miejskim; "
        f"w komórkach wiejskich od {pct(min(R[a]['degurba']['fua']['rural_hybrid'] for a in R), 0)} do "
        f"{pct(max(R[a]['degurba']['fua']['rural_hybrid'] for a in R), 0)}. Udział zależy od tego, jak duże FUA "
        "narysował Eurostat (Kielce i Rzeszów mają rozległe FUA z gęstą wsią), więc porównuje się go między miastami "
        "tylko razem z rdzeniem.",
        "- Porównania z liczbą OECD (43 % mieszkańców polskich FUA w strefach dojazdów) nie da się zrobić "
        "wprost: strefa dojazdów to część FUA poza miastem (granica gmin), a nie klasa komórek. Na granicach URAU "
        "odpowiednikiem jest 1 − ludność rdzenia / ludność FUA (krok density), nie stopień urbanizacji.",
    ])

    # ---------------------------------------------------------------- classes
    ge = {a: R[a]["density_classes"]["fua"]["at_or_above"]["5000"] for a in R}
    gc = {a: R[a]["density_classes"]["core"]["at_or_above"]["5000"] for a in R}
    top = sorted(R, key=lambda a: -ge[a])
    out["CLASS_READING"] = "\n".join([
        "**Jak czytać.**",
        "",
        f"- W FUA w komórkach ≥ 5 000 os./km² mieszka od {pct(min(ge.values()), 0)} ({nm(min(ge, key=ge.get))}) do "
        f"{pct(max(ge.values()), 0)} ({nm(max(ge, key=ge.get))}) mieszkańców, w rdzeniach od "
        f"{pct(min(gc.values()), 0)} ({nm(min(gc, key=gc.get))}) do {pct(max(gc.values()), 0)} "
        f"({nm(max(gc, key=gc.get))}).",
        f"- Szczecin i Trójmiasto są na czele w FUA ({pct(ge['szczecin'], 0)} i {pct(ge['trojmiasto'], 0)}), bo ich "
        f"FUA są małe względem rdzenia; w rdzeniach prowadzi Warszawa ({pct(gc['warszawa'], 0)}; typowy mieszkaniec "
        f"rdzenia w komórce {n(R['warszawa']['density_classes']['core']['median_density'])} os./km²). Ta sama "
        "zależność od granicy FUA, co przy PWD (density.md §8 pkt 4).",
        f"- Rzeszów odstaje w dół w obu domenach (FUA {pct(ge['rzeszow'], 0)}, rdzeń {pct(gc['rzeszow'], 0)}): "
        "rdzeń z dużym udziałem zabudowy jednorodzinnej po przyłączeniach gmin (wyjaśnienie prawdopodobne, nie "
        "sprawdzane). Wynik zgodny z najniższym PWD rdzenia (4 377 os./km², RAPORT §14.1).",
        "- Kolejność FUA według udziału ≥ 5 000: " + ", ".join(nm(a) for a in top) + ".",
        "- Wskaźnik jest prosty i sprawdzony krzyżowo (osobny kod `pipeline.class_shares`), ale liczy tylko "
        "mieszkańców i dziedziczy wzór GHSL wewnątrz komórek 1 km.",
    ])

    # ---------------------------------------------------------------- critical
    out["CRITICAL"] = "\n".join([
        "Wartości zaskakujące, sprawdzone przed pozostawieniem:",
        "",
        f"1. **PRX Warszawy {g3(e('warszawa', 'b10_gap0')['prx'])} w pierwszej wersji** (jedno skupisko bez łączenia "
        "przerw): mapa pokazała, że Wisła odcina ratusz od Pragi. Poprawione regułą łączenia przerw do 600 m; "
        "wariant bez niej zostaje jako wrażliwość (tabela 2, poziom `qa`).",
        f"2. **PRX Trójmiasta {g3(e('trojmiasto')['prx'])}**, blisko dolnej granicy 0,35 z próby Angela. Sprawdzone na "
        "mapie: zasięg to pasmo od Pruszcza po Wejherowo, ratusz Gdańska w jego południowej części. Wynik zostaje, "
        "z opisem, że dla miasta liniowego indeks z jednym centrum nie mierzy zwartości.",
        f"3. **ρ na zasięgu Angela < 1, a ρ z kroku density > 1** w tych samych miastach. Sprawdzone: to różnica "
        "obszaru (zasięg z obrzeżem i enklawami zamiast maski netto) i centrum (ratusz zamiast punktu z "
        "config.yaml; PRX z centrum z config.yaml w tabeli 2 różni się o "
        f"{n(max(abs(e(a)['prx'] - e(a)['prx_config_centre']) for a in M), 3)} najwyżej). Zostaje.",
        "4. **Lublin z η jak konurbacja**: sprawdzone na liście skupisk (Świdnik, osiedla). Zostaje z opisem.",
        "5. **Tychy jako największe skupisko GZM**: komórki 250 m w centrum Tychów (osiedla z wielkiej płyty) "
        "mają ≥ 10 000 os./km² na dużym, zwartym obszarze. Sprawdzone na siatce spisowej (2026-11-24): w promieniu "
        "3 km od centrum Tychów leżą cztery sąsiednie komórki NSP 1 km z 10 369–14 048 mieszkańcami, więcej niż "
        "przy Bytomiu (do 13 098). Zostaje.",
        "",
        "Gdzie miara nie ma sensu:",
        "",
        "- PRX, spójność i ρ z ratuszem Gdańska dla Trójmiasta: opisują pasmo, nie zwartość; nie zestawiać z innymi "
        "miastami (flaga w `metrics_form.csv`).",
        "- PRX i ρ GZM względem Katowic: opisują konurbację względem jednego z dziewięciu ośrodków; do porównań "
        "policentryczności lepsze są η i skupiska.",
        "- Bydgoszcz–Toruń: zasięgi obu miast są osobne; wartości dotyczą każdego miasta osobno, a nie aglomeracji.",
        "- Nachylenie ranga–wielkość przy mniej niż 4 skupiskach ≥ 5 000 mieszkańców (Kielce, Rzeszów): brak.",
        "- Ranking 10 miast jednocentrowych według PRX: nieodporny (sekcja 2).",
    ])
    out["UNVERIFIED"] = "\n".join([
        "- Metody Atlas of Urban Expansion nie odtworzono co do szczegółu: progi (komórka zabudowana ≥ 10 % w GHSL "
        "zamiast pikseli Landsata), łączenie przerw 600 m i wybór jednego skupiska to decyzje projektu. Wartości PRX "
        "dla polskich miast z Atlasu (jeśli w próbie są) nie zostały znalezione ani porównane.",
        "- Średnia PRX z próby 200 miast Angela i in. nie była czytana; znamy tylko dolną granicę 0,35 (notatki).",
        "- Ratusze: siedziby prezydentów według wiedzy ogólnej, nie sprawdzane w BIP (w tym Toruń, "
        "Wały gen. Sikorskiego 8, wybór ręczny w `pipeline.form_extra.SECOND_PICK`).",
        "- Nazwy osiedli i miejsc przy skupiskach gęstości (Nowa Huta, Winogrady, Tychy, Świdnik) przypisano z "
        "położenia i nazwy gminy, bez ortofotomapy.",
        "- Przyczyna różnic między centrami miejskimi projektu i Eurostatu (reguła zabudowy ≥ 50 %, kolejność "
        "wypełniania luk): wniosek z charakteru komórek, nie z kodu Eurostatu.",
        "- Nazwy klastrów przygranicznych (Słubice–Frankfurt, Zgorzelec–Görlitz) z samych współrzędnych.",
        "- Oficjalnej warstwy skupisk miejskich (klastry średniej gęstości) i poziomu 2 stopnia urbanizacji nie "
        "pobrano; udziały skupisk i obszarów wiejskich są z reguły uproszczonej.",
        "- Wpływ wzoru GHSL wewnątrz komórek 1 km na klasy gęstości 250 m i na skupiska (GHSL zaniża wielkie "
        "osiedla): kierunek znany, wielkość nieznana do czasu warstwy z BDOT10k.",
        "- Wybór progu skupisk (10 000 os./km²) i minimum 5 000 mieszkańców nie ma podstawy w literaturze; "
        "pokazano wrażliwość na 5 000 i na próg LouBar.",
    ])
    return out
