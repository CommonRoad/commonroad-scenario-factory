from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple, TypeVar

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.planning.planning_problem import PlanningProblem, PlanningProblemSet
from commonroad.scenario.scenario import Scenario

from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map_with_args

_T = TypeVar("_T")


def pipeline_flatten(ctx: PipelineContext, xss: Iterable[Iterable[_T]]) -> Iterable[_T]:
    """
    If xss is a nested iterable, it is flattend by one level. Otherwise the iterable, is preserved.
    """
    for xs in xss:
        if not isinstance(xs, Iterable):
            yield xs
        else:
            yield from xs


@dataclass
class WriteCommonRoadScenarioToFileArguments(PipelineStepArguments):
    output_folder: str


@pipeline_map_with_args
def pipeline_write_commonroad_scenario_to_file(
    args: WriteCommonRoadScenarioToFileArguments, ctx: PipelineContext, scenario: Scenario
) -> Optional[Path]:
    output_path = ctx.get_output_folder(args.output_folder)
    cr_file_path = output_path.joinpath(f"{scenario.scenario_id}.xml")

    CommonRoadFileWriter(scenario, PlanningProblemSet()).write_to_file(str(cr_file_path), OverwriteExistingFile.ALWAYS)

    return cr_file_path


@dataclass
class WriteCommonRoadScenarioWithPlanningProblemToFileArguments(PipelineStepArguments):
    output_folder: str


@pipeline_map_with_args
def pipeline_write_commonroad_scenario_with_planning_problem_to_file(
    args: WriteCommonRoadScenarioWithPlanningProblemToFileArguments,
    ctx: PipelineContext,
    scenario_and_planning_problem: Tuple[Scenario, PlanningProblem],
) -> Optional[Path]:
    scenario, planning_problem = scenario_and_planning_problem
    output_path = ctx.get_output_folder(args.output_folder)
    cr_file_path = output_path.joinpath(f"{scenario.scenario_id}.xml")

    planning_problem_set = PlanningProblemSet([planning_problem])
    CommonRoadFileWriter(scenario, planning_problem_set).write_to_file(str(cr_file_path), OverwriteExistingFile.ALWAYS)

    return cr_file_path


__all__ = [
    "pipeline_flatten",
    "WriteCommonRoadScenarioToFileArguments",
    "pipeline_write_commonroad_scenario_to_file",
    "WriteCommonRoadScenarioWithPlanningProblemToFileArguments",
    "pipeline_write_commonroad_scenario_with_planning_problem_to_file",
]
