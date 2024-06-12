import logging
from pathlib import Path

from scenario_factory.globetrotter.globetrotter_io import extract_forking_points
from scenario_factory.pipeline.bounding_box_coordinates import (
    ComputeBoundingBoxForCityArguments,
    LoadCitiesFromCsvArguments,
    compute_bounding_box_for_city,
    load_cities_from_csv,
)
from scenario_factory.pipeline.context import Pipeline, PipelineContext
from scenario_factory.pipeline.conversion_to_commonroad import convert_osm_file_to_commonroad_scenario
from scenario_factory.pipeline.generate_scenarios import (
    GenerateRandomTrafficArguments,
    create_sumo_configuration_for_commonroad_scenario,
    generate_random_traffic,
    simulate_scenario,
)
from scenario_factory.pipeline.osm_map_extraction import ExtractOsmMapArguments, extract_osm_map
from scenario_factory.pipeline.run_globetrotter import (
    convert_intersection_to_commonroad_scenario,
    extract_intersections,
)
from scenario_factory.pipeline.utils import flatten

_logger = logging.getLogger("scenario_factory")
_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(fmt="%(asctime)s|%(name)s|%(levelname)s|%(message)s"))
_logger.addHandler(handler)

cities_file = Path("cities_selected.csv")
input_maps_folder = Path("input_maps")

ctx = PipelineContext(Path("."))
pipeline = Pipeline(ctx)

pipeline.populate(load_cities_from_csv(LoadCitiesFromCsvArguments(cities_file)))
pipeline.map(compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius=0.1)))
pipeline.map(extract_osm_map(ExtractOsmMapArguments(input_maps_folder, overwrite=True)))
pipeline.map(convert_osm_file_to_commonroad_scenario)
pipeline.map(extract_forking_points)
pipeline.map(extract_intersections)
pipeline.reduce(flatten)
# pipeline.map(write_intersection_to_file)
pipeline.map(convert_intersection_to_commonroad_scenario)
pipeline.map(create_sumo_configuration_for_commonroad_scenario)
pipeline.map(generate_random_traffic(GenerateRandomTrafficArguments(scenarios_per_map=2)))
pipeline.reduce(flatten)
pipeline.map(simulate_scenario)
# use the result, to make sure that everything is evaluated
pipeline.report_results()

# output_path = generate_scenarios(ctx.get_output_folder("globetrotter"), number_of_processes=16)
# generate_videos(output_path.joinpath("noninteractive"), output_path.joinpath("videos"))
