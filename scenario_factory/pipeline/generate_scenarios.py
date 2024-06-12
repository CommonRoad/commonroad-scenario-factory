import shutil
from copy import deepcopy
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path
from typing import Iterable

import numpy as np
from commonroad.scenario.scenario import Scenario
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.maps.sumo_scenario import ScenarioWrapper

from scenario_factory.config_files.scenario_config import ScenarioConfig
from scenario_factory.generate_senarios import (
    convert_commonroad_scenario_to_sumo,
    create_scenarios,
    generate_random_traffic_on_sumo_network,
)
from scenario_factory.pipeline.context import PipelineContext, PipelineStepArguments, pipeline_map_with_args

np.random.seed(123456)


def create_sumo_configuration_for_commonroad_scenario(
    ctx: PipelineContext, commonroad_scenario: Scenario
) -> CR2SumoMapConverter:
    output_folder = ctx.get_output_folder("output")
    cr2sumo = convert_commonroad_scenario_to_sumo(commonroad_scenario, output_folder)
    return cr2sumo


@dataclass
class GenerateRandomTrafficArguments(PipelineStepArguments):
    scenarios_per_map: int


@pipeline_map_with_args
def generate_random_traffic(
    ctx: PipelineContext, args: GenerateRandomTrafficArguments, cr2sumo: CR2SumoMapConverter
) -> Iterable[ScenarioWrapper]:
    output_folder = ctx.get_output_folder("output")
    intermediate_sumo_files_path = output_folder.joinpath("intermediate", str(cr2sumo.initial_scenario.scenario_id))

    sumo_net_path = intermediate_sumo_files_path.joinpath(str(cr2sumo.initial_scenario.scenario_id) + ".net.xml")
    for i in range(args.scenarios_per_map):
        scenario = deepcopy(cr2sumo.initial_scenario)
        sumo_conf = deepcopy(cr2sumo.conf)

        scenario.scenario_id.configuration_id = i + 1
        scenario_name = str(scenario.scenario_id)
        sumo_conf.scenario_name = scenario_name
        cr2sumo_map_converter = CR2SumoMapConverter(scenario, sumo_conf)
        scenario_dir_name = intermediate_sumo_files_path.joinpath(scenario_name)
        if scenario_dir_name.exists():
            shutil.rmtree(scenario_dir_name)
        scenario_dir_name.mkdir(parents=True)
        sumo_net_copy = scenario_dir_name.joinpath(scenario_name + ".net.xml")
        shutil.copy(sumo_net_path, sumo_net_copy)  # copy sumo net file into scenario-specific sub-folder

        yield generate_random_traffic_on_sumo_network(cr2sumo_map_converter, sumo_net_copy)


def simulate_scenario(ctx: PipelineContext, scenario_wrapper: ScenarioWrapper) -> Scenario:
    sumo_conf = SumoConfig()
    sumo_conf.simulation_steps = 100
    sumo_sim = SumoSimulation()
    sumo_sim.initialize(sumo_conf, scenario_wrapper)

    for _ in range(sumo_conf.simulation_steps):
        sumo_sim.simulate_step()
    sumo_sim.simulate_step()

    sumo_sim.stop()

    scenario = sumo_sim.commonroad_scenarios_all_time_steps()

    return scenario


def generate_scenarios(
    globetrotter_folder: Path,
    scenario_config: ScenarioConfig = ScenarioConfig(),
    sumo_config: SumoConfig = SumoConfig(),
    scenarios_per_map: int = 2,
    create_noninteractive: bool = True,
    create_interactive: bool = True,
    number_of_processes: int = 4,
) -> Path:
    """
    Generate scenarios from the CommonRoad files.

    Args:
        globetrotter_folder (Path): Path to the folder containing the CommonRoad files.
        scenario_config (ScenarioConfig): Configuration for the scenario generation.
        sumo_config (SumoConfig): Configuration for the SUMO simulation.
        scenarios_per_map (int): Number of scenarios to generate per map.
        create_noninteractive (bool): Whether to create non-interactive scenarios.
        create_interactive (bool): Whether to create interactive scenarios.
        number_of_processes (int): Number of processes to use for the parallel processing.

    Returns:
        Path: Path to the folder containing the generated scenarios.
    """
    sumo_config.highway_mode = False

    filenames = globetrotter_folder.rglob("*.xml")
    output_folder = globetrotter_folder.parent.joinpath("output")
    output_folder.mkdir(parents=True, exist_ok=True)

    pool = Pool(processes=number_of_processes)
    res0 = pool.starmap(
        create_scenarios,
        [
            (
                filename,
                deepcopy(sumo_config),
                deepcopy(scenario_config),
                scenarios_per_map,
                output_folder,
                create_noninteractive,
                create_interactive,
            )
            for filename in filenames
        ],
    )

    res = {}
    for r in res0:
        if type(r) is tuple and len(r) == 2:
            res[r[1]] = r[0]

    res = {r[1]: r[0] for r in res0}

    print(f"obtained_scenario_number: {sum(list(res.values()))}")
    return output_folder
