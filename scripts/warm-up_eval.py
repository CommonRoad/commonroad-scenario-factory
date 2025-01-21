from collections import defaultdict
from pathlib import Path

import numpy as np
from commonroad.common.file_reader import CommonRoadFileReader
from crots.abstractions.warm_up_estimator import warm_up_estimator
from matplotlib import pyplot as plt

scenario, _ = CommonRoadFileReader(
    Path("/tmp/sims_paper_ots_keep_warmup/DEU_MONAEast-2_2_T-3.xml")
).open()

number_of_vehicles_at_k = defaultdict(int)
velocity_sum_of_vehicles_at_k = defaultdict(float)

for obs in scenario.dynamic_obstacles:
    # number_of_vehicles_at_k[obs.initial_state.time_step] += 1
    for state in obs.prediction.trajectory.state_list:
        number_of_vehicles_at_k[state.time_step] += 1
        velocity_sum_of_vehicles_at_k[state.time_step] += state.velocity

velocity_mean_at_k = {
    k: v / number_of_vehicles_at_k[k] for k, v in velocity_sum_of_vehicles_at_k.items()
}

total_lanelet_network_length = 0.0
for lanelet in scenario.lanelet_network.lanelets:
    total_lanelet_network_length += np.sum(
        np.linalg.norm(np.diff(lanelet.center_vertices, axis=0), axis=1)
    )

total_lanelet_network_length /= 1000  # convert to km

warm_up_with_margin = warm_up_estimator(scenario.lanelet_network)
print(f"Warm-up estimate is: {warm_up_with_margin/5}")

times = [x / 5 for x in list(number_of_vehicles_at_k.keys())[:-1]]
np.savetxt("times.csv", times, delimiter=",")
rhos = list(number_of_vehicles_at_k.values())[:-1] / total_lanelet_network_length
np.savetxt("rhos.csv", rhos, delimiter=",")
velocities = list(velocity_mean_at_k.values())[:-1]
np.savetxt("velocities.csv", velocities, delimiter=",")

plt.figure(figsize=(10, 5))
plt.plot(times, rhos, color="blue")
plt.plot(times, velocities, color="orange")
plt.legend(["Density", "Velocity"])
plt.plot([0, 230], [13.82, 13.82], color="blue")
plt.plot([0, 230], [13.82 + 1.63, 13.82 + 1.63], linestyle="--", color="blue")
plt.plot([0, 230], [13.82 - 1.63, 13.82 - 1.63], linestyle="--", color="blue")
plt.plot([0, 230], [11.06, 11.06], color="orange")
plt.plot([0, 230], [11.06 + 1.61, 11.06 + 1.61], linestyle="--", color="orange")
plt.plot([0, 230], [11.06 - 1.61, 11.06 - 1.61], linestyle="--", color="orange")
plt.plot([warm_up_with_margin / 5, warm_up_with_margin / 5], [0, 17], color="red")
plt.plot([warm_up_with_margin, warm_up_with_margin], [0, 17], color="red")


plt.ylim(bottom=0)
plt.show()
