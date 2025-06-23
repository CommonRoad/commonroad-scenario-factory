__all__ = [
    "pipeline_extract_osm_map",
    "pipeline_convert_osm_map_to_commonroad_scenario",
    "pipeline_verify_and_repair_commonroad_scenario",
    "pipeline_extract_intersections",
    "pipeline_filter_lanelet_network",
]

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
    pipeline_filter,
    pipeline_map,
)
from scenario_factory.scenario_container import ScenarioContainer


@pipeline_map()
def pipeline_extract_osm_map(
    ctx: PipelineContext, region: RegionMetadata, map_provider: MapProvider, radius: float
) -> Path:
    """

    :param args: The arguments for this pipeline step, containing the map provider and the extraction radius.
    :param ctx: The context for this pipeline execution.
    :param region: The region for which the map should be extracted.
    :returns: Path to the extracted OSM maps.
    """
    output_folder = ctx.get_temporary_folder("extracted_maps")
    bounding_box = BoundingBox.from_coordinates(region.coordinates, radius)
    return map_provider.get_map(region, bounding_box, output_folder)


@pipeline_map()
def pipeline_convert_osm_map_to_commonroad_scenario(
    ctx: PipelineContext, osm_file: Path
) -> ScenarioContainer:
    """
    Convert an OpenStreetMap file to a CommonRoad Scenario.

    :param ctx: The context for the current pipeline execution
    :param osm_file: Path to the OpenStreetMap file that should be converted to CommonRoad
    :returns: A new scenario with the converted OpenStreetMap as lanelet network
    """
    scenario = convert_osm_file_to_commonroad_scenario(osm_file)
    scenario_container = ScenarioContainer(scenario)
    return scenario_container


@pipeline_map()
def pipeline_verify_and_repair_commonroad_scenario(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Apply the verification and repair algorithms from the CommonRoad Scenario Designer.

    :param ctx: The context for the current pipeline execution
    :param scenario_container: The scenario that should be repaired. Repairing will happen in place, so this scenario will be modified.
    :returns: The input scenario_container with the repaired scenario
    """
    verify_and_repair_commonroad_scenario(scenario_container.scenario)
    # Repair happens in place, so we simply pass the input scenario down the pipeline
    return scenario_container


@pipeline_map()
def pipeline_extract_intersections(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> List[ScenarioContainer]:
    """
    Extract all intersections from the scenario using the globetrotter algorithm.

    :param ctx: The context for the current pipeline execution.
    :param scenario_container: The scenario from which the intersections shall be extracted. Will not be modified
    :returns: New scenarios for all intersections that were identified in the input scenario
    """

    new_scenarios = extract_intersections_from_scenario(scenario_container.scenario)
    return [ScenarioContainer(scenario) for scenario in new_scenarios]


@pipeline_filter()
def pipeline_filter_lanelet_network(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    filter: LaneletNetworkFilter,
) -> bool:
    """
    Filter the lanelet network in the given scenario according to the filter predicate.

    :param filter: The predicate for filtering lanelet networks
    :param ctx: The context for the current pipeline execution
    :param scenario_container: The scenario on which the lanelet network filter will be applied
    """
    return filter.matches(scenario_container.scenario.lanelet_network)
