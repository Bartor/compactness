"""Phase 1, QA for the density measures: control plots (PNG) and results/qa/density/density.md.

Reads what pipeline.grid250, pipeline.density and pipeline.density_control left in
data/interim/{grid250,density}/ and results/qa/density/.  Plots are QA sketches, not
publication graphics.

Run: python -m pipeline.density_qa
"""
from __future__ import annotations

import datetime as dt
import json
import math
import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from pipeline.boundaries import all_agglomeration_ids, load_agglomeration
from pipeline.common import INTERIM, RESULTS, load_config, write_meta
from pipeline import density as D

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

QA = RESULTS / "qa" / "density"
DEN = INTERIM / "density"
TO_MOLL = Transformer.from_crs("EPSG:2180", "ESRI:54009", always_xy=True)
PHASE1_MONO = ["krakow", "lodz", "poznan", "warszawa", "wroclaw"]
plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "figure.dpi": 100})


# ------------------------------------------------------------------ formatting (Polish)

def n(v, nd: int = 0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "brak danych"
    s = f"{v:,.{nd}f}".replace(",", " ").replace(".", ",")
    return s


def g4(v) -> str:
    """Four significant digits, Polish decimal comma."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "brak danych"
    if v == 0:
        return "0"
    nd = max(0, 3 - int(math.floor(math.log10(abs(v)))))
    return n(v, nd)


def pct(v, nd: int = 1) -> str:
    return "brak danych" if v is None else n(v * 100, nd) + " %"


def table(head: list[str], rows: list[list]) -> str:
    out = "| " + " | ".join(head) + " |\n|" + "|".join(["---"] * len(head)) + "|\n"
    for r in rows:
        out += "| " + " | ".join(str(x) for x in r) + " |\n"
    return out


def load() -> tuple[dict, dict, dict]:
    res = {}
    for agg in sorted(all_agglomeration_ids()):
        with open(DEN / f"{agg}.json", encoding="utf-8") as f:
            res[agg] = json.load(f)
    with open(DEN / "control.json", encoding="utf-8") as f:
        ctl = json.load(f)
    with open(INTERIM / "grid250" / "qa.json", encoding="utf-8") as f:
        g250 = json.load(f)
    return res, ctl, g250


def profile(agg: str, key: str) -> pd.DataFrame:
    return pd.read_csv(DEN / f"{agg}_profile_{key}.csv")


# ------------------------------------------------------------------ plots

def outline_px(geom, tr):
    """Polygon exterior(s) in pixel coordinates of a Mollweide window."""
    g = D.reproj(shapely.segmentize(geom, 500), TO_MOLL)
    out = []
    for p in getattr(g, "geoms", [g]):
        for ring in [p.exterior, *p.interiors][:1]:
            xy = np.asarray(ring.coords)
            out.append(((xy[:, 0] - tr[2]) / tr[0], (xy[:, 1] - tr[5]) / tr[4]))
    return out


def plot_pwdens(agg: str, r: dict, a: dict) -> None:
    c = D.census()
    idx = D.census_in(a["fua"])
    sub = c.iloc[idx].copy()
    sub["d"] = sub.RES / sub.area_km2
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1.2, 1]})
    sub.plot(ax=ax1, column=sub.d.clip(upper=15000), cmap="magma_r", linewidth=0, legend=True,
             legend_kwds={"label": "os./km² (obcięte do 15 000)", "shrink": 0.7})
    gpd.GeoSeries([a["fua"]], crs=2180).boundary.plot(ax=ax1, color="#1D4ED8", linewidth=0.8)
    gpd.GeoSeries([a["core"]], crs=2180).boundary.plot(ax=ax1, color="#16a34a", linewidth=0.8)
    for cc in r["centres"]:
        ax1.plot(cc["x"], cc["y"], "k+", ms=8)
    ax1.set_title(f"{r['name']}: gęstość w komórkach NSP 2021 1 km (środek w FUA)\nniebieski: FUA, zielony: rdzeń")
    ax1.set_xticks([]); ax1.set_yticks([]); ax1.set_aspect("equal")
    bins = np.arange(0, 27000, 500)
    for dom, col in (("fua", "#1D4ED8"), ("core", "#16a34a")):
        s = c.iloc[D.census_in(a[dom])]
        ax2.hist(s.RES / s.area_km2, bins=bins, weights=s.RES / s.RES.sum(), histtype="step", color=col,
                 label=f"{dom.upper()}: PWD {n(r[dom]['census']['pwdens'])}, brutto {n(r[dom]['gross_density'])}")
        ax2.axvline(r[dom]["census"]["pwdens"], color=col, ls="--", lw=1)
    ax2.set_xlabel("gęstość komórki 1 km, os./km²"); ax2.set_ylabel("udział ludności obszaru")
    ax2.set_title("Rozkład ludności według gęstości komórki (linia przerywana: PWD)")
    ax2.legend(fontsize=7)
    fig.suptitle("QA §4.1, gęstość ważona populacją (siatka spisowa 1 km, NSP 2021-03-31)", fontsize=9)
    fig.savefig(QA / f"pwdens_{agg}.png", bbox_inches="tight")
    plt.close(fig)


def plot_profile(agg: str, r: dict) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    f = profile(agg, "fua")
    ok = f.area_km2 > 0
    ax1.semilogy(f.r_in_km[ok] + 0.5, f.density[ok], "o-", ms=3, color="#1D4ED8", label="pierścień 1 km, FUA (GHSL 100 m)")
    ck = r["clark"]
    if ck["b"] is not None:
        rr = np.linspace(1, 25, 50)
        ax1.semilogy(rr, ck["d0"] * np.exp(-ck["b"] * rr), "r-",
                     label=f"Clark 1–25 km: D0 {n(ck['d0'])}, b {g4(ck['b'])}/km, R² {g4(ck['r2'])}")
    ax1.set_xlim(0, 41); ax1.set_xlabel("odległość od centrum, km"); ax1.set_ylabel("os./km² (pole pierścienia w FUA)")
    ax1.legend(fontsize=7); ax1.set_title("Gęstość w pierścieniach (tylko tabela/QA)")
    styles = {"fua": ("#1D4ED8", "-", "(i) FUA, udział w ludności FUA"),
              "free": ("#E07B00", "-", "(ii) bez granic, udział w ludności do 40 km"),
              "fua_nearest": ("#1D4ED8", ":", "(i) do najbliższego z N centrów (inna miara)"),
              "free_nearest": ("#E07B00", ":", "(ii) do najbliższego z N centrów (inna miara)")}
    for k, (col, ls, lab) in styles.items():
        p = DEN / f"{agg}_profile_{k}.csv"
        if not p.exists():
            continue
        d = profile(agg, k)
        ax2.plot(np.r_[0, d.r_out_km], np.r_[0, d.cum_share], color=col, ls=ls, label=lab)
    cc = r["census_check"]
    ax2.plot(cc["steps_km"], cc["census_fua"], "s", color="#1D4ED8", mfc="none", label="NSP 1 km, (i)")
    ax2.plot(cc["steps_km"], cc["census_free"], "s", color="#E07B00", mfc="none", label="NSP 1 km, (ii)")
    ax2.set_xlim(0, max(40, int(f.r_out_km.max()))); ax2.set_ylim(0, 1.02)
    ax2.axvline(40, color="grey", lw=0.5)
    ax2.set_xlabel("odległość od centrum, km"); ax2.set_ylabel("udział skumulowany")
    ax2.legend(fontsize=6.5, loc="lower right"); ax2.grid(alpha=0.3)
    ax2.set_title(f"Krzywa skumulowana; maks. różnica GHSL–NSP: {g4(cc['max_abs_diff_pp_fua'])} pp (i), "
                  f"{g4(cc['max_abs_diff_pp_free'])} pp (ii)")
    flag = " (POLICENTRYCZNA: miara jednocentrowa z zastrzeżeniem)" if r["polycentric"] else ""
    fig.suptitle(f"QA §4.2, {r['name']}{flag}: centrum {r['centres'][0]['name']}; GHS-POP 2020 (model)", fontsize=9)
    fig.savefig(QA / f"profile_{agg}.png", bbox_inches="tight")
    plt.close(fig)


def plot_mask(agg: str, r: dict, a: dict, thr_work: float) -> None:
    z = np.load(DEN / f"{agg}.npz")
    tr = z["tr"]
    M, pop, domf = z["mask"], z["pop"], z["dom_f"]
    rows, cols = np.nonzero(domf)
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1.5, 1]})
    img = np.full(M.shape + (3,), 1.0)
    img[domf] = (0.93, 0.93, 0.93)
    dens = np.clip(pop / 0.01 / 15000, 0, 1)
    shade = np.stack([1 - 0.6 * dens] * 3, axis=-1)
    img[domf] = shade[domf] * 0.93
    img[M] = (0.85, 0.35, 0.1)
    ax1.imshow(img[r0:r1, c0:c1], interpolation="nearest")
    for dom, col in (("fua", "#1D4ED8"), ("core", "#16a34a")):
        for xs, ys in outline_px(a[dom], tr):
            ax1.plot(xs - c0, ys - r0, color=col, lw=0.7)
    for cc in r["centres"]:
        X, Y = TO_MOLL.transform(cc["x"], cc["y"])
        ax1.plot((X - tr[2]) / tr[0] - c0, (Y - tr[5]) / tr[4] - r0, "k+", ms=9)
    e = r["rho"][str(thr_work)]["fua"]
    ax1.set_title(f"Maska zabudowy ≥ {int(thr_work * 100)} % (pomarańczowy), spójna z centrami, luka ≤ 600 m\n"
                  f"pole {n(e['area_km2'])} km², {pct(e['pop_share'])} ludności FUA, ρ = {g4(e['rho'])}; "
                  "szarość: gęstość GHSL")
    ax1.set_xticks([]); ax1.set_yticks([])
    ths = sorted(r["rho"], key=float)
    x = [float(t) * 100 for t in ths]
    ax2.plot(x, [r["rho"][t]["fua"]["rho_raw"] for t in ths], "o-", color="#1D4ED8", label="ρ FUA (surowe)")
    ax2.plot(x, [r["rho"][t]["core"]["rho_raw"] for t in ths], "s--", color="#16a34a", label="ρ rdzeń (surowe)")
    if "fua_nearest" in r["rho"][ths[0]]:
        ax2.plot(x, [r["rho"][t]["fua_nearest"]["rho_raw"] for t in ths], "^:", color="k",
                 label="ρ do najbliższego centrum (inna miara)")
    ax2.axhline(1, color="grey", lw=0.6)
    ax2.set_yscale("log"); ax2.set_xlabel("próg udziału zabudowy w komórce 100 m, %"); ax2.set_ylabel("ρ")
    ax3 = ax2.twinx()
    ax3.bar(x, [r["rho"][t]["fua"]["pop_share"] * 100 for t in ths], width=3, alpha=0.25, color="#E07B00")
    ax3.set_ylabel("udział ludności FUA w masce, % (słupki)")
    ax2.legend(fontsize=7, loc="upper left")
    ax2.set_title("Wrażliwość na próg (null w tabelach, gdy w masce < 5 % ludności)")
    flag = " (POLICENTRYCZNA)" if r["polycentric"] else ""
    fig.suptitle(f"QA §4.3, {r['name']}{flag}: indeks dyspersji Bertauda; GHS-BUILT-S i GHS-POP 2020 100 m", fontsize=9)
    fig.savefig(QA / f"mask_{agg}.png", bbox_inches="tight")
    plt.close(fig)


def lorenz(p):
    s = np.sort(p)
    return np.r_[0, np.arange(1, len(s) + 1) / len(s)], np.r_[0, np.cumsum(s) / s.sum()]


def plot_gini(agg: str, r: dict) -> None:
    z = np.load(DEN / f"{agg}.npz")
    pop, M, circ = z["pop"].astype(float), z["mask"], z["circle"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))
    for key, m, col, lab in (("mask_fua", M, "#E07B00", "maska ≥ próg roboczy"), ("circle", circ, "#1D4ED8", f"koło {D.CIRCLE_KM} km")):
        ge = r["gini_eta"][key]
        F, L = lorenz(pop[m])
        ax1.plot(F, L, color=col, label=f"{lab}: G/Gmax {g4(ge['gini_norm'])}, η {g4(ge['eta'])}, F* {g4(ge['loubar_F'])}")
        ax1.axvline(ge["loubar_F"], color=col, ls=":", lw=0.8)
    ax1.plot([0, 1], [0, 1], color="grey", lw=0.5)
    ax1.set_xlabel("F (udział komórek)"); ax1.set_ylabel("L (udział ludności)"); ax1.legend(fontsize=7)
    ax1.set_title("Krzywe Lorenza; kropkowana: próg LouBar")
    ge = r["gini_eta"]["mask_fua"]
    thr = ge["loubar_pop_per_cell"]
    rows, cols = np.nonzero(M)
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    img = np.ones(M.shape + (3,))
    img[M] = (0.85, 0.85, 0.85)
    img[M & (pop >= thr)] = (0.8, 0.1, 0.1)
    ax2.imshow(img[r0:r1, c0:c1], interpolation="nearest")
    ax2.set_xticks([]); ax2.set_yticks([])
    ax2.set_title(f"Hotspoty (LouBar ≥ {n(ge['loubar_density'])} os./km², {ge['n_hotspots']} komórek) w masce")
    fig.suptitle(f"QA §4.4, {r['name']}: Gini i η (Volpati i Barthelemy 2018); tylko kontrola, nie na grafiki; "
                 "GHS-POP 2020 100 m", fontsize=9)
    fig.savefig(QA / f"gini_{agg}.png", bbox_inches="tight")
    plt.close(fig)


def plot_control(agg: str, r: dict, a: dict) -> None:
    c = D.census()
    gh = D.ghsl_on_census()
    idx = D.census_in(a["fua"])
    nsp, g = c.RES.values[idx].astype(float), gh[idx]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1, 1.2]})
    ax1.scatter(nsp + 1, g + 1, s=3, alpha=0.4, color="#1D4ED8")
    lim = max(nsp.max(), g.max()) * 1.2
    ax1.plot([1, lim], [1, lim], color="grey", lw=0.6)
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.set_xlabel("NSP 2021, osoby w komórce 1 km (+1)"); ax1.set_ylabel("GHSL 2020 w tej komórce (+1)")
    ax1.set_title("Komórki 1 km w FUA")
    sub = c.iloc[idx].copy()
    sub["diff"] = g * nsp.sum() / g.sum() - nsp
    lim = np.percentile(np.abs(sub["diff"]), 99)
    sub.plot(ax=ax2, column="diff", cmap="RdBu_r", vmin=-lim, vmax=lim, linewidth=0, legend=True,
             legend_kwds={"label": "GHSL przeskalowany do sumy NSP minus NSP, osoby", "shrink": 0.7})
    gpd.GeoSeries([a["core"]], crs=2180).boundary.plot(ax=ax2, color="k", linewidth=0.6)
    ax2.set_xticks([]); ax2.set_yticks([]); ax2.set_aspect("equal")
    ax2.set_title("Różnica przestrzenna po usunięciu różnicy poziomu (czerwone: GHSL więcej)")
    fig.suptitle(f"QA §7.1, {r['name']}: GHS-POP 2020 zsumowany do komórek NSP 2021 1 km", fontsize=9)
    fig.savefig(QA / f"control_{agg}.png", bbox_inches="tight")
    plt.close(fig)


def summary_plots(res: dict, ctl: dict, thr_list: list[float]) -> None:
    ids = sorted(res, key=lambda k: -res[k]["fua"]["census"]["pwdens"])
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = np.arange(len(ids))
    ax.bar(x - 0.3, [res[k]["fua"]["census"]["pwdens"] for k in ids], 0.2, label="PWD FUA (1 km)", color="#1D4ED8")
    ax.bar(x - 0.1, [res[k]["core"]["census"]["pwdens"] for k in ids], 0.2, label="PWD rdzeń (1 km)", color="#93c5fd")
    ax.bar(x + 0.1, [res[k]["fua"]["gross_density"] for k in ids], 0.2, label="brutto FUA", color="#E07B00")
    ax.bar(x + 0.3, [res[k]["core"]["gross_density"] for k in ids], 0.2, label="brutto rdzeń", color="#fdba74")
    ax.set_xticks(x, [res[k]["name"] + (" *" if res[k]["polycentric"] else "") for k in ids], rotation=30, ha="right")
    ax.set_ylabel("os./km²"); ax.legend(fontsize=7)
    ax.set_title("PWD (siatka spisowa 1 km) i gęstość brutto; NSP 2021-03-31; * policentryczne")
    fig.savefig(QA / "summary_pwdens.png", bbox_inches="tight"); plt.close(fig)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
    ths = [str(t) for t in thr_list]
    for k in sorted(res):
        rr = res[k]
        ls = ":" if rr["polycentric"] else "-"
        ax1.plot([float(t) * 100 for t in ths], [rr["rho"][t]["fua"]["rho_raw"] for t in ths], ls, marker="o", ms=3,
                 label=rr["name"])
    ax1.set_yscale("log"); ax1.set_xlabel("próg zabudowy, %"); ax1.set_ylabel("ρ FUA (surowe)")
    ax1.axhline(1, color="grey", lw=0.5); ax1.legend(fontsize=6, ncol=2)
    ax1.set_title("ρ według progu (kropkowane: policentryczne)")
    mono = [k for k in sorted(res) if not res[k]["polycentric"]]
    for k in mono:
        ranks = []
        for t in ths[:-1]:
            vals = sorted(mono, key=lambda m: res[m]["rho"][t]["fua"]["rho_raw"])
            ranks.append(vals.index(k) + 1)
        ax2.plot([float(t) * 100 for t in ths[:-1]], ranks, "o-", ms=3)
        ax2.annotate(res[k]["name"], (float(ths[-2]) * 100 + 0.5, ranks[-1]), fontsize=6, va="center")
    ax2.invert_yaxis(); ax2.set_xlabel("próg zabudowy, %"); ax2.set_ylabel("miejsce (1 = najniższe ρ)")
    ax2.set_title("Ranking miast jednocentrowych według ρ FUA (bez progu 50 %)")
    fig.savefig(QA / "summary_rho_sensitivity.png", bbox_inches="tight"); plt.close(fig)

    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
    for k in sorted(res):
        if res[k]["polycentric"]:
            continue
        lw = 1.6 if k in PHASE1_MONO else 0.8
        f = profile(k, "fua"); fr = profile(k, "free")
        axs[0].plot(np.r_[0, f.r_out_km], np.r_[0, f.cum_share], lw=lw, label=res[k]["name"])
        axs[1].plot(np.r_[0, fr.r_out_km], np.r_[0, fr.cum_share], lw=lw, label=res[k]["name"])
        axs[2].plot(np.r_[0, fr.r_out_km], np.r_[0, fr.cum_pop] / 1e6, lw=lw, label=res[k]["name"])
    axs[0].set_title("(i) udział w ludności FUA"); axs[1].set_title("(ii) bez granic: udział w ludności do 40 km")
    axs[2].set_title("(ii) bez granic: ludność skumulowana, mln")
    for ax in axs:
        ax.set_xlim(0, 40); ax.grid(alpha=0.3); ax.set_xlabel("km od centrum")
    axs[0].legend(fontsize=6)
    fig.suptitle("Profile skumulowane, aglomeracje jednocentrowe (grube: faza 1); GHS-POP 2020 100 m (model)", fontsize=9)
    fig.savefig(QA / "summary_profiles_monocentric.png", bbox_inches="tight"); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4))
    for k in sorted(res):
        if not res[k]["polycentric"]:
            continue
        for ax, key in zip(axs, ("fua", "fua_nearest")):
            d = profile(k, key)
            ax.plot(np.r_[0, d.r_out_km], np.r_[0, d.cum_share], label=res[k]["name"])
    axs[0].set_title("(i) od centrum głównego"); axs[1].set_title("(i) do najbliższego z N centrów (inna miara)")
    for ax in axs:
        ax.set_xlim(0, 60); ax.grid(alpha=0.3); ax.legend(fontsize=7); ax.set_xlabel("km")
    fig.suptitle("Profile skumulowane, aglomeracje policentryczne / liniowe (osobny panel)", fontsize=9)
    fig.savefig(QA / "summary_profiles_polycentric.png", bbox_inches="tight"); plt.close(fig)

    t = pd.DataFrame(ctl["totals"])
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.2))
    order = t[t.domain == "fua"].sort_values("ghsl_to_nsp").agglomeration.tolist()
    for ax, dom in zip(axs, ("fua", "core")):
        s = t[t.domain == dom].set_index("agglomeration").loc[order].reset_index()
        y = np.arange(len(s))
        ax.barh(y + 0.3, s.ghsl_to_nsp - 1, 0.2, color="k", label="GHSL / NSP (siatka) − 1")
        ax.barh(y + 0.1, s.f_national_to_resident - 1, 0.2, color="#E07B00", label="definicja: krajowa / rezydująca − 1")
        ax.barh(y - 0.1, s.f_ghsl_to_national - 1, 0.2, color="#1D4ED8", label="GHSL / BDL krajowa − 1 (reszta)")
        ax.barh(y - 0.3, s.f_bdl_resident_to_grid - 1, 0.2, color="#16a34a", label="BDL rezydująca / siatka − 1 (przypisanie)")
        ax.set_yticks(y, s.name); ax.axvline(0, color="grey", lw=0.5)
        for v in (-0.05, 0.05):
            ax.axvline(v, color="red", lw=0.5, ls=":")
        ax.set_title(dom.upper())
    axs[0].legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(1.1, -0.08), ncol=2)
    fig.suptitle("§7.1: rozkład różnicy GHSL 2020 / NSP 2021 na czynniki (ułamki; kropkowane ±5 %)", fontsize=9)
    fig.savefig(QA / "summary_control.png", bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------ markdown

def write_md(res: dict, ctl: dict, g250: dict, thr_list: list[float], thr_work: float) -> None:
    today = dt.date.today().isoformat()
    ids = sorted(res, key=lambda k: (res[k]["phase"], k))
    tw = str(thr_work)
    poly = [k for k in ids if res[k]["polycentric"]]
    mono = [k for k in ids if not res[k]["polycentric"]]

    def nm(k):
        return res[k]["name"] + (" *" if res[k]["polycentric"] else "")

    t_main = table(
        ["Aglomeracja", "Faza", "Ludność FUA (NSP)", "PWD FUA", "PWD rdzeń", "Brutto FUA", "Brutto rdzeń",
         "PWD GHSL 250 m FUA", "PWD GHSL 250 m rdzeń"],
        [[nm(k), res[k]["phase"], n(res[k]["fua"]["census"]["pop"]), n(res[k]["fua"]["census"]["pwdens"]),
          n(res[k]["core"]["census"]["pwdens"]), n(res[k]["fua"]["gross_density"]), n(res[k]["core"]["gross_density"]),
          n(res[k]["fua"]["ghsl250"]["pwdens"]), n(res[k]["core"]["ghsl250"]["pwdens"])] for k in ids])

    rob_rows = []
    worst = 0.0
    for k in ids:
        for dom in ("fua", "core"):
            cc = res[k][dom]["census"]
            dn = cc["pwdens_nominal"] / cc["pwdens"] - 1
            da = cc["pwdens_area_weighted"] / cc["pwdens"] - 1
            worst = max(worst, abs(dn), abs(da))
            rob_rows.append([nm(k), dom.upper(), n(cc["pwdens"]), n(cc["pwdens_nominal"]), pct(dn, 2),
                             n(cc["pwdens_area_weighted"]), pct(da, 2), cc["boundary_cells"], cc["clipped_cells"],
                             n(cc["pwdens_ghsl_1km"]), pct(cc["pwdens_ghsl_1km"] / cc["pwdens"] - 1)])
    t_rob = table(["Aglomeracja", "Domena", "PWD (główna)", "pole nominalne 1 km²", "różnica",
                   "komórki brzegowe ważone polem", "różnica", "komórki przecięte granicą obszaru",
                   "komórki przycięte granicą państwa", "PWD z GHSL na tych samych komórkach", "różnica"], rob_rows)

    t_prof = table(
        ["Aglomeracja", "r50 (i) FUA, km", "r50 (ii), km", "udział do 10 km (i)", "udział do 10 km (ii)",
         "gęstość 0–1 km", "Clark b, 1/km", "Clark D0", "R²", "maks. różnica GHSL–NSP (i), pp", "(ii), pp"],
        [[nm(k), g4(res[k]["r50"]["fua"]), g4(res[k]["r50"]["free"]), pct(res[k]["share_within"]["fua"]["10"]),
          pct(res[k]["share_within"]["free"]["10"]), n(res[k]["clark"]["first_km_density"]), g4(res[k]["clark"]["b"]),
          n(res[k]["clark"]["d0"]), g4(res[k]["clark"]["r2"]), g4(res[k]["census_check"]["max_abs_diff_pp_fua"]),
          g4(res[k]["census_check"]["max_abs_diff_pp_free"])] for k in ids])

    steps = res[ids[0]]["census_check"]["steps_km"]
    cc_rows = []
    for k in ids:
        cc = res[k]["census_check"]
        cc_rows.append([nm(k)] + [f"{n(cc['ghsl_fua'][i] * 100, 1)} / {n(cc['census_fua'][i] * 100, 1)}"
                                  for i in range(len(steps)) if steps[i] in (2, 5, 10, 20, 30)])
    t_cc = table(["Aglomeracja"] + [f"do {s} km: GHSL / NSP, %" for s in steps if s in (2, 5, 10, 20, 30)], cc_rows)

    ths = [str(t) for t in thr_list]

    def rho_cell(e):
        if e["rho"] is None:
            return f"brak danych ({g4(e['rho_raw'])})" if e.get("rho_raw") is not None else "brak danych"
        return g4(e["rho"])

    rho_rows = []
    for k in ids:
        rho_rows.append([nm(k)] + [rho_cell(res[k]["rho"][t]["fua"]) for t in ths]
                        + [f"{n(res[k]['rho'][t]['fua']['area_km2'])} / {pct(res[k]['rho'][t]['fua']['pop_share'], 0)}"
                           for t in ths])
    t_rho = table(["Aglomeracja"] + [f"ρ FUA, ≥ {int(float(t) * 100)} %" for t in ths]
                  + [f"maska ≥ {int(float(t) * 100)} %: km² / udział ludności FUA" for t in ths], rho_rows)
    rho_core = table(["Aglomeracja"] + [f"ρ rdzeń, ≥ {int(float(t) * 100)} %" for t in ths]
                     + [f"udział ludności rdzenia w masce ≥ {int(float(t) * 100)} %" for t in ths],
                     [[nm(k)] + [rho_cell(res[k]["rho"][t]["core"]) for t in ths]
                      + [pct(res[k]["rho"][t]["core"]["pop_share"], 0) for t in ths] for k in ids])
    rank_rows = []
    for t in ths:
        valid = [k for k in mono if res[k]["rho"][t]["fua"]["rho"] is not None]
        order = sorted(valid, key=lambda k: res[k]["rho"][t]["fua"]["rho"])
        rank_rows.append([f"≥ {int(float(t) * 100)} %", ", ".join(f"{res[k]['name']} {g4(res[k]['rho'][t]['fua']['rho'])}"
                                                                    for k in order) or "brak danych"])
    t_rank = table(["Próg", "Miasta jednocentrowe od najniższego ρ FUA"], rank_rows)
    from scipy.stats import spearmanr
    corr_rows = []
    for i, t1 in enumerate(ths):
        for t2 in ths[i + 1:]:
            valid = [k for k in mono if res[k]["rho"][t1]["fua"]["rho"] is not None and res[k]["rho"][t2]["fua"]["rho"] is not None]
            if len(valid) >= 4:
                s = spearmanr([res[k]["rho"][t1]["fua"]["rho"] for k in valid], [res[k]["rho"][t2]["fua"]["rho"] for k in valid]).statistic
                corr_rows.append([f"{int(float(t1) * 100)} % vs {int(float(t2) * 100)} %", len(valid), g4(s)])
    t_corr = table(["Progi", "Miast", "Korelacja Spearmana rankingów ρ FUA"], corr_rows)

    gaps = list(res[ids[0]]["rho_gap_sensitivity"].keys())
    t_gap = table(["Aglomeracja"] + [f"luka ≤ {res[ids[0]]['rho_gap_sensitivity'][g]['gap_m']} m" for g in gaps]
                  + ["część klastra poza FUA (FUA + 15 km)"],
                  [[nm(k)] + [f"{g4(res[k]['rho_gap_sensitivity'][g]['rho'])} ({n(res[k]['rho_gap_sensitivity'][g]['area_km2'])} km²)"
                              for g in gaps] + [pct(res[k]["rho_truncation"]["share_outside_fua"])] for k in ids])

    t_near = table(["Aglomeracja", "Liczba centrów"] + [f"ρ do najbliższego, ≥ {int(float(t) * 100)} %" for t in ths]
                   + [f"wariant N kół, ≥ {int(thr_work * 100)} %", f"średnia odległość do najbliższego centrum, km (≥ {int(thr_work * 100)} %)"],
                   [[nm(k), len(res[k]["centres"])] + [rho_cell(res[k]["rho"][t]["fua_nearest"]) for t in ths]
                    + [g4(res[k]["rho"][tw]["fua_nearest"].get("rho_ndisc")), g4(res[k]["rho"][tw]["fua_nearest"]["mean_dist_km"])]
                    for k in poly])

    ge_rows = []
    for k in ids:
        ge = res[k]["gini_eta"]
        ge_rows.append([nm(k), g4(ge["mask_fua"]["gini_norm"]), g4(ge["mask_fua"]["eta"]), n(ge["mask_fua"]["loubar_density"]),
                        ge["mask_fua"]["n_hotspots"], ge["mask_fua"]["n_cells"], g4(ge["circle"]["gini_norm"]),
                        g4(ge["circle"]["eta"]), n(ge["circle"]["loubar_density"]), ge["circle"]["n_hotspots"]])
    t_ge = table(["Aglomeracja", "G/Gmax maska", "η maska", "próg LouBar maska, os./km²", "hotspoty", "komórki",
                  f"G/Gmax koło {D.CIRCLE_KM} km", "η koło", "próg LouBar koło", "hotspoty"], ge_rows)

    nat = ctl["national"]
    t_nat = table(["Wielkość", "Ludność", "Uwagi"], [
        ["Siatka NSP 2021 1 km (`RES`), suma", n(nat["nsp_grid_sum"]), "ludność rezydująca, 31.03.2021"],
        ["BDL NSP 2021, ludność rezydująca, suma gmin (zm. 1644331)", n(nat["bdl_resident_2021_sum"]), "zgodna z siatką co do osoby"],
        ["BDL NSP 2021, ludność ogółem (def. krajowa), suma gmin (zm. 1639271)", n(nat["bdl_national_2021_sum"]), "31.03.2021"],
        ["GHS-POP 2020, komórki 250 m o środku w Polsce", n(nat["ghsl_poland_250m"]), "epoka 2020, model"],
        ["GHS-POP 2020 zsumowany do komórek NSP 1 km", n(nat["ghsl_in_census_footprint_1km"]),
         "zawiera ludność zagraniczną w komórkach przyciętych granicą"],
        ["to samo, bez komórek przyciętych", n(nat["ghsl_in_census_footprint_1km_unclipped_cells"]), ""],
    ])
    tt = pd.DataFrame(ctl["totals"])
    tot_rows = []
    for _, r in tt.sort_values(["agglomeration", "domain"], ascending=[True, False]).iterrows():
        tot_rows.append([res[r.agglomeration]["name"], r.domain.upper(), int(r.gminas), n(r.nsp_grid), n(r.bdl_resident_2021),
                         n(r.bdl_national_2021), n(r.ghsl_2020), g4(r.ghsl_to_nsp), g4(r.f_bdl_resident_to_grid),
                         g4(r.f_national_to_resident), g4(r.f_ghsl_to_national), r.flag_gt5pct])
    t_tot = table(["Aglomeracja", "Domena", "Gmin", "NSP siatka", "BDL rezydująca", "BDL krajowa", "GHSL 2020",
                   "GHSL/NSP", "(a) BDL rez./siatka", "(b) krajowa/rez.", "(c) GHSL/krajowa", "|GHSL/NSP−1| > 5 %"], tot_rows)
    cells = pd.DataFrame(ctl["cells"])
    t_cells = table(["Aglomeracja", "Domena", "Komórki", "Pearson", "Pearson log(1+x)", "Spearman", "Indeks niepodobieństwa D"],
                    [[res[r.agglomeration]["name"], r.domain.upper(), int(r.cells), g4(r.pearson), g4(r.pearson_log1p),
                      g4(r.spearman), pct(r.dissimilarity)]
                     for _, r in cells.sort_values(["agglomeration", "domain"], ascending=[True, False]).iterrows()])
    top = pd.DataFrame(ctl["top_cells"])
    top_rows = []
    for k in ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]:
        s = top[(top.agglomeration == k) & (top.kind == "abs")].head(3)
        s2 = top[(top.agglomeration == k) & (top.kind == "rel")].head(2)
        for _, r in pd.concat([s, s2]).iterrows():
            top_rows.append([res[k]["name"], "bezwzględna" if r.kind == "abs" else "względna", f"{r.lat}, {r.lon}",
                             r.gmina, n(r.nsp_2021), n(r.ghsl_2020), n(r["diff"])])
    t_top = table(["Aglomeracja", "Rodzaj", "Środek komórki (lat, lon)", "Gmina", "NSP 2021", "GHSL 2020", "GHSL − NSP"], top_rows)

    g = g250
    gw = g["window_check"]
    per = g["per_agglomeration"]
    maxf = max(abs(v["fua"]["rel_diff"]) for v in per.values())
    maxc = max(abs(v["core"]["rel_diff"]) for v in per.values())

    def rw(k, t="0.2"):
        return res[k]["rho"][t]["fua"]

    def share_range(t):
        v = [res[k]["rho"][t]["fua"]["pop_share"] for k in ids]
        return f"{n(min(v) * 100)}–{n(max(v) * 100)} %"

    def area_range(t):
        v = [res[k]["rho"][t]["fua"]["area_km2"] for k in ids]
        return f"{n(min(v))}–{n(max(v))} km²"

    gd = [res[k][d]["census"]["pwdens_ghsl_1km"] / res[k][d]["census"]["pwdens"] - 1 for k in ids for d in ("fua", "core")
          if k != "rzeszow"]
    ghsl_pwdens_range = f"{n(-max(gd) * 100)}–{n(-min(gd) * 100)} %"
    below1 = [(res[k]["name"], d, t) for k in ids for d in ("fua", "core") for t in ths
              if res[k]["rho"][t][d]["rho"] is not None and res[k]["rho"][t][d]["rho"] < 1]
    below1_txt = ("; wyjątki (ρ < 1): " + ", ".join(f"{a} {b} przy {int(float(c) * 100)} %" for a, b, c in below1)) if below1 else ""
    eta_mono = sorted(mono, key=lambda k: res[k]["gini_eta"]["mask_fua"]["eta"])
    eta_low = ", ".join(f"{res[k]['name']} {g4(res[k]['gini_eta']['mask_fua']['eta'])}" for k in eta_mono[:3])
    eta_high = ", ".join(f"{res[k]['name']} {g4(res[k]['gini_eta']['mask_fua']['eta'])}" for k in eta_mono[-2:])
    seeds = sorted({res[k]["rho"][t]["fua"]["seed_radius_m"] for k in ids for t in ths})
    corr = {r[0]: r[2] for r in corr_rows}
    core_sh = [res[k]["rho"][t]["core"]["pop_share"] for k in ids for t in ths[:2]]

    txt = f"""# Faza 1: miary gęstości (§4.1–4.4) i kontrola GHSL vs NSP (§7.1)

Wygenerowano: {today} (`python -m pipeline.density_qa`; liczby z `pipeline.grid250`, `pipeline.density`,
`pipeline.density_control`). Wszystkie liczby w tym pliku są przepisywane przez kod z plików pośrednich, więc zgadzają się z
`results/metrics/metrics_density.csv` (po scaleniu: `metrics.csv`). Daty danych: **ludność NSP 2021 stan na 31.03.2021** (ludność rezydująca), **GHSL epoka 2020**
(dane modelowane, nie spisowe). Rozkładów jazdy ta faza nie używa (`timetable_date` = brak). Granice: Eurostat URAU 2021, GZM
w wariancie (a) (suma czterech FUA), Trójmiasto jako suma dwóch FUA. Aglomeracje oznaczone * są policentryczne lub liniowe
(GZM, Trójmiasto, Bydgoszcz–Toruń): miary jednocentrowe podajemy dla nich wyłącznie z zastrzeżeniem (brief §11).

## 1. Metoda w wersji wykonanej

Każdą regułę, której brief nie przesądza, trzeba było doprecyzować. Poniżej wszystkie takie decyzje.

### 1.1 Gęstość ważona populacją (PWD, §4.1)

- **Wzór:** gęstość ważona populacją: Σ pᵢ·dᵢ / Σ pᵢ, gdzie dᵢ = pᵢ / pole komórki i.
- **Siatka główna:** NSP 2021, siatka 1 km (EU LAEA, EPSG:3035, kody `CRS3035RES1000mN…E…`), pole `RES` (ludność rezydująca).
- **Przypisanie do domeny (FUA, rdzeń):** komórka należy do obszaru, gdy jej **centroid** (EPSG:2180) leży wewnątrz
  wielokąta, jak w fazie 0.
- **Pole komórki:** własne pole komórki w EPSG:3035 (układ równopolowy, natywny dla siatki). Dla komórek pełnych to dokładnie
  1 km²; dla przyciętych granicą państwa lub brzegiem morza jest mniejsze (w kraju 4 241 takich komórek z 28 753 osobami).
  W EPSG:2180 pola pełnych komórek różnią się od 1 km² o 0,02–0,2 % przez zniekształcenie odwzorowania, dlatego nie liczymy
  pola w EPSG:2180.
- **Sprawdzenie, czy wybór coś zmienia:** (a) pole nominalne 1 km² dla każdej komórki; (b) komórki przecięte granicą
  domeny ważone udziałem swojego pola w domenie, zamiast reguły centroidu. Największa zmiana PWD w którejkolwiek
  aglomeracji i domenie: **{pct(worst, 2)}**. Wybór nie wpływa na wynik w sposób istotny (tabela 2).
- **Pomocniczo, GHSL 250 m:** siatka 250 m w EPSG:2180 (patrz 1.2), komórka o środku w obszarze, d = p / 0,0625 km².
  Liczba jest z innej siatki i innego źródła, więc **nie porównujemy jej z PWD 1 km** (MAUP).
- **Kontrola źródła:** GHSL zsumowany do tych samych komórek spisowych 1 km (PWD „GHSL 1 km”). To oddziela różnicę
  źródła od różnicy siatki.
- **Gęstość brutto:** ludność NSP (reguła centroidu) / pole wielokąta w EPSG:3035. Służy tylko do kontrastu i zależy od
  rysunku granicy.

### 1.2 Siatka GHSL 250 m (produkt wielokrotnego użytku)

- **Plik:** `data/interim/grid250/ghs_pop_2020_250m_epsg2180.tif`, float32, nodata −1 (morze, poza źródłem).
- **Zasięg:** {g['grid']['width']} × {g['grid']['height']} komórek, EPSG:2180, krawędzie komórek w wielokrotnościach 250 m.
  Obejmuje Polskę i wszystkie FUA + 15 km.
- **Metoda:** z GHS-POP 100 m (Mollweide) przez `rasterio.warp.reproject` z `Resampling.sum` i `tolerance=0`.
  Przy domyślnym przybliżonym transformatorze GDAL (`tolerance=0.125` piksela) wynik miał względem dokładnej referencji
  dipole ±100 osób na komórkę (RMSE ok. 19 osób). Po przejściu na transformator dokładny:
  - RMSE: {g4(gw['rel_rmse_gdal_vs_ref'] * 100)} % średniej zamieszkanej komórki;
  - maks. różnica: {g4(gw['max_abs_cell_diff_gdal'])} osoby;
  - referencja: okno 30 × 30 km w centrum Warszawy, każdy piksel źródła podzielony na 20 × 20 podpikseli;
  - różnica sum w oknie: {g4(gw['sum_diff_gdal_minus_reference'])} osoby na {n(gw['sum_reference'])}.
- **Naiwne przypisanie środków pikseli** daje w tym samym oknie RMSE {g4(gw['rel_rmse_naive_vs_ref'] * 100)} %, czyli prążki.
  Obraz: `grid250_moire_warszawa.png`.
- **Sumy:** różnica 250 m względem 100 m (obie liczone regułą „środek komórki w wielokącie”) wynosi maks. {pct(maxf, 3)} na FUA
  i {pct(maxc, 2)} na rdzeń. Ta różnica to w całości przypisanie komórek brzegowych, nie utrata ludności.
- **Maska Polski:** `poland_mask_250m_epsg2180.tif`, środek komórki w komórce siatki spisowej.
- **Tabele zamieszkanych komórek:** `cells_<aglomeracja>.parquet`, z flagami FUA, rdzeń, bufor i Polska; to przyszłe
  pochodzenia dla dostępności (§4.6).

### 1.3 Profil gęstości (§4.2)

- **Dane:** GHS-POP 100 m. Pierścienie 1 km są za drobne na siatkę spisową 1 km, a GHSL to dane modelowane.
- **Odległość:** od środka piksela do centrum z `config.yaml`, w EPSG:2180. Pierścienie [k, k+1) km.
- **Gęstość pierścienia:** ludność / pole komórek pierścienia w domenie (lasy i wody wewnątrz domeny wliczone).
  Osobno podajemy pole zamieszkane (komórki z ludnością > 0) w plikach `data/interim/density/*_profile_*.csv`.
- **Wariant (i) „fua”:** tylko komórki o środku w FUA; udział w ludności FUA (GHSL). Pierścienie sięgają do najdalszej
  komórki FUA, więc krzywa kończy się na 100 %. Warszawa i inne duże FUA sięgają dalej niż 40 km: wtedy udział przy
  40 km jest mniejszy od 100 %.
- **Wariant (ii) „free”, bez granic:** wszystkie komórki o środku w Polsce w promieniu r. Udział liczony w ludności do
  40 km; w pliku jest też liczba bezwzględna. Ludność za granicą państwa jest pominięta (dotyczy Szczecina). Przy dużym r
  wchodzą sąsiednie ośrodki.
- **Kontrola spisem:** ta sama krzywa z komórek NSP 1 km (centroid), co 5 km (oraz 2 km), w obu wariantach (tabela 4).
- **Gradient Clarka:**
  - model: ln D = ln D0 − b·r, MNK na pierścieniach [1,2) … [24,25) km wariantu (i), z ludnością > 0 i co najmniej
    1 km² pola w domenie;
  - pierwszy kilometr podany osobno;
  - wynik tylko do tabel i QA (tier `table`/`qa`), nie na grafiki (brief §11).
- **GZM, Trójmiasto, Bydgoszcz–Toruń:** dodatkowy wariant „do najbliższego z N centrów” (centrum + `extra_centres`).
  To **inna miara**: osobne serie `*_nearest`, osobny plik wykresu.

### 1.4 Indeks dyspersji Bertauda ρ (§4.3)

- **Wzór:** ρ = [Σ pᵢ·distᵢ / Σ pᵢ] / (⅔·R), gdzie R = √(A/π), A = pole maski terenu zabudowanego netto.
- **Interpretacja (brief §4.3):** ρ = 1 oznacza walec o **równomiernej** gęstości na kole o polu A. To nie jest optimum.
  Miasta z gęstością malejącą od centrum mają ρ < 1; większe ρ oznacza ludność dalej od centrum niż przy równomiernym
  rozkładzie.
- **Maska, reguła precyzyjna:**
  1. Komórki GHS-BUILT-S 100 m (Mollweide; pole 0,01 km², odwzorowanie równopolowe) z udziałem zabudowy
     (wartość / 10 000 m²) ≥ X, środek komórki w domenie FUA. GHS-SMOD nie jest używany.
  2. **Spójność z rdzeniem:**
     - zarodki: komórki maski w promieniu 1 km od któregokolwiek centrum z `config.yaml` (centrum + `extra_centres`);
       gdyby żadna się nie kwalifikowała, promień rośnie co 1 km do 5 km (użyte promienie w tym przebiegu: {", ".join(n(v) + " m" for v in seeds)});
     - łączność: 8-sąsiedztwo po dylatacji maski dyskiem o promieniu 3 komórek. Do maski wchodzą tylko oryginalne
       komórki ≥ X z klastrów zawierających zarodek. W efekcie **przerwa do ok. 600 m** w zabudowie (rzeka, tory,
       szeroka arteria) nie rozcina miasta.
     - Wybór 600 m: przy 200 m Wisła odcina w Warszawie całą Pragę, a Odra i Dąbie w Szczecinie Prawobrzeże. Już
       przy 600 m dołączają pojedyncze miasteczka połączone pasmem zabudowy (Police, Łańcut), a przy ≥ 1 km wiele
       wsi. Wrażliwość ρ na tę regułę: tabela 7.
  3. **Wody:** brief każe wyłączyć wody, ale osobnej warstwy wód nie używamy. Komórki wodne mają ~0 m² zabudowy, więc
     odpadają przy każdym progu z listy.
  4. **Domena:** FUA. Tabela 7 pokazuje, jaka część klastra wychodzi poza FUA, gdy tę samą regułę puścić na FUA + 15 km.
  5. **Rdzeń:** ta sama maska ograniczona do komórek o środku w rdzeniu.
- **Licznik:** tylko ludność GHS-POP 100 m z komórek maski; odległość od środka komórki do centrum w EPSG:2180.
- **Wartość „brak danych”:** gdy maska obejmuje < 5 % ludności domeny. Przy progu 50 % maska ma kilka km² wokół
  rynku i ρ traci sens; surowa wartość jest w nawiasie w tabelach.
- **Wariant „do najbliższego z N centrów”** (GZM, Trójmiasto, Bydgoszcz–Toruń; inna miara): odległość do najbliższego
  centrum, mianownik ⅔R jak w ρ (dosłownie wg briefu). Pomocniczo podajemy wariant z mianownikiem dla N równych kół
  (⅔·√(A/(Nπ))).

### 1.5 Gini i η (§4.4, tylko QA)

- **Domeny (stałe):** maska z §4.3 przy progu roboczym {int(thr_work * 100)} % oraz koło {D.CIRCLE_KM} km wokół centrum
  (komórki w Polsce). Rozdzielczość 100 m (GHS-POP).
- **Wzory wg Volpati i Barthelemy (2018), arXiv:1804.00855:**
  - Gini: wzór (1) na liczbach ludności komórek, normalizowany przez G_max = (n−1)/n (wzory 2–3);
  - hotspoty: komórki powyżej wartości LouBar, czyli miejsca, w którym styczna do krzywej Lorenza w F = 1 przecina oś;
  - η: wzór (6), średnia odległość między hotspotami / średnia odległość między wszystkimi komórkami domeny.
- **Uproszczenie obliczeniowe:** obie średnie liczymy na stałej próbie losowej (ziarno 0, maks. {D.ETA_SAMPLE} komórek),
  żeby uniknąć ~10¹⁰ par.
- Próg LouBar i rozdzielczość są zapisane przy każdej liczbie (tabela 8, `metrics_density.csv`, kolumna `flag`).

## 2. Wyniki: gęstość ważona populacją (§4.1)

Tabela 1. PWD na siatce spisowej 1 km i gęstość brutto (os./km²; NSP 2021-03-31). Kolumny GHSL 250 m są z innej siatki
i nie porównuje się ich z PWD 1 km.

{t_main}
Wielkości są zgodne z oczekiwaniami. PWD dużych miast na siatce 1 km wynosi kilka tysięcy os./km², od kilku do
kilkunastu razy więcej niż gęstość brutto FUA:

- Warszawa: rdzeń {n(res['warszawa']['core']['census']['pwdens'])}, FUA {n(res['warszawa']['fua']['census']['pwdens'])}
  vs brutto FUA {n(res['warszawa']['fua']['gross_density'])};
- PWD rdzenia > PWD FUA w każdej aglomeracji;
- GZM ma najmniejszą różnicę rdzeń–FUA, co pasuje do konurbacji bez wyraźnego śródmieścia.

Tabela 2. Odporność PWD na definicję pola komórki i przypisania (os./km²).

{t_rob}
PWD z GHSL na tych samych komórkach 1 km jest systematycznie niższe od spisowego (o {ghsl_pwdens_range}), z wyjątkiem Rzeszowa.
GHSL wygładza szczyty gęstości: rozdziela ludność według kubatury zabudowy, także niemieszkalnej (patrz §7.1).

## 3. Wyniki: profil gęstości (§4.2)

Tabela 3. Profil (GHS-POP 2020 100 m).

- r50: promień, w którym mieszka 50 % ludności;
- udział do 10 km: (i) w ludności FUA, (ii) w ludności do 40 km;
- Clark: tylko tabela/QA;
- ostatnie kolumny: maksymalna różnica krzywej skumulowanej GHSL względem NSP 1 km na krokach 2, 5, …, 40 km.

{t_prof}
Tabela 4. Kontrola krzywej skumulowanej (i) spisem: udział ludności FUA w promieniu r, GHSL / NSP (%).

{t_cc}
Krzywe są monotoniczne z konstrukcji (sumy skumulowane nieujemnych liczb). W wariancie (i) każda kończy się na 100,0 %
(sprawdzone w `density_qa`, asercja).

Zgodność GHSL ze spisem w kształcie krzywej jest dobra: różnice do ok. 3–4 pp. Odstają dwa przypadki:

- **Rzeszów, różnica {g4(res['rzeszow']['census_check']['max_abs_diff_pp_fua'])} pp przy 5 km:** GHSL koncentruje ludność
  w centrum Rzeszowa bardziej niż spis (patrz §7.1, rdzeń Rzeszowa +13,5 %);
- **pierwsze 2 km:** krok 2 km jest porównywalny z rozmiarem komórki spisowej, więc różnica tam jest częściowo
  artefaktem przypisania komórek 1 km do pierścienia.

**Rekomendacja wariantu na grafikę: (ii) bez granic, jako liczba osób w promieniu r (oś Y w tysiącach lub milionach),
dla pięciu jednocentrowych aglomeracji fazy 1.** Uzasadnienie:

1. **Wariant (i) zmienia ranking przez rysunek granicy FUA, nie przez formę miasta.** Duża FUA Warszawy (9 296 km²,
   sięga poza 40 km) daje jej najniższy udział do 10 km ({pct(res['warszawa']['share_within']['fua']['10'])} w (i)),
   choć w (ii) jest w środku stawki ({pct(res['warszawa']['share_within']['free']['10'])}). Mała FUA Szczecina działa
   odwrotnie. Brief (§2) każe unikać wyników, które mierzą przebieg granicy.
2. **Wariant (ii) da się sprawdzić spisem** bez żadnej granicy. Różnice z NSP 1 km są tu mniejsze niż w (i).
3. **Udział w (ii) wymaga arbitralnego mianownika** (ludność do 40 km), który w miastach otoczonych gęstą wsią
   (Rzeszów, Kielce: r50 ok. 22 km) mierzy region, a nie miasto. Liczba bezwzględna nie ma tego problemu, a kształt
   krzywej nadal widać.

Jeżeli grafika ma pokazać udział (jak w briefie), proponujemy (ii) z mianownikiem „do 40 km” z adnotacją albo (i)
z wyraźną informacją, że udział zależy od zasięgu FUA. Dane obu wariantów są w `results/charts/profile_cumulative_*.json`.
GZM, Trójmiasto i Bydgoszcz–Toruń idą osobnym panelem (osobny plik), z wariantem „do najbliższego z N centrów”
oznaczonym jako inna miara.

## 4. Wyniki: indeks dyspersji Bertauda ρ (§4.3)

Tabela 5. **ρ (FUA) dla każdego progu z `built_up_threshold_sensitivity`**, pole maski i udział ludności FUA (GHSL)
w masce. To tabela do decyzji o progu (brief §12.4). Próg roboczy: {int(thr_work * 100)} %.

{t_rho}
Tabela 5a. ρ dla rdzenia (ta sama maska ograniczona do rdzenia).

{rho_core}
Tabela 6. Ranking miast jednocentrowych według ρ FUA przy każdym progu i zgodność rankingów.

{t_rank}
{t_corr}
**Jak czytać wartości:**

- **ρ > 1 prawie wszędzie{below1_txt}.** To nie jest błąd liczenia; sprawdzone (sekcja 8). Maska jest
  „netto”: zawiera tylko komórki 100 m z wysokim udziałem powierzchni budynków. W polskich miastach parki, doliny rzek,
  tereny kolejowe i luźna zabudowa blokowa wypadają z maski. Pole A jest więc małe w stosunku do rozpiętości miasta, a
  maska ma kształt gwiazdy (pasma wzdłuż dróg), nie koła. Dla kształtu niekołowego średnia odległość od centrum jest
  większa niż ⅔R nawet przy równomiernej gęstości.
- **Poziom ρ nie jest porównywalny z wartościami Bertauda i Malpezziego (2003)**, którzy liczyli teren zabudowany
  inaczej (z map i zdjęć, z małymi terenami otwartymi). Nie sprawdzaliśmy ich liczb dla polskich miast.
- **Próg zmienia poziom ρ i, powyżej 20 %, także kolejność miast:**
  - 10 %: maska {area_range("0.1")}, {share_range("0.1")} ludności FUA;
  - 20 %: {area_range("0.2")}, {share_range("0.2")};
  - 30 %: {area_range("0.3")}, tylko {share_range("0.3")};
  - 50 %: {area_range("0.5")} i < 5 % ludności, więc ρ to „brak danych”;
  - ranking miast jednocentrowych przy 10 % i 20 % jest zgodny (Spearman {corr.get("10 % vs 20 %", "brak danych")}),
    przy 30 % się rozsypuje (Spearman z 20 %: {corr.get("20 % vs 30 %", "brak danych")}). Maska 30 % to głównie
    śródmieścia i strefy przemysłowe, a nie miejsca, gdzie mieszka większość ludzi.
- **Rekomendacja agenta (do decyzji właściciela):** próg 10 % albo 20 %, nie 30 % ani 50 %. 10 % obejmuje większość
  mieszkańców, więc licznik ρ opiera się na typowym mieszkańcu, a nie na wybranej części. Kolejność przy 10 % i 20 % jest
  w przybliżeniu ta sama, więc wybór między nimi zmienia głównie poziom.
- **Rdzeń:** ρ rdzenia jest zwykle nieco niższe niż ρ FUA. Maska rdzenia obejmuje
  {n(min(core_sh) * 100)}–{n(max(core_sh) * 100)} % jego ludności przy progach 10–20 %.

Tabela 7. Wrażliwość ρ FUA (próg {int(thr_work * 100)} %) na tolerancję luki w regule spójności (w nawiasie: pole maski) oraz
część klastra, która wyszłaby poza FUA przy domenie FUA + 15 km.

{t_gap}
Reguła spójności przesuwa ρ o kilka do kilkudziesięciu procent, a kolejność miast nie jest na nią w pełni odporna.
To druga, obok progu, decyzja metodyczna. Co dołącza między 400 a 600 m (sprawdzone na mapie maski):

- **Szczecin:** Prawobrzeże (część miasta, za Odrą i Dąbiem), ale też miasto Police na północy.
- **Rzeszów:** Łańcut, ok. 17 km na wschód, połączony pasmem zabudowy wzdłuż drogi.
- **Kielce:** kilka wsi.

Żadna pojedyncza wartość nie jest dobra dla wszystkich miast: przy 400 m Wisła w Warszawie jest już „przekroczona”,
ale Prawobrzeże Szczecina jeszcze nie. Przy 600 m dochodzą osobne miasteczka połączone zabudową wzdłuż dróg.
Rekomendacja: 600 m (uzasadnienie w 1.4), z tą wadą opisaną przy wyniku.

Część klastra poza FUA jest mała: do ok. 3 % w GZM i ok. 6 % w Trójmieście, poniżej 2 % gdzie indziej. Domena FUA
obcina więc niewiele, ale nie nic.

Tabela 7a. Wariant „do najbliższego z N centrów” (inna miara; nie porównywać z ρ jednocentrowym).

{t_near}
- **GZM:** ρ jednocentrowe ({g4(rw('gzm')['rho'])} przy 20 %) mierzy przede wszystkim to, że Katowice nie są jedynym
  centrum. Wariant do najbliższego z 9 centrów spada poniżej 1. Na grafiki tylko wariant opisany jako inna miara albo
  wcale.
- **Trójmiasto:** wynik z wyraźnym zastrzeżeniem. Miasto jest liniowe (ok. 35 km wzdłuż brzegu), a koło o polu maski
  wychodzi w morze. ρ = {g4(rw('trojmiasto')['rho'])} przy centrum Gdańsk Główny.
- **Bydgoszcz–Toruń:** ρ ok. 5 to artefakt dwóch ośrodków odległych o ok. 42 km (oba miasta w masce, zarodki przy obu
  centrach). Do tabel tylko wariant N centrów.

## 5. Gini i η (§4.4, tylko QA, nie na grafiki)

Tabela 8. Gini znormalizowany (G/Gmax) i η. Rozdzielczość 100 m; domeny stałe: maska ≥ {int(thr_work * 100)} % oraz
koło {D.CIRCLE_KM} km.

{t_ge}
- Gini w kole jest wyższy niż w masce, bo koło zawiera tereny niezamieszkane. To dokładnie efekt, przed którym brief
  ostrzega przy liczeniu na FUA.
- η w masce: najwyższe dla Bydgoszczy–Torunia (dwa ośrodki) i Trójmiasta, wysokie dla GZM. Odpowiada to
  policentryczności. Wśród miast jednocentrowych najniższe η: {eta_low} (hotspoty skupione); najwyższe: {eta_high}.
- Wartości zależą od progu LouBar i rozdzielczości (zapisane w tabeli), więc służą tylko do opisu w RAPORT.md.

## 6. Kontrola §7.1: GHSL 2020 vs NSP 2021 vs BDL

### 6.1 Sumy krajowe

{t_nat}
- **Siatka NSP to ludność rezydująca.** Jej suma jest równa co do osoby sumie gmin z BDL dla zmiennej „ludność
  rezydująca” NSP 2021. To potwierdza ustalenie z RAPORT §4.1 bezpośrednio z BDL.
- **GHSL 2020 jest skalibrowany powyżej obu definicji:**
  - 38,47 mln w Polsce (komórki 250 m);
  - o ok. 1,1 % ponad ludność wg definicji krajowej (38,04 mln);
  - o 3,9 % ponad ludność rezydującą.
- **Część każdego „GHSL > NSP” to więc różnica poziomu, nie rozkładu.** Do poziomu ludności krajowej dochodzi ok. 1 %
  z kalibracji GHSL. Hipoteza, której nie sprawdzono w dokumentacji JRC: GHSL jest skalibrowany do szacunku ludności
  Polski na 2020 r. sprzed rewizji spisowej (GUS podawał ok. 38,3 mln na 31.12.2020).

### 6.2 Rozkład różnicy na czynniki per FUA i rdzeń

Ten sam obszar, gminy przypisane regułą ≥ 50 % pola (LAU 2021). Rozkład:
GHSL/NSP = (c) GHSL/BDL krajowa × (b) BDL krajowa/BDL rezydująca × (a) BDL rezydująca/siatka.

- **(a) przypisanie:** gminy w całości vs komórki według centroidu;
- **(b) czysty efekt definicji:** ten sam spis, ta sama data;
- **(c) reszta:** model GHSL, data 2020 vs 31.03.2021 i dane wejściowe GHSL.

Zmiennej BDL 72305 (stan 31.12.2020) nie pobrano: zapora GUS zablokowała anonimowe API po ok. 90 zapytaniach
(HTTP 500, „Strona została zablokowana ze względów bezpieczeństwa”).

Tabela 9. Sumy i czynniki.

{t_tot}
Wykres: `summary_control.png`.

**Wyjaśnienie odchyleń > 5 %** (flaga z fazy 0: Wrocław FUA i rdzeń, rdzenie GZM, Bydgoszczy–Torunia, Rzeszowa, Kielc,
Białegostoku):

- **Wrocław (FUA {g4(tt[(tt.agglomeration == 'wroclaw') & (tt.domain == 'fua')].ghsl_to_nsp.iloc[0])}, rdzeń
  {g4(tt[(tt.agglomeration == 'wroclaw') & (tt.domain == 'core')].ghsl_to_nsp.iloc[0])}).**
  - Definicja niczego tu nie wyjaśnia (b ≈ 1,007): Wrocław ma prawie tyle samo mieszkańców wg obu definicji.
  - Cała różnica to (c): GHSL ma o ok. 8 % mniej ludzi niż oficjalna liczba wg definicji krajowej.
  - Ten sam znak, słabiej, mają Kraków, Poznań, Trójmiasto i Warszawa (c = 0,92–0,96). Są to miasta i strefy
    podmiejskie, które najszybciej rosły w latach 2011–2021.
  - Wyjaśnienie prawdopodobne, niesprawdzone w dokumentacji JRC: dane wejściowe GHS-POP dla Polski to liczby gminne z
    wcześniejszego okresu, przeniesione na 2020; nie oddają napływu do dużych miast. Wynik nie jest błędem przypisania
    (a ≈ 1).
- **Rdzenie GZM, Bydgoszczy–Torunia, Kielc, Białegostoku (GHSL/NSP 1,06–1,08).** Dwa składniki:
  - (b) = 1,02–1,04: ludność wg definicji krajowej przewyższa rezydującą. To regiony z emigracją; osoby długo
    przebywające za granicą liczą się w definicji krajowej, nie w rezydującej.
  - (c) = 1,00–1,04: niewielka nadwyżka modelu.
  - Po uwzględnieniu definicji odchylenia mieszczą się w 5 % (poza Rzeszowem).
  - W Bydgoszczy–Toruniu i Szczecinie część różnicy rdzenia to (a) = 1,02. Granica URAU rdzenia i komórki siatki
    przy brzegu nie pokrywają się: komórki o centroidzie tuż za granicą miasta.
- **Rdzeń Rzeszowa (GHSL/NSP 1,135):** (b) 1,038 × (c) 1,077 × (a) 1,015. Nadwyżka modelu jest skupiona w centrum.
  Kilka komórek w śródmieściu i na północnym wschodzie miasta ma w GHSL 2–4 razy więcej ludzi niż w spisie
  (współrzędne w `control_top_cells.csv`). To zgodne z mechanizmem kubatury niemieszkalnej opisanym niżej.
  Zabudowy w tych komórkach nie oglądano. FUA Rzeszowa jako całość się zgadza (0,999), więc model przesuwa ludność
  z okolicy do miasta, a nie ją dodaje.

### 6.3 Porównanie na komórkach 1 km

Tabela 10. Korelacja i indeks niepodobieństwa D = ½ Σ |gᵢ/G − nᵢ/N| (udział ludności, który trzeba by przesunąć, żeby
oba rozkłady były identyczne; niezależny od różnicy poziomu).

{t_cells}
- **Korelacja na komórkach 1 km jest wysoka** (Pearson 0,78–0,94), ale **D wynosi 16–26 %.** Na poziomie
  pojedynczych kilometrów GHSL i spis rozmieszczają różnie co szóstą do co czwartej osoby.
- Ta różnica jest dużo większa niż różnica sum. To mierzy jakość GHSL jako warstwy 250 m i jako pochodzeń dla
  dostępności, a nie sum dla FUA.
- Komórki przycięte granicą państwa praktycznie nie wpływają na D (kolumna `dissimilarity_unclipped` w
  `control_cells.csv`).

Tabela 11. Wybrane komórki o największej różnicy (pełna lista: `control_top_cells.csv`; po 10 bezwzględnych i 10
względnych na aglomerację).

{t_top}
**Prawdopodobne przyczyny** (rozpoznane po współrzędnych; nie weryfikowane w terenie ani na ortofotomapie):

1. **GHSL >> NSP w strefach przemysłowych, portowych i usługowych**, gdzie NSP ma 0 mieszkańców. Przykłady:
   - kombinat ArcelorMittal w Nowej Hucie (do 5 300 osób na komórkę w GHSL);
   - Huta Katowice w Dąbrowie Górniczej;
   - Huta Warszawa na Bielanach i rejon lotniska Okęcie;
   - rafineria w Gdańsku i tereny stoczniowo-portowe nad Martwą Wisłą; port i stocznia w Gdyni;
   - strefy przemysłowe Widzewa i Olechowa w Łodzi;
   - Bielany Wrocławskie (Kobierzyce, centra handlowe i logistyka);
   - parki logistyczne pod Poznaniem (Swarzędz, Kórnik, Komorniki).

   GHS-POP rozdziela ludność według objętości zabudowy, a wielkie hale i zakłady mają dużą objętość.
2. **GHSL >> NSP w ścisłych centrach:**
   - Stare Miasto w Krakowie (14 946 vs 5 662);
   - Rynek we Wrocławiu;
   - Śródmieście Warszawy;
   - Stary Rynek w Poznaniu.

   Biura, handel, hotele i urzędy to kubatura bez mieszkańców.
3. **GHSL << NSP w wielkich osiedlach blokowych:**
   - Ursynów i osiedla na północy Warszawy (52,32° N, 20,95° E); Legionowo, Ząbki, Piaseczno;
   - Bieńczyce i Mistrzejowice (Nowa Huta) w Krakowie;
   - Zaspa i Przymorze w Gdańsku;
   - Retkinia i Widzew Wschód w Łodzi;
   - Winogrady i Piątkowo w Poznaniu;
   - Tysiąclecie w Katowicach;
   - osiedla Tychów i Dąbrowy Górniczej.

   GHSL daje tam zwykle 35–60 % ludności spisowej. Model kubaturowy nie oddaje gęstości zaludnienia wysokich bloków.
   W Ząbkach i Piasecznie dochodzi prawdopodobnie zabudowa nowsza niż dane wejściowe GHSL (niesprawdzone).
4. **Koszary, akademiki i więzienia nie pojawiły się wśród największych różnic** w aglomeracjach fazy 1. Nie
   szukaliśmy ich celowo.
5. **Komórki przycięte brzegiem lub granicą:** pojedyncze przypadki na wybrzeżu Gdańska i w Szczecinie. GHSL liczy
   tam cały kwadrat.

**Wniosek dla projektu:**

- PWD i krzywe skumulowane liczymy na spisie, jak przewiduje brief.
- GHSL jest wystarczający do profilu 1 km i krzywej skumulowanej: różnice w krzywej do 3–4 pp poza Rzeszowem.
- Na poziomie komórek GHSL przesuwa ludność z blokowisk do centrów i stref przemysłowych. To trzeba opisać przy warstwie
  250 m i przy dostępności, gdzie GHSL wyznacza pochodzenia (§4.6).
- Warstwa 6c (BDOT10k, brief §13) jest właściwym lekarstwem.

## 7. Ograniczenia

- **GHS-POP to model.** Wszystkie wyniki 100 m i 250 m (profile, ρ, Gini, η, PWD 250 m) dziedziczą błędy opisane w §6:
  ludność w strefach przemysłowych, niedoszacowanie blokowisk, poziom ok. 1 % powyżej definicji krajowej.
- **ρ zależy od dwóch decyzji metodycznych:** progu (tabela 5) i reguły spójności (tabela 7). Jego poziom nie jest
  porównywalny z literaturą.
- **Daty się nie pokrywają:** GHSL to epoka 2020, NSP stan 31.03.2021, granice 2021. Migracje po 2021 r. i nowe
  osiedla nie są uwzględnione.
- **Rdzenie** to granice URAU (miasto). Dla GZM to 13 miast, dla Trójmiasta trzy.
- **Wariant (ii) profilu** pomija ludność za granicą państwa (Szczecin).
- **Gini i η liczone na próbie** maks. {D.ETA_SAMPLE} komórek (stałe ziarno). Błąd próbkowania średniej odległości
  szacujemy na < 1 %, ale tego nie mierzono.
- **Centra punktowe** z `config.yaml`. ρ i profil są wrażliwe na położenie centrum o kilkaset metrów; tego nie badano.

## 8. Co zaskoczyło i co wyszło przy sprawdzeniu

1. **Prążki w siatce 250 m.**
   - Pierwsza wersja (domyślne ustawienia GDAL) miała względem dokładnej referencji dipole ±100 osób na komórkę.
   - Kontrola: podział pikseli na 10 × 10 i 20 × 20 podpikseli (te dwie referencje różnią się między sobą o RMSE
     1,7 osoby).
   - Przyczyna: przybliżony transformator współrzędnych GDAL. Po `tolerance=0` różnica spadła do poziomu szumu
     referencji. **Poprawione.**
2. **ρ > 1 wszędzie.** Kontrole:
   - mapa maski Warszawy (przy luce 200 m klaster kończył się na Wiśle, stąd zmiana reguły na 600 m);
   - wrażliwość na lukę 0–1 400 m: ρ Warszawy stabilne około 1,4;
   - rozkład wartości GHS-BUILT-S (dane w m² na komórkę 0–10 000, zgodnie z dokumentacją; przy progu 20 % w FUA
     Warszawy jest 582 km² zabudowy z 76 % ludności).

   Wynik zostaje: to cecha maski netto (patrz §4), nie błąd. **Zostaje z zastrzeżeniem.**
3. **Maska przy progu 50 % jest prawie pusta** (0–2 km²). Komórka 100 m z połową powierzchni pod dachami to w
   Polsce rzadkość poza zwartymi kwartałami śródmieść. ρ = „brak danych”. **Zostaje.**
4. **Szczecin ma najwyższe PWD FUA (6 506), wyższe niż Warszawa (5 910).** Kontrole:
   - najgęstsza komórka spisowa w kraju leży w śródmieściu Szczecina (14,539° E, 53,429° N): 26 043 osoby na km²;
   - sąsiednie komórki mają do 11 758 osób, GHSL w tej samej komórce 22 411. Oba źródła się zgadzają, więc to nie
     artefakt spisu (np. adresy zbiorcze);
   - mała FUA (1 362 km², 75 % ludności w rdzeniu) nie rozcieńcza wyniku przedmieściami tak jak w Warszawie.

   **Zostaje.** Pokazuje też, że PWD FUA mierzy częściowo udział rdzenia w FUA.
5. **GHSL ma 38,5 mln mieszkańców Polski**, więcej niż obie definicje GUS. Kontrola: dwa niezależne rachunki
   (komórki 250 m o środku w Polsce; komórki spisowe 1 km bez przyciętych) dają 38,47 i 38,37 mln. Różnica 0,26 %
   to komórki brzegowe. **Zostaje jako fakt o źródle.**
6. **Wrocław GHSL −7 %** nie wynika z definicji ludności: BDL pokazuje b ≈ 1,007. To różnica modelu (patrz 6.2).
7. **GHSL ma ludność w kombinatach i portach** (5 300 osób w komórce huty w Nowej Hucie). Kontrola: NSP = 0 w tych
   komórkach. **Zostaje jako fakt o źródle**, opisany przy warstwie 250 m.

## 9. Pliki

- Wyniki:
  - `results/metrics/metrics_density.csv` i `.json` (scalone z innymi krokami w `metrics.csv`): format długi; `tier`: `main` (na grafikę), `table`, `qa`;
  - `results/charts/pwdens.json`;
  - `results/charts/profile_cumulative_monocentric.json`, `profile_cumulative_polycentric.json`.
- QA:
  - `results/qa/density/{{pwdens,profile,mask,gini,control}}_<aglomeracja>.png`;
  - `summary_*.png`, `grid250_moire_warszawa.png`;
  - `control_*.csv`.
- Pośrednie: `data/interim/grid250/` (siatka 250 m, maska Polski, `cells_*.parquet`, `qa.json`),
  `data/interim/density/`.
- BDL: `data/raw/bdl/*.json`, w manifeście jako `bdl_nsp2021_resident_gmina`, `bdl_nsp2021_national_gmina`.
- Polecenia (w tej kolejności): `python -m pipeline.grid250`, `python -m pipeline.density`,
  `python -m pipeline.density_control`, `python -m pipeline.density_qa`.
"""
    (QA / "density.md").write_text(txt, encoding="utf-8", newline="\n")


def checks(res: dict) -> None:
    for k, r in res.items():
        for key in ("fua", "core", "free"):
            d = profile(k, key)
            assert (np.diff(d.cum_pop.values) >= -1e-6).all(), (k, key, "cumulative not monotone")
        last = profile(k, "fua").cum_share.iloc[-1]
        assert abs(last - 1) < 1e-6, (k, "variant (i) does not reach 100 %", last)
        assert r["fua"]["census"]["pwdens"] > r["fua"]["gross_density"], (k, "PWD <= gross")
        assert r["core"]["census"]["pwdens"] > r["fua"]["census"]["pwdens"], (k, "core PWD <= FUA PWD")


def main() -> None:
    t0 = time.time()
    QA.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    thr_list = sorted({float(t) for t in cfg["built_up_threshold_sensitivity"]} | {float(cfg["built_up_threshold"])})
    thr_work = float(cfg["built_up_threshold"])
    res, ctl, g250 = load()
    checks(res)
    for agg in sorted(res):
        a = load_agglomeration(agg)
        r = res[agg]
        plot_pwdens(agg, r, a)
        plot_profile(agg, r)
        plot_mask(agg, r, a, thr_work)
        plot_gini(agg, r)
        plot_control(agg, r, a)
        print(agg, flush=True)
    summary_plots(res, ctl, thr_list)
    write_md(res, ctl, g250, thr_list, thr_work)
    write_meta(QA, "density_qa (+ grid250, density_control plots and tables)",
               inputs=D.INPUT_IDS + ["bdl_nsp2021_resident_gmina", "bdl_nsp2021_national_gmina"], started=t0,
               extra={"working_threshold": thr_work, "thresholds": thr_list,
                      "population_dates": {"census": D.POP_DATE_NSP, "ghsl": D.POP_DATE_GHSL}})


if __name__ == "__main__":
    main()
