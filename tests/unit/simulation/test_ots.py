from typing import Optional

import pytest
from commonroad.scenario.scenario import Scenario

from scenario_factory.simulation import (
    SimulationConfig,
    SimulationMode,
    simulate_commonroad_scenario_with_ots,
)
from tests.unit.simulation.simulator_test_base import SimulatorTestBase


class TestSimulateCommonroadScenarioWithOts(SimulatorTestBase):
    def simulate(
        self, scenario: Scenario, simulation_config: SimulationConfig, seed: int
    ) -> Optional[Scenario]:
        return simulate_commonroad_scenario_with_ots(scenario, simulation_config, seed)

    def test_refuses_to_resimulate_empty_scenario(self):
        scenario = Scenario(dt=0.1)
        simulation_config = SimulationConfig(mode=SimulationMode.RESIMULATION)
        with pytest.raises(RuntimeError):
            simulate_commonroad_scenario_with_ots(scenario, simulation_config, 100)
