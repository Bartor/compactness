"""The 15 suburban public-transport-versus-car pairs of the NIK audit P/25/019 ("Transport zbiorowy w miastach"),
public-transport side routed in R5 on the 2026-11-25 timetables (run through pipeline.trips_sample nik).

What NIK states (Informacja o wynikach kontroli, p. 29; infographic 5, p. 17): times from a public map application
with real-time journey planning, recorded on five days in the morning peak (to the city) and the afternoon peak
(from the city), between the gmina office ("urząd gminy") and the city centre; distance, hour and the shortest and
longest time were recorded.  The infographic gives one PT and one car time per gmina without saying which of these
(direction, day, shortest or longest) it is.  The exact city-centre point is not given.

Our side
* Gmina end: the gmina office as mapped in OpenStreetMap (poland-latest.osm.pbf, 2026-11-22; amenity=townhall or office=government
  with the office's name, object ids below).  Gminas whose office was not found in OSM are not reproduced (no coordinates are invented).
* City end: two variants, the project's centre and hub points from config.yaml (NIK's point is unknown).
* Morning: gmina office -> city, departures every minute 07:00-09:00; afternoon: city -> gmina office, 16:00-18:00.
  R5 regional path results, same parameters as the production transit run (walk 5 km/h, access and egress
  <= 12 min, up to 8 rides, all feeds), trip limit 120 min.  Reported: fastest, median and slowest departure minute.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from pipeline.common import load_config
from pipeline.trips_sample import OUT, QA, load_network, log, pointset, wait_for_memory

CFG = load_config()

# gmina, agglomeration, NIK PT min, NIK car min, OSM object, OSM name / address, lon, lat (None = not found in OSM)
PAIRS = [
    ("Łomianki", "warszawa", 59, 41, "w149628551", "Urząd Miasta i Gminy Łomianki, Warszawska 115", 20.886558, 52.340566),
    ("Nadarzyn", "warszawa", 56, 33, "w705756976", "Urząd Gminy Nadarzyn, Mszczonowska 24", 20.800272, 52.090086),
    ("Piaseczno", "warszawa", 51, 46, "w5857806", "Urząd Miasta i Gminy Piaseczno, Kościuszki 5", 21.027931, 52.073741),
    ("Marki", "warszawa", 34, 40, "w162060277", "Urząd Miasta Marki, al. Piłsudskiego 95", 21.107328, 52.326691),
    ("Sulejówek", "warszawa", 32, 42, "n12920327401", "Urząd Miasta Sulejówek, Dworcowa 55", 21.279032, 52.246312),
    ("Wielka Wieś", "krakow", 40, 21, "w403023531", "Urząd Gminy Wielka Wieś, pl. Wspólnoty 1, Szyce (office=government)", 19.862744, 50.140234),
    ("Liszki", "krakow", 49, 31, "w216573524", "Urząd Gminy Liszki, Mały Rynek 2 (office=government)", 19.766094, 50.038063),
    ("Niepołomice", "krakow", 50, 38, "w243798093", "Ratusz, pl. Zwycięstwa 13, Niepołomice", 20.215495, 50.033238),
    ("Skawina", "krakow", 31, 34, "w337039194", "Urząd Miasta i Gminy Skawina, Rynek 1 (office=government)", 19.825806, 49.975515),
    ("Wieliczka", "krakow", 25, 33, "w114724141", "Urząd Miasta i Gminy, Powstania Warszawskiego 1, Wieliczka", 20.059099, 49.984625),
    ("Tarnowo Podgórne", "poznan", 46, 29, "n4511876280", "Urząd Gminy Tarnowo Podgórne, Poznańska 115", 16.658874, 52.463586),
    ("Murowana Goślina", "poznan", 42, 42, "w362561806", "Urząd Miasta i Gminy Murowana Goślina, pl. Powstańców Wielkopolskich 9", 17.010754, 52.575731),
    ("Swarzędz", "poznan", 26, 26, "w42262659", "Urząd Miasta i Gminy w Swarzędzu, Rynek 1", 17.077701, 52.410275),
    ("Kórnik", "poznan", 37, 36, "n9645541262", "Urząd Miasta i Gminy w Kórniku, pl. Niepodległości 1", 17.08948, 52.247216),
    ("Stęszew", "poznan", 36, 37, "n1499474214", "Urząd Miejski Gminy Stęszew (punkt OSM bez adresu)", 16.702284, 52.280327),
]
WINDOWS = {"rano_do_miasta": (7 * 3600, 9 * 3600), "popoludnie_z_miasta": (16 * 3600, 18 * 3600)}
MAX_MIN = 120


def _minutes(task, jnet, olon, olat, dlon, dlat, t0: int, t1: int) -> dict[int, tuple[int, int, str]]:
    """Best (seconds, rides, routes) per departure minute."""
    import com.conveyal.r5
    import jpype
    t = task.clone()
    t.fromLat, t.fromLon = float(olat), float(olon)
    t.destinationPointSets = jpype.JArray(com.conveyal.r5.analyst.PointSet)([pointset([dlon], [dlat])])
    t.includePathResults = True
    t.fromTime, t.toTime = t0, t1
    t.maxTripDurationMinutes = MAX_MIN
    res = com.conveyal.r5.analyst.TravelTimeComputer(t, jnet).computeTravelTimes()
    mm = res.paths.iterationsForPathTemplates[0]
    tl = jnet.transitLayer
    best: dict[int, tuple[int, int, str]] = {}
    if mm is None:
        return best
    for rs in mm.keySet():
        if rs.routes is None:
            nr, lab = 0, "pieszo"
        else:
            rr = list(rs.routes.toArray())
            nr = len(rr)
            lab = " + ".join(str(tl.routes.get(r).route_short_name or tl.routes.get(r).route_id) for r in rr)
        for it in mm.get(rs):
            m = int(it.departureTime)
            v = (int(it.totalTime), nr, lab)
            if m not in best or v[:2] < best[m][:2]:
                best[m] = v
    return best


def route_nik() -> None:
    import geopandas as gpd
    from pipeline.access import make_task
    from pipeline import access_inputs as AI
    rows = []
    for agg in ["warszawa", "krakow", "poznan"]:
        pairs = [p for p in PAIRS if p[1] == agg]
        ends = {"centrum": CFG["agglomerations"][agg]["centre"], "węzeł": CFG["agglomerations"][agg]["hub"]}
        todo = [p for p in pairs if p[6] is not None]
        if todo:
            wait_for_memory()
            tn = load_network(agg)
            jnet = tn._transport_network
            d = AI.destinations(agg).iloc[:10]
            lon, lat = AI.TO4326.transform(d["x"].to_numpy(), d["y"].to_numpy())
            task, _ = make_task(tn, gpd.GeoDataFrame({"id": d["cell_id"].to_numpy()},
                                                     geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326"), "pt_am")
        for g, _, nik_pt, nik_car, osm, addr, glon, glat in pairs:
            base = {"gmina": g, "agglomeration": agg, "nik_pt_min": nik_pt, "nik_car_min": nik_car, "osm_object": osm,
                    "gmina_point": addr, "gmina_lon": glon, "gmina_lat": glat}
            if glon is None:
                rows.append({**base, "status": "nie odtworzono: urzędu gminy nie ma w OSM jako amenity=townhall"})
                continue
            for ek, e in ends.items():
                for wk, (t0, t1) in WINDOWS.items():
                    if wk.startswith("rano"):
                        b = _minutes(task, jnet, glon, glat, e["lon"], e["lat"], t0, t1)
                    else:
                        b = _minutes(task, jnet, e["lon"], e["lat"], glon, glat, t0, t1)
                    n = (t1 - t0) // 60
                    v = np.array([b[m][0] / 60 for m in sorted(b)]) if b else np.array([])
                    fastest = min(b.items(), key=lambda kv: kv[1][:2]) if b else None
                    rows.append({**base, "city_point": f"{e['name']} ({ek})", "city_lon": e["lon"], "city_lat": e["lat"],
                                 "window": wk, "minutes_with_path": len(b), "minutes_in_window": int(n),
                                 "r5_min": round(float(v.min()), 1) if len(v) else None,
                                 "r5_median": round(float(np.median(v)), 1) if len(v) else None,
                                 "r5_max": round(float(v.max()), 1) if len(v) else None,
                                 "r5_fastest_departure": f"{fastest[0] // 3600:02d}:{fastest[0] // 60 % 60:02d}" if fastest else None,
                                 "r5_fastest_lines": fastest[1][2] if fastest else None,
                                 "r5_fastest_rides": fastest[1][1] if fastest else None,
                                 "status": "ok" if len(v) else "brak trasy w 120 min"})
            log(f"NIK {g}: routed")
    df = pd.DataFrame(rows)
    QA.mkdir(parents=True, exist_ok=True)
    f = OUT / "nik_routed.csv"
    df.to_csv(f.with_suffix(".tmp"), index=False, lineterminator="\n")
    os.replace(f.with_suffix(".tmp"), f)
    log(f"NIK: {len(df)} rows -> {f}")
