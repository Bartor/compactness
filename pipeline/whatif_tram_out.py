"""Results of the Wrocław tram what-if (pipeline.whatif_tram): control check, scenario table, cell layer, maps, metrics.

    python -m pipeline.whatif_tram aggregate

Outputs: results/metrics/metrics_whatif.csv/.json (+ _meta_whatif.json), results/layers/whatif_wroclaw_cells.parquet,
results/qa/whatif/ (whatif.md, CSV tables, PNG sketches, _meta.json).  Production files are read only.

Per cell and scenario: transport performance = 100 x reachable / proximity (production definitions,
pipeline.access_aggregate); change against S0 in points.  City values: population-weighted mean of cell ratios
("średnia stosunków") and ratio of population-weighted sums ("stosunek średnich", headline since 2026-11-24), for the
core (city proper), the covered area (cells inside the phase-2 GTFS mask) and the FUA; urban centre as in
pipeline.access_uc (origins, destinations and proximity inside the Eurostat 2021 urban centre).
"""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
import time

import numpy as np
import pandas as pd

from pipeline import access_aggregate as AG
from pipeline import access_inputs as AI
from pipeline import whatif_tram as W
from pipeline.common import RESULTS, sig, write_json, write_meta

AGG = W.AGG
STEP = "whatif_tram"
METRICS = RESULTS / "metrics"
LAYERS = RESULTS / "layers"
QA = W.QA
SCENS = [s for s in W.SCENARIOS if s != "S0"]
MAIN = "S2"
CUTS = (30, 45)
NAMES = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
         "trojmiasto": "Trójmiasto", "gzm": "GZM"}
DOM_PL = {"core": "rdzeń", "covered": "obszar pokryty", "fua": "FUA", "urban_centre": "urban centre"}
GRID = "ghsl_census_scaled"
FIELDS = AG.FIELDS
DIST_BANDS = [0, 2, 4, 6, 8, 10, 15, 1e9]
DENS_BANDS = [0, 1000, 2500, 5000, 10000, 1e9]          # residents per km2 of the 250 m cell
TRAM_BANDS = [0, 500, 1000, 2000, 5000, 1e9]            # m from the nearest tram stop


def f1(x, nd=1) -> str:
    return "–" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}".replace(".", ",")


def fint(x) -> str:
    return "–" if x is None else f"{int(round(x)):,}".replace(",", " ")


# ------------------------------------------------------------------ data
def base() -> pd.DataFrame:
    b = AG.base_frame(AGG)
    c = AI.centres(AGG)[0]
    b["dist_centre_km"] = np.hypot(b["x"] - c["x"], b["y"] - c["y"]) / 1000
    b["density"] = b["w_census"] / 0.0625
    b["dist_tram_m"] = tram_distance(b)
    return b


def tram_distance(b: pd.DataFrame) -> np.ndarray:
    from scipy.spatial import cKDTree
    st = W.base_stop_times()
    used = set(st.loc[st["tram"], "stop_id"])
    s = W.read_table("stops.txt")
    s = s[s["stop_id"].isin(used)]
    x, y = AI.TO2180.transform(s["stop_lon"].astype(float).to_numpy(), s["stop_lat"].astype(float).to_numpy())
    d, _ = cKDTree(np.c_[x, y]).query(np.c_[b["x"], b["y"]])
    return d


def perf(b, u, c, w="census"):
    acc = u[f"acc_{w}_{c}"].to_numpy(np.float64)
    prox = b[f"prox_{w}_fast_{c}"].to_numpy(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(prox > 0, 100 * acc / prox, np.nan), acc, prox


def uc_values(units: dict) -> tuple[dict, pd.DataFrame]:
    """Urban-centre ratios per scenario from the uccensus sums (origins = urban-centre cells)."""
    from pipeline import access_uc as U
    from pipeline.access_uc_aggregate import mor, prox_frame, rom
    u = U.uc_cells(AGG)
    P = prox_frame(AGG)
    oi = u["origin_idx"].to_numpy()
    w = u["w_census"].to_numpy(np.float64)
    out = {}
    for s, df in units.items():
        for c in CUTS:
            acc = df[f"acc_uccensus_{c}"].to_numpy(np.float64)[oi]
            prox = P[f"prox_census_fast{c}"].to_numpy(np.float64)
            out[(s, c)] = (mor(acc, prox, w), rom(acc, prox, w))
    return out, u


# ------------------------------------------------------------------ control
def control(b, units) -> dict:
    prod = AG.load_unit(AGG, "all", "pt_am")
    s0 = units["S0"]
    assert (prod["cell_id"].to_numpy() == s0["cell_id"].to_numpy()).all()
    out = {"cells": int(len(s0))}
    for w in ("census", "raw"):
        diffs = [np.abs(s0[f"acc_{w}_{c}"].to_numpy(np.float64) - prod[f"acc_{w}_{c}"].to_numpy(np.float64)) for c in AI.CUTOFFS]
        D = np.stack(diffs)
        out[f"max_abs_diff_{w}"] = float(D.max())
        out[f"cells_differing_{w}"] = int((D > 0).any(axis=0).sum())
    for c in CUTS:
        out[f"max_abs_diff_r5only_{c}"] = float(np.abs(s0[f"r5only_census_{c}"].to_numpy(np.float64) - prod[f"r5only_census_{c}"].to_numpy(np.float64)).max())
    # urban centre against the production urban-centre routing
    from pipeline import access_uc as U
    ucp = pd.read_parquet(U.unit_path(AGG, "pt_am"))
    u = U.uc_cells(AGG)
    oi = u["origin_idx"].to_numpy()
    out["uc_max_abs_diff"] = float(max(np.abs(s0[f"acc_uccensus_{c}"].to_numpy(np.float64)[oi] - ucp[f"acc_census_{c}"].to_numpy(np.float64)).max()
                                       for c in AI.CUTOFFS))
    # published metrics
    pub = pd.read_csv(METRICS / "metrics_access.csv")
    pub = pub[(pub["agglomeration"] == AGG) & (pub["feed_variant"] == "all") & (pub["population_grid"] == GRID)]
    pubu = pd.read_csv(METRICS / "metrics_access_uc.csv")
    pubu = pubu[(pubu["agglomeration"] == AGG) & (pubu["population_grid"] == GRID)]
    rows = []
    w = b["w_census"].to_numpy(np.float64)
    uc, _ = uc_values({"S0": s0})
    for dom in ("core", "covered", "fua"):
        sel = sel_dom(b, dom)
        for c in CUTS:
            p, acc, prox = perf(b, s0, c)
            for kind, v in (("mean_of_ratios", AG.wmean(p, w, sel)), ("ratio_of_means", AG.ratio_of_means(acc, prox, w, sel))):
                m = f"tp_pt_am_{c}min" + ("_ratio_of_means" if kind == "ratio_of_means" else "")
                pv = pub.loc[(pub["domain"] == dom) & (pub["metric"] == m), "value"]
                rows.append({"domain": dom, "metric": m, "s0": sig(v), "published": float(pv.iloc[0]) if len(pv) else None})
    for c in CUTS:
        for i, m in enumerate((f"tp_pt_am_{c}min", f"tp_pt_am_{c}min_ratio_of_means")):
            pv = pubu.loc[pubu["metric"] == m, "value"]
            rows.append({"domain": "urban_centre", "metric": m, "s0": sig(uc[("S0", c)][i]), "published": float(pv.iloc[0]) if len(pv) else None})
    t = pd.DataFrame(rows)
    t["equal"] = t["s0"] == t["published"]
    out["published"] = t.to_dict("records")
    out["all_published_equal"] = bool(t["equal"].all())
    return out


def sel_dom(b, dom):
    if dom == "core":
        return b["in_core"].to_numpy()
    if dom == "covered":
        return b["in_mask_all"].to_numpy()
    return np.ones(len(b), bool)


# ------------------------------------------------------------------ scenario values
def city_table(b, units) -> pd.DataFrame:
    w = b["w_census"].to_numpy(np.float64)
    uc, _ = uc_values(units)
    rows = []
    for s in units:
        for c in CUTS:
            p, acc, prox = perf(b, units[s], c)
            for dom in ("core", "covered", "fua"):
                sel = sel_dom(b, dom)
                rows.append({"scenario": s, "cutoff": c, "domain": dom, "ratio_of_means": AG.ratio_of_means(acc, prox, w, sel),
                             "mean_of_ratios": AG.wmean(p, w, sel)})
            rows.append({"scenario": s, "cutoff": c, "domain": "urban_centre", "ratio_of_means": uc[(s, c)][1],
                         "mean_of_ratios": uc[(s, c)][0]})
    t = pd.DataFrame(rows)
    s0 = t[t["scenario"] == "S0"].set_index(["cutoff", "domain"])
    for k in ("ratio_of_means", "mean_of_ratios"):
        t[f"d_{k}"] = t[k] - t.set_index(["cutoff", "domain"]).index.map(s0[k]).to_numpy()
    return t


def cell_deltas(b, units) -> dict:
    out = {}
    for s in units:
        for c in CUTS:
            p, _, _ = perf(b, units[s], c)
            p0, _, _ = perf(b, units["S0"], c)
            out[(s, c)] = p - p0
    return out


def gainers(b, dl) -> pd.DataFrame:
    w = b["w_census"].to_numpy(np.float64)
    rows = []
    for s in SCENS:
        for c in CUTS:
            d = dl[(s, c)]
            for dom in ("core", "covered"):
                sel = sel_dom(b, dom) & np.isfinite(d)
                tot = w[sel].sum()
                r = {"scenario": s, "cutoff": c, "domain": dom, "population": tot}
                for k, m in (("gain_gt2", d > 2), ("gain_gt5", d > 5), ("gain_any", d > 0.01), ("loss_any", d < -0.01),
                             ("loss_gt1", d < -1)):
                    r[f"pop_{k}"] = float(w[sel & m].sum())
                    r[f"share_{k}"] = 100 * float(w[sel & m].sum() / tot)
                r["max_gain"] = float(np.nanmax(d[sel]))
                r["max_loss"] = float(np.nanmin(d[sel]))
                rows.append(r)
    return pd.DataFrame(rows)


def by_band(b, dl, col, edges, label) -> pd.DataFrame:
    w = b["w_census"].to_numpy(np.float64)
    sel0 = b["in_mask_all"].to_numpy()
    cat = pd.cut(b[col], edges, right=False)
    rows = []
    for s in SCENS:
        for c in CUTS:
            d = dl[(s, c)]
            for k, g in pd.Series(np.arange(len(b))).groupby(cat, observed=False):
                ix = g.to_numpy()
                ix = ix[sel0[ix] & np.isfinite(d[ix])]
                ww = w[ix]
                rows.append({"scenario": s, "cutoff": c, label: str(k), "cells": len(ix), "population": float(ww.sum()),
                             "mean_gain": float((d[ix] * ww).sum() / ww.sum()) if ww.sum() > 0 else None,
                             "share_gt2": 100 * float(ww[d[ix] > 2].sum() / ww.sum()) if ww.sum() > 0 else None,
                             "max_gain": float(d[ix].max()) if len(ix) else None,
                             "min_gain": float(d[ix].min()) if len(ix) else None})
    return pd.DataFrame(rows)


def ranking(ct: pd.DataFrame) -> pd.DataFrame:
    pub = pd.read_csv(METRICS / "metrics_access.csv")
    pub = pub[(pub["feed_variant"] == "all") & (pub["population_grid"] == GRID)]
    pubu = pd.read_csv(METRICS / "metrics_access_uc.csv")
    pubu = pubu[pubu["population_grid"] == GRID]
    rows = []
    for dom in ("core", "covered", "urban_centre"):
        src = pubu if dom == "urban_centre" else pub[pub["domain"] == dom]
        for c in CUTS:
            m = f"tp_pt_am_{c}min_ratio_of_means"
            others = src[(src["metric"] == m) & (src["agglomeration"] != AGG)].set_index("agglomeration")["value"].astype(float)
            for s in ["S0"] + SCENS:
                v = float(ct[(ct.scenario == s) & (ct.cutoff == c) & (ct.domain == dom)]["ratio_of_means"].iloc[0])
                rank = 1 + int((others > v).sum())
                above = others[others > v].sort_values()
                rows.append({"domain": dom, "cutoff": c, "scenario": s, "value": v, "rank_of_7": rank,
                             "next_above": f"{NAMES[above.index[0]]} {above.iloc[0]:.1f}".replace(".", ",") if len(above) else "",
                             "others": "; ".join(f"{NAMES[a]} {x:.1f}".replace(".", ",") for a, x in others.sort_values(ascending=False).items())})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ layer, maps
def layer(b, units, dl) -> pd.DataFrame:
    import geopandas as gpd
    m = b["in_mask_all"].to_numpy()
    d = pd.DataFrame({"agglomeration": AGG, "cell_id": b["cell_id"].to_numpy(), "pop_census_scaled": b["w_census"].round(3),
                      "in_core": b["in_core"].to_numpy(), "in_mask_all": m,
                      "dist_centre_km": b["dist_centre_km"].round(3), "dist_tram_stop_m": np.round(b["dist_tram_m"], 0)})
    for c in CUTS:
        p0, _, _ = perf(b, units["S0"], c)
        d[f"tp_s0_{c}"] = np.where(m, np.round(p0, 3), np.nan).astype(np.float32)
        for s in SCENS:
            d[f"d_{s.lower()}_{c}"] = np.where(m, np.round(dl[(s, c)], 3), np.nan).astype(np.float32)
    lon, lat = AI.TO4326.transform(b["x"].to_numpy(), b["y"].to_numpy())
    g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(np.round(lon, 6), np.round(lat, 6)), crs="EPSG:4326")
    LAYERS.mkdir(parents=True, exist_ok=True)
    g.to_parquet(LAYERS / "whatif_wroclaw_cells.parquet", index=False)
    return d


def maps(b, dl, sstats: dict) -> list[str]:
    import geopandas as gpd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch
    st = gpd.read_parquet(LAYERS / "tram_stretches.parquet")
    st = st[st["agglomeration"] == AGG].to_crs(2180)
    m = b["in_mask_all"].to_numpy() & (b["w_census"].to_numpy() > 0)
    core = b["in_core"].to_numpy()
    xs, ys = b["x"].to_numpy(), b["y"].to_numpy()
    edges = [-1e9, -1, -0.01, 0.01, 1, 2, 5, 10, 1e9]
    labels = ["strata > 1 pkt", "strata do 1 pkt", "bez zmiany", "0–1 pkt", "1–2 pkt", "2–5 pkt", "5–10 pkt", "> 10 pkt"]
    cols = ["#c0392b", "#ef9a8a", "#dcdad5", "#c6dbef", "#9ecae1", "#4292c6", "#08519c", "#08306b"]
    cmap, norm = ListedColormap(cols), BoundaryNorm(edges, len(cols))
    xr = (xs[core].min() - 6000, xs[core].max() + 6000)
    yr = (ys[core].min() - 6000, ys[core].max() + 6000)
    files = []
    for s in SCENS:
        for c in CUTS:
            d = dl[(s, c)]
            fig, ax = plt.subplots(figsize=(9, 8.2), dpi=110)
            fig.patch.set_facecolor("#fcfcfb")
            ax.set_facecolor("#fcfcfb")
            k = m & np.isfinite(d)
            ax.scatter(xs[k], ys[k], c=d[k], cmap=cmap, norm=norm, marker="s", s=7.5, linewidths=0)
            st.plot(ax=ax, color="#222222", linewidth=0.5, alpha=0.6)
            ax.set_xlim(*xr)
            ax.set_ylim(*yr)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_xlabel("")
            ax.set_ylabel("")
            for sp in ax.spines.values():
                sp.set_visible(False)
            ax.legend(handles=[Patch(color=cl, label=lb) for cl, lb in zip(cols, labels)], loc="lower left", fontsize=8,
                      frameon=True, title=f"zmiana TP {c} min wobec S0", title_fontsize=8)
            ax.set_title(f"{s}: {W.SCENARIOS[s]['label']}\nzmiana transport performance {c} min (7:00–9:00, rozkład), pkt; "
                         f"linie: odcinki tramwajowe", fontsize=9, loc="left")
            fn = f"map_{s.lower()}_d{c}.png"
            fig.savefig(QA / fn, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            files.append(fn)
    return files


# ------------------------------------------------------------------ metrics rows
def metric_rows(ct, gn, bstats) -> list[dict]:
    rows = []
    src = ("R5 v7.5.1 (r5py 1.1.7); GTFS: wszystkie feedy, rozkład tramwajów Wrocławia zmieniony w scenariuszu "
           "(pipeline.whatif_tram); OSM 2026-11-22; ludność: NSP 2021 + GHSL 2020")
    flag0 = "scenariusz what-if na rozkładzie (nie rzeczywistość, bez kosztu i wykonalności); "

    def add(dom, metric, label, value, unit, tier, flag=""):
        rows.append({"agglomeration": AGG, "domain": dom, "metric": metric, "label": label,
                     "value": sig(value) if value is not None else None, "unit": unit, "grid": AG.GRID_LABEL[GRID],
                     "source": src, "population_date": AG.POP_DATE[GRID], "timetable_date": W.__dict__.get("REF_DAY", "2026-11-25"),
                     "coverage_share": None, "flag": (flag0 + flag).strip("; ") or None, "tier": tier,
                     "feed_variant": "all", "population_grid": GRID})

    for r in ct.itertuples(index=False):
        s, c, dom = r.scenario.lower(), r.cutoff, r.domain
        lab = W.SCENARIOS[r.scenario]["label"]
        add(dom, f"whatif_{s}_tp_pt_am_{c}min_ratio_of_means",
            f"Transport performance {c} min (7:00–9:00), scenariusz {r.scenario}: {lab}; stosunek średnich", r.ratio_of_means, "%",
            "table" if r.scenario != "S0" else "qa")
        add(dom, f"whatif_{s}_tp_pt_am_{c}min", f"Jak whatif_{s}_tp_pt_am_{c}min_ratio_of_means, ale średnia stosunków komórek",
            r.mean_of_ratios, "%", "table" if r.scenario != "S0" else "qa")
        if r.scenario != "S0":
            add(dom, f"whatif_{s}_minus_s0_tp_pt_am_{c}min_ratio_of_means",
                f"Zmiana transport performance {c} min wobec rozkładu bez zmian (S0), scenariusz {r.scenario}, stosunek średnich, pkt",
                r.d_ratio_of_means, "pkt", "main" if (r.scenario == MAIN and dom in ("core", "covered")) else "table")
            add(dom, f"whatif_{s}_minus_s0_tp_pt_am_{c}min",
                f"Jak whatif_{s}_minus_s0_tp_pt_am_{c}min_ratio_of_means, ale średnia stosunków komórek, pkt",
                r.d_mean_of_ratios, "pkt", "table")
    for r in gn.itertuples(index=False):
        s = r.scenario.lower()
        for k, txt in (("gt2", "o więcej niż 2 pkt"), ("gt5", "o więcej niż 5 pkt")):
            add(r.domain, f"whatif_{s}_pop_gain_{k}_{r.cutoff}min",
                f"Mieszkańcy komórek, w których transport performance {r.cutoff} min rośnie {txt} (scenariusz {r.scenario})",
                getattr(r, f"pop_gain_{k}"), "os.", "table")
            add(r.domain, f"whatif_{s}_share_gain_{k}_{r.cutoff}min",
                f"Udział mieszkańców obszaru z przyrostem transport performance {r.cutoff} min {txt} (scenariusz {r.scenario})",
                getattr(r, f"share_gain_{k}"), "%", "table")
        add(r.domain, f"whatif_{s}_share_loss_{r.cutoff}min",
            f"Udział mieszkańców obszaru ze spadkiem transport performance {r.cutoff} min (scenariusz {r.scenario}; skutek zaokrągleń i przesunięć rozkładu)",
            r.share_loss_any, "%", "qa")
    for s, st in bstats.items():
        am = next(b for b in st["bands"] if b["band"] == "am_peak")
        add("fua", f"whatif_{s.lower()}_tram_speed_am_peak", f"Rozkładowa prędkość tramwajów na odcinkach, szczyt poranny 7–9, scenariusz {s}",
            am["speed_after"], "km/h", "table", "suma długości / suma czasu przejazdów na odcinkach; czasy w pełnych minutach")
        add("fua", f"whatif_{s.lower()}_tram_veh_h_saved", f"Wozogodziny tramwajowe oszczędzone w dobie (środa), scenariusz {s}",
            st["veh_h_saved_day"], "wozogodziny", "table", "")
    return sorted(rows, key=lambda m: (m["domain"], m["metric"]))


def write_metrics(rows) -> None:
    write_json(METRICS / "metrics_whatif.json", {"generated_for_timetable_date": "2026-11-25", "step": STEP, "metrics": rows})
    with open(METRICS / "metrics_whatif.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


# ------------------------------------------------------------------ main
def main() -> None:
    t0 = time.time()
    QA.mkdir(parents=True, exist_ok=True)
    units = {}
    for s in W.SCENARIOS:
        u = W.load_route(s)
        if u is None:
            raise SystemExit(f"{s}: routing not finished (python -m pipeline.whatif_tram route)")
        units[s] = u
    b = base()
    for u in units.values():
        assert (u["cell_id"].to_numpy() == b["cell_id"].to_numpy()).all()
    ctl = control(b, units)
    write_json(QA / "control.json", ctl)
    ct = city_table(b, units)
    dl = cell_deltas(b, units)
    gn = gainers(b, dl)
    dist = by_band(b, dl, "dist_centre_km", DIST_BANDS, "dist_centre_km")
    dens = by_band(b, dl, "density", DENS_BANDS, "density_per_km2")
    tram = by_band(b, dl, "dist_tram_m", TRAM_BANDS, "dist_tram_stop_m")
    rk = ranking(ct)
    bstats = {s: json.loads((W.feed_dir(s) / "build.json").read_text(encoding="utf-8")) for s in W.SCENARIOS}
    for name, df in (("scenario_table", ct), ("gainers", gn), ("by_distance", dist), ("by_density", dens),
                     ("by_tram_distance", tram), ("ranking", rk)):
        df.to_csv(QA / f"{name}.csv", index=False, lineterminator="\n", float_format="%.4g")
    spd = pd.DataFrame([{"scenario": s, **bb} for s, st in bstats.items() for bb in st["bands"]])
    spd.to_csv(QA / "tram_speed_bands.csv", index=False, lineterminator="\n")
    shutil.copyfile(W.OUT / "s3_classes.csv", QA / "s3_classes.csv")
    shutil.copyfile(W.feed_dir("S4") / "headways.csv", QA / "s4_headways.csv")
    lay = layer(b, units, dl)
    pngs = maps(b, dl, bstats)
    loss = losses(b, units, dl)
    loss.to_csv(QA / "losses.csv", index=False, lineterminator="\n", float_format="%.4g")
    rows = metric_rows(ct, gn, bstats)
    write_metrics(rows)
    timing = {s: json.loads((W.route_dir(s) / "timing.json").read_text(encoding="utf-8")) for s in W.SCENARIOS
              if (W.route_dir(s) / "timing.json").exists()}
    from pipeline import whatif_tram_md
    whatif_tram_md.write(ctl=ctl, ct=ct, gn=gn, dist=dist, dens=dens, tram=tram, rk=rk, bstats=bstats, loss=loss, timing=timing,
                         hopchk=json.loads((W.OUT / "hop_check.json").read_text(encoding="utf-8")))
    extra = {"code_version": W.CODE_VERSION, "timetable_date": "2026-11-25", "scenarios": {k: v["label"] for k, v in W.SCENARIOS.items()},
             "main_scenario": MAIN, "control_all_published_equal": ctl["all_published_equal"], "rows": len(rows),
             "routing": timing, "outputs": ["metrics/metrics_whatif.csv", "metrics/metrics_whatif.json",
                                             "layers/whatif_wroclaw_cells.parquet", "qa/whatif/"] + pngs,
             "note": "rozkład, nie rzeczywistość; zmodyfikowane GTFS tylko w data/interim/whatif (poza results/)"}
    write_meta(QA, STEP, started=t0, extra=extra)
    with tempfile.TemporaryDirectory() as td:
        p = write_meta(td, STEP, started=t0, extra=extra)
        shutil.copyfile(p, METRICS / "_meta_whatif.json")
        p = write_meta(td, STEP + "_layer", started=t0, extra={**extra, "layer": "whatif_wroclaw_cells.parquet", "cells": int(len(lay))})
        shutil.copyfile(p, LAYERS / "_meta_whatif.json")
    print(f"aggregate: {len(rows)} rows, control equal={ctl['all_published_equal']}, {time.time() - t0:.0f} s")


def losses(b, units, dl) -> pd.DataFrame:
    """Cells that lose in any scenario at 30 or 45 min: where they are and by how much."""
    w = b["w_census"].to_numpy(np.float64)
    m = b["in_mask_all"].to_numpy()
    rows = []
    for s in SCENS:
        for c in CUTS:
            d = dl[(s, c)]
            k = np.flatnonzero(m & np.isfinite(d) & (d < -0.01))
            for i in k[np.argsort(d[k])][:15]:
                rows.append({"scenario": s, "cutoff": c, "cell_id": b["cell_id"].iat[i], "pop": w[i], "d_points": d[i],
                             "dist_centre_km": b["dist_centre_km"].iat[i], "dist_tram_m": b["dist_tram_m"].iat[i]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main()
