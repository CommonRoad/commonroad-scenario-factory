from typing import Sequence

import numpy as np
from commonroad.geometry.shape import Rectangle
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import ObstacleType
from commonroad.scenario.scenario import DynamicObstacle
from commonroad.scenario.state import ExtendedPMState, InitialState, PMState, TraceState
from commonroad.scenario.trajectory import Trajectory

from scenario_factory.ego_vehicle_selector import (
    AccelerationCriterion,
    BrakingCriterion,
    EgoVehicleManeuver,
    _does_ego_vehicle_maneuver_last_long_enough,
    _does_ego_vehicle_maneuver_reach_minimum_velocity,
    threshold_and_lag_detection,
    threshold_and_max_detection,
)


class TestThresholdAndLagDection:
    def test_should_not_detect_anything_for_empty_signal(self):
        matches, time_step = threshold_and_lag_detection(np.array([]), 1, 1)
        assert matches is False
        assert time_step == -1

    def test_should_not_detect_anything_under_threshold(self):
        signals = np.array([i for i in range(0, 100)])
        matches, time_step = threshold_and_lag_detection(signals, threshold=100.0, lag_threshold=1.0)
        assert matches is False
        assert time_step == -1

    def test_should_not_detect_if_lagged_threshold_is_not_met(self):
        signals = np.array([i for i in range(0, 100)])
        matches, time_step = threshold_and_lag_detection(signals, threshold=60.0, lag_threshold=60.0)
        assert matches is False
        assert time_step == -1

    def test_should_detect_if_lagged_threshold_is_also_met(self):
        signals = np.array([i for i in range(0, 100)])
        matches, time_step = threshold_and_lag_detection(signals, threshold=60.0, lag_threshold=6.0)
        assert matches
        assert time_step == 90


class TestThresholdAndMaxDetection:
    def test_should_not_detect_anything_for_empty_signal(self):
        matches, time_step = threshold_and_max_detection(np.array([]), threshold=0.0)
        assert matches is False
        assert time_step == -1

    def test_should_not_detect_anything_under_threshold(self):
        matches, time_step = threshold_and_max_detection(np.array([i for i in range(0, 100)]), threshold=100.0)
        assert matches is False
        assert time_step == -1

        matches, time_step = threshold_and_max_detection(np.array([1, 1, -3, 4, 6]), threshold=6.0)
        assert matches is False
        assert time_step == -1

    def test_should_detect_over_threshold(self):
        matches, time_step = threshold_and_max_detection(np.array([i for i in range(0, 100)]), threshold=50.0)
        assert matches
        assert time_step == 50


def _test_obstacle_with_trajectory(state_list: Sequence[TraceState]) -> DynamicObstacle:
    obstacle_shape = Rectangle(2.0, 2.0)
    test_obstacle = DynamicObstacle(
        obstacle_id=1,
        obstacle_type=ObstacleType.CAR,
        obstacle_shape=obstacle_shape,
        initial_state=InitialState(
            time_step=1, position=np.array([0.0, 0.0]), orientation=0.0, velocity=0.0, acceleration=0.0
        ),
        prediction=TrajectoryPrediction(
            trajectory=Trajectory(initial_time_step=2, state_list=list(state_list)),
            shape=obstacle_shape,
        ),
    )
    return test_obstacle


class TestBrakingCriertion:
    def test_should_not_detect_anything_if_acceleration_is_missing(self):
        test_obstacle = _test_obstacle_with_trajectory([PMState(time_step=2)])
        criterion = BrakingCriterion()
        matches, time_step = criterion.matches(test_obstacle)
        assert matches is False
        assert time_step < 0

    def test_should_not_detect_anything_when_not_braking(self):
        test_obstacle = _test_obstacle_with_trajectory(
            [
                ExtendedPMState(
                    time_step=i + 2, position=np.array([float(i), float(i)]), velocity=1.0, acceleration=0.0
                )
                for i in range(0, 100)
            ]
        )
        criterion = BrakingCriterion()
        matches, time_step = criterion.matches(test_obstacle)
        assert matches is False
        assert time_step < 0

    def test_should_detect_if_braking(self):
        state_list = [
            ExtendedPMState(time_step=i + 2, position=np.array([float(i), float(i)]), velocity=1.0, acceleration=0.0)
            for i in range(0, 10)
        ]

        state_list.extend(
            [
                ExtendedPMState(
                    time_step=i + 2, position=np.array([float(i), float(i)]), velocity=1.0, acceleration=-4.0
                )
                for i in range(10, 20)
            ]
        )
        test_obstacle = _test_obstacle_with_trajectory(state_list)

        criterion = BrakingCriterion()
        matches, index = criterion.matches(test_obstacle)
        assert matches
        assert index == 9

    def test_should_detect_if_hold_not_met(self):
        state_list = [
            ExtendedPMState(time_step=i + 2, position=np.array([float(i), float(i)]), velocity=1.0, acceleration=0.0)
            for i in range(0, 10)
        ]

        state_list.extend(
            [
                ExtendedPMState(
                    time_step=i + 2, position=np.array([float(i), float(i)]), velocity=1.0, acceleration=-5.0
                )
                for i in range(10, 12)
            ]
        )
        test_obstacle = _test_obstacle_with_trajectory(state_list)

        criterion = BrakingCriterion()
        matches, index = criterion.matches(test_obstacle)
        assert matches is False
        assert index < 0


class TestAccelerationCriertion:
    def test_should_not_detect_anything_if_acceleration_is_missing(self):
        test_obstacle = _test_obstacle_with_trajectory([PMState(time_step=2)])
        criterion = AccelerationCriterion()
        matches, time_step = criterion.matches(test_obstacle)
        assert matches is False
        assert time_step < 0

    def test_should_not_detect_anything_when_not_accelerating(self):
        test_obstacle = _test_obstacle_with_trajectory(
            [
                ExtendedPMState(
                    time_step=i + 2, position=np.array([float(i), float(i)]), velocity=1.0, acceleration=0.0
                )
                for i in range(0, 100)
            ]
        )
        criterion = BrakingCriterion()
        matches, time_step = criterion.matches(test_obstacle)
        assert matches is False
        assert time_step < 0


class TestDoesEgoVehicleManeuverReachMinimumVelocity:
    def test_should_reject_if_no_state_reach_minimum_velocity(self):
        ego_vehicle = _test_obstacle_with_trajectory([PMState(time_step=2 + i, velocity=13.0) for i in range(0, 20)])
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=5)
        assert (
            _does_ego_vehicle_maneuver_reach_minimum_velocity(maneuver, scenario_time_steps=150, min_ego_velocity=23.5)
            is False
        )
        assert (
            _does_ego_vehicle_maneuver_reach_minimum_velocity(maneuver, scenario_time_steps=10, min_ego_velocity=20)
            is False
        )

    def test_should_accept_if_ego_vehicle_exactly_matches_minimum_velocity_at_least_once(self):
        state_list = [PMState(time_step=2 + i, velocity=13.5) for i in range(0, 10)]
        state_list.append(PMState(time_step=22, velocity=30.0))
        state_list.extend([PMState(time_step=23 + i, velocity=13.0) for i in range(0, 10)])
        ego_vehicle = _test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=5)
        assert _does_ego_vehicle_maneuver_reach_minimum_velocity(
            maneuver, scenario_time_steps=150, min_ego_velocity=23.5
        )
        assert _does_ego_vehicle_maneuver_reach_minimum_velocity(
            maneuver, scenario_time_steps=20, min_ego_velocity=29.0
        )

    def test_should_reject_if_maneuver_start_time_is_after_state_that_reaches_minimum_velocity(self):
        state_list = [PMState(time_step=2 + i, velocity=30) for i in range(0, 10)]
        state_list.extend([PMState(time_step=12 + i, velocity=13.0) for i in range(0, 10)])
        ego_vehicle = _test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=14)
        assert (
            _does_ego_vehicle_maneuver_reach_minimum_velocity(maneuver, scenario_time_steps=150, min_ego_velocity=23.5)
            is False
        )


class TestDoesEgoVehicleManeuverLastLongEnough:
    def test_should_reject_maneuver_that_is_not_long_enough(self):
        state_list = [PMState(time_step=2)]
        ego_vehicle = _test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=5)
        assert _does_ego_vehicle_maneuver_last_long_enough(maneuver, scenario_time_steps=150) is False

    def test_should_accept_maneuver_that_is_exactly_long_enough(self):
        state_list = [PMState(time_step=2 + i) for i in range(0, 10)]
        ego_vehicle = _test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=2)
        assert _does_ego_vehicle_maneuver_last_long_enough(maneuver, scenario_time_steps=9)

    def test_should_reject_maneuver_that_starts_outside_of_trajectory(self):
        state_list = [PMState(time_step=2 + i) for i in range(0, 10)]
        ego_vehicle = _test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=20)
        assert _does_ego_vehicle_maneuver_last_long_enough(maneuver, scenario_time_steps=100) is False
