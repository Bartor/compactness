"""QA note and plots for pipeline.form_extra: results/qa/form/form.md (Polish) and results/qa/form/*.png.

    python -m pipeline.form_md       # after python -m pipeline.form_extra

Every number in the note is read from data/interim/form/<agg>.json, degurba_national.json, metrics_density.json
and results/web/class_shares.json (cross-check only, read if present).
"""
from __future__ import annotations

import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from pipeline import form_extra as F  # noqa: E402
from pipeline.boundaries import all_agglomeration_ids  # noqa: E402
from pipeline.common import RESULTS  # noqa: E402

QA = RESULTS / "qa" / "form"
MONO_ORDER = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "szczecin", "lublin", "bialystok", "rzeszow",
              "kielce"]
POLY_ORDER = ["gzm", "trojmiasto", "bydgoszcz_torun"]


def load() -> dict:
    return {a: json.loads((F.OUT / f"{a}.json").read_text(encoding="utf-8")) for a in sorted(all_agglomeration_ids())}


def n(v, d=0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "brak"
    s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def g3(v) -> str:
    if v is None:
        return "brak"
    return n(v, 3 if abs(v) < 10 else 1)


def pct(v, d=1) -> str:
    return "brak" if v is None else n(v * 100, d) + " %"


def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def name(r: dict) -> str:
    return r["name"] + (" *" if r["polycentric"] else "")


def order(R: dict) -> list[str]:
    return [a for a in MONO_ORDER + POLY_ORDER if a in R]


# ------------------------------------------------------------------ plots

def plot_extents(R: dict) -> None:
    ids = order(R)
    fig, axs = plt.subplots(3, 5, figsize=(17, 10.5))
    for ax in axs.ravel():
        ax.axis("off")
    for ax, a in zip(axs.ravel(), ids):
        z = np.load(F.OUT / f"{a}.npz")
        img = np.zeros(z["extent"].shape + (3,)) + 1.0
        img[z["dom_f"]] = (0.93, 0.93, 0.93)
        img[z["extent"]] = (0.98, 0.70, 0.35)
        if "extent2" in z.files:
            img[z["extent2"] & ~z["extent"]] = (0.98, 0.85, 0.55)
        img[z["uc"]] = img[z["uc"]] * 0.55
        rr, cc = np.nonzero(z["extent"] | z["uc"])
        pad = 40
        r0, r1 = max(rr.min() - pad, 0), min(rr.max() + pad, img.shape[0])
        c0, c1 = max(cc.min() - pad, 0), min(cc.max() + pad, img.shape[1])
        ax.imshow(img[r0:r1, c0:c1], interpolation="nearest")
        tr = z["tr"]
        X, Y = F.D.TO_MOLL.transform(*z["townhall"])
        ax.plot((X - tr[2]) / tr[0] - 0.5 - c0, (Y - tr[5]) / tr[4] - 0.5 - r0, "k+", ms=10, mew=2)
        e = R[a]["extent"]["b10"]
        ax.set_title(f"{R[a]['name']}: PRX {g3(e['prx'])}, ρ {g3(e['rho_ext'])}", fontsize=10)
    fig.suptitle("Zasięg miejski (pomarańczowy, metoda Angela na GHS-BUILT-S 100 m), centrum miejskie Eurostatu 2021 "
                 "(przyciemnione), FUA (szare), ratusz (+)", fontsize=11)
    fig.tight_layout()
    fig.savefig(QA / "extents.png", dpi=90)
    plt.close(fig)


def plot_gzm_hotspots(R: dict) -> None:
    import pandas as pd
    d = F.cells250("gzm")
    f = d[d.in_fua & (d["pop"] > 0)]
    dens = f["pop"].values / F.CELL250_KM2
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.scatter(f.x, f.y, s=1, c="#e6e6e6", marker="s", lw=0)
    for thr, col in ((5000, "#f6b26b"), (10000, "#cc4125")):
        m = dens >= thr
        ax.scatter(f.x.values[m], f.y.values[m], s=2.2, c=col, marker="s", lw=0,
                   label=f"komórki ≥ {thr:,} os./km²".replace(",", " "))
    cs = F.D.centres("gzm")
    for c in cs:
        ax.plot(c["x"], c["y"], "k^", ms=7)
        ax.annotate(c["name"], (c["x"], c["y"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
    for k in R["gzm"]["hotspots"]["main"]["clusters"][:15]:
        ax.annotate(str(k["rank"]), (k["x"], k["y"]), fontsize=8, color="#7f0000", ha="center", weight="bold")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.legend(loc="lower left", fontsize=8, markerscale=4)
    ax.set_title("GZM: skupiska gęstości (komórki 250 m, NSP 2021 rozłożony wzorem GHSL) i 9 centrów z config.yaml; "
                 "liczby = ranga skupiska ≥ 10 000", fontsize=9)
    fig.tight_layout()
    fig.savefig(QA / "hotspots_gzm.png", dpi=100)
    plt.close(fig)
    _ = pd


def plot_rank_size(R: dict) -> None:
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    for ax, ids, title in ((axs[0], [a for a in MONO_ORDER if a in R], "jednocentrowe"),
                           (axs[1], [a for a in POLY_ORDER if a in R], "wielomiejskie / liniowe")):
        for a in ids:
            p = [k["pop"] for k in R[a]["hotspots"]["main"]["clusters"] if k["pop"] >= 1000]
            if p:
                ax.loglog(np.arange(1, len(p) + 1), p, marker="o", ms=3, lw=1, label=R[a]["name"])
        ax.axhline(F.HOT_MIN_POP, color="#999", lw=0.8, ls="--")
        ax.set_xlabel("ranga skupiska")
        ax.set_title(f"Skupiska ≥ 10 000 os./km² (250 m), {title}", fontsize=10)
        ax.legend(fontsize=7)
    axs[0].set_ylabel("mieszkańcy skupiska")
    fig.tight_layout()
    fig.savefig(QA / "rank_size.png", dpi=90)
    plt.close(fig)


def plot_classes(R: dict) -> None:
    ids = sorted(R, key=lambda a: R[a]["density_classes"]["fua"]["at_or_above"]["5000"])
    labs = [c["label"] for c in F.class_labels()]
    cols = plt.get_cmap("YlOrBr")(np.linspace(0.12, 0.95, len(labs)))
    fig, axs = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, dom in zip(axs, ("fua", "core")):
        left = np.zeros(len(ids))
        for k in range(len(labs)):
            v = np.array([R[a]["density_classes"][dom]["share"][k] for a in ids]) * 100
            ax.barh(range(len(ids)), v, left=left, color=cols[k], label=labs[k], edgecolor="white", lw=0.4)
            left += v
        ge = [100 * R[a]["density_classes"][dom]["at_or_above"]["5000"] for a in ids]
        for i, g in enumerate(ge):
            ax.plot(100 - g, i, "k|", ms=14)
        ax.set_yticks(range(len(ids)), [R[a]["name"] for a in ids])
        ax.set_xlim(0, 100)
        ax.set_title("FUA" if dom == "fua" else "rdzeń", fontsize=10)
        ax.set_xlabel("% mieszkańców (kreska: granica 5 000 os./km²)")
    h, lb = axs[0].get_legend_handles_labels()
    fig.legend(h, lb, title="os./km² (komórka 250 m)", fontsize=8, loc="lower center", ncol=len(labs))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(QA / "density_classes.png", dpi=90)
    plt.close(fig)


# ------------------------------------------------------------------ note

def class_shares_check(R: dict) -> list[str]:
    p = RESULTS / "web" / "class_shares.json"
    if not p.exists():
        return ["Plik `results/web/class_shares.json` nie istnieje; kontroli krzyżowej nie zrobiono."]
    cs = json.loads(p.read_text(encoding="utf-8"))["layers"].get("density_250m", {})
    worst = 0.0
    n_ok = 0
    for a, r in R.items():
        if a not in cs:
            continue
        for dom in ("fua", "core"):
            mine = r["density_classes"][dom]["pop"]
            theirs = cs[a][dom]["pop"]
            if len(mine) == len(theirs):
                worst = max(worst, max(abs(x - y) for x, y in zip(mine, theirs)))
                n_ok += 1
    return [f"Kontrola krzyżowa z `results/web/class_shares.json` (warstwa `density_250m`, osobny kod z "
            f"`pipeline.class_shares`): {n_ok} par aglomeracja × obszar, największa różnica liczby mieszkańców klasy "
            f"{n(worst, 1)} os. (zaokrąglenie do pełnych osób w tamtym pliku)."]


def build(R: dict) -> str:
    nat = json.loads((F.OUT / "degurba_national.json").read_text(encoding="utf-8"))
    ids = order(R)
    L: list[str] = []
    A = L.append
    A("# Forma miasta: indeks bliskości Angela, policentryczność, stopień urbanizacji, klasy gęstości")
    A("")
    A(f"Wygenerowano: {json.loads((F.OUT / '_meta.json').read_text(encoding='utf-8'))['run_at'][:10]} "
      "(`python -m pipeline.form_extra`, potem `python -m pipeline.form_md`). Liczby w tabelach są przepisywane "
      "przez kod z `data/interim/form/*.json`, więc zgadzają się z `results/metrics/metrics_form.csv`. Daty: "
      "**ludność NSP 2021 stan na 31.03.2021** (siatka 1 km; wewnątrz komórek 1 km rozkład wzorem GHS-POP 2020), "
      "**zabudowa GHS-BUILT-S epoka 2020**, centra miejskie Eurostatu 2021 (wydanie 2024-11-19), ratusze z OSM "
      "(stan 2026-11-22). Rozkładów jazdy ten krok nie używa. Aglomeracje z * są wielomiejskie lub liniowe "
      "(GZM, Trójmiasto, Bydgoszcz–Toruń).")
    A("")
    A("Spis treści: 1. Definicje · 2. Indeks bliskości Angela i ρ · 3. Policentryczność · 4. Stopień urbanizacji · "
      "5. Klasy gęstości · 6. Lektura krytyczna · 7. Nie zweryfikowano · 8. Pliki")
    A("")
    # ---------------------------------------------------------------- definitions
    A("## 1. Definicje")
    A("")
    A("### 1.1 Zasięg miejski (urban extent)")
    A("")
    A("Indeks Angela wymaga zasięgu miejskiego narysowanego według opublikowanej reguły. Dane pozwalają na dwie:")
    A("")
    A("- **Zasięg główny: metoda Atlas of Urban Expansion (Angel i in.) odtworzona na GHS-BUILT-S 100 m.**")
    A("  1. komórka zabudowana: co najmniej 10 % powierzchni komórki 100 m pod budynkami (GHS-BUILT-S 2020);")
    A("  2. „miejskość” komórki zabudowanej = udział komórek zabudowanych w kole o polu 1 km² wokół niej "
      "(promień 564 m; liczone tylko komórki w Polsce): miejska ≥ 50 %, podmiejska 25–50 %, wiejska < 25 %;")
    A("  3. otwarta przestrzeń na obrzeżu: komórki niezabudowane do 100 m od zabudowy miejskiej lub podmiejskiej;")
    A("  4. enklawy: dziury w tym obszarze mniejsze niż 200 ha (spójne 4-kierunkowo);")
    A("  5. zasięg = zabudowa miejska + podmiejska + obrzeże + enklawy; skupiska spójne 8-kierunkowo po połączeniu "
      "przerw do 600 m (ta sama reguła co maska ρ w kroku density; bez niej Wisła odcina ratusz Warszawy od Pragi); "
      "zasięg miasta to skupisko, w którym leży ratusz.")
    A("  Dlaczego ta reguła: to ta sama konstrukcja, na której Angel i in. policzyli indeksy dla 200 miast, więc "
      "wartości są z nimi zestawialne co do rzędu wielkości. Różnice wobec Atlasu: Atlas używa pikseli 30 m z "
      "Landsata, w których „zabudowa” obejmuje też drogi, parkingi i utwardzone podwórza; GHS-BUILT-S liczy tylko "
      "budynki. Próg 10 % na komórce 100 m wybrano jako najbliższy (komórka z ok. 1 000 m² dachów to w obrazie "
      "Landsata zwykle kilka pikseli zabudowanych); wrażliwość: 5 % i 20 % (tabela 2). Nie ma warstwy wód. "
      "Atlas łączy kilka skupisk w jedno miasto według własnych reguł; tu zastępuje je łączenie przerw do 600 m "
      "(wrażliwość: bez łączenia, tabela 2).")
    A("- **Zasięg kontrolny: centrum miejskie Eurostatu 2021** (`HDENS_CLST_2021`, komórki 1 km, ≥ 1 500 os./km², "
      "≥ 50 000 mieszkańców, spis 2021), to, w którym leży ratusz. Reguła jest opublikowana i niezależna od naszych "
      "wyborów, ale opiera się na ludności, nie na zabudowie, i ma rozdzielczość 1 km.")
    A("")
    A("**Centrum:** ratusz (siedziba prezydenta) miasta rdzenia z `pipeline.density_centres` (Angel i in. "
      "ustalają centrum właśnie jako ratusz). Dla Gdyni ratusz wybrano tą samą regułą, dla Torunia ręcznie "
      "(tabela 2a).")
    A("")
    A("### 1.2 Indeksy")
    A("")
    A("Dla zasięgu o polu A (liczba komórek 100 m × 0,01 km²; Mollweide jest równopolowe) i R = √(A/π):")
    A("")
    A("- **Indeks bliskości (PRX, Angel):** ⅔R / średnia odległość wszystkich komórek zasięgu od ratusza. "
      "1 = koło z ratuszem w środku; niższy = teren miasta leży dalej od ratusza niż w kole o tym samym polu "
      "(kształt wydłużony, postrzępiony albo ratusz z boku). Angel i in. nie znaleźli w próbie 200 miast wartości "
      "poniżej 0,35.")
    A("- **Indeks spójności (Angel):** średnia odległość między dwoma punktami koła (128R/45π ≈ 0,905R) / średnia "
      "odległość między wszystkimi parami komórek zasięgu (liczona dokładnie, po wszystkich parach). Nie zależy od "
      "centrum.")
    A("- **ρ Bertauda na tym samym zasięgu:** średnia odległość mieszkańca od ratusza / ⅔R. To odwrotność PRX, "
      "tyle że ważona ludnością. Iloczyn PRX × ρ = średnia odległość terenu / średnia odległość mieszkańca: > 1, "
      "gdy ludzie mieszkają bliżej ratusza niż leży teren (gęstość maleje od centrum).")
    A("- **Co dodaje każda miara:** PRX mówi o kształcie śladu zabudowy względem centrum (sam teren, bez ludności); "
      "ρ na tym samym zasięgu dodaje rozkład ludności w tym śladzie. ρ z kroku density (maska ≥ 20 %, FUA) mierzy "
      "coś trzeciego: rozkład mieszkańców gęstej zabudowy względem centrum z config.yaml, na masce netto, która "
      "pomija luźną zabudowę.")
    A("")
    A("### 1.3 Policentryczność")
    A("")
    A("- **η (Volpati i Barthelemy 2018, wzór 6):** komórki 100 m maski zabudowy ≥ 20 % w FUA (jak w kroku density); "
      "„hotspoty” = komórki powyżej progu LouBar (styczna do krzywej Lorenza ludności w F = 1); η = średnia "
      "odległość między hotspotami / średnia odległość między wszystkimi komórkami. Bliżej 0: hotspoty w jednym "
      "miejscu; bliżej 1: rozrzucone po całym obszarze jak komórki w ogóle. Krok density liczył to na próbie 4 000 "
      "komórek; tu po wszystkich parach (obie wartości w tabeli 3).")
    A(f"- **Skupiska gęstości (ranga–wielkość):** komórki 250 m siatki przeskalowanej do NSP 2021 w FUA o gęstości "
      f"≥ {n(F.HOT_MAIN)} os./km² (klasa „10 000–20 000” i wyższa warstwy gęstości na mapie), połączone 8-kierunkowo. "
      f"Liczymy skupiska z ≥ {n(F.HOT_MIN_POP)} mieszkańców, udział największego skupiska w ludności wszystkich "
      f"skupisk, stosunek drugiego do największego i nachylenie prostej ln(ludność) od ln(ranga) (MNK, co najmniej "
      f"{F.RANK_MIN_N} skupiska). Nachylenie bliskie 0: skupiska podobnej wielkości (wiele ośrodków); silnie ujemne: "
      "jedno dominuje. Wrażliwość: próg 5 000 os./km² i próg LouBar komórek 250 m danej FUA. Volpati i "
      "Barthelemy definiują hotspoty i η; wykres ranga–wielkość skupisk to propozycja z notatek do przeglądu "
      "literatury (`research_notes/.../urban_form_and_density.md`, Q4 pkt 6), nie metoda z tej pracy.")
    A("")
    A("### 1.4 Stopień urbanizacji i klasy gęstości")
    A("")
    A("- **Centra miejskie:** oficjalna warstwa Eurostatu 2021 (`HDENS_CLST_2021`, zbudowana na tej samej siatce "
      "spisowej 2021). Udział = ludność NSP 2021 komórek 1 km (środek w obszarze), które leżą w centrum miejskim.")
    A("- **Skupiska miejskie (uproszczenie projektu):** komórki ≥ 300 os./km², spójne 8-kierunkowo, skupisko ≥ 5 000 "
      "mieszkańców, poza centrami miejskimi; reszta = komórki wiejskie. Oficjalnej warstwy skupisk (klastry średniej "
      "gęstości) nie pobrano, poziomu 2 (gęste i półgęste skupiska, przedmieścia) nie liczono.")
    A("- **Klasy gęstości:** komórka 250 m siatki przeskalowanej do NSP 2021, gęstość = mieszkańcy / 0,0625 km², "
      "klasy jak warstwa gęstości na mapie (500, 1 000, 2 500, 5 000, 10 000, 20 000 os./km²). „Typowy mieszkaniec” = "
      "mediana gęstości komórki ważona ludnością.")
    A("")
    # ---------------------------------------------------------------- 2
    A("## 2. Indeks bliskości Angela i ρ Bertauda")
    A("")
    A("Tabela 1. Zasięg główny (GHSL, komórka zabudowana ≥ 10 %), centrum = ratusz; obok zasięg kontrolny (centrum "
      "miejskie Eurostatu 2021) i ρ z kroku density (centrum z config.yaml).")
    A("")
    rows = []
    for a in ids:
        r = R[a]
        e, u, ds = r["extent"]["b10"], r["uc_extent"], r["density_step"]
        rows.append([name(r), n(e["area_km2"]), pct(e["pop_share_of_fua"], 0), g3(e["prx"]), g3(e["cohesion"]),
                     g3(e["rho_ext"]), g3(e["land_over_pop"]), n(u["area_km2"]), g3(u["prx"]), g3(u["cohesion"]),
                     g3(u["rho_ext"]), g3(ds.get("fua:rho_t20")), g3(ds.get("core:rho_t10"))])
    A(table(["Aglomeracja", "pole zasięgu, km²", "ludność FUA w zasięgu", "PRX", "spójność", "ρ na zasięgu",
             "PRX × ρ", "centrum Eurostatu, km²", "PRX (Eurostat)", "spójność (Eurostat)", "ρ (Eurostat)",
             "ρ FUA ≥ 20 % (density)", "ρ rdzeń ≥ 10 % (density)"], rows))
    A("")
    A("![Zasięgi](extents.png)")
    A("")
    A("Tabela 2. Wrażliwość zasięgu głównego: próg komórki zabudowanej, centrum, skład zasięgu.")
    A("")
    rows = []
    for a in ids:
        r = R[a]
        e5, e10, e20 = (r["extent"][k] for k in ("b5", "b10", "b20"))
        comp = e10["composition_km2"]
        rows.append([name(r), f"{g3(e5['prx'])} / {g3(e10['prx'])} / {g3(e20['prx'])}",
                     f"{n(e5['area_km2'])} / {n(e10['area_km2'])} / {n(e20['area_km2'])}",
                     f"{g3(e5['rho_ext'])} / {g3(e10['rho_ext'])} / {g3(e20['rho_ext'])}",
                     g3(e10["prx_config_centre"]),
                     f"{n(comp['urban'])} / {n(comp['suburban'])} / {n(comp['fringe'])} / {n(comp['captured'])}",
                     pct(e10["share_outside_fua"], 1), "tak" if e10["touches_window_edge"] else "nie"])
    A(table(["Aglomeracja", "PRX ≥ 5 / 10 / 20 %", "pole, km² ≥ 5 / 10 / 20 %", "ρ na zasięgu ≥ 5 / 10 / 20 %",
             "PRX, centrum z config.yaml", "skład, km²: miejska / podmiejska / obrzeże / enklawy",
             "część zasięgu poza FUA", "dotyka brzegu okna"], rows))
    A("")
    sec = [a for a in ids if "second" in R[a]["extent"]]
    if sec:
        A("Tabela 2a. Drugie miasto aglomeracji wielomiejskiej: zasięg z jego ratuszem.")
        A("")
        rows = []
        for a in sec:
            s = R[a]["extent"]["second"]
            c = s["centre"]
            rows.append([name(R[a]), f"{c['city']}: {c['name']} ({c['osm'] or 'brak'}; {c['rule']})",
                         "tak" if s["same_cluster_as_first"] else "nie", n(s["area_km2"]), g3(s["prx"]),
                         g3(s["cohesion"]), g3(s["rho_ext"])])
        A(table(["Aglomeracja", "ratusz", "to samo skupisko co pierwszy ratusz", "pole, km²", "PRX", "spójność",
                 "ρ na zasięgu"], rows))
        A("")
    rl = {"hand": "wybór ręczny", "name": "reguła nazwy"}
    A("Ratusze pierwszego miasta (`pipeline.density_centres`, density.md §4b): "
      + "; ".join(f"{R[a]['name']}: {R[a]['townhall']['name']} ({R[a]['townhall']['osm']}, "
                  f"{rl.get(R[a]['townhall']['rule'], R[a]['townhall']['rule'])})" for a in ids) + ".")
    A("")
    A("@@ANGEL_READING@@")
    A("")
    # ---------------------------------------------------------------- 3
    A("## 3. Policentryczność")
    A("")
    A("Tabela 3. η i skupiska gęstości (FUA).")
    A("")
    rows = []
    for a in ids:
        r = R[a]
        et = r["eta"]
        h, h5, hl = (r["hotspots"][k] for k in ("main", "t5000", "loubar"))
        big = h["clusters"][0] if h["clusters"] else None
        rows.append([name(r), g3(et["eta"]), g3(r["density_step"].get("fua:eta_mask")), n(et["loubar_density"]),
                     n(h["n_hotspots_min_pop"]), pct(h["largest_share"], 0), g3(h["second_over_largest"]),
                     f"{g3(h['rank_size_slope'])} (n = {h['rank_size_n']})", pct(h["hot_pop_share_of_fua"], 0),
                     (f"{big['gmina']}, {n(big['pop'])} os., {n(big['nearest_centre_km'], 1)} km od: "
                      f"{big['nearest_centre']}") if big else "brak",
                     f"{n(h5['n_hotspots_min_pop'])} / {pct(h5['largest_share'], 0)} / {g3(h5['rank_size_slope'])}",
                     f"{n(hl['threshold'])}: {n(hl['n_hotspots_min_pop'])} / {pct(hl['largest_share'], 0)} / "
                     f"{g3(hl['rank_size_slope'])}"])
    A(table(["Aglomeracja", "η (dokładnie)", "η (próba 4 000, density)", "próg LouBar 100 m, os./km²",
             "skupiska ≥ 10 000 os./km² z ≥ 5 000 mieszk.", "udział największego", "drugie / największe",
             "nachylenie ranga–wielkość", "ludność FUA w skupiskach", "największe skupisko",
             "próg 5 000: liczba / udział największego / nachylenie",
             "próg LouBar 250 m: wartość: liczba / udział / nachylenie"], rows))
    A("")
    A("![Ranga–wielkość](rank_size.png)")
    A("")
    g = R.get("gzm")
    if g:
        A("Tabela 4. GZM: dziewięć centrów z config.yaml a skupiska gęstości (najbliższa komórka skupiska, ranga i "
          "ludność skupiska).")
        A("")
        rows = []
        for c10, c5 in zip(g["hotspots"]["main"]["centres"], g["hotspots"]["t5000"]["centres"]):
            rows.append([c10["centre"], n(c10["nearest_hot_cell_km"], 2), n(c10["hotspot_rank"]),
                         n(c10["hotspot_pop"]), c10["hotspot_gmina"], n(c5["nearest_hot_cell_km"], 2),
                         n(c5["hotspot_rank"]), n(c5["hotspot_pop"])])
        A(table(["Centrum", "≥ 10 000: odległość, km", "ranga", "ludność", "gmina", "≥ 5 000: odległość, km",
                 "ranga", "ludność"], rows))
        A("")
        A("Tabela 4a. GZM: 15 największych skupisk ≥ 10 000 os./km².")
        A("")
        rows = [[k["rank"], n(k["pop"]), n(k["cells"]), k["gmina"], k["nearest_centre"], n(k["nearest_centre_km"], 1)]
                for k in g["hotspots"]["main"]["clusters"][:15]]
        A(table(["Ranga", "mieszkańcy", "komórki 250 m", "gmina (środek ciężkości)", "najbliższe centrum", "km"], rows))
        A("")
        A("![GZM](hotspots_gzm.png)")
        A("")
    A("@@POLY_READING@@")
    A("")
    # ---------------------------------------------------------------- 4
    A("## 4. Stopień urbanizacji: uproszczona klasyfikacja a oficjalne centra miejskie Eurostatu 2021")
    A("")
    A("Tabela 5. Udział ludności (NSP 2021, komórki 1 km o środku w obszarze). „Projekt” = uproszczona klasyfikacja "
      "z kroku density; „Eurostat” = oficjalne centra miejskie 2021; skupiska i komórki wiejskie liczone z "
      "oficjalnymi centrami.")
    A("")
    rows = []
    for a in ids:
        r = R[a]
        f_, c_ = r["degurba"]["fua"], r["degurba"]["core"]
        rows.append([name(r), pct(f_["uc_official"]), pct(f_["uc_own"]),
                     n((f_["uc_own"] - f_["uc_official"]) * 100, 1), pct(f_["cluster_hybrid"]), pct(f_["rural_hybrid"]),
                     pct(c_["uc_official"]), n((c_["uc_own"] - c_["uc_official"]) * 100, 1), pct(c_["cluster_hybrid"]),
                     pct(c_["rural_hybrid"]), n(f_["only_official_pop"]), n(f_["only_own_pop"])])
    A(table(["Aglomeracja", "FUA: centrum (Eurostat)", "FUA: centrum (projekt)", "różnica, pp", "FUA: skupisko",
             "FUA: wiejskie", "rdzeń: centrum (Eurostat)", "różnica, pp", "rdzeń: skupisko", "rdzeń: wiejskie",
             "FUA: ludność tylko w centrach Eurostatu", "FUA: ludność tylko w centrach projektu"], rows))
    A("")
    bridged = nat["only_official_ge1500_pop"] - nat["only_official_ge1500_crossborder_pop"]
    A(f"Cała Polska: centra Eurostatu obejmują {pct(nat['pop_share_official'])} ludności siatki, centra projektu "
      f"{pct(nat['pop_share_own'])}; komórek {n(nat['cells_official'])} i {n(nat['cells_own'])}, wspólnych "
      f"{n(nat['cells_both'])}. Ludność oficjalnych klastrów w Polsce równa się sumie NSP 2021 w ich komórkach "
      f"co do osoby w {nat['official_pop_equals_census_sum_clusters']} z {nat['official_clusters_in_poland']} "
      f"klastrów; pozostałe {nat['crossborder_clusters']} to klastry przygraniczne. Skąd różnice:")
    A("")
    A(f"- tylko w centrach Eurostatu: {n(nat['only_official_cells'])} komórek, {n(nat['only_official_pop'])} os.:")
    A(f"  - {n(nat['only_official_lt1500_cells'])} komórek o gęstości < 1 500 ({n(nat['only_official_lt1500_pop'])} "
      f"os.; w tym {nat['only_official_zero_pop_cells']} bez mieszkańców): wypełnienie luk albo reguła zabudowy "
      "≥ 50 %, której projekt nie stosuje;")
    A(f"  - {n(nat['only_official_ge1500_crossborder_pop'])} os. w komórkach ≥ 1 500 os./km² w dwóch klastrach "
      "przygranicznych (Słubice z Frankfurtem nad Odrą i Zgorzelec z Görlitz według współrzędnych; nazw nie "
      "sprawdzano na mapie): po stronie polskiej mają mniej niż 50 000 mieszkańców, razem z niemiecką więcej;")
    A(f"  - {n(bridged)} os. w komórkach ≥ 1 500 os./km², których własne skupisko (spójne 4-kierunkowo) ma "
      "poniżej 50 000 mieszkańców, a w warstwie Eurostatu jest częścią dużego klastra (Warszawa, GZM, Łódź, "
      "Trójmiasto): połączenie przez komórki rzadsze niż 1 500, zapewne przez regułę zabudowy;")
    A(f"- tylko w centrach projektu: {n(nat['only_own_cells'])} komórek, {n(nat['only_own_pop'])} os., wszystkie "
      "poniżej 1 500 os./km² (dołączone przez wypełnienie luk w projekcie, a nie u Eurostatu).")
    A("")
    A("@@DEGURBA_READING@@")
    A("")
    # ---------------------------------------------------------------- 5
    A("## 5. Mieszkańcy według gęstości komórki 250 m")
    A("")
    A("Tabela 6. Udział mieszkańców w klasach gęstości (FUA), udział mieszkańców komórek ≥ 5 000 i ≥ 10 000 os./km² "
      "w FUA i rdzeniu oraz gęstość komórki typowego mieszkańca.")
    A("")
    labs = [c["label"] for c in F.class_labels()]
    rows = []
    for a in sorted(R, key=lambda a: -R[a]["density_classes"]["fua"]["at_or_above"]["5000"]):
        dc = R[a]["density_classes"]
        rows.append([name(R[a])] + [pct(s, 0) for s in dc["fua"]["share"]]
                    + [pct(dc["fua"]["at_or_above"]["5000"]), pct(dc["core"]["at_or_above"]["5000"]),
                       pct(dc["fua"]["at_or_above"]["10000"]), pct(dc["core"]["at_or_above"]["10000"]),
                       n(dc["fua"]["median_density"]), n(dc["core"]["median_density"])])
    A(table(["Aglomeracja"] + [f"FUA {lab}" for lab in labs]
            + ["FUA ≥ 5 000", "rdzeń ≥ 5 000", "FUA ≥ 10 000", "rdzeń ≥ 10 000", "typowy mieszkaniec FUA, os./km²",
               "typowy mieszkaniec rdzenia, os./km²"], rows))
    A("")
    A("![Klasy gęstości](density_classes.png)")
    A("")
    for s in class_shares_check(R):
        A(s)
    A("")
    A("Dane pod wykres: `results/charts/form.json` (dla FUA i rdzenia: mieszkańcy i udziały w klasach, udział "
      "„w komórkach o gęstości co najmniej X” dla każdej granicy klas, mediana; oraz lista skupisk do wykresu "
      "ranga–wielkość).")
    A("")
    A("@@CLASS_READING@@")
    A("")
    A("## 6. Lektura krytyczna")
    A("")
    A("@@CRITICAL@@")
    A("")
    A("## 7. Nie zweryfikowano")
    A("")
    A("@@UNVERIFIED@@")
    A("")
    A("## 8. Pliki")
    A("")
    A("- Kod: `pipeline/form_extra.py` (obliczenia), `pipeline/form_md.py` (ta notatka i wykresy), "
      "`pipeline/form_text.py` (komentarze do tabel; asercje sprawdzają, że po ponownym przebiegu nadal są "
      "prawdziwe).")
    A("- Wyniki: `results/metrics/metrics_form.csv` i `.json` (krok `form`; poziom `table` albo `qa`), "
      "`results/charts/form.json`, `_meta_form.json` w obu katalogach.")
    A("- QA: `results/qa/form/form.md`, `extents.png`, `hotspots_gzm.png`, `rank_size.png`, `density_classes.png`.")
    A("- Pośrednie: `data/interim/form/<aglomeracja>.json` i `.npz` (maski zasięgów), `degurba_national.json`.")
    A("- Polecenia: `python -m pipeline.form_extra`, potem `python -m pipeline.form_md` (wymaga wcześniej "
      "`pipeline.density` i `pipeline.popgrid`).")
    A("")
    return "\n".join(L)


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    R = load()
    plot_extents(R)
    plot_gzm_hotspots(R)
    plot_rank_size(R)
    plot_classes(R)
    text = build(R)
    from pipeline import form_text as T
    for k, v in T.sections(R).items():
        text = text.replace(f"@@{k}@@", v)
    (QA / "form.md").write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {QA / 'form.md'}")


if __name__ == "__main__":
    main()
