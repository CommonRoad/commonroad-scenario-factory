import numpy as np
from commonroad.scenario.intersection import Intersection, IntersectionIncomingElement
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.traffic_light import TrafficLight
from commonroad.scenario.traffic_sign import TrafficSign

from scenario_factory.globetrotter.clustering import (
    extract_forking_points,
    relevant_intersections,
    relevant_traffic_lights,
    relevant_traffic_signs,
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
        lanelets = [
            # The lanelet from which the forking point will be selected
            Lanelet(
                left_vertices=np.array([[0.0, 0.0], [0.0, 5.0]]),
                center_vertices=np.array([[2.5, 0.0], [2.5, 5.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 5.0]]),
                lanelet_id=0,
                successor=[1, 2],
            ),
            # The two successor lanelets. Their physical properties are unimportant
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=1,
                predecessor=[0],
            ),
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=2,
                predecessor=[0],
            ),
        ]
        forking_points = extract_forking_points(lanelets)
        assert len(forking_points) == 1
        # The algorithm should select the end point
        assert (forking_points[0] == np.array([2.5, 5.0])).all()

    def test_returns_start_as_one_point_for_combining_lanelet(self):
        lanelets = [
            # The lanelet from which the forking point will be selected
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=0,
                predecessor=[1, 2],
            ),
            # The two predecessor lanelets. Their physical properties are unimportant
            Lanelet(
                left_vertices=np.array([[0.0, 0.1], [0.0, 5.1]]),
                center_vertices=np.array([[2.5, 0.1], [2.5, 5.2]]),
                right_vertices=np.array([[5.0, 0.1], [5.0, 5.1]]),
                lanelet_id=1,
                successor=[0],
            ),
            Lanelet(
                left_vertices=np.array([[0.1, -0.1], [0.1, 5.0]]),
                center_vertices=np.array([[2.5, 0.1], [2.6, 5.1]]),
                right_vertices=np.array([[5.1, -0.1], [5.1, 5.0]]),
                lanelet_id=2,
                successor=[0],
            ),
        ]
        forking_points = extract_forking_points(lanelets)
        assert len(forking_points) == 1
        # The algorithm should select the end point
        assert (forking_points[0] == np.array([2.5, 5.0])).all()


class TestRelevantTrafficSigns:
    def test_empty(self):
        assert len(relevant_traffic_signs([], [])) == 0

    def test_no_referenced_traffic_signs(self):
        lanelets = [
            # The lanelet from which the forking point will be selected
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=0,
            )
        ]
        traffic_signs = [
            TrafficSign(
                traffic_sign_id=0, traffic_sign_elements=[], first_occurrence={0}, position=np.array([0.0, 0.0])
            )
        ]

        assert len(relevant_traffic_signs(traffic_signs, lanelets)) == 0

    def test_referenced_traffic_sign(self):
        lanelets = [
            # The lanelet from which the forking point will be selected
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=0,
                traffic_signs={0},
            ),
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=1,
                traffic_signs={0},
            ),
        ]
        traffic_signs = [
            TrafficSign(
                traffic_sign_id=0, traffic_sign_elements=[], first_occurrence={0}, position=np.array([0.0, 0.0])
            ),
            TrafficSign(
                traffic_sign_id=1, traffic_sign_elements=[], first_occurrence={2}, position=np.array([0.0, 0.0])
            ),
        ]
        assert len(relevant_traffic_signs(traffic_signs, lanelets)) == 1


class TestRelevantTrafficLights:
    def test_empty(self):
        assert len(relevant_traffic_lights([], [])) == 0

    def test_no_referenced_traffic_lights(self):
        lanelets = [
            # The lanelet from which the forking point will be selected
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=0,
            )
        ]
        traffic_lights = [TrafficLight(traffic_light_id=0, position=np.array([0.0, 0.0]))]

        assert len(relevant_traffic_lights(traffic_lights, lanelets)) == 0

    def test_referenced_traffic_lights_but_no_successor(self):
        lanelets = [
            # The lanelet from which the forking point will be selected
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=0,
                traffic_lights={0},
            )
        ]
        traffic_lights = [TrafficLight(traffic_light_id=0, position=np.array([0.0, 0.0]))]

        assert len(relevant_traffic_lights(traffic_lights, lanelets)) == 0

    def test_referenced_traffic_lights_and_successor(self):
        lanelets = [
            # The lanelet from which the forking point will be selected
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=0,
                traffic_lights={0},
                successor=[1],
            )
        ]
        traffic_lights = [TrafficLight(traffic_light_id=0, position=np.array([0.0, 0.0]))]

        assert len(relevant_traffic_lights(traffic_lights, lanelets)) == 1


class TestRelevantIntersections:
    def test_empty(self):
        assert len(relevant_intersections([], [])) == 0

    def test_empty_lanelets(self):
        intersections = [
            Intersection(
                intersection_id=0, incomings=[IntersectionIncomingElement(incoming_id=1, incoming_lanelets={3})]
            )
        ]

        assert len(relevant_intersections(intersections, [])) == 0

    def test_referenced_lanelet(self):
        intersections = [
            Intersection(
                intersection_id=0, incomings=[IntersectionIncomingElement(incoming_id=1, incoming_lanelets={0})]
            )
        ]

        lanelets = [
            Lanelet(
                left_vertices=np.array([[0.0, 5.0], [0.0, 10.0]]),
                center_vertices=np.array([[2.5, 5.0], [2.5, 10.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 10.0]]),
                lanelet_id=0,
            )
        ]

        assert len(relevant_intersections(intersections, lanelets)) == 1
