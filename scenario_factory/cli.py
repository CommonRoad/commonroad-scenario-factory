import logging
from pathlib import Path

import click

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
@click.option("--seed", type=int, default=12345)
def generate(cities: str, output: str, maps: str, radius: float, seed: int):
    logger = logging.getLogger("scenario_factory")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)

    osm_logger = logging.getLogger("scenario_factory.osm")
    osm_logger.setLevel(logging.DEBUG)

    ctx = PipelineContext(Path(output), seed=seed)
    pipeline = Pipeline(ctx)
    pipeline.populate(pipeline_load_plain_cities_from_csv(LoadCitiesFromCsvArguments(Path(cities))))
    logger.info(f"Processing {len(pipeline.state)} cities")
    pipeline.map(pipeline_compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius)))
    pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(Path(maps), overwrite=True)))
    pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
    pipeline.map(pipeline_extract_intersections)
    pipeline.reduce(pipeline_flatten)
    logger.info(f"Found {len(pipeline.state)} interesting intersections")
    pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario)
    pipeline.reduce(pipeline_flatten)
    logger.info(f"Generated random traffic on {len(pipeline.state)} scenarios")
    pipeline.map(pipeline_simulate_scenario)
    logger.info("Extract final scenarios")
    pipeline.map(
        pipeline_generate_cr_scenarios(
            GenerateCommonRoadScenariosArguments(create_noninteractive=True, create_interactive=False)
        ),
        num_processes=4,
    )
    pipeline.report_results()
    [print(result.log.getvalue()) for result in pipeline.results if result.step == "pipeline_generate_cr_scenarios"]
    print(pipeline.state)
    logger.info(f"Successfully generated {len(pipeline.state)} scenarios")


if __name__ == "__main__":
    generate()
