__all__ = [
    "pipeline_simulate_scenario_with_sumo",
    "pipeline_simulate_scenario_with_ots",
]

import logging
from typing import Optional

from scenario_factory.pipeline import PipelineContext, PipelineStepExecutionMode, pipeline_map
from scenario_factory.scenario_container import ReferenceScenario, ScenarioContainer
from scenario_factory.simulation import (
    SimulationConfig,
    simulate_commonroad_scenario_with_ots,
    simulate_commonroad_scenario_with_sumo,
)
from scenario_factory.utils import copy_scenario

_LOGGER = logging.getLogger(__name__)


@pipeline_map(mode=PipelineStepExecutionMode.PARALLEL)
def pipeline_simulate_scenario_with_sumo(
    ctx: PipelineContext, scenario_container: ScenarioContainer, simulation_config: SimulationConfig
) -> ScenarioContainer:
    """
    Convert a CommonRoad Scenario to SUMO, generate random traffic on the network and simulate the traffic in SUMO.
    """
    commonroad_scenario = scenario_container.scenario
    output_folder = ctx.get_temporary_folder("sumo_simulation_intermediates")
    intermediate_sumo_files_path = output_folder.joinpath(str(commonroad_scenario.scenario_id))
    intermediate_sumo_files_path.mkdir(parents=True, exist_ok=True)

    simulated_scenario = simulate_commonroad_scenario_with_sumo(
        commonroad_scenario, simulation_config, intermediate_sumo_files_path
    )
    _LOGGER.debug(
        "Simulated scenario %s with SUMO and created %s new obstacles",
        simulated_scenario.scenario_id,
        len(simulated_scenario.dynamic_obstacles),
    )

    # Attach the original scenario as the reference scenario, so that downstream functionality
    # can compare the original with the simulation.
    reference_scenario = ReferenceScenario(copy_scenario(commonroad_scenario))
    new_scenario_container = ScenarioContainer(
        simulated_scenario, reference_scenario=reference_scenario
    )
    return new_scenario_container


@pipeline_map(mode=PipelineStepExecutionMode.PARALLEL)
def pipeline_simulate_scenario_with_ots(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    simulation_config: SimulationConfig,
) -> Optional[ScenarioContainer]:
    """
    Simulate a scenario with OTS.
    """
    commonroad_scenario = scenario_container.scenario
    simulated_scenario = simulate_commonroad_scenario_with_ots(
        commonroad_scenario, simulation_config
    )
    _LOGGER.debug(
        "Simulated scenario %s with OTS and created %s new obstacles",
        simulated_scenario.scenario_id,
        len(simulated_scenario.dynamic_obstacles),
    )

    # Attach the original scenario as the reference scenario, so that downstream functionality
    # can compare the original with the simulation.
    reference_scenario = ReferenceScenario(copy_scenario(commonroad_scenario))
    new_scenario = ScenarioContainer(simulated_scenario, reference_scenario=reference_scenario)
    return new_scenario
