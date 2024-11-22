import dataclasses
from typing import (
    Any,
    Protocol,
    Sequence,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)

from commonroad.common.util import Interval
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
    State,
    TraceState,
)
from typing_extensions import TypeGuard

StateWithAcceleration = Union[
    InitialState, ExtendedPMState, LongitudinalState, InputState, PMInputState
]
StateWithOrientation = Union[InitialState, ExtendedPMState, KSState, LateralState, MBState]
StateWithPosition = Union[InitialState, PMState]
StateWithVelocity = Union[InitialState, PMState, KSState, MBState, LongitudinalState]


@runtime_checkable
class WithTimeStep(Protocol):
    time_step: Union[int, Interval]


@runtime_checkable
class WithDiscreteTimeStep(Protocol):
    time_step: int


@runtime_checkable
class WithDiscreteVelocity(Protocol):
    velocity: float


def is_state_with_acceleration(state: TraceState) -> TypeGuard[StateWithAcceleration]:
    return state.has_value("acceleration")


def is_state_list_with_acceleration(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithAcceleration]]:
    return all(is_state_with_acceleration(state) for state in state_list)


def is_state_with_orientation(state: TraceState) -> TypeGuard[StateWithOrientation]:
    return isinstance(state, State) and state.has_value("orientation")


def is_state_list_with_orientation(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithOrientation]]:
    return all(is_state_with_orientation(state) for state in state_list)


def is_state_with_position(state: Any) -> TypeGuard[StateWithPosition]:
    return isinstance(state, State) and state.has_value("position")


def is_state_list_with_position(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithPosition]]:
    return all(is_state_with_position(state) for state in state_list)


def is_state_with_discrete_time_step(
    state: TraceState,
) -> TypeGuard[WithDiscreteTimeStep]:
    return isinstance(state.time_step, int)


def is_state_with_velocity(state: TraceState) -> TypeGuard[StateWithVelocity]:
    return state.has_value("velocity")


def is_state_with_discrete_velocity(
    state: StateWithVelocity,
) -> TypeGuard[WithDiscreteVelocity]:
    return isinstance(state.velocity, float)


def is_state_list_with_velocity(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithVelocity]]:
    return all(is_state_with_velocity(state) for state in state_list)


_StateT = TypeVar("_StateT", bound=State)


def convert_state_to_state_type(
    input_state: TraceState, target_state_type: Type[_StateT]
) -> _StateT:
    """
    Alternative to `State.convert_state_to_state`, which also accepts type parameters.
    If :param:`input_state` is not already :param:`target_state_type`,
    a new state of type :param:`target_state_type` is created and all attributes,
    that both state types have in common, are copied from :param:`input_state` to the new state
    """
    if isinstance(input_state, target_state_type):
        return input_state

    resulting_state = target_state_type()
    # Make sure that all fields are populated in the end, and no fields are set to 'None'
    resulting_state.fill_with_defaults()

    # Copy over all fields that are common to both state types
    for to_field in dataclasses.fields(target_state_type):
        if to_field.name in input_state.attributes:
            input_state_attribute_value = getattr(input_state, to_field.name)
            setattr(resulting_state, to_field.name, input_state_attribute_value)
    return resulting_state


def convert_state_to_state(input_state: TraceState, reference_state: TraceState) -> TraceState:
    """
    Alternative to `State.convert_state_to_state`, which can also handle `CustomState`.

    :param input_state: The state which should be convereted. If the attributes already match those of `reference_state`, `input_state` will be returned.
    :param reference_state: The state which will be used as a reference, for which attributes should be available of the resulting state. All attributes which are not yet present on `input_state` will be set to their defaults.

    :returns: Either the `input_state`, if the attributes already match. Otherwise, a new state with the attributes from `reference_state` and values from `input_state`. If not all attributes of `reference_state` are available in `input_state` they are not included in the new state.
    """
    if set(input_state.used_attributes) == set(reference_state.used_attributes):
        return input_state

    new_state = type(reference_state)()
    new_state.fill_with_defaults()
    for attribute in reference_state.used_attributes:
        if input_state.has_value(attribute):
            setattr(new_state, attribute, getattr(input_state, attribute))

    return new_state
