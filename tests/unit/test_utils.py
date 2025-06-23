import copy
from pathlib import Path

import numpy as np
import pytest
from commonroad.common.solution import Solution
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import CustomState, ExtendedPMState, InitialState
from commonroad.scenario.traffic_light import (
    TrafficLight,
    TrafficLightCycle,
    TrafficLightCycleElement,
    TrafficLightState,
)

from scenario_factory.builder import ScenarioBuilder
from scenario_factory.utils import (
    CommonRoadXmlFileType,
    align_state_list_to_time_step,
    align_state_to_time_step,
    align_traffic_light_to_time_step,
    convert_state_to_state,
    copy_scenario,
    determine_xml_file_type,
    get_full_state_list_of_obstacle,
    try_load_xml_file_as_commonroad_scenario,
    try_load_xml_file_as_commonroad_solution,
)
from tests.helpers.obstacle import create_test_obstacle_with_trajectory
from tests.resources.interface import RESOURCES, ResourceType


class TestAlignStateToTimeStep:
    @pytest.mark.parametrize(
        ["state_time_step", "alignment_time_step", "expected_time_step"],
        [(0, 0, 0), (10, 0, 10), (3, 3, 0), (14, 5, 9), (0, 17, 17), (20, 17, 3)],
    )
    def test_correctly_aligns_state_to_time_step(
        self, state_time_step, alignment_time_step, expected_time_step
    ) -> None:
        state = CustomState(time_step=state_time_step)
        align_state_to_time_step(state, alignment_time_step)
        assert state.time_step == expected_time_step


class TestAlignStateListToTimeStep:
    @pytest.mark.parametrize(
        ["state_time_steps", "alignment_time_step", "expected_time_steps"],
        [
            ([10, 11, 12, 13], 0, [10, 11, 12, 13]),
            ([0, 1, 2, 5, 7], 17, [17, 18, 19, 22, 24]),
            ([3, 4, 5, 6, 7, 8], 5, [8, 9, 10, 11, 12, 13]),
        ],
    )
    def test_correctly_aligns_state_list_to_time_step(
        self, state_time_steps, alignment_time_step, expected_time_steps
    ) -> None:
        state_list = [CustomState(time_step=time_step) for time_step in state_time_steps]
        align_state_list_to_time_step(state_list, alignment_time_step)
        print(state_list)
        for i, expected_time_step in enumerate(expected_time_steps):
            assert state_list[i].time_step == expected_time_step


class TestAlignTrafficLightToTimeStep:
    @pytest.mark.parametrize(
        ["cycle", "alignment_time_step", "expected_offset"],
        [
            (
                TrafficLightCycle(
                    time_offset=0,
                    cycle_elements=[
                        TrafficLightCycleElement(TrafficLightState.RED, 30),
                        TrafficLightCycleElement(TrafficLightState.GREEN, 15),
                    ],
                ),
                0,
                0,
            ),
            (
                TrafficLightCycle(
                    time_offset=50,
                    cycle_elements=[
                        TrafficLightCycleElement(TrafficLightState.RED, 60),
                        TrafficLightCycleElement(TrafficLightState.GREEN, 30),
                        TrafficLightCycleElement(TrafficLightState.YELLOW, 15),
                    ],
                ),
                50,
                0,
            ),
            (
                TrafficLightCycle(
                    time_offset=0,
                    cycle_elements=[
                        TrafficLightCycleElement(TrafficLightState.RED, 60),
                        TrafficLightCycleElement(TrafficLightState.GREEN, 30),
                        TrafficLightCycleElement(TrafficLightState.YELLOW, 15),
                    ],
                ),
                50,
                55,
            ),
            (
                TrafficLightCycle(
                    time_offset=150,
                    cycle_elements=[
                        TrafficLightCycleElement(TrafficLightState.RED, 60),
                        TrafficLightCycleElement(TrafficLightState.RED_YELLOW, 15),
                        TrafficLightCycleElement(TrafficLightState.GREEN, 30),
                        TrafficLightCycleElement(TrafficLightState.YELLOW, 15),
                    ],
                ),
                200,
                70,
            ),
            (
                TrafficLightCycle(
                    time_offset=100,
                    cycle_elements=[
                        TrafficLightCycleElement(TrafficLightState.RED, 60),
                        TrafficLightCycleElement(TrafficLightState.RED_YELLOW, 15),
                        TrafficLightCycleElement(TrafficLightState.GREEN, 30),
                        TrafficLightCycleElement(TrafficLightState.YELLOW, 15),
                    ],
                ),
                550,
                30,
            ),
            (
                TrafficLightCycle(
                    time_offset=100,
                    cycle_elements=[
                        TrafficLightCycleElement(TrafficLightState.RED, 60),
                        TrafficLightCycleElement(TrafficLightState.RED_YELLOW, 15),
                        TrafficLightCycleElement(TrafficLightState.GREEN, 30),
                        TrafficLightCycleElement(TrafficLightState.YELLOW, 15),
                    ],
                ),
                50,
                50,
            ),
        ],
    )
    def test_correctly_aligns_already_aligned_traffic_light(
        self, cycle, alignment_time_step, expected_offset
    ):
        traffic_light = TrafficLight(
            traffic_light_id=1,
            position=np.array([0.0, 0.0]),
            traffic_light_cycle=copy.deepcopy(cycle),
        )
        align_traffic_light_to_time_step(traffic_light, alignment_time_step)
        assert traffic_light.traffic_light_cycle is not None
        assert traffic_light.traffic_light_cycle.time_offset == expected_offset

        cycle_length = sum([elem.duration for elem in cycle.cycle_elements])
        for i in range(0, 2 * cycle_length):
            original_state = cycle.get_state_at_time_step(i + alignment_time_step)
            aligned_state = traffic_light.get_state_at_time_step(i)
            assert (
                original_state == aligned_state
            ), f"Original state {original_state} at time step {i + alignment_time_step} does not match aligned state {aligned_state} at time step {i}"


class TestCopyScenario:
    def test_handles_empty_scenario(self):
        scenario_builder = ScenarioBuilder()
        scenario = scenario_builder.build()
        new_scenario = copy_scenario(scenario)
        assert id(new_scenario) != id(scenario)
        # Although the lanelet network should not be copied, a new one will be created
        assert id(new_scenario.lanelet_network) != id(scenario.lanelet_network)
        assert len(new_scenario.lanelet_network.lanelets) == 0
        assert len(new_scenario.dynamic_obstacles) == 0

    def test_copies_lanelet_network(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(10.0, 10.0))

        scenario = scenario_builder.build()
        new_scenario = copy_scenario(scenario, copy_lanelet_network=True)
        assert id(new_scenario) != id(scenario)
        assert id(new_scenario.lanelet_network) != id(scenario.lanelet_network)
        assert len(new_scenario.lanelet_network.lanelets) == 1
        assert len(new_scenario.dynamic_obstacles) == 0


class TestConvertStateToState:
    def test_keeps_same_custom_state_if_states_are_the_same(self):
        state = CustomState(time_step=1, foo="bar")
        new_state = convert_state_to_state(state, state)
        assert "foo" in new_state.used_attributes

    def test_keeps_same_custom_state_if_attributes_match(self):
        state1 = CustomState(time_step=1, foo="bar")
        state2 = CustomState(time_step=4, foo="test")
        new_state = convert_state_to_state(state1, state2)
        assert "foo" in new_state.used_attributes


class TestGetFullStateListOfObstacle:
    def test_returns_only_initial_state_if_obstacle_has_no_prediction(self):
        initial_state = InitialState()
        initial_state.fill_with_defaults()

        obstacle = create_test_obstacle_with_trajectory([initial_state])
        state_list = get_full_state_list_of_obstacle(obstacle)

        assert len(state_list) == 1
        assert isinstance(state_list[0], InitialState)

    def test_harmonizes_all_states_to_same_type_extended_pm(self):
        obstacle = create_test_obstacle_with_trajectory(
            [
                ExtendedPMState(
                    time_step=i,
                    position=np.array([0.0, 0.0]),
                    velocity=1.0,
                    orientation=0.0,
                    acceleration=0.0,
                )
                for i in range(0, 100)
            ]
        )

        state_list = get_full_state_list_of_obstacle(obstacle)
        assert len(state_list) == 100
        assert all(isinstance(state, ExtendedPMState) for state in state_list)

    def test_harmonizes_all_states_to_same_type_custom(self):
        obstacle = create_test_obstacle_with_trajectory(
            [
                CustomState(time_step=i, position=np.array([0.0, 0.0]), foo="bar", x=1)
                for i in range(0, 100)
            ]
        )

        state_list = get_full_state_list_of_obstacle(obstacle)
        assert len(state_list) == 100
        assert all(isinstance(state, CustomState) for state in state_list)


class TestTryLoadXmlFileAsCommonRoadScenario:
    def test_returns_none_if_file_does_not_exist(self) -> None:
        result = try_load_xml_file_as_commonroad_scenario(Path("not existing path"))
        assert result is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.OSM_MAP])
    def test_returns_none_if_file_is_osm_map(self, file: str) -> None:
        file_path = ResourceType.OSM_MAP.get_folder() / file
        result = try_load_xml_file_as_commonroad_scenario(file_path)
        assert result is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.CR_SOLUTION])
    def test_returns_none_if_file_is_commonroad_solution(self, file: str) -> None:
        file_path = ResourceType.CR_SOLUTION.get_folder() / file
        result = try_load_xml_file_as_commonroad_scenario(file_path)
        assert result is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.CR_SCENARIO])
    def test_can_successfully_load_commonroad_scenario(self, file: str) -> None:
        file_path = ResourceType.CR_SCENARIO.get_folder() / file
        result = try_load_xml_file_as_commonroad_scenario(file_path)
        assert result is not None
        assert isinstance(result[0], Scenario)
        assert isinstance(result[1], PlanningProblemSet)


class TestTryLoadXmlFileAsCommonRoadSolution:
    def test_returns_none_if_file_does_not_exist(self) -> None:
        solution = try_load_xml_file_as_commonroad_solution(Path("not existing path"))
        assert solution is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.OSM_MAP])
    def test_returns_none_if_file_is_osm_map(self, file: str) -> None:
        file_path = ResourceType.OSM_MAP.get_folder() / file
        solution = try_load_xml_file_as_commonroad_solution(file_path)
        assert solution is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.CR_SCENARIO])
    def test_returns_none_if_file_is_commonroad_scenario(self, file: str) -> None:
        file_path = ResourceType.CR_SCENARIO.get_folder() / file
        solution = try_load_xml_file_as_commonroad_solution(file_path)
        assert solution is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.CR_SOLUTION])
    def test_can_successfully_load_commonroad_solution(self, file: str) -> None:
        file_path = ResourceType.CR_SOLUTION.get_folder() / file
        solution = try_load_xml_file_as_commonroad_solution(file_path)
        assert isinstance(solution, Solution)


class TestDetermineXmlFileType:
    @pytest.mark.parametrize("scenario_file", RESOURCES[ResourceType.CR_SCENARIO])
    def test_identifies_all_scenarios(self, scenario_file: str) -> None:
        scenario_path = ResourceType.CR_SCENARIO.get_folder() / scenario_file
        determined_xml_file_type = determine_xml_file_type(scenario_path)
        assert determined_xml_file_type == CommonRoadXmlFileType.SCENARIO

    @pytest.mark.parametrize("osm_map", RESOURCES[ResourceType.OSM_MAP])
    def test_identifies_osm_maps_as_unkown_file_types(self, osm_map: str) -> None:
        osm_map_path = ResourceType.OSM_MAP.get_folder() / osm_map
        determined_xml_file_type = determine_xml_file_type(osm_map_path)
        assert determined_xml_file_type == CommonRoadXmlFileType.UNKNOWN

    @pytest.mark.parametrize("solution_file", RESOURCES[ResourceType.CR_SOLUTION])
    def test_identifies_all_solutions(self, solution_file: str) -> None:
        solution_path = ResourceType.CR_SOLUTION.get_folder() / solution_file
        determined_xml_file_type = determine_xml_file_type(solution_path)
        assert determined_xml_file_type == CommonRoadXmlFileType.SOLUTION
