import math

import numpy as np
from commonroad.common.file_writer import Tag
from commonroad.scenario.obstacle import DynamicObstacle
from commonroad.scenario.state import TraceState
from commonroad.scenario.traffic_sign import SupportedTrafficSignCountry
from commonroad.scenario.traffic_sign_interpreter import TrafficSignInterpreter
from commonroad.scenario.scenario import Lanelet, LaneletNetwork, Scenario
from commonroad.common.util import make_valid_orientation, Interval
from sumocr.sumo_config.default import ParamType

from scenario_factory.scenario_features.features import changes_lane, euclidean_distance, get_cut_in_info, \
    get_obstacle_state_list, \
    get_min_ego_acc, get_obstacle_state_at_timestep, get_lanelets, get_obstacles_in_lanelet, \
    get_min_ttc, get_min_dhw, get_min_thw
# from scenario_factory.cr_scenario_factory import GenerateCRScenarios
from commonroad.common.common_lanelet import LaneletType


# from scenario_factory.scenario_checker import check_collision

def assign_tags(list_ego_obstacles, scenario):
    tags = {Tag('simulated')}
    lanelet_network = scenario.lanelet_network
    dt = scenario.dt
    lanelets_ego_passed_through = set()
    obstacles = [obs for obs in scenario._dynamic_obstacles.values()]
    for ego_vehicle in list_ego_obstacles:
        ego_states = get_obstacle_states(ego_vehicle)
        ego_lanelets = get_lanelets_ego_passed_through(lanelet_network, ego_states)
        if Tag('traffic_jam') not in tags and merging_lanes(ego_lanelets):
            tags.add(Tag('merging_lanes'))

        ego_lanelets = set(ego_lanelets)
        if lane_following(len(ego_lanelets)):
            tags.add(Tag('lane_following'))

        lanelets_ego_passed_through.update(ego_lanelets)

        if Tag('traffic_jam') not in tags and is_traffic_jam(ego_states, obstacles):
            tags.add(Tag('traffic_jam'))
        if Tag('emergency_braking') not in tags and is_emergency_braking(ego_states):
            tags.add(Tag('emergency_braking'))
        if Tag('oncoming_traffic') not in tags and identify_oncoming_traffic(lanelet_network, ego_states, obstacles):
            tags.add(Tag('oncoming_traffic'))

        # comfort, critical, evasive, illegal_cut_in, lane_change
        tags.update(feature_wrapper_tags(scenario, ego_vehicle))

        # turn_left, turn_right
        tags.update(determine_turn_directions(ego_states))

    if Tag('oncoming_traffic') not in tags:
        # there is no oncoming traffic in the whole scenario
        tags.add(Tag('no_oncoming_traffic'))

    # single, two, multi, parallel lane
    # rural, slip_road, highway, interstate, urban, intersection
    tags.update(tag_lanelet(lanelets_ego_passed_through))

    # speed_limit, race_track, roundabout
    tags.update(tag_traffic_sign(lanelet_network, lanelets_ego_passed_through,
                                 scenario.scenario_id.country_id))
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


def lane_following(num_lanelets):
    return num_lanelets == 1


def merging_lanes(lanelets: [Lanelet]):
    # input: lanelets the ego vehicle passed through
    for i in range(len(lanelets) -1):
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
        tags.add(Tag('critical'))
    if lane_change(lc_ts):
        tags.add(Tag('lane_change'))
    if illegal_cut_in(cut_in_ts):
        tags.add(Tag('illegal_cut_in'))
    if is_comfort(min_acc):
        tags.add(Tag('comfort'))
    if has_evasive_behavior(min_ttc, min_ttc_ts):
        tags.add(Tag('evasive'))
    return tags


def is_critical(min_dhw, min_thw, min_ttc, dhw_threshold: float = 5.0, thw_threshold: float = 1.0,
                ttc_threshold: float = 1.0):
    # a very simplified version using features
    # small TTC indicates a high likelihood of collision
    # small THW suggests that the ego vehicle needs to respond quickly
    # small DHW suggests that the vehicle is close to other vehicle in space
    return min_thw < thw_threshold and min_dhw < dhw_threshold and min_ttc < ttc_threshold


def lane_change(lc_ts):
    return lc_ts != -1


def illegal_cut_in(cut_in_ts):
    return cut_in_ts != -1


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
            tags.add(Tag('turn_right'))
        if diff < -turning_detection_threshold:
            tags.add(Tag('turn_left'))
    return tags


def get_closest_distance(ego_state, obstacles):
    obstacle_states = [get_obstacle_state_at_timestep(obstacle, ego_state.time_step) for obstacle in obstacles]
    dists = [euclidean_distance(ego_state.position, obstacle_state.position)
             for obstacle_state in obstacle_states if obstacle_state is not None]
    if not dists:
        return None
    min_dist = min(dists)
    return min_dist


def is_traffic_jam(states, obstacles, time_threshold=10, velocity_threshold=1.0,
                   distance_threshold=5.0, acceleration_threshold=0.0):
    velocities = [state.velocity for state in states]
    distances = [get_closest_distance(state, obstacles) for state in states]
    accelerations = [state.acceleration for state in states]

    in_traffic_jam = False
    last_non_traffic_jam_index = 0
    traffic_jam_periods = []

    for i in range(len(states)):
        if ((velocities[i] is None or velocities[i] < velocity_threshold) and
                (accelerations[i] is None or accelerations[i] < acceleration_threshold)):
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
            min_distance = min(distances[start:end + 1])
            if min_distance < distance_threshold:
                return True
    return False


#
def is_emergency_braking(states: [TraceState], braking_detection_threshold: float = -3.0,
                         min_braking_detection_ts: int = 4):
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


def identify_oncoming_traffic(lanelet_network: LaneletNetwork, states: [TraceState], all_obstacles,
                              distance_threshold=5.0, orientation_threshold=np.deg2rad(90)):
    for ego_state in states:
        ego_lanelet, adj_left_lanelet, adj_right_lanelet = get_lanelets(lanelet_network, ego_state)
        obstacles = [obstacle for lanelet in [ego_lanelet, adj_left_lanelet, adj_right_lanelet] if lanelet is not None
                     for obstacle in get_obstacles_in_lanelet(all_obstacles, lanelet, ego_state.time_step)]
        ego_position = ego_state.position
        ego_orientation = ego_state.orientation

        oncoming_traffic = []

        for obstacle in obstacles:
            try:
                other_state = obstacle.prediction.trajectory.state_list[ego_state.time_step - 1]
            except IndexError:
                continue
            other_position = other_state.position
            other_orientation = other_state.orientation

            relative_position = (other_position[0] - ego_position[0], other_position[1] - ego_position[1])
            relative_orientation = abs(other_orientation - ego_orientation)

            distance = math.sqrt(relative_position[0] ** 2 + relative_position[1] ** 2)

            if distance < distance_threshold and orientation_threshold < relative_orientation:
                return True

    return False


def tag_traffic_sign(lanelet_network: LaneletNetwork, lanelets: {Lanelet}, country: SupportedTrafficSignCountry):
    tags = set()
    # traffic sign: roundabout, racetrack
    interpreter = TrafficSignInterpreter(country, lanelet_network)
    traffic_sign_ids = interpreter.traffic_sign_ids
    if interpreter.speed_limit(frozenset([lane.lanelet_id for lane in lanelets])) is not None:
        tags.add(Tag('speed_limit'))
    for lanelet in lanelets:
        for traffic_sign_id in lanelet.traffic_signs:
            traffic_sign = lanelet_network.find_traffic_sign_by_id(traffic_sign_id)
            for elem in traffic_sign.traffic_sign_elements:
                if sign := getattr(traffic_sign_ids, 'RACE_TRACK', None):
                    if elem.traffic_sign_element_id == sign:
                        tags.add(Tag('RACE_TRACK'))
                if sign := getattr(traffic_sign_ids, 'ROUNDABOUT', None):
                    if elem.traffic_sign_element_id == sign:
                        tags.add(Tag('ROUNDABOUT'))
    return tags


def tag_lanelet(lanelets: {Lanelet}):
    tags = set()
    all_lanelet_types = set()

    for lanelet in lanelets:
        if lanelet.adj_left is None and lanelet.adj_right is None:
            tags.add(Tag('single_lane'))

        if (lanelet.adj_left is not None or lanelet.adj_right is not None) and \
                (lanelet.adj_left_same_direction or lanelet.adj_right_same_direction):
            tags.add(Tag('two_lane'))  # same direction

        if (lanelet.adj_left is not None and lanelet.adj_right is not None) and \
                (lanelet.adj_left_same_direction is False or lanelet.adj_right_same_direction is False):
            tags.add(Tag('multi_lane'))  # opposite directions

        if (lanelet.adj_left is not None and lanelet.adj_right is not None) and \
                (lanelet.adj_left_same_direction and lanelet.adj_right_same_direction):
            tags.add(Tag('parallel_lanes'))

        if lanelet.lanelet_type:
            all_lanelet_types.update(lanelet.lanelet_type)

    if LaneletType.COUNTRY in all_lanelet_types:
        tags.add(Tag('rural'))

    if LaneletType.EXIT_RAMP or LaneletType.ACCESS_RAMP in all_lanelet_types:
        tags.add(Tag('slip_road'))

    if LaneletType.HIGHWAY in all_lanelet_types:
        tags.add(Tag('highway'))

    if LaneletType.INTERSTATE in all_lanelet_types:
        tags.add(Tag('interstate'))

    if LaneletType.INTERSECTION in all_lanelet_types:
        tags.add(Tag('intersection'))

    if LaneletType.URBAN in all_lanelet_types:
        tags.add(Tag('urban'))

    return tags
