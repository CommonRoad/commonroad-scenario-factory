import logging
from collections import defaultdict
from copy import deepcopy
from typing import Dict, List, Sequence, Tuple

import numpy as np
from commonroad.scenario.intersection import Intersection
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.traffic_light import TrafficLight
from commonroad.scenario.traffic_sign import TrafficSign
from scipy.spatial import distance
from sklearn.cluster import AgglomerativeClustering

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


def relevant_traffic_signs(
    traffic_signs: Sequence[TrafficSign], lanelets: Sequence[Lanelet]
) -> List[TrafficSign]:
    """
    Select traffic signs that are referenced by at least one lanelet.

    :param traffic_lights: The list of traffic_lights to check
    :param lanelets: The list of lanelets to check against
    :returns: The selected intersections
    """
    referenced_traffic_signs = set()

    for lanelet in lanelets:
        for traffic_sign in lanelet.traffic_signs:
            referenced_traffic_signs.add(traffic_sign)

    traffic_signs_dict = {}
    for traffic_sign in traffic_signs:
        traffic_signs_dict[traffic_sign.traffic_sign_id] = traffic_sign

    return [
        traffic_signs_dict[referenced_traffic_sign]
        for referenced_traffic_sign in referenced_traffic_signs
    ]


def relevant_traffic_lights(
    traffic_lights: Sequence[TrafficLight], lanelets: Sequence[Lanelet]
) -> List[TrafficLight]:
    """
    Select traffic lights that are referenced by at least one lanelet.

    :param traffic_lights: The list of traffic_lights to check
    :param lanelets: The list of lanelets to check against
    :returns: The selected intersections
    """
    referenced_traffic_lights = set()

    for lanelet in lanelets:
        for traffic_light in lanelet.traffic_lights:
            if len(lanelet.successor) > 0:
                referenced_traffic_lights.add(traffic_light)

    traffic_lights_dict = {}
    for traffic_light in traffic_lights:
        traffic_lights_dict[traffic_light.traffic_light_id] = traffic_light

    return [
        traffic_lights_dict[referenced_traffic_light]
        for referenced_traffic_light in referenced_traffic_lights
    ]


def relevant_intersections(
    intersections: Sequence[Intersection], lanelets: Sequence[Lanelet]
) -> List[Intersection]:
    """
    Select intersections with known incoming lanelets.

    :param intersections: The list of intersections to check
    :param lanelets: The list of lanelets to check against
    :returns: The selected intersections
    """
    referenced_intersections = set()
    lanelet_ids = set()
    for lanelet in lanelets:
        lanelet_ids.add(lanelet.lanelet_id)

    for intersection in intersections:
        for incoming in intersection.incomings:
            if incoming.incoming_lanelets is None:
                continue

            for lt_id in incoming.incoming_lanelets:
                if lt_id in lanelet_ids:
                    referenced_intersections.add(intersection)

    return list(referenced_intersections)


def cut_intersection_from_scenario(
    scenario: Scenario, center: np.ndarray, max_distance: float
) -> Scenario:
    """
    Create new scenario from old scenario, by cutting the lanelet network around center with radius

    :param scenario: Original scenario
    :param center: Center of new scenario
    :param max_distance: Cut radius
    :return: New Scenario only containing desired intersection
    """

    intersection_cut_margin = 30
    radius = max_distance + intersection_cut_margin

    net = deepcopy(scenario.lanelet_network)
    lanelets = net.lanelets_in_proximity(
        center, radius
    )  # TODO debug cases where lanelets contains none entries
    lanelets_not_none = [i for i in lanelets if i is not None]
    traffic_lights = relevant_traffic_lights(
        scenario.lanelet_network.traffic_lights, lanelets_not_none
    )
    traffic_signs = relevant_traffic_signs(
        scenario.lanelet_network.traffic_signs, lanelets_not_none
    )
    intersections = relevant_intersections(
        scenario.lanelet_network.intersections, lanelets_not_none
    )
    _LOGGER.debug(
        f"For new scenario from {scenario.scenario_id} identified the interesting intersections '{intersections}' out of all intersections '{[intersection.intersection_id for intersection in scenario.lanelet_network.intersections]}'"
    )

    # create new scenario
    cut_lanelet_scenario = Scenario(dt=0.1)
    cut_lanelet_scenario.scenario_id = deepcopy(scenario.scenario_id)
    cut_lanelet_network = LaneletNetwork.create_from_lanelet_list(
        lanelets_not_none, cleanup_ids=False
    )
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
                or len(incoming.successors_straight)
                + len(incoming.successors_left)
                + len(incoming.successors_right)
                < 1
            ):
                remove_incoming.add(incoming)

        for incoming in remove_incoming:
            intersection.incomings.remove(incoming)

        if len(intersection.incomings) < 1:
            remove_intersection.add(intersection)

    for intersection in remove_intersection:
        _LOGGER.debug(
            f"Dicarded intersection {intersection} from scenario {cut_lanelet_scenario.scenario_id} because it does not contain "
        )
        cut_lanelet_scenario.lanelet_network.remove_intersection(intersection)

    return cut_lanelet_scenario


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
    """ """
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
    return generate_intersections(scenario, forking_points)
