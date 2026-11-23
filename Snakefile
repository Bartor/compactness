# Local build (brief §14.2). Nothing here runs in CI: computation is local,
# results are committed, GitHub Actions only deploys the web UI.
#
#   snakemake -c1 fetch          # download sources into data/raw (+ manifest)
#   snakemake -c1 inventory      # phase 0 tables in results/qa/phase0
#   snakemake -c1 density        # phase 1: density measures
#   snakemake -c1 supply         # phase 2: vehicle-km, tram speed (needs gtfs_service)
#   snakemake -c1 frequent       # phase 2: population near frequent service
#   snakemake -c1 merge_metrics  # metrics_<step> -> metrics.csv/json + results/web/metrics.json
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


rule merge_metrics:
    # metrics_<step>.* -> metrics.csv / metrics.json and the map panel subset results/web/metrics.json
    input:
        "pipeline/merge_metrics.py",
        stamp("density"),
        stamp("supply"),
        stamp("frequent"),
    output:
        touch(stamp("merge_metrics")),
    shell:
        '"{PY}" -m pipeline.merge_metrics'


rule inventory:
    input:
        stamp("phase0_boundaries"),
        stamp("gtfs_inventory"),
        stamp("jobs_inventory"),
        stamp("stop_coverage"),
    output:
        touch(stamp("inventory")),
