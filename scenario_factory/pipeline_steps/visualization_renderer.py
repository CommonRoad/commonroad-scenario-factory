from dataclasses import dataclass
from pathlib import Path

from commonroad.visualization.draw_params import MPDrawParams
from commonroad.visualization.mp_renderer import MPRenderer

from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStep,
    PipelineStepArguments,
    PipelineStepExecutionMode,
    pipeline_map_with_args,
)
from scenario_factory.scenario_types import ScenarioContainer


@dataclass
class RenderCommonRoadScenarioArgs(PipelineStepArguments):
    output_path: Path
    fps: int = 5
    time_steps: int = 25


@pipeline_map_with_args(mode=PipelineStepExecutionMode.PARALLEL)
def pipeline_render_commonroad_scenario(
    args: RenderCommonRoadScenarioArgs, ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Pipeline step for visualizing a CommonRoad scenario as a video file.

    :param args: Instance of RenderCommonRoadScenarioArgs containing parameters such as the output path, FPS, and time steps.
    :param ctx: PipelineContext object used for logging and shared resources during execution.
    :param scenario_container: ScenarioContainer holding the CommonRoad scenario to be rendered.
    :return: The unchanged ScenarioContainer after rendering is complete.
    """
    scenario = scenario_container.scenario

    # DrawParams config
    draw_params = MPDrawParams()
    draw_params.time_begin = 0
    draw_params.time_end = args.time_steps
    draw_params.fps = args.fps
    draw_params.dynamic_obstacle.show_label = False
    draw_params.dynamic_obstacle.draw_icon = True
    draw_params.dynamic_obstacle.draw_shape = True

    rnd = MPRenderer()
    output_file = args.output_path / f"{scenario.scenario_id}.gif"

    rnd.create_video([scenario], str(output_file), draw_params=draw_params)

    return scenario_container
