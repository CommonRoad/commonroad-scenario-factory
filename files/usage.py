import random
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from scenario_factory.globetrotter.region import load_regions_from_csv
from scenario_factory.pipeline import PipelineContext
from scenario_factory.pipeline_steps import pipeline_simulate_scenario_with_sumo
from scenario_factory.pipeline_steps.utils import (
    WriteScenarioToFileArguments,
    pipeline_add_metadata_to_scenario,
    pipeline_assign_tags_to_scenario,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipelines import create_globetrotter_pipeline, create_scenario_generation_pipeline
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.utils import select_osm_map_provider

output_path = Path(".")
cities_file = Path("cities_selected.csv")
input_maps_folder = Path("input_maps")
radius = 0.3
seed = 10

random.seed(seed)
np.random.seed(seed)

scenario_factory_config = ScenarioFactoryConfig(seed=seed, simulation_steps=600)

with TemporaryDirectory() as temp_dir:
    ctx = PipelineContext(Path(temp_dir), scenario_factory_config)

    map_provider = select_osm_map_provider(radius, input_maps_folder)

    base_pipeline = (
        create_globetrotter_pipeline(radius, map_provider)
        .map(pipeline_add_metadata_to_scenario)
        .map(pipeline_simulate_scenario_with_sumo)
    )

    scenario_generation_pipeline = create_scenario_generation_pipeline(
        scenario_factory_config.criterions, scenario_factory_config.filters
    )

    pipeline = (
        base_pipeline.chain(scenario_generation_pipeline)
        .map(pipeline_assign_tags_to_scenario)
        .map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    )

    inputs = load_regions_from_csv(cities_file)
    result = pipeline.execute(inputs, ctx)
