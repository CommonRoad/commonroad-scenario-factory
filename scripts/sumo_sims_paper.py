from pathlib import Path
from typing import List

from resources.paper.frame_factors import get_frame_factor_sim
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    pipeline_compute_single_scenario_metrics,
    pipeline_compute_waymo_metrics,
    pipeline_remove_parked_dynamic_obstacles,
    pipeline_simulate_scenario_with_sumo,
)
from scenario_factory.scenario_container import (
    ScenarioContainer,
    load_scenarios_from_folder,
    write_general_scenario_metrics_of_scenario_containers_to_csv,
    write_waymo_metrics_of_scenario_containers_to_csv,
)
from scenario_factory.simulation import SimulationConfig, SimulationMode

# Input values, change according to needs
simulation_mode = SimulationMode.DEMAND_TRAFFIC_GENERATION
simulation_steps = 300  # Only used for random traffic generation
start_seed = 576
num_simulations = 2
output_path = Path("/tmp/sumo/random")


output_path.mkdir(parents=True, exist_ok=True)

scenarios = load_scenarios_from_folder(Path(__file__).parents[1].joinpath("resources/paper/"))

is_resimulation = simulation_mode in [SimulationMode.DELAY, SimulationMode.RESIMULATION]
frame_factor_callback = get_frame_factor_sim if is_resimulation else None


all_result_scenario_containers: List[ScenarioContainer] = []
for i in range(start_seed, start_seed + num_simulations):
    pipeline = Pipeline().map(pipeline_remove_parked_dynamic_obstacles)
    simulation_config = SimulationConfig(
        simulation_mode,
        simulation_steps if simulation_mode == SimulationMode.RANDOM_TRAFFIC_GENERATION else None,
        seed=i,
    )
    pipeline.map(pipeline_simulate_scenario_with_sumo(simulation_config))

    pipeline.map(pipeline_compute_single_scenario_metrics(frame_factor_callback))
    if is_resimulation:
        pipeline.map(pipeline_compute_waymo_metrics)

    ctx = PipelineContext()
    results = pipeline.execute(scenarios, ctx)
    all_result_scenario_containers.extend(results.values)

write_general_scenario_metrics_of_scenario_containers_to_csv(
    all_result_scenario_containers, output_path.joinpath("general_scenario_metrics.csv")
)

if is_resimulation:
    write_waymo_metrics_of_scenario_containers_to_csv(
        all_result_scenario_containers, output_path.joinpath("waymo_metrics.csv")
    )
