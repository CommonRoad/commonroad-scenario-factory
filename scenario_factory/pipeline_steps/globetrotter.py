__all__ = [
    "ExtractOsmMapArguments",
    "pipeline_extract_osm_map",
    "pipeline_convert_osm_map_to_commonroad_scenario",
    "pipeline_extract_intersections",
    "LoadCitiesFromCsvArguments",
    "pipeline_load_plain_cities_from_csv",
    "ComputeBoundingBoxForCityArguments",
    "pipeline_compute_bounding_box_for_city",
]

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

from commonroad.scenario.scenario import Scenario

from scenario_factory.globetrotter import (
    BoundedCity,
    PlainCity,
    compute_bounding_box_for_city,
    convert_osm_file_to_commonroad_scenario,
    extract_bounding_box_from_osm_map,
    extract_intersections_from_scenario,
    load_plain_cities_from_csv,
)
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map,
    pipeline_map_with_args,
    pipeline_populate_with_args,
)


@dataclass
class LoadCitiesFromCsvArguments(PipelineStepArguments):
    cities_path: Path


@pipeline_populate_with_args
def pipeline_load_plain_cities_from_csv(args: LoadCitiesFromCsvArguments, ctx: PipelineContext) -> Iterator[PlainCity]:
    yield from load_plain_cities_from_csv(args.cities_path)


@dataclass
class ComputeBoundingBoxForCityArguments(PipelineStepArguments):
    radius: float


@pipeline_map_with_args
def pipeline_compute_bounding_box_for_city(
    args: ComputeBoundingBoxForCityArguments,
    ctx: PipelineContext,
    city: PlainCity,
) -> BoundedCity:
    return compute_bounding_box_for_city(city, args.radius)


@dataclass
class ExtractOsmMapArguments(PipelineStepArguments):
    input_maps_folder: Path
    overwrite: bool


@pipeline_map_with_args
def pipeline_extract_osm_map(
    args: ExtractOsmMapArguments,
    ctx: PipelineContext,
    city: BoundedCity,
) -> Path:
    """
    Args:
        city (BoundedCity): The city for which the map should be extracted.

    Returns:
        Path: Path to the extracted OSM maps.
    """
    output_folder = ctx.get_temporary_folder("extracted_maps")
    # TODO: Include the bounding box in the map name, to enable efficient caching
    output_file = output_folder.joinpath(f"{city.country}_{city.name}.osm")

    return extract_bounding_box_from_osm_map(city, output_file, args.input_maps_folder, args.overwrite)


@pipeline_map
def pipeline_convert_osm_map_to_commonroad_scenario(ctx: PipelineContext, osm_file: Path) -> Scenario:
    scenario = convert_osm_file_to_commonroad_scenario(osm_file)
    return scenario


@pipeline_map
def pipeline_extract_intersections(ctx: PipelineContext, scenario: Scenario) -> List[Scenario]:
    """
    Extract all intersections from the scenario.
    """

    new_scenarios = extract_intersections_from_scenario(scenario)
    return new_scenarios
