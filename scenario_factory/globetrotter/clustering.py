from copy import deepcopy
from typing import List, Tuple

import commonroad
import numpy as np
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.traffic_light import TrafficLight
from commonroad.scenario.traffic_sign import TrafficSign
from scipy.spatial import distance
from sklearn.cluster import AgglomerativeClustering

from scenario_factory.globetrotter.intersection import Intersection


def find_clusters_agglomerative(points: np.ndarray) -> AgglomerativeClustering:
    """
    Find intersections using agglomerative clustering

    :param points: forking points used for the clustering process
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


def centroids_and_distances(labels, points):
    """
    Create dictionaries with points assigned to each cluster, the clusters' centers and max distances in each cluster

    :param labels: The resulting labels from the clustering process for each forking point
    :param points: forking points
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


def relevant_traffic_signs(traffic_signs: List[TrafficSign], lanelets: List[Lanelet]) -> List[TrafficSign]:
    referenced_traffic_signs = set()

    for lanelet in lanelets:
        for traffic_sign in lanelet.traffic_signs:
            referenced_traffic_signs.add(traffic_sign)

    traffic_signs_dict = {}
    for traffic_sign in traffic_signs:
        traffic_signs_dict[traffic_sign.traffic_sign_id] = traffic_sign

    return [traffic_signs_dict[referenced_traffic_sign] for referenced_traffic_sign in referenced_traffic_signs]


def relevant_traffic_lights(traffic_lights: List[TrafficLight], lanelets: List[Lanelet]) -> List[TrafficLight]:
    referenced_traffic_lights = set()

    for lanelet in lanelets:
        for traffic_light in lanelet.traffic_lights:
            if len(lanelet.successor) > 0:
                referenced_traffic_lights.add(traffic_light)

    traffic_lights_dict = {}
    for traffic_light in traffic_lights:
        traffic_lights_dict[traffic_light.traffic_light_id] = traffic_light

    return [traffic_lights_dict[referenced_traffic_light] for referenced_traffic_light in referenced_traffic_lights]


def relevant_intersections(intersections: List[Intersection], lanelets: List[Lanelet]) -> List[Intersection]:
    referenced_intersections = set()
    lanelet_ids = set()
    for lanelet in lanelets:
        lanelet_ids.add(lanelet.lanelet_id)

    for intersection in intersections:
        for incoming in intersection.incomings:
            for lt_id in incoming.incoming_lanelets:
                if lt_id in lanelet_ids:
                    referenced_intersections.add(intersection)

    return list(referenced_intersections)


def cut_area(scenario, center, max_distance) -> Scenario:
    """
    Create new scenario from old scenario, based on center and radius

    :param scenario: Original scenario
    :param center: Center of new scenario
    :param max_distance: Cut radius
    :return: New Scenario only containing desired intersection
    """
    center = np.array(list(center))

    intersection_cut_margin = 30
    radius = max_distance + intersection_cut_margin

    net = scenario.lanelet_network
    lanelets = net.lanelets_in_proximity(center, radius)  # TODO debug cases where lanelets contains none entries
    lanelets_not_none = [i for i in lanelets if i is not None]
    traffic_lights = relevant_traffic_lights(scenario.lanelet_network.traffic_lights, lanelets_not_none)
    traffic_signs = relevant_traffic_signs(scenario.lanelet_network.traffic_signs, lanelets_not_none)
    intersections = relevant_intersections(scenario.lanelet_network.intersections, lanelets_not_none)

    # create new scenario
    cut_lanelet_scenario = commonroad.scenario.scenario.Scenario(0.1)
    cut_lanelet_network = scenario.lanelet_network.create_from_lanelet_list(lanelets_not_none, cleanup_ids=False)
    cut_lanelet_scenario.location = scenario.location
    cut_lanelet_scenario.replace_lanelet_network(cut_lanelet_network)
    cut_lanelet_scenario.add_objects(traffic_lights)
    cut_lanelet_scenario.add_objects(traffic_signs)
    cut_lanelet_scenario.add_objects(deepcopy(intersections))
    cut_lanelet_scenario.lanelet_network.cleanup_lanelet_references()
    cut_lanelet_scenario.lanelet_network.cleanup_traffic_light_references()
    cut_lanelet_scenario.lanelet_network.cleanup_traffic_sign_references()

    # clean-up intersections
    remove_intersection = set()
    for intersection in cut_lanelet_scenario.lanelet_network.intersections:
        remove_incoming = set()
        for incoming in intersection.incomings:
            if (
                len(incoming.incoming_lanelets) < 1
                or len(incoming.successors_straight) + len(incoming.successors_left) + len(incoming.successors_right)
                < 1
            ):
                remove_incoming.add(incoming)

        for incoming in remove_incoming:
            intersection.incomings.remove(incoming)

        if len(intersection.incomings) < 1:
            remove_intersection.add(intersection)

    for intersection in remove_intersection:
        cut_lanelet_scenario.lanelet_network.remove_intersection(intersection)

    print(f"Detected {len(traffic_lights)} traffic lights")
    print(f"Detected {len(traffic_signs)} traffic signs")

    return cut_lanelet_scenario


def create_intersection(scenario: Scenario, center: np.ndarray, max_distance: float, points: list) -> Intersection:
    """
    Method to create intersection object

    :param points:
    :param max_distance:
    :param center:
    :param scenario:
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
        intersection = create_intersection(scenario, centroids[key], distances[key], clusters[key])
        intersections.append(intersection)
    return intersections, clustering_result
