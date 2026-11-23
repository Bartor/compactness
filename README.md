# Zwartość miast

Compactness and public-transport potential of Polish agglomerations: population-weighted
density, density profiles, people near frequent transport, *transport performance*
(DG REGIO method) and scheduled tram speeds, per functional urban area (FUA) and core.

The method, scope and rules are in [zwartosc-miast-brief.md](zwartosc-miast-brief.md) (Polish).
What has been computed, with which data and what was rejected: [results/RAPORT.md](results/RAPORT.md) (Polish).

## How it is built

All computation runs **locally**; results are committed like artefacts. GitHub Actions only
deploys the static map (`web/`) to GitHub Pages and computes nothing.

```
config.yaml      agglomerations, centres, reference day, windows, thresholds, feeds
pipeline/        Python modules, one per step
Snakefile        build steps with dependency tracking
data/manifest.csv  URL, download date, SHA-256 and licence of every source (committed)
data/raw, data/interim   downloads and intermediates (not committed, reproducible)
results/         metrics, chart data, small layers, QA plots, RAPORT.md (committed)
tiles/           PMTiles for the map (committed)
web/             static map: React, @bartor-net/ui-kit, MapLibre GL, PMTiles
collector/       GTFS-Realtime archiver; shelved, not run (scheduled times are used instead)
```

Setup (Python 3.12, Java 21 for the GTFS validator and R5):

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

```sh
.venv/Scripts/snakemake -c1 fetch
```

```sh
.venv/Scripts/snakemake -c1 inventory
```

Map, locally:

```sh
npm --prefix web install
npm --prefix web run dev
```

## Data and licences

Raw sources are never redistributed here; `data/manifest.csv` says where each came from.
Results are aggregates. Attribution: © OpenStreetMap contributors (ODbL), JRC GHSL,
GUS (NSP 2021), Eurostat GISCO / © EuroGeographics (Urban Audit 2021), IGiPZ PAN
(Goliszek 2026, CC BY 4.0), GTFS publishers listed in the report.

Population data are from 2020–2021 and timetables from 2026: every result carries both dates.
