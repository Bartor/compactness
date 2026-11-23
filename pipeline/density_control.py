"""Phase 1, control §7.1: GHSL 2020 vs NSP 2021 (census grid) vs BDL (gmina totals).

Population concepts (all counted for the same domains):
* NSP grid: census 1 km grid, field RES = usually-resident population ("ludność rezydująca"),
  31.03.2021; cells assigned by centroid (phase-0 rule).
* BDL 1644331: NSP 2021, "Ludność rezydująca wg płci i miejsca zamieszkania", ogółem, gmina,
  31.03.2021 (same concept as the grid; checks the centroid assignment and the grid itself).
* BDL 1639271: NSP 2021, "Ludność wg płci i miejsca zamieszkania", ogółem, gmina, 31.03.2021:
  population by the national definition ("ludność faktycznie zamieszkała", incl. people
  temporarily abroad < 12 months), Poland 38 036 118.
* BDL 72305 (31.12.2020, national definition, pre-census balance) was meant as a third reference,
  closest in date to the GHSL epoch; on 2026-11-23 the GUS firewall blocked the API after ~90
  anonymous requests (HTTP 500 "Strona została zablokowana"), so it is not used.
* GHSL: GHS-POP R2023A epoch 2020, 100 m, cells with centre in the polygon (phase-0 rule).

Gminas (types 1-3 of BDL; Warsaw as the city, not its districts) belong to a domain when at
least 50 % of their LAU 2021 area lies inside it (phase-0 rule).  BDL unit id -> LAU_ID:
"10" + first 11 digits (the 12th is the gmina type).

Decomposition per domain: GHSL/NSP = (GHSL/BDL_nat_2021) x (BDL_nat_2021/BDL_res_2021)
x (BDL_res_2021/NSP_grid).  The middle factor is the pure definition effect (resident vs
national, same census, same date); the last one is boundary assignment (whole gminas vs cell
centroids); the first one is what remains between GHSL 2020 and the national-definition count
(model error, the 2020 vs 31.03.2021 date and GHSL's own input data).

Cell level (1 km): GHSL summed into each census cell (LAEA, area-weighted, see pipeline.density).
Per domain: Pearson r on counts and on log(1+x), Spearman rho, dissimilarity index
D = 1/2 sum |g_i/G - n_i/N| (share of population that would have to move to make the two
spatial distributions identical; insensitive to the level difference), the largest absolute and
relative differences with locations.

Outputs: results/qa/density/control_totals.csv, control_cells.csv, control_top_cells.csv,
data/interim/density/control.json.  BDL downloads: data/raw/bdl/*.json (manifest ids bdl_*).

Run: python -m pipeline.density_control
"""
from __future__ import annotations

import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from scipy import stats

from pipeline.boundaries import all_agglomeration_ids, load_agglomeration, load_lau
from pipeline.common import INTERIM, RAW, RESULTS, USER_AGENT, read_manifest, register, round_sig, sig, write_json
from pipeline.density import census, census_in, ghsl_on_census
from pipeline.phase0_boundaries import ghsl_sum

QA = RESULTS / "qa" / "density"
OUT = INTERIM / "density"
BDL_DIR = RAW / "bdl"
BDL_API = "https://bdl.stat.gov.pl/api/v1/data/by-variable/{var}"
BDL_VARS = {
    "bdl_nsp2021_resident_gmina": {"var": 1644331, "year": 2021,
                                    "desc": "NSP 2021, ludność rezydująca ogółem, gminy, stan 31.03.2021 (BDL P4252)",
                                    "data_date": "2021-03-31"},
    "bdl_nsp2021_national_gmina": {"var": 1639271, "year": 2021,
                                    "desc": "NSP 2021, ludność ogółem (definicja krajowa), gminy, stan 31.03.2021 (BDL P4179)",
                                    "data_date": "2021-03-31"},
}
NSP_RESIDENT_PL = 37_019_327
NSP_NATIONAL_PL = 38_036_118
TOP_N = 10
REL_MIN_POP = 300          # relative differences only for cells where max(GHSL, NSP) >= this


# ------------------------------------------------------------------ BDL

def fetch_bdl(mid: str, spec: dict) -> pd.DataFrame:
    path = BDL_DIR / f"{mid}.json"
    known = {r["id"] for r in read_manifest()}
    if not (path.exists() and mid in known):
        BDL_DIR.mkdir(parents=True, exist_ok=True)
        url = BDL_API.format(var=spec["var"])
        params = {"format": "json", "unit-level": 6, "year": spec["year"], "page-size": 100}
        rows, page = [], 0
        while True:
            for attempt in range(5):
                r = requests.get(url, params={**params, "page": page}, timeout=60,
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                if r.status_code == 200:
                    break
                time.sleep(5 * (attempt + 1))
            r.raise_for_status()
            r.encoding = "utf-8"
            js = r.json()
            rows += js["results"]
            if "next" not in js.get("links", {}):
                break
            page += 1
            time.sleep(0.6)
        rows.sort(key=lambda d: d["id"])
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"variableId": spec["var"], "year": spec["year"], "unit_level": 6, "results": rows},
                      f, ensure_ascii=False, indent=0, sort_keys=True)
            f.write("\n")
        full_url = f"{url}?format=json&unit-level=6&year={spec['year']}&page-size=100 (all pages)"
        register(mid, path, full_url, license="GUS BDL: dane publiczne, cytować GUS Bank Danych Lokalnych",
                 source="GUS Bank Danych Lokalnych, API v1 (anonimowo)", data_date=spec["data_date"],
                 notes=spec["desc"])
    with open(path, encoding="utf-8") as f:
        js = json.load(f)
    out = []
    for d in js["results"]:
        uid = d["id"]
        if uid[-1] not in "123":
            continue
        val = [v["val"] for v in d["values"] if str(v["year"]) == str(spec["year"])]
        out.append({"bdl_id": uid, "LAU_ID": "10" + uid[:11], "name": d["name"], mid: float(val[0]) if val else np.nan})
    return pd.DataFrame(out)


def bdl_table() -> pd.DataFrame:
    df = None
    for mid, spec in BDL_VARS.items():
        t = fetch_bdl(mid, spec)
        df = t if df is None else df.merge(t[["LAU_ID", mid]], on="LAU_ID", how="outer")
    return df


def gminas_in(geom, lau: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cand = lau.iloc[np.sort(lau.sindex.query(geom, predicate="intersects"))]
    share = cand.geometry.intersection(geom).area / cand.geometry.area
    return cand[share.values >= 0.5]


# ------------------------------------------------------------------ cells

def dissimilarity(g: np.ndarray, n: np.ndarray) -> float:
    return float(0.5 * np.abs(g / g.sum() - n / n.sum()).sum())


def cell_stats(g: np.ndarray, n: np.ndarray) -> dict:
    return {"cells": int(len(g)), "pearson": float(np.corrcoef(g, n)[0, 1]),
            "pearson_log1p": float(np.corrcoef(np.log1p(g), np.log1p(n))[0, 1]),
            "spearman": float(stats.spearmanr(g, n).statistic),
            "dissimilarity": dissimilarity(g, n),
            "sum_abs_diff_scaled": float(np.abs(g * n.sum() / g.sum() - n).sum())}


def reason(row) -> str:
    """Mechanical hint only; the narrative explanation is written in density.md."""
    if row.clipped:
        return "komórka przycięta granicą państwa/brzegiem: GHSL liczy cały kwadrat"
    if row.nsp == 0 and row.ghsl > 0:
        return "NSP = 0: brak mieszkańców w spisie (zabudowa niemieszkalna, przemysł, usługi?)"
    if row.ghsl < 0.2 * row.nsp:
        return "GHSL << NSP: zabudowa nowsza niż dane wejściowe GHSL albo obiekt zbiorowego zakwaterowania?"
    if row.ghsl > 2 * row.nsp:
        return "GHSL >> NSP: kubatura niemieszkalna w komórce (biura, handel, przemysł)?"
    return ""


def main() -> None:
    t0 = time.time()
    QA.mkdir(parents=True, exist_ok=True)
    lau = load_lau()
    bdl = bdl_table()
    lau_b = lau.merge(bdl, on="LAU_ID", how="left")
    unmatched = int(lau_b["bdl_nsp2021_resident_gmina"].isna().sum())
    c = census()
    gh = ghsl_on_census()
    to_wgs = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

    national = {
        "nsp_grid_sum": int(c.RES.sum()), "nsp_resident_published": NSP_RESIDENT_PL,
        "nsp_national_published": NSP_NATIONAL_PL,
        "bdl_resident_2021_sum": int(bdl["bdl_nsp2021_resident_gmina"].sum()),
        "bdl_national_2021_sum": int(bdl["bdl_nsp2021_national_gmina"].sum()),
        "ghsl_in_census_footprint_1km": int(round(gh.sum())),
        "ghsl_in_census_footprint_1km_unclipped_cells": int(round(gh[~c.clipped.values].sum())),
        "bdl_rows_gminas": int(len(bdl)), "lau_without_bdl_match": unmatched,
    }
    with open(INTERIM / "grid250" / "qa.json", encoding="utf-8") as f:
        national["ghsl_poland_250m"] = int(round(json.load(f)["totals"]["poland_sum_250m"]))

    totals, cellrows, tops = [], [], []
    for agg in sorted(all_agglomeration_ids()):
        a = load_agglomeration(agg)
        for dom in ("fua", "core"):
            geom = a[dom]
            gm = gminas_in(geom, lau_b)
            idx = census_in(geom)
            nsp = float(c.RES.values[idx].sum())
            g100 = ghsl_sum(geom)
            res21 = float(gm["bdl_nsp2021_resident_gmina"].sum())
            nat21 = float(gm["bdl_nsp2021_national_gmina"].sum())
            totals.append({
                "agglomeration": agg, "name": a["name"], "domain": dom, "gminas": int(len(gm)),
                "nsp_grid": int(nsp), "bdl_resident_2021": int(res21), "bdl_national_2021": int(nat21),
                "ghsl_2020": int(round(g100)),
                "ghsl_to_nsp": g100 / nsp,
                "f_ghsl_to_national": g100 / nat21,
                "f_national_to_resident": nat21 / res21, "f_bdl_resident_to_grid": res21 / nsp,
                "ghsl_to_bdl_resident": g100 / res21,
                "flag_gt5pct": "TAK" if abs(g100 / nsp - 1) > 0.05 else "nie",
            })
            sub = c.iloc[idx]
            g = gh[idx]
            n = sub.RES.values.astype(float)
            st = cell_stats(g, n)
            unc = ~sub.clipped.values
            st_unc = cell_stats(g[unc], n[unc]) if unc.sum() > 10 else {}
            cellrows.append({"agglomeration": agg, "domain": dom, **st,
                             "dissimilarity_unclipped": st_unc.get("dissimilarity"),
                             "clipped_cells": int((~unc).sum())})
            if dom == "fua":
                df = pd.DataFrame({"CODE": sub.CODE.values, "x": sub.px.values, "y": sub.py.values, "nsp": n, "ghsl": g,
                                   "clipped": sub.clipped.values})
                df["diff"] = df.ghsl - df.nsp
                df["scaled_diff"] = df.ghsl * n.sum() / g.sum() - df.nsp
                big = df[np.maximum(df.ghsl, df.nsp) >= REL_MIN_POP].copy()
                big["rel"] = big.ghsl / big.nsp.where(big.nsp > 0, np.nan)
                sel = pd.concat([
                    df.reindex(df["diff"].abs().sort_values(ascending=False, kind="stable").index[:TOP_N]).assign(kind="abs"),
                    big.reindex((np.log(big.ghsl.clip(lower=1) / big.nsp.clip(lower=1))).abs()
                                .sort_values(ascending=False, kind="stable").index[:TOP_N]).assign(kind="rel"),
                ])
                lon, lat = to_wgs.transform(sel.x.values, sel.y.values)
                pts = gpd.GeoSeries(gpd.points_from_xy(sel.x, sel.y), crs="EPSG:2180")
                j = gpd.sjoin(gpd.GeoDataFrame(geometry=pts), lau[["LAU_NAME", "geometry"]], how="left",
                              predicate="within")
                j = j[~j.index.duplicated()]
                for (i, r), lo, la, gname in zip(sel.iterrows(), lon, lat, j.LAU_NAME.values):
                    tops.append({"agglomeration": agg, "kind": r.kind, "cell": r.CODE, "lon": round(lo, 4),
                                 "lat": round(la, 4), "gmina": gname, "nsp_2021": int(r.nsp),
                                 "ghsl_2020": round(float(r.ghsl)), "diff": round(float(r["diff"])),
                                 "ratio": sig(r.ghsl / r.nsp) if r.nsp > 0 else None,
                                 "clipped": bool(r.clipped), "hint": reason(r)})
    tot = pd.DataFrame(totals)
    cells = pd.DataFrame(cellrows)
    top = pd.DataFrame(tops)
    for df, name in ((tot, "control_totals.csv"), (cells, "control_cells.csv"), (top, "control_top_cells.csv")):
        out = df.copy()
        for col in out.columns:
            if out[col].dtype == float:
                out[col] = out[col].map(lambda v: v if pd.isna(v) else (sig(v, 5) if abs(v) < 1e5 else round(v)))
        out.to_csv(QA / name, index=False, encoding="utf-8", lineterminator="\n")
    write_json(OUT / "control.json", round_sig({"national": national, "totals": totals, "cells": cellrows,
                                                "top_cells": tops, "bdl_variables": BDL_VARS}, 6))
    print(tot[["agglomeration", "domain", "ghsl_to_nsp", "f_ghsl_to_national", "f_national_to_resident",
               "f_bdl_resident_to_grid"]].to_string())
    print(national)
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
