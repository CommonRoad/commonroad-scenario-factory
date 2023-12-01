import os
import unittest
import matplotlib
import pickle
import numpy as np
from commonroad.common.util import Interval

from commonroad.scenario.scenario import Scenario
from cr_scenario_features.models.scenario_model import ScenarioModel

matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from commonroad.visualization.draw_dispatch_cr import draw_object
from commonroad.common.file_reader import CommonRoadFileReader

from cr_scenario_features.models.lane_model import LaneletSectionNetwork


class TestScenarioModel(unittest.TestCase):
    def setUp(self) -> None:
        files = ['test_files/USA_Lanker-2_20_T-1.xml', 'test_files/ITA_CarpiCentro-6_1_T-1.xml']
        self.intersection_files = [os.path.join(os.path.dirname(__file__), file) for file in files]

    def test_distance(self):
        load = False
        if load is False:
            scenario, pp = CommonRoadFileReader(self.intersection_files[0]).open(lanelet_assignment=False)
            scenario.assign_obstacles_to_lanelets(time_steps=[0], use_center_only=True)
            os.remove(self.intersection_files[0] + ".obj")
            filehandler = open(self.intersection_files[0] + ".obj", "wb")
            pickle.dump(scenario, filehandler)
            filehandler.close()
        else:
            file = open(self.intersection_files[0] + ".obj", 'rb')
            scenario:Scenario = pickle.load(file)
            file.close()
        # plt.ion()
        # plt.figure()
        # draw_object(scenario, draw_params={'time_end':0,'dynamic_obstacle': {'show_label': True},
        #                                    'lanelet': {'show_label': True}})
        # plt.autoscale()
        # plt.axis('equal')
        # plt.draw()
        # plt.pause(100)
        sm = ScenarioModel(scenario)
        init_pos = scenario.obstacle_by_id(2533).initial_state.position
        obs_array = sm.get_obstacles_array(init_pos)
        for ii, array in enumerate(obs_array):
            print(ii)
            plt.figure()
            draw_object(scenario.lanelet_network)
            draw_object(scenario.obstacle_by_id(2533), draw_params={'time_end':0,'dynamic_obstacle': {'show_label': True}})
            draw_object([scenario.obstacle_by_id(obs) for obs in array[0]], draw_params={'time_end':0,'dynamic_obstacle': {'show_label': True}})
            plt.title(str(ii))
            plt.axis('equal')
            plt.autoscale()
            plt.show()
            for obs_id, pos, lat_index in zip(array[0], array[1], array[2]):
                print(obs_id, pos, lat_index)

            plt.pause(1)
            break

    def test_closest_obstacles(self):

        load = False
        for file in self.intersection_files[1:]:
            if load is False:
                scenario, pp = CommonRoadFileReader(file).open(lanelet_assignment=False)
                scenario.assign_obstacles_to_lanelets(time_steps=[0], use_center_only=True)
                try:
                    os.remove(file + ".obj")
                except:
                    pass
                filehandler = open(file + ".obj", "wb")
                pickle.dump(scenario, filehandler)
                filehandler.close()
            else:
                file = open(file + ".obj", 'rb')
                scenario: Scenario = pickle.load(file)
                file.close()

            plt.ion()
            plt.figure()
            draw_object(scenario, draw_params={'time_end':0,'dynamic_obstacle': {'show_label': True},
                                               'lanelet': {'show_label': True}})
            plt.autoscale()
            plt.axis('equal')

            sm = ScenarioModel(scenario)
            obs = scenario.obstacle_by_id(2533)
            init_pos = np.array([0.0, 0.0])
            init_pos = list(pp.planning_problem_dict.values())[0].initial_state.position
            print(init_pos)
            plt.scatter(init_pos[0], init_pos[1], zorder=1000)
            rear_vehicles, front_vehicles = sm. \
                get_array_closest_obstacles(init_pos,
                                            longitudinal_range=Interval(-50, 50),
                                            relative_lateral_indices=True,
                                            time_step=0)
            print(rear_vehicles)
            print(front_vehicles)
            obs_array = sm.get_obstacles_array(init_pos)
            for ii, array in enumerate(obs_array):
                print(ii)
                # plt.figure()
                # draw_object(scenario.lanelet_network)
                # draw_object(scenario.obstacle_by_id(2533),
                #             draw_params={'time_end': 0, 'dynamic_obstacle': {'show_label': True}})
                # draw_object([scenario.obstacle_by_id(obs) for obs in array[0]],
                #             draw_params={'time_end': 0, 'dynamic_obstacle': {'show_label': True}})
                # plt.title(str(ii))
                # plt.axis('equal')
                # plt.autoscale()
                # plt.show()
                for obs_id, pos, lat_index in zip(array[0], array[1], array[2]):
                    print(obs_id, pos, lat_index)

            plt.show()
            # plt.pause(100)



if __name__ == '__main__':
    unittest.main()
