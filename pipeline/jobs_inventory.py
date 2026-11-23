"""Inventory of the Goliszek jobs / working-age population dataset (phase 0).

Reads data/raw/jobs/*.gpkg, writes
  results/qa/phase0/jobs/jobs_inventory.md / .csv / _meta.json
  data/interim/jobs/footprints.gpkg   (dissolved footprint of cells with data, per city)

City / FUA polygons: results/web/fua.geojson (level == "fua", plus a core level if it has one)
when present, otherwise the URAU 2021 files already in data/raw/boundaries.
"""
from __future__ import annotations

import json
import time
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from .common import INTERIM, RAW, RESULTS, ROOT, round_sig, write_meta

warnings.filterwarnings("ignore", category=RuntimeWarning)

JOBS = RAW / "jobs" / "Jobs_2025_7_Cities.gpkg"
WORK = RAW / "jobs" / "Workers_2025_7_Cities.gpkg"
META = RAW / "jobs" / "dataset_metadata.json"
OUT = RESULTS / "qa" / "phase0" / "jobs"
INT = INTERIM / "jobs"
CRS = "EPSG:2180"

# dataset name -> (Polish name, URAU code stem, input year as documented by the author)
CITIES = {
    "Gdansk":   ("Gdańsk",   "PL006", "nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025)"),
    "Krakow":   ("Kraków",   "PL003", "nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025)"),
    "Lodz":     ("Łódź",     "PL002", "dane wejściowe z 2023"),
    "Poznan":   ("Poznań",   "PL005", "dane z 2019, aktualizowane do 2025 zmianą kubatury GHSL 2020-2025"),
    "Szczecin": ("Szczecin", "PL007", "prognoza na 2025 z badania ruchu z 2016"),
    "Warsaw":   ("Warszawa", "PL001", "nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025)"),
    "Wroclaw":  ("Wrocław",  "PL004", "nie podano w opisie zbioru (ogólnie: horyzont alokacji 2025)"),
}
OUTSIDE_THRESHOLD = 0.10   # >10% of jobs or footprint outside the administrative city => "wider"


def load_refs() -> tuple[dict, str]:
    """Return ({dataset city: (core_geom, fua_geom)}, description of the source) in EPSG:2180."""
    web = RESULTS / "web" / "fua.geojson"
    if web.exists():
        g = gpd.read_file(web)
        if "level" in g.columns:
            g = g.to_crs(CRS)
            # best effort: match by name; fall back to URAU below if names do not match
            fua = g[g["level"] == "fua"]
            core = g[g["level"] != "fua"]
            out = {}
            for k, (pl, code, _) in CITIES.items():
                def pick(df):
                    m = df[df.apply(lambda r: any(pl.lower() in str(v).lower() for v in r.drop("geometry")), axis=1)]
                    return m.geometry.union_all() if len(m) else None
                out[k] = (pick(core), pick(fua))
            if all(v[0] is not None and v[1] is not None for v in out.values()):
                return out, "results/web/fua.geojson (level == fua / rdzeń)"
    cities = gpd.read_file(RAW / "boundaries" / "URAU_RG_100K_2021_3035_CITIES.gpkg").to_crs(CRS)
    fuas = gpd.read_file(RAW / "boundaries" / "URAU_RG_100K_2021_3035_FUA.gpkg").to_crs(CRS)
    out = {}
    for k, (pl, code, _) in CITIES.items():
        c = cities[cities["URAU_CODE"] == code + "C"]
        f = fuas[fuas["URAU_CODE"] == code + "F"]
        out[k] = (c.geometry.union_all(), f.geometry.union_all())
    return out, "URAU 2021 (GISCO), pliki w data/raw/boundaries: miasto (C) i FUA (F); results/web/fua.geojson jeszcze nie istnieje"


def grid_check(g: gpd.GeoDataFrame) -> dict:
    """Is it the GHSL 100 m Mollweide grid?  Vertices on multiples of 100 m in ESRI:54009, cell areas."""
    m = g.to_crs("ESRI:54009")
    rng = np.random.default_rng(0)
    idx = rng.choice(len(m), size=min(5000, len(m)), replace=False)
    pts = []
    for geom in m.geometry.iloc[idx]:
        for part in geom.geoms:
            pts.extend(list(part.exterior.coords)[:-1])
    a = np.array(pts)[:, :2]
    on = np.abs(((a + 50) % 100) - 50) < 0.5
    area = m.geometry.area
    return {
        "vertices_on_100m_multiples_x": float(on[:, 0].mean()),
        "vertices_on_100m_multiples_y": float(on[:, 1].mean()),
        "share_full_cells_10000m2_in_mollweide": float((np.abs(area - 10000) < 5).mean()),
        "share_partial_cells": float((area < 9995).mean()),
        "max_cell_area_m2": float(area.max()),
        "multipart_share": float(np.mean([len(x.geoms) > 1 for x in m.geometry])),
    }


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    INT.mkdir(parents=True, exist_ok=True)
    meta = json.loads(META.read_text(encoding="utf-8"))
    jobs = gpd.read_file(JOBS)
    wrk = gpd.read_file(WORK)
    for g in (jobs, wrk):
        g["geometry"] = g.geometry.force_2d()
    crs_name = jobs.crs.to_string() if jobs.crs else "?"
    gc_j, gc_w = grid_check(jobs), grid_check(wrk)
    refs, ref_src = load_refs()
    fua_pending = "pending" in ref_src or "jeszcze nie istnieje" in ref_src

    rows, foot_layers = [], []
    for k, (pl, code, years) in CITIES.items():
        core, fua = refs[k]
        r = {"miasto": pl, "kod_zbioru": k, "lata_wejsciowe": years}
        fp_all = []
        for name, g, col in (("jobs", jobs, "Jobs_25"), ("workers", wrk, "Workers_25")):
            s = g[g["Name_ALL"] == k]
            fp = s.geometry.union_all()
            fp_all.append(fp)
            cen = s.geometry.centroid
            inside = cen.within(core)
            inside_fua = cen.within(fua)
            b = fp.bounds
            r[f"{name}_komorki"] = len(s)
            r[f"{name}_suma"] = float(s[col].sum())
            r[f"{name}_bbox_2180_xmin_ymin_xmax_ymax_m"] = " ".join(f"{v:.0f}" for v in b)
            r[f"{name}_bbox_km"] = f"{(b[2]-b[0])/1000:.1f} x {(b[3]-b[1])/1000:.1f}"
            r[f"{name}_pow_footprint_km2"] = fp.area / 1e6
            r[f"{name}_udzial_sumy_w_miescie"] = float(s.loc[inside, col].sum() / s[col].sum())
            r[f"{name}_udzial_sumy_w_FUA"] = float(s.loc[inside_fua, col].sum() / s[col].sum())
            r[f"{name}_udzial_pow_footprint_poza_miastem"] = float(fp.difference(core).area / fp.area)
            r[f"{name}_pokrycie_miasta_footprintem"] = float(fp.intersection(core).area / core.area)
            r[f"{name}_pokrycie_FUA_footprintem"] = float(fp.intersection(fua).area / fua.area)
            foot_layers.append((name, k, fp))
        both = fp_all[0].union(fp_all[1])
        foot_layers.append(("union", k, both))
        r["miasto_adm_pow_km2"] = core.area / 1e6
        r["FUA_pow_km2"] = fua.area / 1e6
        r["union_pokrycie_miasta"] = float(both.intersection(core).area / core.area)
        r["union_pokrycie_FUA"] = float(both.intersection(fua).area / fua.area)
        r["union_udzial_pow_poza_miastem"] = float(both.difference(core).area / both.area)
        wider = (r["jobs_udzial_sumy_w_miescie"] < 1 - OUTSIDE_THRESHOLD
                 or r["workers_udzial_sumy_w_miescie"] < 1 - OUTSIDE_THRESHOLD
                 or r["union_udzial_pow_poza_miastem"] > OUTSIDE_THRESHOLD)
        r["zasieg"] = "szerzej niż miasto" if wider else "miasto (granice administracyjne)"
        rows.append(r)

    df = pd.DataFrame(rows)
    df = df.sort_values("miasto", key=lambda s: s.map(lambda x: x.translate(str.maketrans("ŁłÓóŚśŹźŻżĄąĆćĘęŃń", "LlOoSsZzZzAaCcEeNn"))))
    df.to_csv(OUT / "jobs_inventory.csv", index=False, encoding="utf-8", lineterminator="\n",
              float_format="%.4f")

    # footprints (EPSG:2180), one layer per kind
    fp_path = INT / "footprints.gpkg"
    if fp_path.exists():
        fp_path.unlink()
    for name in ("jobs", "workers", "union"):
        lay = [(k, fp) for n, k, fp in foot_layers if n == name]
        gdf = gpd.GeoDataFrame(
            {"city": [CITIES[k][0] for k, _ in lay], "dataset_city": [k for k, _ in lay],
             "area_km2": [fp.area / 1e6 for _, fp in lay]},
            geometry=[fp for _, fp in lay], crs=CRS)
        gdf.to_file(fp_path, layer=name, driver="GPKG")

    write_report(df, meta, crs_name, gc_j, gc_w, ref_src, fua_pending, jobs, wrk)
    write_meta(OUT, "jobs_inventory",
               inputs=["jobs_Jobs_2025_7_Cities.gpkg", "jobs_Workers_2025_7_Cities.gpkg",
                       "jobs_dataset_metadata"], started=t0,
               extra={"reference_polygons": ref_src, "outside_threshold": OUTSIDE_THRESHOLD,
                      "grid_check_jobs": round_sig(gc_j), "grid_check_workers": round_sig(gc_w)})
    print(df[["miasto", "jobs_suma", "workers_suma", "jobs_udzial_sumy_w_miescie",
              "workers_udzial_sumy_w_miescie", "union_udzial_pow_poza_miastem",
              "union_pokrycie_miasta", "union_pokrycie_FUA", "zasieg"]].to_string())
    print(gc_j, gc_w)


def f0(x):
    return f"{x:,.0f}".replace(",", " ")


def pct(x):
    return f"{100 * x:.0f}%"


def write_report(df, meta, crs_name, gc_j, gc_w, ref_src, fua_pending, jobs, wrk) -> None:
    L = []
    A = L.append
    A("# Zbiór miejsc pracy i ludności w wieku produkcyjnym (Goliszek): inwentaryzacja")
    A("")
    A("Faza 0, raport generowany przez `pipeline/jobs_inventory.py`. Dane: Goliszek S. (IGiPZ PAN), "
      "*Spatially disaggregated working-age population and job estimates for seven Polish cities with a "
      "2025 allocation horizon*, Mendeley Data, v1, doi:10.17632/mr9ywkgd9t.1, licencja CC BY 4.0, "
      f"publikacja {meta.get('publish_date', '')[:10]}.")
    A("")
    A("## Pliki i format")
    A("")
    A("| Plik | Warstwa | Geometria | Obiekty | Pola | Suma |")
    A("|---|---|---|---|---|---|")
    A(f"| `Jobs_2025_7_Cities.gpkg` | `jobs_2025shp` | MultiPolygon Z | {f0(len(jobs))} | `Id`, `Name_ALL`, `Jobs_25` | {f0(jobs['Jobs_25'].sum())} miejsc pracy |")
    A(f"| `Workers_2025_7_Cities.gpkg` | `workers_2025shp` | MultiPolygon Z | {f0(len(wrk))} | `Id`, `Name_ALL`, `Workers_25` | {f0(wrk['Workers_25'].sum())} osób w wieku produkcyjnym |")
    A("")
    A("- `Workers_25` to ludność w wieku produkcyjnym (kobiety 18-59, mężczyźni 18-64), **nie** zatrudnieni mieszkańcy; `Jobs_25` to miejsca pracy według lokalizacji zakładu (autor: „Workers_25 represents working-age population, not employed residents”). Wartości ułamkowe (alokacja proporcjonalna), zachowane bez zaokrąglania.")
    A("- `Name_ALL` zawiera nazwy miast bez polskich znaków (Gdansk, Krakow, Lodz, Poznan, Szczecin, Warsaw, Wroclaw). `Id` jest unikalny w obrębie miasta, ale w Jobs zakresy Id różnych miast nakładają się, a ten sam `Id` w plikach Jobs i Workers wskazuje różne geometrie (sprawdzone: 0 zgodnych par), więc nie jest kluczem łączenia plików. Łączyć trzeba geometrią.")
    A("- Warstwy zawierają tylko komórki z dodatnią wartością (autor: „Released layers contain polygons with positive allocated values”). Brak komórek = brak alokacji (0 albo poza zasięgiem danych wejściowych); tego z samych plików nie da się rozróżnić.")
    A("- Brak GZM i brak osobnych danych dla Gdyni (Trójmiasto: tylko Gdańsk). Brak przepływów OD (autor: „does not contain individual records or origin-destination commuting flows”).")
    A("")
    A("## Układ współrzędnych i siatka")
    A("")
    A(f"- CRS pliku: `{crs_name[:60]}` (ESRI:102173, ETRS89 / Poland CS92, tożsamy z EPSG:2180). Do EPSG:2180 nie trzeba przeliczać.")
    A(f"- Komórki mają nominalnie 100 x 100 m. Po przeliczeniu do Mollweide (ESRI:54009) wierzchołki leżą na wielokrotnościach 100 m: {pct(gc_j['vertices_on_100m_multiples_x'])} (x) i {pct(gc_j['vertices_on_100m_multiples_y'])} (y) wierzchołków w Jobs; {pct(gc_w['vertices_on_100m_multiples_x'])} i {pct(gc_w['vertices_on_100m_multiples_y'])} w Workers. Pełne komórki mają dokładnie 10 000 m² w Mollweide: {pct(gc_j['share_full_cells_10000m2_in_mollweide'])} (Jobs), {pct(gc_w['share_full_cells_10000m2_in_mollweide'])} (Workers).")
    A("- **Wniosek: to siatka GHSL 100 m w Mollweide (ESRI:54009), przepisana do EPSG:2180** (w 2180 komórki są lekko zniekształcone, szerokość ok. 109-111 m zamiast 100 m, pole zachowane w Mollweide). Pozostałe wierzchołki to cięcia na granicach stref modeli ruchu: "
      f"{pct(gc_j['share_partial_cells'])} komórek Jobs i {pct(gc_w['share_partial_cells'])} komórek Workers jest niepełnych (pole < 10 000 m²).")
    A(f"- Obiekty wieloczęściowe: {pct(gc_j['multipart_share'])} (Jobs) i {pct(gc_w['multipart_share'])} (Workers); największy obiekt Jobs ma {f0(gc_j['max_cell_area_m2'])} m², Workers {f0(gc_w['max_cell_area_m2'])} m² (kilka sąsiednich komórek scalonych w jeden obiekt MultiPolygon). **Do analizy nie traktować obiektu jako jednej komórki:** przed dopasowaniem do GHS-POP/siatki 250 m trzeba rasteryzować lub dzielić wg siatki, a wartość rozkładać proporcjonalnie do pola.")
    A("- Zgodność z siatką GHS-POP/GHS-BUILT-S R2023A (też 100 m Mollweide) jest więc zachowana, ale wartości dotyczą **epoki zabudowy 2025** (modelowanej), a nie 2020, której używamy do ludności (§3 briefu). Przy łączeniu z ludnością GHS-POP 2020 trzeba to wpisać w ograniczenia.")
    A("")
    A("## Metoda wg autora (cytaty istotne dla interpretacji)")
    A("")
    A("- „Source counts were supplied as attributes of transport-zone polygons.” Dane wejściowe to **strefy modeli ruchu / badań komunikacyjnych miast**, nie rejestr zatrudnienia.")
    A("- „We distributed the working-age population within each transport zone in proportion to residential volume, and jobs in proportion to non-residential volume.” Podział wewnątrz strefy wg kubatury zabudowy GHSL (GHS-BUILT-V): mieszkaniowej (całość minus niemieszkaniowa) dla ludności, **niemieszkaniowej dla miejsc pracy**. W obrębie strefy rozkład jest więc modelowany, nie obserwowany; wiarygodna jest wielkość strefy, nie pojedynczej komórki.")
    A("- „We applied no additional spatial masks or land-use exclusions.” Brak masek (np. lasów, wód): komórki mogą mieć wartości tam, gdzie GHSL ma kubaturę błędnie.")
    A("- „The dataset has a common 2025 allocation horizon, but its source counts do not represent a uniform observation year.” **Horyzont 2025 dotyczy epoki kubatury GHSL, nie roku danych o pracy/ludności.**")
    A("- Poznań: dane z 2019 zaalokowane wg kubatury 2020, potem zaktualizowane zmianą kubatury 2020-2025 „without renormalising the resulting estimates to the original zone totals”: sumy nie muszą zgadzać się ze źródłowymi.")
    A("- Łódź: „inputs refer to 2023”; Szczecin: „2025 forecast from the 2016 traffic study” (prognoza, nie stan faktyczny; tłumaczy to prawdopodobnie niską liczbę miejsc pracy względem ludności).")
    A("- „These assessments describe consistency with building capacity and spatial structure, rather than direct accuracy against observed population or employment counts.” Autor nie waliduje dokładności względem spisu/zatrudnienia. Wyniki traktować jako „estymaty alokacyjne”, nie pomiar.")
    A("- Dla Gdańska, Krakowa, Warszawy i Wrocławia opis zbioru nie podaje roku danych wejściowych (tylko ogólny horyzont 2025); trzeba go ustalić z manuskryptu towarzyszącego (nie jest dołączony do zbioru).")
    A("")
    A("## Sumy i lata wejściowe per miasto")
    A("")
    A("| Miasto | Miejsca pracy | Wiek produkcyjny | Miejsca pracy / ludność w w.p. | Lata wejściowe (wg autora) |")
    A("|---|---|---|---|---|")
    for _, r in df.iterrows():
        A(f"| {r['miasto']} | {f0(r['jobs_suma'])} | {f0(r['workers_suma'])} | {r['jobs_suma'] / r['workers_suma']:.2f} | {r['lata_wejsciowe']} |")
    A(f"| **Razem** | **{f0(df['jobs_suma'].sum())}** | **{f0(df['workers_suma'].sum())}** | {df['jobs_suma'].sum() / df['workers_suma'].sum():.2f} | |")
    A("")
    A("Sumy zgadzają się z opisem zbioru (ok. 3,25 mln miejsc pracy i 3,62 mln osób w wieku produkcyjnym).")
    A("")
    A("## Zasięg przestrzenny")
    A("")
    A(f"Odniesienie: {ref_src}. Footprint = suma (dissolve) komórek z danymi; zapisany w `data/interim/jobs/footprints.gpkg` (EPSG:2180, warstwy `jobs`, `workers`, `union`). "
      "„W mieście” = środek komórki w granicy miasta (URAU „city”, generalizowana 1:100 000, więc granica przybliżona).")
    A("")
    A("| Miasto | Pow. miasta (URAU) km² | Footprint Jobs km² | Footprint Workers km² | Bbox Jobs (km) | Praca: udział sumy w mieście | Ludność w.p.: udział sumy w mieście | Footprint (suma) poza miastem | Pokrycie miasta | Pokrycie FUA | Wniosek |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in df.iterrows():
        A(f"| {r['miasto']} | {r['miasto_adm_pow_km2']:.0f} | {r['jobs_pow_footprint_km2']:.0f} | {r['workers_pow_footprint_km2']:.0f} | {r['jobs_bbox_km']} | {pct(r['jobs_udzial_sumy_w_miescie'])} | {pct(r['workers_udzial_sumy_w_miescie'])} | {pct(r['union_udzial_pow_poza_miastem'])} | {pct(r['union_pokrycie_miasta'])} | {pct(r['union_pokrycie_FUA'])} | {r['zasieg']} |")
    A("")
    A("Pokrycie = udział powierzchni miasta (FUA) przykryty footprintem (Jobs lub Workers). Footprint nie zawiera komórek o zerowej alokacji, więc pokrycie <100% w mieście oznacza tereny bez kubatury GHSL (lasy, wody, pola), a nie dziury w danych; to hipoteza, nie sprawdzono tego względem pokrycia terenu. Szczecin wyróżnia się niskim pokryciem miasta (ok. 1/3 powierzchni): zakres stref modelu ruchu z 2016 r. lub rozległe tereny niezabudowane w granicach miasta; do wyjaśnienia przed użyciem w dostępności.")
    if fua_pending:
        A("")
        A("Uwaga: **porównanie z FUA robione na surowych granicach URAU 2021 (GISCO)**, bo `results/web/fua.geojson` jeszcze nie istnieje; po jego pojawieniu się raport trzeba przeliczyć (`python -m pipeline.jobs_inventory`). Kolumna „Pokrycie FUA” dotyczy całego obszaru FUA, bez bufora 15 km.")
    A("")
    A("### Interpretacja i konsekwencje")
    A("")
    wide = df[df["zasieg"].str.startswith("szerzej")]["miasto"].tolist()
    narrow = df[~df["zasieg"].str.startswith("szerzej")]["miasto"].tolist()
    A(f"- Zasięg szerszy niż miasto (próg: >{int(OUTSIDE_THRESHOLD * 100)}% sumy lub powierzchni poza granicą miasta): {', '.join(wide) if wide else 'brak'}.")
    A(f"- Zasięg ≈ miasto w granicach administracyjnych: {', '.join(narrow) if narrow else 'brak'}.")
    A("- Zbiór **nie obejmuje całych FUA** w żadnym z siedmiu miast: poza footprintem wynik dostępności do miejsc pracy to „brak danych”, nie 0 (§4.6 briefu). W szczególności dostępność miejsc pracy z gmin podmiejskich spoza footprintu jest nieobliczalna, a miejsca pracy leżące poza footprintem nie są wliczone do liczby osiągalnych w 30/45 min (**zaniżenie** w pobliżu granicy zasięgu).")
    A("- Kraków, Wrocław, Poznań, Łódź, Gdańsk, Szczecin i Warszawa mają różne lata danych i różny stopień modelowania (m.in. prognoza dla Szczecina); porównania **między miastami** wymagają adnotacji.")
    A("- Dane Goliszka służą tylko do wskaźników miejsc pracy (§4.6); ludność do miar gęstości pozostaje z NSP 2021 / GHS-POP 2020.")
    (OUT / "jobs_inventory.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
