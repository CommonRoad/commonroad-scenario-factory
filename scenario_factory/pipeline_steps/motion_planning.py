import commonroad_route_planner.fast_api.fast_api as route_planner_fapi
from commonroad.common.solution import (
    CostFunction,
    PlanningProblemSolution,
    Solution,
    VehicleModel,
    VehicleType,
)
from commonroad.planning.planner_interface import TrajectoryPlannerInterface
from commonroad.planning.planning_problem import PlanningProblemSet

from scenario_factory.pipeline import PipelineContext, pipeline_map
from scenario_factory.scenario_container import ScenarioContainer


@pipeline_map()
def pipeline_solve_planning_problem_with_motion_planner(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    motion_planner: TrajectoryPlannerInterface,
) -> ScenarioContainer:
    """
    Solve the planning problems attached to the scenario container with the motion planner from `args`.

    :param args: Step arguments with the motion planner that should be used to solve the planning problem sets.
    :param ctx: The context of the pipeline execution.
    :param scenario_container: The scenario container with a planning problem set attachment

    :returns: The input scenario container with the solution for the planning problem sets.
    """
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            f"Cannot solve planning problem with motion planner for scenario {scenario_container.scenario.scenario_id}: No `PlanningProblemSet` attachment!"
        )

    planning_problem_solutions = []
    for planning_problem_id, planning_problem in planning_problem_set.planning_problem_dict.items():
        reference_path = (
            route_planner_fapi.generate_reference_path_from_lanelet_network_and_planning_problem(
                scenario_container.scenario.lanelet_network, planning_problem
            )
        )

        trajectory = motion_planner.plan(
            scenario_container.scenario, planning_problem, ref_path=reference_path.reference_path
        )
        planning_problem_solution = PlanningProblemSolution(
            planning_problem_id=planning_problem_id,
            # TODO: Should those values be configurable? Can those values be determined automatically?
            vehicle_model=VehicleModel.KS,
            vehicle_type=VehicleType.FORD_ESCORT,
            cost_function=CostFunction.SA1,
            trajectory=trajectory,
        )
        planning_problem_solutions.append(planning_problem_solution)

    solution = Solution(scenario_container.scenario.scenario_id, planning_problem_solutions)

    return scenario_container.with_attachments(solution=solution)
