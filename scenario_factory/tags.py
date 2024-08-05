__all__ = ["find_applicable_tags_for_scenario"]

import logging
from typing import Optional, Sequence, Set

from commonroad.scenario.scenario import Scenario, Tag
from commonroad_labeling.common.tag import ScenarioTag, TagEnum
from commonroad_labeling.road_configuration.scenario.scenario_lanelet_layout import (
    LaneletLayoutIntersection,
    LaneletLayoutMergingLane,
    LaneletLayoutMultiLane,
    LaneletLayoutRoundabout,
    LaneletLayoutSingleLane,
)
from commonroad_labeling.road_configuration.scenario.scenario_traffic_sign import TrafficSignSpeedLimit

logger = logging.getLogger(__name__)

_SCENARIO_CRITERIONS: Sequence[type[ScenarioTag]] = [
    LaneletLayoutSingleLane,
    LaneletLayoutIntersection,
    LaneletLayoutMergingLane,
    LaneletLayoutMultiLane,
    LaneletLayoutRoundabout,
    TrafficSignSpeedLimit,
]

# commonroad-auto-labeling has its own TagEnum, but a CommonRoad Scenario must have CommonRoad Tags
_AUTO_LABELING_TAG_TO_COMMONROAD_TAG = {
    TagEnum.SCENARIO_LANELET_LAYOUT_SINGLE_LANE: Tag.SINGLE_LANE,
    TagEnum.SCENARIO_LANELET_LAYOUT_MULTI_LANE: Tag.MULTI_LANE,
    TagEnum.SCENARIO_LANELET_LAYOUT_INTERSECTION: Tag.INTERSECTION,
    TagEnum.SCENARIO_LANELET_LAYOUT_ROUNDABOUT: Tag.ROUNDABOUT,
    TagEnum.SCENARIO_LANELET_LAYOUT_MERGING_LANE: Tag.MERGING_LANES,
    TagEnum.SCENARIO_TRAFFIC_SIGN_SPEED_LIMIT: Tag.SPEED_LIMIT,
}


def _convert_auto_labeling_tag_to_commonroad_tag(tag: TagEnum) -> Optional[Tag]:
    return _AUTO_LABELING_TAG_TO_COMMONROAD_TAG.get(tag)


def find_applicable_tags_for_scenario(scenario: Scenario) -> Set[Tag]:
    tags = set()

    for criterion in _SCENARIO_CRITERIONS:
        initialize_criterion = criterion(scenario)
        matched_tag = initialize_criterion.get_tag_if_fulfilled()
        if matched_tag is None:
            continue

        commonroad_tag = _convert_auto_labeling_tag_to_commonroad_tag(matched_tag)
        if commonroad_tag is None:
            logger.debug(
                f"Found tag {matched_tag} for scenario {scenario.scenario_id}, but no corresponding CommonRoad tag exists"
            )
            continue

        tags.add(commonroad_tag)

    logger.debug(f"Found new tags {tags} for scenario {scenario.scenario_id}")
    return tags
