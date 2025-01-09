import copy

import numpy as np
import pytest
from commonroad.scenario.state import CustomState, ExtendedPMState, InitialState
from commonroad.scenario.traffic_light import (
    TrafficLight,
    TrafficLightCycle,
    TrafficLightCycleElement,
    TrafficLightState,
)

from scenario_factory.builder import ScenarioBuilder
from scenario_factory.utils import (
    align_state_list_to_time_step,
    align_state_to_time_step,
    convert_state_to_state,
    copy_scenario,
    get_full_state_list_of_obstacle,
)
from scenario_factory.utils.align import align_traffic_light_to_time_step
from tests.helpers.obstacle import create_test_obstacle_with_trajectory


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
