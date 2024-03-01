from commonroad.common.file_reader import CommonRoadFileReader
from pathlib import Path

import matplotlib.pyplot as plt
from commonroad.visualization.mp_renderer import MPRenderer

do_commonroad = False
do_globetrotter = False
do_output = True

# CommonRoad Map
if do_commonroad:
    files = Path("commonroad").rglob("*.xml")
    file = next(files)

    scenario, _ = CommonRoadFileReader(file).open()
    # Plot scenario
    plt.figure(figsize=(40, 40))
    renderer = MPRenderer()
    renderer.draw_scenario(scenario)
    renderer.render()
    plt.show()
    # TODO add functionality to draw bounding box of map extraction

# Globetrotter Extractions
if do_globetrotter:
    files = Path("globetrotter").rglob("*.xml")

    for file in files:
        scenario, _ = CommonRoadFileReader(file).open()
        # Plot scenario
        plt.figure(figsize=(20, 20))
        renderer = MPRenderer()
        renderer.draw_scenario(scenario)
        renderer.render()
        plt.show()

# Generate videos from non interactive scenarios
if do_output:
    files = Path("output").joinpath("noninteractive").rglob("*.xml")
    file = next(files)
    video_folder = file.parent.parent.joinpath("videos")
    video_folder.mkdir(parents=True, exist_ok=True)
    files = Path("output").joinpath("noninteractive").rglob("*.xml")

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
