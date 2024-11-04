import csv
from pathlib import Path
from typing import Iterable

from commonroad_labeling.criticality.input_output.crime_output import ScenarioCriticalityData

from scenario_factory.scenario_container import (
    ScenarioContainer,
)


def write_criticality_metrics_to_csv(
    scenario_containers: Iterable[ScenarioContainer], csv_file_path: Path
) -> None:
    """
    Write the cricticality data that is attached to the scenario_containers as CSV to `csv_file_path`.

    :param scenario_containers: Scenario containers with criticality data attached
    :param csv_file_path: Path to the file to which the data should be written. The file will be created if it does not exist, otherwise it will be overwritten.

    :returns: Nothing
    """
    assert all(
        scenario_container.has_attachment(ScenarioCriticalityData)
        for scenario_container in scenario_containers
    )
    formatted_data = []
    all_measurments = set()
    for scenario_container in scenario_containers:
        criticality_data = scenario_container.get_attachment(ScenarioCriticalityData)
        # The existence of criticality data on each scenario container was already verified with the assert at the function start
        assert criticality_data is not None

        all_measurments.update(criticality_data.measure_list)

        for time_step, measurment in criticality_data.data.items():
            row = {
                "scenarioId": str(scenario_container.scenario.scenario_id),
                "timeStep": time_step,
            }
            metrics = {}
            for metric, value in measurment.items():
                metrics[metric] = value
            row.update(metrics)
            formatted_data.append(row)

    measurment_fields = sorted(list(all_measurments))
    fieldnames = ["scenarioId", "timeStep"] + measurment_fields
    with csv_file_path.open(mode="w") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)
