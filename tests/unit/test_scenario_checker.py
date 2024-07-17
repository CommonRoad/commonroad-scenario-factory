import numpy as np
from commonroad.geometry.shape import Circle, Rectangle
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import InitialState

from scenario_factory.scenario_checker import get_colliding_dynamic_obstacles, has_scenario_collisions


class TestGetCollidingDynamicObstacles:
    def test_finds_no_collisions_for_empty_obstacle_list(self):
        assert len(get_colliding_dynamic_obstacles([])) == 0
        assert len(get_colliding_dynamic_obstacles([], get_all=True)) == 0

    def test_returns_all_collisions_for_two_obstacles(self):
        shape = Circle(5.0)

        obstacles = [
            DynamicObstacle(
                obstacle_id=i,
                obstacle_type=ObstacleType.CAR,
                obstacle_shape=shape,
                initial_state=InitialState(time_step=0, position=np.array([0.0, 0.0]), orientation=0.0, velocity=0.0),
            )
            for i in range(0, 2)
        ]

        collisions = get_colliding_dynamic_obstacles(obstacles, get_all=True)
        assert len(collisions) == 2

    def test_returns_all_collisions_for_five_obstacles(self):
        shape = Rectangle(2.0, 2.0)

        obstacles = [
            DynamicObstacle(
                obstacle_id=i,
                obstacle_type=ObstacleType.CAR,
                obstacle_shape=shape,
                initial_state=InitialState(
                    time_step=0, position=np.array([float(i), float(i)]), orientation=0.0, velocity=0.0
                ),
            )
            for i in range(0, 5)
        ]

        collisions = get_colliding_dynamic_obstacles(obstacles, get_all=True)
        assert len(collisions) == 5

    def test_returns_one_collision_for_two_obstacles(self):
        shape = Circle(5.0)

        obstacles = [
            DynamicObstacle(
                obstacle_id=i,
                obstacle_type=ObstacleType.CAR,
                obstacle_shape=shape,
                initial_state=InitialState(time_step=0, position=np.array([0.0, 0.0]), orientation=0.0, velocity=0.0),
            )
            for i in range(0, 2)
        ]

        collisions = get_colliding_dynamic_obstacles(obstacles, get_all=False)
        assert len(collisions) == 1


class TestHasScenarioCollisions:
    def test_returns_false_for_empty_scenario(self):
        scenario = Scenario(dt=0.2)
        assert has_scenario_collisions(scenario) is False

    def test_returns_true_for_colliding_scenario(self):
        scenario = Scenario(dt=2)
        shape = Rectangle(2.0, 2.0)

        obstacles = [
            DynamicObstacle(
                obstacle_id=i,
                obstacle_type=ObstacleType.CAR,
                obstacle_shape=shape,
                initial_state=InitialState(
                    time_step=0, position=np.array([float(i), float(i)]), orientation=0.0, velocity=0.0
                ),
            )
            for i in range(0, 5)
        ]
        scenario.add_objects(obstacles)

        assert has_scenario_collisions(scenario)
