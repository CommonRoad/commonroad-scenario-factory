import logging
import math
from dataclasses import dataclass, fields
from typing import List, Tuple

import numpy as np
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import State

_LOGGER = logging.getLogger(__name__)


@dataclass
class WaymoMetricResult:
    """
    Data class for the Waymo metrics.
    """

    ADE3: float
    ADE5: float
    ADE8: float
    FDE3: float
    FDE5: float
    FDE8: float
    MR3: float
    MR5: float
    MR8: float

    def __str__(self) -> str:
        return "Waymo Metrics: " + ", ".join(
            [f"{field.name}: {getattr(self, field.name):.4f}" for field in fields(self)]
        )


def compute_waymo_metrics(scenario: Scenario, scenario_reference: Scenario) -> WaymoMetricResult:
    """
    Compute the Waymo metrics for the scenario.

    :param scenario: The scenario for which the metrics should be computed.
    :param scenario_reference: The reference scenario for the computation.
    """
    # assert scenario.scenario_id == scenario_reference.scenario_id
    assert scenario.dt == scenario_reference.dt

    ade3s: List[float] = []
    ade5s: List[float] = []
    ade8s: List[float] = []
    fde3s: List[float] = []
    fde5s: List[float] = []
    fde8s: List[float] = []
    mr3s: List[float] = []
    mr5s: List[float] = []
    mr8s: List[float] = []
    for dyn_obst in scenario.dynamic_obstacles:
        try:
            dyn_obst_ref = scenario_reference._dynamic_obstacles[dyn_obst.obstacle_id]

        except KeyError:
            _LOGGER.warning(
                f"Obstacle with ID {dyn_obst.obstacle_id} not found in reference scenario {scenario_reference.scenario_id}"
            )
            continue

        displacement_errors = []

        states = dyn_obst.prediction.trajectory.state_list
        states_ref = dyn_obst_ref.prediction.trajectory.state_list
        time_step_offset = states[0].time_step - states_ref[0].time_step
        time_step_offset_neg = 0
        if time_step_offset < 0:  # vehicles can only be spawned after the reference vehicle
            if time_step_offset == -1:  # TODO this is hacky; debug!
                time_step_offset_neg = -time_step_offset
                time_step_offset = 0
            else:
                raise ValueError(
                    f"Vehicle {dyn_obst.obstacle_id} is spawned before the reference vehicle."
                )

        for k in range(min(len(states) - time_step_offset_neg, len(states_ref) - time_step_offset)):
            displacement_errors.append(
                np.linalg.norm(
                    states[k + time_step_offset_neg].position
                    - states_ref[k + time_step_offset].position
                )
            )

        ade3, ade5, ade8, fde3, fde5, fde8 = _waymo_metrics_de(displacement_errors, scenario.dt)
        mr3, mr5, mr8 = _waymo_metrics_MR(
            states[time_step_offset_neg:], states_ref[time_step_offset:], scenario.dt
        )

        for value, container in zip(
            [ade3, ade5, ade8, fde3, fde5, fde8, mr3, mr5, mr8],
            [ade3s, ade5s, ade8s, fde3s, fde5s, fde8s, mr3s, mr5s, mr8s],
        ):
            if not math.isnan(value):
                container.append(value)

    return WaymoMetricResult(
        np.mean(np.array(ade3s)),
        np.mean(np.array(ade5s)),
        np.mean(np.array(ade8s)),
        np.mean(np.array(fde3s)),
        np.mean(np.array(fde5s)),
        np.mean(np.array(fde8s)),
        np.mean(np.array(mr3s)),
        np.mean(np.array(mr5s)),
        np.mean(np.array(mr8s)),
    )


def _waymo_metrics_de(
    displacement_errors: np.ndarray, time_step_size: float
) -> Tuple[float, float, float, float, float, float]:
    """
    Compute the displacement error metrics.

    :param displacement_errors: The displacement errors.
    :param time_step_size: The size of the time step.
    """
    index_3 = int(3 / time_step_size)
    index_5 = int(5 / time_step_size)
    index_8 = int(8 / time_step_size)

    ade3, ade5, ade8, fde3, fde5, fde8 = (
        float("nan"),
        float("nan"),
        float("nan"),
        float("nan"),
        float("nan"),
        float("nan"),
    )
    if len(displacement_errors) > index_3:
        ade3 = np.mean(displacement_errors[: index_3 + 1])
        fde3 = displacement_errors[index_3]
    if len(displacement_errors) > index_5:
        ade5 = np.mean(displacement_errors[: index_5 + 1])
        fde5 = displacement_errors[index_5]
    if len(displacement_errors) > index_8:
        ade8 = np.mean(displacement_errors[: index_8 + 1])
        fde8 = displacement_errors[index_8]

    return ade3, ade5, ade8, fde3, fde5, fde8


def _waymo_metrics_MR(
    states: List, states_ref: List, time_step_size: float
) -> Tuple[float, float, float]:
    """
    Compute the miss rate metrics.
    """
    index_3 = int(3 / time_step_size)
    index_5 = int(5 / time_step_size)
    index_8 = int(8 / time_step_size)

    min_len = min(len(states), len(states_ref))
    if min_len > index_3:
        threshold_lon_scaled = 2 * _scale(states_ref[0].velocity)
        threshold_lat_scaled = 1 * _scale(states_ref[0].velocity)
        MR3 = (
            sum(
                [
                    is_miss(states[k], states_ref[k], threshold_lon_scaled, threshold_lat_scaled)
                    for k in range(index_3)
                ]
            )
            / index_3
        )
    else:
        MR3 = float("nan")
    if min_len > index_5:
        threshold_lon_scaled = 3.6 * _scale(states_ref[0].velocity)
        threshold_lat_scaled = 1.8 * _scale(states_ref[0].velocity)
        MR5 = (
            sum(
                [
                    is_miss(states[k], states_ref[k], threshold_lon_scaled, threshold_lat_scaled)
                    for k in range(index_5)
                ]
            )
            / index_5
        )
    else:
        MR5 = float("nan")
    if min_len > index_8:
        threshold_lon_scaled = 6 * _scale(states_ref[0].velocity)
        threshold_lat_scaled = 3 * _scale(states_ref[0].velocity)
        MR8 = (
            sum(
                [
                    is_miss(states[k], states_ref[k], threshold_lon_scaled, threshold_lat_scaled)
                    for k in range(index_8)
                ]
            )
            / index_8
        )
    else:
        MR8 = float("nan")

    return MR3, MR5, MR8


def is_miss(
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


def _scale(v: float) -> float:
    """
    Return the scale factor for the threshold.
    """
    if v < 1.4:
        return 0.5
    elif v < 11:
        return 0.5 + 0.5 * (v - 1.4) / (11 - 1.4)
    else:
        return 1
