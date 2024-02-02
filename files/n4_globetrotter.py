from pathlib import Path
from scenario_factory.globetrotter.globetrotter_io import commonroad_parse, save_intersections
from scenario_factory.globetrotter.clustering import generate_intersections
from commonroad.common.file_reader import CommonRoadFileReader

commonroad_files = Path("commonroad").glob('*.xml')

# globetrotter
for commonroad_file in commonroad_files:
    print(f"======== {commonroad_file.stem} ========")
    scenario, forking_points = commonroad_parse(commonroad_file)
    intersections, clustering_result = generate_intersections(scenario, forking_points)

    output_dir = commonroad_file.parent.joinpath("..", "globetrotter", commonroad_file.stem)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_intersections(intersections, output_dir, output_dir.stem)


# simple check
files = Path("globetrotter").rglob("*.xml")
files_total = 0
files_successful = 0
files_error = []
for file in files:
    print(f"========== Open {file.stem} ==========")
    files_total += 1
    try:
        scenario, _ = CommonRoadFileReader(file).open()
        files_successful += 1
    except:
        files_error.append(file.stem)

print(f"Files in total: {files_total}")
print(f"Files successful: {files_successful}")
