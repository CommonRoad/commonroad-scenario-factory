from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeVar

from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map_with_args
from scenario_factory.scenario_types import EgoScenarioWithPlanningProblemSet

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
class WriteScenarioToFileArguments(PipelineStepArguments):
    output_folder: Path


@pipeline_map_with_args
def pipeline_write_scenario_to_file(
    args: WriteScenarioToFileArguments, ctx: PipelineContext, scenario: EgoScenarioWithPlanningProblemSet
) -> Path:
    return scenario.write(args.output_folder)


__all__ = [
    "pipeline_flatten",
    "WriteScenarioToFileArguments",
    "pipeline_write_scenario_to_file",
]
