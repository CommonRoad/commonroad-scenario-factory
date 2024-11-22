import copy
from typing import Iterator, List, Tuple

from commonroad.common.util import Interval
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario


def get_scenario_final_time_step(scenario: Scenario) -> int:
    """
    Determines the maximum time step in a scenario. This is usefull, to determine the length of a scenario.

    :param scenario: The scenario to analyze.

    :return: The final time step in the scenario, or 0 if no obstacles are in the scenario/
    """
    max_time_step = 0
    for dynamic_obstacle in scenario.dynamic_obstacles:
        if dynamic_obstacle.prediction is None:
            max_time_step = max(max_time_step, dynamic_obstacle.initial_state.time_step)
            continue

        max_time_step = max(max_time_step, dynamic_obstacle.prediction.final_time_step)

    if isinstance(max_time_step, Interval):
        return int(max_time_step.end)
    else:
        return max_time_step


def get_scenario_start_time_step(scenario: Scenario) -> int:
    """
    Determines the minimum time step in a scenario.

    :param scenario: The scenario to analyze.

    :return: The first time step in the scenario, or 0 if no obstacles are in the scenario.
    """
    time_steps = [
        dynamic_obstacle.initial_state.time_step for dynamic_obstacle in scenario.dynamic_obstacles
    ]
    if len(time_steps) == 0:
        return 0

    min_time_step = min(time_steps)

    if isinstance(min_time_step, Interval):
        return int(min_time_step.start)
    else:
        return min_time_step


def _create_new_scenario_with_metadata_from_old_scenario(scenario: Scenario) -> Scenario:
    """
    Create a new scenario from an old scenario and include all its metadata.

    :param scenario: The old scenario, from which the metadata will be taken

    :returns: The new scenario with all metadata, which is safe to modify.
    """
    new_scenario = Scenario(
        dt=scenario.dt,
        # The following metadata values are all objects. As they could be arbitrarily modified in-place they need to be copied.
        scenario_id=copy.deepcopy(scenario.scenario_id),
        location=copy.deepcopy(scenario.location),
        tags=copy.deepcopy(scenario.tags),
        # Author, afiiliation and source are plain strings and do not need to be copied
        author=scenario.author,
        affiliation=scenario.affiliation,
        source=scenario.source,
    )

    return new_scenario


def copy_scenario(
    scenario: Scenario,
    copy_lanelet_network: bool = True,
    copy_dynamic_obstacles: bool = True,
    copy_static_obstacles: bool = True,
    copy_environment_obstacles: bool = True,
    copy_phantom_obstacles: bool = True,
) -> Scenario:
    """
    Helper to efficiently copy a CommonRoad Scenario. Should be prefered over a simple deepcopy of the scenario object, if not all elements of the input scenario are required in the end (e.g. the dynamic obstacles should not be included)

    :param scenario: The scenario to be copied.
    :param copy_lanelet_network: If True, the lanelet network (and all of its content) will be copied to the new scenario. If False, the new scenario will have no lanelet network.
    :param copy_dynamic_obstacles: If True, the dynamic obtsacles will be copied to the new scenario. If False, the new scenario will have no dynamic obstacles.
    :param copy_static_obstacles: If True, the static obstacles will be copied to the new scenario. If False, the new scenario will have no static obstacles.
    :param copy_environment_obstacles: If True, the environment obstacles will be copied to the new scenario. If False, the new scenario will have no environment obstacles.
    :param copy_phantom_obstacles: If True, the phantom obstacles will be copied to the new scenario. If False, the new scenario will have no phantom obstacles.
    """
    new_scenario = _create_new_scenario_with_metadata_from_old_scenario(scenario)

    if copy_lanelet_network:
        # It is necessary that `create_from_lanelet_network` is used instead of a simple deepcopy
        # because the geoemtry cache inside lanelet network might otherwise be incomplete
        new_lanelet_network = LaneletNetwork.create_from_lanelet_network(scenario.lanelet_network)
        new_scenario.add_objects(new_lanelet_network)

    if copy_dynamic_obstacles:
        for dynamic_obstacle in scenario.dynamic_obstacles:
            new_scenario.add_objects(copy.deepcopy(dynamic_obstacle))

    if copy_static_obstacles:
        for static_obstacle in scenario.static_obstacles:
            new_scenario.add_objects(copy.deepcopy(static_obstacle))

    if copy_environment_obstacles:
        for environment_obstacle in scenario.environment_obstacle:
            new_scenario.add_objects(copy.deepcopy(environment_obstacle))

    if copy_phantom_obstacles:
        for phatom_obstacle in scenario.phantom_obstacle:
            new_scenario.add_objects(copy.deepcopy(phatom_obstacle))

    return new_scenario


def get_dynamic_obstacle_ids_in_scenario(scenario: Scenario) -> List[int]:
    return [dynamic_obstacle.obstacle_id for dynamic_obstacle in scenario.dynamic_obstacles]


def iterate_zipped_dynamic_obstacles_from_scenarios(
    *scenarios: Scenario,
) -> Iterator[Tuple[DynamicObstacle, ...]]:
    """
    Iterates over zipped dynamic obstacles across multiple scenarios.

    This function ensures that dynamic obstacles with matching IDs are
    present in all provided scenarios and yields them as tuples,
    one from each scenario.

     :param scenario: A variable number of `Scenario` objects
        to zip dynamic obstacles from. The first scenario is used as
        the reference.

    :yields: Tuples of matching `DynamicObstacle` objects across the scenarios.

    :raises RuntimeError: If a dynamic obstacle in the base scenario is
        missing or not a `DynamicObstacle` in other scenarios.
    """
    # Simply use the first scenario as the "base" scenario. This way, it is implicitly assume that
    # all dynamic obstacles from this "base" scenario are also in the other scenarios.

    base_scenario = scenarios[0]
    common_obstacle_ids = set(get_dynamic_obstacle_ids_in_scenario(base_scenario))
    for scenario in scenarios[1:]:
        common_obstacle_ids.intersection_update(get_dynamic_obstacle_ids_in_scenario(scenario))

    if len(common_obstacle_ids) == 0:
        raise RuntimeError(
            f"Cannot zip obstacles from the scenarios {', '.join([str(scenario.scenario_id) for scenario in scenarios])}: The scenarios do not have a single obstacle in common!"
        )

    for dynamic_obstacle_id in common_obstacle_ids:
        all_obstacles = []
        for scenario in scenarios:
            dynamic_obstacle = scenario.obstacle_by_id(dynamic_obstacle_id)
            if dynamic_obstacle is None:
                raise RuntimeError(
                    f"Cannot zip obstacles from scenario {scenario.scenario_id}: The obstacle {dynamic_obstacle_id} is not part of the scenario, but it was determined to be there. This is a bug!"
                )

            if not isinstance(dynamic_obstacle, DynamicObstacle):
                raise RuntimeError(
                    f"Cannot zip obstacles from scenario {scenario.scenario_id}: The obstacle {dynamic_obstacle.obstacle_id} is part of the scenario, but is not a dynamic obstacle!"
                )

            all_obstacles.append(dynamic_obstacle)
        yield tuple(all_obstacles)
