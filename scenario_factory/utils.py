import builtins
import copy
import dataclasses
import logging
from contextlib import contextmanager
from typing import AnyStr, Callable, Optional, Protocol, Sequence, Type, TypeVar, Union

from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario
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


def _create_new_scenario_with_metadata_from_old_scenario(scenario: Scenario) -> Scenario:
    """
    Create a new scenario from an old scenario and include all its metadata.

    :param scenario: The old scenario, from which the metadata will be taken

    :returns: The new scenario with all metadata, which is safe to modify.
    """
    new_scenario = Scenario(
        dt=scenario.dt,
        # The following metadata values are all objects. As they could be arbitrarily modified in-place they need to be copied.
        scenario_id=copy.deepcopy(scenario.scenario_id),
        location=copy.deepcopy(scenario.location),
        tags=copy.deepcopy(scenario.tags),
        # Author, afiiliation and source are plain strings and do not need to be copied
        author=scenario.author,
        affiliation=scenario.affiliation,
        source=scenario.source,
    )

    return new_scenario


def copy_scenario(
    scenario: Scenario,
    copy_lanelet_network: bool = False,
    copy_dynamic_obstacles: bool = False,
    copy_static_obstacles: bool = False,
    copy_environment_obstacles: bool = False,
) -> Scenario:
    """
    Helper to efficiently copy a CommonRoad Scenario. Should be prefered over a simple deepcopy of the scenario object, if not all elements of the input scenario are required in the end (e.g. the dynamic obstacles should not be included)

    :param scenario: The scenario to be copied.
    :param copy_lanelet_network: If True, the lanelet network (and all of its content) will be copied to the new scenario. If False, the new scenario will have no lanelet network.
    :param copy_dynamic_obstacles: If True, the dynamic obtsacles will be copied to the new scenario. If False, the new scenario will have no dynamic obstacles.
    :param copy_static_obstacles: If True, the static obstacles will be copied to the new scenario. If False, the new scenario will have no static obstacles.
    :param copy_environment_obstacles: If True, the environment obstacles will be copied to the new scenario. If False, the new scenario will have no environment obstacles.
    """
    new_scenario = _create_new_scenario_with_metadata_from_old_scenario(scenario)

    if copy_lanelet_network:
        new_scenario.add_objects(copy.deepcopy(scenario.lanelet_network))

    if copy_dynamic_obstacles:
        for dynamic_obstacle in scenario.dynamic_obstacles:
            new_scenario.add_objects(copy.deepcopy(dynamic_obstacle))

    if copy_static_obstacles:
        for static_obstacle in scenario.static_obstacles:
            new_scenario.add_objects(copy.deepcopy(static_obstacle))

    if copy_environment_obstacles:
        for environment_obstacle in scenario.environment_obstacle:
            new_scenario.add_objects(copy.deepcopy(environment_obstacle))

    return new_scenario


def configure_root_logger(level: int = logging.INFO) -> logging.Logger:
    """
    Configure the root logger to print messages to he console.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root_logger.addHandler(handler)

    return root_logger


@contextmanager
def redirect_all_print_calls_to(target: Optional[Callable] = None):
    """
    Patch out the python builtin `print` function so that it becomes a nop.
    """
    backup_print = builtins.print
    if target is None:
        builtins.print = lambda *args, **kwargs: None
    else:
        builtins.print = target
    try:
        yield
    finally:
        builtins.print = backup_print


class StreamToLogger:
    """
    Generic Stream that can be used as a replacement for an StringIO to redirect stdout and stderr to a logger.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def write(self, s: AnyStr) -> int:
        stripped = s.strip()
        if len(stripped) == 0:
            return 0

        self._logger.debug(stripped)
        return len(s)

    def flush(self):
        pass

    def close(self):
        pass


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
            setattr(resulting_state, to_field.name, getattr(input_state, to_field.name))
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


def get_full_state_list_of_obstacle(
    dynamic_obstacle: DynamicObstacle, target_state_type: Optional[Type[State]] = None
) -> Sequence[TraceState]:
    """
    Get the state list of the :param:`dynamic_obstacle` including its initial state.
    Will harmonize all states to the same state type, which can be controlled through :param:`target_state_type`.

    :param dynamic_obstacle: The obstacle from which the states should be extracted
    :param target_state_type: Provide an optional state type, to which all resulting states should be converted

    :returns: The full state list of the obstacle where all states have the same state type. This does however not guarantee that all states also have the same attributes, if `CustomStates` are used. See `convert_state_to_state` for more information.
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
        # * If state_list only contains the initial state, it is this state
        #    and this function keeps the state as InitialState
        # * If state_list also contains the trajectory prediction,
        #    the reference state is the last state of this trajectory,
        #    and so the initial state will be converted to the same state type
        #    as all other states in the trajectory.
        reference_state = state_list[-1]
        if isinstance(reference_state, CustomState):
            # If the reference state is a custom state, it needs special treatment,
            # because custom states do not have a pre-definied list of attributes
            # that can be used in the conversion.
            # Instead the conversion needs to consider the reference state instance.
            return [convert_state_to_state(state, reference_state) for state in state_list]
        else:
            target_state_type = type(reference_state)

    # Harmonizes the state types: If the caller wants to construct a trajectory
    # from this state list, all states need to have the same attributes aka. the same state type.
    return [convert_state_to_state_type(state, target_state_type) for state in state_list]


StateWithAcceleration = Union[
    InitialState, ExtendedPMState, LongitudinalState, InputState, PMInputState
]
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


def is_state_list_with_orientation(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithOrientation]]:
    return all(is_state_with_orientation(state) for state in state_list)


def is_state_with_position(state: TraceState) -> TypeGuard[StateWithPosition]:
    return state.has_value("position")


def is_state_list_with_position(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithPosition]]:
    return all(is_state_with_position(state) for state in state_list)


def is_state_with_discrete_time_step(
    state: TraceState,
) -> TypeGuard[StateWithDiscreteTimeStep]:
    return isinstance(state.time_step, int)


def is_state_with_velocity(state: TraceState) -> TypeGuard[StateWithVelocity]:
    return state.has_value("velocity")


def is_state_with_discrete_velocity(
    state: StateWithVelocity,
) -> TypeGuard[StateWithDiscreteVelocity]:
    return isinstance(state.velocity, float)


def is_state_list_with_velocity(
    state_list: Sequence[TraceState],
) -> TypeGuard[Sequence[StateWithVelocity]]:
    return all(is_state_with_velocity(state) for state in state_list)
