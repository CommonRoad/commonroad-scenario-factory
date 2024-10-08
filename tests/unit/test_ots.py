from commonroad.scenario.scenario import Scenario

from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from scenario_factory.simulation.ots import simulate_commonroad_scenario_with_ots


class TestSimulateCommonroadScenarioWithOts:
    def test_refuses_to_resimulate_empty_scenario(self):
        scenario = Scenario(dt=0.1)
        simulation_config = SimulationConfig(mode=SimulationMode.RESIMULATION)
        simulated_scenario = simulate_commonroad_scenario_with_ots(scenario, simulation_config, 100)
        assert simulated_scenario is None
