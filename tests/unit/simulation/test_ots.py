from commonroad.scenario.scenario import Scenario, Tag

from scenario_factory.builder import ScenarioBuilder
from scenario_factory.simulation import (
    SimulationConfig,
    SimulationMode,
    simulate_commonroad_scenario_with_ots,
)


class TestSimulateCommonroadScenarioWithOts:
    def test_refuses_to_resimulate_empty_scenario(self):
        scenario = Scenario(dt=0.1)
        simulation_config = SimulationConfig(mode=SimulationMode.RESIMULATION)
        simulated_scenario = simulate_commonroad_scenario_with_ots(scenario, simulation_config, 100)
        assert simulated_scenario is None

    def test_adds_the_simulated_tag_to_scenario_if_scenario_has_no_tags_set(self):
        simulation_config = SimulationConfig(
            mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=100
        )
        scenario_builder = ScenarioBuilder()
        scenario_builder.create_lanelet_network().add_lanelet(start=(0.0, 0.0), end=(0.0, 100.0))
        scenario = scenario_builder.build()

        simulated_scenario = simulate_commonroad_scenario_with_ots(
            scenario, simulation_config, seed=1
        )

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

        simulated_scenario = simulate_commonroad_scenario_with_ots(
            scenario, simulation_config, seed=1
        )

        assert simulated_scenario is not None

        assert len(simulated_scenario.tags) == 4
        assert Tag.SIMULATED in simulated_scenario.tags
