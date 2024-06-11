import logging
from pathlib import Path

from scenario_factory.globetrotter.globetrotter_io import extract_forking_points
from scenario_factory.pipeline.bounding_box_coordinates import (
    ComputeBoundingBoxForCityArguments,
    LoadCitiesFromFileArguments,
    compute_bounding_box_for_city,
    load_cities_from_file,
    write_cities_to_file,
)
from scenario_factory.pipeline.context import Pipeline, PipelineContext
from scenario_factory.pipeline.conversion_to_commonroad import convert_osm_file_to_commonroad_scenario
from scenario_factory.pipeline.generate_scenarios import generate_scenarios, simulate_scenario
from scenario_factory.pipeline.osm_map_extraction import ExractOsmMapArguments, extract_osm_map
from scenario_factory.pipeline.run_globetrotter import extract_intersections, write_intersection_to_file
from scenario_factory.pipeline.utils import flatten, keep
from scenario_factory.pipeline.visualize import generate_videos

logging.getLogger().setLevel(logging.DEBUG)

cities_file = Path("cities_selected.csv")
input_maps_folder = Path("input_maps")

ctx = PipelineContext(Path("."))
pipeline = Pipeline(ctx)

pipeline.populate(load_cities_from_file, LoadCitiesFromFileArguments(cities_file))
pipeline.map(compute_bounding_box_for_city, ComputeBoundingBoxForCityArguments(radius=0.3))
# # pipeline.drain(write_cities_to_file)
pipeline.map(extract_osm_map, ExractOsmMapArguments(input_maps_folder, overwrite=True))
pipeline.map(convert_osm_file_to_commonroad_scenario)
pipeline.map(extract_forking_points)
pipeline.map(extract_intersections)
pipeline.reduce(flatten)
pipeline.map(write_intersection_to_file)
pipeline.map(simulate_scenario, num_processes=1)
# use the result, to make sure that everything is evaluated
pipeline.drain(keep)
pipeline.report_results()

# output_path = generate_scenarios(ctx.get_output_folder("globetrotter"), number_of_processes=16)
# generate_videos(output_path.joinpath("noninteractive"), output_path.joinpath("videos"))
