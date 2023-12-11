"""
This class contains functions for creation of final CommonRoad scenario files.
"""
import copy
import logging
import math
import os
import pickle
import random
import shutil
import warnings
from collections import defaultdict
from math import cos, sin
from typing import Dict, List, Union, Tuple, Callable
from xml.etree import cElementTree as ET

import matplotlib.pyplot as plt
import numpy as np
from commonroad.common.file_writer import CommonRoadFileWriter
from commonroad.common.file_writer import OverwriteExistingFile
from commonroad.common.file_writer import Tag
from commonroad.common.solution import Solution, PlanningProblemSolution, VehicleModel, VehicleType, CostFunction, \
    CommonRoadSolutionWriter
from commonroad.common.util import Interval
from commonroad.geometry.shape import Rectangle
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblemSet, PlanningProblem
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.scenario import Scenario, LaneletNetwork, ScenarioID
from commonroad.scenario.state import InitialState, State
from commonroad.scenario.trajectory import Trajectory
from commonroad.visualization.drawable import IDrawable
from commonroad.visualization.mp_renderer import MPRenderer
from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_checker
from commonroad_dc.pycrcc import RectOBB
from scenario_factory.scenario_features.features import changes_lane, get_obstacle_state_list
from scenario_factory.scenario_features.models.scenario_model import ScenarioModel
from crdesigner.map_conversion.sumo_map.config import SumoConfig, EGO_ID_START
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from sumocr.sumo_config.default import InteractiveSumoConfigDefault, ParamType
from scenario_factory.config_files.scenario_config import ScenarioConfig
from scenario_factory.enums import EgoSelectionCriterion
from scenario_factory.scenario_checker import check_collision
from scenario_factory.scenario_util import apply_smoothing_filter, find_first_greater, sort_by_list, \
    get_state_at_time, select_by_vehicle_type
from sumocr.sumo_config import DefaultConfig
from pathlib import Path


class StateList(list):
    def __init__(self, state_list: List[State]):
        assert not None in state_list
        super().__init__(state_list)

    def to_array(self, states: Union[str, List[str]]) -> np.ndarray:
        if isinstance(states, str):
            states = [states]

        array = np.empty([self.__len__(), len(states)])
        for col, state_name in enumerate(states):
            array[:, col] = np.array([getattr(state, state_name) for state in self.__iter__()])

        return array


class GenerateCRScenarios:
    """
    Class for generating CommonRoad scenarios from recorded scenarios.
    """

    def __init__(self, scenario: Scenario, scenario_length: int, scenario_name: str, config: ScenarioConfig,
                 map_folder: str, solution_folder: str = None, timestr: str = None,
                 ego_selection_criteria: List[Callable] = None,
                 delete_collising_obstacles: bool = True,
                 seed=100):
        """

        :param conf: configuration file for sumo simulation
        :param config: configuration file for cr scenario generation
        :param boundary: boundary of the map
        :param lanelet_network:
        :param sumo_scenario_folder:
        :param scenario_name:
        :param timestr: time stamp which will be written in folder name for file tracking
        :param delete_collising_obstacles: delete obstacles that are colliding with others
        """
        random.seed(seed)
        self.scenario: Scenario = scenario
        if delete_collising_obstacles is True:
            self.delete_colliding_obstacles(scenario, all=True, max_collisions=None)
        self.cc = create_collision_checker(scenario)
        self._object_dict_cc = None
        self.scenario_length = scenario_length
        self.conf_scenario: ScenarioConfig = config
        self.lanelet_network: LaneletNetwork = scenario.lanelet_network
        self.map_folder = map_folder
        self.output_dir_name = os.path.join(self.map_folder, '../')
        self.scenario_name = scenario_name
        self.timestr = timestr

        self.state_dict = {}
        self.veh_ids = set()
        self.list_cr_scenarios: List[Scenario] = []
        self.list_cr_scenarios_with_ego = []
        self.list_planning_problem_set = []
        self.list_init_time_steps = []
        self.ego_ids_list = []
        self.ego_selection_criteria = ego_selection_criteria if ego_selection_criteria is not None \
            else self._default_ego_selection_criteria()
        if self.conf_scenario.save_ego_solution_file is True:
            assert solution_folder is not None, "Provide a solution_folder if conf_scenario.save_ego_solution_file=True"
        self.solution_folder = solution_folder
        self.logger = self._init_logging()

    @property
    def scenario(self) -> Scenario:
        return self._scenario_model.scenario

    @scenario.setter
    def scenario(self, scenario: Scenario):
        self._scenario_model = ScenarioModel(scenario, assign_vehicles_on_the_fly=False)

    @property
    def scenario_model(self):
        return self._scenario_model

    @scenario_model.setter
    def scenario_model(self, scenario_model: ScenarioModel):
        self._scenario_model = scenario_model

    def _init_logging(self):
        # Create a custom logger
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(level=getattr(logging, self.conf_scenario.logging_level))

        if not logger.hasHandlers():
            # Create handlers
            c_handler = logging.StreamHandler()

            # Create formatters and add it to handlers
            c_format = logging.Formatter('<%(name)s.%(funcName)s> %(message)s')
            c_handler.setFormatter(c_format)

            # Add handlers to the logger
            logger.addHandler(c_handler)

        return logger

    def _default_ego_selection_criteria(self) -> List[Callable]:
        """:returns default list of selection criteria"""
        mapping = {EgoSelectionCriterion.turning: self.turning_criterion,
                   EgoSelectionCriterion.acceleration: self.acceleration_criterion,
                   EgoSelectionCriterion.braking: self.braking_criterion,
                   EgoSelectionCriterion.lane_change: self.lane_change_criterion,
                   EgoSelectionCriterion.merging: self.merging_criterion}
        return [mapping[crit] for crit in self.conf_scenario.ego_selection_criteria]

    def create_cr_scenarios(self, map_nr, scenario_counter=0):
        """
        convert simulated sumo states of all vehicles to cr scenarios and create planning problems
        """
        # create dicts for easier data handling
        for obs_id, obs in self.scenario._dynamic_obstacles.items():
            self.veh_ids.add(obs_id)
            for state in obs.prediction.trajectory.state_list:
                if state.time_step not in self.state_dict:
                    self.state_dict[state.time_step] = {}

                self.state_dict[state.time_step][obs_id] = state

        obstacles = self.scenario._dynamic_obstacles

        # Create planning problems by selecting ego vehicles and deleting of that vehicle afterward
        list_obstacles, \
            list_obstacles_with_ego, \
            self.list_planning_problem_set, \
            self.list_init_time_steps, \
            self.list_ego_obstacles, \
            self.ego_ids_list = self.create_planning_problem(obstacles,
                                                             self.conf_scenario.planning_pro_with_lanelet,
                                                             self.conf_scenario.visualize_ego,
                                                             self.conf_scenario.planning_pro_per_scen)
        # Write cr scenarios for each planning problem

        for i_sc, obstacles in enumerate(list_obstacles):
            scenario_counter += 1
            scenario_id = ScenarioID(
                cooperative=False,
                country_id=self.conf_scenario.map_name.split('_')[0],
                map_name=self.conf_scenario.map_name.split('_')[1].split('-')[0],
                map_id=int(self.conf_scenario.map_name.split('_')[1].split('-')[1]),
                configuration_id=scenario_counter,
                scenario_version="2020a"
            )
            scenario_id.obstacle_behavior = "I"  # TODO must be checked whether interactive or which type of obstacle prediction
            scenario_id.prediction_id = 1
            cr_scenario = Scenario(self.scenario.dt,
                                   scenario_id=scenario_id,
                                   location=self.scenario.location,
                                   tags=self.scenario.tags,
                                   author=self.scenario.author,
                                   affiliation=self.scenario.affiliation,
                                   source=self.scenario.source)
            cr_scenario.add_objects(self.lanelet_network)
            cr_scenario.add_objects(list(obstacles.values()))
            self.list_cr_scenarios.append(cr_scenario)
            if self.conf_scenario.visualize_ego is True:
                obstacles_with_ego = list_obstacles_with_ego[i_sc]
                cr_scenario_with_ego = Scenario(self.scenario.dt,
                                                scenario_id=scenario_id,
                                                location=self.scenario.location,
                                                tags=self.scenario.tags,
                                                author=self.scenario.author,
                                                affiliation=self.scenario.affiliation,
                                                source=self.scenario.source)
                cr_scenario_with_ego.lanelet_network = self.lanelet_network
                cr_scenario_with_ego.add_objects(list(obstacles_with_ego.values()))
                self.list_cr_scenarios_with_ego.append(cr_scenario_with_ego)

        return scenario_counter

    def _choose_ego_from_obstacles(self, planning_pro_per_scen: int, obstacles: Dict[int, DynamicObstacle]):
        """
         For each planning problem, choose one obstacle as ego vehicle.
        :param planning_pro_per_scen: number of planning problems generated from one scenario
        :param obstacles: CommonRoad obstacles in the scenario
        :return: num_planning_pro: number of planning problems found by the function
        :return: ego_list
        :return: obs_list
        :return: obs_list_with_ego
        """
        # Mapping vehicles on one lane to the lane id.
        # mapping = lanelet_network.map_obstacles_to_lanelets(obstacles)

        ego_list = []
        obs_list = []
        obs_list_with_ego = []
        ego_ids = []
        to_remove = []
        obstacles = copy.deepcopy(obstacles)
        # statistics for all vehicles' maximum velocity differences
        # self.velocity_threshold = self.velocity_statistics(obstacles, 0.33)
        ego_selected: Dict[int, int] = self.select_ego_vehicles(obstacles, self.ego_selection_criteria)
        num_planning_pro = planning_pro_per_scen
        for ego_id, init_time in ego_selected.items():  # obs: List[Obstacles]
            obstacles_copy = copy.deepcopy(obstacles)
            ego = obstacles_copy[ego_id]
            end_time = init_time + self.conf_scenario.cr_scenario_time_steps + 1
            obstacles_copy = self.apply_time_frame(obstacles_copy, init_time, end_time)
            self._remove_irrelevant_obs_ids(ego, init_time, end_time, obstacles_copy)
            ego = obstacles_copy[ego_id]
            assert ego_id in obstacles_copy, 'UNEXPECTED ERROR: default_ego_id {} not in obstacles anymore, deleted?'.format(
                ego_id)

            obstacles_copy_with_ego = copy.deepcopy(obstacles_copy)
            obstacles_copy_with_ego[ego_id]._obstacle_id = self.conf_scenario.default_ego_id
            del obstacles_copy[ego_id]

            obs_list_with_ego.append(obstacles_copy_with_ego)
            obs_list.append(obstacles_copy)
            ego_list.append(ego)
            ego_ids.append(ego_id)

            # choose more ego candidates than needed when possible, and later randomly choose some from candidates
            # if len(ego_list) >= 2 * num_planning_pro:
            #     break

        if len(ego_list) < num_planning_pro:
            self.logger.info(f"Only {len(ego_list)} planning problems found.")
            num_planning_pro = len(ego_list)

        if len(ego_list) > num_planning_pro:
            ego_idx = random.sample(range(len(ego_list)), int(num_planning_pro))
            ego_list = [ego_list[idx] for idx in ego_idx]
            obs_list = [obs_list[idx] for idx in ego_idx]
            obs_list_with_ego = [obs_list_with_ego[idx] for idx in ego_idx]
            ego_ids = [obs.obstacle_id for obs in ego_list]

        init_times = [ego_selected[ego_id] for ego_id in ego_ids]

        return num_planning_pro, ego_list, obs_list, obs_list_with_ego, ego_ids, init_times

    @staticmethod
    def apply_time_frame(obstacles: Dict[int, DynamicObstacle], init_time, end_time) -> Dict[int, DynamicObstacle]:
        """
        Kep only states in selected time frame.
        :param obstacles:
        :param init_time:
        :param end_time:
        :return:
        """
        new_obs = {}
        for obs_id, obs in obstacles.items():
            if init_time >= obs.initial_state.time_step:
                initial_state = copy.deepcopy(obs.state_at_time(init_time))

                if initial_state is None:
                    # print('initial None! obs_id:', obs_id, init_time, obs.prediction.trajectory.initial_time_step,
                    #       obs.prediction.trajectory.final_state.time_step)
                    # print(init_time)
                    # print([state.time_step for state in obs.prediction.trajectory.state_list])
                    # already out of simulation
                    continue

                state_list = copy.deepcopy(
                    [obs.prediction.trajectory.state_at_time_step(t) for t in range(init_time + 1, end_time)
                     if obs.prediction.trajectory.state_at_time_step(t) is not None])
                if len(state_list) <= 3 or state_list[0].time_step != init_time + 1:
                    continue

                # apply new initial time step
                initial_state.time_step = 0
                for i, state in enumerate(state_list):
                    state.time_step = i + 1

                initial_state = InitialState(time_step=initial_state.time_step, position=initial_state.position, orientation=initial_state.orientation, velocity=initial_state.velocity, acceleration=initial_state.acceleration)
                new_obs[obs_id] = DynamicObstacle(copy.deepcopy(obs.obstacle_id), obs.obstacle_type,
                                                  obstacle_shape=obs.obstacle_shape,
                                                  initial_state=initial_state,
                                                  prediction=TrajectoryPrediction(Trajectory(initial_time_step=1,
                                                                                             state_list=state_list),
                                                                                  shape=obs.obstacle_shape)
                                                  )
            pass
        return new_obs

    def create_planning_problem(self, obstacles, planning_pro_with_lanelet=False,
                                visualize_ego=False, planning_pro_per_scen=1):
        """
        Define planning problem for commonroad scenarios.
        :param obstacles: commonroad scenarios converted by _get_all_cr_obstacles
        :param planning_pro_with_lanelet: define goal area in the planning problem by state or lanelet.
        :param planning_pro_per_scen: number of planning problems generated from one scenario
        :return: list of dynamic obstacles
        :return: list of planning problem sets
        """
        lanelet_network = self.lanelet_network

        # find some ego vehicles
        self.logger.debug('start searching for interesting ego vehicles')
        num_planning_pro, ego_list, obs_list, obs_list_with_ego, ego_ids, list_init_time_steps = \
            self._choose_ego_from_obstacles(planning_pro_per_scen, obstacles)

        list_obstacles = []
        list_obstacles_with_ego = []  # used when parameter "visualize_ego" is true
        list_planning_problem_set = []
        for i in range(num_planning_pro):
            self.logger.info(f'create scenario for vehicle {ego_ids[i]}')
            ego = ego_list[i]
            obstacles_short = obs_list[i]

            # define planning problem id
            planing_problem_id = ego_ids[i]

            # define initialState
            initial_pos = ego.initial_state.position
            initial_v = ego.initial_state.velocity
            initial_orientation = ego.initial_state.orientation
            initial_yaw_rate = 0.0
            initial_slip_angle = 0.0
            initial_time_step = ego.initial_state.time_step
            initial_state = InitialState(position=initial_pos,
                                         velocity=initial_v,
                                         orientation=initial_orientation,
                                         yaw_rate=initial_yaw_rate,
                                         slip_angle=initial_slip_angle,
                                         time_step=initial_time_step)

            # define goalState using the final state
            last_state = copy.deepcopy(ego.prediction.trajectory.final_state)
            goal_center = last_state.position
            goal_orientation = last_state.orientation

            goal_state = InitialState(time_step=Interval(last_state.time_step - 1, last_state.time_step),
                                      position=Rectangle(length=6, width=2, center=goal_center, orientation=goal_orientation))
            state_list = [goal_state]
            goal_region = GoalRegion(state_list)

            # define goalState using the final lanelet
            if planning_pro_with_lanelet is True:
                lanelet_of_goal_position = lanelet_network.find_lanelet_by_position([goal_center])[0]  # list of id
                if len(lanelet_of_goal_position) > 0:
                    if len(lanelet_of_goal_position) > 1:
                        initial_lanelets = self.lanelet_network.find_lanelet_by_position([initial_pos])[0]
                        lanelet_of_goal_position_tmp = None
                        dist_min = np.inf
                        for l_goal in lanelet_of_goal_position:
                            for l_init in initial_lanelets:
                                dist = self.scenario_model.lanelet_section_network. \
                                    get_shortest_distance_lanelets(l_init, l_goal)
                                if dist < dist_min:
                                    lanelet_of_goal_position_tmp = l_goal
                        if lanelet_of_goal_position_tmp is None:
                            raise ValueError(f"No reachable goal position can be found for ego {ego.obstacle_id}!")
                        lanelet_of_goal_position = [lanelet_of_goal_position_tmp]

                    self.logger.debug(f'{i + 1}th goal lanelet defined at lanelet {lanelet_of_goal_position}')
                    goal_lanelet = {0: lanelet_of_goal_position}
                    state_list[0].position = lanelet_network.find_lanelet_by_id(
                        lanelet_of_goal_position[0]).polygon
                    goal_region = GoalRegion(state_list, goal_lanelet)
                else:
                    self.logger.warning(f'No goal lanelet found for the {i + 1}th planning problem.')
                    break

            # combine elements of a planning problem and generate planning problem set
            planning_problem = PlanningProblem(planing_problem_id, initial_state, goal_region)
            planning_problem_set = PlanningProblemSet()
            planning_problem_set.add_planning_problem(planning_problem)

            list_obstacles.append(obstacles_short)
            list_planning_problem_set.append(planning_problem_set)
            if visualize_ego is True:
                obstacles_with_ego = obs_list_with_ego[i]
                list_obstacles_with_ego.append(obstacles_with_ego)

        return list_obstacles, list_obstacles_with_ego, list_planning_problem_set, list_init_time_steps, ego_list, ego_ids

    def _select_as_ego(self, vehicle: DynamicObstacle, selection_function='v_diff'):
        """
        Check whether current vehicle can be selected as an ego vehicle.
        :param vehicle: the dynamic obstacle to be checked
        :param selection_function: 'v_diff'-- based on velocity difference of the trajectory; 'accel'-- based on acceleration of the vehicle
        :return: True if the vehicle can be an ego, False else.
        """
        if selection_function == 'v_diff':
            return self._velocity_diff_of_trajectory(vehicle) > self.velocity_threshold
        elif selection_function == 'accel':
            min_accel, max_accel = self.check_acceleration(vehicle)
            return min_accel < self.conf_scenario.max_decel or max_accel > self.conf_scenario.max_accel
        else:
            raise self.logger.error('No selection_function {} defined.'.format(selection_function))

    @staticmethod
    def check_acceleration(obstacle: DynamicObstacle):
        """
        Check the minimal and maximal acceleration value of a obstacle.
        :param obstacle: obstacle to be checked
        :return: minimal acceleration value, maximal acceleration value
        """
        state_list = obstacle.prediction.trajectory.state_list
        accel_list = []
        for state in state_list:
            accel_list.append(state.acceleration)
        return min(accel_list), max(accel_list)

    def velocity_statistics(self, obstacles: List[DynamicObstacle], percentage=0.67) -> float:
        """
        Select the velocity threshold value which filters out one third of the obstacles with the largest velocity
        differences in its trajectory.
        :param obstacles: all the obstacles to be selected
        :param percentage: [0-1] define the percentage of obstacles to be selected
        :return:
        """
        velocity_diff = dict()
        threshold = 3  # self.conf.threshold = 3

        for obstacle in obstacles:
            velocity_diff[obstacle.obstacle_id] = self._velocity_diff_of_trajectory(obstacle)

        if all(i >= threshold for i in list(velocity_diff.values())):
            self.logger.warning(
                'All the velocity differences exceed the threshold.'
                'Please consider using selection function \'accel\' instead of \'v_diff\'.')

        num = int(percentage * len(velocity_diff))
        idx = np.argsort(velocity_diff)  # indecies of velocity_diff from small to large velocity differences
        sorted_obs_ids = sorted(velocity_diff.items(), key=lambda x: x[1])

        if idx is True:
            threshold = velocity_diff[idx[-num]]
        if threshold < 3:
            threshold = 3
        return threshold

    @staticmethod
    def _velocity_diff_of_trajectory(obstacle: DynamicObstacle) -> float:
        """
        Compute the difference between the maximum and minimum velocity of one obstacle's trajectory.
        :param obstacle: the chosen obstacle
        :return: velocity difference of the obstalce's trajectory
        """
        state_list = obstacle.prediction.trajectory.state_list
        speed_list = []
        for state in state_list:
            speed_list.append(state.velocity)
        return max(speed_list) - min(speed_list)

    def _remove_irrelevant_obs_ids(self, ego: DynamicObstacle, init_time, end_time, obstacles_copy):
        """
        Once the ego is selected, select all the vehicles which have never been within sensor_range
        and return a list of their IDs.
        :param ego: ego vehicle
        :return: a list of ids of the irrelevant obstacles
        """
        relevant = [ego.obstacle_id]
        for time_step, veh_dict in self.state_dict.items():
            if not (init_time < time_step < end_time) or ego.obstacle_id not in veh_dict:
                continue
            proj_pos = veh_dict[ego.obstacle_id].position
            proj_pos[0] += math.cos(veh_dict[ego.obstacle_id].orientation) + 2.0 * veh_dict[ego.obstacle_id].velocity
            proj_pos[1] += math.sin(veh_dict[ego.obstacle_id].orientation) + 2.0 * veh_dict[ego.obstacle_id].velocity
            if init_time <= time_step <= end_time:
                for veh_id, state in veh_dict.items():
                    if veh_id not in relevant:
                        if np.less_equal(np.abs(state.position[0] - proj_pos[0]),
                                         self.conf_scenario.sensor_range) \
                                and np.less_equal(np.abs(state.position[1] - proj_pos[1]),
                                                  self.conf_scenario.sensor_range):
                            relevant.append(veh_id)

        to_remove = list(set(self.veh_ids).difference(set(relevant)))
        for id_remove in to_remove:
            if id_remove in obstacles_copy:
                del obstacles_copy[id_remove]

    def write_cr_file_and_video(self, scenario_counter, output_path: Path, create_video=False, check_validity=True):
        """
        Write commonroad scenario file and create corresponding videos.
        :param output_path:
        :param check_validity:
        :param create_video:
        :param scenario_counter: counter for generated scenarios from the i-th map
        :return: nothing
        """
        # create for each planning problem a cr scenario file and the corresponding videos
        generated_scenarios = 0
        for k in range(len(self.list_cr_scenarios)):
            commonroad_scenario = self.list_cr_scenarios[k]

            if check_validity:
                if check_collision(commonroad_scenario._dynamic_obstacles) is True:
                    warnings.warn('<write_cr_file_and_video> Collision detected! Skipping scenario.')
                    continue
                else:
                    self.logger.info('Scenario contains no collision.')
            planning_problem_set = self.list_planning_problem_set[k]
            # write cr file without ego
            commonroad_scenario.scenario_id.prediction_id = 1
            commonroad_scenario.scenario_id.obstacle_behavior = "T"
            filename = output_path.joinpath(str(commonroad_scenario.scenario_id) + '.xml')
            self.write_final_cr_file(filename, commonroad_scenario, planning_problem_set, check_validity)
            self.logger.info(f"Commonroad scenario file created for {k + 1 + scenario_counter}th planning problem")

            # write cr file with ego
            if self.conf_scenario.visualize_ego:
                filename_ego = os.path.join(self.output_dir_name, str(commonroad_scenario.scenario_id) + '_ego.xml')
                commonroad_scenario_with_ego = self.list_cr_scenarios_with_ego[k]
                self.write_final_cr_file(filename_ego, commonroad_scenario_with_ego, planning_problem_set)
                self.logger.info(f"Commonroad scenario file with ego created for"
                                 f"{k + 1 + scenario_counter} th planning problem")

            generated_scenarios += 1
            if create_video is True:
                # create ego centered video
                if self.conf_scenario.visualize_ego is True:
                    cr_scenario_with_ego = self.list_cr_scenarios_with_ego[k]
                    ego_vehicle = cr_scenario_with_ego.obstacle_by_id(self.conf_scenario.default_ego_id)
                    video_center_traj = []
                    ego_state_list = ego_vehicle.prediction.trajectory.state_list
                    for state in ego_state_list:
                        video_center_traj.append(state.position)
                    video_center_traj = tuple(video_center_traj)
                    video_with_ego_centered_path = os.path.join(self.output_dir_name,
                                                                str(commonroad_scenario.scenario_id)
                                                                + '_with_ego_centered.mp4')
                    self.create_scenario_video_ego_centered(
                        [cr_scenario_with_ego, planning_problem_set],
                        time_begin=0,
                        time_end=self.conf_scenario.cr_scenario_time_steps,
                        file_path=video_with_ego_centered_path,
                        draw_params={
                            'scenario': {'dynamic_obstacle': {'show_label': self.conf_scenario.visualize_veh_id},
                                         'lanelet_network': {
                                             'lanelet': {'show_label': self.conf_scenario.visualize_lanelet_id}}}},
                        fps=10,
                        dpi=120,
                        ego_centric_threshold=self.conf_scenario.ego_centric_threshold,
                        ego_id=ego_vehicle.obstacle_id)
                    self.logger.info(f"Video created for {k + 1 + scenario_counter}th planning problem"
                                     f"(ego visualized & ego centered)")

                # self.logger.info(f"Video created for {k + 1 + scenario_counter}th planning problem (ego visualized)")

        return generated_scenarios

    def write_final_cr_file(self, filename, commonroad_scenario: Scenario, planning_problem_set=None,
                            check_validity=False):
        """
        Write final commonroad scenario file.
        :param filename:
        :param commonroad_scenario:
        :param planning_problem_set:
        :return:
        """
        if self.conf_scenario.tags is not None:
            tags = [Tag(tag) for tag in self.conf_scenario.tags]
        else:
            tags = self.conf_scenario.tags

        if planning_problem_set is not None:
            fw = CommonRoadFileWriter(commonroad_scenario, planning_problem_set, author=self.conf_scenario.author,
                                      affiliation=self.conf_scenario.affiliation, source=self.conf_scenario.source,
                                      tags=tags, decimal_precision=4)
            fw.write_to_file(filename, OverwriteExistingFile.ALWAYS, check_validity=check_validity)
        else:
            problemset = PlanningProblemSet(None)
            file_writer = CommonRoadFileWriter(commonroad_scenario, problemset,
                                               tags, decimal_precision=4)
            file_writer.write_to_file(filename, OverwriteExistingFile.ALWAYS)

    # INTERACTIVE SCENARIOS
    @staticmethod
    def reduce_scenario(scenario: Scenario):
        """
        Keep only initial state of dynamic obstacles.
        :param scenario:
        :return:
        """
        scenario._dynamic_obstacles = copy.deepcopy(scenario._dynamic_obstacles)
        for obstacle in scenario.dynamic_obstacles:
            obstacle.prediction = None
        return scenario

    @staticmethod
    def make_vehicle_in_route_file(path_in: str, path_out: str, vehicle_id: str):
        with open(path_in, 'r') as f:
            tree = ET.parse(f)

        vehicle_id = str(vehicle_id)
        found = False
        vehicles = tree.findall("vehicle")
        for v in vehicles:
            if v.get("id") == vehicle_id:
                v.set("id", EGO_ID_START + vehicle_id)
                found = True
                break

        assert found is True, f"No vehicle found with id {vehicle_id} in file {path_in}"
        tree.write(path_out, xml_declaration=True, encoding="utf-8")

    def write_interactive_scenarios_and_videos(self,
                                               scenario_counter: int,
                                               ids_cr2sumo: Dict[int, str],
                                               sumo_net_path: Path,
                                               rou_files: Dict[str, str],
                                               config: SumoConfig,
                                               default_config: InteractiveSumoConfigDefault,
                                               create_video: bool,
                                               check_validity: bool,
                                               output_path: Path):
        generated_scenarios = 0
        for k in range(len(self.list_cr_scenarios)):
            commonroad_scenario = self.list_cr_scenarios[k]
            commonroad_scenario.scenario_id.obstacle_behavior = "I"
            dir_name = output_path.joinpath(str(commonroad_scenario.scenario_id))
            dir_name.mkdir(parents=True, exist_ok=True)
            # copy sumo files
            net_file = str(commonroad_scenario.scenario_id) + ".net.xml"
            shutil.copy(sumo_net_path, dir_name.joinpath(net_file))
            rou_files_new = {}
            deleted_vehicle = False
            for veh_type, rou_file in rou_files.items():
                rou_file_new = dir_name.joinpath(str(commonroad_scenario.scenario_id) + f".{veh_type}.rou.xml")
                if veh_type == "vehicle":
                    self.make_vehicle_in_route_file(rou_file, rou_file_new, ids_cr2sumo[self.ego_ids_list[k]])
                    deleted_vehicle = True
                else:
                    shutil.copy(rou_file, rou_file_new)
                rou_files_new[veh_type] = rou_file_new

            assert deleted_vehicle is True, f"ego vehicle not deleted"
            CR2SumoMapConverter.generate_cfg_file(str(commonroad_scenario.scenario_id), net_file=net_file,
                                                  route_files=rou_files_new, output_folder=dir_name)
            # check_validity
            if check_validity:
                if check_collision(commonroad_scenario._dynamic_obstacles) is True:
                    warnings.warn('<write_cr_file_and_video> Collision detected! Skipping scenario.')
                    continue
                else:
                    self.logger.info('Scenario contains no collision.')

            # write cr file without ego
            planning_problem_set: PlanningProblemSet = self.list_planning_problem_set[k]
            assert self.ego_ids_list[k] in planning_problem_set.planning_problem_dict.keys()
            self.write_interactive_scenario_files(dir_name,
                                                  self.list_init_time_steps[k],
                                                  commonroad_scenario,
                                                  planning_problem_set,
                                                  config, default_config, check_validity)
            self.logger.info(f"Commonroad scenario file created for {k + 1 + scenario_counter}th planning problem")

            if self.conf_scenario.save_ego_solution_file:

                for s in self.list_ego_obstacles[k].prediction.trajectory.state_list:
                    s.steering_angle = 0

                self.list_ego_obstacles[k].initial_state.steering_angle = 0

                traj = Trajectory(initial_time_step=0,
                                  state_list=[self.list_ego_obstacles[k].initial_state] + self.list_ego_obstacles[
                                      k].prediction.trajectory.state_list)
                solution_pp = PlanningProblemSolution(list(planning_problem_set.planning_problem_dict.keys())[0],
                                                      vehicle_model=VehicleModel.KS,
                                                      vehicle_type=VehicleType.FORD_ESCORT,
                                                      cost_function=CostFunction.TR1,
                                                      trajectory=traj)
                CommonRoadSolutionWriter(Solution(commonroad_scenario.scenario_id, [solution_pp])).write_to_file(
                    self.solution_folder)
            # write cr file with ego
            if self.conf_scenario.visualize_ego:
                filename_ego = os.path.join(self.output_dir_name, str(commonroad_scenario.scenario_id) + '_ego.xml')
                commonroad_scenario_with_ego = self.list_cr_scenarios_with_ego[k]
                self.write_final_cr_file(filename_ego, commonroad_scenario_with_ego, planning_problem_set)
                self.logger.info(f"Commonroad scenario file with ego created for"
                                 f"{k + 1 + scenario_counter} th planning problem")

            if create_video is True:
                # create ego centered video
                if self.conf_scenario.visualize_ego is True:
                    cr_scenario_with_ego = self.list_cr_scenarios_with_ego[k]
                    ego_vehicle = cr_scenario_with_ego.obstacle_by_id(self.conf_scenario.default_ego_id)
                    video_center_traj = []
                    ego_state_list = ego_vehicle.prediction.trajectory.state_list
                    for state in ego_state_list:
                        video_center_traj.append(state.position)
                    video_center_traj = tuple(video_center_traj)
                    video_with_ego_centered_path = os.path.join(self.output_dir_name,
                                                                str(commonroad_scenario.scenario_id)
                                                                + '_with_ego_centered.mp4')
                    self.create_scenario_video_ego_centered(
                        [cr_scenario_with_ego, planning_problem_set],
                        time_begin=0,
                        time_end=self.conf_scenario.cr_scenario_time_steps,
                        file_path=video_with_ego_centered_path,
                        draw_params={
                            'scenario': {'dynamic_obstacle': {'show_label': self.conf_scenario.visualize_veh_id},
                                         'lanelet_network': {
                                             'lanelet': {'show_label': self.conf_scenario.visualize_lanelet_id}}}},
                        fps=10,
                        dpi=120,
                        ego_centric_threshold=self.conf_scenario.ego_centric_threshold,
                        ego_id=ego_vehicle.obstacle_id)
                    self.logger.info(f"Video created for {k + 1 + scenario_counter}th planning problem"
                                     f"(ego visualized & ego centered)")

            generated_scenarios += 1

        return generated_scenarios

    def write_interactive_scenario_files(self, dirname,
                                         init_time_step: int,
                                         commonroad_scenario: Scenario,
                                         planning_problem_set,
                                         simulation_config: SumoConfig,
                                         interactive_base_config: InteractiveSumoConfigDefault,
                                         check_validity=False, ):
        if self.conf_scenario.tags is not None:
            tags = [Tag(tag) for tag in self.conf_scenario.tags]
        else:
            tags = self.conf_scenario.tags

        filename = os.path.join(dirname, str(commonroad_scenario.scenario_id) + '.cr.xml')
        commonroad_scenario_init_state = self.reduce_scenario(commonroad_scenario)
        fw = CommonRoadFileWriter(commonroad_scenario_init_state, planning_problem_set, self.conf_scenario.author,
                                  self.conf_scenario.affiliation, self.conf_scenario.source,
                                  tags, decimal_precision=4)
        fw.write_to_file(filename, OverwriteExistingFile.ALWAYS, check_validity=check_validity)

        set_attributes = {"presimulation_steps": simulation_config.presimulation_steps + init_time_step,
                          "simulation_steps": self.conf_scenario.cr_scenario_time_steps,
                          "scenario_name": str(commonroad_scenario.scenario_id),
                          "country_id": commonroad_scenario.scenario_id.country_name}
        with open(os.path.join(dirname, "simulation_config.p"), 'wb') as f:
            out_config = copy.deepcopy(DefaultConfig())
            for attr in dir(interactive_base_config):
                if attr.startswith('__') or callable(getattr(out_config, attr)):
                    continue
                if getattr(interactive_base_config, attr) == ParamType.NOT_SET:
                    setattr(out_config, attr, set_attributes[attr])
                elif attr.startswith("_abc"):
                    continue
                else:
                    setattr(out_config, attr, getattr(simulation_config, attr))

            out_config.scenarios_path = None
            pickle.dump(out_config, f)

        # with open(os.path.join(dirname, "simulation_config.p"), "rb") as input_file:
        #     conf = pickle.load(input_file)
        #     ppp=0
        # yaml.dump(out_config, f, default_flow_style=False)

    @staticmethod
    def create_scenario_video_ego_centered(obj: Union[IDrawable, List[IDrawable]], time_begin: int,
                                           time_end: int, file_path: str, draw_params: Union[dict, None] = None,
                                           fig_size: Union[list, None] = None, fps: int = 10, dpi=80,
                                           ego_centric_threshold=100, ego_id=False):
        """
        Create scenario video in gif format given the path to the scenario xml
        :param filename: Name of the video to be saved
        :param scenarios_path: path to the scenario xml used for creating the video gif
        :param add_only: true if you are only creating new videos and not updating the old ones
        :return:
        """
        file_path = os.path.normpath(file_path)
        assert time_begin < time_end, \
            f'<video/create_scenario_video> time_begin={time_begin} needs to smaller than time_end={time_end}.'

        if fig_size is None:
            fig_size = [15, 8]

        plt.close('all')
        # fig = plt.figure(figsize=(fig_size[0], fig_size[1]))
        # ln, = plt.plot([], [], animated=True)
        plot_limits = [-ego_centric_threshold / 2,
                       ego_centric_threshold / 2,
                       -ego_centric_threshold / 2,
                       ego_centric_threshold / 2]
        renderer = MPRenderer()
        if type(obj) != list:
            obj = [obj]

        if draw_params is not None:
            draw_params = copy.copy(draw_params)
        else:
            draw_params = {}

        draw_params["focus_obstacle_id"] = ego_id
        draw_params["time_begin"] = time_begin
        draw_params["time_end"] = time_end
        renderer.create_video(obj, file_path=file_path, delta_time_steps=2, plotting_horizon=0, draw_params=draw_params)
        # def update(frame=0):
        #     # plot frame
        #     plt.clf()
        #     ax = plt.gca()
        #     ax.set_aspect('equal')
        #     ax.set_xlim(video_center_traj[frame][0] - ego_centric_threshold / 2,
        #                 video_center_traj[frame][0] + ego_centric_threshold / 2)
        #     ax.set_ylim(video_center_traj[frame][1] - ego_centric_threshold / 2,
        #                 video_center_traj[frame][1] + ego_centric_threshold / 2)
        #     draw_params.update({'time_begin': time_begin + frame,
        #                         'time_end': time_begin + min(frame_count, frame + duration)})
        #     renderer.draw_list(obj, draw_params=draw_params)
        #
        #     return ln,
        #
        # frame_count = max(50, len(video_center_traj))
        # # Interval determines the duration of each frame
        # interval = 1.0 / fps
        #
        # # length of trajecotry steps
        # duration = 1
        #
        # anim = FuncAnimation(fig, update, frames=frame_count,
        #                      init_func=update, blit=True, interval=interval)
        # anim.save(file_path, dpi=dpi,
        #           writer='imagemagick')

    def select_ego_vehicles(self, obstacles: Dict[int, DynamicObstacle], ego_selection_criteria: List[Callable]) -> \
            Dict[int, int]:
        """
        Returns ids of vehicles that are chosen as ego vehicle and optionally a time step where the interesting maneuver begins.
        :param obstacles: dict of vehicles to choose from
        :param ego_selection_criteria: List of selection function, which return ids and time steps of selected vehicles
        :return: dictionary with {obstacle_id: time_step}
        """
        ego_veh_candidates = select_by_vehicle_type(obstacles, (ObstacleType.CAR,))
        ego_veh_init_times = defaultdict(list)
        # collect initial time steps for each selected vehicle based on selection criteria
        obs_braking, _ = self.braking_criterion(ego_veh_candidates)
        for func in ego_selection_criteria:
            obs_ids, time_steps = func(ego_veh_candidates)
            for obs, time_step in zip(obs_ids, time_steps):
                if obs in obs_braking:
                    ego_veh_init_times[obs].append(time_step)

        # apply simple pre-filtering to discard uninteresting scenarios
        delete_ids = []
        for obs_id, time_steps in ego_veh_init_times.items():
            self.logger.debug(f'Checking {obs_id}')
            # DEBUG
            assert obstacles[obs_id].obstacle_id == obs_id, 'bug: obstacle id != obs_id'
            if obs_id not in self.scenario._dynamic_obstacles:
                self.logger.warning(f'{obs_id} not in scenario, there is a bug')
                delete_ids.append(obs_id)
                continue

            filtered_list = []
            if obstacles[obs_id].prediction.trajectory.final_state.time_step - obstacles[obs_id].initial_state.time_step \
                    < self.conf_scenario.cr_scenario_time_steps:
                delete_ids.append(obs_id)
                self.logger.debug(f'vehicle {obs_id} skipped: time horizon too short')
                continue

            vel = StateList(obstacles[obs_id].prediction.trajectory.state_list).to_array('velocity').flatten()
            for init_time in time_steps:
                # ensure time interval has minimal length
                if obstacles[obs_id].prediction.trajectory.final_state.time_step - init_time \
                        < self.conf_scenario.cr_scenario_time_steps:
                    self.logger.debug(f'vehicle {obs_id} skipped:'
                                      f'trajectory too short'
                                      f'({obstacles[obs_id].prediction.trajectory.final_state.time_step - init_time})!')
                    continue

                # ensure minimal velocity in at least one time step during complete time interval
                try:
                    v_max = np.max(vel[init_time - obstacles[obs_id].initial_state.time_step:
                                       init_time - obstacles[obs_id].initial_state.time_step
                                       + self.conf_scenario.cr_scenario_time_steps])
                    if v_max < self.conf_scenario.min_ego_velocity:
                        self.logger.debug(f'vehicle {obs_id} skipped: v_max only {v_max} m/s!')
                        continue
                except:
                    print('unexpected', init_time, obstacles[obs_id].prediction.trajectory.final_state.time_step,
                          vel[init_time:init_time + self.conf_scenario.cr_scenario_time_steps])
                    continue

                # filter out single-lane lanelets without merging/diverging/intersecting lanelets
                if init_time == obstacles[obs_id].initial_state.time_step:
                    init_lanelets = list(obstacles[obs_id].initial_center_lanelet_ids)
                else:
                    init_lanelets = list(obstacles[obs_id].prediction.center_lanelet_assignment[init_time])

                final_lanelets = list(obstacles[obs_id].prediction.
                                      center_lanelet_assignment[
                                          init_time + self.conf_scenario.cr_scenario_time_steps - 1])
                if len(init_lanelets) == 1:
                    # disregard when initial and final lanelets are both only single lane
                    init_lanelet = self.lanelet_network.find_lanelet_by_id(init_lanelets[0])
                    if len(final_lanelets) == 1:
                        final_lanelet = self.lanelet_network.find_lanelet_by_id(final_lanelets[0])
                        if not any([init_lanelet.adj_left_same_direction == True,
                                    init_lanelet.adj_right_same_direction == True,
                                    final_lanelet.adj_left_same_direction == True,
                                    final_lanelet.adj_right_same_direction == True,
                                    init_lanelet in self.lanelet_network.map_inc_lanelets_to_intersections]):
                            self.logger.debug(f'right {init_lanelet.adj_right} left {init_lanelet.adj_left}.')
                            self.logger.debug(f'right {final_lanelet.adj_right} left {final_lanelet.adj_left}.')
                            if random.uniform(0, 1) > 0.4:
                                self.logger.debug(f'vehicle {obs_id} skipped: boring single lane!')
                                # disregard with a high probability
                                continue
                    elif len(final_lanelets) == 0:
                        self.logger.debug(f'vehicle {obs_id} skipped: not on map!')
                        continue
                elif len(init_lanelets) == 0:
                    self.logger.debug(f'vehicle {obs_id} skipped: not on map!')
                    continue

                # filter vehicle in front
                # select only ego vehicles with min. number of obstacles in range_min_vehicles
                rear_vehicles, front_vehicles = self.scenario_model. \
                    get_array_closest_obstacles(obstacles[obs_id],
                                                longitudinal_range=Interval(-15, self.conf_scenario.range_min_vehicles),
                                                relative_lateral_indices=True,
                                                time_step=init_time)
                num_veh = 0
                for lane_indx in range(-1, 1):
                    try:
                        num_veh += len(rear_vehicles[lane_indx])
                    except KeyError:
                        pass
                    try:
                        num_veh += len(front_vehicles[lane_indx])
                    except KeyError:
                        pass

                # num_veh = self.get_number_of_veh_in_range(
                #     orientation=get_state_at_time(obstacles[obs_id], init_time).orientation,
                #     position=get_state_at_time(obstacles[obs_id], init_time).position,
                #     time_step=init_time, range_min_vehicles=self.conf_scenario.range_min_vehicles,
                #     obstacles=obstacles)
                self.logger.debug(f'!!! front {front_vehicles}, back {rear_vehicles}')
                if num_veh < self.conf_scenario.min_vehicles_in_range:
                    self.logger.debug(f'vehicle {obs_id} skipped: only {num_veh} vehicles ahead.')
                    continue

                filtered_list.append(init_time)

            if len(filtered_list) > 0:
                ego_veh_init_times[obs_id] = filtered_list
            else:
                delete_ids.append(obs_id)

        for obs_id in delete_ids:
            del ego_veh_init_times[obs_id]

        # extract one time step from collected lists
        ego_dict: Dict[int, int] = {}
        for obs_id, time_steps in ego_veh_init_times.items():
            obs = obstacles[obs_id]
            min_time = obstacles[obs_id].initial_state.time_step
            time_steps_cleaned = [x for x in time_steps if x is not None]
            if len(time_steps_cleaned) > 1:
                num_veh = []
                for time_step in time_steps_cleaned:
                    obs_state = get_state_at_time(obstacles[obs_id], time_step)
                    if obs_state is not None:
                        num_veh.append(
                            self.get_number_of_veh_in_range(
                                position=get_state_at_time(obstacles[obs_id], time_step).position,
                                time_step=time_step,
                                range_min_vehicles=self.conf_scenario.range_min_vehicles,
                                obstacles=obstacles))
                ego_dict[obs_id] = time_steps_cleaned[np.argmax(num_veh)]
            elif len(time_steps_cleaned) == 0:
                ego_dict[obs_id] = min_time
            else:  # len == 1
                ego_dict[obs_id] = time_steps_cleaned[0]

            # ensure that scenarios doesn't start before init time step of obstacle
            ego_dict[obs_id] = int(np.max([ego_dict[obs_id], min_time]))

            # filter with other criteria
            delete = False

            # self.logger.debug(f'number of  vehicles in sensor_range: {num_veh}')
            # if num_veh < self.conf_scenario.min_vehicles_in_range:
            #     delete = True

            if delete:
                del ego_dict[obs_id]
            else:
                self.logger.debug(f'new default_ego_id: {obs_id} at init time={ego_dict[obs_id]}')
        return ego_dict

    def turning_criterion(self, obstacles: Dict[int, DynamicObstacle]):
        """
        Find vehicles that take a turn.
        :param obstacles:
        :return:
        """
        ego_ids = []
        init_time = []

        for obs_id, obs in obstacles.items():
            turns, time_step = self._turning_heuristic(obs)
            if turns:
                self.logger.debug(f'found turning vehicle {obs_id} at time step {time_step}')
                ego_ids.append(obs.obstacle_id)
                init_time.append(time_step)

        return ego_ids[:5], init_time[:5]

    def acceleration_criterion(self, obstacles: Dict[int, DynamicObstacle]):
        """
        Find vehicles that exceed an given acceleration.
        :param obstacles:
        :return:
        """
        ego_ids = []
        init_time = []

        for obs_id, obs in obstacles.items():
            turns, time_step = self._acceleration_heuristic(obs)
            if turns:
                self.logger.debug(f'found accelerating vehicle {obs_id} at time step {time_step}')
                ego_ids.append(obs.obstacle_id)
                init_time.append(time_step)

        return ego_ids, init_time

    def braking_criterion(self, obstacles: Dict[int, DynamicObstacle]):
        """
        Find vehicles that exceed an given deceleration.
        :param obstacles:
        :return:
        """
        ego_ids = []
        init_time = []

        for obs_id, obs in obstacles.items():
            brakes, time_step = self._braking_heuristic(obs)
            if brakes:
                self.logger.debug(f'found braking vehicle {obs_id} at time step {time_step}')
                ego_ids.append(obs.obstacle_id)
                init_time.append(time_step)

        return ego_ids, init_time

    def lane_change_criterion(self, obstacles: Dict[int, DynamicObstacle]):
        """
        Find vehicles that change the lane, ordered by absolute acceleration.
        :param obstacles:
        :return:
        """
        ego_ids = []
        init_time = []
        accelerations = []
        for obs_id, obs in obstacles.items():
            changes_lane, time_step = self._lane_change_heuristic(obs)
            if changes_lane:
                self.logger.debug(f'found lane-changing vehicle {obs_id} at time step {time_step}')
                acc_time_frame = [max(1, time_step - 5),
                                  min(obs.prediction.trajectory.final_state.time_step, time_step + 5)]
                state_list = obs.prediction.trajectory.states_in_time_interval(acc_time_frame[0], acc_time_frame[1])
                if None in state_list: continue
                acc = StateList(state_list).to_array('velocity')
                accelerations.append(-np.max(np.abs(acc)))  # negative values, due to ascending order
                ego_ids.append(obs.obstacle_id)
                init_time.append(time_step)

        ego_ids = sort_by_list(ego_ids, accelerations)
        init_time = sort_by_list(init_time, accelerations)
        return ego_ids, init_time

    def merging_criterion(self, obstacles: Dict[int, DynamicObstacle]):
        """
        Find vehicles that passes a merging lane, ordered by absolute acceleration.
        :param obstacles:
        :return:
        """
        ego_ids = []
        init_time = []
        accelerations = []
        for obs_id, obs in obstacles.items():
            merges, time_step = self._merging_heuristic(obs)
            if merges:
                acc_time_frame = [max(1, time_step - 5),
                                  min(obs.prediction.trajectory.final_state.time_step, time_step + 5)]
                if acc_time_frame[1] - acc_time_frame[0] < 10: continue
                self.logger.debug(f'found merging vehicle {obs_id} at time step {time_step}')
                state_list = [obs.prediction.trajectory.state_at_time_step(t) for t in
                              range(acc_time_frame[0], acc_time_frame[1])]
                if None in state_list: continue
                acc = StateList(state_list).to_array('acceleration')
                accelerations.append(-np.max(np.abs(acc)))  # negative values, due to ascending order
                ego_ids.append(obs.obstacle_id)
                init_time.append(time_step)

        ego_ids = sort_by_list(ego_ids, accelerations)
        init_time = sort_by_list(init_time, accelerations)
        self.logger.debug(f'chosen steps {init_time[:3]}')
        return ego_ids[:3], init_time[:3]

    def _turning_heuristic(self, obstacle: DynamicObstacle) -> Tuple[bool, Union[None, int]]:
        """
        Compute the difference between the maximum and minimum velocity of one obstacle's trajectory.
        :param obstacle: the chosen obstacle
        :return: velocity difference of the obstalce's trajectory
        """
        orientations_ = np.array([state.orientation for state in obstacle.prediction.trajectory.state_list])
        orientations = np.unwrap(orientations_)
        turns, time_step = self._threshold_and_lag_detection(
            orientations,
            initial_timestep=obstacle.initial_state.time_step,
            threshold=self.conf_scenario.turning_detection_threshold,
            lag_threshold=self.conf_scenario.turning_detection_threshold_time)
        if time_step is not None:
            time_step += obstacle.prediction.trajectory.initial_time_step

        return turns, time_step

    def _acceleration_heuristic(self, obstacle: DynamicObstacle) -> Tuple[bool, Union[None, int]]:
        """
        Compute the difference between the maximum and minimum velocity of one obstacle's trajectory.
        :param obstacle: the chosen obstacle
        :return: velocity difference of the obstalce's trajectory
        """
        accelerations = np.array([state.acceleration for state in obstacle.prediction.trajectory.state_list])
        return self._threshold_and_max_detection(accelerations,
                                                 initial_timestep=obstacle.initial_state.time_step,
                                                 threshold=self.conf_scenario.acceleration_detection_threshold,
                                                 time_gap=self.conf_scenario.acceleration_detection_threshold_time)

    def _braking_heuristic(self, obstacle: DynamicObstacle) -> Tuple[bool, Union[None, int]]:
        """
        Compute the difference between the maximum and minimum velocity of one obstacle's trajectory.
        :param obstacle: the chosen obstacle
        :return: velocity difference of the obstalce's trajectory
        """
        accelerations = np.array([state.acceleration for state in obstacle.prediction.trajectory.state_list])
        return self._threshold_and_max_detection(accelerations,
                                                 initial_timestep=obstacle.initial_state.time_step,
                                                 threshold=self.conf_scenario.braking_detection_threshold,
                                                 time_gap=self.conf_scenario.braking_detection_threshold_time)

    def _lane_change_heuristic(self, obstacle: DynamicObstacle) -> Tuple[bool, Union[None, int]]:
        """
        Computes time-step of lane changes
        :param obstacle:
        :return:
        """
        lane_change, direction, time_step = changes_lane(self.lanelet_network, obstacle)
        if lane_change:
            velocity = obstacle.prediction.trajectory.state_at_time_step(time_step).velocity
            if velocity < self.conf_scenario.lc_detection_min_velocity:
                lane_change = False

        return lane_change, max(0, time_step - int(self.conf_scenario.lc_detection_threshold_time / self.scenario.dt))

    def _merging_heuristic(self, obstacle: DynamicObstacle) -> Tuple[bool, Union[None, int]]:
        """
        Computes time-step of lane changes
        :param obstacle:
        :return:
        """
        lane_merge, time_step = self.passes_merging_lane(obstacle)
        if lane_merge:
            velocity = obstacle.prediction.trajectory.state_at_time_step(time_step).velocity
            if velocity < self.conf_scenario.merge_detection_min_velocity:
                lane_merge = False

        return lane_merge, max(0, time_step - int(self.conf_scenario.lc_detection_threshold_time / self.scenario.dt))

    def _threshold_and_lag_detection(self, signal: np.ndarray, initial_timestep: int,
                                     threshold: float, lag_threshold: float) -> Tuple[bool, Union[None, int]]:
        """
        Find whether threshold is exceeded and time step by comparing with lagged signal.
        :param obstacle: the chosen obstacle
        :return: velocity difference of the obstalce's trajectory
        """
        max_difference = np.abs(np.max(signal) - np.min(signal))
        if max_difference > threshold:
            # detect when vehicle is turning by comparred lagging signal to original one
            # -> more time in advance for fast turns
            success, signal_lagged = apply_smoothing_filter(signal)
            if not success:
                return True, 0
            delta_lag = signal - signal_lagged
            init_time = find_first_greater(np.abs(delta_lag), lag_threshold)

            if init_time is None \
                    or init_time + initial_timestep + self.conf_scenario.cr_scenario_time_steps > self.scenario_length:
                return False, None
            else:
                return True, init_time + initial_timestep
        else:
            return False, None

    def _threshold_and_max_detection(self, signal: np.ndarray, threshold: float, initial_timestep: int,
                                     time_gap: float = 1.0, n_hold: int = 2):
        """
        Chceks whether signal exceeds threshold for at least n_hold consecutive time steps and
        returns first time_step-time_gap.
        :param signal:
        :param threshold:
        :param time_gap:
        :return:
        """
        exceeds = None
        # differentiate between min and max thresholds
        if threshold >= 0:
            if np.max(signal) > threshold:
                exceeds = np.greater(signal, threshold)
        else:
            if np.min(signal) < threshold:
                exceeds = np.less(signal, threshold)

        if exceeds is not None:
            # check if and where threshold is exceed for at least n_hold time steps
            diff = exceeds.astype('int16')
            diff = np.diff(diff)
            i_0 = np.where(diff > 0)[0]
            i_end = np.where(diff < 0)[0]

            if i_0.size > 0:
                if i_end.size == 0 or i_0[-1] > i_end[-1]:
                    i_end = np.append(i_end, [exceeds.size - 1])

            if i_0.size == 0 or i_0[0] > i_end[0]:
                i_0 = np.append([0], i_0)

            durations = i_end - i_0

            if durations.size > 0 and np.max(durations) >= n_hold:
                init_time = i_0[np.argmax(durations)]
                if init_time > 0:  # braking at time 0 is usually implausible
                    init_time = int(max(0, init_time - int(time_gap / self.scenario.dt)))

                    if self.conf_scenario.cr_scenario_time_steps + init_time + initial_timestep <= self.scenario_length:
                        return True, init_time + initial_timestep

        return False, None

    def get_number_of_veh_in_range(self, position: np.ndarray, time_step: int, range_min_vehicles,
                                   obstacles: Dict[int, DynamicObstacle], orientation=None):
        counter = 0
        length_ahead = 35.0  # half of length
        if orientation is not None:
            center = position + np.array([cos(orientation), sin(orientation)]) * (length_ahead - 10.0)
            rect = RectOBB(3.0, length_ahead, orientation, center[0], center[1])
            coll = self.cc.time_slice(time_step).find_all_colliding_objects(rect)
            print('N colliding:', len(coll))
            return len(coll)
        else:
            for _, obs in obstacles.items():
                state = get_state_at_time(obs, time_step)
                if state is not None and np.linalg.norm(state.position - position, ord=np.inf) < range_min_vehicles:
                    counter += 1
                    if counter > self.conf_scenario.min_vehicles_in_range * 3:
                        return counter

        return counter

    def delete_colliding_obstacles(self, scenario: Scenario, all=True, max_collisions=None):
        """
        :param scenario:
        :param all: if True, both obstacles of a pair of colliding obstacles is deleted, otherwise only the first one
        :return:
        """
        collsion, ids = check_collision(scenario._dynamic_obstacles, return_colliding_ids=True, get_all=all,
                                        max_collisions=max_collisions)
        print(len(ids), "COLLISOINSW;", len(scenario._dynamic_obstacles), "OBSTCALES")
        for id_ in ids:
            self.scenario.remove_obstacle(scenario._dynamic_obstacles[id_])

    @staticmethod
    def passes_merging_lane(obstacle: DynamicObstacle):
        obstacle_states = get_obstacle_state_list(obstacle)
        lanelets = list(obstacle.prediction.center_lanelet_assignment.values())
        for x0, x0_lanelets, x1_lanelets in zip(obstacle_states[3:-1], lanelets[3:-1], lanelets[4:]):
            if x0_lanelets is None or x1_lanelets is None: continue
            if len(x0_lanelets) != len(x1_lanelets):
                lane_change_ts = x0.time_step + 1
                return True, lane_change_ts
        return False, -1
