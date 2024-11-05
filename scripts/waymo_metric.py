import csv
from pathlib import Path
from typing import Iterable

from scenario_factory.metrics.waymo_metric import WaymoMetric
from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps.waymo_metric import (
    ComputeWaymoMetricsArguments,
    pipeline_compute_waymo_metric,
)
from scenario_factory.scenario_container import (
    ScenarioContainer,
    load_scenarios_with_reference_from_folders,
)

pipeline = Pipeline()
pipeline.map(pipeline_compute_waymo_metric(ComputeWaymoMetricsArguments()))

scenario_containers = load_scenarios_with_reference_from_folders(
    Path("/home/florian/git/temp/cr-ots-interface/resources/simulations/"),
    Path("/home/florian/git/temp/cr-ots-interface/resources/abstraction/"),
)
result = pipeline.execute(scenario_containers)


def dump_waymo_metrics(
    scenario_containers: Iterable[ScenarioContainer], csv_file_path: Path
) -> None:
    formatted_data = []
    for scenario_container in scenario_containers:
        waymo_metrics = scenario_container.get_attachment(WaymoMetric)
        formatted_data.append(
            {
                "scenario_id": str(scenario_container.scenario.scenario_id),
                "ade3": waymo_metrics.ade3,  # type: ignore
                "ade5": waymo_metrics.ade5,  # type: ignore
                "ade8": waymo_metrics.ade8,  # type: ignore
                "fde3": waymo_metrics.fde3,  # type: ignore
                "fde5": waymo_metrics.fde5,  # type: ignore
                "fde8": waymo_metrics.fde8,  # type: ignore
                "mr3": waymo_metrics.mr3,  # type: ignore
                "mr5": waymo_metrics.mr5,  # type: ignore
                "mr8": waymo_metrics.mr8,  # type: ignore
                "rmse_mean": waymo_metrics.rmse_mean,  # type: ignore
                "rmse_stdev": waymo_metrics.rmse_stdev,  # type: ignore
            }
        )

    with open(csv_file_path, "w") as csv_file:
        csv_writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "scenario_id",
                "ade3",
                "ade5",
                "ade8",
                "fde3",
                "fde5",
                "fde8",
                "mr3",
                "mr5",
                "mr8",
                "rmse_mean",
                "rmse_stdev",
            ],
        )
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)


dump_waymo_metrics(result.values, Path("/tmp/waymo_metrics.csv"))
