import numpy as np
from commonroad.common.util import Interval
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import ExtendedPMState

from scenario_factory.builder import LaneletNetworkBuilder
from scenario_factory.builder.dynamic_obstacle_builder import DynamicObstacleBuilder
from scenario_factory.builder.trajectory_builder import TrajectoryBuilder
from scenario_factory.scenario_generation import (
    create_planning_problem_for_ego_vehicle,
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
                [
                    ExtendedPMState(
                        time_step=0, position=np.array([0.0, 0.0]), velocity=1.0, acceleration=0.0
                    )
                ],
                obstacle_id=obstacle_id,
            )
            scenario.add_objects(obstacle)

        assert len(scenario.dynamic_obstacles) == 4
        deleted_obstacles = delete_colliding_obstacles_from_scenario(scenario, all=True)
        assert len(deleted_obstacles) == 4
        assert len(scenario.dynamic_obstacles) == 0


class TestCreatePlanningPorlbmeForEgoVehicle:
    def test_does_not_assign_goal_region_to_lanelet_if_goal_and_initial_state_are_on_same_lanelet(
        self,
    ):
        lanelet_network_builder = LaneletNetworkBuilder()
        lanelet1 = lanelet_network_builder.add_lanelet((0.0, 0.0), (0.0, 10.0), width=5)
        lanelet_network = lanelet_network_builder.build()
        ego_vehicle = (
            DynamicObstacleBuilder(dynamic_obstacle_id=1)
            .set_trajectory(
                TrajectoryBuilder()
                .start(0, position=lanelet1.center_vertices[0], velocity=25.0, orientation=1.0)
                .end(10, position=lanelet1.center_vertices[-1], velocity=23.4, orientation=1.0)
            )
            .build()
        )
        planning_problem = create_planning_problem_for_ego_vehicle(
            lanelet_network, ego_vehicle, Interval(0, 150)
        )
        assert planning_problem.planning_problem_id == ego_vehicle.obstacle_id
        assert len(planning_problem.goal.state_list) == 1
        assert planning_problem.goal.lanelets_of_goal_position is None

    def test_assigns_goal_region_to_lanelet_if_goal_and_initial_state_are_on_different_lanelets(
        self,
    ):
        lanelet_network_builder = LaneletNetworkBuilder()
        lanelet1 = lanelet_network_builder.add_lanelet((0.0, 0.0), (0.0, 10.0), width=5)
        lanelet2 = lanelet_network_builder.add_adjacent_lanelet(lanelet1, width=5)
        lanelet_network = lanelet_network_builder.build()
        ego_vehicle = (
            DynamicObstacleBuilder(dynamic_obstacle_id=1)
            .set_trajectory(
                TrajectoryBuilder()
                .start(0, position=lanelet1.center_vertices[0], velocity=25.0, orientation=1.0)
                .end(10, position=lanelet2.center_vertices[-1], velocity=23.4, orientation=1.0)
            )
            .build()
        )

        planning_problem = create_planning_problem_for_ego_vehicle(
            lanelet_network, ego_vehicle, Interval(30, 40), planning_problem_with_lanelet=True
        )
        assert planning_problem.planning_problem_id == ego_vehicle.obstacle_id
        assert len(planning_problem.goal.state_list) == 1
        assert planning_problem.goal.lanelets_of_goal_position is not None
        assert len(planning_problem.goal.lanelets_of_goal_position.values()) == 1
        assert planning_problem.goal.lanelets_of_goal_position[0] == [lanelet2.lanelet_id]


class TestCreatePlanningProblemSetAndSolutionForEgoVehicle:
    def test_creates_empty_planning_problem_and_solution_for_emtpy_ego_vehicle(self):
        scenario = Scenario(dt=0.1)
        ego_vehicle = create_test_obstacle_with_trajectory(
            [
                ExtendedPMState(
                    time_step=i,
                    position=np.array([0.0, 0.0]),
                    velocity=1.0,
                    acceleration=0.0,
                    orientation=0.0,
                )
                for i in range(0, 100)
            ]
        )
        planning_problem_set, planning_problem_solution = (
            create_planning_problem_set_and_solution_for_ego_vehicle(
                scenario, ego_vehicle, 150, planning_problem_with_lanelet=False
            )
        )
        # TODO: missing asserts
