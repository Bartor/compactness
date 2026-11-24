"""Catalog entries of the scheduled-speed overlay (three layers of kind "lines") for results/web/catalog.json.

    python -m pipeline.speed_catalog

The map files themselves are written by pipeline.speed_web (results/web/speed/). Colour is the property "v_<variant>"
(km/h in the fixed classes of speed_core.CLASS_BREAKS), width "t_<variant>" (trips per hour); the variant keys are the
time bands of config.yaml's speed_time_bands. Buses are one file per agglomeration (url_template), loaded for the
selected city only. Speeds are scheduled, never measured.
"""
from __future__ import annotations

import json
import time

from pipeline.common import RESULTS, load_config, write_json, write_meta

WEB = RESULTS / "web"
QA = RESULTS / "qa" / "speed_catalog"

ENTRIES = json.loads(r'''
[
  {
    "id": "speed_tram",
    "title": "Prędkość z rozkładu: tramwaje (odcinki)",
    "chip": "tramwaje",
    "kind": "lines",
    "type": "geojson",
    "url": "data/speed/trams.geojson",
    "status": "ready",
    "mode_group": "tram",
    "property": "v",
    "size_property": "t",
    "size_stops": [
      4,
      8,
      15,
      30
    ],
    "size_label": "kursy na godzinę w paśmie",
    "unit": "km/h, z rozkładu (rozkładowa prędkość komunikacyjna)",
    "variants": [
      {
        "key": "w_am",
        "label": "śr. 07–09"
      },
      {
        "key": "w_md",
        "label": "śr. 09–15"
      },
      {
        "key": "w_pm",
        "label": "śr. 15–18"
      },
      {
        "key": "w_ee",
        "label": "śr. 18–20"
      },
      {
        "key": "w_ev",
        "label": "śr. 20–23"
      },
      {
        "key": "w_e",
        "label": "śr. 05–07"
      },
      {
        "key": "w_n",
        "label": "śr. noc"
      },
      {
        "key": "w_all",
        "label": "śr. doba"
      },
      {
        "key": "s_mo",
        "label": "sob. 05–09"
      },
      {
        "key": "s_d",
        "label": "sob. 09–18"
      },
      {
        "key": "s_ev",
        "label": "sob. 18–23"
      },
      {
        "key": "s_n",
        "label": "sob. noc"
      },
      {
        "key": "s_all",
        "label": "sob. doba"
      }
    ],
    "ramp": {
      "stops": [
        12,
        15,
        18,
        22,
        26
      ],
      "colors": [
        "#5B1A8C",
        "#952C80",
        "#C73E73",
        "#EF6A5A",
        "#FBA45C",
        "#FCE38A"
      ],
      "labels": [
        "poniżej 12 km/h",
        "12–15 km/h",
        "15–18 km/h",
        "18–22 km/h",
        "22–26 km/h",
        "26 km/h i więcej"
      ]
    },
    "population_date": null,
    "attribution": "wydawcy rozkładów jazdy (lista w „O danych”), © współtwórcy OpenStreetMap",
    "note": "Sieć tramwajowa podzielona na odcinki między ważnymi przystankami; kolor to prędkość z rozkładu jazdy (długość przez czas rozkładowy, z postojami na przystankach) w wybranym paśmie, grubość to liczba kursów na godzinę. Każdy kierunek jest narysowany po swojej prawej stronie. To rozkład, nie pomiar: rzeczywiste prędkości mogą być niższe. Rozkład podaje pełne minuty, więc prędkość odcinka ma przedział ±1 min (w okienku); odcinki krótsze niż 5 min są przerywane. W okienku także czas ponad jazdę swobodną w s/km: liczba z prostego modelu, nie pomiar strat na światłach."
  },
  {
    "id": "speed_bus",
    "title": "Prędkość z rozkładu: autobusy i trolejbusy (odcinki)",
    "chip": "autobusy",
    "kind": "lines",
    "type": "geojson",
    "url_template": "data/speed/bus_{agg}.geojson",
    "cities": [
      "warszawa",
      "krakow",
      "wroclaw",
      "poznan",
      "lodz",
      "trojmiasto",
      "gzm"
    ],
    "needs_city": true,
    "status": "ready",
    "mode_group": "bus",
    "property": "v",
    "size_property": "t",
    "size_stops": [
      4,
      8,
      15,
      30
    ],
    "size_label": "kursy na godzinę w paśmie",
    "unit": "km/h, z rozkładu (rozkładowa prędkość komunikacyjna)",
    "variants": [
      {
        "key": "w_am",
        "label": "śr. 07–09"
      },
      {
        "key": "w_md",
        "label": "śr. 09–15"
      },
      {
        "key": "w_pm",
        "label": "śr. 15–18"
      },
      {
        "key": "w_ee",
        "label": "śr. 18–20"
      },
      {
        "key": "w_ev",
        "label": "śr. 20–23"
      },
      {
        "key": "w_e",
        "label": "śr. 05–07"
      },
      {
        "key": "w_n",
        "label": "śr. noc"
      },
      {
        "key": "w_all",
        "label": "śr. doba"
      },
      {
        "key": "s_mo",
        "label": "sob. 05–09"
      },
      {
        "key": "s_d",
        "label": "sob. 09–18"
      },
      {
        "key": "s_ev",
        "label": "sob. 18–23"
      },
      {
        "key": "s_n",
        "label": "sob. noc"
      },
      {
        "key": "s_all",
        "label": "sob. doba"
      }
    ],
    "ramp": {
      "stops": [
        12,
        15,
        18,
        22,
        26
      ],
      "colors": [
        "#5B1A8C",
        "#952C80",
        "#C73E73",
        "#EF6A5A",
        "#FBA45C",
        "#FCE38A"
      ],
      "labels": [
        "poniżej 12 km/h",
        "12–15 km/h",
        "15–18 km/h",
        "18–22 km/h",
        "22–26 km/h",
        "26 km/h i więcej"
      ]
    },
    "population_date": null,
    "attribution": "wydawcy rozkładów jazdy (lista w „O danych”)",
    "note": "Odcinki sieci autobusowej i trolejbusowej wybranej aglomeracji (feedy oficjalne z kształtami tras; bez Krakowa „ald”, który nie ma kształtów). Kolor to prędkość z rozkładu w paśmie, grubość to kursy na godzinę. Sieć autobusowa ma dużo rozgałęzień, więc wiele odcinków jest krótszych niż 5 minut (linia przerywana): ich prędkość mocno zależy od zaokrąglenia rozkładu. To rozkład, nie pomiar."
  },
  {
    "id": "speed_rail",
    "title": "Prędkość z rozkładu: metro i kolej (linie)",
    "chip": "metro i kolej",
    "kind": "lines",
    "type": "geojson",
    "url": "data/speed/rail.geojson",
    "status": "ready",
    "mode_group": "rail",
    "property": "v",
    "size_property": "t",
    "size_stops": [
      4,
      8,
      15,
      30
    ],
    "size_label": "kursy na godzinę w paśmie",
    "unit": "km/h, z rozkładu",
    "variants": [
      {
        "key": "w_am",
        "label": "śr. 07–09"
      },
      {
        "key": "w_md",
        "label": "śr. 09–15"
      },
      {
        "key": "w_pm",
        "label": "śr. 15–18"
      },
      {
        "key": "w_ee",
        "label": "śr. 18–20"
      },
      {
        "key": "w_ev",
        "label": "śr. 20–23"
      },
      {
        "key": "w_e",
        "label": "śr. 05–07"
      },
      {
        "key": "w_n",
        "label": "śr. noc"
      },
      {
        "key": "w_all",
        "label": "śr. doba"
      },
      {
        "key": "s_mo",
        "label": "sob. 05–09"
      },
      {
        "key": "s_d",
        "label": "sob. 09–18"
      },
      {
        "key": "s_ev",
        "label": "sob. 18–23"
      },
      {
        "key": "s_n",
        "label": "sob. noc"
      },
      {
        "key": "s_all",
        "label": "sob. doba"
      }
    ],
    "ramp": {
      "stops": [
        12,
        15,
        18,
        22,
        26
      ],
      "colors": [
        "#5B1A8C",
        "#952C80",
        "#C73E73",
        "#EF6A5A",
        "#FBA45C",
        "#FCE38A"
      ],
      "labels": [
        "poniżej 12 km/h",
        "12–15 km/h",
        "15–18 km/h",
        "18–22 km/h",
        "22–26 km/h",
        "26 km/h i więcej"
      ]
    },
    "population_date": null,
    "attribution": "wydawcy rozkładów jazdy (lista w „O danych”)",
    "note": "Jedna linia metra lub kolei to jeden przebieg (najczęstszy wzorzec przystanków w środę, przycięty do obszaru funkcjonalnego + 15 km) z prędkością całej linii w paśmie. Dla kolei „linia” to oznaczenie z rozkładu (często kategoria pociągu wspólna dla wielu relacji), więc to przybliżenie. To rozkład, nie pomiar."
  }
]
''')


def catalog_entries(cfg: dict) -> dict[str, dict]:
    day, sat = cfg["reference_day"], cfg.get("reference_saturday")
    out = {}
    for e in ENTRIES:
        e = dict(e)
        lid = e.pop("id")
        e["timetable_date"] = day
        e["timetable_dates"] = {"weekday": day, "saturday": sat}
        out[lid] = e
    return out


def update_catalog(entries: dict[str, dict]) -> bool:
    """Upsert the entries as one block, where the first of them was or at the end. False if the catalog is missing."""
    path = WEB / "catalog.json"
    if not path.exists():
        print("  results/web/catalog.json is missing (run pipeline.phase0_boundaries): catalog not updated")
        return False
    cat = json.loads(path.read_text(encoding="utf-8"))
    first = next((i for i, l in enumerate(cat["layers"]) if l["id"] in entries), None)
    others = [l for l in cat["layers"] if l["id"] not in entries]
    at = len(others) if first is None else sum(1 for l in cat["layers"][:first] if l["id"] not in entries)
    block = [{"id": lid, **e} for lid, e in entries.items()]
    cat["layers"] = others[:at] + block + others[at:]
    write_json(path, cat)
    return True


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    entries = catalog_entries(cfg)
    missing = [e["url"] for e in entries.values() if "url" in e and not (WEB / e["url"].removeprefix("data/")).exists()]
    done = update_catalog(entries)
    write_meta(QA, "speed_catalog", inputs=[], started=t0, extra={
        "catalog_layers": list(entries), "catalog_updated": done, "missing_files": missing})
    print(f"speed_catalog: {len(entries)} layers, catalog updated {done}, missing files {missing}")


if __name__ == "__main__":
    main()
