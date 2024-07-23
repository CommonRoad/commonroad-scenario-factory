__all__ = [
    "pipeline_flatten",
    "WriteScenarioToFileArguments",
    "pipeline_write_scenario_to_file",
]

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, TypeVar

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.scenario.scenario import Scenario

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
) -> Optional[Path]:
    if isinstance(scenario, EgoScenarioWithPlanningProblemSet):
        return scenario.write(args.output_folder)
    elif isinstance(scenario, Scenario):
        file_path = args.output_folder.joinpath(f"{scenario.scenario_id}.cr.xml")
        CommonRoadFileWriter(
            scenario, None, author="test", affiliation="test", source="test", tags=set()
        ).write_scenario_to_file(str(file_path), overwrite_existing_file=OverwriteExistingFile.ALWAYS)
        return file_path
