import math

import numpy as np
from commonroad.common.file_writer import Tag
from commonroad.scenario.traffic_sign import SupportedTrafficSignCountry
from commonroad.scenario.traffic_sign_interpreter import TrafficSigInterpreter
from commonroad.scenario.scenario import Lanelet, LaneletNetwork
from commonroad.common.util import make_valid_orientation
from scenario_factory.scenario_features.features import changes_lane, euclidean_distance, get_cut_in_info, get_obstacle_state_list, \
    get_min_ego_acc, get_obstacle_state_at_timestep, get_lanelets, get_obstacles_in_lanelet, \
    get_min_ttc, get_min_dhw, get_min_thw
from scenario_factory.cr_scenario_factory import GenerateCRScenarios
from commonroad.common.common_lanelet import LaneletType
# from scenario_factory.scenario_checker import check_collision


def assign_tags(cr_scenario: GenerateCRScenarios):
    tags = {Tag('simulated')}

    lanelet_network = cr_scenario.lanelet_network
    ego_list = cr_scenario.list_ego_obstacles
    scenario = cr_scenario.scenario
    obstacles = cr_scenario.veh_ids
    dt = scenario.dt
    lanelets_ego_passed_through = set()

    for ego_vehicle in ego_list:
        ego_states = get_obstacle_state_list(ego_vehicle)
        lanelets_ego_passed_through.update(get_lanelets_ego_passed_through(lanelet_network, ego_states))
        if lane_change(lanelet_network, ego_vehicle):
            tags.add(Tag('lane_change'))
        if illegal_cut_in(scenario, ego_vehicle):
            tags.add(Tag('illegal_cut_in'))
        if is_comfort(ego_vehicle, dt):
            tags.add(Tag('comfort'))
        if is_emergency_braking(ego_vehicle):
            tags.add(Tag('emergency_braking'))
        if has_evasive_behavior(scenario, ego_vehicle):
            tags.add(Tag('evasive'))
        if is_critical(scenario, ego_vehicle):
            tags.add(Tag('critical'))
        if is_lane_following(lanelet_network, ego_states):
            tags.add(Tag('lane_following'))
        if is_traffic_jam(ego_vehicle, obstacles):
            tags.add(Tag('traffic_jam'))
        if identify_oncoming_traffic(lanelet_network, ego_states, obstacles):
            tags.add(Tag('oncoming_traffic'))
        else:
            tags.add(Tag('no_oncoming_traffic'))

        tags.update(determine_turn_directions(ego_vehicle))

    # lanelet based tags
    tags.update(tag_lanelet(lanelets_ego_passed_through))
    tags.update(tag_traffic_sign(lanelet_network, lanelets_ego_passed_through,
                                 cr_scenario.scenario.scenario_id.country_id))
    return tags


def is_critical(scenario, ego_vehicle, dhw_threshold: float = 1.0, thw_threshold: float = 5.0,
                ttc_threshold: float = 2.0):
    # a very simplified version using features
    min_dhw, _ = get_min_dhw(scenario, ego_vehicle)
    min_thw, _ = get_min_thw(scenario, ego_vehicle)
    min_ttc, _ = get_min_ttc(scenario, ego_vehicle)
    return min_thw < thw_threshold and min_dhw < dhw_threshold and min_ttc < ttc_threshold


def lane_change(lanelet_network, ego_vehicle):
    ego_lc, _, _ = changes_lane(lanelet_network, ego_vehicle)
    return ego_lc


def illegal_cut_in(scenario, ego_vehicle):
    cut_in_dir, cut_in_ts, cut_in_dist_reduced = get_cut_in_info(scenario, ego_vehicle)
    return cut_in_ts != -1


def is_comfort(ego_vehicle, dt):
    return get_min_ego_acc(ego_vehicle, dt) < 1.0


def determine_turn_directions(ego_vehicle, turning_detection_threshold: float = np.deg2rad(60)):
    tags = set()
    states = get_obstacle_state_list(ego_vehicle)
    orientations = [state.orientation for state in states]
    for i in range(1, len(orientations)):
        if orientations[i - 1] is None or orientations[i] is None:
            break
        diff = orientations[i] - orientations[i - 1]
        diff = make_valid_orientation(diff)
        if diff > turning_detection_threshold:
            tags.add(Tag('turn_right'))
        elif diff < -turning_detection_threshold:
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


def is_traffic_jam(ego_vehicle, obstacles, time_threshold=10, velocity_threshold=1.0,
                   distance_threshold=5.0, acceleration_threshold=0.2):
    states = get_obstacle_state_list(ego_vehicle)
    velocities = [state.velocity for state in states]
    distances = [get_closest_distance(state, obstacles) for state in states]
    accelerations = [state.acceleration for state in states]
    times = [state.time for state in states]

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
        if times[end] - times[start] > time_threshold:
            min_distance = min(distances[start:end + 1])
            if min_distance < distance_threshold:
                return True
    return False


def get_lanelets_ego_passed_through(lanelet_network: LaneletNetwork, ego_states) -> {Lanelet}:
    ego_lanelets = set()
    for ego_state in ego_states:
        ego_lanelet_ids = lanelet_network.find_lanelet_by_position([ego_state.position])[0]
        if not ego_lanelet_ids:
            return []
        ego_lanelet_id = ego_lanelet_ids[0]
        ego_lanelet = lanelet_network.find_lanelet_by_id(ego_lanelet_id)
        ego_lanelets.add(ego_lanelet)
    return ego_lanelets


def is_lane_following(lanelet_network, states):
    for state in states:
        ego_lanelet_ids = lanelet_network.find_lanelet_by_position(state.position)
        if len(ego_lanelet_ids) == 1:
            return True
    return False


#
def is_emergency_braking(ego_vehicle, braking_detection_threshold: float = -3.0, min_braking_detection_ts: int = 4):
    states = get_obstacle_state_list(ego_vehicle)
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


def has_evasive_behavior(scenario, ego_vehicle, evasive_threshold=2.0):
    min_ttc, min_ttc_ts = get_min_ttc(scenario, ego_vehicle)
    return min_ttc < evasive_threshold and min_ttc_ts != -1


def identify_oncoming_traffic(lanelet_network, all_obstacles, states, distance_threshold=5.0):
    for ego_state in states:
        ego_lanelet, adj_left_lanelet, adj_right_lanelet = get_lanelets(lanelet_network, ego_state)
        obstacles = [get_obstacles_in_lanelet(all_obstacles, lanelet, ego_state.time) for lanelet in
                     [ego_lanelet, adj_left_lanelet, adj_right_lanelet]]
        ego_position = ego_state.position
        ego_orientation = ego_state.orientation

        oncoming_traffic = []

        for obstacle in obstacles:
            other_state = obstacle.state
            other_position = other_state.position
            other_orientation = other_state.orientation

            relative_position = (other_position[0] - ego_position[0], other_position[1] - ego_position[1])
            relative_orientation = other_orientation - ego_orientation

            distance = math.sqrt(relative_position[0] ** 2 + relative_position[1] ** 2)
            angle = math.atan2(relative_position[1], relative_position[0])

            oncoming = (
                    distance < distance_threshold
                    and -math.pi / 4 < relative_orientation < math.pi / 4
            )

            oncoming_traffic.append(oncoming)

        if any(oncoming_traffic):
            return True

    return False


def tag_traffic_sign(lanelet_network: LaneletNetwork, lanelets: {Lanelet}, country: SupportedTrafficSignCountry):
    tags = set()
    # traffic sign: roundabout, racetrack
    interpreter = TrafficSigInterpreter(country, lanelet_network)
    traffic_sign_ids = interpreter.traffic_sign_ids

    for lanelet in lanelets:
        for traffic_sign_id in lanelet.traffic_signs:
            traffic_sign = lanelet_network.find_traffic_sign_by_id(traffic_sign_id)
            for elem in traffic_sign.traffic_sign_elements:
                if elem.traffic_sign_element_id == traffic_sign_ids.RACE_TRACK:
                    tags.add(Tag('speed_limit'))
                if elem.traffic_sign_element_id == traffic_sign_ids.RACE_TRACK:
                    tags.add(Tag('race_track'))
                if elem.traffic_sign_element_id == traffic_sign_ids.ROUNDABOUT:
                    tags.add(Tag('round_about'))
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
            tags.add(Tag('parallel_lane'))

        # alternative: passes_merging_lane(obstacle: DynamicObstacle)
        if len(lanelet.successor) > 1:
            tags.add(Tag('merging_lanes'))

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

    if LaneletType.URBAN in all_lanelet_types:
        tags.add(Tag('urban'))

    if LaneletType.INTERSECTION in all_lanelet_types:
        tags.add(Tag('intersection'))

    return tags