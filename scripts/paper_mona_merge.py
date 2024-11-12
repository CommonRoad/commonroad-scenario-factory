import shutil
from pathlib import Path

from commonroad.common.file_reader import CommonRoadFileReader
from crots.abstractions.warm_up_estimator import warm_up_estimator
from sumocr.backend.sumo_simulation_backend import TraciSumoSimulationBackend
from sumocr.scenario.scenario_wrapper import ScenarioWrapper, SumoScenarioWrapper
from sumocr.simulation import NonInteractiveSumoSimulation
from sumocr.sumo_map.config import SumoConfig
from sumocr.sumo_map.cr2sumo.converter import SumoTrafficGenerationMode
from sumocr.sumo_map.util import get_scenario_length_in_seconds

from scenario_factory.metrics.general_scenario_metric import compute_general_scenario_metric
from scenario_factory.metrics.waymo_metric import compute_waymo_metric
from scenario_factory.utils import (
    align_scenario_to_time_step,
    crop_scenario_to_time_frame,
    get_scenario_length_in_time_steps,
)

traffic_generation_mode = SumoTrafficGenerationMode.INFRASTRUCTURE
warmup_required = traffic_generation_mode in [
    SumoTrafficGenerationMode.RANDOM,
    SumoTrafficGenerationMode.DEMAND,
    SumoTrafficGenerationMode.INFRASTRUCTURE,
]

scenario, _ = CommonRoadFileReader(
    Path(__file__).parents[1].joinpath("resources/paper/C-DEU_MONAMerge-2_1_T-299.xml")
).open()
simulation_steps = get_scenario_length_in_time_steps(scenario)
if warmup_required:
    warmup_time_steps = int(warm_up_estimator(scenario.lanelet_network) * scenario.dt)
    simulation_steps += warmup_time_steps
else:
    warmup_time_steps = 0

sim = NonInteractiveSumoSimulation.from_scenario(
    scenario, traffic_generation_mode=traffic_generation_mode
)

shutil.copyfile(
    Path(__file__)
    .parents[1]
    .joinpath("resources/paper/sumo/mona_merge/C-DEU_MONAMerge-2_1_T-299.net.xml"),
    str(Path(sim.scenario_wrapper.runtime_directory.name) / "C-DEU_MONAMerge-2_1_T-299.net.xml"),
)

result = sim.run(simulation_steps=simulation_steps)
cropped_scenario = crop_scenario_to_time_frame(result.scenario, min_time_step=warmup_time_steps)
align_scenario_to_time_step(cropped_scenario, warmup_time_steps)

metrics_general = compute_general_scenario_metric(cropped_scenario, is_orig=False)
print(metrics_general)
if not warmup_required:
    metrics_waymo = compute_waymo_metric(cropped_scenario, scenario)
    print(metrics_waymo)
