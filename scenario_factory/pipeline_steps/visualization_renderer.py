from pathlib import Path

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.visualization.draw_params import MPDrawParams
from commonroad.visualization.drawable import IDrawable
from commonroad.visualization.mp_renderer import MPRenderer

from scenario_factory.pipeline import PipelineContext, PipelineStepExecutionMode, pipeline_map
from scenario_factory.scenario_container import ScenarioContainer
from scenario_factory.utils import get_scenario_final_time_step, get_scenario_start_time_step


@pipeline_map(mode=PipelineStepExecutionMode.PARALLEL)
def pipeline_render_commonroad_scenario(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    output_path: Path,
) -> ScenarioContainer:
    """
    Pipeline step for visualizing a CommonRoad scenario as a video file (gif).

    :param ctx: PipelineContext object used for logging and shared resources during execution.
    :param scenario_container: ScenarioContainer holding the CommonRoad scenario to be rendered.
    :param output_path: The folder where the video will be saved.

    :return: The unchanged ScenarioContainer after rendering is complete.
    """
    scenario = scenario_container.scenario

    # calculate the time frame
    start_time = get_scenario_start_time_step(scenario)
    end_time = get_scenario_final_time_step(scenario)

    # DrawParams config
    draw_params = MPDrawParams()
    draw_params.time_begin = start_time
    draw_params.time_end = end_time
    draw_params.dynamic_obstacle.show_label = False
    draw_params.dynamic_obstacle.draw_icon = True
    draw_params.dynamic_obstacle.draw_shape = True

    rnd = MPRenderer()
    output_file = output_path / f"{scenario.scenario_id}.gif"

    # `MPRenderer.create_video` requires a list of all objects that should be included in the video.
    # Since some objects (e.g., planning problem sets) are optional on a scenario container
    # they are conditionally included for visualization.
    rnd_obj_list: list[IDrawable] = [scenario]

    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is not None:
        rnd_obj_list.append(planning_problem_set)

    rnd.create_video(
        rnd_obj_list,
        str(output_file),
        draw_params=draw_params,
        # Explicitly set the dt in case the `MPRenderer` cannot auto-detect it.
        # dt must be in [ms], but scenario dt is in [s]. Therefore, it must be scaled with 1000.
        dt=scenario.dt * 1000.0,
    )

    return scenario_container
