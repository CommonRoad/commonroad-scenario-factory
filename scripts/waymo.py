import csv
from pathlib import Path
from typing import Iterable

from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import pipeline_simulate_scenario_with_ots, SimulateScenarioArguments
from scenario_factory.pipeline_steps.waymo_metrics import (
    ComputeWaymoMetricsArguments,
    pipeline_compute_waymo_metrics,
)
from scenario_factory.scenario_types import ScenarioWithWaymoMetrics, load_scenarios_from_folder
from scenario_factory.simulation import SimulationConfig, SimulationMode

pipeline = Pipeline()
pipeline.map(pipeline_simulate_scenario_with_ots(SimulateScenarioArguments(SimulationConfig(SimulationMode.RESIMULATION))))
pipeline.map(pipeline_compute_waymo_metrics(ComputeWaymoMetricsArguments()))


scenario_containers = load_scenarios_from_folder("/tmp/input_scenarios")
result = pipeline.execute(scenario_containers)


def dump_waymo_metrics(
    scenario_containers: Iterable[ScenarioWithWaymoMetrics], csv_file_path: Path
) -> None:
    formatted_data = []
    for scenario_container in scenario_containers:
        waymo_metrics = scenario_container.waymo_metrics
        formatted_data.append(
            {
                "scenario_id": str(scenario_container.scenario.scenario_id),
                "ADE3": waymo_metrics.ADE3,
                "ADE5": waymo_metrics.ADE5,
                "ADE8": waymo_metrics.ADE8,
                "FDE3": waymo_metrics.FDE3,
                "FDE5": waymo_metrics.FDE5,
                "FDE8": waymo_metrics.FDE8,
                "MR3": waymo_metrics.MR3,
                "MR5": waymo_metrics.MR5,
                "MR8": waymo_metrics.MR8,
            }
        )

    with open(csv_file_path, "w") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=["scenario_id", "ADE3", "ADE5", "ADE8", "FDE3", "FDE5", "FDE8", "MR3", "MR5", "MR8"])
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)


dump_waymo_metrics(result.values, Path("/tmp/waymo_metrics.csv"))
