from functools import lru_cache
from pathlib import Path

from commonroad.scenario.scenario import Location, Scenario, ScenarioID
from commonroad.scenario.traffic_sign import TrafficSignIDZamunda
from crdesigner.map_conversion.osm2cr.converter_modules.converter import GraphScenario
from crdesigner.map_conversion.osm2cr.converter_modules.cr_operations.export import create_scenario_intermediate
from crdesigner.map_conversion.osm2cr.converter_modules.utility.geonamesID import get_geonamesID
from crdesigner.map_conversion.osm2cr.converter_modules.utility.labeling_create_tree import create_tree_from_file


@lru_cache
def get_geonames_tree():
    geonames_tree = create_tree_from_file()
    return geonames_tree


def convert_osm_file_to_commonroad_scenario(osm_file: Path) -> Scenario:
    """
    Convert an OSM file to a CommonRoad XML file.

    Args:
        osm_file (Path): Path to the OSM file.
    """
    geonames_tree = get_geonames_tree()
    # conversion
    print(f"======== Converting {osm_file.stem} ========")

    graph = GraphScenario(str(osm_file)).graph
    scenario, intermediate_format = create_scenario_intermediate(graph)
    location = Location(
        gps_latitude=graph.center_point[0],
        gps_longitude=graph.center_point[1],
        geo_name_id=get_geonamesID(graph.center_point[0], graph.center_point[1], geonames_tree),
        geo_transformation=None,
    )

    print(f"Found {len(scenario.lanelet_network.traffic_signs)} traffic signs")
    print(f"Found {len(scenario.lanelet_network.traffic_lights)} traffic lights")

    # map repairing
    # simplified repairing by Florian
    referenced_traffic_lights = set()
    referenced_traffic_signs = set()
    for lanelet in scenario.lanelet_network.lanelets:
        for traffic_light in lanelet.traffic_lights:
            referenced_traffic_lights.add(traffic_light)

        for traffic_sign in lanelet.traffic_signs:
            referenced_traffic_signs.add(traffic_sign)

    for traffic_light in scenario.lanelet_network.traffic_lights:
        if traffic_light.traffic_light_id not in referenced_traffic_lights:
            scenario.lanelet_network.remove_traffic_light(traffic_light.traffic_light_id)

    for traffic_sign in scenario.lanelet_network.traffic_signs:
        if traffic_sign.traffic_sign_id not in referenced_traffic_signs:
            scenario.lanelet_network.remove_traffic_sign(traffic_sign.traffic_sign_id)

    for traffic_sign in scenario.lanelet_network.traffic_signs:
        for tse in traffic_sign.traffic_sign_elements:
            if tse.traffic_sign_element_id == TrafficSignIDZamunda.YIELD:
                tse.additional_values = []

    # TODO: Use correct scenario_id
    country_id = osm_file.stem.split("_")[0]
    map_name = osm_file.stem.split("_")[-1]
    scenario.scenario_id = ScenarioID(country_id=country_id, map_name=map_name)
    scenario.location = location

    return scenario
