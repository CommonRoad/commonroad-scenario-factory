import logging
from dataclasses import dataclass

import numpy as np
from commonroad.scenario.scenario import Scenario

_LOGGER = logging.getLogger(__name__)


@dataclass
class WaymoMetricResult:
    """
    Data class for the Waymo metrics.
    """

    ADE3: float
    ADE5: float
    ADE8: float
    # TODO add
    # FDE3: float
    # FDE5: float
    # FDE8: float
    # miss_rate3: float
    # miss_rate5: float
    # miss_rate8: float

    def __str__(self) -> str:
        return f"Waymo Metrics: ADE3={self.ADE3}, ADE5={self.ADE5}, ADE8={self.ADE8}"


def compute_waymo_metrics(scenario: Scenario, scenario_reference: Scenario) -> WaymoMetricResult:
    """
    Compute the Waymo metrics for the scenario.

    Parameters
    ----------
    scenario: Scenario
        The scenario for which the metrics should be computed.
    scenario_reference: Scenario
        The reference scenario.
    """
    assert scenario.scenario_id == scenario_reference.scenario_id
    assert scenario.dt == scenario_reference.dt

    for dyn_obst in scenario.dynamic_obstacles:
        dyn_obst_ref = scenario_reference.obstacle_by_id(dyn_obst.obstacle_id)
        if dyn_obst_ref is None:
            logging.warning(
                f"Obstacle with ID {dyn_obst.obstacle_id} not found in reference scenario {scenario_reference.scenario_id}"
            )
            continue

        displacement_errors = []

        states = dyn_obst.prediction.trajectory.state_list
        states_ref = dyn_obst_ref.prediction.trajectory.state_list
        assert (
            states[0].time_step == states_ref[0].time_step
        )  # TODO offset could be != 0, but then we need to handle it

        for k in range(len(states)):
            displacement_errors.append(np.linalg.norm(states[k].position - states_ref[k].position))
            # TODO implement

    return WaymoMetricResult(0.1, 0.2, 0.3)
