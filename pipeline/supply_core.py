"""Vehicle-kilometres clipped to a domain (FUA / core), from the de-duplicated service layer.

Method (stated in results/qa/transit/supply.md)
* Segment = consecutive stops of one trip.  Length = straight line between the stops (EPSG:2180, planar
  distortion < 0.1 % in Poland) scaled per trip so that the segments add up to the trip length ``dist_m``
  (shape length when the trip has a shape and the shape/stop ratio is within [0.8, 2.0]; otherwise the stop
  distance itself, ``scale_method`` = "stops").
* Segment with both stops inside the domain: counted whole.  One stop inside: counted by the share of the
  straight line that lies inside.  Both outside: 0 (even if the straight line grazes the domain).
* Hour of a segment = hour of the departure from its first stop (service day hours 24-29 are kept apart and
  reported as "24+").
* Segments with a missing stop coordinate are counted as unknown length and reported (``n_seg_nocoord``).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shapely

from pipeline import gtfs_service as gs
from pipeline.boundaries import load_agglomeration

K_MIN, K_MAX = 0.8, 2.0


def _inside(poly, x, y):
    shapely.prepare(poly)
    return shapely.contains_xy(poly, np.nan_to_num(x, nan=-1e9), np.nan_to_num(y, nan=-1e9))


def segments(agg: str, day: str, variant: str) -> pd.DataFrame:
    """One row per stop-to-stop segment of the active trips with km inside FUA and core."""
    a = load_agglomeration(agg)
    trips = gs.active_trips(agg, day, variant)
    st = gs.stop_times(agg, day, variant)
    st = st.sort_values(["feed", "uid", "stop_sequence"], kind="stable").reset_index(drop=True)
    uid = st["uid"].to_numpy()
    same = uid[1:] == uid[:-1]
    x = st["x"].to_numpy(dtype=np.float64)
    y = st["y"].to_numpy(dtype=np.float64)
    dx, dy = x[1:] - x[:-1], y[1:] - y[:-1]
    L = np.hypot(dx, dy)
    nocoord = same & ~np.isfinite(L)
    L = np.where(same & np.isfinite(L), L, 0.0)
    seg = pd.DataFrame({
        "uid": uid[:-1][same], "L": L[same], "nocoord": nocoord[same],
        "dep": st["dep_s"].to_numpy(dtype=np.float64)[:-1][same],
        "x0": x[:-1][same], "y0": y[:-1][same], "x1": x[1:][same], "y1": y[1:][same],
        "s0": st["suid"].to_numpy()[:-1][same], "s1": st["suid"].to_numpy()[1:][same],
    })
    # per-trip scale
    sumL = seg.groupby("uid")["L"].sum()
    t = trips.set_index("uid")
    k = (t["dist_m"] / sumL.reindex(t.index)).astype(float)
    shape = t["dist_method"] == "shape"
    ok = shape & k.between(K_MIN, K_MAX)
    scale = pd.Series(np.where(ok, k, np.where(t["dist_method"] == "stops", k.where(k.between(0.9, 1.1), 1.0), 1.0)), index=t.index)
    scale_method = pd.Series(np.where(ok, "shape", "stops"), index=t.index)
    seg["k"] = seg["uid"].map(scale).fillna(1.0)
    seg["km"] = seg["L"] * seg["k"] / 1000.0
    seg["scale_method"] = seg["uid"].map(scale_method)
    seg["shape_ratio_bad"] = seg["uid"].map(shape & ~k.between(K_MIN, K_MAX))
    for col in ("feed", "route_class", "is_replacement_bus"):
        seg[col] = seg["uid"].map(t[col])
    seg["hour"] = np.minimum(np.floor(seg["dep"].fillna(0) / 3600), 29).astype(int)
    # domain membership per stop, boundary segments by line intersection
    for dom in ("fua", "core"):
        poly = a[dom]
        ins0 = _inside(poly, seg["x0"].to_numpy(), seg["y0"].to_numpy())
        ins1 = _inside(poly, seg["x1"].to_numpy(), seg["y1"].to_numpy())
        frac = np.where(ins0 & ins1, 1.0, 0.0)
        valid = np.isfinite(seg["x0"].to_numpy() + seg["y0"].to_numpy() + seg["x1"].to_numpy() + seg["y1"].to_numpy()) & (seg["L"].to_numpy() > 0)
        b = np.flatnonzero((ins0 ^ ins1) & valid)
        if len(b):
            lines = shapely.linestrings(np.stack([np.stack([seg["x0"].to_numpy()[b], seg["y0"].to_numpy()[b]], 1),
                                                  np.stack([seg["x1"].to_numpy()[b], seg["y1"].to_numpy()[b]], 1)], 1))
            inter = shapely.length(shapely.intersection(lines, poly))
            tot = shapely.length(lines)
            frac[b] = np.where(tot > 0, np.clip(inter / np.where(tot > 0, tot, 1), 0, 1), 0.0)
        seg[f"km_{dom}"] = seg["km"] * frac
        seg[f"boundary_{dom}"] = ins0 ^ ins1
    return seg.drop(columns=["x0", "y0", "x1", "y1", "s0", "s1"])
