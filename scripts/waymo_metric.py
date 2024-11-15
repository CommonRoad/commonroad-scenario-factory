from pathlib import Path

from scenario_factory.metrics.output import write_waymo_metrics_to_csv
from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps.waymo_metric import (
    ComputeWaymoMetricsArguments,
    pipeline_compute_waymo_metrics,
)
from scenario_factory.scenario_container import (
    load_scenarios_with_reference_from_folders,
)

pipeline = Pipeline()
pipeline.map(pipeline_compute_waymo_metrics(ComputeWaymoMetricsArguments()))

scenario_containers = load_scenarios_with_reference_from_folders(
    Path("/home/florian/git/temp/cr-ots-interface/resources/simulations/"),
    Path("/home/florian/git/temp/cr-ots-interface/resources/abstraction/"),
)
result = pipeline.execute(scenario_containers)

write_waymo_metrics_to_csv(result.values, Path("/tmp/waymo_metrics.csv"))
