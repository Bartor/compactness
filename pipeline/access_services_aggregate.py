"""Aggregation for pipeline.access_services and pipeline.agegrid (ROADMAP item 13).

Outputs
* results/metrics/metrics_services.csv / .json (row schema of the other step files) + _meta_services.json
* results/layers/services_cells.parquet (+ _meta_services.json): per covered origin cell, minutes to the nearest
  secondary school / SOR (null = not within 60 min)
* results/qa/services/: facility counts, tables (csv + md fragments), age tables, _meta.json

Domains: "covered" = FUA cells in the GTFS coverage mask (all routed origins); "core" = core cells in the mask (the
routing covers mask cells only; coverage_share says which part of the core residents that is).  Shares are of
residents (census-scaled grid) of the domain; "none60" = no facility of the kind within 60 min.
"""
from __future__ import annotations

import json
import shutil
import time

import numpy as np
import pandas as pd

from pipeline import access_inputs as AI
from pipeline import access_services as S
from pipeline.common import RESULTS, sig, write_json, write_meta

QA = RESULTS / "qa" / "services"
METRICS = RESULTS / "metrics"
LAYERS = RESULTS / "layers"
AGG_ORDER = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
AGG_NAME = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
            "trojmiasto": "Trójmiasto", "gzm": "GZM"}
DOM_LABEL = {"core": "rdzeń", "covered": "obszar pokryty"}
GRID_LABEL = "GHSL 250 m przeskalowany do NSP 2021 (EPSG:2180)"
POP_DATE = "2021-03-31 (NSP 2021, wzór GHSL 2020)"
DAY = S.CFG["reference_day"]
SRC_SCHOOL = ("RSPO (rspo.gov.pl, stan 2026-11-24; licea, technika, branżowe I st. dla młodzieży, bez specjalnych); "
              "R5 v7.5.1 (r5py 1.1.7); GTFS wszystkie feedy; OSM 2026-11-22; ludność: NSP 2021 + GHSL 2020")
SRC_SOR = ("RPRM (rprm.ezdrowie.gov.pl, stan 2026-11-24; SOR aktywne, bez dziecięcych; położenie: adres dopasowany "
           "w OSM); R5 v7.5.1 (r5py 1.1.7); GTFS wszystkie feedy; OSM 2026-11-22; ludność: NSP 2021 + GHSL 2020")
SRC_AGE = "GUS NSP 2021, siatka 1 km (RES_0_14, RES_65_), rozdzielona na komórki 250 m (pipeline.agegrid)"
WIN = {"pt_am": "środa 7:00–9:00", "pt_evening": "środa 20:00–22:00"}
FLAG_MASK = "tylko komórki w masce pokrycia GTFS (§6); braki przewoźników w feedach zaniżają wynik"


def wshare(v: np.ndarray, w: np.ndarray, sel: np.ndarray) -> float | None:
    den = w[sel].sum()
    return None if den <= 0 else float(100.0 * w[sel & v].sum() / den)


def wmedian(t: np.ndarray, w: np.ndarray, sel: np.ndarray) -> float | None:
    """Population-weighted median minutes; null when more than half of the residents have no facility in 60 min."""
    m = sel & (w > 0)
    if w[m].sum() <= 0:
        return None
    tt = np.where(np.isfinite(t[m]), t[m], np.inf)
    o = np.argsort(tt, kind="stable")
    cw = np.cumsum(w[m][o]) / w[m].sum()
    v = tt[o][np.searchsorted(cw, 0.5)]
    return None if not np.isfinite(v) else float(v)


class Rows:
    def __init__(self):
        self.rows = []

    def add(self, agg, dom, metric, label, value, unit, src, tier, flag="", cov=None, day=DAY, grid="census"):
        self.rows.append({
            "agglomeration": agg, "domain": dom, "metric": metric, "label": label,
            "value": sig(value) if value is not None else None, "unit": unit,
            "grid": GRID_LABEL if grid == "census" else "GHSL 2020, 250 m (EPSG:2180)", "source": src,
            "population_date": POP_DATE if grid == "census" else "2020 (GHSL, model)", "timetable_date": day,
            "coverage_share": sig(cov) if cov is not None else None, "flag": flag or None, "tier": tier,
            "feed_variant": "all", "population_grid": "ghsl_census_scaled" if grid == "census" else "ghsl_raw"})


def coverage(agg: str) -> dict:
    o = AI.origins(agg)
    m = AI.mask(agg).set_index("cell_id").reindex(o["cell_id"])["in_mask_all"].fillna(False).astype(bool).to_numpy()
    w = o["w_census"].to_numpy()
    core = o["in_core"].to_numpy()
    return {"covered": float(w[m].sum() / w.sum()), "core": float(w[core & m].sum() / w[core].sum())}


def age_flag(diff: float, diff_c: float, lo: float, hi: float, allv: float) -> tuple[str, bool]:
    ok = abs(diff) >= 1.0 and np.sign(diff) == np.sign(diff_c)
    txt = (f"różnica względem wszystkich mieszkańców {diff:+.1f} pkt (wariant środka komórki {diff_c:+.1f}); "
           f"zakres przy skrajnym rozmieszczeniu grupy wewnątrz kwadratów 1 km: {lo:.1f}–{hi:.1f}")
    if not ok:
        txt = "nie do obrony przy tej dezagregacji (różnica < 1 pkt albo niezgodny znak wariantów); " + txt
    elif np.isfinite(lo) and not (lo <= allv <= hi):
        txt = "różnica odporna: utrzymuje się przy każdym rozmieszczeniu grupy wewnątrz kwadratów 1 km; " + txt
    return txt, ok


def service_rows(R: Rows, agg: str, d: pd.DataFrame, o: pd.DataFrame, age: pd.DataFrame, cov: dict) -> list[dict]:
    qa = []
    w = o["w_census"].to_numpy(np.float64)
    wr = o["w_raw"].to_numpy(np.float64)
    a = age.set_index("cell_id").reindex(o["cell_id"])
    wg = {"0_14": a["pop_0_14"].to_numpy(np.float64), "65": a["pop_65"].to_numpy(np.float64)}
    wc = {g: w * a[f"share_{g}_centroid"].to_numpy(np.float64) for g in wg}
    sq = a["census_idx"].fillna(-1).to_numpy().astype(np.int64)
    doms = {"covered": np.ones(len(o), bool), "core": o["in_core"].to_numpy()}
    spec = [
        ("school", "pt_am", (15, 20, 30, 45), "0_14", SRC_SCHOOL, "do najbliższej szkoły ponadpodstawowej"),
        ("sor", "pt_am", (30, 45), "65", SRC_SOR, "do najbliższego szpitalnego oddziału ratunkowego (SOR)"),
        ("sor", "pt_evening", (30, 45), "65", SRC_SOR, "do najbliższego szpitalnego oddziału ratunkowego (SOR)"),
    ]
    for dom, sel in doms.items():
        fl = FLAG_MASK if dom == "covered" else FLAG_MASK + "; rdzeń = komórki rdzenia w masce"
        for kind, scen, cuts, grp, src, what in spec:
            t = d[f"t_{kind}_{scen}"].to_numpy(np.float64)
            reach = np.isfinite(t)
            for c in cuts:
                v = reach & (t <= c)
                lab = (f"Mieszkańcy z czasem ≤ {c} min {what} komunikacją zbiorową z dojściem pieszym "
                       f"({WIN[scen]}, mediana z odjazdów co minutę, nie gorzej niż pieszo), % mieszkańców")
                tier = "main" if (kind == "school" and scen == "pt_am" and c in (20, 30)) or \
                                 (kind == "sor" and scen == "pt_am" and c in (30, 45)) else "table"
                val = wshare(v, w, sel)
                R.add(agg, dom, f"svc_{kind}_{scen}_le{c}min", lab, val, "%", src, tier, fl, cov[dom])
                R.add(agg, dom, f"svc_{kind}_{scen}_le{c}min_raw_ghsl", lab + " (surowy GHSL)", wshare(v, wr, sel),
                      "%", src, "qa", fl, cov[dom], grid="raw")
                # age group
                gv = wshare(v, np.nan_to_num(wg[grp]), sel)
                gvc = wshare(v, np.nan_to_num(wc[grp]), sel)
                lo, hi = age_bounds(v.astype(np.float64) * 100, w, wg[grp], sq, sel)
                txt, ok = age_flag(gv - val, gvc - val, lo, hi, val)
                glab = "0–14 lat" if grp == "0_14" else "65+ lat"
                R.add(agg, dom, f"svc_{kind}_{scen}_le{c}min_age{grp}",
                      lab.replace("% mieszkańców", f"% mieszkańców w wieku {glab}"), gv, "%",
                      src + "; wiek: " + SRC_AGE, "table", txt, cov[dom])
                qa.append({"agglomeration": agg, "domain": dom, "kind": kind, "scen": scen, "cut": c, "all": val,
                           "group": grp, "group_value": gv, "group_value_centroid": gvc, "bound_low": lo,
                           "bound_high": hi, "supported": ok, "robust": bool(ok and not (lo <= val <= hi))})
            none = ~reach
            lab = (f"Mieszkańcy bez {what.replace('do najbliższej ', '').replace('do najbliższego ', '')} w zasięgu "
                   f"60 min komunikacją zbiorową z dojściem pieszym ({WIN[scen]}), % mieszkańców")
            val = wshare(none, w, sel)
            R.add(agg, dom, f"svc_{kind}_{scen}_none60", lab, val, "%", src, "table", fl, cov[dom])
            gv = wshare(none, np.nan_to_num(wg[grp]), sel)
            R.add(agg, dom, f"svc_{kind}_{scen}_none60_age{grp}",
                  lab.replace("% mieszkańców", f"% mieszkańców w wieku {'0–14' if grp == '0_14' else '65+'} lat"), gv,
                  "%", src + "; wiek: " + SRC_AGE, "table", "", cov[dom])
            R.add(agg, dom, f"svc_{kind}_{scen}_median_min",
                  f"Mediana czasu {what} komunikacją zbiorową z dojściem pieszym ({WIN[scen]}), ważona ludnością; "
                  "brak, gdy ponad połowa mieszkańców nie ma takiego celu w 60 min", wmedian(t, w, sel), "min", src,
                  "table", fl, cov[dom])
        for kind, cuts, src, what in (("school", (15, 30), SRC_SCHOOL, "do najbliższej szkoły ponadpodstawowej"),
                                      ("sor", (30,), SRC_SOR, "do najbliższego SOR")):
            t = d[f"t_{kind}_walk"].to_numpy(np.float64)
            for c in cuts:
                R.add(agg, dom, f"svc_{kind}_walk_le{c}min",
                      f"Mieszkańcy z czasem ≤ {c} min {what} pieszo (5 km/h, po sieci OSM), % mieszkańców",
                      wshare(np.isfinite(t) & (t <= c), w, sel), "%", src.split("; GTFS")[0], "table", fl, cov[dom],
                      day=None)
    return qa


def age_bounds(m, p, g, sq, sel) -> tuple[float, float]:
    from pipeline.agegrid import bounds
    ok = sel & (sq >= 0) & np.isfinite(g) & (p > 0)
    gc = pd.Series(g[ok]).groupby(sq[ok]).sum()
    return bounds(m[ok], p[ok], gc, sq[ok])


def age_part1_rows(R: Rows) -> pd.DataFrame:
    """Rows for part 1 (frequent service and transit performance by age group) from agegrid.age_metrics."""
    t = pd.read_parquet(S.OUT / "age_metrics.parquet")
    out = []
    for (agg, dom, meas), g in t.groupby(["agglomeration", "domain", "measure"], sort=False):
        allr = g[g["group"] == "all"].iloc[0]
        for _, r in g[g["group"] != "all"].iterrows():
            glab = "0–14 lat" if r["group"] == "0_14" else "65+ lat"
            if meas.startswith("freq"):
                T = int(meas[7:9])
                lab = (f"Mieszkańcy w wieku {glab} ≤ 500 m (pieszo po sieci OSM) od przystanku z odstępem ≤ {T} min "
                       "w obu kierunkach (06:00–20:00, odcinek wspólny), % grupy")
                src = "GTFS wszystkie feedy (pipeline.frequent, definicja główna); OSM 2026-11-22; wiek: " + SRC_AGE
                pairs = [(f"age_{meas}_age{r['group']}", r["value"], r["value_centroid"], allr["value"],
                          r["bound_low"], r["bound_high"], lab, "%", "table")]
            else:
                lab = (f"Transport performance komunikacją zbiorową, 30 min (środa 7:00–9:00), mieszkańcy w wieku "
                       f"{glab}")
                src = "R5 v7.5.1 (r5py 1.1.7); GTFS wszystkie feedy; OSM 2026-11-22; wiek: " + SRC_AGE
                pairs = [(f"age_tp_pt_am_30min_age{r['group']}", r["ratio_of_means"], r["ratio_of_means_centroid"],
                          allr["ratio_of_means"], np.nan, np.nan, lab + ": stosunek średnich", "%", "table"),
                         (f"age_tp_pt_am_30min_age{r['group']}_mean_of_ratios", r["value"], r["value_centroid"],
                          allr["value"], r["bound_low"], r["bound_high"],
                          lab + ": średnia stosunków komórek ważona liczbą osób w grupie", "%", "table")]
            for metric, v, vc, va, lo, hi, lab_, unit, tier in pairs:
                if np.isfinite(lo):
                    txt, ok = age_flag(v - va, vc - va, lo, hi, va)
                else:
                    ok = abs(v - va) >= 1.0 and np.sign(v - va) == np.sign(vc - va)
                    txt = (f"różnica względem wszystkich mieszkańców {v - va:+.1f} pkt (wariant środka komórki "
                           f"{vc - va:+.1f})")
                    if not ok:
                        txt = "nie do obrony przy tej dezagregacji (różnica < 1 pkt albo niezgodny znak wariantów); " + txt
                if dom == "covered":
                    txt = FLAG_MASK + "; " + txt
                R.add(agg, dom, metric, lab_, v, unit, src, tier, txt, None,
                      day=DAY if "tp" in metric or "freq" in metric else None)
                out.append({"agglomeration": agg, "domain": dom, "metric": metric, "group": r["group"], "value": v,
                            "value_centroid": vc, "all": va, "diff": v - va, "bound_low": lo, "bound_high": hi,
                            "supported": ok, "robust": bool(ok and np.isfinite(lo) and not (lo <= va <= hi))})
    return pd.DataFrame(out)


def layer(frames: dict) -> pd.DataFrame:
    import shapely
    rows = []
    for agg, (d, o) in frames.items():
        lon, lat = o["lon"].to_numpy(), o["lat"].to_numpy()
        r = pd.DataFrame({"agglomeration": agg, "cell_id": o["cell_id"].to_numpy(),
                          "pop_census_scaled": o["w_census"].round(4).to_numpy(), "in_core": o["in_core"].to_numpy()})
        for c in ("t_school_pt_am", "t_school_walk", "t_sor_pt_am", "t_sor_pt_evening", "t_sor_walk"):
            r[c] = d[c].astype("Float32").to_numpy()
        r["geometry"] = shapely.to_wkb(shapely.points(lon, lat))
        rows.append(r)
    return pd.concat(rows, ignore_index=True)


def fac_counts() -> pd.DataFrame:
    f = pd.read_parquet(S.OUT / "facilities.parquet")
    rows = []
    for agg in AGG_ORDER:
        g = f[f["agglomeration"] == agg]
        for kind, sub in (("school", g[g["kind"] == "school"]), ("sor", g[g["kind"] == "sor"])):
            m = sub[sub["in_main"]]
            row = {"agglomeration": agg, "kind": kind, "main_region": int(len(m)), "main_fua": int(m["in_fua"].sum()),
                   "main_core": int(m["in_core"].sum()), "excluded_region": int((~sub["in_main"]).sum()),
                   "points_routed": int(len(S.facilities(agg)[1].query(kind)))}
            if kind == "school":
                for t, n in m["type"].value_counts().items():
                    row[f"fua_{t}"] = int(m.loc[m["type"] == t, "in_fua"].sum())
                row["students_fua"] = float(m.loc[m["in_fua"], "students"].sum())
            rows.append(row)
    return pd.DataFrame(rows)


def fmt(v, d=1) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "brak"
    return f"{v:.{d}f}".replace(".", ",")


def tables_md(m: pd.DataFrame, agep1: pd.DataFrame, fc: pd.DataFrame) -> str:
    """Markdown tables for results/qa/services/services.md (generated, pasted into the note)."""
    v = {(r.agglomeration, r.domain, r.metric): r.value for r in m.itertuples()}
    fl = {(r.agglomeration, r.domain, r.metric): r.flag for r in m.itertuples()}
    out = []
    # facilities
    out.append("| Aglomeracja | Szkoły w FUA + 15 km | w FUA | w rdzeniu | licea / technika / branżowe (FUA) | SOR w FUA + 15 km | w FUA | w rdzeniu |")
    out.append("|---|---|---|---|---|---|---|---|")
    for a in AGG_ORDER:
        s = fc[(fc.agglomeration == a) & (fc.kind == "school")].iloc[0]
        h = fc[(fc.agglomeration == a) & (fc.kind == "sor")].iloc[0]
        ty = " / ".join(str(int(s.get(f"fua_{t}", 0) or 0)) for t in
                        ("liceum ogólnokształcące", "technikum", "branżowa szkoła I stopnia"))
        out.append(f"| {AGG_NAME[a]} | {s.main_region} | {s.main_fua} | {s.main_core} | {ty} | {h.main_region} | "
                   f"{h.main_fua} | {h.main_core} |")
    out.append("")
    # schools
    out.append("| Aglomeracja | Obszar | ≤ 15 | ≤ 20 | ≤ 30 | ≤ 45 | bez szkoły w 60 min | mediana, min | pieszo ≤ 15 | pieszo ≤ 30 | 0–14: ≤ 20 | 0–14: ≤ 30 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for a in AGG_ORDER:
        for dom in ("covered", "core"):
            g = lambda k: v.get((a, dom, k))
            out.append(f"| {AGG_NAME[a] if dom == 'covered' else ''} | {DOM_LABEL[dom]} | "
                       + " | ".join(fmt(g(f"svc_school_pt_am_le{c}min")) for c in (15, 20, 30, 45))
                       + f" | {fmt(g('svc_school_pt_am_none60'))} | {fmt(g('svc_school_pt_am_median_min'), 0)} | "
                       f"{fmt(g('svc_school_walk_le15min'))} | {fmt(g('svc_school_walk_le30min'))} | "
                       f"{fmt(g('svc_school_pt_am_le20min_age0_14'))} | {fmt(g('svc_school_pt_am_le30min_age0_14'))} |")
    out.append("")
    # SOR
    out.append("| Aglomeracja | Obszar | 7–9: ≤ 30 | 7–9: ≤ 45 | 20–22: ≤ 30 | 20–22: ≤ 45 | bez SOR w 60 min, 7–9 | bez SOR w 60 min, 20–22 | mediana 7–9, min | pieszo ≤ 30 | 65+: ≤ 30 (7–9) | 65+: ≤ 45 (7–9) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for a in AGG_ORDER:
        for dom in ("covered", "core"):
            g = lambda k: v.get((a, dom, k))
            out.append(f"| {AGG_NAME[a] if dom == 'covered' else ''} | {DOM_LABEL[dom]} | "
                       f"{fmt(g('svc_sor_pt_am_le30min'))} | {fmt(g('svc_sor_pt_am_le45min'))} | "
                       f"{fmt(g('svc_sor_pt_evening_le30min'))} | {fmt(g('svc_sor_pt_evening_le45min'))} | "
                       f"{fmt(g('svc_sor_pt_am_none60'))} | {fmt(g('svc_sor_pt_evening_none60'))} | "
                       f"{fmt(g('svc_sor_pt_am_median_min'), 0)} | {fmt(g('svc_sor_walk_le30min'))} | "
                       f"{fmt(g('svc_sor_pt_am_le30min_age65'))} | {fmt(g('svc_sor_pt_am_le45min_age65'))} |")
    out.append("")
    # age part 1
    p = agep1.set_index(["agglomeration", "domain", "metric"])
    out.append("| Aglomeracja | Obszar | Kursy ≤ 10 min: wszyscy / 0–14 / 65+ | Kursy ≤ 20 min: wszyscy / 0–14 / 65+ | KZ 30, stosunek średnich: wszyscy / 0–14 / 65+ | KZ 30, średnia stosunków: wszyscy / 0–14 / 65+ |")
    out.append("|---|---|---|---|---|---|")

    for a in AGG_ORDER:
        for dom in ("covered", "core"):
            cells = []
            for stem in ("age_freq_le10min_age{g}", "age_freq_le20min_age{g}", "age_tp_pt_am_30min_age{g}",
                         "age_tp_pt_am_30min_age{g}_mean_of_ratios"):
                x = p.loc[(a, dom, stem.replace("{g}", "0_14"))]
                y = p.loc[(a, dom, stem.replace("{g}", "65"))]
                mk = lambda r: fmt(r["value"]) + ("" if r["supported"] else "*") + ("†" if r["robust"] else "")
                cells.append(f"{fmt(x['all'])} / {mk(x)} / {mk(y)}")
            out.append(f"| {AGG_NAME[a] if dom == 'covered' else ''} | {DOM_LABEL[dom]} | " + " | ".join(cells) + " |")
    out.append("")
    out.append("\\* różnica względem wszystkich mieszkańców nie do obrony przy tej dezagregacji (< 1 pkt albo niezgodny "
               "znak wariantu „środek komórki”); † różnica odporna: wartość dla wszystkich leży poza zakresem, jaki grupa "
               "mogłaby mieć przy dowolnym rozmieszczeniu wewnątrz kwadratów 1 km.")
    return "\n".join(out) + "\n"


def main() -> None:
    t0 = time.time()
    QA.mkdir(parents=True, exist_ok=True)
    age = pd.read_parquet(S.OUT / "age_cells.parquet")
    R = Rows()
    frames, qa, missing = {}, [], []
    for agg in AGG_ORDER:
        d = S.load(agg)
        if d is None:
            missing.append(agg)
            continue
        o = S.origins(agg)
        frames[agg] = (d, o)
        qa += service_rows(R, agg, d, o, age[age["agglomeration"] == agg], coverage(agg))
    agep1 = age_part1_rows(R)
    m = pd.DataFrame(R.rows)
    m["_a"] = m["agglomeration"].map({a: i for i, a in enumerate(AGG_ORDER)})
    m = m.sort_values(["_a", "domain", "metric"], kind="stable").drop(columns="_a").reset_index(drop=True)
    tmp = QA / "_tmp_meta"
    m.to_csv(METRICS / "metrics_services.csv", index=False, lineterminator="\n", encoding="utf-8")
    (METRICS / "metrics_services.json").write_text(json.dumps(json.loads(m.to_json(orient="records", force_ascii=False)),
                                                              ensure_ascii=False, indent=1), encoding="utf-8")
    pd.DataFrame(qa).to_csv(QA / "services_age_check.csv", index=False, lineterminator="\n")
    agep1.to_csv(QA / "age_part1.csv", index=False, lineterminator="\n")
    fc = fac_counts()
    fc.to_csv(QA / "facility_counts.csv", index=False, lineterminator="\n")
    if not missing:
        (QA / "tables.md").write_text(tables_md(m, agep1, fc), encoding="utf-8")
    if frames:
        lay = layer(frames)
        lay.to_parquet(LAYERS / "services_cells.parquet", index=False)
    extra = {"missing_agglomerations": missing, "reference_day": DAY,
             "sources": {"rspo": "data/raw/rspo_secondary/SOURCE.json", "rprm": "data/raw/rprm_sor/SOURCE.json",
                         "osm": "osm_poland_pbf", "census_age": "nsp2021_grid_1km_shp"},
             "note": ("travel time to nearest facility per covered origin cell (R5, min over facility points); "
                      "age groups from NSP 2021 1 km grid disaggregated to 250 m (pipeline.agegrid)")}
    inputs = ["nsp2021_grid_1km_shp", "osm_poland_pbf", "ghs_pop_2020_R3_C20", "ghs_pop_2020_R4_C20"]
    write_meta(QA, "services", inputs=inputs, started=t0, extra={**extra, "outputs": sorted(
        p.name for p in QA.iterdir() if p.name not in ("_meta.json", "_tmp_meta"))})
    write_meta(tmp, "services", inputs=inputs, started=t0,
               extra={**extra, "outputs": ["metrics_services.csv", "metrics_services.json"]})
    shutil.copyfile(tmp / "_meta.json", METRICS / "_meta_services.json")
    if frames:
        write_meta(tmp, "services", inputs=inputs, started=t0, extra={**extra, "files": {"services_cells.parquet": {
            "crs": "EPSG:4326", "geometry": "centre point of a 250 m EPSG:2180 cell (cell_id = E<x0>N<y0>)",
            "rows": "populated FUA cells inside the GTFS coverage mask (all feeds)",
            "t_*": "minutes to the nearest facility, null = none within 60 min; pt = median over departures each "
                   "minute in the window, never worse than walking"}}})
        shutil.copyfile(tmp / "_meta.json", LAYERS / "_meta_services.json")
    shutil.rmtree(tmp)
    write_json(QA / "summary.json", {"rows": int(len(m)), "missing": missing, "runtime_s": round(time.time() - t0, 1)})
    print(f"metrics_services: {len(m)} rows; missing {missing}")


if __name__ == "__main__":
    main()
