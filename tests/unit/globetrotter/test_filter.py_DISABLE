import os.path

import pytest

from scenario_factory.globetrotter.filter import NoTrafficLightsFilter
from tests.resources.interface import (
    ResourceType,
    get_test_dataset_csv,
    load_cr_lanelet_network_from_file,
)
from tests.utility import bool_from_string


def get_no_traffic_lights_test_dataset():
    return [
        (entry[0], entry[1], bool_from_string(entry[2]))
        for entry in get_test_dataset_csv(
            os.path.join("globetrotter", "filter", "no_traffic_lights")
        )
    ]


_NO_TRAFFIC_LIGHTS_TEST_DATASET = get_no_traffic_lights_test_dataset()


class TestNoTrafficLightsFilter:
    @pytest.mark.parametrize(
        "label, lanelet_network, expect_match", _NO_TRAFFIC_LIGHTS_TEST_DATASET
    )
    def test_matches(self, label: str, lanelet_network: str, expect_match: bool):
        network = load_cr_lanelet_network_from_file(
            ResourceType.CR_LANELET_NETWORK.get_folder() / lanelet_network
        )
        f = NoTrafficLightsFilter()
        assert (
            f.matches(network) == expect_match
        ), f"Expected correct filtering behaviour for entry: {label}."
