import logging
from pathlib import Path
from typing import Union

from commonroad.scenario.scenario import Scenario, Tag
from commonroad_ots.abstractions.warm_up_estimator import warm_up_estimator
from commonroad_sumo import (
    NonInteractiveSumoSimulation,
    SumoSimulationConfig,
    SumoTrafficGenerationMode,
)
from commonroad_sumo.cr2sumo.traffic_generator import (
    AbstractTrafficGenerator,
    RandomTrafficGenerator,
)

from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from scenario_factory.utils import (
    align_scenario_to_time_step,
    crop_scenario_to_time_frame,
    get_scenario_final_time_step,
)

_LOGGER = logging.getLogger(__name__)


def _get_traffic_generator_or_mode_for_simulation_config(
    simulation_config: SimulationConfig,
) -> Union[AbstractTrafficGenerator, SumoTrafficGenerationMode]:
    if simulation_config.mode == SimulationMode.RANDOM_TRAFFIC_GENERATION:
        return RandomTrafficGenerator(seed=simulation_config.seed)
    elif simulation_config.mode == SimulationMode.DELAY:
        return SumoTrafficGenerationMode.SAFE_RESIMULATION
    elif simulation_config.mode == SimulationMode.RESIMULATION:
        return SumoTrafficGenerationMode.UNSAFE_RESIMULATION
    elif simulation_config.mode == SimulationMode.DEMAND_TRAFFIC_GENERATION:
        return SumoTrafficGenerationMode.DEMAND
    elif simulation_config.mode == SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION:
        return SumoTrafficGenerationMode.INFRASTRUCTURE
    else:
        raise ValueError(
            f"Cannot determine traffic conversion mode for simulation mode {simulation_config.mode}"
        )


def _execute_sumo_simulation(
    commonroad_scenario: Scenario,
    traffic_generator_or_mode: Union[AbstractTrafficGenerator, SumoTrafficGenerationMode],
    simulation_steps: int,
    seed: int,
) -> Scenario:
    """
    Convert the lanelet network in :param:`commonroad_scenario` to a SUMO network. This will also generate the random traffic on the network.

    :param commonroad_scenario: Scenario with a lanelet network that should be converted
    :param output_folder: The folder in which the SUMO files will be created
    :param sumo_config: Configuration for the converter

    :returns: A wrapper that can be used in the SUMO simulation
    """
    simulation_config = SumoSimulationConfig(
        random_seed=seed,
    )
    sumo_simulation = NonInteractiveSumoSimulation.from_scenario(
        commonroad_scenario,
        traffic_generator_or_mode=traffic_generator_or_mode,
        simulation_config=simulation_config,
    )
    simulation_result = sumo_simulation.run(simulation_steps)
    return simulation_result.scenario


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


def simulate_commonroad_scenario_with_sumo(
    scenario: Scenario,
    simulation_config: SimulationConfig,
    working_directory: Path,
) -> Scenario:
    """
    Simulate a CommonRoad scenario with the micrsocopic simulator SUMO. Currently, only random traffic generation is supported.

    :param scenario: The scenario with a lanelet network on which random traffic should be generated.
    :param simulation_config: The configuration for this simulation.
    :param working_directory: An empty directory that can be used to place SUMOs intermediate files there.
    :param seed: The random seed, used for the random traffic generation.

    :returns: A new scenario with the simulated trajectories.

    :raises ValueError: If the selected simulation config is invalid.
    """

    traffic_generator_or_mode = _get_traffic_generator_or_mode_for_simulation_config(
        simulation_config
    )

    if simulation_config.simulation_steps is None:
        if simulation_config.mode in [SimulationMode.RANDOM_TRAFFIC_GENERATION]:
            raise ValueError(
                f"Invalid simulation config for SUMO simulation with mode {simulation_config.mode}: option 'simulation_time_steps' must be set, but is 'None'!"
            )
        else:
            simulation_steps = get_scenario_final_time_step(scenario)
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

    new_scenario = _execute_sumo_simulation(
        scenario, traffic_generator_or_mode, simulation_steps, simulation_config.seed
    )

    _patch_scenario_metadata_after_simulation(new_scenario)

    if simulation_mode_requires_warmup:
        original_scenario_length = get_scenario_final_time_step(new_scenario)
        new_scenario = crop_scenario_to_time_frame(new_scenario, min_time_step=warmup_time_steps)
        align_scenario_to_time_step(new_scenario, warmup_time_steps)
        _LOGGER.debug(
            "Cut %s time steps from scenario %s after simulation with SUMO in mode %s to account for warmup time. The scenario after simulation had %s time steps and now has %s time steps",
            warmup_time_steps,
            new_scenario.scenario_id,
            simulation_config.mode,
            original_scenario_length,
            get_scenario_final_time_step(new_scenario),
        )

    return new_scenario
