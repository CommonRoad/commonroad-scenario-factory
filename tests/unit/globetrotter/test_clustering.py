import os.path

import numpy as np
import pytest

from scenario_factory.globetrotter import extract_intersections_from_scenario
from scenario_factory.globetrotter.clustering import (
    centroids_and_distances,
    cut_intersection_from_scenario,
    extract_forking_points,
    find_clusters_agglomerative,
    generate_intersections,
    get_distance_to_outer_point,
    relevant_intersections,
    relevant_traffic_lights,
    relevant_traffic_signs,
)
from tests.resources.interface import (
    ResourceType,
    get_test_dataset_json,
    load_cr_lanelet_network_from_file,
    load_cr_scenario_from_file,
)


class ClusteringTestEntry:
    label: str
    points: list[tuple[float, float]]
    expected_labels: list[int]

    def __init__(self, serial):
        self.label = serial["label"]
        self.points = [(serial_point["x"], serial_point["y"]) for serial_point in serial["points"]]
        self.expected_labels = serial["expected_labels"]


def get_clustering_test_dataset():
    return [
        ClusteringTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "clustering")
        )
    ]


class OuterDistanceTestEntry:
    label: str
    center: tuple[float, float]
    cluster: list[tuple[float, float]]
    expected_distance: float

    def __init__(self, serial):
        self.label = serial["label"]
        self.center = (serial["center"]["x"], serial["center"]["y"])
        self.cluster = [
            (serial_point["x"], serial_point["y"]) for serial_point in serial["cluster"]
        ]
        self.expected_distance = serial["expected_distance"]


def get_outer_distance_test_dataset():
    return [
        OuterDistanceTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "outer_distance")
        )
    ]


class CentroidTestEntry:
    label: str
    labels: list[int]
    points: list[tuple[float, float]]
    expected_result: dict[
        int, tuple[tuple[float, float], float, list[tuple[float, float]]]
    ]  # Dictionary of (centroid, distance, points) for each cluster

    def __init__(self, serial):
        self.label = serial["label"]
        self.labels = serial["labels"]
        self.points = [(serial_point["x"], serial_point["y"]) for serial_point in serial["points"]]
        self.expected_result = {}
        for serial_result_entry in serial["expected_result"]:
            centroid = (serial_result_entry["centroid"]["x"], serial_result_entry["centroid"]["y"])
            distance = serial_result_entry["distance"]
            points = [
                (serial_point["x"], serial_point["y"])
                for serial_point in serial_result_entry["points"]
            ]
            self.expected_result[serial_result_entry["key"]] = (centroid, distance, points)


def get_centroid_test_dataset():
    return [
        CentroidTestEntry(serial)
        for serial in get_test_dataset_json(os.path.join("globetrotter", "clustering", "centroid"))
    ]


class TrafficSignsTestEntry:
    label: str
    lanelet_network: str
    traffic_signs: list[int]
    expected_traffic_signs: list[int]

    def __init__(self, serial):
        self.label = serial["label"]
        self.lanelet_network = serial["lanelet_network"]
        self.traffic_signs = serial["traffic_signs"]
        self.expected_traffic_signs = serial["expected_traffic_signs"]


def get_traffic_signs_test_dataset():
    return [
        TrafficSignsTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "traffic_signs")
        )
    ]


class TrafficLightsTestEntry:
    label: str
    lanelet_network: str
    traffic_lights: list[int]
    expected_traffic_lights: list[int]

    def __init__(self, serial):
        self.label = serial["label"]
        self.lanelet_network = serial["lanelet_network"]
        self.traffic_lights = serial["traffic_lights"]
        self.expected_traffic_lights = serial["expected_traffic_lights"]


def get_traffic_lights_test_dataset():
    return [
        TrafficLightsTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "traffic_lights")
        )
    ]


class IntersectionsTestEntry:
    label: str
    lanelet_network: str
    intersections: list[int]
    expected_intersections: list[int]

    def __init__(self, serial):
        self.label = serial["label"]
        self.lanelet_network = serial["lanelet_network"]
        self.intersections = serial["intersections"]
        self.expected_intersections = serial["expected_intersections"]


def get_intersections_test_dataset():
    return [
        IntersectionsTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "intersections")
        )
    ]


class CutIntersectionTestEntry:
    label: str
    scenario: str
    center: tuple[float, float]
    max_distance: float
    expected_scenario: str

    def __init__(self, serial):
        self.label = serial["label"]
        self.scenario = serial["scenario"]
        self.center = (serial["center"]["x"], serial["center"]["y"])
        self.max_distance = serial["max_distance"]
        self.expected_scenario = serial["expected_scenario"]


def get_cut_intersection_test_dataset():
    return [
        CutIntersectionTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "cut_intersection")
        )
    ]


class ForkingPointsTestEntry:
    label: str
    lanelet_network: str
    expected_forking_points: list[tuple[float, float]] | None

    def __init__(self, serial):
        self.label = serial["label"]
        self.lanelet_network = serial["lanelet_network"]
        self.expected_forking_points = (
            None
            if serial["expected_forking_points"] is None
            else [
                (serial_point["x"], serial_point["y"])
                for serial_point in serial["expected_forking_points"]
            ]
        )


def get_forking_points_test_dataset():
    return [
        ForkingPointsTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "forking_points")
        )
    ]


class GenerateIntersectionsTestEntry:
    label: str
    scenario: str
    forking_points: list[tuple[float, float]]
    expected_scenarios: list[str]

    def __init__(self, serial):
        self.lanelet_network = serial["lanelet_network"]
        self.scenario = serial["scenario"]
        self.forking_points = [
            (serial_point["x"], serial_point["y"]) for serial_point in serial["forking_points"]
        ]
        self.expected_scenarios = serial["expected_scenarios"]


def get_generate_intersections_test_dataset():
    return [
        GenerateIntersectionsTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "clustering", "generate_intersections")
        )
    ]


_CLUSTERING_TEST_DATASET = get_clustering_test_dataset()
_OUTER_DISTANCE_TEST_DATASET = get_outer_distance_test_dataset()
_CENTROID_TEST_DATASET = get_centroid_test_dataset()
_TRAFFIC_SIGNS_TEST_DATASET = get_traffic_signs_test_dataset()
_TRAFFIC_LIGHTS_TEST_DATASET = get_traffic_lights_test_dataset()
_INTERSECTIONS_TEST_DATASET = get_intersections_test_dataset()
_CUT_INTERSECTION_TEST_DATASET = get_cut_intersection_test_dataset()
_FORKING_POINTS_TEST_DATASET = get_forking_points_test_dataset()
_GENERATE_INTERSECTIONS_TEST_DATASET = get_generate_intersections_test_dataset()


class TestGlobals:
    @pytest.mark.parametrize("entry", _CLUSTERING_TEST_DATASET)
    def test_find_clusters_agglomerative(self, entry: ClusteringTestEntry):
        labels = list(find_clusters_agglomerative(np.array(entry.points)).labels_)
        assert (
            labels == entry.expected_labels
        ), f"Expected correct clusters for entry: {entry.label}."

    @pytest.mark.parametrize("entry", _OUTER_DISTANCE_TEST_DATASET)
    def test_get_distance_to_outer_point(self, entry: OuterDistanceTestEntry):
        distance = get_distance_to_outer_point(np.array(entry.center), np.array(entry.cluster))
        assert (
            distance == entry.expected_distance
        ), f"Expected correct distance for entry: {entry.label}."

    @pytest.mark.parametrize("entry", _CENTROID_TEST_DATASET)
    def test_centroids_and_distances(self, entry: CentroidTestEntry):
        centroids, distances, clusters = centroids_and_distances(
            np.array(entry.labels), np.array(entry.points)
        )
        assert (
            len(centroids) == len(distances) == len(clusters) == len(entry.expected_result)
        ), f"Expected precisely one result per cluster for entry: {entry.label}."
        for key in entry.expected_result:
            exp_centroid, exp_distance, exp_cluster = entry.expected_result[key]
            assert np.all(
                np.array(exp_centroid) == centroids[key]
            ), f"Expected matching centroids for cluster {key} for entry: {entry.label}."
            assert (
                exp_distance == distances[key]
            ), f"Expected matching distance for cluster {key} for entry: {entry.label}."
            assert np.all(
                np.array(exp_cluster) == np.array(clusters[key])
            ), f"Expected matching member points for cluster {key} for entry {entry.label}."

    @pytest.mark.parametrize("entry", _TRAFFIC_SIGNS_TEST_DATASET)
    def test_relevant_traffic_signs(self, entry: TrafficSignsTestEntry):
        lanelet_network = load_cr_lanelet_network_from_file(
            ResourceType.CR_LANELET_NETWORK.get_folder() / entry.lanelet_network
        )
        input_traffic_signs = [
            ts for ts in lanelet_network.traffic_signs if ts.traffic_sign_id in entry.traffic_signs
        ]
        expected_traffic_signs = {
            ts.traffic_sign_id: ts
            for ts in lanelet_network.traffic_signs
            if ts.traffic_sign_id in entry.expected_traffic_signs
        }
        traffic_signs = relevant_traffic_signs(input_traffic_signs, lanelet_network.lanelets)
        assert len(traffic_signs) == len(
            expected_traffic_signs
        ), f"Expected to result in correct number of traffic signs for entry {entry.label}."
        for ts in traffic_signs:
            assert (
                ts is expected_traffic_signs[ts.traffic_sign_id]
            ), f"Filter passed unexpected traffic sign for entry {entry.label}."

    @pytest.mark.parametrize("entry", _TRAFFIC_LIGHTS_TEST_DATASET)
    def test_relevant_traffic_lights(self, entry: TrafficLightsTestEntry):
        lanelet_network = load_cr_lanelet_network_from_file(
            ResourceType.CR_LANELET_NETWORK.get_folder() / entry.lanelet_network
        )
        input_traffic_lights = [
            tl
            for tl in lanelet_network.traffic_lights
            if tl.traffic_light_id in entry.traffic_lights
        ]
        expected_traffic_lights = {
            tl.traffic_light_id: tl
            for tl in lanelet_network.traffic_lights
            if tl.traffic_light_id in entry.expected_traffic_lights
        }

        traffic_lights = relevant_traffic_lights(input_traffic_lights, lanelet_network.lanelets)
        assert len(traffic_lights) == len(
            expected_traffic_lights
        ), f"Expected to result in correct number of traffic lights for entry {entry.label}."
        for tl in traffic_lights:
            assert (
                tl is expected_traffic_lights[tl.traffic_light_id]
            ), f"Filter passed unexpected traffic light for entry {entry.label}."

    @pytest.mark.parametrize("entry", _INTERSECTIONS_TEST_DATASET)
    def test_relevant_intersections(self, entry: IntersectionsTestEntry):
        lanelet_network = load_cr_lanelet_network_from_file(
            ResourceType.CR_LANELET_NETWORK.get_folder() / entry.lanelet_network
        )
        input_intersections = [
            ints
            for ints in lanelet_network.intersections
            if ints.intersection_id in entry.intersections
        ]
        expected_intersections = {
            ints.intersection_id: ints
            for ints in lanelet_network.intersections
            if ints.intersection_id in entry.expected_intersections
        }
        intersections = relevant_intersections(input_intersections, lanelet_network.lanelets)
        assert len(intersections) == len(
            expected_intersections
        ), f"Expected to result in correct number of intersections for entry {entry.label}."
        for ints in intersections:
            assert (
                ints is expected_intersections[ints.intersection_id]
            ), f"Filter passed unexpected intersection for entry {entry.label}."

    @pytest.mark.parametrize("entry", _CUT_INTERSECTION_TEST_DATASET)
    def test_cut_intersections_from_scenario(self, entry: CutIntersectionTestEntry):
        # TODO: Conceive test examples
        input_scenario = load_cr_scenario_from_file(
            ResourceType.CR_SCENARIO.get_folder() / entry.scenario
        )
        comp_scenario = cut_intersection_from_scenario(
            input_scenario, np.array(entry.center), entry.max_distance
        )
        exp_scenario = load_cr_scenario_from_file(
            ResourceType.CR_SCENARIO.get_folder() / entry.expected_scenario
        )
        assert comp_scenario == exp_scenario, f"Expected correct scenario for entry {entry.label}."

    @pytest.mark.parametrize("entry", _FORKING_POINTS_TEST_DATASET)
    def test_extract_forking_points(self, entry: ForkingPointsTestEntry):
        lanelet_network = load_cr_lanelet_network_from_file(
            ResourceType.CR_LANELET_NETWORK.get_folder() / entry.lanelet_network
        )
        if entry.expected_forking_points is None:
            try:
                extract_forking_points(lanelet_network.lanelets)
            except ValueError:
                pass
            else:
                assert (
                    False
                ), f"Expected forking point extraction to throw an error for entry {entry.label}."
        else:
            comp_forking_points = extract_forking_points(lanelet_network.lanelets)
            assert np.all(
                comp_forking_points == np.array(entry.expected_forking_points)
            ), f"Expected correct forking points for entry {entry.label}."

    @pytest.mark.parametrize("entry", _GENERATE_INTERSECTIONS_TEST_DATASET)
    def test_generate_intersections(self, entry: GenerateIntersectionsTestEntry):
        # TODO: Conceive test examples
        scenario = load_cr_scenario_from_file(
            ResourceType.CR_SCENARIO.get_folder() / entry.scenario
        )
        exp_scenarios = [
            load_cr_scenario_from_file(ResourceType.CR_SCENARIO.get_folder() / result_scenario)
            for result_scenario in entry.expected_scenarios
        ]
        comp_scenarios = generate_intersections(scenario, np.array(entry.forking_points))
        assert (
            exp_scenarios == comp_scenarios
        ), f"Expected correct intersection-scenario generation for entry {entry.label}."

    @pytest.mark.parametrize("entry", _GENERATE_INTERSECTIONS_TEST_DATASET)
    def test_extract_intersections_from_scenario(self, entry: GenerateIntersectionsTestEntry):
        # TODO: Conceive test examples
        scenario = load_cr_scenario_from_file(
            ResourceType.CR_SCENARIO.get_folder() / entry.scenario
        )
        exp_scenarios = [
            load_cr_scenario_from_file(ResourceType.CR_SCENARIO.get_folder() / result_scenario)
            for result_scenario in entry.expected_scenarios
        ]
        comp_scenarios = extract_intersections_from_scenario(scenario)
        assert (
            exp_scenarios == comp_scenarios
        ), f"Expected correct intersection-scenario generation for entry {entry.label}."
