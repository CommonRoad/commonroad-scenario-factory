from dataclasses import dataclass

from scenario_factory.metrics.general_scenario_metric import compute_general_scenario_metric
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map_with_args
from scenario_factory.scenario_container import ScenarioContainer


@dataclass
class ComputeGeneralScenarioMetricsArguments(PipelineStepArguments):
    """Arguments for the step `pipeline_compute_single_scenario_metrics` to specify the configuration for the computation."""

    is_orig: bool = False  # real-world recordings need other frame factors


@pipeline_map_with_args()
def pipeline_compute_general_scenario_metrics(
    args: ComputeGeneralScenarioMetricsArguments,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> ScenarioContainer:
    """
    Compute the single scenario metrics for the scenario.

    :param args: `ComputeGeneralScenarioMetricsArguments` that specify the configuration for the computation
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    """

    general_scenario_metric = compute_general_scenario_metric(
        scenario_container.scenario, args.is_orig
    )
    return scenario_container.with_attachments(general_scenario_metric=general_scenario_metric)
