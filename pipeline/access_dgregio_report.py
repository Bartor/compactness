"""Tables and the QA note of the DG REGIO side step (pipeline.access_dgregio).

    python -m pipeline.access_dgregio prep      # urban centres, supply, stop check, production-chunk analyses
    python -m pipeline.access_dgregio report    # results/qa/access/dgregio/dgregio.md + CSV + _meta.json

Every number in the note comes from a CSV written next to it.  Production data are read only.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from pipeline import access_dgregio as D
from pipeline import access_inputs as AI
from pipeline.common import write_meta

NAMES = {a: n for a, (_, n) in D.CITIES.items()}
CUT_SPEED = {30: "fast30", 45: "fast45"}


def f1(x, nd=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    return f"{x:.{nd}f}".replace(".", ",")


def sgn(x, nd=1):
    if x is None or not np.isfinite(x):
        return "–"
    return ("+" if x >= 0 else "−") + f1(abs(x), nd)


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def mor(acc, prox, w):
    """Population-weighted mean of cell ratios (production headline)."""
    acc, prox, w = map(lambda a: np.asarray(a, float), (acc, prox, w))
    m = (w > 0) & (prox > 0) & np.isfinite(acc)
    return float(100 * (w[m] * acc[m] / prox[m]).sum() / w[m].sum())


def rom(acc, prox, w):
    """Ratio of population-weighted means (DG REGIO annex)."""
    acc, prox, w = map(lambda a: np.asarray(a, float), (acc, prox, w))
    m = (w > 0) & np.isfinite(acc)
    return float(100 * (w[m] * acc[m]).sum() / (w[m] * prox[m]).sum())


# ------------------------------------------------------------------ prep
def prep(aggs) -> None:
    D.QA.mkdir(parents=True, exist_ok=True)
    an = D.annex()
    uc_rows, sup_rows, feed_rows, prod_rows, stop_rows = [], [], [], [], []
    for agg in aggs:
        d = D.frame(agg)
        poly, ncell = D.uc_polygon(agg)
        uo = D.uc_origins(agg)
        ud = D.uc_dests(agg)
        uc_rows.append({"agglomeration": agg, "uc_code": D.CITIES[agg][0], "uc_cells_1km": ncell,
                        "annex_area_km2": an.loc[agg, "t1_06"], "annex_pop_2011": an.loc[agg, "t1_05"],
                        "our_pop_census2021_in_uc": d.loc[d["in_uc"], "w_census"].sum(),
                        "our_pop_ghsl2020_in_uc": d.loc[d["in_uc"], "w_raw"].sum(),
                        "uc_origin_cells_250m": len(uo), "uc_dest_cells_250m": len(ud),
                        "uc_pop_outside_city": d.loc[d["in_uc"] & ~d["in_core"], "w_census"].sum(),
                        "city_pop_census2021": d.loc[d["in_core"], "w_census"].sum(),
                        "city_pop_outside_uc_share": d.loc[d["in_core"] & ~d["in_uc"], "w_census"].sum() / d.loc[d["in_core"], "w_census"].sum()})
        # supply (annex table 1 definition)
        g, bf = D.supply(agg)
        amap = {"total": ("t1_19", "t1_25"), "bus": ("t1_20", "t1_26"), "tram": ("t1_21", "t1_27"),
                "metro": ("t1_22", "t1_28"), "rail": ("t1_23", "t1_29")}
        for _, r in g.iterrows():
            a_v, a_s = amap.get(r["mode"], (None, None))
            av = an.loc[agg, a_v] if a_v else None
            asp = an.loc[agg, a_s] if a_s else None
            av = float(av) if isinstance(av, (int, float)) else None
            asp = float(asp) if isinstance(asp, (int, float)) else None
            ours_h = r["vkm_per_1000inh"] / 14.0
            sup_rows.append({"agglomeration": agg, "mode": r["mode"], "our_vkm_6_20_in_uc": r["km"],
                             "our_vkm_per_1000inh_per_hour": ours_h, "annex_2018_value": av,
                             "ratio_annex_to_ours": av / ours_h if av and ours_h else None,
                             "our_speed_kmh": r["speed_kmh"], "annex_speed_kmh": asp, "our_segments": r["n"]})
        feed_rows.append(bf)
        # OSM stops in the UC without a served GTFS stop nearby (bus/tram 100 m, rail 300 m)
        stop_rows += stop_check(agg)
        # production chunks: origins in the city proper (published) and in the urban centre
        b = pd.concat([AI.origins(agg)[["cell_id", "w_census", "w_raw", "in_core"]], AI.proximity(agg).drop(columns="cell_id")], axis=1)
        b["in_uc"] = D.in_uc(agg, AI.origins(agg)["x"].to_numpy(), AI.origins(agg)["y"].to_numpy())
        for net, scen, kind in (("all", "pt_am", "transit"), ("street", "walk", "walk"), ("street", "bike_lts3", "bike"),
                                ("street", "bike_lts4", "bike")):
            u = D.prod_unit(agg, net, scen)
            assert (u["cell_id"].to_numpy() == b["cell_id"].to_numpy()).all()
            cuts = (30, 45) if kind == "transit" else (30,)
            for c in cuts:
                sp = "walk" if kind == "walk" else "fast"
                for dom in ("in_core", "in_uc"):
                    sel = b[dom].to_numpy()
                    for wname, wcol in (("census", "w_census"), ("raw", "w_raw")):
                        w = np.where(sel, b[wcol], 0.0)
                        acc = u[f"acc_{wname}_{c}"].to_numpy()
                        prox = b[f"prox_{wname}_{sp}_{c}"].to_numpy()
                        prod_rows.append({"agglomeration": agg, "scenario": scen, "cutoff": c, "origins": dom[3:],
                                          "grid": wname, "mean_of_ratios": mor(acc, prox, w), "ratio_of_means": rom(acc, prox, w)})
                    if kind == "transit":   # production destinations restricted to the city proper (censuscore)
                        w = np.where(sel, b["w_census"], 0.0)
                        prod_rows.append({"agglomeration": agg, "scenario": scen + "_dest_city", "cutoff": c, "origins": dom[3:],
                                          "grid": "census", "mean_of_ratios": mor(u[f"acc_censuscore_{c}"], b[f"prox_censuscore_fast_{c}"], w),
                                          "ratio_of_means": rom(u[f"acc_censuscore_{c}"], b[f"prox_censuscore_fast_{c}"], w)})
                    if kind == "transit" and dom == "in_uc":   # R5 alone, without the walk rule
                        w = np.where(sel, b["w_census"], 0.0)
                        prod_rows.append({"agglomeration": agg, "scenario": scen + "_r5only", "cutoff": c, "origins": "uc",
                                          "grid": "census", "mean_of_ratios": mor(u[f"r5only_census_{c}"], b[f"prox_census_fast_{c}"], w),
                                          "ratio_of_means": rom(u[f"r5only_census_{c}"], b[f"prox_census_fast_{c}"], w)})
        # walking on the urban-centre domain from the production walk cache, proximity clipped to the UC
        P = D.proximity(uo, ud, D.RADII)
        wk = D.walk_uc(agg, list(range(20, 31)))
        (D.OUT / agg).mkdir(parents=True, exist_ok=True)
        wk.assign(cell_id=uo["cell_id"].to_numpy()).to_parquet(D.OUT / agg / "walk_uc.parquet")
        for grid in ("census", "raw"):
            w = uo[f"w_{grid}"].to_numpy()
            for c in range(20, 31):
                prod_rows.append({"agglomeration": agg, "scenario": "walk_ucdomain", "cutoff": c, "origins": "uc", "grid": grid,
                                  "mean_of_ratios": mor(wk[f"acc_{grid}_{c}"], P[f"prox_{grid}_walk30"], w),
                                  "ratio_of_means": rom(wk[f"acc_{grid}_{c}"], P[f"prox_{grid}_walk30"], w)})
        P.assign(cell_id=uo["cell_id"].to_numpy()).to_parquet(D.OUT / f"prox_uc_{agg}.parquet")
    pd.DataFrame(uc_rows).to_csv(D.QA / "urban_centres.csv", index=False)
    pd.DataFrame(sup_rows).to_csv(D.QA / "supply_uc_vs_annex.csv", index=False)
    pd.concat(feed_rows).to_csv(D.QA / "supply_uc_by_feed.csv", index=False)
    pd.DataFrame(stop_rows).to_csv(D.QA / "stops_uc_osm_vs_gtfs.csv", index=False)
    pd.DataFrame(prod_rows).to_csv(D.QA / "production_chunks_domains.csv", index=False)
    print("prep done")


def stop_check(agg: str) -> list[dict]:
    """OSM stops (de-duplicated, phase 1) in the urban centre with no stop served on the reference day nearby."""
    from scipy.spatial import cKDTree
    from pipeline import gtfs_service as gs
    from pipeline.common import INTERIM
    osm = pd.read_parquet(INTERIM / "osm" / "stops_dedup.parquet")
    osm = osm[D.in_uc(agg, osm["x"].to_numpy(), osm["y"].to_numpy())]
    st = gs.stop_times(agg, D.REF_DAY, "all")
    served = st.dropna(subset=["x", "y"]).drop_duplicates("suid")
    rows = []
    for kind, osm_kinds, classes, r in (("bus/tram", None, ("bus", "tram", "trolleybus"), 100.0),
                                        ("rail", ("rail_station",), ("rail", "metro"), 300.0)):
        o = osm[osm["kind"].isin(osm_kinds)] if osm_kinds else osm[~osm["kind"].isin(("rail_station",))]
        g = served[served["route_class"].isin(classes)]
        t = cKDTree(np.c_[g["x"], g["y"]])
        dist, _ = t.query(np.c_[o["x"], o["y"]])
        miss = o[dist > r]
        rows.append({"agglomeration": agg, "stop_kind": kind, "osm_kinds": ",".join(sorted(o["kind"].unique())),
                     "radius_m": r, "osm_stops_in_uc": len(o), "without_served_gtfs_stop": int((dist > r).sum()),
                     "share_matched": float((dist <= r).mean()) if len(o) else None,
                     "unmatched_names": "; ".join(sorted(set(miss["name"].dropna().astype(str)))[:25])})
    return rows


# ------------------------------------------------------------------ report
ORIGIN_SET: dict = {}


def load_route(agg: str, scen: str, limit: int | None = None) -> pd.DataFrame | None:
    """Routing result of the side step; a full-UC file falls back to the 800-origin sample (Warszawa: the full
    run was skipped for time, its file is a text placeholder)."""
    for lim in ([limit] if limit else [None, 800]):
        p = D.OUT / agg / f"{scen}{'_lim' + str(lim) if lim else ''}.parquet"
        if p.exists() and p.stat().st_size > 1000:
            ORIGIN_SET[(agg, scen)] = "pełny UC" if lim is None else f"próba {lim} startów"
            return pd.read_parquet(p).set_index("uo_row")
    return None


def equiv_cutoff(curve_cuts, curve_vals, target):
    """Cutoff (min) at which our curve reaches the target value (linear interpolation), or None."""
    x, y = np.asarray(curve_cuts, float), np.asarray(curve_vals, float)
    if target < y[0] or target > y[-1]:
        return None
    return float(np.interp(target, y, x))


def report(aggs) -> None:
    t0 = time.time()
    an = D.annex()
    prod = pd.read_csv(D.QA / "production_chunks_domains.csv")
    uc = pd.read_csv(D.QA / "urban_centres.csv").set_index("agglomeration")

    def P(agg, scen, c, origins, grid="census", stat="mean_of_ratios"):
        r = prod[(prod.agglomeration == agg) & (prod.scenario == scen) & (prod.cutoff == c) & (prod.origins == origins) & (prod.grid == grid)]
        return float(r[stat].iloc[0]) if len(r) else None

    dec_rows, curve_rows, plaus_rows, sens_rows = [], [], [], []
    for agg in aggs:
        uo = D.uc_origins(agg)
        Px = pd.read_parquet(D.OUT / f"prox_uc_{agg}.parquet")
        assert (Px["cell_id"].to_numpy() == uo["cell_id"].to_numpy()).all()
        w = uo["w_census"].to_numpy()
        wr = uo["w_raw"].to_numpy()
        R = {s: load_route(agg, s) for s in ("pt_base", "pt_walk5km", "pt_walk5km_slow4", "bike_lts3", "bike_lts4")}
        R9 = {s: load_route(agg, s, 800) for s in ("pt_base_9dep", "pt_walk5km_9dep")}
        pop_uc = float(uc.loc[agg, "our_pop_census2021_in_uc"])
        prod_pt = D.prod_unit(agg, "all", "pt_am")
        prox_fua = AI.proximity(agg)
        if R["pt_walk5km"] is not None and R9["pt_walk5km_9dep"] is not None and ORIGIN_SET.get((agg, "pt_walk5km")) == "pełny UC":
            ix, r5 = R9["pt_walk5km_9dep"].index, R["pt_walk5km"]
            for c in (30, 45):
                k = CUT_SPEED[c]
                sens_rows.append({"agglomeration": agg, "measure": f"PT {c}", "item": "krok 4: próba 800 startów zamiast pełnego UC (błąd próby)",
                                  "delta": rom(r5.loc[ix, f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix])
                                  - rom(r5[f"acc_census_{c}"], Px.loc[r5.index, f"prox_census_{k}"], w[r5.index])})
        for c in (30, 45):
            k = CUT_SPEED[c]
            dg = float(an.loc[agg, "t2_13" if c == 30 else "t2_14"])
            steps = [("0. Nasz wynik opublikowany: starty w mieście (rdzeń), cele i mianownik FUA + 15 km, średnia stosunków",
                      P(agg, "pt_am", c, "core"))]
            b = R["pt_base"]
            rows = b.index if b is not None else uo.index
            oi = uo.loc[rows, "origin_idx"].to_numpy()
            steps.append(("1. Starty tylko w urban centre 2011 (cele i mianownik bez zmian)",
                          mor(prod_pt[f"acc_census_{c}"].to_numpy()[oi], prox_fua[f"prox_census_fast_{c}"].to_numpy()[oi], w[rows])))
            if ORIGIN_SET.get((agg, "pt_base")) != "pełny UC":
                sens_rows.append({"agglomeration": agg, "measure": f"PT {c}", "item": "krok 1 na pełnym UC zamiast próby (błąd próby)",
                                  "delta": P(agg, "pt_am", c, "uc") - steps[-1][1]})
            if b is not None:
                steps.append(("2. Cele i mianownik też tylko w urban centre (nowy routing, parametry produkcyjne)",
                              mor(b[f"acc_census_{c}"], Px.loc[b.index, f"prox_census_{k}"], w[b.index])))
                steps.append(("3. Agregacja jak DG REGIO: stosunek średnich ważonych",
                              rom(b[f"acc_census_{c}"], Px.loc[b.index, f"prox_census_{k}"], w[b.index])))
            r5 = R["pt_walk5km"]
            if r5 is not None:
                steps.append(("4. Dojście i odejście do 5 km (OTP maxWalkDistance 5000 m) zamiast 1 km",
                              rom(r5[f"acc_census_{c}"], Px.loc[r5.index, f"prox_census_{k}"], w[r5.index])))
            r9 = R9["pt_walk5km_9dep"]
            if r9 is not None and r5 is not None:
                ix = r9.index
                d9 = (rom(r9[f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix])
                      - rom(r5.loc[ix, f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix]))
                d9l = (rom(r9[f"lenient_acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix])
                       - rom(r5.loc[ix, f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix]))
                steps.append(("5. Średnia z 9 odjazdów co 15 min 7:00–9:00 zamiast mediany z odjazdów co minutę (różnica z próby 800 startów)",
                              steps[-1][1] + d9))
                sens_rows.append({"agglomeration": agg, "measure": f"PT {c}", "item": "9 odjazdów: para liczona przy brakach (średnia tylko z odjazdów z wynikiem ≤ 60 min) zamiast wykluczenia",
                                  "delta": d9l - d9})
                b9 = R9["pt_base_9dep"]
                if b9 is not None and b is not None:
                    sens_rows.append({"agglomeration": agg, "measure": f"PT {c}", "item": "9 odjazdów przy dojściu 1 km (zamiast 5 km), ta sama próba",
                                      "delta": rom(b9[f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix])
                                      - rom(b.loc[ix, f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix])})
            rs = R.get("pt_walk5km_slow4")
            if rs is not None and r5 is not None:
                ix = rs.index
                sens_rows.append({"agglomeration": agg, "measure": f"PT {c}", "item": "co by było, gdyby: odcinki piesze 4 km/h zamiast 5 km/h (krok 4, te same starty)",
                                  "delta": rom(rs[f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix])
                                  - rom(r5.loc[ix, f"acc_census_{c}"], Px.loc[ix, f"prox_census_{k}"], w[ix])})
            if r5 is not None:
                sens_rows.append({"agglomeration": agg, "measure": f"PT {c}", "item": "siatka ludności GHSL 2020 surowa zamiast NSP 2021 (krok 4)",
                                  "delta": rom(r5[f"acc_raw_{c}"], Px.loc[r5.index, f"prox_raw_{k}"], wr[r5.index])
                                  - rom(r5[f"acc_census_{c}"], Px.loc[r5.index, f"prox_census_{k}"], w[r5.index])})
            prev = None
            for name, v in steps:
                dec_rows.append({"agglomeration": agg, "measure": f"PT {c}", "step": name, "value": v,
                                 "delta": None if prev is None or v is None else v - prev})
                prev = v if v is not None else prev
            dec_rows.append({"agglomeration": agg, "measure": f"PT {c}", "step": "DG REGIO (aneks, tabela 2)", "value": dg, "delta": None})
            dec_rows.append({"agglomeration": agg, "measure": f"PT {c}", "step": "Reszta niewyjaśniona (DG REGIO − ostatni krok)",
                             "value": None, "delta": dg - prev})
            # curves: our final-step ratio of means at every cutoff, equivalent cutoff of the DG value
            if r5 is not None:
                for cc in D.CUTS:
                    curve_rows.append({"agglomeration": agg, "mode": "pt_walk5km", "cutoff": cc,
                                       "acc_share_of_uc_pop": float((w[r5.index] * r5[f"acc_census_{cc}"]).sum() / w[r5.index].sum() / pop_uc)})
            # plausibility (c)
            dg_acc = float(an.loc[agg, "t2_09" if c == 30 else "t2_10"])
            dg_prox = float(an.loc[agg, "t2_05" if c == 30 else "t2_06"])
            pop11 = float(an.loc[agg, "t1_05"])
            our_prox = float((w * Px[f"prox_census_{k}"]).sum() / w.sum())
            our_acc = None if r5 is None else float((w[r5.index] * r5[f"acc_census_{c}"]).sum() / w[r5.index].sum())
            plaus_rows.append({"agglomeration": agg, "measure": f"PT {c}",
                               "dg_prox_share_of_uc": dg_prox / pop11, "dg_acc_share_of_uc": dg_acc / pop11,
                               "our_prox_share_of_uc": our_prox / pop_uc, "our_acc_share_of_uc": None if our_acc is None else our_acc / pop_uc,
                               "our_fua_prox_over_uc_pop": float((w * AI.proximity(agg).set_index("cell_id").loc[uo["cell_id"], f"prox_census_fast_{c}"].to_numpy()).sum() / w.sum()) / pop_uc})
        # walking
        dgw = float(an.loc[agg, "t2_11"])
        steps = [("0. Nasz wynik opublikowany (rdzeń, cele FUA + 15 km, średnia stosunków)", P(agg, "walk", 30, "core")),
                 ("1. Starty tylko w urban centre", P(agg, "walk", 30, "uc")),
                 ("2. Cele i mianownik tylko w urban centre (czasy z produkcyjnej pamięci spacerów)", P(agg, "walk_ucdomain", 30, "uc")),
                 ("3. Stosunek średnich", P(agg, "walk_ucdomain", 30, "uc", stat="ratio_of_means")),
                 ("4. Prędkość 4,8 km/h (OTP domyślnie 1,33 m/s): próg 28 min przy 5 km/h", P(agg, "walk_ucdomain", 28, "uc", stat="ratio_of_means"))]
        prev = None
        for name, v in steps:
            dec_rows.append({"agglomeration": agg, "measure": "pieszo 30", "step": name, "value": v, "delta": None if prev is None else v - prev})
            prev = v
        dec_rows.append({"agglomeration": agg, "measure": "pieszo 30", "step": "DG REGIO (aneks, tabela 2)", "value": dgw, "delta": None})
        dec_rows.append({"agglomeration": agg, "measure": "pieszo 30", "step": "Reszta niewyjaśniona (DG REGIO − ostatni krok)", "value": None, "delta": dgw - prev})
        wc = prod[(prod.agglomeration == agg) & (prod.scenario == "walk_ucdomain") & (prod.grid == "census")].sort_values("cutoff")
        curve_rows += [{"agglomeration": agg, "mode": "walk_ratio_of_means", "cutoff": int(r.cutoff), "value": r.ratio_of_means} for r in wc.itertuples()]
        # cycling
        dgb = float(an.loc[agg, "t2_12"])
        for lts in (3, 4):
            rb = R[f"bike_lts{lts}"]
            pb = D.prod_unit(agg, "street", f"bike_lts{lts}")
            rows = rb.index if rb is not None else uo.index
            oi = uo.loc[rows, "origin_idx"].to_numpy()
            steps = [(f"0. Nasz wynik opublikowany, LTS ≤ {lts}", P(agg, f"bike_lts{lts}", 30, "core")),
                     ("1. Starty tylko w urban centre",
                      mor(pb["acc_census_30"].to_numpy()[oi], prox_fua["prox_census_fast_30"].to_numpy()[oi], w[rows]))]
            if rb is not None:
                steps += [("2. Cele i mianownik tylko w urban centre (nowy routing)", mor(rb["acc_census_30"], Px.loc[rb.index, "prox_census_fast30"], w[rb.index])),
                          ("3. Stosunek średnich", rom(rb["acc_census_30"], Px.loc[rb.index, "prox_census_fast30"], w[rb.index]))]
            prev = None
            for name, v in steps:
                dec_rows.append({"agglomeration": agg, "measure": f"rower 30 LTS {lts}", "step": name, "value": v, "delta": None if prev is None else v - prev})
                prev = v
            dec_rows.append({"agglomeration": agg, "measure": f"rower 30 LTS {lts}", "step": "DG REGIO (aneks, tabela 2)", "value": dgb, "delta": None})
            dec_rows.append({"agglomeration": agg, "measure": f"rower 30 LTS {lts}", "step": "Reszta niewyjaśniona (DG REGIO − ostatni krok)", "value": None, "delta": dgb - prev})
            if rb is not None:
                for cc in D.CUTS:
                    curve_rows.append({"agglomeration": agg, "mode": f"bike_lts{lts}_ratio_of_means", "cutoff": cc,
                                       "value": rom(rb[f"acc_census_{cc}"], Px.loc[rb.index, "prox_census_fast30"], w[rb.index])})
        if R["pt_walk5km"] is not None:
            r5 = R["pt_walk5km"]
            for c in (30, 45):
                k = CUT_SPEED[c]
                for cc in D.CUTS:
                    curve_rows.append({"agglomeration": agg, "mode": f"pt_walk5km_ratio_of_means_den{c}", "cutoff": cc,
                                       "value": rom(r5[f"acc_census_{cc}"], Px.loc[r5.index, f"prox_census_{k}"], w[r5.index])})
    dec = pd.DataFrame(dec_rows)
    curves = pd.DataFrame(curve_rows)
    plaus = pd.DataFrame(plaus_rows)
    sens = pd.DataFrame(sens_rows)
    dec.to_csv(D.QA / "decomposition.csv", index=False)
    curves.to_csv(D.QA / "curves_uc.csv", index=False)
    plaus.to_csv(D.QA / "plausibility_30_45.csv", index=False)
    sens.to_csv(D.QA / "sensitivity.csv", index=False)
    feed2018()
    write_md(an, uc, dec, curves, plaus, sens)
    timing = [l for l in (D.OUT / "run.log").read_text(encoding="utf-8").splitlines() if "origins x" in l] if (D.OUT / "run.log").exists() else []
    write_meta(D.QA, "access_dgregio", started=t0, extra={
        "code_version": D.CODE_VERSION,
        "sources": {
            "dgregio_wp_01_2020": {"path": "data/raw/dgregio_wp2020/012020_low_carbon_urban.pdf",
                                   "url": "https://ec.europa.eu/regional_policy/sources/work/012020_low_carbon_urban.pdf"},
            "dgregio_data_annex": {"path": "data/raw/dgregio_wp2020/wp_low_carbon_urban_accessibility_data_annex.xlsx",
                                   "url": "https://ec.europa.eu/regional_policy/sources/work/wp_low_carbon_urban_accessibility_data_annex.xlsx"},
            "eurostat_hdens_clst_2011": {"path": "data/raw/eurostat_hdens_2011/HDENS_CLST_2011.zip",
                                         "url": "https://ec.europa.eu/eurostat/cache/GISCO/geodatafiles/HDENS_CLST_2011.zip",
                                         "licence": "Eurostat GISCO population-distribution download rules; (c) European Union, re-use with attribution"},
            "wayback_ztm_poznan_gtfs_2018_truncated": {"path": "data/raw/wayback_ztm_poznan_gtfs_truncated_20181214_20181216/, data/raw/wayback_ztm_poznan_gtfs_truncated_20181228_20181228/",
                                                       "note": "Internet Archive copies of ZTM Poznań GTFS, truncated at 1 MiB; only routes/calendar usable"},
            "mpk_poznan_annual_reports": {"path": "data/raw/mpk_poznan_annual_reports/", "url": "https://www.mpk.poznan.pl/wp-content/uploads/2022/10/raport-roczny-2017.pdf; .../2025/12/raport-roczny-2024-PL.pdf"}},
        "reference_day": D.REF_DAY, "routing_log": timing,
        "scenarios": D.SCENARIOS, "sample_9dep_origins_per_city": 800})
    print("report written", D.QA / "dgregio.md")


def _zip_members_partial(path) -> dict:
    """Complete members of a truncated zip (local headers only; the archive copy has no central directory)."""
    import struct
    import zlib
    b = open(path, "rb").read()
    i, out = 0, {}
    while b[i:i + 4] == b"PK\x03\x04":
        _, flag, meth, _, _, _, cs, _, nl, el = struct.unpack("<HHHHHIIIHH", b[i + 4:i + 30])
        name = b[i + 30:i + 30 + nl].decode()
        s = i + 30 + nl + el
        if flag & 8 or s + cs > len(b):
            out[name] = None            # truncated
            break
        out[name] = zlib.decompress(b[s:s + cs], -15) if meth == 8 else b[s:s + cs]
        i = s + cs
    return out


def feed2018() -> None:
    """Poznań 2018 timetable test (follow-up): what could be obtained, routes in the archived Dec 2018 files
    vs 2026, and MPK Poznań ordered / executed vehicle-km from its annual reports."""
    import io
    import zipfile
    from pipeline.common import RAW
    att = [
        ("ZTM Poznań, lista plików GTFS (otwarte-dane/gtfsfiles)", "https://www.ztm.poznan.pl/otwarte-dane/gtfsfiles/",
         "lista obejmuje 483 pliki, najstarszy 20230101_20230104.zip; brak plików z 2018 r."),
        ("ZTM Poznań, getGTFSFile z nazwą pliku z 2018 r.", "https://www.ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile/?file=20181214_20181216.zip",
         "serwer zwraca bieżący feed (feed_info 20261124–20261205) niezależnie od nazwy; pobrany plik usunięto"),
        ("Internet Archive, indeks CDX adresów getGTFSFile", "web.archive.org/cdx/search/cdx?url=ztm.poznan.pl/pl/dla-deweloperow/getGTFSFile*",
         "617 zarchiwizowanych plików, z 2018 r. tylko 3: 20181214_20181216, 20181224_20181225, 20181228_20181228 (pierwsze kopie z 2019 r.)"),
        ("Internet Archive, kopie plików z grudnia 2018 r.", "web.archive.org/web/<ts>id_/…getGTFSFile/?file=…",
         "każda kopia ucięta przez archiwum na 1 MiB: kompletne są agency, calendar, routes (i w 20181228 shapes, stops); stop_times i trips brak, więc wozkm i routing niemożliwe; to samo dla sprawdzonych plików z 2019 r."),
        ("transitfeeds.com (OpenMobilityData) i jego magazyn S3", "https://transitfeeds.com/p/ztm-poznan/731",
         "HTTP 403 z wyzwaniem Cloudflare (ochrona przed botami, nie obchodzono); listing S3 openmobilitydata-data: AccessDenied; brak kopii w Internet Archive"),
        ("Mobility Database", "https://mobilitydatabase.org/feeds/gtfs/mdb-982",
         "historia tylko od ok. 2024 r. według strony katalogu (nie sprawdzano API wymagającego konta)"),
    ]
    pd.DataFrame(att, columns=["źródło", "adres", "wynik"]).to_csv(D.QA / "feed2018_attempts.csv", index=False)
    rows = []
    for f in ("20181214_20181216", "20181228_20181228"):
        p = RAW / f"wayback_ztm_poznan_gtfs_truncated_{f}" / f"{f}.zip"
        if not p.exists():
            continue
        m = _zip_members_partial(p)
        r = pd.read_csv(io.BytesIO(m["routes.txt"]), dtype=str, encoding="utf-8-sig")
        for (ag, rt), n in r.groupby(["agency_id", "route_type"]).size().items():
            rows.append({"feed": f, "agency_id": ag, "route_type": rt, "routes": int(n)})
    z = zipfile.ZipFile(D.INTERIM / "r5" / "poznan" / "gtfs_all" / "poznan.zip")
    r26 = pd.read_csv(z.open("routes.txt"), dtype=str, encoding="utf-8-sig")
    for (ag, rt), n in r26.groupby(["agency_id", "route_type"]).size().items():
        rows.append({"feed": "2026 (pipeline, ważny od 20261124)", "agency_id": ag, "route_type": rt, "routes": int(n)})
    pd.DataFrame(rows).to_csv(D.QA / "feed2018_routes.csv", index=False)
    mpk = [
        (2017, "plan (zał. 1 do umowy)", 12036.578, 19286.906, "MPK Poznań, raport roczny 2017, s. 14 PDF"),
        (2017, "zamówienie skorygowane", 11778.800, 19343.127, "MPK Poznań, raport roczny 2017, s. 14 PDF"),
        (2024, "plan (zał. 1 do umowy)", 12142.0, 18050.0, "MPK Poznań, raport roczny 2024, s. 18 i 20 PDF"),
        (2024, "wykonanie", 11984.0, 17898.0, "MPK Poznań, raport roczny 2024, s. 18 i 20 PDF"),
    ]
    pd.DataFrame(mpk, columns=["rok", "rodzaj", "tramwaj_tys_pociagokm", "autobus_tys_wozokm", "źródło"]).to_csv(D.QA / "mpk_poznan_vkm_annual.csv", index=False)


def write_md(an, uc, dec, curves, plaus, sens) -> None:
    # filled in by write_md_text (kept separate so the prose can be edited without touching the numbers)
    from pipeline.access_dgregio_text import render
    (D.QA / "dgregio.md").write_text(render(an, uc, dec, curves, plaus, sens, f1, sgn, md_table, NAMES), encoding="utf-8")
