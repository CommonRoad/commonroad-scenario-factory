from __future__ import annotations

import logging

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver

logger = logging.getLogger(__name__)


class ScenarioContainer:
    """
    The ScenarioContainer is used to wrap a scenario, such that it is easy to associate extra data with a scenario. All pipeline steps should use the ScenarioContainer instead of a plain CommonRoad scenario as their input parameter and output values.

    The pipeline steps in the scenario-factory are mostly concerned with handling CommonRoad scenarios. But often, additional data (like a planning problem set) is required or produced during a pipeline step. To ensure that each pipeline step can be applied generally, and does not rely on any specific order. For example, a pipeline step might produce a scenario with a planning problem set and another pipeline step might only require a CommonRoad scenario.
    """

    scenario: Scenario

    def __init__(self, scenario: Scenario):
        self.scenario = scenario


class ScenarioWithPlanningProblemSet(ScenarioContainer):
    planning_problem_set: PlanningProblemSet

    def __init__(self, scenario: Scenario, planning_problem_set: PlanningProblemSet):
        super().__init__(scenario)
        self.planning_problem_set = planning_problem_set


class ScenarioWithEgoVehicleManeuver(ScenarioContainer):
    ego_vehicle_maneuver: EgoVehicleManeuver

    def __init__(self, scenario: Scenario, ego_vehicle_maneuver: EgoVehicleManeuver):
        super().__init__(scenario)
        self.ego_vehicle_maneuver = ego_vehicle_maneuver
