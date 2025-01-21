from collections import defaultdict
from pathlib import Path
from matplotlib import pyplot as plt

from commonroad.common.file_reader import CommonRoadFileReader

scenario_resim, _ = CommonRoadFileReader(Path("/tmp/sims_paper_ots/DEU_MONAEast-2_2_T-1.xml")).open()
scenario_delay, _ = CommonRoadFileReader(Path("/tmp/sims_paper_ots/DEU_MONAEast-2_2_T-2.xml")).open()

delay = defaultdict(float)
for obs in scenario_delay.dynamic_obstacles:
    delay[obs.obstacle_id] = (obs.initial_state.time_step - scenario_resim.obstacle_by_id(obs.obstacle_id).initial_state.time_step)*0.2

plt.figure(figsize=(10, 5))
plt.plot(list(delay.values()))
plt.show()

print(f"Avg delay: {sum(delay.values())/len(delay)}")