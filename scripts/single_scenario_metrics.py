import csv
from pathlib import Path
from typing import Iterable

from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps.single_scenario_metrics import (
    ComputeSingleScenarioMetricsArguments,
    pipeline_compute_single_scenario_metrics,
)
from scenario_factory.scenario_types import (
    ScenarioWithSingleScenarioMetrics,
    load_scenarios_from_folder,
)

pipeline = Pipeline()
pipeline.map(pipeline_compute_single_scenario_metrics(ComputeSingleScenarioMetricsArguments()))

scenario_containers = load_scenarios_from_folder(
    Path("/home/florian/git/temp/cr-ots-interface/resources/simulations/"),
)

result = pipeline.execute(scenario_containers)


def dump_single_scenario_metrics(
    scenario_containers: Iterable[ScenarioWithSingleScenarioMetrics], csv_file_path: Path
) -> None:
    formatted_data = []
    for scenario_container in scenario_containers:
        single_scenario_metrics = scenario_container.single_scenario_metrics
        formatted_data.append(
            {
                "scenario_id": str(scenario_container.scenario.scenario_id),
                "f [1/s]": single_scenario_metrics.frequency,
                "v mean [m/s]": single_scenario_metrics.velocity_mean,
                "v stdev [m/s]": single_scenario_metrics.velocity_stdev,
                "rho mean [1/m]": single_scenario_metrics.traffic_density_mean,
                "rho stdev [1/m]": single_scenario_metrics.traffic_density_stdev,
            }
        )

    with open(csv_file_path, "w") as csv_file:
        csv_writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "scenario_id",
                "f [1/s]",
                "v mean [m/s]",
                "v stdev [m/s]",
                "rho mean [1/m]",
                "rho stdev [1/m]",
            ],
        )
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)


dump_single_scenario_metrics(result.values, Path("/tmp/single_scenario_metrics.csv"))
