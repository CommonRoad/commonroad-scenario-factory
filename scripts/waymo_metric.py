from pathlib import Path

from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import (
    pipeline_compute_waymo_metrics,
)
from scenario_factory.scenario_container import (
    load_scenarios_with_reference_from_folders,
    write_waymo_metrics_of_scenario_containers_to_csv,
)

pipeline = Pipeline()
pipeline.map(pipeline_compute_waymo_metrics)

scenario_containers = load_scenarios_with_reference_from_folders(
    Path("../cr-ots-interface/resources/simulations/"),
    Path("../cr-ots-interface/resources/abstraction/"),
)
print(scenario_containers)
result = pipeline.execute(scenario_containers)

write_waymo_metrics_of_scenario_containers_to_csv(result.values, Path("/tmp/waymo_metrics.csv"))
