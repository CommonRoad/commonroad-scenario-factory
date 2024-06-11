from copy import deepcopy
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from crdesigner.map_conversion.sumo_map.config import SumoConfig

from scenario_factory.config_files.scenario_config import ScenarioConfig
from scenario_factory.generate_senarios import create_scenarios
from scenario_factory.pipeline.context import PipelineContext

np.random.seed(123456)


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
