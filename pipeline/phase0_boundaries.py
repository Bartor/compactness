"""Phase 0, boundaries: agglomeration table, GZM variants, QA map, web hand-off.

Outputs
* results/qa/phase0/boundaries/agglomerations.csv + .md      (Polish)
* results/qa/phase0/boundaries/gzm_variants.json (numbers; the Polish .md is written from them)
* results/qa/phase0/boundaries/gzm_variants.png
* results/web/fua.geojson, results/web/catalog.json

Population assignment
* NSP 2021 1 km grid: a cell belongs to a polygon when its centroid (EPSG:2180) lies inside it.
* GHS-POP R2023A 2020 (100 m, Mollweide): the polygon is densified (250 m), reprojected to
  ESRI:54009, a window is read from the VRT and cells whose centre lies inside the polygon
  (rasterio geometry_mask, all_touched=False) are summed; nodata is ignored.

Run: python -m pipeline.phase0_boundaries
"""
from __future__ import annotations

import datetime as dt
import json
import re
import warnings
import time
from functools import lru_cache

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer
from rasterio import features, windows
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

from pipeline.boundaries import (gzm_boundary, gzm_gminas, load_agglomeration, load_lau, load_urau)
from pipeline.common import RAW, RESULTS, load_config, round_sig, sig, write_json, write_meta

matplotlib.use("Agg")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pipeline")
import matplotlib.pyplot as plt  # noqa: E402

QA = RESULTS / "qa" / "phase0" / "boundaries"
WEB = RESULTS / "web"
GHS_POP_VRT = RAW / "ghsl" / "ghs_pop" / "ghs_pop_2020_poland.vrt"
NSP_SHP = RAW / "nsp2021" / "extracted" / "GRID_NSP2021_RES.shp"
TO_MOLL = Transformer.from_crs("EPSG:2180", "ESRI:54009", always_xy=True).transform
GZM_MIN_FUA_SHARE = 0.05  # FUA belongs to GZM variant (a) when >= 5 % of its area is inside GZM

INPUT_IDS = ["urau_2021_100k_all", "lau_2021_01m", "nsp2021_grid_1km_shp"]


@lru_cache(maxsize=1)
def nsp_points() -> gpd.GeoDataFrame:
    g = gpd.read_file(NSP_SHP)[["RES", "geometry"]].to_crs("EPSG:2180")
    pts = gpd.GeoDataFrame({"RES": g.RES.values}, geometry=g.geometry.centroid, crs="EPSG:2180")
    return pts


def nsp_sum(geom) -> int:
    pts = nsp_points()
    idx = pts.sindex.query(geom, predicate="contains")
    return int(pts.RES.values[idx].sum())


_src = None


def ghsl_sum(geom) -> float:
    global _src
    if _src is None:
        _src = rasterio.open(GHS_POP_VRT)
    src = _src
    g = shp_transform(TO_MOLL, shapely.segmentize(geom, 250))
    win = windows.from_bounds(*g.bounds, transform=src.transform)
    win = windows.Window(int(np.floor(win.col_off)) - 1, int(np.floor(win.row_off)) - 1,
                         int(np.ceil(win.width)) + 3, int(np.ceil(win.height)) + 3)
    arr = src.read(1, window=win)
    m = features.geometry_mask([g], out_shape=arr.shape, transform=src.window_transform(win),
                               invert=True, all_touched=False)
    ok = m & (arr != src.nodata) & (arr > 0)
    return float(arr[ok].sum())


def gminas_inside(geom, min_share: float = 0.5) -> gpd.GeoDataFrame:
    lau = load_lau()
    cand = lau.iloc[lau.sindex.query(geom, predicate="intersects")]
    share = cand.geometry.intersection(geom).area / cand.geometry.area
    return cand[share >= min_share]


def km2(geom) -> float:
    return geom.area / 1e6


def names(codes: list[str]) -> str:
    u = load_urau().set_index("URAU_CODE")
    return "; ".join(u.loc[c, "URAU_NAME"] for c in codes)


def agglomeration_row(agg_id: str) -> dict:
    a = load_agglomeration(agg_id)
    fua, core = a["fua"], a["core"]
    g_fua, g_core = gminas_inside(fua), gminas_inside(core)
    nsp_f, nsp_c = nsp_sum(fua), nsp_sum(core)
    gh_f, gh_c = ghsl_sum(fua), ghsl_sum(core)
    return {
        "id": agg_id, "name": a["name"], "phase": a["phase"],
        "fua_codes": " ".join(a["fua_codes"]), "city_codes": " ".join(a["city_codes"]),
        "fua_names": names(a["fua_codes"]), "core_names": names(a["city_codes"]),
        "fua_area_km2": km2(fua), "core_area_km2": km2(core),
        "gminas_fua": len(g_fua), "gminas_core": len(g_core),
        "core_admin_area_km2": float(g_core.AREA_KM2.sum()),
        "nsp_pop_fua": nsp_f, "nsp_pop_core": nsp_c,
        "ghsl_pop_fua": round(gh_f), "ghsl_pop_core": round(gh_c),
        "ghsl_to_nsp_fua": gh_f / nsp_f, "ghsl_to_nsp_core": gh_c / nsp_c,
        "lau_pop_2021_fua": float(g_fua.POP_2021.sum()),
    }


def flag(r: float) -> str:
    return "TAK" if abs(r - 1) > 0.05 else "nie"


def write_table(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows).sort_values(["phase", "id"]).reset_index(drop=True)
    df["flag_fua_gt5pct"] = df.ghsl_to_nsp_fua.map(flag)
    df["flag_core_gt5pct"] = df.ghsl_to_nsp_core.map(flag)
    out = df.copy()
    for c in ["fua_area_km2", "core_area_km2", "core_admin_area_km2", "ghsl_to_nsp_fua", "ghsl_to_nsp_core"]:
        out[c] = out[c].map(sig)
    out["lau_pop_2021_fua"] = out.lau_pop_2021_fua.round().astype(int)
    out.to_csv(QA / "agglomerations.csv", index=False, encoding="utf-8", lineterminator="\n")
    return out


def md_table(df: pd.DataFrame, cols: dict[str, str]) -> str:
    head = "| " + " | ".join(cols.values()) + " |\n|" + "|".join(["---"] * len(cols)) + "|\n"
    body = ""
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (int, np.integer)):
                cells.append(f"{v:,}".replace(",", " "))
            elif isinstance(v, (float, np.floating)):
                cells.append(f"{v:,.4g}".replace(",", " ") if abs(v) < 1e4 else f"{v:,.0f}".replace(",", " "))
            else:
                cells.append(str(v))
        body += "| " + " | ".join(cells) + " |\n"
    return head + body


def write_table_md(df: pd.DataFrame) -> None:
    t1 = md_table(df, {"name": "Aglomeracja", "phase": "Faza", "fua_codes": "Kody FUA", "city_codes": "Kody rdzenia (URAU)",
                       "fua_area_km2": "Pow. FUA km²", "core_area_km2": "Pow. rdzenia km²",
                       "core_admin_area_km2": "Pow. adm. gmin rdzenia km²",
                       "gminas_fua": "Gmin w FUA", "gminas_core": "Gmin w rdzeniu"})
    t2 = md_table(df, {"name": "Aglomeracja", "nsp_pop_fua": "NSP 2021 FUA", "ghsl_pop_fua": "GHSL 2020 FUA",
                       "ghsl_to_nsp_fua": "GHSL/NSP FUA", "flag_fua_gt5pct": "|różn.|>5%",
                       "nsp_pop_core": "NSP 2021 rdzeń", "ghsl_pop_core": "GHSL 2020 rdzeń",
                       "ghsl_to_nsp_core": "GHSL/NSP rdzeń", "flag_core_gt5pct": "|różn.|>5%"})
    txt = f"""# Faza 0: aglomeracje, granice i ludność (tabela wstępna)

Wygenerowano: {dt.date.today().isoformat()} (`python -m pipeline.phase0_boundaries`). Granice: Eurostat GISCO Urban Audit 2021
(skala 100K) i LAU 2021; GZM w **wariancie (a)**: suma FUA przecinających się z Metropolią GZM
(decyzja właściciela z 2026-11-23, patrz `gzm_variants.md`).

## Granice

{t1}
Pola FUA i rdzenia liczone z geometrii URAU w EPSG:2180. „Pow. adm. gmin rdzenia” to suma pól `AREA_KM2` z LAU 2021
gmin zawartych (≥ 50 % powierzchni) w rdzeniu: dla porównania z polem granicy URAU (Warszawa ~517 km², Kraków ~327,
Wrocław ~293 to powierzchnie administracyjne, nie miara miasta; brief §2). Liczba gmin: jednostki LAU, których ≥ 50 %
powierzchni leży w danym obszarze. Rdzeń Trójmiasta = Gdańsk + Gdynia (miasta URAU) + Sopot (jednostka LAU; Sopot nie jest
miastem URAU). Rdzeń GZM = 13 miast URAU leżących w GZM. Rdzeń Bydgoszczy–Torunia = oba miasta.

## Ludność: NSP 2021 (siatka 1 km) kontra GHS-POP R2023A, epoka 2020

{t2}
Zasady przypisania:

- **NSP 2021:** komórka siatki 1 km (zmienna `RES`, ludność rezydująca ogółem; stan na 31.03.2021) należy do obszaru,
  jeśli jej **centroid** leży wewnątrz wielokąta (centroid-in-polygon, EPSG:2180).
- **GHSL:** wielokąt zagęszczony (250 m), przeliczony do Mollweide (ESRI:54009); z VRT czytane jest okno, a sumowane są
  komórki 100 m, których środek leży w wielokącie (`rasterio.features.geometry_mask`, `all_touched=False`); nodata pomijane.
- Stosunek GHSL/NSP odbiega od 1 także dlatego, że oba zbiory mają inną datę (2020 vs 31.03.2021), a siatka NSP sumuje się
  do ok. 37,0 mln (poniżej BDL), więc to pierwsze spojrzenie (brief §7.1), nie wynik kontroli. Odchylenie > 5 %
  oznaczono w kolumnach „|różn.|>5%”; wymaga opisu w RAPORT.md (porównanie rozkładu na 1 km, BDL: faza 1).
- Granice URAU (100K) i siatka nie pokrywają się dokładnie, więc na brzegu FUA wpływ centroidów jest rzędu kilku komórek.
"""
    (QA / "agglomerations.md").write_text(pl_dec(txt), encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ GZM variants

def variant_numbers(geom) -> dict:
    g = gminas_inside(geom)
    return {"area_km2": km2(geom), "gminas": len(g), "nsp_pop": nsp_sum(geom), "ghsl_pop": round(ghsl_sum(geom)),
            "lau_pop_2021": float(g.POP_2021.sum())}


def gzm_analysis() -> dict:
    u = load_urau()
    G = gzm_boundary()
    fuas = u[u.URAU_CATG == "F"]
    inter = []
    for r in fuas.itertuples():
        i = r.geometry.intersection(G)
        if i.area > 0:
            nf, gf = nsp_sum(r.geometry), ghsl_sum(r.geometry)
            ni, gi = nsp_sum(i), ghsl_sum(i)
            inter.append({"code": r.URAU_CODE, "name": r.URAU_NAME, "fua_area_km2": km2(r.geometry),
                          "inside_area_km2": km2(i), "area_share_inside": i.area / r.geometry.area,
                          "nsp_pop_fua": nf, "nsp_pop_inside": ni, "nsp_share_inside": ni / nf,
                          "ghsl_pop_fua": round(gf), "ghsl_pop_inside": round(gi), "ghsl_share_inside": gi / gf,
                          "nsp_share_of_gzm": 0.0})
    gz_nsp = nsp_sum(G)
    for d in inter:
        d["nsp_share_of_gzm"] = d["nsp_pop_inside"] / gz_nsp
    sel = [d["code"] for d in inter if d["area_share_inside"] >= GZM_MIN_FUA_SHARE]
    all_codes = [d["code"] for d in inter]
    uu = u.set_index("URAU_CODE")
    A = unary_union(uu.loc[sel].geometry.values)
    A_all = unary_union(uu.loc[all_codes].geometry.values)
    res = {
        "intersecting_fuas": sorted(inter, key=lambda d: d["code"]),
        "selected_codes": sel, "all_intersecting_codes": all_codes, "min_share": GZM_MIN_FUA_SHARE,
        "a_selected": variant_numbers(A), "a_all_intersecting": variant_numbers(A_all),
        "b_metropolis": variant_numbers(G),
        "a_minus_b_km2": km2(A.difference(G)), "b_minus_a_km2": km2(G.difference(A)),
        "a_minus_b_nsp": nsp_sum(A.difference(G)), "b_minus_a_nsp": nsp_sum(G.difference(A)),
        "gminas_in_a_not_in_b": sorted(set(gminas_inside(A).LAU_NAME) - set(gzm_gminas().LAU_NAME)),
        "gminas_in_b_not_in_a": sorted(set(gzm_gminas().LAU_NAME) - set(gminas_inside(A).LAU_NAME)),
    }
    return res, A, G, fuas


def gzm_map(A, G, fuas) -> None:
    fig, ax = plt.subplots(figsize=(10, 9))
    bx = G.buffer(25000).bounds
    near = fuas[fuas.geometry.intersects(G.buffer(25000))]
    lau = load_lau()
    lau_near = lau.iloc[lau.sindex.query(G.buffer(25000), predicate="intersects")]
    lau_near.boundary.plot(ax=ax, color="#d8d8d8", linewidth=0.3)
    gpd.GeoSeries([A], crs=2180).plot(ax=ax, color="#1D4ED8", alpha=0.18)
    gpd.GeoSeries([G], crs=2180).plot(ax=ax, color="#E07B00", alpha=0.22)
    gzm_gminas().boundary.plot(ax=ax, color="#E07B00", linewidth=0.5)
    gpd.GeoSeries([A], crs=2180).boundary.plot(ax=ax, color="#1D4ED8", linewidth=2.2)
    gpd.GeoSeries([G], crs=2180).boundary.plot(ax=ax, color="#E07B00", linewidth=2.2, linestyle="--")
    sel = set(load_config()["agglomerations"]["gzm"]["fua_codes"])
    for r in near.itertuples():
        col = "#1D4ED8" if r.URAU_CODE in sel else "#555555"
        gpd.GeoSeries([r.geometry], crs=2180).boundary.plot(ax=ax, color=col, linewidth=0.9)
        p = r.geometry.representative_point()
        label = r.URAU_NAME.replace("FUA ", "").title()[:22]
        ax.annotate(f"{label}\n({r.URAU_CODE})", (p.x, p.y), fontsize=7, ha="center", color=col)
    ax.set_xlim(bx[0], bx[2]); ax.set_ylim(bx[1], bx[3]); ax.set_aspect("equal")
    ax.set_title("GZM: (a) suma FUA przecinających Metropolię (niebieski) vs (b) 41 gmin Metropolii (pomarańczowy, linia przerywana)\n"
                 "szare: FUA spoza wariantu (a); cienkie linie: gminy LAU 2021 (EPSG:2180)", fontsize=9)
    ax.set_xlabel("x [m], EPSG:2180"); ax.set_ylabel("y [m]")
    fig.savefig(QA / "gzm_variants.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def pl_dec(t: str) -> str:
    """Decimal comma for numbers in Polish text."""
    return re.sub(r"(?<=\d)\.(?=\d)", ",", t)


def fmt(v, nd=0):
    return f"{v:,.{nd}f}".replace(",", " ")


def write_gzm_md(r: dict) -> None:
    a, b, aa = r["a_selected"], r["b_metropolis"], r["a_all_intersecting"]
    rows = ""
    for d in r["intersecting_fuas"]:
        nm = d["name"].replace("FUA ", "").title()
        rows += (f"| {d['code']} | {nm} | {fmt(d['fua_area_km2'])} | {fmt(d['inside_area_km2'])} | "
                 f"{d['area_share_inside']:.1%} | {fmt(d['nsp_pop_fua'])} | {fmt(d['nsp_pop_inside'])} | "
                 f"{d['nsp_share_inside']:.1%} | {d['ghsl_share_inside']:.1%} | {d['nsp_share_of_gzm']:.1%} |\n")

    def vrow(label, v):
        return (f"| {label} | {fmt(v['area_km2'])} | {v['gminas']} | {fmt(v['nsp_pop'])} | {fmt(v['ghsl_pop'])} | "
                f"{fmt(v['ghsl_pop'] / v['nsp_pop'] * 100 - 100, 1)} % | {fmt(v['lau_pop_2021'])} |\n")

    txt = f"""# GZM: dwa warianty granicy (decyzja właściciela, brief §2 i §12.1)

Stan na {dt.date.today().isoformat()}. **Decyzja właściciela z 2026-11-23: wariant (a), suma czterech FUA**
(`config.yaml`: `gzm.boundary_variant: fua_union`). Wariant (b) zostaje poniżej jako punkt odniesienia.

## Jak Eurostat dzieli konurbację (URAU 2021)

Konurbacja nie jest jedną FUA. W URAU 2021 jest tu **pięć osobnych FUA** (każda z własnym rdzeniem lub rdzeniami), a poza
Metropolią leżą kolejne (Rybnik, Jastrzębie-Zdrój, Bielsko-Biała, Częstochowa):

- **PL010F** Katowice (z Chorzowem, Mysłowicami, Siemianowicami, Świętochłowicami; miasta URAU w tej FUA: Katowice, Sosnowiec,
  Bytom, Ruda Śląska, Chorzów, Będzin, Mysłowice, Siemianowice Śląskie, Świętochłowice),
- **PL055F** Gliwice / Zabrze, **PL061F** Tychy, **PL070F** Dąbrowa Górnicza.
- **PL060F** Rybnik dotyka Metropolii tylko śladowo (patrz niżej).

Granica Metropolii GZM: suma **41 gmin członkowskich** z LAU 2021. Lista wg metropoliagzm.pl/metropolia-dzis (pięć
podregionów, „41 miast i gmin”), zgodna z pl.wikipedia.org (hasło Górnośląsko-Zagłębiowska Metropolia). Podstawa prawna: ustawa z 9.03.2017 o związku
metropolitalnym w województwie śląskim (Dz.U. 2017 poz. 730; tekst jedn. Dz.U. 2025 poz. 186) i rozporządzenie Rady Ministrów
z 26.06.2017 (Dz.U. 2017 poz. 1290), w mocy od 1.07.2017. Jaworzno **nie** należy do Metropolii. Lista w kodzie: `pipeline/boundaries.py`
(`GZM_GMINAS`). Uwaga: LAU 2021 pochodzi ze skali 1:1 mln, URAU ze skali 1:100 tys., więc na brzegach są drobne niezgodności
(stąd „ślad” Rybnika).

## Warianty: liczby

| Wariant | Powierzchnia km² | Liczba gmin | Ludność NSP 2021 | Ludność GHSL 2020 | GHSL vs NSP | Ludność LAU 2021 (BDL) |
|---|---|---|---|---|---|---|
{vrow("(a) suma FUA przecinających się z GZM, reguła ≥ 5 % pola FUA w GZM (" + ", ".join(r["selected_codes"]) + ")", a)}{vrow("(a′) wszystkie FUA dotykające GZM (dodatkowo PL060F Rybnik)", aa)}{vrow("(b) granica Metropolii GZM (41 gmin)", b)}
Różnica (a) minus (b): **{fmt(r['a_minus_b_km2'])} km²** i **{fmt(r['a_minus_b_nsp'])} mieszkańców (NSP)** leżą w (a), poza GZM; gminy w (a), nie
będące członkami GZM (≥ 50 % powierzchni w (a)): {", ".join(r['gminas_in_a_not_in_b']) or "brak"}.
Różnica (b) minus (a): **{fmt(r['b_minus_a_km2'])} km²** i **{fmt(r['b_minus_a_nsp'])} mieszkańców (NSP)** leżą w GZM, poza (a); gminy GZM poza (a):
{", ".join(r['gminas_in_b_not_in_a']) or "brak"}.

## FUA przecinające się z GZM: jaka część leży w Metropolii

| Kod | FUA | Pow. FUA km² | Pow. w GZM km² | Udział pola FUA w GZM | Ludność NSP FUA | Ludność NSP w GZM | Udział ludności NSP FUA w GZM | Udział ludności GHSL FUA w GZM | Udział w ludności GZM (NSP) |
|---|---|---|---|---|---|---|---|---|---|
{rows}
**Proponowana reguła nakładania:** FUA wchodzi do wariantu (a), jeśli co najmniej **5 %** jej pola leży w Metropolii.
Wynik jest odporny na wybór progu: każdy próg między ~1 % a ~60 % daje ten sam zestaw (cztery FUA); Rybnik (ślad rzędu 0,1 km²,
artefakt różnicy skal LAU/URAU) odpada, a pozostałe leżą w GZM w ≥ 60 % pola. Zwróć uwagę, że FUA Gliwice/Zabrze i Dąbrowa
Górnicza sięgają poza GZM, i te części wchodzą do (a).

## Kompromisy (opis neutralny)

**(a) suma FUA przecinających się z GZM**
- Spójna z pozostałymi aglomeracjami (wszędzie FUA Eurostatu; porównywalność definicji w całym zestawie i z innymi pracami opartymi na URAU).
- Obejmuje strefy dojazdów wokół rdzeni, w tym obszary poza Metropolią; nie zależy od członkostwa gmin w związku metropolitalnym,
  które jest decyzją polityczną i zmieniało się (Jaworzno nie przystąpiło; gminy mogą dołączać).
- Granica nie pokrywa się z żadną jednostką administracyjną; do tabel per gmina potrzebna jest reguła przypisania gmin do obszaru.
- Wynik jest „sumą kilku FUA”, więc część miar (np. rdzeń, ludność w FUA) zależy od tego, że Eurostat podzielił konurbację na kilka FUA (cztery w wariancie (a), łącznie 13 miast URAU).

**(b) granica Metropolii GZM (41 gmin)**
- Zgodna z jednostką, którą rozumieją odbiorcy w regionie, i z danymi administracyjnymi (BDL, GTFS ZTM GZM obejmuje te gminy).
- Granica = granice gmin, więc wprost sumuje się z tabelami gminnymi (BDL, LAU).
- Odcina część stref dojazdów i sąsiednie ośrodki powiązane funkcjonalnie, a także jest mniej porównywalna z innymi aglomeracjami
  (tam FUA, tu granica związku). Zawiera gminy o charakterze wiejskim (np. Zbrosławice, Rudziniec, Sośnicowice), których FUA nie obejmuje.
- Zmiana składu Metropolii zmienia obszar.

Dla obu wariantów obowiązuje bufor 15 km (FUA lub granica GZM + 15 km) jako domena celów, więc różnica wpływa głównie na
miary „na obszarze”, a w mniejszym stopniu na miary dostępności liczone na buforze.

Mapa: `gzm_variants.png`. Liczby: `gzm_variants.json`.
"""
    (QA / "gzm_variants.md").write_text(pl_dec(txt), encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ web hand-off

NOTES = {
    "trojmiasto": ("Miasto liniowe i nadmorskie (Gdańsk, Sopot, Gdynia): miary względem jednego centrum wymagają zastrzeżenia. "
                   "Eurostat wydziela dwie FUA (Gdańsk z Sopotem oraz Gdynia); granica to ich suma, rdzeń to trzy miasta."),
    "gzm": ("Konurbacja policentryczna (Eurostat: kilka FUA), więc miary względem jednego centrum wymagają zastrzeżenia. "
            "Granica to suma czterech FUA przecinających Metropolię GZM (Katowice, Gliwice/Zabrze, Tychy, Dąbrowa Górnicza), nie 41 gmin Metropolii."),
    "bydgoszcz_torun": "Dwa ośrodki: granica to suma FUA Bydgoszczy i Torunia.",
}


def to_wgs_geojson_geom(geom) -> dict:
    s = gpd.GeoSeries([geom.simplify(100, preserve_topology=True)], crs=2180).to_crs(4326).iloc[0]
    s = shapely.set_precision(s, 1e-5)
    m = shapely.geometry.mapping(s)

    def r(c):
        return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {"type": m["type"], "coordinates": r(m["coordinates"])}


def write_web() -> None:
    cfg = load_config()
    feats, aggs = [], []
    for agg_id in sorted(cfg["agglomerations"]):
        a = load_agglomeration(agg_id)
        c = cfg["agglomerations"][agg_id]
        for level, geom in (("core", a["core"]), ("fua", a["fua"])):
            feats.append({"type": "Feature", "properties": {"id": agg_id, "name": a["name"], "level": level, "phase": a["phase"]},
                          "geometry": to_wgs_geojson_geom(geom)})
        w, s, e, n = gpd.GeoSeries([a["fua"]], crs=2180).to_crs(4326).total_bounds
        aggs.append({"id": agg_id, "name": a["name"], "phase": a["phase"],
                     "centre": [c["centre"]["lon"], c["centre"]["lat"]],
                     "bbox": [round(w, 5), round(s, 5), round(e, 5), round(n, 5)],
                     "note": NOTES.get(agg_id, "")})
    feats.sort(key=lambda f: (f["properties"]["id"], f["properties"]["level"]))
    WEB.mkdir(parents=True, exist_ok=True)
    with open(WEB / "fua.geojson", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        f.write("\n")
    planned = [
        ("density_250m", "Gęstość zaludnienia 250 m (GHSL 2020)", "density"),
        ("frequent_transport", "Zasięg częstej komunikacji", "access"),
        ("transport_performance_30", "Transport performance 30 min", "access"),
        ("gtfs_nodata", "Maska braku danych GTFS", "mask"),
    ]
    layers = [{"id": "fua", "title": "Granice FUA i rdzeni", "type": "geojson", "url": "data/fua.geojson", "kind": "boundary",
               "status": "ready", "attribution": "© EuroGeographics / Eurostat GISCO, Urban Audit 2021",
               "population_date": None, "timetable_date": None,
               "note": "Granice uproszczone (tolerancja ok. 100 m). GZM: suma czterech FUA; Trójmiasto: suma dwóch FUA."}]
    # layers that pipeline.tiles has already filled in (status other than "planned") are kept as they are
    old_path = WEB / "catalog.json"
    kept = {}
    if old_path.exists():
        kept = {l["id"]: l for l in json.loads(old_path.read_text(encoding="utf-8")).get("layers", [])
                if l.get("status") != "planned"}
    for lid, title, kind in planned:
        if lid in kept:
            layers.append(kept[lid])
            continue
        layers.append({"id": lid, "title": title, "type": "pmtiles", "url": None, "kind": kind, "status": "planned",
                       "attribution": "", "population_date": None, "timetable_date": None, "note": ""})
    write_json(WEB / "catalog.json", {"generated": dt.date.today().isoformat(), "agglomerations": aggs, "layers": layers})


def main() -> None:
    t0 = time.time()
    QA.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    rows = [agglomeration_row(k) for k in cfg["agglomerations"]]
    df = write_table(rows)
    write_table_md(df)
    res, A, G, fuas = gzm_analysis()
    write_json(QA / "gzm_variants.json", round_sig(res))
    gzm_map(A, G, fuas)
    write_gzm_md(res)
    write_web()
    extra = {"gzm_variant_used": "fua_union", "min_fua_share_gzm": GZM_MIN_FUA_SHARE}
    write_meta(QA, "phase0_boundaries", inputs=INPUT_IDS, started=t0, extra=extra)
    write_meta(WEB, "phase0_boundaries_web", inputs=INPUT_IDS[:2], started=t0, extra=extra)
    print(df.drop(columns=["fua_names", "core_names"]).to_string())


if __name__ == "__main__":
    main()
