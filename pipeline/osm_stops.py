"""Extract public-transport stops from the Poland PBF (brief section 6) and de-duplicate them.

One pyosmium pass (nodes + ways, way locations via the node-location index).  Relations
(multipolygon platforms/stations) are not read: they are rare for stops and would need a
second pass; the effect is stated in the report.

Outputs (interim): data/interim/osm/stops.parquet, stops_dedup.parquet, dedup_stats.json
"""
from __future__ import annotations

import json
import os
import sys
import time

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

from .common import INTERIM, RAW, RESULTS, write_json, write_meta

PBF = RAW / "osm" / "poland-latest.osm.pbf"
OUT = Path(os.environ.get("OSM_OUT", INTERIM / "osm"))
DEDUP_RADIUS_M = 15.0

LIFECYCLE_KEYS = ("disused", "abandoned", "construction", "proposed", "razed", "demolished", "removed")
LIFECYCLE_VALUES = {"disused", "abandoned", "construction", "proposed", "razed", "demolished"}
YES = {"yes", "designated", "official"}


def is_inactive(tags) -> bool:
    for k in LIFECYCLE_KEYS:
        v = tags.get(k)
        if v is not None and v != "no":
            return True
    for k in ("highway", "railway", "public_transport"):
        if tags.get(k) in LIFECYCLE_VALUES:
            return True
    return False


def platform_mode(tags) -> str:
    """Mode of a public_transport=platform object from its tags."""
    if tags.get("tram") in YES:
        return "tram"
    if tags.get("subway") in YES:
        return "subway"
    if tags.get("train") in YES or tags.get("railway") == "platform":
        return "rail_platform"
    if tags.get("light_rail") in YES:
        return "tram"
    if tags.get("bus") in YES or tags.get("trolleybus") in YES:
        return "bus"
    if tags.get("ferry") in YES:
        return "ferry"
    return "platform_unknown"


def classify(tags):
    """Return (kind, source_tag) or None if the object is not a stop we keep."""
    if is_inactive(tags):
        return None
    hw, rw, pt = tags.get("highway"), tags.get("railway"), tags.get("public_transport")
    if rw == "tram_stop":
        return "tram", "railway=tram_stop"
    if hw == "bus_stop":
        return "bus", "highway=bus_stop"
    if rw in ("station", "halt"):
        if tags.get("station") == "subway" or tags.get("subway") in YES:
            return "subway", f"railway={rw}"
        return "rail_station", f"railway={rw}"
    if pt == "station":
        if tags.get("station") == "subway" or tags.get("subway") in YES:
            return "subway", "public_transport=station"
        if tags.get("train") in YES or tags.get("station") in ("train", "light_rail"):
            return "rail_station", "public_transport=station"
        if tags.get("bus") in YES or tags.get("trolleybus") in YES:
            return "bus", "public_transport=station"  # bus station
        if tags.get("tram") in YES:
            return "tram", "public_transport=station"
        return "platform_unknown", "public_transport=station"
    if pt == "platform":
        return platform_mode(tags), "public_transport=platform"
    return None


def extract() -> pd.DataFrame:
    import osmium
    fp = (osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY)
          .with_locations("flex_mem")
          .with_filter(osmium.filter.KeyFilter("highway", "public_transport", "railway")))
    rows = []
    it = iter(fp)
    while True:
        try:
            o = next(it)
        except StopIteration:
            break
        except RuntimeError:
            if os.environ.get("OSM_ALLOW_TRUNCATED") == "1":  # testing on a partial download only
                break
            raise
        tags = o.tags
        c = classify(tags)
        if c is None:
            continue
        kind, src = c
        if o.is_node():
            lon, lat = o.location.lon, o.location.lat
            typ = "node"
        else:
            xs, ys = [], []
            for n in o.nodes:
                if n.location.valid():
                    xs.append(n.location.lon)
                    ys.append(n.location.lat)
            if not xs:
                continue
            lon, lat = float(np.mean(xs)), float(np.mean(ys))  # vertex mean: stops are small objects
            typ = "way"
        g = tags.get
        rows.append((typ, o.id, lon, lat, kind, src, g("name"), g("ref") or g("local_ref"),
                     g("network"), g("operator")))
    df = pd.DataFrame(rows, columns=["osm_type", "osm_id", "lon", "lat", "kind", "source_tag",
                                     "name", "ref", "network", "operator"])
    t = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    df["x"], df["y"] = t.transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    df = df.sort_values(["osm_type", "osm_id"]).reset_index(drop=True)
    return df


GROUP = {"bus": "bus", "tram": "tram", "rail_station": "rail", "rail_platform": "rail",
         "subway": "subway", "ferry": "ferry", "platform_unknown": "unknown"}


def dedup(df: pd.DataFrame, radius: float = DEDUP_RADIUS_M):
    """Greedy seed-and-absorb merge of the same physical stop.

    Rule: objects are ranked (stop-pole / station objects first, then platform nodes, then
    platform ways; named before unnamed; then by id).  Each unassigned object in rank order
    becomes a seed and absorbs every still-unassigned object within ``radius`` metres that
    is (a) of the same mode group, or an unclassified platform (``platform_unknown``, which
    is absorbed by any mode) and (b) not in name conflict (both named and different after
    case folding -> no merge).  Seeds do not chain, so a row of stops spaced less than
    ``radius`` apart is not collapsed into one.
    """
    d = df.reset_index(drop=True)
    is_pole = (d["source_tag"].isin(["highway=bus_stop", "railway=tram_stop"])
               | d["source_tag"].str.startswith("railway=")
               | (d["source_tag"] == "public_transport=station"))
    rank = np.where(is_pole, 0, np.where(d["osm_type"] == "node", 1, 2))
    unnamed = d["name"].isna().astype(int).to_numpy()
    order = np.lexsort((d["osm_id"].to_numpy(), (d["osm_type"] == "way").to_numpy(), unnamed, rank))
    xy = d[["x", "y"]].to_numpy()
    tree = cKDTree(xy)
    grp = d["kind"].map(GROUP).to_numpy()
    nm = d["name"].fillna("").str.casefold().str.strip().to_numpy()
    taken = np.zeros(len(d), bool)
    members: dict[int, list[int]] = {}
    for pi in order:
        if taken[pi]:
            continue
        taken[pi] = True
        mem = []
        for pj in sorted(tree.query_ball_point(xy[pi], radius)):
            if taken[pj]:
                continue
            if not (grp[pi] == grp[pj] or grp[pj] == "unknown"):
                continue
            if nm[pi] and nm[pj] and nm[pi] != nm[pj]:
                continue
            taken[pj] = True
            mem.append(pj)
        members[pi] = mem
    keep = sorted(members)
    out = d.iloc[keep].copy().reset_index(drop=True)
    out["n_merged"] = [1 + len(members[p]) for p in keep]
    out["merged_ids"] = [";".join(f"{d.at[j, 'osm_type'][0]}{d.at[j, 'osm_id']}" for j in members[p])
                         for p in keep]
    for c in ("name", "ref", "network", "operator"):
        vals = out[c].tolist()
        for n, p in enumerate(keep):
            if pd.isna(vals[n]):
                for j in members[p]:
                    if not pd.isna(d.at[j, c]):
                        vals[n] = d.at[j, c]
                        break
        out[c] = vals
    pairs: dict[str, int] = {}
    for p in keep:
        for j in members[p]:
            k = f"{d.at[p, 'source_tag']} <- {d.at[j, 'source_tag']}"
            pairs[k] = pairs.get(k, 0) + 1
    return out, pairs


NUTS2_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_01M_2021_4326_LEVL_2.geojson"
REPORT_DIR = RESULTS / "qa" / "phase0" / "osm"
AGGLO = {  # key -> (name, URAU FUA code)
    "warszawa": ("Warszawa", "PL001F"), "lodz": ("Łódź", "PL002F"), "krakow": ("Kraków", "PL003F"),
    "wroclaw": ("Wrocław", "PL004F"), "poznan": ("Poznań", "PL005F"),
    "trojmiasto": ("Trójmiasto", "PL006F"), "gzm": ("GZM", "PL010F"),
}
KIND_ORDER = ["bus", "tram", "rail_station", "rail_platform", "subway", "ferry", "platform_unknown"]
KIND_PL = {"bus": "autobus", "tram": "tramwaj", "rail_station": "stacja kolejowa",
           "rail_platform": "peron kolejowy", "subway": "metro", "ferry": "prom",
           "platform_unknown": "peron, tryb nieznany"}


def agglomeration_polygons():
    """FUA polygons in EPSG:2180: results/web/fua.geojson when usable, else URAU 2021 FUA from raw."""
    import geopandas as gpd
    web = RESULTS / "web" / "fua.geojson"
    if web.exists():
        g = gpd.read_file(web)
        key = next((c for c in ("agglomeration", "agglo", "agglomeration_id", "key") if c in g.columns), None)
        if key and "level" in g.columns:
            g = g[g["level"] == "fua"].to_crs("EPSG:2180")
            out = {k: g[g[key] == k].geometry.union_all() for k in AGGLO}
            if all(not v.is_empty for v in out.values()):
                return out, "wielokąty FUA z `results/web/fua.geojson` (level == fua)"
    g = gpd.read_file(RAW / "boundaries" / "URAU_RG_100K_2021_3035_FUA.gpkg").to_crs("EPSG:2180")
    out = {k: g[g["URAU_CODE"] == code].geometry.union_all() for k, (_, code) in AGGLO.items()}
    return out, ("wielokąty FUA z URAU 2021 (GISCO, `data/raw/boundaries`), bo `results/web/fua.geojson` "
                 "jeszcze nie istniało w chwili uruchomienia; zamiast prostokątów użyto więc prawdziwych granic FUA "
                 "(Trójmiasto = FUA Gdańsk PL006F, GZM = FUA Katowice PL010F; wariant GZM do decyzji)")


def voivodeships():
    import geopandas as gpd
    from .common import download
    path = download("osm_aux_nuts2_2021", NUTS2_URL, RAW / "osm" / "NUTS_RG_01M_2021_4326_LEVL_2.geojson",
                    license="GISCO / EuroGeographics, free reuse with attribution",
                    source="Eurostat GISCO NUTS 2021, level 2 (auxiliary: assigning OSM stops to voivodeships)",
                    data_date="2021")
    g = gpd.read_file(path)
    g = g[g["CNTR_CODE"] == "PL"].to_crs("EPSG:2180")
    return g[["NUTS_ID", "NAME_LATN", "geometry"]]


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "-"


def report() -> None:
    import geopandas as gpd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .common import read_manifest

    t0 = time.time()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_parquet(OUT / "stops.parquet")
    dd = pd.read_parquet(OUT / "stops_dedup.parquet")
    stats = json.loads((OUT / "dedup_stats.json").read_text(encoding="utf-8"))
    man = {r["id"]: r for r in read_manifest()}.get("osm_poland_pbf", {})
    polys, poly_src = agglomeration_polygons()
    vo = voivodeships()

    def tag_geo(df):
        g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["x"], df["y"]), crs="EPSG:2180")
        j = gpd.sjoin(g, vo, how="left", predicate="within")
        j = j[~j.index.duplicated()]
        df = df.copy()
        df["voiv"] = j["NAME_LATN"].reindex(df.index).to_numpy()
        for k, poly in polys.items():
            df[f"in_{k}"] = g.within(poly).to_numpy()
        return df

    raw, dd = tag_geo(raw), tag_geo(dd)
    for d in (raw, dd):
        d["unnamed"] = d["name"].isna() | (d["name"].astype(str).str.strip() == "")

    rows = []
    for v in sorted(vo["NAME_LATN"]) + [None]:
        for k in KIND_ORDER:
            mr = (raw["voiv"].isna() if v is None else raw["voiv"] == v) & (raw["kind"] == k)
            md = (dd["voiv"].isna() if v is None else dd["voiv"] == v) & (dd["kind"] == k)
            if mr.sum() == 0 and md.sum() == 0:
                continue
            rows.append({"wojewodztwo_nuts2": v or "(poza granicą PL wg NUTS)", "rodzaj": k,
                         "n_surowe": int(mr.sum()), "n_po_deduplikacji": int(md.sum()),
                         "n_bez_nazwy_po_dedup": int(dd.loc[md, "unnamed"].sum())})
    pd.DataFrame(rows).to_csv(REPORT_DIR / "osm_stops_by_voivodeship_kind.csv", index=False,
                              encoding="utf-8", lineterminator="\n")

    ag_rows = []
    colors = {"bus": "#1f77b4", "tram": "#d62728", "rail_station": "#000000", "rail_platform": "#7f7f7f",
              "subway": "#9467bd", "ferry": "#17becf", "platform_unknown": "#ff7f0e"}
    for k, (nm, _) in AGGLO.items():
        r = {"agg": nm}
        for kind in KIND_ORDER:
            r[kind] = int((dd[f"in_{k}"] & (dd["kind"] == kind)).sum())
        r["razem_dedup"] = int(dd[f"in_{k}"].sum())
        r["razem_surowe"] = int(raw[f"in_{k}"].sum())
        r["bez_nazwy"] = int((dd[f"in_{k}"] & dd["unnamed"]).sum())
        r["fua_km2"] = polys[k].area / 1e6
        ag_rows.append(r)
        fig, ax = plt.subplots(figsize=(9, 9), dpi=110)
        gpd.GeoSeries([polys[k]], crs="EPSG:2180").boundary.plot(ax=ax, color="0.3", lw=0.8)
        sub = dd[dd[f"in_{k}"]]
        for kind in KIND_ORDER:
            s_ = sub[sub["kind"] == kind]
            if len(s_):
                big = kind in ("rail_station", "subway")
                ax.scatter(s_["x"], s_["y"], s=(14 if big else 2.5), c=colors[kind],
                           label=f"{KIND_PL[kind]} ({len(s_)})", linewidths=0, alpha=0.9)
        ax.set_aspect("equal")
        ax.set_title(f"{nm}: przystanki OSM po deduplikacji (FUA)", fontsize=11)
        ax.legend(loc="lower left", markerscale=3, fontsize=8)
        ax.set_xlabel("x EPSG:2180 [m]")
        ax.set_ylabel("y EPSG:2180 [m]")
        fig.tight_layout()
        fig.savefig(REPORT_DIR / f"qa_{k}.png")
        plt.close(fig)

    n_raw, n_dd = len(raw), len(dd)
    L = []
    A = L.append
    A("# Przystanki OSM (maska pokrycia GTFS): inwentaryzacja")
    A("")
    A("Faza 0, generowane przez `pipeline/osm_stops.py` (ekstrakcja i deduplikacja) oraz `python -m pipeline.osm_stops --report` (ten raport). "
      "To wejście do maski pokrycia GTFS (§6 briefu); dopasowanie do przystanków GTFS jest osobnym, późniejszym krokiem.")
    A("")
    A("## Dane")
    A("")
    A(f"- Plik: `poland-latest.osm.pbf` (Geofabrik), {int(man.get('bytes', 0)) / 1e9:.2f} GB, licencja ODbL 1.0, pobrany {man.get('downloaded_at', '?')[:10]}; "
      f"**stan danych (znacznik replikacji z nagłówka PBF): {man.get('data_date', '?')}**; SHA-256 w `data/manifest.csv`.")
    A("- Jeden przebieg pyosmium po całym pliku (węzły i drogi; współrzędne dróg z indeksu lokalizacji węzłów). Obiekty ze znacznikami `highway`, `public_transport` lub `railway`, klasyfikowane jak niżej. Drogi (platformy jako obszary) sprowadzone do punktu = średnia współrzędnych wierzchołków.")
    A("- **Nie czytano relacji** (multipoligony peronów i stacji). Są rzadkie, ale ich brak lekko zaniża liczbę dużych stacji i peronów; stacje kolejowe są przeważnie węzłami lub zamkniętymi drogami.")
    A("")
    A("### Reguły wyboru obiektów")
    A("")
    A("| Obiekt | `kind` |")
    A("|---|---|")
    A("| `railway=tram_stop` | `tram` |")
    A("| `highway=bus_stop` | `bus` |")
    A("| `railway=station` lub `halt` (z `station=subway` albo `subway=yes`) | `rail_station` (`subway`) |")
    A("| `public_transport=station` | `subway` / `rail_station` / `bus` (dworzec autobusowy) / `tram` wg `station`, `train`, `subway`, `bus`, `tram`; bez trybu: `platform_unknown` |")
    A("| `public_transport=platform` | `tram=yes`: `tram`; `subway=yes`: `subway`; `train=yes` lub `railway=platform`: `rail_platform`; `light_rail=yes`: `tram`; `bus=yes` / `trolleybus=yes`: `bus`; `ferry=yes`: `ferry`; inaczej `platform_unknown` |")
    A("")
    A("Pominięte: `public_transport=stop_position` (chyba że ma też jeden ze znaczników powyżej) oraz obiekty `disused` / `abandoned` / `construction` / `proposed` / `razed` (jako klucz albo wartość `highway` / `railway` / `public_transport`). "
      "Peronów niekomunikacyjnych nie da się w OSM wiarygodnie wykluczyć; `platform_unknown` zostaje jako osobna kategoria (tryb nieokreślony, część może nie być przystankami). Przystanki szkolne i prywatne (`access=private`) nie są filtrowane.")
    A("")
    A("## Liczby krajowe (wg `kind`)")
    A("")
    A("| Rodzaj | Surowe | Po deduplikacji | Usunięte | Bez nazwy (po dedup.) |")
    A("|---|---|---|---|---|")
    for k in KIND_ORDER:
        a, b = int((raw["kind"] == k).sum()), int((dd["kind"] == k).sum())
        if a == 0 and b == 0:
            continue
        un = int(dd.loc[dd["kind"] == k, "unnamed"].sum())
        A(f"| {KIND_PL[k]} (`{k}`) | {a} | {b} | {a - b} | {un} ({pct(un, b)}) |")
    A(f"| **Razem** | **{n_raw}** | **{n_dd}** | **{n_raw - n_dd}** | **{int(dd['unnamed'].sum())} ({pct(dd['unnamed'].sum(), n_dd)})** |")
    A("")
    A("Podział wg znacznika źródłowego (surowe): " + ", ".join(f"`{k}`: {v}" for k, v in raw["source_tag"].value_counts().items()) + ".")
    A("")
    A(f"Po dedup.: rekordy z `ref` {pct(dd['ref'].notna().sum(), n_dd)}, z `operator` {pct(dd['operator'].notna().sum(), n_dd)}, z `network` {pct(dd['network'].notna().sum(), n_dd)}.")
    A("Rozbicie wg województw (NUTS 2 z GISCO 2021; Mazowsze to w NUTS 2021 dwa regiony: stołeczny i regionalny) w `osm_stops_by_voivodeship_kind.csv`.")
    A("")
    A(f"## Deduplikacja (promień {DEDUP_RADIUS_M:.0f} m)")
    A("")
    A("OSM często opisuje jeden fizyczny przystanek podwójnie: słupek `highway=bus_stop` (węzeł) i peron `public_transport=platform` (węzeł lub obszar). Reguła:")
    A("")
    A("1. Obiekty w EPSG:2180 szeregowane: słupki i stacje (`highway=bus_stop`, `railway=*`, `public_transport=station`) przed peronami-węzłami, te przed peronami-drogami; w grupie najpierw nazwane, potem wg `osm_id`.")
    A(f"2. Kolejno każdy jeszcze nieprzypisany obiekt jest **zalążkiem** i pochłania wszystkie nieprzypisane obiekty w promieniu {DEDUP_RADIUS_M:.0f} m, które (a) są **tego samego trybu** (autobus; tramwaj; kolej = stacja i peron kolejowy; metro; prom) albo są `platform_unknown` (pochłaniany przez dowolny tryb), oraz (b) **nie mają konfliktu nazw** (obie nazwy obecne i różne po `casefold`: nie łączymy).")
    A("3. Zalążki nie łączą się łańcuchowo, więc rząd przystanków co ok. 10 m nie zapada się w jeden punkt. Brakujące `name` / `ref` / `network` / `operator` zalążka są uzupełniane od pochłoniętych. Pozycja = pozycja zalążka; `n_merged` i `merged_ids` zapisują pochłonięte obiekty.")
    A("")
    A(f"Efekt: **{n_raw} → {n_dd}** obiektów, usunięto **{n_raw - n_dd}** ({pct(n_raw - n_dd, n_raw)}).")
    A("")
    A("| Zalążek ← pochłonięty | Liczba |")
    A("|---|---|")
    for k, v in stats["pairs"].items():
        A(f"| `{k}` | {v} |")
    A("")
    A("Interpretacja: wiersze `… ← public_transport=platform` to właściwy efekt (podwójny opis jednego przystanku). Wiersze „słupek ← słupek” to dwa obiekty tego samego trybu i nazwy w odległości poniżej progu (np. dwa słupki jednego przystanku albo dwa kierunki na torowisku tramwajowym); dla maski pokrycia nie ma to znaczenia, ale **liczba po deduplikacji to liczba punktów-przystanków, nie słupków ani peronów**.")
    A("")
    A("## Aglomeracje fazy 1")
    A("")
    A(f"Obszar: {poly_src}.")
    A("")
    A("| Aglomeracja | FUA km² | Razem (dedup.) | Razem (surowe) | " + " | ".join(KIND_PL[k] for k in KIND_ORDER) + " | Bez nazwy |")
    A("|" + "---|" * (6 + len(KIND_ORDER)))
    for r in ag_rows:
        A(f"| {r['agg']} | {r['fua_km2']:.0f} | {r['razem_dedup']} | {r['razem_surowe']} | " + " | ".join(str(r[k]) for k in KIND_ORDER) + f" | {r['bez_nazwy']} ({pct(r['bez_nazwy'], r['razem_dedup'])}) |")
    A("")
    A("Wykresy kontrolne (przystanki po dedup. na tle granicy FUA): " + ", ".join(f"`qa_{k}.png`" for k in AGGLO) + ". Mają pokazać dziury (obszary bez przystanków, np. gminy ze słabo zmapowanym transportem) i skupiska artefaktów.")
    A("")
    A("## Ograniczenia")
    A("")
    A("- OSM jest uzupełniany ochotniczo: kompletność jest nierówna między gminami; brak przystanku w OSM może zawyżać późniejszy wskaźnik pokrycia.")
    A("- Przystanki obecne w OSM, a nieobecne w GTFS (przewoźnicy prywatni), to dokładnie sygnał dziur GTFS (§6 briefu); nie filtrowano po `operator`.")
    A("- Przystanki tymczasowe, objazdowe i szkolne nie są wydzielane.")
    A("- Dedup nie łączy przystanków różnych trybów (np. autobus i tramwaj przy wspólnym przystanku), co jest zamierzone.")
    (REPORT_DIR / "osm_stops.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    write_meta(REPORT_DIR, "osm_stops_report", inputs=["osm_poland_pbf", "osm_aux_nuts2_2021"], started=t0,
               extra={"n_raw": n_raw, "n_dedup": n_dd, "dedup_radius_m": DEDUP_RADIUS_M,
                      "agglomeration_polygons": poly_src})
    print("report written")


def main() -> None:
    if "--report" in sys.argv:
        return report()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    df = extract()
    print("extracted", len(df), "objects in", round(time.time() - t0), "s")
    df.to_parquet(OUT / "stops.parquet", index=False)
    dd, pairs = dedup(df)
    dd.to_parquet(OUT / "stops_dedup.parquet", index=False)
    write_json(OUT / "dedup_stats.json", {
        "radius_m": DEDUP_RADIUS_M, "n_in": len(df), "n_out": len(dd),
        "removed": len(df) - len(dd),
        "pairs": dict(sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0])))})
    print("dedup", len(df), "->", len(dd))
    print(df["kind"].value_counts().to_string())
    write_meta(OUT, "osm_stops", inputs=["osm_poland_pbf"], started=t0,
               extra={"n_raw": len(df), "n_dedup": len(dd)})


if __name__ == "__main__":
    sys.exit(main())
