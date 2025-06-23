from pathlib import Path

from scenario_factory.pipeline.pipeline import Pipeline
from scenario_factory.pipeline_steps import (
    pipeline_compute_criticality_metrics,
)
from scenario_factory.scenario_container import (
    load_scenarios_from_folder,
    write_criticality_metrics_of_scenario_containers_to_csv,
)

pipeline = Pipeline()
pipeline.map(pipeline_compute_criticality_metrics)

scenario_containers = load_scenarios_from_folder("/tmp/use_case")
result = pipeline.execute(scenario_containers)
write_criticality_metrics_of_scenario_containers_to_csv(result.values, Path("/tmp/crime.csv"))
