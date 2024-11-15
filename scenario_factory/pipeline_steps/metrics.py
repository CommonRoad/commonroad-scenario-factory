import logging
from dataclasses import dataclass, field
from typing import Sequence

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad_crime.data_structure.base import CriMeBase
from commonroad_crime.measure import TTC

from scenario_factory.metrics import (
    compute_crime_criticality_metrics_for_scenario_and_planning_problem_set,
    compute_general_scenario_metric,
    compute_waymo_metric,
)
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map,
    pipeline_map_with_args,
)
from scenario_factory.scenario_container import (
    ReferenceScenario,
    ScenarioContainer,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComputeCriticalityMetricsArgs(PipelineStepArguments):
    metrics: Sequence[type[CriMeBase]] = field(default_factory=lambda: [TTC])


@pipeline_map_with_args()
def pipeline_compute_criticality_metrics(
    args: ComputeCriticalityMetricsArgs,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> ScenarioContainer:
    """
    Compute the criticality metrics for the scenario.

    :param ctx: The context for this pipeline execution
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    :returns: The input `ScenarioContainer` with an additional `CriticalityMetric` attachment.
    """
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            f"Cannot compute criticality metric for scenario {scenario_container.scenario.scenario_id}: Scenario container has no `PlanningProblemSet` attachment, but one is required!"
        )

    crime_metrics = compute_crime_criticality_metrics_for_scenario_and_planning_problem_set(
        scenario_container.scenario,
        planning_problem_set,
        args.metrics,
    )

    return scenario_container.with_attachments(
        criticality_metric=crime_metrics,
    )


@pipeline_map()
def pipeline_compute_waymo_metrics(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Compute the Waymo metrics for the scenario.

    :param ctx: The context for this pipeline execution
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    :returns: The input `ScenarioContainer` with an additional `WaymoMetric` attachment.
    """
    reference_scenario = scenario_container.get_attachment(ReferenceScenario)
    if reference_scenario is None:
        raise ValueError(
            f"Cannot compute waymo metric for scenario {scenario_container.scenario.scenario_id}: Scenario contaienr must have a `ReferenceScenario` attachment!"
        )
    waymo_metric = compute_waymo_metric(
        scenario_container.scenario, reference_scenario.reference_scenario
    )
    _LOGGER.debug(
        "Computed Waymo metrics for scenario %s: %s",
        str(scenario_container.scenario.scenario_id),
        str(waymo_metric),
    )

    return scenario_container.with_attachments(waymo_metric=waymo_metric)


@dataclass
class ComputeSingleScenarioMetricsArguments(PipelineStepArguments):
    """Arguments for the step `pipeline_compute_single_scenario_metrics` to specify the configuration for the computation."""

    is_orig: bool = False


@pipeline_map_with_args()
def pipeline_compute_single_scenario_metrics(
    args: ComputeSingleScenarioMetricsArguments,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> ScenarioContainer:
    """
    Compute the single scenario metrics for the scenario.

    :param args: `ComputeSingleScenarioMetricsArguments` that specify the configuration for the computation
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    """

    general_scenario_metric = compute_general_scenario_metric(
        scenario_container.scenario, args.is_orig
    )
    return scenario_container.with_attachments(general_scenario_metric=general_scenario_metric)
