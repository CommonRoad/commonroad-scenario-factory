__all__ = [
    "ExtractOsmMapArguments",
    "pipeline_extract_osm_map",
    "pipeline_convert_osm_map_to_commonroad_scenario",
    "pipeline_extract_intersections",
    "LoadRegionsFromCsvArguments",
    "pipeline_load_regions_from_csv",
]

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

from commonroad.scenario.scenario import Scenario

from scenario_factory.globetrotter import (
    RegionMetadata,
    convert_osm_file_to_commonroad_scenario,
    extract_intersections_from_scenario,
    load_regions_from_csv,
)
from scenario_factory.globetrotter.osm import MapProvider, verify_and_repair_commonroad_scenario
from scenario_factory.globetrotter.region import BoundingBox
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map,
    pipeline_map_with_args,
    pipeline_populate_with_args,
)


@dataclass
class LoadRegionsFromCsvArguments(PipelineStepArguments):
    regions_path: Path


@pipeline_populate_with_args
def pipeline_load_regions_from_csv(args: LoadRegionsFromCsvArguments, ctx: PipelineContext) -> Iterator[RegionMetadata]:
    yield from load_regions_from_csv(args.regions_path)


@dataclass
class ExtractOsmMapArguments(PipelineStepArguments):
    map_provider: MapProvider
    radius: float


@pipeline_map_with_args
def pipeline_extract_osm_map(
    args: ExtractOsmMapArguments,
    ctx: PipelineContext,
    region: RegionMetadata,
) -> Path:
    """
    :param region: The region for which the map should be extracted.
    :returns: Path to the extracted OSM maps.
    """
    output_folder = ctx.get_temporary_folder("extracted_maps")
    bounding_box = BoundingBox.from_coordinates(region.coordinates, args.radius)
    return args.map_provider.get_map(region, bounding_box, output_folder)


@pipeline_map
def pipeline_convert_osm_map_to_commonroad_scenario(ctx: PipelineContext, osm_file: Path) -> Scenario:
    scenario = convert_osm_file_to_commonroad_scenario(osm_file)
    return scenario


@pipeline_map
def pipeline_verify_and_repair_commonroad_scenario(ctx: PipelineContext, scenario: Scenario) -> Scenario:
    verify_and_repair_commonroad_scenario(scenario)
    # Repair happens in place, so we simply pass the input scenario down the pipeline
    return scenario


@pipeline_map
def pipeline_extract_intersections(ctx: PipelineContext, scenario: Scenario) -> List[Scenario]:
    """
    Extract all intersections from the scenario.
    """

    new_scenarios = extract_intersections_from_scenario(scenario)
    return new_scenarios
