from commonroad.scenario.lanelet import LaneletNetwork

from scenario_factory.globetrotter.filter import NoTrafficLightsFilter
from tests.automation.mark import with_dataset
from tests.unit.globetrotter.filter_datasets import NO_TRAFFIC_LIGHTS_TEST_DATASET


class TestNoTrafficLightsFilter:
    @with_dataset(NO_TRAFFIC_LIGHTS_TEST_DATASET)
    def test_matches(self, label: str, lanelet_network: LaneletNetwork, expect_match: bool):
        f = NoTrafficLightsFilter()
        assert (
            f.matches(lanelet_network) == expect_match
        ), f"Expected correct filtering behaviour for entry: {label}."
