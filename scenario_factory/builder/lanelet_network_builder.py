from typing import List, Literal, Optional, Set, Tuple, Union

import numpy as np
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork, LaneletType, LineMarking, StopLine
from commonroad.scenario.traffic_light import (
    TrafficLight,
    TrafficLightCycle,
    TrafficLightCycleElement,
    TrafficLightDirection,
    TrafficLightState,
)
from commonroad.scenario.traffic_sign import TrafficSign, TrafficSignElement, TrafficSignIDGermany
from shapely.geometry import LineString

from scenario_factory.builder.core import (
    BuilderCore,
    BuilderIdAllocator,
    create_curve,
)
from scenario_factory.builder.intersection_builder import IntersectionBuilder


class TrafficSignBuilder(BuilderCore[TrafficSign]):
    """
    The `TrafficSignBuilder` is used to easily construct `TrafficSign`s and associate them with lanelets. Usually created by `TrafficSignBuilder.create_traffic_sign`.

    :param traffic_sign_id: The unique CommonRoad ID that will be assigned to the resulting traffic sign.
    """

    def __init__(self, traffic_sign_id: int) -> None:
        self._traffic_sign_id = traffic_sign_id

        self._elements: List[TrafficSignElement] = []
        self._lanelets: List[Lanelet] = []

    def for_lanelet(self, lanelet: Lanelet) -> "TrafficSignBuilder":
        """
        Associate the traffic sign with `lanelet`.
        """
        self._lanelets.append(lanelet)
        return self

    def add_element(self, element_id: TrafficSignIDGermany) -> "TrafficSignBuilder":
        traffic_sign_element = TrafficSignElement(element_id)
        self._elements.append(traffic_sign_element)
        return self

    def get_associated_lanelet_ids(self) -> Set[int]:
        """
        Get the CommonRoad IDs of all associated lanelets. Usefull, when the traffic sign
        should be added to a lenelet network.
        """
        return {lanelet.lanelet_id for lanelet in self._lanelets}

    def build(self) -> TrafficSign:
        new_traffic_sign = TrafficSign(
            self._traffic_sign_id,
            self._elements,
            self.get_associated_lanelet_ids(),
            self._lanelets[0].right_vertices[-1],
        )
        return new_traffic_sign


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


class LaneletNetworkBuilder(BuilderCore[LaneletNetwork]):
    """
    The `LaneletNetworkBuilder` is used to easily construct lanelet networks with lanelets, traffic signs, traffic lights and intersections. It makes it easy to define lanelets and their relationships without having to define the whole geometry and juggling around with CommonRoad ids.

    :param id_allocator: Optionally provide an existing `BuilderIdAllocator` to prevent id collisions.
    """

    def __init__(self, id_allocator: Optional[BuilderIdAllocator] = None) -> None:
        if id_allocator is None:
            self._id_allocator = BuilderIdAllocator()
        else:
            self._id_allocator = id_allocator

        self._lanelets: List[Lanelet] = []

        # The builders are tracked here, so that all sub-builders can be finalized during 'build'
        self._traffic_light_builders: List[TrafficLightBuilder] = []
        self._traffic_sign_builders: List[TrafficSignBuilder] = []
        self._intersection_builders: List[IntersectionBuilder] = []

    def create_traffic_sign(self) -> TrafficSignBuilder:
        traffic_sign_builder = TrafficSignBuilder(self._id_allocator.new_id())
        self._traffic_sign_builders.append(traffic_sign_builder)
        return traffic_sign_builder

    def create_traffic_light(self) -> TrafficLightBuilder:
        traffic_light_builder = TrafficLightBuilder(self._id_allocator.new_id())
        self._traffic_light_builders.append(traffic_light_builder)
        return traffic_light_builder

    def create_intersection(self) -> IntersectionBuilder:
        intersection_builder = IntersectionBuilder(self._id_allocator)
        self._intersection_builders.append(intersection_builder)
        return intersection_builder

    def add_lanelet(
        self,
        start: Union[np.ndarray, List[float], Tuple[float, float]],
        end: Union[np.ndarray, List[float], Tuple[float, float]],
        width: float = 4.0,
        lanelet_type: LaneletType = LaneletType.URBAN,
    ) -> Lanelet:
        """
        Create and add a new lanelet to the lanelet network. The center line is created directly from the `start` to the `end` point while the left and right lines are offset from this center line by width/2.

        :param start: The start point of the new lanelet.
        :param end: The end point of the lanelet.
        :param width: The width of the lanelet.
        returns: The newly created lanelet
        """
        if start == end:
            raise ValueError("Lanelet cannot have the same start and end point!")

        center_line = LineString(np.array([start, end]))
        right_line = center_line.offset_curve(-width / 2)
        left_line = center_line.offset_curve(width / 2)

        lanelet_id = self._id_allocator.new_id()
        new_lanelet = Lanelet(
            left_vertices=np.array(left_line.coords),
            center_vertices=np.array(center_line.coords),
            right_vertices=np.array(right_line.coords),
            lanelet_id=lanelet_id,
            lanelet_type={lanelet_type},
        )
        self._lanelets.append(new_lanelet)
        return new_lanelet

    def add_adjacent_lanelet(
        self,
        original_lanelet: Lanelet,
        side: Literal["left", "right"] = "right",
        width: float = 4.0,
    ) -> Lanelet:
        if side != "left" and side != "right":
            raise ValueError(f"'side' must be either 'left' or 'right', but got '{side}'!")

        right = side == "right"

        if right and original_lanelet.adj_right is not None:
            raise ValueError(
                f"Cannot add adjacent lanelet on the right to {original_lanelet.lanelet_id}: Already has an adjacent lanelet on the right!"
            )
        elif not right and original_lanelet.adj_left is not None:
            raise ValueError(
                f"Cannot add adjacent lanelet on the left to {original_lanelet.lanelet_id}: Already has an adjacent lanelet on the left!"
            )

        left_line, center_line, right_line = None, None, None
        if right:
            left_line = LineString(original_lanelet.right_vertices)
            center_line = left_line.offset_curve(-width / 2)
            right_line = left_line.offset_curve(-width)
        else:
            right_line = LineString(original_lanelet.left_vertices)
            center_line = right_line.offset_curve(width / 2)
            left_line = right_line.offset_curve(width)

        lanelet_id = self._id_allocator.new_id()
        new_lanelet = Lanelet(
            left_vertices=np.array(left_line.coords),
            right_vertices=np.array(right_line.coords),
            center_vertices=np.array(center_line.coords),
            lanelet_id=lanelet_id,
        )
        self._lanelets.append(new_lanelet)

        if right:
            self.set_adjacent(new_lanelet, original_lanelet)
        else:
            self.set_adjacent(original_lanelet, new_lanelet)
        return new_lanelet

    def set_adjacent(
        self,
        right_lanelet: Lanelet,
        left_lanelet: Lanelet,
        same_direction: bool = True,
    ):
        right_lanelet.adj_left = left_lanelet.lanelet_id
        right_lanelet.adj_left_same_direction = same_direction

        left_lanelet.adj_right = right_lanelet.lanelet_id
        left_lanelet.adj_right_same_direction = same_direction

        return self

    def add_stopline(
        self, lanelet: Lanelet, offset: int = 0, line_marking: LineMarking = LineMarking.SOLID
    ):
        stopline_start = lanelet.left_vertices[1] - offset
        stopline_end = lanelet.right_vertices[1] - offset
        stopline = StopLine(start=stopline_start, end=stopline_end, line_marking=line_marking)

        lanelet.stop_line = stopline

        return self

    def connect(self, start: Lanelet, end: Lanelet) -> "LaneletNetworkBuilder":
        start.add_successor(end.lanelet_id)
        end.add_predecessor(start.lanelet_id)
        return self

    def _create_connecting_lanelet_from_geo(
        self,
        start: Lanelet,
        end: Lanelet,
        left_vertices: np.ndarray,
        center_vertices: np.ndarray,
        right_vertices: np.ndarray,
    ) -> Lanelet:
        connection_lanelet_id = self._id_allocator.new_id()
        connection_lanelet_type = (
            start.lanelet_type if start.lanelet_type == end.lanelet_type else None
        )
        connection_line_marking_left = (
            start.line_marking_left_vertices
            if start.line_marking_left_vertices == end.line_marking_left_vertices
            else LineMarking.NO_MARKING
        )
        connection_line_marking_right = (
            start.line_marking_right_vertices
            if start.line_marking_right_vertices == end.line_marking_right_vertices
            else LineMarking.NO_MARKING
        )
        connection_lanelet = Lanelet(
            left_vertices=left_vertices,
            center_vertices=center_vertices,
            right_vertices=right_vertices,
            lanelet_id=connection_lanelet_id,
            lanelet_type=connection_lanelet_type,
            line_marking_left_vertices=connection_line_marking_left,
            line_marking_right_vertices=connection_line_marking_right,
        )

        self.connect(start, connection_lanelet)
        self.connect(connection_lanelet, end)

        return connection_lanelet

    def create_straight_connecting_lanelet(
        self,
        start: Lanelet,
        end: Lanelet,
    ) -> Lanelet:
        new_lanelet = self._create_connecting_lanelet_from_geo(
            start,
            end,
            left_vertices=np.array([start.left_vertices[1], end.left_vertices[0]]),
            center_vertices=np.array([start.center_vertices[1], end.center_vertices[0]]),
            right_vertices=np.array([start.right_vertices[1], end.right_vertices[0]]),
        )
        self._lanelets.append(new_lanelet)
        return new_lanelet

    def create_curved_connecting_lanelet(
        self,
        start: Lanelet,
        end: Lanelet,
    ) -> Lanelet:
        new_lanelet = self._create_connecting_lanelet_from_geo(
            start,
            end,
            left_vertices=create_curve(start.left_vertices, end.left_vertices),
            center_vertices=create_curve(start.center_vertices, end.center_vertices),
            right_vertices=create_curve(start.right_vertices, end.right_vertices),
        )
        self._lanelets.append(new_lanelet)
        return new_lanelet

    def build(self) -> LaneletNetwork:
        lanelet_network = LaneletNetwork.create_from_lanelet_list(self._lanelets)

        for intersection_builder in self._intersection_builders:
            lanelet_network.add_intersection(intersection_builder.build())

        for traffic_light_builder in self._traffic_light_builders:
            traffic_light = traffic_light_builder.build()
            lanelet_ids = traffic_light_builder.get_associated_lanelet_ids()
            lanelet_network.add_traffic_light(traffic_light, lanelet_ids)

        for traffic_sign_builder in self._traffic_sign_builders:
            traffic_sign = traffic_sign_builder.build()
            lanelet_ids = traffic_sign_builder.get_associated_lanelet_ids()
            lanelet_network.add_traffic_sign(traffic_sign, lanelet_ids)

        return lanelet_network
