from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from commonroad.scenario.scenario import Scenario

from scenario_factory.simulation import (
    SimulationConfig,
    simulate_commonroad_scenario_with_sumo,
)
from tests.unit.simulation.simulator_test_base import SimulatorTestBase


class TestSimulateCommonroadScenarioWithSumo(SimulatorTestBase):
    def simulate(
        self, scenario: Scenario, simulation_config: SimulationConfig
    ) -> Optional[Scenario]:
        with TemporaryDirectory() as tempdir:
            simulated_scenario = simulate_commonroad_scenario_with_sumo(
                scenario, simulation_config, Path(tempdir)
            )
            return simulated_scenario
