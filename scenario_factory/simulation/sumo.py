import copy
import logging
import os
import subprocess
import warnings
from pathlib import Path
from typing import Tuple

from commonroad.scenario.scenario import Scenario, Tag
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import TLS, CR2SumoMapConverter
from crdesigner.map_conversion.sumo_map.errors import ScenarioException
from crdesigner.map_conversion.sumo_map.sumolib_net import sumo_net_from_xml
from crdesigner.map_conversion.sumo_map.util import update_edge_lengths
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.scenario.scenario_wrapper import ScenarioWrapper

from scenario_factory.simulation.config import SimulationConfig, SimulationMode

_LOGGER = logging.getLogger(__name__)


def _fix_traffic_light_signal_offsets(traffic_light_signals: TLS) -> None:
    """
    Currently the TLS program will be offset by the maximum cycle offset of all traffic lights
    that are part of one TLS program. This does not realy make sense, because the offsets only apply to individual cycles and not to the whole TLS program.
    If the offsets are applied however, this means that the CommonRoad and SUMO scenario get out of sync, because the TLS program starts after the CommonRoad one.
    To keep the CommonRoad and SUMO scenario in sync, the offset is removed here.
    """
    for programs in traffic_light_signals.programs.values():
        for program in programs.values():
            program.offset = 0


# The CR2SumoMapConverter does not limit the output of SUMO netconvert.
# If we process many different scenarios, netconvert will spam unecessary warnings to the console.
# Therefore, a custom converter is used, which limits the output by capturing SUMO netconverts output on stderr and also applies some fixes so that the SUMO scenarios become usable.
class CustomCommonroad2SumoMapConverter(CR2SumoMapConverter):
    def __init__(self, scenario: Scenario, conf: SumoConfig) -> None:
        # Override the logging level, otherwise the converter will spam info logs (which should be debug logs...)
        conf.logging_level = "ERROR"
        super().__init__(scenario, conf)

    # Overrides the `write_intermediate_files` method of the parent class,
    # to apply important fix
    def write_intermediate_files(self, output_path: str) -> Tuple[str, ...]:
        _fix_traffic_light_signal_offsets(self.traffic_light_signals)
        return super().write_intermediate_files(output_path)

    # Overrides the `merge_intermediate_files` method of the parent class
    # Mostly the same as the method of the parent class, except that we capture the subprocess output.
    # Otherwise the netconvert output will be spammed to stdout.
    def merge_intermediate_files(
        self,
        output_path: str,
        cleanup: bool,
        nodes_path: str,
        edges_path: str,
        connections_path: str,
        traffic_path: str,
        type_path: str,
    ) -> bool:
        """
        Function that merges the edges and nodes files into one using netconvert
        :param output_path
        :param cleanup: deletes temporary input files after creating net file (only deactivate for debugging)
        :param connections_path:
        :param nodes_path:
        :param edges_path:
        :param traffic_path:
        :param type_path:
        :param output_path: the relative path of the output
        :return: bool: returns False if conversion fails
        """

        # The header of the xml files must be removed
        to_remove = ["options", "xml"]
        for path in [nodes_path, edges_path, connections_path, traffic_path]:
            # Removing header in file
            with open(path, "r") as file:
                lines = file.readlines()
            with open(path, "w") as file:
                for line in lines:
                    if not any(word in line for word in to_remove):
                        file.write(line)

        self._output_file = str(output_path)
        # Calling of Netconvert
        command = (
            f"{os.environ['SUMO_HOME']}/bin/netconvert "
            f" --no-turnarounds=true"
            f" --junctions.internal-link-detail=20"
            f" --geometry.avoid-overlap=true"
            f" --geometry.remove.keep-edges.explicit=true"
            f" --geometry.remove.min-length=0.0"
            f" --tls.crossing-min.time={10}"
            f" --tls.crossing-clearance.time={10}"
            f" --offset.disable-normalization=true"
            f" --node-files={nodes_path}"
            f" --edge-files={edges_path}"
            f" --connection-files={connections_path}"
            f" --tllogic-files={traffic_path}"
            f" --type-files={type_path}"
            f" --output-file={output_path}"
            f" --seed={self.conf.random_seed_trip_generation}"
        )
        success = True
        try:
            # Capture stderr and include in output, so that we can analyze the warnings
            netconvert_output = subprocess.check_output(
                command.split(), timeout=5.0, stderr=subprocess.STDOUT
            )

            # All warnings produced by netconvert are considered debug messages,
            # because they are usuallay rather informative
            # and do not affect the functionality of the simulation
            for line in netconvert_output.decode().splitlines():
                if line.startswith("Warning"):
                    warning_message = line.lstrip("Warning: ")
                    _LOGGER.debug(
                        f"netconvert produced a warning while creating {self._output_file}: {warning_message}"
                    )

            update_edge_lengths(self._output_file)
            net = sumo_net_from_xml(self._output_file)
            self._update_junctions_from_net(net)

        except FileNotFoundError as e:
            if "netconvert" in e.filename:
                warnings.warn("Is netconvert installed and added to PATH?")
            success = False
        except ScenarioException:
            raise
        except Exception as e:
            self.logger.exception(e)
            success = False

        if cleanup and success:
            for path in [nodes_path, edges_path, connections_path, traffic_path]:
                os.remove(path)

        return success


def _get_new_sumo_config_for_scenario(
    scenario: Scenario, simulation_config: SimulationConfig, seed: int
) -> SumoConfig:
    if simulation_config.simulation_steps is None:
        raise ValueError(
            "Invalid simulation config for SUMO: option 'simulation_time_steps' must be set, but is 'None'!"
        )

    new_sumo_config = SumoConfig()

    new_sumo_config.random_seed = seed
    new_sumo_config.random_seed_trip_generation = seed
    new_sumo_config.simulation_steps = simulation_config.simulation_steps
    new_sumo_config.scenario_name = str(scenario.scenario_id)
    new_sumo_config.dt = scenario.dt
    # Disable highway mode so that intersections are not falsely identified as zipper junctions
    new_sumo_config.highway_mode = False

    return new_sumo_config


def _convert_commonroad_scenario_to_sumo_scenario(
    commonroad_scenario: Scenario, output_folder: Path, sumo_config: SumoConfig
) -> ScenarioWrapper:
    """
    Convert the lanelet network in :param:`commonroad_scenario` to a SUMO network. This will also generate the random traffic on the network.

    :param commonroad_scenario: Scenario with a lanelet network that should be converted
    :param output_folder: The folder in which the SUMO files will be created
    :param sumo_config: Configuration for the converter

    :returns: A wrapper that can be used in the SUMO simulation
    """
    new_scenario = copy.deepcopy(commonroad_scenario)
    cr2sumo = CustomCommonroad2SumoMapConverter(new_scenario, sumo_config)
    conversion_possible = cr2sumo.create_sumo_files(str(output_folder))

    if not conversion_possible:
        raise RuntimeError(
            f"Failed to convert CommonRoad scenario {commonroad_scenario.scenario_id} to SUMO"
        )

    scenario_wrapper = ScenarioWrapper()
    scenario_wrapper.sumo_cfg_file = str(cr2sumo.sumo_cfg_file)
    scenario_wrapper.initial_scenario = new_scenario
    return scenario_wrapper


def _execute_sumo_simulation(
    scenario_wrapper: ScenarioWrapper, sumo_config: SumoConfig
) -> Scenario:
    """
    Execute the concrete SUMO simulation.

    :param scenario_wrapper: A wrapper around the converted scenario.
    :param sumo_config: The configuration for the sumo simulation.

    :returns: A new scenario with the trajectories of the simulated obstacles.
    """
    sumo_sim = SumoSimulation()
    sumo_sim.initialize(sumo_config, scenario_wrapper)

    for _ in range(sumo_config.simulation_steps):
        sumo_sim.simulate_step()
    sumo_sim.simulate_step()

    sumo_sim.stop()

    scenario = sumo_sim.commonroad_scenarios_all_time_steps()
    scenario.scenario_id.obstacle_behavior = "T"
    scenario.scenario_id.prediction_id = 1
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
    if simulation_config.mode != SimulationMode.RANDOM_TRAFFIC_GENERATION:
        raise ValueError(
            f"Unsupported simulation mode {simulation_config.mode} for SUMO! Currently only {SimulationMode.RANDOM_TRAFFIC_GENERATION} is supported."
        )

    sumo_config = _get_new_sumo_config_for_scenario(scenario, simulation_config, seed)

    scenario_wrapper = _convert_commonroad_scenario_to_sumo_scenario(
        scenario, working_directory, sumo_config
    )
    new_scenario = _execute_sumo_simulation(scenario_wrapper, sumo_config)

    _patch_scenario_metadata_after_simulation(new_scenario)

    return new_scenario
