import random
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from crdesigner.map_conversion.sumo_map.config import SumoConfig

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
    pipeline_generate_ego_scenarios,
    pipeline_load_plain_cities_from_csv,
    pipeline_simulate_scenario,
)
from scenario_factory.pipeline_steps.utils import WriteScenarioToFileArguments, pipeline_write_scenario_to_file

output_path = Path(".")
cities_file = Path("cities_selected.csv")
input_maps_folder = Path("input_maps")
radius = 0.3
seed = 10

sumo_config = SumoConfig()
sumo_config.simulation_steps = 600
sumo_config.random_seed = seed
sumo_config.random_seed_trip_generation = seed
random.seed(seed)
np.random.seed(seed)

with TemporaryDirectory() as temp_dir:
    ctx = PipelineContext(Path(temp_dir), sumo_config=sumo_config)
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
        pipeline_generate_ego_scenarios(
            GenerateCommonRoadScenariosArguments(create_noninteractive=True, create_interactive=True)
        ),
        num_processes=4,
    )
    pipeline.reduce(pipeline_flatten)
    pipeline.map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    pipeline.report_results()
