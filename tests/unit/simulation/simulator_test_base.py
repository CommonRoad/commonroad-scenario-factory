from abc import ABC, abstractmethod
from typing import Optional

from commonroad.scenario.scenario import Scenario, Tag

from scenario_factory.builder.scenario_builder import ScenarioBuilder
from scenario_factory.simulation.config import SimulationConfig, SimulationMode


class SimulatorTestBase(ABC):
    """
    This contains tests that should be executed by every simulator (currently SUMO and OTS). This base class is inherited in each of the simulators tests, to execute them.
    """

    @abstractmethod
    def simulate(
        self, scenario: Scenario, simulation_config: SimulationConfig, seed: int
    ) -> Optional[Scenario]:
        """
        This method should be overriden by the specific simulator tests, to execute a simulation.
        """
        ...

    def test_adds_the_simulated_tag_to_scenario_if_scenario_has_no_tags_set(self):
        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        scenario_builder = ScenarioBuilder()
        scenario_builder.create_lanelet_network().add_lanelet(start=(0.0, 0.0), end=(0.0, 100.0))
        scenario = scenario_builder.build()

        simulated_scenario = self.simulate(scenario, simulation_config, seed=1)

        assert simulated_scenario is not None

        assert len(simulated_scenario.tags) == 1
        assert Tag.SIMULATED in simulated_scenario.tags

    def test_adds_the_simulated_tag_to_scenario_if_scenario_already_has_other_tags(self):
        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        scenario_builder = ScenarioBuilder()
        scenario_builder.create_lanelet_network().add_lanelet(start=(0.0, 0.0), end=(0.0, 100.0))
        scenario = scenario_builder.build()
        scenario.tags = {Tag.INTERSECTION, Tag.ONCOMING_TRAFFIC, Tag.EVASIVE}

        simulated_scenario = self.simulate(scenario, simulation_config, seed=1)

        assert simulated_scenario is not None

        assert len(simulated_scenario.tags) == 4
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
        simulated_scenario = self.simulate(scenario, simulation_config, seed=1)
        assert simulated_scenario

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
        simulated_scenario = self.simulate(scenario, simulation_config, seed=1)
        assert simulated_scenario is not None

        assert simulated_scenario.scenario_id.obstacle_behavior == "T"

    def test_can_simulate_scenarios_with_traffic_lights(self):
        """
        This tests if we can successfully simulate a signaled T-Intersection.
        """
        scenario_builder = ScenarioBuilder()
        lanelet_network_builder = scenario_builder.create_lanelet_network()
        lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 10.0))
        lanelet2 = lanelet_network_builder.add_adjacent_lanelet(
            lanelet1, side="left", same_direction=False
        )
        lanelet3 = lanelet_network_builder.add_lanelet(start=(0.0, 30.0), end=(0.0, 40.0))
        lanelet4 = lanelet_network_builder.add_adjacent_lanelet(
            lanelet3, side="left", same_direction=False
        )
        lanelet5 = lanelet_network_builder.add_lanelet(start=(10.0, 18.0), end=(20.0, 18.0))
        lanelet6 = lanelet_network_builder.add_adjacent_lanelet(
            lanelet5, side="left", same_direction=False
        )
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet1, lanelet3)
        lanelet_network_builder.create_straight_connecting_lanelet(lanelet4, lanelet2)
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet5)
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet4, lanelet5)
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet6, lanelet2)
        lanelet_network_builder.create_curved_connecting_lanelet(lanelet6, lanelet3)
        intersection_builder = lanelet_network_builder.create_intersection()
        (
            intersection_builder.create_incoming()
            .add_incoming_lanelet(lanelet1)
            .connect_straight(lanelet3)
            .connect_right(lanelet5)
        )
        (
            intersection_builder.create_incoming()
            .add_incoming_lanelet(lanelet4)
            .connect_straight(lanelet2)
            .connect_left(lanelet5)
        )
        (
            intersection_builder.create_incoming()
            .add_incoming_lanelet(lanelet6)
            .connect_left(lanelet2)
            .connect_right(lanelet3)
        )
        (lanelet_network_builder.create_traffic_light().for_lanelet(lanelet1).use_default_cycle())
        (lanelet_network_builder.create_traffic_light().for_lanelet(lanelet4).use_default_cycle())
        (
            lanelet_network_builder.create_traffic_light()
            .for_lanelet(lanelet6)
            .use_default_cycle()
            .set_cycle_offset(60)
        )
        scenario = scenario_builder.build()

        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        simulated_scenario = self.simulate(scenario, simulation_config, seed=10)
        assert simulated_scenario is not None

        assert len(simulated_scenario.dynamic_obstacles) > 0
        assert len(simulated_scenario.lanelet_network.traffic_lights) == 3
        for traffic_light in simulated_scenario.lanelet_network.traffic_lights:
            assert traffic_light.traffic_light_cycle is not None
            assert traffic_light.traffic_light_cycle.cycle_elements is not None
            assert len(traffic_light.traffic_light_cycle.cycle_elements) > 0
