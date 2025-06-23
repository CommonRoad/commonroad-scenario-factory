__all__ = [
    "generate_scenario_with_planning_problem_set_and_solution_for_ego_vehicle_maneuver",
    "delete_colliding_obstacles_from_scenario",
]


import copy
import logging
import math
from typing import List, Set, Tuple

import numpy as np
from commonroad.common.solution import (
    PlanningProblemSolution,
)
from commonroad.common.util import Interval
from commonroad.geometry.shape import Rectangle
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem, PlanningProblemSet
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.scenario import DynamicObstacle, Scenario
from commonroad.scenario.state import InitialState, PMState, TraceState

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver
from scenario_factory.scenario_checker import get_colliding_dynamic_obstacles_in_scenario
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.utils import (
    align_dynamic_obstacle_to_time_step,
    align_scenario_to_time_step,
    copy_scenario,
    create_planning_problem_solution_for_ego_vehicle,
    crop_dynamic_obstacle_to_time_frame,
    find_most_likely_lanelet_by_state,
)

_LOGGER = logging.getLogger(__name__)


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
    # Use a dictionary to improve look up speed
    relevant_obstacle_map = {}

    assert isinstance(ego_vehicle.prediction, TrajectoryPrediction)

    for ego_vehicle_state in ego_vehicle.prediction.trajectory.state_list:
        # Copy the position, because otherwise this would modify the resulting trajectory of the ego vehicle
        proj_pos = copy.deepcopy(ego_vehicle_state.position)
        proj_pos[0] += math.cos(ego_vehicle_state.orientation) + 2.0 * ego_vehicle_state.velocity
        proj_pos[1] += math.sin(ego_vehicle_state.orientation) + 2.0 * ego_vehicle_state.velocity
        for obstacle in obstacles:
            if obstacle.obstacle_id == ego_vehicle.obstacle_id:
                continue

            if obstacle.obstacle_id in relevant_obstacle_map:
                continue

            obstacle_state = obstacle.state_at_time(ego_vehicle_state.time_step)
            if obstacle_state is None:
                continue

            if np.less_equal(
                np.abs(obstacle_state.position[0] - proj_pos[0]), sensor_range
            ) and np.less_equal(np.abs(obstacle_state.position[1] - proj_pos[1]), sensor_range):
                relevant_obstacle_map[obstacle.obstacle_id] = obstacle

    return list(relevant_obstacle_map.values())


def _create_planning_problem_initial_state_for_ego_vehicle(
    ego_vehicle: DynamicObstacle,
) -> InitialState:
    initial_state = copy.deepcopy(ego_vehicle.initial_state)
    initial_state.yaw_rate = 0.0
    initial_state.slip_angle = 0.0
    return initial_state


def _create_planning_problem_goal_state_for_ego_vehicle(
    ego_vehicle: DynamicObstacle, goal_time_interval: Interval
) -> TraceState:
    """
    Create a new state that can be used as a goal state in a planning problem
    """
    final_state_of_ego_vehicle = copy.deepcopy(ego_vehicle.prediction.trajectory.final_state)
    goal_state = PMState(
        time_step=goal_time_interval,
        position=Rectangle(
            length=6,
            width=2,
            center=final_state_of_ego_vehicle.position,
            orientation=final_state_of_ego_vehicle.orientation,
        ),
    )
    return goal_state


def create_planning_problem_for_ego_vehicle(
    lanelet_network: LaneletNetwork,
    ego_vehicle: DynamicObstacle,
    planning_problem_time_interval: Interval,
    planning_problem_with_lanelet: bool = True,
) -> PlanningProblem:
    """
    Create a new planning problem for the trajectory of the `ego_vehicle`. The initial and final state will become the start and goal state of the planning problem.

    :param lanelet_network: Lanelet network used to match the goal state to the final lanelets, if `planning_problem_with_lanelet` is set.
    :param ego_vehicle: The ego vehicle with a trajectory that will form the basis for the planning problem
    :param planning_problem_time_interval: The time step interval set for the goal state of the planning problem.
    :param planning_problem_with_lanelet: Whether the goal region should also contain references to the final lanelet. If the intial state and goal region are on the same lanelet, the goal region will not contain a reference to the final lanelet.

    :returns: A new PlanningProblem for the `ego_vehicle`
    """
    initial_state = _create_planning_problem_initial_state_for_ego_vehicle(ego_vehicle)
    goal_state = _create_planning_problem_goal_state_for_ego_vehicle(
        ego_vehicle, planning_problem_time_interval
    )

    goal_region_lanelet_mapping = None
    if planning_problem_with_lanelet is True:
        # We should create a planning problem with a goal region, that is associated with the lanelet on which the ego vehicle lands in its goal_state
        lanelet_id_at_goal_state = find_most_likely_lanelet_by_state(lanelet_network, goal_state)
        if lanelet_id_at_goal_state is None:
            raise ValueError(
                f"Tried to match ego vehicle {ego_vehicle.obstacle_id} to the lanelet in its goal state, but no lanelet could be found for state: {goal_state}."
            )

        # Also check the initial lanelet, to determine if the goal and initial lanelet are the same
        lanelet_id_at_initial_state = find_most_likely_lanelet_by_state(
            lanelet_network, initial_state
        )
        if lanelet_id_at_initial_state is None:
            # We are sometimes not able to match the initial state to a lanelet,
            # because the trajectories begin outside of the lanelet network.
            # In such cases, we cannot guarantee that the goal state and initial state are
            # not directly on the same lanelet and therefore do not associate
            # the goal region with the goal lanelet.
            _LOGGER.debug(
                f"While creating planning problem for ego vehicle {ego_vehicle.obstacle_id} tried to match initial state of ego vehicle to a lanelet, but initial state is not on the lanelet network."
            )
        elif lanelet_id_at_initial_state == lanelet_id_at_goal_state:
            # If the initial state and goal state happen on the same lanelet,
            # the goal lanelet will not be associated with the goal region, because
            # otherwise the planning problem would already be solved by the initial state.
            _LOGGER.debug(
                f"While creating planning problem for ego vehicle {ego_vehicle.obstacle_id} matched goal state and initial state to same lanelet ({lanelet_id_at_initial_state}). This configuration is invalid, therefore the planning problem will not have a goal lanelet set."
            )
        else:
            # Create the mapping to be used by the GoalRegion construction.
            # Generally, we could also set multiple lanelets per state, but then this would clash
            # with the `position` of the goal state, which is set to the polygon of the
            # associated lanelet.
            goal_region_lanelet_mapping = {0: [lanelet_id_at_goal_state]}

            # Patch the postion of the goal state to match the whole lanelet
            # TODO: This was the behaviour of the original code. Is this the correct behaviour?
            lanelet_at_goal_state = lanelet_network.find_lanelet_by_id(lanelet_id_at_goal_state)
            goal_state.position = lanelet_at_goal_state.polygon

    goal_region = GoalRegion([goal_state], goal_region_lanelet_mapping)
    planning_problem_id = ego_vehicle.obstacle_id
    planning_problem = PlanningProblem(planning_problem_id, initial_state, goal_region)

    return planning_problem


def create_planning_problem_set_and_solution_for_ego_vehicle(
    scenario: Scenario,
    ego_vehicle: DynamicObstacle,
    scenario_time_steps: int,
    planning_problem_with_lanelet: bool = True,
) -> Tuple[PlanningProblemSet, PlanningProblemSolution]:
    """
    Create a new planning problem set and solution for the trajectory of the :param:`ego_vehicle`. The initial and final state will become the start and goal state of the planning problem, while the trajectory will be used as the solution trajectory.

    :param scenario: Scenario used to match the trajectory to the lanelet network.
    :param ego_vehicle: The ego vehicle with a trajectory that will form the basis for the planning problem and solution.
    :param scenario_time_steps: The wanted length of the ego scenario. This will be used to set the planning problem time interval.
    :param planning_problem_with_lanelet: Whether the goal region should also contain references to the final lanelet.

    :returns: The planning problem set and its associated solution
    """
    planning_problem_time_interval = Interval(0, scenario_time_steps)
    planning_problem = create_planning_problem_for_ego_vehicle(
        scenario.lanelet_network,
        ego_vehicle,
        planning_problem_time_interval,
        planning_problem_with_lanelet,
    )
    planning_problem_set = PlanningProblemSet([planning_problem])
    planning_problem_solution = create_planning_problem_solution_for_ego_vehicle(
        ego_vehicle, planning_problem
    )
    # The planning problem solution is not wrapped in its container object like the planning problem is wrapped in a planning problem set,
    # because the solution wrapper object requires a reference to the benchmark ID.
    # This benchmark ID might change throughout the different steps, so it is not a good idea
    # to wrap the planning problem solution here already, because we do not have a way to bind those two reliable together (we could just use the same object for both, but who says no-one will just copy the scenario id somewhere?).
    return planning_problem_set, planning_problem_solution


def create_scenario_for_ego_vehicle_maneuver(
    scenario: Scenario,
    scenario_config: ScenarioFactoryConfig,
    ego_vehicle_maneuver: EgoVehicleManeuver,
) -> Scenario:
    """
    Create a new scenario that is centered around the ego vehicle from the :param:`ego_vehicle_maneuver` and starts at the beginning of the :param:`ego_vehicle_maneuver`. The ego vehicle will not be included in the final scenario.

    :param scenario: The base scenario with the lanelet network and all other obstacles (can include the ego vehicle)
    :param scenario_config: Scenario factory configuration used to paremterize the scenario creation
    :param ego_vehicle_maneuver: The maneuver, the resulting scenario will be centered around

    :returns: A new scenario with the same metadata and lanelet network as the input scenario but with obstacles that are aligned to the start of the ego vehicle maneuver
    """
    relevant_obstacles = _select_obstacles_in_sensor_range_of_ego_vehicle(
        scenario.dynamic_obstacles, ego_vehicle_maneuver.ego_vehicle, scenario_config.sensor_range
    )
    new_obstacles = []
    for obstacle in relevant_obstacles:
        # Obstacles must have a trajectory that starts at least at the same time as the ego vehicle maneuver
        if obstacle.initial_state.time_step > ego_vehicle_maneuver.start_time:
            continue

        new_obstacle = crop_dynamic_obstacle_to_time_frame(
            obstacle,
            ego_vehicle_maneuver.start_time,
            ego_vehicle_maneuver.start_time + scenario_config.cr_scenario_time_steps,
        )
        if new_obstacle is not None:
            new_obstacles.append(new_obstacle)

    new_scenario = copy_scenario(
        scenario,
        copy_dynamic_obstacles=False,
        copy_static_obstacles=False,
        copy_environment_obstacles=False,
        copy_phantom_obstacles=False,
    )
    new_scenario.add_objects(new_obstacles)

    # Make sure that the scenario starts at time step 0, and all obstacles and traffic lights
    # are also aligned to the new zero point.
    align_scenario_to_time_step(new_scenario, ego_vehicle_maneuver.start_time)

    return new_scenario


def delete_colliding_obstacles_from_scenario(scenario: Scenario, all: bool = True) -> Set[int]:
    """
    Delete dynamic obstacles from the scenario that are involved in a collision.

    :param scenario: The scenario from which the obstacle shall be delted
    :param all: Whether all objects involved in a collision should be deleted or only one

    :returns: The ID set of dynamic obstacles that were removed
    """
    ids = get_colliding_dynamic_obstacles_in_scenario(scenario, get_all=all)
    for id_ in ids:
        obstacle = scenario.obstacle_by_id(id_)
        assert (
            obstacle is not None
        ), f"Found a collision for dynamic obstacle {id_}, but this dynamic obstacle is not part of the scenario."
        scenario.remove_obstacle(obstacle)
    return ids


def generate_scenario_with_planning_problem_set_and_solution_for_ego_vehicle_maneuver(
    commonroad_scenario: Scenario,
    ego_vehicle_maneuver: EgoVehicleManeuver,
    scenario_config: ScenarioFactoryConfig,
) -> Tuple[Scenario, PlanningProblemSet, PlanningProblemSolution]:
    """
    Extract all interesting ego vehicle maneuvers from a simulated scenario and create new scenarios and planning problems centered around each ego vehicle maneuver.
    """
    _LOGGER.debug(
        "Creating scenario, planning problem and solution for ego vehicle %s in scenario %s",
        ego_vehicle_maneuver.ego_vehicle.obstacle_id,
        commonroad_scenario.scenario_id,
    )

    ego_scenario = create_scenario_for_ego_vehicle_maneuver(
        commonroad_scenario, scenario_config, ego_vehicle_maneuver
    )

    # Make sure that the ego vehicle is also aligned to the start of the new scenario and not to the old scenario.
    # This is important, because the planning problem will be created from the trajectories start and end state.
    cropped_ego_vehicle = crop_dynamic_obstacle_to_time_frame(
        ego_vehicle_maneuver.ego_vehicle,
        min_time_step=ego_vehicle_maneuver.start_time,
        max_time_step=ego_vehicle_maneuver.start_time + scenario_config.cr_scenario_time_steps,
    )
    if cropped_ego_vehicle is None:
        raise RuntimeError(
            f"Tried to align ego vehicle {ego_vehicle_maneuver.ego_vehicle} to the start of its scenario, but somehow it does not have a state at its maneuver start. This is a bug."
        )
    align_dynamic_obstacle_to_time_step(cropped_ego_vehicle, ego_vehicle_maneuver.start_time)

    ego_scenario.scenario_id.prediction_id = ego_vehicle_maneuver.ego_vehicle.obstacle_id

    planning_problem_set, planning_problem_solution = (
        create_planning_problem_set_and_solution_for_ego_vehicle(
            ego_scenario,
            cropped_ego_vehicle,
            scenario_config.cr_scenario_time_steps,
            scenario_config.planning_pro_with_lanelet,
        )
    )
    return ego_scenario, planning_problem_set, planning_problem_solution
