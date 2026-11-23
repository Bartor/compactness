"""Sample-based parts of the accessibility step that need R5 itineraries (run inside pipeline.access run).

transfers(): median number of transfers (brief §4.6).  R5's regional computation returns travel times only, so
  the number of transfers is estimated on a sample: origins drawn with probability proportional to census-scaled
  population (FUA cells), for each origin one destination drawn proportionally to census-scaled population among
  the destinations reachable within 45 min by transit + walk (the travel-time rule of the main computation:
  min(transit median 07-09, walk-only)), and a 5-minute departure slot drawn uniformly in the window.  For each
  pair r5py DetailedItineraries (R5 suboptimalMinutes = 0) returns the Pareto-optimal options departing within the
  slot (a 1-minute window makes R5 run out of memory); the fastest one (ties: fewer rides) is kept.  Known r5py limitation: DetailedItineraries does not enforce the 12-minute walk limit the way
  the regional computation does, so a few itineraries may contain longer walks.
od_pairs(): 4 named pairs per city (5-7 in Wroclaw: plus the benchmark pairs) for a manual journey-planner check
  (brief §7.4): origins at GTFS stops near population-weighted random cells in distance rings from the centre,
  destination the configured hub (one tangential stop-to-stop pair); R5 travel time at a specific departure minute
  on the reference Wednesday, the median over 07:00-09:00, walk-only time and the fastest itinerary.
"""
from __future__ import annotations

import datetime as dt
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pipeline import access_inputs as AI

TRANSIT_EXCLUDE = {"WALK", "BICYCLE", "CAR", "BICYCLE_RENT", "CAR_PARK"}


def _mode(m) -> str:
    return str(m).replace("TransportMode.", "")


def _gdf(ids, lon, lat) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"id": list(ids)}, geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")


def _common():
    from r5py import TransportMode
    from pipeline.access import WALK_ACCESS_MIN, WALK_KMH
    return dict(transport_modes=[TransportMode.TRANSIT, TransportMode.WALK], speed_walking=WALK_KMH,
                max_time_walking=dt.timedelta(minutes=WALK_ACCESS_MIN))


def best_options(di: pd.DataFrame, names: dict | None = None) -> pd.DataFrame:
    """Fastest option per (from_id, to_id): total minutes, rides, transfers, legs as text."""
    rows = []
    if di is None or len(di) == 0:
        return pd.DataFrame(columns=["from_id", "to_id", "total_min", "n_rides", "walk_min", "legs", "dep"])
    di = pd.DataFrame(di.drop(columns="geometry", errors="ignore"))
    for (f, t), g in di.groupby(["from_id", "to_id"], sort=True):
        best = None
        for opt, h in g.groupby("option", sort=True):
            h = h.sort_values("segment")
            tot = (pd.to_timedelta(h["travel_time"]).sum() + pd.to_timedelta(h["wait_time"]).fillna(pd.Timedelta(0)).sum()
                   ).total_seconds() / 60
            modes = [_mode(m) for m in h["transport_mode"]]
            rides = sum(m not in TRANSIT_EXCLUDE for m in modes)
            walk = sum(pd.Timedelta(x).total_seconds() / 60 for x, m in zip(h["travel_time"], modes) if m == "WALK")
            key = (round(tot, 3), rides, int(opt))
            if best is None or key < best[0]:
                legs = []
                for r, m in zip(h.itertuples(), modes):
                    s = m
                    if m not in TRANSIT_EXCLUDE and names is not None:
                        rn = names["route"].get((r.feed, r.route_id), r.route_id)
                        s += f" {rn} ({names['stop'].get((r.feed, r.start_stop_id), r.start_stop_id)} -> " \
                             f"{names['stop'].get((r.feed, r.end_stop_id), r.end_stop_id)})"
                    s += f" {pd.Timedelta(r.travel_time).total_seconds() / 60:.1f} min"
                    if pd.notna(r.wait_time) and pd.Timedelta(r.wait_time) > pd.Timedelta(0):
                        s += f" (czekanie {pd.Timedelta(r.wait_time).total_seconds() / 60:.1f} min)"
                    legs.append(s)
                best = (key, {"from_id": f, "to_id": t, "total_min": tot, "n_rides": rides, "walk_min": walk,
                              "legs": " | ".join(legs), "dep": str(h["departure_time"].min())})
        rows.append(best[1])
    return pd.DataFrame(rows)


ITIN_THREADS = 8        # r5py default is half the cores; McRaptor states are large, so fewer parallel pairs
ITIN_MAX_MIN = 60       # = max trip of the regional computation
ITIN_WINDOW_MIN = 5     # R5 v7.5.1 McRaptor runs out of a 16 GB heap with a 1-minute window (tested on Wroclaw: every
                        # pair failed); with 5 or 10 minutes it takes ~1.5 s per pair.  The fastest option departing
                        # within [minute, minute + 5) is kept.


def _itineraries_class():
    """r5py DetailedItineraries with R5 suboptimalMinutes = 0 (Pareto-optimal options only) and fewer threads.

    With the default suboptimal window R5's McRaptorSuboptimalPathProfileRouter keeps every path within 5 min of the
    best and ran out of a 16 GB heap on Wroclaw; the fastest option, which is all we use, is unaffected."""
    from r5py import DetailedItineraries

    class Itineraries(DetailedItineraries):
        NUM_THREADS = ITIN_THREADS

        def _compute(self):
            self.request._regional_task.suboptimalMinutes = 0
            return super()._compute()

    return Itineraries


def _route_pairs(tn, o_ll, d_ll, departure: dt.datetime, max_min: int = ITIN_MAX_MIN):
    n = len(o_ll)
    o = _gdf([f"o{i}" for i in range(n)], [p[0] for p in o_ll], [p[1] for p in o_ll])
    d = _gdf([f"d{i}" for i in range(n)], [p[0] for p in d_ll], [p[1] for p in d_ll])
    return _itineraries_class()(tn, origins=o, destinations=d, departure=departure,
                                departure_time_window=dt.timedelta(minutes=ITIN_WINDOW_MIN),
                                max_time=dt.timedelta(minutes=max_min), snap_to_network=True, **_common())


# ------------------------------------------------------------------ transfers
def transfers(tn, agg: str, net: str, scen: str) -> pd.DataFrame:
    from pipeline.access import SCENARIOS, log, make_task, travel_times, window_departure
    s = SCENARIOS[scen]
    rng = np.random.default_rng(s["seed"])
    o = AI.origins(agg)
    d = AI.destinations(agg)
    w = o["w_census"].to_numpy()
    draws = np.sort(rng.choice(len(o), size=s["n_pairs"], replace=True, p=w / w.sum()))
    uniq = np.unique(draws)
    dlon, dlat = AI.TO4326.transform(d["x"].to_numpy(), d["y"].to_numpy())
    dests = _gdf(d["cell_id"], dlon, dlat)
    pt_task, _ = make_task(tn, dests, "pt_am")
    wk_task, _ = make_task(tn, dests, "walk")
    jnet = tn._transport_network
    tts = {}
    for i in uniq:
        a = travel_times(pt_task, jnet, o["lon"].iat[i], o["lat"].iat[i])
        b = travel_times(wk_task, jnet, o["lon"].iat[i], o["lat"].iat[i])
        tts[i] = (np.minimum(a, b), a, b)
    dep0, span, _ = window_departure(s["window"])
    rows = []
    pop = d["w_census"].to_numpy()
    own = {cid: j for j, cid in enumerate(d["cell_id"])}
    for k, i in enumerate(draws):
        comb, a, b = tts[i]
        cand = (comb <= 45) & (pop > 0)
        cand[own[o["cell_id"].iat[i]]] = False
        if not cand.any():
            rows.append({"draw": k, "origin": o["cell_id"].iat[i], "dest": None})
            continue
        p = np.where(cand, pop, 0.0)
        j = int(rng.choice(len(d), p=p / p.sum()))
        # departure slot of ITIN_WINDOW_MIN minutes (pairs of one slot are routed in one parallel call)
        minute = ITIN_WINDOW_MIN * int(rng.integers(0, int(span.total_seconds() // 60) // ITIN_WINDOW_MIN))
        rows.append({"draw": k, "origin": o["cell_id"].iat[i], "o_lon": o["lon"].iat[i], "o_lat": o["lat"].iat[i],
                     "dest": d["cell_id"].iat[j], "d_lon": dlon[j], "d_lat": dlat[j], "minute": minute,
                     "regional_min": int(comb[j]), "regional_transit_min": int(min(a[j], 999)),
                     "regional_walk_min": int(min(b[j], 999)), "o_in_core": bool(o["in_core"].iat[i])})
    p = pd.DataFrame(rows)
    ok = p[p["dest"].notna()].copy()
    res = []
    for minute, g in ok.groupby("minute", sort=True):
        di = _route_pairs(tn, list(zip(g["o_lon"], g["o_lat"])), list(zip(g["d_lon"], g["d_lat"])),
                          dep0 + dt.timedelta(minutes=int(minute)))
        b = best_options(di)
        b["draw"] = [int(g["draw"].iat[int(x[1:])]) for x in b["from_id"]]
        log(f"  {agg} transfers sample: slot +{int(minute)} min, {len(g)} pairs routed")
        res.append(b.drop(columns=["from_id", "to_id", "legs"]))
    b = pd.concat(res, ignore_index=True) if res else pd.DataFrame(columns=["draw"])
    out = p.merge(b, on="draw", how="left")
    out["transfers"] = np.where(out["n_rides"] >= 1, out["n_rides"] - 1, np.nan)
    out["departure"] = [None if pd.isna(m) else (dep0 + dt.timedelta(minutes=int(m))).isoformat() for m in out.get("minute", [])]
    cols = ["draw", "origin", "dest", "o_in_core", "departure", "regional_min", "regional_transit_min",
            "regional_walk_min", "total_min", "n_rides", "transfers", "walk_min"]
    out = out[[c for c in cols if c in out]].sort_values("draw").reset_index(drop=True)
    for c in ("total_min", "walk_min"):
        out[c] = out[c].astype(float).round(2)
    return out


# ------------------------------------------------------------------ OD pairs
BENCH_PAIRS = {"wroclaw": [
    ("Kozanów (przy przystanku KOZANÓW Dokerska)", (16.9640, 51.1420), "Rynek", (17.0320, 51.1100)),
    ("Jagodno (przy JAGODNO P+R)", (17.0600, 51.0545), "pl. Grunwaldzki", (17.0636, 51.1118)),
    ("Siechnice, stacja", (17.1530, 51.0350), "Wrocław Główny", (17.0365, 51.0983)),
]}
PAIR_TIMES = ["07:35", "07:50", "08:05", "08:20", "08:35", "07:40", "08:10"]


def stops_table(agg: str, net: str) -> tuple[pd.DataFrame, dict]:
    from pipeline.r5_inputs import gtfs_paths
    rows, names = [], {"route": {}, "stop": {}}
    for p in gtfs_paths(agg, "all" if net == "street" else net):
        with zipfile.ZipFile(p) as z:
            st = pd.read_csv(z.open("stops.txt"), dtype=str).fillna("")
            r = pd.read_csv(z.open("routes.txt"), dtype=str).fillna("")
        st["feed"] = p.stem
        rows.append(st)
        for a, b, c in zip(r["route_id"], r["route_short_name"], r["route_long_name"]):
            names["route"][(p.stem, a)] = b or c or a
        for a, b in zip(st["stop_id"], st["stop_name"]):
            names["stop"][(p.stem, a)] = b or a
    s = pd.concat(rows, ignore_index=True)
    s["lon"] = s["stop_lon"].astype(float)
    s["lat"] = s["stop_lat"].astype(float)
    s["x"], s["y"] = AI.TO2180.transform(s["lon"].to_numpy(), s["lat"].to_numpy())
    return s.sort_values(["feed", "stop_id"]).reset_index(drop=True), names


def pick_pairs(agg: str, net: str, seed: int) -> list[dict]:
    from scipy.spatial import cKDTree
    from pipeline.boundaries import load_agglomeration
    rng = np.random.default_rng(seed)
    o = AI.origins(agg)
    cen = AI.centres(agg)
    c0 = cen[0]
    hub = next((c for c in cen if c["kind"] == "hub"), c0)
    st, _ = stops_table(agg, net)
    fua = load_agglomeration(agg)["fua"]
    st = st[shapely.contains_xy(fua, st["x"].to_numpy(), st["y"].to_numpy())].reset_index(drop=True)
    tree = cKDTree(st[["x", "y"]].to_numpy())
    dist = np.hypot(o["x"] - c0["x"], o["y"] - c0["y"]).to_numpy()
    ang = np.degrees(np.arctan2(o["y"] - c0["y"], o["x"] - c0["x"])).to_numpy()
    w = o["w_census"].to_numpy()

    def draw(lo, hi, extra=None):
        m = (dist >= lo) & (dist < hi) & (w > 0)
        if extra is not None:
            m &= extra
        if not m.any():
            return None
        i = int(rng.choice(len(o), p=np.where(m, w, 0) / np.where(m, w, 0).sum()))
        _, j = tree.query([o["x"].iat[i], o["y"].iat[i]])
        s = st.iloc[int(j)]
        return {"name": f"{s['stop_name']} (przystanek {s['feed']}:{s['stop_id']})", "lon": float(s["lon"]),
                "lat": float(s["lat"]), "ang": ang[i], "dist_km": dist[i] / 1000}

    hubp = {"name": f"{hub['name']} (węzeł z config.yaml)", "lon": hub["lon"], "lat": hub["lat"]}
    pairs = []
    for lo, hi, lab in ((1500, 5000, "1,5–5 km od centrum"), (5000, 12000, "5–12 km"), (12000, 1e9, "> 12 km")):
        a = draw(lo, hi)
        if a:
            pairs.append({"kind": f"do węzła, start {lab}", "o": a, "d": hubp})
    a = draw(3000, 10000)
    if a:
        b = draw(3000, 10000, np.abs(((ang - a["ang"]) + 180) % 360 - 180) > 100)
        if b:
            pairs.append({"kind": "styczna (przystanek–przystanek, 3–10 km od centrum)", "o": a, "d": b})
    for on, oll, dn, dll in BENCH_PAIRS.get(agg, []):
        pairs.append({"kind": "para z r5_benchmark (plan.md 4.2)", "o": {"name": on, "lon": oll[0], "lat": oll[1]},
                      "d": {"name": dn, "lon": dll[0], "lat": dll[1]}})
    return pairs


def od_pairs(tn, agg: str, net: str, scen: str) -> pd.DataFrame:
    from r5py import TransportMode, TravelTimeMatrix
    from pipeline.access import SCENARIOS, WALK_KMH, window_departure
    pairs = pick_pairs(agg, net, SCENARIOS[scen]["seed"])
    _, names = stops_table(agg, net)
    dep0, span, day = window_departure("am_peak")
    rows = []
    for k, p in enumerate(pairs):
        hh, mm = map(int, PAIR_TIMES[k % len(PAIR_TIMES)].split(":"))
        dep = dep0.replace(hour=hh, minute=mm)
        o = _gdf(["o"], [p["o"]["lon"]], [p["o"]["lat"]])
        d = _gdf(["d"], [p["d"]["lon"]], [p["d"]["lat"]])
        at = TravelTimeMatrix(tn, origins=o, destinations=d, departure=dep, departure_time_window=dt.timedelta(minutes=1),
                              percentiles=[50], max_time=dt.timedelta(minutes=90), **_common())
        med = TravelTimeMatrix(tn, origins=o, destinations=d, departure=dep0, departure_time_window=span,
                               percentiles=[50], max_time=dt.timedelta(minutes=90), **_common())
        wk = TravelTimeMatrix(tn, origins=o, destinations=d, departure=dep, transport_modes=[TransportMode.WALK],
                              speed_walking=WALK_KMH, max_time=dt.timedelta(minutes=120))
        di = _route_pairs(tn, [(p["o"]["lon"], p["o"]["lat"])], [(p["d"]["lon"], p["d"]["lat"])], dep)
        b = best_options(di, names)

        def val(m):
            v = m.iloc[0].get("travel_time_p50", m.iloc[0].get("travel_time"))
            return None if pd.isna(v) else float(v)

        rows.append({"pair": k + 1, "kind": p["kind"], "origin": p["o"]["name"], "origin_lon": round(p["o"]["lon"], 5),
                     "origin_lat": round(p["o"]["lat"], 5), "destination": p["d"]["name"],
                     "destination_lon": round(p["d"]["lon"], 5), "destination_lat": round(p["d"]["lat"], 5),
                     "day": day, "departure": dep.strftime("%H:%M"), "r5_transit_at_departure_min": val(at),
                     "r5_transit_median_0709_min": val(med), "r5_walk_only_min": val(wk),
                     "itinerary_total_min": round(float(b["total_min"].iat[0]), 1) if len(b) else None,
                     "itinerary_rides": int(b["n_rides"].iat[0]) if len(b) else None,
                     "itinerary": b["legs"].iat[0] if len(b) else ""})
    return pd.DataFrame(rows)
