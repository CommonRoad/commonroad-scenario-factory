__all__ = [
    "EgoVehicleSelectionCriterion",
    "BrakingCriterion",
    "AccelerationCriterion",
    "TurningCriterion",
    "LaneChangeCriterion",
]

import logging
from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario

from scenario_factory.ego_vehicle_selection.utils import threshold_and_lag_detection, threshold_and_max_detection
from scenario_factory.scenario_features.features import changes_lane, get_obstacle_state_list

logger = logging.getLogger(__name__)


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

        # It is possible that not all states contain an acceleration attribute, so it must be checked
        if not all(hasattr(state, "acceleration") for state in obstacle.prediction.trajectory.state_list):
            return False, -1

        accelerations = np.array([state.acceleration for state in obstacle.prediction.trajectory.state_list])
        found_match, time_step = threshold_and_max_detection(
            accelerations,
            threshold=self._acceleration_detection_threshold,
        )

        if found_match:
            assert isinstance(obstacle.initial_state.time_step, int)
            # The time_step is relative as it basically represents an index into the accelerations array. Therefore it must be made absolute based on the initial time step.
            time_step += obstacle.initial_state.time_step
            logger.debug(f"AccelerationCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}")

        return found_match, time_step


class BrakingCriterion(EgoVehicleSelectionCriterion):
    # TODO: In theory a braking criterion is the same as an acceleration criterion so, the both could be merged
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

        # It is possible that not all states contain an acceleration attribute, so it must be checked
        if not all(hasattr(state, "acceleration") for state in obstacle.prediction.trajectory.state_list):
            return False, -1

        accelerations = np.array([state.acceleration for state in obstacle.prediction.trajectory.state_list])
        found_match, time_step = threshold_and_max_detection(
            accelerations, threshold=self._braking_detection_threshold, n_hold=self._braking_detection_threshold_hold
        )

        if found_match:
            assert isinstance(obstacle.initial_state.time_step, int)
            # The time_step is relative as it basically represents an index into the accelerations array. Therefore it must be made absolute based on the initial time step.
            time_step += obstacle.initial_state.time_step
            logger.debug(f"BrakingCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}")

        return found_match, time_step


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

        # It is possible that not all states contain an orientation attribute, so it must be checked
        plain_orientations = np.array([state.orientation for state in obstacle.prediction.trajectory.state_list])
        unwrapped_orientations = np.unwrap(plain_orientations)
        turns, time_step = threshold_and_lag_detection(
            unwrapped_orientations,
            threshold=self._turning_detection_threshold,
            lag_threshold=self._turning_detection_threshold_lag,
        )

        if turns:
            assert isinstance(obstacle.initial_state.time_step, int)
            # The time_step is relative as it basically represents an index into the plain_orientations array. Therefore it must be made absolute based on the initial time step.
            time_step += obstacle.initial_state.time_step
            logger.debug(f"TurningCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}")

        return turns, time_step


class LaneChangeCriterion(EgoVehicleSelectionCriterion):
    def __init__(self, lc_detection_min_velocity: float = 10.0, lc_detection_start_time_offset: float = 0.5):
        super().__init__(lc_detection_start_time_offset)
        self._lc_detection_min_velocity = lc_detection_min_velocity

    def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        lane_change, direction, time_step = changes_lane(scenario.lanelet_network, obstacle)
        if not lane_change:
            return False, -1

        velocity = obstacle.prediction.trajectory.state_at_time_step(time_step).velocity
        if velocity >= self._lc_detection_min_velocity:
            return False, -1

        logger.debug(f"LaneChangeCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}")

        return True, time_step


class MergingCriterion(EgoVehicleSelectionCriterion):
    def __init__(self, merge_detection_min_velocity: float = 10.0, merge_detection_start_time_offset: float = 0.5):
        super().__init__(merge_detection_start_time_offset)
        self._merge_detection_min_velocity = merge_detection_min_velocity

    @staticmethod
    def _passes_merging_lane(obstacle: DynamicObstacle):
        obstacle_states = get_obstacle_state_list(obstacle)
        lanelets = list(obstacle.prediction.center_lanelet_assignment.values())
        for x0, x0_lanelets, x1_lanelets in zip(obstacle_states[3:-1], lanelets[3:-1], lanelets[4:]):
            if x0_lanelets is None or x1_lanelets is None:
                continue
            if len(x0_lanelets) != len(x1_lanelets):
                lane_change_ts = x0.time_step + 1
                return True, lane_change_ts
        return False, -1

    def matches(self, scenario: Scenario, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        lane_merge, time_step = self._passes_merging_lane(obstacle)
        if not lane_merge:
            return False, -1

        # Check if 'velocity' is defined on the state. CommonRoads TraceState has dynamic attributes, therefore it is not guaranteed to be there...
        matching_state = obstacle.prediction.trajectory.state_at_time_step(time_step)
        if not hasattr(matching_state, "velocity"):
            return False, -1

        # Check if the min velocity is exceeded
        velocity = matching_state.velocity
        if velocity < self._merge_detection_min_velocity:
            return False, -1

        logger.debug(f"MergingCriterion matched obstacle {obstacle.obstacle_id} at time step {time_step}")

        return lane_merge, time_step
