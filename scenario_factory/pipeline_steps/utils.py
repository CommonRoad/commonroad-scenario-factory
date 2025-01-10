__all__ = [
    "pipeline_write_scenario_to_file",
    "pipeline_assign_tags_to_scenario",
    "pipeline_add_metadata_to_scenario",
    "pipeline_remove_colliding_dynamic_obstacles",
]

import logging
from pathlib import Path
from typing import Optional, Sequence, Union

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.common.solution import CommonRoadSolutionWriter, Solution
from commonroad.common.util import Interval
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.obstacle import DynamicObstacle

from scenario_factory.pipeline import (
    PipelineContext,
    pipeline_fold,
    pipeline_map,
)
from scenario_factory.scenario_container import (
    ScenarioContainer,
)
from scenario_factory.scenario_generation import delete_colliding_obstacles_from_scenario
from scenario_factory.tags import (
    find_applicable_tags_for_planning_problem_set,
    find_applicable_tags_for_scenario,
)
from scenario_factory.utils import (
    calculate_deviation_between_states,
    calculate_driven_distance_of_dynamic_obstacle,
    copy_scenario,
    create_dynamic_obstacle_from_planning_problem_solution,
    create_planning_problem_solution_for_ego_vehicle,
)
from scenario_factory.utils.scenario import (
    UniqueIncrementalIdAllocator,
    get_scenario_final_time_step,
)

_LOGGER = logging.getLogger(__name__)


@pipeline_map()
def pipeline_write_scenario_to_file(
    ctx: PipelineContext, scenario_container: ScenarioContainer, output_folder: Union[str, Path]
) -> ScenarioContainer:
    """
    Write a CommonRoad scenario to a file in the `args.output_folder`. If the `scenario_container` also holds a planning problem set or a planning problem solution, they will also be written to disk.
    """
    output_folder = output_folder if isinstance(output_folder, Path) else Path(output_folder)
    output_folder.mkdir(exist_ok=True)

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

    scenario_file_path = output_folder.joinpath(f"{commonroad_scenario.scenario_id}.cr.xml")
    CommonRoadFileWriter(commonroad_scenario, planning_problem_set, tags=tags).write_to_file(
        str(scenario_file_path), overwrite_existing_file=OverwriteExistingFile.ALWAYS
    )

    solution = scenario_container.get_attachment(Solution)
    if solution is not None:
        solution_file_name = f"{solution.scenario_id}.solution.xml"
        CommonRoadSolutionWriter(solution).write_to_file(
            str(output_folder), filename=solution_file_name, overwrite=True
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


@pipeline_map()
def pipeline_insert_ego_vehicle_solutions_into_scenario(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Insert the ego vehicles of a solution into the scenario as new dynamic obstacles.

    Counterpart of `pipeline_extract_ego_vehicle_from_scenario`.

    :param scenario_container: A scenario container with a planning problem set and solution attachment.
    :returns: A copy of the scenario in a new scenario container, with the ego vehicle from the solution as dynamic obstacle in the scenario.
    """
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            "Cannot insert ego vehicle trajectory into scenario: scenario container does not contain a planning problem set, but is required!"
        )

    solution = scenario_container.get_attachment(Solution)
    if solution is None:
        raise ValueError(
            "Cannot insert ego vehicle trajectory into scenario: scenario container does not contain a solution, but is required!"
        )

    new_scenario = copy_scenario(
        scenario_container.scenario,
    )
    for planning_problem_solution in solution.planning_problem_solutions:
        dynamic_obstacle = create_dynamic_obstacle_from_planning_problem_solution(
            planning_problem_solution
        )

        planning_problem_id = planning_problem_solution.planning_problem_id
        if planning_problem_id not in planning_problem_set.planning_problem_dict:
            planning_problem_ids = [
                str(planning_problem_id)
                for planning_problem_id in planning_problem_set.planning_problem_dict
            ]
            raise RuntimeError(
                f"Mismatch between planning problem set and solution: planning problem {planning_problem_id} is not part of the planning problem set. Available planning problems are '{','.join(planning_problem_ids)}'."
            )

        new_scenario.add_objects(dynamic_obstacle)

    return scenario_container.new_with_attachments(
        new_scenario,
    )


@pipeline_map()
def pipeline_extract_ego_vehicle_solutions_from_scenario(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Extract the ego vehicles of a planning problem from the scenario as new solutions.

    Counterpart of `pipeline_insert_ego_vehicle_from_scenario`.

    :param scenario_container: A scenario container with a planning problem set.
    :returns: A copy of the scenario in a new scenario container, with the ego vehicle from the solution as dynamic obstacle in the scenario.
    """
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            "Cannot extract ego vehicle from scenario: scenario container does not contain a planning problem set, but is required!"
        )

    new_scenario = copy_scenario(
        scenario_container.scenario,
    )
    planning_problem_solutions = []
    for planning_problem in planning_problem_set.planning_problem_dict.values():
        # The dynamic obstacles must have the same ID as the planning problem.
        obstacle = new_scenario.obstacle_by_id(planning_problem.planning_problem_id)
        if obstacle is None:
            raise RuntimeError(
                f"Cannot extract dynamic obstacle for planning problem {planning_problem.planning_problem_id} from scenario {scenario_container.scenario.scenario_id}: No dynamic obstacle with id {planning_problem.planning_problem_id} found!"
            )

        if not isinstance(obstacle, DynamicObstacle):
            raise RuntimeError(
                f"Cannot extract dynamic obstacle for planning problem {planning_problem.planning_problem_id} from scenario {scenario_container.scenario.scenario_id}: Obstacle with id {planning_problem.planning_problem_id} is not a dynamic obstacle but {type(obstacle)}."
            )

        # Sanity check if the initial states somewhat match
        state_deviation = calculate_deviation_between_states(
            planning_problem.initial_state, obstacle.initial_state
        )
        state_deviation_threshold = 2.0
        if state_deviation > state_deviation_threshold:
            raise RuntimeError(
                f"Cannot extract dynamic obstacle for planning problem {planning_problem.planning_problem_id} from scenario {scenario_container.scenario}: The initial position of the corresponding dynamic obstacle deviates too much from the planning problem: Deviates by {round(state_deviation, 2)}m, but maximum deviation is {round(state_deviation_threshold, 2)}m!"
            )

        planning_problem_solution = create_planning_problem_solution_for_ego_vehicle(
            obstacle, planning_problem
        )
        planning_problem_solutions.append(planning_problem_solution)
        new_scenario.remove_obstacle(obstacle)

    solution = Solution(scenario_container.scenario.scenario_id, planning_problem_solutions)

    return scenario_container.new_with_attachments(
        new_scenario, solution=solution, planning_problem_set=planning_problem_set
    )


@pipeline_map()
def pipeline_remove_parked_dynamic_obstacles(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Remove all dynamic obstacles from the scenario that are parked.
    A dynamic obstacle is identified as 'parked', if it travels less than 0.1 meters during the whole scenario.

    :param ctx: The pipeline context.
    :param scenario_container: The scenario container from which the parked dynamic obstacles will be removed. Will be modified in place.
    """
    commonroad_scenario = scenario_container.scenario

    num_removed = 0
    for dynamic_obstacle in commonroad_scenario.dynamic_obstacles:
        distance_driven = calculate_driven_distance_of_dynamic_obstacle(dynamic_obstacle)
        if distance_driven < 0.1:
            commonroad_scenario.remove_obstacle(dynamic_obstacle)
            num_removed += 1

    _LOGGER.debug(
        "Removed %s parked dynamic obstacles from scenario %s",
        num_removed,
        commonroad_scenario.scenario_id,
    )

    return scenario_container


@pipeline_fold()
def pipeline_assign_unique_incremental_scenario_ids(
    ctx: PipelineContext, scenario_containers: Sequence[ScenarioContainer]
) -> Sequence[ScenarioContainer]:
    """
    Take a sequence of scenario containers and create new `ScenarioID`s for each scenario, such
    that the new ids are unique and incrementing. E.g. DEU_Test-54 -> DEU_Test-1; DEU_Test-89 -> DEU_Test-2.

    :param ctx: Context for this pipeline execution.
    :param scenario_containers: Sequence of scenario containers for which the unique ids should be allocated. Scenarios and attachments will be modified in place.

    :returns: The modified sequence of scenario containers.
    """
    id_allocator = UniqueIncrementalIdAllocator()
    for scenario_container in scenario_containers:
        new_scenario_id = id_allocator.create_new_unique_id(scenario_container.scenario.scenario_id)

        scenario_container.scenario.scenario_id = new_scenario_id
        solution = scenario_container.get_attachment(Solution)
        if solution is not None:
            solution.scenario_id = new_scenario_id

    return scenario_containers


@pipeline_map()
def pipeline_extend_planning_problem_time_interval(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    scenario_length: Optional[int] = None,
) -> ScenarioContainer:
    """
    Extend the planning problem interval to cover the whole scenario duration.

    :param ctx: Context for this pipeline execution.
    :param scenario_container: `ScenarioContainer` with a `PlanningProblemSet` attachment. The `PlanningProblemSet` attachment will be modified in place.
    :param scenario_length: Optionally specify the length of the scenario. This length will be used to determine the end of the planning problem time interval. If it is not provided, it will be automatically determined from the scenario.

    :returns: The `ScenarioContainer` with the modified `PlanningProblemSet` attachment.
    """
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            f"Cannot extend goal time interval for planning problem for scenario {scenario_container.scenario.scenario_id}: The scenario container does not have a `PlanningProblemSet` attachment!"
        )

    if scenario_length is None:
        scenario_length = get_scenario_final_time_step(scenario_container.scenario)
    for planning_problem in planning_problem_set.planning_problem_dict.values():
        for state in planning_problem.goal.state_list:
            assert isinstance(
                state.time_step, Interval
            ), "The time step of a planning problem goal state must be an Interval. This is a bug!"
            final_time_step = max(scenario_length, state.time_step.end)
            state.time_step = Interval(0, final_time_step)

    return scenario_container
