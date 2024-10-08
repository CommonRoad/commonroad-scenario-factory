__all__ = [
    "EgoVehicleSelectionCriterion",
    "AccelerationCriterion",
    "BrakingCriterion",
    "TurningCriterion",
    "LaneChangeCriterion",
]

import logging
from abc import ABC, abstractmethod
from typing import Any, Iterable, Tuple

import numpy as np
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario

from scenario_factory.ego_vehicle_selection.utils import (
    threshold_and_lag_detection,
    threshold_and_max_detection,
)
from scenario_factory.utils import (
    get_full_state_list_of_obstacle,
    is_state_list_with_acceleration,
    is_state_list_with_orientation,
    is_state_list_with_position,
    is_state_with_discrete_time_step,
    is_state_with_discrete_velocity,
    is_state_with_velocity,
)

_LOGGER = logging.getLogger(__name__)


def _pairwise(iterable: Iterable[Any]) -> Iterable[Any]:
    iterator = iter(iterable)
    a = next(iterator, None)
    for b in iterator:
        yield a, b
        a = b


class EgoVehicleSelectionCriterion(ABC):
    """
    An EgoVehicleSelectionCriterion is used to determine whether a dynamic obstacle performs an 'intersting' maneuver in a scenario. What is considered 'interesting' is determined by each criterion.
    """

    def __init__(self, start_time_offset: float):
        self._start_time_offset = start_time_offset

    def compute_adjusted_start_time(self, orig_start_time: int, dt: float) -> int:
        """
        Each criterion must provide an time step offset, to determine how many time steps should be included in a resulting scenario before the maneuver happened. As this is specific to each criterion it is computed here based on the start_time_offset, which is configured individually for each criterion.
        """
        return int(max(0, orig_start_time - int(self._start_time_offset / dt)))

    @abstractmethod
    def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        """
        Check whether the obstacle in the scenario matches the criterion at one time step. If it matches, the according absolute time step is returned. Otherwise -1 is returned.
        """
        ...


class AccelerationCriterion(EgoVehicleSelectionCriterion):
    """
    Criterion that matches if a dynamic obstacle is accelerating.

    :param acceleration_detection_threshold: The minimum acceleration that must be exceed to be considered as accelerating
    :param acceleration_detection_threshold_hold: The number of time steps over which the obstacle must exceed the threshold
    :param acceleration_detection_start_time_offset: The start time offset for the resulting scenario
    """

    def __init__(
        self,
        acceleration_detection_threshold: float = 2.0,
        acceleration_detection_threshold_hold: int = 3,
        acceleration_detection_start_time_offset: float = 0.5,
    ):
        super().__init__(acceleration_detection_start_time_offset)
        self._acceleration_detection_threshold = acceleration_detection_threshold
        self._acceleration_detection_threshold_hold = acceleration_detection_threshold_hold

    def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        # prediction could also be SetPrediction, so it must be type checked...
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        state_list = get_full_state_list_of_obstacle(obstacle)

        # It is possible that not all states contain an acceleration attribute, so it must be checked
        if not is_state_list_with_acceleration(state_list):
            return False, -1

        accelerations = np.array([state.acceleration for state in state_list])

        found_match, state_index = threshold_and_max_detection(
            accelerations,
            threshold=self._acceleration_detection_threshold,
        )
        if not found_match:
            return False, -1

        # threshold_and_max_detection only returns an index into the input array.
        # To get the real time_step, we must first get the matching state
        matching_state = state_list[state_index]
        if not is_state_with_discrete_time_step(matching_state):
            return False, -1
        time_step = matching_state.time_step

        _LOGGER.debug(
            f"AccelerationCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}"
        )

        return True, time_step


class BrakingCriterion(EgoVehicleSelectionCriterion):
    """
    Criterion that matches if a dynamic obstacle is accelerating.

    :param braking_detection_threshold: The minimum deceleration that must be exceed to be considered as accelerating
    :param braking_detection_threshold_hold: The number of time steps over which the obstacle must exceed the threshold
    :param braking_detection_start_time_offset: The start time offset for the resulting scenario
    """

    def __init__(
        self,
        braking_detection_threshold: float = -3.0,
        braking_detection_threshold_hold: int = 4,
        braking_detection_threshold_start_time_offset: float = 0.5,
    ):
        super().__init__(braking_detection_threshold_start_time_offset)
        self._braking_detection_threshold = braking_detection_threshold
        self._braking_detection_threshold_hold = braking_detection_threshold_hold

    def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        # prediction could also be SetPrediction, so it must be type checked...
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        state_list = get_full_state_list_of_obstacle(obstacle)

        # It is possible that not all states contain an acceleration attribute, so it must be checked
        if not is_state_list_with_acceleration(state_list):
            return False, -1

        accelerations = np.array([state.acceleration for state in state_list])

        found_match, state_index = threshold_and_max_detection(
            accelerations,
            threshold=self._braking_detection_threshold,
            n_hold=self._braking_detection_threshold_hold,
        )
        if not found_match:
            return False, -1

        # threshold_and_max_detection only returns an index into the input array.
        # To get the real time_step, we must first get the matching state
        matching_state = state_list[state_index]
        if not is_state_with_discrete_time_step(matching_state):
            return False, -1
        time_step = matching_state.time_step

        _LOGGER.debug(
            f"BrakingCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}"
        )

        return True, time_step


class TurningCriterion(EgoVehicleSelectionCriterion):
    """
    Criterion that matches if a dynamic obstacle is turning.

    :param turning_detection_threshold: The minimum turning radius in radians that must be exceed to be considered as turning
    :param turning_detection_threshold_lag: The number of time steps over which the obstacle must exceed the threshold
    :param turning_detection_start_time_offset: The start time offset for the resulting scenario
    """

    def __init__(
        self,
        turning_detection_threshold: float = np.deg2rad(60.0),
        turning_detection_threshold_lag: float = np.deg2rad(6.0),
        turning_detection_start_time_offset: float = 0.5,
    ):
        super().__init__(turning_detection_start_time_offset)
        self._turning_detection_threshold = turning_detection_threshold
        self._turning_detection_threshold_lag = turning_detection_threshold_lag

    def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        # prediction could also be SetPrediction, so it must be type checked...
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        state_list = get_full_state_list_of_obstacle(obstacle)

        # It is possible that not all states contain an orientation attribute, so it must be checked
        if not is_state_list_with_orientation(state_list):
            return False, -1

        plain_orientations = np.array([state.orientation for state in state_list])
        unwrapped_orientations = np.unwrap(plain_orientations)

        turns, state_index = threshold_and_lag_detection(
            unwrapped_orientations,
            threshold=self._turning_detection_threshold,
            lag_threshold=self._turning_detection_threshold_lag,
        )
        if not turns:
            return False, -1

        matched_state = state_list[state_index]
        if not is_state_with_discrete_time_step(matched_state):
            return False, -1
        time_step = matched_state.time_step

        _LOGGER.debug(
            f"TurningCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}"
        )

        return True, time_step


def _are_lanelets_adjacent(lanelet0: Lanelet, lanelet1: Lanelet) -> bool:
    if lanelet0.adj_left == lanelet1.lanelet_id and lanelet0.adj_left_same_direction:
        return True

    if lanelet0.adj_right == lanelet1.lanelet_id and lanelet0.adj_right_same_direction:
        return True

    return False


def _changes_lanes(lanelet_network: LaneletNetwork, obstacle: DynamicObstacle) -> Tuple[bool, int]:
    """
    Simple heuristic to determine if the obstacle *might* change lanes.
    """
    state_list = get_full_state_list_of_obstacle(obstacle)

    if not is_state_list_with_position(state_list):
        return False, -1

    position_list = [state.position for state in state_list]
    mapped_lanelets_list = lanelet_network.find_lanelet_by_position(position_list)

    for state_index, (curr_lanelet_list, next_lanelet_list) in enumerate(
        _pairwise(mapped_lanelets_list)
    ):
        if curr_lanelet_list is None or next_lanelet_list is None:
            # If no lanelet could be mapped at this position, None is returned by find_lanelet_by_position...
            continue

        if len(curr_lanelet_list) == 0 or len(next_lanelet_list) == 0:
            continue

        if curr_lanelet_list == next_lanelet_list:
            # Both lanelet assignments are the same -> no lane change
            continue

        # Take the first lanelet from the current list and the last lanelet from the next list.
        # This way, we prefer lane change *starts*, because scenarios should start
        # before the lane change and not if the lane change is finished.
        # This also means, that simple 'bounces' are also detected as lane changes
        curr_lanelet = lanelet_network.find_lanelet_by_id(curr_lanelet_list[0])
        next_lanelet = lanelet_network.find_lanelet_by_id(next_lanelet_list[-1])
        if _are_lanelets_adjacent(curr_lanelet, next_lanelet):
            # state_index points to curr_lanelet_list, but the lane change happens on next_lanelet_list
            matched_state = state_list[state_index + 1]
            if not is_state_with_discrete_time_step(matched_state):
                return False, -1
            return True, matched_state.time_step

    return False, -1


class LaneChangeCriterion(EgoVehicleSelectionCriterion):
    """
    Criterion that matches if a dynamic obstacle is switches to an adjacent lane once.

    :param lc_detection_min_velocity: The minimum velocity that the vehicle must have, so that this is considered as a lane change
    :param lc_detection_start_time_offset: The start time offset for the resulting scenario
    """

    def __init__(
        self, lc_detection_min_velocity: float = 10.0, lc_detection_start_time_offset: float = 0.5
    ):
        super().__init__(lc_detection_start_time_offset)
        self._lc_detection_min_velocity = lc_detection_min_velocity

    def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        changed_lane, time_step = _changes_lanes(scenario.lanelet_network, obstacle)
        if not changed_lane:
            return False, -1

        matched_state = obstacle.state_at_time(time_step)
        if matched_state is None or not is_state_with_velocity(matched_state):
            return False, -1

        if not is_state_with_discrete_velocity(matched_state):
            return False, -1

        if matched_state.velocity <= self._lc_detection_min_velocity:
            return False, -1

        _LOGGER.debug(
            f"LaneChangeCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}"
        )

        return True, time_step
