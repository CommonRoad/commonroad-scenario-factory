from pathlib import Path

from resources.paper.frame_factors import get_frame_factor_sim
from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import (
    ComputeSingleScenarioMetricsArguments,
    SimulateScenarioArguments,
    WriteScenarioToFileArguments,
    pipeline_compute_single_scenario_metrics,
    pipeline_compute_waymo_metrics,
    pipeline_remove_parked_dynamic_obstacles,
    pipeline_simulate_scenario_with_sumo,
    pipeline_write_scenario_to_file,
)
from scenario_factory.scenario_container import (
    load_scenarios_from_folder,
    write_general_scenario_metrics_of_scenario_containers_to_csv,
    write_waymo_metrics_of_scenario_containers_to_csv,
)
from scenario_factory.simulation import SimulationConfig, SimulationMode

path = Path("/tmp/sumo/random")
path.mkdir(parents=True, exist_ok=True)

scenarios = load_scenarios_from_folder(Path(__file__).parents[1].joinpath("resources/paper/"))

simulation_config = SimulationConfig(SimulationMode.RANDOM_TRAFFIC_GENERATION, 300)  # 300
pipeline = (
    Pipeline()
    .map(pipeline_remove_parked_dynamic_obstacles)
    .map(pipeline_simulate_scenario_with_sumo(SimulateScenarioArguments(simulation_config)))
    .map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(path)))
    .map(
        pipeline_compute_single_scenario_metrics(
            ComputeSingleScenarioMetricsArguments(frame_factor_callback=get_frame_factor_sim)
        )
    )
    .map(pipeline_compute_waymo_metrics)
)

results = pipeline.execute(scenarios, debug=True)
write_general_scenario_metrics_of_scenario_containers_to_csv(
    results.values, path.joinpath("general_scenario_metrics.csv")
)
write_waymo_metrics_of_scenario_containers_to_csv(
    results.values, path.joinpath("waymo_metrics.csv")
)
