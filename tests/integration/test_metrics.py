from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scenario_factory.metrics import GeneralScenarioMetric, WaymoMetric
from scenario_factory.pipeline.pipeline import Pipeline
from scenario_factory.pipeline_steps.metrics import (
    ComputeSingleScenarioMetricsArguments,
    pipeline_compute_single_scenario_metrics,
    pipeline_compute_waymo_metrics,
)
from scenario_factory.pipeline_steps.simulation import (
    SimulateScenarioArguments,
    pipeline_simulate_scenario_with_ots,
    pipeline_simulate_scenario_with_sumo,
)
from scenario_factory.scenario_container import (
    load_scenarios_from_folder,
    write_general_scenario_metrics_of_scenario_containers_to_csv,
    write_waymo_metrics_of_scenario_containers_to_csv,
)
from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from tests.resources import ResourceType


@pytest.mark.parametrize("simulation_mode", [SimulationMode.RESIMULATION, SimulationMode.DELAY])
@pytest.mark.parametrize(
    "simulation_step", [pipeline_simulate_scenario_with_sumo, pipeline_simulate_scenario_with_ots]
)
def test_can_compute_waymo_metrics_after_simulation(
    simulation_mode: SimulationMode, simulation_step
):
    pipeline = (
        Pipeline()
        .map(
            simulation_step(
                SimulateScenarioArguments(config=SimulationConfig(mode=simulation_mode))
            )
        )
        .map(pipeline_compute_waymo_metrics)
    )

    scenarios = load_scenarios_from_folder(ResourceType.COMMONROAD_SCENARIO.get_folder())
    result = pipeline.execute(scenarios, debug=True)
    assert len(result.errors) == 0
    assert len(result.values) == len(scenarios)

    assert all(
        scenario_container.has_attachment(WaymoMetric) for scenario_container in result.values
    )
    with TemporaryDirectory() as tempdir:
        csv_file = Path(tempdir) / "waymo_metrics.csv"
        write_waymo_metrics_of_scenario_containers_to_csv(result.values, csv_file)

        assert csv_file.exists()


@pytest.mark.parametrize(
    "simulation_mode",
    [
        SimulationMode.RESIMULATION,
        SimulationMode.DELAY,
        SimulationMode.DEMAND_TRAFFIC_GENERATION,
    ],
)
@pytest.mark.parametrize(
    "simulation_step", [pipeline_simulate_scenario_with_sumo, pipeline_simulate_scenario_with_ots]
)
def test_can_compute_single_scenario_metrics_after_simulation(
    simulation_mode: SimulationMode, simulation_step
):
    pipeline = (
        Pipeline()
        .map(
            simulation_step(
                SimulateScenarioArguments(config=SimulationConfig(mode=simulation_mode))
            )
        )
        .map(pipeline_compute_single_scenario_metrics(ComputeSingleScenarioMetricsArguments()))
    )

    scenarios = load_scenarios_from_folder(ResourceType.COMMONROAD_SCENARIO.get_folder())
    result = pipeline.execute(scenarios, debug=True)
    assert len(result.errors) == 0
    assert len(result.values) == len(scenarios)

    assert all(
        scenario_container.has_attachment(GeneralScenarioMetric)
        for scenario_container in result.values
    )
    with TemporaryDirectory() as tempdir:
        csv_file = Path(tempdir) / "general_metrics.csv"
        write_general_scenario_metrics_of_scenario_containers_to_csv(result.values, csv_file)

        assert csv_file.exists()
