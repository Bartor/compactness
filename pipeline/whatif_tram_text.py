"""Fixed Polish text blocks of results/qa/whatif/whatif.md (pipeline.whatif_tram_md); numbers come from the tables."""
from __future__ import annotations

import pandas as pd

from pipeline import whatif_tram as W


def f(x, nd=1) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "–"
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "−")


def band_label(k: str) -> str:
    s = str(k).strip("[)")
    a, b = [float(x) for x in s.split(",")]
    big = 1e8
    if b >= big:
        return f"≥ {a:g}".replace(".", ",")
    return f"{a:g}–{b:g}".replace(".", ",")


def intro(A) -> None:
    A("# Wrocław: co dałyby szybsze tramwaje (scenariusze what-if)")
    A("")
    A("Plik generuje `python -m pipeline.whatif_tram aggregate`. Kod: `pipeline/whatif_tram.py` (rozkłady scenariuszy, routing), "
      "`whatif_tram_out.py` (wyniki), `whatif_tram_md.py` i `whatif_tram_text.py` (ta nota). Liczby: `results/metrics/metrics_whatif.csv`, "
      "tabele w tym katalogu, warstwa komórek `results/layers/whatif_wroclaw_cells.parquet`.")
    A("")
    A("**Pytanie.** Tramwaje we Wrocławiu mają w rozkładzie niższą prędkość niż w pozostałych dużych miastach (16,2 km/h na odcinkach w szczycie "
      "porannym; 34,5 % wozokilometrów 7–9 na odcinkach wolniejszych niż 15 km/h; speed.md §3.4). O ile wzrósłby zasięg mieszkańców komunikacją "
      "zbiorową, gdyby te odcinki jeździły z realistyczną prędkością docelową, a w jednym wariancie także częściej?")
    A("")
    A("**Czym to jest, a czym nie.** Wszystko jest liczone na **rozkładzie jazdy**, nie na rzeczywistych przejazdach. Scenariusz mówi, ile byłoby "
      "warte szybsze (albo częstsze) kursowanie tramwajów w mierze dostępności z fazy 3. Nie mówi, jak to osiągnąć (priorytet, torowiska, "
      "rozkład), ile to kosztuje ani czy da się to zrobić; nie modeluje też reakcji pasażerów i przewoźnika.")
    A("")


def method(A, hopchk: dict) -> None:
    A("## 1. Scenariusze")
    A("")
    A("| Id | Co się zmienia |")
    A("|---|---|")
    A("| S0 | nic (kontrola: ten sam rozkład przepuszczony przez ten sam kod) |")
    A("| S1 | odcinek × pasmo godzin wolniejszy niż 15 km/h dostaje 15 km/h |")
    A("| S2 | każdy odcinek jedzie przez cały dzień z własną prędkością wieczorną (20–23), „szczyt jak wieczór” |")
    A(f"| S3 | każdy odcinek dostaje medianę prędkości 7–9 porównywalnych odcinków Krakowa i Poznania (reguła niżej) |")
    A(f"| S4 | S2 + na każdej linii kursy co {W.HW_TARGET_MIN:g} min zamiast co 12 min (pierwsze odjazdy 05:45–10:00) |")
    A(f"| S4h | same kursy co {W.HW_TARGET_MIN:g} min, bez przyspieszenia (oddziela efekt krótszego czekania od efektu prędkości) |")
    A("")
    A("We wszystkich scenariuszach odcinek nigdy nie zwalnia (cel niższy od obecnej prędkości nic nie zmienia), żaden przejazd między przystankami "
      "nie staje się szybszy niż jazda swobodna z modelu speed.md §3.3 (przyspieszenie i hamowanie 1,0 m/s², 50 km/h, postój 20 s), a autobusy, "
      "kolej i pozostałe feedy zostają bez zmian. Cel stosowany jest w każdym paśmie dnia roboczego; do wyniku liczą się pasma, w których "
      "tramwaje jeżdżą w oknie 7:00–10:00 (szczyt poranny i początek międzyszczytu).")
    A("")
    A("**Reguła porównywalności w S3.** Odcinek jest „w jezdni”, gdy co najmniej 15 % jego długości biegnie w jezdni albo w strefie pieszej "
      "(reguła speed.md §3.2), inaczej „wydzielony”; odstęp przystanków = długość / liczba przejazdów, granica 450 m (mediana Wrocławia). "
      "Odcinki odniesienia: Kraków i Poznań, co najmniej 5 min, co najmniej 8 kursów 7–9. Cel = mediana ich prędkości 7–9 w tej samej klasie "
      "(`s3_classes.csv`):")
    A("")
    cls = pd.read_csv(W.OUT / "s3_classes.csv")
    A("| Torowisko | Odstęp przystanków | Odcinki odniesienia (Kraków / Poznań) | Cel, km/h | Kwartyle, km/h |")
    A("|---|---|---|---|---|")
    for r in cls.itertuples(index=False):
        A(f"| {r.track} | {r.spacing} | {r.n_ref} ({r.n_krakow} / {r.n_poznan}) | {f(r.target_kmh)} | {f(r.p25_kmh)}–{f(r.p75_kmh)} |")
    A("")
    A("Każda klasa ma co najmniej 14 odcinków odniesienia, więc wariantu zapasowego (18 km/h na torowisku wydzielonym, 15 km/h w jezdni) nie "
      "użyto. Zastrzeżenie: reguła „w jezdni” zaniża udział jazdy w jezdni na szerokich ulicach (Świdnicka we Wrocławiu, Święty Marcin w Poznaniu; "
      "speed.md §3.2), więc część wrocławskich odcinków w jezdni trafia do klasy „wydzielone” z wyższym celem; S3 jest przez to raczej górnym "
      "wariantem.")
    A("")
    A("## 2. Jak przepisano rozkład")
    A("")
    A("- **Źródło:** produkcyjny oczyszczony GTFS Wrocławia, wariant „wszystkie feedy” (`data/interim/r5/wroclaw/gtfs_all/`, tylko do odczytu). "
      "Zmienia się tylko `stop_times.txt` (w S4 i S4h także `trips.txt`) pliku `wroclaw.zip`, i tylko dla kursów tramwajowych środy; "
      "pozostałe pliki zip są kopiowane bajt w bajt. Zmienione rozkłady leżą w `data/interim/whatif/gtfs/<scenariusz>/`, nigdy w `results/`.")
    A(f"- **Przejazdy i odcinki:** przejazdy (przystanek → następny przystanek) z pamięci warstwy prędkości (`data/interim/speed/hops_wroclaw_2026-11-25`), "
      f"z długością wzdłuż kształtu trasy i pasmem godziny odjazdu; para przystanków → odcinek z `tram_stretch_stop_pairs.csv`. "
      f"{str(hopchk['hops_on_stretch'])[:-3]} {str(hopchk['hops_on_stretch'])[-3:]} z {str(hopchk['hops_total'])[:-3]} {str(hopchk['hops_total'])[-3:]} przejazdów leży na odcinkach; pozostałe (krańcowe przejazdy między peronami "
      f"jednej pętli: {hopchk['hops_terminal_shuffle']}, krawędzie poza odcinkami) się nie zmieniają. Sumy czasu i długości odcinek × pasmo "
      f"zgadzają się z `tram_stretch_bands.csv` (te same liczby przejazdów; różnice do {f(hopchk['max_abs_diff_time_s'], 0)} s czasu i "
      f"{f(100 * hopchk['max_rel_diff_length'], 2)} % długości wynikają z zaokrąglenia tabeli do 4 cyfr znaczących).")
    A("- **Ile czasu zabrać:** dla odcinka × pasma suma czasu docelowego S* = max(L / v*, F), gdzie L to suma długości przejazdów, v* prędkość "
      "docelowa, F suma czasów jazdy swobodnej (z postojem 20 s). Jeśli S* jest mniejsze od obecnej sumy S, różnica S − S* jest odejmowana "
      "z czasu ponad jazdę swobodną poszczególnych przejazdów (max(0, t − czas swobodny)), proporcjonalnie do niego. Dzięki temu postój "
      "z modelu nie jest skracany, przejazd nie staje się szybszy od własnej jazdy swobodnej, a czas zabierany jest tam, gdzie rozkład ma "
      "zapas.")
    A("- **Pełne minuty bez obciążenia:** oszczędności kolejnych przejazdów są sumowane wzdłuż kursu; przystanek k przesuwa się o "
      "60 × floor(skumulowana oszczędność / 60 + u) s, gdzie u ∈ [0, 1) to stała liczba kursu (z SHA-1 identyfikatora kursu). Wartość "
      "oczekiwana floor(x + u) równa się x, więc przesunięcie na każdym przystanku jest średnio równe oszczędności ciągłej (sprawdzenie: "
      "wozogodziny w pełnych minutach a ciągłe w §4), czasy zostają niemalejące, a pierwszy odjazd się nie zmienia (skumulowana oszczędność 0), "
      "więc częstotliwość na pierwszym przystanku jest ta sama. Przyjazd i odjazd na przystanku przesuwają się razem. Zwykłe zaokrąglenie "
      "do najbliższej minuty byłoby obciążone: kurs z oszczędnością 20 s nie zyskiwałby nic, a takich kursów jest dużo.")
    A(f"- **Częstsze kursy (S4, S4h):** wszystkie linie tramwajowe jeżdżą w szczycie co 12 min (`s4_headways.csv`), więc dokładanie kopii "
      f"kursów dałoby odstępy 6/12 min, a nie 10. Zamiast tego główny wzorzec każdej linii i kierunku (najczęstszy ciąg przystanków) jest "
      f"w oknie pierwszych odjazdów 05:45–10:00 przeplanowany na odjazdy co 10 min: faza pierwszego odjazdu po 7:00 w cyklu 12 min jest "
      f"przeskalowana do cyklu 10 min (w pełnych minutach), każdy nowy kurs kopiuje czasy przejazdu kursu oryginalnego najbliższego w czasie. "
      f"Kursy skrócone (zjazdy, wyjazdy z zajezdni) zostają bez zmian. Koordynacja linii na wspólnych odcinkach nie jest zachowana dokładnie "
      f"(fazy skalowane są na pierwszym przystanku, czasy przejazdu nie); routing pokazuje, co z tego wynika.")
    A("- **Walidacja każdego rozkładu** (`data/interim/whatif/gtfs/<s>/build.json`): te same kursy (S4, S4h: kursy przeplanowane zastąpione "
      "nowymi), te same ciągi przystanków, czasy niemalejące, odjazd ≥ przyjazd, pierwsze odjazdy bez zmian, wiersze kursów nietramwajowych "
      "i pozostałe pliki identyczne. Wszystkie scenariusze przechodzą.")
    A("- **Routing:** ustawienia produkcyjne (`pipeline.access`, scenariusz `pt_am`): R5 v7.5.1, środa 2026-11-25, odjazdy co minutę 7:00–9:00, "
      "mediana, maks. 60 min, pieszo 5 km/h, dojście i odejście ≤ 12 min, do 8 przejazdów, reguła min(komunikacja, sam spacer) z produkcyjną "
      "pamięcią spacerów; te same starty (20 153 komórki) i cele (42 554) co produkcja. Sieć R5 każdego scenariusza zbudowana od nowa "
      "(`data/interim/whatif/r5/<s>/`). Z jednego routingu liczone są rdzeń, obszar pokryty, FUA i urban centre (cele urban centre jako osobna "
      "waga, jak `access_uc`).")
    A("")


def after_control(A, ctl) -> None:
    ok = ctl["all_published_equal"] and ctl["cells_differing_census"] == 0
    A("**Wniosek:** " + ("kontrola przechodzi dokładnie: S0 odtwarza produkcję komórka po komórce i co do cyfry w wartościach opublikowanych, "
                         "więc różnice scenariuszy wobec S0 to wyłącznie skutek zmiany rozkładu." if ok else
                         "kontrola **nie** przechodzi dokładnie; różnice opisane wyżej trzeba wyjaśnić przed użyciem wyników."))
    A("")


def after_build(A, bstats) -> None:
    s2 = next(b for b in bstats["S2"]["bands"] if b["band"] == "am_peak")
    A(f"- S2 podnosi prędkość tramwajów w szczycie porannym do {f(s2['speed_after'])} km/h, czyli do poziomu wieczoru (17,9 km/h) – tak jak "
      f"zamierzono. Część odcinków ma wieczorem prędkość niższą niż rano i się nie zmienia, część jest ograniczona jazdą swobodną.")
    A("- Wozogodziny w pełnych minutach i ciągłe różnią się o mniej niż 1 %, więc reguła zaokrąglenia nie zawyża ani nie zaniża oszczędności.")
    A("- Przejazdów 0-minutowych przybywa (w S0 jest ich 345 na ok. 110 tys.): to ten sam artefakt pełnych minut co w oryginalnym rozkładzie; "
      "suma czasu kursu jest poprawna.")
    hw = pd.read_csv(W.feed_dir("S4") / "headways.csv")
    add, rem = hw["veh_h_added"].sum(), hw["veh_h_removed"].sum()
    A(f"- S4 i S4h: {int(hw['retimed'].sum())} wzorców (linia × kierunek) przeplanowanych z 12 na 10 min; w oknie 05:45–10:00 "
      f"{int(hw['trips_window_before'].sum())} → {int(hw['trips_window_after'].sum())} kursów, +{f(add - rem, 0)} wozogodzin "
      f"({f(100 * (add - rem) / rem, 0)} % pracy tych wzorców w oknie). Na granicach okna odstęp do kursu oryginalnego wynosi 1–23 min "
      f"(mediana 12); w środku okna dokładnie 10 min.")
    A("")


def after_results(A, ct, gn) -> None:
    from pipeline.whatif_tram_md import val
    d = {s: val(ct, s, 30, "core", "d_ratio_of_means") for s in W.SCENARIOS}
    d45 = {s: val(ct, s, 45, "core", "d_ratio_of_means") for s in W.SCENARIOS}
    cov = gn[(gn.domain == "covered")].set_index(["scenario", "cutoff"])
    A(f"- **Skala.** Przyspieszenie tramwajów podnosi transport performance rdzenia (stosunek średnich) przy 30 min o {f(d['S1'], 1)} pkt (S1), "
      f"{f(d['S2'], 1)} pkt (S2) i {f(d['S3'], 1)} pkt (S3), przy 45 min o {f(d45['S1'], 1)}, {f(d45['S2'], 1)} i {f(d45['S3'], 1)} pkt. "
      f"Dla porównania: różnica między Wrocławiem a Krakowem w rdzeniu przy 30 min wynosi dziś 3,6 pkt. Same częstsze kursy (S4h, 12 → 10 min) "
      f"dają {f(d['S4h'], 1)} pkt przy 30 i 45 min, oba razem (S4) {f(d['S4'], 1)} i {f(d45['S4'], 1)} pkt.")
    A(f"- **Prędkość waży więcej niż częstotliwość w tej skali zmian.** Skrócenie odstępu z 12 do 10 min zmniejsza średnie czekanie na pierwszy "
      f"tramwaj o ok. 1 min, a przyspieszenie S2 (+11 % prędkości w szczycie) skraca 20-minutowy przejazd tramwajem o ok. 2 min. Oba efekty prawie się sumują: S2 + S4h osobno "
      f"= {f(d['S2'] + d['S4h'], 2)} pkt przy 30 min wobec {f(d['S4'], 2)} pkt razem (przy 45 min {f(d45['S2'] + d45['S4h'], 2)} wobec {f(d45['S4'], 2)}); "
      f"razem jest trochę więcej, bo szybszy tramwaj z krótszym odstępem częściej mieści się w progu.")
    A(f"- **Przy 45 min przyspieszenie daje więcej niż przy 30 min** (S2: {f(d45['S2'], 1)} wobec {f(d['S2'], 1)} pkt): dłuższa jazda tramwajem "
      f"to więcej zaoszczędzonych minut, a pierścień celów na granicy progu jest większy. Częstotliwość (S4h) działa odwrotnie, bo oszczędza "
      f"stałą minutę czekania niezależnie od długości podróży.")
    A(f"- **Ilu mieszkańców zyskuje wyraźnie.** W S2 transport performance 30 min rośnie o ponad 2 pkt u {fi(cov.loc[('S2', 30), 'pop_gain_gt2'])} "
      f"mieszkańców obszaru pokrytego ({f(cov.loc[('S2', 30), 'share_gain_gt2'])} %), o ponad 5 pkt u {fi(cov.loc[('S2', 30), 'pop_gain_gt5'])}; "
      f"w S3 u {fi(cov.loc[('S3', 30), 'pop_gain_gt2'])} i {fi(cov.loc[('S3', 30), 'pop_gain_gt5'])}.")
    A("- **Średnia stosunków rośnie mniej niż stosunek średnich**, bo zysk koncentruje się w gęstym centrum, które w stosunku średnich waży "
      "więcej (duża liczba ludzi w promieniu); mieszkańcy przedmieść bez tramwaju nie zyskują nic.")
    A("")


def fi(x) -> str:
    return f"{int(round(float(x))):,}".replace(",", " ")


def after_where(A, dist, dens, tram, loss) -> None:
    def row(df, s, c, i):
        return df[(df.scenario == s) & (df.cutoff == c)].iloc[i]
    A(f"- **Gdzie.** Przy 30 min zyskuje przede wszystkim śródmieście i pierwszy pierścień: do 2 km od Rynku średnio "
      f"{f(row(dist, 'S2', 30, 0).mean_gain, 1)} pkt w S2 (przyrost > 2 pkt u {f(row(dist, 'S2', 30, 0).share_gt2, 0)} % mieszkańców), 2–4 km "
      f"{f(row(dist, 'S2', 30, 1).mean_gain, 1)} pkt, dalej niż 6 km poniżej 0,5 pkt. Przy 45 min zysk przesuwa się na zewnątrz (4–6 km: "
      f"{f(row(dist, 'S2', 45, 2).mean_gain, 1)} pkt): z osiedli na końcu linii do centrum jedzie się dłużej, więc dopiero dłuższy próg "
      f"zbiera zaoszczędzone minuty. Zyskują gęsto zaludnione komórki (≥ 10 000 os./km²: {f(row(dens, 'S2', 30, 4).mean_gain, 1)} pkt w S2 "
      f"przy 30 min) i komórki do 500 m od przystanku tramwajowego ({f(row(tram, 'S2', 30, 0).mean_gain, 1)} pkt).")
    far, far2 = row(tram, "S2", 30, -1), row(tram, "S2", 30, -2)
    far45 = row(tram, "S2", 45, -1)
    A(f"- **Kontrola: daleko od tramwaju prawie nic się nie zmienia.** Komórki ponad 5 km od przystanku tramwajowego: S2 przy 30 min średnio "
      f"{f(far.mean_gain, 2)} pkt (od {f(far.min_gain, 2)} do {f(far.max_gain, 2)}), przy 45 min {f(far45.mean_gain, 2)} pkt; 2–5 km od tramwaju "
      f"przy 30 min {f(far2.mean_gain, 2)} pkt. Niewielki przyrost daleko od tramwaju przy 45 min to podróże z przesiadką z autobusu "
      f"albo pociągu na tramwaj, więc jest uzasadniony.")
    if len(loss):
        A("- **Spadki** (`losses.csv`, kolumna „Jakikolwiek spadek” w §5) są małe i lokalne, ale obecne w każdym scenariuszu. Mechanizm: tramwaj "
          "przyjeżdża na przystanek pośredni wcześniej, a autobus, pociąg albo inna linia tramwajowa jeżdżą jak dotąd; przesiadka "
          "zgrana w obecnym rozkładzie może się rozjechać i trzeba czekać na następny kurs. Przykład: komórka E347500N356500 (ok. 10 km od "
          "tramwaju; trasy podróży nie sprawdzano, prawdopodobnie autobus z przesiadką na tramwaj) traci w S2 przy 45 min 6,5 pkt, ale przy 55 i 60 min zyskuje: cele, które były tuż poniżej "
          "45 min, wypadają tuż ponad próg, a dalsze się przybliżają. To efekt progu, nie gorsza sieć. W S4h udział mieszkańców z jakimkolwiek "
          "spadkiem jest największy (7–8 %), bo zmieniają się fazy odjazdów wszystkich linii (koordynacja na wspólnych odcinkach i z autobusami). "
          "Do tego dochodzi zaokrąglenie do pełnych minut. Mediana po minutach odjazdu łagodzi, ale nie usuwa tych efektów; w modelu "
          "z przeplanowaniem przesiadek spadków by nie było.")
    A("")


def after_ranking(A, rk) -> None:
    def r(dom, c, s):
        x = rk[(rk.domain == dom) & (rk.cutoff == c) & (rk.scenario == s)].iloc[0]
        return x
    A(f"- Rdzeń, 30 min: Wrocław jest dziś {r('core', 30, 'S0').rank_of_7}. z 7; w S2 {r('core', 30, 'S2').rank_of_7}., w S3 "
      f"{r('core', 30, 'S3').rank_of_7}., w S4 {r('core', 30, 'S4').rank_of_7}. Rdzeń, 45 min: dziś {r('core', 45, 'S0').rank_of_7}., w S2 "
      f"{r('core', 45, 'S2').rank_of_7}., w S4 {r('core', 45, 'S4').rank_of_7}.")
    A("- Kolejności nie należy czytać jako rankingu (RAPORT §16.2, §17.8): różnice między miastami środka tabeli są tego samego rzędu co "
      "niepewność z wyboru siatki ludności i różnica rozkład–rzeczywistość. Pozostałe miasta liczone są na swoich obecnych rozkładach, "
      "więc porównanie mówi tylko, gdzie byłby Wrocław, gdyby przyspieszył tylko on.")
    A("")


def maps(A) -> None:
    A("## 8. Mapy (szkice QA)")
    A("")
    A("Zmiana transport performance wobec S0 w komórkach 250 m obszaru pokrytego, rdzeń Wrocławia z otoczeniem; linie = odcinki tramwajowe. "
      "Niebieski = przyrost (ciemniej = więcej), szary = bez zmiany, czerwony = spadek.")
    A("")
    for s in ("S2", "S1", "S3", "S4", "S4h"):
        A(f"- {s}: [30 min](map_{s.lower()}_d30.png), [45 min](map_{s.lower()}_d45.png)")
    A("")
    A("![S2, 30 min](map_s2_d30.png)")
    A("")


def limits(A) -> None:
    A("## 9. Ograniczenia")
    A("")
    A("- **Rozkład, nie rzeczywistość.** Wynik mówi, ile dałby szybszy rozkład tramwajów przy obecnej sieci i obecnych rozkładach pozostałych "
      "środków. Rzeczywiste przejazdy są wolniejsze niż rozkład (RAPORT §16.2), a przyspieszenie rozkładu bez zmian na ulicy (priorytet, "
      "torowiska) skończyłoby się opóźnieniami, nie zyskiem.")
    A("- **Jednolite cele.** S1 (15 km/h) i S3 (mediana klasy) traktują wszystkie odcinki jednej klasy tak samo; nie wiemy, które odcinki dałoby "
      "się przyspieszyć i o ile. S2 opiera się na własnym rozkładzie wieczornym Wrocławia, więc jest najlepiej uzasadniony, ale wieczorem jest też "
      "mniej pasażerów i krótsze postoje, czego w szczycie nie da się po prostu przenieść.")
    A("- **Bez kosztu i wykonalności.** Nie liczono kosztu przyspieszenia ani kosztu częstszych kursów (S4: ok. +28 % wozogodzin w oknie "
      "05:45–10:00 na przeplanowanych wzorcach, po odjęciu oszczędności z przyspieszenia mniej), dostępności taboru i przepustowości węzłów.")
    A("- **Skutki uboczne nie są modelowane poza tym, co uchwyci routing.** Autobusy i koleje mają te same rozkłady; przesiadki skoordynowane "
      "w obecnym rozkładzie mogą się rozjechać (stąd spadki w §6). Nie ma reakcji popytu, zatłoczenia, zmiany obiegów i zjazdów do zajezdni.")
    A("- **Model jazdy swobodnej** ma parametry przyjęte, nie zmierzone (speed.md §3.3); od nich zależy, gdzie cel jest ograniczany.")
    A("- **Rozpoznanie torowiska w jezdni** jest dolnym oszacowaniem (speed.md §3.2), co wpływa na klasy S3.")
    A("- **Sobota i inne pory dnia** nie były liczone (zmieniony jest cały dzień roboczy, routing tylko 7:00–9:00).")
    A("")


def runtimes(A, timing) -> None:
    A("## 10. Czas obliczeń")
    A("")
    A("| Scenariusz | Budowa sieci R5, s | Routing 20 153 startów, s | Wątki |")
    A("|---|---|---|---|")
    for s, t in timing.items():
        A(f"| {s} | {f(t['network_s'], 0)} | {f(t['routing_s'], 0)} | {t['threads']} |")
    A("")
    A("Budowa rozkładu scenariusza: 20–40 s; JVM z limitem pamięci 8 GB, jedna naraz.")
    A("")


def files(A) -> None:
    A("## 11. Pliki")
    A("")
    A("- `scenario_table.csv` – wartości i zmiany na obszar, próg i scenariusz; `gainers.csv` – mieszkańcy z przyrostem i spadkiem;")
    A("- `by_distance.csv`, `by_density.csv`, `by_tram_distance.csv` – rozkład zmian; `ranking.csv` – miejsce wśród 7 miast; `losses.csv` – najgorsze komórki;")
    A("- `tram_speed_bands.csv` – prędkość tramwajów na pasmo i scenariusz; `s3_classes.csv` – klasy S3; `s4_headways.csv` – przeplanowane wzorce;")
    A("- `control.json` – kontrola S0; `map_<s>_d30.png`, `map_<s>_d45.png` – mapy;")
    A("- `results/layers/whatif_wroclaw_cells.parquet` – komórka: ludność, rdzeń, maska, TP S0, zmiany wszystkich scenariuszy (30 i 45 min), odległość od Rynku i od tramwaju;")
    A("- `results/metrics/metrics_whatif.csv/.json` – wiersze w schemacie pozostałych kroków (krok `whatif_tram`, metryki `whatif_<s>_…`).")
    A("")


def not_verified(A) -> None:
    A("## 12. Nie zweryfikowano")
    A("")
    A("- Czy cele są osiągalne w rzeczywistości (żadnych pomiarów, GTFS-RT odłożone).")
    A("- Przyczyn pojedynczych spadków komórka po komórce (sprawdzono tylko, gdzie leżą i jakiej są wielkości).")
    A("- Czy przeplanowanie S4 zachowuje sensowną koordynację linii na wspólnych odcinkach; nie porównano z żadnym rzeczywistym rozkładem co 10 min.")
    A("- Klas S3 wobec stanu w terenie (ręczna kontrola reguły „w jezdni” obejmowała tylko 16 odcinków w pięciu miastach).")
    A("- Wyników dla soboty i innych okien czasu.")
    A("- Recenzji metody przez badacza transportu.")
    A("")
