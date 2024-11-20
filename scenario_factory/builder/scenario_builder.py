from typing import List, Optional

from commonroad.scenario.scenario import Scenario

from scenario_factory.builder.core import BuilderCore, BuilderIdAllocator
from scenario_factory.builder.dynamic_obstacle_builder import DynamicObstacleBuilder
from scenario_factory.builder.lanelet_network_builder import LaneletNetworkBuilder


class ScenarioBuilder(BuilderCore[Scenario]):
    """
    The `ScenarioBuilder` can be used to easily construct a new CommonRoad Scenario with a `LaneletNetwork`.
    """

    def __init__(self) -> None:
        self._id_allocator = BuilderIdAllocator()

        self._lanelet_network_builder: Optional[LaneletNetworkBuilder] = None
        self._dynamic_obstacle_builders: List[DynamicObstacleBuilder] = []

    def create_lanelet_network(self) -> LaneletNetworkBuilder:
        if self._lanelet_network_builder is not None:
            raise RuntimeError("ScenarioBuilder already has a lanelet network builder!")
        self._lanelet_network_builder = LaneletNetworkBuilder(self._id_allocator)
        return self._lanelet_network_builder

    def create_dynamic_obstacle(self, obstacle_id: Optional[int] = None) -> DynamicObstacleBuilder:
        """
        Create a new `DynamicObstacleBuilder`.
        If the scenario is build, the dynamic obstacle will also be build and added to the scenario.
        """
        if obstacle_id is None:
            obstacle_id = self._id_allocator.new_id()
        new_dynamic_obstacle_builder = DynamicObstacleBuilder(obstacle_id)
        self._dynamic_obstacle_builders.append(new_dynamic_obstacle_builder)
        return new_dynamic_obstacle_builder

    def build(self) -> Scenario:
        new_scenario = Scenario(dt=0.1)
        if self._lanelet_network_builder is not None:
            lanelet_network = self._lanelet_network_builder.build()
            new_scenario.add_objects(lanelet_network)

        for dynamic_obstacle_builder in self._dynamic_obstacle_builders:
            dynamic_obstacle = dynamic_obstacle_builder.build()
            new_scenario.add_objects(dynamic_obstacle)

        return new_scenario
