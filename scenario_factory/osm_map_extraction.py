import logging
import subprocess
from pathlib import Path
from typing import Optional

from scenario_factory.city import BoundedCity

# TODO: This mapping is far from ideal. A better alternative would be to either use a transparent proxy to GeoFabrik and download the maps on demand or use a static index using types (maybe those from commonroad-io?)
_CITY_TO_MAP_MAPPING = {
    "DEU": {"Bremen": "bremen-latest.osm.pbf", "default": "germany-latest.osm.pbf"},
    "ESP": "spain-latest.osm.pbf",
    "BEL": "belgium-latest.osm.pbf",
    "CHN": "china-latest.osm.pbf",
    "USA": {
        "NewYork": "new-york-latest.osm.pbf",
        "Washington": "district-of-columbia-latest.osm.pbf",
        "Austin": "texas-latest.osm.pbf",
        "Phoenix": "arizona-latest.osm.pbg",
        # TODO: Why does germany have a default fallback, while USA does not?
    },
    "FRA": "france-latest.osm.pbf",
}


def _get_map_file_for_city(city: BoundedCity) -> Optional[str]:
    if city.country not in _CITY_TO_MAP_MAPPING:
        return None

    if isinstance(_CITY_TO_MAP_MAPPING[city.country], str):
        return _CITY_TO_MAP_MAPPING[city.country]
    elif isinstance(_CITY_TO_MAP_MAPPING[city.country], dict):
        # There are multiple maps for a country present. Now the correct one for the city is selected.
        country_maps = _CITY_TO_MAP_MAPPING[city.country]

        if city.name in country_maps:
            return country_maps[city.name]

        if "default" in country_maps:
            return country_maps["default"]

    return None


class OsmFileExtractionIsNotAutomatedException(Exception):
    def __init__(self, city: BoundedCity, output_file: Path):
        self.city = city
        super().__init__(
            f"OSM file extraction for {city.country}_{city.name} not automated. Do by hand! \n"
            f"This is the terminal command: \n"
            f"osmium extract --bbox {city.bounding_box} -o {output_file} input_file"
        )


class NoOsmMapInputFileException(Exception):
    def __init__(self, city: BoundedCity, input_file):
        self.city = city
        super().__init__(f"Could not find input file {input_file} for {city.country}_{city.name}.")


def extract_bounding_box_from_osm_map(
    city: BoundedCity, output_file: Path, input_maps_folder: Path, overwrite: bool
) -> Path:
    """
    Extract the OSM map according to bounding box specified for the city by calling osmium.

    Args:
        city (BoundedCity): The city for which the map should be extracted.
        output_file (Path): Path to the file, where the OSM map should be placed.
        input_maps_folder (Path): Folder containing the input OSM maps, from which the extract will be created.
        overwrite (bool): Whether existing extracts should be overwritten

    Returns:
        Path: Path to the extracted OSM maps.
    """

    map_file = _get_map_file_for_city(city)
    if map_file is None:
        raise OsmFileExtractionIsNotAutomatedException(city, output_file)

    input_file = input_maps_folder.joinpath(map_file)
    if not input_file.exists():
        raise NoOsmMapInputFileException(city, input_file)

    logging.info(f"Extracting {city.country}_{city.name}")

    cmd = ["osmium", "extract", "--bbox", str(city.bounding_box), "-o", str(output_file), str(input_file)]
    if overwrite:
        cmd.append("--overwrite")

    logging.debug(f"Osmium extraction command: {' '.join(cmd)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode > 1 or output_file.stat().st_size <= 200:
        logging.debug(proc.stdout)
        raise RuntimeError(
            f"Failed to extract bounding box for {city.country}_{city.name} from {input_file} using osmium"
        )

    return output_file
