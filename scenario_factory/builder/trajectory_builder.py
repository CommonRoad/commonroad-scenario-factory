from typing import List, Tuple, TypedDict, Union

import numpy as np
from commonroad.scenario.state import CustomState, TraceState
from commonroad.scenario.trajectory import Trajectory
from typing_extensions import Self, Unpack

from scenario_factory.builder.core import BuilderCore
from scenario_factory.utils import align_trajectory_to_time_step


class _StateArguments(TypedDict, total=False):
    position: Union[np.ndarray, Tuple[float, float], List[float]]
    velocity: float
    orientation: float


def _create_state_from_state_arguments(
    time_step: int, **kwargs: Unpack[_StateArguments]
) -> TraceState:
    """
    Helper to create a state. Handles automatic conversion of arguments.
    """
    position = kwargs.get("position")
    if isinstance(position, tuple) or isinstance(position, list):
        if len(position) != 2:
            raise ValueError(
                "Cannot create state from state arguments: Position must be excactly of length 2."
            )
        position = np.array(position)

    state_attributes = {
        "time_step": time_step,
        "position": position,
        "velocity": kwargs.get("velocity"),
        "orientation": kwargs.get("orientation"),
    }
    return CustomState(**state_attributes)


class TrajectoryBuilder(BuilderCore[Trajectory]):
    """
    The `TrajectoryBuilder` can be used to easily create a trajectory only from a start and end state.

    The resulting trajectory will be interpolated between those start and end states.
    """

    def __init__(self):
        self._state_list = []

    def start(self, time_step: int, **kwargs: Unpack[_StateArguments]) -> Self:
        """Specify the start state of the trajectory with only a few state arguments."""
        self.start_state(_create_state_from_state_arguments(time_step, **kwargs))
        return self

    def end(self, time_step: int, **kwargs: Unpack[_StateArguments]) -> Self:
        """Specify the end state of the trajectory with only a few state arguments."""
        self.end_state(_create_state_from_state_arguments(time_step, **kwargs))
        return self

    def start_state(self, start_state: TraceState) -> Self:
        """
        Specify the start state of the trajectory.
        """
        start_state.fill_with_defaults()
        self._state_list.insert(0, start_state)
        return self

    def end_state(self, end_state: TraceState) -> Self:
        """
        Specify the end state of the trajectory.
        """
        end_state.fill_with_defaults()
        self._state_list.append(end_state)
        return self

    def build(self) -> Trajectory:
        """
        Construct the `Trajectory` from the start and end states by interpolating the missing states.
        This will make sure that the trajectory is defined at each time step between start time step and end state time step.
        """
        if len(self._state_list) < 1:
            raise RuntimeError("Cannot build trajectory: At least 1 state is required!")

        time_steps = [state.time_step for state in self._state_list]
        initial_time_step = min(time_steps)
        num_resampled_states = max(time_steps) - min(time_steps)

        new_trajectory = Trajectory.resample_continuous_time_state_list(
            self._state_list,
            time_stamps_cont=np.array(time_steps),
            resampled_dt=1,
            num_resampled_states=num_resampled_states,
            initial_time_cont=initial_time_step,
        )
        align_trajectory_to_time_step(new_trajectory, initial_time_step)
        return new_trajectory
