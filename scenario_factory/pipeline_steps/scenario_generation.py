__all__ = [
    "pipeline_find_ego_vehicle_maneuvers",
    "pipeline_filter_ego_vehicle_maneuver",
    "pipeline_select_one_maneuver_per_ego_vehicle",
    "pipeline_generate_scenario_for_ego_vehicle_maneuver",
]

import logging
from collections import defaultdict
from typing import Iterable, List, Sequence

from commonroad.common.solution import Solution

from scenario_factory.ego_vehicle_selection.criterions import EgoVehicleSelectionCriterion
from scenario_factory.ego_vehicle_selection.filters import EgoVehicleManeuverFilter
from scenario_factory.ego_vehicle_selection.maneuver import EgoVehicleManeuver
from scenario_factory.ego_vehicle_selection.selection import (
    find_ego_vehicle_maneuvers_in_scenario,
    select_one_maneuver_per_ego_vehicle,
)
from scenario_factory.pipeline import (
    PipelineContext,
    pipeline_filter,
    pipeline_fold,
    pipeline_map,
)
from scenario_factory.scenario_container import (
    ScenarioContainer,
)
from scenario_factory.scenario_generation import (
    generate_scenario_with_planning_problem_set_and_solution_for_ego_vehicle_maneuver,
)

_LOGGER = logging.getLogger(__name__)


@pipeline_map()
def pipeline_find_ego_vehicle_maneuvers(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    criterions: Iterable[EgoVehicleSelectionCriterion],
) -> List[ScenarioContainer]:
    """
    Find vehicles in the scenario that perform a maneuver that could qualify them as an ego vehicle.

    :param args: `FindEgoVehicleManeuversArguments` that specify the criterions according to which maneuvers will be determined
    :param ctx: The context for this pipeline execution
    :param scenario_container: The scenario in which maneuvers should be detected. Will not be modified.
    """
    ego_vehicle_maneuvers = find_ego_vehicle_maneuvers_in_scenario(
        scenario_container.scenario, criterions
    )
    _LOGGER.debug(
        "Identified %s maneuvers in scenario %s that could qualify for an ego vehicle",
        len(ego_vehicle_maneuvers),
        scenario_container.scenario.scenario_id,
    )
    return [
        ScenarioContainer(scenario_container.scenario, ego_vehicle_maneuver=ego_vehicle_maneuver)
        for ego_vehicle_maneuver in ego_vehicle_maneuvers
    ]


@pipeline_filter()
def pipeline_filter_ego_vehicle_maneuver(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    filter: EgoVehicleManeuverFilter,
) -> bool:
    """
    Only include ego vehicle maneuvers that match the given filter predicate.
    Usually applied after `pipeline_find_ego_vehicle_maneuvers`, to filter maneuvers out, from which no interesting new scenario can be derived.

    Usage:

        pipeline.filter(pipeline_filter_ego_vehicle_maneuver(LongEnoughManeuverFilter()))

    :param filter: The filter predicate that should be applied. Must be supplied
    :param ctx: The context for this pipeline execution.
    :param scenario_container: Scenario with an ego vehicle maneuver. Will not be modified.

    :return: Whether the filter predicate matched.
    """
    ego_vehicle_maneuver = scenario_container.get_attachment(EgoVehicleManeuver)
    if ego_vehicle_maneuver is None:
        raise ValueError(
            f"Pipelinen step `pipeline_filter_ego_vehicle_maneuver` requires a scenario with an ego vehicle maneuver, but got {type(scenario_container)}"
        )
    scenario_factory_config = ctx.get_scenario_factory_config()
    return filter.matches(
        scenario_container.scenario,
        scenario_factory_config.cr_scenario_time_steps,
        ego_vehicle_maneuver,
    )


@pipeline_fold()
def pipeline_select_one_maneuver_per_ego_vehicle(
    ctx: PipelineContext, scenario_containers: Sequence[ScenarioContainer]
) -> Sequence[ScenarioContainer]:
    """

    :param ctx: The context for this pipeline execution
    :param scenario_containers:
    """
    scenario_factory_config = ctx.get_scenario_factory_config()

    ego_vehicle_maneuvers_sorted_by_scenario_id = defaultdict(list)
    scenario_id_map = dict()
    for scenario_container in scenario_containers:
        ego_vehicle_maneuver = scenario_container.get_attachment(EgoVehicleManeuver)
        if ego_vehicle_maneuver is None:
            raise ValueError()

        ego_vehicle_maneuvers_sorted_by_scenario_id[scenario_container.scenario.scenario_id].append(
            ego_vehicle_maneuver
        )
        scenario_id_map[scenario_container.scenario.scenario_id] = scenario_container.scenario

    results = []
    for (
        scenario_id,
        ego_vehicle_maneuvers,
    ) in ego_vehicle_maneuvers_sorted_by_scenario_id.items():
        commonroad_scenario = scenario_id_map[scenario_id]
        maneuvers = select_one_maneuver_per_ego_vehicle(
            commonroad_scenario,
            ego_vehicle_maneuvers,
            scenario_factory_config.sensor_range,
        )
        for maneuver in maneuvers:
            results.append(ScenarioContainer(commonroad_scenario, ego_vehicle_maneuver=maneuver))

    return results


@pipeline_map()
def pipeline_generate_scenario_for_ego_vehicle_maneuver(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    ego_vehicle_maneuver = scenario_container.get_attachment(EgoVehicleManeuver)
    if ego_vehicle_maneuver is None:
        raise ValueError()

    scenario_config = ctx.get_scenario_factory_config()

    (
        scenario,
        planning_problem_set,
        planning_problem_solution,
    ) = generate_scenario_with_planning_problem_set_and_solution_for_ego_vehicle_maneuver(
        scenario_container.scenario,
        ego_vehicle_maneuver,
        scenario_config,
    )

    solution = Solution(scenario.scenario_id, [planning_problem_solution])
    return ScenarioContainer(scenario, planning_problem_set=planning_problem_set, solution=solution)
