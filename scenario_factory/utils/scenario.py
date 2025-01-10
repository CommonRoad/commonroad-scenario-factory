import copy
from collections import defaultdict
from typing import Iterator, List, Optional, Tuple

import numpy as np
from commonroad.common.util import Interval, subtract_orientations
from commonroad.geometry.shape import Circle, Polygon, Rectangle, Shape
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario, ScenarioID
from commonroad.scenario.state import TraceState

from scenario_factory.utils.types import is_state_with_orientation, is_state_with_position


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


def _get_position_point_from_state(state: TraceState) -> Optional[np.ndarray]:
    """
    Reliably get the position of `state` as a single point.

    The position of a state can either be a point or a shape. This function either returns the position if it already is a point, or returns the center of the shape as the position point.

    :param state: The state with a position attribute.

    :returns: The position as a single point, or None if the state does not have the `position `attribute.

    :raises ValueError: If the states position is not a valid shape or a numpy array.
    """
    if not is_state_with_position(state):
        return None

    if (
        isinstance(state.position, Rectangle)
        or isinstance(state.position, Circle)
        or isinstance(state.position, Polygon)
    ):
        return state.position.center
    elif isinstance(state.position, np.ndarray):
        return state.position
    else:
        raise ValueError(
            f"Cannot get position point from state {state}: states position is neither a supported shape nor a numpy arrary!"
        )


def _get_orientation_from_state(state: TraceState) -> Optional[float]:
    """
    Reliably determine the orientation of `state` as float.

    :param state: The state from which the orientation should be retrived.

    :returns: The orientation as a float, or None if no orientation is set.
    """
    if (
        is_state_with_position(state)
        and isinstance(state.position, Rectangle)
        and state.position.orientation is not None
    ):
        return state.position.orientation

    if is_state_with_orientation(state) and isinstance(state.orientation, float):
        return state.orientation
    return None


def find_lanelets_by_state(lanelet_network: LaneletNetwork, state: TraceState) -> List[int]:
    """
    Find all lanelets in `lanelet_network` which match the position of `state`.

    :param lanelet_network: The `LaneletNetwork` on which `state` will be matched.
    :param state: The state to match to `lanelet_network`. Must have the `position` attribute.

    :returns: A list of lanelet ids, which match `state`.

    :raises ValueError: If state does not have a `position` attribute or if the `position` attribute is invalid.
    """
    if not is_state_with_position(state):
        raise ValueError(
            f"Cannot find lanelets for state {state}: state does not have required 'position' attribute!"
        )

    if isinstance(state.position, Shape):
        lanelet_ids = lanelet_network.find_lanelet_by_shape(state.position)
        return lanelet_ids
    elif isinstance(state.position, np.ndarray):
        position_lanelet_ids = lanelet_network.find_lanelet_by_position([state.position])
        assert (
            len(position_lanelet_ids) == 1
        ), "`LaneletNetwork.find_lanelet_by_position` did not return anything for our input. This is a bug in commonroad-io!"
        lanelet_ids = position_lanelet_ids[0]
        return lanelet_ids
    else:
        raise ValueError(
            f"Cannot find lanelets for state {state}: states' position is neither a valid shape nor a numpy array!"
        )


def find_most_likely_lanelet_by_state(
    lanelet_network: LaneletNetwork, state: TraceState
) -> Optional[int]:
    """
    Alternative implementation of `LaneletNetwork.find_most_likely_lanelet_by_state` which can handle different combinations of state attributes. Espacially, states whose position is a shape and not a single point.

    :param lanelet_network: The `LaneletNetwork` to which `state` will be matched.
    :param state: The state which should be matched. Must have at least the `position` attribute. Should have `orientation` attribute, for most likely lanelet matching to work.

    :returns: None if no lanelet matches the state. Otherwise the ID of the most likely lanelet.

    :raises ValueError: If `state` does not have the `position` or `orientation` attribute.
    """
    lanelet_ids = find_lanelets_by_state(lanelet_network, state)

    if len(lanelet_ids) == 0:
        return None
    elif len(lanelet_ids) == 1:
        return lanelet_ids[0]

    # Multiple matching lanelets were found, so we need to determine the most likely one
    position_point = _get_position_point_from_state(state)
    if position_point is None:
        raise ValueError(
            f"Cannot find most likely lanelet for state {state}: state does not have required 'position' attribute!"
        )

    orientation = _get_orientation_from_state(state)
    if orientation is None:
        raise ValueError(
            f"Cannot find most likely lanelet for state {state}: state does not have required 'orientation' attribute!"
        )

    lanelets = [lanelet_network.find_lanelet_by_id(lanelet_id) for lanelet_id in lanelet_ids]

    try:
        lanelet_orientations = [
            lanelet.orientation_by_position(position_point) for lanelet in lanelets
        ]
    except AssertionError:
        # It is possible that `Lanelet.orientation_by_position` fails with an `AssertionError`
        # when the position point is located unfavourably inside the lanelet.
        # Although not optimal, in this case it is possible to simply select the first lanelet as the
        # most likely lanelet.
        # TODO: In the future, it might make sense to fallback to another selection approach in this case.
        return lanelet_ids[0]

    relative_orientations = [
        abs(subtract_orientations(lanelet_orientation, orientation))
        for lanelet_orientation in lanelet_orientations
    ]

    sorted_indices = np.argsort(np.array(relative_orientations))
    lanelet_id = np.array(lanelet_ids).astype(int)[sorted_indices][0]
    # Must cast to int, because otherwise `lanelet_id` would be of some numpy int type
    return int(lanelet_id)


class _UniqueIncrementalIdAllocatorHelper:
    """
    Helper class to ease the allocation of unique Ids. It assigns unique incremental Ids based
    on a parent key, and makes sure to map equal keys to the same id.

    E.g. for the map DEU_Test-1 we want to be able to create new configuration ids.
    Different configuration ids should be mapped to new incremental ids like
    DEU_Test-1_37 -> DEU_Test-1_1 and DEU_Test-1_85 -> DEU_Test-1_2.
    But if the original configuration ids are equal those should also be mapped to the same
    incremental id, because their id is further defined by their prediction id.
    E.g. DEU_Test-1_37_T-4 -> DEU_Test-1_1_T-1 and DEU_Test-1_37_T-10 -> DEU_Test-1_1_T-2
    """

    def __init__(self):
        self._counter = defaultdict(lambda: 1)
        self._mapping = {}

    def get_or_increment(self, key: Tuple) -> int:
        """
        Allocate a unique ID for a given key combination.
        Only generate a new ID if the exact key hasn't been seen before.
        """
        if len(key) < 2:
            raise ValueError(
                "Key for `_UniqueIncrementalIdAllocatorHelper` must have at least 2 items."
            )

        if key in self._mapping:
            return self._mapping[key]

        # The parent key alows us to keep incrementing in the "parent" domain.
        parent_key = key[:-1]
        self._mapping[key] = self._counter[parent_key]
        self._counter[parent_key] += 1
        return self._mapping[key]


class UniqueIncrementalIdAllocator:
    """
    A utility class for generating unique and incrementing scenario IDs across different dimensions.

    This allocator provides a systematic way to create new scenario IDs while maintaining
    uniqueness and incremental properties for map IDs, configuration IDs, and prediction IDs.

    The allocator ensures that:
    - Map IDs are unique and incremental per country, map name, and original map ID
    - Configuration IDs are unique and incremental per country, map name, map ID, and original configuration ID
    - Prediction IDs are incremental per unique combination of country, map name, map ID, and configuration ID
    """

    def __init__(self):
        self._map_id_allocator = _UniqueIncrementalIdAllocatorHelper()
        self._configuration_id_allocator = _UniqueIncrementalIdAllocatorHelper()
        self._prediction_id_counter = defaultdict(lambda: 1)

    def create_new_unique_id(self, scenario_id: ScenarioID) -> ScenarioID:
        """
        Create a new `ScenarioID`, which is unique and incrementing in the context of this allocator.

        :param scenario_id: The original scenario ID to base the new ID on.

        :returns: A new scenario ID which is unique with one part of the id
            (e.g. map, configuration, prediction) being larger than the corresponding part of
            any other `ScenarioID` that was previously passed to this method.
        """

        # TODO: handle duplicate input ids
        new_s_id = ScenarioID()
        new_s_id.country_id = scenario_id.country_id
        new_s_id.obstacle_behavior = scenario_id.obstacle_behavior

        # ScenarioID exposes wrong typing information for map_name.
        # Actually, a ScenarioID must always have a map_name set.
        assert scenario_id.map_name
        new_s_id.map_name = scenario_id.map_name

        map_allocator_key = (scenario_id.country_id, scenario_id.map_name, scenario_id.map_id)
        new_s_id.map_id = self._map_id_allocator.get_or_increment(map_allocator_key)

        if scenario_id.configuration_id is None:
            return new_s_id
        conf_allocator_key = map_allocator_key + (scenario_id.configuration_id,)
        new_s_id.configuration_id = self._configuration_id_allocator.get_or_increment(
            conf_allocator_key
        )

        if scenario_id.prediction_id is None:
            return new_s_id
        # For predictions we do not need the allocators as for map id and configuration id
        # because
        new_s_id.prediction_id = self._prediction_id_counter[conf_allocator_key]
        self._prediction_id_counter[conf_allocator_key] += 1

        return new_s_id
