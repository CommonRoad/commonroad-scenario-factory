import csv
from pathlib import Path
from typing import Iterable

from commonroad_labeling.criticality.input_output.crime_output import ScenarioCriticalityData

from scenario_factory.metrics.general_scenario_metric import GeneralScenarioMetric
from scenario_factory.metrics.waymo_metric import WaymoMetric
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


def write_general_scenario_metrics_to_csv(
    scenario_containers: Iterable[ScenarioContainer], csv_file_path: Path
) -> None:
    assert all(
        scenario_container.has_attachment(GeneralScenarioMetric)
        for scenario_container in scenario_containers
    )
    formatted_data = []

    for scenario_container in scenario_containers:
        general_scenario_metric = scenario_container.get_attachment(GeneralScenarioMetric)
        formatted_data.append(
            {
                "scenario_id": str(scenario_container.scenario.scenario_id),
                "f [1/s]": general_scenario_metric.frequency,  # type: ignore
                "v mean [m/s]": general_scenario_metric.velocity_mean,  # type: ignore
                "v stdev [m/s]": general_scenario_metric.velocity_stdev,  # type: ignore
                "rho mean [1/km]": general_scenario_metric.traffic_density_mean,  # type: ignore
                "rho stdev [1/km]": general_scenario_metric.traffic_density_stdev,  # type: ignore
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
                "rho mean [1/km]",
                "rho stdev [1/km]",
            ],
        )
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)


def write_waymo_metrics_to_csv(
    scenario_containers: Iterable[ScenarioContainer], csv_file_path: Path
) -> None:
    assert all(
        scenario_container.has_attachment(WaymoMetric) for scenario_container in scenario_containers
    )

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
