"""QA for pipeline.frequent: tables, checks, maps, histograms, frequent.md (Polish) and _meta files.

Called from ``pipeline.frequent.main``; not a separate step.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline import frequent as F
from pipeline.boundaries import load_agglomeration
from pipeline.common import RESULTS, round_sig, sig, write_json, write_meta

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

QA = F.QA
TO2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
NAMES = {a: F.CFG["agglomerations"][a]["name"] for a in F.AGGS}
SCALED, RAW = "ghsl_census_scaled", "ghsl_raw"

# known places for the sanity check: (agg, label, lon, lat, expectation)
PLACES = [
    ("warszawa", "Marszałkowska / Świętokrzyska", 21.0090, 52.2350, "≤ 5"),
    ("warszawa", "Marszałkowska / pl. Konstytucji", 21.0155, 52.2223, "≤ 5"),
    ("wroclaw", "Rynek", 17.0320, 51.1100, "≤ 5"),
    ("krakow", "Rynek Główny", 19.9373, 50.0617, "≤ 5"),
    ("poznan", "Stary Rynek", 16.9342, 52.4083, "≤ 5"),
    ("lodz", "Piotrkowska Centrum", 19.4573, 51.7594, "≤ 5"),
    ("trojmiasto", "Gdańsk Główny", 18.6440, 54.3556, "≤ 5"),
    ("gzm", "Katowice Rynek", 19.0216, 50.2594, "≤ 5"),
]


# ------------------------------------------------------------------ helpers
def sh(r, key, grid, sel):
    c = r["cells"]
    p = c[f"pop_{grid}"].to_numpy()
    if p[sel].sum() <= 0:
        return np.nan
    return float((p[sel] * r["frac"][key][sel]).sum() / p[sel].sum() * 100)


def sel_of(r, dom, v):
    return F.domain_sel(r["cells"], dom, v)


def f1(x, nd=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    return f"{x:.{nd}f}".replace(".", ",")


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def csv(df: pd.DataFrame, name: str) -> None:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: None if pd.isna(v) else sig(v))
    d.to_csv(QA / name, index=False, encoding="utf-8", lineterminator="\n")


# ------------------------------------------------------------------ tables
def headline(results) -> pd.DataFrame:
    v, g, k = F.REC["feed_variant"], F.REC["population_grid"], F.REC["agg"]
    rows = []
    for r in results:
        for dom in ("covered", "core", "fua"):
            cov = F.coverage(r, g, "core" if dom == "core" else "fua", v)
            row = {"aglomeracja": NAMES[r["agg"]], "domena": F.DOM_LABEL[dom]}
            for T in F.THRESH:
                row[f"≤{T} min"] = sh(r, (v, k, T, "net"), g, sel_of(r, dom, v))
            row["pokrycie %"] = cov * 100
            row["flaga"] = "niepełne" if (dom != "covered" and cov < F.COV_MIN) else ""
            rows.append(row)
    return pd.DataFrame(rows)


def effects(results) -> pd.DataFrame:
    """Long table: every comparison, every threshold, domains covered/core/fua."""
    v0, g0, k0 = F.REC["feed_variant"], F.REC["population_grid"], F.REC["agg"]
    rows = []
    for r in results:
        for dom in ("covered", "core", "fua"):
            s0 = sel_of(r, dom, v0)
            for T in F.THRESH:
                base = sh(r, (v0, k0, T, "net"), g0, s0)
                comp = {
                    "siatka: GHSL surowy": sh(r, (v0, k0, T, "net"), RAW, s0),
                    "feedy: oficjalne (ta sama domena)": sh(r, ("official", k0, T, "net"), g0, s0),
                    "feedy: oficjalne (własna maska)": sh(r, ("official", k0, T, "net"), g0, sel_of(r, dom, "official")),
                    "agregacja (i): wszystkie linie": sh(r, (v0, "all", T, "net"), g0, s0),
                    "agregacja: jedna linia": sh(r, (v0, "line", T, "net"), g0, s0),
                    "bez wymogu dwóch kierunków": sh(r, (v0, "nodir", T, "net"), g0, s0),
                    "bez reguły partnera": sh(r, (v0, "seg_nopair", T, "net"), g0, s0),
                    "odległość euklidesowa": sh(r, (v0, k0, T, "euc"), g0, s0),
                    "komórka = środek": float((r["cells"][f"pop_{g0}"].to_numpy()[s0] *
                                               r["cent"][(v0, k0, T, "net")][s0]).sum()
                                              / r["cells"][f"pop_{g0}"].to_numpy()[s0].sum() * 100),
                }
                for name, val in comp.items():
                    rows.append({"agglomeration": r["agg"], "domain": dom, "T_min": T, "comparison": name,
                                 "recommended_pct": base, "variant_pct": val, "delta_pp": val - base})
    return pd.DataFrame(rows)


def itdp_table(results) -> pd.DataFrame:
    v, g = F.REC["feed_variant"], F.REC["population_grid"]
    rows = []
    for r in results:
        for dom in ("core", "covered"):
            s0 = sel_of(r, dom, v)
            rows.append({
                "aglomeracja": NAMES[r["agg"]], "domena": F.DOM_LABEL[dom],
                "nasza (ii) sieć": f1(sh(r, (v, "seg", 10, "net"), g, s0)),
                "nasza (i) sieć": f1(sh(r, (v, "all", 10, "net"), g, s0)),
                "nasza bez kierunków": f1(sh(r, (v, "nodir", 10, "net"), g, s0)),
                "nasza (ii) prosta": f1(sh(r, (v, "seg", 10, "euc"), g, s0)),
                "styl ITDP sieć": f1(sh(r, (v, "itdp", 10, "net"), g, s0)),
                "styl ITDP prosta": f1(sh(r, (v, "itdp", 10, "euc"), g, s0)),
            })
    return pd.DataFrame(rows)


def rail_table(results) -> pd.DataFrame:
    v, g = F.REC["feed_variant"], F.REC["population_grid"]
    rows = []
    for r in results:
        for dom in ("covered", "core", "fua"):
            s0 = sel_of(r, dom, v)
            a10 = sh(r, (v, "rail>10", 0, "net"), g, s0)
            a4 = sh(r, (v, "rail4-10", 0, "net"), g, s0)
            a0 = sh(r, (v, "rail<4", 0, "net"), g, s0)
            rows.append({"aglomeracja": NAMES[r["agg"]], "domena": F.DOM_LABEL[dom], "> 10/h": f1(a10),
                         "4–10/h": f1(a4 - a10), "< 4/h": f1(a0 - a4), "≥ 4/h razem": f1(a4),
                         "brak stacji w 1 km": f1(100 - a0),
                         "≥ 4/h, prosta 1 km": f1(sh(r, (v, "rail4-10", 0, "euc"), g, s0)),
                         "tylko szynowe (ii) ≤ 10 min, 500 m": f1(sh(r, (v, "rb_seg", 10, "net"), g, s0))})
    return pd.DataFrame(rows)


def mask_table(results) -> pd.DataFrame:
    rows = []
    for r in results:
        c = r["cells"]
        for v in F.FEEDV:
            for grid in (SCALED, RAW):
                p = c[f"pop_{grid}"].to_numpy()
                core = c.in_core.to_numpy()
                row = {"aglomeracja": NAMES[r["agg"]], "feedy": v, "siatka": "przeskal." if grid == SCALED else "surowy",
                       "FUA w masce %": p[c[f"in_mask_{v}"]].sum() / p.sum() * 100,
                       "rdzeń w masce %": p[core & c[f"in_mask_{v}"]].sum() / p[core].sum() * 100,
                       "bez przyst. OSM w 1 km %": p[c.no_osm_stop_1km].sum() / p.sum() * 100}
                for t in F.MASK_SENSITIVITY:
                    row[f"próg {t:g}"] = p[r["mask_sens"][v][str(t)]].sum() / p.sum() * 100
                row["gminy ≥ 0,85"] = p[r["mask_sens"][v]["gmina_0.85"]].sum() / p.sum() * 100
                rows.append(row)
    return pd.DataFrame(rows)


def sanity(results) -> pd.DataFrame:
    by = {r["agg"]: r for r in results}
    rows = []
    v = F.REC["feed_variant"]
    for agg, label, lon, lat, exp in PLACES:
        r = by[agg]
        x, y = TO2180.transform(lon, lat)
        c = r["cells"]
        i = int(np.argmin(np.hypot(c.x - x, c.y - y)))
        cls = F.best_class(r, v)[i]
        fr = {T: r["frac"][(v, F.REC["agg"], T, "net")][i] for T in F.THRESH}
        hw = r["cl_tables"][(v, "main")].merge(r["clusters"][["cl", "x", "y", "name"]], on="cl")
        d = np.hypot(hw.x - x, hw.y - y)
        near = hw[(d <= 600) & (hw.n > 0)].sort_values("h_seg").head(1)
        rows.append({"aglomeracja": NAMES[agg], "miejsce": label, "oczekiwane": exp, "klasa komórki": cls,
                     "udział punktów ≤5 min": f1(fr[5] * 100, 0) + " %",
                     "najlepszy zespół ≤ 600 m": "" if near.empty else
                     f"{near.name.iloc[0]} (ii) {f1(near.h_seg.iloc[0])} min, (i) {f1(near.h_all.iloc[0])} min",
                     "wynik": "OK" if cls == "5" else "SPRAWDZIĆ"})
    # villages: clusters with 1-6 departures in the whole day, no frequent (<= 30 min) cluster within 1 km
    for r in results:
        agg = r["agg"]
        vv = F.visits(agg, v)
        dday = vv[(~vv.is_last) & (vv.cl >= 0)].groupby("cl").size()
        hw = r["cl_tables"][(v, "main")]
        cl = r["clusters"].set_index("cl")
        fua = load_agglomeration(agg)["fua"]
        import shapely
        cand = dday[(dday >= 1) & (dday <= 6)].index
        freq = hw.cl[hw.h_seg <= 30]
        fx = cl.loc[freq, ["x", "y"]].to_numpy()
        from scipy.spatial import cKDTree
        tf = cKDTree(fx)
        c = r["cells"]
        picks = []
        for cid in cand:
            px, py = cl.at[cid, "x"], cl.at[cid, "y"]
            if not shapely.contains_xy(fua, px, py):
                continue
            if tf.query([px, py])[0] < 1500:
                continue
            i = int(np.argmin(np.hypot(c.x - px, c.y - py)))
            if np.hypot(c.x[i] - px, c.y[i] - py) > 200:
                continue
            picks.append((c[f"pop_{SCALED}"].iloc[i], cid, i))
        picks.sort(reverse=True)
        for _, cid, i in picks[:2]:
            cls = F.best_class(r, v)[i]
            rows.append({"aglomeracja": NAMES[agg], "miejsce": f"{cl.at[cid, 'name']} (rzadki przystanek, {int(dday[cid])} odj./dobę, ≥ 1,5 km od częstego)",
                         "oczekiwane": "> 30 lub brak danych", "klasa komórki": cls,
                         "udział punktów ≤5 min": "–", "najlepszy zespół ≤ 600 m": "",
                         "wynik": "OK" if cls in (">30", None) else "SPRAWDZIĆ"})
    return pd.DataFrame(rows)


def top_clusters(results) -> pd.DataFrame:
    rows = []
    v = F.REC["feed_variant"]
    for r in results:
        hw = r["cl_tables"][(v, "main")].merge(r["clusters"][["cl", "cluster_id", "name", "n_stops", "x", "y"]], on="cl")
        rd = r["cl_tables"][(v, "rail")]
        hw = hw.merge(rd[["cl", "dph"]], on="cl")
        vv = F.visits(r["agg"], v)
        D = F.departures(vv, F.WIN, None, False)
        modes = D.groupby("cl").route_class.agg(lambda s: ";".join(sorted(set(s))))
        feeds = D.groupby("cl").feed.agg(lambda s: ";".join(sorted(set(s))))
        # possible double counting: same line, same next cluster, same minute
        k = D.assign(m=(D.dep // 60).astype(int))
        dup = k.duplicated(["cl", "line", "next_key", "m"]).groupby(k.cl).mean()
        top = hw.sort_values(["n", "cl"], ascending=[False, True]).head(10)
        for t in top.itertuples():
            rows.append({"agglomeration": r["agg"], "cluster_id": t.cluster_id, "name": t.name, "n_stops": t.n_stops,
                         "departures_06_20": int(t.n), "departures_per_h": t.n / (F.WIN_MIN / 60),
                         "nA": int(t.nA), "nB": int(t.nB), "h_all_min": t.h_all, "h_seg_min": t.h_seg,
                         "h_line_min": t.h_line, "rail_dph": t.dph, "dir_status": t.dir_status,
                         "same_minute_dup_share": float(dup.get(t.cl, 0.0)),
                         "modes": modes.get(t.cl, ""), "feeds": feeds.get(t.cl, "")})
    return pd.DataFrame(rows)


def dir_counts(results) -> pd.DataFrame:
    rows = []
    for r in results:
        for v in F.FEEDV:
            hw = r["cl_tables"][(v, "main")]
            vc = hw.dir_status.value_counts()
            D = F.departures(F.visits(r["agg"], v), F.WIN, None, False)
            k = D.assign(m=(D.dep // 60).astype(int))
            dup = float(k.duplicated(["cl", "line", "next_key", "m"]).mean() * 100)
            rows.append({"aglomeracja": NAMES[r["agg"]], "feedy": v, "zespoły z odjazdami": int((hw.n > 0).sum()),
                         **{k_: int(vc.get(k_, 0)) for k_ in ("two_way", "paired", "terminal", "one_way")},
                         "odjazdy 06–20": int(len(D)), "dubel linia+odcinek+minuta %": f1(dup, 2)})
    return pd.DataFrame(rows)


def snap_table(results) -> pd.DataFrame:
    rows = []
    for r in results:
        s = r["snap"]
        nc = r.get("nocoord", {}).get("all", {})
        rows.append({"aglomeracja": NAMES[r["agg"]],
                     "słupki bez współrzędnych (pominięte)": ", ".join(nc.get("stops", [])) or "0",
                     "ich odjazdy 06–20": nc.get("departures_in_window", 0),
                     "przystanki w FUA": s["stops_in_fua"],
                     "nieprzyciągnięte w FUA": s["stops_in_fua_unsnapped"],
                     "punkty próbkowe": s["points_total"], "punkty nieprzyciągnięte": s["points_unsnapped"],
                     "ludność w nieprzyciągniętych punktach %": f1(100 * s["pop_share_unsnapped_points_scaled"], 2),
                     "mediana dociągnięcia punktu m": f1(s["point_snap_median_m"], 0),
                     "p95 dociągnięcia punktu m": f1(s["point_snap_p95_m"], 0),
                     "węzły grafu": r["router_nodes"]})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ plots
CLS = ["5", "10", "15", "20", "30", ">30"]
COLS = ["#0b2a6f", "#1d4ed8", "#4f7be8", "#86a6f0", "#c3d3f7", "#ece9e2"]


def plot_map(r) -> None:
    agg = r["agg"]
    v = F.REC["feed_variant"]
    c = r["cells"]
    a = load_agglomeration(agg)
    x0, y0, x1, y1 = a["fua"].bounds
    nx_, ny_ = int(np.ceil((x1 - x0) / F.CELL)) + 2, int(np.ceil((y1 - y0) / F.CELL)) + 2
    ci = ((c.x - x0) // F.CELL).astype(int).to_numpy(); ri = ((y1 - c.y) // F.CELL).astype(int).to_numpy()
    cls = F.best_class(r, v)
    arr = np.full((ny_, nx_), np.nan)
    code = np.array([CLS.index(k) if k is not None else -1 for k in cls])
    arr[ri[code >= 0], ci[code >= 0]] = code[code >= 0]
    out = np.zeros((ny_, nx_))
    out[ri[code < 0], ci[code < 0]] = 1
    fig, ax = plt.subplots(figsize=(10, 10 * (y1 - y0) / (x1 - x0) + 0.8))
    ext = (x0, x0 + nx_ * F.CELL, y1 - ny_ * F.CELL, y1)
    cmap = ListedColormap(COLS)
    ax.imshow(arr, cmap=cmap, norm=BoundaryNorm(np.arange(-0.5, 6.5), cmap.N), extent=ext, interpolation="nearest")
    gray = np.where(out > 0, 1.0, np.nan)
    ax.imshow(gray, cmap=ListedColormap(["#b0b0b0"]), extent=ext, interpolation="nearest", alpha=0.8)
    xs = np.linspace(ext[0], ext[1], nx_); ys = np.linspace(ext[3], ext[2], ny_)
    ax.contourf(xs, ys, out, levels=[0.5, 1.5], colors="none", hatches=["////"])
    for geom, col, lw in ((a["fua"], "#333333", 0.8), (a["core"], "#c2410c", 1.0)):
        gs_ = getattr(geom, "geoms", [geom])
        for g in gs_:
            xx, yy = g.exterior.xy
            ax.plot(xx, yy, color=col, lw=lw)
    from matplotlib.patches import Patch
    hand = [Patch(color=COLS[i], label=f"≤ {k} min" if k != ">30" else "> 30 min / brak") for i, k in enumerate(CLS)]
    hand.append(Patch(facecolor="#b0b0b0", hatch="////", label="poza maską: brak danych"))
    ax.legend(handles=hand, loc="lower left", fontsize=8, framealpha=0.9)
    ax.set_xticks([]); ax.set_yticks([])
    hl = [sh(r, (v, F.REC["agg"], T, "net"), F.REC["population_grid"], sel_of(r, "covered", v)) for T in F.THRESH]
    ax.set_title(f"{NAMES[agg]}: najlepsza klasa odstępu w zasięgu 500 m pieszo (wariant (ii), feedy: {v}, "
                 f"środa {F.DAY}, 06–20)\nobszar pokryty: " + ", ".join(f"≤{T}: {f1(x)} %" for T, x in zip(F.THRESH, hl))
                 + f"; pokrycie FUA {f1(100 * F.coverage(r, F.REC['population_grid'], 'fua', v))} %. Szkic QA, nie grafika.",
                 fontsize=9)
    fig.savefig(QA / f"map_{agg}.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def plot_hist(results) -> None:
    v = F.REC["feed_variant"]
    fig, axs = plt.subplots(2, 4, figsize=(18, 8))
    bins = np.logspace(np.log10(1), np.log10(840), 40)
    for ax, r in zip(axs.ravel(), results):
        hw = r["cl_tables"][(v, "main")]
        hw = hw[hw.n > 0]
        for k, col, lab in (("all", "#86a6f0", "(i) wszystkie linie"), ("seg", "#1d4ed8", "(ii) odcinek"),
                            ("nodir", "#c2410c", "bez kierunków")):
            h = hw[f"h_{k}"].replace(np.inf, 900).clip(upper=840)
            ax.hist(h, bins=bins, histtype="step", color=col, lw=1.4, label=lab)
        for T in F.THRESH:
            ax.axvline(T, color="#999999", lw=0.6, ls=":")
        ax.set_xscale("log")
        ax.set_title(f"{NAMES[r['agg']]}: zespoły przystanków (n = {len(hw)})", fontsize=9)
        ax.set_xlabel("średni odstęp 06–20, min (oba kierunki; 840 = jeden odjazd / brak drugiego kierunku)", fontsize=7)
    axs.ravel()[0].legend(fontsize=8)
    ax = axs.ravel()[-1]
    for r in results:
        y = [sh(r, (v, F.REC["agg"], T, "net"), F.REC["population_grid"], sel_of(r, "covered", v)) for T in F.THRESH]
        ax.plot(F.THRESH, y, marker="o", label=NAMES[r["agg"]])
    ax.set_xticks(F.THRESH); ax.set_ylim(0, 100); ax.legend(fontsize=7)
    ax.set_title("Krzywa (obszar pokryty, wariant zalecany)", fontsize=9)
    ax.set_xlabel("próg odstępu T, min"); ax.set_ylabel("% ludności")
    fig.suptitle(f"Rozkład średnich odstępów na zespołach przystanków, środa {F.DAY}, feedy: {v}. Szkic QA.", fontsize=10)
    fig.tight_layout()
    fig.savefig(QA / "headway_histograms.png", dpi=100)
    plt.close(fig)


# ------------------------------------------------------------------ report
def write_qa(results, rows, sizes) -> None:
    QA.mkdir(parents=True, exist_ok=True)
    hl = headline(results)
    eff = effects(results)
    it = itdp_table(results)
    rt = rail_table(results)
    mt = mask_table(results)
    sn = sanity(results)
    tc = top_clusters(results)
    dc = dir_counts(results)
    st = snap_table(results)
    csv(eff, "effects.csv"); csv(tc, "top10_clusters.csv"); csv(mt, "mask_coverage.csv")
    csv(sn.astype(str), "sanity_checks.csv")
    for r in results:
        plot_map(r)
    plot_hist(results)
    from pipeline.frequent_md import write_md
    write_md(results, {"headline": hl, "effects": eff, "itdp": it, "rail": rt, "mask": mt, "sanity": sn,
                       "top": tc, "dirs": dc, "snap": st}, sizes)
    # _meta files (shared folders get _meta_frequent.json so that other steps' _meta.json stay intact)
    inputs = ["osm_poland_pbf", "nsp2021_grid_1km_shp", "ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20",
              "ghs_built_s_2020_R3_C20", "ghs_built_s_2020_R4_C20", "urau_2021_100k_all", "lau_2021_01m"]
    extra = {"timetable_date": F.DAY, "window": F.CFG["frequency_window"], "recommended": F.REC,
             "proposed_config": proposed_config()}
    write_meta(QA, "frequent_qa", inputs=inputs, extra={**extra, "outputs": sorted(p.name for p in QA.iterdir()
                                                                                    if p.name != "_meta.json")})
    write_meta(F.LAYERS, "frequent_layers", inputs=inputs, extra={**extra, "files": {
        "frequent_cells.parquet": {"crs": "EPSG:4326", "geometry": "centre point of a 250 m EPSG:2180 cell; cell_id = "
                                   "E<x0>N<y0> lower-left corner in EPSG:2180, square 250 m",
                                   "rows": "populated cells (either grid) with centre in FUA",
                                   "headway_class": "smallest T with >= 50 % of the 3x3 sample points within 500 m walk "
                                                    "of a cluster with headway <= T (aggregation (ii)); '>30'; null = "
                                                    "outside the GTFS coverage mask (no data)"},
        "frequent_stop_clusters.parquet": {"crs": "EPSG:4326", "rows": "stop clusters with departures 06-20"},
        "gtfs_coverage_mask.parquet": {"crs": "EPSG:4326", "rows": "dissolved 250 m cells with centre in FUA per "
                                       "agglomeration x feed variant x status"},
        "sizes_mb": sizes}})
    tmp = Path(tempfile.mkdtemp())
    for folder in (F.METRICS, F.CHARTS):
        write_meta(tmp, "frequent", inputs=inputs, extra={**extra, "outputs":
                   ["metrics_frequent.csv", "metrics_frequent.json"] if folder == F.METRICS else
                   ["frequent_curve.json", "frequent_rail.json"]})
        shutil.copyfile(tmp / "_meta.json", folder / "_meta_frequent.json")
    shutil.rmtree(tmp, ignore_errors=True)


def proposed_config() -> dict:
    return {"frequent": {"pair_radius_m": F.PAIR_RADIUS_M, "terminal_share": F.TERMINAL_SHARE,
                         "stop_max_snap_m": F.STOP_MAX_SNAP_M, "point_max_snap_m": F.PT_MAX_SNAP_M,
                         "cell_sample_points": F.SAMPLE_N * F.SAMPLE_N, "itdp_window": {"start": "07:00", "end": "21:00"},
                         "aggregation": F.REC["agg"], "recommended_feed_variant": F.REC["feed_variant"]},
            "coverage_mask": {"unit": "cell250", "radius_m": F.MASK_RADIUS_M, "min_stop_share": F.MASK_MIN_STOP_SHARE,
                              "no_stop_cells": "in_mask"},
            "walk_network": {"buffer_m": 3000, "min_component_m": 2000}}
