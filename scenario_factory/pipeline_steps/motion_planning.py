from dataclasses import dataclass

from commonroad.common.solution import (
    CostFunction,
    PlanningProblemSolution,
    Solution,
    VehicleModel,
    VehicleType,
)
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad_route_planner.route_planner import RoutePlanner
from sumocr.simulation.interactive_simulation import TrajectoryPlannerInterface

from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map_with_args
from scenario_factory.scenario_container import ScenarioContainer


@dataclass
class SolvePlanningProblemWithMotionPlannerArgs(PipelineStepArguments):
    motion_planner: TrajectoryPlannerInterface


@pipeline_map_with_args()
def pipeline_solve_planning_problem_with_motion_planner(
    args: SolvePlanningProblemWithMotionPlannerArgs,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> ScenarioContainer:
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            f"Cannot solve planning problem with motion planner for scenario {scenario_container.scenario.scenario_id}: No `PlanningProblemSet` attachment!"
        )

    planning_problem_solutions = []
    for planning_problem_id, planning_problem in planning_problem_set.planning_problem_dict.items():
        route_planner = RoutePlanner(scenario_container.scenario.lanelet_network, planning_problem)
        route = route_planner.plan_routes().retrieve_first_route()

        trajectory = args.motion_planner.plan(
            scenario_container.scenario, planning_problem, ref_path=route.reference_path
        )
        planning_problem_solution = PlanningProblemSolution(
            planning_problem_id=planning_problem_id,
            vehicle_model=VehicleModel.KS,
            vehicle_type=VehicleType.FORD_ESCORT,
            cost_function=CostFunction.SA1,
            trajectory=trajectory,
        )
        planning_problem_solutions.append(planning_problem_solution)

    solution = Solution(scenario_container.scenario.scenario_id, planning_problem_solutions)

    return scenario_container.with_attachments(solution=solution)
