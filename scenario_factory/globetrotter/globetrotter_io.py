import os.path
from typing import List, Tuple

import crdesigner.map_conversion.osm2cr.converter_modules.converter as converter
import numpy as np
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.file_writer import CommonRoadFileWriter
from commonroad.common.writer.file_writer_interface import OverwriteExistingFile
from commonroad.scenario.scenario import Location, Scenario
from crdesigner.map_conversion.osm2cr.converter_modules.cr_operations.export import (
    create_scenario_intermediate,
)
from crdesigner.map_conversion.osm2cr.converter_modules.graph_operations import (
    road_graph as rg,
)
from crdesigner.map_conversion.osm2cr.converter_modules.utility.geonamesID import (
    get_geonamesID,
)
from scenario_factory.globetrotter.intersection import Intersection
from pathlib import Path


def save_as_cr(graph: rg.Graph, file_path: str) -> None:
    """
    Hotfix for saving a graph as a CommonRoad scenario
    """
    scenario, intermediate_format = create_scenario_intermediate(graph)
    problemset = intermediate_format.get_dummy_planning_problem_set()
    location = Location(
        gps_latitude=graph.center_point[0],
        gps_longitude=graph.center_point[1],
        geo_name_id=get_geonamesID(graph.center_point[0], graph.center_point[1]),
        geo_transformation=None,
    )

    print(f"Found {len(scenario.lanelet_network.traffic_signs)} traffic signs")
    print(f"Found {len(scenario.lanelet_network.traffic_lights)} traffic lights")
    file_writer = CommonRoadFileWriter(
        scenario,
        problemset,
        author="scenario-factory",
        affiliation="TUM, Germany",
        source="OpenStreetMaps",
        tags=set(),
        location=location,
    )
    file_writer.write_to_file(file_path, OverwriteExistingFile.ALWAYS)


def osm2commonroad(osm_path: Path, commonroad_xml_path: Path) -> None:
    scenario = converter.GraphScenario(str(osm_path))

    # Note: We really want to call scenario.save_as_cr(commonroad_xml_path)
    # However this removes some traffic signs we want to keep, therefore
    # save_as_cr is a hotfix that does the same thing but w/o removing the traffic signs

    # scenario.save_as_cr(commonroad_xml_path)
    save_as_cr(scenario.graph, str(commonroad_xml_path))


def commonroad_parse(commonroad_xml_path: Path) -> Tuple[Scenario, np.ndarray]:
    """
    Get scenario and forking points from a CommonRoad XML file.

    :param commonroad_xml_path: CommonRoad scenario saved as an XML file
    :return: A tuple with the scenario and a numpy array containing the forking points
    """
    scenario, _ = CommonRoadFileReader(commonroad_xml_path).open()
    lanelets = scenario.lanelet_network.lanelets
    forking_set = set()

    lanelet_ids = [lanelet.lanelet_id for lanelet in lanelets]

    for lanelet in lanelets:
        if len(lanelet.predecessor) > 1 and set(lanelet.predecessor).issubset(
            lanelet_ids
        ):
            forking_set.add(
                (lanelet.center_vertices[0][0], lanelet.center_vertices[0][1])
            )
        if len(lanelet.successor) > 1 and set(lanelet.successor).issubset(lanelet_ids):
            forking_set.add(
                (lanelet.center_vertices[-1][0], lanelet.center_vertices[-1][1])
            )

    forking_points = np.array(list(forking_set))
    return scenario, forking_points


def save_intersections(intersections: List[Intersection], output_dir: Path, name: str) -> None:
    """
    Save intersections a CommonRoad XML files

    Every intersection will be saved as a separate file.

    :param intersections: A list of intersections to save
    :param output_dir: The output directory
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, intersection in enumerate(intersections):
        intersection.intersection_to_xml(
            os.path.join(output_dir, f"{name}-{i+1}.xml")
        )
