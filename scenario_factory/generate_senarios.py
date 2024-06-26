import copy
import logging
import math
from pathlib import Path
from typing import List, Optional, Set

import numpy as np
from commonroad.common.util import Interval
from commonroad.geometry.shape import Rectangle
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem, PlanningProblemSet
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.scenario import DynamicObstacle, Scenario

# Options
from commonroad.scenario.state import InitialState, PMState, TraceState
from commonroad.scenario.trajectory import Trajectory
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from sumocr.scenario.scenario_wrapper import ScenarioWrapper

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver
from scenario_factory.scenario_checker import get_colliding_dynamic_obstacles_in_scenario
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.scenario_util import find_most_likely_lanelet_by_state

logger = logging.getLogger(__name__)


def convert_commonroad_scenario_to_sumo(
    commonroad_scenario: Scenario, output_folder: Path, sumo_config: SumoConfig
) -> ScenarioWrapper:
    cr2sumo = CR2SumoMapConverter(commonroad_scenario, sumo_config)
    conversion_possible = cr2sumo.create_sumo_files(str(output_folder))

    if not conversion_possible:
        raise RuntimeError(f"Failed to convert CommonRoad scenario {commonroad_scenario.scenario_id} to SUMO")

    scenario_wrapper = ScenarioWrapper()
    scenario_wrapper.sumo_cfg_file = cr2sumo.sumo_cfg_file
    scenario_wrapper.initial_scenario = copy.deepcopy(commonroad_scenario)

    return scenario_wrapper


def _create_new_obstacle_in_time_frame(
    orig_obstacle: DynamicObstacle, start_time: int, end_time: int, with_prediction: bool = True
) -> Optional[DynamicObstacle]:
    """
    Create a copy of orig_obstacle aligned to time step 0.

    :param orig_obstacle: The obstacle from which the new one will be derived
    :param start_time: Start of the time frame (inclusive)
    :param end_time: End of the time frame (exclusive)
    :param with_prediction: Whether to include the aligned trajectory in the resulting obstacle
    """
    state_at_start = copy.deepcopy(orig_obstacle.state_at_time(start_time))
    if state_at_start is None:
        return None

    # As state_at_start can also be a TraceState, an extra InitialState must be created from it
    initial_state = InitialState(
        time_step=0,
        position=state_at_start.position,
        orientation=state_at_start.orientation,
        velocity=state_at_start.velocity,
        acceleration=state_at_start.acceleration,
    )

    prediction = None
    if with_prediction:
        # The state_list creation is seperated in to two list comprehensions, so that mypy does not complain about possible None values...
        state_list = [orig_obstacle.state_at_time(time_step) for time_step in range(start_time + 1, end_time)]
        state_list = [copy.deepcopy(state) for state in state_list if state is not None]

        for i, state in enumerate(state_list):
            state.time_step = i + 1

        prediction = TrajectoryPrediction(
            Trajectory(initial_time_step=1, state_list=state_list), shape=orig_obstacle.obstacle_shape
        )

    new_obstacle = DynamicObstacle(
        obstacle_id=orig_obstacle.obstacle_id,
        obstacle_type=orig_obstacle.obstacle_type,
        obstacle_shape=orig_obstacle.obstacle_shape,
        initial_state=initial_state,
        prediction=prediction,
    )

    return new_obstacle


def _select_obstacles_in_sensor_range_of_ego_vehicle(
    obstacles: List[DynamicObstacle],
    ego_vehicle: DynamicObstacle,
    sensor_range: int,
) -> List[DynamicObstacle]:
    """
    Select all dynamic obstacles that are at least once during their trajectory in the range around the ego vehicle. This method can be used to reduce the number of obstacles in the resulting scenario, to exclude obstacles that are too far away from an ego vehicle.

    :param obstacles: The list of obstacles from which should be selected
    :param ego_vehicle: The ego vehicle around which obstacles should be selected
    :param sensor_range: The radius around the ego vehicle

    :returns: The selected dynamic obstacles
    """
    relevant = [ego_vehicle]

    assert isinstance(ego_vehicle.prediction, TrajectoryPrediction)

    for ego_vehicle_state in ego_vehicle.prediction.trajectory.state_list:
        # Copy the position, because otherwise this would modify the resulting trajectory of the ego vehicle
        proj_pos = copy.deepcopy(ego_vehicle_state.position)
        proj_pos[0] += math.cos(ego_vehicle_state.orientation) + 2.0 * ego_vehicle_state.velocity
        proj_pos[1] += math.sin(ego_vehicle_state.orientation) + 2.0 * ego_vehicle_state.velocity
        for obstacle in obstacles:
            if obstacle in relevant:
                continue

            obstacle_state = obstacle.state_at_time(ego_vehicle_state.time_step)
            if obstacle_state is None:
                continue

            if np.less_equal(np.abs(obstacle_state.position[0] - proj_pos[0]), sensor_range) and np.less_equal(
                np.abs(obstacle_state.position[1] - proj_pos[1]), sensor_range
            ):
                relevant.append(obstacle)

    return relevant


def _create_planning_problem_initial_state_for_ego_vehicle(
    ego_vehicle: DynamicObstacle,
) -> InitialState:
    initial_state = copy.deepcopy(ego_vehicle.initial_state)
    initial_state.yaw_rate = 0.0
    initial_state.slip_angle = 0.0
    return initial_state


def _create_planning_problem_goal_state_for_ego_vehicle(ego_vehicle: DynamicObstacle) -> TraceState:
    final_state_of_ego_vehicle = copy.deepcopy(ego_vehicle.prediction.trajectory.final_state)
    goal_state = PMState(
        time_step=Interval(final_state_of_ego_vehicle.time_step - 1, final_state_of_ego_vehicle.time_step),
        position=Rectangle(
            length=6,
            width=2,
            center=final_state_of_ego_vehicle.position,
            orientation=final_state_of_ego_vehicle.orientation,
        ),
    )
    return goal_state


def create_planning_problem_set_for_ego_vehicle_maneuver(
    scenario: Scenario,
    scenario_config: ScenarioFactoryConfig,
    ego_vehicle_maneuver: EgoVehicleManeuver,
) -> PlanningProblemSet:
    initial_state = _create_planning_problem_initial_state_for_ego_vehicle(ego_vehicle_maneuver.ego_vehicle)
    goal_state = _create_planning_problem_goal_state_for_ego_vehicle(ego_vehicle_maneuver.ego_vehicle)

    goal_region_lanelet_mapping = None
    if scenario_config.planning_pro_with_lanelet is True:
        # We should create a planning problem goal region, that is associated with the lanelet on which the ego vehicle lands in its goal_state
        lanelet_id_at_goal_state = find_most_likely_lanelet_by_state(
            lanelet_network=scenario.lanelet_network, state=goal_state
        )
        if lanelet_id_at_goal_state is None:
            raise ValueError(
                f"Tried to match maneuver {ego_vehicle_maneuver} to the lanelet in its goal state, but no lanelet could be found for state: {goal_state}"
            )

        # Create the mapping to be used by the GoalRegion construction
        goal_region_lanelet_mapping = {0: [lanelet_id_at_goal_state]}

        # Patch the postion of the goal state to match the whole lanelet
        # TODO: This was the behaviour of the original code. Is this the correct behaviour?
        lanelet_at_goal_state = scenario.lanelet_network.find_lanelet_by_id(lanelet_id_at_goal_state)
        goal_state.position = lanelet_at_goal_state.polygon

    goal_region = GoalRegion([goal_state], goal_region_lanelet_mapping)
    planning_problem_id = ego_vehicle_maneuver.ego_vehicle.obstacle_id
    planning_problem = PlanningProblem(planning_problem_id, initial_state, goal_region)
    planning_problem_set = PlanningProblemSet([planning_problem])

    return planning_problem_set


def create_scenario_for_ego_vehicle_maneuver(
    scenario: Scenario,
    scenario_config: ScenarioFactoryConfig,
    ego_vehicle_maneuver: EgoVehicleManeuver,
) -> Scenario:
    relevant_obstacles = _select_obstacles_in_sensor_range_of_ego_vehicle(
        scenario.dynamic_obstacles, ego_vehicle_maneuver.ego_vehicle, scenario_config.sensor_range
    )
    new_obstacles = []
    for obstacle in relevant_obstacles:
        # Obstacles must have a trajectory that starts at least at the same time as the ego vehicle maneuver
        if obstacle.initial_state.time_step > ego_vehicle_maneuver.start_time:
            continue

        new_obstacle = _create_new_obstacle_in_time_frame(
            obstacle,
            ego_vehicle_maneuver.start_time,
            ego_vehicle_maneuver.start_time + scenario_config.cr_scenario_time_steps + 1,
            with_prediction=True,
        )
        if new_obstacle is not None:
            new_obstacles.append(new_obstacle)

    new_scenario = Scenario(dt=scenario.dt)
    new_scenario.scenario_id = copy.deepcopy(scenario.scenario_id)
    new_scenario.add_objects(new_obstacles)
    new_scenario.add_objects(scenario.lanelet_network)
    return new_scenario


def reduce_scenario_to_interactive_scenario(scenario: Scenario) -> Scenario:
    new_scenario = copy.deepcopy(scenario)
    for obstacle in new_scenario.dynamic_obstacles:
        obstacle.prediction = None

    return new_scenario


def delete_colliding_obstacles_from_scenario(scenario: Scenario, all: bool = True) -> Set[int]:
    ids = get_colliding_dynamic_obstacles_in_scenario(scenario, get_all=all)
    for id_ in ids:
        obstacle = scenario.obstacle_by_id(id_)
        assert (
            obstacle is not None
        ), f"Found a collision for dynamic obstacle {id_}, but this dynamic obstacle is not part of the scenario."
        scenario.remove_obstacle(obstacle)
    return ids
