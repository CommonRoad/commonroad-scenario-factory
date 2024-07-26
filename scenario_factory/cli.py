import logging
import random
import shutil
import tempfile
from pathlib import Path

import click
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
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipeline_steps.utils import WriteScenarioToFileArguments, pipeline_add_metadata_to_scenario
from scenario_factory.scenario_config import ScenarioFactoryConfig


@click.command()
@click.option(
    "--cities",
    "-c",
    type=click.Path(exists=True, readable=True),
    default="./files/cities_selected.csv",
    help="CSV file containing the cities, for which the scenarios will be generated",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False),
    default="./files/output",
    help="Directory where outputs will be written to",
)
@click.option(
    "--maps",
    "-m",
    type=click.Path(readable=True),
    default="./files/input_maps",
    help="Directory that will be used by osmium to extract OSM maps",
)
@click.option(
    "--radius", "-r", type=float, default=0.3, help="The radius in which intersections will be selected from each city"
)
@click.option("--seed", type=int, default=12345)
def generate(cities: str, output: str, maps: str, radius: float, seed: int):
    output_path = Path(output)
    if not output_path.exists():
        output_path.mkdir(parents=True)
    logger = logging.getLogger("scenario_factory")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)

    sumo_config = SumoConfig()
    sumo_config.simulation_steps = 600
    sumo_config.random_seed = seed
    sumo_config.random_seed_trip_generation = seed
    random.seed(seed)
    np.random.seed(seed)

    scenario_config = ScenarioFactoryConfig(cr_scenario_time_steps=150)

    temp_dir = Path(tempfile.mkdtemp())
    ctx = PipelineContext(temp_dir, scenario_config=scenario_config, sumo_config=sumo_config)
    pipeline = Pipeline(ctx)
    pipeline.populate(pipeline_load_plain_cities_from_csv(LoadCitiesFromCsvArguments(Path(cities))))
    logger.info(f"Processing {len(pipeline.state)} cities")
    pipeline.map(pipeline_compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius)))
    pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(Path(maps), overwrite=True)))
    pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
    pipeline.map(pipeline_extract_intersections)
    pipeline.reduce(pipeline_flatten)
    logger.info(f"Found {len(pipeline.state)} interesting intersections")
    pipeline.map(pipeline_add_metadata_to_scenario)
    pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario, num_processes=16)
    pipeline.reduce(pipeline_flatten)
    pipeline.map(pipeline_simulate_scenario, num_processes=16)
    logger.info("Generating ego scenarios from simulated scenarios")
    pipeline.map(
        pipeline_generate_ego_scenarios(
            GenerateCommonRoadScenariosArguments(create_noninteractive=True, create_interactive=True)
        ),
        num_processes=16,
    )
    pipeline.reduce(pipeline_flatten)
    logger.info(f"Successfully generated {len(pipeline.state)} scenarios")
    pipeline.map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    pipeline.report_results()

    if len(pipeline.errors) == 0:
        shutil.rmtree(temp_dir)
    else:
        logger.info(
            f"Scenario factory encountered {len(pipeline.errors)} errors. For debugging purposes the temprorary directory at {temp_dir.absolute()} will not be removed."
        )


if __name__ == "__main__":
    generate()
