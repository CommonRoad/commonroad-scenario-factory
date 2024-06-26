from copy import deepcopy
from dataclasses import dataclass
from typing import List, Optional, Tuple

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.scenario.scenario_wrapper import ScenarioWrapper

from scenario_factory.ego_vehicle_selection import select_interesting_ego_vehicle_maneuvers_from_scenario
from scenario_factory.generate_senarios import (
    convert_commonroad_scenario_to_sumo,
    create_planning_problem_set_for_ego_vehicle_maneuver,
    create_scenario_for_ego_vehicle_maneuver,
    delete_colliding_obstacles_from_scenario,
    reduce_scenario_to_interactive_scenario,
)
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map, pipeline_map_with_args


@pipeline_map
def pipeline_create_sumo_configuration_for_commonroad_scenario(
    ctx: PipelineContext, commonroad_scenario: Scenario
) -> ScenarioWrapper:
    output_folder = ctx.get_output_folder("output")
    intermediate_sumo_files_path = output_folder.joinpath("intermediate", str(commonroad_scenario.scenario_id))
    intermediate_sumo_files_path.mkdir(parents=True, exist_ok=True)

    sumo_config = ctx.get_sumo_config_for_scenario(commonroad_scenario)
    scenario_wrapper = convert_commonroad_scenario_to_sumo(commonroad_scenario, output_folder, sumo_config)
    return scenario_wrapper


@pipeline_map
def pipeline_simulate_scenario(ctx: PipelineContext, scenario_wrapper: ScenarioWrapper) -> Scenario:
    sumo_config = ctx.get_sumo_config_for_scenario(scenario_wrapper.initial_scenario)
    sumo_sim = SumoSimulation()
    sumo_sim.initialize(sumo_config, scenario_wrapper)

    for _ in range(sumo_config.simulation_steps):
        sumo_sim.simulate_step()
    sumo_sim.simulate_step()

    sumo_sim.stop()

    scenario = sumo_sim.commonroad_scenarios_all_time_steps()

    return scenario


@dataclass
class GenerateCommonRoadScenariosArguments(PipelineStepArguments):
    create_noninteractive: bool = True
    create_interactive: bool = False
    max_collisions: Optional[int] = None


@pipeline_map_with_args
def pipeline_generate_cr_scenarios(
    args: GenerateCommonRoadScenariosArguments, ctx: PipelineContext, scenario: Scenario
) -> List[Tuple[PlanningProblemSet, Scenario]]:
    scenario_config = ctx.get_scenario_config()

    num_collisions = len(delete_colliding_obstacles_from_scenario(scenario, all=True))
    if args.max_collisions is not None:
        if num_collisions > args.max_collisions:
            raise RuntimeError(
                f"Skipping scenario {scenario.scenario_id} because it has {num_collisions}, but the maximum allowed number of collisions is {args.max_collisions}"
            )

    ego_vehicle_maneuvers = select_interesting_ego_vehicle_maneuvers_from_scenario(
        scenario,
        criterions=scenario_config.criterions,
        filters=scenario_config.filters,
        scenario_time_steps=scenario_config.cr_scenario_time_steps,
        sensor_range=scenario_config.sensor_range,
    )

    results = []

    for i, maneuver in enumerate(ego_vehicle_maneuvers):
        new_scenario = create_scenario_for_ego_vehicle_maneuver(scenario, scenario_config, maneuver)
        new_scenario.scenario_id.prediction_id = i + 1

        planning_problem_set = create_planning_problem_set_for_ego_vehicle_maneuver(
            new_scenario, scenario_config, maneuver
        )
        if args.create_noninteractive:
            new_noninteractive_scenario = deepcopy(new_scenario)
            new_noninteractive_scenario.scenario_id.obstacle_behavior = "T"

            results.append((planning_problem_set, new_noninteractive_scenario))

        if args.create_interactive:
            new_interactive_scenario = reduce_scenario_to_interactive_scenario(new_scenario)
            new_interactive_scenario.scenario_id.obstacle_behavior = "I"

            results.append((planning_problem_set, new_interactive_scenario))

    return results


__all__ = [
    "pipeline_create_sumo_configuration_for_commonroad_scenario",
    "pipeline_simulate_scenario",
    "GenerateCommonRoadScenariosArguments",
    "pipeline_generate_cr_scenarios",
]
