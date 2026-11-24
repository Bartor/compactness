"""Part 3 of the scheduled-speed work: the tram network as stretches along the track, with OSM attributes and the
time the timetable allows beyond a simple free-running model ("implied slack").

    python -m pipeline.tram_stretches

Everything is scheduled, not real: speeds are rozkładowa prędkość komunikacyjna (stops included).

Stretch rule (fixed here, repeated in results/qa/speed/speed.md)
1. Stop places: tram stops (feed stop ids) of the reference days' tram trips are merged into places when they
   share a normalised name (gtfs_service._norm_name) within PLACE_NAME_M, or lie within PLACE_ANY_M of each other,
   unless a trip runs directly from one to the other (two stops of one name before and after a junction).
2. Place graph: an undirected edge joins two places that some tram trip runs between without another stop.
3. Break places: degree != 2 in the place graph (junctions of services, termini), places where at least
   TERM_MIN_TRIPS trips (or TERM_SHARE of the trips passing) start or end, and the TOP_PLACES busiest places of the
   city (tram trips stopping, Wednesday).
4. Chains: maximal paths between break places through degree-2 places.  A chain longer than 2 x TARGET_MIN minutes
   (mean scheduled time, Wednesday, both directions pooled) is cut at stops into round(T / TARGET_MIN) pieces of
   about equal time.  A piece shorter than MIN_MIN minutes or with fewer than MIN_HOPS hops is merged with a
   neighbour: through a break place of degree 2 (a terminus-like or busy place), or through a junction towards the
   neighbour onto which at least MERGE_SHARE of the trips on the short piece's end edge continue (so a stretch may
   pass a junction where most of its trips run straight on); if neither is possible it stays and carries
   below_min = true (its speed is reported but kept out of rankings and the main
   share).  Why 5 minutes: times are whole minutes, so a stretch time is off by the rounding at its two ends,
   standard deviation about 0.41 min (two independent uniform errors of +-0.5 min) -> about 8 % at 5 min, i.e.
   +-1.4 km/h at 17 km/h; the empirical line-to-line spread is in stretch_rounding_check.csv.
5. A stretch is used in each direction in which tram trips run along it (stretch_dir_id = stretch_id + "-A"/"-B";
   A = the direction from the place with the smaller key).  Ids: stretch_id = <city>-<sha1 of the ordered place keys,
   8 hex>, stable as long as the stop places and the break rule do not change.
6. Per stretch direction, day type and band (band of the hop's departure): speed = sum of hop lengths / sum of hop
   times over every hop traversal on the stretch (trips covering only part of it count for that part);
   scheduled time = representative length (sum of median hop lengths) / speed.

Hops that open or close a trip between two stops of the same name (arrival -> departure platform of a terminal
loop; speed_core.terminal_shuffle) are left out: their time often holds a layover.

Geometry: per edge the most frequent GTFS-shape piece of the hops on it (pipeline.speed_core), joined; straight
when no shape.  OSM attributes (pipeline.speed_osm, OSM 2026-11-22) are read off the OSM tram track that the
geometry follows: points every SAMPLE_M along the stretch are matched to the nearest railway=tram segment within
MATCH_M; match quality = share of matched points and their median distance.

Street-running inference (per piece of OSM track of at most 20 m; no OSM tag says "separated" reliably):
* street: the track segment's two nodes belong to one road way (track drawn on the road axis), or the tram way has
  embedded=yes, or a road with embedded_rails=tram lies within EMBED_M, or the nearest road centre line
  (highway motorway..residential, living_street, busway) is within STREET_2WAY_M (STREET_1WAY_M for one-way roads);
* pedestrian: same tests met by a highway=pedestrian way (shared with pedestrians, not with cars);
* separated: none of the above (own right of way, median, own alignment).
Crossings: a road crossing is a tram-track node shared with a road (residential or higher, living_street, busway)
that crosses at more than CROSS_ANGLE degrees, a railway=tram_level_crossing / level_crossing node on the track, or
a geometric intersection of track and road without a common node (neither on a bridge or in a tunnel); points
within INTERSECTION_M along the stretch are one intersection.  Signalised: a highway=traffic_signals node (or a
crossing with crossing=traffic_signals / crossing:signals=yes) within SIGNAL_M of the intersection.  Pedestrian
crossings of the track: track nodes tagged railway=crossing / tram_crossing / highway=crossing or shared with a
footway, path or cycleway, merged within 20 m; "standalone" = farther than 30 m from a road intersection.
Switches: track nodes where three or more track segments meet.  Curves: radius from three points 10 m apart on the
stretch geometry; n_curves_r50 = runs with radius < 50 m.

Implied slack = scheduled time - free-running time.  Free running per hop of length d: accelerate at A_ACC to at
most V_CAP, brake at B_BRK, plus DWELL_S per stop; optional curve limit (A_LAT).  Slack mixes signals, speed
restrictions, shared track, passenger exchange beyond the assumed dwell and timetable padding; it is not a
measurement of signal delay.
"""
from __future__ import annotations

import hashlib
import time

import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

from pipeline import gtfs_service as gs
from pipeline import speed_core as sc
from pipeline import speed_osm as so
from pipeline.boundaries import load_agglomeration
from pipeline.common import RESULTS, sig, write_json, write_meta

QA = RESULTS / "qa" / "speed" / "stretches"
TABLES = RESULTS / "tables"
LAYERS = RESULTS / "layers"
CODE_VERSION = "tram-stretches-2026-11-24.3"
CITIES = [("warszawa", "warsaw_ztm", "Warszawa"), ("krakow", "krakow_tram", "Kraków"), ("wroclaw", "wroclaw", "Wrocław"),
          ("poznan", "poznan", "Poznań"), ("lodz", "lodz", "Łódź"), ("trojmiasto", "gdansk", "Gdańsk"),
          ("gzm", "gzm", "GZM")]
CITY_CODE = {"warszawa": "WAW", "krakow": "KRK", "wroclaw": "WRO", "poznan": "POZ", "lodz": "LDZ", "trojmiasto": "GDN",
             "gzm": "GZM"}

# stretch rule
PLACE_NAME_M, PLACE_ANY_M = 300.0, 40.0
TERM_MIN_TRIPS, TERM_SHARE = 20, 0.05
TOP_PLACES = 10
MIN_MIN, MIN_HOPS, TARGET_MIN = 5.0, 2, 7.0
MERGE_SHARE = 0.5             # share of trips continuing from a short piece onto a neighbour through a junction
RANK_MIN_TRIPS = 8            # trips in the band for a stretch to enter a ranking
SLOW_KMH = 15.0               # threshold of the "slow stretches" share (sensitivity 12 / 18 in the QA files)

# OSM matching
SAMPLE_M, MATCH_M = 10.0, 15.0
STREET_2WAY_M, STREET_1WAY_M, EMBED_M = 4.5, 3.0, 10.0
CROSS_ANGLE = 35.0
CROSS_NEAR_M = 12.0           # crossing point to stretch geometry
INTERSECTION_M, SIGNAL_M = 40.0, 35.0

# free-running model (assumptions; see speed.md for the ranges they come from)
KIN = {"a_acc": 1.0,          # m/s2, mean acceleration 0 -> cap (modern low-floor trams: 1.0-1.3 starting; assumption)
       "b_brk": 1.0,          # m/s2, service braking used in normal stops (service 1.0-1.5; emergency > 2.5; assumption)
       "v_cap_kmh": 50.0,     # km/h, typical speed limit of Polish urban tram track (40-70 by section; assumption)
       "dwell_s": 20.0,       # s per stop (assumption; GTFS carries no dwell)
       "a_lat": None}         # m/s2 lateral limit in curves; None = no curve limit (variant 0.65)
SENS = [("główny", {}),
        ("przysp. 0,7 m/s²", {"a_acc": 0.7}), ("przysp. 1,3 m/s²", {"a_acc": 1.3}),
        ("hamowanie 0,8 m/s²", {"b_brk": 0.8}), ("hamowanie 1,3 m/s²", {"b_brk": 1.3}),
        ("limit 40 km/h", {"v_cap_kmh": 40.0}), ("limit 60 km/h", {"v_cap_kmh": 60.0}), ("limit 70 km/h", {"v_cap_kmh": 70.0}),
        ("postój 10 s", {"dwell_s": 10.0}), ("postój 30 s", {"dwell_s": 30.0}),
        ("łuki: 0,65 m/s²", {"a_lat": 0.65})]


def _h(s: str, n: int = 8) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


# ------------------------------------------------------------------ kinematics
def free_time(d, p: dict) -> np.ndarray:
    """Free-running time (s) of hops of length d (m) between two stops, dwell included."""
    d = np.asarray(d, float)
    a, b, v = p["a_acc"], p["b_brk"], p["v_cap_kmh"] / 3.6
    full = v * v / (2 * a) + v * v / (2 * b)
    t_full = d / v + v / (2 * a) + v / (2 * b)
    vp = np.sqrt(np.maximum(d, 0) * 2 * a * b / (a + b))
    t_short = vp / a + vp / b
    return np.where(d >= full, t_full, t_short) + p["dwell_s"]


def curve_penalty(curves: list[tuple[float, float]], p: dict) -> float:
    """Extra seconds for curves (length m, min radius m) when a lateral limit is set; approach speed = cap."""
    if not p.get("a_lat"):
        return 0.0
    a, b, v = p["a_acc"], p["b_brk"], p["v_cap_kmh"] / 3.6
    t = 0.0
    for L, R in curves:
        vc = min(v, np.sqrt(p["a_lat"] * R))
        if vc >= v:
            continue
        t += L * (1 / vc - 1 / v) + (v - vc) ** 2 / (2 * v) * (1 / a + 1 / b)
    return t


# ------------------------------------------------------------------ places and graph
def places(h: pd.DataFrame, names: dict) -> pd.DataFrame:
    s = pd.concat([h[["from_suid", "x0", "y0"]].set_axis(["suid", "x", "y"], axis=1),
                   h[["to_suid", "x1", "y1"]].set_axis(["suid", "x", "y"], axis=1)]).drop_duplicates("suid")
    s = s.dropna(subset=["x", "y"]).sort_values("suid", kind="stable").reset_index(drop=True)
    s["name"] = s["suid"].map(names).fillna(s["suid"])
    s["nkey"] = gs._norm_name(s["name"])
    xy = s[["x", "y"]].to_numpy(float)
    parent = np.arange(len(s))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    tree = cKDTree(xy)
    nk = s["nkey"].to_numpy()
    # two stops that some trip runs between directly stay separate (e.g. the two stops of the same name before and
    # after a roundabout), otherwise that hop would vanish inside one place
    sid = s["suid"].to_numpy()
    pos = {x: i for i, x in enumerate(sid)}
    nbr: dict[int, set] = {}
    for a_, b_ in set(zip(h["from_suid"], h["to_suid"])):
        if a_ in pos and b_ in pos:
            nbr.setdefault(pos[a_], set()).add(pos[b_]); nbr.setdefault(pos[b_], set()).add(pos[a_])
    members = {i: {i} for i in range(len(s))}
    for i, j in sorted(tree.query_pairs(PLACE_NAME_M)):
        d = np.hypot(*(xy[i] - xy[j]))
        if d <= PLACE_ANY_M or nk[i] == nk[j]:
            a, b = find(i), find(j)
            if a == b:
                continue
            # never join two groups when a trip runs directly from a stop of one to a stop of the other
            if any(nbr.get(m, set()) & members[b] for m in members[a]):
                continue
            lo, hi = min(a, b), max(a, b)
            parent[hi] = lo
            members[lo] |= members.pop(hi)
    s["root"] = [find(i) for i in range(len(s))]
    g = s.groupby("root")
    cx, cy = g["x"].transform("mean"), g["y"].transform("mean")
    nm = g["nkey"].agg(lambda v: v.value_counts().sort_index().sort_values(ascending=False, kind="stable").index[0])
    disp = g["name"].agg(lambda v: v.str.replace(r"\s+\d{1,2}$", "", regex=True).value_counts().sort_index()
                         .sort_values(ascending=False, kind="stable").index[0])
    s["place_key"] = s["root"].map(nm) + "@" + (cx / 100).round().astype(int).astype(str) + "_" + \
        (cy / 100).round().astype(int).astype(str)
    s["place_name"] = s["root"].map(disp)
    s["px"], s["py"] = cx, cy
    return s[["suid", "name", "x", "y", "place_key", "place_name", "px", "py"]]


def chains(adj: dict, brk: set) -> list[list[str]]:
    seen_e, out = set(), []
    for a in sorted(adj):
        if a not in brk:
            continue
        for b in sorted(adj[a]):
            if (a, b) in seen_e:
                continue
            path = [a, b]
            seen_e.add((a, b)); seen_e.add((b, a))
            while path[-1] not in brk:
                cur, prev = path[-1], path[-2]
                nxt = [n for n in sorted(adj[cur]) if n != prev]
                if len(nxt) != 1 or (cur, nxt[0]) in seen_e:
                    break
                path.append(nxt[0])
                seen_e.add((cur, nxt[0])); seen_e.add((nxt[0], cur))
            out.append(path)
    # cycles without break places
    for a in sorted(adj):
        for b in sorted(adj[a]):
            if (a, b) not in seen_e:
                path = [a, b]
                seen_e.add((a, b)); seen_e.add((b, a))
                while path[-1] != a:
                    cur, prev = path[-1], path[-2]
                    nxt = [n for n in sorted(adj[cur]) if n != prev and (cur, n) not in seen_e]
                    if not nxt:
                        break
                    path.append(nxt[0]); seen_e.add((cur, nxt[0])); seen_e.add((nxt[0], cur))
                out.append(path)
    return out


def build_stretches(h: pd.DataFrame, pl: pd.DataFrame) -> tuple[list[list[str]], dict, set]:
    pk = dict(zip(pl["suid"], pl["place_key"]))
    e = h.assign(pa=h["from_suid"].map(pk), pb=h["to_suid"].map(pk)).dropna(subset=["pa", "pb"])
    e = e[e["pa"] != e["pb"]]
    adj: dict[str, set] = {}
    for a, b in set(zip(e["pa"], e["pb"])):
        adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    # terminus-like places and busy places
    tr = h.groupby("uid").agg(f=("from_suid", "first"), l=("to_suid", "last"))
    ends = pd.concat([tr["f"].map(pk), tr["l"].map(pk)]).value_counts()
    visits = pd.concat([e["pa"], e.groupby("uid")["pb"].last()]).value_counts()
    brk = {p for p in adj if len(adj[p]) != 2}
    for p, n in ends.items():
        if n >= TERM_MIN_TRIPS or n >= TERM_SHARE * visits.get(p, 0):
            brk.add(p)
    busy = e.groupby("pa")["uid"].nunique().sort_values(ascending=False, kind="stable")
    busy = busy.reset_index().sort_values(["uid", "pa"], ascending=[False, True], kind="stable")
    top = set(busy["pa"].head(TOP_PLACES))
    brk |= top
    ch = chains(adj, brk)
    # edge time (mean scheduled hop time, both directions pooled) and hop counts
    et = e.groupby(["pa", "pb"])["t_s"].mean()
    etd = et.to_dict()
    _em: dict = {}

    def etime(a, b):
        k_ = (a, b) if a < b else (b, a)
        if k_ not in _em:
            v = [etd.get((a, b)), etd.get((b, a))]
            v = [x for x in v if x is not None and np.isfinite(x)]
            _em[k_] = sum(v) / len(v) / 60 if v else 0.0
        return _em[k_]
    # split long chains
    pieces = []
    for c in ch:
        tt = np.array([etime(a, b) for a, b in zip(c[:-1], c[1:])])
        T = tt.sum()
        k = int(round(T / TARGET_MIN)) if T >= 2 * TARGET_MIN else 1
        if k <= 1:
            pieces.append(c); continue
        cum = np.r_[0, np.cumsum(tt)]
        cuts = [0]
        for q in range(1, k):
            j = int(np.argmin(np.abs(cum - T * q / k)))
            if cuts[-1] < j < len(c) - 1:
                cuts.append(j)
        cuts.append(len(c) - 1)
        for i0, i1 in zip(cuts[:-1], cuts[1:]):
            pieces.append(c[i0:i1 + 1])
    # through-running counts: trips going a -> b -> c (both orientations pooled per unordered end pair)
    e2 = e.sort_values(["uid", "k"], kind="stable")
    same = e2["uid"].to_numpy()[1:] == e2["uid"].to_numpy()[:-1]
    cont = same & (e2["pb"].to_numpy()[:-1] == e2["pa"].to_numpy()[1:])
    tri = pd.DataFrame({"a": e2["pa"].to_numpy()[:-1][cont], "b": e2["pb"].to_numpy()[:-1][cont],
                        "c": e2["pb"].to_numpy()[1:][cont]})
    tri = tri[tri["a"] != tri["c"]]
    through: dict[tuple, int] = {}
    for (a, b, c), n in tri.groupby(["a", "b", "c"]).size().items():
        k_ = (min(a, c), b, max(a, c))
        through[k_] = through.get(k_, 0) + int(n)
    trav = e.assign(u=np.minimum(e["pa"], e["pb"]), v=np.maximum(e["pa"], e["pb"])).groupby(["u", "v"]).size()

    def thr(n1, e_, m1):
        return through.get((min(n1, m1), e_, max(n1, m1)), 0)

    # merge short pieces: through a degree-2 break place, or through a junction towards the neighbour onto which
    # at least MERGE_SHARE of the trips on the short piece's end edge continue
    _pm: dict = {}

    def ptime(c):
        k_ = tuple(c)
        if k_ not in _pm:
            _pm[k_] = sum(etime(a, b) for a, b in zip(c[:-1], c[1:]))
        return _pm[k_]

    def short(c):
        return ptime(c) < MIN_MIN or len(c) - 1 < MIN_HOPS
    changed = True
    while changed:
        changed = False
        pieces.sort(key=lambda c: (ptime(c), c))
        ends_of: dict[str, list[int]] = {}
        for i, c in enumerate(pieces):
            ends_of.setdefault(c[0], []).append(i); ends_of.setdefault(c[-1], []).append(i)
        for i, c in enumerate(pieces):
            if not short(c) or c[0] == c[-1]:
                continue
            opts = []
            for end in (c[0], c[-1]):
                n1 = c[1] if end == c[0] else c[-2]
                nt = trav.get((min(n1, end), max(n1, end)), 0)
                for j in ends_of.get(end, []):
                    if j == i:
                        continue
                    o = pieces[j]
                    if o[0] == o[-1]:
                        continue
                    m1 = o[1] if o[0] == end else o[-2]
                    simple = len(adj[end]) == 2 and len(ends_of[end]) == 2
                    share = thr(n1, end, m1) / nt if nt else 0.0
                    if not (simple or share >= MERGE_SHARE):
                        continue
                    a_ = c if c[-1] == end else c[::-1]
                    b_ = o if o[0] == end else o[::-1]
                    if len(set(a_ + b_[1:])) < len(a_) + len(b_) - 1:
                        continue
                    opts.append((-share if not simple else -2.0, ptime(o), end, j))
            if not opts:
                continue
            _, _, end, j = sorted(opts)[0]
            o = pieces[j]
            a = c if c[-1] == end else c[::-1]
            b = o if o[0] == end else o[::-1]
            new = a + b[1:]
            pieces = [p for x, p in enumerate(pieces) if x not in (i, j)] + [new]
            changed = True
            break
    # canonical orientation: smaller end key first
    out = []
    for c in pieces:
        if (c[-1], c[::-1]) < (c[0], c):
            c = c[::-1]
        out.append(c)
    out.sort()
    return out, adj, brk


# ------------------------------------------------------------------ OSM preparation per city
def _seg_arrays(ways: pd.DataFrame, max_len: float | None = None):
    """Segments of ways: (ax, ay, bx, by, way index, node a, node b, segment index in way)."""
    A, B, W, NA, NB = [], [], [], [], []
    for i, (xs, ys, rf) in enumerate(zip(ways["x"], ways["y"], ways["refs"])):
        n = len(xs) - 1
        if n < 1:
            continue
        A.append(np.c_[xs[:-1], ys[:-1]]); B.append(np.c_[xs[1:], ys[1:]])
        W.append(np.full(n, i)); NA.append(rf[:-1]); NB.append(rf[1:])
    return (np.vstack(A), np.vstack(B), np.concatenate(W), np.concatenate(NA), np.concatenate(NB))


def osm_city(agg: str, osm: dict) -> dict:
    fua = load_agglomeration(agg)["fua"].buffer(2000)
    x0, y0, x1, y1 = fua.bounds

    def inbox(df):
        return np.array([(xs.max() >= x0) & (xs.min() <= x1) & (ys.max() >= y0) & (ys.min() <= y1)
                         for xs, ys in zip(df["x"], df["y"])])
    tw = osm["tram"]
    tw = tw[inbox(tw)].reset_index(drop=True)
    tA, tB, tW, tNA, tNB = _seg_arrays(tw)
    tgeom = shapely.linestrings(np.stack([tA, tB], axis=1))
    ttree = shapely.STRtree(tgeom)
    # roads near the track
    rd = osm["road"]
    rd = rd[inbox(rd)]
    rd = rd[rd["highway"] != "service"].reset_index(drop=True)
    rA, rB, rW, rNA, rNB = _seg_arrays(rd)
    rgeom = shapely.linestrings(np.stack([rA, rB], axis=1))
    near = np.unique(ttree.query(rgeom, predicate="dwithin", distance=30.0)[0])
    rA, rB, rW, rNA, rNB, rgeom = rA[near], rB[near], rW[near], rNA[near], rNB[near], rgeom[near]
    rtree = shapely.STRtree(rgeom)
    hw = rd["highway"].to_numpy()
    oneway = rd["oneway"].isin(["yes", "-1", "1", "true"]).to_numpy() | rd["junction"].isin(["roundabout", "circular"]).to_numpy()
    emb = rd["embedded_rails"].fillna("").str.contains("tram").to_numpy()
    rbridge = (rd["bridge"].fillna("no") != "no").to_numpy() | (rd["tunnel"].fillna("no") != "no").to_numpy()
    rcls = rd["cls"].to_numpy()
    # road node -> road ways
    rnode_way: dict[int, set] = {}
    for i, rf in enumerate(rd["refs"]):
        for n in rf:
            rnode_way.setdefault(int(n), set()).add(i)
    # ---- classify track pieces (<= 20 m)
    pcs_a, pcs_b, pcs_seg = [], [], []
    L = np.hypot(*(tB - tA).T)
    nsub = np.maximum(1, np.ceil(L / 20.0)).astype(int)
    for k in range(int(nsub.max())):
        m = nsub > k
        f0 = k / nsub[m]; f1 = (k + 1) / nsub[m]
        pcs_a.append(tA[m] + (tB[m] - tA[m]) * f0[:, None]); pcs_b.append(tA[m] + (tB[m] - tA[m]) * f1[:, None])
        pcs_seg.append(np.flatnonzero(m))
    pa, pb, pseg = np.vstack(pcs_a), np.vstack(pcs_b), np.concatenate(pcs_seg)
    o = np.argsort(pseg, kind="stable")
    pa, pb, pseg = pa[o], pb[o], pseg[o]
    mid = (pa + pb) / 2
    mpts = shapely.points(mid)
    cls = np.full(len(pseg), "separated", dtype=object)
    # shared nodes with one road way
    seg_shared = np.full(len(tA), None, dtype=object)
    for i in range(len(tA)):
        wa, wb = rnode_way.get(int(tNA[i])), rnode_way.get(int(tNB[i]))
        if wa and wb:
            common = sorted(wa & wb)
            if common:
                seg_shared[i] = common[0]
    emb_way = tw["embedded"].fillna("").eq("yes").to_numpy()[tW]
    # nearest road centre line
    idx_pt, idx_rd = rtree.query_nearest(mpts, max_distance=STREET_2WAY_M + 0.01, return_distance=False, all_matches=False)
    dist = np.full(len(mpts), np.inf)
    nearest_road = np.full(len(mpts), -1)
    if len(idx_pt):
        dd = shapely.distance(mpts[idx_pt], rgeom[idx_rd])
        dist[idx_pt] = dd
        nearest_road[idx_pt] = rW[idx_rd]
    near_ok = np.isfinite(dist) & (nearest_road >= 0)
    nr = np.where(nearest_road >= 0, nearest_road, 0)
    near_ok &= np.where(oneway[nr], dist <= STREET_1WAY_M, dist <= STREET_2WAY_M)
    # embedded_rails roads within EMBED_M
    emb_idx = np.flatnonzero(emb[rW])
    emb_hit = np.zeros(len(mpts), bool)
    if len(emb_idx):
        etree = shapely.STRtree(rgeom[emb_idx])
        hit = etree.query(mpts, predicate="dwithin", distance=EMBED_M)[0]
        emb_hit[np.unique(hit)] = True
    shared = seg_shared[pseg]
    has_shared = np.array([s is not None for s in shared])
    shared_hw = np.array([hw[s] if s is not None else "" for s in shared], dtype=object)
    near_hw = np.where(near_ok, hw[nr], "")
    is_ped = (has_shared & (shared_hw == "pedestrian")) | (~has_shared & near_ok & (near_hw == "pedestrian"))
    is_street = (has_shared & (shared_hw != "pedestrian")) | emb_way[pseg] | emb_hit | (near_ok & (near_hw != "pedestrian"))
    cls[is_street] = "street"
    cls[is_ped & ~(emb_way[pseg] | emb_hit)] = "pedestrian"
    reason = np.full(len(pseg), "", dtype=object)
    reason[has_shared] = "węzły wspólne z drogą"
    reason[(reason == "") & emb_way[pseg]] = "tor embedded=yes"
    reason[(reason == "") & emb_hit] = "droga z embedded_rails=tram"
    reason[(reason == "") & near_ok] = "oś jezdni blisko toru"
    piece_geom = shapely.linestrings(np.stack([pa, pb], axis=1))
    ptree = shapely.STRtree(piece_geom)
    # ---- points: switches, crossings
    deg = pd.Series(np.r_[tNA, tNB]).value_counts()
    node_xy = {}
    for xs, ys, rf in zip(tw["x"], tw["y"], tw["refs"]):
        for x, y, n in zip(xs, ys, rf):
            node_xy[int(n)] = (x, y)
    sw = [node_xy[n] for n in deg[deg >= 3].index if n in node_xy]
    # track direction per node (from its segment)
    tdir = {}
    for i in range(len(tA)):
        v = tB[i] - tA[i]
        tdir.setdefault(int(tNA[i]), v); tdir.setdefault(int(tNB[i]), v)
    pts = []          # (x, y, kind, minor)
    rway_nodes = [list(map(int, rf)) for rf in rd["refs"]]
    for n, (x, y) in node_xy.items():
        ws = rnode_way.get(n)
        if not ws:
            continue
        for w in sorted(ws):
            if rcls[w] < 0 and hw[w] != "living_street":
                continue
            rf = rway_nodes[w]
            j = rf.index(n)
            nb = [rf[j - 1]] if j > 0 else []
            nb += [rf[j + 1]] if j + 1 < len(rf) else []
            rx, ry = rd["x"].iloc[w], rd["y"].iloc[w]
            q = np.array([rx[j], ry[j]])
            neigh = [np.array([rx[j + d], ry[j + d]]) for d in (-1, 1) if 0 <= j + d < len(rf)]
            if not neigh:
                continue
            rv = neigh[-1] - neigh[0] if len(neigh) == 2 else neigh[0] - q
            tv = tdir.get(n)
            if tv is None:
                continue
            c = abs(np.dot(rv, tv)) / (np.linalg.norm(rv) * np.linalg.norm(tv) + 1e-9)
            ang = np.degrees(np.arccos(np.clip(c, 0, 1)))
            if ang > CROSS_ANGLE:
                pts.append((x, y, "road", rcls[w] < 1))
                break
    xn = osm["xnodes"]
    tn = xn[xn["id"].isin(node_xy.keys())]
    for r in tn.itertuples(index=False):
        if r.railway in ("level_crossing", "tram_level_crossing"):
            pts.append((r.x, r.y, "road", False))
        if r.railway in ("crossing", "tram_crossing") or r.highway == "crossing":
            pts.append((r.x, r.y, "ped", False))
    foot = set(osm["foot"]["id"].to_numpy().tolist())
    for n, (x, y) in node_xy.items():
        if n in foot:
            pts.append((x, y, "ped", False))
    # geometric crossings without a common node
    main_r = np.flatnonzero((rcls[rW] >= 1) & ~rbridge[rW])
    tb = (tw["bridge"].fillna("no") != "no").to_numpy() | (tw["tunnel"].fillna("no") != "no").to_numpy()
    t_ok = np.flatnonzero(~tb[tW])
    if len(main_r) and len(t_ok):
        rt = shapely.STRtree(rgeom[main_r])
        it, ir = rt.query(tgeom[t_ok], predicate="crosses")
        for a_, b_ in zip(it, ir):
            ti, ri = t_ok[a_], main_r[b_]
            if {int(tNA[ti]), int(tNB[ti])} & {int(rNA[ri]), int(rNB[ri])}:
                continue
            p = shapely.intersection(tgeom[ti], rgeom[ri])
            if p.geom_type == "Point":
                pts.append((p.x, p.y, "road", False))
    P = pd.DataFrame(pts, columns=["x", "y", "kind", "minor"]).drop_duplicates().sort_values(["kind", "x", "y"], kind="stable")
    P = P.reset_index(drop=True)
    sg = xn[(xn["highway"].fillna("").str.contains("traffic_signals")) | (xn["crossing"] == "traffic_signals") |
            (xn["crossing_signals"] == "yes") | (xn["traffic_signals"].notna())]
    sg = sg[(sg["x"] >= x0) & (sg["x"] <= x1) & (sg["y"] >= y0) & (sg["y"] <= y1)]
    return {"pieces": {"geom": piece_geom, "tree": ptree, "cls": cls, "reason": reason, "seg": pseg,
                       "way": tW[pseg], "dist": dist, "near_hw": near_hw},
            "tram_ways": tw, "points": P, "ptree": shapely.STRtree(shapely.points(P[["x", "y"]].to_numpy())) if len(P) else None,
            "signals": cKDTree(sg[["x", "y"]].to_numpy()) if len(sg) else None,
            "switches": np.array(sw) if sw else np.empty((0, 2)),
            "road_names": rd["name"].to_numpy(), "road_hw": hw, "road_emb": emb, "road_oneway": oneway,
            "road_tree": rtree, "road_way_of_seg": rW, "road_geom": rgeom}


def _resample(coords: np.ndarray, step: float) -> tuple[np.ndarray, np.ndarray]:
    seg = np.hypot(*np.diff(coords, axis=0).T)
    cum = np.r_[0, np.cumsum(seg)]
    L = cum[-1]
    s = np.arange(0, L + 1e-9, step) if L > 0 else np.array([0.0])
    x = np.interp(s, cum, coords[:, 0]); y = np.interp(s, cum, coords[:, 1])
    return np.c_[x, y], s


def curves(coords: np.ndarray) -> list[tuple[float, float]]:
    """Runs of the line with radius < 100 m: (length m, min radius m), from 3 points 10 m apart (5 m resampling)."""
    p, s = _resample(coords, 5.0)
    if len(p) < 5:
        return []
    a, b, c = p[:-4], p[2:-2], p[4:]
    ab = np.hypot(*(b - a).T); bc = np.hypot(*(c - b).T); ca = np.hypot(*(a - c).T)
    area2 = np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))
    R = np.where(area2 > 1e-6, ab * bc * ca / (2 * area2 + 1e-12), np.inf)
    tight = R < 100
    out = []
    i = 0
    while i < len(R):
        if tight[i]:
            j = i
            while j + 1 < len(R) and tight[j + 1]:
                j += 1
            out.append(((j - i + 1) * 5.0, float(R[i:j + 1].min())))
            i = j + 1
        else:
            i += 1
    return out


def _cluster_1d(a: np.ndarray, gap: float) -> list[np.ndarray]:
    if len(a) == 0:
        return []
    o = np.sort(a)
    br = np.flatnonzero(np.diff(o) > gap)
    return np.split(o, br + 1)


OSM_COLS = ["osm_match_share", "osm_match_median_m", "share_street", "share_pedestrian", "share_separated",
            "share_unmatched", "n_road_crossings", "n_signalised", "n_minor_crossings", "n_ped_crossings",
            "n_ped_standalone", "n_switches", "n_curves_r50", "len_curves_r100_m"]


def no_osm(coords: np.ndarray) -> dict:
    out = {c: None for c in OSM_COLS}
    out["length_m"] = float(shapely.length(shapely.linestrings(coords)))
    out["_curves"] = []
    return out


def osm_attrs(coords: np.ndarray, O: dict) -> dict:
    line = shapely.linestrings(coords)
    L = float(shapely.length(line))
    pts, s = _resample(coords, SAMPLE_M)
    pg = shapely.points(pts)
    pc = O["pieces"]
    ip, ig = pc["tree"].query_nearest(pg, max_distance=MATCH_M, return_distance=False, all_matches=False)
    d = np.full(len(pg), np.nan)
    kind = np.full(len(pg), "brak dopasowania", dtype=object)
    if len(ip):
        d[ip] = shapely.distance(pg[ip], pc["geom"][ig])
        kind[ip] = pc["cls"][ig]
    n = len(pg)
    out = {"length_m": L, "osm_match_share": float(np.isfinite(d).mean()),
           "osm_match_median_m": float(np.nanmedian(d)) if np.isfinite(d).any() else None,
           "share_street": float((kind == "street").mean()), "share_pedestrian": float((kind == "pedestrian").mean()),
           "share_separated": float((kind == "separated").mean()), "share_unmatched": float((kind == "brak dopasowania").mean())}
    # crossings
    P = O["points"]
    road_c, ped_c, minor_c, sig_n = [], [], [], 0
    if O["ptree"] is not None:
        hit = O["ptree"].query(line, predicate="dwithin", distance=CROSS_NEAR_M)
        if len(hit):
            Q = P.iloc[np.sort(hit)]
            al = shapely.line_locate_point(line, shapely.points(Q[["x", "y"]].to_numpy()))
            Q = Q.assign(al=al)
            Q = Q[(Q["al"] > 1.0) & (Q["al"] < L - 1.0)]
            road = Q[(Q["kind"] == "road") & ~Q["minor"]]
            minor = Q[(Q["kind"] == "road") & Q["minor"]]
            road_c = _cluster_1d(road["al"].to_numpy(), INTERSECTION_M)
            minor_c = _cluster_1d(minor["al"].to_numpy(), INTERSECTION_M)
            ped = Q[Q["kind"] == "ped"]
            ped_c = _cluster_1d(ped["al"].to_numpy(), 20.0)
            if O["signals"] is not None and len(road):
                for c in road_c:
                    sub = road[road["al"].between(c.min() - 0.01, c.max() + 0.01)]
                    dd, _ = O["signals"].query(sub[["x", "y"]].to_numpy(), k=1)
                    if (dd <= SIGNAL_M).any():
                        sig_n += 1
    rc_mid = np.array([c.mean() for c in road_c])
    ped_alone = sum(1 for c in ped_c if len(rc_mid) == 0 or np.abs(rc_mid - c.mean()).min() > 30.0)
    out.update({"n_road_crossings": len(road_c), "n_signalised": sig_n, "n_minor_crossings": len(minor_c),
                "n_ped_crossings": len(ped_c), "n_ped_standalone": int(ped_alone)})
    sw = O["switches"]
    if len(sw):
        tr = shapely.STRtree(shapely.points(sw))
        hs = tr.query(line, predicate="dwithin", distance=8.0)
        al = shapely.line_locate_point(line, shapely.points(sw[np.sort(hs)])) if len(hs) else np.array([])
        out["n_switches"] = len(_cluster_1d(np.asarray(al), 15.0))
    else:
        out["n_switches"] = 0
    cv = curves(coords)
    out["n_curves_r50"] = int(sum(1 for Lc, R in cv if R < 50))
    out["len_curves_r100_m"] = float(sum(Lc for Lc, R in cv))
    out["_curves"] = cv
    return out


# ------------------------------------------------------------------ per city
def city_run(agg: str, feeds, city: str, osm: dict | None, mode: str = "tram", prefix: str = "") -> dict:
    """Stretches of one mode in one agglomeration (feeds: list of feed ids).  ``osm`` None = no OSM attributes
    (buses, trolleybuses: the OSM tram-track logic does not apply)."""
    feeds = [feeds] if isinstance(feeds, str) else list(feeds)
    st = gs.stops(agg, sc.VARIANT)
    names = dict(zip(st["suid"], st["stop_name"].astype(str)))
    H = {}
    for dt in sc.days():
        h = sc.hops(agg, dt)
        H[dt] = h[(h["mode"] == mode) & (h["feed"].isin(feeds)) & ~h["repl_bus"].astype(bool)].copy()
        H[dt]["line"] = H[dt]["line"].astype(str)
        H[dt] = H[dt][~sc.terminal_shuffle(H[dt], agg)].copy()
    hw = H["weekday"]
    pl = places(pd.concat([H["weekday"], H["saturday"]]), names)
    pk = dict(zip(pl["suid"], pl["place_key"]))
    pname = dict(zip(pl["place_key"], pl["place_name"]))
    pxy = pl.drop_duplicates("place_key").set_index("place_key")[["px", "py"]]
    ch, adj, brk = build_stretches(hw, pl)
    code = CITY_CODE[agg]
    # directed edges -> (stretch_dir_id, edge index)
    emap, srows = {}, []
    for c in ch:
        sid = f"{code}-{prefix}{_h('|'.join(c))}"
        for dname, seq in (("A", c), ("B", c[::-1])):
            for i, (a, b) in enumerate(zip(seq[:-1], seq[1:])):
                emap[(a, b)] = (sid, dname, i)
            srows.append({"stretch_id": sid, "dir": dname, "places": seq})
    for dt in H:
        H[dt]["pa"] = H[dt]["from_suid"].map(pk)
        H[dt]["pb"] = H[dt]["to_suid"].map(pk)
        m = [emap.get((a, b)) for a, b in zip(H[dt]["pa"], H[dt]["pb"])]
        H[dt]["sid"] = [x[0] if x else None for x in m]
        H[dt]["sdir"] = [x[1] if x else None for x in m]
        H[dt]["eidx"] = [x[2] if x else -1 for x in m]
    # stop pairs -> stretch
    sp = H["weekday"].dropna(subset=["sid"]).groupby(["from_suid", "to_suid", "sid", "sdir", "eidx"]).size().rename("trips_weekday").reset_index()
    # representative edge geometry and length
    shp = {f: sc.shape_arrays(f) for f in feeds}
    hwm = H["weekday"].dropna(subset=["sid"])
    elen = hwm.groupby(["sid", "sdir", "eidx"])["len_m"].median()
    rep = (hwm[hwm["len_src"] == "shape"].groupby(["sid", "sdir", "eidx", "pid", "k"]).size().rename("n").reset_index()
           .sort_values(["sid", "sdir", "eidx", "n", "pid", "k"], ascending=[True, True, True, False, True, True], kind="stable")
           .drop_duplicates(["sid", "sdir", "eidx"]))
    repk = {(r.sid, r.sdir, r.eidx): (r.pid, r.k) for r in rep.itertuples(index=False)}
    hp = hwm.drop_duplicates(["pid", "k"]).set_index(["pid", "k"])
    O = osm_city(agg, osm) if osm is not None else None
    rows, geoms = [], []
    for s in srows:
        sid, dname, seq = s["stretch_id"], s["dir"], s["places"]
        ne = len(seq) - 1
        present = [(sid, dname, i) in elen.index for i in range(ne)]
        if not any(present):
            continue
        parts = []
        for i in range(ne):
            key = (sid, dname, i)
            if key in repk:
                r = hp.loc[repk[key]]
                parts.append(sc.hop_geometry(r, shp[r["feed"]]))
            else:
                a, b = seq[i], seq[i + 1]
                parts.append(np.array([pxy.loc[a].to_numpy(), pxy.loc[b].to_numpy()], dtype=float))
        coords = np.vstack([parts[0]] + [p[1:] for p in parts[1:]])
        lens = np.array([elen.get((sid, dname, i), np.nan) for i in range(ne)])
        attrs = osm_attrs(coords, O) if O is not None else no_osm(coords)
        rows.append({"agglomeration": agg, "city": city, "stretch_id": sid, "dir": dname,
                     "stretch_dir_id": f"{sid}-{dname}", "from_place": pname[seq[0]], "to_place": pname[seq[-1]],
                     "name": f"{pname[seq[0]]} → {pname[seq[-1]]}", "n_stops": len(seq), "n_hops": ne,
                     "edges_with_service": int(sum(present)),
                     "stop_sequence": " > ".join(pname[p] for p in seq), "place_keys": " > ".join(seq),
                     "length_m": float(np.nansum(lens)) if np.isfinite(lens).all() else float(attrs["length_m"]),
                     "edge_lengths_m": [float(x) for x in lens],
                     **{k: v for k, v in attrs.items() if k != "length_m"}})
        geoms.append(coords)
    S = pd.DataFrame(rows)
    # geometry quality and feeds per stretch direction (Wednesday hops)
    q = hwm.assign(sd=hwm["sid"] + "-" + hwm["sdir"])
    S["mode"] = mode
    S["share_hops_shape"] = S["stretch_dir_id"].map(q.groupby("sd")["len_src"].agg(lambda v: float((v == "shape").mean())))
    S["feeds"] = S["stretch_dir_id"].map(q.groupby("sd")["feed"].agg(lambda v: ", ".join(sorted(set(v)))))
    # ---- stats per band
    st_rows = []
    for dt, h in H.items():
        hh = h.dropna(subset=["sid"])
        hh = hh.assign(sd=hh["sid"] + "-" + hh["sdir"])
        for band in sc.band_ids(dt) + ["all_day"]:
            g = hh if band == "all_day" else hh[hh["band"] == band]
            if g.empty:
                continue
            a = g.groupby("sd").agg(len_sum=("len_m", "sum"), t_sum=("t_s", "sum"), n_hops=("uid", "size"),
                                    n_trips=("uid", "nunique"))
            a["lines"] = g.groupby("sd")["line"].agg(lambda v: ", ".join(sorted(set(map(str, v)), key=_line_key)))
            a = a.reset_index().assign(day_type=dt, band=band)
            st_rows.append(a)
    ST = pd.concat(st_rows, ignore_index=True)
    unm = {dt: float(H[dt]["sid"].isna().mean()) for dt in H}
    return {"S": S, "geoms": geoms, "ST": ST, "pairs": sp, "places": pl, "brk": brk, "adj": adj, "chains": ch,
            "H": H, "O": O, "unmapped_hop_share": unm}


def _line_key(s: str):
    try:
        return (0, int(s), s)
    except ValueError:
        return (1, 0, s)


# ------------------------------------------------------------------ assembly
def stretch_metrics(S: pd.DataFrame, ST: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Per stretch direction x day x band: speed, scheduled time, free time, slack (model parameters p)."""
    base = S.set_index("stretch_dir_id")
    ft = {}
    for sd, r in base.iterrows():
        el = np.asarray(r["edge_lengths_m"], float)
        el = el[np.isfinite(el)]
        ft[sd] = float(free_time(el, p).sum() + curve_penalty(r["_curves"], p)) / 60
    m = ST.copy()
    m["speed_kmh"] = m["len_sum"] / m["t_sum"] * 3.6
    L = m["sd"].map(base["length_m"])
    m["sched_min"] = L / (m["speed_kmh"] / 3.6) / 60
    m["free_min"] = m["sd"].map(ft)
    m["slack_min"] = m["sched_min"] - m["free_min"]
    m["slack_min_per_km"] = m["slack_min"] / (L / 1000)
    m["length_m"] = L
    return m


def run() -> dict:
    t0 = time.time()
    QA.mkdir(parents=True, exist_ok=True)
    osm = so.load()
    allS, allST, allP, geoms, diag, spot = [], [], [], [], [], []
    per_city = {}
    for agg, feed, city in CITIES:
        R = city_run(agg, feed, city, osm)
        per_city[agg] = R
        allS.append(R["S"]); allST.append(R["ST"]); geoms += R["geoms"]
        pr = R["pairs"].copy()
        pr.insert(0, "agglomeration", agg)
        allP.append(pr)
        S = R["S"]
        diag.append({"agglomeration": agg, "city": city, "feed": feed, "places": int(R["places"]["place_key"].nunique()),
                     "tram_stops": int(len(R["places"])), "break_places": len(R["brk"]),
                     "stretches": int(S["stretch_id"].nunique()), "stretch_directions": int(len(S)),
                     "median_length_m": float(S["length_m"].median()), "median_stops": float(S["n_stops"].median()),
                     "hops_unmapped_weekday": R["unmapped_hop_share"]["weekday"],
                     "hops_unmapped_saturday": R["unmapped_hop_share"]["saturday"],
                     "osm_match_share_median": float(S["osm_match_share"].median()),
                     "osm_match_share_p10": float(S["osm_match_share"].quantile(.1)),
                     "osm_match_distance_median_m": float(S["osm_match_median_m"].median()),
                     "share_street_len": float((S["share_street"] * S["length_m"]).sum() / S["length_m"].sum()),
                     "share_pedestrian_len": float((S["share_pedestrian"] * S["length_m"]).sum() / S["length_m"].sum()),
                     "share_separated_len": float((S["share_separated"] * S["length_m"]).sum() / S["length_m"].sum()),
                     "share_unmatched_len": float((S["share_unmatched"] * S["length_m"]).sum() / S["length_m"].sum())})
        print(f"  {city}: {S['stretch_id'].nunique()} stretches, {len(S)} directions, {time.time() - t0:.0f} s", flush=True)
    S = pd.concat(allS, ignore_index=True)
    ST = pd.concat(allST, ignore_index=True)
    M = stretch_metrics(S, ST, KIN)
    from pipeline import tram_stretches_out as out
    res = out.write_all(S, M, ST, geoms, pd.concat(allP, ignore_index=True), pd.DataFrame(diag), per_city, t0)
    del per_city
    res["bus"] = run_bus(t0)
    res["lines"] = out.write_rail_metro(t0)
    return res


def bus_feeds(agg: str, mode: str) -> list[str]:
    """Official feeds of the agglomeration with trips of ``mode`` that carry shapes (krakow_ald has none)."""
    off = set(gs.feeds_for(agg, "official"))
    t = gs.active_trips(agg, sc.days()["weekday"], "all")
    t = t[(t["route_class"] == mode) & t["feed"].isin(off) & ~t["is_replacement_bus"].astype(bool)]
    sh = t.groupby("feed")["dist_method"].agg(lambda v: (v == "shape").mean())
    return sorted(sh[sh >= 0.9].index)


def run_bus(t0: float) -> dict:
    """The same stretch method for buses and trolleybuses (official feeds with shapes), no OSM attributes, no slack."""
    from pipeline import tram_stretches_out as out
    allS, allST, geoms, diag = [], [], [], []
    for agg, _, city in CITIES:
        for mode, prefix in (("bus", "b"), ("trolleybus", "t")):
            feeds = bus_feeds(agg, mode)
            if not feeds:
                continue
            R = city_run(agg, feeds, sc.AGG_NAMES[agg], None, mode, prefix)
            S = R["S"]
            allS.append(S); allST.append(R["ST"]); geoms += R["geoms"]
            diag.append({"agglomeration": agg, "mode": mode, "feeds": ", ".join(feeds),
                         "stops": int(len(R["places"])), "places": int(R["places"]["place_key"].nunique()),
                         "stretches": int(S["stretch_id"].nunique()), "stretch_directions": int(len(S)),
                         "median_length_m": float(S["length_m"].median()),
                         "hops_unmapped_weekday": R["unmapped_hop_share"]["weekday"],
                         "share_hops_shape_median": float(S["share_hops_shape"].median())})
            print(f"  {sc.AGG_NAMES[agg]} {mode}: {len(S)} directions, {time.time() - t0:.0f} s", flush=True)
    S = pd.concat(allS, ignore_index=True)
    ST = pd.concat(allST, ignore_index=True)
    M = stretch_metrics(S, ST, KIN)
    return out.write_bus(S, M, geoms, pd.DataFrame(diag), t0)


if __name__ == "__main__":
    run()
