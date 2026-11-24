# Local build (brief §14.2). Nothing here runs in CI: computation is local,
# results are committed, GitHub Actions only deploys the web UI.
#
#   snakemake -c1 fetch          # download sources into data/raw (+ manifest)
#   snakemake -c1 inventory      # phase 0 tables in results/qa/phase0
#   snakemake -c1 density        # phase 1: density measures
#   snakemake -c1 supply         # phase 2: vehicle-km, tram speed (needs gtfs_service)
#   snakemake -c1 frequent       # phase 2: population near frequent service
#   snakemake -c1 density_service  # density x service frequency: metrics_density_service.*
#   snakemake -c1 transfer_ease  # ease of transfer at stop areas: metrics_transfer.*, layers/transfer_nodes.parquet
#   snakemake -c1 transfer_web   # stop areas as map points: results/web/transfer_nodes.geojson, catalog entries
#   snakemake -c1 access_run     # phase 3: R5 routing, ~12 h for all 7 agglomerations (explicit target only)
#   snakemake -c1 access         # phase 3: aggregate whatever access_run has finished
#   snakemake -c1 access_uc_run  # phase 3, urban-centre domain: R5 routing, ~1 h on 6 threads (explicit target only)
#   snakemake -c1 access_uc      # phase 3, urban-centre domain: metrics_access_uc.* + results/qa/access_uc
#   snakemake -c1 merge_metrics  # metrics_<step> -> metrics.csv/json + results/web/metrics.json
#   snakemake -c1 tiles          # phase 4: PMTiles in tiles/, layer entries in results/web/catalog.json
#   snakemake -c1 all
#
# Steps with many outputs are tracked through stamp files in data/interim/_stamps;
# a step re-runs when its code, config.yaml or an upstream stamp changes.
# Feeds have short validity windows, so `fetch_gtfs` is re-run on purpose
# (snakemake -c1 -R fetch_gtfs), never implicitly.

import sys

PY = sys.executable
STAMPS = "data/interim/_stamps"

configfile: "config.yaml"


def stamp(name):
    return f"{STAMPS}/{name}.done"


rule all:
    input:
        stamp("inventory"),
        stamp("density"),
        stamp("merge_metrics"),
        stamp("tiles"),


rule fetch:
    input:
        stamp("fetch_boundaries"),
        stamp("fetch_population"),
        stamp("fetch_gtfs"),
        stamp("fetch_osm"),
        stamp("fetch_jobs"),


rule fetch_boundaries:
    input:
        "config.yaml",
        "pipeline/fetch_boundaries.py",
    output:
        touch(stamp("fetch_boundaries")),
    shell:
        '"{PY}" -m pipeline.fetch_boundaries'


rule fetch_population:
    input:
        "config.yaml",
        "pipeline/fetch_population.py",
        stamp("fetch_boundaries"),
    output:
        touch(stamp("fetch_population")),
    shell:
        '"{PY}" -m pipeline.fetch_population'


rule fetch_gtfs:
    input:
        "pipeline/fetch_gtfs.py",
    output:
        touch(stamp("fetch_gtfs")),
    shell:
        '"{PY}" -m pipeline.fetch_gtfs all'    # download + MobilityData validator


rule fetch_osm:
    input:
        "pipeline/fetch_osm.py",
    output:
        touch(stamp("fetch_osm")),
    shell:
        '"{PY}" -m pipeline.fetch_osm'


rule fetch_jobs:
    input:
        "pipeline/fetch_jobs.py",
    output:
        touch(stamp("fetch_jobs")),
    shell:
        '"{PY}" -m pipeline.fetch_jobs'


rule phase0_boundaries:
    # agglomeration table, GZM variants, web hand-off (results/web)
    input:
        "config.yaml",
        "pipeline/phase0_boundaries.py",
        "pipeline/boundaries.py",
        stamp("fetch_population"),
    output:
        touch(stamp("phase0_boundaries")),
    shell:
        '"{PY}" -m pipeline.phase0_boundaries'


rule osm_stops:
    input:
        "pipeline/osm_stops.py",
        stamp("fetch_osm"),
        stamp("phase0_boundaries"),
    output:
        touch(stamp("osm_stops")),
    shell:
        '"{PY}" -m pipeline.osm_stops && "{PY}" -m pipeline.osm_stops --report'


rule gtfs_inventory:
    input:
        "config.yaml",
        "pipeline/gtfs_inventory.py",
        "pipeline/gtfs_io.py",
        stamp("fetch_gtfs"),
    output:
        touch(stamp("gtfs_inventory")),
    shell:
        '"{PY}" -m pipeline.gtfs_inventory all'


rule jobs_inventory:
    input:
        "pipeline/jobs_inventory.py",
        stamp("fetch_jobs"),
        stamp("phase0_boundaries"),
    output:
        touch(stamp("jobs_inventory")),
    shell:
        '"{PY}" -m pipeline.jobs_inventory'


rule stop_coverage:
    input:
        "config.yaml",
        "pipeline/stop_coverage.py",
        stamp("osm_stops"),
        stamp("fetch_gtfs"),
        stamp("fetch_boundaries"),
    output:
        touch(stamp("stop_coverage")),
    shell:
        '"{PY}" -m pipeline.stop_coverage'


rule grid250:
    # GHS-POP 100 m (Mollweide) -> 250 m grid in EPSG:2180, area-preserving
    input:
        "pipeline/grid250.py",
        stamp("fetch_population"),
    output:
        touch(stamp("grid250")),
    shell:
        '"{PY}" -m pipeline.grid250'


rule density:
    # phase 1 (brief 4.1-4.4, 7.1): metrics, chart data, QA plots
    input:
        "config.yaml",
        "pipeline/density.py",
        "pipeline/density_control.py",
        "pipeline/density_qa.py",
        "pipeline/boundaries.py",
        stamp("grid250"),
        stamp("fetch_boundaries"),
    output:
        touch(stamp("density")),
    shell:
        '"{PY}" -m pipeline.density && "{PY}" -m pipeline.density_control && "{PY}" -m pipeline.density_qa'


rule popgrid:
    # census 1 km and GHSL 250 m population on one footing (scaled / raw variants)
    input:
        "config.yaml",
        "pipeline/popgrid.py",
        stamp("grid250"),
        stamp("fetch_population"),
    output:
        touch(stamp("popgrid")),
    shell:
        '"{PY}" -m pipeline.popgrid'


rule walk_network:
    # OSM pedestrian network per agglomeration
    input:
        "config.yaml",
        "pipeline/walk_network.py",
        stamp("fetch_osm"),
        stamp("fetch_boundaries"),
    output:
        touch(stamp("walk_network")),
    shell:
        '"{PY}" -m pipeline.walk_network'


rule gtfs_service:
    # per-stop service levels from GTFS for the reference day
    input:
        "config.yaml",
        "pipeline/gtfs_service.py",
        "pipeline/gtfs_io.py",
        stamp("fetch_gtfs"),
        stamp("fetch_boundaries"),
    output:
        touch(stamp("gtfs_service")),
    shell:
        '"{PY}" -m pipeline.gtfs_service'


rule supply:
    # vehicle-km per inhabitant, tram operating speed (metrics_supply.*)
    input:
        "config.yaml",
        "pipeline/supply.py",
        "pipeline/supply_core.py",
        "pipeline/supply_report.py",
        "pipeline/tram_speed.py",
        "pipeline/top_stops.py",
        stamp("gtfs_service"),
    output:
        touch(stamp("supply")),
    shell:
        '"{PY}" -m pipeline.supply'


rule frequent:
    # population near frequent transit service (metrics_frequent.*)
    input:
        "config.yaml",
        "pipeline/frequent.py",
        "pipeline/frequent_md.py",
        "pipeline/frequent_qa.py",
        "pipeline/frequent_text.py",
        stamp("popgrid"),
        stamp("walk_network"),
        stamp("gtfs_service"),
        stamp("stop_coverage"),
    output:
        touch(stamp("frequent")),
    shell:
        '"{PY}" -m pipeline.frequent'


rule density_service:
    # population density x service frequency (metrics_density_service.*, results/qa/density_service)
    input:
        "config.yaml",
        "pipeline/density_service.py",
        stamp("frequent"),
    output:
        touch(stamp("density_service")),
    shell:
        '"{PY}" -m pipeline.density_service'


rule transfer_ease:
    # ease of transfer at stop areas (extra layer, RAPORT 12.2): metrics_transfer.*, layers/transfer_nodes.parquet,
    # results/qa/transfer; OSM crossing / tunnel / bridge tags cached in data/interim/transfer (one PBF pass).
    # Not yet an input of merge_metrics or tiles.
    input:
        "config.yaml",
        "pipeline/transfer_ease.py",
        "pipeline/transfer_osm.py",
        "pipeline/transfer_walk.py",
        "pipeline/transfer_report.py",
        "pipeline/transfer_md.py",
        stamp("fetch_osm"),
        stamp("walk_network"),
        stamp("gtfs_service"),
        stamp("frequent"),
    output:
        touch(stamp("transfer_ease")),
    shell:
        '"{PY}" -m pipeline.transfer_ease'


rule transfer_web:
    # stop areas as points for the map: results/web/transfer_nodes.geojson + catalog entries transfer_walk, transfer_wait
    input:
        "config.yaml",
        "pipeline/transfer_web.py",
        stamp("transfer_ease"),
    output:
        touch(stamp("transfer_web")),
    shell:
        '"{PY}" -m pipeline.transfer_web'


rule r5_inputs:
    # clipped OSM + cleaned GTFS zips per agglomeration and feed variant (data/interim/r5)
    input:
        "config.yaml",
        "pipeline/r5_inputs.py",
        stamp("fetch_osm"),
        stamp("gtfs_service"),
    output:
        touch(stamp("r5_inputs")),
    shell:
        '"{PY}" -m pipeline.r5_inputs'


rule access_run:
    # Phase 3 routing (brief 4.6): ~12 hours on 20 threads for all priorities and agglomerations.  Deliberately
    # NOT part of `all` and not an input of any other rule: start it explicitly (snakemake -c1 access_run, or
    # python -m pipeline.access run).  Resumable: finished chunks with an unchanged signature are skipped, so the
    # same command continues after an interruption.  Progress: data/interim/access/run.log and
    # python -m pipeline.access status.
    input:
        "pipeline/access.py",
        "pipeline/access_inputs.py",
        "pipeline/access_samples.py",
        "pipeline/r5_env.py",
        stamp("r5_inputs"),
        stamp("popgrid"),
        stamp("frequent"),
    output:
        touch(stamp("access_run")),
    shell:
        '"{PY}" -m pipeline.access run'


rule access:
    # aggregate the finished access units -> metrics_access.*, charts/access_performance.json,
    # layers/access_cells.parquet, qa/access/access.md; unfinished units are listed as pending.  It does not
    # depend on access_run (explicit target), so re-run it (snakemake -c1 -R access) after the routing progressed.
    input:
        "pipeline/access_aggregate.py",
        "pipeline/access_qa.py",
        "pipeline/access_inputs.py",
        stamp("frequent"),
        stamp("popgrid"),
    output:
        touch(stamp("access")),
    shell:
        '"{PY}" -m pipeline.access aggregate'


rule access_uc_run:
    # Urban-centre variant (pipeline.access_uc): transit and bike routing on the Eurostat 2021 urban centres of each
    # agglomeration, on copies of the production networks.  Explicit target like access_run; resumable per
    # (agglomeration, scenario) through signature files in data/interim/access_uc/.
    input:
        "pipeline/access_uc.py",
        "pipeline/access_dgregio.py",
        "pipeline/access_inputs.py",
        "pipeline/r5_env.py",
        stamp("r5_inputs"),
        stamp("popgrid"),
    output:
        touch(stamp("access_uc_run")),
    shell:
        '"{PY}" -m pipeline.access_uc route'


rule access_uc:
    # aggregate the urban-centre variant -> metrics_access_uc.*, results/qa/access_uc/access_uc.md; walk times come
    # from the production walk cache, unfinished routing is listed as pending (no rows).  Like `access`, it does
    # not depend on access_uc_run: re-run it (snakemake -c1 -R access_uc) after the routing progressed.
    input:
        "pipeline/access_uc.py",
        "pipeline/access_uc_aggregate.py",
        "pipeline/access_aggregate.py",
        "pipeline/access_inputs.py",
        stamp("frequent"),
        stamp("popgrid"),
    output:
        touch(stamp("access_uc")),
    shell:
        '"{PY}" -m pipeline.access_uc aggregate'


rule merge_metrics:
    # metrics_<step>.* -> metrics.csv / metrics.json and the map panel subset results/web/metrics.json
    input:
        "pipeline/merge_metrics.py",
        stamp("density"),
        stamp("supply"),
        stamp("frequent"),
        stamp("density_service"),
        stamp("access"),
        stamp("access_uc"),
    output:
        touch(stamp("merge_metrics")),
    shell:
        '"{PY}" -m pipeline.merge_metrics'


rule tiles:
    # phase 4 (brief 8, 14.3-14.4): five PMTiles files (density, frequent transit, performance 30 min, GTFS no-data
    # mask, density x service), their catalog entries, results/web/attributions.json, results/qa/tiles/tiles.md.  Single process.
    # After more agglomerations finish routing: re-run `snakemake -c1 -R access tiles` or only
    # python -m pipeline.tiles --layer transport_performance_30
    input:
        "config.yaml",
        "pipeline/tiles.py",
        "pipeline/tiles_core.py",
        "pipeline/tiles_layers.py",
        "pipeline/tiles_verify.py",
        "pipeline/density_service.py",
        stamp("popgrid"),
        stamp("frequent"),
        stamp("density_service"),
        stamp("access"),
        stamp("phase0_boundaries"),
    output:
        touch(stamp("tiles")),
    shell:
        '"{PY}" -m pipeline.tiles'


rule inventory:
    input:
        stamp("phase0_boundaries"),
        stamp("gtfs_inventory"),
        stamp("jobs_inventory"),
        stamp("stop_coverage"),
    output:
        touch(stamp("inventory")),
