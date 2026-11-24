"""Stop areas for the map: results/layers/transfer_nodes.parquet -> results/web/transfer_nodes.geojson.

    python -m pipeline.transfer_web

One point per stop area inside an agglomeration's FUA (`in_fua`), with the components of the ease-of-transfer
step side by side (they are never blended into a score).  Outside the GTFS coverage mask (`in_mask` false) a
node is kept with `nodata: true` and without any component value, never with zeros.  Share fields are
FRACTIONS 0..1 (as in the parquet), rounded to 2 decimals; times are minutes, rounded to 2 decimals.
Also upserts the two catalog entries `transfer_walk` and `transfer_wait` in results/web/catalog.json.
If the file grows beyond MAX_BYTES, nodes with a single line and no transfer pair are dropped first, then
the flag text is shortened.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import geopandas as gpd

from pipeline.common import RESULTS, load_config, write_json, write_meta

WEB = RESULTS / "web"
SRC = RESULTS / "layers" / "transfer_nodes.parquet"
OUT = WEB / "transfer_nodes.geojson"
QA = RESULTS / "qa" / "transfer_web"
MAX_BYTES = 3_000_000

# property name in the file -> column in the parquet
COLUMNS = {
    "lines": "n_lines", "pairs": "n_pairs", "pairs_excl": "n_pairs_parallel_excluded",
    "dep_h": "dep_per_h_day", "dep_h_am": "dep_per_h_am",
    "walk_dir": "walk_dir_min_median", "walk_dir_p90": "walk_dir_min_p90", "walk_best": "walk_min_median",
    "cross": "crossings_dir_median", "cross_signal": "crossings_signal_share",
    "steps": "steps_dir_share", "stepfree": "stepfree_dir_share",
    "wait_am": "wait_am_median", "wait_day": "wait_day_median",
    "walkwait_am": "walkwait_dir_am_median", "walkwait_am_w": "walkwait_am_median_w",
}
# kept for a node outside the mask: what the map needs to place and size it (not an ease-of-transfer component)
NODATA_KEEP = ("lines", "dep_h", "dep_h_am")

# short flag texts (the full ones are in the parquet); used only when the file is too large
FLAG_SHORT = {
    "poza maską pokrycia GTFS: brak danych": "",
    "ścieżka głównie po osi jezdni w OSM: przejścia mogą być niepoliczone": "przejścia mogą być niepoliczone (ścieżka po osi jezdni)",
    "stacja: dojście do punktu stacji z GTFS, nie do konkretnego peronu": "dojście do punktu stacji, nie peronu",
    "kolej/metro: perony nierozróżnione w GTFS, przejście między pociągami nieznane": "perony kolejowe nierozróżnione",
}

RAMP_BLUE = ["#B9CEF3", "#8AACEB", "#5A86E0", "#1D4ED8", "#13308A"]
RAMP_ORANGE = ["#F8D9A8", "#F0A35E", "#D9722B", "#A94A12", "#6B2C0A"]


def num(v, nd: int = 2):
    """Plain number rounded to nd decimals; None for null / NaN; whole values stay ints."""
    if v is None:
        return None
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        return None
    r = round(f, nd)
    return int(r) if r == int(r) else r


def feature(row, short_flag: bool) -> dict:
    nodata = not bool(row["in_mask"])
    p: dict = {"id": row["node_id"], "agg": row["agglomeration"], "name": row["name"], "modes": row["modes"]}
    for prop, col in COLUMNS.items():
        if nodata and prop not in NODATA_KEEP:
            continue
        v = num(row[col], 0 if prop in ("lines", "pairs", "pairs_excl") else 2)
        if v is not None:
            p[prop] = v
    flag = row["flag"] or ""
    if flag:
        parts = [x.strip() for x in flag.split(";") if x.strip()]
        if short_flag:
            parts = [FLAG_SHORT.get(x, x) for x in parts]
        # the "no data" part is carried by `nodata`
        parts = [x for x in parts if x and not x.startswith("poza maską")]
        if parts:
            p["flag"] = "; ".join(parts)
    if nodata:
        p["nodata"] = True
    pt = row.geometry
    return {"type": "Feature", "properties": p,
            "geometry": {"type": "Point", "coordinates": [round(pt.x, 6), round(pt.y, 6)]}}


def dump(rows, short_flag: bool) -> str:
    fc = {"type": "FeatureCollection", "features": [feature(r, short_flag) for _, r in rows.iterrows()]}
    return json.dumps(fc, ensure_ascii=False, separators=(",", ":")) + "\n"


def catalog_entries(cfg: dict) -> dict[str, dict]:
    common = {
        "type": "geojson", "url": "data/transfer_nodes.geojson", "kind": "points", "status": "ready",
        "size_property": "dep_h", "size_stops": [20, 50, 100, 200], "size_label": "odjazdów na godzinę (6–20)",
        "has_nodata": True, "nodata_label": "brak danych (poza pokryciem GTFS)",
        "timetable_date": cfg["reference_day"], "population_date": None,
        "attribution": "wydawcy GTFS (lista w „O danych”), © współtwórcy OpenStreetMap",
    }
    note = (
        "Punkt to zespół przystanków, czyli przystanki tramwaju, autobusu, kolei i metra leżące tak blisko siebie, że można między nimi "
        "przesiąść się pieszo; {what}, a wielkość punktu to liczba odjazdów na godzinę. "
        "Dojście liczono po sieci pieszej OSM, 5 km/h, osobno dla każdego kierunku jazdy, a czekanie z rozkładu jazdy, w pełnych minutach. "
        "To miara własna, której składowe są pokazane osobno i nie są łączone w jedną ocenę; nie jest to metoda AMPTI. "
        "Informacja o drodze bez schodów zależy od kompletności OpenStreetMap, a zespoły poza pokryciem GTFS nie mają wartości."
    )
    return {
        "transfer_walk": {
            **common, "title": "Przesiadki: dojście między liniami", "property": "walk_dir",
            "unit": "mediana dojścia między liniami, min",
            "novalue_label": "bez wartości (brak ruchów przesiadkowych z kierunkami)",
            "ramp": {"stops": [1, 2, 3, 5], "colors": RAMP_BLUE,
                     "labels": ["do 1 min", "1–2 min", "2–3 min", "3–5 min", "ponad 5 min"]},
            "note": note.format(what="kolor pokazuje medianę dojścia między liniami"),
        },
        "transfer_wait": {
            **common, "title": "Przesiadki: czekanie na linię docelową (7–9)", "property": "wait_am",
            "unit": "oczekiwane czekanie, min",
            "ramp": {"stops": [3, 5, 10, 15], "colors": RAMP_ORANGE,
                     "labels": ["do 3 min", "3–5 min", "5–10 min", "10–15 min", "ponad 15 min"]},
            "note": note.format(what="kolor pokazuje oczekiwane czekanie na linię docelową w godzinach 7–9"),
        },
    }


def update_catalog(entries: dict[str, dict]) -> None:
    path = WEB / "catalog.json"
    cat = json.loads(path.read_text(encoding="utf-8"))
    done, layers = set(), []
    for l in cat["layers"]:
        if l["id"] in entries:
            layers.append({"id": l["id"], **entries[l["id"]]})
            done.add(l["id"])
        else:
            layers.append(l)
    for lid, e in entries.items():
        if lid not in done:
            layers.append({"id": lid, **e})
    cat["layers"] = layers
    write_json(path, cat)


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    g = gpd.read_parquet(SRC)
    g = g[g["in_fua"]].sort_values("node_id", kind="stable")
    g = g.set_crs("EPSG:4326") if g.crs is None else g.to_crs("EPSG:4326")
    n_all = len(g)
    text, dropped, short = dump(g, False), 0, False
    if len(text.encode("utf-8")) > MAX_BYTES:
        keep = ~((g["n_lines"] <= 1) & (g["n_pairs"] == 0))
        dropped = int((~keep).sum())
        g = g[keep]
        text = dump(g, False)
    if len(text.encode("utf-8")) > MAX_BYTES:
        short = True
        text = dump(g, True)
    WEB.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    size = OUT.stat().st_size
    update_catalog(catalog_entries(cfg))
    write_meta(QA, "transfer_web", inputs=[], started=t0, extra={
        "source": "results/layers/transfer_nodes.parquet", "output": "results/web/transfer_nodes.geojson",
        "timetable_date": cfg["reference_day"], "features": len(g), "nodata_features": int((~g["in_mask"]).sum()),
        "dropped_single_line_no_pair": dropped, "flag_shortened": short, "bytes": size,
        "share_unit": "fraction 0..1 (cross_signal, steps, stepfree)", "time_unit": "minutes",
        "catalog_layers": ["transfer_walk", "transfer_wait"]})
    print(f"transfer_web: {len(g)} of {n_all} nodes, {size / 1e6:.2f} MB, dropped {dropped}, flag shortened {short}")


if __name__ == "__main__":
    main()
