"""Scheduled-speed overlay, stop-to-stop: tram segments between consecutive stop places -> results/web/speed/.

    python -m pipeline.speed_segments_web            # trams, seven cities
    python -m pipeline.speed_segments_web --measure-bus   # also measure what stop-to-stop bus files would weigh (no files)

The map unit is the segment between two consecutive stop places in one direction ("odcinek między przystankami"),
not the multi-stop stretch of pipeline.tram_stretches: the reader joins segments on the site and sees the +-1 minute
rounding interval of the selection (wide for one segment, narrow for a chain of several).  The stretch files of
pipeline.speed_web stay as they are (buses and rail keep stretches / lines on the map; the report uses stretches).

Inputs (all local): the hop cache of pipeline.speed_core (data/interim/speed/hops_<agg>_<day>.parquet), the stop places
and the stop-pair -> stretch mapping of pipeline.tram_stretches.city_run (same code, same places as the committed
stretches), OSM track attributes of pipeline.speed_osm (OSM 2026-11-22) through tram_stretches.osm_attrs on the
segment geometry.  Timetables: Wednesday 2026-11-25 and Saturday 2026-11-28 (speed_core.days()).

Rules
* Segment = ordered pair (place a, place b) of consecutive stop places of a tram trip, a != b; terminal shuffles
  (speed_core.terminal_shuffle) are left out as in the stretches.  Id = <city code>-<sha1("a>b"), 5 hex> (longer only
  on a collision within the city): stable as long as the stop places do not change.
* Length = median hop length along the GTFS shape (Wednesday; Saturday when the segment runs only then).
* Scheduled time of a segment in a band = mean of the scheduled hop times (arrival at b - departure from a, whole
  minutes in the source) over the hops departing in the band; trips per hour = hops / band hours.  A selection's time
  is the sum of its segments' times and its speed = length / time (computed on the site).
* Free running (the site recomputes it with the reader's parameters): tram_stretches.free_time per segment with the cap
  cap(v0) = 1 / (f / msh + (1 - f) / v0), f = share of the sample points (every 10 m) on OSM track with a maxspeed
  (30-100 km/h), msh = their harmonic mean; identical to tram_stretches.cap_kmh on the segment's points.
* OSM attributes per segment (tram_stretches.osm_attrs on the segment geometry): street-running share, road crossings,
  signalised ones, pedestrian crossings away from junctions, switches.  A crossing within 1 m of a segment end, i.e. at
  the stop, is not counted on either segment (the same rule cuts stretch ends).
* Line directions (line x GTFS direction_id): trips, mean trip length and mean trip time per band of the trip's first
  departure (hops without terminal shuffles); traversals of each segment per band and line direction.
* Patterns: the stop-place sequence of each Wednesday / Saturday trip pattern as segment indices (for "this line in this
  direction" on the site), with the number of trips.
Every speed is scheduled ("z rozkładu"), never measured.  No trip ids or stop times are written, only aggregates.
Missing values are null or left out, never 0.  Numbers are rounded to 4 significant digits.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time

import numpy as np
import pandas as pd
import shapely

from pipeline import speed_core as sc
from pipeline import speed_osm as so
from pipeline import speed_web as sw
from pipeline import tram_stretches as ts
from pipeline.common import INTERIM, RESULTS, sig, write_meta

OUT = sw.OUT / "segments"           # results/web/speed/segments/ (beside the stretch files of speed_web)
CHECKS = INTERIM / "speed" / "segments_checks"
MAP_FILE = "trams.geojson"
MAX_MB = 5.0
ID_HEX = 5
BKEYS = list(sw.BANDS)
SHAPE_MIN = 0.5        # share of hops with shape geometry below which a segment is drawn as "straight"


# ------------------------------------------------------------------ pure helpers
def seg_id(code: str, a: str, b: str, n: int = ID_HEX) -> str:
    return f"{code}-{hashlib.sha1(f'{a}>{b}'.encode('utf-8')).hexdigest()[:n]}"


def unique_ids(code: str, pairs: list[tuple[str, str]]) -> list[str]:
    """Ids for ordered place pairs; the hash grows by one hex digit until the city has no collision."""
    n = ID_HEX
    while True:
        ids = [seg_id(code, a, b, n) for a, b in pairs]
        if len(set(ids)) == len(ids):
            return ids
        n += 1


def cap_parts(ms) -> tuple[float | None, float]:
    """(harmonic mean of the tagged maxspeeds or None, share of points tagged) from per-point maxspeeds (NaN = none)."""
    if ms is None:
        return None, 0.0
    ms = np.asarray(ms, float)
    if len(ms) == 0:
        return None, 0.0
    t = np.isfinite(ms)
    if not t.any():
        return None, 0.0
    return float(1.0 / np.mean(1.0 / ms[t])), float(t.mean())


def cap_from_parts(msh: float | None, msf: float, v0: float) -> float:
    """Time-equivalent cap from cap_parts; equals tram_stretches.cap_kmh on the same points."""
    if msh is None or msf <= 0:
        return v0
    return 1.0 / (msf / msh + (1.0 - msf) / v0)


def chain_interval_min(n_pieces: int) -> float:
    """Rounding error bound, minutes, of the time of n contiguous pieces: each piece's time is the difference of two
    whole-minute times at its two ends (inner stop times cancel), so +-1 min per piece."""
    return float(n_pieces)


def r4(v):
    """4 significant digits; None for missing."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return sig(f, 4)


def band_hours(key: str) -> float:
    dt, b = sw.BANDS[key]
    return sw.band_minutes(dt, b) / 60.0


# ------------------------------------------------------------------ per city
def day_hops(R: dict) -> dict[str, pd.DataFrame]:
    """The city's hops per day type with valid place pairs (a != b)."""
    out = {}
    for dt, h in R["H"].items():
        h = h.dropna(subset=["pa", "pb"])
        out[dt] = h[h["pa"] != h["pb"]].copy()
    return out


def segment_frame(H: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per ordered place pair with length, stretch membership, shape share and a representative hop."""
    rows = []
    for dt in ("weekday", "saturday"):
        h = H[dt]
        g = h.groupby(["pa", "pb"], sort=True)
        f = pd.DataFrame({"len": g["len_m"].median(), "shape_share": g["len_src"].agg(lambda v: float((v == "shape").mean())),
                          "n": g.size()})
        st = h.dropna(subset=["sid"]).groupby(["pa", "pb"])[["sid", "sdir", "eidx"]].first()
        f = f.join(st)
        rep = (h[h["len_src"] == "shape"].groupby(["pa", "pb", "shape_id", "a0", "a1"], dropna=False).size().rename("c")
               .reset_index().sort_values(["pa", "pb", "c", "shape_id", "a0"], ascending=[True, True, False, True, True],
                                          kind="stable").drop_duplicates(["pa", "pb"]).set_index(["pa", "pb"]))
        f = f.join(rep[["shape_id", "a0", "a1"]])
        xy = h.groupby(["pa", "pb"])[["x0", "y0", "x1", "y1", "feed"]].first()
        f = f.join(xy).assign(day=dt)
        rows.append(f.reset_index())
    S = pd.concat(rows, ignore_index=True)
    # Wednesday first, Saturday only where the segment does not run on Wednesday
    S = S.sort_values(["pa", "pb", "day"], ascending=[True, True, False], kind="stable").drop_duplicates(["pa", "pb"])
    return S.reset_index(drop=True)


def segment_geometry(r, shp: dict) -> np.ndarray:
    if isinstance(r.shape_id, str) and r.shape_id and np.isfinite(r.a0) and r.feed in shp and r.shape_id in shp[r.feed]:
        p, cum = shp[r.feed][r.shape_id]
        return sc.cut(p, cum, r.a0, r.a1)
    return np.array([[r.x0, r.y0], [r.x1, r.y1]], dtype=float)


def band_stats(H: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per (pa, pb, key): hops n and summed time T; per (pa, pb, line, direction_id, key): hops."""
    a, b = [], []
    for key, (dt, band) in sw.BANDS.items():
        h = H[dt]
        g = h if band == "all_day" else h[h["band"] == band]
        if g.empty:
            continue
        s = g.groupby(["pa", "pb"]).agg(n=("t_s", "size"), T=("t_s", "sum")).reset_index().assign(key=key)
        a.append(s)
        ld = g.groupby(["pa", "pb", "line", "direction_id"]).size().rename("n").reset_index().assign(key=key)
        b.append(ld)
    return pd.concat(a, ignore_index=True), pd.concat(b, ignore_index=True)


def line_dirs(H: dict[str, pd.DataFrame], pname: dict) -> pd.DataFrame:
    """Per line x direction_id: name (most common first -> last place), and per band key trips, mean length (m) and
    mean time (s) of the trips whose first departure falls in the band."""
    out = []
    for dt in ("weekday", "saturday"):
        h = H[dt].sort_values(["uid", "k"], kind="stable")
        tr = h.groupby("uid").agg(line=("line", "first"), d=("direction_id", "first"), band=("trip_band", "first"),
                                  dep=("dep_s", "min"), arr=("arr_s", "max"), L=("len_m", "sum"),
                                  f=("pa", "first"), l=("pb", "last"))
        tr["T"] = tr["arr"] - tr["dep"]
        tr = tr[tr["T"] > 0]
        for key, (kdt, band) in sw.BANDS.items():
            if kdt != dt:
                continue
            g = tr if band == "all_day" else tr[tr["band"] == band]
            if g.empty:
                continue
            s = g.groupby(["line", "d"]).agg(trips=("L", "size"), L=("L", "mean"), T=("T", "mean")).reset_index()
            out.append(s.assign(key=key))
        ends = tr.groupby(["line", "d", "f", "l"]).size().rename("c").reset_index().assign(day=dt)
        out.append(ends)
    allv = pd.concat([x for x in out if "key" in x.columns], ignore_index=True)
    ends = pd.concat([x for x in out if "day" in x.columns], ignore_index=True)
    ends = (ends.groupby(["line", "d", "f", "l"])["c"].sum().reset_index()
            .sort_values(["line", "d", "c", "f", "l"], ascending=[True, True, False, True, True], kind="stable")
            .drop_duplicates(["line", "d"]))
    ends["name"] = ends["f"].map(pname) + " → " + ends["l"].map(pname)
    allv = allv.merge(ends[["line", "d", "name"]], on=["line", "d"], how="left")
    return allv


def patterns(H: dict[str, pd.DataFrame], seg_index: dict) -> list[dict]:
    """Distinct (line, segment sequence) of the trips of both days, with weekday trips; sorted."""
    acc: dict[tuple, list] = {}
    for dt in ("weekday", "saturday"):
        h = H[dt].sort_values(["uid", "k"], kind="stable")
        h = h.assign(si=[seg_index.get((a, b), -1) for a, b in zip(h["pa"], h["pb"])])
        seqs = h.groupby("uid").agg(line=("line", "first"), d=("direction_id", "first"),
                                     seq=("si", lambda v: tuple(int(x) for x in v if x >= 0)))
        for (line, d, seq), n in seqs.groupby(["line", "d", "seq"]).size().items():
            if len(seq) == 0:
                continue
            k = (str(line), str(d), seq)
            acc.setdefault(k, [0, 0])
            acc[k][0 if dt == "weekday" else 1] += int(n)
    rows = [{"line": k[0], "d": k[1], "s": list(k[2]), "nw": v[0], "ns": v[1]} for k, v in acc.items()]
    rows.sort(key=lambda r: (ts._line_key(r["line"]), r["d"], -r["nw"], -r["ns"], r["s"]))
    return rows


def build_city(agg: str, feeds, city: str, osm: dict | None, mode: str = "tram", prefix: str = "") -> dict:
    """Everything of one city: map features, the detail document, check tables."""
    R = ts.city_run(agg, feeds, city, osm, mode, prefix)
    code = ts.CITY_CODE[agg]
    pl = R["places"]
    pname = dict(zip(pl["place_key"], pl["place_name"]))
    H = day_hops(R)
    S = segment_frame(H)
    S["id"] = unique_ids(code + ("-" + prefix if prefix else ""), list(zip(S["pa"], S["pb"])))
    S = S.sort_values("id", kind="stable").reset_index(drop=True)
    seg_index = {(a, b): i for i, (a, b) in enumerate(zip(S["pa"], S["pb"]))}
    feeds_l = [feeds] if isinstance(feeds, str) else list(feeds)
    shp = {f: sc.shape_arrays(f) for f in feeds_l}
    geoms = [segment_geometry(r, shp) for r in S.itertuples(index=False)]
    O = R["O"]
    osm_rows = []
    for g in geoms:
        if O is None:
            osm_rows.append({})
            continue
        at = ts.osm_attrs(g, O)
        msh, msf = cap_parts(at["_ms"])
        osm_rows.append({"st": at["share_street"], "x": at["n_road_crossings"], "xs": at["n_signalised"],
                         "xp": at["n_ped_standalone"], "sw": at["n_switches"], "msh": msh, "msf": msf,
                         "match": at["osm_match_share"]})
    BS, LD = band_stats(H)
    LS = line_dirs(H, pname)
    pats = patterns(H, seg_index)
    return {"agg": agg, "code": code, "R": R, "H": H, "S": S, "geoms": geoms, "osm": osm_rows, "BS": BS, "LD": LD,
            "LS": LS, "patterns": pats, "pname": pname}


# ------------------------------------------------------------------ outputs
def per_band(S: pd.DataFrame, BS: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Arrays (segments x bands): hops n and mean time t (s); NaN where the segment has no hop in the band."""
    idx = {(a, b): i for i, (a, b) in enumerate(zip(S["pa"], S["pb"]))}
    n = np.full((len(S), len(BKEYS)), np.nan)
    t = np.full((len(S), len(BKEYS)), np.nan)
    kpos = {k: j for j, k in enumerate(BKEYS)}
    for r in BS.itertuples(index=False):
        i = idx.get((r.pa, r.pb))
        if i is None:
            continue
        n[i, kpos[r.key]] = r.n
        t[i, kpos[r.key]] = r.T / r.n
    return n, t


def map_features(C: dict) -> list[dict]:
    S, n, t = C["S"], *per_band(C["S"], C["BS"])
    feats = []
    for i, r in enumerate(S.itertuples(index=False)):
        p = {"id": r.id, "agg": C["agg"], "m": "tram", "name": f"{C['pname'][r.pa]} → {C['pname'][r.pb]}",
             "len": sw.num(r.len, 0)}
        cls = []
        for j, key in enumerate(BKEYS):
            v = None
            if np.isfinite(t[i, j]) and t[i, j] > 0 and np.isfinite(r.len):
                v = sw.num(r.len / t[i, j] * 3.6, 1)
            if v is not None:
                p[f"v_{key}"] = v
            if np.isfinite(n[i, j]) and n[i, j] > 0:
                p[f"t_{key}"] = sw.num(n[i, j] / band_hours(key), 1)
            c = int(sc.speed_class([v])[0]) if v is not None else -1
            cls.append(str(c) if c >= 0 else "-")
            if np.isfinite(t[i, j]) and t[i, j] == 0:
                p[f"z_{key}"] = 1          # 0 min in the timetable: no speed
        p["c"] = "".join(cls)
        if r.shape_share < SHAPE_MIN:
            p["straight"] = 1
        feats.append({"type": "Feature", "properties": p,
                      "geometry": {"type": "LineString", "coordinates": geom4326(C["geoms"][i])}})
    return feats


def geom4326(xy: np.ndarray) -> list:
    """EPSG:2180 polyline -> simplified (speed_web.SIMPLIFY_M) [[lon, lat], ...] with speed_web.COORD_DECIMALS."""
    line = shapely.simplify(shapely.linestrings(np.asarray(xy, float)), sw.SIMPLIFY_M, preserve_topology=False)
    c = np.asarray(line.coords)
    lo, la = sw.TO4326.transform(c[:, 0], c[:, 1])
    out = np.round(np.c_[lo, la], sw.COORD_DECIMALS)
    out = out[np.r_[True, (np.diff(out, axis=0) != 0).any(axis=1)]]
    if len(out) < 2:
        out = np.vstack([out, out])
    return [[float(a), float(b)] for a, b in out]


def detail_doc(C: dict) -> dict:
    """The per-city document the site loads when a selection opens (columnar)."""
    S = C["S"]
    n, t = per_band(S, C["BS"])
    pname = C["pname"]
    seg_cols = ["id", "a", "b", "len", "stretch", "pos", "msh", "msf", "st", "x", "xs", "xp", "sw", "bb"]
    pkeys = sorted(set(S["pa"]) | set(S["pb"]))
    pidx = {k: i for i, k in enumerate(pkeys)}
    rows = []
    for i, r in enumerate(S.itertuples(index=False)):
        o = C["osm"][i]
        stretch = f"{r.sid}-{r.sdir}" if isinstance(r.sid, str) else None
        g = np.asarray(geom4326(C["geoms"][i]))
        bb = [float(round(x, 5)) for x in (g[:, 0].min(), g[:, 1].min(), g[:, 0].max(), g[:, 1].max())]
        rows.append([r.id, pidx[r.pa], pidx[r.pb], r4(r.len), stretch,
                     int(r.eidx) if stretch is not None and np.isfinite(r.eidx) else None,
                     r4(o.get("msh")), r4(o.get("msf")) if o else None, r4(o.get("st")),
                     o.get("x"), o.get("xs"), o.get("xp"), o.get("sw"), bb])
    # line directions
    LS = C["LS"]
    ldk = sorted({(str(a), str(b)) for a, b in zip(LS["line"], LS["d"])}, key=lambda x: (ts._line_key(x[0]), x[1]))
    ldi = {k: i for i, k in enumerate(ldk)}
    lds = []
    for line, d in ldk:
        g = LS[(LS["line"].astype(str) == line) & (LS["d"].astype(str) == d)].set_index("key")
        nm = g["name"].dropna()
        lds.append({"line": line, "d": d, "name": nm.iloc[0] if len(nm) else None,
                    "trips": [int(g.loc[k, "trips"]) if k in g.index else None for k in BKEYS],
                    "len": [r4(g.loc[k, "L"]) if k in g.index else None for k in BKEYS],
                    "time": [r4(g.loc[k, "T"]) if k in g.index else None for k in BKEYS]})
    # segment x line direction hops per band: {seg index: [[ld, [n per band]], ...]}
    LD = C["LD"]
    sidx = {(a, b): i for i, (a, b) in enumerate(zip(S["pa"], S["pb"]))}
    kpos = {k: j for j, k in enumerate(BKEYS)}
    use: dict[int, dict[int, list]] = {}
    for r in LD.itertuples(index=False):
        i = sidx.get((r.pa, r.pb))
        li = ldi.get((str(r.line), str(r.direction_id)))
        if i is None or li is None:
            continue
        use.setdefault(i, {}).setdefault(li, [None] * len(BKEYS))[kpos[r.key]] = int(r.n)
    seg_lines = [[[li, v] for li, v in sorted(use.get(i, {}).items())] for i in range(len(S))]
    pats = [{"line": p["line"], "d": p["d"], "ld": ldi.get((p["line"], p["d"])), "s": p["s"], "nw": p["nw"], "ns": p["ns"]}
            for p in C["patterns"]]
    return {
        "agg": C["agg"], "code": C["code"], "mode": "tram",
        "title": "Odcinki między przystankami: czasy z rozkładu (nie pomiar)",
        "timetable_dates": sc.days(),
        "bands": [{"key": k, "hours": r4(band_hours(k))} for k in BKEYS],
        "model": {"a_acc": ts.KIN["a_acc"], "b_brk": ts.KIN["b_brk"], "v_cap_kmh": ts.KIN["v_cap_kmh"],
                  "dwell_s": ts.KIN["dwell_s"], "range_dwell_s": list(ts.RANGE_DWELL_S),
                  "range_cap_kmh": list(ts.RANGE_CAP_KMH), "maxspeed_kmh": [ts.MAXSPEED_MIN, ts.MAXSPEED_MAX]},
        "places": [pname[k] for k in pkeys],
        "segments": {"columns": seg_cols, "rows": rows},
        "n": [[None if not np.isfinite(x) else int(x) for x in row] for row in n],
        "t": [[r4(x) for x in row] for row in t],
        "seg_lines": seg_lines,
        "line_dirs": lds,
        "patterns": pats,
        "notes": {"a/b": "przystanek początkowy i końcowy odcinka (indeks w places)",
                  "stretch/pos": "dłuższy odcinek między węzłami (warstwa odcinków) i miejsce w nim",
                  "bb": "zasięg geometrii: lon/lat min, lon/lat max",
                  "st/x/xs/xp/sw": "OSM: udział w jezdni, skrzyżowania z drogą, z sygnalizacją, przejścia poza skrzyżowaniami, rozjazdy",
                  "t":"średni czas z rozkładu między odjazdem z przystanku a przyjazdem na następny, s, kursy odjeżdżające w paśmie",
                  "n": "liczba przejazdów odcinka w paśmie (kursy)",
                  "msh/msf": "limit z OSM: średnia harmoniczna oznaczonych maxspeed i udział punktów z oznaczeniem",
                  "line_dirs": "linia x kierunek (direction_id): kursy, średnia długość (m) i czas (s) kursu wg pasma pierwszego odjazdu"},
    }


# ------------------------------------------------------------------ checks
def check_city_speed(C: dict) -> list[dict]:
    """Length-weighted speed over all hops (sum len / sum time) per band vs the stretch-based figure."""
    H = C["H"]
    ref = pd.read_csv(RESULTS / "qa" / "speed" / "stretches" / "city_stretch_summary.csv")
    ref = ref[ref["agglomeration"] == C["agg"]].set_index(["day_type", "band"])["speed_kmh_all_stretches"]
    out = []
    for key, (dt, band) in sw.BANDS.items():
        h = H[dt]
        g = h if band == "all_day" else h[h["band"] == band]
        on = g.dropna(subset=["sid"])
        if g.empty:
            continue
        v_all = g["len_m"].sum() / g["t_s"].sum() * 3.6
        v_on = on["len_m"].sum() / on["t_s"].sum() * 3.6
        r = ref.get((dt, band))
        out.append({"agg": C["agg"], "band": key, "v_hops_all": v_all, "v_hops_on_stretches": v_on, "v_stretches": r,
                    "diff_on": v_on - r if r is not None else None, "diff_all": v_all - r if r is not None else None,
                    "share_hops_no_stretch": float(g["sid"].isna().mean())})
    return out


def check_stretch_sum(C: dict) -> pd.DataFrame:
    """Per stretch direction and band: stretch scheduled time and time above free running (central parameters) from
    the stretch table vs the sum over its segments."""
    S = C["S"]
    n, t = per_band(S, C["BS"])
    bands = pd.read_csv(RESULTS / "tables" / "tram_stretch_bands.csv")
    st = pd.read_csv(RESULTS / "tables" / "tram_stretches.csv", usecols=["stretch_dir_id", "agglomeration", "n_hops", "length_m"])
    st = st[st["agglomeration"] == C["agg"]]
    bands = bands[bands["stretch_dir_id"].isin(st["stretch_dir_id"])]
    bmap = {(dt, b): k for k, (dt, b) in sw.BANDS.items()}
    sd = [f"{a}-{b}" if isinstance(a, str) else None for a, b in zip(S["sid"], S["sdir"])]
    S = S.assign(sd=sd)
    p = ts.KIN
    free = []
    for i, r in enumerate(S.itertuples(index=False)):
        o = C["osm"][i]
        cap = cap_from_parts(o.get("msh"), o.get("msf") or 0.0, p["v_cap_kmh"])
        free.append(float(ts.free_time([r.len], {**p, "v_cap_kmh": cap})[0]) if np.isfinite(r.len) else np.nan)
    S["free"] = free
    rows = []
    groups = {k: g for k, g in S.groupby("sd")}
    for r in bands.itertuples(index=False):
        g = groups.get(r.stretch_dir_id)
        k = bmap.get((r.day_type, r.band))
        if g is None or k is None:
            continue
        j = BKEYS.index(k)
        tt = t[g.index.to_numpy(), j]
        nh = int(st.loc[st["stretch_dir_id"] == r.stretch_dir_id, "n_hops"].iloc[0])
        complete = np.isfinite(tt).all() and len(g) == nh
        T = float(np.nansum(tt)) / 60
        Lseg = float(g["len"].sum())
        F = float(g["free"].sum()) / 60
        taf_seg = (T - F) * 60 / (Lseg / 1000) if Lseg > 0 else np.nan
        rows.append({"agg": C["agg"], "stretch_dir_id": r.stretch_dir_id, "band": k, "complete": complete,
                     "sched_min_stretch": r.sched_min, "sched_min_segments": T, "diff_min": T - r.sched_min,
                     "free_min_stretch": r.free_min, "free_min_segments": F,
                     "taf_stretch": r.taf_s_per_km, "taf_segments": taf_seg,
                     "diff_taf": taf_seg - r.taf_s_per_km if np.isfinite(r.taf_s_per_km) else np.nan,
                     "n_trips": r.n_trips})
    return pd.DataFrame(rows)


def why_stats(cities: list[dict]) -> dict:
    """The numbers behind 'why stretches': hop times and the width of the +-1 min interval."""
    t_all, seg_min, seg_len = [], [], []
    for C in cities:
        h = C["H"]["weekday"]
        t_all.append(h["t_s"].to_numpy() / 60)
        n, t = per_band(C["S"], C["BS"])
        j = BKEYS.index("w_md")
        ok = np.isfinite(t[:, j]) & np.isfinite(C["S"]["len"].to_numpy())
        seg_min.append(t[ok, j] / 60)
        seg_len.append(C["S"]["len"].to_numpy()[ok])
    t_all = np.concatenate(t_all)
    sm, sl = np.concatenate(seg_min), np.concatenate(seg_len)
    med_t, med_l = float(np.median(sm)), float(np.median(sl))
    v = med_l / 1000 / (med_t / 60)

    def iv(L, T):
        return [L / 1000 / ((T + 1) / 60), (L / 1000 / ((T - 1) / 60)) if T > 1 else None]
    # a 5-minute chain at the median segment speed
    L5 = v * 1000 * 5 / 60
    return {"hop_traversals_weekday": int(len(t_all)), "hop_time_median_min": float(np.median(t_all)),
            "share_hops_le_1min": float((t_all <= 1).mean()), "share_hops_lt_2min": float((t_all < 2).mean()),
            "share_hops_0min": float((t_all == 0).mean()),
            "segment_mean_time_median_min_w_md": med_t, "segment_length_median_m": med_l,
            "segment_speed_at_medians_kmh": v, "interval_single_segment_kmh": iv(med_l, med_t),
            "interval_5min_chain_kmh": iv(L5, 5.0), "chain_5min_length_m": L5}


# ------------------------------------------------------------------ bus measurement (no files)
def measure_bus() -> dict:
    """What stop-to-stop bus map files would weigh (same feature layout as the tram map file), per agglomeration."""
    out = {}
    for agg, _, city in ts.CITIES:
        feats = []
        for mode, prefix in (("bus", "b"), ("trolleybus", "t")):
            feeds = ts.bus_feeds(agg, mode)
            if not feeds:
                continue
            C = build_city(agg, feeds, sc.AGG_NAMES[agg], None, mode, prefix)
            feats += map_features(C)
        out[agg] = {"features": len(feats), "mb": round(len(sw.dump(feats).encode("utf-8")) / 1e6, 3)}
        print(f"  bus {agg}: {out[agg]}", flush=True)
    return out


def main() -> None:
    t0 = time.time()
    osm = so.load()
    feats, cities, sizes, counts = [], [], {}, {}
    chk_speed, chk_sum = [], []
    for agg, feed, city in ts.CITIES:
        C = build_city(agg, feed, city, osm)
        f = map_features(C)
        feats += f
        doc = detail_doc(C)
        name = f"{agg}.json"
        sizes[name] = sw.write_text(OUT / name, json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
        counts[name] = len(doc["segments"]["rows"])
        chk_speed += check_city_speed(C)
        chk_sum.append(check_stretch_sum(C))
        # keep only what the summary needs
        cities.append({"agg": agg, "H": {"weekday": C["H"]["weekday"][["t_s"]]}, "S": C["S"][["pa", "pb", "len"]],
                       "BS": C["BS"]})
        print(f"  {city}: {len(f)} segments, {time.time() - t0:.0f} s", flush=True)
    feats.sort(key=lambda x: x["properties"]["id"])
    sizes[MAP_FILE] = sw.write_text(OUT / MAP_FILE, sw.dump(feats))
    counts[MAP_FILE] = len(feats)
    why = why_stats(cities)
    cs = pd.DataFrame(chk_speed)
    sm = pd.concat(chk_sum, ignore_index=True)
    mb = {k: round(v / 1e6, 3) for k, v in sorted(sizes.items())}
    over = [k for k, v in mb.items() if v > MAX_MB]
    QA = CHECKS          # check tables stay in data/interim (not published); their summary goes into _meta.json
    QA.mkdir(parents=True, exist_ok=True)
    cs_out = cs.copy()
    for c in cs_out.columns:
        if cs_out[c].dtype.kind == "f":
            cs_out[c] = cs_out[c].map(r4)
    cs_out.to_csv(QA / "check_city_speed.csv", index=False, lineterminator="\n")
    sm_out = sm.sort_values(["agg", "stretch_dir_id", "band"], kind="stable").copy()
    for c in sm_out.columns:
        if sm_out[c].dtype.kind == "f":
            sm_out[c] = sm_out[c].map(r4)
    sm_out.to_csv(QA / "check_stretch_sum.csv", index=False, lineterminator="\n")
    comp = sm[sm["complete"]]
    summary = {
        "city_speed_max_abs_diff_on_stretches_kmh": r4(cs["diff_on"].abs().max()),
        "city_speed_max_abs_diff_all_hops_kmh": r4(cs["diff_all"].abs().max()),
        "stretch_sum_rows": int(len(sm)), "stretch_sum_complete_rows": int(len(comp)),
        "stretch_sum_abs_diff_min_p50": r4(comp["diff_min"].abs().median()),
        "stretch_sum_abs_diff_min_p95": r4(comp["diff_min"].abs().quantile(0.95)),
        "stretch_sum_abs_diff_min_max": r4(comp["diff_min"].abs().max()),
        "stretch_sum_abs_diff_taf_p50": r4(comp["diff_taf"].abs().median()),
        "stretch_sum_abs_diff_taf_p95": r4(comp["diff_taf"].abs().quantile(0.95)),
    }
    extra = {"label": "rozkładowa prędkość komunikacyjna (z rozkładu, nie pomiar), odcinki między przystankami",
             "timetable_dates": sc.days(), "osm_date": "2026-11-22",
             "sources": ["data/interim/speed/hops_<agg>_<day>.parquet (pipeline.speed_core)",
                         "pipeline.tram_stretches.city_run (stop places, stretch mapping)",
                         "data/interim/speed/osm_*.parquet (pipeline.speed_osm, OSM 2026-11-22)"],
             "rules": __doc__.split("Rules", 1)[1].split("Every speed", 1)[0].strip(),
             "model_central": ts.KIN, "range": {"dwell_s": list(ts.RANGE_DWELL_S), "cap_kmh": list(ts.RANGE_CAP_KMH)},
             "files": {"trams.geojson": "map: one feature per segment and direction, v_B km/h, t_B trips/h, "
                                        "z_B (0 min in the timetable), c (class per band), straight",
                       "<agg>.json": "detail per city for the selection panel and the what-if"},
             "features": counts, "sizes_mb": mb, "max_mb": MAX_MB, "over_max": over,
             "why_stretches": {k: (r4(v) if not isinstance(v, list) else [r4(x) for x in v]) for k, v in why.items()},
             "checks": summary}
    if "--measure-bus" in sys.argv:
        extra["bus_stop_to_stop_measured_mb"] = measure_bus()
    write_meta(OUT, "speed_segments_web", inputs=[], started=t0, extra=extra)
    print(f"speed_segments_web: {counts}; MB {mb}; over {over}; checks {summary}; why {extra['why_stretches']}; "
          f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
