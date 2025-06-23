from typing import List, Set

import numpy as np
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.traffic_light import (
    TrafficLight,
    TrafficLightCycle,
    TrafficLightCycleElement,
    TrafficLightDirection,
    TrafficLightState,
)

from scenario_factory.builder.core import BuilderCore


class TrafficLightBuilder(BuilderCore[TrafficLight]):
    """
    The TrafficLightBuilder is used to easily construct CommonRoad traffic lights. Usually created by `LaneletNetworkBuilder.create_traffic_light`.

    :param traffic_light_id: The unique CommonRoad ID which will be assigned to the resulting traffic light.
    """

    def __init__(self, traffic_light_id: int) -> None:
        self._traffic_light_id = traffic_light_id

        self._lanelets: List[Lanelet] = []
        self._cycle_offset = 0
        self._cycle_elements: List[TrafficLightCycleElement] = []
        self._direction = TrafficLightDirection.ALL

    def for_lanelet(self, lanelet: Lanelet) -> "TrafficLightBuilder":
        """
        Associate this traffic light with this `lanelet`.

        :param lanelet: The lanlet to which this traffic light should be assigned. The first lanelet that is added using this method, will be used to determine the position of this traffic light.
        """
        self._lanelets.append(lanelet)
        return self

    def use_default_cycle(self) -> "TrafficLightBuilder":
        self._cycle_elements = [
            TrafficLightCycleElement(TrafficLightState.RED, duration=60),
            TrafficLightCycleElement(TrafficLightState.RED_YELLOW, duration=10),
            TrafficLightCycleElement(TrafficLightState.GREEN, duration=30),
            TrafficLightCycleElement(TrafficLightState.YELLOW, duration=10),
        ]
        return self

    def add_phase(self, state: TrafficLightState, duration: int) -> "TrafficLightBuilder":
        self._cycle_elements.append(TrafficLightCycleElement(state, duration))
        return self

    def set_cycle_offset(self, offset: int) -> "TrafficLightBuilder":
        self._cycle_offset = offset
        return self

    def set_direction(self, direction: TrafficLightDirection) -> "TrafficLightBuilder":
        self._direction = direction
        return self

    def get_associated_lanelet_ids(self) -> Set[int]:
        return {lanelet.lanelet_id for lanelet in self._lanelets}

    def _get_most_likely_position(self) -> np.ndarray:
        # For now, simply select the end point of the first lanelet.
        # TODO: Add checks to select the right-most lanelet and also consider left-most lanelet
        # for left hand traffic
        return self._lanelets[0].right_vertices[-1]

    def build(self) -> TrafficLight:
        """
        Build the traffic light according to the builder configuration.

        :returns: A new traffic light.
        :raises ValueError: If no lanelets were associated with this traffic light.
        """
        if len(self._lanelets) == 0:
            raise ValueError(
                f"Cannot build traffic light {self._traffic_light_id}: No lanelets associated with this traffic light!"
            )

        cycle = TrafficLightCycle(self._cycle_elements, time_offset=self._cycle_offset)
        new_traffic_light = TrafficLight(
            self._traffic_light_id,
            self._get_most_likely_position(),
            traffic_light_cycle=cycle,
            direction=self._direction,
        )
        return new_traffic_light
