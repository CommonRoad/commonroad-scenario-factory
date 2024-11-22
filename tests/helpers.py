from hashlib import md5
from pathlib import Path
from typing import Sequence

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.geometry.shape import Rectangle
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.state import InitialState, TraceState
from commonroad.scenario.trajectory import Trajectory

from scenario_factory.pipeline import (
    PipelineContext,
    PipelineFilterPredicate,
    pipeline_filter,
    pipeline_fold,
    pipeline_map,
)


@pipeline_map()
def pipeline_simple_map(ctx: PipelineContext, value: int) -> int:
    return value**2


@pipeline_filter()
def pipeline_simple_filter(
    filter: PipelineFilterPredicate, ctx: PipelineContext, value: int
) -> bool:
    return filter.matches(value)


@pipeline_fold()
def pipeline_simple_fold(ctx: PipelineContext, values: Sequence[int]) -> Sequence[int]:
    return [sum(values)]


class IsEvenFilter(PipelineFilterPredicate):
    def matches(self, value: int) -> bool:
        return value % 2 == 0


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


def is_valid_commonroad_scenario(scenario_path: Path) -> bool:
    _, _ = CommonRoadFileReader(scenario_path).open()
    return True


def hash_file(path: Path):
    hash_func = md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()
