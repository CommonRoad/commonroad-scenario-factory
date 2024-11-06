from pathlib import Path
from commonroad.visualization.draw_params import MPDrawParams
from commonroad.visualization.mp_renderer import MPRenderer
from scenario_factory.pipeline import (PipelineContext,PipelineStep,PipelineStepExecutionMode,PipelineStepType,)

#Render class
def pipeline_render_commonroad_scenario(
    output_path: Path, fps: int = 5, time_steps: int = 25
) -> PipelineStep:
    """
    Pipeline step for visualizing the scenario as a video file.
    Args:
        output_path: The path where the visualization should be saved.
        fps: Frames per second for the GIF.
        time_steps: The number of time steps for the animation.
    """

    # Render the scenario as a video and save it in the output folder
    def render_step(context: PipelineContext, scenario_container):
        scenario = scenario_container.scenario

        # DrawParams config
        draw_params = MPDrawParams()
        draw_params.time_begin = 0
        draw_params.time_end = time_steps  # dynamic end-time
        draw_params.fps = fps  # dynamic FPS
        draw_params.dynamic_obstacle.show_label = False
        draw_params.dynamic_obstacle.draw_icon = True
        draw_params.dynamic_obstacle.draw_shape = True

        rnd = MPRenderer()
        output_file = output_path / f"{scenario.scenario_id}.gif"

        rnd.create_video([scenario], str(output_file), draw_params=draw_params)

    return PipelineStep(
        render_step, type=PipelineStepType.MAP, mode=PipelineStepExecutionMode.SEQUENTIAL
    )
