"""Travel-survey context per agglomeration (ROADMAP item 6): the latest household travel survey (KBR) figures, as
published, each value with its source and page / table.

    python -m pipeline.survey_context        # results/web/survey_context.json, results/qa/survey_context/

Nothing here is computed, interpolated or read from memory: every number was read on 2026-11-24 from the page or
PDF named in its ``src`` / ``loc`` (the research notes in research_notes/ and results/qa/phase0/research/
kbr_modal_split.md point to the same pages).  A value the source does not give is null.  Shares are in per cent of
the base stated in ``base``; bases differ between cities (all trips vs non-walking trips, trip >= 100 m vs >= 250 m,
main mode vs every mode used), which is why ``comparability`` is part of every record.
"""
from __future__ import annotations

import time

from pipeline.common import RESULTS, write_json, write_meta

OUT_WEB = RESULTS / "web" / "survey_context.json"
QA = RESULTS / "qa" / "survey_context"
ACCESSED = "2026-11-24"
VERSION = "survey_context-2026-11-24.1"

S = {
    "wro": {"title": "Kompleksowe Badanie Ruchu 2024 we Wrocławiu i gminach sąsiednich: wyniki (wroclaw.pl, 03.12.2024)",
            "url": "https://www.wroclaw.pl/komunikacja/kompleksowe-badanie-ruchu-2024-we-wroclawiu-i-gminach-sasiednich-wyniki",
            "primary": True},
    "gda": {"title": "Gdańskie Badania Ruchu 2022, Raport 3a: opracowanie wyników badań i pomiarów (Biuro Rozwoju Gdańska)",
            "url": "https://www.brg.gda.pl/attachments/article/1905/Raport-3a---opracowanie-wynikow-badan-i-pomiarow.pdf",
            "primary": True},
    "gda_press": {"title": "Rzadziej korzystamy z komunikacji miejskiej i rowerów. Auto liderem badań ruchu w Gdańsku (trojmiasto.pl, 18.06.2023)",
                  "url": "https://www.trojmiasto.pl/wiadomosci/Rzadziej-korzystamy-z-komunikacji-miejskiej-i-rowerow-Auto-liderem-badan-ruchu-w-Gdansku-n179086.html",
                  "primary": False},
    "krk": {"title": "Kompleksowe Badania Ruchu w Krakowskim Obszarze Metropolitalnym (KBR 2023), BIP Kraków",
            "url": "https://www.bip.krakow.pl/?sub_dok_id=184386", "primary": True},
    "poz": {"title": "Badanie ankietowe i aktualizacja modelu ruchu: synteza opracowania (Poznań, listopad 2019)",
            "url": "https://www.poznan.pl/mim/public/komunikacja/attachments.att?co=show&instance=1017&parent=107729&lang=pl&id=348807",
            "primary": True},
    "poz_new": {"title": "W Poznaniu i metropolii rozpoczęły się Kompleksowe Badania Ruchu (ZTM Poznań, 16.11.2026)",
                "url": "https://www.ztm.poznan.pl/aktualnosci/pozostale/w-poznaniu-i-metropolii-rozpoczely-sie-kompleksowe-badania-ruchu/",
                "primary": True},
    "waw": {"title": "Warszawskie Badanie Ruchu (warszawa19115.pl, aktualizacja 21.04.2026)",
            "url": "https://warszawa19115.pl/-/warszawskie-badanie-ruchu", "primary": True},
    "lodz": {"title": "Kierowcy i pasażerowie pod lupą. W Łodzi rozpoczęły się kompleksowe badania ruchu (tulodz.pl, 08.10.2026)",
             "url": "https://tulodz.pl/wiadomosci-lodz/kierowcy-i-pasazerowie-pod-lupa-w-lodzi-rozpoczely-sie-kompleksowe-badania-ruchu/cqxUjH69RYX52cDHDSIL",
             "primary": False},
    "gzm": {"title": "InfoGZM: opracowania GZM (pomiar kordonowy 2024; brak badania ankietowego gospodarstw)",
            "url": "https://infogzm.metropoliagzm.pl/publikacje/opracowania-gzm/", "primary": True},
}


def v(value, src: str, loc: str, note: str | None = None) -> dict:
    d = {"v": value, "src": src, "loc": loc}
    if note:
        d["note"] = note
    return d


NULL_SPLIT = {"walk": None, "bike": None, "pt": None, "car": None, "other": None}

RECORDS: dict[str, dict] = {
    "wroclaw": {
        "status": "published",
        "survey": "Kompleksowe Badanie Ruchu 2024 (3. edycja)",
        "year": v(2024, "wro", "strona, akapit wstępny"),
        "area": "Wrocław i 9 gmin sąsiednich; ok. 10,5 tys. ankiet",
        "trip_definition": v("każde przemieszczenie osoby powyżej 6. roku życia na odległość co najmniej 100 m w dniu roboczym",
                             "wro", "strona, opis metody"),
        "base": "wszystkie podróże (pieszo wliczone); strona nie mówi wprost, czy tylko mieszkańców Wrocławia",
        "modal_split": {
            "walk": v(33.1, "wro", "strona, podział zadań przewozowych 2024"),
            "bike": v(4.7, "wro", "strona, podział zadań przewozowych 2024"),
            "pt": v(21.6, "wro", "strona, podział zadań przewozowych 2024"),
            "car": v(39.8, "wro", "strona, podział zadań przewozowych 2024"),
            "other": v(0.8, "wro", "strona, podział zadań przewozowych 2024", "hulajnoga"),
        },
        "avg_trip_min": v(23, "wro", "strona: „Pojedyncza podróż mieszkańca Wrocławia trwa średnio 23 minuty”", "wszystkie środki"),
        "avg_trip_min_pt": None,
        "trips_per_person": v(1.7, "wro", "strona, ruchliwość"),
        "pt_transfer_share": None,
        "previous": {"year": 2018, "pt": v(27.6, "wro", "strona, porównanie z 2018 r.")},
        "comparability": "Wszystkie podróże od 100 m, z pieszymi. Najbliżej Gdańska i Poznania, ale tamte badania liczą podróże inaczej (od 250 m albo tylko osoby od 16 lat).",
        "upcoming": None,
    },
    "trojmiasto": {
        "status": "published",
        "survey": "Gdańskie Badania Ruchu 2022 (tylko Gdańsk i gminy sąsiednie; Gdynia i Sopot bez badania)",
        "year": v(2022, "gda", "tytuł raportu", "badania od 8.03.2022 do 28.04.2023 według artykułu trojmiasto.pl (gda_press)"),
        "area": "mieszkańcy Gdańska (dane w kolumnie „Gdańsk”); całe badanie: 15 065 wywiadów, w tym 10 000 w Gdańsku (s. 5, tabela 1)",
        "trip_definition": v("każde przemieszczenie w konkretnym celu, dowolnym środkiem lub pieszo, na odległość co najmniej 250 m",
                             "gda", "s. 19, rozdz. 2.5.1"),
        "base": "wszystkie podróże mieszkańców Gdańska; udziały policzone od liczby środków użytych w podróżach (podróż kilkoma środkami liczy się kilka razy)",
        "modal_split": {
            "walk": v(24.2, "gda", "s. 31, rysunek 38, kolumna Gdańsk"),
            "bike": v(4.3, "gda", "s. 31, rysunek 38, kolumna Gdańsk", "rower lub hulajnoga"),
            "pt": v(28.7, "gda", "s. 31, rysunek 38, kolumna Gdańsk"),
            "car": v(42.8, "gda", "s. 31, rysunek 38, kolumna Gdańsk", "tekst na s. 30 podaje 42,9"),
            "other": None,
        },
        "avg_trip_min": v(24, "gda", "s. 37, rozdz. 2.5.5", "cały badany obszar, wszystkie środki"),
        "avg_trip_min_pt": v(36, "gda", "s. 37, rozdz. 2.5.5", "cały badany obszar; samochód 25, rower 21, pieszo 13 min"),
        "trips_per_person": None,
        "pt_transfer_share": None,
        "pt_transfer_note": v(94.0, "gda", "s. 29, rysunek 36, kolumna Gdańsk",
                              "odsetek podróży mieszkańców Gdańska jednym środkiem transportu; to nie jest udział przesiadek w komunikacji"),
        "previous": {"year": 2016, "pt": v(32.1, "gda_press", "artykuł, zestawienie lat", "źródło wtórne")},
        "comparability": "Dotyczy tylko Gdańska, nie całego Trójmiasta. Podróż liczy się od 250 m (we Wrocławiu od 100 m), a udział to udział użytych środków.",
        "upcoming": None,
    },
    "krakow": {
        "status": "published",
        "survey": "Kompleksowe Badania Ruchu w Krakowskim Obszarze Metropolitalnym (KBR 2023)",
        "year": v(2023, "krk", "strona, opis badań: ankiety maj–czerwiec 2023, pomiary napełnień październik 2023"),
        "area": "10 tys. gospodarstw (21 087 respondentów), w tym 6 tys. w Krakowie i 35 gminach wokół",
        "trip_definition": None,
        "base": "podróże niepiesze; strona mówi o mieszkańcach miasta, ale nie rozstrzyga tego wprost przy podziale zadań",
        "modal_split": {
            "walk": None,
            "bike": v(5, "krk", "strona, podział zadań przewozowych", "udział w podróżach niepieszych"),
            "pt": v(54, "krk", "strona, podział zadań przewozowych", "udział w podróżach niepieszych"),
            "car": v(39, "krk", "strona, podział zadań przewozowych", "udział w podróżach niepieszych"),
            "other": None,
        },
        "avg_trip_min": v(30, "krk", "strona: „Średni czas trwania podróży mieszkańców Miasta wynosi prawie 30 min”", "„prawie 30 min”"),
        "avg_trip_min_pt": None,
        "trips_per_person": v(1.92, "krk", "strona, ruchliwość mieszkańców w dniu roboczym"),
        "pt_transfer_share": None,
        "previous": None,
        "comparability": "Udziały bez podróży pieszych, więc nie zestawiać z Wrocławiem, Gdańskiem ani Poznaniem, które liczą też pieszych.",
        "upcoming": None,
    },
    "poznan": {
        "status": "published",
        "survey": "Badanie ankietowe i aktualizacja modelu ruchu (badania jesienią 2018, synteza z listopada 2019)",
        "year": v(2018, "poz", "s. 6, rozdz. II.1: badania „wykonane zostały jesienią 2018 r.”"),
        "area": "mieszkańcy Poznania; w 2018 r. ankietowano osoby powyżej 16 lat (s. 9, przypis 2)",
        "trip_definition": None,
        "base": "wszystkie podróże mieszkańców Poznania (z pieszymi)",
        "modal_split": {
            "walk": v(20.6, "poz", "s. 10, rozdz. III.2"),
            "bike": v(8.4, "poz", "s. 10, rozdz. III.2"),
            "pt": v(33.7, "poz", "s. 10, rozdz. III.2", "42,4 % w podróżach niepieszych"),
            "car": None,
            "other": None,
        },
        "modal_split_note": "Udziału samochodu tekst nie podaje (jest tylko na rysunku 1, s. 11, którego nie odczytano).",
        "avg_trip_min": None,
        "avg_trip_min_pt": None,
        "trips_per_person": v(2.20, "poz", "s. 9, rozdz. III.1", "po weryfikacji w modelu ruchu"),
        "pt_transfer_share": None,
        "previous": {"year": 2013, "pt": v(42.4, "poz", "s. 10, rozdz. III.2")},
        "comparability": "Badanie sprzed pandemii (2018) i tylko osób od 16 lat; nowe badanie trwa. Wszystkie podróże z pieszymi, jak we Wrocławiu.",
        "upcoming": {"text": "Nowe Kompleksowe Badania Ruchu (Poznań i metropolia): wywiady z pasażerami jesienią 2026, gospodarstwa i pomiary wiosną 2027, koniec projektu w 2027 r.",
                     "src": "poz_new", "loc": "komunikat"},
    },
    "warszawa": {
        "status": "partial",
        "survey": "Warszawskie Badanie Ruchu 2024–2025",
        "year": v("2024–2025", "waw", "strona: badania ankietowe „w 2024 i 2025 roku”", "strona nie mówi, z którego roku jest która liczba"),
        "area": "mieszkańcy Warszawy i gmin metropolii powyżej 6 lat, cały dzień roboczy",
        "trip_definition": None,
        "base": "na stronie miasta brak jednego podziału zadań dla całej Warszawy; są tylko udziały według miejsca końca podróży",
        "modal_split": None,
        "partial": [
            {"label": "podróże kończące się w Strefie Czystego Transportu",
             "walk": v(33, "waw", "strona, wyniki dla SCT"), "pt": v(40.6, "waw", "strona, wyniki dla SCT"),
             "car": v(23.6, "waw", "strona, wyniki dla SCT"), "bike": None, "other": None},
            {"label": "podróże poza Strefą Czystego Transportu",
             "walk": v(37.3, "waw", "strona, wyniki poza SCT"), "pt": v(23.6, "waw", "strona, wyniki poza SCT"),
             "car": v(35.5, "waw", "strona, wyniki poza SCT"), "bike": None, "other": None},
        ],
        "avg_trip_min": None,
        "avg_trip_min_pt": None,
        "trips_per_person": None,
        "pt_transfer_share": None,
        "previous": None,
        "comparability": "Miasto nie opublikowało jednego udziału dla całej Warszawy, tylko osobno dla podróży do centrum (SCT) i poza nim, więc nie ma liczby do porównania z innymi miastami.",
        "upcoming": None,
    },
    "lodz": {
        "status": "in_progress",
        "survey": None, "year": None, "area": None, "trip_definition": None, "base": None, "modal_split": None,
        "avg_trip_min": None, "avg_trip_min_pt": None, "trips_per_person": None, "pt_transfer_share": None, "previous": None,
        "comparability": "Brak opublikowanego badania; poprzedniego badania nie znaleziono.",
        "upcoming": {"text": "Łódzkie Badania Ruchu: od października 2026, Łódź i 15 gmin, ok. 9 tys. osób, projekt na 18 miesięcy.",
                     "src": "lodz", "loc": "artykuł"},
    },
    "gzm": {
        "status": "none",
        "survey": None, "year": None, "area": None, "trip_definition": None, "base": None, "modal_split": None,
        "avg_trip_min": None, "avg_trip_min_pt": None, "trips_per_person": None, "pt_transfer_share": None, "previous": None,
        "comparability": "Dla Metropolii GZM nie znaleziono badania ankietowego gospodarstw; jest tylko pomiar kordonowy z 2024 r. (natężenia ruchu).",
        "upcoming": None,
        "none_src": {"src": "gzm", "loc": "lista opracowań (przejrzana częściowo)"},
    },
}

ORDER = ["warszawa", "krakow", "wroclaw", "poznan", "lodz", "trojmiasto", "gzm"]
MODES = [("walk", "pieszo"), ("bike", "rower"), ("pt", "komunikacja zbiorowa"), ("car", "samochód"), ("other", "inne")]


def _fmt(x) -> str:
    if x is None:
        return "brak"
    if isinstance(x, dict):
        val = x["v"]
        txt = str(val).replace(".", ",") if isinstance(val, (int, float)) else str(val)
        return txt + (f" ({x['note']})" if x.get("note") else "")
    return str(x)


def qa_note() -> str:
    L = ["# Kontekst z badań ruchu: lista wartości i źródeł", "",
         f"Dostęp do źródeł: {ACCESSED}. Kod: `pipeline/survey_context.py`; dane dla strony: `results/web/survey_context.json`.",
         "Żadna liczba nie jest wyliczona ani uzupełniona: wartości przepisano ze stron i PDF podanych przy każdej z nich. "
         "„brak” = źródło tej wartości nie podaje. Udziały w % podstawy podanej w kolumnie „Podstawa”.", "",
         "## Wartości", "",
         "| Aglomeracja | Wielkość | Wartość | Źródło | Miejsce |", "|---|---|---|---|---|"]
    for agg in ORDER:
        r = RECORDS[agg]
        rows = []
        for k, lab in [("year", "rok"), ("trip_definition", "definicja podróży"), ("avg_trip_min", "średni czas podróży, min"),
                       ("avg_trip_min_pt", "średni czas podróży komunikacją, min"), ("trips_per_person", "podróże na osobę i dobę"),
                       ("pt_transfer_share", "udział podróży komunikacją z przesiadką, %"), ("pt_transfer_note", "podróże jednym środkiem, %")]:
            x = r.get(k)
            if isinstance(x, dict):
                rows.append((lab, _fmt(x), x["src"], x["loc"]))
            elif k in r:
                rows.append((lab, "brak", "", ""))
        for mk, ml in MODES:
            ms = r.get("modal_split")
            x = ms.get(mk) if ms else None
            if x:
                rows.append((f"udział: {ml}", _fmt(x), x["src"], x["loc"]))
            elif ms is not None:
                rows.append((f"udział: {ml}", "brak", "", ""))
        for p in r.get("partial") or []:
            for mk, ml in MODES:
                if p.get(mk):
                    rows.append((f"{p['label']}: {ml}", _fmt(p[mk]), p[mk]["src"], p[mk]["loc"]))
        if r.get("previous"):
            pv = r["previous"]
            rows.append((f"komunikacja zbiorowa w {pv['year']} r.", _fmt(pv["pt"]), pv["pt"]["src"], pv["pt"]["loc"]))
        if not rows:
            rows.append(("badanie", "brak badania", (r.get("upcoming") or r.get("none_src") or {}).get("src", ""), ""))
        for lab, val, src, loc in rows:
            L.append(f"| {agg} | {lab} | {val} | {src} | {loc} |")
    L += ["", "## Podstawa i porównywalność", "", "| Aglomeracja | Stan | Podstawa | Co ogranicza porównanie |", "|---|---|---|---|"]
    st = {"published": "opublikowane", "partial": "częściowe", "in_progress": "badanie w toku", "none": "brak badania"}
    for agg in ORDER:
        r = RECORDS[agg]
        L.append(f"| {agg} | {st[r['status']]} | {r.get('base') or 'brak'} | {r['comparability']} |")
    L += ["", "## Źródła", "", "| Klucz | Tytuł | Adres | Pierwotne |", "|---|---|---|---|"]
    for k, s in S.items():
        L.append(f"| {k} | {s['title']} | {s['url']} | {'tak' if s['primary'] else 'nie (wtórne)'} |")
    L += ["", "## Czego nie sprawdzono", "",
          "- Pełnych raportów Wrocławia (KBR 2024) i Krakowa (raport ankietowy KBR 2023) nie otwarto: udział pieszych w Krakowie, "
          "czasy według środków i udział przesiadek pozostają nieznane.",
          "- Poznań: udział samochodu jest tylko na rysunku (s. 11), którego nie odczytano; definicji podróży synteza nie podaje.",
          "- Gdańsk: daty badań (8.03.2022–28.04.2023) podaje tylko artykuł prasowy, nie strony 1–45 raportu; liczby podróży na osobę z raportu nie odczytano.",
          "- Warszawa: pełnej prezentacji WBR 2024–2025 nie otwarto; jeśli ma udział dla całego miasta, nie jest tu użyty.",
          "- Gdynia i Sopot: badania nie znaleziono. GZM: listy opracowań InfoGZM nie przejrzano w całości.",
          "- Udziału podróży komunikacją z przesiadką nie podaje żadne z otwartych źródeł; pole jest puste we wszystkich miastach.",
          ""]
    return "\n".join(L)


def main() -> None:
    t0 = time.time()
    doc = {"version": VERSION, "accessed": ACCESSED,
           "note": "Wartości przepisane ze źródeł (src = klucz w sources, loc = strona, tabela lub akapit). null = źródło nie podaje.",
           "modes": [{"key": k, "label": lab} for k, lab in MODES],
           "sources": S, "agglomerations": {a: RECORDS[a] for a in ORDER}}
    write_json(OUT_WEB, doc)
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "survey_context.md").write_text(qa_note(), encoding="utf-8", newline="\n")
    meta = write_meta(QA, "survey_context", started=t0, extra={"version": VERSION, "accessed": ACCESSED,
                                                              "outputs": ["results/web/survey_context.json",
                                                                          "results/qa/survey_context/survey_context.md"]})
    (RESULTS / "web" / "_meta_survey_context.json").write_text(meta.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
