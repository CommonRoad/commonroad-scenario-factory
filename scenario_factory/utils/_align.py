from typing import Sequence

from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import TrafficLight
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario

from scenario_factory.utils._types import WithTimeStep


def align_state_to_time_step(state: WithTimeStep, time_step: int) -> None:
    """
    Aligns the time step of `state` to a reference `time_step`.

    :param state: The state object to align.
    :param time_step: The reference time step to align `state` to.

    :return: The state object with the adjusted time step.
    """
    state.time_step -= time_step


def align_state_list_to_time_step(states: Sequence[WithTimeStep], time_step: int) -> None:
    """
    Aligns the time steps of all states in a list to a reference time step.

    :param states: A list of states to align.
    :param time_step: The reference time step for alignment.
    """
    for state in states:
        align_state_to_time_step(state, time_step)


def align_dynamic_obstacle_to_time_step(dynamic_obstacle: DynamicObstacle, time_step: int) -> None:
    """
    Aligns the `dynamic_obstacle` to a reference `time_step` by shifting all time steps such that `time_step`
    becomes the new zero point. The relative intervals between time steps remain unchanged.

    This function modifies `dynamic_obstacle` in place, adjusting the time steps of its initial state, initial
    signal state, signal series, and trajectory prediction (if applicable).

    :param dynamic_obstacle: The dynamic obstacle to align. Modified in place.
    :param time_step: The reference time step that will serve as the zero point.
    """
    align_state_to_time_step(dynamic_obstacle.initial_state, time_step)

    if dynamic_obstacle.initial_signal_state is not None:
        align_state_to_time_step(dynamic_obstacle.initial_signal_state, time_step)

    if dynamic_obstacle.signal_series is not None:
        align_state_list_to_time_step(dynamic_obstacle.signal_series, time_step)

    if dynamic_obstacle.prediction is None:
        return

    if isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        align_state_list_to_time_step(dynamic_obstacle.prediction.trajectory.state_list, time_step)
        dynamic_obstacle.prediction.trajectory.initial_time_step = (
            dynamic_obstacle.prediction.trajectory.state_list[0].time_step
        )
    else:
        raise ValueError(
            f"Cannot align dynamic obstacle {dynamic_obstacle.obstacle_id} to time step {time_step}: exepected a prediction of type `TrajectoryPrediction` but got `SetBasedPrediction`"
        )


def align_traffic_light_to_time_step(traffic_light: TrafficLight, time_step: int) -> None:
    """
    Aligns the `traffic_ligh` to a reference `time_step` by shifting all time steps such that `time_step`
    becomes the new zero point. The relative intervals between time steps remain unchanged.

    This function modifies `traffic_light` in place, adjusting the cycle offset.

    :param traffic_light: The traffic light to align. Modified in place.
    :param time_step: The reference time step that will serve as the zero point.
    """
    if traffic_light.traffic_light_cycle is not None:
        traffic_light.traffic_light_cycle.time_offset = (
            traffic_light.traffic_light_cycle.time_offset - time_step
        ) % (traffic_light.traffic_light_cycle.cycle_init_timesteps[-1])


def align_scenario_to_time_step(scenario: Scenario, time_step: int) -> None:
    """
    Align `scenario` to a reference `time_step` such that the time step becomes the new zero point.
    The relative intervals between time steps inside the scenario remain unchanged.

    This function modifies all `dynamic_obstacles` in place, and aligns their time steps accordingly.
    Other objects in the scenario are currently not modified.

    :param scenario: The scenario to align. Modified in place.
    :param time_step: The reference time step that will serve as the zero point.
    """
    # TODO: also align static and environment obstacles
    for dynamic_obstacle in scenario.dynamic_obstacles:
        align_dynamic_obstacle_to_time_step(dynamic_obstacle, time_step)

    for traffic_light in scenario.lanelet_network.traffic_lights:
        align_traffic_light_to_time_step(traffic_light, time_step)
