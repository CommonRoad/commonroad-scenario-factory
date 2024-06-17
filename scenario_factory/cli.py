import logging
from pathlib import Path

import click

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
    GenerateCommonRoadScenariosArguments,
    GenerateRandomTrafficArguments,
    create_sumo_configuration_for_commonroad_scenario,
    generate_cr_scenarios,
    generate_random_traffic,
    simulate_scenario,
)
from scenario_factory.pipeline.osm_map_extraction import ExtractOsmMapArguments, extract_osm_map
from scenario_factory.pipeline.run_globetrotter import (
    convert_intersection_to_commonroad_scenario,
    extract_intersections,
)
from scenario_factory.pipeline.utils import flatten


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
    type=click.Path(),
    default="./files",
    help="Directory where intermediate and final outputs will be placed",
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
def generate(cities: str, output: str, maps: str, radius: float):
    logger = logging.getLogger("scenario_factory")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)

    ctx = PipelineContext(Path(output))
    pipeline = Pipeline(ctx)
    pipeline.populate(load_cities_from_csv(LoadCitiesFromCsvArguments(Path(cities))))
    logger.info(f"Processing {len(pipeline.state)} cities")
    pipeline.map(compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius)))
    pipeline.map(extract_osm_map(ExtractOsmMapArguments(Path(maps), overwrite=True)))
    pipeline.map(convert_osm_file_to_commonroad_scenario)
    pipeline.map(extract_forking_points)
    pipeline.map(extract_intersections)
    pipeline.reduce(flatten)
    logger.info(f"Found {len(pipeline.state)} interesting intersections")
    pipeline.map(convert_intersection_to_commonroad_scenario)
    pipeline.map(create_sumo_configuration_for_commonroad_scenario)
    pipeline.map(generate_random_traffic(GenerateRandomTrafficArguments(scenarios_per_map=2)))
    pipeline.reduce(flatten)
    logger.info(f"Generated random traffic on {len(pipeline.state)} scenarios")
    pipeline.map(simulate_scenario)
    pipeline.map(
        generate_cr_scenarios(
            GenerateCommonRoadScenariosArguments(create_noninteractive=True, create_interactive=False)
        ),
        num_processes=4,
    )
    pipeline.report_results()
    logger.info(f"Successfully generated {len(pipeline.state)} scenarios")


if __name__ == "__main__":
    generate()
