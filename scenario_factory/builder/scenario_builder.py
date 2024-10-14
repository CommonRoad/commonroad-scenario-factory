from typing import Optional

from commonroad.scenario.scenario import Scenario

from scenario_factory.builder.core import BuilderCore, BuilderIdAllocator
from scenario_factory.builder.lanelet_network_builder import LaneletNetworkBuilder


class ScenarioBuilder(BuilderCore[Scenario]):
    """
    The `ScenarioBuilder` can be used to easily construct a new CommonRoad Scenario with a `LaneletNetwork`.
    """

    def __init__(self) -> None:
        self._id_allocator = BuilderIdAllocator()

        self._lanelet_network_builder: Optional[LaneletNetworkBuilder] = None

    def create_lanelet_network(self) -> LaneletNetworkBuilder:
        if self._lanelet_network_builder is not None:
            raise RuntimeError("ScenarioBuilder already has a lanelet network builder!")
        self._lanelet_network_builder = LaneletNetworkBuilder(self._id_allocator)
        return self._lanelet_network_builder

    def build(self) -> Scenario:
        new_scenario = Scenario(dt=0.1)
        if self._lanelet_network_builder is not None:
            lanelet_network = self._lanelet_network_builder.build()
            new_scenario.add_objects(lanelet_network)

        return new_scenario
