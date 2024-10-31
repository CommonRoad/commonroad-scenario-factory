from pathlib import Path
from typing import Sequence

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from commonroad_crime.data_structure.base import CriMeBase
from commonroad_labeling.criticality.computer.cm_computer import CMComputer
from commonroad_labeling.criticality.input_output.crime_output import (
    ScenarioCriticalityData,
    parse_crime_output_dir_to_object,
)
from commonroad_labeling.criticality.trajectory_inserter.trajectory_inserter import (
    TrajectoryInserter,
)


def compute_crime_criticality_metrics(
    scenario: Scenario,
    planning_problem_set: PlanningProblemSet,
    runtime_directory_path: Path,
    metrics: Sequence[type[CriMeBase]],
) -> ScenarioCriticalityData:
    trajectory_inserter = TrajectoryInserter()
    scenario_with_ego_trajectory, ego_id = trajectory_inserter.insert_ego_trajectory(
        scenario, planning_problem_set
    )

    runtime_directory = str(runtime_directory_path.absolute())
    cm_computer = CMComputer(metrics=metrics)  # type: ignore
    cm_computer.compute_metrics_for_id(scenario_with_ego_trajectory, ego_id, "", runtime_directory)

    crime_metrics = parse_crime_output_dir_to_object(runtime_directory)
    if len(crime_metrics) > 1:
        raise RuntimeError(
            f"Found {len(crime_metrics)} CriMe metric files for scenario {scenario}, but only one can be processed. This means there is a duplicated scenario ID."
        )

    if len(crime_metrics) < 1:
        raise RuntimeError(
            f"Failed to compute criticality metric fro scenario {scenario.scenario_id}: CriMe did not produce a criticality metric file!"
        )

    crime_metric_data_of_scenario = crime_metrics[0]
    return crime_metric_data_of_scenario
