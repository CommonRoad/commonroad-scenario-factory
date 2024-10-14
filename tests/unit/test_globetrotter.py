import numpy as np
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.traffic_sign import TrafficSignIDGermany

from scenario_factory.builder import LaneletNetworkBuilder, ScenarioBuilder
from scenario_factory.globetrotter.clustering import (
    cut_intersection_from_scenario,
    extract_forking_points,
)


class TestExtractForkingPoints:
    def test_returns_no_points_for_empty_lanelet_network(self):
        assert len(extract_forking_points([])) == 0

    def test_returns_no_points_for_one_lanelet(self):
        lanelets = [
            Lanelet(
                left_vertices=np.array([[0.0, 0.0], [0.0, 5.0]]),
                center_vertices=np.array([[2.5, 0.0], [2.5, 5.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 5.0]]),
                lanelet_id=0,
            )
        ]
        assert len(extract_forking_points(lanelets)) == 0

    def test_returns_end_as_one_point_for_forking_lanelet(self):
        lanelet_network_builder = LaneletNetworkBuilder()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 5.0))
        lanelet2 = lanelet_network_builder.add_lanelet(start=(10.0, 10.0), end=(10.0, 20.0))
        lanelet3 = lanelet_network_builder.add_lanelet(start=(-10.0, 10.0), end=(-10.0, 20.0))
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet1, lanelet2)
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet1, lanelet3)
        lanelet_network = lanelet_network_builder.build()

        forking_points = extract_forking_points(lanelet_network.lanelets)
        assert len(forking_points) == 1
        # The algorithm should select the end point
        assert (forking_points[0] == np.array([0.0, 5.0])).all()

    def test_returns_start_as_one_point_for_combining_lanelet(self):
        lanelet_network_builder = LaneletNetworkBuilder()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 20.0), end=(0.0, 30.0))
        lanelet2 = lanelet_network_builder.add_lanelet(start=(10.0, 0.0), end=(10.0, 10.0))
        lanelet3 = lanelet_network_builder.add_lanelet(start=(-10.0, 0.0), end=(-10.0, 10.0))
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet2, lanelet1)
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet3, lanelet1)
        lanelet_network = lanelet_network_builder.build()

        forking_points = extract_forking_points(lanelet_network.lanelets)
        assert len(forking_points) == 1
        # The algorithm should select the start point
        assert (forking_points[0] == np.array([0.0, 20.0])).all()


class TestCutIntersectionFromScenario:
    def test_includes_only_lanelets_in_radius(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        # Lanelets crossing the center
        lanelet1 = lanelet_network_builder.add_lanelet(start=(-50.0, -25.0), end=(50.0, 25.0))
        lanelet2 = lanelet_network_builder.add_lanelet(start=(-50.0, 25.0), end=(50.0, -25.0))
        lanelet3 = lanelet_network_builder.add_lanelet(start=(0.0, 50.0), end=(0.0, -50.0))
        lanelet4 = lanelet_network_builder.add_lanelet(start=(-50.0, 0.0), end=(50.0, 0.0))
        # Lanelets outside of the circle
        lanelet5 = lanelet_network_builder.add_lanelet(start=(-50.0, 50.0), end=(50.0, 50.0))
        lanelet6 = lanelet_network_builder.add_lanelet(start=(-50.0, 50.0), end=(50.0, 50.0))
        lanelet7 = lanelet_network_builder.add_lanelet(start=(-50.0, 50.0), end=(-50.0, -50.0))
        lanelet8 = lanelet_network_builder.add_lanelet(start=(-50.0, -50.0), end=(50.0, -50.0))
        # Lanelets outside of the circle but connected to lanelets inside the circle
        lanelet9 = lanelet_network_builder.add_lanelet(start=(0.0, 100.0), end=(0.0, 50.0))
        lanelet_network_builder.connect(lanelet9, lanelet3)
        lanelet10 = lanelet_network_builder.add_lanelet(start=(0.0, -50.0), end=(0.0, -100.0))
        lanelet_network_builder.connect(lanelet10, lanelet3)
        scenario = scenario_builder.build()

        new_scenario = cut_intersection_from_scenario(
            scenario, np.array([0.0, 0.0]), max_distance=20, intersection_cut_margin=5
        )
        for lanelet in [lanelet1, lanelet2, lanelet3, lanelet4]:
            assert new_scenario.lanelet_network.find_lanelet_by_id(lanelet.lanelet_id) is not None

        for lanelet in [lanelet5, lanelet6, lanelet7, lanelet8]:
            assert new_scenario.lanelet_network.find_lanelet_by_id(lanelet.lanelet_id) is None

    def test_includes_only_intersections_in_radius(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, -20.0), end=(0.0, -10.0))
        lanelet2 = lanelet_network_builder.add_lanelet(start=(0.0, 10.0), end=(0.0, 20.0))
        connection1 = lanelet_network_builder.create_straight_connecting_lanelet(lanelet1, lanelet2)
        lanelet3 = lanelet_network_builder.add_lanelet(start=(10.0, 0.0), end=(20.0, 0.0))
        lanelet4 = lanelet_network_builder.add_lanelet(start=(30.0, 0.0), end=(40.0, 0.0))
        lanelet5 = lanelet_network_builder.add_lanelet(start=(30.0, 10.0), end=(30.0, 20.0))
        connection2 = lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet3)
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet3, lanelet4)
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet3, lanelet5)
        (
            lanelet_network_builder.create_intersection()
            .create_incoming()
            .add_incoming_lanelet(lanelet1)
            .connect_straight(lanelet2)
            .connect_right(lanelet3)
        )
        (
            lanelet_network_builder.create_intersection()
            .create_incoming()
            .add_incoming_lanelet(lanelet3)
            .connect_straight(lanelet4)
        )
        scenario = scenario_builder.build()
        new_scenario = cut_intersection_from_scenario(
            scenario, np.array([0.0, 0.0]), max_distance=15, intersection_cut_margin=5
        )

        assert len(new_scenario.lanelet_network.intersections) == 1
        kept_intersection = new_scenario.lanelet_network.intersections[0]
        assert len(kept_intersection.incomings) == 1
        assert lanelet1.lanelet_id in kept_intersection.incomings[0].incoming_lanelets
        assert len(kept_intersection.incomings[0].successors_straight) == 1
        assert connection1.lanelet_id in kept_intersection.incomings[0].successors_straight
        assert len(kept_intersection.incomings[0].successors_right) == 1
        assert connection2.lanelet_id in kept_intersection.incomings[0].successors_right

    def test_only_includes_traffic_signs_in_radius(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 20.0))
        (
            lanelet_network_builder.create_traffic_sign()
            .add_element(TrafficSignIDGermany.WARNING_SLIPPERY_ROAD)
            .for_lanelet(lanelet1)
        )
        lanelet2 = lanelet_network_builder.add_lanelet(start=(0.0, 20.0), end=(0.0, 40.0))
        (
            lanelet_network_builder.create_traffic_sign()
            .add_element(TrafficSignIDGermany.WARNING_STEEP_HILL_DOWNWARDS)
            .for_lanelet(lanelet2)
        )
        scenario = scenario_builder.build()
        new_scenario = cut_intersection_from_scenario(
            scenario, np.array([0.0, 0.0]), max_distance=10, intersection_cut_margin=5
        )

        assert len(new_scenario.lanelet_network.traffic_signs) == 1
        assert (
            len(new_scenario.lanelet_network.find_lanelet_by_id(lanelet1.lanelet_id).traffic_signs)
            == 1
        )

    def test_only_includes_traffic_lights_in_radius(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        # The first traffic light (inside the radius)
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 20.0))
        lanelet_network_builder.create_traffic_light().for_lanelet(lanelet1)

        # The second traffic light (outside the radius)
        lanelet2 = lanelet_network_builder.add_lanelet(start=(0.0, 20.0), end=(0.0, 40.0))
        lanelet_network_builder.create_traffic_light().for_lanelet(lanelet2)

        scenario = scenario_builder.build()

        new_scenario = cut_intersection_from_scenario(
            scenario, np.array([0.0, 0.0]), max_distance=10, intersection_cut_margin=5
        )

        assert len(new_scenario.lanelet_network.traffic_lights) == 1
        assert (
            len(new_scenario.lanelet_network.find_lanelet_by_id(lanelet1.lanelet_id).traffic_lights)
            == 1
        )
