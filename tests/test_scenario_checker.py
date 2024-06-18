from commonroad.geometry.shape import Circle, Rectangle
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.state import InitialState
import numpy as np

from scenario_factory.scenario_checker import get_colliding_dynamic_obstacles


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
