import logging
import subprocess
from pathlib import Path
from typing import Optional

from commonroad.scenario.scenario import Location, Scenario, ScenarioID
from crdesigner.map_conversion.osm2cr.converter_modules.converter import GraphScenario
from crdesigner.map_conversion.osm2cr.converter_modules.cr_operations.export import (
    create_scenario_intermediate,
    sanitize,
)
from crdesigner.map_conversion.osm2cr.converter_modules.utility.geonamesID import get_geonamesID
from crdesigner.map_conversion.osm2cr.converter_modules.utility.labeling_create_tree import create_tree_from_file
from crdesigner.verification_repairing.config import MapVerParams
from crdesigner.verification_repairing.repairing.map_repairer import MapRepairer
from crdesigner.verification_repairing.verification.map_verifier import MapVerifier

from scenario_factory.city import BoundedCity

logger = logging.getLogger(__name__)

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

    :param city: The city for which the map should be extracted.
    :param output_file:Path to the file, where the OSM map should be placed.
    :param input_maps_folder: Folder containing the input OSM maps, from which the extract will be created.
    :param overwrite: Whether existing extracts should be overwritten

    :returns: Path to the extracted OSM maps.
    """

    map_file = _get_map_file_for_city(city)
    if map_file is None:
        raise OsmFileExtractionIsNotAutomatedException(city, output_file)

    input_file = input_maps_folder.joinpath(map_file)
    if not input_file.exists():
        raise NoOsmMapInputFileException(city, input_file)

    logger.debug(f"Extracting {city.country}_{city.name}")

    cmd = ["osmium", "extract", "--bbox", str(city.bounding_box), "-o", str(output_file), str(input_file)]
    if overwrite:
        cmd.append("--overwrite")

    logger.debug(f"Osmium extraction command: {' '.join(cmd)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode > 1 or output_file.stat().st_size <= 200:
        logger.debug(proc.stdout)
        raise RuntimeError(
            f"Failed to extract bounding box for {city.country}_{city.name} from {input_file} using osmium"
        )

    return output_file


def _verify_and_repair_scenario(scenario: Scenario) -> int:
    map_verifier = MapVerifier(scenario.lanelet_network, MapVerParams())
    invalid_states = map_verifier.verify()

    if len(invalid_states) > 0:
        map_repairer = MapRepairer(scenario.lanelet_network)
        map_repairer.repair_map(invalid_states)

    return len(invalid_states)


def convert_osm_file_to_commonroad_scenario(osm_file: Path) -> Scenario:
    """
    Convert an OSM file to a CommonRoad Scenario

    :param osm_file: Path to the OSM file.
    :returns: The resulting scenario
    """
    # Ree the geonames tree from file, because otherwise create_scenario_intermediate will try to fetch it from the internet, which fails because of missing credentials for the geonames API.
    geonames_tree = create_tree_from_file()

    logger.debug(f"Converting OSM {osm_file} to CommonRoad Scenario")

    graph = GraphScenario(str(osm_file)).graph
    scenario, _ = create_scenario_intermediate(graph)
    sanitize(scenario)

    geo_name_id = get_geonamesID(graph.center_point[0], graph.center_point[1], geonames_tree)
    location = Location(
        gps_latitude=graph.center_point[0],
        gps_longitude=graph.center_point[1],
        geo_name_id=geo_name_id,
    )
    scenario.location = location

    logger.debug(f"Convertered OSM {osm_file} to CommonRoad Scenario with GeoName ID {geo_name_id}")

    num_invalid_states = _verify_and_repair_scenario(scenario)
    if num_invalid_states > 0:
        logger.debug(f"Found {num_invalid_states} errors in lanelet network created from OSM {osm_file}.")

    # TODO: Find another method to derive the scenario ID, instead of the osm file
    country_id = osm_file.stem.split("_")[0]
    map_name = osm_file.stem.split("_")[-1]
    scenario.scenario_id = ScenarioID(country_id=country_id, map_name=map_name)
    return scenario
