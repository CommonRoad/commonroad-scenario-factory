from dataclasses import dataclass, field
from typing import Sequence

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad_crime.data_structure.base import CriMeBase
from commonroad_crime.measure import TTC

from scenario_factory.metrics.crime import compute_crime_criticality_metrics
from scenario_factory.pipeline.pipeline_context import PipelineContext
from scenario_factory.pipeline.pipeline_step import PipelineStepArguments, pipeline_map_with_args
from scenario_factory.scenario_container import (
    ScenarioContainer,
)


@dataclass
class ComputeCriticalityMetricsArgs(PipelineStepArguments):
    metrics: Sequence[type[CriMeBase]] = field(default_factory=lambda: [TTC])


@pipeline_map_with_args()
def pipeline_compute_criticality_metrics(
    args: ComputeCriticalityMetricsArgs,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> ScenarioContainer:
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError()

    runtime_directory_path = ctx.get_temporary_folder("crime") / str(
        scenario_container.scenario.scenario_id
    )
    runtime_directory_path.mkdir(exist_ok=False)

    crime_metric_data_of_scenario = compute_crime_criticality_metrics(
        scenario_container.scenario,
        planning_problem_set,
        runtime_directory_path,
        args.metrics,
    )

    return scenario_container.with_new_attachments(
        criticality_data=crime_metric_data_of_scenario,
    )
