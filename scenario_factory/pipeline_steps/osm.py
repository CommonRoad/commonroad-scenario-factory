from dataclasses import dataclass
from pathlib import Path

from commonroad.scenario.scenario import Scenario

from scenario_factory.city import BoundedCity
from scenario_factory.osm import convert_osm_file_to_commonroad_scenario, extract_bounding_box_from_osm_map
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map, pipeline_map_with_args


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
    output_folder = ctx.get_output_folder("extracted_maps")
    # TODO: Include the bounding box in the map name, to enable efficient caching
    output_file = output_folder.joinpath(f"{city.country}_{city.name}.osm")

    return extract_bounding_box_from_osm_map(city, output_file, args.input_maps_folder, args.overwrite)


@pipeline_map
def pipeline_convert_osm_map_to_commonroad_scenario(ctx: PipelineContext, osm_file: Path) -> Scenario:
    scenario = convert_osm_file_to_commonroad_scenario(osm_file)
    return scenario


__all__ = [
    "ExtractOsmMapArguments",
    "pipeline_extract_osm_map",
    "pipeline_convert_osm_map_to_commonroad_scenario",
]
