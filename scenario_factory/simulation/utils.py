import math
from typing import Set

import networkx as nx
import numpy as np
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from crots.conversion.default_speed_limit import get_default_speed_limit_for_lanelet_type


def compute_warmup_time_for_lanelet_network(lanelet_network: LaneletNetwork) -> float:
    """
    Estimate the warm-up time for the simulation based on the lanelet network. For lane changes, take the average of
    both lanes.

    Parameters
    ----------
    lanelet_network: LaneletNetwork
        Lanelet network to be analyzed.

    Returns
    -------
    warm_up_estimate: float
        Warm-up time in seconds.
    """
    # construct networkx graph from lanelet network with lanelet durations as weights
    graph = nx.DiGraph()
    for lanelet in lanelet_network.lanelets:
        duration_own = compute_lanelet_duration(lanelet)
        if not graph.has_node(lanelet.lanelet_id):
            graph.add_node(lanelet.lanelet_id)
        for succ in lanelet.successor:
            graph.add_edge(lanelet.lanelet_id, succ, weight=duration_own)
        if lanelet.adj_left and lanelet.adj_left_same_direction:
            duration_adj = compute_lanelet_duration(
                lanelet_network.find_lanelet_by_id(lanelet.adj_left)
            )
            graph.add_edge(
                lanelet.lanelet_id, lanelet.adj_left, weight=(duration_adj + duration_own) / 2
            )
        if lanelet.adj_right and lanelet.adj_right_same_direction:
            duration_adj = compute_lanelet_duration(
                lanelet_network.find_lanelet_by_id(lanelet.adj_right)
            )
            graph.add_edge(
                lanelet.lanelet_id, lanelet.adj_right, weight=(duration_adj + duration_own) / 2
            )

    # get longest shortest path
    durations = dict(nx.all_pairs_dijkstra_path_length(graph))
    warm_up_estimate = (
        max([max(durations[node].values()) for node in durations.keys()]) * 5.0
    )  # add 400% margin to max
    return math.ceil(warm_up_estimate)


def compute_lanelet_duration(lanelet: Lanelet) -> float:
    """
    Compute the duration it takes to travel a lanelet.

    Parameters
    ----------
    lanelet: Lanelet
        Lanelet to be analyzed.

    Returns
    -------
    duration: float
        Duration in seconds.
    """
    # determine speed limit
    v = min(
        [90 / 3.6, get_default_speed_limit_for_lanelet_type(lanelet.lanelet_type)]
    )  # 90 km/h as upper limit (trucks won't go faster)

    # determine length of lanelet
    s = np.sum(np.linalg.norm(np.diff(lanelet.center_vertices, axis=0), axis=0))

    duration = s / v

    return duration
