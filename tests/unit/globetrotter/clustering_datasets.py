import numpy as np
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.scenario import Scenario

from tests.automation.datasets import Dataset
from tests.automation.validation import TestCase
from tests.helpers.lanelet_network import UsefulLaneletNetworks

# ---------------------------------
# Entry Models
# ---------------------------------


class ClusteringTestCase(TestCase):
    points: np.ndarray
    expected_labels: np.ndarray


class OuterDistanceTestCase(TestCase):
    center: np.ndarray
    cluster: np.ndarray
    expected_distance: float


class CentroidTestCase(TestCase):
    labels: np.ndarray
    points: np.ndarray
    expected_result: dict[
        int, tuple[np.ndarray, float, np.ndarray]
    ]  # Map: cluster -> (centroid, distance, points)


class CutIntersectionTestCase(TestCase):
    scenario: Scenario
    center: np.ndarray
    max_distance: float
    expected_scenario: Scenario


class ForkingPointsTestCase(TestCase):
    lanelet_network: LaneletNetwork
    expected_forking_points: np.ndarray | None


class GenerateIntersectionsTestCase(TestCase):
    scenario: Scenario
    forking_points: np.ndarray
    expected_scenarios: list[Scenario]  # Ordered as the forking points


# ---------------------------------
# Dynamic Datasets
# ---------------------------------


CLUSTERING_TEST_DATASET = Dataset(
    [
        ClusteringTestCase(
            label="generic1",
            points=np.array([[0, 0], [2, 0], [0, 3], [60, 0], [63, 0], [61, 3]]),
            expected_labels=np.array([1, 1, 1, 0, 0, 0]),
        ),
        ClusteringTestCase(
            label="generic2",
            points=np.array(
                [[0, 0], [2, 0], [0, 2], [60, 0], [62, 0], [60, 2], [60, 60], [62, 60], [60, 62]]
            ),
            expected_labels=np.array([2, 2, 2, 1, 1, 1, 0, 0, 0]),
        ),
    ]
)

OUTER_DISTANCE_TEST_DATASET = Dataset(
    [
        OuterDistanceTestCase(
            label="generic1",
            cluster=np.array([[0, 0], [1, 1], [3, 1]]),
            center=np.array([1, 1]),
            expected_distance=2,
        ),
        OuterDistanceTestCase(
            label="generic2", cluster=np.array([]), center=np.array([0, 0]), expected_distance=0
        ),
    ]
)

CENTROID_TEST_DATASET = Dataset(
    [
        CentroidTestCase(
            label="generic1",
            labels=np.array([2, 2, 2, 1, 1, 1, 0, 0, 0]),
            points=np.array(
                [[0, 0], [3, 0], [0, 3], [60, 0], [63, 0], [60, 3], [60, 60], [63, 60], [60, 63]]
            ),
            expected_result={
                2: (np.array([1, 1]), 2.23606797749979, np.array([[0, 0], [3, 0], [0, 3]])),
                1: (np.array([61, 1]), 2.23606797749979, np.array([[60, 0], [63, 0], [60, 3]])),
                0: (np.array([61, 61]), 2.23606797749979, np.array([[60, 60], [63, 60], [60, 63]])),
            },
        )
    ]
)

FORKING_POINTS_TEST_DATASET = Dataset(
    [
        ForkingPointsTestCase(
            label="empty_network",
            lanelet_network=UsefulLaneletNetworks.empty_no_meta(),
            expected_forking_points=np.array([]),
        ),
        ForkingPointsTestCase(
            label="one_split_network",
            lanelet_network=UsefulLaneletNetworks.one_split_no_meta(),
            expected_forking_points=np.array([[20, -5]]),
        ),
        ForkingPointsTestCase(
            label="malformed_one_split_network",
            lanelet_network=UsefulLaneletNetworks.malformed_one_split_no_meta(),
            expected_forking_points=None,
        ),
    ]
)
