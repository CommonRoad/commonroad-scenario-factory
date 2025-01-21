from collections import defaultdict
from pathlib import Path

import numpy as np
from commonroad.common.file_reader import CommonRoadFileReader
from matplotlib import pyplot as plt

scenario_resim, _ = CommonRoadFileReader(
    Path("/tmp/sims_paper_ots/DEU_MONAEast-2_1_T-1.xml")
).open()
scenario_delay, _ = CommonRoadFileReader(
    Path("/tmp/sims_paper_ots/DEU_MONAEast-2_1_T-2.xml")
).open()

delay = defaultdict(float)
for obs in scenario_delay.dynamic_obstacles:
    delay[obs.obstacle_id] = (
        obs.initial_state.time_step
        - scenario_resim.obstacle_by_id(obs.obstacle_id).initial_state.time_step
    ) * 0.2

np.savetxt("delay.csv", list(delay.values()), delimiter=",")

plt.figure(figsize=(10, 5))
plt.plot(list(delay.values()))
plt.show()

print(f"Avg delay: {sum(delay.values())/len(delay)}")

stri = "0"
for i in range(1, 135):
    stri += f",{i}"
print(stri)
