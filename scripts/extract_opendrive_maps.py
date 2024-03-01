"""
Extract CommonRoad maps from large OpenDrive file
"""
import glob
import itertools
import os
import time
import warnings
from copy import deepcopy
from functools import lru_cache
from typing import Dict, List, Set

import matplotlib
import networkx as nx
import numpy as np
from autocorrect_intersections import ScenarioFixer
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.common.util import Interval
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem, PlanningProblemSet
from commonroad.scenario.intersection import Intersection
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork, LaneletType
from commonroad.scenario.obstacle import ObstacleType
from commonroad.scenario.scenario import Scenario, Tag
from commonroad.scenario.trajectory import State
from commonroad.visualization.mp_renderer import MPRenderer
from commonroad_dc import pycrcc
from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_object
from commonroad_dc.pycrcc import CollisionChecker
from commonroad_route_planner.route_planner import RoutePlanner
from crdesigner.map_conversion.opendrive.opendrive_conversion.network import Network
from crdesigner.map_conversion.opendrive.opendrive_parser.parser import parse_opendrive
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from crdesigner.map_conversion.sumo_map.util import erode_lanelet
from evaluate_solutions import timeout
from lxml import etree
from matplotlib import pyplot as plt
from shapely.geometry import LineString
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.maps.sumo_scenario import ScenarioWrapper

matplotlib.use("TkAgg")


convert_od = False
plot = False
use_full_map = False
extract = True
sumo_use_extracted = True
convert_sumo = True
save_full_map = False
sumo_simulate = False
seed = 200
np.random.seed(seed)

# extraction settings
map_name = "Frankfurt"
n_maps = 200
map_id_0 = 100
erosion_radius = 0.6
allowed_lanelet_types = {LaneletType.DRIVE_WAY}
forbidden_lanelet_types = {LaneletType.EXIT_RAMP}
min_length_route = 300

# sumo settings
CONFIG = SumoConfig

# folder = "/home/klischat/GIT_REPOS/commonroad-map-tool/test/opendrive_test_files"
folder = "/home/klischat/Downloads/xodr_out/in"
f = list(glob.glob(os.path.join(folder, "*.xodr"), recursive=True))[1]
f = os.path.join(folder, "el-vendrell-02.06.20.xodr")
f = os.path.join(folder, "KA-Suedtangente-atlatec.xodr")
# f = os.path.join(folder, "SanFrancisco-Downtown-Sample-OpenDrive.xodr")
f = os.path.join(folder, "Ko_HAF_OpenDRIVE_07_05_2018_Frankfurt_phase2.xodr")
# f = os.path.join(folder, "SanFranciscoComplete.xodr")

# if ii != 1:
#     continue
print(str(f))
cr_name = str(os.path.basename(f))[:-4].replace("-", "").replace("_", "").replace(".", "")
cr_file = os.path.join("/home/klischat/Downloads/xodr_out/raw_maps_phase2", cr_name + ".xml")
# cr_file = "/home/klischat/Downloads/xodr_out/raw_maps/KoHAFOpenDRIVE07052018Frankfurt-1.xml"
path_cr_map_full = os.path.join("/home/klischat/Downloads/xodr_out/cr_maps/", cr_name + "full.xml")
path_cr_map_full = os.path.join("/home/klischat/Downloads/xodr_out/cr_maps_phase2/", cr_name + "full.xml")

map_folder_extracted = os.path.join("/home/klischat/Downloads/xodr_out", cr_name)
if not os.path.exists(map_folder_extracted):
    os.mkdir(map_folder_extracted)

param_id = 1
# set map specific parameters
id_lanelets_start = None
ids_lanelets_goal = None
min_length_extract = None
map_settings = {
    "KASuedtangenteatlatec": {
        1: {
            "id_lanelets_start": [154],
            "ids_lanelets_goal": [130],
            "min_length_extract": 150,
        },
        2: {
            "id_lanelets_start": [143],
            "ids_lanelets_goal": [165],
            "min_length_extract": 150,
        },
    },
    "SanFranciscoDowntownSampleOpenDrive": {1: {}},
    "KoHAFOpenDRIVE07052018Frankfurt": {
        1: {
            "id_lanelets_start": [1333],
            "ids_lanelets_goal": [413],
            "min_length_extract": 400,
        }
    },
    "KoHAFOpenDRIVE07052018Frankfurtphase2": {
        1: {
            # "id_lanelets_start": [1333],
            # "ids_lanelets_goal": [413],
            "min_length_extract": 400,
        }
    },
}

if convert_od is True:
    # OpenDRIVE parser to load file

    with open("{}".format(str(f)), "r") as file_in:
        opendrive = parse_opendrive(etree.parse(file_in).getroot())

    # create OpenDRIVE intermediate network object
    road_network = Network()

    # convert OpenDRIVE file
    road_network.load_opendrive(opendrive)

    # export to CommonRoad scenario
    scenario = road_network.export_commonroad_scenario(
        map_name=cr_name, map_id=0, filter_types=["driving", "onRamp", "offRamp", "exit", "entry"]
    )

    # store converted file as CommonRoad scenario
    writer = CommonRoadFileWriter(
        scenario=scenario,
        planning_problem_set=PlanningProblemSet(),
        author="",
        affiliation="",
        source="OpenDRIVE 2 Lanelet Converter",
        tags={Tag.URBAN, Tag.HIGHWAY},
    )
    writer.write_to_file(cr_file, OverwriteExistingFile.ALWAYS)
    scenario, pp = CommonRoadFileReader(cr_file).open()
    warnings.warn("deleted all trafic lights")
    scenario.lanelet_network._traffic_lights = {}
    scenario.lanelet_network.cleanup_traffic_light_references()
    ScenarioFixer(scenario).autofit_long_incomings()
    ScenarioFixer(scenario).delete_traffic_light_if_no_intersection()
    ScenarioFixer(scenario).delete_redundant_incomings()
    writer = CommonRoadFileWriter(
        scenario=scenario,
        planning_problem_set=PlanningProblemSet(),
        author="",
        affiliation="",
        source="OpenDRIVE 2 Lanelet Converter",
        tags={Tag.URBAN, Tag.HIGHWAY},
    )
    writer.write_to_file(cr_file, OverwriteExistingFile.ALWAYS)

# get map specific parameters
for param, value in map_settings[cr_name][param_id].items():
    exec(f"{param} = {value}")


def poly_intersect(line1, line2):
    if len(line1) < 4 or len(line2) < 4:
        return False

    ls1 = LineString(line1[1:-1])
    ls2 = LineString(line2[1:-1])
    return ls1.intersects(ls2)


def lanelet_intersects(lanelet, cc: pycrcc.CollisionChecker):
    objects = cc.find_all_colliding_objects(l2co[lanelet.lanelet_id])
    if len(objects) > 0:
        return True
    else:
        return False


def self_intersects(line1):
    if len(line1) < 4:
        return False
    ls1 = LineString(line1[1:-1])
    return not ls1.is_simple


l2co = {}
co2l = {}


@lru_cache(1000)
def is_lanelet_valid(lanelet_id: int, lanelet_network):
    return lanelet_network.find_lanelet_by_id(lanelet_id).convert_to_polygon().shapely_object.is_valid


def remove_intersecting_lanelets(lanelets: Dict[int, Lanelet], other_lanelets: Dict[int, Lanelet], erosion_radius):
    delete_ids = set()
    lanelets_union = dict(other_lanelets)
    lanelets_union.update(lanelets)
    lanelets_union = {l_id: erode_lanelet(deepcopy(l), radius=erosion_radius) for l_id, l in lanelets_union.items()}
    lanelets_eroded = {l_id: lanelet for l_id, lanelet in lanelets_union.items() if l_id in lanelets}
    # rnd = MPRenderer(draw_params={"lanelet_network":{"lanelet":{"show_label":True}}})
    # ln.draw(rnd)
    # rnd.render()
    # plt.show(block=True)
    cc = pycrcc.CollisionChecker()
    for l_id, l in lanelets_union.items():
        if l.lanelet_id not in l2co:
            # l_eroded = _erode_lanelets([lanelet], radius=0.2).lanelets[0]
            l2co[l.lanelet_id] = create_collision_object(l.convert_to_polygon())
            co2l[l2co[l.lanelet_id]] = l.lanelet_id
        if l_id not in lanelets:
            cc.add_collision_object(l2co[l.lanelet_id])

    for l_id, l_i in lanelets_eroded.items():
        # if self_intersects(l_i.center_vertices):
        #     delete_ids.add(i)
        #     break
        # for j, l_j in lanelets_union.items():
        # if j == i and self_intersects(l_i.center_vertices):
        #     delete_ids.add(i)
        #     break
        # if poly_intersect(l_i.center_vertices, l_j.center_vertices):
        if lanelet_intersects(l_i, cc) and not is_adjacent(l_i, list(other_lanelets.keys())):
            delete_ids.add(l_id)

    for l_id in delete_ids:
        del lanelets[l_id]
    return lanelets


def get_all_adjacent(lanelet: int, lanelet_network) -> Set[int]:
    new_lanelets = set()
    l_left = lanelet_network.find_lanelet_by_id(lanelet)
    while l_left.adj_left is not None and l_left.adj_left_same_direction:
        new_lanelets.add(l_left.adj_left)
        l_left = lanelet_network._lanelets[l_left.adj_left]

    l_right = lanelet_network.find_lanelet_by_id(lanelet)
    while l_right.adj_right is not None and l_right.adj_right_same_direction:
        new_lanelets.add(l_right.adj_right)
        l_right = lanelet_network._lanelets[l_right.adj_right]

    return new_lanelets


def join_all_pred_succ(
    lanelet: Lanelet, lanelet_network: LaneletNetwork, extracted_lanelets: Dict[int, Lanelet], min_length: float
):
    def add_until_length(attr: str, min_length: float):
        lanelet_tmp = lanelet
        length = 0
        while length < min_length:
            latest_addition = set()
            neighbours = getattr(lanelet_tmp, attr)
            if neighbours:
                latest_addition |= set(neighbours)
            else:
                break
            latest_addition -= extracted_lanelets.keys()
            # latest_lanelets: Dict[int, Lanelet] = {lanelet: lanelet_network._lanelets[lanelet] for lanelet in
            # latest_addition}
            # latest_addition = set()
            for l_id in latest_addition.copy():
                latest_addition |= get_all_adjacent(l_id, lanelet_network)

            latest_addition -= extracted_lanelets.keys()
            latest_lanelets = {lanelet: lanelet_network._lanelets[lanelet] for lanelet in latest_addition}
            latest_lanelets = remove_intersecting_lanelets(latest_lanelets, extracted_lanelets, erosion_radius)
            extracted_lanelets.update(latest_lanelets)
            if not latest_lanelets:
                break
            lanelet_tmp = max(list(latest_lanelets.values()), key=lambda x: x.distance[-1])
            length += lanelet_tmp.distance[-1]

    add_until_length(attr="predecessor", min_length=min_length)
    add_until_length(attr="successor", min_length=min_length)


def complete_intersections(lanelets: Dict[int, Lanelet], sc: Scenario, erosion_radius=0.4):
    """
    Add all lanelets that belong to an intersection once one of them if already in the `lanelets` dict.
    :param lanelets:
    :return:
    """
    lanelet2inter = sc.lanelet_network.map_inc_lanelets_to_intersections
    add_lanelet_ids = set()
    for l_id, l in lanelets.items():
        if l_id in lanelet2inter:
            add_lanelet_ids_tmp = set()
            for inc in lanelet2inter[l_id].incomings:
                # print("inter:",inter.intersection_id,"inc_id",inc.incoming_id, "inc.incoming_lanelets",
                # inc.incoming_lanelets)
                # print("out", "left", inc.successors_left, "right", inc.successors_right, "straight",
                # inc.successors_straight)
                # print("out", inc.successors_right | inc.successors_left | inc.successors_straight)
                add_lanelet_ids_tmp |= inc.incoming_lanelets
                add_lanelet_ids_tmp |= inc.successors_left
                add_lanelet_ids_tmp |= inc.successors_right
                add_lanelet_ids_tmp |= inc.successors_straight

            tmp = {lanelet: sc.lanelet_network.find_lanelet_by_id(lanelet) for lanelet in add_lanelet_ids_tmp}
            len0 = len(tmp)
            remove_intersecting_lanelets(tmp, other_lanelets=lanelets, erosion_radius=erosion_radius)
            if len0 == len(tmp):
                add_lanelet_ids |= add_lanelet_ids_tmp

    lanelets.update({l_id: sc.lanelet_network._lanelets[l_id] for l_id in add_lanelet_ids})


def cleanup_incomplete_intersections(intersections: Dict[int, Intersection], lanelets: Dict[int, Lanelet]):
    lanelet_ids = set(lanelets.keys())
    delete_intersections = []
    delete_lanelets = set()
    for inter_id, inter in intersections.items():
        lanelets_intersection = set(
            itertools.chain.from_iterable(
                [
                    inc.incoming_lanelets | inc.successors_straight | inc.successors_left | inc.successors_right
                    for inc in inter.incomings
                ]
            )
        )
        if len(lanelets_intersection - lanelet_ids) > 0:
            delete_intersections.append(inter_id)
            delete_lanelets |= set(
                itertools.chain.from_iterable(
                    [inc.successors_straight | inc.successors_left | inc.successors_right for inc in inter.incomings]
                )
            )

    for inter_id in delete_intersections:
        del intersections[inter_id]


def is_adjacent(lanelet: Lanelet, lanelet_list: List[int]):
    adj = lanelet.adj_left in lanelet_list or lanelet.adj_right in lanelet_list
    return adj


def extract_random_route(
    lanelet_network: LaneletNetwork,
    rp: RoutePlanner,
    allowed_lanelet_types: Set[LaneletType],
    forbidden_lanelet_types: Set[LaneletType],
    erosion_radius: float,
    seed: int,
    min_length: float,
    min_num_lanelets=5,
):
    def choose_initial_lanelet(
        lanelet_network: LaneletNetwork,
        allowed_lanelet_types: Set[LaneletType],
        forbidden_lanelet_types: Set[LaneletType],
    ):
        lanelet_candidates = [
            l_id
            for l_id, lanelet in lanelet_network._lanelets.items()
            if len(lanelet.lanelet_type & allowed_lanelet_types) > 0
            and len(lanelet.lanelet_type & forbidden_lanelet_types) == 0
        ]
        choice = np.random.choice(lanelet_candidates)
        i = 0
        while is_lanelet_valid(choice, lanelet_network) is False:
            choice = np.random.choice(lanelet_candidates)
            i += 1
            if i > 20:
                raise ValueError("No invalid lanelet found as inital lanelet!")

        return choice

    def find_route(initial_lanelet: int, lanelet_network: LaneletNetwork, rp: RoutePlanner, min_length: float):

        t = nx.bfs_tree(rp.digraph, initial_lanelet, depth_limit=20)
        nodes = list(t.nodes())
        np.random.shuffle(nodes)  # randomize order
        route_gen = (
            route
            for n in nodes
            if t.out_degree(n) == 0
            for route in nx.all_simple_paths(t, initial_lanelet, n)
            if len(route) >= min_num_lanelets
        )

        def lanelet_intersects(lanelet: int, current_path: List[int]):
            """
            :returns: True if lanelet intersects with current path
            """
            if len(current_path) == 0:
                return False

            if lanelet not in l2co:
                l2co[lanelet] = create_collision_object(
                    erode_lanelet(
                        deepcopy(lanelet_network.find_lanelet_by_id(lanelet)), radius=0.4
                    ).convert_to_polygon()
                )
                co2l[l2co[lanelet]] = lanelet
            cc = CollisionChecker()
            for l_id in current_path:
                if l_id not in l2co:
                    l2co[l_id] = create_collision_object(
                        erode_lanelet(
                            deepcopy(lanelet_network.find_lanelet_by_id(l_id)), radius=0.4
                        ).convert_to_polygon()
                    )
                    co2l[l2co[l_id]] = l_id
                cc.add_collision_object(l2co[l_id])

            colliding_objects = cc.find_all_colliding_objects(l2co[lanelet])
            if colliding_objects:
                colliding_lanelets = [co2l[o] for o in colliding_objects]
                return not is_adjacent(lanelet_network.find_lanelet_by_id(lanelet), colliding_lanelets)
            else:
                return False

        found = False
        while found is False:
            length = 0
            route = next(route_gen, None)
            if route is None:
                break
            for i, l_id in enumerate(route):
                length += lanelet_network.find_lanelet_by_id(l_id).distance[-1]
                if lanelet_intersects(l_id, route[:i]):
                    found = False
                    route = None
                    break
                if i > 1 and length >= min_length:
                    route = route[: i + 1]
                    found = True
                    break

        return route

    np.random.seed(seed)
    route = None
    while route is None:
        initial_lanelet = choose_initial_lanelet(
            lanelet_network,
            allowed_lanelet_types=allowed_lanelet_types,
            forbidden_lanelet_types=forbidden_lanelet_types,
        )
        route = find_route(initial_lanelet, lanelet_network, rp, min_length=min_length)

    return route


def extract_map(scenario: Scenario, min_length_extract: float, seed: int):
    # for inter in scenario.lanelet_network.intersections:
    #     for inc in inter.incomings:
    #         if len(inc.successors_right | inc.successors_left | inc.successors_straight) == 0:
    #             print(inter.intersection_id)

    # extract highway
    pp = PlanningProblem(
        100,
        initial_state=State(
            position=np.array([0, 0]), time_step=0, velocity=0.0, orientation=0, yaw_rate=0, slip_angle=0
        ),
        goal_region=GoalRegion([State(time_step=Interval(0, 1))], {0: [1247]}),
    )

    rp = RoutePlanner(scenario, pp, log_to_console=True)
    rp.id_lanelets_start = id_lanelets_start  # kohaf:1333#1217
    rp.ids_lanelets_goal = ids_lanelets_goal  # 413,1247
    rp._create_lanelet_network_graph()
    route = extract_random_route(
        scenario.lanelet_network,
        rp,
        allowed_lanelet_types=allowed_lanelet_types,
        forbidden_lanelet_types=forbidden_lanelet_types,
        erosion_radius=erosion_radius,
        seed=seed,
        min_length=min_length_route,
    )
    # routes = rp.plan_routes()
    #
    # sections = routes.list_route_candidates[0].retrieve_route_sections()

    lanelets_route = [scenario.lanelet_network._lanelets[lanelet] for lanelet in route]
    all_lanelets = {lanelet.lanelet_id: lanelet for lanelet in lanelets_route}
    # all_lanelets_len_orig = len(all_lanelets)
    # complete_intersections(all_lanelets, scenario)
    for lanelet in lanelets_route:
        adj_lanelets = get_all_adjacent(lanelet.lanelet_id, scenario.lanelet_network)
        for l_id in adj_lanelets:
            all_lanelets[l_id] = scenario.lanelet_network.find_lanelet_by_id(l_id)

    for lanelet in list(all_lanelets.values()):
        join_all_pred_succ(lanelet, scenario.lanelet_network, all_lanelets, min_length=min_length_extract)

    # complete_intersections(all_lanelets)
    complete_intersections(all_lanelets, scenario)

    scenario_new = Scenario(
        dt=scenario.dt,
        scenario_id=scenario.scenario_id,
        affiliation=scenario.affiliation,
        author=scenario.author,
        source=scenario.source,
        location=scenario.location,
        tags=scenario.tags,
    )

    for l_id in all_lanelets:
        if is_lanelet_valid(l_id, lanelet_network=scenario.lanelet_network) is False:
            return None

    scenario_new.lanelet_network = LaneletNetwork.create_from_lanelet_list(
        list(all_lanelets.values()), cleanup_ids=True, original_lanelet_network=deepcopy(scenario.lanelet_network)
    )
    scenario_new.lanelet_network._traffic_lights = {}
    scenario_new.lanelet_network.cleanup_traffic_light_references()
    scenario_new.lanelet_network.cleanup_traffic_signs()
    scenario_new.lanelet_network.cleanup_traffic_sign_references()
    return scenario_new


draw_params = {
    "traffic_sign": {
        "draw_traffic_signs": False,
    },
    "intersection": {"draw_intersections": True},
    "lanelet_network": {
        "lanelet": {
            "draw_border_vertices": False,
            "draw_line_markings": True,
            "draw_left_bound": False,
            "draw_center_bound": False,
            "show_label": False,
            "draw_right_bound": False,
            "left_bound_color": "r",
            "right_bound_color": "g",
        }
    },
}

# filename_cr = "/home/klischat/Downloads/xodr_out/extracted/extracted.xml"
# filename_cr = "/home/klischat/Downloads/xodr_out/extracted/DEU_KoHAFOpenDRIVE07052018Frankfurt-1_1_T-1.xml"
if extract is True:
    filename_cr = os.path.join("/home/klischat/Downloads/xodr_out/extracted/", cr_name + f"_{param_id}.xml")
else:
    filename_cr = cr_file

if extract:
    if use_full_map:
        path = path_cr_map_full
    else:
        path = cr_file

    scenario, pps = CommonRoadFileReader(path).open()
    scenario.lanelet_network.cleanup_traffic_light_references()
    scenario.lanelet_network.cleanup_traffic_sign_references()
    w = []
    for lanelet in scenario.lanelet_network.lanelets:
        w_min = np.min(np.linalg.norm(lanelet.left_vertices - lanelet.right_vertices, axis=1))
        if w_min <= 0.5:
            lns = list(
                itertools.chain.from_iterable(
                    [scenario.lanelet_network.find_lanelet_by_id(l_id).predecessor for l_id in lanelet.successor]
                )
            )
            lns.extend(
                list(
                    itertools.chain.from_iterable(
                        [scenario.lanelet_network.find_lanelet_by_id(l_id).successor for l_id in lanelet.predecessor]
                    )
                )
            )
            lns = set(lns)
            lns.discard(lanelet.lanelet_id)
            if len(lns) < 1:
                continue

            if lanelet.adj_left:
                if lanelet.adj_right:
                    if (
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_left)._adj_right_same_direction
                        and lanelet.adj_left_same_direction
                    ):
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_left)._adj_right = lanelet.adj_right
                    else:
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_left)._adj_left = lanelet.adj_right
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_right)._adj_right_same_direction = False

                    scenario.lanelet_network.find_lanelet_by_id(
                        lanelet.adj_right
                    )._adj_right_same_direction = lanelet.adj_right_same_direction
                else:
                    scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_left)._adj_right = None
                    scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_left)._adj_right_same_direction = None

            if lanelet.adj_right:
                if lanelet.adj_left:
                    if (
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_right)._adj_left_same_direction
                        and lanelet._adj_right_same_direction
                    ):
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_right)._adj_left = lanelet.adj_left
                    else:
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_right)._adj_right = lanelet.adj_left
                        scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_right)._adj_left_same_direction = False

                else:
                    scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_right)._adj_left = None
                    scenario.lanelet_network.find_lanelet_by_id(lanelet.adj_right)._adj_left_same_direction = None

            if lanelet.successor:
                for s in lanelet.successor:
                    del scenario.lanelet_network.find_lanelet_by_id(s).predecessor[
                        scenario.lanelet_network.find_lanelet_by_id(s).predecessor.index(lanelet.lanelet_id)
                    ]
            if lanelet.predecessor:
                for p in lanelet.predecessor:
                    del scenario.lanelet_network.find_lanelet_by_id(p).successor[
                        scenario.lanelet_network.find_lanelet_by_id(p).successor.index(lanelet.lanelet_id)
                    ]

            scenario.remove_lanelet(lanelet)
            # lns.add(lanelet.lanelet_id)
            # lnw = LaneletNetwork.create_from_lanelet_list(
            # [scenario.lanelet_network.find_lanelet_by_id(ll) for ll in lns], cleanup_ids=True,
            # original_lanelet_network=scenario.lanelet_network)
            # rnd=MPRenderer()
            # lnw.draw(rnd)
            # rnd.render(show=False)
            # plt.title(f"{lanelet.lanelet_id}, {lns}")
            # plt.show(block=True)
            # plt.close('all')

    scenario.lanelet_network.cleanup_traffic_light_references()
    scenario.lanelet_network.cleanup_traffic_sign_references()
    scenario.lanelet_network.cleanup_traffic_lights()
    scenario.lanelet_network.cleanup_traffic_signs()

    for i in range(1, n_maps + 1):
        try:
            with timeout(seconds=3):
                scenario_new = extract_map(scenario, min_length_extract=min_length_extract, seed=i)
        except (ValueError, TimeoutError):
            scenario_new = None

        if scenario_new is None:
            continue
        scenario_new.scenario_id.map_id = i + map_id_0
        scenario_new.scenario_id.map_name = map_name
        # plt.figure(figsize=(20,15))
        # rnd = MPRenderer(draw_params={"lanelet_network":{"lanelet":{"show_label":True}}})
        # scenario_new.draw(rnd)

        # if plot is True:
        #     if i == n_maps - 1:
        #         rnd.render(show=False)
        #         plt.show(block=True)
        #     else:
        #         rnd.ax.set_title(f"{seed}, {i}")
        #         rnd.render(show=True)
        #     rnd.ax.set_title(f"{seed}, {i}")
        #     print("PLOTTED")

        # for inter in scenario_new.lanelet_network.intersections:
        #     for inc in inter.incomings:
        #         assert len(inc.incoming_lanelets) > 0
        filename_cr_tmp = os.path.join(map_folder_extracted, str(scenario_new.scenario_id) + ".xml")
        try:
            CommonRoadFileWriter(scenario_new, pps).write_to_file(
                filename_cr_tmp, OverwriteExistingFile.ALWAYS, check_validity=False
            )
        except Exception as e:
            warnings.warn(f"extracted file {i} is invalid XML.")
            print(e)
            continue

        try:
            CommonRoadFileReader(filename_cr_tmp).open()
        except Exception:
            warnings.warn(f"extracted file {i} cannot be read!")


print(" - - Opened successfully - -")

# draw_params["time_end"] = 50
# rnd = MPRenderer(draw_params=draw_params)
# rnd.create_video([sc_read], file_path="/home/klischat/Downloads/xodr_out/extracted/out.mp4")
# print(" - - video successfully - -")


# In[14]:
# cr_file_tmp = "/home/klischat/Downloads/xodr_out/ESP_elvendrell0206202-1_1_T-1.xml"
#
# sc_read, pp_read = CommonRoadFileReader(cr_file_tmp).open()

timestamp = time.strftime("%Y-%m-%d-%H%M%S")
sumo_folder = os.path.join("/home/klischat/Downloads/xodr_out/extracted_sumo/", timestamp, cr_name)
os.makedirs(sumo_folder, exist_ok=False)

if convert_sumo is True:
    if sumo_use_extracted:
        files = list(glob.glob(os.path.join(map_folder_extracted, "*.xml"), recursive=True))
    else:
        files = [cr_file]

    for file in files:
        # if not "110" in file:
        #     continue
        sc_read, pp_read = CommonRoadFileReader(file).open()
        conf = CONFIG.from_scenario(sc_read)
        conf.veh_distribution[ObstacleType.PEDESTRIAN] = 0.0
        # sumo_path = os.path.join(sumo_folder, str(sc_read.scenario_id))
        sumo_map_converter = CR2SumoMapConverter(sc_read, conf)
        conf.country_id = sc_read.scenario_id.country_id
        conversion_successful = sumo_map_converter.create_sumo_files(sumo_folder)
        # if conversion_successful is False:
        #     raise ValueError()

        # write adapted map to cr_maps
        if save_full_map and not extract:
            sc_read.lanelet_network = sumo_map_converter.lanelet_network
            CommonRoadFileWriter(sc_read, pp_read).write_to_file(path_cr_map_full)

        print(" - - converted to sumo successfull \n{file} - - ")

# In[15]:


if sumo_simulate:
    scenario_wrapper = ScenarioWrapper.init_from_scenario(conf, sumo_folder, cr_map_file=filename_cr)
    conf.presimulation_steps = 50
    sumo_sim = SumoSimulation()
    sumo_sim.planning_problem_set = None
    sumo_sim.initialize(conf, scenario_wrapper)
    t0 = time.time()
    n = 200
    for tt in range(n):
        print(f"Time step simulation: {tt} of {n}", end="\r")
        ego_vehicles = sumo_sim.ego_vehicles
        commonroad_scenario = sumo_sim.commonroad_scenario_at_time_step(sumo_sim.current_time_step)

        # assert len(commonroad_scenario.obstacles) > 0
        # plan trajectories for all ego vehicles
        # for id, ego_vehicle in ego_vehicles.items():
        #     current_state = ego_vehicle.current_state
        #
        #     # own implementation for testing - ego vehicle just stays in the initial position
        #     next_state = deepcopy(current_state)
        #     next_state.time_step = 1
        #     next_state.position = current_state.position + np.array([np.cos(current_state.orientation) *
        #                                                              current_state.velocity * config.dt,
        #                                                              np.sin(current_state.orientation) *
        #                                                              current_state.velocity * config.dt])
        #
        #     ego_vehicle.set_planned_trajectory([next_state])

        sumo_sim.simulate_step()

    sumo_sim.stop()
    print(time.time() - t0)

    # Generated scenario
    sumo_path = "TODO_use_correct_value"
    out_scenario = sumo_sim.commonroad_scenarios_all_time_steps()
    plt.close("all")
    CommonRoadFileWriter(
        out_scenario,
        pp_read,
        author="",
        affiliation="",
        source="OpenDRIVE 2 Lanelet Converter",
        tags={Tag.URBAN, Tag.HIGHWAY},
    ).write_scenario_to_file(os.path.join(sumo_path, "cr_simulated.xml"), OverwriteExistingFile.ALWAYS)
    print("wrote xml sumo")
    rnd = MPRenderer(draw_params=draw_params)
    rnd.create_video(
        [out_scenario], file_path=os.path.join(sumo_path, "sumo.mp4"), delta_time_steps=10, fig_size=[25, 18]
    )
    print("created video sumo")
    plt.pause(100)
