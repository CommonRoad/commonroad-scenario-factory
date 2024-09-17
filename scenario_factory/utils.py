import dataclasses
from pathlib import Path
from typing import Optional, Protocol, Sequence, Type, TypeVar, Union

from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.state import (
    CustomState,
    ExtendedPMState,
    InitialState,
    InputState,
    KSState,
    LateralState,
    LongitudinalState,
    MBState,
    PMInputState,
    PMState,
    State,
    TraceState,
)
from typing_extensions import TypeGuard

from scenario_factory.globetrotter.osm import LocalFileMapProvider, MapProvider, OsmApiMapProvider


def select_osm_map_provider(radius: float, maps_path: Path) -> MapProvider:
    # radius > 0.8 would result in an error in the OsmApiMapProvider, because the OSM API limits the amount of data we can download
    if radius > 0.8:
        return LocalFileMapProvider(maps_path)
    else:
        return OsmApiMapProvider()


_StateT = TypeVar("_StateT", bound=State)


def convert_state_to_state_type(input_state: TraceState, target_state_type: Type[_StateT]) -> _StateT:
    """
    Alternative to State.convert_state_to_state, which accepts type parameters instead of only instance parameters.
    If :param:`input_state` is not already :param:`target_state_type`, a new state of type :param:`target_state_type` is created and all attributes, that both state types have in common, are copied from :param:`input_state` to the new state
    """
    if isinstance(input_state, target_state_type):
        return input_state

    resulting_state = target_state_type()
    # Make sure that all fields are populated in the end, and no fields are set to 'None'
    resulting_state.fill_with_defaults()

    # Copy over all fields that are common to both state types
    for to_field in dataclasses.fields(target_state_type):
        if to_field.name in input_state.attributes:
            setattr(resulting_state, to_field.name, getattr(input_state, to_field.name))
    return resulting_state


def convert_state_to_state(input_state: TraceState, reference_state: TraceState) -> TraceState:
    if input_state.used_attributes == reference_state.used_attributes:
        return input_state

    new_state = type(reference_state)()
    new_state.fill_with_defaults()
    for attribute in reference_state.used_attributes:
        if input_state.has_value(attribute):
            setattr(new_state, attribute, getattr(input_state, attribute))

    return new_state


def get_full_state_list_of_obstacle(
    dynamic_obstacle: DynamicObstacle, target_state_type: Optional[Type[State]] = None
) -> Sequence[TraceState]:
    """
    Get the state list of the :param:`dynamic_obstacle` including its initial state. Will harmonize all states to the same state type, which can be controlled through :param:`target_state_type`.

    :param dynamic_obstacle: The obstacle from which the states should be extracted
    :param target_state_type: Provide an optional state type, to which all resulting states should be converted

    :returns: The full state list of the obstacle where all states have the same state type
    """
    if target_state_type == CustomState:
        raise ValueError(
            "Cannot convert to state type 'CustomState', because the needed attributes cannot be determined."
        )

    state_list = [dynamic_obstacle.initial_state]
    if isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        state_list += dynamic_obstacle.prediction.trajectory.state_list

    if target_state_type is None:
        # Use the last state from the state_list as the reference state,
        # because for all cases this indicates the correct state type:
        # * If state_list only contains the initial state, it is this state and this function keeps the state as InitialState
        # * If state_list also contains the trajectory prediction, the reference state is the last state of this trajectory, and so the initial state will be converted to the same state type as all other states in the trajectory.
        reference_state = state_list[-1]
        if isinstance(reference_state, CustomState):
            # If the reference state is a custom state, it needs special treatment,
            # because custom states do not have a pre-definied list of attributes that can be used in the conversion.
            # Instead the conversion needs to consider the reference state instance.
            return [convert_state_to_state(state, reference_state) for state in state_list]
        else:
            target_state_type = type(reference_state)

    # Harmonizes the state types: If the caller wants to construct a trajectory from this state list, all states need to have the same attributes aka. the same state type.
    return [convert_state_to_state_type(state, target_state_type) for state in state_list]


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
