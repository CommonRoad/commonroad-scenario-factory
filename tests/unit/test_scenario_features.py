import numpy as np
from commonroad.scenario.lanelet import Lanelet, LaneletType
from commonroad.scenario.scenario import Tag

from scenario_factory.scenario_features.assign_tags import find_applicable_tags_for_lanelets


class TestFindApplicableTagsForLanelets:
    def test_empty_tags_for_empty_lanelets(self):
        assert len(find_applicable_tags_for_lanelets([])) == 0

    def test_finds_highway_tag_for_highway_lanelets(self):
        lanelets = [
            Lanelet(
                lanelet_id=1,
                left_vertices=np.array([[0.0, 0.0], [0.0, 5.0]]),
                center_vertices=np.array([[2.5, 0.0], [2.5, 5.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 5.0]]),
                lanelet_type={LaneletType.HIGHWAY},
            )
        ]

        tags = find_applicable_tags_for_lanelets(lanelets)
        assert Tag.HIGHWAY in tags

    def test_finds_single_lane_tag_for_only_a_single_lane(self):
        lanelets = [
            Lanelet(
                lanelet_id=1,
                left_vertices=np.array([[0.0, 0.0], [0.0, 5.0]]),
                center_vertices=np.array([[2.5, 0.0], [2.5, 5.0]]),
                right_vertices=np.array([[5.0, 0.0], [5.0, 5.0]]),
            )
        ]

        tags = find_applicable_tags_for_lanelets(lanelets)
        assert Tag.SINGLE_LANE in tags
