from pathlib import Path
from typing import List

from commonroad.common.file_reader import CommonRoadFileReader

from resources.paper.frame_factors import get_frame_factor_sim
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    pipeline_compute_single_scenario_metrics,
    pipeline_compute_waymo_metrics,
    pipeline_remove_parked_dynamic_obstacles,
    pipeline_simulate_scenario_with_ots,
    pipeline_simulate_scenario_with_sumo,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipeline_steps.utils import (
    pipeline_remove_pedestrians,
    pipeline_update_meta_information,
)
from scenario_factory.scenario_container import (
    ScenarioContainer,
    write_general_scenario_metrics_of_scenario_containers_to_csv,
    write_waymo_metrics_of_scenario_containers_to_csv,
)
from scenario_factory.simulation import SimulationConfig, SimulationMode

# Input values, change according to needs
simulation_tool_ots = True
simulation_mode = SimulationMode.DEMAND_TRAFFIC_GENERATION
simulation_steps = 300  # Only used for random traffic generation
start_seed = 1
num_simulations = 1
output_path = Path(f"/tmp/sims_paper_{'ots' if simulation_tool_ots else 'sumo'}_keep_warmup")

output_path.mkdir(parents=True, exist_ok=True)

scenario_names = [
    "DEU_MONAEast-2_2_T-300.xml"
]  # , "DEU_MONAMerge-2_2_T-300.xml", "DEU_MONAWest-2_2_T-300.xml"]
scenarios = []

for scenario_name in scenario_names:
    scenario, _ = CommonRoadFileReader(
        Path(__file__).parents[1].joinpath(f"resources/paper_accepted/{scenario_name}")
    ).open()
    scenarios += [ScenarioContainer(scenario)]

is_resimulation = simulation_mode in [SimulationMode.DELAY, SimulationMode.RESIMULATION]
frame_factor_callback = get_frame_factor_sim if is_resimulation else None


all_result_scenario_containers: List[ScenarioContainer] = []
for i in range(start_seed, start_seed + num_simulations):
    pipeline = (
        Pipeline().map(pipeline_remove_parked_dynamic_obstacles).map(pipeline_remove_pedestrians)
    )
    simulation_config = SimulationConfig(
        simulation_mode,
        simulation_steps if simulation_mode == SimulationMode.RANDOM_TRAFFIC_GENERATION else None,
        seed=i,
    )
    if simulation_tool_ots:
        pipeline.map(pipeline_simulate_scenario_with_ots(simulation_config))
    else:
        pipeline.map(pipeline_simulate_scenario_with_sumo(simulation_config))

    pipeline.map(pipeline_compute_single_scenario_metrics(frame_factor_callback))
    if is_resimulation:
        pipeline.map(pipeline_compute_waymo_metrics)

    pipeline.map(pipeline_update_meta_information(simulation_config, simulation_tool_ots))
    pipeline.map(pipeline_write_scenario_to_file(output_path))

    ctx = PipelineContext()
    results = pipeline.execute(scenarios, ctx)
    all_result_scenario_containers.extend(results.values)
    results.print_cum_time_per_step()

pred_id = (not simulation_tool_ots) * 5
match simulation_mode:
    case SimulationMode.RESIMULATION:
        pred_id += 1
    case SimulationMode.DELAY:
        pred_id += 2
    case SimulationMode.DEMAND_TRAFFIC_GENERATION:
        pred_id += 3
    case SimulationMode.INFRASTRUCTURE_TRAFFIC_GENERATION:
        pred_id += 4
    case SimulationMode.RANDOM_TRAFFIC_GENERATION:
        pred_id += 5
    case _:
        raise ValueError(f"Unknown simulation mode {simulation_mode}")

write_general_scenario_metrics_of_scenario_containers_to_csv(
    all_result_scenario_containers, output_path.joinpath(f"general_scenario_metrics_{pred_id}.csv")
)

if is_resimulation:
    write_waymo_metrics_of_scenario_containers_to_csv(
        all_result_scenario_containers, output_path.joinpath(f"waymo_metrics_{pred_id}.csv")
    )
