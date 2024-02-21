"""
Quick fixes for some bugs in CommonRoad maps.
"""
import itertools
import warnings
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import shapely
from commonroad.scenario.intersection import Intersection, IntersectionIncomingElement
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from commonroad.scenario.scenario import Scenario
from commonroad.visualization.mp_renderer import MPRenderer
from crdesigner.map_conversion.sumo_map.util import _erode_lanelets
from shapely.geometry import LineString, MultiPoint, Point
from shapely.validation import explain_validity

matplotlib.use("TkAgg")


class ScenarioFixer:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario

    @property
    def lanelet_network(self) -> LaneletNetwork:
        return self.scenario.lanelet_network

    def _find_intersecting_lanelets(
        self,
        lanelet_network: LaneletNetwork,
        in_lanelets: Dict[tuple, List[int]],
        out_lanelets: Dict[tuple, List[int]],
        visualize=False,
    ) -> Dict[Tuple[int, int], Set[Tuple[int, int]]]:
        """

        :param lanelet_network:
        :return:
        """
        eroded_lanelet_network = _erode_lanelets(lanelet_network, radius=0.3)
        """
        incoming_dict = {
            (inter.intersection_id, inc.incoming_id): inc.incoming_lanelets
            for inter in lanelet_network.intersections
            for inc in inter.incomings
        }
        """
        # visualize eroded lanelets
        if visualize:
            plt.figure(figsize=(25, 25))
            rnd = MPRenderer()
            rnd.draw_list([eroded_lanelet_network])
            rnd.render()
            plt.axis("equal")
            plt.autoscale()
            plt.show()

        polygons_dict = {}
        # incoming_shapes_dict = {}
        all_lanelets = set(itertools.chain.from_iterable(list(in_lanelets.values()) + list(out_lanelets.values())))
        for lanelet_id in all_lanelets:
            polygon = eroded_lanelet_network.find_lanelet_by_id(lanelet_id).convert_to_polygon()

            polygons_dict[lanelet_id] = polygon.shapely_object

            if polygons_dict[lanelet_id].is_valid is False:
                polygons_dict[lanelet_id] = polygons_dict[lanelet_id].buffer(0)
                warnings.warn(
                    f"Invalid lanelet shape! Please check the scenario, "
                    f"because invalid lanelet has been found: "
                    f"{lanelet_id}: {explain_validity(polygons_dict[lanelet_id])}"
                )

        # collect all outgoing lanelets which intersect with an incoming element
        intersecting_incomings: Dict[Tuple[int, int], Set[Tuple[int, int]]] = defaultdict(set)
        for incoming_id, lanelets_in in in_lanelets.items():
            for out_id, lanelets_out in out_lanelets.items():
                if incoming_id[0] != out_id[0]:
                    continue  # check only inc/out of same intersection
                for l_in in lanelets_in:
                    for l_out in lanelets_out:
                        if l_out == l_in:
                            continue
                        # shapely
                        if polygons_dict[l_in].intersection(polygons_dict[l_out]).area > 0.0:
                            intersecting_incomings[incoming_id].add((l_in, l_out))

        # merge lists of adjacent incomings
        delete_ids = set()
        adj_incomings = self._get_adj_incomings()
        for i, (inc_id, lanelet_set) in enumerate(intersecting_incomings.items()):
            if inc_id not in adj_incomings:
                continue
            new_lanelet_list = lanelet_set.copy()
            last_adj = None
            for j, (inc_id_other, lanelet_set_other) in enumerate(intersecting_incomings.items()):
                if i <= j:
                    continue
                if inc_id_other in adj_incomings[inc_id]:
                    new_lanelet_list &= lanelet_set_other
                    last_adj = inc_id_other

            if last_adj is not None:
                intersecting_incomings[last_adj] = new_lanelet_list
                delete_ids.add(inc_id)

        for inc_id in delete_ids:
            del intersecting_incomings[inc_id]

        return intersecting_incomings

    def _get_adj_incomings(self) -> Dict[Tuple[int, int], Set[Tuple[int, int]]]:
        """
        Collects ids of incoming lanelets
        :return:
        """
        adj_incomings = defaultdict(set)
        for int_id, inter in self.lanelet_network._intersections.items():
            for i, inc in enumerate(inter.incomings[:-1]):
                for inc2 in inter.incomings[i + 1 :]:
                    for l1 in inc.incoming_lanelets:
                        if (
                            l1 in inc2.incoming_lanelets
                            or (
                                self.lanelet_network.find_lanelet_by_id(l1).adj_left is not None
                                and self.lanelet_network.find_lanelet_by_id(l1).adj_left in inc2.incoming_lanelets
                            )
                            or (
                                self.lanelet_network.find_lanelet_by_id(l1).adj_right is not None
                                and self.lanelet_network.find_lanelet_by_id(l1).adj_right in inc2.incoming_lanelets
                            )
                        ):
                            adj_incomings[(int_id, inc.incoming_id)].add((int_id, inc2.incoming_id))
                            adj_incomings[(int_id, inc2.incoming_id)].add((int_id, inc.incoming_id))

        return dict(adj_incomings)

    def _find_intersection_points(
        self, lanelet_network: LaneletNetwork, intersecting_incomings: Dict[Tuple[int, int], List[Tuple[int, int]]]
    ):
        lines = {}
        cutting_points_incoming: Dict[Tuple[int, int], shapely.geometry.Point] = {}
        for inc, lanelets_intersecting in intersecting_incomings.items():
            # inc: tuple(intersection_id, incoming_id, lanelet_id)
            intersection_points = []
            for l_in, l_out in lanelets_intersecting:
                if l_in not in lines:
                    lines[l_in] = [
                        LineString(lanelet_network.find_lanelet_by_id(l_in).left_vertices),
                        LineString(lanelet_network.find_lanelet_by_id(l_in).right_vertices),
                        LineString(lanelet_network.find_lanelet_by_id(l_in).center_vertices),
                    ]
                if l_out not in lines:
                    lines[l_out] = [
                        LineString(lanelet_network.find_lanelet_by_id(l_out).left_vertices),
                        LineString(lanelet_network.find_lanelet_by_id(l_out).right_vertices),
                        LineString(lanelet_network.find_lanelet_by_id(l_out).center_vertices),
                    ]

                lines_in = lines[l_in]
                lines_out = lines[l_out]

                # plt.close("all")
                # plt.figure()
                # for ll in lines_in + lines_out:
                #     x, y = ll.coords.xy
                #     plt.plot(x,y)

                def append_point_and_dist(point_tmp):
                    dist = lines_in[2].project(point_tmp)
                    intersection_points.append((point_tmp, dist))

                for line_in in lines_in[:2]:
                    for line_out in lines_out[:2]:
                        intersection_geom = line_in.intersection(line_out)
                        typ = type(intersection_geom)
                        if typ == Point:
                            append_point_and_dist(intersection_geom)
                        elif typ == MultiPoint:
                            for p in intersection_geom:
                                append_point_and_dist(p)
                        elif typ == LineString:
                            for p in intersection_geom.boundary:
                                append_point_and_dist(p)
                        else:
                            raise NotImplementedError(f"unimplemented intersection geometry type {typ}!")

            # for pp, _ in intersection_points:
            #     plt.scatter(pp.x, pp.y)
            # plt.show(block=False)
            # plt.pause(5)
            cutting_points_incoming[inc] = min(intersection_points, key=lambda x: x[1])[0]

        return cutting_points_incoming

    def _get_adjacent_lanelets(self, lanelet: Lanelet, oncomings_allowed=True) -> List[int]:
        """
        Get all adjacent lanelets orderered from right to left.
        :param lanelet:
        :return:
        """
        all_lanelest = [lanelet.lanelet_id]
        l_left = lanelet
        while l_left.adj_left and l_left.adj_left_same_direction:
            if oncomings_allowed is False and l_left.adj_left_same_direction is False:
                return []
            all_lanelest.append(l_left.adj_left)
            l_left = self.lanelet_network._lanelets[l_left.adj_left]

        l_right = lanelet
        while l_right.adj_right and l_right.adj_right_same_direction:
            if oncomings_allowed is False and l_right.adj_right_same_direction is False:
                return []
            all_lanelest.insert(0, l_right.adj_right)
            l_right = self.lanelet_network._lanelets[l_right.adj_right]

        return all_lanelest

    def _cut_lanelet(self, lanelet: Lanelet, point: Point, margin: float = 0.0, next_direction="left", use_point=True):
        """
        :param lanelet:
        :param point:
        :param margin:
        :param next_direction:
        :param use_point: make point part of vertices (point was generated when cutting adjacent lanelet)
        :return:
        """
        distance = max(0.5, LineString(lanelet.center_vertices).project(point) - margin)
        res = list(lanelet.interpolate_position(distance))
        cut_vertices = res[:3]
        cut_index = res[3] + 1
        # create additional lanelet
        # rnd = MPRenderer()
        # LaneletNetwork.create_from_lanelet_list([lanelet], original_lanelet_network=self.lanelet_network).draw(rnd)
        # rnd.render()
        # for v in cut_vertices:
        #     plt.scatter(v[0], v[1], zorder=1000)
        # plt.scatter(point.x, point.y, zorder=1001)
        # plt.show(block=True)

        if next_direction == "left":
            next_point = Point(cut_vertices[2][0], cut_vertices[2][1])
        elif next_direction == "right":
            next_point = Point(cut_vertices[1][0], cut_vertices[1][1])
        else:
            raise ValueError(f"unknown direction'{next_direction}")

        for i in range(3):
            cut_vertices[i] = cut_vertices[i].reshape([1, 2])

        if cut_index <= 2:
            vertices = [
                lanelet.center_vertices[cut_index, :],
                lanelet.right_vertices[cut_index, :],
                lanelet.left_vertices[cut_index, :],
            ]
            for i in range(3):
                cut_vertices[i] = np.append(0.5 * (vertices[i] + cut_vertices[i]), cut_vertices[i], axis=0)

        lanelet_pred = Lanelet(
            left_vertices=np.append(lanelet.left_vertices[:cut_index, :], cut_vertices[2], axis=0),
            right_vertices=np.append(lanelet.right_vertices[:cut_index, :], cut_vertices[1], axis=0),
            center_vertices=np.append(lanelet.center_vertices[:cut_index, :], cut_vertices[0], axis=0),
            lanelet_id=self.scenario.generate_object_id(),
            predecessor=lanelet.predecessor,
            successor=[lanelet.lanelet_id],
            line_marking_right_vertices=lanelet.line_marking_right_vertices,
            line_marking_left_vertices=lanelet.line_marking_left_vertices,
            stop_line=lanelet.stop_line,
            lanelet_type=lanelet.lanelet_type,
            user_one_way=lanelet.user_one_way,
            user_bidirectional=lanelet.user_bidirectional,
            traffic_signs=lanelet.traffic_signs,
            traffic_lights=lanelet.traffic_lights,
        )
        if use_point:
            if next_direction == "left":
                lanelet_pred._right_vertices[cut_index, 0] = point.x
                lanelet_pred._right_vertices[cut_index, 1] = point.y
            elif next_direction == "right":
                lanelet_pred._left_vertices[cut_index, 0] = point.x
                lanelet_pred._left_vertices[cut_index, 1] = point.y
            else:
                raise ValueError

        # cut existing lanelet
        lanelet._center_vertices = np.insert(lanelet._center_vertices[cut_index:, :], 0, cut_vertices[0][-1, :], axis=0)
        lanelet._right_vertices = np.insert(lanelet._right_vertices[cut_index:, :], 0, cut_vertices[1][-1, :], axis=0)
        lanelet._left_vertices = np.insert(lanelet._left_vertices[cut_index:, :], 0, cut_vertices[2][-1, :], axis=0)

        # delete traffic light / sign references in front lanelet
        lanelet._traffic_lights = set()
        lanelet._traffic_signs = set()

        return lanelet_pred, next_point

    def _cut_lanelet_section_at_point(
        self, scenario: Scenario, lanelet_id: int, point: Point, margin: float
    ) -> Dict[int, int]:
        """
        Cuts all lanelets of an intersection at the projetion of a point.
        :param scenario:
        :param lanelet_id:
        :param point:
        :param margin: add margin in front of cutting point
        :return: mapping from existing lanelet ids to newly created predecessors
        """
        ln = scenario.lanelet_network
        lanelets = self._get_adjacent_lanelets(ln.find_lanelet_by_id(lanelet_id))
        # start cutting at innermost lanelet
        inner_lanelet = min(lanelets, key=lambda lanelet: ln.find_lanelet_by_id(lanelet).inner_distance[-1])
        adj = ["left", "right"]
        if lanelets.index(inner_lanelet) < len(lanelets) * 0.5:
            start = 0
            end = len(lanelets)
            dir = 1
        else:
            start = len(lanelets) - 1
            end = -1
            dir = -1
            adj.reverse()

        new_lanelets = []
        lanelet = ln.find_lanelet_by_id(lanelets[start])
        new_lanelet, point = self._cut_lanelet(lanelet, point, margin, next_direction=adj[0], use_point=False)
        new_lanelets.append(new_lanelet)
        for index_l in range(start + dir, end, dir):
            lanelet = ln.find_lanelet_by_id(lanelets[index_l])
            new_lanelet, point = self._cut_lanelet(lanelet, point, margin=0, next_direction=adj[0], use_point=True)
            new_lanelets.append(new_lanelet)

        # set lateral adj of new lanelets and add to lanelet network
        l_adj = new_lanelets[0]
        for lanelet, l_adj in zip(new_lanelets[:-1], new_lanelets[1:]):
            scenario.lanelet_network.add_lanelet(lanelet)
            setattr(lanelet, f"adj_{adj[0]}", l_adj.lanelet_id)
            setattr(l_adj, f"adj_{adj[1]}", lanelet.lanelet_id)
            setattr(lanelet, f"adjacent_{adj[0]}_same_direction", True)
            setattr(l_adj, f"adjacent_{adj[1]}_same_direction", True)

        scenario.lanelet_network.add_lanelet(l_adj)

        return {l_id: new_lanelets[i].lanelet_id for i, l_id in enumerate(lanelets)}

    def _replace_intersection_lanelet_references(
        self, replace_dict: Dict[int, int], replace_incomings: bool = True, replace_successors: bool = True
    ):
        """
        Replace lanelet_id references in incoming elements to this
        :param replace_dict: maps existing ids to new ids
        :param new_lanelets:
        :return:
        """

        def replace_ids_in_set(replace_dict, id_set: Set[int]):
            for old_id in replace_dict.keys() & id_set:
                id_set.remove(old_id)
                id_set.add(replace_dict[old_id])

        for inter in self.lanelet_network.intersections:
            for inc in inter.incomings:
                # if first part of cut lanelet was successor of other intersection, replace
                if replace_successors is True:
                    for id_set in [inc._successors_left, inc._successors_straight, inc._successors_right]:
                        replace_ids_in_set(replace_dict, id_set)

                # replace successors in inc with the second part of the cut lanelet (i.e. old_id)
                if replace_incomings is True:
                    for old_id in replace_dict.keys() & inc.incoming_lanelets:
                        replace_tmp = {
                            succ: old_id for succ in self.lanelet_network.find_lanelet_by_id(old_id).successor
                        }
                        for id_set in [inc._successors_left, inc._successors_straight, inc._successors_right]:
                            replace_ids_in_set(replace_tmp, id_set)

                # replace incoming of with first part of cut lanelet (needs to be replaced last!)
                if replace_successors is True:
                    for id_set in [inc.incoming_lanelets]:
                        replace_ids_in_set(replace_dict, id_set)

    def _cut_incoming(
        self,
        point: Point,
        intersection: Intersection,
        incoming_element: IntersectionIncomingElement,
        scenario: Scenario,
        margin: float,
    ):
        replacement_mapping = self._cut_lanelet_section_at_point(
            scenario, list(incoming_element.incoming_lanelets)[0], point, margin
        )
        self._replace_intersection_lanelet_references(replacement_mapping)

    def autofit_long_incomings(self, margin=2.0):
        lanelet_network = self.lanelet_network
        incoming_lanelets = defaultdict(list)
        for inter in lanelet_network.intersections:
            for inc in inter.incomings:
                for l_id in inc.incoming_lanelets:
                    incoming_lanelets[(inter.intersection_id, inc.incoming_id)].append(l_id)

        out_lanelets = defaultdict(list)
        for inter in lanelet_network.intersections:
            for inc in inter.incomings:
                for l_id in inc.successors_left | inc.successors_straight | inc.successors_left:
                    out_lanelets[(inter.intersection_id, inc.incoming_id)].append(l_id)
        # all_lanelets = list(set(incoming_lanelets.keys()) | set(out_lanelets.keys()))
        # lanelet_dict = dict(zip(all_lanelets, [[lanelet] for lanelet in all_lanelets]))
        intersecting_incomings = self._find_intersecting_lanelets(lanelet_network, incoming_lanelets, out_lanelets)
        cutting_points_incoming = self._find_intersection_points(lanelet_network, intersecting_incomings)
        for inc_id, point in cutting_points_incoming.items():
            intersection = lanelet_network.find_intersection_by_id(inc_id[0])
            for inc in intersection.incomings:
                if inc.incoming_id != inc_id[1]:
                    continue
                incoming_element = inc
                break
            self._cut_incoming(point, intersection, incoming_element, self.scenario, margin=margin)

    def _merge_lanelet_section(self, lanelet):
        all_lanelets = set(self._get_adjacent_lanelets(lanelet, oncomings_allowed=False))
        # replacement_dict = {}
        unique_pred = True
        unique_succ = True
        for l_id in all_lanelets:
            if len(self.lanelet_network.find_lanelet_by_id(l_id).predecessor) > 1:
                unique_pred = False
            if len(self.lanelet_network.find_lanelet_by_id(l_id).successor) > 1:
                unique_succ = False

        if unique_pred is True:
            merge_dir = "predecessor"
        elif unique_succ is True:
            merge_dir = "successor"
        else:
            merge_dir = "predecessor"

        for l_id in all_lanelets:
            lanelet_tmp = self.scenario._lanelet_network._lanelets[l_id]
            for l_id_other in getattr(lanelet_tmp, dir):
                merge_list = [lanelet_tmp, self.scenario._lanelet_network._lanelets[l_id_other]]
                if merge_dir == "predecessor":
                    merge_list.reverse()
                self.scenario._lanelet_network._lanelets[l_id] = Lanelet.merge_lanelets(merge_list[0], merge_list[1])

    def merge_short_lanelets(self, max_dist: float = 4.0):
        """
        Merge short lanelets with their predecessor
        :param max_dist:
        :return:
        """
        short_lanelets = {l_id for l_id, l in self.lanelet_network._lanelets.items() if l.inner_distance[-1] < max_dist}
        while short_lanelets:
            l_id_tmp = short_lanelets.pop()
            lanelet_tmp = self.lanelet_network.find_lanelet_by_id(l_id_tmp)
            all_lanelets = self._merge_lanelet_section(lanelet_tmp)
            short_lanelets -= all_lanelets

    def delete_traffic_light_if_no_intersection(self):
        """
        Delete traffic lights, if lanelet is not an incoming of an intersection.
        :return:
        """
        incoming_mapping = self.lanelet_network.map_inc_lanelets_to_intersections
        for l_id, lanelet in self.lanelet_network._lanelets.items():
            if len(lanelet.traffic_lights) > 0 and len(lanelet.successor) > 1 and lanelet not in incoming_mapping:
                lanelet._traffic_lights = set()

        self.lanelet_network.cleanup_traffic_lights()

    def delete_redundant_incomings(self):
        for inter in self.lanelet_network.intersections:
            delete_incomings = {}
            for i, inc in enumerate(inter.incomings):
                inc_set = set(inc.incoming_lanelets)
                for j, inc2 in enumerate(inter.incomings):
                    if j == i or inc2 in delete_incomings:
                        continue
                    if (
                        inc_set <= inc2.incoming_lanelets
                        and inc.successors_left <= inc2.successors_left
                        and inc.successors_straight <= inc2.successors_straight
                        and inc.successors_right <= inc2.successors_right
                    ):
                        delete_incomings[inc] = inc2
                        break

            for inc, inc_new in delete_incomings.items():
                for inc2 in inter.incomings:
                    if inc2.left_of == inc.incoming_id:
                        inc2.left_of = inc_new.incoming_id

                del inter._incomings[inter.incomings.index(inc)]
                # if __name__ == "__main__":


#     cr_file = "/home/klischat/Downloads/xodr_out/elvendrell020620.xml"
#
#     scenario, pp = CommonRoadFileReader(cr_file).open()
#     plt.figure()
#     ax = plt.subplot(1, 2, 1)
#     rnd = MPRenderer(ax=ax)
#     scenario.draw(rnd)
#     rnd.render()
#     ScenarioFixer(scenario).autofit_long_incomings(scenario.lanelet_network)
#     ax = plt.subplot(1, 2, 2)
#     rnd = MPRenderer(ax=ax)
#     scenario.draw(rnd)
#     rnd.render()
#     plt.show()
#     plt.pause(100)
