__all__ = [
    "WriteScenarioToFileArguments",
    "pipeline_write_scenario_to_file",
    "pipeline_assign_tags_to_scenario",
    "pipeline_add_metadata_to_scenario",
    "pipeline_remove_colliding_dynamic_obstacles",
]

import logging
from dataclasses import dataclass
from pathlib import Path

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.common.solution import CommonRoadSolutionWriter, Solution
from commonroad.planning.planning_problem import PlanningProblemSet

from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map,
    pipeline_map_with_args,
)
from scenario_factory.scenario_container import (
    ScenarioContainer,
)
from scenario_factory.scenario_generation import delete_colliding_obstacles_from_scenario
from scenario_factory.tags import (
    find_applicable_tags_for_planning_problem_set,
    find_applicable_tags_for_scenario,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WriteScenarioToFileArguments(PipelineStepArguments):
    """Arguments for the step `pipeline_write_scenario_to_file` to specify the output folder."""

    output_folder: Path


@pipeline_map_with_args()
def pipeline_write_scenario_to_file(
    args: WriteScenarioToFileArguments,
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
) -> ScenarioContainer:
    """
    Write a CommonRoad scenario to a file in the `args.output_folder`. If the `scenario_container` also holds a planning problem set or a planning problem solution, they will also be written to disk.
    """
    optional_planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    planning_problem_set = (
        optional_planning_problem_set
        if optional_planning_problem_set is not None
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

    scenario_file_path = args.output_folder.joinpath(f"{commonroad_scenario.scenario_id}.cr.xml")
    CommonRoadFileWriter(commonroad_scenario, planning_problem_set, tags=tags).write_to_file(
        str(scenario_file_path), overwrite_existing_file=OverwriteExistingFile.ALWAYS
    )

    solution = scenario_container.get_attachment(Solution)
    if solution is not None:
        solution_file_name = f"{solution.scenario_id}.solution.xml"
        CommonRoadSolutionWriter(solution).write_to_file(
            str(args.output_folder), filename=solution_file_name, overwrite=True
        )

    return scenario_container


@pipeline_map()
def pipeline_assign_tags_to_scenario(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Find applicable tags for the scenario. Preserves existing tags and guarantees that the tags attribute of the scenario is set.

    :param ctx: The pipeline execution context.
    :param scenario_container: The scenario for which tags will be selected. If the container, also has a planning problem set attached, tags for the planning problems will also be assigned.

    :returns: The updated scenario container.
    """
    commonroad_scenario = scenario_container.scenario
    if commonroad_scenario.tags is None:
        commonroad_scenario.tags = set()

    scenario_tags = find_applicable_tags_for_scenario(commonroad_scenario)
    commonroad_scenario.tags.update(scenario_tags)

    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is not None:
        planning_problem_tags = find_applicable_tags_for_planning_problem_set(
            commonroad_scenario, planning_problem_set
        )
        commonroad_scenario.tags.update(planning_problem_tags)

    return scenario_container


@pipeline_map()
def pipeline_add_metadata_to_scenario(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Populate the metadata of the scenario with the values in the scenario factory config that is attached to the pipeline context. Will override existing metadata, except tags.
    """
    scenario_factory_config = ctx.get_scenario_factory_config()

    commonroad_scenario = scenario_container.scenario

    commonroad_scenario.author = scenario_factory_config.author
    commonroad_scenario.affiliation = scenario_factory_config.affiliation
    commonroad_scenario.source = scenario_factory_config.source

    if not isinstance(commonroad_scenario.tags, set):
        commonroad_scenario.tags = set()

    commonroad_scenario.tags.update(scenario_factory_config.tags)

    return scenario_container


@pipeline_map()
def pipeline_remove_colliding_dynamic_obstacles(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Remove all dynamic obstacles that are part of a collision from the scenario in :param:`scenario_container`
    """
    commonroad_scenario = scenario_container.scenario
    deleted_obstacles = delete_colliding_obstacles_from_scenario(commonroad_scenario, all=True)
    if len(deleted_obstacles) > 0:
        _LOGGER.debug(
            "Removed %s obstacles from scenario %s because they are involved in a collision with another dynamic obstacle",
            len(deleted_obstacles),
            commonroad_scenario.scenario_id,
        )
    return scenario_container
