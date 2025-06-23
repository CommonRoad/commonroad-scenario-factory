from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Set, Tuple, Union

import numpy as np
from commonroad.common.util import Interval
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.obstacle import DynamicObstacle, Obstacle
from commonroad.scenario.scenario import Scenario

from scenario_factory.scenario_features.models.lane_model import (
    LaneletSection,
    LaneletSectionNetwork,
    ProjectionError,
    SectionID,
    SectionRoute,
)


class ScenarioModel:
    """
    Class for computing positions of obstacles in a scenario and related requests in lane-based coordinate systems.
    """

    def __init__(self, scenario: Scenario, assign_vehicles_on_the_fly: bool = True):
        """
        :param scenario: CommonRoad scenario
        :param assign_vehicles_on_the_fly: if false, vehicles are initially assigned to lanelets for all time steps
        """
        self.__assigned_time_steps: List[int] = []
        self.scenario: Scenario = scenario
        self.lanelet_network = scenario.lanelet_network
        self.assign_vehicles_on_the_fly = assign_vehicles_on_the_fly
        if not assign_vehicles_on_the_fly:
            scenario.assign_obstacles_to_lanelets(use_center_only=True)

        # handling lane_section-based coordinate systems
        self.lanelet_section_network = LaneletSectionNetwork.from_lanelet_network(
            self.lanelet_network
        )
        # stores longitudinal positions long_positions[lanelet_id[time_step[obstacle_id]]]
        self.long_positions: Dict[int, Dict[int, Dict[int, np.ndarray]]] = defaultdict(
            lambda: defaultdict(dict)
        )

    def assign_vehicles_at_time_step(self, time_step):
        """
        Assigns vehicles to lanelets for the specified time step in the current simulation scenario.

        This method ensures that vehicles (obstacles) are assigned to their respective lanelets only
        if they exist at the specific time step and meet the required criteria. This is necessary because
        not all obstacles have a valid state at every time step. If the vehicle assignment is handled
        dynamically within the simulation and the time step has not already been processed, the assignment
        is performed. The method avoids redundant assignment for already processed time steps or if
        dynamic assignment is disabled.

        :param time_step: The specific time step at which vehicles should be assigned.
        :return: None
        """
        if self.assign_vehicles_on_the_fly is False or time_step in self.__assigned_time_steps:
            return
        else:
            # Scenario.assign_obstacles_to_lanelets expectes that each obstacle has a definied state at time_step.
            # But this is not given, therefore we must pre-filter the obstacles, so that only obstacles which have a state at time_step are also assigned to the respective lanelets.
            obstacle_ids_to_assign = set(
                [
                    dynamic_obstacle.obstacle_id
                    for dynamic_obstacle in self.scenario.dynamic_obstacles
                    if dynamic_obstacle.state_at_time(time_step) is not None
                ]
            )
            self.scenario.assign_obstacles_to_lanelets(
                time_steps=[time_step], obstacle_ids=obstacle_ids_to_assign, use_center_only=True
            )

    def get_reachable_sections_front(
        self, position: np.ndarray, max_distance
    ) -> List[SectionRoute]:
        """
        Get section_ids of all lanelets within lane-based max_distance.
        :param position: initial state
        :param max_distance: maximal Distance
        :return:
        """
        lsn = self.lanelet_section_network
        lanelet_ids = self.lanelet_network.find_lanelet_by_position([position])[0]
        # init paths with current section(s)
        new_paths: List[List[LaneletSection]] = [
            [ls]
            for ls in {
                lsn._lanelet_sections_dict[lsn.lanelet2section_id[lanelet_id]]
                for lanelet_id in lanelet_ids
            }
        ]
        new_lengths = [0 for p in new_paths]

        # init end result
        reachable_paths = []
        while new_paths:
            path = new_paths.pop()
            length = new_lengths.pop()
            if path[-1].succ_sections and length <= max_distance:
                for succ_id in path[-1].succ_sections:
                    succ_section = self.lanelet_section_network._lanelet_sections_dict[succ_id]
                    new_paths.append(path + [succ_section])
                    new_lengths.append(int(length + succ_section.min_length()))
            else:
                reachable_paths.append(SectionRoute(path))

        return reachable_paths

    def get_obstacles_on_section(
        self, lanelet_section: LaneletSection, time_step: Interval
    ) -> List[Obstacle]:
        """
        Retrieves the obstacles located on a specific lanelet section at a
        given time step. This function consolidates both static and
        dynamic obstacles contained within the provided lanelet section
        into a unified list of obstacle objects. It first collects obstacle
        information at the specified time step and retrieves corresponding
        obstacle details from the scenario.

        :param lanelet_section: The lanelet section across which static
            and dynamic obstacles are queried.
        :param time_step: The specific time step at which dynamic obstacles
            are queried.
        :return: A list of obstacles present in the lanelet section at
            the specified time step.
        :rtype: List[Obstacle]
        """
        self.assign_vehicles_at_time_step(time_step)
        obstacle_ids: Set[int] = set()
        for lanelet in lanelet_section.lanelet_list:
            if lanelet.static_obstacles_on_lanelet is not None:
                obstacle_ids = obstacle_ids.union(lanelet.static_obstacles_on_lanelet)
            if lanelet.dynamic_obstacles_on_lanelet[time_step] is not None:
                obstacle_ids = obstacle_ids.union(lanelet.dynamic_obstacles_on_lanelet[time_step])

        return [self.scenario.obstacle_by_id(obs_id) for obs_id in obstacle_ids]

    def _map_obstacles_to_local_coordinates(
        self, lanelets: Union[List[int], SectionID], time_step: int = 0
    ):
        """
        Maps obstacles in the lanelet network to local coordinate references at a particular
        time step. This method handles both static and dynamic obstacles for the specified
        lanelets by associating them with their corresponding local positions within sections.

        :param lanelets: lanelet identifiers to process. Can be a list of integers, a single integer, or a `SectionID`.
        :param time_step:  the mapping to local coordinates to be performed Def = 0.
        :return: None
        """
        self.assign_vehicles_at_time_step(time_step)

        lanelet_ids: List[int] = []

        if isinstance(lanelets, int):
            lanelet_ids = [lanelets]
        elif isinstance(lanelets, SectionID):
            section = self.lanelet_section_network._lanelet_sections_dict[lanelets]
            lanelet_ids = [lanelet.lanelet_id for lanelet in section.lanelet_list]
        elif isinstance(lanelets, list):
            lanelet_ids = lanelets

        for l_id in lanelet_ids:
            s_id = self.lanelet_section_network.lanelet2section_id[l_id]
            obs_s = self.lanelet_network.find_lanelet_by_id(l_id).static_obstacles_on_lanelet
            obs_s = obs_s if obs_s is not None else set()
            obs_d = self.lanelet_network.find_lanelet_by_id(l_id).dynamic_obstacle_by_time_step(
                time_step
            )
            for obs_id in obs_d | obs_s:
                try:
                    self.long_positions[l_id][time_step][obs_id] = self.map_obstacle_to_section_sys(
                        obs_id, s_id, time_step=time_step
                    )[0]
                except ValueError:
                    continue

    @lru_cache(maxsize=1024)
    def map_obstacle_to_lanelet_sys(
        self, obstacle: Union[Obstacle, int], lanelet: Union[Lanelet, int], time_step: int
    ):
        """
        Maps an obstacle to a lanelet in the system at a specific time step. This function determines
        the curvilinear position of the obstacle on the given lanelet. It retrieves necessary
        information about the lanelet and obstacle based on their ID or provided objects. If
        the obstacle ID does not exist in the scenario, an exception is raised.

        :param obstacle: The obstacle object or its corresponding integer ID to be mapped.
        :param lanelet: The lanelet object or its corresponding integer ID where the obstacles will be mapped.
        :param time_step: The specific timestep for which the obstacle's position is to be determined.
        :return: Curvilinear position of the obstacle on the specified lanelet.
        """
        if isinstance(lanelet, int):
            lanelet_id = lanelet
            lanelet = self.lanelet_network.find_lanelet_by_id(lanelet_id)
        else:
            lanelet_id = lanelet.lanelet_id

        if isinstance(obstacle, int):
            obstacle_obj = self.scenario.obstacle_by_id(obstacle)
            if obstacle_obj is None:
                raise ValueError(
                    f"Obstacle {obstacle} not contained in scenario. All obstacles:"
                    f"{[obs.obstacle_id for obs in self.scenario.obstacles]}"
                )
            obstacle = obstacle_obj

        return self.lanelet_section_network.get_curv_position_lanelet(
            position=obstacle.state_at_time(time_step=time_step).position,
            lanelet_id=lanelet_id,
        )

    @lru_cache(maxsize=1024)
    def map_obstacle_to_section_sys(
        self,
        obstacle: Union[Obstacle, int],
        lanelet_section: Union[LaneletSection, SectionID],
        time_step: int,
    ) -> np.ndarray:
        """
        Maps a given obstacle to a specific section of a lanelet network at a
        specified time step. This function ensures compatibility of the obstacle
        identifier and lanelet section representation with the underlying data structures
        before querying the mapping details. The result is an array that represents
        the position of the obstacle on the specified section of the lanelet network.

        :param obstacle: The obstacle being mapped.
        :param lanelet_section: The lanelet section that the obstacle is being mapped to
        :param time_step: The time step at which the obstacle is being mapped.
        :return: A numpy array representing the obstacle's position on the specified section of the lanelet network.
        """
        if isinstance(lanelet_section, LaneletSection):
            lanelet_section = lanelet_section.section_id
        if isinstance(obstacle, int):
            # print(obstacle)
            obstacle = self.scenario.obstacle_by_id(obstacle)
            if obstacle is None:
                raise ValueError(
                    f"Obstacle {obstacle} not contained in scenario. All obstacles:"
                    f"{[obs.obstacle_id for obs in self.scenario.obstacles]}"
                )

        return self.lanelet_section_network.get_curv_position_section(
            position=obstacle.state_at_time(time_step=time_step).position,
            section_id=lanelet_section,
        )

    def _get_long_slice(
        self, section_route: SectionRoute, time_step: int, exclude_obstacle: Union[int, None] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates longitudinal and lateral position indices for a given section route at a specific
        time step. This allows for obtaining information about the spatial distribution of objects
        while optionally excluding a specific obstacle.

        :param section_route: The section route object that includes lanelet sections and
            required mapping details.

        :param time_step: The specific time step for which the longitudinal and lateral positions
            will be mapped.

        :param exclude_obstacle: The ID of the obstacle to be excluded from the resulting dataset.
            Use None to include all obstacles.

        :return: A tuple containing three numpy arrays:
            - Array of obstacle IDs
            - Array of longitudinal positions of the obstacles
            - Array of lateral indices of the obstacles
        :rtype: Tuple[np.ndarray, np.ndarray, np.ndarray]
        """
        long_position_dict = {}
        lat_index_dict = {}
        s0 = 0.0
        for lanelet_section in section_route.lanelet_sections:
            for lanelet in lanelet_section.lanelet_list:
                lat_index = section_route.lateral_indices[lanelet.lanelet_id]
                for obs_id, pos in self.long_positions[lanelet.lanelet_id][time_step].items():
                    if obs_id == exclude_obstacle:
                        continue
                    long_position_dict[obs_id] = pos + s0
                    lat_index_dict[obs_id] = lat_index

            s0 += lanelet_section.min_length()

        return (
            np.array(list(long_position_dict.keys())),
            np.array(list(long_position_dict.values())),
            np.array(list(lat_index_dict.values())),
        )

    def get_obstacles_array(
        self,
        init_position: Union[np.ndarray, DynamicObstacle],
        longitudinal_range: Interval = Interval(-50, 100),
        time_step=0,
        relative_lateral_indices: bool = True,
    ) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """
        Get array of obstacles with distance and lane information around a given position.
        :param init_position: reference position
        :param longitudinal_range: return only vehicle within longitudinal range
        :param time_step: time step of positions
        :return: list of tuples with obstacle_ids, long_positions, lateral_indices for each reachable section_route
        """
        exclude_id = None
        if isinstance(init_position, DynamicObstacle):
            # exclude vehicle from all results
            exclude_id = init_position.obstacle_id
            # print(time_step, [state.time_step for state in init_position.prediction.trajectory.state_list])
            init_position = init_position.state_at_time(time_step).position

        reachable_routes = self.get_reachable_sections_front(
            init_position, max_distance=longitudinal_range.end
        )
        initial_lanelets = self.lanelet_network.find_lanelet_by_position([init_position])[0]
        obstacle_arrays = []
        for section_route in reachable_routes[:]:
            # get data for initial position
            try:
                s_init = self.lanelet_section_network.get_curv_position_section(
                    init_position, section_route[0].section_id
                )[0]
            except ProjectionError:
                continue

            init_lateral_index = None
            for init_lanelet in initial_lanelets:
                if init_lanelet in section_route.lateral_indices:
                    init_lateral_index = section_route.lateral_indices[init_lanelet]
                    break

            for section in section_route:
                self._map_obstacles_to_local_coordinates(section.section_id, time_step)

            obstacle_ids, long_positions, lateral_indices = self._get_long_slice(
                section_route, time_step, exclude_id
            )
            if long_positions.size > 0:
                long_positions -= s_init

            # apply range interval
            range_mask = np.logical_and(
                long_positions >= longitudinal_range.start, long_positions <= longitudinal_range.end
            )
            obstacle_ids = obstacle_ids[range_mask]
            long_positions = long_positions[range_mask]
            lateral_indices = lateral_indices[range_mask]

            if relative_lateral_indices is True:
                lateral_indices -= init_lateral_index

            obstacle_arrays.append((obstacle_ids, long_positions, lateral_indices))

        return obstacle_arrays

    def get_array_closest_obstacles(
        self,
        init_position: Union[np.ndarray, DynamicObstacle],
        longitudinal_range: Interval = Interval(-50, 100),
        time_step: int = 0,
        relative_lateral_indices: bool = True,
    ) -> Tuple[Dict[int, Dict[int, float]], Dict[int, Dict[int, float]]]:
        """
        Returns the closest obstacles in front and behind `init_position`, separated by lane index.

        The method collects obstacles around the given position (or a DynamicObstacle) within
        a specified longitudinal range, then for each lane index determines the single closest
        obstacle in front and behind.

        :param init_position: reference position
        :param longitudinal_range: return only vehicle within longitudinal range
        :param time_step: time step of positions
        :param relative_lateral_indices: relative lateral indices
        :return a tuple containing two dictionaries
        """

        def _select_closest(
            mask: np.ndarray,
            obstacle_ids: np.ndarray,
            long_positions: np.ndarray,
            position_dict: Dict[int, float],
        ):
            """
            Finds the obstacle with the minimal absolute distance among the masked obstacles
            and stores it into position_dict.
            """
            if not np.any(mask):
                return
            obs_ids_sel = obstacle_ids[mask]
            long_pos_sel = long_positions[mask]
            ind_min = np.argmin(np.abs(long_pos_sel))
            obs_min = obs_ids_sel[ind_min]
            pos_min = long_pos_sel[ind_min]
            position_dict[obs_min] = pos_min

        # 1) First, retrieve all obstacle data
        obs_arrays = self.get_obstacles_array(
            init_position=init_position,
            longitudinal_range=longitudinal_range,
            time_step=time_step,
            relative_lateral_indices=relative_lateral_indices,
        )

        # 2) Initialize result structures for "vehicles behind" / "vehicles ahead"
        min_behind: Dict[int, Dict[int, float]] = {}
        min_front: Dict[int, Dict[int, float]] = {}

        if not obs_arrays:
            # If there was no return on the array, returns as empty immediately
            return min_behind, min_front

        # 3) Process each found group of (obstacle_ids, long_positions, lat_indices)
        for obstacle_ids, long_positions, lat_indices in obs_arrays:
            #    3a) If no obstacles or lateral indices are empty -> skip range(...)
            if obstacle_ids.size == 0 or lat_indices.size == 0:
                continue

            #    3b) Determine the minimum and maximum lane indices
            lat_min = int(np.min(lat_indices))
            lat_max = int(np.max(lat_indices))

            #    3c) Iterate through all integer lane indices
            for lat_index in range(lat_min, lat_max + 1):
                if lat_index not in min_behind:
                    min_behind[lat_index] = {}
                if lat_index not in min_front:
                    min_front[lat_index] = {}

                #        3d) Vehicles "ahead" = long_positions >= 0
                mask_front = (long_positions >= 0.0) & (lat_indices == lat_index)
                _select_closest(mask_front, obstacle_ids, long_positions, min_front[lat_index])

                #        3e) Vehicles "behind" = long_positions < 0
                mask_behind = (long_positions < 0.0) & (lat_indices == lat_index)
                _select_closest(mask_behind, obstacle_ids, long_positions, min_behind[lat_index])

        return min_behind, min_front
