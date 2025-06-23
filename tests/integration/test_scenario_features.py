import numpy as np
from commonroad.common.util import Interval

from scenario_factory.builder import ScenarioBuilder
from scenario_factory.scenario_features.models.scenario_model import ScenarioModel


def test_basic_scenario_features():
    # Create a simple test scenario with two parallel lanes using the builder
    scenario_builder = ScenarioBuilder()

    lanelet_network_builder = scenario_builder.create_lanelet_network()

    # Add two parallel lanelets
    lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(50.0, 0.0), width=4)
    lanelet2 = lanelet_network_builder.add_lanelet(start=(60.0, 10.0), end=(60.0, 30.0), width=4)
    lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet2)
    scenario = scenario_builder.build()

    # Initialize ScenarioModel
    scenario_model = ScenarioModel(scenario)

    # Test 1: Check if position is on lanelet
    test_position = np.array([55.0, 1.0])
    lanelet_ids = scenario_model.lanelet_network.find_lanelet_by_position([test_position])[0]
    assert len(lanelet_ids) > 0, "Position should be on at least one lanelet"

    # Test 2: Check reachable sections calculation
    reachable_sections = scenario_model.get_reachable_sections_front(
        position=test_position, max_distance=40.0
    )
    assert len(reachable_sections) > 0, "Should find reachable sections"

    # Test 3: Check coordinate transformation
    lanelet_id = lanelet_ids[0]
    curv_coords = scenario_model.lanelet_section_network.get_curv_position_lanelet(
        position=test_position, lanelet_id=lanelet_id
    )
    assert isinstance(curv_coords, np.ndarray)
    assert len(curv_coords) == 2, "Should return [s, t] coordinates"
    assert not np.isnan(curv_coords).any(), "Coordinates should be valid numbers"

    # Test 4: Check behavior with invalid position
    invalid_position = np.array([1000.0, 1000.0])
    invalid_lanelet_ids = scenario_model.lanelet_network.find_lanelet_by_position(
        [invalid_position]
    )[0]
    assert len(invalid_lanelet_ids) == 0, "Invalid position should not be on any lanelet"

    # Test 5: Check obstacle array for invalid position
    obstacles = scenario_model.get_obstacles_array(
        init_position=invalid_position, longitudinal_range=Interval(-50, 100), time_step=0
    )
    assert len(obstacles) == 0, "Should return empty list for invalid position"
