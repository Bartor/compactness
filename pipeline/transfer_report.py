"""Outputs of the transfer-ease step: layer, metrics, QA tables, Polish note, _meta files (pipeline.transfer_ease)."""
from __future__ import annotations

import csv
import shutil
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline import transfer_ease as T
from pipeline.boundaries import load_agglomeration
from pipeline.common import round_sig, sig, write_json, write_meta

NAMES = {a: T.CFG["agglomerations"][a]["name"] for a in T.AGGS}
TOPN = 20
WALK_EASY_MIN = 2.0
WALK_HARD_MIN = 5.0
COV_MIN = float(T.CFG["coverage_min_share"])

# Known interchanges: (agglomeration, label, lon, lat, name pattern).  The node chosen is the one with the most
# departures among nodes whose names match the pattern and whose centre is within KNOWN_RADIUS_M of the point.
KNOWN_RADIUS_M = 600.0
KNOWN = [
    ("warszawa", "Centrum", 21.0107, 52.2302, r"Centrum"),
    ("warszawa", "Dworzec Centralny", 21.0030, 52.2287, r"Centraln"),
    ("warszawa", "Dworzec Wileński", 21.0346, 52.2546, r"Wileński"),
    ("warszawa", "Dworzec Gdański", 20.9945, 52.2575, r"Gdański"),
    ("krakow", "Rondo Mogilskie", 19.9590, 50.0655, r"Mogilsk"),
    ("krakow", "Dworzec Główny Zachód (Basztowa, Pawia)", None, None, r"Dworzec Główny Zachód"),
    ("krakow", "Kraków Główny (kolej)", 19.9479, 50.0684, r"Kraków Główny"),
    ("krakow", "Rondo Grunwaldzkie", 19.9330, 50.0485, r"Grunwaldzk"),
    ("krakow", "Podgórze SKA", None, None, r"Podgórze SKA"),
    ("krakow", "Borek Fałęcki", 19.9290, 50.0115, r"Borek Fałęcki"),
    ("wroclaw", "Galeria Dominikańska", 17.0403, 51.1083, r"(?i)dominika"),
    ("wroclaw", "pl. Grunwaldzki", 17.0606, 51.1117, r"(?i)pl\. grunwaldzki"),
    ("wroclaw", "Dworzec Główny", 17.0365, 51.0985, r"(?i)dworzec główny|wrocław główny"),
    ("poznan", "Rondo Kaponiera", 16.9126, 52.4081, r"Kaponiera"),
    ("poznan", "Poznań Główny / Dworzec Zachodni", 16.9110, 52.4020, r"Poznań Główny|Dworzec Zachodni|Most Dworcowy"),
    ("poznan", "Rondo Rataje", 16.9535, 52.3935, r"Rataje"),
    ("lodz", "Piotrkowska Centrum", 19.4573, 51.7594, r"Piotrkowska Centrum"),
    ("lodz", "Łódź Fabryczna", 19.4700, 51.7700, r"Fabryczn"),
    ("lodz", "Łódź Kaliska", 19.4300, 51.7570, r"Kalisk"),
    ("trojmiasto", "Gdańsk Główny", 18.6440, 54.3556, r"Gdańsk Główny|Dworzec Główny|Brama Wyżynna"),
    ("trojmiasto", "Gdańsk Wrzeszcz", 18.6060, 54.3800, r"Wrzeszcz"),
    ("trojmiasto", "Gdynia Główna", 18.5268, 54.5218, r"Gdynia Główna|Dworzec"),
    ("gzm", "Katowice Rynek", 19.0216, 50.2594, r"Rynek"),
    ("gzm", "Katowice Dworzec", 19.0170, 50.2575, r"Katowice$|Dworzec|Katowice Dw"),
    ("gzm", "Sosnowiec Główny", 19.1290, 50.2780, r"Sosnowiec Główny|Dworzec PKP|Sosnowiec Dworzec"),
]

LAYER_COLS = [
    "node_id", "agglomeration", "name", "names_all", "cluster_ids", "n_stops", "n_clusters", "diameter_m", "modes",
    "has_rail_or_metro", "n_lines", "n_pairs", "n_pairs_walk", "n_pairs_parallel_excluded", "n_pairs_platform_unknown",
    "dep_per_h_day", "dep_per_h_am",
    "walk_min_median", "walk_min_p90", "walk_m_median", "detour_median", "same_stop_share",
    "walk_dir_min_median", "walk_dir_min_p90", "crossings_dir_median", "steps_dir_share", "stepfree_dir_share",
    "walkwait_dir_am_median", "n_pairs_dir",
    "crossings_median", "crossings_max", "crossings_signal_share", "crossings_value_share", "track_crossing_pair_share",
    "steps_pair_share", "tunnel_pair_share", "bridge_pair_share", "stepfree_pair_share", "stepfree_extra_min_median",
    "road_share_median", "wait_am_median", "wait_day_median", "walkwait_am_median", "walkwait_am_p90",
    "walkwait_day_median", "walkwait_am_median_w",
    "walk_w_am_min", "wait_w_am_min", "walkwait_w_am_min", "n_movements_am",
    "walk_w_day_min", "wait_w_day_min", "walkwait_w_day_min", "n_movements_day", "stops_mean_walk_m", "stops_mean_straight_m",
    *T.REVISION_COLS,
    "timed_pairs_checked", "timed_pairs", "rail_pair_share",
    "in_fua", "in_core", "in_mask", "flag",
]
COMPONENTS = [c for c in LAYER_COLS[LAYER_COLS.index("walk_min_median"):LAYER_COLS.index("in_fua")]]
# additive trios (walk, wait, total): node columns and city-summary keys
TRIOS = [("walk_w_am_min", "wait_w_am_min", "walkwait_w_am_min"),
         ("walk_w_day_min", "wait_w_day_min", "walkwait_w_day_min"),
         ("top_add_walk_am", "top_add_wait_am", "top_add_total_am"),
         ("top_add_walk_day", "top_add_wait_day", "top_add_total_day")]


def _dec(x) -> int:
    """Decimals that common.sig keeps for x at 4 significant digits (>= 0)."""
    if x is None or x == 0:
        return 0
    return max(0, 3 - int(np.floor(np.log10(abs(x)))))


def _missing(x) -> bool:
    return x is None or (isinstance(x, (float, np.floating)) and np.isnan(x))


def add_rounded(a, b):
    """Published total of an additive trio: the sum of the two parts rounded to 4 significant digits, so that
    part + part = total exactly in the published numbers.  None when a part is missing."""
    if _missing(a) or _missing(b):
        return None
    a, b = sig(float(a)), sig(float(b))
    return round(a + b, max(_dec(a), _dec(b)))


def fix_trios(df: pd.DataFrame) -> pd.DataFrame:
    """After 4-digit rounding: replace each trio total by the sum of its rounded parts."""
    for w, t, tot in TRIOS:
        if w in df.columns and t in df.columns and tot in df.columns:
            df[tot] = [add_rounded(a, b) for a, b in zip(df[w], df[t])]
    return df


def check_additive(nodes: pd.DataFrame, city: pd.DataFrame) -> dict:
    """Internal check (the step fails when it breaks): walk + wait = total for every node and every city row,
    (a) unrounded within 1e-9 min; (b) the published total equals the sum of the two published (4-digit) parts, and
    it differs from the unrounded total by no more than the sum of the parts' rounding errors (half a unit of each
    part's last digit).  ``max_dev_share`` = largest deviation as a share of that bound."""
    res = {}
    for name, df in (("nodes", nodes), ("city", city)):
        n = bad = bad_pub = 0
        maxdev = 0.0
        for w, t, tot in TRIOS:
            if w not in df.columns:
                continue
            for a, b, c in zip(df[w], df[t], df[tot]):
                if _missing(a) or _missing(b) or _missing(c):
                    if not (_missing(a) and _missing(b) and _missing(c)):
                        bad += 1
                    continue
                n += 1
                a, b, c = float(a), float(b), float(c)
                if abs(a + b - c) > 1e-9:
                    bad += 1
                pub = add_rounded(a, b)
                # rounding error of the published total = sum of the two parts' rounding errors (<= half a unit
                # of each part's last digit)
                bound = 0.5 * 10.0 ** (-_dec(sig(a))) + 0.5 * 10.0 ** (-_dec(sig(b)))
                dev = abs(pub - c)
                maxdev = max(maxdev, dev / bound)
                if abs(pub - (sig(a) + sig(b))) > 1e-9 or dev > bound * (1 + 1e-9):
                    bad_pub += 1
        res[name] = {"checked": n, "failed_unrounded": bad, "failed_published": bad_pub,
                     "max_dev_share": round(maxdev, 3)}
    if any(v["failed_unrounded"] or v["failed_published"] for v in res.values()):
        raise SystemExit(f"transfer_ease: additive check failed: {res}")
    return res


def _pl(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "brak danych"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _known_pick(nt: pd.DataFrame, agg: str, lon, lat, pat: str):
    c = nt[(nt.agglomeration == agg) & nt.names_all.str.contains(pat, regex=True, na=False)]
    if lon is not None and len(c):
        x, y = T.TO2180.transform(lon, lat)
        c = c[np.hypot(c.x - x, c.y - y) <= KNOWN_RADIUS_M]
    if c.empty:
        return None
    return c.sort_values(["dep_per_h_day", "node_id"], ascending=[False, True]).iloc[0]


def build_tables(results: list[dict]) -> dict:
    out = {"nodes": {}, "geo": {}}
    for R in results:
        agg = R["agg"]
        geo = load_agglomeration(agg)
        mask = T.mask_geom(agg)
        for rn in T.RULES:
            nt = T.node_table(R, rn, geo, mask)
            nt["has_rail_or_metro"] = nt.modes.str.contains("rail|metro", regex=True)
            fl = []
            for r in nt.itertuples():
                f = []
                if not r.in_mask:
                    f.append("poza maską pokrycia GTFS: brak danych")
                if r.n_pairs_platform_unknown > 0:
                    f.append("kolej/metro: perony nierozróżnione w GTFS, przejście między pociągami nieznane")
                if r.has_rail_or_metro:
                    f.append("stacja: dojście do punktu stacji z GTFS, nie do konkretnego peronu")
                if r.road_share_median is not None and r.road_share_median > 0.5:
                    f.append("ścieżka głównie po osi jezdni w OSM: przejścia mogą być niepoliczone")
                fl.append("; ".join(f))
            nt["flag"] = fl
            # outside the mask: components are no data
            out_m = ~nt.in_mask.to_numpy()
            for c in COMPONENTS:
                nt[c] = nt[c].astype(object)
                nt.loc[out_m, c] = None
            out["nodes"].setdefault(rn, []).append(nt)
    for rn in T.RULES:
        out["nodes"][rn] = pd.concat(out["nodes"][rn], ignore_index=True)
    return out


def _wmean(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = np.isfinite(x) & (w > 0)
    return float((x[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else None


def _mean(s: pd.Series):
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.mean()) if len(x) else None


def _median(s: pd.Series):
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.median()) if len(x) else None


def revision_values(top: pd.DataFrame, d: pd.DataFrame, v: dict, extra: dict | None) -> dict:
    """City values of the review revisions: top-20 node means / medians and pooled movement values of the area."""
    out = {"top_conn_w_am": _mean(top.conn_wait_w_am_min), "top_conn_delta_am": _mean(top.conn_delta_w_am_min),
           "top_conn_med_am": _median(top.conn_wait_am_median), "top_conn_p90_am": _median(top.conn_wait_am_p90),
           "top_w6_hi": _mean(top.w6_hi_mean), "top_w6_lo": _mean(top.w6_lo_mean)}
    for k in ("low", "central", "high"):
        out[f"top_gtt_{k}_am"] = T.gtt(v.get("top_add_walk_am"), v.get("top_add_wait_am"), k)
    keys = ("w6_hi", "w6_lo", "w6_scored_share", "crossings_grade_share", "freq10_share", "freq15_share",
            "top_freq10_share", "top_freq15_share", "movements_n", "timed15_n", "timed15_top10_share",
            "timed15_candidates", "x_grade", "x_signal", "x_zebra", "x_unmarked", "x_unknown")
    out.update({k: None for k in keys})
    if not extra:
        return out
    mv = extra["mv"]
    m = mv[mv.area.isin(set(d.area))] if len(mv) else mv
    out["movements_n"] = int(len(m))
    if len(m):
        sc = m[m.w6_n > 0]
        out["w6_hi"] = _wmean(sc.w6_hi_sum / sc.w6_n, sc.weight) if len(sc) else None
        out["w6_lo"] = _wmean(sc.w6_lo_sum / sc.w6_n, sc.weight) if len(sc) else None
        cnt = {c: float(m[f"x_{c}"].sum()) for c in ("grade", "signal", "zebra", "unmarked", "unknown")}
        tot = sum(cnt.values())
        out.update({f"x_{c}": int(cnt[c]) for c in cnt})
        if tot > 0:
            out["w6_scored_share"] = (1 - cnt["unknown"] / tot) * 100
            out["crossings_grade_share"] = cnt["grade"] / tot * 100
        win_min = (T.WIN_AM[1] - T.WIN_AM[0]) / 60
        mt = m[m.area.isin(set(top.area))]
        for h, col in zip(T.FREQ_HEADWAYS, ("freq10_share", "freq15_share")):
            need = win_min / h - 1e-9
            f = (m.n_a_am >= need) & (m.n_b_am >= need)
            out[col] = float(f.mean() * 100)
            ft = (mt.n_a_am >= need) & (mt.n_b_am >= need)
            out[f"top_{col}"] = float(ft.mean() * 100) if len(mt) else None
    tm = extra["timed"]
    tm = tm[tm.area.isin(set(d.area)) & tm.both_infrequent.astype(bool)] if len(tm) else tm
    out["timed15_n"] = int(len(tm))
    if len(tm):
        out["timed15_top10_share"] = float((tm["rank"] <= 0.1).mean() * 100)
        out["timed15_candidates"] = int(tm.timed.sum())
    return out


def city_values(nt: pd.DataFrame, pairs_by_agg: dict, agg: str, dom: str, extra: dict | None = None) -> dict:
    n = nt[(nt.agglomeration == agg)]
    base = n[n.in_core] if dom == "core" else n[n.in_fua]
    cov = (base.loc[base.in_mask, "dep_per_h_day"].sum() / base.dep_per_h_day.sum()) if base.dep_per_h_day.sum() > 0 else None
    d = base[base.in_mask]
    w = d[d.walk_min_median.notna()]
    tot = w.dep_per_h_day.sum()
    v = {"coverage": cov, "nodes_n": int(len(d))}
    v["dep_share_walk_le2"] = float(w.loc[w.walk_min_median.astype(float) <= WALK_EASY_MIN, "dep_per_h_day"].sum() / tot * 100) if tot > 0 else None
    wd = d[d.walk_dir_min_median.notna()]
    td = wd.dep_per_h_day.sum()
    v["dep_share_walkdir_le2"] = float(wd.loc[wd.walk_dir_min_median.astype(float) <= WALK_EASY_MIN, "dep_per_h_day"].sum() / td * 100) if td > 0 else None
    v["dep_share_walkdir_gt5"] = float(wd.loc[wd.walk_dir_min_median.astype(float) > WALK_HARD_MIN, "dep_per_h_day"].sum() / td * 100) if td > 0 else None
    v["dep_share_walk_gt5"] = float(w.loc[w.walk_min_median.astype(float) > WALK_HARD_MIN, "dep_per_h_day"].sum() / tot * 100) if tot > 0 else None
    top = d.sort_values(["dep_per_h_day", "node_id"], ascending=[False, True]).head(TOPN)
    v["top_n"] = int(len(top))
    for k, c in (("top_walk", "walk_min_median"), ("top_ww_am", "walkwait_am_median"),
                 ("top_ww_day", "walkwait_day_median"), ("top_cross", "crossings_median"),
                 ("top_wait_am", "wait_am_median"), ("top_walk_dir", "walk_dir_min_median"),
                 ("top_ww_dir_am", "walkwait_dir_am_median"), ("top_cross_dir", "crossings_dir_median"),
                 ("top_ww_am_w", "walkwait_am_median_w")):
        x = pd.to_numeric(top[c], errors="coerce").dropna()
        v[k] = float(x.median()) if len(x) else None
    for win in ("am", "day"):
        cols = [f"walk_w_{win}_min", f"wait_w_{win}_min", f"walkwait_w_{win}_min"]
        tt = top[cols].apply(pd.to_numeric, errors="coerce").dropna()
        for k, c in zip(("walk", "wait", "total"), cols):
            v[f"top_add_{k}_{win}"] = float(tt[c].mean()) if len(tt) else None
        v[f"top_add_n_{win}"] = int(len(tt))
    P = pairs_by_agg[agg]
    P = P[~P.parallel & P.walk_m.notna()] if len(P) else P
    pt = P[P.area.isin(set(top.area))]
    v["top_stepfree_share"] = float(pt.stepfree_m.notna().mean() * 100) if len(pt) else None
    v["top_steps_share"] = float(pt.steps.astype(bool).mean() * 100) if len(pt) else None
    pa = P[P.area.isin(set(d.area))]
    v["same_stop_share"] = float(pa.same_stop.mean() * 100) if len(pa) else None
    nx = pa.crossings.sum() if len(pa) else 0
    v["crossing_value_share"] = float(pa.crossings_value.sum() / nx * 100) if nx > 0 else None
    v["crossing_signal_share"] = float(pa.crossings_signal.sum() / nx * 100) if nx > 0 else None
    v["road_share"] = float((pa.road_m.sum() / pa.len_m.sum()) * 100) if len(pa) and pa.len_m.sum() > 0 else None
    v["pairs_n"] = int(len(pa))
    v.update(revision_values(top, d, v, extra))
    return v


METRIC_SPEC = [
    # id, key, unit, tier, label
    ("transfer_dep_share_walkdir_le2min", "dep_share_walkdir_le2", "%", "main",
     "Odjazdy w zespołach przesiadkowych, w których mediana dojścia między liniami (z uwzględnieniem kierunków jazdy) "
     "wynosi ≤ 2 min; udział odjazdów 6–20 we wszystkich zespołach przesiadkowych obszaru"),
    ("transfer_top20_walkwait_w_am_mean_min", "top_add_total_am", "min", "main",
     "20 zespołów z największą liczbą odjazdów: typowa przesiadka 7–9, dojście + czekanie (średnia ważona liczbą "
     "kursów w zespole, potem średnia po zespołach); równa sumie składowych transfer_top20_walk_w_am_mean_min "
     "i transfer_top20_wait_w_am_mean_min"),
    ("transfer_top20_walk_w_am_mean_min", "top_add_walk_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: dojście między liniami z kierunkami, 7–9 (średnia ważona liczbą "
     "kursów, potem średnia po zespołach); składowa, która z czekaniem sumuje się do transfer_top20_walkwait_w_am_mean_min"),
    ("transfer_top20_wait_w_am_mean_min", "top_add_wait_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: oczekiwane czekanie na linię docelową w jej kierunku, 7–9 (średnia "
     "ważona liczbą kursów, potem średnia po zespołach); składowa, która z dojściem sumuje się do "
     "transfer_top20_walkwait_w_am_mean_min"),
    ("transfer_top20_walkwait_w_day_mean_min", "top_add_total_day", "min", "table",
     "20 zespołów z największą liczbą odjazdów: typowa przesiadka 6–20, dojście + czekanie (średnia ważona liczbą "
     "kursów, potem średnia po zespołach); równa sumie składowych transfer_top20_walk_w_day_mean_min "
     "i transfer_top20_wait_w_day_mean_min"),
    ("transfer_top20_walk_w_day_mean_min", "top_add_walk_day", "min", "table",
     "20 zespołów z największą liczbą odjazdów: dojście z kierunkami, ruchy z czekaniem 6–20 (średnia ważona liczbą "
     "kursów, potem średnia po zespołach); składowa sumy 6–20"),
    ("transfer_top20_wait_w_day_mean_min", "top_add_wait_day", "min", "table",
     "20 zespołów z największą liczbą odjazdów: oczekiwane czekanie na linię docelową w jej kierunku, 6–20 (średnia "
     "ważona liczbą kursów, potem średnia po zespołach); składowa sumy 6–20"),
    ("transfer_top20_walkwait_dir_am_median_min", "top_ww_dir_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana (po zespołach) mediany dojścia (z kierunkami) + oczekiwanego "
     "czekania, 7–9 (mediana; nie równa się sumie median dojścia i czekania)"),
    ("transfer_top20_walk_dir_median_min", "top_walk_dir", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana dojścia między liniami z uwzględnieniem kierunków jazdy "
     "(sieć piesza OSM, 5 km/h) (mediana; mediany składowych nie sumują się)"),
    ("transfer_top20_crossings_dir_median", "top_cross_dir", "przejść", "table",
     "20 zespołów z największą liczbą odjazdów: mediana liczby przejść przez jezdnię lub torowisko na dojściu "
     "(z kierunkami) (mediana; mediany składowych nie sumują się)"),
    ("transfer_top20_wait_am_median_min", "top_wait_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana oczekiwanego czekania na linię docelową, 7–9 (mediana; mediany składowych nie sumują się)"),
    ("transfer_top20_walkwait_am_median_w_min", "top_ww_am_w", "min", "table",
     "20 zespołów z największą liczbą odjazdów: dojście (najlepsza para słupków) + czekanie 7–9, mediana ważona "
     "liczbą kursów pary linii (mediana; mediany składowych nie sumują się)"),
    ("transfer_dep_share_walk_le2min", "dep_share_walk_le2", "%", "table",
     "Odjazdy w zespołach, w których mediana dojścia między liniami przy najlepszej parze słupków (bez kierunków) "
     "wynosi ≤ 2 min; udział odjazdów 6–20"),
    ("transfer_top20_walk_median_min", "top_walk", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana dojścia przy najlepszej parze słupków (bez kierunków) (mediana; mediany składowych nie sumują się)"),
    ("transfer_top20_walkwait_am_median_min", "top_ww_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: dojście (najlepsza para słupków) + oczekiwane czekanie 7–9, mediana (mediana; mediany składowych nie sumują się)"),
    ("transfer_top20_stepfree_pair_share", "top_stepfree_share", "%", "table",
     "20 zespołów z największą liczbą odjazdów: odsetek par linii z dojściem bez schodów znalezionym w sieci OSM"),
    ("transfer_dep_share_walkdir_gt5min", "dep_share_walkdir_gt5", "%", "table",
     "Odjazdy w zespołach z medianą dojścia (z kierunkami) > 5 min; udział odjazdów 6–20"),
    ("transfer_same_stop_pair_share", "same_stop_share", "%", "table",
     "Pary linii, dla których najlepsza para słupków to ten sam słupek"),
    ("transfer_nodes_n", "nodes_n", "zespołów", "table",
     "Liczba zespołów przystanków z co najmniej jedną parą linii do przesiadki"),
    # revisions after the literature review (2026-11-24, code version .3)
    ("transfer_top20_connwait_w_am_mean_min", "top_conn_w_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: czekanie po rzeczywistym przyjeździe linii dowożącej i dojściu, 7–9 "
     "(średnia ważona liczbą kursów, potem średnia po zespołach); obok oczekiwanego czekania przy losowym przyjściu "
     "(transfer_top20_wait_w_am_mean_min), nie zamiast niego"),
    ("transfer_top20_connwait_am_median_min", "top_conn_med_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: mediana czekania na przesiadkę po rzeczywistym przyjeździe, 7–9 "
     "(ważona mediana zespołu, potem mediana po zespołach)"),
    ("transfer_top20_connwait_am_p90_min", "top_conn_p90_am", "min", "table",
     "20 zespołów z największą liczbą odjazdów: 90. percentyl czekania na przesiadkę po rzeczywistym przyjeździe, "
     "7–9 (ważony percentyl zespołu, potem mediana po zespołach)"),
    ("transfer_top20_gtt_low_am_min", "top_gtt_low_am", "min równoważnych", "table",
     "20 zespołów z największą liczbą odjazdów: uogólniony czas przesiadki 7–9, wariant niski: dojście × 1,2 + "
     "czekanie × 1,47 + 5 min, w minutach równoważnych jeździe (wagi z literatury; nie do rankingu węzłów)"),
    ("transfer_top20_gtt_central_am_min", "top_gtt_central_am", "min równoważnych", "table",
     "20 zespołów z największą liczbą odjazdów: uogólniony czas przesiadki 7–9, wariant środkowy: dojście × 1,66 + "
     "czekanie × 1,47 + 13 min (Wardman 1998; Jara-Díaz i in. 2022); nie do rankingu węzłów"),
    ("transfer_top20_gtt_high_am_min", "top_gtt_high_am", "min równoważnych", "table",
     "20 zespołów z największą liczbą odjazdów: uogólniony czas przesiadki 7–9, wariant wysoki: dojście × 1,66 + "
     "czekanie × 1,47 + 18 min; nie do rankingu węzłów"),
    ("transfer_crossing_w6_hi_mean_pct", "w6_hi", "%", "table",
     "Bezpieczeństwo przejść na dojściach w skali AMPTI W6 (bezkolizyjne 100, z sygnalizacją 70, zebra 30, "
     "niewyznakowane 0): średnia po ruchach przesiadkowych ważona liczbą kursów; sygnalizacja liczona jako 70 "
     "(bez kolizji ze skrętami)"),
    ("transfer_crossing_w6_lo_mean_pct", "w6_lo", "%", "table",
     "To samo, sygnalizacja liczona jako 50 (z kolizjami ze skrętami); OSM nie mówi, który przypadek zachodzi"),
    ("transfer_crossing_w6_scored_share", "w6_scored_share", "%", "qa",
     "Kontrola danych OSM: odsetek przejść na dojściach, którym tagi OSM pozwalają nadać klasę W6"),
    ("transfer_movements_freq10_share", "freq10_share", "%", "table",
     "Ruchy przesiadkowe, w których obie linie (przyjazdowa w swoim kierunku i odjazdowa w swoim) kursują w "
     "godzinach 7–9 średnio co 10 min lub częściej; odsetek ruchów"),
    ("transfer_movements_freq15_share", "freq15_share", "%", "table",
     "To samo dla progu 15 min"),
    ("transfer_timed_both15_top10_share", "timed15_top10_share", "%", "qa",
     "Test skomunikowań ograniczony do par, w których obie linie kursują średnio co 15 min lub rzadziej (6–20): "
     "odsetek par w najlepszych 10 % przesunięć rozkładu (bez koordynacji ok. 10 %)"),
    ("transfer_osm_crossing_value_share", "crossing_value_share", "%", "qa",
     "Kontrola danych OSM: odsetek przejść na policzonych dojściach z wartością crossing=* lub sygnalizacją"),
    ("transfer_osm_road_centerline_share", "road_share", "%", "qa",
     "Kontrola danych OSM: odsetek długości dojść prowadzonych osią jezdni (chodniki niezmapowane osobno)"),
]


def metric_rows(nodes: pd.DataFrame, pairs_by_agg: dict, extra_by_agg: dict | None = None) -> list[dict]:
    rows = []
    src = (f"GTFS (feedy wg config.yaml, wariant wszystkie feedy, dzień {T.DAY}, warstwa usług pipeline.gtfs_service); "
           "OSM 2026-11-22 (sieć piesza pipeline.walk_network, tagi przejść); bez danych o ludności")
    for agg in T.AGGS:
        for dom in ("core", "covered"):
            v = city_values(nodes, pairs_by_agg, agg, dom, (extra_by_agg or {}).get(agg))
            cov = v["coverage"]
            for mid, key, unit, tier, label in METRIC_SPEC:
                flag = []
                if dom == "core" and cov is not None and cov < COV_MIN:
                    flag.append(f"niepełne pokrycie GTFS: {cov * 100:.1f} % odjazdów w zespołach przesiadkowych rdzenia w masce")
                if dom == "covered":
                    flag.append("tylko zespoły w masce pokrycia GTFS; coverage_share = udział odjazdów zespołów FUA w masce")
                if key.startswith("top") and v["top_n"] < TOPN:
                    flag.append(f"tylko {v['top_n']} zespołów w obszarze")
                if key.startswith("top_add_"):
                    na = v[f"top_add_n_{key.rsplit('_', 1)[1]}"]
                    if na < v["top_n"]:
                        flag.append(f"średnia z {na} zespołów; pozostałe nie mają ruchu z dojściem i czekaniem w oknie")
                flag.append("miara własna, nie AMPTI; składowe podawane osobno")
                val = v[key]
                if key.startswith("top_add_total_"):
                    win = key.rsplit("_", 1)[1]
                    pub = add_rounded(v[f"top_add_walk_{win}"], v[f"top_add_wait_{win}"])
                else:
                    pub = sig(val) if val is not None else None
                rows.append({"agglomeration": agg, "domain": dom, "metric": mid, "label": label,
                             "value": pub, "unit": unit, "grid": None,
                             "source": src, "population_date": None, "timetable_date": T.DAY,
                             "coverage_share": sig(cov) if cov is not None else None, "flag": "; ".join(flag),
                             "tier": tier, "feed_variant": T.VARIANT, "population_grid": None})
    return rows


FIELDS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
          "timetable_date", "coverage_share", "flag", "tier", "feed_variant", "population_grid"]


def write_metrics(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda m: (m["agglomeration"], m["feed_variant"], m["domain"], m["metric"]))
    T.METRICS.mkdir(parents=True, exist_ok=True)
    write_json(T.METRICS / "metrics_transfer.json", {"generated_for_timetable_date": T.DAY, "metrics": rows})
    with open(T.METRICS / "metrics_transfer.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for m in rows:
            w.writerow({k: ("" if m[k] is None else m[k]) for k in FIELDS})


def _round_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f" or df[c].dtype == object:
            df[c] = [sig(x) if isinstance(x, (float, np.floating)) else x for x in df[c]]
    return fix_trios(df)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _round_df(df).to_csv(path, index=False, lineterminator="\n")


def write_layer(nodes: pd.DataFrame) -> int:
    n = nodes[nodes.in_fua].copy()
    lon, lat = T.TO4326.transform(n.x.to_numpy(), n.y.to_numpy())
    n = n[LAYER_COLS].reset_index(drop=True)
    n = _round_df(n)
    for c in COMPONENTS:
        n[c] = pd.to_numeric(n[c], errors="coerce")
    n = n.sort_values(["agglomeration", "node_id"]).reset_index(drop=True)
    g = gpd.GeoDataFrame(n, geometry=gpd.points_from_xy(np.round(lon, 6), np.round(lat, 6)), crs="EPSG:4326")
    # keep the geometry aligned to the sorted rows
    order = nodes[nodes.in_fua].reset_index(drop=True)
    order = order.assign(lon=np.round(lon, 6), lat=np.round(lat, 6)).set_index("node_id").reindex(n.node_id)
    g = gpd.GeoDataFrame(n, geometry=gpd.points_from_xy(order.lon.to_numpy(), order.lat.to_numpy()), crs="EPSG:4326")
    T.LAYERS.mkdir(parents=True, exist_ok=True)
    g.to_parquet(T.LAYERS / "transfer_nodes.parquet", index=False)
    return len(g)


def write_all(results: list[dict], t0: float) -> None:
    from pipeline.transfer_md import write_md
    tabs = build_tables(results)
    pairs = {rn: {R["agg"]: R["rules"][rn]["pairs"] for R in results} for rn in T.RULES}
    main = tabs["nodes"]["main"]
    extra = {rn: {R["agg"]: {"mv": R["rules"][rn]["movements"], "timed": R["rules"][rn]["timed"]} for R in results}
             for rn in T.RULES}
    rows = metric_rows(main, pairs["main"], extra["main"])
    write_metrics(rows)
    n_layer = write_layer(main)
    T.QA.mkdir(parents=True, exist_ok=True)
    # known interchanges, each rule
    kn = []
    for agg, label, lon, lat, pat in KNOWN:
        for rn in T.RULES:
            r = _known_pick(tabs["nodes"][rn], agg, lon, lat, pat)
            rec = {"agglomeration": agg, "interchange": label, "rule": rn}
            if r is not None:
                rec.update({c: r[c] for c in ["node_id", "name", "names_all", "n_stops", "n_clusters", "diameter_m",
                                              "modes", "n_lines", "n_pairs", "n_pairs_platform_unknown",
                                              "dep_per_h_day", "dep_per_h_am"] + COMPONENTS[:-1] + ["in_mask", "flag"]})
            kn.append(rec)
    kn = pd.DataFrame(kn)
    write_csv(kn[kn.rule == "main"].drop(columns="rule"), T.QA / "known_interchanges.csv")
    write_csv(kn, T.QA / "known_interchanges_rules.csv")
    # pairs at the known interchanges (main rule)
    lines = pd.concat([R["lines"] for R in results]).drop_duplicates("line").set_index("line")
    pk = []
    for _, r in kn[(kn.rule == "main") & kn.node_id.notna()].iterrows():
        area = int(main.loc[main.node_id == r.node_id, "area"].iloc[0])
        p = pairs["main"][r.agglomeration]
        p = p[(p.area == area) & ~p.parallel].copy()
        p.insert(0, "node_id", r.node_id)
        p["label_a"] = p.line_a.map(lines.label); p["label_b"] = p.line_b.map(lines.label)
        p["walk_min"] = p.walk_m / T.M_PER_MIN
        pk.append(p.drop(columns=["area", "parallel"]))
    pk = pd.concat(pk, ignore_index=True).sort_values(["node_id", "line_a", "line_b"])
    write_csv(pk, T.QA / "pairs_known_interchanges.csv")
    # city summaries for every rule
    cs = []
    for rn in T.RULES:
        for agg in T.AGGS:
            for dom in ("core", "covered"):
                v = city_values(tabs["nodes"][rn], pairs[rn], agg, dom, extra[rn][agg])
                cs.append({"rule": rn, "agglomeration": agg, "domain": dom, **v})
    cs = pd.DataFrame(cs)
    write_csv(cs, T.QA / "city_summary_rules.csv")
    # OSM tag completeness per city
    ot = []
    for R in results:
        c = R["census"]
        v = city_values(main, pairs["main"], R["agg"], "covered", extra["main"][R["agg"]])
        xs = {k: v[f"x_{k}"] or 0 for k in ("grade", "signal", "zebra", "unmarked", "unknown")}
        xt = sum(xs.values())
        ot.append({"agglomeration": R["agg"], **c,
                   "share_footway_road_nodes_tagged": c["footway_road_nodes_tagged"] / c["footway_road_nodes"] * 100,
                   "share_footway_road_nodes_with_value": c["footway_road_nodes_with_value"] / c["footway_road_nodes"] * 100,
                   "share_highway_crossing_with_value": c["highway_crossing_nodes_with_crossing_value"] / c["highway_crossing_nodes"] * 100,
                   "paths_crossing_value_share": v["crossing_value_share"], "paths_crossing_signal_share": v["crossing_signal_share"],
                   "paths_road_centerline_share": v["road_share"],
                   "share_elevator_dead_end": c["elevator_nodes_dead_end"] / c["elevator_nodes"] * 100
                   if c["elevator_nodes"] else None,
                   "share_footway_road_nodes_w6_class": c["footway_road_nodes_w6_class"] / c["footway_road_nodes"] * 100,
                   "paths_w6_scored_share": v["w6_scored_share"], "paths_crossings_n": xt,
                   **{f"paths_x_{k}_share": (xs[k] / xt * 100 if xt else None) for k in xs}})
    ot = pd.DataFrame(ot)
    write_csv(ot, T.QA / "osm_tag_completeness.csv")
    # timed connections
    tm = []
    for R in results:
        t = R["rules"]["main"]["timed"]
        if len(t):
            t = t.copy(); t.insert(0, "agglomeration", R["agg"])
            nid = main[main.agglomeration == R["agg"]].set_index("area").node_id
            t.insert(1, "node_id", t.area.map(nid))
            tm.append(t[t.timed].drop(columns=["area"]))
    tm = pd.concat(tm, ignore_index=True).dropna(subset=["node_id"]).sort_values(["agglomeration", "node_id", "line_a", "line_b"])
    write_csv(tm, T.QA / "timed_connections_possible.csv")
    # top nodes per city (main)
    top = (main[main.in_mask].sort_values(["agglomeration", "dep_per_h_day", "node_id"], ascending=[True, False, True])
           .groupby("agglomeration").head(TOPN))
    write_csv(top[["agglomeration", "node_id", "name", "n_stops", "diameter_m", "modes", "n_lines", "n_pairs",
                   "dep_per_h_day"] + COMPONENTS[:-1] + ["flag"]], T.QA / "top_nodes.csv")
    rev = write_revision_tables(results, main)
    secs = {R["agg"]: round(R["seconds"], 1) for R in results}
    add_check = check_additive(main, cs)
    from pipeline.transfer_detail import write_detail
    detail = write_detail(results, main)
    ctx = {"rev": rev, "detail": detail, "additive_check": add_check, "tabs": tabs, "known": kn, "pairs_known": pk, "city": cs, "osm": ot, "timed": tm, "top": top,
           "rows": rows, "n_layer": n_layer, "seconds": secs, "results": results}
    write_md(ctx)
    # _meta files
    inputs = ["osm_poland_pbf"] + sorted({f"gtfs_{f}" for a in T.AGGS for f in T.gs.feeds_for(a, T.VARIANT)})
    extra = {"code_version": T.CODE_VERSION, "timetable_date": T.DAY, "feed_variant": T.VARIANT,
             "additive_check": add_check,
             "osm_date": "2026-11-22", "rules": T.RULES, "params": params(), "seconds_per_agglomeration": secs}
    write_meta(T.QA, "transfer_ease", inputs=inputs, started=t0,
               extra={**extra, "outputs": sorted(p.name for p in T.QA.iterdir() if p.name != "_meta.json")})
    tmp = Path(tempfile.mkdtemp())
    for folder, outs in ((T.METRICS, ["metrics_transfer.csv", "metrics_transfer.json"]),
                         (T.LAYERS, ["transfer_nodes.parquet"])):
        ex = {**extra, "outputs": outs}
        if folder == T.LAYERS:
            ex["files"] = {"transfer_nodes.parquet": {
                "crs": "EPSG:4326", "geometry": "mean position of the member stops of the stop area",
                "rows": "stop areas inside the FUA with at least one counted transfer pair (main area rule)",
                "null": "no data (outside the GTFS coverage mask, or no measurable pair); never 0 for missing"}}
        write_meta(tmp, "transfer_ease", inputs=inputs, started=t0, extra=ex)
        shutil.copyfile(tmp / "_meta.json", folder / "_meta_transfer.json")
    shutil.rmtree(tmp, ignore_errors=True)


def _binom_p(k: int, n: int, p: float = 0.1) -> float | None:
    """One-sided binomial p-value P(X >= k) for X ~ Bin(n, p)."""
    if n <= 0:
        return None
    from scipy.stats import binom
    return float(binom.sf(k - 1, n, p))


def _share_row(g: pd.DataFrame) -> dict:
    k, n = int((g["rank"] <= 0.1).sum()), int(len(g))
    return {"pairs": n, "top10": k, "top10_share": k / n * 100, "p_value": _binom_p(k, n),
            "candidates": int(g.timed.sum()), "obs_wait_mean": float(g.obs_wait.mean()),
            "rand_wait_mean": float(g.rand_wait.mean())}


def write_revision_tables(results: list[dict], main: pd.DataFrame) -> dict:
    """QA tables of the coordination test revisions: pairs where both lines run every >= 15 min (per city and mode
    pair, per node), the night-window positive control, and the node pulse test.  Returns what the note needs."""
    mp, nodes15, night, pulse = [], [], [], []
    for R in results:
        agg = R["agg"]
        rr = R["rules"]["main"]
        nt = main[main.agglomeration == agg].set_index("area")
        names = rr["stops"].groupby("area").stop_name.first()

        def name_of(a):
            return nt["name"].get(a) if a in nt.index else names.get(a)
        d_areas = set(nt.index[nt.in_mask & nt.in_fua])
        t = rr["timed"]
        t = t[t.both_infrequent.astype(bool) & t.area.isin(d_areas)] if len(t) else t
        if len(t):
            for (ma, mb), g in t.groupby(["mode_a", "mode_b"], sort=True):
                mp.append({"agglomeration": agg, "mode_a": ma, "mode_b": mb, **_share_row(g)})
            mp.append({"agglomeration": agg, "mode_a": "all", "mode_b": "all", **_share_row(t)})
            for area, g in t.groupby("area", sort=True):
                nodes15.append({"agglomeration": agg, "node_id": nt.node_id.get(area), "name": name_of(area),
                                **_share_row(g)})
        ng = rr.get("night")
        if ng is not None and len(ng):
            for area, g in ng.groupby("area", sort=True):
                night.append({"agglomeration": agg, "node_id": nt.node_id.get(area), "name": name_of(area),
                              **_share_row(g)})
            night.append({"agglomeration": agg, "node_id": None, "name": "(wszystkie)", **_share_row(ng)})
        pu = rr.get("pulse")
        if pu is not None and len(pu):
            pu = pu.copy()
            pu.insert(0, "agglomeration", agg)
            pu.insert(1, "node_id", pu.area.map(nt.node_id))
            pu.insert(2, "name", [name_of(a) for a in pu.area])
            pu["in_area"] = pu.area.isin(d_areas)
            pulse.append(pu.drop(columns="area"))
    mp = pd.DataFrame(mp)
    nodes15 = pd.DataFrame(nodes15)
    night = pd.DataFrame(night)
    pulse = pd.concat(pulse, ignore_index=True) if pulse else pd.DataFrame()
    write_csv(mp, T.QA / "timed_both15_mode_pairs.csv")
    write_csv(nodes15.sort_values(["agglomeration", "node_id"], na_position="last"), T.QA / "timed_both15_nodes.csv")
    write_csv(night.sort_values(["agglomeration", "name", "node_id"], na_position="last"), T.QA / "timed_night_control.csv")
    if len(pulse):
        pulse = pulse.sort_values(["win", "agglomeration", "name", "node_id", "n_dep"], na_position="last",
                                  kind="stable").reset_index(drop=True)
    write_csv(pulse, T.QA / "pulse_nodes.csv")
    return {"mode_pairs": mp, "nodes15": nodes15, "night": night, "pulse": pulse}


def params() -> dict:
    from pipeline import transfer_walk as W
    return {"walk_kmh": T.WALK_KMH, "window_day": "06:00-20:00", "window_am": "07:00-09:00",
            "min_line_events": T.MIN_LINE_EVENTS, "parallel_share": T.PARALLEL_SHARE,
            "main_dir_share": T.MAIN_DIR_SHARE, "wait_cap_min": T.WAIT_CAP_MIN,
            "timed": {"min_headway_min": T.TIMED_MIN_HEADWAY, "ratio": T.TIMED_RATIO, "min_arrivals": T.TIMED_MIN_ARR},
            "stop_max_snap_m": T.STOP_MAX_SNAP_M, "local_margin_m": W.LOCAL_MARGIN_M,
            "dijkstra_limit_m": W.DIJKSTRA_LIMIT_M, "crossing_group_gap_m": W.GROUP_GAP_M,
            "top_n": TOPN, "walk_easy_min": WALK_EASY_MIN, "walk_hard_min": WALK_HARD_MIN,
            "gtt_band": {k: {"walk_weight": a, "wait_weight": b, "penalty_min": c} for k, (a, b, c) in T.GTT_BAND.items()},
            "w6": {"hi": W.W6_HI, "lo": W.W6_LO}, "freq_headways_min": list(T.FREQ_HEADWAYS),
            "night_window": "23:00-04:30", "night_max_headway_min": T.NIGHT_MAX_HEADWAY,
            "pulse": {"cycle_min": T.PULSE_CYCLE_MIN, "bin_min": T.PULSE_BIN_MIN, "quantile": T.PULSE_Q,
                      "min_departures": T.PULSE_MIN_DEP, "rotations": T.PULSE_SIMS},
            "detail_min_dep_h": T.DETAIL_MIN_DEP_H}
