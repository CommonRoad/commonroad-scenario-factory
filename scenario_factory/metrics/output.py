import csv
from pathlib import Path
from typing import Iterable

from scenario_factory.scenario_types import ScenarioWithCriticalityData


def write_criticality_metrics_to_csv(
    scenario_containers: Iterable[ScenarioWithCriticalityData], csv_file_path: Path
) -> None:
    """
    Write the cricticality data that is attached to the scenario_containers as CSV to `csv_file_path`.

    :param scenario_containers: Scenario containers with criticality data attached
    :param csv_file_path: Path to the file to which the data should be written. The file will be created if it does not exist, otherwise it will be overwritten.

    :returns: Nothing
    """
    formatted_data = []
    for scenario_container in scenario_containers:
        for time_step, measurment in scenario_container.criticality_data.data.items():
            row = {
                "scenarioId": str(scenario_container.scenario.scenario_id),
                "timeStep": time_step,
            }
            metrics = {}
            for metric, value in measurment.items():
                metrics[metric] = value
            row.update(metrics)
            formatted_data.append(row)

    all_measurments = {
        measurment
        for scenario_container in scenario_containers
        for measurment in scenario_container.criticality_data.measure_list
    }
    measurment_fields = sorted(list(all_measurments))
    fieldnames = ["scenarioId", "timeStep"] + measurment_fields
    with csv_file_path.open(mode="w") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)
