import numpy as np
from commonroad.scenario.lanelet import Lanelet, LaneletNetwork

from scenario_factory.builder import LaneletNetworkBuilder
from scenario_factory.builder.core import BuilderIdAllocator


class UsefulLaneletNetworks:
    """
    Contains a collection of simple dynamically constructed lanelet networks that can be used for testing.
    """

    @staticmethod
    def empty_no_meta() -> LaneletNetwork:
        builder = LaneletNetworkBuilder()
        return builder.build()

    @staticmethod
    def malformed_one_split_no_meta() -> LaneletNetwork:
        id_allocator = BuilderIdAllocator(seed=0)  # TODO: Feels wrong to have to do this...
        builder = LaneletNetworkBuilder(id_allocator)
        lanelet1 = builder.add_lanelet((0, -5), (20, -5), 10)
        lanelet2 = builder.add_lanelet((80, -5), (100, -5), 10)
        lanelet3 = builder.add_lanelet((20, -5), (40, 15), 10)

        lanelet1.add_successor(lanelet2.lanelet_id)
        lanelet1.add_successor(lanelet3.lanelet_id)
        lanelet2.add_predecessor(lanelet1.lanelet_id)
        lanelet3.add_predecessor(lanelet1.lanelet_id)
        return builder.build()

    @staticmethod
    def one_split_no_meta() -> LaneletNetwork:
        id_allocator = BuilderIdAllocator(seed=0)  # TODO: Feels wrong to have to do this...
        builder = LaneletNetworkBuilder(id_allocator)
        lanelet1 = builder.add_lanelet((0, -5), (20, -5), 10)
        lanelet2 = builder.add_lanelet((20, -5), (40, -5), 10)
        lanelet3 = builder.add_lanelet((20, -5), (40, 15), 10)

        lanelet1.add_successor(lanelet2.lanelet_id)
        lanelet1.add_successor(lanelet3.lanelet_id)
        lanelet2.add_predecessor(lanelet1.lanelet_id)
        lanelet3.add_predecessor(lanelet1.lanelet_id)
        return builder.build()

    @staticmethod
    def single_intersection() -> LaneletNetwork:
        raise NotImplementedError()

    @staticmethod
    def single_lanelet_no_meta() -> LaneletNetwork:
        left = np.array([[0, 0], [20, 0], [20, 20]])
        right = np.array([[0, -10], [30, -10], [30, 20]])
        lanelet1 = Lanelet(left, (left + right) / 2, right, 1)
        return LaneletNetwork.create_from_lanelet_list([lanelet1])

    @staticmethod
    def single_lanelet_traffic_light() -> LaneletNetwork:
        id_allocator = BuilderIdAllocator(seed=0)
        builder = LaneletNetworkBuilder(id_allocator)
        lanelet1 = builder.add_lanelet((0, 0), (20, 0), 10)
        lanelet2 = builder.add_lanelet((20, 0), (40, 0), 10)
        lanelet1.add_successor(lanelet2.lanelet_id)
        lanelet2.add_predecessor(lanelet1.lanelet_id)
        tl = builder.create_traffic_light()
        tl.for_lanelet(lanelet1)
        return builder.build()

    @staticmethod
    def single_lanelet_traffic_light_no_successor() -> LaneletNetwork:
        raise NotImplementedError()

    @staticmethod
    def single_lanelet_traffic_sign() -> LaneletNetwork:
        raise NotImplementedError()
