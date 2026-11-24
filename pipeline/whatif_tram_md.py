"""Polish QA note of the Wrocław tram what-if: results/qa/whatif/whatif.md (called by pipeline.whatif_tram_out)."""
from __future__ import annotations

import pandas as pd

from pipeline import whatif_tram as W

NAMES = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
         "trojmiasto": "Trójmiasto", "gzm": "GZM"}
BAND_PL = {"night": "noc 23–05", "early": "wczesny ranek 05–07", "am_peak": "szczyt poranny 07–09",
           "midday": "międzyszczyt 09–15", "pm_peak": "szczyt popołudniowy 15–18", "early_eve": "wczesny wieczór 18–20",
           "evening": "wieczór 20–23"}
BAND_ORDER = list(BAND_PL)
DOM_PL = {"core": "rdzeń", "covered": "obszar pokryty", "fua": "FUA", "urban_centre": "urban centre"}


def f(x, nd=1) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "–"
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "−")


def fs(x, nd=1) -> str:
    """Signed."""
    if x is None or (isinstance(x, float) and x != x):
        return "–"
    s = f(abs(x), nd)
    return ("+" if x > 0 else ("−" if x < 0 else "")) + s if s.strip("0,") else "0" + ("," + "0" * nd if nd else "")


def fi(x) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "–"
    return f"{int(round(x)):,}".replace(",", " ")


def val(ct, s, c, dom, k="ratio_of_means"):
    r = ct[(ct.scenario == s) & (ct.cutoff == c) & (ct.domain == dom)]
    return float(r[k].iloc[0])


def write(*, ctl, ct, gn, dist, dens, tram, rk, bstats, loss, timing, hopchk) -> None:
    from pipeline import whatif_tram_text as T
    L: list[str] = []
    A = L.append
    T.intro(A)
    T.method(A, hopchk)
    # control
    A("## 3. Kontrola (S0)")
    A("")
    A("S0 to rozkład bez zmian przepuszczony przez ten sam czytnik i zapis co scenariusze. Plik `wroclaw.zip` S0 jest **bajtowo identyczny** "
      "z plikiem produkcyjnym, sieć R5 zbudowano od nowa w katalogu scenariusza i policzono wszystkie starty.")
    A("")
    A(f"- Komórki: {fi(ctl['cells'])}; suma ludności osiągalnej (siatka spisowa i surowy GHSL, progi 5–60 min) różni się od produkcji "
      f"w {ctl['cells_differing_census']} i {ctl['cells_differing_raw']} komórkach, maks. różnica {f(ctl['max_abs_diff_census'], 3)} i "
      f"{f(ctl['max_abs_diff_raw'], 3)} os.; sam wynik R5 (bez reguły pieszej) maks. różnica {f(ctl['max_abs_diff_r5only_30'], 3)} (30 min) i "
      f"{f(ctl['max_abs_diff_r5only_45'], 3)} (45 min).")
    A(f"- Urban centre (porównanie z osobnym routingiem `access_uc`): maks. różnica {f(ctl['uc_max_abs_diff'], 3)} os.")
    A("- Wartości opublikowane (4 cyfry znaczące) a S0:")
    A("")
    A("| Obszar | Miara | S0 | Opublikowane | Zgodne |")
    A("|---|---|---|---|---|")
    for r in ctl["published"]:
        A(f"| {DOM_PL[r['domain']]} | `{r['metric']}` | {f(r['s0'], 2)} | {f(r['published'], 2)} | {'tak' if r['equal'] else '**nie**'} |")
    A("")
    T.after_control(A, ctl)
    # build table
    A("## 4. Zmieniony rozkład: prędkość i wozogodziny")
    A("")
    A("Prędkość rozkładowa na odcinkach (suma długości / suma czasu przejazdów, czasy po zaokrągleniu do pełnych minut), środa, km/h; "
      "w nawiasie wariant bez zaokrąglenia (ciągłe sekundy), który pokazuje, że zaokrąglenie nie przesuwa wyniku.")
    A("")
    A("| Pasmo | S0 | S1 | S2 | S3 |")
    A("|---|---|---|---|---|")
    for bnd in BAND_ORDER:
        cells = []
        for s in ("S0", "S1", "S2", "S3"):
            b = next((x for x in bstats[s]["bands"] if x["band"] == bnd), None)
            cells.append("–" if b is None else (f(b["speed_after"], 1) if s == "S0" else f"{f(b['speed_after'], 1)} ({f(b['speed_after_continuous'], 1)})"))
        A(f"| {BAND_PL[bnd]} | " + " | ".join(cells) + " |")
    A("")
    A("| Scenariusz | Wozokm 7–9 na odcinkach < 15 km/h | Wozogodziny oszczędzone w dobie (pełne minuty / ciągłe) | Kursy skrócone | Maks. skrócenie kursu, min | Grupy odcinek × pasmo zmienione | W tym ograniczone jazdą swobodną | Przejazdy 0 min (S4, S4h: kursy nieprzeplanowane) |")
    A("|---|---|---|---|---|---|---|---|")
    for s in W.SCENARIOS:
        st = bstats[s]
        A(f"| {s} | {f(st['share_vkm_below_15_am_peak_after'])} % | {f(st['veh_h_saved_day'])} / {f(st['veh_h_saved_day_continuous'])} | "
          f"{fi(st['trips_shortened'])} z {fi(st['trips'])} | {f(st['max_trip_saving_min'], 0)} | {st['groups_changed']} z {st['groups']} | "
          f"{st['groups_capped_by_free_running']} | {fi(st['validation']['tram_hops_0min'])} z {fi(st['validation']['tram_hops'])} |")
    A("")
    T.after_build(A, bstats)
    # scenario table
    A("## 5. Wyniki: transport performance")
    A("")
    A("Stosunek średnich (wynik główny), w nawiasie średnia stosunków (typowy mieszkaniec); środa 7:00–9:00, wszystkie feedy, siatka spisowa. "
      "Zmiana wobec S0 w punktach.")
    A("")
    for c in (30, 45):
        A(f"**{c} min**")
        A("")
        A("| Scenariusz | Rdzeń | Zmiana | Obszar pokryty | Zmiana | Urban centre | Zmiana |")
        A("|---|---|---|---|---|---|---|")
        for s in W.SCENARIOS:
            cells = []
            for dom in ("core", "covered", "urban_centre"):
                v, m = val(ct, s, c, dom), val(ct, s, c, dom, "mean_of_ratios")
                dv, dm = val(ct, s, c, dom, "d_ratio_of_means"), val(ct, s, c, dom, "d_mean_of_ratios")
                cells += [f"{f(v)} ({f(m)})", "" if s == "S0" else f"{fs(dv, 2)} ({fs(dm, 2)})"]
            A(f"| {s} | " + " | ".join(cells) + " |")
        A("")
    A("Mieszkańcy, u których transport performance rośnie (obszar pokryty; komórki 250 m):")
    A("")
    A("| Scenariusz | Próg | > 2 pkt, os. | > 2 pkt, % | > 5 pkt, os. | > 5 pkt, % | Jakikolwiek spadek, % | Spadek > 1 pkt, os. | Maks. przyrost / spadek, pkt |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in gn[gn.domain == "covered"].itertuples(index=False):
        A(f"| {r.scenario} | {r.cutoff} min | {fi(r.pop_gain_gt2)} | {f(r.share_gain_gt2)} | {fi(r.pop_gain_gt5)} | {f(r.share_gain_gt5)} | "
          f"{f(r.share_loss_any)} | {fi(r.pop_loss_gt1)} | {fs(r.max_gain)} / {fs(r.max_loss)} |")
    A("")
    T.after_results(A, ct, gn)
    # who gains, where
    A("## 6. Kto zyskuje i gdzie")
    A("")
    for title, df, col in (("Odległość od Rynku, km", dist, "dist_centre_km"), ("Gęstość zaludnienia komórki, os./km²", dens, "density_per_km2"),
                           ("Odległość od najbliższego przystanku tramwajowego, m", tram, "dist_tram_stop_m")):
        A(f"**{title}** (obszar pokryty; średni przyrost ważony ludnością, pkt; w nawiasie udział mieszkańców z przyrostem > 2 pkt)")
        A("")
        A("| Przedział | Mieszkańcy | S1 30 | S2 30 | S3 30 | S4 30 | S4h 30 | S2 45 |")
        A("|---|---|---|---|---|---|---|---|")
        for k in df[col].unique():
            sub = df[df[col] == k]
            pop = sub["population"].iloc[0]
            cells = []
            for s, c in (("S1", 30), ("S2", 30), ("S3", 30), ("S4", 30), ("S4h", 30), ("S2", 45)):
                r = sub[(sub.scenario == s) & (sub.cutoff == c)].iloc[0]
                cells.append(f"{fs(r.mean_gain, 2)} ({f(r.share_gt2, 0)} %)")
            A(f"| {T.band_label(k)} | {fi(pop)} | " + " | ".join(cells) + " |")
        A("")
    T.after_where(A, dist, dens, tram, loss)
    # ranking
    A("## 7. Miejsce Wrocławia wśród siedmiu miast")
    A("")
    A("Stosunek średnich; pozostałe miasta z wyników produkcyjnych (`metrics_access.csv`, `metrics_access_uc.csv`), bez zmian.")
    A("")
    A("| Obszar | Próg | S0 | S1 | S2 | S3 | S4 | S4h | Pozostałe miasta |")
    A("|---|---|---|---|---|---|---|---|---|")
    for dom in ("core", "covered", "urban_centre"):
        for c in (30, 45):
            sub = rk[(rk.domain == dom) & (rk.cutoff == c)].set_index("scenario")
            cells = [f"{f(sub.loc[s, 'value'])} ({sub.loc[s, 'rank_of_7']}.)" for s in W.SCENARIOS]
            A(f"| {DOM_PL[dom]} | {c} min | " + " | ".join(cells) + f" | {sub.loc['S0', 'others']} |")
    A("")
    T.after_ranking(A, rk)
    T.maps(A)
    T.limits(A)
    T.runtimes(A, timing)
    T.files(A)
    T.not_verified(A)
    (W.QA / "whatif.md").write_text("\n".join(L) + "\n", encoding="utf-8")
