from abc import ABC, abstractmethod

from commonroad.scenario.lanelet import LaneletNetwork


class LaneletNetworkFilter(ABC):
    @abstractmethod
    def matches(self, lanelet_network: LaneletNetwork) -> bool:
        """
        :param lanelet_network: The lanelet network this filter is applied to
        """
        ...


class NoTrafficLightsFilter(LaneletNetworkFilter):
    """
    Only select a `LaneletNetwork`, if it does not contain any traffic lights.
    """

    def matches(self, lanelet_network: LaneletNetwork) -> bool:
        return len(lanelet_network.traffic_lights) == 0


class HasTrafficLightsFilter(LaneletNetworkFilter):
    """
    Only select a `LaneletNetwork`, if it does contain at least one traffic light.
    """

    def matches(self, lanelet_network: LaneletNetwork) -> bool:
        return len(lanelet_network.traffic_lights) > 0
