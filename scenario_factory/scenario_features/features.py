import argparse
import glob
import os
from typing import List, Union

import math
import numpy as np
import pandas as pd
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.geometry.shape import Shape, Circle, Rectangle, Polygon, ShapeGroup
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import Obstacle, DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.trajectory import Trajectory, State
try:
    from commonroad_ccosy.geometry.trapezoid_coordinate_system import create_coordinate_system_from_polyline
except ModuleNotFoundError:
    pass

SENSOR_RANGE = 100.0


def get_obstacle_state_at_timestep(obstacle: DynamicObstacle, timestep):
    if timestep == 0: return obstacle.initial_state
    return obstacle.prediction.trajectory.state_at_time_step(timestep)


def get_obstacle_state_list(obstacle: DynamicObstacle):
    return [obstacle.initial_state] + obstacle.prediction.trajectory.state_list


def get_timespan_of_scenario(scenario):
    dynamic_obstacles = scenario.dynamic_obstacles
    max_timestep = 0
    for obstacle in dynamic_obstacles:
        last_state = get_obstacle_state_list(obstacle)[-1]
        if last_state.time_step > max_timestep:
            max_timestep = last_state.time_step
    return max_timestep * scenario.dt


# def get_ego_mid_timestep(ego_vehicle):
#     return round(len(get_obstacle_state_list(ego_vehicle)) / 2)


def get_ego_acc_at_timestep(ego_vehicle, timestep, dt):
    first_state = get_obstacle_state_at_timestep(ego_vehicle, timestep)
    second_state = get_obstacle_state_at_timestep(ego_vehicle, timestep + 1)
    if first_state is None or second_state is None: return 0  # TODO what to set in case of end Time Step
    acc = (second_state.velocity - first_state.velocity) / dt
    return round(acc, 4)


def get_min_ego_acc(ego_vehicle, dt):
    ego_states = get_obstacle_state_list(ego_vehicle)
    accelerations = [
        (x1.velocity - x0.velocity) / dt
        for x0, x1 in zip(ego_states[:-1], ego_states[1:])
    ]
    return round(min(accelerations), 4)


def ego_max_breaktime(ego_vehicle, dt):
    states = get_obstacle_state_list(ego_vehicle)
    accelerations = [
        (x1.velocity - x0.velocity) / dt
        for x0, x1 in zip(states[:-1], states[1:])
    ]
    max_break_ts_count = 0
    break_ts_count = 0
    for acceleration in accelerations:
        if acceleration >= 0:
            break_ts_count = 0
            continue

        break_ts_count += 1
        max_break_ts_count = max(max_break_ts_count, break_ts_count)

    return round(max_break_ts_count * dt, 4)


def ego_breaktime_until_timestep(ego_vehicle, timestep, dt):
    final_state = get_obstacle_state_at_timestep(ego_vehicle, timestep)
    final_idx = get_obstacle_state_list(ego_vehicle).index(final_state)
    states = get_obstacle_state_list(ego_vehicle)[:final_idx + 1]
    accelerations = [
        (x1.velocity - x0.velocity) / dt
        for x0, x1 in zip(states[:-1], states[1:])
    ]
    break_ts_count = 0
    for acceleration in reversed(accelerations):
        if acceleration >= 0:
            break
        break_ts_count += 1

    return round(break_ts_count * dt, 4)


def euclidean_distance(pos1: np.ndarray, pos2: np.ndarray) -> float:
    """
    Returns the euclidean distance between 2 points.

    :param pos1: the first point
    :param pos2: the second point
    """
    return np.sqrt(((pos1[0] - pos2[0]) ** 2) + ((pos1[1] - pos2[1]) ** 2))


# def sort_vertices(position: np.ndarray, vertices: np.ndarray) -> np.ndarray:
#     return np.array(sorted(vertices, key=lambda vertice: euclidean_distance(position, vertice)))


# def get_closest_vertices(position: np.ndarray, vertices: np.ndarray, n=2) -> List[np.ndarray]:
#     min_dist_verts = sort_vertices(position, vertices)[:n]
#     closest_verts = [vert for vert in vertices if vert in min_dist_verts]
#     return closest_verts


def get_curvy_distance(ego_pos, obst_pos, coord_sys):
    ego_pos_curvy = coord_sys.convert_to_curvilinear_coords(ego_pos[0], ego_pos[1])
    obst_pos_curvy = coord_sys.convert_to_curvilinear_coords(obst_pos[0], obst_pos[1])
    return euclidean_distance(ego_pos_curvy, obst_pos_curvy)


def find_shape_positions(shape: Shape) -> np.ndarray:
    if isinstance(shape, np.ndarray): return np.array([shape])
    if isinstance(shape, (Circle, Rectangle, Polygon)): return np.array([shape.center])
    if isinstance(shape, ShapeGroup):
        return np.array([position for shp in shape.shapes for position in find_shape_positions(shp)])


def is_obstacle_in_lanelet(obstacle, lanelet, timestep):
    if obstacle.occupancy_at_time(timestep) is None: return False
    shape_positions = find_shape_positions(obstacle.occupancy_at_time(timestep).shape)
    lanelet_polygon = lanelet.convert_to_polygon()
    return any([lanelet_polygon.contains_point(shape_position) for shape_position in shape_positions])


# def obstacle_positions_at_timestep(obstacles: List[Obstacle], timestep):
#     positions = [position
#                  for obstacle in obstacles
#                  if obstacle.occupancy_at_time(timestep) is not None
#                  for position in find_shape_positions(obstacle.occupancy_at_time(timestep).shape)]
#
#     return positions

def get_obstacles_in_lanelet(obstacles, lanelet, timestep):
    return [
        obstacle
        for obstacle in obstacles
        if is_obstacle_in_lanelet(obstacle, lanelet, timestep)
    ]


def get_leading_and_preceeding_positions_by_pos(dynamic_obstacles, lanelet, ego_state, coord_sys, sensor_range=SENSOR_RANGE):
    if lanelet is None: return -1, -1
    obstacles = get_obstacles_in_lanelet(dynamic_obstacles, lanelet, ego_state.time_step)
    front_obstacles = get_obstacles_in_front(ego_state, obstacles)
    rear_obstacles = [obstacle for obstacle in obstacles if obstacle not in front_obstacles]
    closest_front = get_closest_obstacle(ego_state, front_obstacles)
    closest_rear = get_closest_obstacle(ego_state, rear_obstacles)

    front_dist = -1
    rear_dist = -1
    sensor_range = ego_state.velocity * 3 if sensor_range is None else sensor_range  # TODO what value to set here?

    if closest_front is not None:
        front_state = get_obstacle_state_at_timestep(closest_front, ego_state.time_step)
        front_dist = get_curvy_distance(ego_state.position, front_state.position, coord_sys)
        front_dist = -1 if front_dist > sensor_range else front_dist

    if closest_rear is not None:
        rear_state = get_obstacle_state_at_timestep(closest_rear, ego_state.time_step)
        rear_dist = get_curvy_distance(ego_state.position, rear_state.position, coord_sys)
        rear_dist = -1 if rear_dist > sensor_range else rear_dist

    return round(front_dist, 4), round(rear_dist, 4)  # TODO maybe minus for rear ones? but then what about -1?


def get_lanelets(lanelet_network, ego_state):

    ego_lanelet_ids = lanelet_network.find_lanelet_by_position([ego_state.position])[0]
    if not ego_lanelet_ids: return None, None, None
    ego_lanelet_id = ego_lanelet_ids[0]
    ego_lanelet = lanelet_network.find_lanelet_by_id(ego_lanelet_id)

    adj_left_id = ego_lanelet.adj_left
    adj_left_lanelet = None
    if adj_left_id is not None and ego_lanelet.adj_left_same_direction:
        adj_left_lanelet = lanelet_network.find_lanelet_by_id(adj_left_id)

    adj_right_id = ego_lanelet.adj_right
    adj_right_lanelet = None
    if adj_right_id is not None and ego_lanelet.adj_right_same_direction:
        adj_right_lanelet = lanelet_network.find_lanelet_by_id(adj_right_id)

    return ego_lanelet, adj_left_lanelet, adj_right_lanelet


def get_leading_and_preceeding_positions(scenario, ego_vehicle, timestep, suffix):
    ego_state = get_obstacle_state_at_timestep(ego_vehicle, timestep)
    ego_lanelet, left_lanelet, right_lanelet = get_lanelets(scenario, ego_state)
    coord_sys = create_coordinate_system_from_polyline(ego_lanelet.center_vertices)

    # leading, preceeding
    l_pos, p_pos = get_leading_and_preceeding_positions_by_pos(scenario.dynamic_obstacles,
                                                               ego_lanelet, ego_state, coord_sys)

    # leading left, preceeding left
    l_left_pos, p_left_pos = get_leading_and_preceeding_positions_by_pos(scenario.dynamic_obstacles,
                                                                         left_lanelet, ego_state, coord_sys)

    # leading right, preceeding right
    l_right_pos, p_right_pos = get_leading_and_preceeding_positions_by_pos(scenario.dynamic_obstacles,
                                                                           right_lanelet, ego_state, coord_sys)
    return {
        'l_rel_pos_%s' % suffix: l_pos,
        'p_rel_pos_%s' % suffix: p_pos,
        'll_rel_pos_%s' % suffix: l_left_pos,
        'pl_rel_pos_%s' % suffix: p_left_pos,
        'lr_rel_pos_%s' % suffix: l_right_pos,
        'pr_rel_pos_%s' % suffix: p_right_pos,
    }


def get_surrounding_vehicle_count(relative_pos_dict):
    count = 6
    for val in list(relative_pos_dict.values()):
        if val == -1:
            count -= 1
    return count


def line_orientation(points):
    return math.atan2(points[1][1] - points[0][1], points[1][0] - points[0][0])


def is_obstacle_in_front(vehicle_state: State, obstacle_position: np.ndarray) -> bool:
    lower_limit = (-math.pi / 2) + vehicle_state.orientation
    upper_limit = (math.pi / 2) + vehicle_state.orientation
    return lower_limit < line_orientation([vehicle_state.position, obstacle_position]) < upper_limit


def get_obstacles_in_front(ego_state: State, obstacles: List[DynamicObstacle]) -> List[DynamicObstacle]:
    valid_obstacles = [(obstacle, get_obstacle_state_at_timestep(obstacle, ego_state.time_step))
                       for obstacle in obstacles
                       if get_obstacle_state_at_timestep(obstacle, ego_state.time_step) is not None]
    front_obstacles = [obstacle
                       for obstacle, obstacle_state in valid_obstacles
                       if is_obstacle_in_front(ego_state, obstacle_state.position)]
    return front_obstacles


def get_closest_obstacle(ego_state: State, obstacles: List[DynamicObstacle]) -> Union[None, DynamicObstacle]:
    if not obstacles: return None
    obstacle_states = [get_obstacle_state_at_timestep(obstacle, ego_state.time_step) for obstacle in obstacles]
    dists = [euclidean_distance(ego_state.position, obstacle_state.position)
             for obstacle_state in obstacle_states if obstacle_state is not None]
    if not dists: return None
    min_idx = np.argmin(dists)
    return obstacles[int(min_idx)]


def get_closest_front_obstacle(scenario, ego_state):
    ego_lanelet, _, _ = get_lanelets(scenario, ego_state)
    obstacles = get_obstacles_in_lanelet(scenario.obstacles, ego_lanelet, ego_state.time_step)
    front_obstacles = get_obstacles_in_front(ego_state, obstacles)
    closest_obstacle = get_closest_obstacle(ego_state, front_obstacles)
    return closest_obstacle


def get_min_dhw(scenario: Scenario, ego_vehicle: DynamicObstacle, sensor_range=SENSOR_RANGE) -> (float, int):
    """
    Calculates the minimum Distance Headway for the ego vehicle.

    :param scenario: CommonRoad Scenario
    :param ego_vehicle: CommonRoad Dynamic Obstacle which represents the Ego Vehicle
    :return: float
    """
    min_dhw = math.inf
    min_dhw_ts = -1
    for ego_state in get_obstacle_state_list(ego_vehicle):
        closest_obstacle = get_closest_front_obstacle(scenario, ego_state)
        if closest_obstacle is None: continue

        obstace_state = get_obstacle_state_at_timestep(closest_obstacle, ego_state.time_step)
        ego_lanelet, _, _ = get_lanelets(scenario, ego_state)
        curvy_coord = create_coordinate_system_from_polyline(ego_lanelet.center_vertices)
        dist = get_curvy_distance(ego_state.position, obstace_state.position, curvy_coord)  # distance center of gravity

        sensor_range = ego_state.velocity * 3 if sensor_range is None else sensor_range
        if dist > sensor_range: return -1, -1

        dist -= ego_vehicle.obstacle_shape.length / 2  # Assume rectangle, and ignore minor orientation diff
        dist += closest_obstacle.obstacle_shape.length / 2  # Assume rectangle and ignore minor orientation diff
        if dist < min_dhw:
            min_dhw = dist
            min_dhw_ts = ego_state.time_step

    min_dhw = round(min_dhw, 4) if not min_dhw == math.inf else -1
    return min_dhw, min_dhw_ts


def get_min_thw(scenario: Scenario, ego_vehicle: DynamicObstacle, sensor_range=SENSOR_RANGE) -> (float, int):
    """
    Calculates the minimum Distance Headway for the ego vehicle.

    :param scenario: CommonRoad Scenario
    :param ego_vehicle: CommonRoad Dynamic Obstacle which represents the Ego Vehicle
    :return: float
    """
    min_thw = math.inf  # Upper Threshold
    min_thw_ts = -1
    for ego_state in get_obstacle_state_list(ego_vehicle):
        if ego_state.velocity <= 0: continue

        closest_obstacle = get_closest_front_obstacle(scenario, ego_state)
        if closest_obstacle is None: continue

        obstace_state = get_obstacle_state_at_timestep(closest_obstacle, ego_state.time_step)
        ego_lanelet, _, _ = get_lanelets(scenario, ego_state)
        curvy_coord = create_coordinate_system_from_polyline(ego_lanelet.center_vertices)
        dist = get_curvy_distance(ego_state.position, obstace_state.position, curvy_coord)  # distance center of gravity

        sensor_range = ego_state.velocity * 3 if sensor_range is None else sensor_range
        if dist > sensor_range: return -1, -1

        dist -= ego_vehicle.obstacle_shape.length / 2  # Assume rectangle, and ignore minor orientation diff
        dist += closest_obstacle.obstacle_shape.length / 2  # Assume rectangle and ignore minor orientation diff

        thw = dist / ego_state.velocity
        if thw < min_thw:
            min_thw = thw
            min_thw_ts = ego_state.time_step

    min_thw = round(min_thw, 4) if not min_thw == math.inf else -1
    return min_thw, min_thw_ts


def get_min_ttc(scenario: Scenario, ego_vehicle: DynamicObstacle, sensor_range=SENSOR_RANGE) -> (float, int):
    """
    Calculates the minimum Distance Headway for the ego vehicle.

    :param scenario: CommonRoad Scenario
    :param ego_vehicle: CommonRoad Dynamic Obstacle which represents the Ego Vehicle
    :return: float
    """
    min_ttc = math.inf  # Upper Threshold
    min_ttc_ts = -1
    for ego_state in get_obstacle_state_list(ego_vehicle):
        closest_obstacle = get_closest_front_obstacle(scenario, ego_state)
        if closest_obstacle is None: continue

        obstace_state = get_obstacle_state_at_timestep(closest_obstacle, ego_state.time_step)
        ego_lanelet, _, _ = get_lanelets(scenario, ego_state)
        curvy_coord = create_coordinate_system_from_polyline(ego_lanelet.center_vertices)
        dist = get_curvy_distance(ego_state.position, obstace_state.position, curvy_coord)  # distance center of gravity

        sensor_range = ego_state.velocity * 3 if sensor_range is None else sensor_range
        if dist > sensor_range: return -1, -1

        dist -= ego_vehicle.obstacle_shape.length / 2  # Assume rectangle, and ignore minor orientation diff
        dist -= closest_obstacle.obstacle_shape.length / 2  # Assume rectangle and ignore minor orientation diff

        vel_diff = ego_state.velocity - obstace_state.velocity
        if vel_diff <= 0: continue

        ttc = dist / vel_diff
        if ttc < min_ttc:
            min_ttc = ttc
            min_ttc_ts = ego_state.time_step

    min_ttc = round(min_ttc, 4) if not min_ttc == math.inf else -1
    return min_ttc, min_ttc_ts


def changes_lane(lanelet_network, obstacle):
    obstacle_states = get_obstacle_state_list(obstacle)
    for x0, x1 in zip(obstacle_states[:-1], obstacle_states[1:]):
        x0_lanelet, _, _ = get_lanelets(lanelet_network, x0)
        x1_lanelet, _, _ = get_lanelets(lanelet_network, x1)
        if x0_lanelet is None or x1_lanelet is None: continue
        if not x0_lanelet.lanelet_id == x1_lanelet.lanelet_id:
            lane_change_direction = -1 if x1_lanelet.lanelet_id == x0_lanelet.adj_left else +1
            lane_change_ts = x1.time_step
            return True, lane_change_direction, lane_change_ts
    return False, 0, -1


def get_cut_in_info(scenario: Scenario, ego_vehicle: DynamicObstacle, sensor_range=SENSOR_RANGE):
    dynamic_obstacles = scenario.dynamic_obstacles
    lc_obstacles = [(obstacle,) + changes_lane(scenario, obstacle)[1:]
                    for obstacle in dynamic_obstacles if changes_lane(scenario, obstacle)[0]]
    sorted_lc_obstacles = sorted(lc_obstacles, key=lambda x: x[2])

    for obstacle, lc_dir, lc_ts in sorted_lc_obstacles:
        obst_state = get_obstacle_state_at_timestep(obstacle, lc_ts)
        ego_state = get_obstacle_state_at_timestep(ego_vehicle, lc_ts)
        obst_lanelet, _, _ = get_lanelets(scenario, obst_state)
        ego_lanelet, _, _ = get_lanelets(scenario, ego_state)
        if obst_lanelet.lanelet_id == ego_lanelet.lanelet_id and is_obstacle_in_front(ego_state, obst_state.position):
            curvy_coord = create_coordinate_system_from_polyline(ego_lanelet.center_vertices)
            ego_state_before = get_obstacle_state_at_timestep(ego_vehicle, ego_state.time_step - 1)
            front_obst_before = get_closest_front_obstacle(scenario, ego_state_before)
            if front_obst_before is None: continue

            front_obst_bef_state = get_obstacle_state_at_timestep(front_obst_before, ego_state_before.time_step)
            dist_before = get_curvy_distance(ego_state_before.position, front_obst_bef_state.position, curvy_coord)

            sensor_range = ego_state_before.velocity * 3 if sensor_range is None else sensor_range
            dist_before = dist_before if dist_before <= sensor_range else sensor_range

            new_dist = get_curvy_distance(ego_state.position, obst_state.position, curvy_coord)
            dist_reduced = dist_before - new_dist
            if dist_reduced < 0: continue  # if the obstacle does not cut in directly in front

            return lc_dir, lc_ts, round(dist_reduced, 4)

    return 0, -1, -1


def get_feature_defaults(feature_suffix):
    return {
        feature_suffix: -1,
        'ego_v_%s' % feature_suffix: -1,
        'ego_acc_%s' % feature_suffix: 0, # TODO what to set for default value
        'l_rel_pos_%s' % feature_suffix: -1,
        'p_rel_pos_%s' % feature_suffix: -1,
        'll_rel_pos_%s' % feature_suffix: -1,
        'pl_rel_pos_%s' % feature_suffix: -1,
        'lr_rel_pos_%s' % feature_suffix: -1,
        'pr_rel_pos_%s' % feature_suffix: -1,
        'surr_veh_count_%s' % feature_suffix: -1,
        'ego_breaktime_until_%s' % feature_suffix: -1,
    }


def extract_features(scenario, planning_problem_set, ego_vehicle):
    features = {}
    features['scenario_id'] = scenario.benchmark_id
    features['timespan'] = get_timespan_of_scenario(scenario)
    if ego_vehicle is not None:
        # ego_mid_ts = get_ego_mid_timestep(ego_vehicle)  # min TTC frame from original dataset

        # Initial Time Step Features
        ego_init_ts = 0
        features['ego_v_init'] = round(get_obstacle_state_at_timestep(ego_vehicle, ego_init_ts).velocity, 4)
        features['ego_acc_init'] = get_ego_acc_at_timestep(ego_vehicle, ego_init_ts, scenario.dt)
        init_sur_rel_pos = get_leading_and_preceeding_positions(scenario, ego_vehicle, ego_init_ts, 'init')
        features.update(init_sur_rel_pos)
        init_sur_veh_count = get_surrounding_vehicle_count(init_sur_rel_pos)
        features['surr_veh_count_init'] = init_sur_veh_count
        features['ego_acc_min'] = get_min_ego_acc(ego_vehicle, scenario.dt)
        features['ego_breaktime_max'] = ego_max_breaktime(ego_vehicle, scenario.dt)

        # End Time Step Features
        ego_end_ts = get_obstacle_state_list(ego_vehicle)[-1].time_step
        features['ego_v_end'] = round(get_obstacle_state_at_timestep(ego_vehicle, ego_end_ts).velocity, 4)
        end_sur_rel_pos = get_leading_and_preceeding_positions(scenario, ego_vehicle, ego_end_ts, 'end')
        features.update(end_sur_rel_pos)
        end_sur_veh_count = get_surrounding_vehicle_count(end_sur_rel_pos)
        features['surr_veh_count_end'] = end_sur_veh_count

        # Ego Lane Change Features
        ego_lc, ego_lc_dir, ego_lc_ts = changes_lane(scenario, ego_vehicle)
        features['ego_lane_change_ts'] = ego_lc_ts * scenario.dt if not ego_lc_ts == -1 else ego_lc_ts
        features['ego_lane_change'] = ego_lc_dir

        # Cut In Features
        cut_in_dir, cut_in_ts, cut_in_dist_reduced = get_cut_in_info(scenario, ego_vehicle)
        features['cut_in_ts'] = cut_in_ts * scenario.dt if not cut_in_ts == -1 else cut_in_ts
        features['cut_in_dir'] = cut_in_dir
        features['cut_in_dist_reduced'] = cut_in_dist_reduced

        # Ego Min DHW Time Step Features
        features.update(get_feature_defaults('min_dhw'))
        min_dhw, min_dhw_ts = get_min_dhw(scenario, ego_vehicle)  # TODO might not be correct or accurate
        # print('min_dhw_ts', min_dhw_ts)
        if min_dhw_ts > -1:
            features['min_dhw'] = min_dhw
            features['ego_v_min_dhw'] = round(get_obstacle_state_at_timestep(ego_vehicle, min_dhw_ts).velocity, 4)
            features['ego_acc_min_dhw'] = get_ego_acc_at_timestep(ego_vehicle, min_dhw_ts, scenario.dt)
            min_dhw_sur_rel_pos = get_leading_and_preceeding_positions(scenario, ego_vehicle, min_dhw_ts, 'min_dhw')
            features.update(min_dhw_sur_rel_pos)
            min_dhw_sur_veh_count = get_surrounding_vehicle_count(min_dhw_sur_rel_pos)
            features['surr_veh_count_min_dhw'] = min_dhw_sur_veh_count
            features['ego_breaktime_until_min_dhw'] = ego_breaktime_until_timestep(ego_vehicle, min_dhw_ts, scenario.dt)

        # Ego Min THW Time Step Features
        features.update(get_feature_defaults('min_thw'))
        min_thw, min_thw_ts = get_min_thw(scenario, ego_vehicle)  # TODO might not be correct or accurate
        # print('min_thw_ts', min_thw_ts)
        if min_thw_ts > -1:
            features['min_thw'] = min_thw
            features['ego_v_min_thw'] = round(get_obstacle_state_at_timestep(ego_vehicle, min_thw_ts).velocity, 4)
            features['ego_acc_min_thw'] = get_ego_acc_at_timestep(ego_vehicle, min_thw_ts, scenario.dt)
            min_thw_sur_rel_pos = get_leading_and_preceeding_positions(scenario, ego_vehicle, min_thw_ts, 'min_thw')
            features.update(min_thw_sur_rel_pos)
            min_thw_sur_veh_count = get_surrounding_vehicle_count(min_thw_sur_rel_pos)
            features['surr_veh_count_min_thw'] = min_thw_sur_veh_count
            features['ego_breaktime_until_min_thw'] = ego_breaktime_until_timestep(ego_vehicle, min_thw_ts, scenario.dt)

        # Ego Min TTC Time Step Features
        features.update(get_feature_defaults('min_ttc'))
        min_ttc, min_ttc_ts = get_min_ttc(scenario, ego_vehicle)  # TODO might not be correct or accurate
        # print('min_ttc_ts', min_ttc_ts)
        if min_ttc_ts > -1:
            features['min_ttc'] = min_ttc
            features['ego_v_min_ttc'] = round(get_obstacle_state_at_timestep(ego_vehicle, min_ttc_ts).velocity, 4)
            features['ego_acc_min_ttc'] = get_ego_acc_at_timestep(ego_vehicle, min_ttc_ts, scenario.dt)
            min_ttc_sur_rel_pos = get_leading_and_preceeding_positions(scenario, ego_vehicle, min_ttc_ts, 'min_ttc')
            features.update(min_ttc_sur_rel_pos)
            min_ttc_sur_veh_count = get_surrounding_vehicle_count(min_ttc_sur_rel_pos)
            features['surr_veh_count_min_ttc'] = min_ttc_sur_veh_count
            features['ego_breaktime_until_min_ttc'] = ego_breaktime_until_timestep(ego_vehicle, min_ttc_ts, scenario.dt)

    return features


def remove_redundant_state_fields(init_state, example_state: State) -> State:  # Non KS fields
    vals = {
        attr: getattr(init_state, attr, 0.0)
        for attr in example_state.attributes
    }
    return State(**vals)


def read_scenario(path, ego, ego_id):
    scenario, planning_problem_set = CommonRoadFileReader(path).open()

    if ego is None:
        return scenario, planning_problem_set, None

    ego_vehicle = scenario.obstacle_by_id(ego_id)  # ego id is always 99
    scenario.remove_obstacle(ego_vehicle)  # remove ego from obstacle list

    return scenario, planning_problem_set, ego_vehicle


def get_args():
    parser = argparse.ArgumentParser(description="Extracts features from CommonRoad scenarios.")
    parser.add_argument('path', metavar='p', type=str, help='Path to scenario file or folder')
    parser.add_argument('--out', type=str, default="./", help='Path to store generated csv file')
    parser.add_argument('--f', action='store_true', help='Set if the provided path is a folder containing scenarios')
    parser.add_argument('--ego', action='store_false',
                        help='Set if the scenario contains ego trajectory as an obstacle')
    parser.add_argument('--ego-id', type=int, default=99, help='Ego obstacle id')

    return parser.parse_args()


# Print iterations progress
def print_progress_bar(iteration,
                       total,
                       prefix='',
                       suffix='',
                       decimals=1,
                       length=100,
                       fill='█',
                       print_end="\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print('\r%s|%s| %s%% %s' % (prefix, bar, percent, suffix), end=print_end)
    # Print New Line on Complete
    if iteration == total:
        print()


def main():
    # get arguments
    args = get_args()

    # make output dir
    if not os.path.exists(args.out):
        os.makedirs(args.out)

    # generate path to scenario files
    if not args.f and not args.path.endswith('.xml'):
        print('Provided path is not a xml file!')
        return

    scenario_paths = sorted([args.path] if not args.f else glob.glob(os.path.join(args.path, "*.xml")))
    print('Found %s files.' % len(scenario_paths))

    print('Extracting features from scenario files:')
    feature_list = []
    for idx, scenario_path in enumerate(scenario_paths):
        try:
            scenario, planning_problem_set, ego_vehicle = read_scenario(scenario_path, args.ego, args.ego_id)
            features = extract_features(scenario, planning_problem_set, ego_vehicle)
            feature_list.append(features)
            print_progress_bar(iteration=idx + 1, total=len(scenario_paths), length=50,
                               suffix='(%s/%s)' % (idx + 1, len(scenario_paths)))
        except Exception as e:
            print('Could not process scenario file:', scenario_path)
            print(e)
            continue

    print('Extracting features done!')
    df = pd.DataFrame(feature_list)
    df.to_csv(os.path.join(args.out, "features.csv"), sep='\t')
    print('Saved extracted features to %s' % os.path.join(args.out, "features.csv"))


if __name__ == "__main__":
    main()
