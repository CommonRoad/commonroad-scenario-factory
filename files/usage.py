from pathlib import Path

from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    ComputeBoundingBoxForCityArguments,
    ExtractOsmMapArguments,
    GenerateCommonRoadScenariosArguments,
    LoadCitiesFromCsvArguments,
    pipeline_compute_bounding_box_for_city,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_create_sumo_configuration_for_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_flatten,
    pipeline_generate_cr_scenarios,
    pipeline_load_plain_cities_from_csv,
    pipeline_simulate_scenario,
)

output_folder = Path(".")
cities_file = Path("cities_selected.csv")
input_maps_folder = Path("input_maps")
radius = 0.3

ctx = PipelineContext(output_folder)
pipeline = Pipeline(ctx)

pipeline.populate(pipeline_load_plain_cities_from_csv(LoadCitiesFromCsvArguments(Path(cities_file))))
pipeline.map(pipeline_compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius)))
pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(Path(input_maps_folder), overwrite=True)))
pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
pipeline.map(pipeline_extract_intersections)
pipeline.reduce(pipeline_flatten)
pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario)
pipeline.reduce(pipeline_flatten)
pipeline.map(pipeline_simulate_scenario)
pipeline.map(
    pipeline_generate_cr_scenarios(
        GenerateCommonRoadScenariosArguments(create_noninteractive=True, create_interactive=False)
    ),
    num_processes=4,
)
pipeline.report_results()
