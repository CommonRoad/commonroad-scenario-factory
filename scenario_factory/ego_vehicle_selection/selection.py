__all__ = ["find_ego_vehicle_maneuvers_in_scenario", "select_one_maneuver_per_ego_vehicle"]

import logging
from collections import defaultdict
from typing import Iterable, List, Sequence

import numpy as np
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.scenario import Scenario

from scenario_factory.ego_vehicle_selection.criterions import EgoVehicleSelectionCriterion
from scenario_factory.ego_vehicle_selection.maneuver import EgoVehicleManeuver
from scenario_factory.utils import is_state_with_position

_LOGGER = logging.getLogger(__name__)


def find_ego_vehicle_maneuvers_in_scenario(
    scenario: Scenario, criterions: Iterable[EgoVehicleSelectionCriterion]
) -> List[EgoVehicleManeuver]:
    """
    Using the ego vehicle selection criterions from :param:`criterions`, select maneuvers of obstacles in the scenario which match any of the criterions.

    :param scenario: CommonRoad scenario with dynamic obstacles
    :param criterions: The ego vehicle selection criterion which will be matched

    :returns: All maneuvers found in the scenario
    """
    # For the time being, only cars can be ego vehicles
    possible_ego_vehicles = filter(
        lambda obstacle: obstacle.obstacle_type == ObstacleType.CAR, scenario.dynamic_obstacles
    )
    selected_maneuvers = []
    for obstacle in possible_ego_vehicles:
        for criterion in criterions:
            matches, absolute_init_time = criterion.matches(scenario, obstacle)
            if not matches:
                continue
            # Each criterion has a specific start time offset which must be used to shift the adsolute init time, so that scenarios start before a specific maneuver
            adjusted_absolute_init_time = criterion.compute_adjusted_start_time(
                absolute_init_time, scenario.dt
            )
            _LOGGER.debug(
                f"Adjusted maneuver start time {absolute_init_time} of obstacle {obstacle.obstacle_id} to {adjusted_absolute_init_time}"
            )

            selected_maneuvers.append(EgoVehicleManeuver(obstacle, adjusted_absolute_init_time))

    return selected_maneuvers


def _get_number_of_vehicles_in_range(
    position: np.ndarray, time_step: int, obstacles: Sequence[DynamicObstacle], detection_range: int
) -> int:
    counter = 0
    for obstacle in obstacles:
        obstacle_state = obstacle.state_at_time(time_step)
        if obstacle_state is None:
            continue

        if not is_state_with_position(obstacle_state):
            raise RuntimeError(
                f"The state {obstacle_state} of obstacle {obstacle.obstacle_id} is invalid: The position attribute is not set!"
            )

        if np.linalg.norm(obstacle_state.position - position, ord=np.inf) >= detection_range:
            continue

        counter += 1

    return counter


def _select_most_interesting_maneuver(
    scenario: Scenario, maneuvers: Sequence[EgoVehicleManeuver], detection_range: int
) -> EgoVehicleManeuver:
    # TODO: This is a bit clunky as scenario and detection_range are also needed here. Maybe a better metric/approach can be found?

    if len(maneuvers) == 0:
        raise ValueError(
            "Cannot select the most interesting maneuver from an empty list of maneuvers!"
        )

    if len(maneuvers) == 1:
        return maneuvers[0]

    max_num_vehicles = 0
    current_best_maneuver = maneuvers[0]
    for maneuver in maneuvers:
        ego_vehicle_state = maneuver.ego_vehicle.state_at_time(maneuver.start_time)
        if ego_vehicle_state is None:
            continue

        if not is_state_with_position(ego_vehicle_state):
            raise RuntimeError(
                f"The state {ego_vehicle_state} of obstacle {maneuver.ego_vehicle.obstacle_id} is invalid: The position attribute is not set!"
            )

        num_vehicles = _get_number_of_vehicles_in_range(
            ego_vehicle_state.position,
            maneuver.start_time,
            scenario.dynamic_obstacles,
            detection_range,
        )
        if num_vehicles < max_num_vehicles:
            continue

        max_num_vehicles = num_vehicles
        current_best_maneuver = maneuver

    return current_best_maneuver


def select_one_maneuver_per_ego_vehicle(
    scenario: Scenario, maneuvers: Sequence[EgoVehicleManeuver], detection_range: int
) -> List[EgoVehicleManeuver]:
    """
    For every vehicle with a qualifying ego vehicle maneuver in one scenario select only the most 'interesting' maneuver. The most interesting maneuver is the one with the most other vehicles around the vehicle in it's :param:`detection_range`.

    :param scenario: The scenario in which the maneuvers were found
    :param maneuvers: All qualifying ego vehicle maneuvers found in the given scenario
    :param detection_range: The range around the possible ego vehicle to look for other vehicles for determening the most interesting maneuver.
    """
    maneuvers_per_ego_vehicle = defaultdict(list)
    for maneuver in maneuvers:
        maneuvers_per_ego_vehicle[maneuver.ego_vehicle.obstacle_id].append(maneuver)

    return [
        _select_most_interesting_maneuver(scenario, ego_vehicle_maneuver_list, detection_range)
        for ego_vehicle_maneuver_list in maneuvers_per_ego_vehicle.values()
    ]
