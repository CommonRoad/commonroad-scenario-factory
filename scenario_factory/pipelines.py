from typing import Iterable

from scenario_factory.ego_vehicle_selection.criterions import EgoVehicleSelectionCriterion
from scenario_factory.ego_vehicle_selection.filters import EgoVehicleManeuverFilter
from scenario_factory.globetrotter.filter import NoTrafficLightsFilter
from scenario_factory.globetrotter.osm import MapProvider
from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import (
    ExtractOsmMapArguments,
    FindEgoVehicleManeuversArguments,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_filter_ego_vehicle_maneuver,
    pipeline_filter_lanelet_network,
    pipeline_find_ego_vehicle_maneuvers,
    pipeline_generate_scenario_for_ego_vehicle_maneuver,
    pipeline_remove_colliding_dynamic_obstacles,
    pipeline_select_one_maneuver_per_ego_vehicle,
    pipeline_verify_and_repair_commonroad_scenario,
)


def create_globetrotter_pipeline(radius: float, map_provider: MapProvider) -> Pipeline:
    """
    The basic globetrotter pipeline that takes Points of Interest as inputs and creates CommonRoad Scenarios for each intersection that was found.
    """
    pipeline = Pipeline()
    (
        pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(map_provider, radius=radius)))
        .map(pipeline_convert_osm_map_to_commonroad_scenario)
        .map(pipeline_verify_and_repair_commonroad_scenario)
        .map(pipeline_extract_intersections)
        .filter(pipeline_filter_lanelet_network(NoTrafficLightsFilter()))
    )
    return pipeline


def create_scenario_generation_pipeline(
    ego_vehicle_selection_criterions: Iterable[EgoVehicleSelectionCriterion],
    ego_vehicle_filters: Iterable[EgoVehicleManeuverFilter],
) -> Pipeline:
    """
    The basic scenario generation pipeline that finds possible ego vehicles in the scenarios according to the given criterions and filter. It takes scenarios with traffic as inputs and outputs scenarios with planning problems as well as their solutions.
    """
    pipeline = Pipeline()

    pipeline.map(pipeline_remove_colliding_dynamic_obstacles)
    pipeline.map(
        pipeline_find_ego_vehicle_maneuvers(
            FindEgoVehicleManeuversArguments(criterions=ego_vehicle_selection_criterions)
        ),
    )
    for filter in ego_vehicle_filters:
        pipeline.filter(pipeline_filter_ego_vehicle_maneuver(filter))

    pipeline.fold(pipeline_select_one_maneuver_per_ego_vehicle)
    pipeline.map(pipeline_generate_scenario_for_ego_vehicle_maneuver)

    return pipeline
