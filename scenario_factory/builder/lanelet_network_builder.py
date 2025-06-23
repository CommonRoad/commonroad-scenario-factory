from typing import List, Literal, Optional, Set, Tuple, Union

import numpy as np
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork, LaneletType, LineMarking, StopLine
from commonroad.scenario.traffic_sign import TrafficSign, TrafficSignElement, TrafficSignIDGermany

from scenario_factory.builder.core import (
    BuilderCore,
    BuilderIdAllocator,
    create_curve,
    offset_curve,
)
from scenario_factory.builder.intersection_builder import IntersectionBuilder
from scenario_factory.builder.traffic_light_builder import TrafficLightBuilder


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
        num_interpolation_points: int = 5,
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

        x = np.linspace(start[0], end[0], num_interpolation_points)
        y = np.linspace(start[1], end[1], num_interpolation_points)
        center_vertices = np.column_stack((x, y))
        left_vertices = offset_curve(center_vertices, -width / 2)
        right_vertices = offset_curve(center_vertices, width / 2)

        lanelet_id = self._id_allocator.new_id()
        new_lanelet = Lanelet(
            left_vertices=left_vertices,
            center_vertices=center_vertices,
            right_vertices=right_vertices,
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
        same_direction: bool = True,
        lanelet_type: LaneletType = LaneletType.URBAN,
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

        if right:
            left_vertices = original_lanelet.right_vertices
            center_vertices = offset_curve(left_vertices, width / 2)
            right_vertices = offset_curve(left_vertices, width)
        else:
            right_vertices = original_lanelet.left_vertices
            center_vertices = offset_curve(right_vertices, -width / 2)
            left_vertices = offset_curve(right_vertices, -width)

        if not same_direction:
            # By default the vertices are configured for adjacent lanelets that have the same directon.
            # If they should not have the same direction, the left and right vertices are swapped
            # Additionally, the vertices coordinates must be reversed, so the direction is right.
            left_vertices_temp = left_vertices
            left_vertices = right_vertices[::-1]
            right_vertices = left_vertices_temp[::-1]
            center_vertices = center_vertices[::-1]

        lanelet_id = self._id_allocator.new_id()
        new_lanelet = Lanelet(
            left_vertices=left_vertices,
            right_vertices=right_vertices,
            center_vertices=center_vertices,
            lanelet_id=lanelet_id,
            lanelet_type={lanelet_type},
        )
        self._lanelets.append(new_lanelet)

        if right:
            self.set_adjacent(new_lanelet, original_lanelet, same_direction=same_direction)
        else:
            self.set_adjacent(original_lanelet, new_lanelet, same_direction=same_direction)
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


def _add_intermediate_point_to_vertices(
    vertices: np.ndarray, intermediate_points: int = 5
) -> np.ndarray:
    x_vals = np.linspace(vertices[0][0], vertices[-1][0], intermediate_points + 2)
    y_vals = np.linspace(vertices[0][1], vertices[-1][1], intermediate_points + 2)

    return np.array(list(zip(x_vals, y_vals)))
