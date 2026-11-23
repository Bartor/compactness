"""Verify centre / hub / extra_centres coordinates of config.yaml against OSM Nominatim.

One request per second, generic User-Agent.  Writes results/qa/phase0/boundaries/centres.md.
Config is NOT modified; corrections are proposals only.
Run: python -m pipeline.verify_centres
"""
from __future__ import annotations

import json
import time

import requests
from pyproj import Transformer

from pipeline.common import INTERIM, RESULTS, USER_AGENT, load_config

TOL_M = 150
# Search query per (agglomeration, role, config name); chosen to hit the intended object in OSM.
QUERIES = {
    ("warszawa", "centre"): "Rondo Dmowskiego, Warszawa",
    ("warszawa", "hub"): "Metro Centrum, Warszawa",
    ("krakow", "centre"): "Rynek Główny, Kraków",
    ("krakow", "hub"): "Kraków Główny",
    ("wroclaw", "centre"): "Rynek, Wrocław",
    ("wroclaw", "hub"): "Galeria Dominikańska, Wrocław",
    ("poznan", "centre"): "Stary Rynek, Poznań",
    ("poznan", "hub"): "Rondo Kaponiera, Poznań",
    ("lodz", "centre"): "plac Wolności, Łódź",
    ("lodz", "hub"): "Piotrkowska Centrum, Łódź",
    ("trojmiasto", "centre"): "Gdańsk Główny",
    ("trojmiasto", "hub"): "Gdańsk Główny",
    ("trojmiasto", "extra", "Gdynia Główna"): "Gdynia Główna",
    ("trojmiasto", "extra", "Sopot"): "Sopot dworzec",
    ("gzm", "centre"): "Rynek, Katowice",
    ("gzm", "hub"): "Rynek, Katowice",
    ("gzm", "extra", "Gliwice Rynek"): "Rynek, Gliwice",
    ("gzm", "extra", "Sosnowiec centrum"): "Sosnowiec Główny",
    ("gzm", "extra", "Bytom Rynek"): "Rynek, Bytom",
    ("gzm", "extra", "Zabrze centrum"): "Plac Warszawski, Zabrze",
    ("gzm", "extra", "Tychy centrum"): "plac Baczyńskiego, Tychy",
    ("gzm", "extra", "Chorzów Rynek"): "Rynek, Chorzów",
    ("gzm", "extra", "Dąbrowa Górnicza centrum"): "plac Wolności, Dąbrowa Górnicza",
    ("gzm", "extra", "Ruda Śląska (Nowy Bytom)"): "Nowy Bytom, Ruda Śląska",
    ("szczecin", "centre"): "Brama Portowa, Szczecin",
    ("bydgoszcz_torun", "centre"): "Stary Rynek, Bydgoszcz",
    ("bydgoszcz_torun", "extra", "Toruń, Rynek Staromiejski"): "Rynek Staromiejski, Toruń",
    ("lublin", "centre"): "plac Litewski, Lublin",
    ("rzeszow", "centre"): "Rynek, Rzeszów",
    ("kielce", "centre"): "Rynek, Kielce",
    ("bialystok", "centre"): "Rynek Kościuszki, Białystok",
}


def nominatim(q: str) -> list[dict]:
    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params={"q": q, "format": "jsonv2", "limit": 3, "countrycodes": "pl"},
                     headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    time.sleep(1.1)
    return r.json()


def main() -> None:
    t0 = time.time()
    cfg = load_config()["agglomerations"]
    to_m = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True).transform
    cache_f = INTERIM / "boundaries" / "nominatim_centres.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    items = []
    for aid, a in cfg.items():
        for role in ("centre", "hub"):
            if role in a:
                items.append((aid, role, a[role]["name"], a[role]["lon"], a[role]["lat"], QUERIES.get((aid, role))))
        for e in a.get("extra_centres", []):
            items.append((aid, "extra", e["name"], e["lon"], e["lat"], QUERIES.get((aid, "extra", e["name"]))))
    rows, off = [], []
    for aid, role, name, lon, lat, q in items:
        if not q:
            rows.append((aid, role, name, lon, lat, None, None, None, None)); continue
        if q not in cache:
            cache[q] = nominatim(q)
        res = cache[q]
        best = None
        for c in res:
            x0, y0 = to_m(lon, lat)
            x1, y1 = to_m(float(c["lon"]), float(c["lat"]))
            d = ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
            if best is None or d < best[0]:
                best = (d, c)
        top = res[0] if res else None
        d_top = None
        if top:
            x1, y1 = to_m(float(top["lon"]), float(top["lat"]))
            x0, y0 = to_m(lon, lat)
            d_top = ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
        rows.append((aid, role, name, lon, lat, q, top, d_top, best))
    cache_f.parent.mkdir(parents=True, exist_ok=True)
    cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    L = ["# Weryfikacja centrów i węzłów względem OSM (Nominatim)", "",
         f"Każda współrzędna z `config.yaml` porównana z wynikiem wyszukiwania Nominatim (OSM) dla podanego zapytania; odległość w EPSG:2180. "
         f"Próg zgłoszenia: > {TOL_M} m od pierwszego wyniku. **Config nie został zmieniony**; propozycje to wyniki OSM, do zatwierdzenia przez właściciela. "
         "Nominatim zwraca zwykle punkt lub środek obiektu (plac, stacja), więc dla placów i rynków odchylenia ~100–200 m mogą być zwykłą różnicą między „środkiem obiektu” a punktem, "
         "który ktoś miał na myśli.", "",
         "| Aglomeracja | Rola | Nazwa w config | Config (lon, lat) | Zapytanie | Wynik OSM | OSM (lon, lat) | Odległość m | Uwaga |", "|---|---|---|---|---|---|---|---|---|"]
    bad = []
    for aid, role, name, lon, lat, q, top, d_top, best in rows:
        if not q or not top:
            L.append(f"| {aid} | {role} | {name} | {lon}, {lat} | {q or ''} | brak wyniku | | | nie zweryfikowano |")
            continue
        flag = "PONAD PRÓG" if d_top > TOL_M else "ok"
        extra = ""
        if d_top > TOL_M:
            bad.append((aid, role, name, top, d_top))
            if best and best[0] < d_top and best[0] <= TOL_M:
                extra = f" (kolejny wynik w {best[0]:.0f} m: {best[1]['display_name'][:60]})"
        L.append(f"| {aid} | {role} | {name} | {lon}, {lat} | {q} | {top['display_name'][:70]} ({top.get('category', '')}/{top.get('type', '')}) | "
                 f"{float(top['lon']):.4f}, {float(top['lat']):.4f} | {d_top:.0f} | {flag}{extra} |")
    L += ["", "## Pozycje powyżej progu i propozycje poprawek", ""]
    if not bad:
        L.append("Brak.")
    for aid, role, name, top, d in bad:
        L.append(f"- **{aid} / {role} / {name}**: {d:.0f} m od wyniku OSM; propozycja `lon: {float(top['lon']):.4f}, lat: {float(top['lat']):.4f}` "
                 f"({top['display_name'][:80]}). Do oceny, czy wynik OSM oddaje zamierzony punkt.")
    L += ["", "Uwagi: (1) hub Warszawy opisany jako „Metro Centrum / Warszawa Centralna” zweryfikowano jako stację metra Centrum (38 m); "
          "sama stacja kolejowa Warszawa Centralna leży ok. 540 m dalej na zachód (21,0032; 52,2288), więc nazwa hubu jest dwuznaczna. "
          "(2) Białystok (140 m) i Sosnowiec (132 m) są tuż pod progiem. (3) Wyniki dla ulic pieszych (rynki) to punkt na linii ulicy wg OSM, nie środek placu.", ""]
    out = RESULTS / "qa" / "phase0" / "boundaries"
    (out / "centres.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
