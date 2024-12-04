from commonroad.scenario.lanelet import LaneletNetwork

from tests.automation.datasets import Dataset
from tests.automation.validation import TestCase
from tests.helpers.lanelet_network import UsefulLaneletNetworks

# ---------------------------------
# Entry Models
# ---------------------------------


class NoTrafficLightsTestCase(TestCase):
    lanelet_network: LaneletNetwork
    expect_match: bool


# ---------------------------------
# Dynamic Datasets
# ---------------------------------

NO_TRAFFIC_LIGHTS_TEST_DATASET = Dataset(
    [
        NoTrafficLightsTestCase(
            label="empty_network",
            lanelet_network=UsefulLaneletNetworks.empty_no_meta(),
            expect_match=True,
        ),
        NoTrafficLightsTestCase(
            label="no_traffic_lights",
            lanelet_network=UsefulLaneletNetworks.single_lanelet_no_meta(),
            expect_match=True,
        ),
        NoTrafficLightsTestCase(
            label="single_traffic_light",
            lanelet_network=UsefulLaneletNetworks.single_lanelet_traffic_light(),
            expect_match=False,
        ),
    ]
)
