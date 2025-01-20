import logging
import tempfile
from pathlib import Path
from typing import Optional

import click

from scenario_factory.globetrotter import Coordinates, RegionMetadata, load_regions_from_csv
from scenario_factory.pipeline import PipelineContext
from scenario_factory.pipeline_steps import (
    pipeline_add_metadata_to_scenario,
    pipeline_assign_tags_to_scenario,
    pipeline_render_commonroad_scenario,
    pipeline_simulate_scenario_with_ots,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipelines import (
    create_globetrotter_pipeline,
    create_scenario_generation_pipeline,
    select_osm_map_provider,
)
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.simulation import SimulationConfig, SimulationMode
from scenario_factory.utils import configure_root_logger


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
    "--radius",
    "-r",
    type=float,
    default=0.3,
    help="The radius in which intersections will be selected from each city",
)
@click.option("--seed", type=int, default=12345)
@click.option("--simulation-steps", type=int, default=1000)
def generate(
    cities: str,
    coords: Optional[str],
    output: str,
    maps: str,
    radius: float,
    seed: int,
    simulation_steps: int,
):
    output_path = Path(output)
    if not output_path.exists():
        output_path.mkdir(parents=True)
    root_logger = configure_root_logger(logging.WARNING)

    scenario_config = ScenarioFactoryConfig(
        seed=seed, cr_scenario_time_steps=200, source="Scenario Factory 2.0 - OTS"
    )
    map_provider = select_osm_map_provider(radius, Path(maps))
    simulation_config = SimulationConfig(
        mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=simulation_steps
    )

    base_pipeline = (
        create_globetrotter_pipeline(radius, map_provider)
        .map(pipeline_add_metadata_to_scenario)
        .map(pipeline_simulate_scenario_with_ots(simulation_config))
    )

    scenario_generation_pipeline = create_scenario_generation_pipeline(
        scenario_config.criterions, scenario_config.filters
    )

    pipeline = (
        base_pipeline.chain(scenario_generation_pipeline)
        .map(pipeline_assign_tags_to_scenario)
        .map(pipeline_render_commonroad_scenario(output_path, fps=5))
        .map(pipeline_write_scenario_to_file(output_path))
    )
    if coords is not None:
        coordinates = Coordinates.from_str(coords)
        region = RegionMetadata.from_coordinates(coordinates)
        inputs = [region]
    else:
        inputs = list(load_regions_from_csv(Path(cities)))

    with tempfile.TemporaryDirectory(prefix="scenario_factory") as temp_dir:
        ctx = PipelineContext(Path(temp_dir), scenario_factory_config=scenario_config)
        result = pipeline.execute(inputs, ctx, num_processes=4)

    result.print_cum_time_per_step()
    root_logger.info(
        "Sucessfully generated %s scenarios in %ss",
        len(result.values),
        round(result.exec_time_ns / 1000000000, 2),
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
    "--radius",
    "-r",
    type=float,
    default=0.3,
    help="The radius in which intersections will be selected from each city",
)
def globetrotter(cities, coords, output, maps, radius):
    output_path = Path(output)
    if not output_path.exists():
        output_path.mkdir(parents=True)

    root_logger = configure_root_logger(logging.WARNING)

    map_provider = select_osm_map_provider(radius, Path(maps))
    globetrotter_pipeline = create_globetrotter_pipeline(radius, map_provider)
    globetrotter_pipeline.map(pipeline_add_metadata_to_scenario)
    globetrotter_pipeline.map(pipeline_write_scenario_to_file(output_path))
    inputs = None
    if coords is not None:
        coordinates = Coordinates.from_str(coords)
        region = RegionMetadata.from_coordinates(coordinates)
        inputs = [region]
    else:
        inputs = list(load_regions_from_csv(Path(cities)))

    with tempfile.TemporaryDirectory(prefix="scenario_factory") as temp_dir:
        ctx = PipelineContext(Path(temp_dir))
        execution_result = globetrotter_pipeline.execute(inputs, ctx)

    root_logger.info(
        "Sucessfully extracted %s intersections in %ss",
        len(execution_result.values),
        round(execution_result.exec_time_ns / 1000000000, 2),
    )


if __name__ == "__main__":
    generate()
