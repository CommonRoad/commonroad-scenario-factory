from pathlib import Path

from scenario_factory.metrics.output import write_general_scenario_metrics_to_csv
from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import pipeline_remove_parked_dynamic_obstacles
from scenario_factory.pipeline_steps.general_scenario_metric import (
    ComputeGeneralScenarioMetricsArguments,
    pipeline_compute_general_scenario_metrics,
)
from scenario_factory.scenario_container import load_scenarios_from_folder

pipeline = Pipeline()
pipeline.map(pipeline_remove_parked_dynamic_obstacles).map(
    pipeline_compute_general_scenario_metrics(ComputeGeneralScenarioMetricsArguments(is_orig=True))
)

scenario_containers = load_scenarios_from_folder(
    Path(__file__).parents[1].joinpath("resources/paper/"),
)

result = pipeline.execute(scenario_containers)

write_general_scenario_metrics_to_csv(result.values, Path("/tmp/general_scenario_metrics.csv"))
