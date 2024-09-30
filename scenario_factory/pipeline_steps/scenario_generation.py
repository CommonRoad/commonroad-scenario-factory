__all__ = [
    "FindEgoVehicleManeuversArguments",
    "pipeline_find_ego_vehicle_maneuvers",
    "pipeline_filter_ego_vehicle_maneuver",
    "pipeline_select_one_maneuver_per_ego_vehicle",
    "pipeline_generate_scenario_for_ego_vehicle_maneuver",
]

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from scenario_factory.ego_vehicle_selection.criterions import EgoVehicleSelectionCriterion
from scenario_factory.ego_vehicle_selection.filters import EgoVehicleManeuverFilter
from scenario_factory.ego_vehicle_selection.selection import (
    find_ego_vehicle_maneuvers_in_scenario,
    select_one_maneuver_per_ego_vehicle,
)
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_filter,
    pipeline_fold,
    pipeline_map,
    pipeline_map_with_args,
)
from scenario_factory.scenario_generation import (
    generate_scenario_with_planning_problem_set_and_solution_for_ego_vehicle_maneuver,
)
from scenario_factory.scenario_types import ScenarioContainer, ScenarioWithEgoVehicleManeuver, ScenarioWithSolution

_LOGGER = logging.getLogger(__name__)


@dataclass
class FindEgoVehicleManeuversArguments(PipelineStepArguments):
    criterions: Iterable[EgoVehicleSelectionCriterion]


@pipeline_map_with_args()
def pipeline_find_ego_vehicle_maneuvers(
    args: FindEgoVehicleManeuversArguments, ctx: PipelineContext, scenario_container: ScenarioContainer
) -> List[ScenarioWithEgoVehicleManeuver]:
    """
    Find maneuvers in the scenario that qualify as interesting according to the criterions.
    """
    ego_vehicle_maneuvers = find_ego_vehicle_maneuvers_in_scenario(scenario_container.scenario, args.criterions)
    _LOGGER.debug(
        "Identified %s maneuvers in scenario %s that could qualify for an ego vehicle",
        len(ego_vehicle_maneuvers),
        scenario_container.scenario.scenario_id,
    )
    return [
        ScenarioWithEgoVehicleManeuver(scenario_container.scenario, ego_vehicle_maneuver)
        for ego_vehicle_maneuver in ego_vehicle_maneuvers
    ]


@pipeline_filter()
def pipeline_filter_ego_vehicle_maneuver(
    filter: EgoVehicleManeuverFilter, ctx: PipelineContext, scenario_container: ScenarioWithEgoVehicleManeuver
) -> bool:
    scenario_factory_config = ctx.get_scenario_factory_config()
    return filter.matches(
        scenario_container.scenario,
        scenario_factory_config.cr_scenario_time_steps,
        scenario_container.ego_vehicle_maneuver,
    )


@pipeline_fold()
def pipeline_select_one_maneuver_per_ego_vehicle(
    ctx: PipelineContext, scenario_containers: Sequence[ScenarioWithEgoVehicleManeuver]
) -> Sequence[ScenarioWithEgoVehicleManeuver]:
    scenario_factory_config = ctx.get_scenario_factory_config()

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


@pipeline_map()
def pipeline_generate_scenario_for_ego_vehicle_maneuver(
    ctx: PipelineContext, scenario_container: ScenarioWithEgoVehicleManeuver
) -> ScenarioWithSolution:
    scenario_config = ctx.get_scenario_factory_config()

    (
        scenario,
        planning_problem_set,
        planning_problem_solution,
    ) = generate_scenario_with_planning_problem_set_and_solution_for_ego_vehicle_maneuver(
        scenario_container.scenario,
        scenario_container.ego_vehicle_maneuver,
        scenario_config,
    )

    return ScenarioWithSolution(scenario, planning_problem_set, [planning_problem_solution])
