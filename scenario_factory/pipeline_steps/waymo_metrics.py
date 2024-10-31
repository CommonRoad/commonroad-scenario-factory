import logging
from dataclasses import dataclass, field
from email.policy import default
from typing import Sequence

from scenario_factory.metrics.waymo import compute_waymo_metrics
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    PipelineStepExecutionMode,
    pipeline_map_with_args,
)
from scenario_factory.scenario_types import (
    ScenarioContainer,
    ScenarioWithReferenceScenario,
    ScenarioWithWaymoMetrics,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComputeWaymoMetricsArguments(PipelineStepArguments):
    """Arguments for the step `pipeline_compute_waymo_metrics` to specify the configuration for the computation."""

    pass


@pipeline_map_with_args()
def pipeline_compute_waymo_metrics(
    args: ComputeWaymoMetricsArguments, ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Compute the Waymo metrics for the scenario.

    :param args: `ComputeWaymoMetricsArguments` that specify the configuration for the computation
    :param ctx: The context for this pipeline execution
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    """
    assert isinstance(scenario_container, ScenarioWithReferenceScenario)
    waymo_metrics = compute_waymo_metrics(
        scenario_container.scenario, scenario_container.reference_scenario
    )
    # _LOGGER.warning("Computing Waymo Metric for: ", commonroad_scenario.scenario_id)
    _LOGGER.warning(
        "Computed Waymo metrics for scenario %s: %s",
        str(scenario_container.scenario.scenario_id),
        str(waymo_metrics),
    )
    return ScenarioWithWaymoMetrics(scenario_container.scenario, waymo_metrics)
