import shutil
from pathlib import Path

from commonroad.common.file_reader import CommonRoadFileReader
from crots.abstractions.warm_up_estimator import warm_up_estimator
from sumocr.simulation import NonInteractiveSumoSimulation
from sumocr.sumo_map.cr2sumo.converter import SumoTrafficGenerationMode

from scenario_factory.metrics import (
    compute_general_scenario_metric,
    compute_waymo_metric,
)
from scenario_factory.scenario_container import (
    ScenarioContainer,
    write_general_scenario_metrics_of_scenario_containers_to_csv,
    write_waymo_metrics_of_scenario_containers_to_csv,
)
from scenario_factory.utils import (
    align_scenario_to_time_step,
    crop_scenario_to_time_frame,
    get_scenario_final_time_step,
)

# Uncomment one of the paragraphs and comment the other out
scenario_name = "C-DEU_MONAMerge-2_1_T-299"

# scenario_name = "DEU_AachenHeckstrasse-1_3115929_T-17428"
# SumoConfig.highway_mode = False


# Select traffic generation mode
traffic_generation_mode = SumoTrafficGenerationMode.TRAJECTORIES


warmup_required = traffic_generation_mode in [
    SumoTrafficGenerationMode.RANDOM,
    SumoTrafficGenerationMode.DEMAND,
    SumoTrafficGenerationMode.INFRASTRUCTURE,
]

print(Path(__file__).parents[1].joinpath(f"resources/paper/{scenario_name}.xml").absolute())
scenario, _ = CommonRoadFileReader(
    Path(__file__).parents[1].joinpath(f"resources/paper/{scenario_name}.xml")
).open()
simulation_steps = get_scenario_final_time_step(scenario)
if warmup_required:
    warmup_time_steps = int(warm_up_estimator(scenario.lanelet_network) * scenario.dt)
    simulation_steps += warmup_time_steps
else:
    warmup_time_steps = 0

sim = NonInteractiveSumoSimulation.from_scenario(
    scenario,
    traffic_generation_mode=traffic_generation_mode,
)

shutil.copyfile(
    Path(__file__).parents[1].joinpath(f"resources/paper/sumo/{scenario_name}.net.xml"),
    str(Path(sim.scenario_wrapper.runtime_directory.name) / f"{scenario_name}.net.xml"),
)

result = sim.run(simulation_steps=simulation_steps)
cropped_scenario = crop_scenario_to_time_frame(result.scenario, min_time_step=warmup_time_steps)
align_scenario_to_time_step(cropped_scenario, warmup_time_steps)

metrics_general = compute_general_scenario_metric(cropped_scenario)
scenario_container = ScenarioContainer(cropped_scenario)
scenario_container.add_attachment(metrics_general)
write_general_scenario_metrics_of_scenario_containers_to_csv(
    [scenario_container], Path("/tmp/general_scenario_metrics.csv")
)
if not warmup_required:
    metrics_waymo = compute_waymo_metric(cropped_scenario, scenario)
    print(metrics_waymo)
    scenario_container.add_attachment(metrics_waymo)
    write_waymo_metrics_of_scenario_containers_to_csv(
        [scenario_container], Path("/tmp/waymo_metrics.csv")
    )
