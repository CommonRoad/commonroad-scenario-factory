import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.scenario import Scenario

from scenario_factory.utils import (
    get_scenario_final_time_step,
    get_scenario_start_time_step,
)


@dataclass
class GeneralScenarioMetric:
    """
    Data class for the initial submission metrics.
    """

    frequency: float  # [1 / s]
    traffic_density_mean: float  # [1 / km]
    traffic_density_stdev: float  # [1 / km]
    velocity_mean: float  # [m / s]
    velocity_stdev: float  # [m / s]

    def __str__(self) -> str:
        return f"f: {self.frequency:.4f}, rho_mu: {self.traffic_density_mean:.4f}, rho_sigma: {self.traffic_density_stdev:.4f}, v_mu: {self.velocity_mean:.4f}, v_sigma: {self.velocity_stdev:.4f}"


def compute_general_scenario_metric(
    scenario: Scenario, frame_factor: float = 1.0
) -> GeneralScenarioMetric:
    """
    Compute the initial submission metrics for the scenario.

    :param scenario: The scenario for which the metrics should be computed.
    :param frame_factor: Scaling factor to adjust the traffic densisty for recorded datasets.

    :returns: The scenario metrics
    """
    frequency = _compute_spawn_frequency(scenario)

    traffic_density_mean, traffic_density_stdev = _compute_traffic_density(scenario, frame_factor)
    velocity_mean, velocity_stdev = _compute_velocity(scenario)

    precision = 3
    return GeneralScenarioMetric(
        frequency=round(frequency, precision),
        traffic_density_mean=round(traffic_density_mean, precision),
        traffic_density_stdev=round(traffic_density_stdev, precision),
        velocity_mean=round(velocity_mean, precision),
        velocity_stdev=round(velocity_stdev, precision),
    )


def _compute_spawn_frequency(scenario: Scenario) -> float:
    # divide number of vehicles by scenario duration
    # do not count vehicles that already exist at 0
    min_time_step = get_scenario_start_time_step(scenario)

    # number of vehicles with initial time > 0
    number_of_spawned_vehicles = sum(
        [1 for obs in scenario.dynamic_obstacles if obs.initial_state.time_step > min_time_step]
    )
    if number_of_spawned_vehicles == 0:
        return 0.0

    max_time_step = get_scenario_final_time_step(scenario)
    if max_time_step == 0:
        return 0.0

    return number_of_spawned_vehicles / (scenario.dt * max_time_step)


def _compute_velocity(scenario: Scenario) -> Tuple[float, float]:
    # calculate mean velocity
    velocities_at_k = defaultdict(list)

    for obs in scenario.dynamic_obstacles:
        if not obs.prediction:
            logging.warning(
                f"Missing prediction for dynamic obstacle: {scenario.scenario_id}, {obs.obstacle_id}"
            )  # TODO how?
            continue
        for state in obs.prediction.trajectory.state_list:
            velocities_at_k[state.time_step].append(state.velocity)

    mean_velocity_over_time = np.array(
        [v for v in {k: sum(v) / len(v) for k, v in velocities_at_k.items()}.values()]
    )

    return np.mean(mean_velocity_over_time), np.std(mean_velocity_over_time)


def _compute_traffic_density(scenario: Scenario, frame_factor: float) -> Tuple[float, float]:
    # calculate traffic density
    max_time_step = get_scenario_final_time_step(scenario)
    if max_time_step == 0:
        return float("nan"), float("nan")

    number_of_vehicles_at_time_step: List[int] = [0] * max_time_step
    # By iterating over the time steps instead of the obstacle trajectories, no checks
    # on the trajectories have to be performed here.
    for time_step in range(max_time_step):
        for dynamic_obstacle in scenario.dynamic_obstacles:
            if dynamic_obstacle.state_at_time(time_step) is not None:
                number_of_vehicles_at_time_step[time_step] += 1

    traffic_density_over_time = (
        np.array(number_of_vehicles_at_time_step)
        / _lanelet_network_length(scenario)
        / frame_factor
        * 1000
    )  # [1 / km]
    time_correction = max_time_step / len(
        traffic_density_over_time
    )  # otherwise, times with zero traffic are just ignored

    return np.mean(traffic_density_over_time) * time_correction, np.std(
        traffic_density_over_time
    ) * time_correction


def _lanelet_network_length(scenario: Scenario) -> float:
    return sum([_lanelet_length(lanelet) for lanelet in scenario.lanelet_network.lanelets])


def _lanelet_length(lanelet: Lanelet) -> float:
    return np.sum(np.linalg.norm(np.diff(lanelet.center_vertices, axis=0), axis=1))
