from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario, Tag

import scenario_factory.pipeline_steps.utils
from scenario_factory.builder import (
    PlanningProblemSetBuilder,
    ScenarioBuilder,
)
from scenario_factory.pipeline import PipelineContext
from scenario_factory.pipeline_steps import pipeline_assign_tags_to_scenario
from scenario_factory.scenario_container import ScenarioContainer
from scenario_factory.tags import (
    find_applicable_tags_for_planning_problem_set,
    find_applicable_tags_for_scenario,
)


class TestAssignApplicableTags:
    def test_does_not_assign_tags_to_empty_scenario(self):
        scenario = Scenario(dt=0.1)
        tags = find_applicable_tags_for_scenario(scenario)
        assert len(tags) == 0

    def test_correctly_assigns_single_lane_tag(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(10.0, 0.0))
        scenario = scenario_builder.build()

        tags = find_applicable_tags_for_scenario(scenario)
        assert len(tags) == 1
        assert Tag.SINGLE_LANE in tags

    def test_correctly_assigns_multi_lane_tag_for_two_lanes(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(10.0, 0.0))
        lanelet_network_builder.add_adjacent_lanelet(lanelet1)
        scenario = scenario_builder.build()
        print(scenario.lanelet_network.lanelets)

        tags = find_applicable_tags_for_scenario(scenario)
        assert len(tags) == 1
        assert Tag.MULTI_LANE in tags

    def test_correctly_assigns_multi_lane_tag_for_multiple_lanes(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(10.0, 0.0))
        lanelet2 = lanelet_network_builder.add_adjacent_lanelet(lanelet1)
        lanelet_network_builder.add_adjacent_lanelet(lanelet1, side="left")
        lanelet_network_builder.add_adjacent_lanelet(lanelet2)
        scenario = scenario_builder.build()

        tags = find_applicable_tags_for_scenario(scenario)
        assert len(tags) == 1
        assert Tag.MULTI_LANE in tags


class TestFindApplicableTagsForPlanningProblemSet:
    def test_assigns_no_tags_for_empty_planning_problem_set(self):
        scenario = Scenario(dt=0.1)
        planning_problem_set = PlanningProblemSet([])

        tags = find_applicable_tags_for_planning_problem_set(scenario, planning_problem_set)
        assert len(tags) == 0

    def test_correctly_assigns_turn_left_tag(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 10.0))
        lanelet2 = lanelet_network_builder.add_lanelet(start=(-5.0, 20.0), end=(-15.0, 20.0))
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet2)
        (
            lanelet_network_builder.create_intersection()
            .create_incoming()
            .add_incoming_lanelet(lanelet1)
            .connect_left(lanelet2)
        )
        scenario = scenario_builder.build()
        planning_problem_set_builder = PlanningProblemSetBuilder()
        planning_problem_set_builder.create_planning_problem().set_start(lanelet1).add_goal(
            lanelet2
        )
        planning_problem_set = planning_problem_set_builder.build()

        tags = find_applicable_tags_for_planning_problem_set(scenario, planning_problem_set)
        assert len(tags) == 1
        assert Tag.TURN_LEFT in tags

    def test_correctly_assigns_turn_right_tag(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 10.0))
        lanelet2 = lanelet_network_builder.add_lanelet(start=(5.0, 20.0), end=(15.0, 20.0))
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet2)
        (
            lanelet_network_builder.create_intersection()
            .create_incoming()
            .add_incoming_lanelet(lanelet1)
            .connect_right(lanelet2)
        )
        scenario = scenario_builder.build()
        planning_problem_set_builder = PlanningProblemSetBuilder()
        planning_problem_set_builder.create_planning_problem().set_start(lanelet1).add_goal(
            lanelet2
        )
        planning_problem_set = planning_problem_set_builder.build()

        tags = find_applicable_tags_for_planning_problem_set(scenario, planning_problem_set)
        assert len(tags) == 1
        assert Tag.TURN_RIGHT in tags

    def test_correctly_assigns_turn_right_and_turn_left_tag_for_multiple_planning_problems(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 10.0))
        lanelet2 = lanelet_network_builder.add_lanelet(start=(5.0, 20.0), end=(15.0, 20.0))
        lanelet3 = lanelet_network_builder.add_lanelet(start=(-5.0, 20.0), end=(-15.0, 20.0))
        lanelet4 = lanelet_network_builder.add_lanelet(start=(0.0, 20.0), end=(0.0, 30.0))
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet2)
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet3)
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet1, lanelet4)
        (
            lanelet_network_builder.create_intersection()
            .create_incoming()
            .add_incoming_lanelet(lanelet1)
            .connect_right(lanelet2)
            .connect_straight(lanelet4)
            .connect_left(lanelet3)
        )
        scenario = scenario_builder.build()
        planning_problem_set_builder = PlanningProblemSetBuilder()
        (
            planning_problem_set_builder.create_planning_problem()
            .set_start(lanelet1)
            .add_goal(lanelet2)
        )
        (
            planning_problem_set_builder.create_planning_problem()
            .set_start(lanelet1)
            .add_goal(lanelet3)
        )
        (
            planning_problem_set_builder.create_planning_problem()
            .set_start(lanelet1)
            .add_goal(lanelet4)
        )
        planning_problem_set = planning_problem_set_builder.build()

        tags = find_applicable_tags_for_planning_problem_set(scenario, planning_problem_set)
        assert len(tags) == 2
        assert Tag.TURN_RIGHT in tags
        assert Tag.TURN_LEFT in tags


class TestPipelineAssignTagsToScenario:
    def test_only_includes_static_tags_if_no_planning_problem_set_is_provided(self, mocker):
        mocker.patch(
            "scenario_factory.pipeline_steps.utils.find_applicable_tags_for_scenario",
            return_value={Tag.SIMULATED},
        )
        mocker.patch(
            "scenario_factory.pipeline_steps.utils.find_applicable_tags_for_planning_problem_set",
            return_value={Tag.INTERSTATE, Tag.COMFORT},
        )

        input_scenario_container = ScenarioContainer(Scenario(dt=0.1))
        result_scenario_container: ScenarioContainer = pipeline_assign_tags_to_scenario(
            PipelineContext(), input_scenario_container
        )  # type: ignore

        assert len(result_scenario_container.scenario.tags) == 1
        scenario_factory.pipeline_steps.utils.find_applicable_tags_for_scenario.assert_called_once()
        scenario_factory.pipeline_steps.utils.find_applicable_tags_for_planning_problem_set.assert_not_called()

    def test_also_includes_dyanmic_tags_if_planning_problem_set_is_provided(self, mocker):
        mocker.patch(
            "scenario_factory.pipeline_steps.utils.find_applicable_tags_for_scenario",
            return_value={Tag.CRITICAL},
        )
        mocker.patch(
            "scenario_factory.pipeline_steps.utils.find_applicable_tags_for_planning_problem_set",
            return_value={Tag.INTERSTATE, Tag.COMFORT},
        )

        input_scenario_container = ScenarioContainer(
            Scenario(dt=0.1), planning_problem_set=PlanningProblemSet()
        )
        result_scenario_container: ScenarioContainer = pipeline_assign_tags_to_scenario(
            PipelineContext(), input_scenario_container
        )  # type: ignore

        assert len(result_scenario_container.scenario.tags) == 3
        scenario_factory.pipeline_steps.utils.find_applicable_tags_for_scenario.assert_called_once()
        scenario_factory.pipeline_steps.utils.find_applicable_tags_for_planning_problem_set.assert_called_once()
