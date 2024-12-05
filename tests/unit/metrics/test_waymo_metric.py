import numpy as np
import pytest

from scenario_factory.builder.dynamic_obstacle_builder import DynamicObstacleBuilder
from scenario_factory.builder.scenario_builder import ScenarioBuilder
from scenario_factory.builder.trajectory_builder import TrajectoryBuilder
from scenario_factory.metrics import compute_waymo_metric
from scenario_factory.metrics.waymo_metric import (
    compute_displacment_vector_between_two_dynamic_obstacles,
)


class TestComputeDisplacementVectorBetweenTwoDynamicObstacles:
    def test_fails_if_one_of_the_obstacles_has_no_prediction(self):
        dynamic_obstacle_without_prediction = DynamicObstacleBuilder(dynamic_obstacle_id=1).build()
        dynamic_obstacle_with_prediction = (
            DynamicObstacleBuilder.from_dynamic_obstacle(dynamic_obstacle_without_prediction)
            .set_trajectory(
                TrajectoryBuilder()
                .start(time_step=10, position=(0.0, 0.0))
                .end(time_step=20, position=(10.0, 10.0))
            )
            .build()
        )

        assert (
            compute_displacment_vector_between_two_dynamic_obstacles(
                dynamic_obstacle_without_prediction, dynamic_obstacle_with_prediction
            )
            is None
        )

        assert (
            compute_displacment_vector_between_two_dynamic_obstacles(
                dynamic_obstacle_with_prediction, dynamic_obstacle_without_prediction
            )
            is None
        )

        assert (
            compute_displacment_vector_between_two_dynamic_obstacles(
                dynamic_obstacle_without_prediction, dynamic_obstacle_without_prediction
            )
            is None
        )

    def test_fails_if_time_step_offset_is_negative(self):
        obstacle_with_earlier_start = (
            DynamicObstacleBuilder(dynamic_obstacle_id=1)
            .set_trajectory(
                TrajectoryBuilder()
                .start(time_step=5, position=(0.0, 0.0))
                .end(time_step=15, position=(5.0, 5.0))
            )
            .build()
        )
        obstacle_with_later_start = (
            DynamicObstacleBuilder(dynamic_obstacle_id=2)
            .set_trajectory(
                TrajectoryBuilder()
                .start(time_step=10, position=(1.0, 1.0))
                .end(time_step=20, position=(6.0, 6.0))
            )
            .build()
        )

        assert (
            compute_displacment_vector_between_two_dynamic_obstacles(
                obstacle_with_earlier_start, obstacle_with_later_start
            )
            is None
        )

    def test_computes_displacement_vector_correctly(self):
        obstacle1 = (
            DynamicObstacleBuilder(dynamic_obstacle_id=1)
            .set_trajectory(
                TrajectoryBuilder()
                .start(time_step=10, position=(0.0, 0.0))
                .end(time_step=14, position=(4.0, 4.0))
            )
            .build()
        )
        obstacle2 = (
            DynamicObstacleBuilder(dynamic_obstacle_id=2)
            .set_trajectory(
                TrajectoryBuilder()
                .start(time_step=10, position=(0.0, 0.0))
                .end(time_step=12, position=(3.0, 2.0))
            )
            .build()
        )

        displacement_vector = compute_displacment_vector_between_two_dynamic_obstacles(
            obstacle1, obstacle2
        )

        assert displacement_vector is not None
        assert len(displacement_vector) == 3
        assert np.allclose(displacement_vector, [0.0, 0.5, 1.0])

    def test_handles_reference_with_missing_states(self):
        obstacle = (
            DynamicObstacleBuilder(dynamic_obstacle_id=1)
            .set_trajectory(
                TrajectoryBuilder()
                .start(time_step=3, position=(0.0, 0.0))
                .end(time_step=8, position=(0.0, 5.0))
            )
            .build()
        )
        incomplete_reference_obstacle = (
            DynamicObstacleBuilder(dynamic_obstacle_id=2)
            .set_trajectory(
                TrajectoryBuilder()
                .start(time_step=3, position=(1.0, 0.0))
                .end(time_step=6, position=(1.0, 3.0))
            )
            .build()
        )

        displacement_vector = compute_displacment_vector_between_two_dynamic_obstacles(
            obstacle, incomplete_reference_obstacle
        )

        assert displacement_vector is not None
        assert len(displacement_vector) == 4
        assert np.allclose(displacement_vector, [1.0, 1.0, 1.0, 1.0])


class TestComputeWaymoMetric:
    def test_fails_if_reference_scenario_does_not_contain_any_obstacles(self):
        scenario_builder = ScenarioBuilder()
        for i in range(0, 5):
            (
                scenario_builder.create_dynamic_obstacle(i)
                .create_trajectory()
                .start(time_step=0, position=(i, 0.0))
                .end(time_step=50, position=(i + 50, 0.0))
            )

        scenario = scenario_builder.build()
        reference_scenario = ScenarioBuilder().build()
        with pytest.raises(RuntimeError):
            compute_waymo_metric(scenario, reference_scenario)
