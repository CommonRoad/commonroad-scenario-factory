""""
Adapted from main script to generate sumo scenarios and convert them back to cr scenarios for existing cr maps.
"""
from copy import deepcopy
from multiprocessing import Pool

import logging
import traceback
import signal
import libsumo
import numpy as np
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from interactive_scenarios.default import InteractiveSumoConfigDefault
from scenario_factory.config_files.scenario_config import ScenarioConfig
from scenario_factory.scenario_checker import DeleteScenario
from scenario_factory.scenario_util import init_logging

import os
from pathlib import Path

from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from scenario_factory.cr_scenario_factory import GenerateCRScenarios
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.maps.sumo_scenario import ScenarioWrapper
import shutil
import time

# Options
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from sumocr.sumo_config.default import SUMO_VEHICLE_PREFIX


class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


if __name__ == "__main__":
    CREATE_VIDEO = False
    NUM_POOL = 12
    CREATE_INTERACTIVE = True
    CREATE_NON_INTERACTIVE = True
    # load parameters
    # from scenario_factory.config_files.scenario_config import ScenarioConfig
    # from scenario_factory.config_files.sumo_config import SumoConf
    # use vehicle parameters from sumo_config
    sumo_conf = SumoConfig()
    sumo_conf.highway_mode = False
    # cr2net_conf = SumoConfigHighway()
    # cr2net_conf.veh_params = sumo_conf.veh_params

    np.random.seed(102)
    scenario_config = ScenarioConfig()
    scenario_directory = scenario_config.scenario_directory
    output_folder = scenario_config.output_folder

    filenames = list(Path(scenario_directory).rglob("*.xml"))
    # filenames = [file for file in filenames if 'Flensburg' not in str(file)]
    # random.shuffle(filenames)
    timestr = time.strftime("%Y%m%d-%H%M%S")

    solution_folder = os.path.join(output_folder, timestr, "solutions")
    os.makedirs(solution_folder, exist_ok=False)

    # start logging, choose logging levels logging.INFO, logging.CRITICAL, logging.DEBUG
    logger = init_logging(__name__, logging.DEBUG)


    def create_scenarios(args):
        cr_file = str(args[0])
        sumo_conf = args[1]
        logger.info(f'Start with map {cr_file}')
        if '.net' in cr_file:
            return 0, 0

        # create unique scenario ids for each scenario
        split_map_name = os.path.splitext(os.path.basename(cr_file))[0].replace('_', '-').rsplit('-')
        if split_map_name[0] == 'C':
            del split_map_name[0]
        location_name = split_map_name[0] + '_' + split_map_name[1]
        orig_map_name = location_name + '-' + split_map_name[2]
        scenario_config.map_name = location_name

        dir_name = os.path.join(output_folder, timestr, orig_map_name)
        os.makedirs(dir_name, exist_ok=False)

        map_nr = int(split_map_name[2])

        obtained_scenario_number = 0

        try:
            with timeout(seconds=300):
                # conversion from CommonRoad to SUMO map
                sumo_net_path = dir_name + "/" + location_name + '-' + str(map_nr) + ".net.xml"
                sumo_conf.scenario_name = location_name + '-' + str(map_nr)
                sumo_conf.random_seed_trip_generation = int(np.random.uniform(100, 999))
                sumo_conf.random_seed = int(np.random.uniform(100, 999))
                cr2sumo_converter = CR2SumoMapConverter.from_file(cr_file, sumo_conf)
                scenario_orig, _ = CommonRoadFileReader(cr_file).open()
                # remove PP from file
                CommonRoadFileWriter(scenario_orig, None).write_scenario_to_file(cr_file, OverwriteExistingFile.ALWAYS)
                cr2sumo_converter._convert_map()
                files = cr2sumo_converter.write_intermediate_files(sumo_net_path)
                logger.info(f'write map to path {cr_file}')
                conversion_possible = cr2sumo_converter.merge_intermediate_files(sumo_net_path, False, *files)

                if not conversion_possible:
                    logger.warning('Conversion to net file failed!')
                    return 0, cr_file

                # read boundary from netfile
                t0 = time.time()
                while not os.path.exists(sumo_net_path):
                    time.sleep(0.1)
                    if time.time() - t0 > 100:
                        raise FileNotFoundError

            scenario_counter = 1
            for i_scenario in range(scenario_config.scen_per_map):
                try:
                    with timeout(seconds=300):
                        sumo_conf_tmp = deepcopy(sumo_conf)
                        scenario_name = location_name + '-' + str(map_nr) + "_" + str(i_scenario + 1)
                        scenario_dir_name = os.path.join(dir_name, scenario_name)
                        sumo_conf_tmp.scenario_name = scenario_name
                        sumo_conf_tmp.scenarios_path = scenario_dir_name
                        sumo_conf_tmp.random_seed = int(np.random.uniform(100, 999))
                        os.makedirs(scenario_dir_name)
                        sumo_net_copy = os.path.join(scenario_dir_name, scenario_name + ".net.xml")
                        cr_map_copy = os.path.join(scenario_dir_name, scenario_name + ".cr.xml")
                        shutil.copy(sumo_net_path, sumo_net_copy)
                        shutil.copy(cr_file, cr_map_copy)
                        # create new route file
                        rou_files, additional_file, sumo_cfg_file = cr2sumo_converter._create_random_routes(
                            sumo_net_copy, scenario_name=scenario_name,
                            return_files=True)
                        while not os.path.isfile(cr2sumo_converter.sumo_cfg_file):
                            time.sleep(0.05)
                        time.sleep(0.1)

                        scenario_wrapper = ScenarioWrapper.init_from_scenario(sumo_conf_tmp, scenario_dir_name,
                                                                              cr_map_file=cr_map_copy)
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
                            trials = maxtrials

                        for step in range(sumo_conf_tmp.simulation_steps):
                            sumo_sim.simulate_step()

                        logger.info("stopping sumo simulation")
                        sumo_sim.stop()
                        logger.info("stopped sumo simulation")
                        scenario = sumo_sim.commonroad_scenarios_all_time_steps()
                        logger.info(f"obtained cr scenario wit {len(scenario.dynamic_obstacles)} obstacles")
                        # select ego vehicles for planning problems and postprocess final CommonRoad scenarios
                        try:
                            cr_scenarios = GenerateCRScenarios(scenario, sumo_conf_tmp.simulation_steps,
                                                               sumo_conf_tmp.scenario_name,
                                                               scenario_config, scenario_dir_name, solution_folder)
                        except DeleteScenario:
                            shutil.rmtree(scenario_dir_name)
                            logger.warning(f'Remove scenario with to many collisions!')
                            return obtained_scenario_number, cr_file

                        scenario_counter_new = cr_scenarios.create_cr_scenarios(map_nr, scenario_counter)
                        if CREATE_NON_INTERACTIVE:
                            scenario_nr_new = cr_scenarios.write_cr_file_and_video(scenario_counter, CREATE_VIDEO,
                                                                                   check_validity=False)
                        if CREATE_INTERACTIVE:
                            scenario_nr_new = cr_scenarios.write_interactive_scenarios_and_videos(scenario_counter,
                                                                                                  sumo_sim.ids_cr2sumo[
                                                                                                      SUMO_VEHICLE_PREFIX],
                                                                                                  sumo_net_path=sumo_net_copy,
                                                                                                  rou_files=rou_files,
                                                                                                  config=sumo_conf_tmp,
                                                                                                  default_config=InteractiveSumoConfigDefault(),
                                                                                                  create_video=CREATE_VIDEO,
                                                                                                  check_validity=False)
                        scenario_counter = scenario_counter_new
                        obtained_scenario_number += scenario_nr_new
                except TimeoutError:
                    logger.warning(f'Timeout during simulation/extraction, continue with next scenario.')
                    try:
                        sumo_sim.stop()
                    except:
                        pass
        except:
            logger.warning(f'UNEXPECTED ERROR, continue with next scenario: {traceback.format_exc()}')
            try:
                sumo_sim.stop()
            except:
                pass
            return obtained_scenario_number, cr_file

        return obtained_scenario_number, cr_file


    pool = Pool(processes=NUM_POOL)
    res0 = pool.map(create_scenarios, zip(filenames, [deepcopy(sumo_conf) for _ in range(len(filenames))]))

    res = {}
    for r in res0:
        if type(r) is tuple and len(r) == 2:
            res[r[1]] = r[0]

    res = {r[1]: r[0] for r in res0}

    logger.info(f'obtained_scenario_number: {sum(list(res.values()))}')
