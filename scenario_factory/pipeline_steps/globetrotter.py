from typing import List

from commonroad.scenario.scenario import Scenario

from scenario_factory.globetrotter import extract_intersections_from_scenario
from scenario_factory.pipeline import PipelineContext, pipeline_map


@pipeline_map
def pipeline_extract_intersections(ctx: PipelineContext, scenario: Scenario) -> List[Scenario]:
    """
    Extract all intersections from the scenario.
    """

    new_scenarios = extract_intersections_from_scenario(scenario)
    return new_scenarios


__all__ = [
    "pipeline_extract_intersections",
]
