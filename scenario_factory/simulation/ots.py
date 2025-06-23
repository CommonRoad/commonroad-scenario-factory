import logging
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import AnyStr, Optional

import jpype
from commonroad.geometry.shape import Rectangle, Shape
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import ObstacleType
from commonroad.scenario.scenario import DynamicObstacle, Scenario, Tag
from commonroad_ots.abstractions.abstraction_level import AbstractionLevel

from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from scenario_factory.utils import (
    copy_scenario,
    crop_trajectory_to_time_frame,
    get_scenario_final_time_step,
)

_LOGGER = logging.getLogger(__name__)


class _StreamToLogger:
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


def _determine_obstacle_shape_for_obstacle_type(obstacle_type: ObstacleType) -> Shape:
    # Magic values taken from the OTS source code.
    # Although, those values come from OTS, it is not trivial to retrive them at runtime, because
    # this requires an active simulator instance.
    # TODO: The cr-ots-interface should take care of correctly configuring those values
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


def _correct_dynamic_obstacle(
    dynamic_obstacle: DynamicObstacle, max_time_step: Optional[int] = None
) -> DynamicObstacle:
    """ """
    if not isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        raise RuntimeError(
            f"Cannot correct dynamic obstacle {dynamic_obstacle.obstacle_id} without a trajectory prediction"
        )

    new_obstacle_shape = _determine_obstacle_shape_for_obstacle_type(dynamic_obstacle.obstacle_type)

    new_prediction = None
    if max_time_step is not None:
        # Fallback prediction is None, for the case that no valid trajectory can be cut
        new_prediction = None
        cut_trajectory = crop_trajectory_to_time_frame(
            dynamic_obstacle.prediction.trajectory, min_time_step=0, max_time_step=max_time_step
        )
        # If the original trajectory starts after max_time_step, it cannot be cut and therefore cut_trajectory would be None
        if cut_trajectory is not None:
            new_prediction = TrajectoryPrediction(
                shape=new_obstacle_shape, trajectory=cut_trajectory
            )
    else:
        # Got no information about the desired trajectory length, so we just copy the trajectory over
        new_prediction = dynamic_obstacle.prediction

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


def _post_process_scenario_simulated_with_random_mode(
    scenario: Scenario, simulation_time_steps: Optional[int] = None
) -> None:
    # The obstacles created by cr-ots are not directly usable:
    # * They do not have a shape assigned
    # * Their trajectory might exceed simulation_length
    # Therefore they must be corrected
    for obstacle in scenario.dynamic_obstacles:
        corrected_obstacle = _correct_dynamic_obstacle(obstacle, simulation_time_steps)
        _replace_dynamic_obstacle_in_scenario(scenario, corrected_obstacle)


def _redirect_java_log_messages_from_ots_to_logger(target_logger: logging.Logger):
    """
    Redirect all tinylog message to the :param:`target_logger`. If a logger already exists, it will be replaced.
    """
    assert jpype.isJVMStarted()

    # The imports must happen on function level, because on module level it is not guaranteed that the JVM is already running.
    from java.util import Set
    from org.djutils.logger import CategoryLogger
    from org.pmw.tinylog import Configuration, LogEntry
    from org.pmw.tinylog.writers import LogEntryValue, Writer

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
        def flush(self): ...

        @jpype.JOverride()
        def close(self): ...

    writers = CategoryLogger.getWriters().toArray()
    if len(writers) != 1:
        # The default setup only includes one writer, which is the console writer.
        # If there are multiple writers, this means that someone (probably the user) configured more writers.
        # Because this should not interfere with any user configuration, the writer will not be replaced in such cases.
        _LOGGER.warning("Cannot replace Java logger, because the right one cannot be determined")
        return

    # Always override the logger, even though one might already exist.
    CategoryLogger.removeWriter(writers[0])
    CategoryLogger.addWriter(JavaLogRedirector())


@contextmanager
def _suppress_java_stdout_and_stderr():
    """
    Redirect the stdout and stderr of the JVM to devnull.
    """
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


def _simulation_mode_to_commonroad_ots_abstraction_level(
    simulation_mode: SimulationMode,
) -> AbstractionLevel:
    if simulation_mode == SimulationMode.RANDOM_TRAFFIC_GENERATION:
        return AbstractionLevel.RANDOM
    elif simulation_mode == SimulationMode.RESIMULATION:
        return AbstractionLevel.RESIMULATION
    elif simulation_mode == SimulationMode.DELAY:
        return AbstractionLevel.DELAY
    elif simulation_mode == SimulationMode.DEMAND_TRAFFIC_GENERATION:
        return AbstractionLevel.DEMAND
    elif simulation_mode == SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION:
        return AbstractionLevel.INFRASTRUCTURE
    else:
        supported_simulation_modes = [mode for mode in SimulationMode]
        raise ValueError(
            f"Unsupported simulation mode {simulation_mode}. Supported simulation modes: {supported_simulation_modes}"
        )


def _execute_ots_simulation(
    input_scenario: Scenario,
    simulation_mode: SimulationMode,
    seed: int,
    simulation_length: Optional[int] = None,
) -> Scenario:
    """
    Simulate :param:`input_scenario` in OTS with :param:`simulation_mode`.

    :param input_scenario: The CommonRoad Scenario that should be simulated. Might be modified during the simulation.
    :param simulation_mode: The configured simulation mode
    :param seed: Seed for the simulation
    :param simulation_length: Optionally provide a limit to the simulation time

    :returns: When the simulation was executed successfully a copy of :param:`input_scenario` with the simulated dynamic obstacles is returned.
    """
    from commonroad_ots.conversion.setup import setup_ots

    # This sets up the java environment for OTS and starts OTS
    setup_ots()
    from commonroad_ots.abstractions.simulation_execution import SimulationExecutor

    abstraction_level = _simulation_mode_to_commonroad_ots_abstraction_level(simulation_mode)

    # Only set the max_time if a simulation_length was provided.
    # If max_time is None, the simulation time will be determined based on the trajectories of the dynamic obstacles in the input_scenario.
    max_time = None if simulation_length is None else simulation_length * input_scenario.dt
    executor = SimulationExecutor(
        input_scenario,
        abstraction_level,
        gui_enabled=False,
        parameters=dict(),
        seed=seed,
        keep_warmup=False,
        write_to_file=False,
        max_time=max_time,
    )

    _redirect_java_log_messages_from_ots_to_logger(_LOGGER)
    stream = _StreamToLogger(_LOGGER)
    # Also StreamToLogger implements the I/O interface, it is not a subclass of IO.
    # Therefore, the type checker does not recognice that infact everything is alright.
    with redirect_stdout(stream):  # type: ignore
        with redirect_stderr(stream):  # type: ignore
            with _suppress_java_stdout_and_stderr():
                try:
                    (
                        new_scenario,
                        conversion_time_sec,
                        simulation_time_sec,
                        retransfer_time_sec,
                        _,
                    ) = executor.execute()
                    _LOGGER.debug(
                        "Successfully simulated scenario %s with OTS. Simulation time: %ss, Conversion time: %ss, Retransfer time: %ss",
                        input_scenario.scenario_id,
                        round(simulation_time_sec, 2),
                        round(conversion_time_sec, 2),
                        round(retransfer_time_sec, 2),
                    )
                    return new_scenario
                except Exception as e:
                    # Not optimal to catch all exceptions here, but OTS does not expose a consistent error type...
                    _LOGGER.error("Error while simulating %s: %s", input_scenario.scenario_id, e)
                    raise e


def _check_can_simulate_scenario_with_simulation_config(
    scenario: Scenario, simulation_config: SimulationConfig
) -> None:
    """
    Check whether the `scenario` has properties that could lead to exceptions in cr-ots-interface when simulated with `simulation_config`.

    :param scenario: The scenario that should be simulated.
    :param simulation_config: The simulation config for the scenario.

    :raises RuntimeError: If the scenario cannot be simulated with the given simulation config.
    """
    if simulation_config.mode != SimulationMode.RANDOM_TRAFFIC_GENERATION:
        # All simulation modes except random traffic generation, need dynamic obstacles in the scenario
        if len(scenario.dynamic_obstacles) == 0:
            raise RuntimeError(
                f"Cannot simulate scenario {scenario.scenario_id} in OTS with {simulation_config.mode}: The scenario does not contain any dynamic obstacles."
            )

    if simulation_config.mode == SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION:
        # The infrastructure simulation mode only considers obstacles that were not defined at the initial time step.
        # But if all obstacles are definied at the initial time step, the simulation is empty, which is not gracefully handled by cr-ots.
        if all(obstacle.initial_state.time_step <= 0 for obstacle in scenario.dynamic_obstacles):
            raise RuntimeError(
                f"Cannot simulate scenario {scenario.scenario_id} in OTS with {simulation_config.mode}: The simulation mode only considers obstacles after the initial time step, but all obstacles start at the initial time step. So the simulation would be empty."
            )


def _patch_scenario_metadata_after_simulation(simulated_scenario: Scenario):
    """
    Make sure the metadata of `scenario` is updated accordingly after the simulation:
    * Obstacle behavior is set to 'Trajectory'
    * The scenario has a prediction ID (required if obstacle behavior is set)
    * Set the 'simulated' tag
    """
    simulated_scenario.scenario_id.obstacle_behavior = "T"
    if simulated_scenario.scenario_id.configuration_id is None:
        simulated_scenario.scenario_id.configuration_id = 1

    if simulated_scenario.scenario_id.prediction_id is None:
        simulated_scenario.scenario_id.prediction_id = 1

    if simulated_scenario.tags is None:
        simulated_scenario.tags = set()

    simulated_scenario.tags.add(Tag.SIMULATED)


def simulate_commonroad_scenario_with_ots(
    commonroad_scenario: Scenario, simulation_config: SimulationConfig
) -> Scenario:
    """
    Use the microscopic traffic simulator OTS, to simulate the scenario according to the simulation mode in `simulation_config`.

    :param commonroad_scenario: The CommonRoad scenario which will be simulated. If the `SimulationMode` is not `SimulationMode.RANDOM_TRAFFIC_GENERATION`, dynamic obstacles must be present in the scenario.
    :param simulation_config: Configuration for the simulation.
    :param seed: Seed used for the traffic generation in OTS.

    :returns: A new CommonRoad scenario with the simulated obstacles and None, if the simulation was unsuccessfull.
    """

    _check_can_simulate_scenario_with_simulation_config(commonroad_scenario, simulation_config)

    # Scenario must be copied, because it might be modified during the simulation
    input_scenario = copy_scenario(commonroad_scenario)
    new_scenario = _execute_ots_simulation(
        input_scenario,
        simulation_config.mode,
        simulation_config.seed,
        simulation_config.simulation_steps,
    )

    scenario_length = get_scenario_final_time_step(new_scenario)

    _LOGGER.debug(
        "Simulated scenario %s and created %s random obstacles for %s time steps",
        str(new_scenario.scenario_id),
        len(new_scenario.dynamic_obstacles),
        scenario_length,
    )

    if simulation_config.mode == SimulationMode.RANDOM_TRAFFIC_GENERATION:
        # The random traffic generation does not produce fully usable scenarios (e.g. obstacle shapes are missing).
        # Therefore, the results are post processed to make the scenario usable.
        _post_process_scenario_simulated_with_random_mode(
            new_scenario, simulation_config.simulation_steps
        )

    _patch_scenario_metadata_after_simulation(new_scenario)

    return new_scenario
