import numpy as np
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import ExtendedPMState, PMState

from scenario_factory.ego_vehicle_selection import (
    AccelerationCriterion,
    BrakingCriterion,
    EgoVehicleManeuver,
    LongEnoughManeuverFilter,
    MinimumVelocityFilter,
    threshold_and_lag_detection,
    threshold_and_max_detection,
)
from scenario_factory.ego_vehicle_selection.criterions import LaneChangeCriterion
from tests.helpers import create_test_obstacle_with_trajectory


class TestThresholdAndLagDection:
    def test_should_not_detect_anything_for_empty_signal(self):
        matches, time_step = threshold_and_lag_detection(np.array([]), 1, 1)
        assert matches is False
        assert time_step == -1

    def test_should_not_detect_anything_under_threshold(self):
        signals = np.array([i for i in range(0, 100)])
        matches, time_step = threshold_and_lag_detection(
            signals, threshold=100.0, lag_threshold=1.0
        )
        assert matches is False
        assert time_step == -1

    def test_should_not_detect_if_lagged_threshold_is_not_met(self):
        signals = np.array([i for i in range(0, 100)])
        matches, time_step = threshold_and_lag_detection(
            signals, threshold=60.0, lag_threshold=60.0
        )
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
        matches, time_step = threshold_and_max_detection(
            np.array([i for i in range(0, 100)]), threshold=100.0
        )
        assert matches is False
        assert time_step == -1

        matches, time_step = threshold_and_max_detection(np.array([1, 1, -3, 4, 6]), threshold=6.0)
        assert matches is False
        assert time_step == -1

    def test_should_detect_over_threshold(self):
        matches, time_step = threshold_and_max_detection(
            np.array([i for i in range(0, 100)]), threshold=50.0
        )
        assert matches
        assert time_step == 50


class TestBrakingCriertion:
    def test_should_not_detect_anything_if_acceleration_is_missing(self):
        scenario = Scenario(dt=0.1)
        test_obstacle = create_test_obstacle_with_trajectory([PMState(time_step=1)])
        criterion = BrakingCriterion()
        matches, time_step = criterion.matches(scenario, test_obstacle)
        assert matches is False
        assert time_step < 0

    def test_should_not_detect_anything_when_not_braking(self):
        scenario = Scenario(dt=0.1)
        test_obstacle = create_test_obstacle_with_trajectory(
            [
                ExtendedPMState(
                    time_step=i + 1,
                    position=np.array([float(i), float(i)]),
                    velocity=1.0,
                    acceleration=0.0,
                )
                for i in range(0, 100)
            ]
        )
        criterion = BrakingCriterion()
        matches, time_step = criterion.matches(scenario, test_obstacle)
        assert matches is False
        assert time_step < 0

    def test_should_detect_if_braking(self):
        scenario = Scenario(dt=0.1)
        state_list = [
            ExtendedPMState(
                time_step=i + 1,
                position=np.array([float(i), float(i)]),
                velocity=1.0,
                acceleration=0.0,
            )
            for i in range(0, 10)
        ]

        state_list.extend(
            [
                ExtendedPMState(
                    time_step=i + 1,
                    position=np.array([float(i), float(i)]),
                    velocity=1.0,
                    acceleration=-4.0,
                )
                for i in range(10, 20)
            ]
        )
        test_obstacle = create_test_obstacle_with_trajectory(state_list)

        criterion = BrakingCriterion()
        matches, index = criterion.matches(scenario, test_obstacle)
        assert matches
        assert index == 10

    def test_should_detect_if_hold_not_met(self):
        scenario = Scenario(dt=0.1)
        state_list = [
            ExtendedPMState(
                time_step=i + 1,
                position=np.array([float(i), float(i)]),
                velocity=1.0,
                acceleration=0.0,
            )
            for i in range(0, 10)
        ]

        state_list.extend(
            [
                ExtendedPMState(
                    time_step=i + 1,
                    position=np.array([float(i), float(i)]),
                    velocity=1.0,
                    acceleration=-5.0,
                )
                for i in range(10, 12)
            ]
        )
        test_obstacle = create_test_obstacle_with_trajectory(state_list)

        criterion = BrakingCriterion()
        matches, index = criterion.matches(scenario, test_obstacle)
        assert matches is False
        assert index < 0


class TestAccelerationCriertion:
    def test_should_not_detect_anything_if_acceleration_is_missing(self):
        scenario = Scenario(dt=0.1)
        test_obstacle = create_test_obstacle_with_trajectory([PMState(time_step=2)])
        criterion = AccelerationCriterion()
        matches, time_step = criterion.matches(scenario, test_obstacle)
        assert matches is False
        assert time_step < 0

    def test_should_not_detect_anything_when_not_accelerating(self):
        scenario = Scenario(dt=0.1)
        test_obstacle = create_test_obstacle_with_trajectory(
            [
                ExtendedPMState(
                    time_step=i + 1,
                    position=np.array([float(i), float(i)]),
                    velocity=1.0,
                    acceleration=0.0,
                )
                for i in range(0, 100)
            ]
        )
        criterion = BrakingCriterion()
        matches, time_step = criterion.matches(scenario, test_obstacle)
        assert matches is False
        assert time_step < 0


class TestLaneChangeCriterion:
    def test_should_not_match_if_on_same_lanelet(self):
        scenario = Scenario(dt=0.1)
        lanelet = Lanelet(
            left_vertices=np.array([[0.0, 0.0], [0.0, 10.0]]),
            center_vertices=np.array([[2.0, 0.0], [2.0, 10.0]]),
            right_vertices=np.array([[4.0, 0.0], [4.0, 10.0]]),
            lanelet_id=10,
        )
        scenario.add_objects(lanelet)
        test_obstacle = create_test_obstacle_with_trajectory(
            [
                PMState(time_step=1, position=np.array([2.0, 0.0]), velocity=12.0),
                PMState(time_step=2, position=np.array([2.0, 4.0]), velocity=12.0),
                PMState(time_step=3, position=np.array([2.0, 6.0]), velocity=12.0),
                PMState(time_step=4, position=np.array([2.0, 8.0]), velocity=12.0),
            ]
        )
        criterion = LaneChangeCriterion()
        matches, time_step = criterion.matches(scenario, test_obstacle)
        assert matches is False
        assert time_step < 0

    def test_should_match_if_ego_vehicle_changes_lane(self):
        scenario = Scenario(dt=0.1)
        lanelet0 = Lanelet(
            left_vertices=np.array([[0.0, 0.0], [0.0, 10.0]]),
            center_vertices=np.array([[2.0, 0.0], [2.0, 10.0]]),
            right_vertices=np.array([[4.0, 0.0], [4.0, 10.0]]),
            adjacent_right=11,
            adjacent_right_same_direction=True,
            lanelet_id=10,
        )
        scenario.add_objects(lanelet0)
        lanelet1 = Lanelet(
            left_vertices=np.array([[4.0, 0.0], [0.0, 10.0]]),
            center_vertices=np.array([[6.0, 0.0], [6.0, 10.0]]),
            right_vertices=np.array([[8.0, 0.0], [8.0, 10.0]]),
            adjacent_left=10,
            adjacent_left_same_direction=True,
            lanelet_id=11,
        )
        scenario.add_objects(lanelet1)
        test_obstacle = create_test_obstacle_with_trajectory(
            [
                PMState(time_step=1, position=np.array([2.0, 0.0]), velocity=12.0),
                PMState(time_step=2, position=np.array([3.0, 2.0]), velocity=12.0),
                PMState(time_step=3, position=np.array([4.0, 4.0]), velocity=12.0),
                PMState(time_step=4, position=np.array([5.0, 6.0]), velocity=12.0),
                PMState(time_step=5, position=np.array([6.0, 8.0]), velocity=12.0),
                PMState(time_step=6, position=np.array([6.0, 10.0]), velocity=12.0),
            ]
        )
        criterion = LaneChangeCriterion()
        matches, time_step = criterion.matches(scenario, test_obstacle)
        assert matches is True
        assert time_step == 3


class TestMinimumVelocityFilter:
    def test_should_reject_if_no_state_reach_minimum_velocity(self):
        scenario = Scenario(dt=0.1)
        ego_vehicle = create_test_obstacle_with_trajectory(
            [PMState(time_step=2 + i, velocity=13.0) for i in range(0, 20)]
        )
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=5)
        filter = MinimumVelocityFilter(min_ego_velocity=23.5)
        assert (
            filter.matches(scenario, scenario_time_steps=150, ego_vehicle_maneuver=maneuver)
            is False
        )
        filter = MinimumVelocityFilter(min_ego_velocity=20)
        assert (
            filter.matches(scenario, scenario_time_steps=10, ego_vehicle_maneuver=maneuver) is False
        )

    def test_should_accept_if_ego_vehicle_exactly_matches_minimum_velocity_at_least_once(self):
        scenario = Scenario(dt=0.1)
        state_list = [PMState(time_step=2 + i, velocity=13.5) for i in range(0, 10)]
        state_list.append(PMState(time_step=22, velocity=30.0))
        state_list.extend([PMState(time_step=23 + i, velocity=13.0) for i in range(0, 10)])
        ego_vehicle = create_test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=5)
        filter = MinimumVelocityFilter(min_ego_velocity=23.5)
        assert filter.matches(scenario, scenario_time_steps=150, ego_vehicle_maneuver=maneuver)
        filter = MinimumVelocityFilter(min_ego_velocity=29.0)
        assert filter.matches(scenario, scenario_time_steps=20, ego_vehicle_maneuver=maneuver)

    def test_should_reject_if_maneuver_start_time_is_after_state_that_reaches_minimum_velocity(
        self,
    ):
        scenario = Scenario(dt=0.1)
        state_list = [PMState(time_step=2 + i, velocity=30) for i in range(0, 10)]
        state_list.extend([PMState(time_step=12 + i, velocity=13.0) for i in range(0, 10)])
        ego_vehicle = create_test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=14)
        filter = MinimumVelocityFilter(min_ego_velocity=23.5)
        assert (
            filter.matches(scenario, scenario_time_steps=150, ego_vehicle_maneuver=maneuver)
            is False
        )


class TestLongEnoughManeuverFilter:
    def test_should_reject_maneuver_that_is_not_long_enough(self):
        scenario = Scenario(dt=0.1)
        state_list = [PMState(time_step=2)]
        ego_vehicle = create_test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=5)
        filter = LongEnoughManeuverFilter()
        assert (
            filter.matches(scenario, scenario_time_steps=150, ego_vehicle_maneuver=maneuver)
            is False
        )

    def test_should_accept_maneuver_that_is_exactly_long_enough(self):
        scenario = Scenario(dt=0.1)
        state_list = [PMState(time_step=2 + i) for i in range(0, 10)]
        ego_vehicle = create_test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=2)
        filter = LongEnoughManeuverFilter()
        assert filter.matches(scenario, scenario_time_steps=9, ego_vehicle_maneuver=maneuver)

    def test_should_reject_maneuver_that_starts_outside_of_trajectory(self):
        scenario = Scenario(dt=0.1)
        state_list = [PMState(time_step=2 + i) for i in range(0, 10)]
        ego_vehicle = create_test_obstacle_with_trajectory(state_list)
        maneuver = EgoVehicleManeuver(ego_vehicle, start_time=20)
        filter = LongEnoughManeuverFilter()
        assert (
            filter.matches(scenario, scenario_time_steps=100, ego_vehicle_maneuver=maneuver)
            is False
        )
