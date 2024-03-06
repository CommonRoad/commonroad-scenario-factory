from pathlib import Path

from scenario_factory.pipeline.bounding_box_coordinates import update_cities_file
from scenario_factory.pipeline.conversion_to_commonroad import convert_to_osm_files
from scenario_factory.pipeline.generate_scenarios import generate_scenarios
from scenario_factory.pipeline.osm_map_extraction import extract_osm_maps
from scenario_factory.pipeline.run_globetrotter import run_globetrotter
from scenario_factory.pipeline.visualize import generate_videos

cities_file = Path("cities_selected.csv")
input_maps_folder = Path("input_maps")
update_cities_file(cities_file, 0.3, True)
extracted_maps_folder = extract_osm_maps(cities_file, input_maps_folder, True)
commonroad_folder = convert_to_osm_files(extracted_maps_folder)
globetrotter_folder = run_globetrotter(commonroad_folder)
output_path = generate_scenarios(globetrotter_folder, number_of_processes=16)
generate_videos(output_path.joinpath("noninteractive"), output_path.joinpath("videos"))
