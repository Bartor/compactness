"""Polish QA note of pipeline.distribution: results/qa/distribution/distribution.md (method, floor, tables, limits)."""
from __future__ import annotations

import numpy as np

from pipeline.common import RESULTS

QA = RESULTS / "qa" / "distribution"
ORDER = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
WSHORT = {"pt_am": "7–9", "pt_midday": "południe", "pt_evening": "wieczór", "pt_saturday": "sobota"}


def f(x, nd=1) -> str:
    if x is None:
        return "brak danych"
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "−")


def table(head: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def write_qa(full: dict, rows: list[dict], sizes: dict) -> None:
    C = full["cities"]
    fl = full["floor"]
    z30, z45 = fl["floors"]["30"]["0.5"], fl["floors"]["45"]["0.5"]
    cuts = full["cutoffs_min"]
    L: list[str] = []
    A = L.append
    A("# Rozkład dostępu: kto ma jaki zasięg, nie tylko średnia miasta")
    A("")
    A(f"Krok `pipeline.distribution` (2026-11-24). Rozkłady: środa {full['timetable_date']} (sobota "
      f"{full['timetable_date_saturday']}), OSM {full['osm_date']}, ludność: {full['population_date']}, siatka 250 m, "
      "wszystkie feedy. Nic nie jest liczone od nowa w routingu: krok czyta sumy z fazy 3 (`data/interim/access/`, "
      "`data/interim/access_uc/`) i wyniki fazy 2.")
    A("")
    A("Pliki: `results/charts/distribution.json` (wszystko), `results/web/charts.json` (wycinek dla strony), "
      "`results/metrics/metrics_distribution.csv/.json` (wiersze jak w innych krokach), ten plik.")
    A("")
    A("## 1. Co liczymy")
    A("")
    A("- **Wartość komórki** to transport performance z fazy 3: ludność osiągalna w czasie T ÷ ludność w promieniu "
      "odpowiadającym 15 km/h (pieszo 5 km/h) × 100. Każdy mieszkaniec dostaje wartość swojej komórki 250 m.")
    A("- **Krzywa „co najmniej X”**: jaki odsetek mieszkańców ma wynik co najmniej X (X = 0, 1, …, 100). "
      "Krzywa zastępuje jeden arbitralny próg i pokazuje cały rozkład; liczona dla komunikacji (30 i 45 min, cztery pory), "
      "pieszo i rowerem w obu wariantach LTS (30 min).")
    A("- **Częstotliwość**: odsetek mieszkańców w zasięgu 500 m pieszo od kursów co najmniej co N min (N = 5, 10, 15, 20, "
      "30). Dla rdzenia i obszaru pokrytego są to te same liczby co w `metrics_frequent` (udział punktów próbkowania "
      "komórki); dla centrum miejskiego – z klas komórek (klasa większości punktów).")
    A("- **Krzywa zasięgu 5–60 min**: stosunek średnich (jak DG REGIO) i pasmo kwartyli komórek ważonych ludnością "
      "(25., 50. i 75. percentyl; percentyl „dolny”: najmniejsza wartość, przy której skumulowany udział ludności "
      "osiąga q).")
    A("- **Minimalny zasięg** (próg) i wskaźniki Fostera–Greera–Thorbeckego: FGT0 = odsetek mieszkańców poniżej progu; "
      "FGT1 = średni niedobór do progu jako % progu, liczony na wszystkich mieszkańców (powyżej progu 0); FGT2 = to samo "
      "z kwadratem niedoboru (duże braki ważą więcej), × 100. Wskaźnik Palmy jako miara pomocnicza. Bez współczynnika "
      "Giniego (przegląd literatury, §21 raportu).")
    A("- **Obszary**: rdzeń (miasto w granicach administracyjnych; dla komunikacji tylko komórki w masce pokrycia GTFS, "
      "udział zachowanej ludności podany), obszar pokryty (komórki FUA w masce), centrum miejskie (urban centre, "
      "starty, cele i mianownik tylko w centrum, §17.5 raportu; tylko 30 i 45 min). Komórki poza maską to brak danych, "
      "nie zero, i nie wchodzą do rozkładów komunikacji.")
    A("")
    A("## 2. Próg minimalnego zasięgu")
    A("")
    A("**Reguła:** połowa mediany siedmiu miast. Mediana siedmiu miast to mediana z siedmiu median rdzeni (mediana "
      "komórek ważona ludnością, szczyt poranny), więc każde miasto liczy się raz, a Warszawa nie przeważa. Wynik "
      "zaokrąglony do pełnego punktu. Ten sam próg obowiązuje we wszystkich miastach, obszarach i porach dnia, więc "
      "odsetki poniżej progu można porównywać.")
    A("")
    A("**Dlaczego tak.** To odpowiednik względnej granicy ubóstwa (50 % mediany dochodu w OECD; 40 % i 60 % jako warianty, "
      "60 % w Eurostacie). Próg bezwzględny (np. „co najmniej 20 % okolicy w 30 min”) nie ma oparcia w literaturze "
      "dla tej miary, a próg względem mediany własnego miasta karałby miasta wyrównane i nie pozwalałby porównywać. "
      "Połowa mediany oznacza wynik, przy którym mieszkaniec osiąga w danym czasie najwyżej połowę tego, co typowy "
      "mieszkaniec rdzenia w typowym z siedmiu miast. To wybór normatywny, nie wynik badań; dlatego obok są dwa "
      "inne progi.")
    A("")
    rows_m = [[C[a]["name"], f(fl["core_medians"]["30"].get(a)), f(fl["core_medians"]["45"].get(a))] for a in ORDER]
    rows_m.append(["**mediana siedmiu miast**", f"**{f(fl['reference_median']['30'])}**", f"**{f(fl['reference_median']['45'])}**"])
    L += table(["Aglomeracja", "Mediana rdzenia, 30 min, %", "Mediana rdzenia, 45 min, %"], rows_m)
    A("")
    fr = fl["floors"]
    A(f"Progi: **30 min: {f(z30, 0)} %** (40 % mediany: {f(fr['30']['0.4'], 0)}, 60 %: {f(fr['30']['0.6'], 0)}); "
      f"**45 min: {f(z45, 0)} %** (40 %: {f(fr['45']['0.4'], 0)}, 60 %: {f(fr['45']['0.6'], 0)}).")
    A("")
    A("## 3. Wynik: mieszkańcy poniżej progu (szczyt poranny)")
    A("")

    def fb(a, dom, c):
        d = C[a]["domains"].get(dom)
        return (d or {}).get("floor", {}).get(str(c), {})

    for c, z in ((30, z30), (45, z45)):
        A(f"**{c} min, próg {f(z, 0)} %.** FGT0 = odsetek mieszkańców poniżej progu, FGT1 i FGT2 × 100.")
        A("")
        rr = []
        for a in ORDER:
            core, cov, uc = fb(a, "core", c), fb(a, "covered", c), fb(a, "urban_centre", c)
            rr.append([C[a]["name"], f(core.get("below_floor")), f(core.get("fgt1"), 2), f(core.get("fgt2"), 2),
                       f(cov.get("below_floor")), f(cov.get("fgt1"), 2), f(cov.get("fgt2"), 2), f(uc.get("below_floor"))])
        L += table(["Aglomeracja", "Rdzeń: FGT0, %", "Rdzeń: FGT1", "Rdzeń: FGT2", "Pokryty: FGT0, %", "Pokryty: FGT1",
                    "Pokryty: FGT2", "Centrum miejskie: FGT0, %"], rr)
        A("")
    A("Jak czytać FGT1: wartość 5 oznacza, że gdyby rozdzielić brakujący zasięg po równo na wszystkich mieszkańców, "
      "każdemu brakowałoby 5 % progu. Wartości centrum miejskiego liczone są z innym mianownikiem (tylko centrum), "
      "a próg pochodzi z rdzeni; porównywać je można tylko między miastami, nie z rdzeniem.")
    A("")
    A("## 4. Wrażliwość na próg")
    A("")
    rr = []
    for a in ORDER:
        r = [C[a]["name"]]
        for c in (30, 45):
            for dom in ("core", "covered"):
                e = {x["fraction_of_median"]: x["fgt0"] for x in fb(a, dom, c).get("floors", [])}
                r.append(" / ".join(f(e.get(k)) for k in (0.4, 0.5, 0.6)))
        rr.append(r)
    L += table([f"Aglomeracja", f"Rdzeń 30 min: {f(fr['30']['0.4'], 0)} / {f(z30, 0)} / {f(fr['30']['0.6'], 0)}",
                f"Pokryty 30 min", f"Rdzeń 45 min: {f(fr['45']['0.4'], 0)} / {f(z45, 0)} / {f(fr['45']['0.6'], 0)}",
                "Pokryty 45 min"], rr)
    A("")
    sens = []
    for c in ("30", "45"):
        v = {k: [next((x["fgt0"] for x in fb(a, "core", c).get("floors", []) if x["fraction_of_median"] == k), np.nan)
                 for a in ORDER] for k in (0.4, 0.5, 0.6)}
        sens.append((c, spearman(v[0.4], v[0.5]), spearman(v[0.6], v[0.5]),
                     [C[a]["name"] for a in np.array(ORDER)[np.argsort(v[0.5])[::-1]]][:2]))
    for c, r40, r60, top in sens:
        A(f"- {c} min, rdzenie: korelacja rang kolejności miast między progiem 40 % a 50 % mediany {f(r40, 2)}, między "
          f"60 % a 50 % {f(r60, 2)}; najwięcej mieszkańców poniżej progu 50 %: {', '.join(top)}.")
    A("")
    A("## 5. Krzywa zasięgu 5–60 min (rdzeń, komunikacja, szczyt poranny)")
    A("")
    A("Stosunek średnich, w nawiasie kwartyle komórek (25. / 50. / 75. percentyl), %.")
    A("")
    show = [15, 30, 45, 60]
    rr = []
    for a in ORDER:
        r = C[a]["domains"]["core"]["reach"].get("pt_am")
        if not r:
            rr.append([C[a]["name"]] + ["brak danych"] * len(show))
            continue
        rr.append([C[a]["name"]] + [f"{f(r['ratio_of_means'][cuts.index(t)])} ({f(r['p25'][cuts.index(t)])} / "
                                    f"{f(r['p50'][cuts.index(t)])} / {f(r['p75'][cuts.index(t)])})" for t in show])
    L += table(["Aglomeracja"] + [f"{t} min" for t in show], rr)
    A("")
    A("Wartości dla 5 i 10 min są w danych, ale nie należy ich czytać jako wyniku sieci: w tak krótkim czasie i "
      "promieniu (1,25 km dla 5 min) dużą część i licznika, i mianownika stanowi własna komórka mieszkańca, więc "
      "krzywa zaczyna się od ok. 10 % i bywa niemonotoniczna (np. pieszo wynik przy 5 min jest wyższy niż przy 10 min). "
      "Krzywą warto czytać od 15 min.")
    A("")
    A("## 6. Pory dnia (rdzeń)")
    A("")
    rr = []
    for a in ORDER:
        t = C[a]["domains"]["core"]["time_of_day"]
        r = [C[a]["name"]]
        for c in (30, 45):
            r.append(" / ".join(f(t.get(f"{w}_{c}", {}).get("below_floor")) for w in WSHORT))
        for c in (30, 45):
            r.append(" / ".join(f(t.get(f"{w}_{c}", {}).get("ratio_of_means")) for w in WSHORT))
        rr.append(r)
    L += table(["Aglomeracja", f"Poniżej progu {f(z30, 0)} %, 30 min: 7–9 / południe / wieczór / sobota",
                f"Poniżej progu {f(z45, 0)} %, 45 min", "Stosunek średnich, 30 min", "Stosunek średnich, 45 min"], rr)
    A("")
    A("Próg jest stały (z poranka), więc wzrost odsetka poza szczytem pokazuje, ilu mieszkańców spada poniżej "
      "minimum, gdy kursów jest mniej. Stosunek średnich różni się od tabeli §17.2 raportu o kilka dziesiątych punktu, "
      "bo tu rdzeń obejmuje tylko komórki w masce pokrycia.")
    A("")
    A("## 7. Częstotliwość: odsetek mieszkańców z kursami co najmniej co N min (rdzeń)")
    A("")
    ns = full["headway_n_min"]
    rr = []
    for a in ORDER:
        d = C[a]["domains"]["core"]
        rr.append([C[a]["name"]] + [f(x) for x in (d.get("headway_at_most") or [None] * len(ns))] +
                  [" / ".join(f(x) for x in (d.get("headway_at_most_classes") or []))])
    L += table(["Aglomeracja"] + [f"co ≤ {n} min, %" for n in ns] + ["kontrola: z klas komórek (5 … 30)"], rr)
    A("")
    A("Wartości z klas komórek są o 1–3 pkt wyższe, bo komórka dostaje klasę, w której leży co najmniej połowa jej "
      "punktów próbkowania, a metryka liczy udział punktów. Wykres na stronie używa liczb z `metrics_frequent`.")
    A("")
    A("## 8. Wskaźnik Palmy (miara pomocnicza)")
    A("")
    rr = [[C[a]["name"]] + [f(C[a]["domains"][dom]["palma"].get(c), 2) for dom in ("core", "covered") for c in ("30", "45")]
          for a in ORDER]
    L += table(["Aglomeracja", "Rdzeń 30", "Rdzeń 45", "Pokryty 30", "Pokryty 45"], rr)
    A("")
    A("Udział 10 % mieszkańców o najlepszym zasięgu w sumie wyników ÷ udział 40 % o najsłabszym. Przy równym rozkładzie "
      "0,25. Miara zależy od tego, gdzie leżą granice obszaru, i nie jest wynikiem głównym.")
    A("")
    A("## 9. Kontrole")
    A("")
    chk = full["checks"]
    ok = sum(1 for c in chk if c["ok"])
    A(f"- Średnia stosunków przeliczona tu z sum fazy 3 zgadza się z `metrics_access` / `metrics_access_uc` w {ok} z "
      f"{len(chk)} porównań (rdzeń i obszar pokryty: średnia stosunków 30 i 45 min; centrum miejskie: stosunek średnich; "
      "tolerancja 0,01 pkt + 0,1 %). Kontrola używa definicji z tamtych kroków (rdzeń z komórkami spoza maski); "
      "rozkłady w tym kroku pomijają komórki spoza maski.")
    bad = [c for c in chk if c["ok"] is False]
    for c in bad:
        A(f"  - niezgodność: {c['agglomeration']} {c['domain']} {c['metric']}: opublikowane {c['published']}, tu {c['recomputed']}")
    diffs = [abs((c["masked"] or 0) - (c["recomputed"] or 0)) for c in chk if c["domain"] == "core" and c["masked"] is not None]
    if diffs:
        A(f"- Pominięcie komórek rdzenia spoza maski podnosi średnią stosunków rdzenia o {f(min(diffs), 2)}–"
          f"{f(max(diffs), 2)} pkt.")
    A("- Krzywe „co najmniej X” są nierosnące, a odsetek przy X = 0 wynosi 100 % (sprawdzane testami "
      "`pipeline/tests/test_distribution.py`, funkcje w `pipeline/distribution_stats.py`).")
    A("")
    A("## 10. Co z tego wynika, czytane krytycznie")
    A("")
    g = C["gzm"]["domains"]["core"]
    w_ = C["warszawa"]["domains"]["core"]
    A(f"- **GZM** ma najwięcej mieszkańców rdzenia poniżej progu 30 min ({f(fb('gzm', 'core', 30).get('below_floor'))} %, "
      f"Warszawa {f(fb('warszawa', 'core', 30).get('below_floor'))} %), a wieczorem i w sobotę odsetek rośnie do "
      f"{f(g['time_of_day'].get('pt_evening_30', {}).get('below_floor'))} i "
      f"{f(g['time_of_day'].get('pt_saturday_30', {}).get('below_floor'))} %. Zgadza się to ze spadkami poza szczytem "
      "z §17.2 raportu, których przyczyny nie ustalono.")
    A(f"- **Górny ogon GZM to Tychy, nie lepsza obsługa.** {f(g['at_least']['pt_am_30'][60])} % mieszkańców rdzenia GZM ma "
      f"wynik 30 min co najmniej 60 % (we Wrocławiu {f(C['wroclaw']['domains']['core']['at_least']['pt_am_30'][60])} %). "
      "Sprawdzone 2026-11-24 na sumach fazy 3: 99 % tych mieszkańców mieszka w prostokącie obejmującym Tychy "
      "(50,06–50,17° N, 18,88–19,06° E; prostokąt, nie granica gminy). W promieniu 7,5 km od tych komórek mieszka "
      "ok. 140 tys. osób (mediana), wobec ok. 270 tys. dla typowej komórki rdzenia GZM, więc mały mianownik daje "
      "wysoki stosunek. To cecha miary względnej, nie dowód lepszej sieci; prawdopodobnie podnosi też wskaźnik Palmy "
      "GZM (najwyższy z rdzeni), czego osobno nie sprawdzano.")
    A(f"- **Warszawa** ma najmniej mieszkańców rdzenia poniżej progu, także poza szczytem; jej pasmo kwartyli przy 30 min "
      f"({f(w_['reach']['pt_am']['p25'][cuts.index(30)])}–{f(w_['reach']['pt_am']['p75'][cuts.index(30)])}) jest "
      "przesunięte w górę, nie węższe niż w innych miastach.")
    cov30 = {a: fb(a, "covered", 30).get("below_floor") for a in ORDER}
    gap = {a: (cov30[a] or 0) - (fb(a, "core", 30).get("below_floor") or 0) for a in ORDER}
    top_cov = sorted(ORDER, key=lambda a: -(cov30[a] or 0))[:2]
    small = min(ORDER, key=lambda a: gap[a])
    A(f"- **Obszar pokryty** ma {'wszędzie' if min(gap.values()) > 0 else 'prawie wszędzie'} więcej mieszkańców poniżej "
      f"progu niż rdzeń; przy 30 min najwięcej {C[top_cov[0]]['name']} ({f(cov30[top_cov[0]])} %) i "
      f"{C[top_cov[1]]['name']} ({f(cov30[top_cov[1]])} %). Najmniejsza różnica rdzeń–obszar pokryty: "
      f"{C[small]['name']} ({f(gap[small])} pkt)" + ("; tam rdzeń i obszar pokryty mają też prawie ten sam wynik średni "
      "(§17.1)." if small == "trojmiasto" else "."))
    worst = {k: max(ORDER, key=lambda a: next((x["fgt0"] for x in fb(a, "core", 30).get("floors", [])
                                               if x["fraction_of_median"] == k), -1)) for k in (0.4, 0.5, 0.6)}
    spread = {a: [x["fgt0"] for x in fb(a, "core", 30).get("floors", [])] for a in ORDER}
    big = [C[a]["name"] for a in ORDER if spread[a] and max(spread[a]) - min(spread[a]) > 10]
    same = len(set(worst.values())) == 1
    A(f"- **Wybór progu.** {'Przy każdym z trzech progów najgorzej wypada ' + C[worst[0.5]]['name'] if same else 'Najgorsze miasto zmienia się z progiem'}"
      f", ale kolejność środka tabeli się zmienia (korelacja rang z progiem głównym {f(min(min(x[1], x[2]) for x in sens), 2)}–{f(max(max(x[1], x[2]) for x in sens), 2)}, §4), a poziomy zależą od "
      f"progu wyraźnie: przy 30 min między progiem {f(fr['30']['0.4'], 0)} a {f(fr['30']['0.6'], 0)} % odsetek rośnie o ponad "
      f"10 pkt w: {', '.join(big) if big else 'żadnym mieście'}. Odsetek poniżej progu nadaje się do pokazania, gdzie "
      "jest problem, nie do rankingu miast o zbliżonych wartościach.")
    A("")
    A("## 11. Ograniczenia")
    A("")
    A("- Próg jest normatywny i względny: przesuwa się, gdy zmienią się mediany miast. Nie mówi, jaki zasięg jest "
      "„wystarczający” dla konkretnej potrzeby.")
    A("- Jednostką jest komórka 250 m, nie osoba: wszyscy mieszkańcy komórki dostają tę samą wartość, więc rozkład "
      "jest węższy niż rozkład podróży rzeczywistych osób.")
    A("- Brak cech społeczno-ekonomicznych: to rozkład przestrzenny, nie rozkład według grup ludności (§16.3 raportu).")
    A("- Wszystkie zastrzeżenia fazy 3: rozkład jazdy zamiast rzeczywistości (5–15 % zawyżenia w literaturze), "
      "wybór siatki ludności (3–7 pkt), granice obszaru (§16.2, §17.8). Wariantu z surowym GHSL tu nie liczono.")
    A("- Centrum miejskie: tylko 30 i 45 min, bez pór dnia i bez krzywej 5–60 min (pamięć podręczna `access_uc` ma "
      "mianownik tylko dla tych dwóch progów).")
    A("- Krzywa częstotliwości dla rdzenia i obszaru pokrytego ma tylko pięć punktów (progi fazy 2), więc na wykresie "
      "jest schodkowa.")
    A("")
    A("## 12. Rozmiary plików")
    A("")
    L += table(["Plik", "kB"], [[k, f(v)] for k, v in sorted(sizes.items())])
    A("")
    A(f"Wierszy metryk: {len(rows)} (w tym `main`: {sum(r['tier'] == 'main' for r in rows)}).")
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "distribution.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
