import numpy as np
from commonroad.scenario.state import ExtendedPMState, InitialState

from scenario_factory.utils import get_full_state_list_of_obstacle
from tests.helpers import create_test_obstacle_with_trajectory


class TestGetFullStateListOfObstacle:
    def test_returns_only_initial_state_if_obstacle_has_no_prediction(self):
        initial_state = InitialState()
        initial_state.fill_with_defaults()

        obstacle = create_test_obstacle_with_trajectory([initial_state])
        state_list = get_full_state_list_of_obstacle(obstacle)

        assert len(state_list) == 1
        assert isinstance(state_list[0], InitialState)

    def test_harmonizes_all_states_to_same_type(self):
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
