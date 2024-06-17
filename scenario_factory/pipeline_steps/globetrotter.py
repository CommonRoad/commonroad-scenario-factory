from typing import List, Tuple

import numpy as np
from commonroad.scenario.scenario import Scenario

from scenario_factory.globetrotter.clustering import generate_intersections
from scenario_factory.globetrotter.globetrotter_io import extract_forking_points
from scenario_factory.globetrotter.intersection import Intersection
from scenario_factory.pipeline import PipelineContext, pipeline_map


@pipeline_map
def pipeline_extract_intersections(ctx: PipelineContext, input_: Tuple[Scenario, np.ndarray]) -> List[Intersection]:
    """
    Run the Globetrotter algorithm on the CommonRoad files.

    Args:
        commonroad_folder (Path): Path to the folder containing the CommonRoad files.

    Returns:
        Path: Path to the folder containing the generated Globetrotter files.
    """
    scenario, forking_points = input_

    intersections, _ = generate_intersections(scenario, forking_points)

    return intersections


@pipeline_map
def pipeline_extract_forking_points(ctx: PipelineContext, scenario: Scenario) -> Tuple[Scenario, np.ndarray]:
    # TODO: Find a better way, to return both scenario and the forking points
    forking_points = extract_forking_points(scenario)
    return scenario, forking_points


@pipeline_map
def pipeline_convert_intersection_to_commonroad_scenario(ctx: PipelineContext, intersection: Intersection) -> Scenario:
    return intersection.scenario


__all__ = [
    "pipeline_extract_intersections",
    "pipeline_convert_intersection_to_commonroad_scenario",
    "pipeline_extract_forking_points",
]
