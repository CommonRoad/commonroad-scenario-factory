from typing import Optional, Protocol, Sequence, Union

from commonroad.geometry.shape import Shape
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.state import (
    ExtendedPMState,
    InitialState,
    InputState,
    KSState,
    LateralState,
    LongitudinalState,
    MBState,
    PMInputState,
    PMState,
    TraceState,
)
from typing_extensions import TypeGuard


def find_most_likely_lanelet_by_state(lanelet_network: LaneletNetwork, state: TraceState) -> Optional[int]:
    if not isinstance(state.position, Shape):
        return None

    lanelet_ids = lanelet_network.find_lanelet_by_shape(state.position)
    if len(lanelet_ids) == 0:
        return None

    if len(lanelet_ids) == 1:
        return lanelet_ids[0]

    # TODO
    return lanelet_ids[0]


def get_full_state_list_of_obstacle(dynamic_obstacle: DynamicObstacle) -> Sequence[TraceState]:
    if dynamic_obstacle.prediction is None or not isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        return [dynamic_obstacle.initial_state]

    return [dynamic_obstacle.initial_state] + dynamic_obstacle.prediction.trajectory.state_list


StateWithAcceleration = Union[InitialState, ExtendedPMState, LongitudinalState, InputState, PMInputState]
StateWithOrientation = Union[InitialState, ExtendedPMState, KSState, LateralState, MBState]
StateWithPosition = Union[InitialState, PMState]
StateWithVelocity = Union[InitialState, PMState, KSState, MBState, LongitudinalState]


class StateWithDiscreteTimeStep(Protocol):
    time_step: int


class StateWithDiscreteVelocity(Protocol):
    velocity: float


def is_state_with_acceleration(state: TraceState) -> TypeGuard[StateWithAcceleration]:
    return state.has_value("acceleration")


def is_state_list_with_acceleration(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithAcceleration]]:
    return all(is_state_with_acceleration(state) for state in state_list)


def is_state_with_orientation(state: TraceState) -> TypeGuard[StateWithOrientation]:
    return state.has_value("orientation")


def is_state_list_with_orientation(state_list: Sequence[TraceState]) -> TypeGuard[Sequence[StateWithOrientation]]:
    return all(is_state_with_orientation(state) for state in state_list)


def is_state_with_position(state: TraceState) -> TypeGuard[StateWithPosition]:
    return state.has_value("position")


def is_state_list_with_position(state_list: Sequence[TraceState]) -> TypeGuard[Sequence[StateWithPosition]]:
    return all(is_state_with_position(state) for state in state_list)


def is_state_with_discrete_time_step(state: TraceState) -> TypeGuard[StateWithDiscreteTimeStep]:
    return isinstance(state.time_step, int)


def is_state_with_velocity(state: TraceState) -> TypeGuard[StateWithVelocity]:
    return state.has_value("velocity")


def is_state_with_discrete_velocity(state: StateWithVelocity) -> TypeGuard[StateWithDiscreteVelocity]:
    return isinstance(state.velocity, float)


def is_state_list_with_velocity(state_list: Sequence[TraceState]) -> TypeGuard[Sequence[StateWithVelocity]]:
    return all(is_state_with_velocity(state) for state in state_list)
