__all__ = [
    "ExtractOsmMapArguments",
    "pipeline_extract_osm_map",
    "pipeline_convert_osm_map_to_commonroad_scenario",
    "pipeline_verify_and_repair_commonroad_scenario",
    "pipeline_extract_intersections",
    "pipeline_filter_lanelet_network",
]

from dataclasses import dataclass
from pathlib import Path
from typing import List

from scenario_factory.globetrotter import (
    RegionMetadata,
    convert_osm_file_to_commonroad_scenario,
    extract_intersections_from_scenario,
)
from scenario_factory.globetrotter.filter import LaneletNetworkFilter
from scenario_factory.globetrotter.osm import MapProvider, verify_and_repair_commonroad_scenario
from scenario_factory.globetrotter.region import BoundingBox
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_filter,
    pipeline_map,
    pipeline_map_with_args,
)
from scenario_factory.scenario_types import ScenarioContainer


@dataclass
class ExtractOsmMapArguments(PipelineStepArguments):
    map_provider: MapProvider
    radius: float


@pipeline_map_with_args()
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


@pipeline_map()
def pipeline_convert_osm_map_to_commonroad_scenario(ctx: PipelineContext, osm_file: Path) -> ScenarioContainer:
    scenario = convert_osm_file_to_commonroad_scenario(osm_file)
    scenario_container = ScenarioContainer(scenario)
    return scenario_container


@pipeline_map()
def pipeline_verify_and_repair_commonroad_scenario(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    verify_and_repair_commonroad_scenario(scenario_container.scenario)
    # Repair happens in place, so we simply pass the input scenario down the pipeline
    return scenario_container


@pipeline_map()
def pipeline_extract_intersections(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> List[ScenarioContainer]:
    """
    Extract all intersections from the scenario.
    """

    new_scenarios = extract_intersections_from_scenario(scenario_container.scenario)
    return [ScenarioContainer(scenario) for scenario in new_scenarios]


@pipeline_filter()
def pipeline_filter_lanelet_network(
    filter: LaneletNetworkFilter, ctx: PipelineContext, scenario_container: ScenarioContainer
) -> bool:
    """
    Apply the :param:`filter` to the lanelet network in :param:`scenario_container`.
    """
    return filter.matches(scenario_container.scenario.lanelet_network)
