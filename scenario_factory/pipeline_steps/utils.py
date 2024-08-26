__all__ = [
    "pipeline_flatten",
    "WriteScenarioToFileArguments",
    "pipeline_write_scenario_to_file",
    "pipeline_add_metadata_to_scenario",
]

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeVar

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.planning.planning_problem import PlanningProblemSet

from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map, pipeline_map_with_args
from scenario_factory.scenario_types import ScenarioContainer, ScenarioWithPlanningProblemSet
from scenario_factory.tags import find_applicable_tags_for_scenario

_T = TypeVar("_T")


def pipeline_flatten(ctx: PipelineContext, xss: Iterable[Iterable[_T]]) -> Iterable[_T]:
    """
    If xss is a nested iterable, it is flattend by one level. Otherwise the iterable is preserved.
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
    args: WriteScenarioToFileArguments,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> Path:
    planning_problem_set = (
        scenario_container.planning_problem_set
        if isinstance(scenario_container, ScenarioWithPlanningProblemSet)
        else PlanningProblemSet(None)
    )
    commonroad_scenario = scenario_container.scenario
    # Metadata must be set on the scenario, otherwise we refuse to write
    if commonroad_scenario.author is None:
        raise ValueError(
            f"Cannot write scenario '{commonroad_scenario.scenario_id}' to file, because metadata is missing: Author of scenario is not set"
        )
    if commonroad_scenario.affiliation is None:
        raise ValueError(
            f"Cannot write scenario '{commonroad_scenario.scenario_id}' to file, because metadata is missing: Affiliation for author of scenario is not set"
        )
    if commonroad_scenario.source is None:
        raise ValueError(
            f"Cannot write scenario '{commonroad_scenario.scenario_id}' to file, because metadata is missing: source of scenario is not set"
        )
    tags = set() if commonroad_scenario.tags is None else commonroad_scenario.tags

    file_path = args.output_folder.joinpath(f"{commonroad_scenario.scenario_id}.cr.xml")
    CommonRoadFileWriter(commonroad_scenario, planning_problem_set, tags=tags).write_scenario_to_file(
        str(file_path), overwrite_existing_file=OverwriteExistingFile.ALWAYS
    )
    return file_path


@pipeline_map
def pipeline_assign_tags_to_scenario(ctx: PipelineContext, scenario_container: ScenarioContainer) -> ScenarioContainer:
    commonroad_scenario = scenario_container.scenario
    tags = find_applicable_tags_for_scenario(commonroad_scenario)
    if commonroad_scenario.tags is None:
        commonroad_scenario.tags = tags
    else:
        commonroad_scenario.tags.update(tags)

    return scenario_container


@pipeline_map
def pipeline_add_metadata_to_scenario(ctx: PipelineContext, scenario_container: ScenarioContainer) -> ScenarioContainer:
    """
    Populate the metadata of the scenario with the values in the scenario factory config that is attached to the pipeline context.
    """
    scenario_factory_config = ctx.get_scenario_config()

    commonroad_scenario = scenario_container.scenario

    commonroad_scenario.author = scenario_factory_config.author
    commonroad_scenario.affiliation = scenario_factory_config.affiliation
    commonroad_scenario.source = scenario_factory_config.source

    if not isinstance(commonroad_scenario.tags, set):
        commonroad_scenario.tags = set()

    commonroad_scenario.tags.update(scenario_factory_config.tags)

    return scenario_container
