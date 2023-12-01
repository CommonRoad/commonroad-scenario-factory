from collections import defaultdict
from functools import lru_cache
from typing import List, Union, Dict, Tuple

import numpy as np
from commonroad.common.util import Interval

from commonroad.scenario.lanelet import LaneletNetwork, Lanelet
from commonroad.scenario.obstacle import Obstacle, DynamicObstacle
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.trajectory import State
from scenario_factory.scenario_features.models.lane_model import (LaneletSectionNetwork, LaneletSection, SectionID,
                                                                  SectionRoute, ProjectionError)


class ScenarioModel:
    """
    Class for computing positions of obstacles in a scenario and related requests in lane-based coordinate systems.
    """

    def __init__(self, scenario: Scenario, assign_vehicles_on_the_fly: bool = True):
        """
        :param scenario: CommonRoad scenario
        :param assign_vehicles_on_the_fly: if false, vehicles are initially assigned to lanelets for all time steps
        """
        self.__assigned_time_steps = []
        self.scenario: Scenario = scenario
        self.lanelet_network = scenario.lanelet_network
        self.assign_vehicles_on_the_fly = assign_vehicles_on_the_fly
        if not assign_vehicles_on_the_fly:
            scenario.assign_obstacles_to_lanelets(use_center_only=True)

        # handling lane_section-based coordinate systems
        self.lanelet_section_network = LaneletSectionNetwork.from_lanelet_network(self.lanelet_network)
        # stores longitudinal positions long_positions[lanelet_id[time_step[obstacle_id]]]
        self.long_positions = defaultdict(lambda: defaultdict(dict))

    def assign_vehicles_at_time_step(self, time_step):
        """:returns if vehicles were already assigned to lanelets at this time step"""
        if self.assign_vehicles_on_the_fly is False or time_step in self.__assigned_time_steps:
            return
        else:
            self.scenario.assign_obstacles_to_lanelets(time_steps=[time_step], use_center_only=True)

    def get_reachable_sections_front(self, position: np.ndarray, max_distance) -> List[SectionRoute]:
        """
        Get section_ids of all lanelets within lane-based max_distance.
        :param state: initial state
        :return:
        """
        lsn = self.lanelet_section_network
        lanelet_ids = self.lanelet_network.find_lanelet_by_position([position])[0]
        # init paths with current section(s)
        new_paths: List[List[LaneletSection]] = \
            [[ls] for ls in {lsn._lanelet_sections_dict[lsn.lanelet2section_id[l]] for l in lanelet_ids}]
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
                    new_lengths.append(length + succ_section.min_length())
            else:
                reachable_paths.append(SectionRoute(path))

        return reachable_paths

    def get_obstacles_on_section(self, lanelet_section: LaneletSection, time_step: Interval) -> List[Obstacle]:
        """ :returns: all vehicles on this section
        """
        self.assign_vehicles_at_time_step(time_step)
        obstacle_ids = set()
        for lanelet in lanelet_section.lanelet_list:
            if lanelet.static_obstacles_on_lanelet is not None:
                obstacle_ids = obstacle_ids.union(lanelet.static_obstacles_on_lanelet)
            if lanelet.dynamic_obstacles_on_lanelet[time_step] is not None:
                obstacle_ids = obstacle_ids.union(lanelet.dynamic_obstacles_on_lanelet[time_step])

        return [self.scenario.obstacle_by_id(obs_id) for obs_id in obstacle_ids]

    def _map_obstacles_to_local_coordinates(self, lanelets: Union[List[int], SectionID], time_step: int = 0):
        """"""
        self.assign_vehicles_at_time_step(time_step)
        if isinstance(lanelets, SectionID):
            lanelets = self.lanelet_section_network._lanelet_sections_dict[lanelets].lanelet_list
            lanelets = [l.lanelet_id for l in lanelets]

        for l_id in lanelets:
            s_id = self.lanelet_section_network.lanelet2section_id[l_id]
            obs_s = self.lanelet_network.find_lanelet_by_id(l_id).static_obstacles_on_lanelet
            obs_s = obs_s if obs_s is not None else set()
            obs_d = self.lanelet_network.find_lanelet_by_id(l_id).dynamic_obstacle_by_time_step(time_step)
            for obs_id in obs_d | obs_s:
                try:
                    self.long_positions[l_id][time_step][obs_id] \
                        = self.map_obstacle_to_section_sys(obs_id, s_id, time_step=time_step)[0]
                except ValueError:
                    continue

    @lru_cache(maxsize=1024)
    def map_obstacle_to_lanelet_sys(self, obstacle: Union[Obstacle, int], lanelet: Union[Lanelet, int], time_step: int):
        """ :returns local coordinates of obstacle on lanelet."""
        if type(lanelet) == Lanelet:
            lanelet = lanelet.lanelet_id
        if type(obstacle) == int:
            obstacle = self.scenario.obstacle_by_id(obstacle)

        return self.lanelet_section_network \
            .get_curv_position_lanelet(position=obstacle.state_at_time(time_step=time_step).position,
                                       lanelet_id=lanelet.lanelet_id)

    @lru_cache(maxsize=1024)
    def map_obstacle_to_section_sys(self, obstacle: Union[Obstacle, int],
                                    lanelet_section: Union[LaneletSection, SectionID], time_step: int) -> np.ndarray:
        """ :returns local coordinates of obstacle on lanelet."""
        if type(lanelet_section) == LaneletSection:
            lanelet_section = lanelet_section.section_id
        if type(obstacle) == int:
            # print(obstacle)
            obstacle = self.scenario.obstacle_by_id(obstacle)
            if obstacle is None:
                raise ValueError(f'Obstacle {obstacle} not contained in scenario. All obstacles:'
                                 f'{[obs.obstacle_id for obs in self.scenario.obstacles]}')

        return self.lanelet_section_network \
            .get_curv_position_section(position=obstacle.state_at_time(time_step=time_step).position,
                                       section_id=lanelet_section)

    def _get_long_slice(self, section_route: SectionRoute, time_step: int, exclude_obstacle: Union[int, None] = None) \
            -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """ :returns obstacle_ids,
                     longitudinal positions with respect to initial lanelet,
                     lateral index of lanelet (right to left)
        """
        long_position_dict = {}
        lat_index_dict = {}
        s0 = 0.0
        for lanelet_section in section_route.lanelet_sections:
            for l in lanelet_section.lanelet_list:
                lat_index = section_route.lateral_indices[l.lanelet_id]
                for obs_id, pos in self.long_positions[l.lanelet_id][time_step].items():
                    if obs_id == exclude_obstacle:
                        continue
                    long_position_dict[obs_id] = pos + s0
                    lat_index_dict[obs_id] = lat_index

            s0 += lanelet_section.min_length()

        return np.array(list(long_position_dict.keys())), \
               np.array(list(long_position_dict.values())), \
               np.array(list(lat_index_dict.values())),

    def get_obstacles_array(self, init_position: Union[np.ndarray, DynamicObstacle],
                            longitudinal_range: Interval = Interval(-50, 100),
                            time_step=0, relative_lateral_indices: bool = True) \
            -> List[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
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

        reachable_routes = self.get_reachable_sections_front(init_position, max_distance=longitudinal_range.end)
        initial_lanelets = self.lanelet_network.find_lanelet_by_position([init_position])[0]
        obstacle_arrays = []
        for section_route in reachable_routes[:]:
            # get data for initial position
            try:
                s_init = self.lanelet_section_network. \
                    get_curv_position_section(init_position, section_route[0].section_id)[0]
            except ProjectionError:
                continue

            init_lateral_index = None
            for init_lanelet in initial_lanelets:
                if init_lanelet in section_route.lateral_indices:
                    init_lateral_index = section_route.lateral_indices[init_lanelet]
                    break

            for section in section_route[:]:
                self._map_obstacles_to_local_coordinates(section.section_id, time_step)

            obstacle_ids, long_positions, lateral_indices = self._get_long_slice(section_route, time_step, exclude_id)
            if long_positions.size > 0:
                long_positions -= s_init

            # apply range interval
            range_mask = np.logical_and(long_positions >= longitudinal_range.start,
                                        long_positions <= longitudinal_range.end)
            obstacle_ids = obstacle_ids[range_mask]
            long_positions = long_positions[range_mask]
            lateral_indices = lateral_indices[range_mask]

            if relative_lateral_indices is True:
                lateral_indices -= init_lateral_index

            obstacle_arrays.append((obstacle_ids, long_positions, lateral_indices))

        return obstacle_arrays

    def get_array_closest_obstacles(self, init_position: Union[np.ndarray, DynamicObstacle],
                                    longitudinal_range: Interval = Interval(-50, 100),
                                    time_step=0, relative_lateral_indices: bool = True):
        """
        Get closest obstacles before and behind init_position separated for every lane.
        :param init_position: initial position or vehicle
        :param longitudinal_range:
        :param time_step:
        :param relative_lateral_indices: if True, return relative lateral lane indices.
        :return:
        """

        def select_with_mask(np_mask: np.ndarray, position_dict: dict):
            """ :returns obstacle id with closest position of vehicle out of the masked ones
                         and puts it into position_dict."""
            if np.any(np_mask != 0):
                obstacle_id_select = obstacle_ids[np_mask]
                long_pos_select = long_positions[np_mask]
                ind_min = np.argmin(np.abs(long_pos_select))
                obs_min = obstacle_id_select[ind_min]

                position_dict[lat_index][obs_min] = long_pos_select[ind_min]

            return position_dict

        obstacle_arrays = self.get_obstacles_array(init_position, longitudinal_range, time_step=time_step,
                                                   relative_lateral_indices=relative_lateral_indices)
        min_front = defaultdict(dict)
        min_behind = defaultdict(dict)

        for array in obstacle_arrays:
            obstacle_ids, long_positions, lateral_indices = array
            if obstacle_ids.size > 0:
                for lat_index in range(np.min(lateral_indices), np.max(lateral_indices) + 1):
                    # select closest vehicle in front
                    mask_tmp = np.logical_and(long_positions >= 0.0, lateral_indices == lat_index)
                    select_with_mask(mask_tmp, min_front)

                    # select closest vehicle in rear
                    mask_tmp = np.logical_and(long_positions < 0.0, lateral_indices == lat_index)
                    select_with_mask(mask_tmp, min_behind)

        return dict(min_behind), dict(min_front)
