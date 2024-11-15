import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.scenario import Scenario


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


def compute_general_scenario_metric(scenario: Scenario, is_orig: bool) -> GeneralScenarioMetric:
    """
    Compute the initial submission metrics for the scenario.

    :param scenario: The scenario for which the metrics should be computed.
    """
    # frequency
    frequency = _compute_spawn_frequency(scenario)

    # calculate traffic density
    traffic_density_mean, traffic_density_stdev = _compute_traffic_density(scenario, is_orig)
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

    # number of vehicles with initial time > 0
    number_of_spawned_vehicles = sum(
        [1 for obs in scenario.dynamic_obstacles if obs.initial_state.time_step > 2]
    )
    max_time_step = 0
    for obs in scenario.dynamic_obstacles:
        if not obs.prediction:
            logging.warning("Missing prediction for dynamic obstacle.")
            continue
        max_time_step = max(max_time_step, obs.prediction.trajectory.state_list[-1].time_step)

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


def _compute_traffic_density(scenario: Scenario, is_orig: bool) -> Tuple[float, float]:
    # calculate traffic density
    number_of_vehicles_at_k: Dict[int, int] = defaultdict(int)
    max_time_step = 0

    for obs in scenario.dynamic_obstacles:
        if not obs.prediction:
            logging.warning("Missing prediction for dynamic obstacle.")  # TODO why?
            continue
        for state in obs.prediction.trajectory.state_list:
            number_of_vehicles_at_k[state.time_step] += 1
            max_time_step = max(max_time_step, state.time_step)

    if is_orig:
        frame_factor = _get_frame_factor_orig(scenario)
    else:
        frame_factor = _get_frame_factor_sim(scenario)

    traffic_density_over_time = (
        np.array([v for v in number_of_vehicles_at_k.values()])
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


def _get_frame_factor_sim(scenario: Scenario) -> float:
    simulation_mode = int(str(scenario.scenario_id).split("_")[2])
    if simulation_mode > 2:  # demand, infrastructure, or random
        return 1.0
    scenario_id = str(scenario.scenario_id).split("-")[-3]
    match scenario_id:
        case "DEU_MONAEast":
            return 0.86
        case "DEU_MONAMerge":
            return 0.80
        case "DEU_MONAWest":
            return 0.96
        case "DEU_AachenBendplatz":
            return 0.85
        case "DEU_AachenHeckstrasse":
            return 0.90
        case "DEU_LocationCLower4":
            return 0.94
        case _:
            return 1.0


def _get_frame_factor_orig(scenario: Scenario) -> float:
    scenario_id = str(scenario.scenario_id).split("-")[-3]
    match scenario_id:
        case "DEU_MONAEast":
            return 0.75
        case "DEU_MONAMerge":
            return 0.6
        case "DEU_MONAWest":
            return 0.9
        case "DEU_AachenBendplatz":
            return 0.7
        case "DEU_AachenHeckstrasse":
            return 0.78
        case "DEU_LocationCLower4":
            return 0.87
        case _:
            return 1.0
