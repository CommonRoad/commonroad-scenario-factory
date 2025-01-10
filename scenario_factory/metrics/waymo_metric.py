import csv
import logging
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import State, TraceState

from scenario_factory.metrics.base import BaseMetric, combine_metrics
from scenario_factory.utils import (
    get_dynamic_obstacle_ids_in_scenario,
    is_state_with_position,
    iterate_zipped_dynamic_obstacles_from_scenarios,
)

_LOGGER = logging.getLogger(__name__)

_DEFAULT_WAYMO_METRIC_PRECISION = 3


@dataclass
class WaymoMetric(BaseMetric):
    """
    Data class for the Waymo metrics.
    """

    ade3: float
    ade5: float
    ade8: float
    fde3: float
    fde5: float
    fde8: float
    mr3: float
    mr5: float
    mr8: float
    rmse_mean: float
    rmse_stdev: float

    def __str__(self) -> str:
        return "Waymo Metrics: " + ", ".join(
            [
                f"{field.name}: {getattr(self, field.name):.4f}"
                for field in fields(self)
                if field.name != "scenario_id"
            ]
        )


def write_waymo_metrics_to_csv(
    waymo_metric_collection: Sequence[WaymoMetric], csv_file_path: Path
) -> None:
    """
    Write `waymo_metric_collection` in CSV format to `csv_file_path`. Metrics for the same scenario id will be combined automatically.

    :param: Collection of `WaymoMetric`. May contain multiple metrics for the same scenario ID.
    :param csv_file_path: File path, where CSV data will be written to.

    :returns: Nothing.
    """
    formatted_data = []
    for waymo_metric in combine_metrics(waymo_metric_collection):
        formatted_data.append(
            {
                "scenario_id": str(waymo_metric.scenario_id),
                "ade3": round(waymo_metric.ade3, _DEFAULT_WAYMO_METRIC_PRECISION),
                "ade5": round(waymo_metric.ade5, _DEFAULT_WAYMO_METRIC_PRECISION),
                "ade8": round(waymo_metric.ade8, _DEFAULT_WAYMO_METRIC_PRECISION),
                "fde3": round(waymo_metric.fde3, _DEFAULT_WAYMO_METRIC_PRECISION),
                "fde5": round(waymo_metric.fde5, _DEFAULT_WAYMO_METRIC_PRECISION),
                "fde8": round(waymo_metric.fde8, _DEFAULT_WAYMO_METRIC_PRECISION),
                "mr3": round(waymo_metric.mr3, _DEFAULT_WAYMO_METRIC_PRECISION),
                "mr5": round(waymo_metric.mr5, _DEFAULT_WAYMO_METRIC_PRECISION),
                "mr8": round(waymo_metric.mr8, _DEFAULT_WAYMO_METRIC_PRECISION),
                "rmse_mean": round(waymo_metric.rmse_mean, _DEFAULT_WAYMO_METRIC_PRECISION),
                "rmse_stdev": round(waymo_metric.rmse_stdev, _DEFAULT_WAYMO_METRIC_PRECISION),
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


def compute_waymo_metric(scenario: Scenario, reference_scenario: Scenario) -> WaymoMetric:
    """
    Compute the Waymo metrics for the scenario.

    :param scenario: The scenario for which the metrics should be computed.
    :param reference_scenario: The reference scenario for the computation.
    """
    assert scenario.dt == reference_scenario.dt

    # To compute waymo metrics, there needs to be at least some overlap between the obstacles in the scenarios.
    # Espacially, it is important that the reference scenario contains all obstacles that are also in the scenario.
    # The other way around is not so important, because it is possible that due to some cutting
    # after simulation some obstacles are missing from the scenario.
    dynamic_obstacle_ids_in_reference = set(
        get_dynamic_obstacle_ids_in_scenario(reference_scenario)
    )
    dynamic_obstacle_ids_in_scenario = set(get_dynamic_obstacle_ids_in_scenario(scenario))
    if not dynamic_obstacle_ids_in_scenario.issubset(dynamic_obstacle_ids_in_reference):
        raise RuntimeError(
            f"Cannot compute waymo metrics for scenario {scenario.scenario_id}: with reference scenario {reference_scenario.scenario_id}: The obstacles {dynamic_obstacle_ids_in_scenario.difference(dynamic_obstacle_ids_in_reference)} are in the scenario, but not in the reference scenario! This is usually the case, if you tried to compute wyamo metrics for a scenario after simulation but the simulation mode does not preserve obstacle IDs."
        )
    measurment_times = [3, 5, 8]

    average_displacement_errors: Dict[int, List[float]] = defaultdict(list)
    final_displacement_errors: Dict[int, List[float]] = defaultdict(list)
    miss_rates: Dict[int, List[float]] = defaultdict(list)
    root_mean_squared_errors: List[float] = []

    for dynamic_obstacle_ref, dynamic_obstacle in iterate_zipped_dynamic_obstacles_from_scenarios(
        reference_scenario, scenario
    ):
        displacement_vector = compute_displacment_vector_between_two_dynamic_obstacles(
            dynamic_obstacle, dynamic_obstacle_ref
        )
        # The displacement vector is none, if the
        if displacement_vector is None:
            continue

        reference_start_state = dynamic_obstacle_ref.state_at_time(
            dynamic_obstacle_ref.prediction.initial_time_step
        )
        if reference_start_state is None:
            raise RuntimeError(
                f"Cannot compute waymo metric for scenario {scenario.scenario_id}: The reference obstacle for obstacle {dynamic_obstacle.obstacle_id} does not contain a state at the beginning of its prediction! This is a bug."
            )

        root_mean_squared_errors.append(_compute_root_mean_squared_error(displacement_vector))
        for measurment_time_in_sec in measurment_times:
            measurment_time_step = int(measurment_time_in_sec / scenario.dt)
            average_displacement_errors[measurment_time_in_sec].append(
                _compute_waymo_average_displacement_error_until_time_step(
                    displacement_vector, measurment_time_step
                )
            )

            final_displacement_errors[measurment_time_in_sec].append(
                _compute_waymo_minimum_final_displacement_error_at_time_step(
                    displacement_vector, measurment_time_step
                )
            )

            miss_rate_thresholds = _get_waymo_miss_rate_thresholds_for_state_and_time(
                measurment_time_in_sec, reference_start_state
            )
            miss_rates[measurment_time_in_sec].append(
                _compute_waymo_miss_rate_until_time_step(
                    dynamic_obstacle,
                    dynamic_obstacle_ref,
                    miss_rate_thresholds,
                    measurment_time_step,
                )
            )

    # The repective metrics might contain 'nan' values, when they could not be computed.
    # This usually happens, when a metric is calculated for a time step that is after the end of the prediction.
    # Therefore, they first need to be filtered.
    filtered_average_displacmenet_errors = _filter_and_combine_waymo_metrics(
        average_displacement_errors
    )
    filtered_final_displacement_errors = _filter_and_combine_waymo_metrics(
        final_displacement_errors
    )
    filtered_miss_rates = _filter_and_combine_waymo_metrics(miss_rates)
    filtered_root_mean_squared_errors = list(
        filter(lambda value: not math.isnan(value), root_mean_squared_errors)
    )

    return WaymoMetric(
        scenario_id=scenario.scenario_id,
        ade3=filtered_average_displacmenet_errors[3],
        ade5=filtered_average_displacmenet_errors[5],
        ade8=filtered_average_displacmenet_errors[8],
        fde3=filtered_final_displacement_errors[3],
        fde5=filtered_final_displacement_errors[5],
        fde8=filtered_final_displacement_errors[8],
        mr3=filtered_miss_rates[3],
        mr5=filtered_miss_rates[5],
        mr8=filtered_miss_rates[8],
        rmse_mean=statistics.mean(filtered_root_mean_squared_errors),
        rmse_stdev=statistics.stdev(filtered_root_mean_squared_errors),
    )


def _filter_and_combine_waymo_metrics(metrics: Dict[int, List[float]]) -> Dict[int, float]:
    """
    Remove all 'nan' values from the metric lists and compute the mean of the filtered values.

    :param metrics: The individual metric values indexed by their measurment time.
    :returns: The mean metric values, indexed by their measurment time.
    """
    filtered_metrics = {}
    for measurment_time, values in metrics.items():
        filtered_values = list(filter(lambda value: not math.isnan(value), values))
        if len(filtered_values) == 0:
            filtered_metrics[measurment_time] = float("nan")
        else:
            filtered_metrics[measurment_time] = statistics.mean(filtered_values)

    return filtered_metrics


def compute_displacment_vector_between_two_dynamic_obstacles(
    dynamic_obstacle: DynamicObstacle, dynamic_obstacle_reference: DynamicObstacle
) -> Optional[np.ndarray]:
    """
    Compute the displacement of `dynamic_obstacle` compared to `dynamic_obstacle_reference`.

    :param dynamic_obstacle: The obstacle for which the error should be calculated.
    :param dynamic_obstacle_reference: The obstacle which represents the "ground truth".
    :returns: The array of displacement errors, or None if tone of the dynamic obstacles does not have a trajectory prediction.

    :raises: RuntimeError: If the displacement cannot be calculated, because the states
        of the dynamic obstacles lack required attributes (e.g. position).
    """
    if not isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        return None

    if not isinstance(dynamic_obstacle_reference.prediction, TrajectoryPrediction):
        return None

    time_step_offset = (
        dynamic_obstacle.prediction.initial_time_step
        - dynamic_obstacle_reference.prediction.initial_time_step
    )
    if time_step_offset < 0:
        _LOGGER.warning(
            "time step offset between %s and %s is %s, but must not be smaller then 0",
            dynamic_obstacle.obstacle_id,
            dynamic_obstacle_reference.obstacle_id,
            time_step_offset,
        )
        return None

    displacement_errors = []
    for time_step in range(
        dynamic_obstacle.prediction.initial_time_step,
        dynamic_obstacle.prediction.final_time_step,
    ):
        state = dynamic_obstacle.state_at_time(time_step)

        if not is_state_with_position(state):
            raise RuntimeError()

        reference_state = dynamic_obstacle_reference.state_at_time(time_step + time_step_offset)
        if reference_state is None:
            # Because we iterate over the prediction length of `dynamic_obstacle` it is possible that `dynamic_obstacle_reference` has no state at the time step.
            # This is valid, because the trajectories of the obstacles might diverge.
            continue

        if not is_state_with_position(reference_state):
            raise RuntimeError()

        displacement_error = np.linalg.norm(state.position - reference_state.position)
        displacement_errors.append(displacement_error)

    if len(displacement_errors) < 1:
        return None

    return np.array(displacement_errors)


def _compute_waymo_average_displacement_error_until_time_step(
    displacement_vector: np.ndarray, time_step: int
) -> float:
    if len(displacement_vector) <= time_step:
        return float("nan")
    return float(np.mean(displacement_vector[: time_step + 1]))


def _compute_waymo_minimum_final_displacement_error_at_time_step(
    displacement_vector: np.ndarray, time_step: int
) -> float:
    if len(displacement_vector) <= time_step:
        return float("nan")
    return float(displacement_vector[time_step])


def _compute_root_mean_squared_error(displacement_vector: np.ndarray) -> float:
    if len(displacement_vector) < 1:
        return float("nan")
    return np.sqrt(1 / len(displacement_vector) * np.sum(np.power(displacement_vector, 2)))


def _scale_velocity_for_miss_rate_threshold(velocity: float) -> float:
    if velocity < 1.4:
        return 0.5
    elif velocity < 11:
        return 0.5 + 0.5 * (velocity - 1.4) / (11 - 1.4)
    else:
        return 1


_MISS_RATE_BASE_THRESHOLDS = {3: (2, 1), 5: (3.6, 1.8), 8: (6, 3)}


def _get_waymo_miss_rate_thresholds_for_state_and_time(
    time_in_sec: int, state: TraceState
) -> Tuple[float, float]:
    base_thresholds = _MISS_RATE_BASE_THRESHOLDS.get(time_in_sec)
    if base_thresholds is None:
        raise ValueError()

    scaled_velocity = _scale_velocity_for_miss_rate_threshold(state.velocity)
    return (base_thresholds[0] * scaled_velocity, base_thresholds[1] * scaled_velocity)


def _compute_waymo_miss_rate_until_time_step(
    dynamic_obstacle: DynamicObstacle,
    dynamic_obstacle_reference: DynamicObstacle,
    thresholds: Tuple[float, float],
    time_step: int,
) -> float:
    """
    Compute the percentage of states from the trajectory of `dynamic_obstacle` that do not match the trajectory of `dynamic_obstacle_reference` by a certain threshold.


    :param dynamic_obstacle:
    :param dynamic_obstacle_reference:
    :param thresholds: A tuple of (lat, lon) thresholds.
    :param time_step: The time step until which the miss rate should be calculated.
    """
    if not isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        return float("nan")

    if not isinstance(dynamic_obstacle_reference.prediction, TrajectoryPrediction):
        return float("nan")

    min_prediction_length = min(
        dynamic_obstacle.prediction.final_time_step,
        dynamic_obstacle_reference.prediction.final_time_step,
    )
    if min_prediction_length < time_step:
        return float("nan")

    misses = 0
    for time_step in range(
        dynamic_obstacle.prediction.initial_time_step, dynamic_obstacle.prediction.final_time_step
    ):
        state = dynamic_obstacle.state_at_time(time_step)
        if state is None:
            raise RuntimeError()
        reference_state = dynamic_obstacle_reference.state_at_time(time_step)
        if reference_state is None:
            continue
        if _is_state_miss(state, reference_state, thresholds[0], thresholds[1]):
            misses += 1

    return misses / time_step


def _is_state_miss(
    state: State, state_ref: State, threshold_lon_scaled: float, threshold_lat_scaled: float
) -> bool:
    """
    Check if the state is a miss.
    """
    orientation_ref = state_ref.orientation
    cartesian_vector = state.position - state_ref.position
    dist_lon = cartesian_vector[0] * np.cos(orientation_ref) + cartesian_vector[1] * np.sin(
        orientation_ref
    )
    dist_lat = -cartesian_vector[0] * np.sin(orientation_ref) + cartesian_vector[1] * np.cos(
        orientation_ref
    )

    return abs(dist_lon) > threshold_lon_scaled or abs(dist_lat) > threshold_lat_scaled
