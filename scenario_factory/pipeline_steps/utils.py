__all__ = [
    "WriteScenarioToFileArguments",
    "pipeline_write_scenario_to_file",
    "pipeline_assign_tags_to_scenario",
    "pipeline_add_metadata_to_scenario",
    "pipeline_remove_colliding_dynamic_obstacles",
]

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.common.solution import CommonRoadSolutionWriter, List
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad_crime.data_structure.base import CriMeBase
from commonroad_crime.measure import TTCStar
from commonroad_labeling.criticality.computer.cm_computer import CMComputer
from commonroad_labeling.criticality.input_output.crime_output import (
    parse_crime_output_dir_to_object,
)
from commonroad_labeling.criticality.trajectory_inserter.trajectory_inserter import (
    TrajectoryInserter,
)

from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map,
    pipeline_map_with_args,
)
from scenario_factory.pipeline.pipeline_step import pipeline_fold
from scenario_factory.scenario_generation import delete_colliding_obstacles_from_scenario
from scenario_factory.scenario_types import (
    ScenarioContainer,
    ScenarioWithCriticalityData,
    ScenarioWithPlanningProblemSet,
    is_scenario_with_planning_problem_set,
    is_scenario_with_solution,
)
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
    planning_problem_set = (
        scenario_container.planning_problem_set
        if is_scenario_with_planning_problem_set(scenario_container)
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

    if is_scenario_with_solution(scenario_container):
        solution = scenario_container.solution
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

    if is_scenario_with_planning_problem_set(scenario_container):
        planning_problem_set = scenario_container.planning_problem_set
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


@dataclass
class ComputeCriticalityMetricsArgs(PipelineStepArguments):
    metrics: Sequence[type[CriMeBase]] = field(default_factory=lambda: [TTCStar])


@pipeline_map_with_args()
def pipeline_compute_criticality_metrics(
    args: ComputeCriticalityMetricsArgs,
    ctx: PipelineContext,
    scenario_container: ScenarioWithPlanningProblemSet,
) -> ScenarioWithCriticalityData:
    trajectory_inserter = TrajectoryInserter()
    scenario_with_ego_trajectory, ego_id = trajectory_inserter.insert_ego_trajectory(
        scenario_container.scenario, scenario_container.planning_problem_set
    )

    runtime_directory_path = ctx.get_temporary_folder("crime") / str(
        scenario_container.scenario.scenario_id
    )
    runtime_directory = str(runtime_directory_path.absolute())
    # `metrics` argument of CMComputer has the wrong type annotation
    cm_computer = CMComputer(metrics=args.metrics)  # type: ignore
    cm_computer.compute_metrics_for_id(scenario_with_ego_trajectory, ego_id, "", runtime_directory)

    crime_metrics = parse_crime_output_dir_to_object(runtime_directory)
    if len(crime_metrics) > 1:
        raise RuntimeError(
            f"Found {len(crime_metrics)} CriMe metric files for scenario {scenario_container.scenario}, but only one can be processed. This means there is a duplicated scenario ID."
        )

    if len(crime_metrics) < 1:
        raise RuntimeError()

    crime_metric_data_of_scenario = crime_metrics[0]

    return ScenarioWithCriticalityData(
        scenario_container.scenario,
        scenario_container.planning_problem_set,
        crime_metric_data_of_scenario,
    )
