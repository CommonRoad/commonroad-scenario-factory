from pathlib import Path
from scenario_factory.globetrotter.globetrotter_io import commonroad_parse, save_intersections
from scenario_factory.globetrotter.clustering import generate_intersections

commonroad_files = Path("commonroad").glob('*.xml')

for commonroad_file in commonroad_files:
    print(f"======== {commonroad_file.stem} ========")
    # try:
    scenario, forking_points = commonroad_parse(commonroad_file)
    # except AssertionError as e:
    #     print(e)
    #     continue

    intersections, clustering_result = generate_intersections(scenario, forking_points)

    output_dir = commonroad_file.parent.joinpath("..", "globetrotter", commonroad_file.stem)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_intersections(intersections, output_dir, output_dir.stem)
