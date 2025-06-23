__all__ = [
    "MapProvider",
    "LocalFileMapProvider",
    "OsmApiMapProvider",
    "verify_and_repair_commonroad_scenario",
    "convert_osm_file_to_commonroad_scenario",
    "extract_bounding_box_from_osm_map",
    "find_osm_file_for_region",
    "fix_center_polylines",
    "get_canonical_region_name",
]

import logging
import subprocess
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping, Optional

import iso3166
import numpy as np
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.traffic_light import TrafficLightState
from crdesigner.common.config.osm_config import osm_config
from crdesigner.map_conversion.osm2cr.converter_modules.converter import GraphScenario
from crdesigner.map_conversion.osm2cr.converter_modules.cr_operations.export import (
    create_scenario_intermediate,
    sanitize,
)
from crdesigner.map_conversion.osm2cr.converter_modules.osm_operations.downloader import (
    download_map,
)
from crdesigner.verification_repairing.config import EvaluationParams, MapVerParams
from crdesigner.verification_repairing.repairing.map_repairer import MapRepairer
from crdesigner.verification_repairing.verification.map_verifier import MapVerifier

from scenario_factory.globetrotter.region import BoundingBox, Coordinates, RegionMetadata

_LOGGER = logging.getLogger(__name__)

# The default source that will be set for a scenario that was created from a OpenStreetMap
DEFAULT_OSM_SOURCE = "OpenStreetMap (OSM)"


def _set_osm_traffic_light_phase_length(phase: TrafficLightState, length: int) -> None:
    phase_2_config_key_mapping = {
        TrafficLightState.RED: "red_phase",
        TrafficLightState.GREEN: "green_phase",
        TrafficLightState.YELLOW: "yellow_phase",
        TrafficLightState.RED_YELLOW: "red_yellow_phase",
    }
    if phase not in phase_2_config_key_mapping:
        supported_phases = ",".join(str(key) for key in phase_2_config_key_mapping.keys())
        raise ValueError(
            f"Cannot set traffic light phase length: Phase {phase} is not supported. Supported phases are: {supported_phases}."
        )

    if length < 0:
        raise ValueError(
            f"Cannot set traffic light phase length: Phase length must be positive, but is {length}."
        )

    phase_config_key = phase_2_config_key_mapping[phase]
    osm_config.TRAFFIC_LIGHT_CYCLE[phase_config_key] = length


def configure_traffic_light_phase_lengths(phase_mapping: Mapping[TrafficLightState, int]) -> None:
    """
    Configure how long each traffic light phase (=color) lasts. This is a global option, and if the default values should be changed, this method must be called before performing any osm2cr conversions.

    Example: Only modify the Red phase

        phase_length_mapping = {
            TrafficLightState.RED: 80
        }
        configure_traffic_light_phase_lengths(phase_mapping)
        scenario = convert_osm_file_to_commonroad_scenario(<path to your map>)

    Example: Update all phases

        phase_length_mapping = {
            TrafficLightState.RED: 40,
            TrafficLightState.GREEN: 30,
            TrafficLightState.YELLOW: 5,
            TrafficLightState.RED_YELLOW: 7
        }
        configure_traffic_light_phase_lengths(phase_mapping)
        scenario = convert_osm_file_to_commonroad_scenario(<path to your map>)

    :param phase_mapping: A mapping of each traffic light state (=color) to its phase length. All `TrafficLightState`s are supported, except `TrafficLightState.INVALID`.

    """
    for phase, length in phase_mapping.items():
        _set_osm_traffic_light_phase_length(phase, length)


# More sensible traffic light settings
configure_traffic_light_phase_lengths(
    {
        TrafficLightState.RED: 120,
        TrafficLightState.RED_YELLOW: 10,
        TrafficLightState.GREEN: 90,
        TrafficLightState.YELLOW: 15,
    }
)


def get_canonical_region_name(region_name: str) -> str:
    canonical_region_name = region_name.lower()

    # Special handling of regions consisting of multiple parts (e.g. New York)
    region_name_parts = canonical_region_name.split(" ")
    if len(region_name_parts) > 1:
        canonical_region_name = "-".join(region_name_parts)

    return canonical_region_name


def find_osm_file_for_region(osm_map_path: Path, map_metadata: RegionMetadata) -> Optional[Path]:
    # Prefer country files, because they are unique
    country_name = iso3166.countries.get(map_metadata.country_code).name
    canonical_country_name = get_canonical_region_name(country_name)
    for osm_file in osm_map_path.glob("*.osm.pbf"):
        if osm_file.name.startswith(canonical_country_name):
            return osm_file

    # Fallback to the region name. This step is not reliable as, region names can be duplicated...
    canonical_region_name = get_canonical_region_name(map_metadata.region_name)
    for osm_file in osm_map_path.glob("*.osm.pbf"):
        if osm_file.name.startswith(canonical_region_name):
            return osm_file

    return None


def extract_bounding_box_from_osm_map(
    bounding_box: BoundingBox, map_file: Path, output_file: Path, overwrite: bool = True
) -> None:
    """
    Extract the OSM map according to bounding box specified for the city by calling osmium.

    :param bounding_box: The bounding box that should be extracted
    :param map_file: The input map file, from which the bounding box should be extracted
    :param output_file: Path to the file, where the extracted OSM map should be placed
    :param overwrite: Whether existing extracts should be overwritten

    :returns: Nothing

    :raises RuntimeError: When the extraction failed
    """

    _LOGGER.debug(f"Extracting {bounding_box} from {map_file}")

    cmd = [
        "osmium",
        "extract",
        "--bbox",
        str(bounding_box),
        "-o",
        str(output_file),
        str(map_file),
    ]
    if overwrite:
        cmd.append("--overwrite")

    _LOGGER.debug(f"Osmium extraction command: {' '.join(cmd)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode > 1 or output_file.stat().st_size <= 200:
        _LOGGER.debug(proc.stdout)
        raise RuntimeError(
            f"Failed to extract bounding box {bounding_box} from {map_file} using osmium"
        )


class MapProvider(ABC):
    """A MapProvider is used to obtain OpenStreetMaps for a specific location as an OSM XML file"""

    def __init__(self) -> None: ...

    def _filename_for_region(self, region: RegionMetadata) -> str:
        return f"{region.country_code}_{region.region_name}.osm"

    @abstractmethod
    def get_map(
        self, region: RegionMetadata, bounding_box: BoundingBox, output_folder: Path
    ) -> Path:
        return output_folder.joinpath(self._filename_for_region(region))


class LocalFileMapProvider(MapProvider):
    def __init__(self, map_folder: Path) -> None:
        super().__init__()
        self._maps_folder = map_folder

    def get_map(
        self, region: RegionMetadata, bounding_box: BoundingBox, output_folder: Path
    ) -> Path:
        target_file = super().get_map(region, bounding_box, output_folder)
        map_file = find_osm_file_for_region(self._maps_folder, region)
        if map_file is None:
            raise ValueError(f"Could not find an OSM file for the region {region}")
        extract_bounding_box_from_osm_map(bounding_box, map_file, target_file)
        return target_file


class OsmApiMapProvider(MapProvider):
    """The OsmApiMapProvider provides"""

    def get_map(
        self, region: RegionMetadata, bounding_box: BoundingBox, output_folder: Path
    ) -> Path:
        target_file = super().get_map(region, bounding_box, output_folder)
        download_map(
            str(target_file),
            bounding_box.west,
            bounding_box.south,
            bounding_box.east,
            bounding_box.north,
        )
        if not target_file.exists():
            # TODO: The CommonRoad Scenario Designer does not expose any result information. Maybe we could implement the function ourselves and provide more error information?
            raise RuntimeError("Failed to download map from OpenStreetMap API")
        return target_file


def fix_center_polylines(lanelet_network: LaneletNetwork) -> None:
    """
    Recalculate all center polylines in the :param:`lanelet_network`, to make sure they are all realy centered between the left and right polylines.
    """
    for lanelet in lanelet_network.lanelets:
        lanelet.center_vertices = 0.5 * (lanelet.left_vertices + lanelet.right_vertices)


def verify_and_repair_commonroad_scenario(scenario: Scenario) -> int:
    """
    Use the Map verification and repairing from the CommonRoad Scenario Designer to repair a CommonRoad scenario.
    """

    map_verifier = MapVerifier(
        scenario.lanelet_network,
        MapVerParams(evaluation=EvaluationParams(partitioned=True)),
    )
    invalid_states = map_verifier.verify()

    if len(invalid_states) > 0:
        map_repairer = MapRepairer(scenario.lanelet_network)
        map_repairer.repair_map(invalid_states)

    fix_center_polylines(scenario.lanelet_network)

    return len(invalid_states)


@contextmanager
def _redirect_all_undirected_log_messages(target_logger):
    def redirect(msg, *args, **kwargs):
        target_logger.debug(msg, *args, **kwargs)

    info, debug, warning, error = (
        logging.info,
        logging.debug,
        logging.warning,
        logging.error,
    )
    logging.info, logging.debug, logging.warning, logging.error = (
        redirect,
        redirect,
        redirect,
        redirect,
    )

    try:
        yield
    finally:
        logging.info, logging.debug, logging.warning, logging.error = (
            info,
            debug,
            warning,
            error,
        )


def convert_osm_file_to_commonroad_scenario(osm_file: Path) -> Scenario:
    """
    Convert an OSM file to a CommonRoad Scenario

    :param osm_file: Path to the OSM file.
    :returns: The resulting scenario
    """

    _LOGGER.debug(f"Converting OSM {osm_file} to CommonRoad Scenario")

    with _redirect_all_undirected_log_messages(_LOGGER):
        graph = GraphScenario(str(osm_file)).graph
        # The CommonRoad Scenario Designer exposes a simple converison function, to
        # convert an OpenStreetMap graph to a CommonRoad scenario. But, the function also
        # creates the location by looking it up in the geonames database.
        # Because, this process is currently broken, the location is looked up below
        # and a custom conversion logic is implemented here.
        scenario, _ = create_scenario_intermediate(graph)
        sanitize(scenario)

    coordinates = Coordinates.from_tuple(graph.center_point)
    map_metadata = RegionMetadata.from_coordinates(coordinates)
    scenario.location = map_metadata.as_commonroad_scenario_location()
    scenario.scenario_id = map_metadata.as_commonroad_scenario_id()
    scenario.source = DEFAULT_OSM_SOURCE

    # During the osm2cr conversion, the coordinates inside the scenario are also
    # projected into the cartesian coordinate system. The resulting coordinates can be very large,
    # which leads to downstream problems and is generally unwanted. Therefore, the scenario is
    # shifted so that the (0,0) coordinate equals the GPS coordinates in the scenario location.
    scenario.translate_rotate(-np.array(coordinates.as_tuple_cartesian()), angle=0.0)

    _LOGGER.debug(f"Convertered OSM {osm_file} at {map_metadata} to CommonRoad Scenario")
    return scenario
