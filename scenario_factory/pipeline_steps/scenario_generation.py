__all__ = [
    "pipeline_simulate_scenario_with_sumo",
    "GenerateCommonRoadScenariosArguments",
]

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Sequence

from scenario_factory.ego_vehicle_selection.criterions import EgoVehicleSelectionCriterion
from scenario_factory.ego_vehicle_selection.filters import EgoVehicleManeuverFilter
from scenario_factory.ego_vehicle_selection.selection import (
    find_ego_vehicle_maneuvers_in_scenario,
    select_one_maneuver_per_ego_vehicle,
)
from scenario_factory.generate_senarios import generate_scenario_with_planning_problem_set_for_ego_vehicle_maneuver
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_filter,
    pipeline_fold,
    pipeline_map,
    pipeline_map_with_args,
)
from scenario_factory.scenario_types import (
    ScenarioContainer,
    ScenarioWithEgoVehicleManeuver,
    ScenarioWithPlanningProblemSet,
)
from scenario_factory.sumo import convert_commonroad_scenario_to_sumo_scenario, simulate_commonroad_scenario


@pipeline_map
def pipeline_simulate_scenario_with_sumo(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    commonroad_scenario = scenario_container.scenario
    output_folder = ctx.get_temporary_folder("output")
    intermediate_sumo_files_path = output_folder.joinpath("intermediate", str(commonroad_scenario.scenario_id))
    intermediate_sumo_files_path.mkdir(parents=True, exist_ok=True)

    sumo_config = ctx.get_sumo_config_for_scenario(commonroad_scenario)
    scenario_wrapper = convert_commonroad_scenario_to_sumo_scenario(
        commonroad_scenario, intermediate_sumo_files_path, sumo_config
    )
    simulated_scenario = simulate_commonroad_scenario(scenario_wrapper, sumo_config)
    return ScenarioContainer(simulated_scenario)


@dataclass
class FindEgoVehicleManeuversArguments(PipelineStepArguments):
    criterions: Sequence[EgoVehicleSelectionCriterion]


@pipeline_map_with_args
def pipeline_find_ego_vehicle_maneuvers(
    args: FindEgoVehicleManeuversArguments, ctx: PipelineContext, scenario_container: ScenarioContainer
) -> List[ScenarioWithEgoVehicleManeuver]:
    ego_vehicle_maneuvers = find_ego_vehicle_maneuvers_in_scenario(scenario_container.scenario, args.criterions)
    return [
        ScenarioWithEgoVehicleManeuver(scenario_container.scenario, ego_vehicle_maneuver)
        for ego_vehicle_maneuver in ego_vehicle_maneuvers
    ]


@pipeline_filter
def pipeline_filter_ego_vehicle_maneuver(
    filter: EgoVehicleManeuverFilter, ctx: PipelineContext, scenario_container: ScenarioWithEgoVehicleManeuver
) -> bool:
    scenario_factory_config = ctx.get_scenario_config()
    return filter.matches(
        scenario_container.scenario,
        scenario_factory_config.cr_scenario_time_steps,
        scenario_container.ego_vehicle_maneuver,
    )


@pipeline_fold
def pipeline_select_one_maneuver_per_ego_vehicle(
    ctx: PipelineContext, scenario_containers: Sequence[ScenarioWithEgoVehicleManeuver]
) -> Sequence[ScenarioWithEgoVehicleManeuver]:
    scenario_factory_config = ctx.get_scenario_config()

    ego_vehicle_maneuvers_sorted_by_scenario_id = defaultdict(list)
    scenario_id_map = dict()
    for scenario_container in scenario_containers:
        ego_vehicle_maneuvers_sorted_by_scenario_id[scenario_container.scenario.scenario_id].append(
            scenario_container.ego_vehicle_maneuver
        )
        scenario_id_map[scenario_container.scenario.scenario_id] = scenario_container.scenario

    results = []
    for scenario_id, ego_vehicle_maneuvers in ego_vehicle_maneuvers_sorted_by_scenario_id.items():
        commonroad_scenario = scenario_id_map[scenario_id]
        maneuvers = select_one_maneuver_per_ego_vehicle(
            commonroad_scenario, ego_vehicle_maneuvers, scenario_factory_config.sensor_range
        )
        for maneuver in maneuvers:
            results.append(ScenarioWithEgoVehicleManeuver(commonroad_scenario, maneuver))

    return results


@dataclass
class GenerateCommonRoadScenariosArguments(PipelineStepArguments):
    max_collisions: Optional[int] = None


@pipeline_map_with_args
def pipeline_generate_scenario_for_ego_vehicle_maneuver(
    args: GenerateCommonRoadScenariosArguments, ctx: PipelineContext, scenario_container: ScenarioWithEgoVehicleManeuver
) -> ScenarioWithPlanningProblemSet:
    scenario_config = ctx.get_scenario_config()

    scenario, planning_problem_set = generate_scenario_with_planning_problem_set_for_ego_vehicle_maneuver(
        scenario_container.scenario,
        scenario_container.ego_vehicle_maneuver,
        scenario_config,
        max_collisions=args.max_collisions,
    )

    return ScenarioWithPlanningProblemSet(scenario, planning_problem_set)
