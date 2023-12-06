import math
from typing import List, Tuple

import commonroad
import numpy as np
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.traffic_light import TrafficLight
from scipy.spatial import distance
from sklearn.cluster import AgglomerativeClustering

from scenario_factory.globetrotter.intersection import Intersection


def find_clusters_agglomerative(points: np.ndarray) -> AgglomerativeClustering:
    """
    Find intersections using Agglomerative Clustering

    :param1 points: forking points used for the clustering process
    :return: Cluster with labeled forking points
    """

    points = np.array(list(points))

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


def get_distance_to_outer_point(center, cluster):
    """
    Euclidean distance between center and outer point
    See https://stackoverflow.com/questions/1401712/how-can-the-euclidean-distance-be-calculated-with-numpy

    :param1 center: The center coordinate
    :param2 cluster: forking points part of the intersection
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


def centroids_and_distances(labels, points):
    """
    Create dictionaries with points assigned to each cluster, the clusters' centers and max distances in each cluster

    :param1 labels: The resulting labels from the clustering process for each forking point
    :param2 points: forking points
    :return: Cluster, center and max_distance dictionaries
    """

    clusters = {i: [] for i in range(0, max(labels) + 1)}
    centroids = {i: None for i in range(0, max(labels) + 1)}
    distances = {i: 0.0 for i in range(0, max(labels) + 1)}

    idx = 0
    while idx < len(points):
        cluster_n = labels[idx]
        # check for noise from DBSCAN
        if cluster_n != -1:
            clusters[cluster_n].append(tuple(points[idx]))
        idx += 1

    # compute center
    for key in clusters:
        centroids[key] = np.mean(clusters[key], axis=0)

    # compute max distance
    for key in distances:
        distances[key] = get_distance_to_outer_point(centroids[key], clusters[key])

    return centroids, distances, clusters


def inside(x: float, y: float, cx: float, cy: float, r: float) -> bool:
    return math.sqrt((x - cx) ** 2 + (y - cy) ** 2) <= r


def traffic_lights_in_proximity(
    traffic_lights: List[TrafficLight], center, radius
) -> List[TrafficLight]:
    return [
        traffic_light
        for traffic_light in traffic_lights
        if inside(
            traffic_light.position[0],
            traffic_light.position[1],
            center[0],
            center[1],
            radius,
        )
    ]


def cut_area(scenario, center, max_distance) -> Scenario:
    """
    Create new scenario from old scenario, based on center and radius

    :param1 scenario: Old scenario
    :param2 center: Center of new scenario
    :param3 max_distance: Cut radius
    :return: New Scenario only containing desired intersection
    """
    center = np.array(list(center))

    intersection_cut_margin = 30
    radius = max_distance + intersection_cut_margin

    net = scenario.lanelet_network
    lanelets = net.lanelets_in_proximity(center, radius)  # TODO debug cases where lanelets contains none entries
    lanelets_not_none = [i for i in lanelets if i is not None]
    traffic_lights = traffic_lights_in_proximity(
        scenario.lanelet_network.traffic_lights, center, radius
    )

    # create new scenario
    cut_lanelet_scenario = commonroad.scenario.scenario.Scenario(0.1)
    cut_lanelet_network = scenario.lanelet_network.create_from_lanelet_list(lanelets_not_none)
    cut_lanelet_scenario.replace_lanelet_network(cut_lanelet_network)
    cut_lanelet_scenario.add_objects(traffic_lights)
    print(f"Detected {len(traffic_lights)} traffic lights")

    return cut_lanelet_scenario


def create_intersection(scenario, center, max_distance, points):
    """
    Method to create intersection object

    :param1 args: required arguments
    :return: New intersection object
    """
    scenario_new = cut_area(scenario, center, max_distance)
    return Intersection(scenario_new, center, points)


def generate_intersections(
    scenario: Scenario, forking_points: np.ndarray
) -> Tuple[List[Intersection], AgglomerativeClustering]:
    print("Scenario generated:")
    print(scenario)
    print(f"Found {len(forking_points)} forking points")

    if len(forking_points) < 2:
        print("[ERROR] Not enough forking points detected")
        exit(-1)

    clustering_result = find_clusters_agglomerative(forking_points)
    labels = clustering_result.labels_
    centroids, distances, clusters = centroids_and_distances(labels, forking_points)

    print(f"Clustering completed. Found {len(clusters)} intersections")

    intersections = []
    for key in centroids:
        intersection = create_intersection(
            scenario, centroids[key], distances[key], clusters[key]
        )
        intersections.append(intersection)
    return intersections, clustering_result
