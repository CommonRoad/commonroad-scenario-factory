import os

import numpy as np

import scenario_factory
from scenario_factory.enums import EgoSelectionCriterion


class ScenarioConfig:
    # logging level for logging module
    logging_level = 'DEBUG'  # select DEBUG, INFO, WARNING, ERROR, CRITICAL

    _scenario_directory = os.path.dirname(scenario_factory.__file__) + "/../files/globetrotter/"
    _output_folder = os.path.dirname(scenario_factory.__file__) + "/../output/"

    # GENERAL ##########################################################################################################
    # Number of scenarios generated from one map
    scen_per_map = 10

    # Number of planning problems generated from one scenario
    planning_pro_per_scen = 2

    # Define the goal state of the planning problem with a lanelet (if False: define with a state)
    planning_pro_with_lanelet = True

    # scenario length (time of CR scenario -> set simulation duration in sumo_config)
    cr_scenario_time_steps = 100

    # vehicles are deleted from final scenario if not within sensor_range once
    sensor_range = 90

    # default map name
    map_name = 'ZAM_NEW'

    # Tags in cr scenario file
    author = 'Florian Finkeldei'
    affiliation = 'TUM - Cyber-Physical Systems'
    source = 'OpenStreetMap, SUMO Traffic Simulator'
    tags = ['simulated']

    # EGO VEHICLE SELECTION ############################################################################################
    # obstacle_id of ego vehicles when ego vehicle is exported
    default_ego_id = 8888

    # list of possible criteria for selecting ego vehicles
    ego_selection_criteria = [EgoSelectionCriterion.merging,
                              EgoSelectionCriterion.turning,
                              EgoSelectionCriterion.braking,
                              EgoSelectionCriterion.lane_change]

    # additional filters to discard uninteresting situations
    min_ego_velocity = 22 / 3.6  # [m/s] velocity must exceed this value at least once
    min_vehicles_in_range = 1  # min. number of vehicles in range_min_vehicles
    range_min_vehicles = 30  # [m]

    # TURNING DETECTION
    turning_detection_threshold: float = np.deg2rad(60)  # [deg] when orientation differs above threshold, a turn is detected
    turning_detection_threshold_time: float = np.deg2rad(6.0)  # threshold to find time step (difference to lagged signal)

    # ACCELERATION DETECTION
    acceleration_detection_threshold: float = 2.0  # [m/s**2]
    acceleration_detection_threshold_hold: int = 3  # number of time steps for which threshold has to be hold at least
    acceleration_detection_threshold_time: float = 0.5  # time for starting scenario before threshold

    # BRAKING DETECTION
    braking_detection_threshold: float = -3.0
    braking_detection_threshold_hold: int = 4  # number of time steps for which threshold has to be hold at least
    braking_detection_threshold_time: float = acceleration_detection_threshold_time  # time for starting scenario before threshold

    # LANE-CHANGE DETECTION
    lc_detection_threshold_time: float = 0.5  # [s]
    lc_detection_min_velocity: float = 10.0  # [m/s] minimum velocity for detecting a lane change

    # LANE MERGE
    merge_detection_min_velocity = 10.0

    # OUT files
    save_ego_solution_file = True

    # Create videos ####################################################################################################
    visualize_ego = False
    visualize_veh_id = True
    visualize_lanelet_id = False
    ego_centric_threshold = 100

    @property
    def scenario_directory(self):
        return os.path.expanduser(self._scenario_directory)

    @property
    def output_folder(self):
        return os.path.expanduser(self._output_folder)
