"""Alternative centres for the centre-sensitivity check of phase 1 (rho, half-population radius).

Three centres per agglomeration (pipeline.density uses them):
* ``config``     the configured centre (config.yaml ``centre``);
* ``townhall``   the city hall of the core city (first URAU city in ``city_codes``) from OSM
                 ``amenity=townhall``; rule below, hand picks listed in TOWNHALL_PICK with the reason;
* ``popcentroid`` the population-weighted centroid of the core (computed in pipeline.density on the
                 census-scaled 100 m grid, not here).

Townhall rule
1. Every OSM object tagged ``amenity=townhall`` in Poland (nodes; ways and multipolygon relations by the
   mean of their member-node coordinates, which is close enough for a building), extracted once from the
   Geofabrik PBF into data/interim/density/townhalls_osm.csv (cache; delete it to rebuild).
2. Candidates: objects whose point lies inside the URAU polygon of the core city.
3. Seat of the city government: ``townhall:type`` = ``city`` if exactly one candidate has it; otherwise a
   candidate whose name says "Urząd Miasta" / "Urząd Miejski" / "Magistrat" and not a district office
   (``dzielnic``, ``delegatur``, ``filia``, ``wydział``, ``biuro``, ``rada``, ``osiedl``) if exactly one.
4. Anything else is decided by hand: TOWNHALL_PICK (OSM type/id and a one-line reason).

Run: python -m pipeline.density_centres   (prints the candidates and the choice per agglomeration)
"""
from __future__ import annotations

import csv
import re

import numpy as np
import shapely
from pyproj import Transformer

from pipeline.boundaries import all_agglomeration_ids, load_urau
from pipeline.common import INTERIM, RAW, load_config

PBF = RAW / "osm" / "poland-latest.osm.pbf"
CACHE = INTERIM / "density" / "townhalls_osm.csv"
WGS_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
FIELDS = ["osm_type", "osm_id", "name", "townhall_type", "official_name", "addr", "lon", "lat"]
SEAT_RX = re.compile(r"urz[aą]d (miasta|miejski)|magistrat", re.I)
NOT_SEAT_RX = re.compile(r"dzielnic|delegatur|filia|wydzia|biuro|rada |osiedl|stare|histor|muzeum", re.I)

# Hand picks: agglomeration -> (osm_type, osm_id, reason).  Filled after inspecting the candidates
# printed by ``python -m pipeline.density_centres``.
TOWNHALL_PICK: dict[str, tuple[str, int, str]] = {
    "krakow": ("node", 4017203772, "3 obiekty 'Urząd Miasta Krakowa'; wybrano pl. Wszystkich Świętych 3 (Pałac "
                                   "Wielopolskich, siedziba prezydenta), pozostałe to budynki urzędu (al. Powstania "
                                   "Warszawskiego, os. Zgody)"),
    "poznan": ("relation", 5442363, "3 obiekty 'Urząd Miasta Poznania'; wybrano pl. Kolegiacki 17 (siedziba "
                                    "prezydenta); Ratusz na Starym Rynku to muzeum"),
    "lodz": ("node", 1880701425, "3 obiekty z nazwą UMŁ; wybrano ul. Piotrkowska 104 (siedziba prezydenta); "
                                 "Piotrkowska 175 i pl. Komuny Paryskiej to inne budynki urzędu"),
    "gzm": ("way", 202209404, "townhall:type=city ma punkt 'Biuro Obsługi Mieszkańców'; wybrano budynek "
                              "Urzędu Miasta Katowice, ul. Młyńska 4 (ok. 80 m dalej)"),
    "bydgoszcz_torun": ("way", 88520891, "townhall:type=city ma oddział ul. Gawędy 5 (Fordon, ok. 10 km od "
                                         "centrum); wybrano ul. Jezuicka 1 (Ratusz, Stary Rynek)"),
    "kielce": ("node", 6588785827, "kilka budynków 'Urząd Miasta Kielce'; wybrano Rynek 1 (siedziba prezydenta)"),
    "bialystok": ("way", 548685792, "2 obiekty Urzędu Miejskiego; wybrano ul. Słonimska 1 (siedziba prezydenta), "
                                    "drugi to departament obsługi mieszkańców"),
}


# ------------------------------------------------------------------ OSM extraction
def extract() -> list[dict]:
    """All amenity=townhall objects in the PBF with a representative point (three passes)."""
    import osmium

    tr = osmium.IdTracker()
    objs: list[dict] = []
    fp = osmium.FileProcessor(str(PBF)).with_filter(osmium.filter.TagFilter(("amenity", "townhall")))
    for o in fp:
        t = o.tags
        rec = {"name": t.get("name", ""), "townhall_type": t.get("townhall:type", ""),
               "official_name": t.get("official_name", ""),
               "addr": " ".join(x for x in (t.get("addr:street", ""), t.get("addr:housenumber", ""),
                                             t.get("addr:city", "")) if x)}
        if o.is_node():
            objs.append({"osm_type": "node", "osm_id": o.id, **rec, "lon": o.location.lon, "lat": o.location.lat})
        elif o.is_way():
            objs.append({"osm_type": "way", "osm_id": o.id, **rec, "refs": [n.ref for n in o.nodes]})
            tr.add_references(o)
        elif o.is_relation():
            ways = [m.ref for m in o.members if m.type == "w"]
            objs.append({"osm_type": "relation", "osm_id": o.id, **rec, "ways": ways})
            for w in ways:
                tr.add_way(w)
    # pass 2: node lists of relation member ways
    way_refs: dict[int, list[int]] = {}
    wanted_ways = {w for o in objs if o["osm_type"] == "relation" for w in o["ways"]}
    if wanted_ways:
        for w in osmium.FileProcessor(str(PBF), osmium.osm.WAY).with_filter(osmium.filter.IdFilter(wanted_ways)):
            way_refs[w.id] = [n.ref for n in w.nodes]
            for n in w.nodes:
                tr.add_node(n.ref)
    # pass 3: node locations
    loc: dict[int, tuple[float, float]] = {}
    for n in osmium.FileProcessor(str(PBF), osmium.osm.NODE).with_filter(tr.id_filter()):
        loc[n.id] = (n.location.lon, n.location.lat)
    out = []
    for o in objs:
        if o["osm_type"] == "way":
            pts = [loc[r] for r in o.pop("refs") if r in loc]
        elif o["osm_type"] == "relation":
            pts = [loc[r] for w in o.pop("ways") for r in way_refs.get(w, []) if r in loc]
        else:
            pts = [(o["lon"], o["lat"])]
        if not pts:
            continue
        a = np.array(sorted(set(pts)))
        o["lon"], o["lat"] = round(float(a[:, 0].mean()), 7), round(float(a[:, 1].mean()), 7)
        out.append(o)
    return sorted(out, key=lambda r: (r["osm_type"], r["osm_id"]))


def townhalls() -> list[dict]:
    if not CACHE.exists():
        rows = extract()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: r[k] for k in FIELDS})
    with open(CACHE, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["osm_id"] = int(r["osm_id"])
        r["lon"], r["lat"] = float(r["lon"]), float(r["lat"])
    return rows


# ------------------------------------------------------------------ selection
def core_city(agg: str):
    code = load_config()["agglomerations"][agg]["city_codes"][0]
    u = load_urau().set_index("URAU_CODE")
    return code, u.loc[code, "URAU_NAME"], u.loc[code, "geometry"]


def candidates(agg: str) -> list[dict]:
    _, _, geom = core_city(agg)
    out = []
    for r in townhalls():
        x, y = WGS_TO_2180.transform(r["lon"], r["lat"])
        if shapely.contains_xy(geom, x, y):
            out.append({**r, "x": x, "y": y})
    return out


def townhall(agg: str) -> dict:
    """Chosen city hall: dict(name, x, y, lon, lat, osm, rule, reason)."""
    cand = candidates(agg)
    if agg in TOWNHALL_PICK:
        t, i, why = TOWNHALL_PICK[agg]
        hit = [c for c in cand if c["osm_type"] == t and c["osm_id"] == i]
        if len(hit) != 1:
            raise RuntimeError(f"{agg}: hand-picked townhall {t}/{i} not among the candidates")
        return {**_rec(hit[0]), "rule": "hand", "reason": why}
    city = [c for c in cand if c["townhall_type"] == "city"]
    if len(city) == 1:
        return {**_rec(city[0]), "rule": "townhall:type=city", "reason": ""}
    pool = city or cand
    seat = [c for c in pool if SEAT_RX.search(c["name"] + " " + c["official_name"])
            and not NOT_SEAT_RX.search(c["name"] + " " + c["official_name"])]
    if len(seat) == 1:
        return {**_rec(seat[0]), "rule": "name", "reason": ""}
    raise RuntimeError(f"{agg}: townhall ambiguous ({len(cand)} candidates, {len(city)} city, {len(seat)} by name); "
                       "add a hand pick to TOWNHALL_PICK")


def _rec(c: dict) -> dict:
    return {"name": c["name"] or c["official_name"] or "(bez nazwy)", "x": c["x"], "y": c["y"],
            "lon": c["lon"], "lat": c["lat"], "osm": f"{c['osm_type']}/{c['osm_id']}"}


def main() -> None:
    for agg in all_agglomeration_ids():
        code, name, _ = core_city(agg)
        cand = candidates(agg)
        print(f"\n== {agg} ({code} {name}): {len(cand)} candidates")
        for c in cand:
            print(f"  {c['osm_type']}/{c['osm_id']}  type={c['townhall_type']!r}  {c['name']!r}  "
                  f"off={c['official_name']!r}  {c['addr']!r}  {c['lat']:.5f},{c['lon']:.5f}")
        try:
            t = townhall(agg)
            print(f"  -> {t['osm']} {t['name']} ({t['rule']}) {t['reason']}")
        except RuntimeError as e:
            print(f"  -> {e}")


if __name__ == "__main__":
    main()
