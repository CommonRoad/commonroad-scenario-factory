import itertools
from functools import lru_cache
from typing import Dict, List, Set

import networkx as nx
import numpy as np
from commonroad.common.util import Interval
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from commonroad.visualization.mp_renderer import MPRenderer
from commonroad_dc.pycrccosy import CurvilinearCoordinateSystem
from matplotlib import pyplot as plt

from scenario_factory.scenario_features.models.util import smoothen_polyline


class SectionID:
    def __init__(self, id: int):
        self.id = id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SectionID):
            return False
        return True if self.id == other.id else False

    def __ne__(self, other: object):
        return not self.__eq__(other)

    def __str__(self):
        return str(self.id)

    def __hash__(self):
        return hash((self.id))


class LaneletSection:
    """
    A lane section consists of laterally adjacent lanelets.
    """

    def __init__(
        self,
        lanelet_list: List[Lanelet],
        section_id: SectionID,
        succ_section: Set[int] = set(),
        pred_section: Set[int] = set(),
    ):
        # stores lanelets starting with the rightmost one
        self.lanelet_list: List[Lanelet] = lanelet_list
        self.section_id = section_id
        self.lanelet_lengths = [lanelet.distance[-1] for lanelet in lanelet_list]
        self.succ_sections: Set[int] = succ_section
        self.pred_sections = pred_section

    @lru_cache(1)
    def min_length(self):
        return min(self.lanelet_lengths)

    @lru_cache(1)
    def max_length(self):
        return max(self.lanelet_lengths)

    @lru_cache(1)
    def reference_lanelet(self):
        return self.lanelet_list[self.lanelet_lengths.index(self.max_length())]


class ProjectionError(ValueError):
    pass


class LaneletSectionNetwork:
    """
    Class for creating lane sections and managing the corresponding lane-based coordinate systems.
    """

    def __init__(self, lanelet_sections: List[LaneletSection], debug_plots=False):
        self.debug_plots = debug_plots
        lanelet_list = itertools.chain.from_iterable(
            [lanelet_section.lanelet_list for lanelet_section in lanelet_sections]
        )
        self.lanelets: Dict[int, Lanelet] = {lanelet.lanelet_id: lanelet for lanelet in lanelet_list}
        self._lanelet_sections = lanelet_sections
        self._lanelet_sections_dict: Dict[SectionID, LaneletSection] = {ls.section_id: ls for ls in lanelet_sections}
        self._section_ids: Set[SectionID] = {ls.section_id for ls in lanelet_sections}
        self._lanelet2section_id = self.create_lanelet2section_id(lanelet_sections)
        self._graph = nx.DiGraph()
        self._coord_systems: Dict[SectionID, CurvilinearCoordinateSystem] = {}
        # coordinates of initial and last vertice of lanelet in its local coordinate system
        self._s_interval: Dict[int, Interval] = {}

    @lru_cache(maxsize=256)
    def get_coordinate_system_lanelet(self, lanelet_id: int):
        lanelet = self.lanelets[lanelet_id]
        csys = CurvilinearCoordinateSystem(smoothen_polyline(lanelet.center_vertices, resampling_distance=0.5))
        # point = csys.projection_domain()[0] * 0.5 + csys.projection_domain()[10] * 0.5
        try:
            self._s_interval[lanelet_id] = Interval(
                csys.convert_to_curvilinear_coords(lanelet.center_vertices[0][0], lanelet.center_vertices[0][1])[0],
                csys.convert_to_curvilinear_coords(lanelet.center_vertices[-1][0], lanelet.center_vertices[-1][1])[0],
            )
        except ValueError:
            print(lanelet.center_vertices)
            # print(csys.projection_domain())
            print(smoothen_polyline(lanelet.center_vertices, resampling_distance=0.5))
            self.debug_plot_curv_projection(
                lanelet.center_vertices[0], csys, smoothen_polyline(lanelet.center_vertices, resampling_distance=0.5)
            )
        # #TODO delete
        # if not hasattr(self, 'DBG'):
        #     self.DBG ={}
        # self.DBG[lanelet_id] = csys
        return csys

    def get_coordinate_system_section(self, section_id: SectionID):
        l_ref = self._lanelet_sections_dict[section_id].reference_lanelet()
        return self.get_coordinate_system_lanelet(l_ref.lanelet_id)

    def get_curv_position_lanelet(self, position: np.ndarray, lanelet_id: int):
        """:returns curvilinear local coordinates of position for lanelet_id."""
        pos_c = self.get_coordinate_system_lanelet(lanelet_id).convert_to_curvilinear_coords(position[0], position[1])
        pos_c[0] -= self._s_interval[lanelet_id].start
        return pos_c

    def get_curv_position_section(self, position: np.ndarray, section_id: SectionID) -> np.ndarray:
        """:returns curvilinear local coordinates of position for section_id."""
        try:
            pos_c = self.get_coordinate_system_section(section_id).convert_to_curvilinear_coords(
                position[0], position[1]
            )
        except ValueError:
            print("section", section_id)
            print("ref_lanelet", self._lanelet_sections_dict[section_id].reference_lanelet().lanelet_id)
            self.debug_plot_curv_projection(position, self.get_coordinate_system_section(section_id))
            raise ProjectionError
        l_ref = self.get_ref_lanelet_by_section_id(section_id).lanelet_id
        pos_c[0] -= self._s_interval[l_ref].start
        return pos_c

    def get_ref_lanelet_by_section_id(self, section_id: SectionID) -> Lanelet:
        """:returns reference lanelet for the given section"""
        return self._lanelet_sections_dict[section_id].reference_lanelet()

    def compute_shortest_longitudnal_distance(self, position_0: np.ndarray, position_1: np.ndarray):
        """
        Compute shortest longitudinal distance between two positions.
        :param position_0:
        :param position_1:
        :return:
        """
        raise NotImplementedError()

    def compute_longitudinal_distance(
        self, long_0: float, long_1: float, section_0: SectionID, section_1: SectionID, distance_type: str = "min"
    ):
        """
        Computes longitudinal distance from long_0,section_0 to long_1,section_1.
        :param long_0: longitudinal position in local coordinates
        :param long_1: longitudinal position in local coordinates
        :param section_0: section of long_0
        :param section_1: section of long_1
        :param distance_type: compute distance using 'min' or 'max' length of sections.
        :return: longitudinal distance
        """
        if distance_type == "min":
            section_route = nx.shortest_path(self.graph, source=section_0, target=section_1, weight="min_length")
        elif distance_type == "max":
            section_route = nx.shortest_path(self.graph, source=section_0, target=section_1, weight="max_length")
        else:
            raise ValueError()

        return self.get_distance_on_route(long_0, long_1, section_route, distance_type), section_route

    def get_distance_on_route(
        self, long_0: float, long_1: float, section_route: List[SectionID], distance_type: str = "min"
    ):
        """
        Computes longitudinal distance from long_0,section_0 to long_1,section_1.route
        :param long_0: longitudinal position in local coordinates
        :param long_1: longitudinal position in local coordinates
        :param section_route: route given by section IDs
        :param distance_type: compute distance using 'min' or 'max' length of sections.
        :return: longitudinal distance
        """
        if distance_type == "min":
            dist_fun = "min_length"
        elif distance_type == "max":
            dist_fun = "max_length"
        else:
            raise ValueError()

        # remaining distance of first lanelet + distance of second lanelet
        distance = getattr(self._lanelet_sections_dict[section_route[0]], dist_fun)() - long_0 + long_1
        if len(section_route) > 2:
            for s_id in section_route[1:-1]:
                distance += getattr(self._lanelet_sections_dict[s_id], dist_fun)()
        return distance

    def get_shortest_distance_lanelets(self, lanelet_id_start: int, lanelet_id_end: int):
        """
        Get shortest distance between two lanelets from beginning of start until beginning of goal.
        :return:
        """
        sid_start = self._lanelet2section_id[lanelet_id_start]
        sid_end = self._lanelet2section_id[lanelet_id_end]
        try:
            return nx.shortest_path_length(self.graph, source=sid_start, target=sid_end, weight="min_length")
        except nx.NetworkXNoPath:
            return np.inf

    def has_path(self, lanelet_id_start: int, lanelet_id_end: int):
        """
        Checks if a path exists from start to goal lanelet.
        :param lanelet_id_start:
        :param lanelet_id_end:
        :return:
        """
        sid_start = self._lanelet2section_id[lanelet_id_start]
        sid_end = self._lanelet2section_id[lanelet_id_end]

        return nx.has_path(self.graph, sid_start, sid_end)

    @property
    def graph(self) -> nx.DiGraph:
        """:returns graph with lanelets as nodes and successor/predecessor relations represented by edges.
        The min/max_length of an edge from lanelet1 to lanelet2 is given by the lengths of lanelet 1."""
        return self._graph

    @graph.setter
    def graph(self, _):
        raise ValueError("attribute cannot be set externally")

    @property
    def section_ids(self):
        return self._section_ids

    @property
    def lanelet_sections(self) -> List[LaneletSection]:
        return list(self._lanelet_sections_dict.values())

    @lanelet_sections.setter
    def lanelet_sections(self, _):
        raise ValueError("attribute cannot be set externally")

    @property
    def lanelet2section_id(self):
        return self._lanelet2section_id

    @lanelet2section_id.setter
    def lanelet2section_id(self, _):
        raise ValueError("attribute cannot be set externally")

    def generate_lane_section_id(self) -> SectionID:
        """Generates a unique ID which is not assigned to any lanelet_sections."""
        if len(self.lanelet_sections) > 0:
            return SectionID(max([id.id for id in self._section_ids]) + 1)
        else:
            return SectionID(0)

    @staticmethod
    def create_lanelet2section_id(lanelet_sections: List[LaneletSection]) -> Dict[int, SectionID]:
        lanelet2section_id = dict()
        for ls in lanelet_sections:
            for lanelet in ls.lanelet_list:
                lanelet2section_id[lanelet.lanelet_id] = ls.section_id
        return lanelet2section_id

    def add_section(self, lanelet_section: LaneletSection):
        assert lanelet_section.section_id not in self._section_ids
        self._section_ids.add(lanelet_section.section_id)
        self._update_all_section_relations(lanelet_section)
        self.lanelet_sections.append(lanelet_section)
        self._lanelet_sections_dict[lanelet_section.section_id] = lanelet_section
        self._lanelet2section_id.update(self.create_lanelet2section_id([lanelet_section]))
        self.lanelets.update({lanelet.lanelet_id: lanelet for lanelet in lanelet_section.lanelet_list})
        self.add_to_graph(lanelet_section)

    def _update_all_section_relations(self, lanelet_section: LaneletSection):
        self._update_predecessors(lanelet_section)
        self._update_successors(lanelet_section)

    def add_to_graph(self, lanelet_section: LaneletSection):
        section_id = lanelet_section.section_id
        assert section_id not in self.graph.nodes
        for p in lanelet_section.pred_sections:
            self._graph.add_edge(
                p,
                section_id,
                min_length=self._lanelet_sections_dict[p].min_length(),
                max_length=self._lanelet_sections_dict[p].max_length(),
            )

        for s in lanelet_section.succ_sections:
            self._graph.add_edge(
                section_id, s, min_length=lanelet_section.min_length(), max_length=lanelet_section.max_length()
            )

    @classmethod
    def from_lanelet_network(cls, lanelet_network: LaneletNetwork) -> "LaneletSectionNetwork":
        """
        Create LaneModel from a lanelet_network
        :param lanelet_network
        :return:
        """
        lane_model = cls(lanelet_sections=[])

        # starting from right to left lanelet
        for lanelet_id, lanelet in lanelet_network._lanelets.items():
            if lanelet_id in lane_model._lanelet2section_id or lanelet.adj_right is not None:
                # ensures starting at right-most lanelet
                continue

            # create new section
            sec_id = lane_model.generate_lane_section_id()
            lanelets_tmp = [lanelet]
            next_lanelet: Lanelet = lanelet

            while next_lanelet.adj_left is not None and next_lanelet.adj_left_same_direction:
                next_lanelet = lanelet_network.find_lanelet_by_id(next_lanelet.adj_left)
                lanelets_tmp.append(next_lanelet)

            new_section = LaneletSection(lanelets_tmp, sec_id)
            lane_model.add_section(new_section)

        return lane_model

    def _update_successors(self, lanelet_section: LaneletSection):
        """
        Collects existing succeeding section of all lanelets in this lanelet_section and updates all relations.
        :param lanelet_section
        :return:
        """
        successor_lanelets = set()
        for lanelet in lanelet_section.lanelet_list:
            if lanelet.successor is not None:
                successor_lanelets = successor_lanelets.union(list(lanelet.successor))

        succ_sections = set()
        for s in successor_lanelets:
            if s in self._lanelet2section_id:
                s_section = self._lanelet2section_id[s]
                succ_sections.add(s_section)
                self._lanelet_sections_dict[s_section].pred_sections.add(lanelet_section.section_id)

        lanelet_section.succ_sections = succ_sections

    def _update_predecessors(self, lanelet_section: LaneletSection):
        """
        Collects existing preceding section of all lanelets in this lanelet_section and updates all relations.
        :param lanelet_section
        :return:
        """
        predecessor_lanelets = set()
        for lanelet in lanelet_section.lanelet_list:
            if lanelet.predecessor is not None:
                predecessor_lanelets = predecessor_lanelets.union(list(lanelet.predecessor))

        pred_sections = set()
        for p in predecessor_lanelets:
            if p in self._lanelet2section_id:
                p_section = self._lanelet2section_id[p]
                pred_sections.add(p_section)
                self._lanelet_sections_dict[p_section].succ_sections.add(lanelet_section.section_id)

        lanelet_section.pred_sections = pred_sections

    def debug_plot_curv_projection(self, position, cosy: CurvilinearCoordinateSystem, reference_path=None):
        if self.debug_plots is False:
            return
        if reference_path is None:
            reference_path = np.array(cosy.reference_path())
        projection_domain = np.array(cosy.projection_domain())
        rnd = MPRenderer()
        # plt.plot(reference_path[:, 0], reference_path[:, 1])
        LaneletNetwork.create_from_lanelet_list(list(self.lanelets.values())).draw(
            rnd, draw_params={"lanelet": {"show_label": True}}
        )
        rnd.render(show=False)
        plt.plot(projection_domain[:, 0], projection_domain[:, 1], "-b", zorder=1000)
        plt.plot(position[0], position[1], "*k", linewidth=5, zorder=1000)
        plt.axis("equal")
        plt.autoscale()
        plt.show()
        plt.pause(1)
        print("failed")


class SectionRoute:
    """
    Represents route by list of connected sections
    """

    def __init__(self, lanelet_sections: List[LaneletSection]):
        assert all([LaneletSection == type(ls) for ls in lanelet_sections])
        # lateral and longitudinal index of each lanelet_id
        self.lateral_indices: Dict[int, int] = {}
        self.long_indices: Dict[int, int] = {}
        self.lanelet_sections = []
        for ls in lanelet_sections:
            self.append(ls)

    def append(self, new_section: LaneletSection) -> None:
        if len(self.lanelet_sections) > 0:
            # find connection to predecessor
            connecting_index = 0
            connecting_lanelet = self.lanelet_sections[-1].lanelet_list[0]
            new_lanelets = [lanelet.lanelet_id for lanelet in new_section.lanelet_list]
            for lanelet in self.lanelet_sections[-1].lanelet_list:
                if lanelet.successor is not None and len(set(lanelet.successor).intersection(new_lanelets)) > 0:
                    connected_lanelets = set(lanelet.successor).intersection(new_lanelets)
                    for connecting_index, connecting_lanelet in enumerate(new_section.lanelet_list):
                        if connecting_lanelet.lanelet_id in connected_lanelets:
                            connecting_index -= self.lateral_indices[lanelet.lanelet_id]
                            break

                    self.lateral_indices[connecting_lanelet.lanelet_id] = connecting_index
                    break
        else:
            connecting_index = 0

        for l_index, lanelet in enumerate(new_section.lanelet_list):
            self.lateral_indices[lanelet.lanelet_id] = l_index - connecting_index
            self.long_indices[lanelet.lanelet_id] = len(self.lanelet_sections)

        self.lanelet_sections.append(new_section)

    def __delitem__(self, key):
        self.__delattr__(key)

    def __getitem__(self, key):
        return self.lanelet_sections[key]

    def __setitem__(self, key, value):
        raise NotImplementedError("Use append(lanelet_section) to add section.")
