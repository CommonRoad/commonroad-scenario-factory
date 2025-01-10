__all__ = [
    "EgoVehicleManeuverFilter",
    "LongEnoughManeuverFilter",
    "MinimumVelocityFilter",
    "InterestingLaneletNetworkFilter",
    "EnoughSurroundingVehiclesFilter",
]

import logging
import random
from abc import ABC, abstractmethod

from commonroad.common.util import Interval
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.scenario import Scenario

from scenario_factory.ego_vehicle_selection.maneuver import EgoVehicleManeuver
from scenario_factory.scenario_features.models.scenario_model import ScenarioModel
from scenario_factory.utils import is_state_list_with_velocity

_LOGGER = logging.getLogger(__name__)


def _does_ego_vehicle_maneuver_reach_minimum_velocity(
    maneuver: EgoVehicleManeuver, scenario_time_steps: int, min_ego_velocity: float
) -> bool:
    if not isinstance(maneuver.ego_vehicle.prediction, TrajectoryPrediction):
        return False

    if not isinstance(maneuver.ego_vehicle.initial_state.time_step, int):
        return False

    # Verify that the vehicle exceeds the minimum velocity at least once during the complete time interval
    adjusted_state_list_start_index = (
        maneuver.start_time - maneuver.ego_vehicle.initial_state.time_step
    )
    state_list = maneuver.ego_vehicle.prediction.trajectory.state_list[
        adjusted_state_list_start_index : adjusted_state_list_start_index + scenario_time_steps
    ]
    if len(state_list) == 0:
        return False

    if not is_state_list_with_velocity(state_list):
        raise RuntimeError(
            "Cannot check whether the ego vehicle reaches the minimum velocity, because the states in it's trajectory do not have a velocity attribute set!"
        )

    if not any(state.velocity >= min_ego_velocity for state in state_list):
        v_max = max([state.velocity for state in state_list])
        _LOGGER.debug(
            f"Maneuver {maneuver} is not interesting as ego vehicle: maximum velocity {v_max} m/s does not exceed required {min_ego_velocity} m/s!"
        )
        return False

    return True


def _does_ego_vehicle_maneuver_last_long_enough(
    maneuver: EgoVehicleManeuver, scenario_time_steps: int
) -> bool:
    """

    :param: scenario_time_steps: The number of time steps that the resulting scenario should have
    """
    if not isinstance(maneuver.ego_vehicle.prediction, TrajectoryPrediction):
        return False

    if not isinstance(maneuver.ego_vehicle.initial_state.time_step, int):
        return False

    if (
        maneuver.ego_vehicle.prediction.final_time_step
        - maneuver.ego_vehicle.initial_state.time_step
        < scenario_time_steps
    ):
        _LOGGER.debug(
            f"Maneuver {maneuver} is not interesting as ego vehicle: Time horizon too short"
        )
        return False

    trajectory_length = maneuver.ego_vehicle.prediction.final_time_step - maneuver.start_time
    if trajectory_length < scenario_time_steps:
        # TODO: trajectory_length is sometimes negative. How is this possible?
        _LOGGER.debug(
            f"Maneuver {maneuver} is not interesting as ego vehicle: Trajectory too short: must be at least {scenario_time_steps} but is only {trajectory_length}"
        )
        return False

    return True


def _does_ego_vehicle_maneuver_happen_on_interesting_lanelet_network(
    maneuver: EgoVehicleManeuver,
    lanelet_network: LaneletNetwork,
    scenario_time_steps: int,
) -> bool:
    """
    Check whether an ego vehicle maneuver happens on an interesting lanelet network.
    """
    if not isinstance(maneuver.ego_vehicle.prediction, TrajectoryPrediction):
        return False

    initial_ego_vehicle_state = maneuver.ego_vehicle.state_at_time(maneuver.start_time)
    if initial_ego_vehicle_state is None:
        raise RuntimeError(
            f"EgoVehicle {maneuver.ego_vehicle} does not have a state at maneuver start {maneuver.start_time}: This is a bug!"
        )

    init_lanelet_ids = lanelet_network.find_lanelet_by_position(
        [initial_ego_vehicle_state.position]
    )[
        0
    ]  # The API is a bit...interesting: It takes a list of input positions and also outputs a list. But as we only want to check one state, we can simply use the 0 index to get the resulting ID assignment

    maneuver_end_time = maneuver.start_time + scenario_time_steps - 1
    final_ego_vehicle_state = maneuver.ego_vehicle.state_at_time(maneuver_end_time)
    if final_ego_vehicle_state is None:
        raise RuntimeError(
            f"EgoVehicle {maneuver.ego_vehicle} does not have a state at maneuver end {maneuver_end_time}: This is a bug!"
        )

    final_lanelet_ids = lanelet_network.find_lanelet_by_position(
        [final_ego_vehicle_state.position]
    )[0]  # see comment above

    if len(final_lanelet_ids) == 0 or len(init_lanelet_ids) == 0:
        _LOGGER.debug(
            f"Maneuver {maneuver} not interesting as ego vehicle: Maneuver does not happen on the map"
        )
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

    return False


def _does_ego_vehicle_maneuver_have_enough_surrounding_vehicles_on_adjacent_lanes_at_start_of_scenario(
    maneuver: EgoVehicleManeuver,
    scenario_model: ScenarioModel,
    detection_range: int,
    min_vehicles_in_range: int,
) -> bool:
    # TODO: This was taken as is from the original code, so some refactoring would still be necessary.
    rear_vehicles, front_vehicles = scenario_model.get_array_closest_obstacles(
        maneuver.ego_vehicle,
        longitudinal_range=Interval(-15, detection_range),  # TODO: magic value of -15?
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
        _LOGGER.debug(
            f"Maneuver {maneuver} not interesting as ego vehicle: Not enough other vehicles found around possible ego vehicle (found {num_veh}; minimum {min_vehicles_in_range})"
        )
        return False
    return True


class EgoVehicleManeuverFilter(ABC):
    """
    Abstract base class for ego vehicle maneuver filters, that determine whether an ego vehicle maneuver can be used to generate new scenarios.
    """

    @abstractmethod
    def matches(
        self, scenario: Scenario, scenario_time_steps: int, ego_vehicle_maneuver: EgoVehicleManeuver
    ) -> bool:
        """
        :param scenario: The base scenario from which this ego vehicle maneuver was extracted
        :param scenario_time_steps: The length of the resulting scenario. This can be used to only consider the wanted time frame in the filter
        :param ego_vehicle_maneuver: The maneuver to test
        """
        ...


class LongEnoughManeuverFilter(EgoVehicleManeuverFilter):
    """
    Only select `EgoVehicleManeuver`s if the ego vehicle has a trajectory for the whole resulting scenario.
    """

    def matches(
        self, scenario: Scenario, scenario_time_steps: int, ego_vehicle_maneuver: EgoVehicleManeuver
    ) -> bool:
        return _does_ego_vehicle_maneuver_last_long_enough(
            ego_vehicle_maneuver, scenario_time_steps
        )


class MinimumVelocityFilter(EgoVehicleManeuverFilter):
    """
    Only select `EgoVehicleManeuver`s if the ego vehicle exceeds the :param:`min_ego_velocity` at least once.
    """

    def __init__(self, min_ego_velocity: float = 22 / 3.6) -> None:
        self._min_ego_velocity = min_ego_velocity

    def matches(
        self, scenario: Scenario, scenario_time_steps: int, ego_vehicle_maneuver: EgoVehicleManeuver
    ) -> bool:
        return _does_ego_vehicle_maneuver_reach_minimum_velocity(
            ego_vehicle_maneuver, scenario_time_steps, self._min_ego_velocity
        )


class InterestingLaneletNetworkFilter(EgoVehicleManeuverFilter):
    """
    Only select `EgoVehicleManauever`s that happen on 'interesting' lanelets

    :param random_inclusion_probability:
        If the lanelet network is not interesting, the scenario might still be included in the result.
        This is controlled by the `random_inclusion_probability`, which determines the probability
        of whether an uninteresting lanelet network will be included.
    """

    def __init__(self, random_inclusion_probability: float = 0.4) -> None:
        self._random_inclusion_probability = random_inclusion_probability

    def matches(
        self, scenario: Scenario, scenario_time_steps: int, ego_vehicle_maneuver: EgoVehicleManeuver
    ) -> bool:
        is_interesting = _does_ego_vehicle_maneuver_happen_on_interesting_lanelet_network(
            ego_vehicle_maneuver,
            scenario.lanelet_network,
            scenario_time_steps,
        )
        if is_interesting:
            return True

        if random.uniform(0, 1) < self._random_inclusion_probability:
            _LOGGER.debug(
                f"Randomly included maneuver {ego_vehicle_maneuver}, although it does not have any interesting lanelet features"
            )
            return True

        return False


class EnoughSurroundingVehiclesFilter(EgoVehicleManeuverFilter):
    """
    Only select `EgoVehicleManeuver`s if the ego vehicle has at least :param:`min_vehicles_in_range` vehicles in a range of :param:`detection_range` at least once during the maneuver.
    """

    def __init__(self, detection_range: int = 30, min_vehicles_in_range: int = 1) -> None:
        self._detection_range = detection_range
        self._min_vehicles_in_range = min_vehicles_in_range

    def matches(
        self, scenario: Scenario, scenario_time_steps: int, ego_vehicle_maneuver: EgoVehicleManeuver
    ) -> bool:
        scenario_model = ScenarioModel(scenario, assign_vehicles_on_the_fly=True)
        return _does_ego_vehicle_maneuver_have_enough_surrounding_vehicles_on_adjacent_lanes_at_start_of_scenario(
            ego_vehicle_maneuver,
            scenario_model,
            detection_range=self._detection_range,
            min_vehicles_in_range=self._min_vehicles_in_range,
        )
