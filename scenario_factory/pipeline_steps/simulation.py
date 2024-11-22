__all__ = [
    "pipeline_simulate_scenario_with_sumo",
    "pipeline_simulate_scenario_with_ots",
]

import logging
from dataclasses import dataclass
from typing import Optional

from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    PipelineStepExecutionMode,
    pipeline_map_with_args,
)
from scenario_factory.scenario_container import ReferenceScenario, ScenarioContainer
from scenario_factory.simulation.config import SimulationConfig
from scenario_factory.simulation.ots import simulate_commonroad_scenario_with_ots
from scenario_factory.simulation.sumo import simulate_commonroad_scenario_with_sumo
from scenario_factory.utils import copy_scenario

_LOGGER = logging.getLogger(__name__)


@dataclass
class SimulateScenarioArguments(PipelineStepArguments):
    """Specify options for either `pipeline_simulate_scenario_with_sumo` or `pipeline_simulate_scenario_with_ots`."""

    config: SimulationConfig


@pipeline_map_with_args(mode=PipelineStepExecutionMode.PARALLEL)
def pipeline_simulate_scenario_with_sumo(
    args: SimulateScenarioArguments, ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Convert a CommonRoad Scenario to SUMO, generate random traffic on the network and simulate the traffic in SUMO.
    """
    commonroad_scenario = scenario_container.scenario
    output_folder = ctx.get_temporary_folder("sumo_simulation_intermediates")
    intermediate_sumo_files_path = output_folder.joinpath(str(commonroad_scenario.scenario_id))
    intermediate_sumo_files_path.mkdir(parents=True, exist_ok=True)

    seed = ctx.get_scenario_factory_config().seed
    simulated_scenario = simulate_commonroad_scenario_with_sumo(
        commonroad_scenario, args.config, intermediate_sumo_files_path, seed
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


@pipeline_map_with_args(mode=PipelineStepExecutionMode.PARALLEL)
def pipeline_simulate_scenario_with_ots(
    args: SimulateScenarioArguments, ctx: PipelineContext, scenario_container: ScenarioContainer
) -> Optional[ScenarioContainer]:
    """
    Simulate a scenario with OTS.
    """
    commonroad_scenario = scenario_container.scenario
    seed = ctx.get_scenario_factory_config().seed
    simulated_scenario = simulate_commonroad_scenario_with_ots(
        commonroad_scenario, args.config, seed
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
