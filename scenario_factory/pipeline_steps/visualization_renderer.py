from pathlib import Path

from commonroad.visualization.draw_params import MPDrawParams
from commonroad.visualization.mp_renderer import MPRenderer

from scenario_factory.pipeline import PipelineContext, PipelineStepExecutionMode, pipeline_map
from scenario_factory.scenario_container import ScenarioContainer
from scenario_factory.utils import get_scenario_final_time_step, get_scenario_start_time_step


@pipeline_map(mode=PipelineStepExecutionMode.PARALLEL)
def pipeline_render_commonroad_scenario(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    output_path: Path,
    fps: int = 5,
) -> ScenarioContainer:
    """
    Pipeline step for visualizing a CommonRoad scenario as a video file.

    :param args: Instance of RenderCommonRoadScenarioArgs containing parameters such as the output path, FPS, and time steps.
    :param ctx: PipelineContext object used for logging and shared resources during execution.
    :param scenario_container: ScenarioContainer holding the CommonRoad scenario to be rendered.
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
    draw_params.fps = fps
    draw_params.dynamic_obstacle.show_label = False
    draw_params.dynamic_obstacle.draw_icon = True
    draw_params.dynamic_obstacle.draw_shape = True

    rnd = MPRenderer()
    output_file = output_path / f"{scenario.scenario_id}.gif"

    rnd.create_video([scenario], str(output_file), draw_params=draw_params)

    return scenario_container
