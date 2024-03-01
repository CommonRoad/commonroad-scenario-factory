import glob
import logging
import os
from copy import deepcopy
from typing import Dict, Generator, Iterable, List, Tuple, Union

import commonroad_dc.pycrcc as pycrcc
import numpy as np
import scipy.signal as signal
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.geometry.shape import Polygon
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.trajectory import State
from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_object


def iter_scenario_pp_from_folder(folder: str) -> Generator[Tuple[Scenario, PlanningProblemSet, str], None, None]:
    for path in glob.glob(os.path.join(folder, "*.xml"), recursive=True):
        try:
            yield tuple(list(CommonRoadFileReader(path).open()) + [path])
        except Exception:
            continue


def iter_scenario_paths_from_folder(folder: str):
    for path in glob.glob(os.path.join(folder, "*.xml"), recursive=True):
        yield path


def iter_scenario_from_folder(folder: str) -> Generator[Tuple[Scenario, PlanningProblemSet, str], None, None]:
    for path in glob.glob(os.path.join(folder, "*.xml"), recursive=True):
        try:
            reader = CommonRoadFileReader(path)
            reader._read_header()
            yield reader._open_scenario(lanelet_assignment=False), path
        except Exception:
            continue


def erode_lanelets(lanelet_network: LaneletNetwork, radius: float) -> LaneletNetwork:
    """Erode shape of lanelet by given radius."""

    lanelets_ero = []
    radius = 2 * radius
    for lanelet in lanelet_network.lanelets:
        lanelet_ero = deepcopy(lanelet)

        # compute eroded vector from center
        perp_vecs = (lanelet_ero.left_vertices - lanelet_ero.right_vertices) * 0.5
        length = np.linalg.norm(perp_vecs, axis=1)
        factors = (1 - np.divide(radius, length)) * 0.5 * np.ones_like(length)  # np.divide(radius, length)
        factors = np.reshape(factors, newshape=[-1, 1])
        perp_vec_ero = np.multiply(perp_vecs, factors)

        # recompute vertices
        lanelet_ero._left_vertices = lanelet_ero.center_vertices + perp_vec_ero
        lanelet_ero._right_vertices = lanelet_ero.center_vertices - perp_vec_ero
        if lanelet_ero._polygon is not None:
            lanelet_ero._polygon = Polygon(
                np.concatenate((lanelet_ero.right_vertices, np.flip(lanelet_ero.left_vertices, 0)))
            )
        lanelets_ero.append(lanelet_ero)

    return LaneletNetwork.create_from_lanelet_list(lanelets_ero)


def is_iterable(p_object):
    try:
        iter(p_object)
    except TypeError:
        return False
    return True


def is_connected(lanelet_a: Lanelet, lanelet_b: Lanelet):
    """Checks whether lanes are in a succ/pred relation or adjacent."""
    if not is_iterable(lanelet_a.adj_left):
        adj_left = [lanelet_a.adj_left]
    else:
        adj_left = lanelet_a.adj_left
    if not is_iterable(lanelet_a.adj_right):
        adj_right = [lanelet_a.adj_right]
    else:
        adj_right = lanelet_a.adj_right

    if lanelet_b.lanelet_id in adj_left or lanelet_b.lanelet_id in adj_right:
        return True

    if lanelet_b.lanelet_id in lanelet_a.successor or lanelet_b.lanelet_id in lanelet_a.predecessor:
        return True

    return False


def find_intersecting_lanelets(lanelet_network: LaneletNetwork) -> List[Tuple[int, int]]:
    """Find pairs of intersecting lanelets. Returns list of lanelet_id pairs."""
    poly_dict = {}  # {polygon_obj: lanelet_id}
    poly_mapping = {}  # {lanelet_id: polygon_obj}
    for lanelet in lanelet_network.lanelets:
        poly_dict[lanelet.lanelet_id] = create_collision_object(lanelet.convert_to_polygon())
        poly_mapping[poly_dict[lanelet.lanelet_id]] = lanelet.lanelet_id

    # check all lanelets pair wise for intersections with each other lanelet
    intersections = []  # list of intersecting lanelet_id pairs
    checked_ids = []  # ids which have already been checked for intersections
    for id, poly in poly_dict.items():
        lanelet_a = lanelet_network._lanelets[id]
        cc_tmp = pycrcc.CollisionChecker()
        checked_ids.append(id)
        for id_tmp, poly_tmp in poly_dict.items():
            if id_tmp not in checked_ids:
                lanelet_b = lanelet_network._lanelets[id_tmp]
                if not is_connected(lanelet_a, lanelet_b):
                    # check only for intersection, if lanelets are not connected
                    cc_tmp.add_collision_object(poly_tmp)

        intersecting_polys = cc_tmp.find_all_colliding_objects(poly)
        for poly_intersec in intersecting_polys:
            intersections.append((id, poly_mapping[poly_intersec]))

    # TODO: only for debugging
    import matplotlib.pyplot as plt
    from commonroad.visualization.draw_dispatch_cr import draw_object

    for pair in intersections:
        # plt.close('all')
        plt.figure()
        plt.axis("equal")
        draw_object(lanelet_network.find_lanelet_by_id(pair[0]), draw_params={"lanelet": {"show_label": True}})
        draw_object(lanelet_network.find_lanelet_by_id(pair[1]), draw_params={"lanelet": {"show_label": True}})
        plt.autoscale()
        plt.show()
        plt.pause(0.01)

    return intersections


def compute_intersections(lanelet_network: LaneletNetwork) -> List[Tuple[int, int]]:
    """
    Compute list of intersecting lanelet_id pairs. Adjacent and successor/predecessor lanelets are ignored.
    :param lanelet_network:
    :return:
    """
    # erode lanelet polyons by a radius, to prevent false positive errors e.g. in curves
    eroded_network = erode_lanelets(lanelet_network, radius=0.3)
    intersecting_lanelet_ids = find_intersecting_lanelets(eroded_network)
    return intersecting_lanelet_ids


def apply_smoothing_filter(array: np.ndarray, par1=0.05 / 2.5):
    if int(array.size) > 12:  # filter fails for length <= 12!
        # butterworth lowpass filter
        b, a = signal.butter(1, par1, output="ba")
        zi = signal.lfilter_zi(b, a)
        z, _ = signal.lfilter(b, a, array, zi=zi * array[0])
        return True, signal.filtfilt(b, a, array)
    else:
        # use simple smoothing filter instead
        return False, array


def sort_by_list(list_in: list, sorter_list: list):
    """
    Sort list_in by another list sorter_list.
    :param list_in:
    :param sorter_list:
    :return: sorted list
    """
    return [ele for _, ele in sorted(zip(sorter_list, list_in), key=lambda pair: pair[0])]


def get_state_at_time(obstacle: DynamicObstacle, time_step: int) -> State:
    if time_step == obstacle.initial_state.time_step:
        return obstacle.initial_state
    return obstacle.prediction.trajectory.state_at_time_step(time_step)


def find_first_greater(vec: np.ndarray, item):
    """return the index of the first occurence of item in vec"""
    for i in range(len(vec)):
        if item < vec[i]:
            return i
    return None


def init_logging(module_name: str, logging_level: int):
    """
    Initis logging for module
    :param module_name:
    :param logging_level: use logging.WARNING, INFO, CRITICAL or DEBUG
    :return:
    """
    # Create a custom logger
    logger = logging.getLogger(module_name)
    logger.setLevel(level=logging_level)

    # Create handlers
    c_handler = logging.StreamHandler()
    # logger.setLevel(level=getattr(logging, self.conf_scenario.logging_level))

    # Create formatters and add it to handlers
    c_format = logging.Formatter("%(message)s")
    c_handler.setFormatter(c_format)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    return logger


def select_by_vehicle_type(
    obstacles: Iterable, vehicle_types: Iterable[ObstacleType] = (ObstacleType.CAR)
) -> Union[Dict[int, DynamicObstacle], Iterable[DynamicObstacle]]:
    """:returns only obstacles with specified vehicle type(s)."""
    if isinstance(obstacles, dict):
        return {obs_id: obs for obs_id, obs in obstacles.items() if (obs.obstacle_type in vehicle_types)}
    else:
        return [obs for obs in obstacles if (obs.obstacle_type in vehicle_types)]
