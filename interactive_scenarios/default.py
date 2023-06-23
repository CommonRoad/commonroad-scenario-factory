# sumo id prefix
import os
from enum import Enum

from typing import List, Dict, Union
from abc import ABCMeta
from commonroad.common.util import Interval
from commonroad.scenario.obstacle import ObstacleType
from sumocr.sumo_config.default import DefaultConfig


class ParamType(Enum):
    COPY = 0   # needs to be copied from map converter config
    NOT_SET = 1  # needs to be set after planning problem extraction


class InteractiveSumoConfigDefault(DefaultConfig):
    # logging level for logging module
    logging_level = 'INFO'  # select DEBUG, INFO, WARNING, ERROR, CRITICAL

    # default path under which the scenario folder with name SumoCommonRoadConfig.scenario_name are located
    scenarios_path = None

    # scenario name and also folder name under which all scenario files are stored
    scenario_name = ParamType.NOT_SET
    # country_id = ParamType.NOT_SET

    ##
    ## simulation
    ##
    field_of_view = 400
    dt = 0.1  # length of simulation step of the interface
    delta_steps = 1  # number of sub-steps simulated in SUMO during every dt
    presimulation_steps = ParamType.NOT_SET  # number of time steps before simulation with ego vehicle starts
    simulation_steps = ParamType.NOT_SET  # number of simulated (and synchronized) time steps
    # lateral resolution > 0 enables SUMO'S sublane model, see https://sumo.dlr.de/docs/Simulation/SublaneModel.html
    lateral_resolution = 1.0
    # re-compute orientation when fetching vehicles from SUMO.
    # Avoids lateral "sliding" at lane changes at computational costs
    compute_orientation = True

    # ego vehicle
    ego_start_time: int = 0
    ego_veh_width = 1.674
    ego_veh_length = 4.298

    # random seed for deterministic sumo traffic generation (applies if not set to None)
    random_seed: int = ParamType.COPY

    # other vehicles size bound (values are sampled from normal distribution within bounds)
    vehicle_length_interval = ParamType.COPY
    vehicle_width_interval = ParamType.COPY

    # vehicle attributes
    veh_params: Dict[str, Dict[ObstacleType, Union[Interval, float]]] = ParamType.COPY