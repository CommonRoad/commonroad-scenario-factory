import math
from typing import Optional, Sequence, Type

import numpy as np
from commonroad.common.solution import (
    CostFunction,
    PlanningProblemSolution,
    VehicleModel,
    VehicleType,
    vehicle_parameters,
)
from commonroad.geometry.shape import Rectangle
from commonroad.planning.planning_problem import PlanningProblem
from commonroad.prediction.prediction import TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.state import CustomState, InitialState, KSState, State, TraceState
from commonroad.scenario.trajectory import Trajectory

from scenario_factory.utils.crop import crop_trajectory_to_time_frame
from scenario_factory.utils.types import (
    convert_state_to_state,
    convert_state_to_state_type,
    is_state_with_position,
)


def get_full_state_list_of_obstacle(
    dynamic_obstacle: DynamicObstacle, target_state_type: Optional[Type[State]] = None
) -> Sequence[TraceState]:
    """
    Get the state list of the :param:`dynamic_obstacle` including its initial state.
    Will harmonize all states to the same state type, which can be controlled through :param:`target_state_type`.

    :param dynamic_obstacle: The obstacle from which the states should be extracted
    :param target_state_type: Provide an optional state type, to which all resulting states should be converted

    :returns: The full state list of the obstacle where all states have the same state type. This does however not guarantee that all states also have the same attributes, if `CustomState`s are used. See `convert_state_to_state` for more information.
    """
    if target_state_type == CustomState:
        raise ValueError(
            "Cannot convert to state type 'CustomState', because the needed attributes cannot be determined."
        )

    state_list = [dynamic_obstacle.initial_state]
    if isinstance(dynamic_obstacle.prediction, TrajectoryPrediction):
        state_list += dynamic_obstacle.prediction.trajectory.state_list

    if target_state_type is None:
        # Use the last state from the state_list as the reference state,
        # because for all cases this indicates the correct state type:
        # * If state_list only contains the initial state, it is this state
        #    and this function keeps the state as InitialState
        # * If state_list also contains the trajectory prediction,
        #    the reference state is the last state of this trajectory,
        #    and so the initial state will be converted to the same state type
        #    as all other states in the trajectory.
        reference_state = state_list[-1]
        if isinstance(reference_state, CustomState):
            # If the reference state is a custom state, it needs special treatment,
            # because custom states do not have a pre-definied list of attributes
            # that can be used in the conversion.
            # Instead the conversion needs to consider the reference state instance.
            return [convert_state_to_state(state, reference_state) for state in state_list]
        else:
            target_state_type = type(reference_state)

    # Harmonizes the state types: If the caller wants to construct a trajectory
    # from this state list, all states need to have the same attributes aka. the same state type.
    return [convert_state_to_state_type(state, target_state_type) for state in state_list]


def _create_trajectory_for_planning_problem_solution(
    ego_vehicle: DynamicObstacle, target_state_type: Type[State]
) -> Trajectory:
    """
    Create a trajectory of the :param:`ego_vehicle`, that can be used in a planning problem solution.
    """
    state_list = get_full_state_list_of_obstacle(ego_vehicle, target_state_type)

    trajectory = Trajectory(
        initial_time_step=state_list[0].time_step,
        state_list=state_list,
    )
    return trajectory


def create_planning_problem_solution_for_ego_vehicle(
    ego_vehicle: DynamicObstacle, planning_problem: PlanningProblem
) -> PlanningProblemSolution:
    """
    Create a planning problem solution for the :param:`planning_problem` with the trajectory of the :param:`ego_vehicle`. The solution always has the KS vehicle model.
    """
    # TODO: Enable different solution vehicle models, instead of only KS.
    # It would be better, to select the vehicle model based on the trajectory state types.
    # Currently, this is not possible easily because their are some discrepencies between
    # the states used in trajectories and the state types for solutions.
    # See https://gitlab.lrz.de/cps/commonroad/commonroad-io/-/issues/131 for more infos.
    trajectory = _create_trajectory_for_planning_problem_solution(
        ego_vehicle, target_state_type=KSState
    )
    planning_problem_solution = PlanningProblemSolution(
        planning_problem_id=planning_problem.planning_problem_id,
        vehicle_model=VehicleModel.KS,
        vehicle_type=VehicleType.FORD_ESCORT,
        cost_function=CostFunction.TR1,
        trajectory=trajectory,
    )
    return planning_problem_solution


def create_dynamic_obstacle_from_planning_problem_solution(
    planning_problem_solution: PlanningProblemSolution,
) -> DynamicObstacle:
    """
    Create new `DynamicObstacle` object which follows the solution trajectory in the `PlanningProblemSolution`.

    This method is similar to `Solution.create_dynamic_obstacle`, but it can handle states which only contain a subset of attributes of an `InitialState`.

    :param planning_problem_solution: The planning problem solution for which the dynamic obstacle should be created.
    :returns: A new `DynamicObstacle` object with the planning problem id from the solution as its obstacle id.
    """
    obstacle_shape = Rectangle(
        length=vehicle_parameters[planning_problem_solution.vehicle_type].l,
        width=vehicle_parameters[planning_problem_solution.vehicle_type].w,
    )
    trajectory = crop_trajectory_to_time_frame(
        planning_problem_solution.trajectory,
        planning_problem_solution.trajectory.initial_time_step + 1,
    )
    if trajectory is None:
        # This can happen if the trajectory only contains one state...
        # In this case we error out, although it would be possible to construct a dynamic obstacle without a trajectory prediction.
        # Usually, this is not intended, therefore this case is considered an error.
        raise ValueError(
            f"Cannot create dynamic obstacle from planning probolem solution {planning_problem_solution.planning_problem_id}: The solution trajectory is not long enough!"
        )
    prediction = TrajectoryPrediction(trajectory, obstacle_shape)
    first_state_in_trajectory = planning_problem_solution.trajectory.state_list[0]
    initial_state = convert_state_to_state_type(first_state_in_trajectory, InitialState)
    return DynamicObstacle(
        obstacle_id=planning_problem_solution.planning_problem_id,
        obstacle_type=ObstacleType.CAR,
        obstacle_shape=obstacle_shape,
        initial_state=initial_state,
        prediction=prediction,
    )


def calculate_driven_distance_of_dynamic_obstacle(dynamic_obstacle: DynamicObstacle) -> float:
    """
    Calculates the total distance traveled by a dynamic obstacle over time.

    :param dynamic_obstacle: The dynamic obstacle for which the traveled distance is calculated.
    :return: The total distance traveled by the dynamic obstacle.
    """
    dist = 0.0
    time_step = dynamic_obstacle.initial_state.time_step + 1
    prev_state = dynamic_obstacle.initial_state
    state = dynamic_obstacle.state_at_time(time_step)
    while state is not None:
        dist += math.dist(prev_state.position, state.position)

        time_step += 1
        prev_state = state
        state = dynamic_obstacle.state_at_time(time_step)

    return dist


def calculate_deviation_between_states(state1: TraceState, state2: TraceState) -> float:
    """
    Calculates the deviation in the positions between `state1` and `state2`.
    """
    if not is_state_with_position(state1):
        raise ValueError()

    if not is_state_with_position(state2):
        raise ValueError()

    return float(np.linalg.norm(state1.position - state2.position))
