import csv
from pathlib import Path
from typing import Iterable

from scenario_factory.pipeline.pipeline import Pipeline
from scenario_factory.pipeline_steps.utils import (
    ComputeCriticalityMetricsArgs,
    pipeline_compute_criticality_metrics,
)
from scenario_factory.scenario_types import ScenarioWithCriticalityData, load_scenarios_from_folder

crime_output_folder = Path("/tmp/crime")
crime_output_folder.mkdir(exist_ok=True)


def dump_criticality_metrics(
    scenario_containers: Iterable[ScenarioWithCriticalityData], csv_file_path: Path
) -> None:
    formatted_data = []
    for scenario_container in scenario_containers:
        for time_step, measurment in scenario_container.criticality_data.data.items():
            for metric, value in measurment.items():
                formatted_data.append(
                    {
                        "scenarioId": str(scenario_container.scenario.scenario_id),
                        "timeStep": time_step,
                        metric: value,
                    }
                )

    all_measurments = {
        key
        for scenario_container in scenario_containers
        for measurment in scenario_container.criticality_data.data.values()
        for key in measurment.keys()
    }
    fieldnames = ["scenarioId", "timeStep"] + list(all_measurments)
    with csv_file_path.open(mode="w") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)


pipeline = Pipeline()
pipeline.map(pipeline_compute_criticality_metrics(ComputeCriticalityMetricsArgs()))

scenario_containers = load_scenarios_from_folder("/tmp/input_scenarios")
result = pipeline.execute(scenario_containers)
dump_criticality_metrics(result.values, Path("/tmp/crime.csv"))
