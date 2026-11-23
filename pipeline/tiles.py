"""Phase 4: map tiles (brief §8, §14.3-14.4).

    python -m pipeline.tiles                       # all four layers
    python -m pipeline.tiles --layer transport_performance_30    # only that one (repeatable)
    python -m pipeline.tiles --no-verify           # skip the read-back check (faster, for experiments)

Writes tiles/<layer>_<data version>.pmtiles, the layer entries of results/web/catalog.json,
results/web/attributions.json, results/qa/tiles/{tiles.md,stats.json,area_check.csv,_meta.json}.
Single process, pure Python (pipeline.tiles_core); a layer whose source data is missing keeps its
catalog entry as it was.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path

from pipeline import tiles_layers as TL
from pipeline.common import RESULTS, ROOT, TILES, load_config, sha256_of, write_json, write_meta
from pipeline.tiles_core import MAX_Z, MIN_Z, build_tiles, write_pmtiles
from pipeline.tiles_verify import open_reader, verify, viewport_bytes

WEB = RESULTS / "web"
QA = RESULTS / "qa" / "tiles"
SOURCES = ["results/layers/frequent_cells.parquet", "results/layers/access_cells.parquet",
           "results/layers/gtfs_coverage_mask.parquet", "data/interim/popgrid/cells_*.parquet"]
VISIT_ZOOMS = [8, 10, 11, 12]
HEAVY_AGG = "warszawa"          # the agglomeration used for the transfer estimate when a layer has it


def layer_table(cfg: dict) -> dict:
    day = cfg["reference_day"]
    L = TL.Layer
    return {
        "density_250m": L("density_250m", "density250", "density250", TL.load_density, TL.describe_density),
        "frequent_transport": L("frequent_transport", "frequent", "frequent", TL.load_frequent, TL.describe_frequent),
        "transport_performance_30": L("transport_performance_30", "performance30", "performance30",
                                      TL.load_performance, TL.describe_performance),
        "gtfs_nodata": L("gtfs_nodata", "gtfs_nodata", "gtfs_nodata", TL.load_mask, TL.describe_mask),
    }


def file_name(layer_id: str, cfg: dict) -> str:
    day = cfg["reference_day"]
    return {"density_250m": "density250_nsp2021.pmtiles",
            "frequent_transport": f"frequent_{day}.pmtiles",
            "transport_performance_30": f"performance30_{day}.pmtiles",
            "gtfs_nodata": f"gtfs_nodata_{day}.pmtiles"}[layer_id]


def read_catalog() -> dict | None:
    p = WEB / "catalog.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def update_catalog(entries: dict[str, dict]) -> None:
    cat = read_catalog()
    if cat is None:
        print("  results/web/catalog.json is missing (run pipeline.phase0_boundaries): catalog not updated")
        return
    done = set()
    layers = []
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
    write_json(WEB / "catalog.json", cat)


def write_attributions(cfg: dict) -> int:
    names = {a: c.get("name", a) for a, c in cfg["agglomerations"].items()}
    rows = []
    for fid in sorted(cfg["feeds"]):
        f = cfg["feeds"][fid]
        rows.append({"id": fid, "publisher": f["publisher"], "license": f["license"], "url": f.get("license_url", ""),
                     "agglomerations": [names.get(a, a) for a in f.get("agglomerations", [])]})
    write_json(WEB / "attributions.json", {"gtfs_feeds": rows})
    return len(rows)


def remove_stale(prefix: str, keep: str) -> list[str]:
    gone = []
    for p in sorted(TILES.glob(f"{prefix}_*.pmtiles")):
        if p.name != keep:
            p.unlink()
            gone.append(p.name)
    return gone


def build_layer(layer: TL.Layer, cfg: dict, cat: dict | None, do_verify: bool) -> tuple[dict, dict] | None:
    t0 = time.time()
    print(f"[{layer.id}]")
    built = layer.load(cfg)
    if built is None:
        print("  source data missing: layer left as it was")
        return None
    names = {a["id"]: a["name"] for a in (cat or {}).get("agglomerations", [])}
    print(f"  {int(built.grid.codes.astype(bool).sum())} cells in {len(built.aggs)} agglomeration(s) "
          f"({time.time() - t0:.0f} s)")
    if int(built.grid.codes.astype(bool).sum()) != built.extra["cells"]:
        raise RuntimeError("cells were lost when filling the grid (duplicate cell ids?)")
    fname = file_name(layer.id, cfg)
    path = TILES / fname
    url = f"tiles/{fname}"
    if layer.id == "transport_performance_30":
        expected = sorted(a["id"] for a in (cat or {}).get("agglomerations", []) if a.get("phase") == 1)
        entry = layer.describe(cfg, built, names, url, expected)
    else:
        entry = layer.describe(cfg, built, names, url)
    fields = {"v": "Number"} if any(p for p in built.props.values()) else {}
    tiles = build_tiles(built.grid, layer.source_layer, built.props)
    t1 = time.time()
    write_pmtiles(path, tiles, bounds=built.grid.bounds_4326(), source_layer=layer.source_layer, name=entry["title"],
                  description=entry["note"], attribution=entry["attribution"],
                  version=fname.rsplit(".", 1)[0].split("_", 1)[1], fields=fields)
    stale = remove_stale(layer.file_prefix, fname)
    print(f"  wrote {fname}: {path.stat().st_size / 1e6:.2f} MB, {len(tiles)} tiles ({t1 - t0:.0f} s tiling)"
          + (f"; removed stale {', '.join(stale)}" if stale else ""))
    stats = {"file": fname, "bytes": path.stat().st_size, "sha256": sha256_of(path), "title": entry["title"],
             "agglomerations": built.aggs, "cells": built.extra["cells"],
             "classes": built.classes, "source_layer": layer.source_layer,
             "extra": {k: v for k, v in built.extra.items() if k != "cells"}}
    if do_verify:
        v = verify(path, built.grid, built.aggs, built.props, layer.source_layer, built.classes)
        stats["verify"] = v
        reader, _ = open_reader(path)
        cen = {a["id"]: a["centre"] for a in (cat or {}).get("agglomerations", [])}
        agg = HEAVY_AGG if HEAVY_AGG in built.aggs else built.aggs[0]
        if agg in cen:
            lon, lat = cen[agg]
            stats["visit"] = {"agglomeration": agg, "directory_bytes": 16384,
                              "viewport_bytes": {str(z): viewport_bytes(reader, lon, lat, z) for z in VISIT_ZOOMS}}
        print(f"  verify: {v['cells_checked']} cells checked, not covered {v['cells_not_covered']}, wrong class "
              f"{v['cells_wrong_class']}, empty covered {v['empty_cells_covered']}, max area diff "
              f"{v['max_abs_diff_pct']} %, bad properties {v['bad_properties']}")
    return entry, stats


# ------------------------------------------------------------------ report
def dist_estimate() -> dict | None:
    """Gzipped size of the built app (web/dist without data and tiles), the catalog and the boundaries."""
    dist = ROOT / "web" / "dist"
    if not dist.exists():
        return None
    app = 0
    for p in dist.rglob("*"):
        if p.is_file() and p.relative_to(dist).parts[0] not in ("data", "tiles"):
            app += len(gzip.compress(p.read_bytes(), compresslevel=6, mtime=0))
    data = {}
    for n in ("catalog.json", "fua.geojson", "attributions.json", "metrics.json"):
        p = WEB / n
        data[n] = len(gzip.compress(p.read_bytes(), compresslevel=6, mtime=0)) if p.exists() else 0
    return {"app_gz": app, "data_gz": data}


def mb(b: float) -> str:
    return f"{b / 1e6:.2f}".replace(".", ",")


def pl(x: float, d: int = 2, sign: bool = False) -> str:
    return f"{x:{'+' if sign else ''}.{d}f}".replace(".", ",")


def kb(b: float) -> str:
    return f"{b / 1e3:.0f}".replace(".", ",")


def write_report(cfg: dict, stats: dict, cat: dict | None) -> None:
    th = cfg.get("tiles", {})
    warn_file, warn_total = th.get("warn_file_mb", 50), th.get("warn_total_mb", 200)
    files = sorted(TILES.glob("*.pmtiles"))
    total = sum(p.stat().st_size for p in files)
    warns = [f"plik {p.name} ma {p.stat().st_size / 1e6:.1f} MB (próg {warn_file} MB)" for p in files
             if p.stat().st_size / 1e6 > warn_file]
    if total / 1e6 > warn_total:
        warns.append(f"katalog tiles/ ma {total / 1e6:.1f} MB (próg {warn_total} MB)")
    for w in warns:
        print(f"WARNING: {w}", file=sys.stderr)
    names = {a["id"]: a["name"] for a in (cat or {}).get("agglomerations", [])}
    L = []
    L.append("# Kafle mapy (faza 4)\n")
    L.append(f"Dzień referencyjny rozkładów: {cfg['reference_day']}; ludność: NSP 2021 (31.03.2021) rozłożona wzorem GHSL 2020. "
             f"Kafle MVT, zoomy {MIN_Z}–{MAX_Z} (powyżej MapLibre powiększa kafel z z{MAX_Z}), extent 4096, bufor 64, gzip; "
             "jeden plik PMTiles na warstwę, jedna klasa wartości = jeden obiekt w kafelku.\n")
    L.append("## Rozmiary\n")
    L.append("| Plik | Rozmiar (MB) | Kafli | Warstwa |\n|---|---|---|---|")
    for lid, s in sorted(stats.items()):
        n = sum(s.get("verify", {}).get("tiles_per_zoom", {}).values()) if "verify" in s else ""
        L.append(f"| `{s['file']}` | {mb(s['bytes'])} | {n} | {s['title']} |")
    L.append(f"| **razem `tiles/`** | **{mb(total)}** | | |\n")
    L.append("Ostrzeżenia o rozmiarze: " + ("; ".join(warns) if warns else "brak (żaden plik nie przekracza "
             f"{warn_file} MB, katalog nie przekracza {warn_total} MB).") + "\n")
    L.append("## Jak powstały kafle\n")
    L += [
        "- Komórki 250 m (EPSG:2180) trafiają do klas rampy kolorów, a sąsiednie komórki tej samej klasy są łączone w wielokąty "
        "(`rasterio.features.shapes`, łączność 4) osobno dla okna siatki pod każdym kafelkiem. Krawędzie są zagęszczane do 250 m, "
        "rzutowane do EPSG:3857, przycinane do kafla z buforem 64 jednostek i przyciągane do siatki 4096.",
        "- Obiekt niesie jedną liczbę `v`: wartość reprezentatywna klasy (nie wartość komórki), taka, że wyrażenie `step` "
        "w aplikacji wybiera kolor klasy. Obiekty bez `v` to brak danych (kreskowane), nigdy zero.",
        "- Zoomy poniżej 9: siatka jest grubiona blokami 2^(9-z) komórek, a klasa bloku to dominanta narysowanych komórek "
        "(remis wygrywa brak danych). Blok jest rysowany, gdy narysowano w nim choć jedną komórkę, więc obszar FUA pozostaje "
        "widoczny na z5–z7, ale na z4–z8 brzegi są poszerzone o do pół bloku (od 500 m na z8 do 16 km na z4).",
        "- Komórki bez ludności nie są rysowane (rzeczywiste zero, nie brak danych); warstwy tranzytowe rysują tylko komórki "
        "z ludnością > 0 w siatce przeskalowanej do spisu (komórki z samą ludnością surową GHSL pomijamy).",
        "",
    ]
    L.append("## Warstwy\n")
    for lid, s in sorted(stats.items()):
        v = s.get("verify")
        L.append(f"### {s['title']} (`{lid}`)\n")
        L.append(f"- Plik `{s['file']}`, {mb(s['bytes'])} MB, SHA-256 `{s['sha256']}`.")
        L.append(f"- Aglomeracje w pliku ({len(s['agglomerations'])}): " + ", ".join(names.get(a, a) for a in s["agglomerations"]) + ".")
        L.append(f"- Narysowanych komórek 250 m: {s['cells']}.")
        for k, val in sorted(s.get("extra", {}).items()):
            if k == "dropped_zero_pop":
                L.append(f"- Pominięto {val} komórek bez ludności w siatce przeskalowanej do spisu (są w źródle, bo mają ludność surową GHSL).")
            elif k == "source_area_km2":
                L.append("- Powierzchnia wielokątów źródłowych (km²): " + ", ".join(f"{names.get(a, a)} {pl(x, 1)}" for a, x in sorted(val.items())) + ".")
        if v:
            h = v["header"]
            L.append(f"- Nagłówek: {h['tile_type']}, kafle {h['tile_compression']}, katalogi {h['internal_compression']}, "
                     f"clustered={h['clustered']}, zoomy {h['min_zoom']}–{h['max_zoom']}, zakres {h['bounds']}, środek {h['center']}, "
                     f"kafli adresowanych {h['addressed_tiles']} (unikalnych {h['tile_contents']}); warstwy wektorowe w metadanych: {', '.join(v['vector_layers'])}.")
            L.append("\n| Zoom | Kafli | Bajtów razem | Największy kafel (B) |\n|---|---|---|---|")
            for z in sorted(v["tiles_per_zoom"], key=int):
                L.append(f"| {z} | {v['tiles_per_zoom'][z]} | {v['bytes_per_zoom'][z]} | {v['max_tile_bytes'][z]} |")
            L.append("")
            L.append(f"Kontrola przypisania na z{MAX_Z}: sprawdzono {v['cells_checked']} narysowanych komórek (środek komórki w kafelku); "
                     f"nie pokryte przez żaden obiekt: {v['cells_not_covered']}, pokryte obiektem innej klasy: {v['cells_wrong_class']}; "
                     f"komórki niezaludnione pokryte obiektem: {v['empty_cells_covered']}; obiekty o niedozwolonej własności: {v['bad_properties']}.\n")
            cls = {c["code"]: c["label"] for c in s["classes"]}
            tot: dict[int, list] = {}
            worst: dict[str, float] = {}
            for r in v["area"]:
                a = tot.setdefault(r["code"], [0.0, 0.0])
                a[0] += r["source_km2"]
                a[1] += r["tiles_km2"]
                if r["diff_pct"] is not None and r["source_km2"] >= 1.0:
                    worst[r["agg"]] = max(worst.get(r["agg"], 0.0), abs(r["diff_pct"]))
            L.append(f"Powierzchnia klas na z{MAX_Z} (km², suma po aglomeracjach): kafle (przycięte do granic kafla bez bufora) wobec komórek źródłowych.\n")
            L.append("| Klasa | Komórki źródłowe (km²) | Kafle (km²) | Różnica (%) |\n|---|---|---|---|")
            for code in sorted(tot):
                a, b = tot[code]
                L.append(f"| {cls.get(code, code)} | {pl(a)} | {pl(b)} | {pl(100 * (b - a) / a, 3, True)} |")
            L.append("")
            L.append("Największa różnica po aglomeracji (klasy o powierzchni ≥ 1 km², pełna tabela w `area_check.csv`): "
                     + ", ".join(f"{names.get(a, a)} {pl(x, 3)} %" for a, x in sorted(worst.items())) + ".\n")
        else:
            L.append("- Kontrola odczytu nie była uruchomiona w tym przebiegu.\n")
    est = dist_estimate()
    L.append("## Transfer na typową wizytę\n")
    rows = [(lid, s) for lid, s in sorted(stats.items()) if "visit" in s.get("verify", {}) or "visit" in s]
    if est is None:
        L.append("Brak `web/dist` (uruchom `npm --prefix web run build`), więc rozmiaru aplikacji nie oszacowano.\n")
    else:
        d = est["data_gz"]
        fixed = est["app_gz"] + d["catalog.json"] + d["fua.geojson"] + d["attributions.json"] + d["metrics.json"]
        L.append(f"Pierwsza wizyta, jedna warstwa wartości, okno 1440 × 900 px na jednej aglomeracji przy zoomach "
                 f"{', '.join(str(z) for z in VISIT_ZOOMS)} (kafle 512 px, bajty skompresowane tak, jak je odczyta przeglądarka). "
                 f"Stałe: aplikacja po gzip {kb(est['app_gz'])} kB, `catalog.json` {kb(d['catalog.json'])} kB, `fua.geojson` "
                 f"{kb(d['fua.geojson'])} kB, `attributions.json` {kb(d['attributions.json'])} kB, `metrics.json` {kb(d['metrics.json'])} kB "
                 f"(razem {kb(fixed)} kB); do tego 16 kB nagłówka i katalogu PMTiles na plik. Podkład OpenFreeMap idzie z ich serwerów, "
                 "nie z limitu Pages.\n")
        L.append("| Warstwa | Aglomeracja | Kafle (kB) | Razem wizyta (kB) | Wizyt w 100 GB/mies. |\n|---|---|---|---|---|")
        for lid, s in rows:
            vis = s["visit"]
            t = sum(vis["viewport_bytes"].values()) + vis["directory_bytes"]
            tot = fixed + t
            L.append(f"| {s['title']} | {names.get(vis['agglomeration'], vis['agglomeration'])} | {kb(t)} | {kb(tot)} | {int(100e9 // tot)} |")
        L.append("\nPowtórna wizyta czyta aplikację i dane z pamięci podręcznej przeglądarki, więc kosztuje tylko kafle, o ile ich pliki się nie zmieniły. "
                 "Kolejna warstwa tej samej aglomeracji dodaje swoje kafle (i 16 kB katalogu). To oszacowanie z jednego położenia okna, nie pomiar ruchu.\n")
    (QA).mkdir(parents=True, exist_ok=True)
    (QA / "tiles.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    with open(QA / "area_check.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["layer", "agglomeration", "class", "source_km2", "tiles_km2", "diff_pct"])
        for lid, s in sorted(stats.items()):
            cls = {c["code"]: c["label"] for c in s["classes"]}
            for r in s.get("verify", {}).get("area", []):
                w.writerow([lid, r["agg"], cls.get(r["code"], r["code"]), r["source_km2"], r["tiles_km2"], r["diff_pct"]])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--layer", action="append", choices=list(layer_table({"reference_day": "x"})), help="layer id (repeatable)")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    cfg = load_config()
    table = layer_table(cfg)
    ids = args.layer or list(table)
    cat = read_catalog()
    TILES.mkdir(parents=True, exist_ok=True)
    stats_path = QA / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {}
    entries = {}
    for lid in ids:
        r = build_layer(table[lid], cfg, cat, not args.no_verify)
        if r:
            entries[lid], stats[lid] = r
    if entries:
        update_catalog(entries)
    n = write_attributions(cfg)
    print(f"attributions.json: {n} feeds")
    # an entry for a layer that is no longer in tiles/ must not stay in the report
    stats = {k: v for k, v in stats.items() if (TILES / v["file"]).exists()}
    write_json(stats_path, stats)
    write_report(cfg, stats, read_catalog())
    meta_inputs = set()
    for m in (RESULTS / "layers" / "_meta.json", RESULTS / "layers" / "_meta_access.json"):
        if m.exists():
            meta_inputs |= set(json.loads(m.read_text(encoding="utf-8")).get("inputs", {}))
    write_meta(QA, "tiles", inputs=sorted(meta_inputs), started=t0, extra={
        "sources": SOURCES, "layers_built_in_this_run": ids,
        "files": {s["file"]: {"bytes": s["bytes"], "sha256": s["sha256"]} for s in stats.values()}})
    print("sizes:")
    for p in sorted(TILES.glob("*.pmtiles")):
        print(f"  {p.name:40s} {p.stat().st_size / 1e6:8.2f} MB")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
