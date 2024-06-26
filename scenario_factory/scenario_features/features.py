import math
from typing import List, Tuple, Union

import numpy as np
from commonroad.geometry.shape import Circle, Polygon, Rectangle, Shape, ShapeGroup
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import TraceState
from commonroad.scenario.trajectory import State
from commonroad_dc.geometry.geometry import CurvilinearCoordinateSystem

SENSOR_RANGE = 100.0


def get_obstacle_state_at_timestep(obstacle: DynamicObstacle, timestep):
    if timestep == 0:
        return obstacle.initial_state
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
    if first_state is None or second_state is None:
        return 0  # TODO what to set in case of end Time Step
    acc = (second_state.velocity - first_state.velocity) / dt
    return round(acc, 4)


def get_min_ego_acc(ego_vehicle, dt):
    ego_states = get_obstacle_state_list(ego_vehicle)
    accelerations = [(x1.velocity - x0.velocity) / dt for x0, x1 in zip(ego_states[:-1], ego_states[1:])]
    return round(min(accelerations), 4)


def ego_max_breaktime(ego_vehicle, dt):
    states = get_obstacle_state_list(ego_vehicle)
    accelerations = [(x1.velocity - x0.velocity) / dt for x0, x1 in zip(states[:-1], states[1:])]
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
    states = get_obstacle_state_list(ego_vehicle)[: final_idx + 1]
    accelerations = [(x1.velocity - x0.velocity) / dt for x0, x1 in zip(states[:-1], states[1:])]
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


def get_curvy_distance(ego_pos, obst_pos, coord_sys: CurvilinearCoordinateSystem):
    ego_pos_curvy = coord_sys.convert_to_curvilinear_coords(ego_pos[0], ego_pos[1])
    obst_pos_curvy = coord_sys.convert_to_curvilinear_coords(obst_pos[0], obst_pos[1])
    return euclidean_distance(ego_pos_curvy, obst_pos_curvy)


def find_shape_positions(shape: Shape) -> np.ndarray:
    if isinstance(shape, np.ndarray):
        return np.array([shape])
    if isinstance(shape, (Circle, Rectangle, Polygon)):
        return np.array([shape.center])
    if isinstance(shape, ShapeGroup):
        return np.array([position for shp in shape.shapes for position in find_shape_positions(shp)])


def is_obstacle_in_lanelet(obstacle, lanelet, timestep):
    if obstacle.occupancy_at_time(timestep) is None:
        return False
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
    return [obstacle for obstacle in obstacles if is_obstacle_in_lanelet(obstacle, lanelet, timestep)]


def get_leading_and_preceeding_positions_by_pos(
    dynamic_obstacles, lanelet, ego_state, coord_sys: CurvilinearCoordinateSystem, sensor_range=SENSOR_RANGE
):
    if lanelet is None:
        return -1, -1
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


def get_lanelets(lanelet_network: LaneletNetwork, ego_state: TraceState):
    if ego_state is not None:
        ego_lanelet_ids = lanelet_network.find_lanelet_by_position([ego_state.position])[0]
    else:
        return None, None, None
    if not ego_lanelet_ids:
        return None, None, None
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
    ego_lanelet, left_lanelet, right_lanelet = get_lanelets(scenario.lanelet_network, ego_state)
    coord_sys = CurvilinearCoordinateSystem(ego_lanelet.center_vertices)

    # leading, preceeding
    l_pos, p_pos = get_leading_and_preceeding_positions_by_pos(
        scenario.dynamic_obstacles, ego_lanelet, ego_state, coord_sys
    )

    # leading left, preceeding left
    l_left_pos, p_left_pos = get_leading_and_preceeding_positions_by_pos(
        scenario.dynamic_obstacles, left_lanelet, ego_state, coord_sys
    )

    # leading right, preceeding right
    l_right_pos, p_right_pos = get_leading_and_preceeding_positions_by_pos(
        scenario.dynamic_obstacles, right_lanelet, ego_state, coord_sys
    )
    return {
        "l_rel_pos_%s" % suffix: l_pos,
        "p_rel_pos_%s" % suffix: p_pos,
        "ll_rel_pos_%s" % suffix: l_left_pos,
        "pl_rel_pos_%s" % suffix: p_left_pos,
        "lr_rel_pos_%s" % suffix: l_right_pos,
        "pr_rel_pos_%s" % suffix: p_right_pos,
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
    valid_obstacles = [
        (obstacle, get_obstacle_state_at_timestep(obstacle, ego_state.time_step))
        for obstacle in obstacles
        if get_obstacle_state_at_timestep(obstacle, ego_state.time_step) is not None
    ]
    front_obstacles = [
        obstacle
        for obstacle, obstacle_state in valid_obstacles
        if is_obstacle_in_front(ego_state, obstacle_state.position)
    ]
    return front_obstacles


def get_closest_obstacle(ego_state: State, obstacles: List[DynamicObstacle]) -> Union[None, DynamicObstacle]:
    if not obstacles:
        return None
    obstacle_states = [get_obstacle_state_at_timestep(obstacle, ego_state.time_step) for obstacle in obstacles]
    dists = [
        euclidean_distance(ego_state.position, obstacle_state.position)
        for obstacle_state in obstacle_states
        if obstacle_state is not None
    ]
    if not dists:
        return None
    min_idx = np.argmin(dists)
    return obstacles[int(min_idx)]


def get_closest_front_obstacle(scenario, ego_state):
    ego_lanelet, _, _ = get_lanelets(scenario.lanelet_network, ego_state)
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
        if closest_obstacle is None:
            continue

        obstace_state = get_obstacle_state_at_timestep(closest_obstacle, ego_state.time_step)
        ego_lanelet, _, _ = get_lanelets(scenario.lanelet_network, ego_state)
        curvy_coord = CurvilinearCoordinateSystem(ego_lanelet.center_vertices)
        dist = get_curvy_distance(ego_state.position, obstace_state.position, curvy_coord)  # distance center of gravity

        sensor_range = ego_state.velocity * 3 if sensor_range is None else sensor_range
        if dist > sensor_range:
            return -1, -1

        dist -= ego_vehicle.obstacle_shape.length / 2  # Assume rectangle, and ignore minor orientation diff
        dist += closest_obstacle.obstacle_shape.length / 2  # Assume rectangle and ignore minor orientation diff
        if dist < min_dhw:
            min_dhw = dist
            min_dhw_ts = ego_state.time_step

    min_dhw = round(min_dhw, 4) if not min_dhw == math.inf else -1
    return min_dhw, min_dhw_ts


def get_min_thw(scenario: Scenario, ego_vehicle: DynamicObstacle, sensor_range=SENSOR_RANGE) -> Tuple[float, int]:
    """
    Calculates the minimum Distance Headway for the ego vehicle.

    :param scenario: CommonRoad Scenario
    :param ego_vehicle: CommonRoad Dynamic Obstacle which represents the Ego Vehicle
    :return: float
    """
    min_thw = math.inf  # Upper Threshold
    min_thw_ts = -1
    for ego_state in get_obstacle_state_list(ego_vehicle):
        if ego_state.velocity <= 0:
            continue

        closest_obstacle = get_closest_front_obstacle(scenario, ego_state)
        if closest_obstacle is None:
            continue

        obstace_state = get_obstacle_state_at_timestep(closest_obstacle, ego_state.time_step)
        ego_lanelet, _, _ = get_lanelets(scenario.lanelet_network, ego_state)
        curvy_coord = CurvilinearCoordinateSystem(ego_lanelet.center_vertices)
        dist = get_curvy_distance(ego_state.position, obstace_state.position, curvy_coord)  # distance center of gravity

        sensor_range = ego_state.velocity * 3 if sensor_range is None else sensor_range
        if dist > sensor_range:
            return -1, -1

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
        if closest_obstacle is None:
            continue

        obstace_state = get_obstacle_state_at_timestep(closest_obstacle, ego_state.time_step)
        ego_lanelet, _, _ = get_lanelets(scenario.lanelet_network, ego_state)
        curvy_coord = CurvilinearCoordinateSystem(ego_lanelet.center_vertices)
        dist = get_curvy_distance(ego_state.position, obstace_state.position, curvy_coord)  # distance center of gravity

        sensor_range = ego_state.velocity * 3 if sensor_range is None else sensor_range
        if dist > sensor_range:
            return -1, -1

        dist -= ego_vehicle.obstacle_shape.length / 2  # Assume rectangle, and ignore minor orientation diff
        dist -= closest_obstacle.obstacle_shape.length / 2  # Assume rectangle and ignore minor orientation diff

        vel_diff = ego_state.velocity - obstace_state.velocity
        if vel_diff <= 0:
            continue

        ttc = dist / vel_diff
        if ttc < min_ttc:
            min_ttc = ttc
            min_ttc_ts = ego_state.time_step

    min_ttc = round(min_ttc, 4) if not min_ttc == math.inf else -1
    return min_ttc, min_ttc_ts


def changes_lane(lanelet_network: LaneletNetwork, obstacle):
    obstacle_states = get_obstacle_state_list(obstacle)
    for x0, x1 in zip(obstacle_states[:-1], obstacle_states[1:]):
        x0_lanelet, _, _ = get_lanelets(lanelet_network, x0)
        x1_lanelet, _, _ = get_lanelets(lanelet_network, x1)
        if x0_lanelet is None or x1_lanelet is None:
            continue
        if not x0_lanelet.lanelet_id == x1_lanelet.lanelet_id:
            lane_change_direction = -1 if x1_lanelet.lanelet_id == x0_lanelet.adj_left else +1
            lane_change_ts = x1.time_step
            return True, lane_change_direction, lane_change_ts
    return False, 0, -1


def get_cut_in_info(scenario: Scenario, ego_vehicle: DynamicObstacle, sensor_range=SENSOR_RANGE):
    dynamic_obstacles = scenario.dynamic_obstacles
    lc_obstacles = [
        (obstacle,) + changes_lane(scenario.lanelet_network, obstacle)[1:]
        for obstacle in dynamic_obstacles
        if changes_lane(scenario.lanelet_network, obstacle)[0]
    ]
    sorted_lc_obstacles = sorted(lc_obstacles, key=lambda x: x[2])

    for obstacle, lc_dir, lc_ts in sorted_lc_obstacles:
        obst_state = get_obstacle_state_at_timestep(obstacle, lc_ts)
        ego_state = get_obstacle_state_at_timestep(ego_vehicle, lc_ts)
        obst_lanelet, _, _ = get_lanelets(scenario.lanelet_network, obst_state)
        ego_lanelet, _, _ = get_lanelets(scenario.lanelet_network, ego_state)
        if obst_lanelet.lanelet_id == ego_lanelet.lanelet_id and is_obstacle_in_front(ego_state, obst_state.position):
            curvy_coord = CurvilinearCoordinateSystem(ego_lanelet.center_vertices)
            ego_state_before = get_obstacle_state_at_timestep(ego_vehicle, ego_state.time_step - 1)
            front_obst_before = get_closest_front_obstacle(scenario, ego_state_before)
            if front_obst_before is None:
                continue

            front_obst_bef_state = get_obstacle_state_at_timestep(front_obst_before, ego_state_before.time_step)
            dist_before = get_curvy_distance(ego_state_before.position, front_obst_bef_state.position, curvy_coord)

            sensor_range = ego_state_before.velocity * 3 if sensor_range is None else sensor_range
            dist_before = dist_before if dist_before <= sensor_range else sensor_range

            new_dist = get_curvy_distance(ego_state.position, obst_state.position, curvy_coord)
            dist_reduced = dist_before - new_dist
            if dist_reduced < 0:
                continue  # if the obstacle does not cut in directly in front

            return lc_dir, lc_ts, round(dist_reduced, 4)

    return 0, -1, -1
