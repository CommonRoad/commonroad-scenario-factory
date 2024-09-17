import numpy as np
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import ExtendedPMState

from scenario_factory.generate_senarios import (
    create_planning_problem_set_and_solution_for_ego_vehicle,
    delete_colliding_obstacles_from_scenario,
)
from tests.helpers import create_test_obstacle_with_trajectory


class TestDeleteCollidingObstaclesFromScenario:
    def test_deletes_nothing_in_empty_scenario(self):
        scenario = Scenario(dt=0.1)
        deleted_obstacles = delete_colliding_obstacles_from_scenario(scenario)
        assert len(deleted_obstacles) == 0

    def test_deletes_all_obstacles_in_collision(self):
        scenario = Scenario(dt=0.1)
        for obstacle_id in range(0, 4):
            obstacle = create_test_obstacle_with_trajectory(
                [ExtendedPMState(time_step=0, position=np.array([0.0, 0.0]), velocity=1.0, acceleration=0.0)],
                obstacle_id=obstacle_id,
            )
            scenario.add_objects(obstacle)

        assert len(scenario.dynamic_obstacles) == 4
        deleted_obstacles = delete_colliding_obstacles_from_scenario(scenario, all=True)
        assert len(deleted_obstacles) == 4
        assert len(scenario.dynamic_obstacles) == 0


class TestCreatePlanningProblemSetAndSolutionForEgoVehicle:
    def test_creates_empty_planning_problem_and_solution_for_emtpy_ego_vehicle(self):
        scenario = Scenario(dt=0.1)
        ego_vehicle = create_test_obstacle_with_trajectory(
            [
                ExtendedPMState(
                    time_step=i, position=np.array([0.0, 0.0]), velocity=1.0, acceleration=0.0, orientation=0.0
                )
                for i in range(0, 100)
            ]
        )
        planning_problem_set, planning_problem_solution = create_planning_problem_set_and_solution_for_ego_vehicle(
            scenario, ego_vehicle, planning_problem_with_lanelet=False
        )
