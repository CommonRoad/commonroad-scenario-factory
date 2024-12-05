from typing import Dict, Iterator, Sequence, Set, Tuple

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad_crime.data_structure.base import CriMeBase, CriMeConfiguration
from commonroad_crime.data_structure.crime_interface import CriMeInterface
from commonroad_labeling.criticality.trajectory_inserter.trajectory_inserter import (
    TrajectoryInserter,
)

from scenario_factory.utils import is_state_with_discrete_time_step


class CriticalityMetrics:
    """
    Collection of multiple computed criticality metrics for a scenario.

    This is used to simplify the access and processing of measurments, over the simple dict that is returned by `CriMeInterface`.

    :param criticality_dict: The measurments for each metric. Usually directly exported from the `CriMeInterface`.
    """

    def __init__(self, criticality_dict: Dict[int, Dict[str, float]]) -> None:
        self._criticality_dict = criticality_dict

    def get_metric_names(self) -> Set[str]:
        """
        Obtain the names of all criticality metrics that were computed.
        """
        metric_names: Set[str] = set()
        for measurment in self._criticality_dict.values():
            metric_names.update(measurment.keys())

        return metric_names

    def measurments_per_time_step(self) -> Iterator[Tuple[int, Dict[str, float]]]:
        """
        Iterate over the measurments at each time step.
        """
        # Currently, this simply wraps the iterator over the dict. The idea here is,
        # to provide an existing API, while the underlying data structure might change.
        for time_step, measurment in self._criticality_dict.items():
            yield time_step, measurment


def compute_criticality_metrics_for_scenario_with_ego_trajectory(
    scenario_with_ego_trajectory: Scenario, ego_id: int, metrics: Sequence[type[CriMeBase]]
) -> CriticalityMetrics:
    """ """
    ego_obstacle = scenario_with_ego_trajectory.obstacle_by_id(ego_id)
    if ego_obstacle is None:
        raise ValueError(
            f"Cannot compute CriMe metrics for scenario {scenario_with_ego_trajectory.scenario_id}: The selected ego vehicle '{ego_id}' was not found in the scenario!"
        )

    if not isinstance(ego_obstacle, DynamicObstacle):
        raise ValueError(
            f"Cannot compute CriMe metrics for scenario {scenario_with_ego_trajectory.scenario_id}: The selected ego vehicle '{ego_id}' is not a dynamic obstacle, but a {type(ego_obstacle)}!"
        )

    if not is_state_with_discrete_time_step(ego_obstacle.initial_state):
        raise ValueError(
            f"Cannot compute CriMe metrics for scenario {scenario_with_ego_trajectory.scenario_id}: Initial state for ego vehicle '{ego_id}' is not a discrete time step!"
        )
    time_step_start = ego_obstacle.initial_state.time_step

    if ego_obstacle.prediction is None:
        raise ValueError(
            f"Cannot compute CriMe metrics for scenario {scenario_with_ego_trajectory.scenario_id}: The selected ego vehicle '{ego_id}', does not have a prediction, but one is required!"
        )
    time_step_stop = ego_obstacle.prediction.final_time_step
    if not isinstance(time_step_stop, int):
        raise ValueError(
            f"Cannot compute CriMe metrics for scenario {scenario_with_ego_trajectory.scenario_id}: Final state in ego vehicle '{ego_id}' prediction is not a discrete time step, but instead {type(time_step_stop)}."
        )

    cri_me_config = _get_cri_me_config_for_scenario(scenario_with_ego_trajectory, ego_id)
    cri_me_interface = CriMeInterface(cri_me_config)
    cri_me_interface.evaluate_scenario(
        measures=list(metrics),
        time_start=time_step_start,
        time_end=time_step_stop,
        vehicle_id=ego_id,
        verbose=False,
    )

    return CriticalityMetrics(cri_me_interface.criticality_dict)


def compute_criticality_metrics_for_scenario_and_planning_problem_set(
    scenario: Scenario,
    planning_problem_set: PlanningProblemSet,
    metrics: Sequence[type[CriMeBase]],
) -> CriticalityMetrics:
    """
    Computes criticality metrics for a given scenario using specified CriMe metrics.

    This function computes criticality metrics by integrating an ego vehicle trajectory into the given scenario,
    executing specified CriMe metrics, and returning the criticality data. It expects a single output metric file,
    ensuring unique results for the scenario.

    :param scenario: The scenario for which criticality metrics are to be computed.
    :param planning_problem_set: The set of planning problems associated with the scenario.
    :param runtime_directory_path: Directory path where runtime files will be stored.
    :param metrics: A list of CriMe metric classes to compute criticality metrics for the scenario.

    :raises RuntimeError: If multiple or no criticality metric files are found in the output directory, or if criticality metrics computation fails.

    :return: The criticality data computed for the scenario.
    """
    trajectory_inserter = TrajectoryInserter()
    scenario_with_ego_trajectory, ego_id = trajectory_inserter.insert_ego_trajectory(
        scenario, planning_problem_set
    )

    return compute_criticality_metrics_for_scenario_with_ego_trajectory(
        scenario_with_ego_trajectory, ego_id, metrics
    )


def _get_cri_me_config_for_scenario(scenario: Scenario, ego_vehicle_id: int) -> CriMeConfiguration:
    """
    Create a configuration for use with the `CriMeInterface`.
    """
    config = CriMeConfiguration()
    config.update(ego_vehicle_id, scenario)

    return config
