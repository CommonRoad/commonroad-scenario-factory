import random
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from crdesigner.map_conversion.sumo_map.config import SumoConfig

from scenario_factory.globetrotter.osm import LocalFileMapProvider
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    ExtractOsmMapArguments,
    GenerateCommonRoadScenariosArguments,
    LoadRegionsFromCsvArguments,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_generate_ego_scenarios,
    pipeline_load_regions_from_csv,
    pipeline_simulate_scenario_with_sumo,
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

    local_map_provider = LocalFileMapProvider(Path(input_maps_folder))

    pipeline.populate(pipeline_load_regions_from_csv(LoadRegionsFromCsvArguments(Path(cities_file))))
    pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(local_map_provider, radius=radius)))
    pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
    pipeline.map(pipeline_extract_intersections)
    pipeline.map(pipeline_simulate_scenario_with_sumo)
    pipeline.map(
        pipeline_generate_ego_scenarios(GenerateCommonRoadScenariosArguments()),
        num_processes=4,
    )
    pipeline.map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    pipeline.report_results()
