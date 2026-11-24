"""metrics_speed.csv/json and results/qa/speed/speed.md from the outputs of speed_tables, tram_stretches, speed_areas.

    python -m pipeline.speed_report

Reads only committed outputs (results/tables, results/qa/speed/*, results/layers), so the note and the metrics are
reproducible from them.  The hand-written parts of the note (spot-checks, critical reading of the rankings) are the
constants in pipeline/speed_text.py; they were written after looking at the 2026-11-25 / 2026-11-28 results and must
be re-read when the data change.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from pipeline import speed_core as sc
from pipeline import speed_text as TX
from pipeline.common import RESULTS, load_config, sig, write_json, write_meta

QA = RESULTS / "qa" / "speed"
TB = RESULTS / "tables"
LY = RESULTS / "layers"
METRICS = RESULTS / "metrics"
COLS = ["agglomeration", "domain", "metric", "label", "value", "unit", "grid", "source", "population_date",
        "timetable_date", "coverage_share", "flag", "tier", "feed_variant"]
TRAM_CITY = {"warszawa": "Warszawa", "krakow": "Kraków", "wroclaw": "Wrocław", "poznan": "Poznań", "lodz": "Łódź",
             "trojmiasto": "Gdańsk", "gzm": "GZM"}
SRC_TRIPS = ("GTFS (warstwa gtfs_service), kursy dnia referencyjnego; długość wzdłuż kształtu trasy (shapes), "
             "w razie braku odcinki proste; suma długości / suma czasów rozkładowych kursów rozpoczętych w paśmie")
SRC_STRETCH = ("GTFS (warstwa gtfs_service), przejazdy między przystankami na odcinkach sieci tramwajowej "
               "(pipeline.tram_stretches); OSM 2026-11-22 tylko do atrybutów odcinków")
FLAG = "rozkładowa prędkość komunikacyjna z postojami, nie rzeczywista"


def fnum(x, d: int = 1) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)) or pd.isna(x):
        return "brak danych"
    x = 0.0 if abs(float(x)) < 0.5 * 10 ** -d else float(x)
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pct(x, d: int = 1) -> str:
    return "brak danych" if x is None or pd.isna(x) else fnum(100 * float(x), d) + " %"


def md_table(df: pd.DataFrame) -> str:
    h = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return h + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)) + "\n"


# ------------------------------------------------------------------ metrics
def metrics(city: pd.DataFrame, gap: pd.DataFrame, share: pd.DataFrame) -> list[dict]:
    days = sc.days()
    rows = []

    def add(agg, domain, metric, label, value, unit, day, tier, variant="all", src=SRC_TRIPS, flag=FLAG):
        rows.append({"agglomeration": agg, "domain": domain, "metric": metric, "label": label,
                     "value": sig(value) if value is not None and pd.notna(value) else None, "unit": unit, "grid": None,
                     "source": src, "population_date": None, "timetable_date": day, "coverage_share": None,
                     "flag": flag, "tier": tier, "feed_variant": variant})
    for agg in sc.AGGS:
        c = TRAM_CITY[agg]
        tr = city[(city["agglomeration"] == agg) & (city["mode"] == "tram") & (city["variant"] == "all")]
        for dt, band, metric, tier in (("weekday", "am_peak", "tram_speed_sched_am_peak", "main"),
                                       ("weekday", "evening", "tram_speed_sched_evening", "main"),
                                       ("weekday", "midday", "tram_speed_sched_midday", "table"),
                                       ("weekday", "pm_peak", "tram_speed_sched_pm_peak", "table"),
                                       ("saturday", "day", "tram_speed_sched_sat_day", "table")):
            r = tr[(tr["day_type"] == dt) & (tr["band"] == band)]
            if len(r):
                add(agg, "city_tram_network", metric,
                    f"Rozkładowa prędkość komunikacyjna tramwajów, {sc.band_label(dt, band)} ({sc.DAY_PL[dt]} {days[dt]}), {c}",
                    float(r["speed_kmh"].iloc[0]), "km/h", days[dt], tier,
                    flag=FLAG + "; sieć tramwajowa miasta, nie FUA; pasmo wg godziny pierwszego odjazdu kursu")
        g = gap[(gap["agglomeration"] == agg) & (gap["mode"] == "tram") & (gap["variant"] == "all")]
        if len(g):
            add(agg, "city_tram_network", "tram_speed_gap_evening_minus_am_peak",
                f"Różnica prędkości tramwajów: wieczór 20–23 minus szczyt poranny 07–09 (śr. {days['weekday']}), {c}",
                float(g["gap_evening_minus_am_peak_kmh"].iloc[0]), "km/h", days["weekday"], "table",
                flag=FLAG + "; dodatnia = wieczorem szybciej")
        s = share[(share["agglomeration"] == agg) & (share["day_type"] == "weekday") & (share["band"] == "am_peak")]
        if len(s):
            add(agg, "city_tram_network", "tram_vkm_share_below15_am_peak",
                f"Udział wozokilometrów tramwajów na odcinkach z prędkością rozkładową < 15 km/h, szczyt poranny (śr. {days['weekday']}), {c}",
                float(s["share_vkm_below_15kmh"].iloc[0]) * 100, "%", days["weekday"], "main", src=SRC_STRETCH,
                flag=FLAG + "; tylko odcinki o czasie przejazdu >= 5 min (krótsze: osobny udział)")
            lo, hi = float(s["taf_lo_s_per_km"].iloc[0]), float(s["taf_hi_s_per_km"].iloc[0])
            add(agg, "city_tram_network", "tram_time_above_free_running_s_per_km_am_peak",
                f"Czas ponad jazdę swobodną (model) tramwajów, s/km, szczyt poranny (śr. {days['weekday']}), {c}",
                float(s["taf_s_per_km"].iloc[0]), "s/km", days["weekday"], "table", src=SRC_STRETCH,
                flag=f"model, nie pomiar; przedział {fnum(lo, 0)}–{fnum(hi, 0)} s/km (postój 10–30 s, limit 40–70 km/h tam, "
                     "gdzie OSM nie podaje maxspeed); wartość środkowa: przyspieszenie i hamowanie 1,0 m/s², limit 50 km/h "
                     "albo maxspeed z OSM, postój 20 s; zawiera sygnalizację, ograniczenia prędkości, wymianę pasażerów "
                     "i rezerwy rozkładu")
            add(agg, "city_tram_network", "tram_vkm_share_short_stretches",
                f"Udział wozokilometrów tramwajów na odcinkach krótszych niż 5 min (poza rankingami), szczyt poranny, {c}",
                float(s["share_vkm_below_min_stretches"].iloc[0]) * 100, "%", days["weekday"], "table", src=SRC_STRETCH)
        for variant in ("all", "official"):
            b = city[(city["agglomeration"] == agg) & (city["mode"] == "bus") & (city["variant"] == variant)]
            for dt, band, metric in (("weekday", "am_peak", "bus_speed_sched_am_peak"), ("weekday", "evening", "bus_speed_sched_evening")):
                r = b[(b["day_type"] == dt) & (b["band"] == band)]
                if len(r):
                    add(agg, "gtfs_service_area", metric,
                        f"Rozkładowa prędkość komunikacyjna autobusów, {sc.band_label(dt, band)} (śr. {days[dt]}), {sc.AGG_NAMES[agg]}",
                        float(r["speed_kmh"].iloc[0]), "km/h", days[dt], "table", variant=variant,
                        flag=FLAG + "; wszystkie kursy autobusowe feedów aglomeracji (także podmiejskie), bez komunikacji zastępczej kolei"
                        + ("; feedy nieoficjalne niezweryfikowane" if variant == "all" else ""))
        m = city[(city["agglomeration"] == agg) & (city["mode"] == "metro") & (city["variant"] == "all") &
                 (city["day_type"] == "weekday") & (city["band"] == "am_peak")]
        if len(m):
            add(agg, "gtfs_service_area", "metro_speed_sched_am_peak",
                f"Rozkładowa prędkość komunikacyjna metra, szczyt poranny 07–09 (śr. {days['weekday']}), {sc.AGG_NAMES[agg]}",
                float(m["speed_kmh"].iloc[0]), "km/h", days["weekday"], "table")
    return rows


def write_metrics(rows: list[dict]) -> None:
    df = pd.DataFrame(rows, columns=COLS).sort_values(["agglomeration", "domain", "metric", "feed_variant"], kind="stable")
    df.to_csv(METRICS / "metrics_speed.csv", index=False, lineterminator="\n")
    recs = [{k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()} for r in df.to_dict("records")]
    write_json(METRICS / "metrics_speed.json", recs)


# ------------------------------------------------------------------ note
def note(D: dict) -> str:
    days = sc.days()
    city, gap, chk, qc, lines = D["city"], D["gap"], D["chk"], D["qc"], D["lines"]
    o = []
    o.append("# Rozkładowa prędkość komunikacyjna: linie, obszary, odcinki tramwajowe\n")
    o.append(f"Rozkłady: środa {days['weekday']} i sobota {days['saturday']} (feedy pobrane 2026-11-23); OSM 2026-11-22; "
             "ludność NSP 2021 w układzie GHSL 2020 (tylko do grup gęstości w części 2). Kod: `pipeline/speed_core.py`, "
             "`speed_tables.py`, `speed_areas.py` (+ `speed_areas_out.py`), `tram_stretches.py` (+ `tram_stretches_out.py`), "
             "`speed_osm.py`, `speed_report.py`, `speed_text.py`; pliki mapy: `speed_web.py`.\n")
    o.append(TX.INTRO)
    o.append(TX.BANDS)
    o.append(TX.FOUNDATION)
    # ---- part 1
    o.append("## 1. Prędkość linii (wszystkie środki)\n")
    o.append(TX.PART1_RULES)
    o.append("### 1.1 Tramwaje według pasm (km/h, suma długości / suma czasu)\n")
    t = city[(city["mode"] == "tram") & (city["variant"] == "all")]
    rows = []
    for agg in sc.AGGS:
        r = {"Miasto": TRAM_CITY[agg]}
        for dt in ("weekday", "saturday"):
            for b in sc.band_ids(dt) + ["all_day"]:
                x = t[(t["agglomeration"] == agg) & (t["day_type"] == dt) & (t["band"] == b)]
                lab = ("śr. " if dt == "weekday" else "sob. ") + (sc.band_label(dt, b) if b != "all_day" else "doba")
                r[lab] = fnum(x["speed_kmh"].iloc[0]) if len(x) else "brak danych"
        rows.append(r)
    tb = pd.DataFrame(rows)
    o.append(md_table(tb.iloc[:, :9]))
    o.append("\n" + md_table(pd.concat([tb.iloc[:, :1], tb.iloc[:, 9:]], axis=1)))
    o.append("\nLiczby kursów w pasmach: `tables/speed_city_mode_band.csv`. W paśmie nocnym jest najmniej kursów tramwajowych (69–396 w środę), "
             "więc ta kolumna jest najmniej pewna.\n")
    o.append("### 1.2 Szczyt a wieczór (środa)\n")
    rows = []
    for agg in sc.AGGS:
        for mode in ("tram", "bus", "trolleybus", "metro"):
            g = gap[(gap["agglomeration"] == agg) & (gap["mode"] == mode) & (gap["variant"] == "all")]
            if not len(g):
                continue
            g = g.iloc[0]
            rows.append({"Aglomeracja": sc.AGG_NAMES[agg], "Środek": sc.MODE_PL[mode],
                         "Szczyt 07–09": fnum(g.weekday_am_peak_kmh), "Międzyszczyt 09–15": fnum(g.weekday_midday_kmh),
                         "Szczyt 15–18": fnum(g.weekday_pm_peak_kmh), "Wieczór 20–23": fnum(g.weekday_evening_kmh),
                         "Wieczór − szczyt poranny": fnum(g.gap_evening_minus_am_peak_kmh),
                         "Sobota 09–18": fnum(g.saturday_day_kmh)})
    o.append(md_table(pd.DataFrame(rows)))
    o.append(TX.GAP_READING)
    o.append("### 1.3 Kolej i feedy bez kształtów tras\n")
    rows = []
    for agg in sc.AGGS:
        g = city[(city["agglomeration"] == agg) & (city["variant"] == "all") & (city["day_type"] == "weekday") & (city["band"] == "all_day")]
        for r in g.itertuples(index=False):
            rows.append({"Aglomeracja": sc.AGG_NAMES[agg], "Środek": sc.MODE_PL.get(r.mode, r.mode), "Kursy": r.n_trips,
                         "Prędkość, km/h": fnum(r.speed_kmh), "Kursy z odcinkami w linii prostej": pct(r.share_trips_fallback),
                         "Kształt / linia prosta (kursy z kształtem)": fnum(r.detour_factor_shaped_trips, 2),
                         "Udział wozokm feedów nieoficjalnych": pct(r.share_vkm_unofficial)})
    o.append(md_table(pd.DataFrame(rows)))
    o.append(TX.FALLBACK)
    o.append("### 1.4 Kontrola: mediany tramwajów z `qa/transit/tram_speed_per_city.csv`\n")
    rows = []
    for r in chk.itertuples(index=False):
        rows.append({"Miasto": r.city, "Dzień": sc.DAY_PL[r.day_type], "Opublikowana mediana": fnum(r.published_median_kmh, 2),
                     "Ponowne uruchomienie tram_speed": fnum(r.rerun_tram_speed_median_kmh, 2),
                     "Ta warstwa (mediana kursów)": fnum(r.this_step_median_kmh, 2), "Kursy (opubl. / tu)": f"{r.published_n_trips} / {r.this_step_n_trips}",
                     "95. centyl różnicy na kurs": fnum(r.p95_abs_diff_per_trip_kmh, 2)})
    o.append(md_table(pd.DataFrame(rows)))
    o.append(TX.CHECK_READING)
    o.append("### 1.5 Wcześniejsze szybkie spojrzenie (hipoteza) a ta warstwa\n")
    rows = []
    for r in qc.itertuples(index=False):
        rows.append({"Aglomeracja": sc.AGG_NAMES[r.agglomeration], "Grupa kursów": r.group, "Kursy": r.n_trips,
                     "Odcinki proste × 1,04": fnum(r.speed_straight_x104_kmh), "Kształt trasy": fnum(r.speed_shape_kmh)})
    o.append(md_table(pd.DataFrame(rows)))
    o.append(TX.QUICK_READING)
    o.append(TX.PUBLISHED)
    pc = D["puls"]
    city = D["city"]
    rows = []
    for r in pc.itertuples(index=False):
        a = city[(city["agglomeration"] == r.agglomeration) & (city["mode"] == "tram") & (city["variant"] == "all") &
                 (city["day_type"] == "weekday") & (city["band"] == "all_day")]
        rows.append({"Miasto": TRAM_CITY[r.agglomeration], "Linie (po 21:00)": f"{r.n_lines} ({r.n_lines_offpeak})",
                     "Puls 2023: średnia / 15:00 / 21:00": f"{fnum(r.puls_2023_overall_kmh)} / {fnum(r.puls_2023_peak_kmh)} / {fnum(r.puls_2023_offpeak_kmh)}",
                     "Ta metoda Pulsu, 2026: średnia / 15:00 / 21:00": f"{fnum(r.puls_style_overall_kmh)} / {fnum(r.puls_style_peak_kmh)} / {fnum(r.puls_style_offpeak_kmh)}",
                     "Różnica (średnia)": fnum(r.diff_overall_kmh),
                     "Wszystkie kursy, cała doba": fnum(a["speed_kmh"].iloc[0]) if len(a) else "brak danych"})
    o.append(md_table(pd.DataFrame(rows)))
    o.append(TX.PULS_READING)
    o.append(TX.DEFINITIONS)
    # ---- part 3
    o.append("## 3. Odcinki sieci tramwajowej\n")
    o.append(TX.STRETCH_RULE)
    dg = D["sdiag"]
    rows = []
    for r in dg.itertuples(index=False):
        rows.append({"Miasto": r.city, "Przystanki (słupki)": r.tram_stops, "Miejsca": r.places, "Odcinki": r.stretches,
                     "Odcinki × kierunki": r.stretch_directions, "Mediana długości, m": fnum(r.median_length_m, 0),
                     "Przejazdy poza odcinkami": pct(r.hops_unmapped_weekday),
                     "Dopasowanie do toru OSM (mediana / 10. centyl)": f"{pct(r.osm_match_share_median, 0)} / {pct(r.osm_match_share_p10, 0)}",
                     "Odległość od toru, m (mediana)": fnum(r.osm_match_distance_median_m),
                     "W jezdni": pct(r.share_street_len), "Wydzielone": pct(r.share_separated_len), "Bez dopasowania": pct(r.share_unmatched_len)})
    o.append(md_table(pd.DataFrame(rows)))
    o.append(TX.MATCH_READING)
    o.append("### 3.1 Zaokrąglenie do minut: kontrola\n")
    rs = D["rsum"]
    o.append(md_table(pd.DataFrame({"Czas odcinka (śr. 09–15)": rs["bin"], "Odcinki × kierunki z ≥ 2 liniami": rs["stretch_directions"],
                                    "Z różnicą czasu między liniami": [pct(x) for x in rs["share_with_line_difference"]],
                                    "Średni rozrzut, min": [fnum(x, 2) for x in rs["mean_range_min"]]})))
    o.append(TX.ROUNDING_READING)
    o.append("### 3.2 Torowisko w jezdni czy wydzielone: reguła i sprawdzenie\n")
    o.append(TX.SEPARATION)
    o.append("### 3.3 Czas ponad jazdę swobodną (model)\n")
    o.append(TX.KINEMATICS)
    dg2 = D["sdiag"]
    o.append("Pokrycie tagiem `maxspeed` (tory `railway=tram` w FUA + 2 km, OSM 2026-11-22):\n\n" + md_table(pd.DataFrame({
        "Miasto": dg2["city"], "Długość torów z dowolnym maxspeed": [pct(x, 0) for x in dg2["share_track_len_maxspeed_any_osm"]],
        "Z maxspeed 30–100 km/h (użyte)": [pct(x, 0) for x in dg2["share_track_len_maxspeed_used"]],
        "Długość odcinków z użytym maxspeed": [pct(x, 0) for x in dg2["share_stretch_len_maxspeed"]]})))
    o.append(TX.MAXSPEED_READING)
    sens = D["sens"]
    pv = sens.pivot_table(index="variant", columns="agglomeration", values="taf_s_per_km", sort=False)
    pv = pv[[a for a in sc.AGGS if a in pv.columns]]
    tbl = pd.DataFrame({"Wariant": pv.index})
    for a in pv.columns:
        tbl[TRAM_CITY[a]] = [fnum(x, 0) for x in pv[a]]
    rk = sens.groupby("variant", sort=False).agg(rc=("rank_corr_with_main", "min"), ov=("top10_overlap_with_main", "min"),
                                                  neg=("share_stretches_faster_than_model", "max")).reindex(pv.index)
    tbl["Min. korelacja rang z głównym"] = [fnum(x, 2) for x in rk["rc"]]
    tbl["Min. wspólnych w top 10"] = [int(x) for x in rk["ov"]]
    tbl["Maks. udział odcinków szybszych niż model"] = [pct(x, 0) for x in rk["neg"]]
    o.append("Czas ponad jazdę swobodną w mieście, s/km (suma czasu rozkładowego minus suma czasu swobodnego, na wozokilometr), "
             "szczyt poranny w środę, odcinki ≥ 5 min; wariant zmienia jeden parametr modelu:\n\n" + md_table(tbl))
    o.append(TX.SENS_READING)
    sh = D["share"]
    o.append("### 3.4 Miasta: prędkość na odcinkach według stałych klas (środa)\n")
    o.append(TX.CLASSES)
    rows = []
    for agg in sc.AGGS:
        for band in ("am_peak", "midday", "evening"):
            x = sh[(sh["agglomeration"] == agg) & (sh["day_type"] == "weekday") & (sh["band"] == band)]
            if not len(x):
                continue
            x = x.iloc[0]
            r = {"Miasto": TRAM_CITY[agg], "Pasmo": sc.band_label("weekday", band), "Prędkość, km/h": fnum(x.speed_kmh_all_stretches)}
            for i, lab in enumerate(sc.CLASS_LABELS):
                r[lab] = pct(getattr(x, f"share_vkm_class_{i}"), 0)
            r["Ponad jazdę swobodną, s/km (przedział)"] = (f"{fnum(x.taf_s_per_km, 0)} ({fnum(x.taf_lo_s_per_km, 0)}–"
                                                          f"{fnum(x.taf_hi_s_per_km, 0)})")
            r["Wozokm na odcinkach < 5 min"] = pct(x.share_vkm_below_min_stretches)
            rows.append(r)
    o.append("Udział wozokilometrów w klasach prędkości (odcinki ≥ 5 min):\n\n" + md_table(pd.DataFrame(rows)))
    o.append("### 3.5 Najwolniejsze odcinki i największy czas ponad jazdę swobodną, szczyt poranny w środę\n")
    o.append(TX.RANK_RULE)
    rk = D["rank"]
    for agg in ("wroclaw",) + TX.RANK_CITIES:
        for kind in ("najniższa prędkość", "największy czas ponad jazdę swobodną"):
            x = rk[(rk["agglomeration"] == agg) & (rk["ranking"] == kind)]
            o.append(f"**{TRAM_CITY[agg]}: {kind}**\n\n")
            o.append(md_table(pd.DataFrame({
                "#": x["rank"], "Odcinek": x["name"], "Linie": x["lines"], "Długość, m": [fnum(v, 0) for v in x["length_m"]],
                "km/h 07–09 (±1 min)": [f"{fnum(v)} ({fnum(a)}–{fnum(b)})" for v, a, b in
                                        zip(x["speed_kmh_am_peak"], x["speed_lo_kmh_am_peak"], x["speed_hi_kmh_am_peak"])],
                "km/h 20–23": [fnum(v) for v in x["speed_kmh_evening"]],
                "Ponad jazdę swobodną, s/km (przedział)": [f"{fnum(v, 0)} ({fnum(a, 0)}–{fnum(b, 0)})" for v, a, b in
                                                           zip(x["taf_s_per_km_am_peak"], x["taf_lo_s_per_km_am_peak"],
                                                               x["taf_hi_s_per_km_am_peak"])],
                "W jezdni": [pct(v, 0) for v in x["share_street"]], "Skrzyżowania (z sygn.)": [f"{a} ({b})" for a, b in zip(x["n_road_crossings"], x["n_signalised"])],
                "Przejścia poza skrzyż.": x["n_ped_standalone"], "Rozjazdy": x["n_switches"]})))
            o.append("\n")
    o.append(TX.RANK_READING)
    o.append("Rankingi wszystkich siedmiu miast: `stretches/ranking_am_peak.csv`.\n\n")
    o.append(TX.BUS_STRETCHES)
    bq = D["busq"]
    o.append(md_table(pd.DataFrame({"Aglomeracja": [sc.AGG_NAMES[a] for a in bq["agglomeration"]], "Środek": [sc.MODE_PL[m] for m in bq["mode"]],
                                    "Odcinki × kierunki": bq["stretch_directions"], "Krótsze niż 5 min": [pct(x) for x in bq["share_directions_below_min"]],
                                    "Ich udział w wozokm": [pct(x) for x in bq["share_vkm_below_min"]],
                                    "Wozokm z geometrią z kształtu": [pct(x) for x in bq["share_vkm_geometry_shape"]]})))
    o.append(TX.BUS_READING)
    # ---- part 2
    o.append("\n## 2. Prędkość w obszarach (bloki 1 km)\n")
    o.append(TX.AREA_RULES)
    cov = D["cov"]
    rows = []
    for r in cov[(cov["day_type"] == "weekday") & (cov["band"] == "am_peak")].itertuples(index=False):
        rows.append({"Aglomeracja": sc.AGG_NAMES[r.agglomeration], "Środek": sc.MODE_PL[r.mode], "Bloki z kursami": r.blocks_with_service,
                     "Bloki z wartością": r.blocks_reported, "Wozokm w blokach z wartością": pct(r.share_vkm_in_reported_blocks),
                     "Mediana bloków, km/h": fnum(r.median_block_speed_kmh)})
    o.append("Szczyt poranny w środę:\n\n" + md_table(pd.DataFrame(rows)))
    sd = D["sdh"]
    rows = []
    for r in sd[sd["day_type"] == "weekday"].itertuples(index=False):
        rows.append({"Aglomeracja": sc.AGG_NAMES[r.agglomeration], "Środek": sc.MODE_PL[r.mode],
                     "Przejazdy pominięte (odcinek w linii prostej)": pct(r.share_hops_straight_left_out),
                     "Ich udział w długości": pct(r.share_len_straight_left_out)})
    o.append("\nPrzejazdy pominięte, bo ich droga nie jest znana (środa):\n\n" + md_table(pd.DataFrame(rows)))
    for title, df in (("gęstości zaludnienia bloku (os./km²)", D["dens"]), ("odległości od najbliższego centrum", D["ring"]),
                      ("odległości od jednego węzła (tylko do porównania z szybkim spojrzeniem)", D["hub"])):
        for mode in ("tram", "bus"):
            x = df[(df["mode"] == mode) & (df["day_type"] == "weekday") & (df["band"] == "am_peak")]
            pv = x.pivot(index="agglomeration", columns="group", values="speed_kmh")
            pv = pv[[g for g in x["group"].drop_duplicates()]]
            t = pd.DataFrame({"Aglomeracja": [sc.AGG_NAMES[a] for a in pv.index]})
            for g in pv.columns:
                t[g] = [fnum(v) for v in pv[g]]
            o.append(f"\n**{sc.MODE_PL[mode].capitalize()}, szczyt poranny w środę, według {title}, km/h**\n\n" + md_table(t))
    o.append(TX.AREA_READING)
    o.append(TX.CHECKS)
    o.append("## 5. Pliki\n")
    sz = D["sizes"]
    o.append(md_table(pd.DataFrame({"Plik": list(sz), "MB": [fnum(v, 2) for v in sz.values()]})))
    o.append(TX.WEB)
    wm = D.get("web")
    if wm:
        names = sorted(wm["sizes_mb"])
        o.append(md_table(pd.DataFrame({"Plik (results/web/speed/)": names,
                                        "Obiekty": [wm["features"].get(n) for n in names],
                                        "MB": [fnum(wm["sizes_mb"][n], 2) for n in names]})))
        o.append(f"Razem {fnum(wm['total_mb'], 2)} MB (cele: tramwaje < 1,5 MB, autobusy < 4 MB na plik, tabela linii "
                 f"< 2 MB, razem < 25 MB; przekroczone: {', '.join(wm['over_target']) or 'żaden'}).\n")
    o.append(TX.LIMITS)
    o.append(TX.UNVERIFIED)
    return "".join(x.strip("\n") + "\n\n" for x in o).rstrip("\n") + "\n"


def main() -> None:
    t0 = time.time()
    D = {"city": pd.read_csv(QA / "tables" / "speed_city_mode_band.csv"),
         "gap": pd.read_csv(QA / "tables" / "speed_peak_evening_gap.csv"),
         "chk": pd.read_csv(QA / "tables" / "tram_median_check.csv"),
         "qc": pd.read_csv(QA / "tables" / "quick_look_check.csv"),
         "lines": pd.read_csv(TB / "speed_lines.csv", dtype={"line": str}),
         "sdiag": pd.read_csv(QA / "stretches" / "stretch_diagnostics.csv"),
         "rsum": pd.read_csv(QA / "stretches" / "stretch_rounding_summary.csv"),
         "sens": pd.read_csv(QA / "stretches" / "sensitivity_kinematics.csv"),
         "share": pd.read_csv(QA / "stretches" / "city_stretch_summary.csv"),
         "rank": pd.read_csv(QA / "stretches" / "ranking_am_peak.csv"),
         "busq": pd.read_csv(QA / "stretches" / "bus_stretch_quality.csv"),
         "puls": pd.read_csv(QA / "tables" / "puls_style_city.csv"),
         "cov": pd.read_csv(QA / "areas" / "coverage.csv"),
         "sdh": pd.read_csv(QA / "areas" / "diag_straight_hops.csv"),
         "dens": pd.read_csv(QA / "areas" / "city_by_density.csv"),
         "ring": pd.read_csv(QA / "areas" / "city_by_nearest_centre.csv"),
         "hub": pd.read_csv(QA / "areas" / "city_by_hub_ring.csv")}
    files = ["tables/speed_lines.csv", "tables/speed_lines.json", "tables/tram_stretches.csv", "tables/tram_stretch_bands.csv",
             "tables/tram_stretch_stop_pairs.csv", "tables/tram_stretch_stops.csv", "tables/bus_stretches.csv",
             "layers/tram_stretches.parquet", "layers/bus_stretches.parquet", "layers/rail_metro_lines.parquet",
             "layers/speed_areas.parquet", "metrics/metrics_speed.csv", "metrics/metrics_speed.json"]
    import json
    wmp = RESULTS / "web" / "speed" / "_meta.json"
    D["web"] = json.loads(wmp.read_text(encoding="utf-8")) if wmp.exists() else None
    rows = metrics(D["city"], D["gap"], D["share"])
    write_metrics(rows)
    D["sizes"] = {f: round((RESULTS / f).stat().st_size / 1e6, 2) for f in files if (RESULTS / f).exists()}
    (QA / "speed.md").write_text(note(D), encoding="utf-8", newline="\n")
    # copy of the city x mode x band table next to the note (the CSV behind section 1)
    from pipeline import gtfs_service as gs
    inputs = sorted({f"gtfs_{f}" for a in sc.AGGS for f in gs.feeds_for(a, "all")} | {"osm_poland_pbf"})
    mp = write_meta(QA, "speed_report", inputs=inputs, started=t0,
                    extra={"timetable_dates": sc.days(), "osm_date": "2026-11-22", "sizes_mb": D["sizes"],
                           "speed_time_bands": load_config()["speed_time_bands"], "metrics_rows": len(rows)})
    import shutil
    shutil.copyfile(mp, METRICS / "_meta_speed.json")
    print(f"speed_report: {len(rows)} metric rows, {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
