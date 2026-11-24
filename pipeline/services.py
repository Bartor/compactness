"""Services as destinations (ROADMAP item 13): secondary schools (RSPO) and hospital emergency departments (RPRM).

    python -m pipeline.services fetch        # downloads into data/raw/<new dirs> (resumable, skips what exists)
    python -m pipeline.services prep         # OSM extract (once) + facilities -> data/interim/services/facilities.parquet
    python -m pipeline.services osmcheck     # OSM schools / hospitals near the register points (positional QA)

Sources
* Secondary schools: RSPO (Rejestr Szkół i Placówek Oświatowych, MEN), read through the JSON API behind the public
  search site rspo.gov.pl (``POST /api/Institution`` for the list with student numbers, ``POST
  /api/Institution/Geotag`` for coordinates).  No account; the official API host api-rspo.men.gov.pl did not resolve
  on 2026-11-24.  Types: 14 liceum ogólnokształcące, 16 technikum, 93 branżowa szkoła I stopnia; categories and
  specificity are fetched as separate queries so that each record carries them.  Lead-authority names (often natural
  persons), phone numbers and e-mails are dropped before the raw copy is written.
* Emergency departments: RPRM (Rejestr Państwowego Ratownictwa Medycznego, rprm.ezdrowie.gov.pl), public CSV export,
  unit type "Szpitalny oddział ratunkowy", status "Aktywna".  The register has addresses only.  The GUGiK address
  service (services.gugik.gov.pl/uug) answered one probe on 2026-11-24 and then returned "Request Rejected" (a web
  application firewall); it was not retried or circumvented.  Addresses are therefore geocoded on OSM
  (poland-latest.osm.pbf, already in data/raw/osm): an object with the same house number, the same last word of the street
  name and the same city or postcode (``sor``).
* OSM is otherwise used only as a positional cross-check of the register points (``osmcheck``).

Selection (``prep``)
* schools, main set: types 14/16/93, category "Dzieci lub młodzież", specificity "brak specyfiki", not liquidated,
  more than 0 students, coordinates present, not inside a closed institution (correctional facility or youth
  educational centre, by name).  Special schools (specificity "specjalna") and adult schools are kept in
  the table with ``in_main = False``.
* SOR: every active SOR; a unit whose name marks it as paediatric gets ``paediatric = True`` and is left out of the
  main set (adults cannot use it).
* A facility belongs to an agglomeration when its point lies in FUA + 15 km (the routing network extent).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.common import INTERIM, RAW, USER_AGENT, write_json

AGGS = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
OUT = INTERIM / "services"
RAW_RSPO = RAW / "rspo_secondary"
RAW_RPRM = RAW / "rprm_sor"
RSPO_API = "https://rspo.gov.pl/api/Institution"
RPRM_EXPORT = "https://rprm.ezdrowie.gov.pl/Registry/PublicExport"
SCHOOL_TYPES = {14: "liceum ogólnokształcące", 16: "technikum", 93: "branżowa szkoła I stopnia"}
CATEGORIES = {1: "Dzieci lub młodzież", 2: "Dorośli", 3: "Bez kategorii"}
SPECIFICITY = {100: "brak specyfiki", 1: "specjalna"}
H = {"User-Agent": USER_AGENT, "Accept": "application/json"}
KEEP = ["id", "rspo", "regon", "name", "liquidationDate", "creationDate", "complexInclusionDate", "studentsNr",
        "hqAddressZipCode", "hqAddressPostal", "hqAddressStreet", "hqAddressBuildingNr"]


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def log(msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ fetch
def _rspo_pages(path: str, body: dict, page: int = 100) -> list[dict]:
    import requests
    out, off = [], 0
    while True:
        for attempt in range(4):
            try:
                r = requests.post(RSPO_API + path, params={"PageOffset": off, "PageSize": page}, json=body,
                                  headers={**H, "Content-Type": "application/json"}, timeout=120)
                r.raise_for_status()
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        j = r.json()
        items = j.get("items") or []
        out += items
        off += page
        if off >= j.get("totalCount", 0) or not items:
            return out
        time.sleep(0.3)


def fetch_rspo() -> None:
    RAW_RSPO.mkdir(parents=True, exist_ok=True)
    dst = RAW_RSPO / "rspo_secondary.json"
    if dst.exists():
        log("rspo: already downloaded")
        return
    parts = RAW_RSPO / "_parts"
    parts.mkdir(exist_ok=True)
    for t in SCHOOL_TYPES:
        for c in CATEGORIES:
            for s in SPECIFICITY:
                p = parts / f"t{t}_c{c}_s{s}.json"
                if p.exists():
                    continue
                body = {"institutionTypeIdList": [t], "categoryIdList": [c], "specificityIdList": [s]}
                lst = _rspo_pages("", body)
                geo = _rspo_pages("/Geotag", body)
                gmap = {g["id"]: g.get("hqGeotag") for g in geo}
                rows = []
                for x in lst:
                    rec = {k: x.get(k) for k in KEEP}
                    rec["type_id"] = (x.get("type") or {}).get("id")
                    rec["locality"] = (x.get("hqAddressLocality") or {}).get("name")
                    g = gmap.get(x["id"]) or {}
                    rec["lat"], rec["lon"] = g.get("latitude"), g.get("longitude")
                    rec["query_type"], rec["query_category"], rec["query_specificity"] = t, c, s
                    rows.append(rec)
                p.write_text(json.dumps({"body": body, "n_list": len(lst), "n_geotag": len(geo), "items": rows},
                                        ensure_ascii=False), encoding="utf-8")
                log(f"rspo type {t} cat {c} spec {s}: {len(lst)} listed, {len(geo)} with coordinates")
    allrows, queries = [], []
    for p in sorted(parts.glob("*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        allrows += j["items"]
        queries.append({"body": j["body"], "n_list": j["n_list"], "n_geotag": j["n_geotag"]})
    tmp = dst.with_suffix(".tmp")
    tmp.write_text(json.dumps({"downloaded_at": now(), "queries": queries, "items": allrows}, ensure_ascii=False,
                              indent=0), encoding="utf-8")
    tmp.replace(dst)
    (RAW_RSPO / "SOURCE.json").write_text(json.dumps({
        "url": [RSPO_API + "?PageOffset=..&PageSize=100 (POST, JSON body)", RSPO_API + "/Geotag (POST, JSON body)"],
        "site": "https://rspo.gov.pl/ (public search of the Rejestr Szkół i Placówek Oświatowych, MEN)",
        "downloaded_at": now(), "sha256": sha(dst), "bytes": dst.stat().st_size,
        "licence": ("not stated on rspo.gov.pl; the annual bulk list of the same register on dane.gov.pl "
                    "(dataset 839, 'Wykaz szkół i placówek oświatowych') is CC BY 4.0; public register (ustawa o "
                    "systemie informacji oświatowej)"),
        "queries": "institutionTypeIdList x categoryIdList x specificityIdList, types 14, 16, 93",
        "stripped": "leadAuthorities, telephone, email, website removed before saving (personal data of operators)",
        "data_date": "state of the register on the download day",
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def fetch_rprm() -> None:
    import requests
    RAW_RPRM.mkdir(parents=True, exist_ok=True)
    dst = RAW_RPRM / "rprm_sor_active.csv"
    if dst.exists():
        log("rprm: already downloaded")
        return
    params = {"SortBy": "", "SortDirection": "Ascending", "ActionName": "Public", "ExportType": "Csv",
              "RegistryType": "", "FilterApplied": "True", "UnitType": "Szpitalny oddział ratunkowy",
              "RegistryStatus": "ACTUAL"}
    r = requests.get(RPRM_EXPORT, params=params, headers={"User-Agent": USER_AGENT}, timeout=180)
    r.raise_for_status()
    dst.with_suffix(".tmp").write_bytes(r.content)
    dst.with_suffix(".tmp").replace(dst)
    (RAW_RPRM / "SOURCE.json").write_text(json.dumps({
        "url": RPRM_EXPORT + "?" + "&".join(f"{k}={v}" for k, v in params.items()),
        "site": "https://rprm.ezdrowie.gov.pl/ (Rejestr Państwowego Ratownictwa Medycznego, public part)",
        "server_filename": r.headers.get("content-disposition"),
        "downloaded_at": now(), "sha256": sha(dst), "bytes": dst.stat().st_size,
        "licence": ("not stated on rprm.ezdrowie.gov.pl; the dane.gov.pl entry for this register (dataset 1642, "
                    "'Ewidencja szpitalnych oddziałów ratunkowych...') is CC BY 4.0; its static file there is from "
                    "2021-05-17, so the live export is used"),
        "data_date": "state of the register on the download day (status 'Aktywna')",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"rprm: {len(r.content)} bytes")


def read_rprm() -> pd.DataFrame:
    d = pd.read_csv(RAW_RPRM / "rprm_sor_active.csv", dtype=str, keep_default_na=False)
    cols = list(d.columns)
    # the export repeats the column name "Jednostka - Ulica" (prefix, then name): pandas renames the second one
    d = d.rename(columns={c: c.strip() for c in cols})
    return d


def _addr(row: pd.Series) -> str:
    street = " ".join(x for x in [row.get("Jednostka - Ulica.1", "")] if x).strip()
    num = row.get("Jednostka - Budynek", "").strip()
    city = row.get("Jednostka - Miejscowość", "").strip()
    return f"{city}, {street} {num}".strip() if street else f"{city} {num}".strip()


# ------------------------------------------------------------------ prep
def schools() -> pd.DataFrame:
    j = json.loads((RAW_RSPO / "rspo_secondary.json").read_text(encoding="utf-8"))
    d = pd.DataFrame(j["items"])
    d["type"] = d["type_id"].map(SCHOOL_TYPES)
    d["category"] = d["query_category"].map(CATEGORIES)
    d["specificity"] = d["query_specificity"].map(SPECIFICITY)
    d = d.sort_values(["id", "query_category", "query_specificity"]).drop_duplicates("id").reset_index(drop=True)
    d["has_xy"] = d["lat"].notna() & d["lon"].notna()
    d["liquidated"] = d["liquidationDate"].notna()
    d["students"] = pd.to_numeric(d["studentsNr"], errors="coerce")
    # schools inside closed institutions (correctional facilities, youth educational centres) are not open to the
    # public: left out of the main set
    d["closed_institution"] = d["name"].str.upper().str.contains(
        r"POPRAWCZ|SCHRONISK|OKRĘGOWYM OŚRODKU WYCHOWAWCZ|OKREGOWYM OSRODKU WYCHOWAWCZ", regex=True)
    d["in_main"] = ((d["query_category"] == 1) & (d["query_specificity"] == 100) & ~d["liquidated"]
                    & (d["students"].fillna(0) > 0) & d["has_xy"] & ~d["closed_institution"])
    d["kind"] = "school"
    d["geocode"] = "RSPO hqGeotag (położenie siedziby wg rejestru)"
    return d


def _norm(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _tokens(street: str) -> set[str]:
    """Meaningful street-name tokens (no initials, titles or 'ul.'), split on spaces and hyphens."""
    stop = {"ul", "al", "pl", "os", "dr", "doc", "prof", "ks", "gen", "im", "sw", "marii", "jana", "ii", "iii"}
    return {w for w in _norm(street).split() if len(w) > 2 and w not in stop}


def _num(n: str) -> str:
    m = re.search(r"(\d+)\s*([a-zA-Z]?)", str(n or ""))
    return (m.group(1) + m.group(2).lower()) if m else ""


def sor_keys() -> pd.DataFrame:
    d = read_rprm()
    out = pd.DataFrame({"id": d["Numer wpisu"], "owner": d["Nazwa podmiotu"], "unit": d["Nazwa jednostki"],
                        "city": d["Jednostka - Miejscowość"], "street": d["Jednostka - Ulica.1"],
                        "number": d["Jednostka - Budynek"], "postcode": d["Jednostka - Kod pocztowy"],
                        "teryt": d["Jednostka - Kod teryt"], "valid_from": d["Data obowiązywania od"]})
    out["address"] = [_addr(r) for _, r in d.iterrows()]
    out["num"] = out["number"].map(_num)
    out["tok"] = out["street"].map(_tokens)
    # key token: the last meaningful word of the street name (usually the surname or the noun), which must match;
    # a shared first name alone ("Macieja") is not enough
    out["key"] = out["street"].map(lambda st: ([w for w in _norm(st).split() if w in _tokens(st)] or [""])[-1])
    return out


def osm_extract() -> None:
    """One low-memory two-pass read of the Poland PBF: (a) amenity=school/college/hospital nodes and ways (way =
    mean of its node coordinates; relations not read), (b) address-tagged nodes and ways whose street token and
    house number match an SOR address of the RPRM export."""
    import osmium
    cache = OUT / "osm_objects.parquet"
    if cache.exists() and (OUT / "osm_addr_candidates.parquet").exists():
        return
    k = sor_keys()
    keyset = {(t, n) for toks, n in zip(k["tok"], k["num"]) for t in toks if n}
    am_rows, ad_rows, ways = [], [], {}
    AM = ("school", "college", "hospital")

    def addr_hit(tags) -> bool:
        hn = tags.get("addr:housenumber")
        if not hn:
            return False
        n = _num(hn)
        toks = _tokens(tags.get("addr:street") or tags.get("addr:place") or "")
        return any((t, n) in keyset for t in toks)

    def info(tags):
        return {"emergency": tags.get("emergency"), "name": tags.get("name"),
                "addr_street": tags.get("addr:street") or tags.get("addr:place"),
                "addr_number": tags.get("addr:housenumber"), "addr_city": tags.get("addr:city"),
                "addr_postcode": tags.get("addr:postcode"), "amenity": tags.get("amenity"),
                "healthcare": tags.get("healthcare"), "building": tags.get("building")}

    t0 = time.time()
    pbf = str(RAW / "osm" / "poland-latest.osm.pbf")
    # pass 1: only objects carrying amenity or addr:housenumber reach Python (filter runs in C++)
    fp = osmium.FileProcessor(pbf, osmium.osm.NODE | osmium.osm.WAY).with_filter(
        osmium.filter.KeyFilter("amenity", "addr:housenumber"))
    for o in fp:
        am = o.tags.get("amenity")
        ak = addr_hit(o.tags) if "addr:housenumber" in o.tags else False
        if not (am in AM or ak):
            continue
        if o.is_node():
            r = {"osm": f"n{o.id}", "lon": o.location.lon, "lat": o.location.lat, **info(o.tags)}
            if am in AM:
                am_rows.append(r)
            if ak:
                ad_rows.append(r)
        else:
            ways[o.id] = (info(o.tags), am in AM, ak, [nd.ref for nd in o.nodes])
    log(f"osm pass 1: {len(am_rows) + len(ad_rows)} nodes, {len(ways)} ways in {time.time() - t0:.0f} s")
    need = {r for v in ways.values() for r in v[3]}
    loc = {}
    for n in osmium.FileProcessor(pbf, osmium.osm.NODE).with_filter(osmium.filter.IdFilter(need)):
        loc[n.id] = (n.location.lon, n.location.lat)
    for wid, (inf, is_am, is_ad, refs) in ways.items():
        pts = [loc[r] for r in refs if r in loc]
        if not pts:
            continue
        r = {"osm": f"w{wid}", "lon": float(np.mean([p[0] for p in pts])), "lat": float(np.mean([p[1] for p in pts])),
             **inf}
        if is_am:
            am_rows.append(r)
        if is_ad:
            ad_rows.append(r)
    pd.DataFrame(am_rows).sort_values("osm").to_parquet(cache, index=False)
    pd.DataFrame(ad_rows).sort_values("osm").to_parquet(OUT / "osm_addr_candidates.parquet", index=False)
    log(f"osm extract: {len(am_rows)} amenity objects, {len(ad_rows)} address candidates in {time.time() - t0:.0f} s")


def sor() -> pd.DataFrame:
    """SOR units geocoded on OSM: an OSM object with the same house number, a shared street token and the same city
    or postcode; among several, a hospital-tagged one first, then the one nearest to an OSM hospital.  Units without
    such a match are left without a point and reported."""
    from pyproj import Transformer
    from scipy.spatial import cKDTree
    to2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    k = sor_keys()
    ad = pd.read_parquet(OUT / "osm_addr_candidates.parquet")
    am = pd.read_parquet(OUT / "osm_objects.parquet")
    hosp = am[am["amenity"] == "hospital"]
    hx, hy = to2180.transform(hosp["lon"].to_numpy(), hosp["lat"].to_numpy())
    htree = cKDTree(np.c_[hx, hy])
    ad["num"] = ad["addr_number"].map(_num)
    ad["tok"] = ad["addr_street"].map(_tokens)
    ad["city_n"] = ad["addr_city"].map(_norm)
    ad["x"], ad["y"] = to2180.transform(ad["lon"].to_numpy(), ad["lat"].to_numpy())
    rows = []
    for _, r in k.iterrows():
        c = ad[(ad["num"] == r["num"]) & ad["tok"].map(lambda t: r["key"] in t)] if r["key"] else ad.iloc[0:0]
        same = c[(c["city_n"] == _norm(r["city"])) | (c["addr_postcode"] == r["postcode"])]
        base = {kk: v for kk, v in r.items() if kk not in ("tok", "key")}
        if len(same) == 0:
            # fallback: an OSM hospital in the same town (addr:city or name) whose name shares words of >= 5 letters
            # with the operator's name, or whose house number equals the register's; best score wins
            cn = _norm(r["city"])
            # town named in the hospital name: compare word stems (first 6 letters) to allow Polish inflection
            # ("Trzebnica" / "w Trzebnicy"); multi-word towns need the full name
            stem = cn[:6] if " " not in cn else cn
            hc = hosp[(hosp["addr_city"].map(_norm) == cn)
                      | hosp["name"].map(_norm).str.contains(rf"\b{re.escape(stem)}", regex=True)]
            # generic words of hospital names and the town itself do not count; an exact addr:city match breaks ties
            generic = {"samodzielny", "publiczny", "zaklad", "opieki", "zdrowotnej", "szpital", "szpitale", "spolka",
                       "ograniczona", "odpowiedzialnoscia", "centrum", "medyczne", "specjalistyczny", "wojewodzki",
                       "powiatowy", "zespol", "zakladow", "kliniczny", "miejski", "imienia"}
            own = {w for w in _norm(r["owner"]).split() if len(w) >= 5 and w not in generic and not w.startswith(stem)}
            best, score = None, 0.9
            for _, h in hc.sort_values("osm").iterrows():
                sc = len(own & {w for w in _norm(h["name"]).split() if len(w) >= 5}) \
                    + 2 * (_num(h["addr_number"]) == r["num"] and r["num"] != "") \
                    + 0.5 * (_norm(h["addr_city"]) == cn) \
                    + 3 * (bool(r["key"]) and r["key"] in _tokens(h["addr_street"] or ""))
                if sc > score:
                    best, score = h, sc
            if best is not None:
                rows.append({**base, "lon": best["lon"], "lat": best["lat"], "geocode_osm": best["osm"],
                             "geocode_candidates": int(len(hc)), "dist_to_osm_hospital_m": 0.0,
                             "geocode_fallback": True})
            else:
                rows.append({**base, "lon": np.nan, "lat": np.nan, "geocode_osm": None,
                             "geocode_candidates": int(len(c)), "dist_to_osm_hospital_m": np.nan})
            continue
        dist, _ = htree.query(np.c_[same["x"], same["y"]])
        same = same.assign(dh=dist, is_h=(same["amenity"] == "hospital") | same["healthcare"].notna())
        best = same.sort_values(["is_h", "dh", "osm"], ascending=[False, True, True]).iloc[0]
        rows.append({**base, "lon": best["lon"], "lat": best["lat"], "geocode_osm": best["osm"],
                     "geocode_candidates": int(len(same)), "dist_to_osm_hospital_m": float(best["dh"])})
    s = pd.DataFrame(rows)
    s["name"] = s["owner"] + " | " + s["unit"]
    s["paediatric"] = s["unit"].str.contains(r"dzieci|dziecięc|pediatr", case=False, regex=True)
    s["has_xy"] = s["lat"].notna()
    s["in_main"] = s["has_xy"] & ~s["paediatric"]
    s["kind"] = "sor"
    s["type"] = np.where(s["paediatric"], "SOR dziecięcy", "SOR")
    s["geocode_fallback"] = s.get("geocode_fallback", pd.Series(False, index=s.index)).fillna(False).astype(bool)
    s["geocode"] = np.where(~s["has_xy"], None, np.where(
        s["geocode_fallback"], "OSM: szpital w tej miejscowości o zgodnej nazwie (zastępczo, adres niedopasowany)",
        "OSM: obiekt z tym samym adresem (punkt adresowy lub budynek)"))
    return s


def prep() -> pd.DataFrame:
    import shapely
    from pyproj import Transformer
    from pipeline.boundaries import load_agglomeration
    to2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    sc, so = schools(), sor()
    cols = ["kind", "id", "name", "type", "in_main", "has_xy", "lon", "lat", "geocode"]
    f = pd.concat([sc.assign(id=sc["id"].astype(str))[cols + ["category", "specificity", "students", "liquidated"]],
                   so[cols + ["paediatric", "address", "geocode_candidates", "dist_to_osm_hospital_m",
                            "geocode_fallback"]]],
                  ignore_index=True)
    ok = f["has_xy"]
    f["x"], f["y"] = np.nan, np.nan
    xx, yy = to2180.transform(f.loc[ok, "lon"].to_numpy(float), f.loc[ok, "lat"].to_numpy(float))
    f.loc[ok, "x"], f.loc[ok, "y"] = xx, yy
    rows = []
    for agg in AGGS:
        a = load_agglomeration(agg)
        for dom in ("buffered", "fua", "core"):
            f[f"in_{dom}"] = False
            f.loc[ok, f"in_{dom}"] = shapely.contains_xy(a[dom], f.loc[ok, "x"].to_numpy(), f.loc[ok, "y"].to_numpy())
        g = f[f["in_buffered"]].copy()
        g.insert(0, "agglomeration", agg)
        rows.append(g)
    out = pd.concat(rows, ignore_index=True).drop(columns=["in_buffered"])
    out = out.sort_values(["agglomeration", "kind", "id"]).reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT / "facilities.parquet", index=False)
    # national counts (QA)
    nat = {
        "schools_listed": int(len(sc)), "schools_with_xy": int(sc["has_xy"].sum()),
        "schools_main": int(sc["in_main"].sum()),
        "schools_by_type_main": {k: int(v) for k, v in sc[sc["in_main"]]["type"].value_counts().sort_index().items()},
        "schools_by_category": {k: int(v) for k, v in sc["category"].value_counts().sort_index().items()},
        "schools_special": int((sc["query_specificity"] == 1).sum()),
        "schools_zero_students": int((sc["students"].fillna(0) == 0).sum()),
        "schools_closed_institution": int(sc["closed_institution"].sum()),
        "sor_active": int(len(so)), "sor_geocoded": int(so["has_xy"].sum()),
        "sor_paediatric": int(so["paediatric"].sum()),
        "sor_geocoded_gt_300m_from_osm_hospital": int((so["dist_to_osm_hospital_m"] > 300).sum()),
        "sor_not_geocoded": so.loc[~so["has_xy"], "address"].tolist(),
        "sor_geocoded_fallback": so.loc[so["geocode_fallback"], "address"].tolist(),
    }
    write_json(OUT / "facilities_national.json", nat)
    log(f"prep: {nat}")
    return out


# ------------------------------------------------------------------ OSM positional check
def osmcheck() -> None:
    """Distance from each register point (in the seven regions) to the nearest OSM school / hospital object
    (nodes and way centroids from osm_extract; relations not read).  For SOR the point itself comes from OSM, so
    the distance only says whether the matched address lies on a mapped hospital site."""
    from pyproj import Transformer
    from scipy.spatial import cKDTree
    osm_extract()
    f = pd.read_parquet(OUT / "facilities.parquet")
    to2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    cache = OUT / "osm_objects.parquet"
    o = pd.read_parquet(cache)
    ox, oy = to2180.transform(o["lon"].to_numpy(), o["lat"].to_numpy())
    o["x"], o["y"] = ox, oy
    res = []
    for kind, ams in (("school", ("school", "college")), ("sor", ("hospital",))):
        oo = o[o["amenity"].isin(ams)]
        tree = cKDTree(np.c_[oo["x"], oo["y"]])
        ff = f[(f["kind"] == kind) & f["has_xy"]].drop_duplicates("id")
        dist, idx = tree.query(np.c_[ff["x"], ff["y"]])
        r = ff[["kind", "id", "name", "type", "in_main"]].copy()
        r["dist_osm_m"] = np.round(dist, 1)
        r["osm_name"] = oo["name"].to_numpy()[idx]
        r["osm_emergency"] = oo["emergency"].to_numpy()[idx]
        res.append(r)
    r = pd.concat(res, ignore_index=True)
    r.to_csv(OUT / "osm_distance.csv", index=False, lineterminator="\n")
    s = {k: {"n": int(len(g)), "le_100m": float((g["dist_osm_m"] <= 100).mean()),
             "le_250m": float((g["dist_osm_m"] <= 250).mean()), "gt_500m": int((g["dist_osm_m"] > 500).sum()),
             "median_m": float(g["dist_osm_m"].median())} for k, g in r[r["in_main"]].groupby("kind")}
    write_json(OUT / "osm_distance_summary.json", s)
    log(f"osmcheck: {s}")


def sorcheck() -> pd.DataFrame:
    """OSM hospitals tagged emergency=yes inside each FUA with no register SOR point within 500 m (candidates for a
    missing or inactive register entry; the OSM tag also covers admission rooms, so this is a list to check, not a
    correction)."""
    import shapely
    from pyproj import Transformer
    from scipy.spatial import cKDTree
    from pipeline.boundaries import load_agglomeration
    t = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    o = pd.read_parquet(OUT / "osm_objects.parquet")
    h = o[(o["amenity"] == "hospital") & (o["emergency"] == "yes")].copy()
    h["x"], h["y"] = t.transform(h["lon"].to_numpy(), h["lat"].to_numpy())
    f = pd.read_parquet(OUT / "facilities.parquet")
    s = f[f["kind"] == "sor"]
    rows = []
    for agg in AGGS:
        g = load_agglomeration(agg)
        hh = h[shapely.contains_xy(g["fua"], h["x"].to_numpy(), h["y"].to_numpy())]
        ss = s[s["agglomeration"] == agg]
        d, _ = cKDTree(np.c_[ss["x"], ss["y"]]).query(np.c_[hh["x"], hh["y"]])
        for (_, r), dd in zip(hh.iterrows(), d):
            rows.append({"agglomeration": agg, "osm": r["osm"], "name": r["name"], "lon": r["lon"], "lat": r["lat"],
                         "dist_to_register_sor_m": round(float(dd)), "no_register_sor_within_500m": bool(dd > 500)})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "sor_osm_crosscheck.csv", index=False, lineterminator="\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "prep", "osmcheck", "sorcheck"])
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch_rspo()
        fetch_rprm()
    elif a.cmd == "prep":
        osm_extract()
        prep()
    elif a.cmd == "osmcheck":
        osmcheck()
    else:
        sorcheck()


if __name__ == "__main__":
    main()
