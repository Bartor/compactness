"""Top-10 stop clusters by departures per hour, 06:00-20:00 on the reference day (brief 7.3 check).

* Departures = every stop_time of the de-duplicated service layer except the last stop of each trip; rail
  replacement buses (``is_replacement_bus``) are left out.  Window ``frequency_window`` from config (06:00-20:00).
* Clusters: stops are clustered by position only (``stop_cluster_radius_m`` = 100 m), regardless of parent_station and
  feed, so metro / rail platforms merge with surface stops of the same node.  Greedy "leader" clustering: the stop with
  most departures takes every unassigned stop within the radius, then the next one, and so on.  This keeps clusters
  within a 200 m diameter and avoids the chaining of single linkage (stops every 80 m along a street would otherwise
  merge into one corridor).  The single-linkage alternative is computed for the top-10 as a comparison column.
* Departures per hour = departures / 14.  This is the SUM over lines and directions of the node, not a headway.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from pipeline import gtfs_service as gs
from pipeline.common import CRS_METRIC, load_config, sig

MODES = ["tram", "metro", "rail", "bus", "trolleybus", "ferry", "other"]


def departures(agg: str, day: str, variant: str) -> pd.DataFrame:
    cfg = load_config()
    fw = cfg["frequency_window"]
    h0, h1 = [int(x[:2]) * 3600 + int(x[3:5]) * 60 for x in (fw["start"], fw["end"])]
    t = gs.active_trips(agg, day, variant)
    st = gs.stop_times(agg, day, variant)
    st = st[st["uid"].isin(set(t.loc[~t["is_replacement_bus"], "uid"]))]
    st = st.sort_values(["uid", "stop_sequence"], kind="stable")
    last = st.groupby("uid")["stop_sequence"].transform("max")
    dep = st[(st["stop_sequence"] < last) & (st["dep_s"] >= h0) & (st["dep_s"] < h1)].copy()
    dep["hours"] = (h1 - h0) / 3600
    dep["minute"] = (dep["dep_s"] // 60).astype(int)
    return dep


def st_last(agg: str, day: str, variant: str) -> pd.Series:
    """Terminal stop (suid) of every trip: separates the two directions of lines without direction_id."""
    st = gs.stop_times(agg, day, variant).sort_values(["uid", "stop_sequence"], kind="stable")
    return st.groupby("uid")["suid"].last()


def _leader_clusters(xy: np.ndarray, weight: np.ndarray, r: float) -> np.ndarray:
    tree = cKDTree(xy)
    order = np.argsort(-weight, kind="stable")
    lab = np.full(len(xy), -1)
    c = 0
    for i in order:
        if lab[i] >= 0:
            continue
        nb = [j for j in tree.query_ball_point(xy[i], r) if lab[j] < 0]
        lab[nb] = c
        c += 1
    return lab


def _single_linkage(xy: np.ndarray, r: float) -> np.ndarray:
    pairs = cKDTree(xy).query_pairs(r, output_type="ndarray")
    n = len(xy)
    m = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    return connected_components(m, directed=False)[1]


def top_clusters(agg: str, day: str, variant: str, n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    r = float(load_config()["stop_cluster_radius_m"])
    dep = departures(agg, day, variant)
    ss = gs.stops(agg, variant)[["suid", "stop_name", "parent_station"]]
    per = dep.groupby("suid").size().rename("deps")
    pos = dep.groupby("suid")[["x", "y"]].first()
    sdf = pd.concat([per, pos], axis=1).reset_index().merge(ss, on="suid", how="left")
    sdf = sdf.dropna(subset=["x", "y"]).reset_index(drop=True)
    xy = sdf[["x", "y"]].to_numpy(dtype=float)
    sdf["cl"] = _leader_clusters(xy, sdf["deps"].to_numpy(float), r)
    sdf["cl_sl"] = _single_linkage(xy, r)
    dep = dep.merge(sdf[["suid", "cl", "cl_sl"]], on="suid", how="inner")
    sl_size = sdf.groupby("cl_sl")["deps"].sum()
    # duplicate diagnostics inside clusters
    lastst = st_last(agg, day, variant)
    dep["last_suid"] = dep["uid"].map(lastst)
    dep["dupkey"] = (dep["suid"] + "|" + dep["route_short_name"].astype(str) + "|" + dep["last_suid"].astype(str) + "|"
                     + dep["minute"].astype(str))
    dep["dup_same_stop"] = dep.duplicated("dupkey", keep=False)
    dep["xkey"] = dep["cl"].astype(str) + "|" + dep["route_short_name"].astype(str) + "|" + dep["minute"].astype(str)
    nfeed = dep.groupby("xkey")["feed"].transform("nunique")
    dep["cross_feed"] = nfeed > 1
    g = dep.groupby("cl")
    tot = g.size().rename("departures_06_20").to_frame()
    tot["departures_per_hour"] = tot["departures_06_20"] / dep["hours"].iloc[0]
    for m in MODES:
        tot[f"deps_{m}"] = dep[dep["route_class"] == m].groupby("cl").size().reindex(tot.index).fillna(0).astype(int)
    tot["n_lines"] = g["route_short_name"].nunique()
    tot["n_stops"] = sdf.groupby("cl").size().reindex(tot.index)
    tot["n_feeds"] = g["feed"].nunique()
    tot["feeds"] = g["feed"].agg(lambda s: ",".join(sorted(set(s))))
    tot["dup_same_stop_pct"] = 100 * g["dup_same_stop"].mean()
    tot["cross_feed_pct"] = 100 * g["cross_feed"].mean()
    tot["x"] = sdf.groupby("cl")["x"].mean().reindex(tot.index)
    tot["y"] = sdf.groupby("cl")["y"].mean().reindex(tot.index)
    # names: most frequent stop names weighted by departures
    names = sdf.sort_values("deps", ascending=False).groupby("cl")["stop_name"].agg(lambda s: " / ".join(pd.unique(s.dropna())[:3]))
    tot["name"] = names.reindex(tot.index)
    tot["parents"] = sdf.groupby("cl")["parent_station"].agg(lambda s: s.notna().sum()).reindex(tot.index)
    # single-linkage size for comparison: departures of the single-linkage component that contains the leader stop
    lead = sdf.sort_values("deps", ascending=False).groupby("cl").first()["cl_sl"]
    tot["deps_single_linkage_component"] = lead.map(sl_size).reindex(tot.index)
    tot = tot.sort_values(["departures_06_20", "name"], ascending=[False, True], kind="stable")
    top = tot.head(n).reset_index().rename(columns={"cl": "cluster_id"})
    tr = Transformer.from_crs(CRS_METRIC, "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(top["x"].to_numpy(), top["y"].to_numpy())
    top["lon"], top["lat"] = np.round(lon, 5), np.round(lat, 5)
    top.insert(0, "rank", range(1, len(top) + 1))
    flags = []
    for r_ in top.itertuples():
        f = []
        if r_.dup_same_stop_pct >= 5:
            f.append("możliwe zdublowane odjazdy (ta sama linia, kierunek, minuta, przystanek)")
        if r_.cross_feed_pct >= 5:
            f.append("ta sama linia i minuta w klastrze z więcej niż jednego feedu")
        if r_.deps_single_linkage_component > 1.3 * r_.departures_06_20:
            f.append("klaster łączony po sąsiedztwie > 100 m byłby większy o > 30 %")
        flags.append("; ".join(f))
    top["flag"] = flags
    return top, sdf


def run(day: str, qa) -> dict:
    rows, metrics = [], []
    for agg in gs.PHASE1:
        for variant in gs.VARIANTS:
            top, _ = top_clusters(agg, day, variant)
            top.insert(0, "variant", variant)
            top.insert(0, "agglomeration", agg)
            rows.append(top)
            metrics.append({"agglomeration": agg, "domain": "fua", "metric": "top1_cluster_departures_per_hour",
                            "label": "Kontrola §7.3: odjazdy na godzinę (6-20, suma linii i kierunków) w klastrze przystanków nr 1",
                            "value": float(top["departures_per_hour"].iloc[0]), "unit": "odjazdów/h", "grid": "",
                            "source": "GTFS (warstwa gtfs_service), klaster 100 m", "population_date": "", "timetable_date": day,
                            "coverage_share": None, "flag": "suma po liniach i kierunkach, nie odstęp; kontrola, nie miara częstotliwości",
                            "tier": "qa", "feed_variant": variant})
    df = pd.concat(rows, ignore_index=True)
    out = df.drop(columns=["x", "y", "cluster_id"]).copy()
    for c in out.columns:
        if out[c].dtype.kind == "f" and c not in ("lon", "lat"):
            out[c] = out[c].map(lambda v: sig(v, 4))
    out.to_csv(qa / "top10_stops.csv", index=False, lineterminator="\n")
    return {"table": df, "metrics": metrics}
