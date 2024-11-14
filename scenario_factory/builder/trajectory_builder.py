import numpy as np
from commonroad.scenario.state import TraceState
from commonroad.scenario.trajectory import Trajectory
from typing_extensions import Self

from scenario_factory.builder.core import BuilderCore


class TrajectoryBuilder(BuilderCore[Trajectory]):
    def __init__(self):
        self._state_list = []

    def start(self, start_state: TraceState) -> Self:
        start_state.fill_with_defaults()
        self._state_list.insert(0, start_state)
        return self

    def end(self, end_state: TraceState) -> Self:
        end_state.fill_with_defaults()
        self._state_list.append(end_state)
        return self

    def build(self) -> Trajectory:
        time_steps = [state.time_step for state in self._state_list]
        num_resampled_states = min(time_steps) + max(time_steps)
        return Trajectory.resample_continuous_time_state_list(
            self._state_list,
            time_stamps_cont=np.array(time_steps),
            resampled_dt=0.1,
            num_resampled_states=num_resampled_states,
        )
