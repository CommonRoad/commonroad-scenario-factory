import builtins
import copy
import dataclasses
import logging
from contextlib import contextmanager
from typing import (
    AnyStr,
    Callable,
    List,
    Optional,
    Protocol,
    Sequence,
    Type,
    TypeVar,
    Union,
)

from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import LaneletNetwork
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
    SignalState,
    State,
    TraceState,
)
from commonroad.scenario.traffic_light import TrafficLight
from commonroad.scenario.trajectory import Trajectory
from typing_extensions import TypeGuard

AnyState = Union[State, SignalState]
AnyStateT = TypeVar("AnyStateT", State, SignalState, AnyState)


def align_state_to_time_step(state: AnyState, time_step: int) -> None:
    """
    Aligns the time step of `state` to a reference `time_step`.

    :param state: The state object to align.
    :param time_step: The reference time step to align `state` to.

    :return: The state object with the adjusted time step.
    """
    state.time_step -= time_step


def align_state_list_to_time_step(states: Sequence[AnyState], time_step: int) -> None:
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
        return dynamic_obstacle

    if not isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        return dynamic_obstacle

    align_state_list_to_time_step(dynamic_obstacle.prediction.trajectory.state_list, time_step)
    dynamic_obstacle.prediction.trajectory.initial_time_step = (
        dynamic_obstacle.prediction.trajectory.state_list[0].time_step
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


def crop_state_list_to_time_frame(
    states: List[AnyStateT], min_time_step: int = 0, max_time_step: Optional[int] = None
) -> Optional[List[AnyStateT]]:
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
    new_scenario = copy_scenario(
        scenario,
        copy_lanelet_network=True,
        copy_static_obstacles=True,
        copy_environment_obstacles=True,
    )

    # TODO: Also cut static and environment obstacles

    for dynamic_obstacle in scenario.dynamic_obstacles:
        new_dynamic_obstacle = crop_dynamic_obstacle_to_time_frame(
            dynamic_obstacle, min_time_step, max_time_step
        )
        if new_dynamic_obstacle is not None:
            new_scenario.add_objects(new_dynamic_obstacle)

    return new_scenario


def get_scenario_length_in_time_steps(scenario: Scenario) -> int:
    """
    Determines the total length of a scenario in time steps.

    :param scenario: The scenario to analyze.

    :return: The total number of time steps in the scenario.
    """
    max_time_step = 0
    for dynamic_obstacle in scenario.dynamic_obstacles:
        if dynamic_obstacle.prediction is None:
            max_time_step = max(max_time_step, dynamic_obstacle.initial_state.time_step)
            continue

        max_time_step = max(max_time_step, dynamic_obstacle.prediction.final_time_step)

    return max_time_step


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
        # It is necessary that `create_from_lanelet_network` is used instead of a simple deepcopy
        # because the geoemtry cache inside lanelet network might otherwise be incomplete
        new_lanelet_network = LaneletNetwork.create_from_lanelet_network(scenario.lanelet_network)
        new_scenario.add_objects(new_lanelet_network)

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
