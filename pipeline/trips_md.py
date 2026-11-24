"""Markdown tables for results/qa/trips/trips.md from the CSVs written by pipeline.trips_analyse.

    python -m pipeline.trips_md            # prints the tables; the note embeds them between the TABLE markers

The note's prose lives in results/qa/trips/trips.md; this module only regenerates the blocks
<!-- TABLE:name --> ... <!-- /TABLE:name --> so that numbers in the tables always come from the CSVs.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from pipeline.trips_analyse import JAKDOJADE, NAMES, ORDER, WBR2015_NO_TRANSFER
from pipeline.trips_sample import OUT, QA


def f(x, nd: int = 1) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    s = f"{float(x):,.{nd}f}".replace(",", " ").replace(".", ",")
    return s


def ci(r, c: str, nd: int = 1) -> str:
    return f"{f(r[c], nd)} ({f(r[c + '_lo'], nd)}–{f(r[c + '_hi'], nd)})"


def md(rows: list[list[str]], head: list[str], align: str | None = None) -> str:
    a = align or "|".join(["---"] * len(head))
    out = ["| " + " | ".join(head) + " |", "|" + a + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def t_sample() -> str:
    s = pd.read_csv(QA / "sample_summary.csv")
    rows = []
    for agg in ORDER:
        for _, r in s[s.agglomeration == agg].iterrows():
            rows.append([NAMES[agg], "mieszkańcy" if r.set == "res" else "miejsca pracy", f"{int(r.planned):d}",
                         f"{int(r.n_pt):d}", f"{int(r.n_walk):d}", f"{int(r.n_none):d}", f"{int(r.n_no_destination):d}",
                         f(r.pt_share_of_routed), f(r.median_dist_km_pt), f(r.routing_s / 60, 0), f(r.ms_per_trip, 0)])
    return md(rows, ["Aglomeracja", "Cele ważone", "Podróży", "KZ (wariant A)", "Pieszo szybciej", "Bez trasy w szczelinie",
                     "Brak celu w 60 min", "KZ, % podróży", "Mediana odległości KZ, km", "Routing, min", "ms / podróż"],
              "---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:")


def _sh(agg, s="res", v="A", o="wszystkie"):
    d = SH[(SH.agglomeration == agg) & (SH.set == s) & (SH.variant == v) & (SH.origins == o)]
    return d.iloc[0] if len(d) else None


def t_shares() -> str:
    rows = []
    for agg in ORDER:
        r = _sh(agg)
        if r is None:
            continue
        j = JAKDOJADE[agg]
        rows.append([NAMES[agg], f"{int(r.n):d}", ci(r, "share_0"), ci(r, "share_1"), ci(r, "share_2"), ci(r, "share_3plus"),
                     ci(r, "mean_transfers", 2), f"{j[0]} / {j[1]} / {j[2]}", f(j[3], 2),
                     f(WBR2015_NO_TRANSFER) if agg == "warszawa" else "–"])
    return md(rows, ["Aglomeracja", "Podróży KZ", "0 przesiadek, % (95 % CI)", "1, %", "2, %", "≥ 3, %",
                     "Średnio przesiadek", "Jakdojade 2025: 0 / 1 / 2, %", "Jakdojade: średnio", "WBR 2015: bez przesiadki, %"],
              "---|---:|---|---|---|---|---|---|---:|---:")


VARS = [("A", "A: najszybsza, cel ≤ 60 min"), ("B", "B: z pieszymi jako 0"), ("C", "C: każda trasa KZ"),
        ("A_cel_do_30_min", "cel ≤ 30 min"), ("A_cel_do_45_min", "cel ≤ 45 min"), ("A_kara_5_min", "kara 5 min"),
        ("A_kara_10_min", "kara 10 min"), ("A_cel_do_45_min_kara_5_min", "cel ≤ 45 min + kara 5 min")]


def t_variants(what: str = "share_0") -> str:
    rows = []
    for agg in ORDER:
        if _sh(agg) is None:
            continue
        row = [NAMES[agg]]
        for v, _ in VARS:
            r = _sh(agg, v=v)
            row.append("–" if r is None else (f(r[what], 2 if what == "mean_transfers" else 1) + (f" (n={int(r.n)})" if v.startswith("A_cel") else "")))
        j = JAKDOJADE[agg]
        row.append(f(j[3], 2) if what == "mean_transfers" else str(j[0]))
        rows.append(row)
    return md(rows, ["Aglomeracja"] + [lab for _, lab in VARS] + ["Jakdojade"], "---|" + "|".join(["---:"] * (len(VARS) + 1)))


def t_area() -> str:
    rows = []
    for agg in ORDER:
        a, b = _sh(agg, o="start w rdzeniu"), _sh(agg, o="start poza rdzeniem")
        if a is None:
            continue
        rows.append([NAMES[agg], f"{int(a.n)}", ci(a, "share_0"), ci(a, "mean_transfers", 2), f"{int(b.n)}", ci(b, "share_0"),
                     ci(b, "mean_transfers", 2)])
    return md(rows, ["Aglomeracja", "Start w rdzeniu: n", "0 przesiadek, %", "Średnio", "Start poza rdzeniem: n",
                     "0 przesiadek, %", "Średnio"], "---|---:|---|---|---:|---|---")


def t_jobs() -> str:
    rows = []
    for agg in ORDER:
        a, b = _sh(agg), _sh(agg, s="jobs")
        if a is None or b is None:
            continue
        rows.append([NAMES[agg], ci(a, "share_0"), ci(b, "share_0"), ci(a, "mean_transfers", 2), ci(b, "mean_transfers", 2),
                     f"{int(b.n)}"])
    return md(rows, ["Aglomeracja", "0 przesiadek, cele: mieszkańcy", "cele: miejsca pracy", "Średnio: mieszkańcy",
                     "Średnio: miejsca pracy", "n (miejsca pracy)"], "---|---|---|---|---|---:")


def t_comp() -> str:
    c = pd.read_csv(QA / "trip_composition.csv")
    rows = []
    for agg in ORDER:
        r = c[(c.agglomeration == agg) & (c.set == "res")]
        if not len(r):
            continue
        r = r.iloc[0]
        rows.append([NAMES[agg], f"{int(r.n_pt)}", ci(r, "mean_rides", 2), f(r.mean_total_min), ci(r, "walk_share"),
                     ci(r, "wait_share"), f(r.wait_first_share), f(r.wait_transfer_share), ci(r, "ride_share"),
                     f(r.transfer_walk_share), f"{f(r.walk_mean_min)} / {f(r.wait_mean_min)} / {f(r.ride_mean_min)}"])
    return md(rows, ["Aglomeracja", "Podróży KZ", "Średnio przejazdów", "Średni czas, min", "Pieszo, % czasu",
                     "Czekanie, % czasu", "w tym na starcie", "w tym przy przesiadkach", "W pojeździe, %",
                     "Dojście przy przesiadce, %", "Pieszo / czekanie / jazda, min"],
              "---|---:|---|---:|---|---|---:|---:|---|---:|---")


def t_rank() -> str:
    r = pd.read_csv(QA / "node_rank_comparison.csv")
    rows = []
    for agg in ORDER:
        q = r[r.agglomeration == agg]
        if not len(q):
            continue
        q = q.iloc[0]
        rows.append([NAMES[agg], f"{int(q.nodes)}", f"{int(q.nodes_with_use)}", f(q.spearman_dep_vs_use_mask, 2),
                     f"{int(q.top20_overlap)} z 20", f(q.top20_use_share_of_transfers), f(q.top20_dep_share_of_transfers),
                     f(q.get("where_jeden zespół")), f(q.get("where_dwa zespoły")),
                     f((q.get("where_jeden koniec w zespole") or 0) + (q.get("where_poza zespołami") or 0))])
    return md(rows, ["Aglomeracja", "Zespołów", "Z przesiadką w próbie", "Spearman: odjazdy 7–9 a użycie",
                     "Wspólne w top 20", "Top 20 wg użycia: % przesiadek", "Top 20 wg odjazdów: % przesiadek",
                     "Przesiadka w jednym zespole, %", "Między dwoma zespołami, %", "Poza zespołami lub jeden koniec, %"],
              "---|---:|---:|---:|---|---:|---:|---:|---:|---:")


def t_top(agg: str) -> str:
    t = pd.read_csv(QA / "node_use_top20.csv")
    t = t[t.agglomeration == agg]
    rows = []
    for _, r in t.iterrows():
        rows.append([str(int(r.rank_use)), str(r["name"]), f"{int(r.trips_changing)}",
                     f"{f(r.share_trips_changing, 2)} ({f(r.share_ci_low, 2)}–{f(r.share_ci_high, 2)})",
                     f(r.share_of_transfers), f(r.obs_transfer_walk_min), f(r.obs_transfer_wait_min),
                     f(r.walk_w_am_min), f(r.wait_w_am_min), f(r.dep_per_h_am, 0), str(int(r.rank_dep_am))])
    return md(rows, ["#", "Zespół", "Podróży z przesiadką", "% podróży KZ (95 % CI)", "% wszystkich przesiadek",
                     "Dojście w próbie, min", "Czekanie w próbie, min", "Warstwa: dojście, min", "Warstwa: czekanie, min",
                     "Odjazdy/h 7–9", "Miejsce wg odjazdów"],
              "---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:")


def t_nik() -> str:
    p = OUT / "nik_routed.csv"
    if not p.exists():
        return "(NIK: brak wyników routingu)"
    d = pd.read_csv(p)
    rows = []
    for g, q in d.groupby("gmina", sort=False):
        q0 = q.iloc[0]
        if q0.status != "ok" and pd.isna(q0.get("r5_min")):
            rows.append([g, NAMES[q0.agglomeration], str(q0.nik_pt_min), str(q0.nik_car_min), "–", "–", "–", "–", "–", q0.status])
            continue
        am_c = q[(q.window == "rano_do_miasta") & q.city_point.str.endswith("(centrum)")].iloc[0]
        am_h = q[(q.window == "rano_do_miasta") & q.city_point.str.endswith("(węzeł)")].iloc[0]
        pm_c = q[(q.window == "popoludnie_z_miasta") & q.city_point.str.endswith("(centrum)")].iloc[0]
        rows.append([g, NAMES[q0.agglomeration], str(q0.nik_pt_min), str(q0.nik_car_min),
                     f"{f(am_c.r5_min, 0)} / {f(am_c.r5_median, 0)} / {f(am_c.r5_max, 0)}",
                     f(am_c.r5_median - q0.nik_pt_min, 0) if pd.notna(am_c.r5_median) else "–",
                     f"{f(am_h.r5_median, 0)}", f"{f(pm_c.r5_min, 0)} / {f(pm_c.r5_median, 0)} / {f(pm_c.r5_max, 0)}",
                     f"{am_c.r5_fastest_lines} ({am_c.r5_fastest_departure})", str(q0.gmina_point)])
    return md(rows, ["Gmina", "Miasto", "NIK: KZ, min", "NIK: samochód, min", "R5 rano do centrum: min / mediana / maks",
                     "Mediana R5 − NIK, min", "R5 rano do węzła: mediana", "R5 po południu z centrum: min / mediana / maks",
                     "Najszybsza trasa R5 rano (odjazd)", "Punkt w gminie (OSM)"],
              "---|---|---:|---:|---|---:|---:|---|---|---")


def blocks() -> dict[str, str]:
    global SH
    SH = pd.read_csv(QA / "transfer_shares.csv")
    b = {"sample": t_sample(), "shares": t_shares(), "variants0": t_variants("share_0"),
         "variantsmean": t_variants("mean_transfers"), "area": t_area(), "jobs": t_jobs(), "comp": t_comp(),
         "rank": t_rank(), "nik": t_nik()}
    for agg in ORDER:
        b[f"top_{agg}"] = t_top(agg)
    return b


def main() -> None:
    b = blocks()
    note = QA / "trips.md"
    if note.exists():
        txt = note.read_text(encoding="utf-8")
        for k, v in b.items():
            txt = re.sub(rf"(<!-- TABLE:{k} -->)\n.*?(<!-- /TABLE:{k} -->)",
                         lambda m, v=v: m[1] + "\n" + v + "\n" + m[2], txt, flags=re.S)
        note.write_text(txt, encoding="utf-8", newline="\n")
        print("tables updated in", note)
    else:
        for k, v in b.items():
            print(f"<!-- TABLE:{k} -->\n{v}\n<!-- /TABLE:{k} -->\n")


if __name__ == "__main__":
    main()
