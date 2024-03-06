from pathlib import Path

from scenario_factory.globetrotter.clustering import generate_intersections
from scenario_factory.globetrotter.globetrotter_io import commonroad_parse, save_intersections


def run_globetrotter(commonroad_folder: Path) -> Path:
    """
    Run the Globetrotter algorithm on the CommonRoad files.

    Args:
        commonroad_folder (Path): Path to the folder containing the CommonRoad files.

    Returns:
        Path: Path to the folder containing the generated Globetrotter files.
    """
    output_folder = commonroad_folder.parent.joinpath("globetrotter")
    output_folder.mkdir(parents=True, exist_ok=True)
    commonroad_files = commonroad_folder.glob("*.xml")

    # globetrotter
    for commonroad_file in commonroad_files:
        print(f"======== {commonroad_file.stem} ========")
        scenario, forking_points = commonroad_parse(commonroad_file)
        intersections, clustering_result = generate_intersections(scenario, forking_points)

        output_dir = commonroad_file.parent.joinpath("..", "globetrotter", commonroad_file.stem)
        output_dir.mkdir(parents=True, exist_ok=True)
        save_intersections(intersections, output_dir, output_dir.stem)

    return output_folder
