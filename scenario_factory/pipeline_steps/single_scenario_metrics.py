from dataclasses import dataclass

from scenario_factory.metrics.single_scenario import compute_single_scenario_metrics
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map_with_args
from scenario_factory.scenario_types import ScenarioContainer, ScenarioWithSingleScenarioMetrics


@dataclass
class ComputeSingleScenarioMetricsArguments(PipelineStepArguments):
    """Arguments for the step `pipeline_compute_single_scenario_metrics` to specify the configuration for the computation."""

    is_orig: bool = False


@pipeline_map_with_args()
def pipeline_compute_single_scenario_metrics(
    args: ComputeSingleScenarioMetricsArguments,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> ScenarioWithSingleScenarioMetrics:
    """
    Compute the single scenario metrics for the scenario.

    :param args: `ComputeSingleScenarioMetricsArguments` that specify the configuration for the computation
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    """

    single_scenario_metric = compute_single_scenario_metrics(
        scenario_container.scenario, args.is_orig
    )
    return ScenarioWithSingleScenarioMetrics(
        scenario=scenario_container.scenario, single_scenario_metrics=single_scenario_metric
    )
