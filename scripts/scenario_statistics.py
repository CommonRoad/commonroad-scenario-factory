import itertools
import random
from multiprocessing import Pool
from pathlib import Path
import numpy as np

from commonroad.common.file_reader import CommonRoadFileReader

from scenario_factory.cr_scenario_factory import StateList

folder_name ='/home/klischatm/out/2020_ITSC2020_Sumo_scenarios/20200609-162150/'

filenames = list(Path(folder_name).rglob("*_T-1.xml"))
random.shuffle(filenames)

def get_file_statistics(file_name:str):
    scenario, _ = CommonRoadFileReader(file_name).open()
    min_vel = []
    max_vel = []
    print(len(scenario.dynamic_obstacles))
    for obs in scenario.dynamic_obstacles:

        data = StateList(obs.prediction.trajectory.state_list).to_array(['velocity'] )
        min_vel.append(np.min(data))
        max_vel.append(np.max(data))

    return min_vel, max_vel

pool = Pool(processes=40)
res0 = pool.map(get_file_statistics, filenames[:200])

min_vel = np.array(list(itertools.chain.from_iterable([r[0] for r in res0])))
max_vel = np.array(list(itertools.chain.from_iterable([r[1] for r in res0])))

import matplotlib.pyplot as plt

plt.figure()
plt.hist(max_vel)
plt.show()