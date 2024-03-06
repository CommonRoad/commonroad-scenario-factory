from pathlib import Path

import matplotlib.pyplot as plt
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.visualization.mp_renderer import MPRenderer


def generate_photos(input_folder: Path) -> None:
    """
    Generate photos from CommonRoad scenarios.

    Args:
        input_folder (Path): Path to the folder containing the CommonRoad files.
    """
    files = input_folder.rglob("*.xml")

    for file in files:
        scenario, _ = CommonRoadFileReader(file).open()
        # Plot scenario
        plt.figure(figsize=(20, 20))
        renderer = MPRenderer()
        renderer.draw_scenario(scenario)
        renderer.render()
        plt.show()


def generate_videos(input_folder: Path, video_folder: Path) -> None:
    """
    Generate videos from CommonRoad scenarios.

    Args:
        input_folder (Path): Path to the folder containing the CommonRoad files.
        video_folder (Path): Path to the folder where the videos will be saved.
    """
    files = input_folder.rglob("*.xml")
    video_folder.mkdir(parents=True, exist_ok=True)

    for file in sorted(files):
        scenario, planning_problems = CommonRoadFileReader(file).open()
        planning_problems = [v for k, v in planning_problems.planning_problem_dict.items()]
        assert len(planning_problems) == 1
        planning_problem = planning_problems[0]
        # Plot scenario
        plt.figure(figsize=(20, 20))
        renderer = MPRenderer()
        renderer.draw_scenario(scenario)
        renderer.draw_planning_problem(planning_problem)
        renderer.draw_params["time_begin"] = 0
        renderer.draw_params["time_end"] = 150
        # renderer.render()

        # save as video
        file_path = video_folder.joinpath(file.stem + ".mp4")
        renderer.create_video([scenario, planning_problem], str(file_path))
