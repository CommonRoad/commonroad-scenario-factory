from typing import Sequence

from commonroad.geometry.shape import Rectangle
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.state import TraceState, InitialState
from commonroad.scenario.trajectory import Trajectory


def create_test_obstacle_with_trajectory(
    state_list: Sequence[TraceState], obstacle_id: int = 1
) -> DynamicObstacle:
    obstacle_shape = Rectangle(2.0, 2.0)

    initial_state: InitialState = state_list[0].convert_state_to_state(InitialState())
    initial_state.fill_with_defaults()

    trajectory_state_list = state_list[1:]
    prediction = (
        TrajectoryPrediction(
            shape=obstacle_shape,
            trajectory=Trajectory(
                initial_time_step=trajectory_state_list[0].time_step,
                state_list=list(trajectory_state_list),
            ),
        )
        if len(trajectory_state_list) > 0
        else None
    )

    test_obstacle = DynamicObstacle(
        obstacle_id=obstacle_id,
        obstacle_type=ObstacleType.CAR,
        obstacle_shape=obstacle_shape,
        initial_state=initial_state,
        prediction=prediction,
    )
    return test_obstacle
