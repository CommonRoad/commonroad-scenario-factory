from typing import Generator, List, Optional, Set

from commonroad.scenario.intersection import (
    Intersection,
    IntersectionIncomingElement,
)
from commonroad.scenario.lanelet import (
    Lanelet,
)

from scenario_factory.builder.core import BuilderCore, BuilderIdAllocator


class IntersectionIncomingElementBuilder(BuilderCore[IntersectionIncomingElement]):
    """
    The `IntersectionIncomingElementBuilder` is used to easily construct `IntersectionIncomingElement`s for intersections. It aids in automatically determining the correct successor lanelets for incoming lanelets.

    :param incoming_element_id: An unique CommonRoad id for the `IntersectionIncomingElement`.
    """

    def __init__(self, incoming_element_id: int):
        self._intersection_incoming_element = IntersectionIncomingElement(incoming_element_id)
        self._incoming_successors: Set[int] = set()

    def add_incoming_lanelet(self, incoming_lanelet: Lanelet):
        """
        Add `incoming_lanelet` to the incoming lanelets of this incoming element
        """
        if self._intersection_incoming_element.incoming_lanelets is None:
            self._intersection_incoming_element.incoming_lanelets = set()
        self._intersection_incoming_element.incoming_lanelets.add(incoming_lanelet.lanelet_id)

        self._incoming_successors.update(incoming_lanelet.successor)

        return self

    def _get_matching_predecessors(self, end_lanelet: Lanelet) -> Generator[int, None, None]:
        assert len(end_lanelet.predecessor) > 0

        for predecessor in end_lanelet.predecessor:
            if predecessor in self._incoming_successors:
                yield predecessor

    def connect_right(self, end: Lanelet):
        """
        Set all predecessors of `end` as a right successors of the incoming element if they are a successor of any of the incoming lanelets.
        """
        if self._intersection_incoming_element.successors_right is None:
            self._intersection_incoming_element.successors_right = set()

        for predecessor in self._get_matching_predecessors(end):
            self._intersection_incoming_element.successors_right.add(predecessor)

        return self

    def connect_straight(self, end: Lanelet):
        """
        Set all predecessors of `end` as a straight successors of the incoming element if they are a successor of any of the incoming lanelets.
        """
        if self._intersection_incoming_element.successors_straight is None:
            self._intersection_incoming_element.successors_straight = set()

        for predesccor in self._get_matching_predecessors(end):
            self._intersection_incoming_element.successors_straight.add(predesccor)

        return self

    def connect_left(self, end: Lanelet):
        """
        Set all predecessors of `end` as a left successors of the incoming element if they are a successor of any of the incoming lanelets.
        """
        if self._intersection_incoming_element.successors_left is None:
            self._intersection_incoming_element.successors_left = set()
        for predesccor in self._get_matching_predecessors(end):
            self._intersection_incoming_element.successors_left.add(predesccor)

        return self

    def build(self) -> IntersectionIncomingElement:
        """
        Construct the `IntersectionIncomingElement` from the builder configuration.
        """
        return self._intersection_incoming_element


class IntersectionBuilder(BuilderCore[Intersection]):
    """
    The `IntersectionBuilder` is used to easily create intersections. The main benefit from using `IntersectionBuilder` over constructing the `Intersection` manually, is the use of the `IntersectionIncomingElementBuilder`, which can automatically infer the relationships of lanelets inside an interesction.
    """

    def __init__(self, id_allocator: Optional[BuilderIdAllocator] = None):
        if id_allocator is None:
            self._id_allocator = BuilderIdAllocator()
        else:
            self._id_allocator = id_allocator

        self._incoming_element_builders: List[IntersectionIncomingElementBuilder] = []
        self._crossings: Set[int] = set()

    def create_incoming(self) -> IntersectionIncomingElementBuilder:
        """
        Create a new `IntersectionIncomingElementBuilder` which can be used to construct a new incoming element for this intersection.
        If this intersection is built, the incoming element will also automatically build.
        """
        incoming_lement_builder = IntersectionIncomingElementBuilder(
            self._id_allocator.new_id(),
        )
        self._incoming_element_builders.append(incoming_lement_builder)
        return incoming_lement_builder

    def add_crossing(self, crossing: Lanelet) -> "IntersectionBuilder":
        self._crossings.add(crossing.lanelet_id)
        return self

    def build(self) -> Intersection:
        """
        Construct the `Intersection` and all its `IntersectionIncomingElement`s from the builder configuration.
        """
        intersection_id = self._id_allocator.new_id()
        incoming_elements = [
            incoming_element_builder.build()
            for incoming_element_builder in self._incoming_element_builders
        ]
        return Intersection(
            intersection_id,
            incomings=incoming_elements,
            crossings=self._crossings,
        )
