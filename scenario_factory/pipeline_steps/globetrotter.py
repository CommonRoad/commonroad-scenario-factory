from typing import List

from commonroad.scenario.scenario import Scenario

from scenario_factory.globetrotter import generate_intersections, extract_forking_points
from scenario_factory.pipeline import PipelineContext, pipeline_map


@pipeline_map
def pipeline_extract_intersections(ctx: PipelineContext, scenario: Scenario) -> List[Scenario]:
    """
    Run the Globetrotter algorithm on the CommonRoad files.

    Args:
        commonroad_folder (Path): Path to the folder containing the CommonRoad files.

    Returns:
        Path: Path to the folder containing the generated Globetrotter files.
    """
    forking_points = extract_forking_points(scenario)

    new_scenarios, _ = generate_intersections(scenario, forking_points)

    return new_scenarios


__all__ = [
    "pipeline_extract_intersections",
]
