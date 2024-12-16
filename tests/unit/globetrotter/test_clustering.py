import numpy as np
import pytest
from commonroad.scenario.lanelet import LaneletNetwork

from scenario_factory.globetrotter.clustering import (
    centroids_and_distances,
    extract_forking_points,
    find_clusters_agglomerative,
    get_distance_to_outer_point,
)
from tests.automation.mark import with_dataset
from tests.unit.globetrotter.clustering_datasets import (
    CENTROID_TEST_DATASET,
    CLUSTERING_TEST_DATASET,
    FORKING_POINTS_TEST_DATASET,
    OUTER_DISTANCE_TEST_DATASET,
)


class TestGlobals:
    @with_dataset(CLUSTERING_TEST_DATASET)
    def test_find_clusters_agglomerative(
        self, label: str, points: np.ndarray, expected_labels: np.ndarray
    ):
        labels = find_clusters_agglomerative(points).labels_
        assert np.allclose(
            labels, expected_labels
        ), f"Expected correct clusters for entry: {label}."

    @with_dataset(OUTER_DISTANCE_TEST_DATASET)
    def test_get_distance_to_outer_point(
        self, label: str, cluster: np.ndarray, center: np.ndarray, expected_distance: float
    ):
        distance = get_distance_to_outer_point(center, cluster)
        assert distance == expected_distance, f"Expected correct distance for entry: {label}."

    @with_dataset(CENTROID_TEST_DATASET)
    def test_centroids_and_distances(
        self,
        label: str,
        points: np.ndarray,
        labels: np.ndarray,
        expected_result: dict[int, tuple[np.ndarray, float, np.ndarray]],
    ):
        centroids, distances, clusters = centroids_and_distances(labels, points)
        assert (
            len(centroids) == len(distances) == len(clusters) == len(expected_result)
        ), f"Expected precisely one result per cluster for entry: {label}."
        for key in expected_result:
            exp_centroid, exp_distance, exp_cluster = expected_result[key]
            assert np.all(
                exp_centroid == centroids[key]
            ), f"Expected matching centroids for cluster {key} for entry: {label}."
            assert (
                exp_distance == distances[key]
            ), f"Expected matching distance for cluster {key} for entry: {label}."
            assert np.all(
                exp_cluster == clusters[key]
            ), f"Expected matching member points for cluster {key} for entry {label}."

    @with_dataset(
        FORKING_POINTS_TEST_DATASET,
        skips=[
            # TODO: Check for malformed intersections when generating forking points (Issue: ??)
            "malformed_one_split_network"
        ],
    )
    def test_extract_forking_points(
        self, label: str, lanelet_network: LaneletNetwork, expected_forking_points: np.ndarray
    ):
        if expected_forking_points is None:
            with pytest.raises(ValueError):
                extract_forking_points(lanelet_network.lanelets)
        else:
            comp_forking_points = extract_forking_points(lanelet_network.lanelets)
            assert np.all(
                comp_forking_points == expected_forking_points
            ), f"Expected correct forking points for entry {label}."
