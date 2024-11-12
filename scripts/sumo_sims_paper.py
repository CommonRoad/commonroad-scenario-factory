from pathlib import Path

from scenario_factory.metrics.output import (
    write_general_scenario_metrics_to_csv,
    write_waymo_metrics_to_csv,
)
from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import (
    SimulateScenarioArguments,
    WriteScenarioToFileArguments,
    pipeline_simulate_scenario_with_sumo,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipeline_steps.general_scenario_metric import (
    ComputeGeneralScenarioMetricsArguments,
    pipeline_compute_general_scenario_metrics,
)
from scenario_factory.pipeline_steps.utils import pipeline_remove_parked_dynamic_obstacles
from scenario_factory.pipeline_steps.waymo_metric import (
    ComputeWaymoMetricsArguments,
    pipeline_compute_waymo_metrics,
)
from scenario_factory.scenario_container import load_scenarios_from_folder
from scenario_factory.simulation import SimulationConfig, SimulationMode

path = Path("/tmp/sumo/")
path.mkdir(parents=True, exist_ok=True)

scenarios = load_scenarios_from_folder(Path(__file__).parents[1].joinpath("resources/paper/"))

simulation_config = SimulationConfig(SimulationMode.RANDOM_TRAFFIC_GENERATION, 300)
pipeline = (
    Pipeline()
    .map(pipeline_remove_parked_dynamic_obstacles)
    .map(pipeline_simulate_scenario_with_sumo(SimulateScenarioArguments(simulation_config)))
    .map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(path)))
    .map(pipeline_compute_general_scenario_metrics(ComputeGeneralScenarioMetricsArguments()))
    .map(pipeline_compute_waymo_metrics(ComputeWaymoMetricsArguments()))
)

results = pipeline.execute(scenarios)
write_general_scenario_metrics_to_csv(results.values, path.joinpath("general_scenario_metrics.csv"))
write_waymo_metrics_to_csv(results.values, path.joinpath("waymo_metrics.csv"))
