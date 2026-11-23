# Local build (brief §14.2). Nothing here runs in CI: computation is local,
# results are committed, GitHub Actions only deploys the web UI.
#
#   snakemake -c1 fetch          # download sources into data/raw (+ manifest)
#   snakemake -c1 inventory      # phase 0 tables in results/qa/phase0
#   snakemake -c1 density        # phase 1: density measures
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


rule inventory:
    input:
        stamp("phase0_boundaries"),
        stamp("gtfs_inventory"),
        stamp("jobs_inventory"),
        stamp("stop_coverage"),
    output:
        touch(stamp("inventory")),
