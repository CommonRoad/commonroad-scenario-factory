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
NUM_POOL = 8

# load parameters
from scenario_factory.config_files.scenario_config import ScenarioConfig
from crdesigner.map_conversion.sumo_map.config import SumoConfig

sumo_conf = SumoConfig()
sumo_conf.highway_mode = False

scenario_config = ScenarioConfig()
scenario_config.planning_pro_per_scen = 4
scenario_config.scen_per_map = 4

filenames = list(Path(scenario_directory).rglob("*.xml"))
# random.shuffle(filenames)
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
        scenario_path = dir_name + "/"  # + location_name + '-' + str(map_nr)
        scenario_orig, _ = CommonRoadFileReader(cr_file).open()
        sumo_conf.scenario_name = str(scenario_orig.scenario_id)
        cr2sumo = CR2SumoMapConverter(scenario_orig, sumo_conf)

        sumo_net_path = os.path.join(scenario_path, sumo_conf.scenario_name + '.net.xml')
        logger.info("Converting to SUMO Map")
        cr2sumo._convert_map()

        logger.info("Merging Intermediate Files")
        intermediary_files = cr2sumo.write_intermediate_files(sumo_net_path)
        conversion_possible = cr2sumo.merge_intermediate_files(sumo_net_path, True, *intermediary_files)
        if not conversion_possible:
            logger.error("Error converting map, see above for details")
            return False

        # wait for previous step to be finished
        while os.path.exists(sumo_net_path) == False:
            time.sleep(0.05)

        # scenario generation and export
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
            shutil.copy(sumo_net_path, sumo_net_copy)  # copy sumo net file into scenario-specific sub-folder
            shutil.copy(cr_file, cr_map_copy)  # copy original commonroad file into scenario-specific sub-folder # TODO this file is redundant? do not copy? or only to upper directory?

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
            scenario.tags = scenario_orig.tags  # TODO general (lanelet network based tags should be written here – latest)

            # select ego vehicles for planning problems and postprocess final CommonRoad scenarios
            cr_scenarios = GenerateCRScenarios(scenario, sumo_conf.simulation_steps, sumo_conf.scenario_name,
                                               scenario_config, scenario_dir_name, solution_folder)

            scenario_counter_prev = scenario_counter
            scenario_counter = cr_scenarios.create_cr_scenarios(map_nr, scenario_counter)

            scenario_nr_added = cr_scenarios.write_cr_file_and_video(scenario_counter_prev, CREATE_VIDEO,
                                                                     check_validity=False)

            obtained_scenario_number += scenario_nr_added
    except:
        logger.warning(f'UNEXPECTED ERROR, continue with next scenario: {traceback.format_exc()}')
        try:
            sumo_sim.stop()
        except:
            pass
        return obtained_scenario_number, cr_file

    return obtained_scenario_number, cr_file

pool = Pool(processes=NUM_POOL)
res_multi = pool.map(create_scenarios, filenames)

res = {}
for r in res_multi:
    if type(r) is tuple and len(r) == 2:
       res[r[1]] = r[0]

res = {r[1]: r[0] for r in res_multi}

logger.info(f'obtained_scenario_number: {sum(list(res.values()))}')
