import numpy as np
import pytest
from commonroad.common.solution import (
    CostFunction,
    PlanningProblemSolution,
    Solution,
    VehicleModel,
    VehicleType,
)
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario, ScenarioID
from commonroad.scenario.state import PMState

from scenario_factory.builder.planning_problem_builder import (
    PlanningProblemSetBuilder,
)
from scenario_factory.builder.scenario_builder import ScenarioBuilder
from scenario_factory.builder.trajectory_builder import TrajectoryBuilder
from scenario_factory.pipeline.pipeline_context import PipelineContext
from scenario_factory.pipeline_steps import pipeline_insert_ego_vehicle_solutions_into_scenario
from scenario_factory.pipeline_steps.utils import (
    pipeline_extract_ego_vehicle_solutions_from_scenario,
)
from scenario_factory.scenario_container import ScenarioContainer


class TestPipelineInsertEgoVehicleSolutionsIntoScenario:
    def test_fails_if_no_solution_is_attached(self):
        planning_problem_set = PlanningProblemSet()
        scenario = Scenario(dt=0.1)
        scenario_container = ScenarioContainer(scenario, planning_problem_set=planning_problem_set)
        pipeline_context = PipelineContext()

        with pytest.raises(ValueError):
            pipeline_insert_ego_vehicle_solutions_into_scenario(
                pipeline_context, scenario_container
            )

    def test_fails_if_no_planning_problem_set_is_attached(self):
        solution = Solution(ScenarioID(), [])
        scenario = Scenario(dt=0.1)
        scenario_container = ScenarioContainer(scenario, solution=solution)
        pipeline_context = PipelineContext()

        with pytest.raises(ValueError):
            pipeline_insert_ego_vehicle_solutions_into_scenario(
                pipeline_context, scenario_container
            )

    def test_correctly_inserts_ego_vehicle_solution(self):
        trajectory = (
            TrajectoryBuilder()
            .start(PMState(time_step=0, position=np.array([0.0, 0.0])))
            .end(PMState(time_step=100, position=np.array([-10.0, 10.0])))
            .build()
        )
        planning_problem_set_builder = PlanningProblemSetBuilder()
        planning_problem = (
            planning_problem_set_builder.create_planning_problem()
            .from_trajectory(trajectory)
            .build()
        )
        planning_problem_id = planning_problem.planning_problem_id
        planning_problem_set = planning_problem_set_builder.build()
        planning_problem_solution = PlanningProblemSolution(
            planning_problem_id,
            VehicleModel.PM,
            VehicleType.FORD_ESCORT,
            CostFunction.JB1,
            trajectory,
        )
        solution = Solution(ScenarioID(), [planning_problem_solution])

        scenario = Scenario(dt=0.1)
        scenario_container = ScenarioContainer(
            scenario, solution=solution, planning_problem_set=planning_problem_set
        )
        pipeline_context = PipelineContext()
        new_scenario_container = pipeline_insert_ego_vehicle_solutions_into_scenario(
            pipeline_context, scenario_container
        )

        obstacle = new_scenario_container.scenario.obstacle_by_id(planning_problem_id)
        assert obstacle is not None
        assert obstacle.obstacle_id == planning_problem_id


class TestPipelineExtractEgoVehicleSolutionsFromScenario:
    def test_fails_if_no_planning_problem_set_is_attached(self):
        solution = Solution(ScenarioID(), [])
        scenario = Scenario(dt=0.1)
        scenario_container = ScenarioContainer(scenario, solution=solution)
        pipeline_context = PipelineContext()

        with pytest.raises(ValueError):
            pipeline_extract_ego_vehicle_solutions_from_scenario(
                pipeline_context, scenario_container
            )

    def test_correctly_extracts_ego_vehicle_solution_from_scenario(self):
        trajectory = (
            TrajectoryBuilder()
            .start(PMState(time_step=0, position=np.array([0.0, 0.0])))
            .end(PMState(time_step=100, position=np.array([-10.0, 10.0])))
            .build()
        )
        scenario_builder = ScenarioBuilder()
        ego_vehicle = scenario_builder.create_dynamic_obstacle().set_trajectory(trajectory).build()

        planning_problem_set_builder = PlanningProblemSetBuilder()
        planning_problem = (
            planning_problem_set_builder.create_planning_problem(ego_vehicle.obstacle_id)
            .from_trajectory(trajectory)
            .build()
        )
        planning_problem_set = planning_problem_set_builder.build()

        scenario = scenario_builder.build()
        scenario_container = ScenarioContainer(scenario, planning_problem_set=planning_problem_set)

        pipeline_context = PipelineContext()
        new_scenario_container: ScenarioContainer = (
            pipeline_extract_ego_vehicle_solutions_from_scenario(
                pipeline_context, scenario_container
            )
        )

        solution = new_scenario_container.get_attachment(Solution)
        assert solution is not None
        assert planning_problem.planning_problem_id in solution.planning_problem_ids

        assert new_scenario_container.scenario.obstacle_by_id(ego_vehicle.obstacle_id) is None
