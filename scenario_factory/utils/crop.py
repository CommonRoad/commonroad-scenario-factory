import copy
from typing import (
    List,
    Optional,
)

from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import (
    InitialState,
)
from commonroad.scenario.trajectory import Trajectory

from scenario_factory.utils.scenario import copy_scenario
from scenario_factory.utils.types import WithTimeStep, convert_state_to_state_type


def crop_state_list_to_time_frame(
    states: List[WithTimeStep], min_time_step: int = 0, max_time_step: Optional[int] = None
) -> Optional[List[WithTimeStep]]:
    """
    Cuts a list of states to fit within a specified time frame.

    :param states: The list of states to cut.
    :param min_time_step: The minimum allowed time step.
    :param max_time_step: The maximum allowed time step. If set to None, an open interval is assumed.

    :return: A copy of states within the specified time frame, or None if out of bounds.
    """
    if max_time_step is not None and max_time_step <= min_time_step:
        raise ValueError(
            f"Cannot cut state list to [{min_time_step},{max_time_step}]: Max time step must be strictly larger than min time step."
        )

    if len(states) < 2:
        return None

    initial_state = states[0]
    final_state = states[-1]

    if initial_state.time_step >= min_time_step:
        if max_time_step is None or final_state.time_step <= max_time_step:
            # The state list is already in the time frame
            return copy.deepcopy(states)
    if max_time_step is not None and initial_state.time_step > max_time_step:
        # The state list starts only after the max time step, so we cannot cut a trajectory from this
        return None

    if final_state.time_step < min_time_step:
        # The
        return None

    max_time_step = final_state.time_step if max_time_step is None else max_time_step
    new_state_list = copy.deepcopy(
        list(
            filter(
                lambda state: state.time_step >= min_time_step and state.time_step <= max_time_step,
                states,
            )
        )
    )

    return new_state_list


def crop_trajectory_to_time_frame(
    trajectory: Trajectory,
    min_time_step: int = 0,
    max_time_step: Optional[int] = None,
) -> Optional[Trajectory]:
    """
    Cuts a trajectory to ensure no state's time step exceeds the specified max time step.

    :param trajectory: The trajectory to be cut.
    :param min_time_step: The minimum time step to retain.
    :param max_time_step: The maximum time step to retain.

    :return: The cut trajectory, or None if the trajectory starts after `max_time_step`.
    """

    cut_state_list = crop_state_list_to_time_frame(
        trajectory.state_list, min_time_step, max_time_step
    )
    if cut_state_list is None:
        return None
    return Trajectory(cut_state_list[0].time_step, cut_state_list)


def crop_dynamic_obstacle_to_time_frame(
    original_obstacle: DynamicObstacle,
    min_time_step: int = 0,
    max_time_step: Optional[int] = None,
) -> Optional[DynamicObstacle]:
    """
    Creates a new dynamic obstacle within a specified time frame.

    :param original_obstacle: The original dynamic obstacle to be cut.
    :param min_time_step: The minimum time step of the new obstacle.
    :param max_time_step: The maximum time step of the new obstacle.

    :return: A new dynamic obstacle within the time frame, or None if out of bounds.
    """
    if max_time_step is not None and max_time_step <= min_time_step:
        raise ValueError(
            f"Cannot create a new dynamic obstacle from {original_obstacle.obstacle_id} in time frame [{min_time_step},{max_time_step}]: end time must be strictly larger than start time."
        )

    if max_time_step is not None and original_obstacle.initial_state.time_step > max_time_step:
        # The obstacle starts only after max time step, so it cannot be cropped
        return None

    if original_obstacle.prediction is not None:
        # Validate the prediction type only if there even is a prediction, otherwise the following
        # check would also fail for obstacles without a prediction, although those are valid.
        if not isinstance(original_obstacle.prediction, TrajectoryPrediction):
            raise ValueError(
                f"Cannot crop dynamic obstacle {original_obstacle.obstacle_id}: Currently only trajectory predictions are supported, but prediction is of type {type(original_obstacle.prediction)}."
            )

        if original_obstacle.prediction.final_time_step <= min_time_step:
            # The prediction starts before the time frame, so this cannot be cropped
            return None

    new_initial_state = None
    if original_obstacle.initial_state.time_step < min_time_step:
        # If the initial state is before the min time step, a new initial state is required.
        # This new initial state is at the start of the time frame aka. min_time_step
        state_at_min_time_step = copy.deepcopy(original_obstacle.state_at_time(min_time_step))
        if state_at_min_time_step is None:
            return None
        new_initial_state = convert_state_to_state_type(state_at_min_time_step, InitialState)
    else:
        new_initial_state = copy.deepcopy(original_obstacle.initial_state)

    new_trajectory_prediction = None
    if original_obstacle.prediction is not None:
        cut_trajectory_state_list = crop_state_list_to_time_frame(
            original_obstacle.prediction.trajectory.state_list, min_time_step + 1, max_time_step
        )

        if cut_trajectory_state_list is not None:
            new_trajectory = Trajectory(
                initial_time_step=cut_trajectory_state_list[0].time_step,
                state_list=cut_trajectory_state_list,
            )
            new_trajectory_prediction = TrajectoryPrediction(
                new_trajectory, original_obstacle.obstacle_shape
            )

    new_initial_signal_state = None
    if original_obstacle.initial_signal_state is not None:
        if original_obstacle.initial_signal_state.time_step < min_time_step:
            new_initial_signal_state = copy.deepcopy(
                original_obstacle.signal_state_at_time_step(min_time_step)
            )
        else:
            new_initial_signal_state = copy.deepcopy(original_obstacle.initial_signal_state)

    new_signal_series = None
    if original_obstacle.signal_series is not None:
        new_signal_series = crop_state_list_to_time_frame(
            original_obstacle.signal_series, min_time_step + 1, max_time_step
        )

    # TODO: crop histories. meta information and lanelet assignments
    return DynamicObstacle(
        obstacle_id=original_obstacle.obstacle_id,
        obstacle_type=original_obstacle.obstacle_type,
        obstacle_shape=original_obstacle.obstacle_shape,
        initial_state=new_initial_state,
        prediction=new_trajectory_prediction,
        initial_signal_state=new_initial_signal_state,
        signal_series=new_signal_series,  # type: ignore
        external_dataset_id=original_obstacle.external_dataset_id,  # type: ignore
    )


def crop_scenario_to_time_frame(
    scenario: Scenario,
    min_time_step: int = 0,
    max_time_step: Optional[int] = None,
) -> Scenario:
    """
    Crops a scenario to include only objects within a specified time frame and crop objects such that they are also in the time frame.
    The input `scenario` and all its objects are not modified.

    :param scenario: The original scenario to crop.
    :param min_time_step: The minimum time step to retain.
    :param max_time_step: The maximum time step to retain.

    :return: A new scenario within the time frame.
    """
    new_scenario = copy_scenario(scenario, copy_dynamic_obstacles=False)

    # TODO: Also cut static and environment obstacles

    for dynamic_obstacle in scenario.dynamic_obstacles:
        new_dynamic_obstacle = crop_dynamic_obstacle_to_time_frame(
            dynamic_obstacle, min_time_step, max_time_step
        )
        if new_dynamic_obstacle is not None:
            new_scenario.add_objects(new_dynamic_obstacle)

    return new_scenario
