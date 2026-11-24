"""Density x service frequency: how well the dense parts of the agglomerations are served (bivariate layer).

    python -m pipeline.density_service

Source: results/layers/frequent_cells.parquet (250 m cells, census-scaled population, best headway class within
500 m walk, GTFS coverage mask, feed variant "all").  Every populated cell inside the coverage mask is put into one
of 3 x 3 classes (density x service); cells outside the mask are "no data" and never a class.  The metrics use the
full 3 x 3 table; the map layer folds it into the five MAP_CLASSES below, because nine blended colours cannot be
told apart reliably on a map.  The headline threshold is 5 000 people/km2 on 250 m cells (50 residents per hectare,
the published "frequent bus" density; it was 2 500 until 2026-11-24).  A threshold sweep (SWEEP_STOPS, tier
"table") repeats the two headline shares and the number of residents for density >= T, so the dependence on the
threshold is visible (the 2 500 figures stay there as a sensitivity row); the classes and the map use 5 000.

Writes results/metrics/metrics_density_service.{csv,json} (+ _meta_density_service.json) and
results/qa/density_service/{density_service.md,_meta.json}.  The class constants below are shared with
pipeline.tiles_layers (the map layer).
"""
from __future__ import annotations

import csv
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.common import RESULTS, load_config, sig, write_json, write_meta

# ------------------------------------------------------------------ classes (not in config.yaml on purpose)
CELL_KM2 = 0.0625
DENSITY_STOPS = [5000.0, 10000.0]                    # people / km2: D1 < 5 000 <= D2 < 10 000 <= D3
DENSITY_LABELS = ["< 5 000 os./km²", "5 000–10 000", "≥ 10 000"]
SERVICE_OF_HEADWAY = {">30": 1, "30": 1, "20": 2, "15": 2, "10": 3, "5": 3}      # S1 poor, S2 medium, S3 good
SERVICE_LABELS = ["rzadziej niż co 20 min lub brak", "co 11–20 min", "co ≤ 10 min"]
HEADWAY_ORDER = [">30", "30", "20", "15", "10", "5"]  # worst -> best; service level for the rank correlation
DENSE_MIN_CLASS = 2                                    # headline: residents of D2 and D3 (>= DENSITY_STOPS[0])
# Map layer: five classes, tiles property v = index; labels state the numbers, not "dense" / "sparse".  Colours for
# the dark basemap (land #1c1f26): the cells with many residents and poor service are the most salient (bright
# warm), many residents with good service a bright cool colour, medium service violet (between the two), the
# low-density classes muted (steel blue, warm grey).  All-pairs OKLab dE x100 >= 18.5 in normal vision and >= 8.5
# under simulated protanopia and deuteranopia (all-pairs palette validator, dark mode, surface #1c1f26); the muted
# classes fall outside the validator's lightness band and chroma floor on purpose.
_T = "5 000 os./km²"
MAP_CLASSES = [(f"≥ {_T}, kursy rzadziej niż co 20 min lub brak", "#FF5A2E"),
               (f"≥ {_T}, co 11–20 min", "#C98BE3"),
               (f"≥ {_T}, co ≤ 10 min", "#4FD6FF"),
               (f"< {_T}, co ≤ 20 min", "#3F78A3"),
               (f"< {_T}, rzadziej lub brak", "#4A4642")]

# Threshold sweep (tier "table"): the headline figures recomputed for cells with density >= T.  Anchors (units
# differ, see density_service.md): 1 500 Eurostat urban-centre cell (1 km); 2 500 this layer's threshold until
# 2026-11-24; 5 000 = 50 residents/ha, "frequent bus" (Angel et al. 2011, after Orosz), the headline; 7 500 ~ Guerra
# & Cervero light rail (people + jobs per gross acre); 10 000 this layer's top class.
SWEEP_STOPS = [1500.0, 2500.0, 5000.0, 7500.0, 10000.0]

FEED_VARIANT = "all"
GRID = "ghsl_census_scaled"
GRID_LABEL = "GHSL 250 m przeskalowany do NSP 2021 (EPSG:2180)"
POP_DATE = "2021-03-31 (NSP 2021, wzór GHSL 2020)"
SOURCE = ("GTFS (feedy wg config.yaml, dzień {d}, warstwa usług pipeline.gtfs_service); OSM 2026-11-22 "
          "(sieć piesza, przystanki); ludność: NSP 2021 + GHSL 2020")
AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
AGG_NAME = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
            "trojmiasto": "Trójmiasto", "gzm": "GZM"}
DOMAINS = ("core", "covered")
DOM_LABEL = {"core": "rdzeń", "covered": "obszar pokryty danymi"}

LAYERS = RESULTS / "layers"
METRICS = RESULTS / "metrics"
QA = RESULTS / "qa" / "density_service"
FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]


# ------------------------------------------------------------------ classification
def density_class(dens: np.ndarray) -> np.ndarray:
    """1, 2, 3 for density below / between / above the stops."""
    return np.searchsorted(DENSITY_STOPS, dens, side="right").astype(np.int64) + 1


def service_class(headway: pd.Series) -> np.ndarray:
    """1, 2, 3 from headway_class_all labels (must all be known)."""
    return headway.map(SERVICE_OF_HEADWAY).astype("int64").to_numpy()


def map_class(d: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Index into MAP_CLASSES from the density class (1..3) and the service class (1..3)."""
    dense = d >= DENSE_MIN_CLASS
    return np.where(dense, s - 1, np.where(s >= 2, 3, 4)).astype(np.int64)


def class_code(d: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Cell of the 3 x 3 metrics table: (d-1)*3 + (s-1), 0..8."""
    return (d - 1) * 3 + (s - 1)


def weighted_midranks(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted average ranks: the rank of a value is the weight below it plus half the weight of its tie group."""
    order = np.argsort(x, kind="stable")
    xs, ws = x[order], w[order]
    new = np.r_[True, xs[1:] != xs[:-1]]
    gid = np.cumsum(new) - 1
    gw = np.bincount(gid, weights=ws)
    below = np.cumsum(gw) - gw
    rank_sorted = (below + gw / 2)[gid]
    out = np.empty(len(x))
    out[order] = rank_sorted
    return out


def weighted_spearman(x, y, w) -> float | None:
    """Weighted Spearman rank correlation: weighted Pearson correlation of the weighted average ranks."""
    x, y, w = (np.asarray(a, dtype=float) for a in (x, y, w))
    keep = w > 0
    x, y, w = x[keep], y[keep], w[keep]
    if len(x) < 2:
        return None
    rx, ry = weighted_midranks(x, w), weighted_midranks(y, w)
    sw = w.sum()
    mx, my = (w * rx).sum() / sw, (w * ry).sum() / sw
    cov = (w * (rx - mx) * (ry - my)).sum()
    vx, vy = (w * (rx - mx) ** 2).sum(), (w * (ry - my) ** 2).sum()
    if vx <= 0 or vy <= 0:
        return None
    return float(cov / np.sqrt(vx * vy))


# ------------------------------------------------------------------ data
def load_cells() -> pd.DataFrame:
    d = pd.read_parquet(LAYERS / "frequent_cells.parquet",
                        columns=["agglomeration", "cell_id", "pop_census_scaled", "in_core", "headway_class_all",
                                 "in_mask_all"])
    d = d[d.pop_census_scaled > 0].reset_index(drop=True)
    mask = d.in_mask_all.to_numpy(bool)
    bad = set(d.headway_class_all[mask].dropna().unique()) - set(SERVICE_OF_HEADWAY)
    if bad or d.headway_class_all[mask].isna().any():
        raise ValueError(f"unexpected headway classes {bad} / missing inside the mask")
    return d


def agg_figures(d: pd.DataFrame, dom: str) -> dict:
    """Class populations and figures of one agglomeration/domain (d = that agglomeration's populated cells)."""
    base = d.in_core.to_numpy(bool) if dom == "core" else np.ones(len(d), bool)
    mask = d.in_mask_all.to_numpy(bool)
    pop_all = float(d.pop_census_scaled[base].sum())
    sel = base & mask
    p = d.pop_census_scaled.to_numpy()[sel]
    dens = p / CELL_KM2
    dc = density_class(dens)
    sc = service_class(d.headway_class_all[sel])
    tab = np.zeros((3, 3))
    for i in (1, 2, 3):
        for j in (1, 2, 3):
            tab[i - 1, j - 1] = p[(dc == i) & (sc == j)].sum()
    tot = tab.sum()
    dense = tab[DENSE_MIN_CLASS - 1:].sum()
    level = d.headway_class_all[sel].map({h: i for i, h in enumerate(HEADWAY_ORDER)}).to_numpy(float)
    sweep = {}
    for t in SWEEP_STOPS:
        above = dens >= t
        pa = float(p[above].sum())
        sweep[t] = {"pop": pa, "pop_share": pa / tot * 100 if tot > 0 else None,
                    "underserved": float(p[above & (sc == 1)].sum()) / pa * 100 if pa > 0 else None,
                    "good": float(p[above & (sc == 3)].sum()) / pa * 100 if pa > 0 else None}
    return {"table": tab, "pop": tot, "pop_domain": pop_all, "coverage": tot / pop_all if pop_all > 0 else None,
            "sweep": sweep,
            "dense_pop": dense,
            "underserved": tab[DENSE_MIN_CLASS - 1:, 0].sum() / dense * 100 if dense > 0 else None,
            "good": tab[DENSE_MIN_CLASS - 1:, 2].sum() / dense * 100 if dense > 0 else None,
            "rho": weighted_spearman(dens, level, p) if tot > 0 else None}


def compute(d: pd.DataFrame) -> dict:
    res = {(a, dom): agg_figures(d[d.agglomeration == a].reset_index(drop=True), dom) for a in AGGS for dom in DOMAINS}
    assert DENSITY_STOPS[0] in SWEEP_STOPS and 2500.0 in SWEEP_STOPS   # headline and the former threshold
    for k, f in res.items():   # the sweep at the class stop must reproduce the main figures
        s = f["sweep"][DENSITY_STOPS[0]]
        assert abs(s["pop"] - f["dense_pop"]) < 1e-6 * max(f["dense_pop"], 1), k
        assert (s["underserved"] is None) == (f["underserved"] is None), k
        if f["underserved"] is not None:
            assert abs(s["underserved"] - f["underserved"]) < 1e-9 and abs(s["good"] - f["good"]) < 1e-9, k
        top = f["sweep"][DENSITY_STOPS[1]]["pop"]          # the top table row is the sweep at the second stop
        assert abs(top - f["table"][2].sum()) < 1e-6 * max(top, 1), k
        assert abs(f["table"].sum() - f["pop"]) < 1e-6 * max(f["pop"], 1), k
    return res


def sweep_md(res: dict) -> list[str]:
    """QA section: how the 'dense' figures depend on the density threshold."""
    heads = [f"≥ {t:,.0f}".replace(",", " ") for t in SWEEP_STOPS]
    L = ["## Wrażliwość na próg gęstości\n",
         "Te same dwa wskaźniki („bez kursów co ≤ 20 min” i „z kursami co ≤ 10 min” w zasięgu 500 m), policzone dla "
         "mieszkańców komórek 250 m o gęstości co najmniej T os./km², dla pięciu progów T. Przy T = 5 000 liczby są równe "
         "wskaźnikom głównym; próg 2 500 był progiem głównym do 2026-11-24 i zostaje jako wariant. Mapa i tabele 3 × 3 "
         "używają klas 5 000 / 10 000.\n",
         "Skąd progi (jednostki się różnią, więc to punkty orientacyjne, nie równoważniki):\n",
         "- 1 500: Eurostat, komórka centrum miejskiego w stopniu urbanizacji (komórki 1 km);",
         "- 2 500: dawny próg tej warstwy (25 mieszkańców na ha w komórce 250 m; na siatce 1 km to mniej więcej 2 000);",
         "- 5 000: próg główny od 2026-11-24; 50 mieszkańców na ha, częsta i atrakcyjna obsługa autobusowa wg Angela "
         "i in. (2011, za Oroszem), liczone na obwodach spisowych USA; 30 na ha to tam próg „podstawowej” obsługi "
         "autobusowej;",
         "- 7 500: rząd wielkości progu opłacalności tramwaju/LRT wg Guerry i Cervero (2011), ok. 30 osób (mieszkańcy "
         "i miejsca pracy) na akr brutto wokół stacji; tu liczymy tylko mieszkańców;",
         "- 10 000: górna klasa gęstości tej warstwy (100 na ha).\n",
         "Progi z literatury dotyczą jednostek większych niż komórka 250 m (obwody spisowe, całe obszary), które "
         "zawierają ulice, parki i działki niemieszkalne. Komórka 250 m bywa prawie w całości mieszkaniowa, więc ta "
         "sama gęstość „obszarowa” daje w niej wyższą liczbę. Próg 2 500 na komórkach 250 m był więc łagodny: "
         "obejmował także zwykłą zabudowę jednorodzinną (25–40 mieszkańców na ha). Dlatego od 2026-11-24 wskaźniki "
         "główne i mapa używają progu 5 000.\n"]
    for dom in DOMAINS:
        L.append(f"### {DOM_LABEL[dom].capitalize()}\n")
        for key, title, d in (("underserved", "bez kursów co ≤ 20 min w zasięgu 500 m, % mieszkańców komórek ≥ T", 1),
                              ("good", "z kursami co ≤ 10 min w zasięgu 500 m, % mieszkańców komórek ≥ T", 1),
                              ("pop_share", "mieszkańcy komórek ≥ T, % ludności w masce", 1),
                              ("pop", "mieszkańcy komórek ≥ T, tys.", 0)):
            L.append(f"**{title[0].upper() + title[1:]}**\n")
            L.append("| Aglomeracja | " + " | ".join(heads) + " |\n|---|" + "---|" * len(heads))
            for a in AGGS:
                s = res[(a, dom)]["sweep"]
                vals = [s[t][key] / 1000 if (key == "pop" and s[t][key] is not None) else s[t][key] for t in SWEEP_STOPS]
                L.append(f"| {AGG_NAME[a]} | " + " | ".join(pl(v, d) for v in vals) + " |")
            L.append("")
    # plain reading of the sweep, computed
    lines = []
    for dom in DOMAINS:
        lo = [res[(a, dom)]["sweep"][SWEEP_STOPS[0]]["underserved"] for a in AGGS]
        hi = [res[(a, dom)]["sweep"][5000.0]["underserved"] for a in AGGS]
        order_25 = sorted(AGGS, key=lambda a: -(res[(a, dom)]["sweep"][2500.0]["underserved"] or 0))
        order_50 = sorted(AGGS, key=lambda a: -(res[(a, dom)]["sweep"][5000.0]["underserved"] or 0))
        lines.append(f"- {DOM_LABEL[dom].capitalize()}: udział bez kursów co ≤ 20 min wynosi {pl(min(lo))}–{pl(max(lo))} % "
                     f"przy 1 500 i {pl(min(hi))}–{pl(max(hi))} % przy 5 000. Kolejność miast od najgorszego: przy "
                     f"2 500 {', '.join(AGG_NAME[a] for a in order_25)}; przy 5 000 "
                     f"{', '.join(AGG_NAME[a] for a in order_50)}.")
    L.append("Jak czytać:\n")
    L += lines
    mono = all(all(res[(a, dom)]["sweep"][t1]["underserved"] >= res[(a, dom)]["sweep"][t2]["underserved"]
                   for t1, t2 in zip(SWEEP_STOPS, SWEEP_STOPS[1:])) for a in AGGS for dom in DOMAINS)
    L.append(("- W każdej aglomeracji i domenie" if mono else "- Prawie wszędzie") +
             " im wyższy próg, tym mniejszy udział mieszkańców bez kursów co ≤ 20 min: gęstsze komórki są lepiej "
             "obsługiwane, zgodnie z dodatnią korelacją rang. Wynik przy dawnym progu 2 500 obejmuje więc także mieszkańców "
             "komórek o gęstości 25–50 na ha, czyli prawdopodobnie w dużej części zabudowy jednorodzinnej (typu "
             "zabudowy w tych komórkach nie sprawdzano), gdzie literatura nie oczekuje częstej komunikacji.")
    L.append("- Mieszkańcy, nie miejsca pracy: progi Guerry i Cervero oraz Newmana i Kenworthy'ego liczą też miejsca "
             "pracy, więc porównanie z nimi jest tylko orientacyjne.\n")
    return L


# ------------------------------------------------------------------ metric rows
def metric_rows(res: dict, day: str, cov_min: float) -> list[dict]:
    rows = []
    src = SOURCE.format(d=day)

    def add(agg, dom, metric, label, value, unit, tier, flag, cov):
        rows.append({"agglomeration": agg, "domain": dom, "metric": metric, "label": label,
                     "value": sig(value) if value is not None else None, "unit": unit, "grid": GRID_LABEL,
                     "source": src, "population_date": POP_DATE, "timetable_date": day,
                     "coverage_share": sig(cov) if cov is not None else None, "flag": flag, "tier": tier,
                     "feed_variant": FEED_VARIANT, "population_grid": GRID})

    for a in AGGS:
        for dom in DOMAINS:
            f = res[(a, dom)]
            cov = f["coverage"]       # core: share of core population in the mask; covered: share of the FUA's
            if dom == "core" and cov is not None and cov < cov_min:
                flag = (f"niepełne pokrycie GTFS: {cov * 100:.1f} % ludności rdzenia w obszarze pokrytym (< 85 %); "
                        "wynik zaniżony, do porównań wariant 'obszar pokryty' lub 'rdzeń'")
            elif dom == "covered":
                flag = "tylko komórki w masce pokrycia GTFS (§6); coverage_share = udział ludności FUA w masce"
            else:
                flag = ""
            tot = f["pop"]
            for i in range(3):
                for j in range(3):
                    v = f["table"][i, j] / tot * 100 if tot > 0 else None
                    add(a, dom, f"dxs_share_d{i + 1}_s{j + 1}",
                        f"Ludność komórek o gęstości {DENSITY_LABELS[i]} i kursach: {SERVICE_LABELS[j]} "
                        f"(odsetek ludności w masce, {DOM_LABEL[dom]})", v, "%", "table", flag, cov)
            add(a, dom, "dxs_dense_underserved_share",
                f"Mieszkańcy komórek 250 m o gęstości ≥ {_T} bez kursów co ≤ 20 min w zasięgu 500 m "
                f"(odsetek mieszkańców tych komórek, {DOM_LABEL[dom]})", f["underserved"], "%", "main", flag, cov)
            add(a, dom, "dxs_dense_good_share",
                f"Mieszkańcy komórek 250 m o gęstości ≥ {_T} z kursami co ≤ 10 min w zasięgu 500 m "
                f"(odsetek mieszkańców tych komórek, {DOM_LABEL[dom]})", f["good"], "%", "main", flag, cov)
            add(a, dom, "dxs_rank_correlation",
                "Korelacja rang (Spearman, ważona ludnością) między gęstością komórki a częstotliwością kursów; "
                "dodatnia = gęstsze komórki mają lepszą komunikację", f["rho"], "–", "main", flag, cov)
            sflag = ((flag + " ") if flag else "") + (
                "Wrażliwość na próg gęstości (komórki 250 m, tylko mieszkańcy, bez miejsc pracy); "
                "przy 5 000 równe wskaźnikom głównym, 2 500 to dawny próg główny. Progi z literatury dotyczą większych "
                "jednostek (density_service.md).")
            for t in SWEEP_STOPS:
                s = f["sweep"][t]
                tt = f"{int(t)}"
                tl = f"{t:,.0f}".replace(",", " ")
                add(a, dom, f"dxs_sweep_t{tt}_pop", f"Mieszkańcy komórek o gęstości ≥ {tl} os./km² (w masce, {DOM_LABEL[dom]})",
                    s["pop"], "os.", "table", sflag, cov)
                add(a, dom, f"dxs_sweep_t{tt}_pop_share",
                    f"Mieszkańcy komórek o gęstości ≥ {tl} os./km² (odsetek ludności w masce, {DOM_LABEL[dom]})",
                    s["pop_share"], "%", "table", sflag, cov)
                add(a, dom, f"dxs_sweep_t{tt}_underserved_share",
                    f"Mieszkańcy komórek o gęstości ≥ {tl} os./km² bez kursów co ≤ 20 min w zasięgu 500 m "
                    f"(odsetek mieszkańców tych komórek)", s["underserved"], "%", "table", sflag, cov)
                add(a, dom, f"dxs_sweep_t{tt}_good_share",
                    f"Mieszkańcy komórek o gęstości ≥ {tl} os./km² z kursami co ≤ 10 min w zasięgu 500 m "
                    f"(odsetek mieszkańców tych komórek)", s["good"], "%", "table", sflag, cov)
    return rows


def write_metrics(rows: list[dict], day: str) -> None:
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["feed_variant"], m["population_grid"], m["domain"],
                                       m["metric"]))
    METRICS.mkdir(parents=True, exist_ok=True)
    write_json(METRICS / "metrics_density_service.json", {"generated_for_timetable_date": day, "metrics": rows})
    with open(METRICS / "metrics_density_service.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


# ------------------------------------------------------------------ QA text
def pl(x, d=1) -> str:
    return "–" if x is None else f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def write_md(res: dict, day: str) -> None:
    L = ["# Gęstość zaludnienia a częstotliwość komunikacji\n",
         "## Metoda\n",
         f"- Komórki 250 m z ludnością (siatka GHSL przeskalowana do NSP 2021), tylko wewnątrz maski pokrycia GTFS "
         f"(wszystkie feedy, dzień {day}); komórki poza maską to brak danych, nie klasa i nie zero.",
         "- Gęstość = ludność komórki / 0,0625 km². Klasy: D1 poniżej 5 000, D2 5 000–10 000, D3 od 10 000 os./km² "
         "(punkty podziału rampy gęstości na mapie). Do 2026-11-24 granicą D1 było 2 500; zmieniono ją po przeglądzie "
         "literatury, bo 2 500 na komórkach 250 m obejmuje zwykłą zabudowę jednorodzinną (sekcja o wrażliwości niżej).",
         "- Kursy: najlepsza klasa odstępu w zasięgu 500 m pieszo po sieci OSM (średnia 6:00–20:00). S1: co 30 min, "
         "rzadziej lub brak; S2: co 15 lub 20 min; S3: co 5 lub 10 min.",
         "- Udziały to odsetki ludności w masce w danej domenie (rdzeń albo obszar pokryty danymi w całym FUA); "
         "każda tabela sumuje się do 100 %. Wskaźniki główne dotyczą mieszkańców komórek od 5 000 os./km² (D2 i D3).",
         "- Korelacja rang: Spearman ważony ludnością (średnie rangi ważone, potem ważona korelacja Pearsona rang) "
         "między gęstością a klasą odstępu uporządkowaną od „> 30” do „5”; dodatnia oznacza, że gęstsze komórki mają "
         "lepszą komunikację.\n"]
    L.append("## Główne wskaźniki\n")
    for dom in DOMAINS:
        L.append(f"### {DOM_LABEL[dom].capitalize()}\n")
        L.append("| Aglomeracja | ≥ 5 000 os./km², bez kursów co ≤ 20 min (%) | ≥ 5 000 os./km², kursy co ≤ 10 min (%) | "
                 "Korelacja rang | Pokrycie GTFS (% ludności) |\n|---|---|---|---|---|")
        for a in AGGS:
            f = res[(a, dom)]
            L.append(f"| {AGG_NAME[a]} | {pl(f['underserved'])} | {pl(f['good'])} | {pl(f['rho'], 2)} | "
                     f"{pl(f['coverage'] * 100 if f['coverage'] is not None else None)} |")
        L.append("")
    L += sweep_md(res)
    L.append("## Tabele 3 × 3 (% ludności w masce)\n")
    L.append("Wiersze: gęstość (od najmniejszej), kolumny: kursy (od najgorszych do najlepszych).\n")
    for dom in DOMAINS:
        L.append(f"### {DOM_LABEL[dom].capitalize()}\n")
        for a in AGGS:
            f = res[(a, dom)]
            L.append(f"**{AGG_NAME[a]}**\n")
            L.append("| Gęstość | " + " | ".join(SERVICE_LABELS) + " |\n|---|---|---|---|")
            for i in range(3):
                L.append(f"| {DENSITY_LABELS[i]} | " + " | ".join(
                    pl(f["table"][i, j] / f["pop"] * 100 if f["pop"] > 0 else None) for j in range(3)) + " |")
            L.append("")
    L.append("## Podział ludności na klasy (wszystkie aglomeracje razem)\n")
    for dom in DOMAINS:
        tab = sum(res[(a, dom)]["table"] for a in AGGS)
        tot = tab.sum()
        L.append(f"### {DOM_LABEL[dom].capitalize()} ({pl(tot / 1e6, 2)} mln mieszkańców w masce)\n")
        L.append("| Gęstość | " + " | ".join(SERVICE_LABELS) + " | Razem |\n|---|---|---|---|---|")
        for i in range(3):
            L.append(f"| {DENSITY_LABELS[i]} | " + " | ".join(pl(tab[i, j] / tot * 100) for j in range(3))
                     + f" | {pl(tab[i].sum() / tot * 100)} |")
        L.append("| Razem | " + " | ".join(pl(tab[:, j].sum() / tot * 100) for j in range(3)) + " | 100,0 |\n")
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "density_service.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    day = cfg["reference_day"]
    d = load_cells()
    res = compute(d)
    rows = metric_rows(res, day, float(cfg["coverage_min_share"]))
    write_metrics(rows, day)
    write_md(res, day)
    inputs = ["osm_poland_pbf", "nsp2021_grid_1km_shp", "ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20",
              "ghs_built_s_2020_R3_C20", "ghs_built_s_2020_R4_C20", "urau_2021_100k_all", "lau_2021_01m"]
    extra = {"timetable_date": day, "source": "results/layers/frequent_cells.parquet",
             "density_stops_per_km2": DENSITY_STOPS, "sweep_stops_per_km2": SWEEP_STOPS,
             "service_of_headway": SERVICE_OF_HEADWAY, "rows": len(rows)}
    write_meta(QA, "density_service", inputs=inputs, started=t0,
               extra={**extra, "outputs": sorted(p.name for p in QA.iterdir() if p.name != "_meta.json")})
    tmp = Path(tempfile.mkdtemp())
    write_meta(tmp, "density_service", inputs=inputs, started=t0,
               extra={**extra, "outputs": ["metrics_density_service.csv", "metrics_density_service.json"]})
    shutil.copyfile(tmp / "_meta.json", METRICS / "_meta_density_service.json")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"density_service: {len(rows)} rows in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
