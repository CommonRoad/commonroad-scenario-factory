""""
Adapted from main script to generate sumo scenarios and convert them back to cr scenarios for existing cr maps.
"""
from copy import deepcopy
from multiprocessing import Pool

import logging
import traceback
import random

from commonroad.common.file_reader import CommonRoadFileReader
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
scenario_directory = os.getcwd() + '/example_files/'
output_folder = os.getcwd() + '/output/noninteractive/'
CREATE_VIDEO = False
NUM_POOL = 1

# load parameters
from scenario_factory.config_files.scenario_config import ScenarioConfig
from scenario_factory.config_files.sumo_config import SumoConf
from scenario_factory.config_files.cr2sumo_map_config import CR2SumoNetConfig_edited
# use vehicle parameters from sumo_config
sumo_conf = SumoConf()
cr2net_conf = CR2SumoNetConfig_edited()
cr2net_conf.veh_params = sumo_conf.veh_params

scenario_config = ScenarioConfig()

filenames = list(Path(scenario_directory).rglob("*.xml"))
# filenames = [file for file in filenames if 'Flensburg' not in str(file)]
random.shuffle(filenames)
timestr = time.strftime("%Y%m%d-%H%M%S")

solution_folder = os.path.join(output_folder, timestr, "solutions")
os.makedirs(solution_folder, exist_ok=False)

# start logging, choose logging levels logging.INFO, logging.CRITICAL, logging.DEBUG
logger = init_logging(__name__, logging.DEBUG)


def create_scenarios(cr_file):
    cr_file = str(cr_file)
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
    os.makedirs(dir_name, exist_ok=True)

    map_nr = int(split_map_name[2])

    obtained_scenario_number = 0

    try:
        # conversion from CommonRoad to SUMO map
        sumo_net_path = dir_name + "/" + location_name + '-' + str(map_nr) + ".net.xml"
        cr2sumo_converter = CR2SumoMapConverter.from_file(cr_file, cr2net_conf)
        scenario_orig, _ = CommonRoadFileReader(cr_file).open()
        cr2sumo_converter._convert_map()
        files = cr2sumo_converter.write_intermediate_files(sumo_net_path)
        logger.info(f'write map to path {cr_file}')
        conversion_possible = cr2sumo_converter.merge_intermediate_files(sumo_net_path, False, *files)

        if not conversion_possible:
            logger.warning('Conversion to net file failed!')
            return 0, cr_file

        # read boundary from netfile
        while os.path.exists(sumo_net_path) == False:
            time.sleep(0.05)

        scenario_counter = 0
        for i_scenario in range(scenario_config.scen_per_map):
            scenario_name = location_name + '-' + str(map_nr) + "_" + str(i_scenario + 1)
            sumo_conf.scenario_name = scenario_name
            sumo_conf.scenarios_path = dir_name

            scenario_dir_name = os.path.join(dir_name, scenario_name)
            if os.path.exists(scenario_dir_name) == False:
                os.mkdir(scenario_dir_name)
            sumo_net_copy = os.path.join(scenario_dir_name, scenario_name + ".net.xml")
            cr_map_copy = os.path.join(scenario_dir_name, scenario_name + ".cr.xml")
            shutil.copy(sumo_net_path, sumo_net_copy)
            shutil.copy(cr_file, cr_map_copy)

            # generate route file and additional files for SUMO simulation
            cr2sumo_converter = CR2SumoMapConverter(deepcopy(scenario_orig), sumo_conf)
            cr2sumo_converter._create_random_routes(sumo_net_copy)

            scenario_wrapper = ScenarioWrapper()
            scenario_wrapper.initialize(scenario_name, cr2sumo_converter.sumo_cfg_file, cr_file, sumo_conf.ego_start_time)
            # simulate sumo scenario and extract scenario files
            sumo_sim = SumoSimulation()
            sumo_sim.initialize(sumo_conf, scenario_wrapper=scenario_wrapper)

            for step in range(sumo_conf.simulation_steps):
                sumo_sim.simulate_step()

            sumo_sim.stop()
            scenario = sumo_sim.commonroad_scenarios_all_time_steps()
            scenario.location = scenario_orig.location
            scenario.tags = scenario_orig.tags

            # select ego vehicles for planning problems and postprocess final CommonRoad scenarios
            cr_scenarios = GenerateCRScenarios(scenario, sumo_conf.simulation_steps, sumo_conf.scenario_name,
                                               scenario_config, scenario_dir_name, solution_folder)

            scenario_counter_new = cr_scenarios.create_cr_scenarios(map_nr, scenario_counter)

            scenario_nr_new = cr_scenarios.write_cr_file_and_video(scenario_counter, CREATE_VIDEO,
                                                                   check_validity=False)
            scenario_counter = scenario_counter_new
            obtained_scenario_number += scenario_nr_new
    except:
        logger.warning(f'UNEXPECTED ERROR, continue with next scenario: {traceback.format_exc()}')
        try:
            sumo_sim.stop()
        except:
            pass
        return obtained_scenario_number, cr_file

    return obtained_scenario_number, cr_file

pool = Pool(processes=NUM_POOL)
res0 = pool.map(create_scenarios, filenames)

res = {}
for r in res0:
    if type(r) is tuple and len(r) == 2:
       res[r[1]] = r[0]

res = {r[1]: r[0] for r in res0}

logger.info(f'obtained_scenario_number: {sum(list(res.values()))}')
