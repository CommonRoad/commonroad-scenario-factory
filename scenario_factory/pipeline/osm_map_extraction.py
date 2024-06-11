import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from scenario_factory.pipeline.bounding_box_coordinates import BoundedCity
from scenario_factory.pipeline.context import PipelineContext, PipelineStepArguments

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


@dataclass
class ExractOsmMapArguments(PipelineStepArguments):
    input_maps_folder: Path
    overwrite: bool


def extract_osm_map(ctx: PipelineContext, city: BoundedCity, args: Optional[ExractOsmMapArguments]) -> Path:
    """
    Extract the OSM map according to bounding box specified in the cities_file. Calls osmium library.

    Args:
        cities_file (Path): Path to the cities file.
        input_maps_folder (Path): Path to the folder containing the input OSM map files.
        overwrite (bool): Overwrite existing OSM map extraction files.

    Returns:
        Path: Path to the folder with the extracted OSM maps.
    """
    assert args is not None
    output_folder = ctx.get_output_folder("extracted_maps")
    output_file = output_folder.joinpath(f"{city.country}_{city.name}.osm")

    map_file = _get_map_file_for_city(city)
    if map_file is None:
        raise OsmFileExtractionIsNotAutomatedException(city, output_file)

    input_file = args.input_maps_folder.joinpath(map_file)
    if not input_file.exists():
        raise NoOsmMapInputFileException(city, input_file)

    logging.info(f"Extracting {city.country}_{city.name}")
    overwr = "--overwrite" if args.overwrite else ""
    os.system(f"osmium extract --bbox {city.bounding_box} -o {output_file} {input_file} {overwr}")
    # if not, the converted file is (almost) empty -- conversion was not successful
    # TODO: Could the osmium exit could be used instead?
    assert os.path.getsize(output_file) > 200
    return output_file
