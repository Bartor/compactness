"""Phase 0 GTFS inventory (brief §3, §4.5, §4.7, §5, §6).

    python -m pipeline.gtfs_inventory inventory   # feeds_inventory.csv/.md
    python -m pipeline.gtfs_inventory service     # service_by_day.csv
    python -m pipeline.gtfs_inventory reference   # reference_day.md (+ anomaly test)
    python -m pipeline.gtfs_inventory rail        # rail_overlap.md
    python -m pipeline.gtfs_inventory topstops    # top_stops_preview.csv
    python -m pipeline.gtfs_inventory all

Outputs go to results/qa/phase0/gtfs/.  Table and report text is Polish, code and comments English.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import common
from pipeline.common import RESULTS, load_config, read_manifest, write_meta
from pipeline.fetch_gtfs import manifest_id
from pipeline.gtfs_io import Feed, route_class, service_dates, stop_events, trip_stats, frequency_runs

OUT = RESULTS / "qa" / "phase0" / "gtfs"
CLASSES = ["tram", "metro", "rail", "bus", "trolleybus", "ferry", "other"]
WD_PL = ["pon", "wt", "śr", "czw", "pt", "sob", "niedz"]


def feed_ids() -> list[str]:
    return list(load_config()["feeds"])


def _pct(x: float) -> float:
    return round(100 * float(x), 1)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.4g")


def _fmt_date(s) -> str:
    return "" if s is None or (isinstance(s, float) and np.isnan(s)) else pd.Timestamp(s).strftime("%Y-%m-%d")


# ------------------------------------------------------------------ inventory
def inventory_row(fid: str, cfg: dict, mf: dict) -> dict:
    feed = Feed(fid)
    m = mf.get(manifest_id(fid), {})
    row: dict = {"feed": fid, "agglomerations": ";".join(cfg.get("agglomerations", [])),
                 "publisher": cfg.get("publisher", ""), "license": cfg.get("license", ""),
                 "url": cfg.get("url", ""), "downloaded_at": m.get("downloaded_at", ""),
                 "sha256": m.get("sha256", ""), "zip_mb": round(feed.path.stat().st_size / 1e6, 1)}
    fi = feed.table("feed_info.txt")
    f0 = fi.iloc[0] if fi is not None and len(fi) else {}
    row["feed_publisher_name"] = f0.get("feed_publisher_name", "") if len(f0) else ""
    row["feed_version"] = f0.get("feed_version", "") if len(f0) else ""
    row["feed_info_start"] = f0.get("feed_start_date", "") if len(f0) else ""
    row["feed_info_end"] = f0.get("feed_end_date", "") if len(f0) else ""
    ts = trip_stats(feed)
    sd = service_dates(feed)
    per_service = ts.groupby("service_id")["runs"].sum()
    orphan = sd[~sd["service_id"].isin(per_service.index)]
    row["service_ids_without_trips"] = int(orphan["service_id"].nunique())
    row["dates_with_orphan_service_only"] = int(len(set(orphan["date"]) - set(sd[sd["service_id"].isin(per_service.index)]["date"])))
    row["orphan_dates_list"] = ",".join(sorted(f"{d:%m-%d}" for d in set(orphan["date"]) - set(sd[sd["service_id"].isin(per_service.index)]["date"])))[:200]
    sd = sd[sd["service_id"].isin(per_service.index)]
    days = sd["date"].drop_duplicates().sort_values()
    row["first_service_date"] = _fmt_date(days.min()) if len(days) else ""
    row["last_service_date"] = _fmt_date(days.max()) if len(days) else ""
    row["n_service_days"] = int(len(days))
    row["calendar_span_days"] = int((days.max() - days.min()).days + 1) if len(days) else 0
    ag = feed.table("agency.txt")
    row["n_agencies"] = 0 if ag is None else len(ag)
    row["agencies"] = "" if ag is None else "; ".join(sorted(ag["agency_name"].dropna().astype(str)))[:300]
    row["timezone"] = "" if ag is None or "agency_timezone" not in ag else ";".join(sorted(ag["agency_timezone"].dropna().unique()))
    rt = feed.table("routes.txt", ["route_id", "route_type"])
    rt["cls"] = rt["route_type"].map(route_class)
    row["routes_total"] = len(rt)
    for c in CLASSES:
        row[f"routes_{c}"] = int((rt["cls"] == c).sum())
    row["route_types_raw"] = ";".join(f"{k}:{v}" for k, v in rt["route_type"].value_counts().sort_index().items())
    stops = feed.table("stops.txt", ["stop_id", "location_type", "parent_station"])
    lt = stops["location_type"].fillna("0") if "location_type" in stops else pd.Series("0", index=stops.index)
    row["stops_total"] = len(stops)
    row["stops_stop_points"] = int((lt == "0").sum())
    row["stops_stations"] = int((lt == "1").sum())
    pp = stops["parent_station"] if "parent_station" in stops else pd.Series(dtype=str)
    sp = (lt == "0")
    row["parent_station_pct"] = _pct(pp[sp].notna().mean()) if len(pp) and sp.any() else 0.0
    row["trips"] = len(ts)
    row["trips_incl_frequencies"] = int(ts["runs"].sum())
    row["exact_duplicate_trips"] = int(ts["is_dup"].sum())
    row["exact_duplicate_trips_pct"] = round(100 * float(ts["is_dup"].mean()), 2) if len(ts) else 0.0
    row["trips_with_shape_pct"] = _pct((ts["dist_method"] == "shape").mean()) if len(ts) else 0.0
    row["shapes_txt"] = feed.has("shapes.txt")
    sdt = None
    if feed.has("shapes.txt"):
        sh = feed.table("shapes.txt", ["shape_dist_traveled"])
        sdt = _pct(sh["shape_dist_traveled"].notna().mean()) if len(sh) and "shape_dist_traveled" in sh else 0.0
    row["shape_dist_in_shapes_pct"] = sdt if sdt is not None else ""
    st = feed.table("stop_times.txt", ["shape_dist_traveled", "arrival_time", "departure_time"])
    row["stop_times_rows"] = len(st)
    row["shape_dist_in_stop_times_pct"] = _pct(st["shape_dist_traveled"].notna().mean()) if "shape_dist_traveled" in st and len(st) else 0.0
    row["stop_times_empty_time_pct"] = _pct(st["departure_time"].isna().mean()) if len(st) else 0.0
    row["frequencies_txt"] = feed.has("frequencies.txt")
    fr = frequency_runs(feed)
    row["frequency_trips"] = int(fr["trip_id"].nunique())
    row["direction_id_pct"] = _pct(ts["direction_id"].notna().mean()) if len(ts) else 0.0
    row["block_id_pct"] = _pct(ts["block_id"].notna().mean()) if len(ts) else 0.0
    row["calendar_txt"] = feed.has("calendar.txt")
    row["calendar_dates_txt"] = feed.has("calendar_dates.txt")
    known = {"agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "calendar.txt", "calendar_dates.txt",
             "shapes.txt", "frequencies.txt", "feed_info.txt", "transfers.txt", "fare_attributes.txt", "fare_rules.txt",
             "attributions.txt", "levels.txt", "pathways.txt"}
    row["extra_files"] = ";".join(sorted(n for n in feed._names if n not in known))
    m_dist = ts.loc[ts["dist_method"] == "shape"]
    if len(m_dist) and (m_dist["dist_stops_m"] > 0).any():
        ok = m_dist[m_dist["dist_stops_m"] > 0]
        row["shape_over_stops_ratio_median"] = round(float((ok["shape_len_m"] / ok["dist_stops_m"]).median()), 3)
    else:
        row["shape_over_stops_ratio_median"] = ""
    return row


def run_inventory() -> pd.DataFrame:
    cfg = load_config()["feeds"]
    mf = {r["id"]: r for r in read_manifest()}
    rows = []
    for fid in feed_ids():
        t = time.time()
        rows.append(inventory_row(fid, cfg[fid], mf))
        print("inventory", fid, round(time.time() - t, 1), "s", flush=True)
    df = pd.DataFrame(rows).sort_values("feed").reset_index(drop=True)
    _write_csv(df, OUT / "feeds_inventory.csv")
    return df


def _yn(x) -> str:
    return "tak" if x in (True, "True", "true") else "nie"


def write_inventory_md(df: pd.DataFrame) -> None:
    L = ["# Inwentaryzacja feedów GTFS (faza 0)", "",
         f"Stan na {dt.date.today().isoformat()}; pliki pobrane dziś, hasze w `data/manifest.csv`. "
         "Ważność liczona z `calendar.txt` + `calendar_dates.txt` (dni, w których jest co najmniej jeden kurs), "
         "a nie z `feed_info.txt`. Pełne dane: `feeds_inventory.csv`.", "",
         "## Ważność i skala", "",
         "| Feed | Wydawca | feed_info (od–do) | Pierwszy–ostatni dzień kursowania | Dni | Agencje | Trasy | Przystanki | Kursy |",
         "|---|---|---|---|---:|---:|---:|---:|---:|"]
    for r in df.itertuples():
        fi = f"{r.feed_info_start}–{r.feed_info_end}" if r.feed_info_start or r.feed_info_end else "brak"
        L.append(f"| `{r.feed}` | {r.publisher} | {fi} | {r.first_service_date} – {r.last_service_date} | {r.n_service_days} | "
                 f"{r.n_agencies} | {r.routes_total} | {r.stops_total} | {r.trips} |")
    L += ["", "## Trasy wg rodzaju (route_type rozszerzone sprowadzone do klas)", "",
          "| Feed | tramwaj | metro | kolej | autobus | trolejbus | prom | inne | surowe route_type |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in df.itertuples():
        L.append(f"| `{r.feed}` | {r.routes_tram} | {r.routes_metro} | {r.routes_rail} | {r.routes_bus} | {r.routes_trolleybus} | "
                 f"{r.routes_ferry} | {r.routes_other} | {r.route_types_raw} |")
    L += ["", "## Kompletność pól", "",
          "| Feed | shapes.txt | kursy z kształtem % | shape_dist w shapes % | shape_dist w stop_times % | frequencies | parent_station % | direction_id % | block_id % | strefa czasowa |",
          "|---|---|---:|---:|---:|---|---:|---:|---:|---|"]
    for r in df.itertuples():
        L.append(f"| `{r.feed}` | {_yn(r.shapes_txt)} | {r.trips_with_shape_pct} | {r.shape_dist_in_shapes_pct} | "
                 f"{r.shape_dist_in_stop_times_pct} | {_yn(r.frequencies_txt)} ({r.frequency_trips}) | {r.parent_station_pct} | "
                 f"{r.direction_id_pct} | {r.block_id_pct} | {r.timezone} |")
    L += ["", "`parent_station %` liczone dla przystanków-słupków (`location_type=0`). "
          "`frequencies (n)` = liczba kursów opisanych przez `frequencies.txt`; takie kursy są rozwijane do liczby odjazdów.", "",
          "## Licencje i pobranie", "", "| Feed | Licencja (wg wydawcy) | Pobrano | URL |", "|---|---|---|---|"]
    for r in df.itertuples():
        L.append(f"| `{r.feed}` | {r.license} | {r.downloaded_at} | {r.url} |")
    bad = df[df["service_ids_without_trips"] > 0]
    L += ["", "## Wykryte defekty", ""]
    if len(bad):
        for r in bad.itertuples():
            L.append(f"- `{r.feed}`: {r.service_ids_without_trips} service_id występuje w kalendarzu, ale nie ma żadnego kursu w `trips.txt`; "
                     f"przez to {r.dates_with_orphan_service_only} dat nie ma żadnych kursów ("
                     "w `krakow_bus` to wszystkie czwartki i piątki po 25.11). Dni te nie nadają się na dzień referencyjny, dopóki ZTP nie poprawi feedu.")
    else:
        L.append("- Brak service_id bez kursów.")
    (OUT / "feeds_inventory.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ service by day
def run_service() -> pd.DataFrame:
    rows = []
    for fid in feed_ids():
        feed = Feed(fid)
        ts = trip_stats(feed)
        ts = ts.assign(km=ts["dist_m"] / 1000 * ts["runs"], h=ts["duration_s"] / 3600 * ts["runs"],
                       n=ts["runs"], km_stops=np.where(ts["dist_method"] == "stops", ts["dist_m"] / 1000 * ts["runs"], 0.0))
        ts["n_dd"] = np.where(ts["is_dup"], 0, ts["n"])
        ts["km_dd"] = np.where(ts["is_dup"], 0.0, ts["km"])
        ts["h_dd"] = np.where(ts["is_dup"], 0.0, ts["h"])
        per = ts.groupby("service_id")[["n", "km", "h", "km_stops", "n_dd", "km_dd", "h_dd"]].sum()
        sd = service_dates(feed)
        sd = sd[sd["service_id"].isin(per.index)]
        j = sd.join(per, on="service_id")
        d = j.groupby("date")[["n", "km", "h", "km_stops", "n_dd", "km_dd", "h_dd"]].sum().reset_index()
        d["feed"] = fid
        rows.append(d)
        print("service", fid, len(d), flush=True)
    df = pd.concat(rows, ignore_index=True)
    df["weekday"] = df["date"].dt.day_of_week.map(lambda i: WD_PL[i])
    df["weekday_n"] = df["date"].dt.day_of_week + 1
    df["km_method"] = np.where(df["km_stops"] <= 0, "shape", np.where(df["km_stops"] >= df["km"] * 0.999, "stops",
                                                                       "mixed"))
    df["share_km_from_stops_pct"] = (100 * df["km_stops"] / df["km"].replace(0, np.nan)).fillna(0)
    out = df.rename(columns={"n": "trips", "km": "vehicle_km", "h": "vehicle_h", "n_dd": "trips_dedup",
                             "km_dd": "vehicle_km_dedup", "h_dd": "vehicle_h_dedup"})
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out = out[["feed", "date", "weekday", "weekday_n", "trips", "vehicle_km", "vehicle_h", "trips_dedup",
               "vehicle_km_dedup", "vehicle_h_dedup", "km_method", "share_km_from_stops_pct"]].sort_values(["feed", "date"]).reset_index(drop=True)
    out["trips"] = out["trips"].astype(int)
    out["trips_dedup"] = out["trips_dedup"].astype(int)
    for c in ("vehicle_km", "vehicle_h", "vehicle_km_dedup", "vehicle_h_dedup"):
        out[c] = out[c].round(1)
    out["share_km_from_stops_pct"] = out["share_km_from_stops_pct"].round(1)
    _write_csv(out, OUT / "service_by_day.csv")
    return out


# ------------------------------------------------------------------ calendar helpers
def pl_holidays(year: int) -> set[pd.Timestamp]:
    """Polish public holidays (incl. Wigilia, a public holiday since 2025)."""
    from dateutil.easter import easter
    e = pd.Timestamp(easter(year))
    fixed = [(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 24), (12, 25), (12, 26)]
    out = {pd.Timestamp(year, m, d) for m, d in fixed}
    out |= {e, e + pd.Timedelta(days=1), e + pd.Timedelta(days=49), e + pd.Timedelta(days=60)}
    return out


def is_holiday(d: pd.Timestamp) -> bool:
    return d.normalize() in pl_holidays(d.year)


def in_excluded_period(d: pd.Timestamp) -> bool:
    for a, b in load_config().get("excluded_periods", []):
        if pd.Timestamp(a) <= d <= pd.Timestamp(b):
            return True
    return False


REF_JSON = OUT / "reference_days.json"

# Manual explanations of anomaly-test deviations > 5 % (filled in after reading the numbers).
EXPLAIN: dict[str, str] = {}


def _load_sbd() -> pd.DataFrame:
    sbd = pd.read_csv(OUT / "service_by_day.csv", parse_dates=["date"])
    return sbd


def _working_median(sbd: pd.DataFrame, feed: str, weekday_set: tuple[int, ...]) -> tuple[float, int]:
    g = sbd[(sbd["feed"] == feed) & sbd["weekday_n"].isin(weekday_set)]
    g = g[~g["date"].map(is_holiday)]
    return (float(g["vehicle_km_dedup"].median()) if len(g) else float("nan")), len(g)


def run_reference() -> dict:
    sbd = _load_sbd()
    feeds = feed_ids()
    today = pd.Timestamp(dt.date.today())
    km = sbd.pivot(index="date", columns="feed", values="vehicle_km_dedup").reindex(columns=feeds)
    tr = sbd.pivot(index="date", columns="feed", values="trips_dedup").reindex(columns=feeds)
    med_w = {f: _working_median(sbd, f, (1, 2, 3, 4, 5)) for f in feeds}
    med_s = {f: _working_median(sbd, f, (6,)) for f in feeds}

    def candidates(weekdays):
        out = []
        for d in km.index:
            if d < today or d.day_of_week + 1 not in weekdays:
                continue
            if is_holiday(d) or in_excluded_period(d):
                continue
            n_valid = int(km.loc[d].notna().sum())
            if n_valid == 0:
                continue
            out.append(d)
        return out

    def deviation(d, f, med):
        v = km.at[d, f] if f in km.columns else np.nan
        m = med[f][0]
        return (v / m - 1) if pd.notna(v) and m and not np.isnan(m) else np.nan

    def pick(cands, med):
        common = [d for d in cands if km.loc[d].notna().all()]
        pool = common if common else []
        if pool:
            score = {d: np.nanmean([abs(deviation(d, f, med)) for f in feeds]) for d in pool}
            best = sorted(pool, key=lambda d: (round(score[d], 4), 0 if d.day_of_week == 2 else 1, d))[0]
            return best, True, score
        return None, False, {}

    cw = candidates((2, 3, 4))
    cs = candidates((6,))
    ref, ref_common, score_w = pick(cw, med_w)
    sat, sat_common, score_s = pick(cs, med_s)
    per_feed: dict[str, str] = {}
    if ref is None:  # same weekday in different weeks, per feed
        for f in feeds:
            ds = [d for d in cw if pd.notna(km.at[d, f])]
            per_feed[f] = f"{min(ds, key=lambda d: abs(deviation(d, f, med_w))):%Y-%m-%d}" if ds else ""
    info = {"reference_day": ref.strftime("%Y-%m-%d") if ref is not None else None,
            "reference_saturday": sat.strftime("%Y-%m-%d") if sat is not None else None,
            "common_reference_day": ref_common, "common_reference_saturday": sat_common,
            "per_feed_fallback": per_feed}
    common_w = [d.strftime("%Y-%m-%d") for d in cw if km.loc[d].notna().all()]
    common_s = [d.strftime("%Y-%m-%d") for d in cs if km.loc[d].notna().all()]
    info["common_candidate_days"] = common_w
    info["common_candidate_saturdays"] = common_s
    common_json = json.dumps(info, ensure_ascii=False, indent=1, sort_keys=True)
    REF_JSON.write_text(common_json + "\n", encoding="utf-8", newline="\n")

    def cell(d, f, tab, scale=1.0, fmt="{:,.0f}"):
        v = tab.at[d, f]
        return "–" if pd.isna(v) else fmt.format(v * scale).replace(",", " ")

    L = ["# Dzień referencyjny: propozycja i test anomalii (faza 0)", "",
         f"Stan na {dt.date.today().isoformat()}. Dane: `service_by_day.csv` (kursy, wozokilometry z długości `shapes` w EPSG:2180, "
         "a gdy kurs nie ma kształtu: suma odległości po prostej między kolejnymi przystankami; udział tej metody w `service_by_day.csv`). "
         "Wartości w tabelach to **po usunięciu dokładnych duplikatów kursów** (kolumny `*_dedup`; dotyczy `gzm`, patrz niżej).",
         "", "## Rekomendacja", ""]
    if ref is not None:
        L += [f"- **Dzień roboczy (wt–czw): {ref.strftime('%Y-%m-%d')} ({WD_PL[ref.day_of_week]})**: jeden wspólny dzień dla wszystkich "
              f"{len(feeds)} feedów (każdy ma tego dnia kursy). Kandydat wybrany spośród wspólnych dni wt–czw o najmniejszym "
              "średnim odchyleniu wozokilometrów od mediany dni roboczych w ważności feedu (remis: środa).",
              f"- **Sobota: {sat.strftime('%Y-%m-%d') if sat is not None else 'brak wspólnej soboty'}**"
              + (" (wspólna dla wszystkich feedów)." if sat is not None else "."),
              f"- Wspólne dni wt–czw (poza świętami i 24.12–6.01): {', '.join(common_w) or 'brak'}.",
              f"- Wspólne soboty: {', '.join(common_s) or 'brak'}.", ""]
    else:
        L += ["- **Brak wspólnego dnia wt–czw** dla wszystkich feedów. Poniżej ten sam dzień tygodnia w różnych tygodniach, "
              "z jawną adnotacją (§5):", ""]
        for f, d in per_feed.items():
            L.append(f"  - `{f}`: {d or 'brak'}")
        L.append("")
    L += ["Uwaga: ograniczeniem wspólnego dnia jest najkrótsze okno ważności (patrz tabela niżej). Feedy wygasają, a raw zostaje w "
          "`data/raw/gtfs/` z datą pobrania i SHA-256; po zmianie feedów dzień trzeba wyznaczyć ponownie "
          "(`python -m pipeline.gtfs_inventory reference`).", ""]

    inv_path = OUT / "feeds_inventory.csv"
    if inv_path.exists():
        inv = pd.read_csv(inv_path)
        L += ["## Defekty feedów wpływające na wybór dnia", ""]
        any_def = False
        for r in inv[inv["exact_duplicate_trips_pct"] > 1].itertuples():
            any_def = True
            L.append(f"- `{r.feed}`: {r.exact_duplicate_trips} kursów ({r.exact_duplicate_trips_pct} %) to dokładne duplikaty (to samo `service_id`, linia, "
                     "kierunek, przystanki i czasy, inne `trip_id`; ten sam `block_id`). Wygląda to na sklejenie kilku dobowych plików ZTM GZM w jeden zip. "
                     "Wozokilometry i kursy w tabelach to wartości po usunięciu duplikatów (`*_dedup`); surowe wartości są w `service_by_day.csv`.")
        for r in inv[inv["service_ids_without_trips"] > 0].itertuples():
            any_def = True
            L.append(f"- `{r.feed}`: {r.service_ids_without_trips} `service_id` z `calendar_dates.txt` nie ma kursów w `trips.txt`, więc {r.dates_with_orphan_service_only} dat "
                     "(czwartki i piątki od 26.11) nie ma w feedzie żadnych kursów. Tych dni nie da się użyć jako dnia referencyjnego, a czwartek 26.11 wypada z wspólnych kandydatów.")
        if not any_def:
            L.append("- Brak.")
        L.append("")

    def table(days, title, weekdays_note):
        feeds_hdr = " | ".join(f"`{f}`" for f in feeds)
        out = [f"## {title}", "", weekdays_note, "",
               "Liczba kursów (z uwzględnieniem `frequencies.txt`); „–” = dzień poza ważnością feedu.", "",
               f"| Data | dzień | feedy z kursami | {feeds_hdr} |", "|---|---|---:|" + "---:|" * len(feeds)]
        for d in days:
            out.append(f"| {d:%Y-%m-%d} | {WD_PL[d.day_of_week]} | {int(km.loc[d].notna().sum())}/{len(feeds)} | "
                       + " | ".join(cell(d, f, tr) for f in feeds) + " |")
        out += ["", "Wozokilometry (tys. km):", "",
                f"| Data | dzień | {feeds_hdr} |", "|---|---|" + "---:|" * len(feeds)]
        for d in days:
            out.append(f"| {d:%Y-%m-%d} | {WD_PL[d.day_of_week]} | " + " | ".join(cell(d, f, km, 1e-3, '{:,.1f}') for f in feeds) + " |")
        out.append("")
        return out

    shown_w = cw[:14]
    shown_s = cs[:6]
    L += table(shown_w, "Kandydaci: dni robocze (wt–czw)",
               "Pierwsze 14 kandydatów (wt–czw, po wyłączeniu świąt i okresu 24.12–6.01; ferie zimowe przypadają w styczniu–lutym, "
               "więc nie dotyczą dat z listopada–grudnia).")
    L += table(shown_s, "Kandydaci: soboty", "Soboty bez świąt i bez okresu 24.12–6.01.")

    L += ["## Ważność feedów", "", "| Feed | pierwszy dzień | ostatni dzień | dni roboczych (pn–pt, bez świąt) w ważności |", "|---|---|---|---:|"]
    for f in feeds:
        g = sbd[sbd["feed"] == f]
        L.append(f"| `{f}` | {g['date'].min():%Y-%m-%d} | {g['date'].max():%Y-%m-%d} | {med_w[f][1]} |")
    L.append("")

    # anomaly test
    def anomaly(day, med, label, wd_label):
        out = [f"## Test anomalii: {label} {day:%Y-%m-%d}" if day is not None else f"## Test anomalii: {label}", "",
               f"Wozokilometry w dniu referencyjnym vs mediana wozokilometrów ({wd_label}) w okresie ważności feedu; "
               "odchylenie > 5 % jest oznaczone i wyjaśnione.", ""]
        if day is None:
            return out + ["Brak wspólnego dnia."], []
        out += ["| Feed | km w dniu ref. | mediana km | n dni w medianie | min–max w oknie | odchylenie | flaga | wyjaśnienie |", "|---|---:|---:|---:|---|---:|---|---|"]
        wset = (6,) if "sobota" in label else (1, 2, 3, 4, 5)
        rows = []
        for f in feeds:
            v = km.at[day, f]
            m, n = med[f]
            dev = (v / m - 1) if pd.notna(v) and m else np.nan
            flag = "TAK" if pd.notna(dev) and abs(dev) > 0.05 else "nie"
            rows.append({"feed": f, "date": f"{day:%Y-%m-%d}", "km": v, "median_km": m, "n": n, "dev_pct": dev * 100, "flag": flag})
            gg = sbd[(sbd["feed"] == f) & sbd["weekday_n"].isin(wset)]
            gg = gg[~gg["date"].map(is_holiday)]["vehicle_km_dedup"]
            rng = f"{gg.min():,.0f}–{gg.max():,.0f}"
            out.append(f"| `{f}` | {v:,.0f} | {m:,.0f} | {n} | {rng} | {dev * 100:+.1f} % | {flag} | {EXPLAIN.get(f + ':' + label, '') if flag == 'TAK' else ''} |".replace(",", " "))
        out.append("")
        return out, rows

    lw, rw = anomaly(ref, med_w, "dzień roboczy", "dni robocze pn–pt bez świąt")
    ls, rs = anomaly(sat, med_s, "sobota", "soboty bez świąt")
    L += lw + ls
    rows = [dict(r, kind="working_day") for r in rw] + [dict(r, kind="saturday") for r in rs]
    if rows:
        pd.DataFrame(rows).round({"km": 1, "median_km": 1, "dev_pct": 2}).to_csv(OUT / "anomaly_test.csv", index=False, lineterminator="\n")
    L += ["## Metoda i ograniczenia", "",
          "- Święta: 1.01, 6.01, Wielkanoc i poniedziałek, 1.05, 3.05, Zielone Świątki, Boże Ciało, 15.08, 1.11, 11.11, 24.12 (od 2025 r.), 25.12, 26.12.",
          "- Mediana dla feedów o długiej ważności (Kraków, WKD, rozkład kolejowy) obejmuje okresy wakacyjne i feryjne, więc jest tylko "
          "przybliżeniem „typowego dnia”; dla feedów 2–3-tygodniowych mediana pochodzi z tego samego okna co dzień referencyjny.",
          "- Test nie wykrywa, że cały feed jest „feryjny” lub objazdowy w całym oknie: do tego potrzebne jest porównanie z poprzednim "
          "rozkładem (archiwum `data/raw/gtfs/`).", ""]
    (OUT / "reference_day.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    return info


def _ref_days() -> dict:
    return json.loads(REF_JSON.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ rail overlap + top stops
def _norm_name(s: pd.Series) -> pd.Series:
    """Stop-name key: casefold, drop trailing platform numbers (' 01'), collapse spaces."""
    import re
    x = s.fillna("").str.casefold().str.replace(r"\s+", " ", regex=True).str.strip()
    x = x.str.replace(r"[\s,]+(nż|nz|\d{1,3}[a-z]?)$", "", regex=True)
    x = x.str.replace(r"\s+(peron|tor)\s*\S*$", "", regex=True)
    return x


def active_trips(fid: str, day: pd.Timestamp) -> pd.DataFrame:
    """Trips running on ``day`` with route short name; frequency trips keep their ``runs``."""
    feed = Feed(fid)
    ts = trip_stats(feed)
    sd = service_dates(feed)
    svc = set(sd.loc[sd["date"] == day, "service_id"])
    t = ts[ts["service_id"].isin(svc)].copy()
    r = feed.table("routes.txt", ["route_id", "route_short_name", "route_long_name"])
    t = t.merge(r, on="route_id", how="left")
    ag = feed.table("agency.txt", ["agency_id", "agency_name"])
    if ag is not None and "agency_id" in t:
        t = t.merge(ag, on="agency_id", how="left")
    t["feed"] = fid
    return t


def _stops_table(fid: str) -> pd.DataFrame:
    feed = Feed(fid)
    st = feed.table("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"])
    st["lat"] = pd.to_numeric(st["stop_lat"], errors="coerce")
    st["lon"] = pd.to_numeric(st["stop_lon"], errors="coerce")
    st["feed"] = fid
    return st


def departures_on_day(fid: str, day: pd.Timestamp) -> pd.DataFrame:
    """Every departure (excluding each trip's last stop) on ``day``; frequency trips are expanded."""
    feed = Feed(fid)
    trips = active_trips(fid, day)
    ev = stop_events(feed)
    ev = ev[ev["trip_id"].isin(set(trips["trip_id"]))].copy()
    ev["trip_id"] = ev["trip_id"].astype(object)
    ev["stop_id"] = ev["stop_id"].astype(object)
    last = ev.groupby("trip_id")["stop_sequence"].transform("max")
    ev = ev[ev["stop_sequence"] < last]
    keep = ["trip_id", "route_id", "route_short_name", "direction_id", "route_class", "first_dep_s", "is_dup"]
    ev = ev.merge(trips[keep], on="trip_id", how="left")
    fr = frequency_runs(feed)
    if len(fr):
        fr = fr[fr["trip_id"].isin(set(ev["trip_id"]))]
    if len(fr):
        fq = ev[ev["trip_id"].isin(set(fr["trip_id"]))]
        rest = ev[~ev["trip_id"].isin(set(fr["trip_id"]))]
        parts = [rest]
        for row in fr.itertuples():
            q = fq[fq["trip_id"] == row.trip_id]
            for k in range(int(row.runs)):
                shift = row.start_s + k * row.headway_s - q["first_dep_s"]
                parts.append(q.assign(dep_s=q["dep_s"] + shift))
        ev = pd.concat(parts, ignore_index=True)
    ev["feed"] = fid
    return ev[["feed", "trip_id", "route_id", "route_short_name", "direction_id", "route_class", "stop_id", "dep_s", "is_dup"]]


def _cluster_stops(stops: pd.DataFrame, radius_m: float) -> pd.DataFrame:
    """Add ``cluster`` (int): parent_station groups first, then identical normalised names within radius_m."""
    from pyproj import Transformer
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    s = stops.dropna(subset=["lat", "lon"]).copy().reset_index(drop=True)
    tr = Transformer.from_crs("EPSG:4326", common.CRS_METRIC, always_xy=True)
    s["x"], s["y"] = tr.transform(s["lon"].to_numpy(), s["lat"].to_numpy())
    s["group"] = np.where(s["parent_station"].notna(), s["feed"] + "|" + s["parent_station"].fillna(""), s["feed"] + "|" + s["stop_id"])
    s["name_key"] = _norm_name(s["stop_name"])
    # parent stations carry the name of the station; children inherit the group
    g = s.groupby("group").agg(x=("x", "mean"), y=("y", "mean"), name_key=("name_key", "first"))
    g = g.reset_index()
    g["gi"] = np.arange(len(g))
    rows, cols = [], []
    for _, idx in g.groupby("name_key").indices.items():
        if len(idx) < 2:
            continue
        pts = g.loc[idx, ["x", "y"]].to_numpy()
        for a, b in cKDTree(pts).query_pairs(radius_m):
            rows.append(idx[a])
            cols.append(idx[b])
    n = len(g)
    mat = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    _, lab = connected_components(mat, directed=False)
    g["cluster"] = lab
    s = s.merge(g[["group", "cluster"]], on="group", how="left")
    return s


def run_rail() -> None:
    refd = _ref_days()
    day = pd.Timestamp(refd["reference_day"] or sorted(refd["common_candidate_days"] or ["2026-11-25"])[0])
    cfg = load_config()
    pt = active_trips("polish_trains", day)
    pt["cls"] = pt["route_class"]
    L = ["# Nakładanie się kolei (`polish_trains`) z feedami miejskimi: pierwsze spojrzenie", "",
         f"Dzień odniesienia: **{day:%Y-%m-%d}** ({WD_PL[day.day_of_week]}). Kursy liczone na ten dzień; „kursy” = rozwinięte `frequencies.txt` (w feedach kolejowych brak).", "",
         "## 1. Co naprawdę zawiera `polish_trains.zip`", "",
         "| agency_id | Przewoźnik | kursy kolejowe (route_type 2) | kursy ZKA/autobus (route_type 3) | wozokm (tys.) |", "|---|---|---:|---:|---:|"]
    pt = pt.assign(km=pt["dist_m"] * pt["runs"] / 1000)
    for (aid, an), grp in pt.groupby(["agency_id", "agency_name"]):
        L.append(f"| {aid} | {an} | {int(grp.loc[grp.cls == 'rail', 'runs'].sum())} | {int(grp.loc[grp.cls == 'bus', 'runs'].sum())} | {grp['km'].sum() / 1000:,.1f} |".replace(",", " "))
    wanted = {"SKMT": "SKM Trójmiasto", "LKA": "ŁKA", "KML": "KMŁ", "KD": "KD", "KS": "KŚ", "KM": "KM"}
    present = set(pt["agency_id"])
    L += ["", "Oczekiwane przez brief: " + ", ".join(f"{v} ({'jest' if k in present else 'BRAK'})" for k, v in wanted.items())
          + ". Dodatkowo w feedzie: SKM Warszawa (`SKM`), Koleje Wielkopolskie (`KW`, linie PKM1–PKM5 = Poznańska Kolej Metropolitalna), "
          "PolRegio, PKP Intercity, Arriva RP, RegioJet, Leo Express. **Brak WKD** (osobny feed `warsaw_wkd`).", ""]
    pf = Feed("polish_trains")
    pts = trip_stats(pf)
    pkm_t = pts[pts["route_id"].astype(str).str.startswith("PR_PM")]
    pkm_d = service_dates(pf)
    pkm_d = pkm_d[pkm_d["service_id"].isin(set(pkm_t["service_id"]))]
    pkm_now = pt[pt["route_id"].astype(str).str.startswith("PR_PM")]
    L += [f"**Pomorska Kolej Metropolitalna (PKM Gdańsk)** nie ma własnej agencji: kursy jeździ PolRegio jako trasa `{', '.join(sorted(set(pkm_t['route_id'])))}` "
          f"({len(pkm_t)} kursów w feedzie; w dniu ref. {int(pkm_now['runs'].sum())}; "
          + (f"dni kursowania {pkm_d['date'].min():%Y-%m-%d} – {pkm_d['date'].max():%Y-%m-%d}" if len(pkm_d) else "brak dni kursowania")
          + "). Linia startuje wraz ze zmianą rozkładu w grudniu, więc w listopadowym dniu referencyjnym jej nie ma. "
          "Przy filtrowaniu po agencji trzeba ją wyciągnąć po `route_id`, nie po `agency_id`.", ""]
    # which agglomerations does each agency serve (trips touching a stop within 25 km of a centre)
    ev = stop_events(Feed("polish_trains"))
    stp = _stops_table("polish_trains")
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", common.CRS_METRIC, always_xy=True)
    stp["x"], stp["y"] = tr.transform(stp["lon"].to_numpy(), stp["lat"].to_numpy())
    ev = ev[ev["trip_id"].isin(set(pt["trip_id"]))][["trip_id", "stop_id"]].copy()
    ev["trip_id"] = ev["trip_id"].astype(object)
    ev["stop_id"] = ev["stop_id"].astype(object)
    ev = ev.merge(stp[["stop_id", "x", "y"]], on="stop_id", how="left")
    L += ["## 2. Przewoźnicy kolejowi w aglomeracjach (kursy, które zatrzymują się na przystanku w promieniu 25 km od centrum)", "",
          "| Aglomeracja | " + " | ".join(sorted(present)) + " | razem |", "|---|" + "---:|" * (len(present) + 1)]
    ptx = pt.set_index("trip_id")
    for key, a in cfg["agglomerations"].items():
        if a.get("phase") != 1:
            continue
        centres = [a["centre"]] + a.get("extra_centres", [])
        mask = np.zeros(len(ev), bool)
        for c in centres:
            cx, cy = tr.transform(c["lon"], c["lat"])
            mask |= np.hypot(ev["x"] - cx, ev["y"] - cy).to_numpy() <= 25000
        tids = set(ev.loc[mask, "trip_id"])
        sub = pt[pt["trip_id"].isin(tids) & (pt["cls"] == "rail")]
        cnt = sub.groupby("agency_id")["runs"].sum()
        L.append(f"| {a['name']} | " + " | ".join(str(int(cnt.get(x, 0))) for x in sorted(present)) + f" | {int(cnt.sum())} |")
    L.append("")
    # overlap candidates: rail/metro routes in city feeds
    L += ["## 3. Kandydaci na dublowanie: trasy szynowe w feedach miejskich", "",
          "| Feed | route_id | nazwa | klasa | kursy w dniu ref. |", "|---|---|---|---|---:|"]
    city_rail = []
    for fid in feed_ids():
        if fid == "polish_trains":
            continue
        t = active_trips(fid, day)
        sub = t[t["route_class"].isin(["rail", "metro"])]
        if len(sub):
            city_rail.append(sub)
            for rid, grp in sub.groupby("route_id"):
                L.append(f"| `{fid}` | {rid} | {grp['route_short_name'].iloc[0]} {str(grp['route_long_name'].iloc[0])[:50]} | {grp['route_class'].iloc[0]} | {int(grp['runs'].sum())} |")
    L.append("")
    # match warsaw S-lines against polish_trains SKM
    msg = []
    if city_rail:
        cr = pd.concat(city_rail)
        w = cr[(cr["feed"] == "warsaw_ztm") & (cr["route_class"] == "rail")].copy()
        s = pt[pt["agency_id"] == "SKM"].copy()
        for name, t, fid in (("w", w, "warsaw_ztm"), ("s", s, "polish_trains")):
            stp_ = _stops_table(fid)[["stop_id", "stop_name"]]
            t = t.merge(stp_.rename(columns={"stop_id": "first_stop_id", "stop_name": "o_name"}), on="first_stop_id", how="left")
            t = t.merge(stp_.rename(columns={"stop_id": "last_stop_id", "stop_name": "d_name"}), on="last_stop_id", how="left")
            t["o_key"] = _norm_name(t["o_name"])
            t["d_key"] = _norm_name(t["d_name"])
            t["dep_min"] = (t["first_dep_s"] // 60).astype(int)
            if name == "w":
                w = t
            else:
                s = t
        key_a = ["route_short_name", "o_key", "dep_min"]
        key_b = ["o_key", "dep_min"]
        ma = w.merge(s[key_a].drop_duplicates(), on=key_a, how="left", indicator=True)
        mb = w.merge(s[key_b].drop_duplicates(), on=key_b, how="left", indicator=True)
        share_a = (ma["_merge"] == "both").mean() * 100 if len(w) else 0
        share_b = (mb["_merge"] == "both").mean() * 100 if len(w) else 0
        sw = set(w["route_short_name"])
        L += ["## 4. Test dublowania: SKM Warszawa w `warsaw_ztm` vs agencja `SKM` w `polish_trains`", "",
              f"- `warsaw_ztm`: {len(w)} kursów kolejowych (linie {', '.join(sorted(sw))}) w dniu ref.; `polish_trains`/SKM: {len(s)} kursów "
              f"(linie {', '.join(sorted(set(s['route_short_name'])))}).",
              f"- Dopasowanie kursu: ta sama linia + ta sama (znormalizowana) nazwa przystanku początkowego + ta sama minuta odjazdu: **{share_a:.1f} %** kursów `warsaw_ztm` ma odpowiednik w `polish_trains`.",
              f"- Luźniejszy klucz (przystanek początkowy + minuta, bez linii): {share_b:.1f} %.",
              "- Wniosek: " + ("to ten sam rozkład SKM Warszawa podany dwukrotnie; kursy należy liczyć raz." if share_a > 70 else
                              "feedy opisują SKM w różny sposób (różnice w przystankach początkowych/czasach); wymagana ręczna weryfikacja przed deduplikacją."), ""]
        # unmatched sample
        um = ma[ma["_merge"] == "left_only"].head(8)
        if len(um):
            L += ["Przykłady kursów `warsaw_ztm` bez odpowiednika (linia, przystanek początkowy, odjazd):", ""]
            for r in um.itertuples():
                L.append(f"- {r.route_short_name}, {r.o_key}, {int(r.dep_min) // 60:02d}:{int(r.dep_min) % 60:02d}")
            L.append("")
    L += ["## 5. Proponowana reguła deduplikacji", "",
          "1. Jedna jednostka zliczania: kurs (trip) w dniu referencyjnym; klucz dopasowania między feedami = (linia, znormalizowana nazwa przystanku początkowego "
          "w promieniu 100 m, minuta odjazdu z przystanku początkowego).",
          "2. **SKM Warszawa**: zostawić wersję z `warsaw_ztm` (linie S1–S4, S40; przystanki zgodne z siecią ZTM i strefami biletowymi, kształty), a agencję `SKM` "
          "z `polish_trains` odrzucić przed zliczaniem (filtr po `agency_id`). Linie M1/M2 są tylko w `warsaw_ztm`.",
          "3. **Pozostała kolej regionalna** (KM, KŚ, KD, KMŁ, ŁKA, SKM Trójmiasto, KW/PKM, PolRegio, IC): jedyne źródło to `polish_trains`; ich kursy są liczone raz, "
          "po przycięciu do FUA + bufor.",
          "4. **WKD** pochodzi wyłącznie z `warsaw_wkd` (brak w `polish_trains`).",
          "5. Autobusowa komunikacja zastępcza (route_type 3, „ZKA”) w `polish_trains` wyłączyć z miar „kolejowych” (to nie kolej; kursy zastępcze są doraźne).",
          "6. Reguła ogólna dla przyszłych feedów: jeśli ten sam kurs (klucz z pkt 1) występuje w feedzie miejskim i kolejowym, wygrywa feed miejski; "
          "każdy odrzucony kurs trafia do `results/qa/` z liczbą odrzuconych na aglomerację.", ""]
    (OUT / "rail_overlap.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def run_topstops() -> None:
    from pyproj import Transformer
    refd = _ref_days()
    day = pd.Timestamp(refd["reference_day"] or sorted(refd["common_candidate_days"] or ["2026-11-25"])[0])
    cfg = load_config()
    tr = Transformer.from_crs("EPSG:4326", common.CRS_METRIC, always_xy=True)
    deps_all: dict[str, pd.DataFrame] = {}
    stops_all: dict[str, pd.DataFrame] = {}
    for fid in feed_ids():
        d = departures_on_day(fid, day)
        deps_all[fid] = d
        stops_all[fid] = _stops_table(fid)
        print("departures", fid, len(d), flush=True)
    out_rows = []
    dup_rows = []
    for key, a in cfg["agglomerations"].items():
        if a.get("phase") != 1:
            continue
        feeds = [f for f, c in cfg["feeds"].items() if key in c.get("agglomerations", [])]
        centres = [a["centre"]] + a.get("extra_centres", [])
        st = pd.concat([stops_all[f] for f in feeds], ignore_index=True)
        st = st[(st["location_type"].fillna("0") != "1") | st["stop_id"].isin(set(st["parent_station"].dropna()))]
        st = st.dropna(subset=["lat", "lon"])
        x, y = tr.transform(st["lon"].to_numpy(), st["lat"].to_numpy())
        near = np.zeros(len(st), bool)
        for c in centres:
            cx, cy = tr.transform(c["lon"], c["lat"])
            near |= np.hypot(x - cx, y - cy) <= 25000
        st = st[near]
        cl = _cluster_stops(st, cfg.get("stop_cluster_radius_m", 100))
        # stops of child platforms point to the parent group through parent_station; map stop_id -> cluster (stop points only)
        sp = cl[["feed", "stop_id", "cluster"]]
        dep = pd.concat([deps_all[f] for f in feeds], ignore_index=True)
        dep = dep.merge(sp, on=["feed", "stop_id"], how="inner")
        win_all = dep[(dep["dep_s"] >= 6 * 3600) & (dep["dep_s"] < 20 * 3600)].copy()
        raw_n = win_all.groupby("cluster").size()
        dupt_n = win_all[win_all["is_dup"]].groupby("cluster").size()
        win = win_all[~win_all["is_dup"]].copy()   # exact duplicate trips removed (GZM)
        win["dep_min"] = (win["dep_s"] // 60).astype(int)
        dkey = ["feed", "cluster", "route_short_name", "direction_id", "dep_min"]
        win["dup_same_feed"] = win.duplicated(subset=dkey, keep="first")
        win["dkey2"] = win["route_short_name"].astype(str) + "|" + win["dep_min"].astype(str)
        nf = win.groupby(["cluster", "dkey2"])["feed"].transform("nunique")
        win["cross_feed"] = nf > 1
        top = win.groupby("cluster").agg(deps=("dep_s", "size"), dup_same=("dup_same_feed", "sum"), cross=("cross_feed", "sum"),
                                         n_stops=("stop_id", "nunique"), feeds=("feed", lambda s: "+".join(sorted(set(s)))))
        top["raw"] = raw_n.reindex(top.index).fillna(0).astype(int)
        top["dupt"] = dupt_n.reindex(top.index).fillna(0).astype(int)
        top = top.sort_values(["deps"], ascending=False, kind="stable").head(10)
        names = cl.groupby("cluster").agg(name=("stop_name", lambda s: s.value_counts().index[0]), lat=("lat", "mean"), lon=("lon", "mean"))
        by_cls = win.groupby(["cluster", "route_class"]).size().unstack(fill_value=0)
        for rank, (c, r) in enumerate(top.iterrows(), start=1):
            row = {"agglomeration": key, "rank": rank, "stop_name": names.at[c, "name"], "lat": round(names.at[c, "lat"], 5),
                   "lon": round(names.at[c, "lon"], 5), "stop_points": int(r["n_stops"]), "feeds": r["feeds"],
                   "departures_06_20": int(r["deps"]), "departures_per_hour": round(r["deps"] / 14, 1),
                   "departures_06_20_raw": int(r["raw"]), "dup_trip_share_pct": round(100 * r["dupt"] / r["raw"], 1) if r["raw"] else 0.0,
                   "dup_same_feed_pct": round(100 * r["dup_same"] / r["deps"], 1),
                   "cross_feed_pct": round(100 * r["cross"] / r["deps"], 1)}
            for k in ("tram", "metro", "rail", "bus", "trolleybus"):
                row[f"deps_{k}"] = int(by_cls.at[c, k]) if k in by_cls.columns else 0
            flags = []
            if row["dup_trip_share_pct"] >= 5:
                flags.append("w feedzie są dokładne duplikaty kursów (usunięte z licznika; kolumna raw je zawiera)")
            if row["dup_same_feed_pct"] >= 5:
                flags.append("możliwe zdublowane odjazdy tej samej linii w tej samej minucie")
            if row["cross_feed_pct"] >= 5:
                flags.append("odjazdy w więcej niż jednym feedzie (np. kolej)")
            row["flag"] = "; ".join(flags)
            out_rows.append(row)
    df = pd.DataFrame(out_rows)
    df.insert(0, "reference_day", f"{day:%Y-%m-%d}")
    _write_csv(df, OUT / "top_stops_preview.csv")
    # feed-level duplicate-trip diagnostic on the reference day (same service_id, identical route/stops/times)
    for fid in feed_ids():
        t = active_trips(fid, day)
        dup_rows.append({"feed": fid, "trips_on_ref_day": int(t["runs"].sum()), "exact_duplicate_trips": int(t["is_dup"].sum()),
                         "dup_pct": round(100 * t["is_dup"].mean(), 2) if len(t) else 0.0})
    pd.DataFrame(dup_rows).to_csv(OUT / "duplicate_trips_check.csv", index=False, lineterminator="\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inventory", "service", "reference", "rail", "topstops", "all"])
    a = ap.parse_args()
    t0 = time.time()
    inputs = [manifest_id(f) for f in feed_ids()]
    if a.cmd in ("inventory", "all"):
        write_inventory_md(run_inventory())
    if a.cmd in ("service", "all"):
        run_service()
    if a.cmd in ("reference", "all"):
        run_reference()
    if a.cmd in ("rail", "all"):
        run_rail()
    if a.cmd in ("topstops", "all"):
        run_topstops()
    write_meta(OUT, "gtfs_inventory", inputs=inputs, started=t0)


if __name__ == "__main__":
    main()
