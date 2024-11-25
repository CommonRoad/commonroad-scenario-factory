import logging
from dataclasses import dataclass

from scenario_factory.metrics.waymo_metric import compute_waymo_metric
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map_with_args,
)
from scenario_factory.scenario_container import ReferenceScenario, ScenarioContainer

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
    assert scenario_container.has_attachment(ReferenceScenario)
    waymo_metric = compute_waymo_metric(
        scenario_container.scenario,
        scenario_container.get_attachment(ReferenceScenario).reference_scenario,  # type: ignore
    )
    _LOGGER.debug(
        "Computed Waymo metrics for scenario %s: %s",
        str(scenario_container.scenario.scenario_id),
        str(waymo_metric),
    )

    return scenario_container.with_attachments(waymo_metric=waymo_metric)
