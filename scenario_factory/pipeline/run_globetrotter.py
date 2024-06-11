from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from commonroad.scenario.scenario import Scenario

from scenario_factory.globetrotter.clustering import generate_intersections
from scenario_factory.globetrotter.intersection import Intersection
from scenario_factory.pipeline.context import PipelineContext, PipelineStepArguments


def extract_intersections(
    ctx: PipelineContext, input_: Tuple[Scenario, np.ndarray], args: Optional[PipelineStepArguments]
) -> List[Intersection]:
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


def write_intersection_to_file(
    ctx: PipelineContext, intersection: Intersection, args: Optional[PipelineStepArguments]
) -> Path:
    output_folder = ctx.get_output_folder("globetrotter")
    output_file = output_folder.joinpath(f"{intersection.scenario.scenario_id}_{hash(intersection)}.xml")

    intersection.intersection_to_xml(output_file)

    return output_file
