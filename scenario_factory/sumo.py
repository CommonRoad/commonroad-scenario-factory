import copy
import logging
import os
import subprocess
import warnings
from pathlib import Path

from commonroad.scenario.scenario import Scenario
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from crdesigner.map_conversion.sumo_map.errors import ScenarioException
from crdesigner.map_conversion.sumo_map.sumolib_net import sumo_net_from_xml
from crdesigner.map_conversion.sumo_map.util import update_edge_lengths
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.scenario.scenario_wrapper import ScenarioWrapper

logger = logging.getLogger(__name__)


# The CR2SumoMapConverter does not limit the output of SUMO netconvert.
# If we process many different scenarios, netconvert will spam unecessary warnings to the console.
# Therefore, a custmo converter is used, which limits the output by capturing SUMO netconverts output on stderr.
class CustomCommonroad2SumoMapConverter(CR2SumoMapConverter):
    def __init__(self, scenario: Scenario, conf: SumoConfig) -> None:
        # Override the logging level, otherwise the converter will spam info logs (which should be debug logs...)
        conf.logging_level = "ERROR"
        super().__init__(scenario, conf)

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
            f" --tls.guess-signals=true"
            f" --tls.group-signals=true"
            f" --tls.green.time={50}"
            f" --tls.red.time={50}"
            f" --tls.yellow.time={10}"
            f" --tls.allred.time={50}"
            f" --tls.left-green.time={50}"
            f" --tls.crossing-min.time={50}"
            f" --tls.crossing-clearance.time={50}"
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
            netconvert_output = subprocess.check_output(command.split(), timeout=5.0, stderr=subprocess.STDOUT)

            # All warnings produced by netconvert are considered debug messages,
            # because they are usuallay rather informative
            # and do not affect the functionality of the simulation
            for line in netconvert_output.decode().splitlines():
                if line.startswith("Warning"):
                    warning_message = line.lstrip("Warning: ")
                    # Although the messages
                    logger.debug(f"netconvert produced a warning while creating {self._output_file}: {warning_message}")

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


def convert_commonroad_scenario_to_sumo_scenario(
    commonroad_scenario: Scenario, output_folder: Path, sumo_config: SumoConfig
) -> ScenarioWrapper:
    new_scenario = copy.deepcopy(commonroad_scenario)
    cr2sumo = CustomCommonroad2SumoMapConverter(new_scenario, sumo_config)
    conversion_possible = cr2sumo.create_sumo_files(str(output_folder))

    if not conversion_possible:
        raise RuntimeError(f"Failed to convert CommonRoad scenario {commonroad_scenario.scenario_id} to SUMO")

    scenario_wrapper = ScenarioWrapper()
    scenario_wrapper.sumo_cfg_file = str(cr2sumo.sumo_cfg_file)
    scenario_wrapper.initial_scenario = new_scenario
    return scenario_wrapper


def simulate_commonroad_scenario(scenario_wrapper: ScenarioWrapper, sumo_config: SumoConfig) -> Scenario:
    sumo_sim = SumoSimulation()
    sumo_sim.initialize(sumo_config, scenario_wrapper)

    for _ in range(sumo_config.simulation_steps):
        sumo_sim.simulate_step()
    sumo_sim.simulate_step()

    sumo_sim.stop()

    scenario = sumo_sim.commonroad_scenarios_all_time_steps()
    return scenario
