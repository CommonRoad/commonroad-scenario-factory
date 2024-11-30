import numpy as np
from commonroad.common.reader.file_reader_protobuf import TrajectoryPrediction
from commonroad.scenario.scenario import Scenario
from commonroad.scenario.state import CustomState, ExtendedPMState, InitialState

from scenario_factory.builder.scenario_builder import ScenarioBuilder
from scenario_factory.utils import (
    convert_state_to_state,
    copy_scenario,
    get_full_state_list_of_obstacle,
)
from tests.helpers.obstacle import create_test_obstacle_with_trajectory


class TestCopyScenario:
    def test_handles_empty_scenario(self):
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(10.0, 10.0))
        scenario_builder.create_dynamic_obstacle()

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
