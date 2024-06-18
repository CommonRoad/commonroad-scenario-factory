import numpy as np
from commonroad.scenario.scenario import Scenario


def extract_forking_points(scenario: Scenario) -> np.ndarray:
    lanelets = scenario.lanelet_network.lanelets
    forking_set = set()

    lanelet_ids = [lanelet.lanelet_id for lanelet in lanelets]

    for lanelet in lanelets:
        if len(lanelet.predecessor) > 1 and set(lanelet.predecessor).issubset(lanelet_ids):
            forking_set.add((lanelet.center_vertices[0][0], lanelet.center_vertices[0][1]))
        if len(lanelet.successor) > 1 and set(lanelet.successor).issubset(lanelet_ids):
            forking_set.add((lanelet.center_vertices[-1][0], lanelet.center_vertices[-1][1]))

    forking_points = np.array(list(forking_set))
    return forking_points
