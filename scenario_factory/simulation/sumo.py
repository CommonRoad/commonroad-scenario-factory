import logging
from pathlib import Path

from commonroad.scenario.scenario import Scenario, Tag
from crots.abstractions.warm_up_estimator import warm_up_estimator
from sumocr.scenario.scenario_wrapper import SumoScenarioWrapper
from sumocr.simulation.non_interactive_simulation import NonInteractiveSumoSimulation
from sumocr.sumo_map.config import SumoConfig
from sumocr.sumo_map.cr2sumo.converter import CR2SumoMapConverter, SumoTrafficGenerationMode

from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from scenario_factory.utils import (
    align_scenario_to_time_step,
    copy_scenario,
    crop_scenario_to_time_frame,
    get_scenario_length_in_time_steps,
)

_LOGGER = logging.getLogger(__name__)


def _get_new_sumo_config_for_scenario(
    scenario: Scenario, simulation_config: SimulationConfig, seed: int
) -> SumoConfig:
    new_sumo_config = SumoConfig()
    # TODO: make this cleaner and maybe also apply to OTS simulation?

    new_sumo_config.random_seed = seed
    new_sumo_config.random_seed_trip_generation = seed
    new_sumo_config.scenario_name = str(scenario.scenario_id)
    new_sumo_config.dt = scenario.dt
    # Disable highway mode so that intersections are not falsely identified as zipper junctions
    # TODO: this should be automatically determined for each scenario or it should be fixed in cr2sumo
    new_sumo_config.highway_mode = False

    return new_sumo_config


def _convert_commonroad_scenario_to_sumo_scenario(
    commonroad_scenario: Scenario,
    output_folder: Path,
    sumo_config: SumoConfig,
    traffic_generation_mode: SumoTrafficGenerationMode,
) -> SumoScenarioWrapper:
    """
    Convert the lanelet network in :param:`commonroad_scenario` to a SUMO network. This will also generate the random traffic on the network.

    :param commonroad_scenario: Scenario with a lanelet network that should be converted
    :param output_folder: The folder in which the SUMO files will be created
    :param sumo_config: Configuration for the converter

    :returns: A wrapper that can be used in the SUMO simulation
    """
    cr2sumo = CR2SumoMapConverter(commonroad_scenario, sumo_config)
    conversion_possible = cr2sumo.create_sumo_files(
        str(output_folder), traffic_generation_mode=traffic_generation_mode
    )

    if not conversion_possible:
        raise RuntimeError(
            f"Failed to convert CommonRoad scenario {commonroad_scenario.scenario_id} to SUMO"
        )

    new_scenario = copy_scenario(commonroad_scenario, copy_lanelet_network=True)
    scenario_wrapper = SumoScenarioWrapper(new_scenario, sumo_config, cr2sumo.sumo_cfg_file)
    return scenario_wrapper


def _execute_sumo_simulation(
    scenario_wrapper: SumoScenarioWrapper, simulation_steps: int
) -> Scenario:
    """
    Execute the concrete SUMO simulation.

    :param scenario_wrapper: A wrapper around the converted scenario.
    :param sumo_config: The configuration for the sumo simulation.

    :returns: A new scenario with the trajectories of the simulated obstacles.
    """

    sumo_sim = NonInteractiveSumoSimulation(scenario_wrapper)
    simulation_result = sumo_sim.run(simulation_steps)
    scenario = simulation_result.scenario

    return scenario


def _patch_scenario_metadata_after_simulation(simulated_scenario: Scenario) -> None:
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


def _get_traffic_generation_mode_for_simulation_mode(
    simulation_mode: SimulationMode,
) -> SumoTrafficGenerationMode:
    if simulation_mode == SimulationMode.RANDOM_TRAFFIC_GENERATION:
        return SumoTrafficGenerationMode.RANDOM
    elif simulation_mode == SimulationMode.DELAY:
        return SumoTrafficGenerationMode.TRAJECTORIES
    elif simulation_mode == SimulationMode.RESIMULATION:
        return SumoTrafficGenerationMode.TRAJECTORIES_UNSAFE
    elif simulation_mode == SimulationMode.DEMAND_TRAFFIC_GENERATION:
        return SumoTrafficGenerationMode.DEMAND
    elif simulation_mode == SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION:
        return SumoTrafficGenerationMode.INFRASTRUCTURE
    else:
        raise ValueError(
            f"Cannot determine traffic generation mode for simulation mode {simulation_mode}"
        )


def simulate_commonroad_scenario_with_sumo(
    scenario: Scenario,
    simulation_config: SimulationConfig,
    working_directory: Path,
    seed: int,
) -> Scenario:
    """
    Simulate a CommonRoad scenario with the micrsocopic simulator SUMO. Currently, only random traffic generation is supported.

    :param scenario: The scenario with a lanelet network on which random traffic should be generated.
    :param simulation_config: The configuration for this simulation.
    :param working_directory: An empty directory that can be used to place SUMOs intermediate files there.
    :param seed: The random seed, used for the random traffic generation.

    :returns: A new scenario with the simulated trajectories.

    :raises ValueError: If the selected simulation mode is not supported.
    """
    sumo_config = _get_new_sumo_config_for_scenario(scenario, simulation_config, seed)

    traffic_generation_mode = _get_traffic_generation_mode_for_simulation_mode(
        simulation_config.mode
    )

    if simulation_config.simulation_steps is None:
        if simulation_config.mode in [SimulationMode.RANDOM_TRAFFIC_GENERATION]:
            raise ValueError(
                f"Invalid simulation config for SUMO simulation with mode {simulation_config.mode}: option 'simulation_time_steps' must be set, but is 'None'!"
            )
        else:
            simulation_steps = get_scenario_length_in_time_steps(scenario)
            _LOGGER.debug(
                "Simulation step was not set for SUMO simulation with mode %s, so it was autodetermined to be %s",
                simulation_config.mode,
                simulation_steps,
            )
    else:
        simulation_steps = simulation_config.simulation_steps

    simulation_mode_requires_warmup = simulation_config.mode in [
        SimulationMode.DEMAND_TRAFFIC_GENERATION,
        SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION,
        SimulationMode.RANDOM_TRAFFIC_GENERATION,
    ]
    warmup_time_steps = 0
    if simulation_mode_requires_warmup:
        warmup_time_steps = int(warm_up_estimator(scenario.lanelet_network) * scenario.dt)
        simulation_steps += warmup_time_steps

    scenario_wrapper = _convert_commonroad_scenario_to_sumo_scenario(
        scenario, working_directory, sumo_config, traffic_generation_mode=traffic_generation_mode
    )
    new_scenario = _execute_sumo_simulation(scenario_wrapper, simulation_steps)

    _patch_scenario_metadata_after_simulation(new_scenario)

    if simulation_mode_requires_warmup:
        original_scenario_length = get_scenario_length_in_time_steps(new_scenario)
        new_scenario = crop_scenario_to_time_frame(new_scenario, min_time_step=warmup_time_steps)
        align_scenario_to_time_step(new_scenario, warmup_time_steps)
        _LOGGER.debug(
            "Cut %s time steps from scenario %s after simulation with SUMO in mode %s to account for warmup time. The scenario after simulation had %s time steps and now has %s time steps",
            warmup_time_steps,
            new_scenario.scenario_id,
            simulation_config.mode,
            original_scenario_length,
            get_scenario_length_in_time_steps(new_scenario),
        )

    return new_scenario
