"""Tables and the node-use layer from the routed trip sample (pipeline.trips_sample).  No JVM.

    python -m pipeline.trips_sample analyse

Trip classes (per trip, after routing)
* "pt": an itinerary with at least one ride exists in the slot and walking the whole way (production walk cache,
  5 km/h, whole minutes) is not faster or equal.  Headline population for transfer shares ("variant A").
* "walk": walking is at least as fast (or R5 returned a walk-only path, or no PT path within 90 min but the
  destination is within a 60-min walk).
* "none": neither (destination reachable by the 07-09 median but not in the trip's own slot).
Variants: A = "pt" trips only; B = "pt" + "walk" trips, walking counted as 0 transfers; C = every trip with a PT
itinerary, even when walking is faster (closest to a journey planner query: the user asked for PT).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.common import INTERIM, RESULTS, sig, write_meta
from pipeline.trips_sample import AGGS, CODE_VERSION, N_TRIPS, OUT, QA, SLOT_MIN, load_trips, sets_for

NAMES = {"warszawa": "Warszawa", "krakow": "Kraków", "lodz": "Łódź", "gzm": "GZM", "wroclaw": "Wrocław",
         "poznan": "Poznań", "trojmiasto": "Trójmiasto"}
ORDER = ["warszawa", "krakow", "lodz", "gzm", "wroclaw", "poznan", "trojmiasto"]
# Jakdojade "Miasta w ruchu. Raport 2025" (October 2025 route queries): % with 0 / 1 / 2 transfers, mean transfers
JAKDOJADE = {"warszawa": (58, 33, 8, 0.52), "wroclaw": (68, 28, 3, 0.35), "poznan": (65, 29, 6, 0.42),
             "lodz": (64, 32, 5, 0.41), "trojmiasto": (71, 25, 4, 0.34), "krakow": (64, 31, 5, 0.41),
             "gzm": (71, 25, 4, 0.35)}
WBR2015_NO_TRANSFER = 57.2       # Warsaw travel survey 2015, synthesis p. 9: PT trips without a transfer, %
Z = 1.959964
BOOT = 500
LAYERS = RESULTS / "layers"


def wilson(k: float, n: float) -> tuple[float | None, float | None]:
    if not n:
        return None, None
    p = k / n
    den = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / den
    h = Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def classify(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    ok = t["status"].eq("ok")
    rides = t["n_rides"].where(ok)
    has_pt = ok & (rides >= 1)
    walk_s = t["walk_only_min"] * 60
    walk_faster = walk_s.notna() & (walk_s <= t["total_s"].where(has_pt, np.inf))
    cls = np.where(has_pt & ~walk_faster, "pt",
                   np.where(walk_faster | (ok & (rides == 0)) | (t["status"].eq("no_path_90") & t["walk_only_min"].notna()),
                            "walk", np.where(t["status"].eq("no_destination"), "no_destination", "none")))
    t["cls"] = cls
    t["has_pt_path"] = has_pt
    t["transfers"] = (rides - 1).where(has_pt)
    t["reach_min"] = t[["regional_pt_min", "walk_only_min"]].min(axis=1)
    for j in range(1, 4):
        for c in (f"best_r{j}_s", f"best_r{j}_rides"):
            if c not in t:
                t[c] = np.nan
    for pen in PENALTIES:
        t[f"transfers_pen{pen}"] = penalised(t, pen).where(has_pt)
    return t


PENALTIES = (5, 10)


def penalised(t: pd.DataFrame, pen_min: int) -> pd.Series:
    """Transfers of the itinerary minimising time + pen_min x transfers among the fastest itineraries with at most
    1, 2, 3 and 8 rides (R5 maxRides)."""
    best_cost = t["total_s"] + 60 * pen_min * (t["n_rides"] - 1)
    best_tr = t["n_rides"] - 1
    for j in range(1, 4):
        ts, tr = t[f"best_r{j}_s"], t[f"best_r{j}_rides"]
        cost = ts + 60 * pen_min * (tr - 1).clip(lower=0)
        better = ts.notna() & (tr >= 1) & ((cost < best_cost) | ((cost == best_cost) & (tr - 1 < best_tr)))
        best_cost = best_cost.where(~better, cost)
        best_tr = best_tr.where(~better, tr - 1)
    return best_tr


def shares(x: pd.Series) -> dict:
    """x: transfers per trip (0 for walking in variant B)."""
    n = int(len(x))
    out = {"n": n}
    for lab, m in (("0", x == 0), ("1", x == 1), ("2", x == 2), ("3plus", x >= 3), ("1plus", x >= 1), ("2plus", x >= 2)):
        k = int(m.sum())
        lo, hi = wilson(k, n)
        out[f"share_{lab}"] = sig(100 * k / n) if n else None
        out[f"share_{lab}_lo"] = sig(100 * lo) if n else None
        out[f"share_{lab}_hi"] = sig(100 * hi) if n else None
    mu = float(x.mean()) if n else None
    se = float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else None
    out["mean_transfers"] = sig(mu)
    out["mean_transfers_lo"] = sig(mu - Z * se) if se is not None else None
    out["mean_transfers_hi"] = sig(mu + Z * se) if se is not None else None
    return out


def composition(p: pd.DataFrame, seed: int) -> dict:
    """Ratio-of-sums shares of trip time for PT trips with a 95 % bootstrap interval."""
    walk = (p["access_s"] + p["egress_s"] + p["transfer_walk_s"]).to_numpy(float)
    w1 = p["wait_first_s"].to_numpy(float)
    wx = p["wait_transfer_s"].to_numpy(float)
    ride = p["ride_s"].to_numpy(float)
    tot = p["total_s"].to_numpy(float)
    xw = p["transfer_walk_s"].to_numpy(float)
    comp = {"walk": walk, "wait": w1 + wx, "wait_first": w1, "wait_transfer": wx, "ride": ride, "transfer_walk": xw}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(p), (BOOT, len(p)))
    out = {"n_pt": int(len(p)), "mean_rides": sig(float(p["n_rides"].mean())),
           "mean_total_min": sig(float(tot.mean() / 60)), "median_total_min": sig(float(np.median(tot) / 60))}
    T = tot.sum()
    Tb = tot[idx].sum(1)
    for k, v in comp.items():
        out[f"{k}_share"] = sig(100 * v.sum() / T)
        b = 100 * v[idx].sum(1) / Tb
        out[f"{k}_share_lo"], out[f"{k}_share_hi"] = sig(float(np.percentile(b, 2.5))), sig(float(np.percentile(b, 97.5)))
        out[f"{k}_mean_min"] = sig(float(v.mean() / 60))
    mr = p["n_rides"].to_numpy(float)
    out["mean_rides_lo"] = sig(float(np.percentile(mr[idx].mean(1), 2.5)))
    out["mean_rides_hi"] = sig(float(np.percentile(mr[idx].mean(1), 97.5)))
    return out


# ------------------------------------------------------------------ nodes
def stop_nodes(agg: str, nodes: pd.DataFrame) -> pd.Series:
    from pipeline import frequent as F
    s, cl = F.clusters(agg)
    cid = s["cl"].map(cl.set_index("cl")["cluster_id"])
    nd = nodes[nodes["agglomeration"] == agg][["node_id", "cluster_ids"]].copy()
    nd["cluster_id"] = nd["cluster_ids"].str.split(";")
    ex = nd.explode("cluster_id")
    c2n = ex.set_index("cluster_id")["node_id"]
    return pd.Series(cid.map(c2n).to_numpy(), index=s["suid"].to_numpy())


def transfer_events(t: pd.DataFrame, lg: pd.DataFrame, s2n: pd.Series) -> pd.DataFrame:
    """One row per transfer of a PT (class 'pt') trip: stops, nodes, walk and wait of the onward ride."""
    keep = t.loc[t["cls"] == "pt", ["set", "trip"]]
    L = lg.merge(keep, on=["set", "trip"]).sort_values(["set", "trip", "ride"])
    prev = L.groupby(["set", "trip"])[["alight_stop", "alight_name", "mode"]].shift(1)
    e = L[L["ride"] >= 1].copy()
    e["from_stop"], e["from_name"], e["from_mode"] = prev.loc[e.index, "alight_stop"], prev.loc[e.index, "alight_name"], prev.loc[e.index, "mode"]
    e = e.rename(columns={"board_stop": "to_stop", "board_name": "to_name", "mode": "to_mode",
                          "walk_before_s": "walk_s"})
    e["node_from"] = e["from_stop"].map(s2n)
    e["node_to"] = e["to_stop"].map(s2n)
    same = e["node_from"].notna() & (e["node_from"] == e["node_to"])
    both = e["node_from"].notna() & e["node_to"].notna() & ~same
    e["where"] = np.where(same, "jeden zespół", np.where(both, "dwa zespoły",
                          np.where(e["node_from"].notna() | e["node_to"].notna(), "jeden koniec w zespole", "poza zespołami")))
    return e[["set", "trip", "ride", "from_stop", "from_name", "from_mode", "to_stop", "to_name", "to_mode", "walk_s",
              "wait_s", "node_from", "node_to", "where"]].reset_index(drop=True)


def node_use(agg: str, ev: pd.DataFrame, n_pt: dict, nodes: pd.DataFrame) -> pd.DataFrame:
    a = ev.melt(id_vars=["set", "trip", "ride", "walk_s", "wait_s", "where"], value_vars=["node_from", "node_to"],
                value_name="node_id").dropna(subset=["node_id"])
    a = a.drop_duplicates(["set", "trip", "ride", "node_id"])          # a transfer within one node counts once
    nd = nodes[nodes["agglomeration"] == agg].copy()
    out = nd[["node_id", "agglomeration", "name", "n_lines", "dep_per_h_am", "walk_w_am_min", "wait_w_am_min",
              "walkwait_w_am_min", "in_core", "in_mask"]].copy()
    for s in ("res", "jobs"):
        b = a[a["set"] == s]
        g = b.groupby("node_id").agg(events=("trip", "size"), trips=("trip", "nunique"),
                                     walk=("walk_s", "mean"), wait=("wait_s", "mean"))
        suf = "" if s == "res" else "_jobs"
        n = n_pt.get(s)
        out[f"transfer_events{suf}"] = out["node_id"].map(g["events"]).fillna(0).astype(int) if n else None
        out[f"trips_changing{suf}"] = out["node_id"].map(g["trips"]).fillna(0).astype(int) if n else None
        out[f"n_pt_trips_sample{suf}"] = n
        if n:
            k = out[f"trips_changing{suf}"].to_numpy(float)
            out[f"share_trips_changing{suf}"] = [sig(100 * x / n) for x in k]
            ci = [wilson(x, n) for x in k]
            out[f"share_ci_low{suf}"] = [sig(100 * c[0]) for c in ci]
            out[f"share_ci_high{suf}"] = [sig(100 * c[1]) for c in ci]
            tot = len(ev[ev["set"] == s])
            out[f"share_of_transfers{suf}"] = [sig(100 * x / tot) if tot else None for x in out[f"transfer_events{suf}"]]
        else:
            for c in ("share_trips_changing", "share_ci_low", "share_ci_high", "share_of_transfers"):
                out[f"{c}{suf}"] = None
        if s == "res":
            out["obs_transfer_walk_min"] = out["node_id"].map(g["walk"] / 60).map(sig)
            out["obs_transfer_wait_min"] = out["node_id"].map(g["wait"] / 60).map(sig)
    k = out["trips_changing"]
    out["confidence"] = np.select([k >= 30, k >= 10, k >= 1], ["dobra (≥ 30 podróży w próbie)",
                                  "przybliżona (10–29 podróży)", "niepewna (1–9 podróży)"], "nie zaobserwowano w próbie")
    out["rank_use"] = out["trips_changing"].rank(ascending=False, method="min").astype(int)
    out["rank_dep_am"] = out["dep_per_h_am"].rank(ascending=False, method="min").astype(int)
    return out.sort_values(["rank_use", "node_id"]).reset_index(drop=True)


def runtimes() -> pd.DataFrame:
    rows = []
    pat = re.compile(r"^\S+ \S+ (\w+) (res|jobs) chunk (\d+): (\d+) trips, (\d+) with a path, (\d+) s")
    f = OUT / "run.log"
    if not f.exists():
        return pd.DataFrame()
    last = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        m = pat.match(line)
        if m:
            last[(m[1], m[2], int(m[3]))] = int(m[6])        # last run of each chunk
    for (agg, s, k), sec in last.items():
        rows.append({"agglomeration": agg, "set": s, "chunk": k, "seconds": sec})
    return pd.DataFrame(rows)


def write_csv(df: pd.DataFrame, name: str) -> None:
    QA.mkdir(parents=True, exist_ok=True)
    f = QA / name
    df.to_csv(f.with_name(f.name + ".tmp"), index=False, lineterminator="\n")
    os.replace(f.with_name(f.name + ".tmp"), f)


def main() -> None:
    t_start = time.time()
    nodes = pd.read_parquet(LAYERS / "transfer_nodes.parquet")
    rt = runtimes()
    summ, shr, comp, top, rank, uses, evs = [], [], [], [], [], [], []
    for agg in ORDER:
        if not (OUT / agg / "chunks").exists():
            continue
        t, lg = load_trips(agg)
        t = classify(t)
        planned = {s: N_TRIPS[s] for s in sets_for(agg)}
        for s in sets_for(agg):
            ts = t[t["set"] == s]
            r = {"agglomeration": agg, "set": s, "planned": planned[s], "routed": len(ts)}
            for c in ("pt", "walk", "none", "no_destination"):
                r[f"n_{c}"] = int((ts["cls"] == c).sum())
            r["n_has_pt_path"] = int(ts["has_pt_path"].sum())
            r["pt_share_of_routed"] = sig(100 * r["n_pt"] / max(len(ts), 1))
            r["median_dist_km_pt"] = sig(float(ts.loc[ts.cls == "pt", "dist_km"].median()))
            r["transfer_walk_split_ok_share"] = sig(100 * float(ts.loc[ts.n_rides >= 3, "transfer_walk_split_ok"].mean())) \
                if (ts.n_rides >= 3).any() else None
            if len(rt):
                q = rt[(rt.agglomeration == agg) & (rt.set == s)]
                r["routing_s"] = int(q.seconds.sum()) if len(q) else None
                r["ms_per_trip"] = sig(1000 * q.seconds.sum() / max(len(ts), 1)) if len(q) else None
            summ.append(r)
            for var, x, area in [("A", ts.loc[ts.cls == "pt", "transfers"], "wszystkie"),
                                 ("A", ts.loc[(ts.cls == "pt") & ts.o_in_core, "transfers"], "start w rdzeniu"),
                                 ("A", ts.loc[(ts.cls == "pt") & ~ts.o_in_core, "transfers"], "start poza rdzeniem"),
                                 ("B", ts.loc[ts.cls.isin(["pt", "walk"])].pipe(lambda d: d["transfers"].where(d.cls == "pt", 0)), "wszystkie"),
                                 ("C", ts.loc[ts.has_pt_path, "transfers"], "wszystkie"),
                                 ("A_cel_do_30_min", ts.loc[(ts.cls == "pt") & (ts.reach_min <= 30), "transfers"], "wszystkie"),
                                 ("A_cel_do_45_min", ts.loc[(ts.cls == "pt") & (ts.reach_min <= 45), "transfers"], "wszystkie"),
                                 ("A_kara_5_min", ts.loc[ts.cls == "pt", "transfers_pen5"], "wszystkie"),
                                 ("A_kara_10_min", ts.loc[ts.cls == "pt", "transfers_pen10"], "wszystkie"),
                                 ("A_cel_do_45_min_kara_5_min", ts.loc[(ts.cls == "pt") & (ts.reach_min <= 45), "transfers_pen5"], "wszystkie")]:
                shr.append({"agglomeration": agg, "set": s, "variant": var, "origins": area, **shares(x.astype(float))})
            p = ts[ts.cls == "pt"]
            comp.append({"agglomeration": agg, "set": s, **composition(p, 20261126 + len(comp))})
        # nodes
        s2n = stop_nodes(agg, nodes)
        ev = transfer_events(t, lg, s2n)
        ev.insert(0, "agglomeration", agg)
        evs.append(ev)
        n_pt = {s: int(((t.set == s) & (t.cls == "pt")).sum()) for s in sets_for(agg)}
        u = node_use(agg, ev, n_pt, nodes)
        uses.append(u)
        tt = u.head(20).copy()
        top.append(tt)
        from scipy.stats import spearmanr
        m = u["in_mask"]
        rho = spearmanr(u.loc[m, "dep_per_h_am"], u.loc[m, "trips_changing"]).statistic
        top_dep = set(u.nsmallest(20, "rank_dep_am")["node_id"])
        top_use = set(u.head(20)["node_id"])
        e_res = ev[ev.set == "res"]
        rank.append({"agglomeration": agg, "nodes": len(u), "nodes_with_use": int((u.trips_changing > 0).sum()),
                     "spearman_dep_vs_use_mask": sig(float(rho)), "top20_overlap": len(top_dep & top_use),
                     "top20_use_share_of_transfers": sig(100 * float(u.head(20)["transfer_events"].sum()) / max(len(e_res), 1)),
                     "top20_dep_share_of_transfers": sig(100 * float(u[u.node_id.isin(top_dep)]["transfer_events"].sum()) / max(len(e_res), 1)),
                     **{f"where_{k}": sig(100 * v / max(len(e_res), 1)) for k, v in e_res["where"].value_counts().items()}})
    S = pd.DataFrame(summ)
    write_csv(S, "sample_summary.csv")
    write_csv(pd.DataFrame(shr), "transfer_shares.csv")
    write_csv(pd.DataFrame(comp), "trip_composition.csv")
    U = pd.concat(uses, ignore_index=True)
    TOP = pd.concat(top, ignore_index=True)
    write_csv(TOP[["agglomeration", "rank_use", "node_id", "name", "trips_changing", "share_trips_changing", "share_ci_low",
                   "share_ci_high", "share_of_transfers", "trips_changing_jobs", "obs_transfer_walk_min",
                   "obs_transfer_wait_min", "walk_w_am_min", "wait_w_am_min", "walkwait_w_am_min", "dep_per_h_am",
                   "rank_dep_am", "n_lines", "confidence"]], "node_use_top20.csv")
    write_csv(pd.DataFrame(rank), "node_rank_comparison.csv")
    E = pd.concat(evs, ignore_index=True)
    E["walk_min"] = (E["walk_s"] / 60).round(2)
    E["wait_min"] = (E["wait_s"] / 60).round(2)
    fe = OUT / "transfer_events.csv"          # ~13 MB: kept out of results/ (not committed)
    E.drop(columns=["walk_s", "wait_s"]).to_csv(fe.with_name(fe.name + ".tmp"), index=False, lineterminator="\n")
    os.replace(fe.with_name(fe.name + ".tmp"), fe)
    # external comparison (variant A and C, residents)
    sh = pd.DataFrame(shr)
    ext = []
    for agg in ORDER:
        r = {"agglomeration": agg}
        for v in ("A", "B", "C", "A_cel_do_45_min", "A_kara_5_min", "A_kara_10_min", "A_cel_do_45_min_kara_5_min"):
            q = sh[(sh.agglomeration == agg) & (sh.set == "res") & (sh.variant == v) & (sh.origins == "wszystkie")]
            if len(q):
                q = q.iloc[0]
                for c in ("share_0", "share_0_lo", "share_0_hi", "share_1", "share_2plus", "mean_transfers", "n"):
                    r[f"{v}_{c}"] = q[c]
        j = JAKDOJADE.get(agg)
        r.update({"jakdojade_0": j[0], "jakdojade_1": j[1], "jakdojade_2": j[2], "jakdojade_mean": j[3]})
        r["wbr2015_0"] = WBR2015_NO_TRANSFER if agg == "warszawa" else None
        ext.append(r)
    write_csv(pd.DataFrame(ext), "external_comparison.csv")
    if (OUT / "nik_routed.csv").exists():
        nk = pd.read_csv(OUT / "nik_routed.csv")
        if "r5_median" in nk:
            nk["r5_median_minus_nik_pt"] = nk["r5_median"] - nk["nik_pt_min"]
            nk["r5_min_minus_nik_pt"] = nk["r5_min"] - nk["nik_pt_min"]
        write_csv(nk, "nik_pairs.csv")
    # layer
    lay = U.drop(columns=["walk_w_am_min", "wait_w_am_min", "walkwait_w_am_min", "in_core", "in_mask", "n_lines"])
    lay = lay.sort_values(["agglomeration", "node_id"]).reset_index(drop=True)
    LAYERS.mkdir(parents=True, exist_ok=True)
    f = LAYERS / "node_use.parquet"
    lay.to_parquet(f.with_name(f.name + ".tmp"), index=False)
    os.replace(f.with_name(f.name + ".tmp"), f)
    tmp = INTERIM / "trips" / "_meta_layer"
    write_meta(tmp, "trips_node_use", started=t_start,
               extra={"code_version": CODE_VERSION, "rows": int(len(lay)), "source": "pipeline.trips_sample / trips_analyse",
                      "note": "share_trips_changing = % of sampled resident-weighted PT trips (class pt) with a transfer "
                              "touching the node; Wilson 95% interval in share_ci_*"})
    shutil.copyfile(tmp / "_meta.json", LAYERS / "_meta_node_use.json")
    write_meta(QA, "trips_sample", started=t_start,
               extra={"code_version": CODE_VERSION, "n_trips": N_TRIPS, "slot_min": SLOT_MIN,
                      "files": sorted(p.name for p in QA.glob("*.csv"))})
    print(S.to_string())


if __name__ == "__main__":
    main()
