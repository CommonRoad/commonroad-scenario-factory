from collections import defaultdict
from itertools import groupby

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
    pipeline_assign_unique_incremental_scenario_ids,
    pipeline_extract_ego_vehicle_solutions_from_scenario,
    pipeline_remove_parked_dynamic_obstacles,
)
from scenario_factory.scenario_container import ScenarioContainer


class TestPipelineInsertEgoVehicleSolutionsIntoScenario:
    def test_fails_if_no_solution_is_attached(self):
        planning_problem_set = PlanningProblemSet()
        scenario = Scenario(dt=0.1)
        scenario_container = ScenarioContainer(scenario, planning_problem_set=planning_problem_set)
        pipeline_context = PipelineContext()

        with pytest.raises(ValueError):
            pipeline_insert_ego_vehicle_solutions_into_scenario()(
                pipeline_context, scenario_container
            )

    def test_fails_if_no_planning_problem_set_is_attached(self):
        solution = Solution(ScenarioID(), [])
        scenario = Scenario(dt=0.1)
        scenario_container = ScenarioContainer(scenario, solution=solution)
        pipeline_context = PipelineContext()

        with pytest.raises(ValueError):
            pipeline_insert_ego_vehicle_solutions_into_scenario()(
                pipeline_context, scenario_container
            )

    def test_correctly_inserts_ego_vehicle_solution(self):
        trajectory = (
            TrajectoryBuilder()
            .start_state(PMState(time_step=0, position=np.array([0.0, 0.0])))
            .end_state(PMState(time_step=100, position=np.array([-10.0, 10.0])))
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
        new_scenario_container = pipeline_insert_ego_vehicle_solutions_into_scenario()(
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
            pipeline_extract_ego_vehicle_solutions_from_scenario()(
                pipeline_context, scenario_container
            )

    def test_correctly_extracts_ego_vehicle_solution_from_scenario(self):
        trajectory = (
            TrajectoryBuilder()
            .start_state(PMState(time_step=0, position=np.array([0.0, 0.0])))
            .end_state(PMState(time_step=100, position=np.array([-10.0, 10.0])))
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
            pipeline_extract_ego_vehicle_solutions_from_scenario()(
                pipeline_context, scenario_container
            )
        )

        solution = new_scenario_container.get_attachment(Solution)
        assert solution is not None
        assert planning_problem.planning_problem_id in solution.planning_problem_ids

        assert new_scenario_container.scenario.obstacle_by_id(ego_vehicle.obstacle_id) is None


class TestPipelineRemoveParkedDynamicObstacles:
    def test_only_removes_parked_and_keeps_driving_vehicles(self):
        scenario_builder = ScenarioBuilder()
        dynamic_obstacle_builder = scenario_builder.create_dynamic_obstacle()
        dynamic_obstacle_builder.create_trajectory().start_state(
            PMState(0, position=np.array([100.0, 0.0]))
        ).end_state(PMState(100, np.array([100.0, 100.0])))
        driving_obstacle = dynamic_obstacle_builder.build()

        dynamic_obstacle_builder = scenario_builder.create_dynamic_obstacle()
        dynamic_obstacle_builder.create_trajectory().start_state(
            PMState(0, position=np.array([0.0, 0.0]))
        ).end_state(PMState(100, np.array([0.0, 0.0])))
        parked_obstacle = dynamic_obstacle_builder.build()

        scenario = scenario_builder.build()
        scenario_container = ScenarioContainer(scenario)
        ctx = PipelineContext()
        result_scenario_container = pipeline_remove_parked_dynamic_obstacles()(
            ctx, scenario_container
        )
        assert (
            result_scenario_container.scenario.obstacle_by_id(driving_obstacle.obstacle_id)
            is not None
        )
        assert (
            result_scenario_container.scenario.obstacle_by_id(parked_obstacle.obstacle_id) is None
        )


class TestPipelineAssignUniqueIncrementalScenarioIDs:
    @pytest.mark.parametrize(
        "scenario_ids",
        [
            [],
            ["DEU_Test-78_8_I-58"],
            [
                "DEU_Test-5_1_T-2000",
                "DEU_Test-5_1_T-8601",
                "DEU_Test-5_4_T-2000",
                "DEU_Test-5_4_T-2001",
                "DEU_Test-5_4_T-8601",
                "FRA_Foo-1_1_T-30",
            ],
            # Only map name is different
            ["DEU_Foo-3_7_T-90", "DEU_Bar-3_7_T-90"],
            # Different country IDs, all other same
            ["DEU_Foo-3_7_T-90", "USA_Foo-3_7_T-90", "FRA_Foo-3_7_T-90"],
            # Test for incremental, unique map ids
            [
                "USA_Tyler-3_1_T-63",
                "USA_Tyler-3_1_T-9",
                "USA_Tyler-4_1_T-35",
                "USA_Tyler-4_1_T-25",
                "USA_Tyler-5_1_T-35",
                "USA_Tyler-6_1_T-25",
                "USA_Tyler-6_2_T-25",
                "USA_Tyler-6_2_T-89",
            ],
        ],
    )
    def test_assigns_unique_and_incremental_ids(self, scenario_ids):
        scenarios = [
            Scenario(
                dt=0.1,
                scenario_id=ScenarioID.from_benchmark_id(scenario_id, scenario_version="2020a"),
            )
            for scenario_id in scenario_ids
        ]
        scenario_containers = [ScenarioContainer(scenario) for scenario in scenarios]

        ctx = PipelineContext()
        new_scenario_containers = pipeline_assign_unique_incremental_scenario_ids()(
            ctx, scenario_containers
        )

        new_scenario_ids = [
            scenario_container.scenario.scenario_id
            for scenario_container in new_scenario_containers
        ]

        # The same number of unique scenario ids in the input as in the output
        assert len(set(scenario_ids)) == len(set(new_scenario_ids))

        # no duplicates in result
        assert len(new_scenario_ids) == len(set(new_scenario_ids))

        maps = defaultdict(list)
        for scenario_id in new_scenario_ids:
            maps[(scenario_id.country_id, scenario_id.map_name)].append(scenario_id)

        for _, map_scenario_ids in maps.items():
            sorted_map_ids = list(
                {
                    scenario_id.map_id
                    for scenario_id in sorted(
                        map_scenario_ids, key=lambda scenario_id: scenario_id.map_id
                    )
                }
            )
            assert all(
                x + 1 == y for x, y in zip(sorted_map_ids, sorted_map_ids[1:])
            ), f"Scenario map IDs are not incrementing for scenario ids {[str(sid) for sid in map_scenario_ids]}: map IDs are {sorted_map_ids}"

            for _, foo in groupby(map_scenario_ids, key=lambda scenario_id: scenario_id.map_id):
                sorted_config_ids = list(
                    {
                        scenario_id.configuration_id
                        for scenario_id in sorted(
                            foo, key=lambda scenario_id: scenario_id.configuration_id
                        )
                    }
                )
                assert all(
                    x + 1 == y for x, y in zip(sorted_config_ids, sorted_config_ids[1:])
                ), f"Scenario configuration IDs are not incrementing for scenario ids {[str(sid) for sid in foo]}: configuration IDs are {sorted_config_ids}"

                for _, bar in groupby(foo, key=lambda scenario_id: scenario_id.configuration_id):
                    sorted_pred_ids = list(
                        {
                            scenario_id.prediction_id
                            for scenario_id in sorted(
                                foo, key=lambda scenario_id: scenario_id.prediction_id
                            )
                        }
                    )
                    assert all(
                        x + 1 == y for x, y in zip(sorted_pred_ids, sorted_pred_ids[1:])
                    ), f"Scenario prediction IDs are not incrementing for scenario ids {[str(sid) for sid in bar]}: prediction IDs are {sorted_pred_ids}"

        # TODO: check attachments
