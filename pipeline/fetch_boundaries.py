"""Download Eurostat GISCO Urban Audit 2021 (FUA, CITIES, GREATER_CITIES) and LAU 2021.

Raw files go to data/raw/boundaries/ and are registered in data/manifest.csv.
Run: python -m pipeline.fetch_boundaries
"""
from __future__ import annotations

from pipeline.common import RAW, download

URAU = "https://gisco-services.ec.europa.eu/distribution/v2/urau/"
LAU = "https://gisco-services.ec.europa.eu/distribution/v2/lau/"
OUT = RAW / "boundaries"
LICENSE = ("Eurostat GISCO terms (ec.europa.eu/eurostat/web/gisco/geodata/administrative-units): acknowledge the source with "
           "'(c) EuroGeographics for the administrative boundaries'; page says non-commercial use; redistribution of modified data "
           "not explicitly addressed - check before republishing")


def main() -> None:
    # Urau 2021, 100K scale, EPSG:3035 GeoPackage; one file with all levels (LEVEL column
    # not present in the per-level files, so fetch per level as well as the combined file).
    files = {
        "urau_2021_100k_all": URAU + "gpkg/URAU_RG_100K_2021_3035.gpkg",
        "urau_2021_100k_fua": URAU + "gpkg/URAU_RG_100K_2021_3035_FUA.gpkg",
        "urau_2021_100k_cities": URAU + "gpkg/URAU_RG_100K_2021_3035_CITIES.gpkg",
        "urau_2021_lb_all": URAU + "gpkg/URAU_LB_2021_3035.gpkg",
        "urau_2021_attributes_csv": URAU + "csv/URAU_AT_2021.csv",
        "lau_2021_01m": LAU + "gpkg/LAU_RG_01M_2021_3035.gpkg",
    }
    for key, url in files.items():
        dest = OUT / url.rsplit("/", 1)[1]
        download(key, url, dest, license=LICENSE,
                 source="Eurostat GISCO " + ("Urban Audit URAU 2021" if "urau" in key else "LAU 2021"),
                 data_date="2021", timeout=600)
        print(key, dest.stat().st_size)


if __name__ == "__main__":
    main()
