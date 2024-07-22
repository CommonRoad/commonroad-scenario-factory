__all__ = [
    "generate_ego_scenarios_with_planning_problem_set_from_simulated_scenario",
    "simulate_commonroad_scenario",
    "convert_commonroad_scenario_to_sumo_scenario",
]


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
from commonroad.scenario.state import InitialState, PMState, TraceState
from commonroad.scenario.trajectory import Trajectory
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from sumocr.interface.id_mapper import IdDomain
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.scenario.scenario_wrapper import ScenarioWrapper

from scenario_factory.ego_vehicle_selection import (
    EgoVehicleManeuver,
    select_interesting_ego_vehicle_maneuvers_from_scenario,
)
from scenario_factory.scenario_checker import get_colliding_dynamic_obstacles_in_scenario
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.scenario_types import (
    EgoScenario,
    EgoScenarioWithPlanningProblemSet,
    InteractiveEgoScenario,
    NonInteractiveEgoScenario,
    SimulatedScenario,
    SumoScenario,
)
from scenario_factory.scenario_util import find_most_likely_lanelet_by_state

logger = logging.getLogger(__name__)


def create_non_interactive_scenario(ego_scenario: EgoScenarioWithPlanningProblemSet) -> NonInteractiveEgoScenario:
    """
    Transform an ego scenario to a non-interactive scenario. This function will not modify the original ego scenario.
    """
    new_scenario = copy.copy(ego_scenario.scenario)
    new_scenario.scenario_id = copy.deepcopy(new_scenario.scenario_id)
    new_scenario.scenario_id.obstacle_behavior = "T"

    return NonInteractiveEgoScenario.from_ego_scenario(ego_scenario, ego_scenario.planning_problem_set, new_scenario)


def create_interactive_scenario(ego_scenario: EgoScenarioWithPlanningProblemSet) -> InteractiveEgoScenario:
    """
    Transform an ego scenario to an interactive scenario. This function will not modify the original ego scenario.
    """
    new_scenario = Scenario(dt=ego_scenario.scenario.dt)
    # Deep copy the Id, as it will be modified
    new_scenario.scenario_id = copy.deepcopy(ego_scenario.scenario.scenario_id)
    new_scenario.scenario_id.obstacle_behavior = "I"

    # Only add a reference of the lanelet network to the scenario
    new_scenario.add_objects(ego_scenario.scenario.lanelet_network)

    for original_obstacle in ego_scenario.scenario.dynamic_obstacles:
        new_obstacle = DynamicObstacle(
            original_obstacle.obstacle_id,
            original_obstacle.obstacle_type,
            obstacle_shape=original_obstacle.obstacle_shape,
            initial_state=copy.deepcopy(original_obstacle.initial_state),
        )
        new_scenario.add_objects(new_obstacle)

    return InteractiveEgoScenario.from_ego_scenario(ego_scenario, ego_scenario.planning_problem_set, new_scenario)


def convert_commonroad_scenario_to_sumo_scenario(
    commonroad_scenario: Scenario, output_folder: Path, sumo_config: SumoConfig
) -> SumoScenario:
    cr2sumo = CR2SumoMapConverter(commonroad_scenario, sumo_config)
    conversion_possible = cr2sumo.create_sumo_files(str(output_folder))

    if not conversion_possible:
        raise RuntimeError(f"Failed to convert CommonRoad scenario {commonroad_scenario.scenario_id} to SUMO")

    sumo_scenario = SumoScenario(commonroad_scenario, Path(cr2sumo.sumo_cfg_file))
    return sumo_scenario


def simulate_commonroad_scenario(sumo_scenario: SumoScenario, sumo_config: SumoConfig) -> SimulatedScenario:
    scenario_wrapper = ScenarioWrapper()
    scenario_wrapper.sumo_cfg_file = str(sumo_scenario.sumo_cfg_file)
    scenario_wrapper.initial_scenario = copy.deepcopy(sumo_scenario.scenario)

    sumo_sim = SumoSimulation()
    sumo_sim.initialize(sumo_config, scenario_wrapper)

    for _ in range(sumo_config.simulation_steps):
        sumo_sim.simulate_step()
    sumo_sim.simulate_step()

    sumo_sim.stop()

    scenario = sumo_sim.commonroad_scenarios_all_time_steps()

    # This is ugly as we have to directly access the internals of the SUMO simulation. But for interactive scenarios, we need the internal ID mapping, as we need to mark the ego vehicle in the SUMO files. So there is currently no way around this...
    id_mapping = dict()
    for dynamic_obstacle in scenario.dynamic_obstacles:
        sumo_id = sumo_sim._id_mapper.cr2sumo(dynamic_obstacle.obstacle_id, IdDomain.VEHICLE)
        if sumo_id is None:
            raise RuntimeError(
                f"Tried to retrive the SUMO ID of obstacle {dynamic_obstacle.obstacle_id}, but no ID could be found. This is a bug."
            )
        id_mapping[dynamic_obstacle.obstacle_id] = sumo_id

    return SimulatedScenario(scenario, sumo_scenario.sumo_cfg_file, sumo_config, id_mapping)


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
    # Use a dictionary to improve looks up speed
    relevant_obstacle_map = {ego_vehicle.obstacle_id: ego_vehicle}

    assert isinstance(ego_vehicle.prediction, TrajectoryPrediction)

    for ego_vehicle_state in ego_vehicle.prediction.trajectory.state_list:
        # Copy the position, because otherwise this would modify the resulting trajectory of the ego vehicle
        proj_pos = copy.deepcopy(ego_vehicle_state.position)
        proj_pos[0] += math.cos(ego_vehicle_state.orientation) + 2.0 * ego_vehicle_state.velocity
        proj_pos[1] += math.sin(ego_vehicle_state.orientation) + 2.0 * ego_vehicle_state.velocity
        for obstacle in obstacles:
            if obstacle.obstacle_id in relevant_obstacle_map:
                continue

            obstacle_state = obstacle.state_at_time(ego_vehicle_state.time_step)
            if obstacle_state is None:
                continue

            if np.less_equal(np.abs(obstacle_state.position[0] - proj_pos[0]), sensor_range) and np.less_equal(
                np.abs(obstacle_state.position[1] - proj_pos[1]), sensor_range
            ):
                relevant_obstacle_map[obstacle.obstacle_id] = obstacle

    return list(relevant_obstacle_map.values())


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


def _create_planning_problem_for_ego_vehicle(
    scenario: Scenario,
    ego_vehicle: DynamicObstacle,
    planning_problem_with_lanelet: bool = True,
) -> PlanningProblem:
    """
    Create a new planning problem set for the ego vehicle in the scenario.

    """
    initial_state = _create_planning_problem_initial_state_for_ego_vehicle(ego_vehicle)
    goal_state = _create_planning_problem_goal_state_for_ego_vehicle(ego_vehicle)

    goal_region_lanelet_mapping = None
    if planning_problem_with_lanelet is True:
        # We should create a planning problem goal region, that is associated with the lanelet on which the ego vehicle lands in its goal_state
        lanelet_id_at_goal_state = find_most_likely_lanelet_by_state(
            lanelet_network=scenario.lanelet_network, state=goal_state
        )
        if lanelet_id_at_goal_state is None:
            raise ValueError(
                f"Tried to match ego vehicle {ego_vehicle} to the lanelet in its goal state, but no lanelet could be found for state: {goal_state}"
            )

        # Create the mapping to be used by the GoalRegion construction
        goal_region_lanelet_mapping = {0: [lanelet_id_at_goal_state]}

        # Patch the postion of the goal state to match the whole lanelet
        # TODO: This was the behaviour of the original code. Is this the correct behaviour?
        lanelet_at_goal_state = scenario.lanelet_network.find_lanelet_by_id(lanelet_id_at_goal_state)
        goal_state.position = lanelet_at_goal_state.polygon

    goal_region = GoalRegion([goal_state], goal_region_lanelet_mapping)
    planning_problem_id = ego_vehicle.obstacle_id
    planning_problem = PlanningProblem(planning_problem_id, initial_state, goal_region)

    return planning_problem


def create_planning_problem_set_for_ego_scenario(
    ego_scenario: EgoScenario, planning_problem_with_lanelet: bool = True
) -> PlanningProblemSet:
    planning_problem = _create_planning_problem_for_ego_vehicle(
        ego_scenario.scenario, ego_scenario.ego_vehicle_maneuver.ego_vehicle, planning_problem_with_lanelet
    )
    planning_problem_set = PlanningProblemSet([planning_problem])

    return planning_problem_set


def create_ego_scenario_with_planning_problem_set(
    ego_scenario: EgoScenario, planning_problem_with_lanelet: bool = True
) -> EgoScenarioWithPlanningProblemSet:
    planning_problem_set = create_planning_problem_set_for_ego_scenario(ego_scenario, planning_problem_with_lanelet)

    return EgoScenarioWithPlanningProblemSet.from_ego_scenario(ego_scenario, planning_problem_set)


def create_ego_scenario_for_ego_vehicle_maneuver(
    simulated_scenario: SimulatedScenario,
    scenario_config: ScenarioFactoryConfig,
    ego_vehicle_maneuver: EgoVehicleManeuver,
) -> EgoScenario:
    """
    Create a non-interactive scenario from an Ego Vehicle Maneuver
    """
    scenario = simulated_scenario.scenario

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

    ego_scenario = EgoScenario.from_simulated_scenario(simulated_scenario, ego_vehicle_maneuver, new_scenario)
    return ego_scenario


def delete_colliding_obstacles_from_scenario(scenario: Scenario, all: bool = True) -> Set[int]:
    """
    Delete dynamic obstacles from the scenario that are involved in a collision.

    :param scenario: The scenario from which the
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


def generate_ego_scenarios_with_planning_problem_set_from_simulated_scenario(
    simulated_scenario: SimulatedScenario,
    scenario_config: ScenarioFactoryConfig,
    max_collisions: Optional[int] = None,
    create_noninteractive: bool = True,
    create_interactive: bool = True,
) -> List[EgoScenarioWithPlanningProblemSet]:
    """
    Extract all interesting ego vehicle maneuvers from a simulated scenario and create new scenarios and planning problems centered around each ego vehicle maneuver.
    """
    commonroad_scenario = simulated_scenario.scenario

    num_collisions = len(delete_colliding_obstacles_from_scenario(commonroad_scenario, all=True))
    if max_collisions is not None:
        if num_collisions > max_collisions:
            raise RuntimeError(
                f"Skipping scenario {commonroad_scenario.scenario_id} because it has {num_collisions}, but the maximum allowed number of collisions is {max_collisions}"
            )

    ego_vehicle_maneuvers = select_interesting_ego_vehicle_maneuvers_from_scenario(
        commonroad_scenario,
        criterions=scenario_config.criterions,
        filters=scenario_config.filters,
        scenario_time_steps=scenario_config.cr_scenario_time_steps,
        sensor_range=scenario_config.sensor_range,
    )

    results: List[EgoScenarioWithPlanningProblemSet] = []

    for i, maneuver in enumerate(ego_vehicle_maneuvers):
        ego_scenario = create_ego_scenario_for_ego_vehicle_maneuver(simulated_scenario, scenario_config, maneuver)
        # TODO: this is ugly, and should be fixed in the scenario ID refactor
        ego_scenario.scenario.scenario_id.prediction_id = i + 1

        ego_scenario_with_planning_problem = create_ego_scenario_with_planning_problem_set(
            ego_scenario, scenario_config.planning_pro_with_lanelet
        )
        if create_noninteractive:
            non_interactive_scenario = create_non_interactive_scenario(ego_scenario_with_planning_problem)
            results.append(non_interactive_scenario)

        if create_interactive:
            interactive_scenario = create_interactive_scenario(ego_scenario_with_planning_problem)
            results.append(interactive_scenario)

    return results
