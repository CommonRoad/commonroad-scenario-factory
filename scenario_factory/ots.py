import copy
import logging
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Optional

import jpype
from commonroad.geometry.shape import Rectangle, Shape
from commonroad.prediction.prediction import Trajectory, TrajectoryPrediction
from commonroad.scenario.obstacle import ObstacleType
from commonroad.scenario.scenario import DynamicObstacle, Scenario

from scenario_factory.utils import StreamToLogger, is_state_with_discrete_time_step

_LOGGER = logging.getLogger(__name__)


def _determine_obstacle_shape_for_obstacle_type(obstacle_type: ObstacleType) -> Shape:
    # Magic values taken from the OTS source code.
    # Those values should be correct and also be used during the simulation.
    # Although, those values come from OTS, it is not trivial to retrive them, because
    # this requires an active simulator instance.
    # This is the best solution, until the bug (that no shapes are created) is fixed upstream.
    if obstacle_type == ObstacleType.CAR:
        return Rectangle(4.19, 1.7)
    elif obstacle_type == ObstacleType.TRUCK or obstacle_type == ObstacleType.BUS:
        return Rectangle(12.0, 2.55)
    elif obstacle_type == ObstacleType.MOTORCYCLE:
        return Rectangle(2.1, 0.7)
    elif obstacle_type == ObstacleType.BICYCLE:
        return Rectangle(1.9, 0.6)
    else:
        raise ValueError(f"Unknown obstacle type {obstacle_type}")


def _cut_trajectory_to_time_step(
    trajectory: Trajectory, max_time_step: int
) -> Optional[Trajectory]:
    """
    Cut the :param:`trajectory` so that no state's time step exceeds :param:`max_time_step`. \

    :param trajectory: The trajectory that should be cut. Will not be modified.
    :param max_time_step: The time step until which the trajectory should be cut.
    :returns: The cut trajectory or None, if :param:`trajectory` starts after :param:`max_time_step`.
    """
    assert is_state_with_discrete_time_step(
        trajectory.final_state
    ), f"Cannot cut trajectory with final state {trajectory.final_state} because its time step is not a discrete value"

    if trajectory.final_state.time_step <= max_time_step:
        # The trajectory does not exceed the max time step, so the trajectory is already correct
        return trajectory

    if trajectory.final_state.time_step > max_time_step:
        # The trajectory starts only after the max time step, so we cannot cut a trajectory from this
        return None

    new_state_list = list(
        filter(lambda state: state.time_step <= max_time_step, trajectory.state_list)
    )

    trajectory_initial_state = new_state_list[0]
    assert is_state_with_discrete_time_step(
        trajectory_initial_state
    ), f"Cannot cut trajectory with initial state {trajectory_initial_state} because its time step is not a discrete value"

    return Trajectory(
        initial_time_step=trajectory_initial_state.time_step, state_list=new_state_list
    )


def _correct_dynamic_obstacle(
    dynamic_obstacle: DynamicObstacle, max_time_step: int
) -> DynamicObstacle:
    """ """
    if not isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        raise RuntimeError(
            f"Cannot correct dynamic obstacle {dynamic_obstacle.obstacle_id} without a trajectory prediction"
        )

    new_obstacle_shape = _determine_obstacle_shape_for_obstacle_type(dynamic_obstacle.obstacle_type)

    # Fallback prediction is None, for the case that no valid trajectory can be cut
    new_prediction = None
    cut_trajectory = _cut_trajectory_to_time_step(
        dynamic_obstacle.prediction.trajectory, max_time_step
    )
    # If the original trajectory starts after max_time_step, it cannot be cut and therefore cut_trajectory would be None
    if cut_trajectory is not None:
        new_prediction = TrajectoryPrediction(shape=new_obstacle_shape, trajectory=cut_trajectory)

    new_obstacle = DynamicObstacle(
        obstacle_id=dynamic_obstacle.obstacle_id,
        obstacle_type=dynamic_obstacle.obstacle_type,
        obstacle_shape=new_obstacle_shape,
        initial_state=dynamic_obstacle.initial_state,
        prediction=new_prediction,
    )

    return new_obstacle


def _replace_dynamic_obstacle_in_scenario(scenario: Scenario, dynamic_obstacle: DynamicObstacle):
    """
    Replace an existing obstacle that has the same ID as :param:`dynamic_obstacle` with :param:`dynamic_obstacle` in the :param:`scenario`.
    """
    scenario.remove_obstacle(dynamic_obstacle)
    scenario.add_objects(dynamic_obstacle)


def _redirect_java_log_messages_from_ots_to_logger(target_logger: logging.Logger):
    """
    Redirect all tinylog message to the :param:`target_logger`.
    This function is reentrant.
    """
    assert jpype.isJVMStarted()

    # The imports must happen on function level, because on module level it is not guaranteed that the JVM is already running.
    from java.util import Set
    from org.djutils.logger import CategoryLogger
    from org.pmw.tinylog import Configuration, LogEntry
    from org.pmw.tinylog.writers import ConsoleWriter, LogEntryValue, Writer

    # A simple class that implements the tinylog Writer interface, so that the log messages from OTS
    # can be captured, and to suppres excessive log message to the console.
    # Instead, all messages are redirected to the target_logger as debug messages.
    @jpype.JImplements(Writer)
    class JavaLogRedirector:
        @jpype.JOverride()
        def getRequiredLogEntryValues(self) -> Set:
            return Set.of([LogEntryValue.LEVEL, LogEntryValue.MESSAGE])

        @jpype.JOverride()
        def write(self, log_entry: LogEntry) -> None:
            # Here the log output is just redirected to the python logger as a debug message
            target_logger.debug(
                "%s",
                log_entry.getMessage(),
            )

        # The rest of the methods are required to satisfy the interface, but are Nop's

        @jpype.JOverride()
        def init(self, configuration: Configuration) -> None:
            pass

        @jpype.JOverride()
        def flush(self):
            pass

        @jpype.JOverride()
        def close(self):
            pass

    writers = CategoryLogger.getWriters().toArray()
    if len(writers) != 1:
        # The default setup only includes one writer, which is the console writer.
        # If there are multiple writers, this means that someone (probably the user) configured more writers.
        # Because this should not interfere with any user configuration, the writer will not be replaced in such cases.
        _LOGGER.warning("Cannot replace Java logger, because the right one cannot be determined")
        return

    # This method is reentrant, and could be called after the writer was already replaced.
    # If this is the case, it does not need to replaced...
    if isinstance(writers[0], ConsoleWriter):
        CategoryLogger.removeWriter(writers[0])
        CategoryLogger.addWriter(JavaLogRedirector())


@contextmanager
def _suppress_java_stdout_and_stderr():
    from java.io import File, PrintStream
    from java.lang import System

    java_original_out = System.out
    java_original_err = System.err
    System.setOut(PrintStream(File("/dev/null")))
    System.setErr(PrintStream(File("/dev/null")))
    try:
        yield
    finally:
        System.setOut(java_original_out)
        System.setErr(java_original_err)


def generate_random_traffic_with_ots(
    commonroad_scenario: Scenario, seed: int, simulation_length: int
) -> Optional[Scenario]:
    """
    Use the microscopic traffic simulator OTS, to simulate random traffic on :param:`commonroad_scenario`.

    :param commonroad_scenario: The CommonRoad scenario with a lanelet network, on which the random traffic will be simulated.
    :param seed: Seed used for the traffic generation in OTS
    :param simulation_length: Number of time steps to which the resulting scenario will be cut.

    :returns: A new CommonRoad scenario with the simulated obstacles.
    """
    from crots.conversion.setup import setup_ots

    setup_ots()
    from crots.abstractions.abstraction_level import AbstractionLevel
    from crots.abstractions.simulation_execution import SimulationExecutor

    input_scenario = copy.deepcopy(commonroad_scenario)

    executor = SimulationExecutor(
        input_scenario,
        AbstractionLevel.RANDOM,
        gui_enabled=False,
        parameters=dict(),
        seed=seed,
        keep_warmup=False,
        write_to_file=False,
        max_time=simulation_length * input_scenario.dt,
    )

    _redirect_java_log_messages_from_ots_to_logger(_LOGGER)
    stream = StreamToLogger(_LOGGER)
    with redirect_stdout(stream):  # type: ignore
        with redirect_stderr(stream):  # type: ignore
            with _suppress_java_stdout_and_stderr():
                try:
                    new_scenario, _, _, _, _ = executor.execute()
                except Exception as e:
                    _LOGGER.error(
                        "Error while simulating %s: %s", commonroad_scenario.scenario_id, e
                    )
                    return None

    max_time_step = max(
        [
            obstacle.prediction.trajectory.final_state.time_step
            for obstacle in new_scenario.dynamic_obstacles
        ]
    )
    _LOGGER.debug(
        "Simulated scenario %s and created %s random obstacles for %s time steps",
        str(new_scenario.scenario_id),
        len(new_scenario.dynamic_obstacles),
        max_time_step,
    )

    # The obstacles created by cr-ots are not directly usable:
    # * They do not have a shape assigned
    # * Their trajectory might exceed simulation_length
    # Therefore they must be corrected
    for obstacle in new_scenario.dynamic_obstacles:
        corrected_obstacle = _correct_dynamic_obstacle(obstacle, simulation_length)
        _replace_dynamic_obstacle_in_scenario(new_scenario, corrected_obstacle)
    return new_scenario
