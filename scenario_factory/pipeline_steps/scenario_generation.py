__all__ = [
    "pipeline_simulate_scenario_with_sumo",
    "GenerateCommonRoadScenariosArguments",
    "pipeline_generate_ego_scenarios",
    "pipeline_assign_tags_to_scenario",
]

from dataclasses import dataclass
from typing import List, Optional

from commonroad.scenario.scenario import Scenario

from scenario_factory.generate_senarios import (
    convert_commonroad_scenario_to_sumo_scenario,
    generate_ego_scenarios_with_planning_problem_set_from_simulated_scenario,
    simulate_commonroad_scenario,
)
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map, pipeline_map_with_args
from scenario_factory.scenario_types import EgoScenarioWithPlanningProblemSet, SimulatedScenario
from scenario_factory.tags import find_applicable_tags_for_scenario


@pipeline_map
def pipeline_simulate_scenario_with_sumo(ctx: PipelineContext, commonroad_scenario: Scenario) -> SimulatedScenario:
    output_folder = ctx.get_temporary_folder("output")
    intermediate_sumo_files_path = output_folder.joinpath("intermediate", str(commonroad_scenario.scenario_id))
    intermediate_sumo_files_path.mkdir(parents=True, exist_ok=True)

    sumo_config = ctx.get_sumo_config_for_scenario(commonroad_scenario)
    scenario_wrapper = convert_commonroad_scenario_to_sumo_scenario(
        commonroad_scenario, intermediate_sumo_files_path, sumo_config
    )
    simulated_scenario = simulate_commonroad_scenario(scenario_wrapper, sumo_config)
    return simulated_scenario


@dataclass
class GenerateCommonRoadScenariosArguments(PipelineStepArguments):
    max_collisions: Optional[int] = None


@pipeline_map_with_args
def pipeline_generate_ego_scenarios(
    args: GenerateCommonRoadScenariosArguments, ctx: PipelineContext, simulated_scenario: SimulatedScenario
) -> List[EgoScenarioWithPlanningProblemSet]:
    scenario_config = ctx.get_scenario_config()

    return generate_ego_scenarios_with_planning_problem_set_from_simulated_scenario(
        simulated_scenario,
        scenario_config,
        max_collisions=args.max_collisions,
    )


@pipeline_map
def pipeline_assign_tags_to_scenario(
    ctx: PipelineContext, ego_scenario: EgoScenarioWithPlanningProblemSet
) -> EgoScenarioWithPlanningProblemSet:
    tags = find_applicable_tags_for_scenario(ego_scenario.scenario)
    if ego_scenario.scenario.tags is None:
        ego_scenario.scenario.tags = tags
    else:
        ego_scenario.scenario.tags.update(tags)

    return ego_scenario
