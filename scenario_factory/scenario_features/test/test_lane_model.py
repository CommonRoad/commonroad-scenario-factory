import os
import unittest
import matplotlib

matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.visualization.draw_dispatch_cr import draw_object
from cr_scenario_features.models.lane_model import LaneletSectionNetwork
from cr_scenario_features.models.scenario_model import ScenarioModel


class TestLaneModel(unittest.TestCase):
    def setUp(self) -> None:
        self.intersection_file = os.path.join(os.path.dirname(__file__), 'test_files/USA_Lanker-2_20_T-1.xml')

    def test_distance(self):
        scenario, pp = CommonRoadFileReader(self.intersection_file).open(lanelet_assignment=False)
        # plt.ion()
        # plt.figure()
        # draw_object(scenario.lanelet_network, draw_params={'lanelet': {'show_label': True}})
        # plt.autoscale()
        # plt.axis('equal')
        # plt.show(0.01)

        lsn = LaneletSectionNetwork.from_lanelet_network(scenario.lanelet_network)
        s1 = lsn.lanelet2section_id[3566]
        s2 = lsn.lanelet2section_id[3522]
        dist, path = lsn.compute_longitudinal_distance(5., 5., s1, s2)
        assert dist > 10

if __name__ == '__main__':
    unittest.main()
