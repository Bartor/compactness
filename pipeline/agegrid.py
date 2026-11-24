"""Age groups on the 250 m grid (ROADMAP item 13, part 1).

    python -m pipeline.agegrid build      # data/interim/services/age_cells.parquet + age_qa.json
    python -m pipeline.agegrid tables     # data/interim/services/age_metrics.parquet (read by access_services)

Source: GUS NSP 2021 1 km grid (GRID_NSP2021_RES, the same file as the census-scaled population grid; manifest id
nsp2021_grid_1km_shp), fields RES (usually resident population, 31.03.2021), RES_0_14, RES_15_64, RES_65_.  The grid
offers exactly these three age groups (no finer split), so the groups used are 0-14 and 65+ (15-64 for checks).

Disaggregation to the project's 250 m EPSG:2180 cells
* every 250 m cell of ``data/interim/popgrid/cells_<agg>.parquet`` keeps its census-scaled population p_c;
* the cell is split into 5 x 5 sub-cells; each sub-cell centre is assigned to the 1 km census cell containing it;
  sub-cells in census cells with RES = 0 are ignored (the scaled grid holds nobody there);
* share of group g in the cell = mean over its valid sub-cells of RES_g / RES of their census cell;
  group population = p_c x share.  A cell with no valid sub-cell gets null (outside Poland or census-empty).
* Check: summed over all cells of an agglomeration region, the group populations equal the census group totals
  weighted by the same sub-cell rule (see age_qa.json), and RES_0_14 + RES_15_64 + RES_65_ = RES in the census file.
* Variant "centroid": share from the census cell holding the cell centre (used only to test robustness).

What the disaggregation cannot support: the age split inside a 1 km square is uniform by construction.  A group
difference therefore comes only from differences BETWEEN 1 km squares.  For each result the table also gives the
range the group value could take if, inside every 1 km square, the group lived in the best- or worst-served 250 m
cells (bounds).  Rule used for flags: a difference group minus all residents is reported as "nie do obrony" when it
is smaller than 1 pp (1 point of performance), or when the main and centroid variants disagree in sign.
"""
from __future__ import annotations

import argparse
import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline.common import INTERIM, RAW, write_json

AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
OUT = INTERIM / "services"
NSP_SHP = RAW / "nsp2021" / "extracted" / "GRID_NSP2021_RES.shp"
GROUPS = {"0_14": "RES_0_14", "15_64": "RES_15_64", "65": "RES_65_"}
GROUP_LABEL = {"all": "wszyscy mieszkańcy", "0_14": "w wieku 0–14 lat", "65": "w wieku 65+ lat", "15_64": "15–64"}
NSUB = 5
RES = 250.0
T2180_TO_3035 = Transformer.from_crs("EPSG:2180", "EPSG:3035", always_xy=True)


def census() -> tuple[pd.DataFrame, np.ndarray, int, int]:
    g = gpd.read_file(NSP_SHP, columns=["CODE", "RES", *GROUPS.values()], ignore_geometry=True)
    g["E"] = g.CODE.str.extract(r"E(\d+)$")[0].astype(np.int64)
    g["N"] = g.CODE.str.extract(r"N(\d+)E")[0].astype(np.int64)
    g = g.sort_values("CODE").reset_index(drop=True)
    # statistical confidentiality: small group counts are blank (NaN) in the GUS file.  Residual = RES - known
    # groups; one blank group takes the residual exactly, several blanks split it in proportion to the national
    # group totals (of complete cells).
    cols = list(GROUPS.values())
    A = g[cols].to_numpy(np.float64)
    miss = np.isnan(A)
    g["age_imputed"] = miss.any(axis=1)
    full = ~miss.any(axis=1)
    nat = A[full].sum(axis=0) / A[full].sum()
    resid = np.maximum(g["RES"].to_numpy(np.float64) - np.nansum(A, axis=1), 0.0)
    wts = np.where(miss, nat[None, :], 0.0)
    ws = wts.sum(axis=1, keepdims=True)
    fill = np.where(ws > 0, resid[:, None] * wts / np.where(ws > 0, ws, 1), 0.0)
    A = np.where(miss, fill, A)
    for i, c in enumerate(cols):
        g[c] = A[:, i]
    e0, n0 = int(g.E.min()), int(g.N.min())
    w, h = (int(g.E.max()) - e0) // 1000 + 1, (int(g.N.max()) - n0) // 1000 + 1
    lut = np.full((h, w), -1, dtype=np.int32)
    lut[((g.N.values - n0) // 1000), ((g.E.values - e0) // 1000)] = np.arange(len(g), dtype=np.int32)
    return g, lut, e0, n0


def lookup(x3035, y3035, lut, e0, n0) -> np.ndarray:
    c = np.floor((x3035 - e0) / 1000).astype(np.int64)
    r = np.floor((y3035 - n0) / 1000).astype(np.int64)
    ok = (c >= 0) & (c < lut.shape[1]) & (r >= 0) & (r < lut.shape[0])
    out = np.full(len(c), -1, dtype=np.int32)
    out[ok] = lut[r[ok], c[ok]]
    return out


def build() -> None:
    t0 = time.time()
    cen, lut, e0, n0 = census()
    R = cen["RES"].to_numpy(np.float64)
    share = {k: np.where(R > 0, cen[v].to_numpy(np.float64) / np.where(R > 0, R, 1), np.nan) for k, v in GROUPS.items()}
    qa = {"census_cells": int(len(cen)), "census_RES": float(R.sum()),
          **{f"census_{k}": float(cen[v].sum()) for k, v in GROUPS.items()},
          "cells_with_blank_groups_imputed": int(cen["age_imputed"].sum()),
          "persons_in_imputed_cells": float(R[cen["age_imputed"].to_numpy()].sum()),
          "max_abs_groups_minus_RES_after_imputation": float(np.abs(cen[list(GROUPS.values())].sum(axis=1) - R).max())}
    imp = cen["age_imputed"].to_numpy()
    k = (np.arange(NSUB) + 0.5) / NSUB - 0.5
    du, dv = np.meshgrid(k, k)
    du, dv = du.ravel() * RES, dv.ravel() * RES
    rows = []
    for agg in AGGS:
        c = pd.read_parquet(INTERIM / "popgrid" / f"cells_{agg}.parquet",
                            columns=["cell_id", "x", "y", "pop_ghsl_census_scaled", "in_fua", "in_core"])
        X = c["x"].to_numpy()[:, None] + du[None, :]
        Y = c["y"].to_numpy()[:, None] + dv[None, :]
        xx, yy = T2180_TO_3035.transform(X.ravel(), Y.ravel())
        j = lookup(xx, yy, lut, e0, n0).reshape(len(c), NSUB * NSUB)
        valid = (j >= 0) & (R[np.where(j >= 0, j, 0)] > 0)
        nv = valid.sum(axis=1)
        xc, yc = T2180_TO_3035.transform(c["x"].to_numpy(), c["y"].to_numpy())
        jc = lookup(xc, yc, lut, e0, n0)
        okc = (jc >= 0) & (R[np.where(jc >= 0, jc, 0)] > 0)
        p = c["pop_ghsl_census_scaled"].to_numpy(np.float64)
        out = {"agglomeration": agg, "cell_id": c["cell_id"].to_numpy(), "pop": p,
               "census_code": np.where(okc, cen["CODE"].to_numpy()[np.where(jc >= 0, jc, 0)], None),
               "census_idx": np.where(okc, jc, -1), "n_valid_sub": nv.astype(np.int8),
               "imputed_sub_share": np.where(nv > 0, (valid & imp[np.where(j >= 0, j, 0)]).sum(axis=1)
                                             / np.maximum(nv, 1), np.nan)}
        for g, s in share.items():
            sv = np.where(valid, s[np.where(j >= 0, j, 0)], 0.0)
            sh = np.where(nv > 0, sv.sum(axis=1) / np.maximum(nv, 1), np.nan)
            out[f"share_{g}"] = sh
            out[f"pop_{g}"] = np.where(nv > 0, p * sh, np.nan)
            out[f"share_{g}_centroid"] = np.where(okc, s[np.where(jc >= 0, jc, 0)], np.nan)
        d = pd.DataFrame(out)
        d["in_fua"], d["in_core"] = c["in_fua"].to_numpy(), c["in_core"].to_numpy()
        rows.append(d)
        f = d[d["in_fua"]]
        qa[agg] = {"cells": int(len(d)), "cells_fua": int(len(f)), "pop_fua": float(f["pop"].sum()),
                   "pop_fua_null_age": float(f.loc[f["share_65"].isna(), "pop"].sum()),
                   "pop_fua_in_imputed_census_cells": float((f["pop"] * f["imputed_sub_share"].fillna(0)).sum()),
                   **{f"fua_{g}": float(f[f"pop_{g}"].sum()) for g in GROUPS},
                   **{f"fua_share_{g}": float(f[f"pop_{g}"].sum() / f.loc[f[f"pop_{g}"].notna(), "pop"].sum())
                      for g in GROUPS},
                   "core_share_65": float(d.loc[d.in_core, "pop_65"].sum() / d.loc[d.in_core & d["pop_65"].notna(), "pop"].sum()),
                   "core_share_0_14": float(d.loc[d.in_core, "pop_0_14"].sum() / d.loc[d.in_core & d["pop_0_14"].notna(), "pop"].sum())}
        # identity check: sum of the three groups equals pop wherever shares are defined
        ss = d[[f"pop_{g}" for g in GROUPS]].sum(axis=1, min_count=3)
        qa[agg]["max_abs_groups_minus_pop"] = float(np.nanmax(np.abs(ss - d["pop"]))) if ss.notna().any() else None
    a = pd.concat(rows, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    a.to_parquet(OUT / "age_cells.parquet", index=False)
    qa["runtime_s"] = round(time.time() - t0, 1)
    write_json(OUT / "age_qa.json", qa)
    print(json.dumps({k: v for k, v in qa.items() if not isinstance(v, dict)}, indent=1))


# ------------------------------------------------------------------ age metrics
def bounds(m: np.ndarray, p: np.ndarray, gcount_by_sq: pd.Series, sq: np.ndarray) -> tuple[float, float]:
    """Lowest / highest group mean of measure m if, inside every 1 km square, the group's count (fixed) were placed
    into the square's 250 m cells (capacity p) from the worst-served (low) or best-served (high) cell upward."""
    df = pd.DataFrame({"sq": sq, "m": m, "p": p})
    lo_num = hi_num = 0.0
    tot = 0.0
    for s, g in df.groupby("sq", sort=False):
        G = float(gcount_by_sq.get(s, 0.0))
        if G <= 0:
            continue
        tot += G
        for asc in (True, False):
            gg = g.sort_values("m", ascending=asc)
            cap = np.minimum(gg["p"].to_numpy(), np.maximum(G - np.r_[0, np.cumsum(gg["p"].to_numpy())[:-1]], 0))
            v = float((cap * gg["m"].to_numpy()).sum())
            if asc:
                lo_num += v
            else:
                hi_num += v
    return (lo_num / tot, hi_num / tot) if tot > 0 else (np.nan, np.nan)


def group_stats(m: np.ndarray, sel: np.ndarray, age: pd.DataFrame, acc=None, prox=None) -> dict:
    """All / 0-14 / 65+ weighted means of m (and ratio of means when acc / prox are given) over sel."""
    out = {}
    p = age["pop"].to_numpy(np.float64)
    ok = sel & np.isfinite(m) & (p > 0)
    for g in ("all", "0_14", "65"):
        if g == "all":
            w, wc = p, p
        else:
            w = age[f"pop_{g}"].to_numpy(np.float64)
            wc = p * age[f"share_{g}_centroid"].to_numpy(np.float64)
        okg = ok & np.isfinite(w)
        okc = ok & np.isfinite(wc)
        r = {"value": float((m[okg] * w[okg]).sum() / w[okg].sum()) if w[okg].sum() > 0 else None,
             "value_centroid": float((m[okc] * wc[okc]).sum() / wc[okc].sum()) if wc[okc].sum() > 0 else None,
             "persons": float(w[okg].sum())}
        if acc is not None:
            o2 = okg & np.isfinite(acc)
            r["ratio_of_means"] = float(100 * (acc[o2] * w[o2]).sum() / (prox[o2] * w[o2]).sum())
            o3 = okc & np.isfinite(acc)
            r["ratio_of_means_centroid"] = float(100 * (acc[o3] * wc[o3]).sum() / (prox[o3] * wc[o3]).sum())
        if g != "all":
            sq = age["census_idx"].to_numpy()
            okb = ok & (sq >= 0) & np.isfinite(w)
            gcnt = pd.Series(w[okb]).groupby(sq[okb]).sum()
            r["bound_low"], r["bound_high"] = bounds(m[okb], p[okb], gcnt, sq[okb])
        out[g] = r
    return out


def tables() -> pd.DataFrame:
    """Per agglomeration x domain (core, covered): frequent service shares (<= 10 and <= 20 min, the headline
    definition of phase 2) and transit performance at 30 min (Wednesday 7-9, all feeds) by age group."""
    import pickle
    from pipeline import access_aggregate as AA
    age = pd.read_parquet(OUT / "age_cells.parquet")
    with open(INTERIM / "frequent" / "results.pkl", "rb") as f:
        fres = {r["agg"]: r for r in pickle.load(f)}
    rows = []
    for agg in AGGS:
        a = age[age["agglomeration"] == agg].set_index("cell_id")
        # phase 2: cells of the frequent step (populated FUA cells), fraction of the 9 sample points within 500 m
        fr = fres[agg]
        fc = fr["cells"]
        af = a.reindex(fc["cell_id"]).reset_index()
        assert np.allclose(af["pop"].to_numpy(), fc["pop_ghsl_census_scaled"].to_numpy(), equal_nan=True)
        for T in (10, 20):
            m = 100.0 * fr["frac"][("all", "seg", T, "net")]
            for dom, sel in (("core", fc["in_core"].to_numpy()), ("covered", fc["in_mask_all"].to_numpy())):
                # the phase-2 core share is over all core cells (cells outside the mask count as not served)
                st = group_stats(m.astype(np.float64), sel, af)
                for g, r in st.items():
                    rows.append({"agglomeration": agg, "domain": dom, "measure": f"freq_le{T}min", "group": g, **r})
        # phase 3: transit performance 30 min, Wednesday 7-9, all feeds, census grid
        b = AA.base_frame(agg)
        u = AA.load_unit(agg, "all", "pt_am")
        perf, acc, prox = AA.perf_cells(b, u, "transit", "census", 30)
        ab = a.reindex(b["cell_id"]).reset_index()
        assert np.allclose(ab["pop"].to_numpy(), b["w_census"].to_numpy(), equal_nan=True)
        for dom, sel in (("core", b["in_core"].to_numpy()), ("covered", b["in_mask_all"].to_numpy())):
            st = group_stats(perf, sel, ab, acc=acc, prox=prox)
            for g, r in st.items():
                rows.append({"agglomeration": agg, "domain": dom, "measure": "tp_pt_am_30min", "group": g, **r})
        print(agg, flush=True)
    t = pd.DataFrame(rows)
    t.to_parquet(OUT / "age_metrics.parquet", index=False)
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "tables"])
    a = ap.parse_args()
    build() if a.cmd == "build" else tables()


if __name__ == "__main__":
    main()
