import itertools
from functools import lru_cache
from typing import Dict, List, Optional, Set, Union

import networkx as nx
import numpy as np
from commonroad.common.util import Interval
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork
from commonroad.visualization.mp_renderer import MPRenderer
from commonroad_clcs.clcs import CLCSParams, CurvilinearCoordinateSystem
from matplotlib import pyplot as plt

from .util import smoothen_polyline


class SectionID:
    """
    Represents a unique identifier for a LaneletSection.
    """

    def __init__(self, id_val: int):
        """
        :param id_val: A unique integer ID.
        """
        self.id = id_val

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SectionID):
            return False
        return self.id == other.id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self.id)

    def __str__(self) -> str:
        return str(self.id)


class LaneletSection:
    """
    A lane section consists of laterally adjacent lanelets, stored right-to-left.
    """

    def __init__(
        self,
        lanelet_list: List[Lanelet],
        section_id: SectionID,
        succ_section: Optional[Set[SectionID]] = None,
        pred_section: Optional[Set[SectionID]] = None,
    ):
        """
        Initializes a LaneletSection with a collection of lanelets.

        :param lanelet_list: The lanelets belonging to this section, rightmost first.
        :param section_id: A SectionID object.
        :param succ_section: Set of successor section IDs (if any).
        :param pred_section: Set of predecessor section IDs (if any).
        """
        self.lanelet_list: List[Lanelet] = lanelet_list
        self.section_id = section_id

        if succ_section is None:
            succ_section = set()
        if pred_section is None:
            pred_section = set()
        self.succ_sections: Set[SectionID] = succ_section
        self.pred_sections: Set[SectionID] = pred_section

        # Precompute length of each lanelet
        self.lanelet_lengths = [lanelet.distance[-1] for lanelet in lanelet_list]

    @lru_cache(maxsize=1)
    def min_length(self) -> float:
        """
        :return: The minimal length among all lanelets in this section.
        """
        return min(self.lanelet_lengths) if self.lanelet_lengths else 0.0

    @lru_cache(maxsize=1)
    def max_length(self) -> float:
        """
        :return: The maximal length among all lanelets in this section.
        """
        return max(self.lanelet_lengths) if self.lanelet_lengths else 0.0

    @lru_cache(maxsize=1)
    def reference_lanelet(self) -> Lanelet:
        """
        :return: The lanelet with the maximum length in this section (reference).
        :raises IndexError: If lanelet_list is empty.
        """
        if not self.lanelet_list:
            raise IndexError("LaneletSection is empty.")
        return self.lanelet_list[self.lanelet_lengths.index(self.max_length())]

    def __iter__(self):
        return iter(self.lanelet_list)


class ProjectionError(ValueError):
    """
    Indicates an error during coordinate projection (e.g., out of domain).
    """

    pass


class LaneletSectionNetwork:
    """
    Manages a collection of LaneletSection objects and handles lane-based coordinate systems.
    """

    def __init__(self, lanelet_sections: List[LaneletSection], debug_plots: bool = False):
        """
        :param lanelet_sections: The list of lanelet sections forming this network.
        :param debug_plots: If True, shows debug plots when projection errors occur.
        """
        self.debug_plots = debug_plots

        # Gather all lanelets into a dict by ID
        lanelets_iter = itertools.chain.from_iterable(
            [lanelet_section.lanelet_list for lanelet_section in lanelet_sections]
        )
        self.lanelets: Dict[int, Lanelet] = {
            lanelet.lanelet_id: lanelet for lanelet in lanelets_iter
        }

        # Store internal section structures
        self._lanelet_sections = lanelet_sections
        self._lanelet_sections_dict: Dict[SectionID, LaneletSection] = {
            ls.section_id: ls for ls in lanelet_sections
        }
        self._section_ids: Set[SectionID] = {ls.section_id for ls in lanelet_sections}
        self._lanelet2section_id: Dict[int, SectionID] = self.create_lanelet2section_id(
            lanelet_sections
        )

        # Build a directed graph capturing adjacency (predecessor/successor) among sections
        self._graph = nx.DiGraph()

        # Cache for s-intervals (start/end of lanelets in local curvilinear coords)
        self._s_interval: Dict[int, Interval] = {}

        # Build the graph
        for section in lanelet_sections:
            self.add_to_graph(section)

    @property
    def graph(self) -> nx.DiGraph:
        """
        :return: A directed graph of sections, with edges weighted by min_length and max_length.
        """
        return self._graph

    @staticmethod
    def create_lanelet2section_id(lanelet_sections: List[LaneletSection]) -> Dict[int, SectionID]:
        """
        Maps each lanelet_id to the SectionID it belongs to.

        :param lanelet_sections: A list of LaneletSection objects.
        :return: Dictionary from lanelet_id -> SectionID.
        """
        lanelet2section_id = {}
        for ls in lanelet_sections:
            for lanelet in ls.lanelet_list:
                lanelet2section_id[lanelet.lanelet_id] = ls.section_id
        return lanelet2section_id

    def add_to_graph(self, lanelet_section: LaneletSection) -> None:
        """
        Adds a LaneletSection to the internal graph structure, creating edges for
        predecessor/successor relationships with appropriate lengths.

        :param lanelet_section: The LaneletSection to be added.
        """
        sid = lanelet_section.section_id
        # Add edges from predecessors to this section
        for p in lanelet_section.pred_sections:
            self._graph.add_edge(
                p,
                sid,
                min_length=self._lanelet_sections_dict[p].min_length(),
                max_length=self._lanelet_sections_dict[p].max_length(),
            )
        # Add edges from this section to successors
        for s in lanelet_section.succ_sections:
            self._graph.add_edge(
                sid,
                s,
                min_length=lanelet_section.min_length(),
                max_length=lanelet_section.max_length(),
            )

    def get_coordinate_system_lanelet(self, lanelet_id: int) -> CurvilinearCoordinateSystem:
        """
        Computes or retrieves (cached) the CurvilinearCoordinateSystem for the given lanelet.

        :param lanelet_id: The ID of the lanelet.
        :return: A CurvilinearCoordinateSystem object representing the lanelet's geometry.
        :raises ProjectionError: if projection of start/end points fails.
        """
        lanelet = self.lanelets[lanelet_id]
        csys = CurvilinearCoordinateSystem(
            smoothen_polyline(lanelet.center_vertices, resampling_distance=0.5), CLCSParams()
        )

        try:
            start_s = csys.convert_to_curvilinear_coords(
                lanelet.center_vertices[0][0], lanelet.center_vertices[0][1]
            )[0]
            end_s = csys.convert_to_curvilinear_coords(
                lanelet.center_vertices[-1][0], lanelet.center_vertices[-1][1]
            )[0]

            self._s_interval[lanelet_id] = Interval(start_s, end_s)
        except ValueError:
            if self.debug_plots:
                self.debug_plot_curv_projection(
                    lanelet.center_vertices[0],
                    csys,
                    csys.ref_path,
                )
            raise ProjectionError(f"Coordinate projection failed for lanelet {lanelet_id}.")

        return csys

    def get_coordinate_system_section(self, section_id: SectionID) -> CurvilinearCoordinateSystem:
        """
        :param section_id: SectionID whose reference lanelet is used for coordinate system.
        :return: The CurvilinearCoordinateSystem of the reference lanelet of the section.
        """
        ref_lanelet = self._lanelet_sections_dict[section_id].reference_lanelet()
        return self.get_coordinate_system_lanelet(ref_lanelet.lanelet_id)

    def get_curv_position_lanelet(self, position: np.ndarray, lanelet_id: int) -> np.ndarray:
        """
        Converts a global (x, y) position into lane-based curvilinear coordinates of a specific lanelet.

        :param position: [x, y] global coordinates.
        :param lanelet_id: The lanelet ID for which the local coords are computed.
        :return: [s, t] local coordinates, where s is along-lane, t is lateral offset.
        :raises ProjectionError: if the projection fails.
        """
        csys = self.get_coordinate_system_lanelet(lanelet_id)
        pos_c = csys.convert_to_curvilinear_coords(position[0], position[1])

        if lanelet_id not in self._s_interval:
            raise ProjectionError(f"No valid s-interval cached for lanelet {lanelet_id}.")

        # Shift s by the lanelet's start
        pos_c[0] -= self._s_interval[lanelet_id].start
        return pos_c

    def get_curv_position_section(self, position: np.ndarray, section_id: SectionID) -> np.ndarray:
        """
        Converts a global (x, y) position into the coordinate system of a section's reference lanelet.

        :param position: [x, y] global coordinates.
        :param section_id: The SectionID for which the local coords are computed.
        :return: [s, t] local coordinates, where s is along-lane, t is lateral offset.
        :raises ProjectionError: if the projection fails.
        """
        csys = self.get_coordinate_system_section(section_id)
        ref_lanelet = self.get_ref_lanelet_by_section_id(section_id)
        if ref_lanelet.lanelet_id not in self._s_interval:
            raise ProjectionError(
                f"No valid s-interval cached for reference lanelet {ref_lanelet.lanelet_id}."
            )

        try:
            pos_c = csys.convert_to_curvilinear_coords(position[0], position[1])
            pos_c[0] -= self._s_interval[ref_lanelet.lanelet_id].start
        except ValueError:
            if self.debug_plots:
                self.debug_plot_curv_projection(position, csys)
            raise ProjectionError(
                f"Projection failed for position {position} in section {section_id}."
            )
        return pos_c

    def get_ref_lanelet_by_section_id(self, section_id: SectionID) -> Lanelet:
        """
        :param section_id: The section in question.
        :return: The reference lanelet of the given section (maximal length).
        """
        return self._lanelet_sections_dict[section_id].reference_lanelet()

    def debug_plot_curv_projection(
        self,
        position: np.ndarray,
        cosy: CurvilinearCoordinateSystem,
        reference_path: np.ndarray = None,
    ) -> None:
        """
        Plot a debug figure to visualize coordinate system projection (for error handling).

        :param position: The position (x, y) to be shown in the plot.
        :param cosy: The coordinate system to visualize.
        :param reference_path: An optional array of points describing the reference path to draw.
        """
        if not self.debug_plots:
            return

        if reference_path is None:
            reference_path = np.array(cosy.reference_path())
        projection_domain = np.array(cosy.projection_domain())

        rnd = MPRenderer()
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

    @property
    def lanelet2section_id(self) -> Dict[int, SectionID]:
        """
        :return: Mapping of lanelet_id to SectionID.
        """
        return self._lanelet2section_id

    @property
    def lanelet_sections(self) -> List[LaneletSection]:
        """
        :return: All LaneletSections in this network.
        """
        return list(self._lanelet_sections_dict.values())

    def generate_lane_section_id(self) -> SectionID:
        """
        Generates a new unique SectionID which is not yet used by any LaneletSection.

        :return: A new SectionID object with the next available integer ID.
        """
        if self._section_ids:
            return SectionID(max([sid.id for sid in self._section_ids]) + 1)
        else:
            return SectionID(0)

    def add_section(self, lanelet_section: LaneletSection) -> None:
        """
        Adds a new LaneletSection to this network, updating internal references and the graph.

        :param lanelet_section: The LaneletSection to be added.
        """
        if lanelet_section.section_id in self._section_ids:
            return  # already exists

        self._section_ids.add(lanelet_section.section_id)
        self._lanelet_sections.append(lanelet_section)
        self._lanelet_sections_dict[lanelet_section.section_id] = lanelet_section
        self._lanelet2section_id.update(self.create_lanelet2section_id([lanelet_section]))
        for lanelet in lanelet_section.lanelet_list:
            self.lanelets[lanelet.lanelet_id] = lanelet
        self._update_predecessors(lanelet_section)
        self._update_successors(lanelet_section)
        self.add_to_graph(lanelet_section)

    def _update_predecessors(self, lanelet_section: LaneletSection) -> None:
        """
        Gathers lanelets that precede the lanelets in this section
        and updates the section relationships accordingly.
        """
        predecessor_lanelets = set()
        for lanelet in lanelet_section.lanelet_list:
            if lanelet.predecessor:
                predecessor_lanelets.update(lanelet.predecessor)

        pred_sections = set()
        for p in predecessor_lanelets:
            if p in self._lanelet2section_id:
                p_section = self._lanelet2section_id[p]
                pred_sections.add(p_section)
                self._lanelet_sections_dict[p_section].succ_sections.add(lanelet_section.section_id)
        lanelet_section.pred_sections = pred_sections

    def _update_successors(self, lanelet_section: LaneletSection) -> None:
        """
        Gathers lanelets that succeed the lanelets in this section
        and updates the section relationships accordingly.
        """
        successor_lanelets = set()
        for lanelet in lanelet_section.lanelet_list:
            if lanelet.successor:
                successor_lanelets.update(lanelet.successor)

        succ_sections = set()
        for s in successor_lanelets:
            if s in self._lanelet2section_id:
                s_section = self._lanelet2section_id[s]
                succ_sections.add(s_section)
                self._lanelet_sections_dict[s_section].pred_sections.add(lanelet_section.section_id)
        lanelet_section.succ_sections = succ_sections

    @classmethod
    def from_lanelet_network(cls, lanelet_network: LaneletNetwork) -> "LaneletSectionNetwork":
        """
        Creates a LaneletSectionNetwork from a CommonRoad LaneletNetwork.

        :param lanelet_network: The LaneletNetwork to convert.
        :return: A LaneletSectionNetwork instance.
        """
        lane_model = cls(lanelet_sections=[])
        # Start from rightmost lanelets, then move left
        for lanelet_id, lanelet in lanelet_network._lanelets.items():
            if lanelet_id in lane_model._lanelet2section_id or lanelet.adj_right is not None:
                # ensures starting at right-most lanelet only
                continue

            sec_id = lane_model.generate_lane_section_id()
            lanelets_tmp = [lanelet]
            next_lanelet = lanelet

            # Traverse left while adj_left_same_direction is True
            while next_lanelet.adj_left is not None and next_lanelet.adj_left_same_direction:
                next_lanelet = lanelet_network.find_lanelet_by_id(next_lanelet.adj_left)
                lanelets_tmp.append(next_lanelet)

            new_section = LaneletSection(lanelets_tmp, sec_id)
            lane_model.add_section(new_section)
        return lane_model


class SectionRoute:
    """
    Represents a route consisting of connected sections, with tracking of
    lateral/longitudinal indices for each lanelet.
    """

    def __init__(self, lanelet_sections: List[LaneletSection]):
        """
        :param lanelet_sections: A list of LaneletSection objects representing a route.
        """
        self.lanelet_sections = lanelet_sections
        self.lateral_indices: Dict[int, int] = {}
        self.long_indices: Dict[int, int] = {}

        for section in lanelet_sections:
            for i, lanelet in enumerate(section.lanelet_list):
                self.lateral_indices[lanelet.lanelet_id] = i

    def append(self, new_section: LaneletSection) -> None:
        """
        Appends a LaneletSection to this route, updating lateral and longitudinal indices.
        """
        if len(self.lanelet_sections) > 0:
            # find the connected lanelet from the previous section
            connecting_index = 0
            for lanelet in self.lanelet_sections[-1].lanelet_list:
                if lanelet.successor and any(
                    s in [nl.lanelet_id for nl in new_section.lanelet_list]
                    for s in lanelet.successor
                ):
                    # found a lanelet that actually connects to new_section
                    connected_lanelets = set(lanelet.successor).intersection(
                        [nl.lanelet_id for nl in new_section.lanelet_list]
                    )
                    for connecting_index, connecting_lanelet in enumerate(new_section.lanelet_list):
                        if connecting_lanelet.lanelet_id in connected_lanelets:
                            connecting_index -= self.lateral_indices[lanelet.lanelet_id]
                            break
                    break
            self.lateral_indices[new_section.lanelet_list[0].lanelet_id] = connecting_index
        else:
            # no predecessor
            connecting_index = 0

        for l_index, lanelet in enumerate(new_section.lanelet_list):
            self.lateral_indices[lanelet.lanelet_id] = l_index - connecting_index
            self.long_indices[lanelet.lanelet_id] = len(self.lanelet_sections)

        self.lanelet_sections.append(new_section)

    def __getitem__(self, key: Union[int, slice]) -> Union[LaneletSection, "SectionRoute"]:
        """Enables Slice-operation"""
        if isinstance(key, slice):
            return SectionRoute(self.lanelet_sections[key])
        return self.lanelet_sections[key]

    def __len__(self) -> int:
        """Returns length of route"""
        return len(self.lanelet_sections)

    def __iter__(self):
        """Makes iterable"""
        return iter(self.lanelet_sections)

    @property
    def section_id(self) -> SectionID:
        """Returns section_id in the first section"""
        if not self.lanelet_sections:
            raise ValueError("Empty route has no section_id")
        return self.lanelet_sections[0].section_id
