from dataclasses import dataclass
from typing import List, Optional

from commonroad.scenario.scenario import Scenario

from scenario_factory.generate_senarios import (
    convert_commonroad_scenario_to_sumo_scenario,
    generate_ego_scenarios_with_planning_problem_set_from_simulated_scenario,
    simulate_commonroad_scenario,
)
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map, pipeline_map_with_args
from scenario_factory.scenario_types import EgoScenarioWithPlanningProblemSet, SimulatedScenario, SumoScenario


@pipeline_map
def pipeline_create_sumo_configuration_for_commonroad_scenario(
    ctx: PipelineContext, commonroad_scenario: Scenario
) -> SumoScenario:
    output_folder = ctx.get_temporary_folder("output")
    intermediate_sumo_files_path = output_folder.joinpath("intermediate", str(commonroad_scenario.scenario_id))
    intermediate_sumo_files_path.mkdir(parents=True, exist_ok=True)

    sumo_config = ctx.get_sumo_config_for_scenario(commonroad_scenario)
    scenario_wrapper = convert_commonroad_scenario_to_sumo_scenario(
        commonroad_scenario, intermediate_sumo_files_path, sumo_config
    )
    return scenario_wrapper


@pipeline_map
def pipeline_simulate_scenario(ctx: PipelineContext, sumo_scenario: SumoScenario) -> SimulatedScenario:
    sumo_config = ctx.get_sumo_config_for_scenario(sumo_scenario.scenario)

    simulated_scenario = simulate_commonroad_scenario(sumo_scenario, sumo_config)
    return simulated_scenario


@dataclass
class GenerateCommonRoadScenariosArguments(PipelineStepArguments):
    create_noninteractive: bool = True
    create_interactive: bool = False
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
        create_noninteractive=args.create_noninteractive,
        create_interactive=args.create_interactive,
    )


__all__ = [
    "pipeline_create_sumo_configuration_for_commonroad_scenario",
    "pipeline_simulate_scenario",
    "GenerateCommonRoadScenariosArguments",
    "pipeline_generate_ego_scenarios",
]
