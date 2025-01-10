import logging
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

import numpy as np
from commonroad.geometry.shape import Circle
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from commonroad.scenario.scenario import Scenario
from scipy.spatial import distance
from sklearn.cluster import AgglomerativeClustering

from scenario_factory.globetrotter.region import Coordinates, RegionMetadata
from scenario_factory.utils import copy_scenario

_LOGGER = logging.getLogger(__name__)


def find_clusters_agglomerative(points: np.ndarray) -> AgglomerativeClustering:
    """
    Find intersections using agglomerative clustering

    :param points: forking points used for the clustering process
    :return: Cluster with labeled forking points
    """
    metric = "euclidean"
    linkage = "single"
    distance_treshold = 35

    # cluster using SciKit's Agglomerative Clustering implementation
    cluster = AgglomerativeClustering(
        metric=metric,
        linkage=linkage,
        distance_threshold=distance_treshold,
        n_clusters=None,
    )
    cluster.fit_predict(points)

    return cluster


def get_distance_to_outer_point(center: np.ndarray, cluster: Sequence[np.ndarray]) -> float:
    """
    Euclidean distance between center and outer point
    See https://stackoverflow.com/questions/1401712/how-can-the-euclidean-distance-be-calculated-with-numpy

    :param center: The center coordinate
    :param cluster: forking points part of the intersection
    :return: Max distance between outer forking point and center
    """

    # edge case if only one forking point was found
    if len(cluster) == 1:
        return 50

    max_dis = 0
    for p in cluster:
        dist = distance.euclidean(center, p)
        max_dis = max(dist, max_dis)

    return max_dis


def centroids_and_distances(
    labels: np.ndarray, points: np.ndarray
) -> Tuple[Dict[float, np.ndarray], Dict[float, float], Dict[float, List[np.ndarray]]]:
    """
    Create dictionaries with points assigned to each cluster, the clusters' centers and max distances in each cluster

    :param labels: The resulting labels from the clustering process for each forking point
    :param points: forking points
    :return: center, max_distance and cluster dictionaries
    """

    clusters = defaultdict(list)
    centroids = dict()
    distances = dict()

    for point, cluster_n in zip(points, labels):
        # check for noise from DBSCAN
        if cluster_n != -1:
            clusters[cluster_n].append(tuple(point))

    # compute center and distances
    for key in clusters:
        centroids[key] = np.mean(clusters[key], axis=0)
        distances[key] = get_distance_to_outer_point(centroids[key], clusters[key])

    return centroids, distances, clusters


def _get_translated_scenario_coordinates(
    scenario: Scenario, translation_vector: Tuple[float, float]
) -> Coordinates:
    """
    Translate the GPS coordinates of the `scenario` such that they are offset by `translation_vector`.

    :param scenario: The reference scenario, with GPS coordinates.
    :param translation_vector: Specifies the values by which the cartesian representation of the scenario coordinates will be translated.

    :returns: A new `Coordinates` object of the translated coordinates.
    """
    original_scenario_coordinates = Coordinates.from_tuple(
        (scenario.location.gps_latitude, scenario.location.gps_longitude)
    )
    original_scenario_center_x, original_scenario_center_y = (
        original_scenario_coordinates.as_tuple_cartesian()
    )
    cut_scenario_center_x = original_scenario_center_x + translation_vector[0]
    cut_scenario_center_y = original_scenario_center_y + translation_vector[1]

    cut_scenario_coordinates = Coordinates.from_tuple_cartesian(
        (cut_scenario_center_x, cut_scenario_center_y)
    )
    return cut_scenario_coordinates


def cut_intersection_from_scenario(
    scenario: Scenario, center: np.ndarray, max_distance: float, intersection_cut_margin: int = 30
) -> Scenario:
    """
    Create new scenario from old scenario, by cutting the lanelet network around center with radius

    :param scenario: Original scenario
    :param center: Center of new scenario
    :param max_distance: Cut radius
    :return: New Scenario only containing desired intersection
    """

    radius = max_distance + intersection_cut_margin
    cut_shape = Circle(radius, center)

    # TODO: Cut static obstacles in circle and include in new scenario
    cut_lanelet_network = LaneletNetwork.create_from_lanelet_network(
        scenario.lanelet_network, cut_shape
    )

    cut_lanelet_network.cleanup_lanelet_references()
    cut_lanelet_network.cleanup_traffic_light_references()
    cut_lanelet_network.cleanup_traffic_sign_references()

    # Make sure that the center point is the new (0,0) of the scenario
    cut_lanelet_network.translate_rotate(-center, angle=0.0)

    cut_scenario = copy_scenario(
        scenario,
        copy_lanelet_network=False,
        copy_dynamic_obstacles=False,
        copy_static_obstacles=False,
        copy_environment_obstacles=False,
        copy_phantom_obstacles=False,
    )
    cut_scenario.add_objects(cut_lanelet_network)

    if scenario.location is not None:
        # Because the new scenario should be centered at the intersection, the GPS coordinates in the
        # scenario location must also be updated. As the `center` coordinates might not be absolute,
        # the GPS coordinates of the input scenario will be used to derive the new scenario GPS coordinates.
        cut_scenario_coordinates = _get_translated_scenario_coordinates(
            scenario, (center[0], center[1])
        )
        cut_scenario_metadata = RegionMetadata.from_coordinates(cut_scenario_coordinates)
        cut_scenario.location = cut_scenario_metadata.as_commonroad_scenario_location()

    return cut_scenario


def extract_forking_points(lanelets: Sequence[Lanelet]) -> np.ndarray:
    """
    Extract the start/end point of a lanelet that has more than one predessor/successor
    """
    forking_set = set()

    lanelet_ids = [lanelet.lanelet_id for lanelet in lanelets]

    for lanelet in lanelets:
        if len(lanelet.predecessor) > 1 and set(lanelet.predecessor).issubset(lanelet_ids):
            forking_set.add((lanelet.center_vertices[0][0], lanelet.center_vertices[0][1]))
        if len(lanelet.successor) > 1 and set(lanelet.successor).issubset(lanelet_ids):
            forking_set.add((lanelet.center_vertices[-1][0], lanelet.center_vertices[-1][1]))

    forking_points = np.array(list(forking_set))
    return forking_points


def generate_intersections(scenario: Scenario, forking_points: np.ndarray) -> List[Scenario]:
    if len(forking_points) < 2:
        raise RuntimeError(
            f"Scenario {scenario.scenario_id} only has {len(forking_points)} forking points, but at least 2 forking points are required to extract intersections"
        )

    clustering_result = find_clusters_agglomerative(forking_points)
    labels = clustering_result.labels_
    centroids, distances, clusters = centroids_and_distances(labels, forking_points)

    _LOGGER.debug(
        f"Found {len(clusters)} new intersections for base scenario {scenario.scenario_id}"
    )

    intersections = []
    for idx, key in enumerate(centroids):
        scenario_new = cut_intersection_from_scenario(scenario, centroids[key], distances[key])
        scenario_new.scenario_id.map_id = idx + 1
        intersections.append(scenario_new)

    return intersections


def extract_intersections_from_scenario(scenario: Scenario) -> List[Scenario]:
    forking_points = extract_forking_points(scenario.lanelet_network.lanelets)
    if len(forking_points) < 2:
        _LOGGER.warning(
            "Scenario %s has %s forking point(s), but at least two are required to extract intersections. The scenario will be used as one intersection.",
            scenario.scenario_id,
            len(forking_points),
        )
        return [scenario]
    return generate_intersections(scenario, forking_points)
