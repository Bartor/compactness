"""Supply (brief 4.7): vehicle-kilometres per mode, hour and inhabitant, anomaly test, and the orchestration of
the whole transit QA step (tram speed, top-10 stops, ``supply.md``, ``metrics_supply``).

Run:  python -m pipeline.supply            (builds everything; needs ``python -m pipeline.gtfs_service`` caches or
                                            builds them itself)

Outputs
* results/metrics/metrics_supply.csv + .json         long format, columns of metrics.csv + feed_variant
* results/charts/supply_vkm.json, tram_speed.json
* results/qa/transit/*  (CSV, PNG, supply.md in Polish)
Seat-kilometres are not computed: GTFS carries no vehicle type and no capacity source was available
(see supply.md, section "Miejscokilometry").
"""
from __future__ import annotations

import shutil
import time
import warnings
from pathlib import Path
from functools import lru_cache

import matplotlib
import numpy as np
import pandas as pd

from pipeline import gtfs_service as gs
from pipeline.boundaries import load_agglomeration
from pipeline.common import RESULTS, load_config, round_sig, sig, write_json, write_meta
from pipeline.gtfs_inventory import in_excluded_period, is_holiday

matplotlib.use("Agg")
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt  # noqa: E402

QA = RESULTS / "qa" / "transit"
CHARTS = RESULTS / "charts"
METRICS = RESULTS / "metrics"
PHASE1 = gs.PHASE1
VARIANTS = gs.VARIANTS
MODES = ["tram", "metro", "rail", "bus", "trolleybus", "ferry", "other"]
MODE_PL = {"tram": "tramwaj", "metro": "metro", "rail": "kolej", "bus": "autobus", "trolleybus": "trolejbus",
           "ferry": "prom", "other": "inne", "total": "razem", "bus_replacement": "autobus zastępczy (kolej)"}
AGG_PL = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
          "trojmiasto": "Trójmiasto", "gzm": "GZM"}
DOMAIN_PL = {"fua": "FUA", "core": "rdzeń"}
POP_DATE = "2021-03-31"
SUPPLY_VERSION = "2026-11-24.1"
COVER_CSV = RESULTS / "qa" / "phase0" / "coverage" / "population_coverage_preliminary.csv"
COVER_SUM = RESULTS / "qa" / "phase0" / "coverage" / "coverage_summary.csv"
INCOMPLETE = "niepełne pokrycie GTFS"
TOL = 0.05   # brief 5: anomaly threshold

PALETTE = {"tram": "#c0392b", "metro": "#8e44ad", "rail": "#2c3e50", "bus": "#2980b9", "trolleybus": "#16a085",
           "ferry": "#7f8c8d", "other": "#bdc3c7"}


# ------------------------------------------------------------------ population and coverage
@lru_cache(maxsize=None)
def population(agg: str) -> dict:
    from pipeline.phase0_boundaries import nsp_sum
    a = load_agglomeration(agg)
    return {"fua": int(nsp_sum(a["fua"])), "core": int(nsp_sum(a["core"]))}


@lru_cache(maxsize=1)
def _coverage() -> tuple[pd.DataFrame, pd.DataFrame]:
    c = pd.read_csv(COVER_CSV).set_index("agg")
    s = pd.read_csv(COVER_SUM)
    s = s[(s["mode"] == "all") & (s["recommended"])].set_index("agg")
    return c, s


def coverage_for(agg: str, variant: str, domain: str) -> tuple[float | None, str]:
    """(coverage_share or None, flag text).  FUA: share of NSP-2021 population living in gminas whose stop
    coverage is >= 85 % (85 % threshold column of the phase-0 table, all 42 feeds).  Core: share of OSM stops
    with a GTFS counterpart (stop based, not population based).  The official variant has its own coverage
    only where it uses the same feeds as ``all`` (Poznań, GZM, Trójmiasto)."""
    c, s = _coverage()
    same = set(gs.feeds_for(agg, "official")) == set(gs.feeds_for(agg, "all"))
    if domain == "core":
        v = float(s.loc[agg, "cov_core"]) if agg in s.index else None
        return v, ("" if v is not None and v >= 0.85 else INCOMPLETE)
    if variant == "official" and not same:
        return None, f"{INCOMPLETE} (wariant official: pokrycia nie liczono, nie wyższe niż dla wariantu all)"
    v = float(c.loc[agg, "gmina_pop_share_cov_ge_85"]) if agg in c.index else None
    return v, ("" if v is not None and v >= 0.85 else INCOMPLETE)


# ------------------------------------------------------------------ vehicle-km tables
def _vkm_tables(agg: str, variant: str, day: str) -> dict[str, pd.DataFrame]:
    """Cached hourly / by-feed vehicle-km tables for one (agglomeration, variant, day)."""
    sigs = f"{SUPPLY_VERSION}-{gs._build_sig(agg, variant)}"
    base = gs.CACHE / f"supply_{agg}_{day}_{variant}"
    sf = base.with_suffix(".sig")
    names = (".hourly.parquet", ".byfeed.parquet", ".diag.parquet")
    if sf.exists() and sf.read_text() == sigs and all(Path(str(base) + n).exists() for n in names):
        return {k: pd.read_parquet(f"{base}.{k}.parquet") for k in ("hourly", "byfeed", "diag")}
    from pipeline.supply_core import segments
    seg = segments(agg, day, variant)
    seg["mode"] = seg["route_class"]
    hourly, byfeed = [], []
    for dom in ("fua", "core"):
        col = f"km_{dom}"
        h = seg.groupby(["mode", "hour"])[col].sum().reset_index().rename(columns={col: "vkm"})
        h["domain"] = dom
        r = seg[seg["mode"].eq("bus") & seg["is_replacement_bus"].astype(bool)].groupby("hour")[col].sum().reset_index()
        r = r.rename(columns={col: "vkm"}).assign(mode="bus_replacement", domain=dom)
        hourly += [h, r]
        f = seg.groupby(["feed", "mode"])[col].sum().reset_index().rename(columns={col: "vkm"})
        f["domain"] = dom
        fr = seg[seg["mode"].eq("bus") & seg["is_replacement_bus"].astype(bool)].groupby("feed")[col].sum().reset_index()
        byfeed += [f, fr.rename(columns={col: "vkm"}).assign(mode="bus_replacement", domain=dom)]
    hourly = pd.concat(hourly, ignore_index=True)
    byfeed = pd.concat(byfeed, ignore_index=True)
    diag = pd.DataFrame([{
        "n_segments": len(seg), "n_seg_nocoord": int(seg["nocoord"].sum()),
        "n_trips_shape_ratio_bad": int(seg.drop_duplicates("uid")["shape_ratio_bad"].astype(bool).sum()),
        "km_scaled_by_shape": float(seg.loc[seg["scale_method"] == "shape", "km"].sum()),
        "km_scaled_by_stops": float(seg.loc[seg["scale_method"] == "stops", "km"].sum()),
        "km_boundary_fua": float(seg.loc[seg["boundary_fua"], "km_fua"].sum()),
        "km_total_all_trips": float(seg["km"].sum()),
    }])
    gs.CACHE.mkdir(parents=True, exist_ok=True)
    hourly.to_parquet(f"{base}.hourly.parquet")
    byfeed.to_parquet(f"{base}.byfeed.parquet")
    diag.to_parquet(f"{base}.diag.parquet")
    sf.write_text(sigs)
    return {"hourly": hourly, "byfeed": byfeed, "diag": diag}


def compute_vkm(days: dict[str, str]) -> dict[str, pd.DataFrame]:
    hourly, byfeed, diag = [], [], []
    for agg in PHASE1:
        for variant in VARIANTS:
            for dname, day in days.items():
                t = _vkm_tables(agg, variant, day)
                key = {"agglomeration": agg, "variant": variant, "day_type": dname, "day": day}
                hourly.append(t["hourly"].assign(**key))
                byfeed.append(t["byfeed"].assign(**key))
                diag.append(t["diag"].assign(**key))
                print(f"  vkm {agg:11s} {variant:8s} {day}", flush=True)
    hourly = pd.concat(hourly, ignore_index=True)
    byfeed = pd.concat(byfeed, ignore_index=True)
    diag = pd.concat(diag, ignore_index=True)
    order = ["agglomeration", "variant", "day_type", "day", "domain", "mode"]
    hourly = hourly.sort_values(order + ["hour"], kind="stable").reset_index(drop=True)
    byfeed = byfeed.sort_values(order[:4] + ["domain", "feed", "mode"], kind="stable").reset_index(drop=True)
    return {"hourly": hourly, "byfeed": byfeed, "diag": diag}


def summarise(hourly: pd.DataFrame) -> pd.DataFrame:
    """Per (agglomeration, variant, day_type, domain, mode) day totals with population and per-capita values."""
    s = hourly.groupby(["agglomeration", "variant", "day_type", "day", "domain", "mode"])["vkm"].sum().reset_index()
    # total = all modes (bus_replacement is a subset of bus and is not added again)
    tot = s[s["mode"] != "bus_replacement"].groupby(["agglomeration", "variant", "day_type", "day", "domain"])["vkm"].sum().reset_index()
    s = pd.concat([s, tot.assign(mode="total")], ignore_index=True)
    # fill modes with no service: 0 km is a real value there (feeds exist), keep only modes present
    s["population"] = [population(a)[d] for a, d in zip(s["agglomeration"], s["domain"])]
    s["vkm_per_inhabitant"] = s["vkm"] / s["population"]
    cov = [coverage_for(a, v, d) for a, v, d in zip(s["agglomeration"], s["variant"], s["domain"])]
    s["coverage_share"] = [c[0] for c in cov]
    s["flag"] = [c[1] for c in cov]
    mord = {m: i for i, m in enumerate(MODES + ["bus_replacement", "total"])}
    s["_o"] = s["mode"].map(mord)
    s = s.sort_values(["agglomeration", "variant", "day_type", "domain", "_o"], kind="stable").drop(columns="_o")
    return s.reset_index(drop=True)


# ------------------------------------------------------------------ anomaly test
def anomaly_test(days: dict[str, str]) -> pd.DataFrame:
    rows = []
    cfg = load_config()
    for agg in PHASE1:
        for fid in gs.feeds_for(agg, "all"):
            ds = gs.daily_series(agg, fid)
            ds = ds[ds["trips"] > 0].copy()
            ds["date"] = pd.to_datetime(ds["date"])
            if ds.empty:
                continue
            for dname, day in days.items():
                d = pd.Timestamp(day)
                want = [0, 1, 2, 3, 4] if dname == "weekday" else [5]
                pool = ds[ds["date"].dt.weekday.isin(want)]
                pool = pool[~pool["date"].map(lambda x: is_holiday(x) or in_excluded_period(x))]
                ref = ds[ds["date"] == d]
                med = float(pool["vehicle_km"].median()) if len(pool) else float("nan")
                v = float(ref["vehicle_km"].iloc[0]) if len(ref) else float("nan")
                dev = (v / med - 1) if (med and np.isfinite(med) and np.isfinite(v)) else float("nan")
                rows.append({"agglomeration": agg, "feed": fid, "day_type": dname, "day": day,
                             "variants": "official+all" if fid in set(cfg["official_feeds"]) else "all",
                             "vkm_day": v, "vkm_median": med, "n_days_median": len(pool),
                             "validity_first": ds["date"].min().date().isoformat(),
                             "validity_last": ds["date"].max().date().isoformat(),
                             "deviation_pct": 100 * dev, "flag_gt5pct": bool(abs(dev) > TOL) if np.isfinite(dev) else None})
    out = pd.DataFrame(rows).sort_values(["day_type", "agglomeration", "feed"], kind="stable").reset_index(drop=True)
    return out


# ------------------------------------------------------------------ plots
def plot_hourly(hourly: pd.DataFrame) -> list[str]:
    files = []
    for agg in PHASE1:
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharex=True)
        for ax, dom in zip(axes, ("fua", "core")):
            h = hourly[(hourly.agglomeration == agg) & (hourly.day_type == "weekday") & (hourly.domain == dom)]
            ha = h[h.variant == "all"]
            bottom = np.zeros(30)
            for m in MODES:
                v = ha[ha["mode"] == m].set_index("hour")["vkm"].reindex(range(30)).fillna(0).to_numpy()
                if v.sum() == 0:
                    continue
                ax.bar(range(30), v / 1000, bottom=bottom, color=PALETTE[m], label=MODE_PL[m], width=0.85)
                bottom += v / 1000
            ho = h[(h.variant == "official") & (h["mode"] != "bus_replacement")].groupby("hour")["vkm"].sum().reindex(range(30)).fillna(0)
            ax.plot(range(30), ho.to_numpy() / 1000, color="k", lw=1.2, ls="--", label="razem, wariant official")
            ax.set_title(f"{AGG_PL[agg]}, {DOMAIN_PL[dom]}: wozokilometry wg godziny (śr. 2026-11-25, wariant all)", fontsize=9)
            ax.set_xlabel("godzina odjazdu z pierwszego przystanku odcinka (24-29 = po północy)")
            ax.set_ylabel("tys. wozkm")
            ax.set_xticks(range(0, 30, 2))
        axes[0].legend(fontsize=7)
        fig.tight_layout()
        p = QA / f"vkm_hourly_{agg}.png"
        fig.savefig(p, dpi=110)
        plt.close(fig)
        files.append(p.name)
    return files


def plot_per_capita(summ: pd.DataFrame) -> None:
    s = summ[(summ.day_type == "weekday") & (summ["mode"].isin(MODES))]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    for ax, dom in zip(axes, ("fua", "core")):
        for j, variant in enumerate(VARIANTS):
            x = np.arange(len(PHASE1)) + (j - 0.5) * 0.38
            bottom = np.zeros(len(PHASE1))
            for m in MODES:
                v = np.array([s[(s.agglomeration == a) & (s.variant == variant) & (s.domain == dom) & (s["mode"] == m)]["vkm_per_inhabitant"].sum()
                              for a in PHASE1])
                ax.bar(x, v, bottom=bottom, width=0.36, color=PALETTE[m], label=MODE_PL[m] if j == 0 else None,
                       alpha=1.0 if variant == "all" else 0.55, edgecolor="white", linewidth=0.3)
                bottom += v
        ax.set_xticks(range(len(PHASE1)), [AGG_PL[a] for a in PHASE1])
        ax.set_title(f"{DOMAIN_PL[dom]}: wozkm/mieszk./dobę (lewy słupek official, prawy all)", fontsize=9)
    axes[0].legend(fontsize=7)
    axes[0].set_ylabel("wozkm na mieszkańca (NSP 2021)")
    fig.tight_layout()
    fig.savefig(QA / "vkm_per_inhabitant.png", dpi=110)
    plt.close(fig)


# ------------------------------------------------------------------ metrics rows
SRC = "GTFS (warstwa gtfs_service), kursy po deduplikacji, odcinki przycięte do obszaru"
GRID_POP = "siatka spisowa 1 km (EU LAEA)"


def vkm_metric_rows(summ: pd.DataFrame) -> list[dict]:
    rows = []
    for r in summ.itertuples(index=False):
        mpl = MODE_PL[r.mode]
        sat = r.day_type == "saturday"
        daylab = "sobota 2026-11-28" if sat else "śr. 2026-11-25"
        pre = "sat" if sat else "day"
        base = {"agglomeration": r.agglomeration, "domain": r.domain, "grid": "", "source": SRC,
                "timetable_date": r.day, "coverage_share": r.coverage_share, "flag": r.flag,
                "tier": "table", "feed_variant": r.variant}
        sub = " (podzbiór autobusów)" if r.mode == "bus_replacement" else ""
        rows.append({**base, "metric": f"vkm_{pre}_{r.mode}", "label": f"Wozokilometry w dobie ({daylab}): {mpl}{sub}",
                     "value": r.vkm, "unit": "wozkm/dobę", "population_date": ""})
        rows.append({**base, "metric": f"vkm_per_cap_{pre}_{r.mode}",
                     "label": f"Wozokilometry na mieszkańca w dobie ({daylab}): {mpl}{sub}",
                     "value": r.vkm_per_inhabitant, "unit": "wozkm/mieszk./dobę", "grid": GRID_POP,
                     "population_date": POP_DATE,
                     "source": SRC + "; ludność: GUS NSP 2021 (siatka 1 km)"})
    return rows


# ------------------------------------------------------------------ main
def main() -> None:
    t0 = time.time()
    cfg = load_config()
    days = {"weekday": cfg["reference_day"], "saturday": cfg["reference_saturday"]}
    QA.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)
    # 1. service layer (cached)
    gs.main()
    # 2. vehicle-km
    print("vehicle-km", flush=True)
    v = compute_vkm(days)
    summ = summarise(v["hourly"])
    v["hourly"].assign(vkm=lambda d: d["vkm"].round(1)).to_csv(QA / "supply_vkm_hourly.csv", index=False, lineterminator="\n")
    v["byfeed"].assign(vkm=lambda d: d["vkm"].round(1)).to_csv(QA / "supply_vkm_by_feed.csv", index=False, lineterminator="\n")
    s_out = summ.copy()
    for c in ("vkm", "vkm_per_inhabitant"):
        s_out[c] = s_out[c].map(sig)
    s_out.to_csv(QA / "supply_vkm_summary.csv", index=False, lineterminator="\n")
    d_out = v["diag"].copy()
    for c in d_out.columns:
        if d_out[c].dtype.kind == "f":
            d_out[c] = d_out[c].map(sig)
    d_out.to_csv(QA / "supply_vkm_diagnostics.csv", index=False, lineterminator="\n")
    plot_hourly(v["hourly"])
    plot_per_capita(summ)
    # 3. anomaly test
    print("anomaly test", flush=True)
    an = anomaly_test(days)
    an_out = an.copy()
    for c in ("vkm_day", "vkm_median", "deviation_pct"):
        an_out[c] = an_out[c].map(sig)
    an_out.to_csv(QA / "anomaly_test_dedup.csv", index=False, lineterminator="\n")
    # 4. tram speed and top stops
    from pipeline import tram_speed, top_stops
    print("tram speed", flush=True)
    tram = tram_speed.run(days, QA, CHARTS)
    print("top stops", flush=True)
    top = top_stops.run(cfg["reference_day"], QA)
    # 5. metrics
    rows = vkm_metric_rows(summ)
    for agg in PHASE1:
        for variant in VARIANTS:
            a = an[(an.agglomeration == agg) & (an.day_type == "weekday")]
            if variant == "official":
                a = a[a["variants"] == "official+all"]
            if len(a):
                rows.append({"agglomeration": agg, "domain": "fua", "metric": "anomaly_max_abs_dev_pct",
                             "label": "Test anomalii (§5): największe odchylenie wozkm dnia ref. od mediany dni roboczych, feedy bez kopii",
                             "value": float(a["deviation_pct"].abs().max()), "unit": "%", "grid": "", "source": "GTFS, po deduplikacji",
                             "population_date": "", "timetable_date": days["weekday"], "coverage_share": None,
                             "flag": "" if (a["deviation_pct"].abs().max() <= 5) else "odchylenie > 5 %: patrz supply.md",
                             "tier": "qa", "feed_variant": variant})
    rows += tram["metrics"] + top["metrics"]
    df = pd.DataFrame(rows)
    cols = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
            "timetable_date", "coverage_share", "flag", "tier", "feed_variant"]
    df = df[cols].sort_values(["agglomeration", "feed_variant", "domain", "metric"], kind="stable").reset_index(drop=True)
    out = df.copy()
    out["value"] = out["value"].map(sig)
    out["coverage_share"] = out["coverage_share"].map(lambda x: sig(x, 4) if pd.notna(x) else None)
    out.to_csv(METRICS / "metrics_supply.csv", index=False, lineterminator="\n")
    recs = [{k: (None if (isinstance(x, float) and np.isnan(x)) or x == "" else x) for k, x in r.items()}
            for r in out.to_dict("records")]
    write_json(METRICS / "metrics_supply.json", recs)
    # 6. chart json
    write_json(CHARTS / "supply_vkm.json", chart_json(summ, v["hourly"], days))
    # 7. report
    from pipeline.supply_report import write_report
    write_report(summ=summ, hourly=v["hourly"], diag=v["diag"], anomaly=an, tram=tram, top=top, days=days)
    inputs = sorted({f"gtfs_{f}" for a in PHASE1 for f in gs.feeds_for(a, "all")})
    extra = {"rules_version": gs.RULES_VERSION, "supply_version": SUPPLY_VERSION, "population_date": POP_DATE,
             "timetable_dates": days, "variants": list(VARIANTS)}
    mp = write_meta(QA, "supply", inputs=inputs, started=t0, extra=extra)
    # charts/ and metrics/ already hold the phase-1 _meta.json: keep the per-step copies under another name
    for d in (CHARTS, METRICS):
        shutil.copyfile(mp, d / "_meta_supply.json")
    print(f"done in {time.time() - t0:.0f}s")


def chart_json(summ: pd.DataFrame, hourly: pd.DataFrame, days: dict) -> dict:
    ser = {}
    for (agg, variant, dom), g in hourly[hourly.day_type == "weekday"].groupby(["agglomeration", "variant", "domain"]):
        d = {}
        for m, gg in g.groupby("mode"):
            d[m] = [round_sig(float(x)) for x in gg.set_index("hour")["vkm"].reindex(range(30)).fillna(0).to_numpy()]
        ser.setdefault(agg, {}).setdefault(variant, {})[dom] = d
    s = summ[summ.day_type == "weekday"]
    per = {}
    for r in s.itertuples(index=False):
        per.setdefault(r.agglomeration, {}).setdefault(r.variant, {}).setdefault(r.domain, {})[r.mode] = {
            "vkm": round_sig(float(r.vkm)), "per_inhabitant": round_sig(float(r.vkm_per_inhabitant)),
            "coverage_share": round_sig(r.coverage_share) if pd.notna(r.coverage_share) else None, "flag": r.flag or None}
    return {
        "title": "Wozokilometry w dobie referencyjnej: tryb, godzina, mieszkaniec",
        "unit": {"vkm": "wozkm/dobę", "per_inhabitant": "wozkm/mieszk./dobę", "hourly": "wozkm w godzinie (godz. 24-29 = po północy)"},
        "timetable_date": days["weekday"], "saturday_date": days["saturday"], "population_date": POP_DATE,
        "population_source": "GUS NSP 2021, siatka 1 km (ludność rezydująca), środek komórki w obszarze",
        "variants": {"official": "feedy z briefu i dodatki od wydawcy", "all": "official + 28 nieoficjalnych przepakowań"},
        "domains": {"fua": "FUA + (Trójmiasto, GZM: suma FUA wg konfiguracji)", "core": "rdzeń (miasta URAU)"},
        "caveats": [
            "Odcinki między przystankami przycięte do obszaru: cały odcinek, gdy oba przystanki są w obszarze; odcinek z jednym końcem w obszarze liczony proporcjonalnie do długości linii prostej w obszarze.",
            "Wozokilometry z długości kształtu trasy (shapes), a gdy go brak lub jest niewiarygodny, z odległości między przystankami.",
            "Dla FUA Warszawy, Krakowa, Wrocławia, Łodzi i Trójmiasta pokrycie GTFS jest poniżej 85 % ludności: wyniki niepełne (flaga w polu coverage).",
            "Kolej: ogólnopolski feed przycięty do kursów z przystankiem w FUA + 15 km; autobusy zastępcze kolei liczone jako autobus i osobno jako podzbiór.",
            "Miejscokilometry nie są liczone (brak źródła pojemności)."],
        "per_agglomeration": per, "hourly": ser,
    }


if __name__ == "__main__":
    main()
