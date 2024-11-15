import logging
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, fields
from typing import Dict, List, Optional, Tuple

import numpy as np
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import State

from scenario_factory.utils._types import (
    WithDiscreteVelocity,
    is_state_with_position,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WaymoMetric:
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
            [f"{field.name}: {getattr(self, field.name):.4f}" for field in fields(self)]
        )


def _zipped_iter_dynamic_obstacles_in_scenarios(*scenarios: Scenario):
    if len(scenarios) < 2:
        raise ValueError("")
    base_scenario = scenarios[0]
    for dynamic_obstacle in base_scenario.dynamic_obstacles:
        all_obstacles = [dynamic_obstacle]
        for other_scenario in scenarios[1:]:
            other_dynamic_obstacle = other_scenario.obstacle_by_id(dynamic_obstacle.obstacle_id)
            if other_dynamic_obstacle is None:
                raise RuntimeError()

            if not isinstance(other_dynamic_obstacle, DynamicObstacle):
                raise RuntimeError()

            all_obstacles.append(other_dynamic_obstacle)
        yield tuple(all_obstacles)


def compute_waymo_metric(scenario: Scenario, scenario_reference: Scenario) -> WaymoMetric:
    """
    Compute the Waymo metrics for the scenario.

    :param scenario: The scenario for which the metrics should be computed.
    :param scenario_reference: The reference scenario for the computation.
    """
    assert scenario.dt == scenario_reference.dt

    measurment_times = [3, 5, 8]

    average_displacement_errors: Dict[int, List[float]] = defaultdict(list)
    final_displacement_errors: Dict[int, List[float]] = defaultdict(list)
    miss_rates: Dict[int, List[float]] = defaultdict(list)
    root_mean_squared_errors: List[float] = []

    for dynamic_obstacle, dynamic_obstacle_ref in _zipped_iter_dynamic_obstacles_in_scenarios(
        scenario, scenario_reference
    ):
        displacement_vector = _compute_displacment_vector_between_two_dynamic_obstacle(
            dynamic_obstacle, dynamic_obstacle_ref
        )
        if displacement_vector is None:
            continue

        reference_start_state = dynamic_obstacle_ref.state_at_time(
            dynamic_obstacle_ref.prediction.initial_time_step
        )
        if reference_start_state is None:
            raise RuntimeError()

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

    print(average_displacement_errors)
    print(final_displacement_errors)
    print(miss_rates)
    print(root_mean_squared_errors)

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
    filtered_metrics = {}
    for measurment_time, values in metrics.items():
        filtered_values = list(filter(lambda value: not math.isnan(value), values))
        if len(filtered_values) == 0:
            filtered_metrics[measurment_time] = float("nan")
        else:
            filtered_metrics[measurment_time] = statistics.mean(filtered_values)

    return filtered_metrics


def _compute_displacment_vector_between_two_dynamic_obstacle(
    dynamic_obstacle: DynamicObstacle, dynamic_obstacle_reference: DynamicObstacle
) -> Optional[np.ndarray]:
    if not isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        return None

    if not isinstance(dynamic_obstacle_reference.prediction, TrajectoryPrediction):
        return None

    time_step_offset = (
        dynamic_obstacle.prediction.trajectory.initial_time_step
        - dynamic_obstacle_reference.prediction.trajectory.initial_time_step
    )
    if time_step_offset < 0:
        _LOGGER.warning(
            "time step offset between %s and %s is %s, but must not be smaller then 0",
            dynamic_obstacle.obstacle_id,
            dynamic_obstacle_reference.obstacle_id,
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
    time_in_sec: int, state: WithDiscreteVelocity
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
