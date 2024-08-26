import logging
import random
import shutil
import tempfile
from pathlib import Path

import click
import numpy as np
from crdesigner.map_conversion.sumo_map.config import SumoConfig

from scenario_factory.globetrotter.osm import LocalFileMapProvider, MapProvider, OsmApiMapProvider
from scenario_factory.globetrotter.region import Coordinates, RegionMetadata
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    ExtractOsmMapArguments,
    GenerateCommonRoadScenariosArguments,
    LoadRegionsFromCsvArguments,
    WriteScenarioToFileArguments,
    pipeline_add_metadata_to_scenario,
    pipeline_assign_tags_to_scenario,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_create_sumo_configuration_for_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_flatten,
    pipeline_generate_ego_scenarios,
    pipeline_load_regions_from_csv,
    pipeline_simulate_scenario,
    pipeline_verify_and_repair_commonroad_scenario,
    pipeline_write_scenario_to_file,
)
from scenario_factory.scenario_config import ScenarioFactoryConfig


def _select_osm_map_provider(radius: float, maps_path: Path) -> MapProvider:
    # radius > 0.8 would result in an error in the OsmApiMapProvider, because the OSM API limits the amount of data we can download
    if radius > 0.8:
        return LocalFileMapProvider(maps_path)
    else:
        return OsmApiMapProvider()


@click.command()
@click.option(
    "--cities",
    "-c",
    type=click.Path(exists=True, readable=True),
    default="./files/cities_selected.csv",
    help="CSV file containing the cities, for which the scenarios will be generated",
)
@click.option("--coords", default=None)
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
def generate(cities: str, coords: str, output: str, maps: str, radius: float, seed: int):
    output_path = Path(output)
    if not output_path.exists():
        output_path.mkdir(parents=True)
    root_logger = logging.getLogger("scenario_factory")
    root_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    root_logger.addHandler(handler)

    sumo_config = SumoConfig()
    sumo_config.simulation_steps = 300
    sumo_config.random_seed = seed
    sumo_config.random_seed_trip_generation = seed
    random.seed(seed)
    np.random.seed(seed)

    scenario_config = ScenarioFactoryConfig(cr_scenario_time_steps=150)
    map_provider = _select_osm_map_provider(radius, Path(maps))

    temp_dir = Path(tempfile.mkdtemp())
    ctx = PipelineContext(temp_dir, scenario_config=scenario_config, sumo_config=sumo_config)
    pipeline = Pipeline(ctx)
    if coords is not None:
        coordinates = Coordinates.from_str(coords)
        region = RegionMetadata.from_coordinates(coordinates)
        pipeline.populate(lambda _: [region])
    else:
        pipeline.populate(pipeline_load_regions_from_csv(LoadRegionsFromCsvArguments(Path(cities))))
    root_logger.info(f"Processing {len(pipeline.state)} regions")
    pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(map_provider, radius=radius)))
    pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
    pipeline.map(pipeline_verify_and_repair_commonroad_scenario)
    pipeline.map(pipeline_extract_intersections)
    pipeline.reduce(pipeline_flatten)
    root_logger.info(f"Found {len(pipeline.state)} interesting intersections")
    pipeline.map(pipeline_add_metadata_to_scenario)
    pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario, num_processes=16)
    pipeline.reduce(pipeline_flatten)
    pipeline.map(pipeline_simulate_scenario, num_processes=16)
    root_logger.info("Generating ego scenarios from simulated scenarios")
    pipeline.map(
        pipeline_generate_ego_scenarios(
            GenerateCommonRoadScenariosArguments(create_noninteractive=True, create_interactive=True)
        ),
        num_processes=16,
    )
    pipeline.reduce(pipeline_flatten)
    root_logger.info(f"Successfully generated {len(pipeline.state)} scenarios")
    pipeline.map(pipeline_assign_tags_to_scenario)
    pipeline.map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    root_logger.info(f"Successfully generated {len(pipeline.state)} scenarios")
    pipeline.report_results()

    if len(pipeline.errors) == 0:
        shutil.rmtree(temp_dir)
    else:
        root_logger.info(
            f"Scenario factory encountered {len(pipeline.errors)} errors. For debugging purposes the temprorary directory at {temp_dir.absolute()} will not be removed."
        )


@click.command()
@click.option(
    "--cities",
    type=click.Path(exists=True, readable=True),
    default="./files/cities_selected.csv",
    help="CSV file containing the cities, for which the scenarios will be generated",
)
@click.option("--coords", default=None)
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
def globetrotter(cities, coords, output, maps, radius):
    output_path = Path(output)
    if not output_path.exists():
        output_path.mkdir(parents=True)

    root_logger = logging.getLogger("scenario_factory")
    root_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    root_logger.addHandler(handler)

    map_provider = _select_osm_map_provider(radius, Path(maps))

    temp_dir = Path(tempfile.mkdtemp(prefix="scenario_factory_tmp"))
    ctx = PipelineContext(temp_dir)
    pipeline = Pipeline(ctx)
    if coords is not None:
        coordinates = Coordinates.from_str(coords)
        region = RegionMetadata.from_coordinates(coordinates)
        pipeline.populate(lambda _: [region])
    else:
        pipeline.populate(pipeline_load_regions_from_csv(LoadRegionsFromCsvArguments(Path(cities))))
    root_logger.info(f"Processing {len(pipeline.state)} regions")
    pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(map_provider, radius=radius)))
    pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
    pipeline.map(pipeline_verify_and_repair_commonroad_scenario)
    root_logger.info("Extracted and Repaired OpenStreetMap")
    pipeline.map(pipeline_extract_intersections)
    pipeline.reduce(pipeline_flatten)
    pipeline.map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    root_logger.info(f"Found {len(pipeline.state)} interesting intersections")
    pipeline.report_results()
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    generate()
