__all__ = ["find_applicable_tags_for_scenario"]

import logging
from typing import Optional, Sequence, Set

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario, Tag
from commonroad_labeling.common.general import get_planned_routes
from commonroad_labeling.common.tag import EgoVehicleGoalTag, ScenarioTag, TagEnum
from commonroad_labeling.ego_vehicle_goal.ego_vehicle_goal_intersection import (
    EgoVehicleGoalIntersectionTurnLeft,
    EgoVehicleGoalIntersectionTurnRight,
)
from commonroad_labeling.road_configuration.scenario.scenario_lanelet_layout import (
    LaneletLayoutIntersection,
    LaneletLayoutMergingLane,
    LaneletLayoutMultiLane,
    LaneletLayoutRoundabout,
    LaneletLayoutSingleLane,
)
from commonroad_labeling.road_configuration.scenario.scenario_traffic_sign import (
    TrafficSignSpeedLimit,
)

_LOGGER = logging.getLogger(__name__)

_SCENARIO_CRITERIONS: Sequence[type[ScenarioTag]] = [
    LaneletLayoutSingleLane,
    LaneletLayoutIntersection,
    LaneletLayoutMergingLane,
    LaneletLayoutMultiLane,
    LaneletLayoutRoundabout,
    TrafficSignSpeedLimit,
]


_EGO_VEHICLE_CRITERIONS: Sequence[type[EgoVehicleGoalTag]] = [
    EgoVehicleGoalIntersectionTurnLeft,
    EgoVehicleGoalIntersectionTurnRight,
]

# commonroad-auto-labeling has its own TagEnum, but a CommonRoad Scenario must have CommonRoad Tags
_AUTO_LABELING_TAG_TO_COMMONROAD_TAG = {
    TagEnum.SCENARIO_LANELET_LAYOUT_SINGLE_LANE: Tag.SINGLE_LANE,
    TagEnum.SCENARIO_LANELET_LAYOUT_MULTI_LANE: Tag.MULTI_LANE,
    TagEnum.SCENARIO_LANELET_LAYOUT_INTERSECTION: Tag.INTERSECTION,
    TagEnum.SCENARIO_LANELET_LAYOUT_ROUNDABOUT: Tag.ROUNDABOUT,
    TagEnum.SCENARIO_LANELET_LAYOUT_MERGING_LANE: Tag.MERGING_LANES,
    TagEnum.SCENARIO_TRAFFIC_SIGN_SPEED_LIMIT: Tag.SPEED_LIMIT,
    TagEnum.ROUTE_OBSTACLE_ONCOMING_TRAFFIC: Tag.ONCOMING_TRAFFIC,
    TagEnum.ROUTE_OBSTACLE_NO_ONCOMING_TRAFFIC: Tag.NO_ONCOMING_TRAFFIC,
    TagEnum.EGO_VEHICLE_GOAL_INTERSECTION_TURN_LEFT: Tag.TURN_LEFT,
    TagEnum.EGO_VEHICLE_GOAL_INTERSECTION_TURN_RIGHT: Tag.TURN_RIGHT,
}


def _convert_auto_labeling_tag_to_commonroad_tag(tag: TagEnum) -> Optional[Tag]:
    """
    Map a tag produced by commonroad-auto-labeling to a CommonRoad tag that can be used in scenarios.

    :param tag: The commonroad-auto-labeling tag.
    :returns: If the tag can be mapped, the matching CommonRoad tag, None otherwise.
    """
    return _AUTO_LABELING_TAG_TO_COMMONROAD_TAG.get(tag)


def find_applicable_tags_for_scenario(scenario: Scenario) -> Set[Tag]:
    """
    Find all *static* tags (mostly lanelet network layout) that are applicable to this scenario.

    :param scenario: The scenario for which tags should be found.
    :returns: A set of tags that are applicable for this scenario.
    """
    tags = set()

    for scenario_criterion in _SCENARIO_CRITERIONS:
        initialized_scenario_criterion = scenario_criterion(scenario)
        matched_tag = initialized_scenario_criterion.get_tag_if_fulfilled()
        if matched_tag is None:
            continue

        commonroad_tag = _convert_auto_labeling_tag_to_commonroad_tag(matched_tag)
        if commonroad_tag is None:
            _LOGGER.warning(
                f"Found tag {matched_tag} for scenario {scenario.scenario_id}, but no corresponding CommonRoad tag exists"
            )
            continue

        tags.add(commonroad_tag)

    _LOGGER.debug(f"Found new tags {tags} for scenario {scenario.scenario_id}")
    return tags


def find_applicable_tags_for_planning_problem_set(
    scenario: Scenario, planning_problem_set: PlanningProblemSet
) -> Set[Tag]:
    tags: Set[Tag] = set()

    try:
        routes = get_planned_routes(scenario, planning_problem_set)
    except ValueError:
        # If not a single route could be planned, a ValueError is thrown.
        # Because no route could be planned, there is no chance to find any tags,
        # so the empty set is returned.
        return tags

    for route in routes:
        # The criterions require a route which has the 'scenario' property set.
        # By default this property is not set, but it can be simply set here.
        # Not sure, why it uses an invalid Route type tho...
        route.scenario = scenario  # type: ignore
        for ego_vehicle_criterion in _EGO_VEHICLE_CRITERIONS:
            initialized_ego_vehicle_criterion = ego_vehicle_criterion(route, scenario)
            matched_tag = initialized_ego_vehicle_criterion.get_tag_if_fulfilled()
            if matched_tag is None:
                continue

            commonroad_tag = _convert_auto_labeling_tag_to_commonroad_tag(matched_tag)
            if commonroad_tag is None:
                _LOGGER.warning(
                    f"Found tag {matched_tag} for scenario {scenario.scenario_id}, but no corresponding CommonRoad tag exists"
                )
                continue

            tags.add(commonroad_tag)

    return tags
