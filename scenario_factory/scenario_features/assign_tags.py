import math
from typing import Sequence, Set

import numpy as np
from commonroad.common.common_lanelet import LaneletType
from commonroad.common.file_writer import Tag
from commonroad.common.util import make_valid_orientation
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.scenario import Lanelet, LaneletNetwork, Scenario
from commonroad.scenario.state import TraceState
from commonroad.scenario.traffic_sign import SupportedTrafficSignCountry
from commonroad.scenario.traffic_sign_interpreter import TrafficSignInterpreter

from scenario_factory.scenario_features.features import (
    changes_lane,
    euclidean_distance,
    get_cut_in_info,
    get_lanelets,
    get_min_dhw,
    get_min_ego_acc,
    get_min_thw,
    get_min_ttc,
    get_obstacle_state_at_timestep,
    get_obstacles_in_lanelet,
    is_obstacle_in_front,
)


def find_applicable_tags_for_scenario(scenario: Scenario, ego_vehicle: DynamicObstacle) -> Set[Tag]:
    tags = {Tag.SIMULATED}

    lanelet_network = scenario.lanelet_network
    # dt = scenario.dt
    ego_states = get_obstacle_states(ego_vehicle)
    lanelets_ego_passed_through = get_lanelets_ego_passed_through(lanelet_network, ego_states)
    if Tag.TRAFFIC_JAM not in tags and merging_lanes(lanelets_ego_passed_through):
        tags.add(Tag.MERGING_LANES)

    if lane_following(ego_vehicle):
        tags.add(Tag.LANE_FOLLOWING)

    if Tag.TRAFFIC_JAM not in tags and is_traffic_jam(ego_states, scenario.dynamic_obstacles):
        tags.add(Tag.TRAFFIC_JAM)
    if Tag.EMERGENCY_BRAKING not in tags and is_emergency_braking(ego_states):
        tags.add(Tag.EMERGENCY_BRAKING)
    if Tag.ONCOMING_TRAFFIC not in tags and identify_oncoming_traffic(
        lanelet_network, ego_states, scenario.dynamic_obstacles
    ):
        tags.add(Tag.ONCOMING_TRAFFIC)

    # comfort, critical, evasive, illegal_cut_in, lane_change
    tags.update(feature_wrapper_tags(scenario, ego_vehicle))

    # turn_left, turn_right
    tags.update(determine_turn_directions(ego_states))

    # single, two, multi, parallel lane
    # rural, slip_road, highway, interstate, urban, intersection
    tags.update(tag_lanelet(lanelets_ego_passed_through))

    # speed_limit, race_track, roundabout
    tags.update(tag_traffic_sign(lanelet_network, lanelets_ego_passed_through, scenario.scenario_id.country_id))

    if Tag.ONCOMING_TRAFFIC not in tags:
        # there is no oncoming traffic in the whole scenario
        tags.add(Tag.NO_ONCOMING_TRAFFIC)

    return tags


def get_obstacle_states(obstacle: DynamicObstacle):
    return obstacle.prediction.trajectory.state_list


def get_lanelets_ego_passed_through(lanelet_network: LaneletNetwork, ego_states: [TraceState]) -> [Lanelet]:
    ego_lanelets = []
    for ego_state in ego_states:
        ego_lanelet_ids = lanelet_network.find_lanelet_by_position([ego_state.position])[0]
        if not ego_lanelet_ids:
            return []
        ego_lanelet_id = ego_lanelet_ids[0]
        ego_lanelet = lanelet_network.find_lanelet_by_id(ego_lanelet_id)
        ego_lanelets.append(ego_lanelet)
    return ego_lanelets


def lane_following(ego: DynamicObstacle):
    # Alternative: num_lanelets == 1
    assignments = ego.prediction.center_lanelet_assignment
    if assignments is None:
        return False
    ids = ego.center_lanelet_ids_history
    return bool(set(ids) & set.union(*assignments.values()))


def merging_lanes(lanelets: [Lanelet]):
    # input: lanelets the ego vehicle passed through
    for i in range(len(lanelets) - 1):
        current_lane = lanelets[i]
        next_id = lanelets[i + 1].lanelet_id
        if current_lane.lanelet_id == next_id:
            continue
        successors = current_lane.successor
        if not successors or len(successors) < 2:
            continue
        if next_id in successors:
            return True
    return False


def feature_wrapper_tags(scenario: Scenario, ego_vehicle: DynamicObstacle):
    tags = set()
    lanelet_network = scenario.lanelet_network
    dt = scenario.dt
    min_ttc, min_ttc_ts = get_min_ttc(scenario, ego_vehicle)
    min_dhw, min_dhw_ts = get_min_dhw(scenario, ego_vehicle)
    min_thw, min_thw_ts = get_min_thw(scenario, ego_vehicle)
    _, _, lc_ts = changes_lane(lanelet_network, ego_vehicle)
    _, cut_in_ts, _ = get_cut_in_info(scenario, ego_vehicle)
    min_acc = get_min_ego_acc(ego_vehicle, dt)

    if is_critical(min_dhw, min_thw, min_ttc):
        tags.add(Tag.CRITICAL)
    if lane_change(lc_ts):
        tags.add(Tag.LANE_CHANGE)
    if illegal_cut_in(cut_in_ts, ego_vehicle, dt):
        tags.add(Tag.ILLEGAL_CUTIN)
    if is_comfort(min_acc):
        tags.add(Tag.COMFORT)
    if has_evasive_behavior(min_ttc, min_ttc_ts):
        tags.add(Tag.EVASIVE)
    return tags


def is_critical(
    min_dhw, min_thw, min_ttc, dhw_threshold: float = 5.0, thw_threshold: float = 1.0, ttc_threshold: float = 1.0
):
    # a very simplified version using features
    # small TTC indicates a high likelihood of collision
    # small THW suggests that the ego vehicle needs to respond quickly
    # small DHW suggests that the vehicle is close to other vehicle in space
    return min_thw < thw_threshold and min_dhw < dhw_threshold and min_ttc < ttc_threshold


def lane_change(lc_ts):
    return lc_ts != -1


def illegal_cut_in(cut_in_ts, ego, dt):
    if cut_in_ts == -1:
        return False
    state = ego.prediction.trajectory.state_list[cut_in_ts * dt - 1]
    if state.acceleration < -2.0:
        return True
    return False


def is_comfort(min_acc, acc_threshold=1.0):
    return -acc_threshold < min_acc < acc_threshold


def has_evasive_behavior(min_ttc, min_ttc_ts, evasive_threshold=2.0):
    # vehicles with collisions are already deleted while selecting ego vehicles
    # no need to check if it crashes
    return min_ttc < evasive_threshold and min_ttc_ts != -1


def determine_turn_directions(ego_states: [TraceState], turning_detection_threshold: float = np.deg2rad(30)):
    tags = set()
    orientations = [state.orientation for state in ego_states]
    for i in range(1, len(orientations)):
        if orientations[i - 1] is None or orientations[i] is None:
            break
        diff = orientations[i] - orientations[i - 1]
        diff = make_valid_orientation(diff)
        if diff > turning_detection_threshold:
            tags.add(Tag.TURN_RIGHT)
        if diff < -turning_detection_threshold:
            tags.add(Tag.TURN_LEFT)
    return tags


def get_closest_distance(ego_state, obstacles):
    obstacle_states = [get_obstacle_state_at_timestep(obstacle, ego_state.time_step) for obstacle in obstacles]
    dists = [
        euclidean_distance(ego_state.position, obstacle_state.position)
        for obstacle_state in obstacle_states
        if obstacle_state is not None
    ]
    if not dists:
        return None
    min_dist = min(dists)
    return min_dist


def is_traffic_jam(
    states, obstacles, time_threshold=10, velocity_threshold=1.0, distance_threshold=5.0, acceleration_threshold=0.0
):
    velocities = [state.velocity for state in states]
    distances = [get_closest_distance(state, obstacles) for state in states]
    accelerations = [state.acceleration for state in states]

    in_traffic_jam = False
    last_non_traffic_jam_index = 0
    traffic_jam_periods = []

    for i in range(len(states)):
        if (velocities[i] is None or velocities[i] < velocity_threshold) and (
            accelerations[i] is None or accelerations[i] < acceleration_threshold
        ):
            if not in_traffic_jam:
                in_traffic_jam = True
                last_non_traffic_jam_index = i
        else:
            if in_traffic_jam:
                in_traffic_jam = False
                traffic_jam_periods.append((last_non_traffic_jam_index, i - 1))

    if in_traffic_jam:
        traffic_jam_periods.append((last_non_traffic_jam_index, len(states) - 1))

    for start, end in traffic_jam_periods:
        if end - start > time_threshold:
            min_distance = min(distances[start : end + 1])
            if min_distance < distance_threshold:
                return True
    return False


#
def is_emergency_braking(
    states: Sequence[TraceState], braking_detection_threshold: float = -3.0, min_braking_detection_ts: int = 4
):
    accelerations = [state.acceleration for state in states]
    braking_ts_count = 0
    braking = False
    for acceleration in accelerations:
        if acceleration <= braking_detection_threshold:
            braking = True
        elif acceleration > 0:
            braking = False
            braking_ts_count = 0
        if braking:
            braking_ts_count += 1
            if braking_ts_count >= min_braking_detection_ts:
                return True
    return False


def identify_oncoming_traffic(
    lanelet_network: LaneletNetwork,
    states: Sequence[TraceState],
    all_obstacles,
    distance_threshold=5.0,
    orientation_threshold=np.deg2rad(30),
):
    for ego_state in states:
        ego_lanelet, adj_left_lanelet, adj_right_lanelet = get_lanelets(lanelet_network, ego_state)
        obstacles = [
            obstacle
            for lanelet in [ego_lanelet, adj_left_lanelet, adj_right_lanelet]
            if lanelet is not None
            for obstacle in get_obstacles_in_lanelet(all_obstacles, lanelet, ego_state.time_step)
        ]
        ego_position = ego_state.position
        ego_orientation = ego_state.orientation

        for obstacle in obstacles:
            try:
                other_state = obstacle.prediction.trajectory.state_list[ego_state.time_step - 1]
            except IndexError:
                continue

            other_position = other_state.position
            if not is_obstacle_in_front(ego_state, other_position):
                continue

            relative_position = (other_position[0] - ego_position[0], other_position[1] - ego_position[1])
            distance = math.sqrt(relative_position[0] ** 2 + relative_position[1] ** 2)
            if not distance < distance_threshold:
                continue

            other_orientation = other_state.orientation
            relative_orientation = abs(abs(other_orientation - ego_orientation) - math.pi)

            if orientation_threshold < relative_orientation:
                return True

    return False


def tag_traffic_sign(
    lanelet_network: LaneletNetwork, lanelets: Sequence[Lanelet], country: SupportedTrafficSignCountry
):
    tags = set()
    interpreter = TrafficSignInterpreter(country, lanelet_network)
    traffic_sign_ids = interpreter.traffic_sign_ids
    if interpreter.speed_limit(frozenset([lane.lanelet_id for lane in lanelets])) is not None:
        tags.add(Tag.SPEED_LIMIT)
    for lanelet in lanelets:
        for traffic_sign_id in lanelet.traffic_signs:
            traffic_sign = lanelet_network.find_traffic_sign_by_id(traffic_sign_id)
            for elem in traffic_sign.traffic_sign_elements:
                if sign := getattr(traffic_sign_ids, "RACE_TRACK", None):
                    if elem.traffic_sign_element_id == sign:
                        tags.add(Tag.RACE_TRACK)
                if sign := getattr(traffic_sign_ids, "ROUNDABOUT", None):
                    if elem.traffic_sign_element_id == sign:
                        tags.add(Tag.ROUNDABOUT)
    return tags


def tag_lanelet(lanelets: Sequence[Lanelet]):
    tags = set()
    all_lanelet_types = set()

    for lanelet in lanelets:
        if lanelet.adj_left is None and lanelet.adj_right is None:
            tags.add(Tag.SINGLE_LANE)

        if (lanelet.adj_left is not None or lanelet.adj_right is not None) and (
            lanelet.adj_left_same_direction or lanelet.adj_right_same_direction
        ):
            tags.add(Tag.TWO_LANE)  # same direction

        if (lanelet.adj_left is not None and lanelet.adj_right is not None) and (
            lanelet.adj_left_same_direction is False or lanelet.adj_right_same_direction is False
        ):
            tags.add(Tag.MULTI_LANE)  # opposite directions

        if (lanelet.adj_left is not None and lanelet.adj_right is not None) and (
            lanelet.adj_left_same_direction and lanelet.adj_right_same_direction
        ):
            tags.add(Tag.PARALLEL_LANES)

        if lanelet.lanelet_type:
            all_lanelet_types.update(lanelet.lanelet_type)

    if LaneletType.COUNTRY in all_lanelet_types:
        tags.add(Tag.RURAL)

    if LaneletType.EXIT_RAMP or LaneletType.ACCESS_RAMP in all_lanelet_types:
        tags.add(Tag.SLIP_ROAD)

    if LaneletType.HIGHWAY in all_lanelet_types:
        tags.add(Tag.HIGHWAY)

    if LaneletType.INTERSTATE in all_lanelet_types:
        tags.add(Tag.INTERSTATE)

    if LaneletType.INTERSECTION in all_lanelet_types:
        tags.add(Tag.INTERSECTION)

    if LaneletType.URBAN in all_lanelet_types:
        tags.add(Tag.URBAN)

    return tags
