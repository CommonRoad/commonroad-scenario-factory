import logging
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
from commonroad.common.util import Interval
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.scenario import Scenario

from scenario_factory.scenario_config import ScenarioConfig
from scenario_factory.scenario_features.features import changes_lane, get_obstacle_state_list
from scenario_factory.scenario_features.models.scenario_model import ScenarioModel
from scenario_factory.scenario_util import apply_smoothing_filter, find_first_greater

logger = logging.getLogger(__name__)


@dataclass
class EgoVehicleManeuver:
    ego_vehicle: DynamicObstacle
    start_time: int


def threshold_and_lag_detection(signal: np.ndarray, threshold: float, lag_threshold: float) -> Tuple[bool, int]:
    """
    Find whether threshold is exceeded and time step by comparing with lagged signal.

    :param obstacle: the chosen obstacle

    :return: velocity difference of the obstalce's trajectory
    """
    if len(signal) == 0:
        return False, -1

    max_difference = np.abs(np.max(signal) - np.min(signal))
    if max_difference <= threshold:
        return False, -1

    # detect when vehicle is turning by comparred lagging signal to original one
    # -> more time in advance for fast turns
    success, signal_lagged = apply_smoothing_filter(signal)
    if not success:
        # Could not apply smoothing filter, because there are not enough signals.
        # But the threshold is execeed, so this counts as a match
        return True, 0

    delta_lag = signal - signal_lagged
    init_time = find_first_greater(np.abs(delta_lag), lag_threshold)
    if init_time is None:
        return False, -1

    return True, init_time


def threshold_and_max_detection(signal: np.ndarray, threshold: float, n_hold: int = 2) -> Tuple[bool, int]:
    """
    Chceks whether signal exceeds threshold for at least n_hold consecutive time steps and
    returns first time_step-time_gap.
    :param signal:
    :param threshold:
    :param time_gap:
    :return:
    """
    if len(signal) == 0:
        return False, -1

    exceeds = None
    # differentiate between min and max thresholds
    if threshold >= 0:
        if np.max(signal) > threshold:
            exceeds = np.greater(signal, threshold)
    else:
        if np.min(signal) < threshold:
            exceeds = np.less(signal, threshold)

    if exceeds is None:
        return False, -1

    # check if and where threshold is exceed for at least n_hold time steps
    diff = exceeds.astype("int16")
    diff = np.diff(diff)
    i_0 = np.where(diff > 0)[0]
    i_end = np.where(diff < 0)[0]

    if i_0.size > 0:
        if i_end.size == 0 or i_0[-1] > i_end[-1]:
            i_end = np.append(i_end, [exceeds.size - 1])

    if i_0.size == 0 or i_0[0] > i_end[0]:
        i_0 = np.append([0], i_0)

    durations = i_end - i_0

    if durations.size > 0 and np.max(durations) >= n_hold:
        init_time = i_0[np.argmax(durations)]
        if init_time > 0:  # maneuver at time 0 is usually implausible
            return True, init_time

    return False, -1


class EgoVehicleSelectionCriterion(ABC):
    """
    Base class for an ego vehicle selection criterion
    """

    def __init__(self, start_time_offset: float):
        self._start_time_offset = start_time_offset

    def compute_adjusted_start_time(self, orig_start_time: int, dt: float):
        return int(max(0, orig_start_time - int(self._start_time_offset / dt)))

    @abstractmethod
    def matches(self, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        ...

    @classmethod
    @abstractmethod
    def configure(cls, scenario: Scenario, scenario_config: ScenarioConfig) -> "EgoVehicleSelectionCriterion":
        ...


class AccelerationCriterion(EgoVehicleSelectionCriterion):
    def __init__(
        self,
        acceleration_detection_threshold: float = 2.0,
        acceleration_detection_threshold_hold: int = 3,
        acceleration_detection_threshold_start_time_offset: float = 0.5,
    ):
        super().__init__(acceleration_detection_threshold_start_time_offset)
        self._acceleration_detection_threshold = acceleration_detection_threshold
        self._acceleration_detection_threshold_hold = acceleration_detection_threshold_hold

    def matches(self, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        if not all(hasattr(state, "acceleration") for state in obstacle.prediction.trajectory.state_list):
            return False, -1

        accelerations = np.array([state.acceleration for state in obstacle.prediction.trajectory.state_list])
        found_match, time_step = threshold_and_max_detection(
            accelerations,
            threshold=self._acceleration_detection_threshold,
        )

        return found_match, time_step

    @classmethod
    def configure(cls, scenario: Scenario, scenario_config: ScenarioConfig) -> "AccelerationCriterion":
        return cls(
            scenario_config.acceleration_detection_threshold,
            scenario_config.acceleration_detection_threshold_hold,
            scenario_config.acceleration_detection_threshold_time,
        )


class BrakingCriterion(EgoVehicleSelectionCriterion):
    def __init__(
        self,
        braking_detection_threshold: float = -3.0,
        braking_detection_threshold_hold: int = 4,
        braking_detection_threshold_start_time_offset: float = 0.5,
    ):
        super().__init__(braking_detection_threshold_start_time_offset)
        self._braking_detection_threshold = braking_detection_threshold
        self._braking_detection_threshold_hold = braking_detection_threshold_hold

    def matches(self, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        if not all(hasattr(state, "acceleration") for state in obstacle.prediction.trajectory.state_list):
            return False, -1

        accelerations = np.array([state.acceleration for state in obstacle.prediction.trajectory.state_list])
        return threshold_and_max_detection(
            accelerations, threshold=self._braking_detection_threshold, n_hold=self._braking_detection_threshold_hold
        )

    @classmethod
    def configure(cls, scenario: Scenario, scenario_config: ScenarioConfig) -> "BrakingCriterion":
        return cls(
            scenario_config.braking_detection_threshold,
            scenario_config.braking_detection_threshold_hold,
            scenario_config.braking_detection_threshold_time,
        )


class TurningCrierion(EgoVehicleSelectionCriterion):
    def __init__(self, turning_detection_threshold: float, turning_detection_threshold_start_time_offset: float):
        super().__init__(turning_detection_threshold_start_time_offset)
        self._turning_detection_threshold = turning_detection_threshold

    def matches(self, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1
        orientations_ = np.array([state.orientation for state in obstacle.prediction.trajectory.state_list])
        orientations = np.unwrap(orientations_)
        turns, time_step = threshold_and_lag_detection(
            orientations,
            threshold=self._turning_detection_threshold,
            lag_threshold=self._turning_detection_threshold_time,
        )
        if time_step is not None:
            time_step += obstacle.prediction.trajectory.initial_time_step

        return turns, time_step


class LaneChangeCriterion(EgoVehicleSelectionCriterion):
    def __init__(self, lc_detection_min_velocity: float, lc_detection_threshold_start_time_offset: float):
        super().__init__(lc_detection_threshold_start_time_offset)
        self._lc_detection_min_velocity = lc_detection_min_velocity

    def matches(self, obstacle: DynamicObstacle) -> Tuple[bool, int]:
        if not isinstance(obstacle.prediction, TrajectoryPrediction):
            return False, -1

        lane_change, direction, time_step = changes_lane(self.lanelet_network, obstacle)
        if not lane_change:
            return False, -1

        velocity = obstacle.prediction.trajectory.state_at_time_step(time_step).velocity
        if velocity >= self._lc_detection_min_velocity:
            return False, -1

        return True, time_step


class MergingCriterion(EgoVehicleSelectionCriterion):
    def __init__(self, merge_detection_threshold_start_time_offset: float, merge_detection_min_velocity):
        super().__init__(merge_detection_threshold_start_time_offset)
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

    def matches(self, obstacle: DynamicObstacle) -> Tuple[bool, int]:
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

        return lane_merge, time_step


def _find_ego_vehicle_maneuvers_in_scenario(
    scenario: Scenario, criterions: Sequence[EgoVehicleSelectionCriterion]
) -> List[EgoVehicleManeuver]:
    possible_ego_vehicles = filter(
        lambda obstacle: obstacle.obstacle_type == ObstacleType.CAR, scenario.dynamic_obstacles
    )
    selected_maneuvers = []
    for obstacle in possible_ego_vehicles:
        for criterion in criterions:
            matches, init_time = criterion.matches(obstacle)
            if not matches:
                continue

            assert isinstance(obstacle.initial_state.time_step, int)
            # The init_time is relative to the initial state of the obstacle
            absolute_init_time = init_time + obstacle.initial_state.time_step
            # Each criterion has a specific start time offset which must be used to shift the adsolute init time, so that scenarios start before a specific maneuver
            adjusted_absolute_init_time = criterion.compute_adjusted_start_time(absolute_init_time, scenario.dt)

            selected_maneuvers.append(EgoVehicleManeuver(obstacle, adjusted_absolute_init_time))

    return selected_maneuvers


def _does_ego_vehicle_maneuver_last_long_enough(maneuver: EgoVehicleManeuver, scenario_time_steps: int) -> bool:
    """

    :param: scenario_time_steps: The number of time steps that the resulting scenario should have
    """
    if not isinstance(maneuver.ego_vehicle.prediction, TrajectoryPrediction):
        return False

    if not isinstance(maneuver.ego_vehicle.initial_state.time_step, int):
        return False

    if (
        maneuver.ego_vehicle.prediction.final_time_step - maneuver.ego_vehicle.initial_state.time_step
        < scenario_time_steps
    ):
        logger.debug(f"Maneuver {maneuver} is not interesting as ego vehicle: Time horizon too short")
        return False

    if maneuver.ego_vehicle.prediction.final_time_step - maneuver.start_time < scenario_time_steps:
        logger.debug(f"Maneuver {maneuver} is not interesting as ego vehicle: Trajectory too short")
        return False

    return True


def _does_ego_vehicle_maneuver_reach_minimum_velocity(
    maneuver: EgoVehicleManeuver, scenario_time_steps: int, min_ego_velocity: float
) -> bool:
    if not isinstance(maneuver.ego_vehicle.prediction, TrajectoryPrediction):
        return False

    if not isinstance(maneuver.ego_vehicle.initial_state.time_step, int):
        return False

    # Ensure that each state has the 'velocity' attribute
    if not all(hasattr(state, "velocity") for state in maneuver.ego_vehicle.prediction.trajectory.state_list):
        return False

    # Verify that the vehicle exceeds the minimum velocity at least once during the complete time interval
    adjusted_state_list_start_index = maneuver.start_time - maneuver.ego_vehicle.initial_state.time_step
    state_list = maneuver.ego_vehicle.prediction.trajectory.state_list[
        adjusted_state_list_start_index : adjusted_state_list_start_index + scenario_time_steps
    ]
    if len(state_list) == 0:
        return False

    if not any(state.velocity >= min_ego_velocity for state in state_list):
        v_max = max([state.velocity for state in state_list])
        logger.debug(
            f"Maneuver {maneuver} is not interesting as ego vehicle: maximum velocity {v_max} m/s does not exceed required {min_ego_velocity} m/s!"
        )
        return False

    return True


def _does_ego_vehicle_maneuver_happen_on_interesting_lanelet_network(
    maneuver: EgoVehicleManeuver, lanelet_network: LaneletNetwork, scenario_time_steps: int
) -> bool:
    """
    Check whether an ego vehicle maneuver happens on an interesting lanelet network.
    """
    if not isinstance(maneuver.ego_vehicle.prediction, TrajectoryPrediction):
        return False

    if maneuver.ego_vehicle.prediction.center_lanelet_assignment is None:
        return False

    if maneuver.start_time == maneuver.ego_vehicle.initial_state.time_step:
        init_lanelet_ids = list(maneuver.ego_vehicle.initial_center_lanelet_ids)
    else:
        init_lanelet_ids = list(maneuver.ego_vehicle.prediction.center_lanelet_assignment[maneuver.start_time])

    final_lanelet_ids = list(
        maneuver.ego_vehicle.prediction.center_lanelet_assignment[maneuver.start_time + scenario_time_steps - 1]
    )

    if len(final_lanelet_ids) == 0 or len(init_lanelet_ids) == 0:
        logger.debug(f"Maneuver {maneuver} not interesting as ego vehicle: Maneuver does not happen on the map")
        return False

    if len(final_lanelet_ids) > 1 or len(init_lanelet_ids) > 1:
        # Vehicle starts or ends on multiple lanelets, this is interesting!
        return True

    init_lanelet_id, final_lanelet_id = init_lanelet_ids[0], final_lanelet_ids[0]
    if init_lanelet_id != final_lanelet_id:
        # The lane is changed, this is interesting!
        return False

    init_lanelet, final_lanelet = (
        lanelet_network.find_lanelet_by_id(init_lanelet_id),
        lanelet_network.find_lanelet_by_id(final_lanelet_id),
    )

    if init_lanelet in lanelet_network.map_inc_lanelets_to_intersections:
        # The lane is an incoming lane in an intersection, this is interesting!
        return True

    if (
        init_lanelet.adj_left_same_direction
        or init_lanelet.adj_right_same_direction
        or final_lanelet.adj_left_same_direction
        or final_lanelet.adj_right_same_direction
    ):
        # The start or end lane has adjacent lanes, this is interesting!
        return True

    # Diregard with a high probability
    if random.uniform(0, 1) > 0.4:
        logger.debug(
            f"Randomly rejected maneuver {maneuver}, because it does not have any interesting lanelet features"
        )
        return False
    return True


def _does_ego_vehicle_maneuver_have_enough_surrounding_vehicles(
    maneuver: EgoVehicleManeuver, scenario_model: ScenarioModel, detection_range: int, min_vehicles_in_range: int
) -> bool:
    # TODO: This was taken as is from the original code, so some refactoring would still be necessary.
    rear_vehicles, front_vehicles = scenario_model.get_array_closest_obstacles(
        maneuver.ego_vehicle,
        longitudinal_range=Interval(-15, detection_range),
        relative_lateral_indices=True,
        time_step=maneuver.start_time,
    )
    num_veh = 0
    for lane_indx in range(-1, 1):
        try:
            num_veh += len(rear_vehicles[lane_indx])
        except KeyError:
            pass
        try:
            num_veh += len(front_vehicles[lane_indx])
        except KeyError:
            pass

    if num_veh < min_vehicles_in_range:
        logger.debug(
            f"Maneuver {maneuver} not interesting as ego vehicle: Not enough other vehicles found around possible ego vehicle (found {num_veh}; minimum {min_vehicles_in_range})"
        )
        return False
    return True


def _get_number_of_vehicles_in_range(
    position: np.ndarray, time_step: int, obstacles: Sequence[DynamicObstacle], detection_range: int
) -> int:
    counter = 0
    for obstacle in obstacles:
        obstacle_state = obstacle.state_at_time(time_step)
        if obstacle_state is None:
            continue

        if np.linalg.norm(obstacle_state.position - position, ord=np.inf) >= detection_range:
            continue

        counter += 1

    return counter


def _select_most_interesting_maneuver(
    scenario: Scenario, maneuvers: Sequence[EgoVehicleManeuver], detection_range: int
) -> EgoVehicleManeuver:
    # TODO: This is a bit clunky as scenario and detection_range are also needed here. Maybe a better metric/approach can be found?

    if len(maneuvers) == 0:
        raise ValueError("Cannot select the most interesting maneuver from an empty list of maneuvers!")

    if len(maneuvers) == 1:
        return maneuvers[0]

    max_num_vehicles = 0
    current_best_maneuver = maneuvers[0]
    for maneuver in maneuvers:
        ego_vehicle_state = maneuver.ego_vehicle.state_at_time(maneuver.start_time)
        if ego_vehicle_state is None:
            continue

        num_vehicles = _get_number_of_vehicles_in_range(
            ego_vehicle_state.position, maneuver.start_time, scenario.dynamic_obstacles, detection_range
        )
        if num_vehicles < max_num_vehicles:
            continue

        max_num_vehicles = num_vehicles
        current_best_maneuver = maneuver

    return current_best_maneuver


def _select_one_maneuver_per_ego_vehicle(
    scenario: Scenario, maneuvers: Sequence[EgoVehicleManeuver], detection_range: int
) -> List[EgoVehicleManeuver]:
    maneuvers_per_ego_vehicle = defaultdict(list)
    for maneuver in maneuvers:
        maneuvers_per_ego_vehicle[maneuver.ego_vehicle.obstacle_id].append(maneuver)

    return [
        _select_most_interesting_maneuver(scenario, ego_vehicle_maneuver_list, detection_range)
        for ego_vehicle_maneuver_list in maneuvers_per_ego_vehicle.values()
    ]


def select_interesting_ego_vehicle_maneuvers_from_scenario(
    scenario: Scenario,
    scenario_config: ScenarioConfig,
    scenario_model: ScenarioModel,
    criterions: Optional[Sequence[EgoVehicleSelectionCriterion]] = None,
) -> List[EgoVehicleManeuver]:
    if criterions is None:
        criterions = [
            BrakingCriterion.configure(scenario, scenario_config),
            AccelerationCriterion.configure(scenario, scenario_config),
        ]

    ego_vehicle_maneuvers = _find_ego_vehicle_maneuvers_in_scenario(scenario, criterions)

    long_enough_maneuvers = filter(
        lambda maneuver: _does_ego_vehicle_maneuver_last_long_enough(
            maneuver,
            scenario_config.cr_scenario_time_steps,
        ),
        ego_vehicle_maneuvers,
    )

    fast_enough_maneuvers = filter(
        lambda maneuver: _does_ego_vehicle_maneuver_reach_minimum_velocity(
            maneuver, scenario_config.cr_scenario_time_steps, scenario_config.min_ego_velocity
        ),
        long_enough_maneuvers,
    )

    interesting_lanelet_maneuvers = filter(
        lambda maneuver: _does_ego_vehicle_maneuver_happen_on_interesting_lanelet_network(
            maneuver, scenario.lanelet_network, scenario_config.cr_scenario_time_steps
        ),
        fast_enough_maneuvers,
    )

    enough_surrounding_vehicles_maneuvers = filter(
        lambda maneuver: _does_ego_vehicle_maneuver_have_enough_surrounding_vehicles(
            maneuver, scenario_model, scenario_config.range_min_vehicles, scenario_config.min_vehicles_in_range
        ),
        interesting_lanelet_maneuvers,
    )

    most_interesting_maneuvers = _select_one_maneuver_per_ego_vehicle(
        scenario, list(enough_surrounding_vehicles_maneuvers), scenario_config.range_min_vehicles
    )

    return most_interesting_maneuvers
