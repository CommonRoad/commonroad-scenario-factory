from typing import List

import numpy as np
from commonroad.geometry.shape import Circle, Polygon, Rectangle, Shape, ShapeGroup
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.state import TraceState
from commonroad.scenario.trajectory import State


def get_obstacle_state_at_timestep(obstacle: DynamicObstacle, timestep):
    if timestep == 0:
        return obstacle.initial_state
    return obstacle.state_at_time(timestep)


def get_obstacle_state_list(obstacle: DynamicObstacle) -> List[State]:
    if not isinstance(obstacle.prediction, TrajectoryPrediction):
        return []
    return [obstacle.initial_state] + obstacle.prediction.trajectory.state_list


def find_shape_positions(shape: Shape) -> np.ndarray:
    if isinstance(shape, np.ndarray):
        return np.array([shape])
    if isinstance(shape, (Circle, Rectangle, Polygon)):
        return np.array([shape.center])
    if isinstance(shape, ShapeGroup):
        return np.array([position for shp in shape.shapes for position in find_shape_positions(shp)])


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


def changes_lane(lanelet_network: LaneletNetwork, obstacle: DynamicObstacle):
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
