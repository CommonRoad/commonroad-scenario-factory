import logging
import os
import shutil
import signal
import time
import traceback
from copy import deepcopy
from multiprocessing import Pool
from pathlib import Path

import libsumo
import numpy as np
from commonroad.common.file_reader import CommonRoadFileReader

# Options
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.maps.sumo_scenario import ScenarioWrapper
from sumocr.sumo_config.default import SUMO_VEHICLE_PREFIX, InteractiveSumoConfigDefault

from scenario_factory.config_files.scenario_config import ScenarioConfig
from scenario_factory.cr_scenario_factory import GenerateCRScenarios
from scenario_factory.scenario_checker import DeleteScenario
from scenario_factory.scenario_util import init_logging


class Timeout:
    def __init__(self, seconds=1, error_message="Timeout"):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def create_scenarios(
    cr_file: Path,
    sumo_config: SumoConfig,
    scenario_config: ScenarioConfig,
    scenarios_per_map: int,
    output_path: Path,
    create_noninteractive: bool,
    create_interactive: bool,
    timeout: int = 60,
):
    logging.info(f"Start with map {cr_file}")

    # create unique scenario ids for each scenario
    split_map_name = os.path.splitext(os.path.basename(cr_file))[0].replace("_", "-").rsplit("-")
    if split_map_name[0] == "C":
        del split_map_name[0]
    location_name = split_map_name[0] + "_" + split_map_name[1]
    orig_map_name = location_name + "-" + split_map_name[2]

    map_nr = int(split_map_name[2])
    obtained_scenario_number = 0
    solution_folder = output_path.joinpath("interactive", "solutions")
    solution_folder.mkdir(parents=True, exist_ok=True)

    try:
        with Timeout(seconds=timeout):
            # conversion from CommonRoad to SUMO map
            intermediate_sumo_files_path = output_path.joinpath("intermediate", orig_map_name)
            scenario_orig, _ = CommonRoadFileReader(cr_file).open()
            scenario_orig.scenario_id = orig_map_name
            sumo_config.scenario_name = str(scenario_orig.scenario_id)
            cr2sumo = CR2SumoMapConverter(scenario_orig, sumo_config)

            sumo_net_path = os.path.join(intermediate_sumo_files_path, sumo_config.scenario_name + ".net.xml")
            logging.info("Converting to SUMO Map")
            cr2sumo._convert_map()

            logging.info("Merging Intermediate Files")
            intermediate_sumo_files_path.mkdir(parents=True, exist_ok=True)
            intermediary_files = cr2sumo.write_intermediate_files(sumo_net_path)
            conversion_possible = cr2sumo.merge_intermediate_files(sumo_net_path, True, *intermediary_files)

            if not conversion_possible:
                logging.warning("Conversion to net file failed!")
                return 0, cr_file

            # wait for previous step to be finished
            while not os.path.isfile(sumo_net_path):
                time.sleep(0.05)

        # scenario generation and export
        scenario_counter = 0
        for i_scenario in range(scenarios_per_map):
            try:
                with ((Timeout(seconds=timeout))):
                    sumo_conf_tmp = deepcopy(sumo_config)
                    scenario_name = location_name + "-" + str(map_nr) + "_" + str(i_scenario + 1)
                    scenario_dir_name = intermediate_sumo_files_path.joinpath(scenario_name)
                    sumo_conf_tmp.scenario_name = scenario_name
                    sumo_conf_tmp.scenarios_path = scenario_dir_name
                    sumo_conf_tmp.random_seed = int(np.random.uniform(100, 999))
                    if scenario_dir_name.exists():
                        shutil.rmtree(scenario_dir_name)
                    scenario_dir_name.mkdir()
                    sumo_net_copy = scenario_dir_name.joinpath(scenario_name + ".net.xml")
                    cr_map_copy = scenario_dir_name.joinpath(scenario_name + ".cr.xml")
                    shutil.copy(sumo_net_path, sumo_net_copy)  # copy sumo net file into scenario-specific sub-folder
                    shutil.copy(cr_file, cr_map_copy)  # copy original commonroad file into scenario-specific sub-folder
                    # TODO this file is redundant? do not copy? or only to upper directory?

                    # generate route file and additional files for SUMO simulation
                    cr2sumo_converter = CR2SumoMapConverter(deepcopy(scenario_orig), sumo_config)
                    rou_files, additional_file, sumo_cfg_file = cr2sumo_converter._create_random_routes(
                        sumo_net_copy, scenario_name=scenario_name, return_files=True
                    )
                    while not os.path.isfile(cr2sumo_converter.sumo_cfg_file):
                        time.sleep(0.05)
                    time.sleep(0.1)

                    scenario_wrapper = ScenarioWrapper.init_from_scenario(
                        sumo_conf_tmp, scenario_dir_name, cr_map_file=cr_map_copy
                    )  # TODO parameters are redundant

                    # simulate sumo scenario and extract scenario files
                    sumo_sim = SumoSimulation()
                    trials = 0
                    maxtrials = 3
                    while trials < maxtrials:
                        try:
                            print(scenario_wrapper)
                            sumo_sim.initialize(sumo_conf_tmp, scenario_wrapper=scenario_wrapper)
                        except libsumo.libsumo.TraCIException:
                            time.sleep(0.1)
                            trials += 1
                        trials = maxtrials  # TODO why this?

                    for step in range(sumo_conf_tmp.simulation_steps):
                        sumo_sim.simulate_step()

                    # logger.info("stopping sumo simulation")
                    sumo_sim.stop()
                    # logger.info("stopped sumo simulation")
                    scenario = sumo_sim.commonroad_scenarios_all_time_steps()
                    logging.info(f"obtained cr scenario with {len(scenario.dynamic_obstacles)} obstacles")

                    scenario.scenario_id = orig_map_name
                    scenario_config.map_name = orig_map_name
                    scenario.location = scenario_orig.location
                    scenario.tags = scenario_orig.tags

                    # select ego vehicles for planning problems and postprocess final CommonRoad scenarios
                    try:
                        cr_scenarios = GenerateCRScenarios(
                            scenario,
                            sumo_conf_tmp.simulation_steps,
                            sumo_conf_tmp.scenario_name,
                            scenario_config,
                            scenario_dir_name,
                            solution_folder,
                        )

                    except DeleteScenario:
                        shutil.rmtree(scenario_dir_name)
                        logging.warning("Remove scenario with to many collisions!")
                        return obtained_scenario_number, cr_file

                    scenario_counter_prev = scenario_counter
                    scenario_counter = cr_scenarios.create_cr_scenarios(map_nr, scenario_counter)
                    scenario_nr_added = 0
                    if create_noninteractive:
                        output_noninteractive = output_path.joinpath("noninteractive")
                        output_noninteractive.mkdir(parents=True, exist_ok=True)
                        scenario_nr_added += cr_scenarios.write_cr_file_and_video(
                            scenario_counter_prev,
                            create_video=False,
                            check_validity=False,  # TODO set True
                            output_path=output_noninteractive,
                        )

                    if create_interactive:
                        output_interactive = output_path.joinpath("interactive")
                        output_interactive.mkdir(parents=True, exist_ok=True)
                        scenario_nr_added += cr_scenarios.write_interactive_scenarios_and_videos(
                            scenario_counter_prev,
                            sumo_sim.ids_cr2sumo[SUMO_VEHICLE_PREFIX],
                            sumo_net_path=sumo_net_copy,
                            rou_files=rou_files,
                            config=sumo_conf_tmp,
                            default_config=InteractiveSumoConfigDefault(),
                            create_video=False,
                            check_validity=False,  # TODO set True
                            output_path=output_interactive,
                        )

                    obtained_scenario_number += scenario_nr_added

            except TimeoutError:
                logging.warning("Timeout during simulation/extraction, continue with next scenario.")
                try:
                    sumo_sim.stop()
                except Exception:
                    pass

    except Exception as e:
        print(e)
        logging.warning(f"UNEXPECTED ERROR, continue with next scenario: {traceback.format_exc()}")
        try:
            sumo_sim.stop()
        except Exception:
            pass
        return obtained_scenario_number, cr_file

    return obtained_scenario_number, cr_file


if __name__ == "__main__":
    # set parameters
    CREATE_VIDEO = False
    NUM_POOL = 6
    CREATE_INTERACTIVE = True
    CREATE_NON_INTERACTIVE = True
    np.random.seed(102)
    timestr = time.strftime("%Y%m%d-%H%M%S")

    # set sumo config
    sumo_config = SumoConfig()
    sumo_config.highway_mode = False

    # set scenario config
    scenario_config = ScenarioConfig()
    scenario_directory = scenario_config.scenario_directory

    # load files
    filenames = list(Path(scenario_directory).rglob("*.xml"))
    filenames = [file for file in filenames]  # if 'DEU' not in str(file)
    # random.shuffle(filenames)

    solution_folder = os.path.join(scenario_config.output_folder, timestr, "solutions")
    os.makedirs(solution_folder, exist_ok=False)

    # start logging, choose logging levels logging.INFO, logging.CRITICAL, logging.DEBUG
    logger = init_logging(__name__, logging.DEBUG)

    pool = Pool(processes=NUM_POOL)
    res0 = pool.map(create_scenarios, zip(filenames, [deepcopy(sumo_config) for _ in range(len(filenames))]))

    res = {}
    for r in res0:
        if type(r) is tuple and len(r) == 2:
            res[r[1]] = r[0]

    res = {r[1]: r[0] for r in res0}

    logger.info(f"obtained_scenario_number: {sum(list(res.values()))}")
