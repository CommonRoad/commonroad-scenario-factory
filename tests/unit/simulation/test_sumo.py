from pathlib import Path
from tempfile import TemporaryDirectory

from commonroad.scenario.scenario import Tag

from scenario_factory.builder import ScenarioBuilder
from scenario_factory.simulation import (
    SimulationConfig,
    SimulationMode,
    simulate_commonroad_scenario_with_sumo,
)


class TestSimulateCommonroadScenarioWithSumo:
    def test_adds_the_simulated_tag_to_scenario_if_scenario_has_no_tags_set(self):
        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        scenario_builder = ScenarioBuilder()
        scenario_builder.create_lanelet_network().add_lanelet(start=(0.0, 0.0), end=(0.0, 100.0))
        scenario = scenario_builder.build()
        with TemporaryDirectory() as tempdir:
            simulated_scenario = simulate_commonroad_scenario_with_sumo(
                scenario, simulation_config, Path(tempdir), seed=0
            )

        assert len(simulated_scenario.tags) == 1
        assert Tag.SIMULATED in simulated_scenario.tags

    def test_adds_the_simulated_tag_to_scenario_if_scenario_already_has_other_tags(self):
        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        scenario_builder = ScenarioBuilder()
        scenario_builder.create_lanelet_network().add_lanelet(start=(0.0, 0.0), end=(0.0, 100.0))
        scenario = scenario_builder.build()
        scenario.tags = {Tag.INTERSTATE, Tag.COMFORT}
        with TemporaryDirectory() as tempdir:
            simulated_scenario = simulate_commonroad_scenario_with_sumo(
                scenario, simulation_config, Path(tempdir), seed=0
            )

        assert len(simulated_scenario.tags) == 3
        assert Tag.SIMULATED in simulated_scenario.tags

    def test_sets_the_obstacle_behavior_to_trajectory_if_no_obstacle_behavior_is_set_before_simulation(
        self,
    ):
        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        scenario_builder = ScenarioBuilder()
        scenario_builder.create_lanelet_network().add_lanelet(start=(0.0, 0.0), end=(0.0, 100.0))
        scenario = scenario_builder.build()
        with TemporaryDirectory() as tempdir:
            simulated_scenario = simulate_commonroad_scenario_with_sumo(
                scenario, simulation_config, Path(tempdir), seed=0
            )

        assert simulated_scenario.scenario_id.obstacle_behavior == "T"

    def test_sets_the_obstacle_behavior_to_trajectory_if_obstacle_behavior_is_set_before_simulation(
        self,
    ):
        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        scenario_builder = ScenarioBuilder()
        scenario_builder.create_lanelet_network().add_lanelet(start=(0.0, 0.0), end=(0.0, 100.0))
        scenario = scenario_builder.build()
        scenario.scenario_id.obstacle_behavior = "I"
        with TemporaryDirectory() as tempdir:
            simulated_scenario = simulate_commonroad_scenario_with_sumo(
                scenario, simulation_config, Path(tempdir), seed=0
            )

        assert simulated_scenario.scenario_id.obstacle_behavior == "T"
