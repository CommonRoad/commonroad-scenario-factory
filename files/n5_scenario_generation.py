from multiprocessing import Pool
from copy import deepcopy
from scenario_factory.config_files.scenario_config import ScenarioConfig
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from pathlib import Path
from scenario_factory.generate_senarios import create_scenarios
import logging
from scenario_factory.scenario_util import init_logging
import numpy as np

np.random.seed(123456)

# start logging, choose logging levels logging.DEBUG, INFO, WARN, ERROR, CRITICAL
logger = init_logging(__name__, logging.WARN)

# set sumo config
sumo_config = SumoConfig()
sumo_config.highway_mode = False

# set scenario config
scenario_config = ScenarioConfig()
scenarios_per_map = 8
create_noninteractive = True
create_interactive = True

filenames = Path("globetrotter").rglob("*.xml")
output_path = Path("output")

"""
for file in filenames:
    create_scenarios(
        file,
        deepcopy(sumo_config),
        deepcopy(scenario_config),
        scenarios_per_map,
        output_path,
        create_noninteractive,
        create_interactive
    )
"""
pool = Pool(processes=18)
res0 = pool.starmap(create_scenarios, [(filename, deepcopy(sumo_config), deepcopy(scenario_config), scenarios_per_map, output_path, create_noninteractive, create_interactive) for filename in filenames])

res = {}
for r in res0:
    if type(r) is tuple and len(r) == 2:
        res[r[1]] = r[0]

res = {r[1]: r[0] for r in res0}

logger.warn(f'obtained_scenario_number: {sum(list(res.values()))}')
