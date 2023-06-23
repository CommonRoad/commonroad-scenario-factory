import io
import json
import random
import shutil
import signal
import time
import traceback
from multiprocessing.pool import Pool
from zipfile import ZipFile

import matplotlib
import yaml
from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad_dc.collision.collision_detection.pycrcc_collision_dispatch import create_collision_object
from commonroad_dc.collision.collision_detection.scenario import create_collision_checker_scenario
from commonroad_dc.feasibility.solution_checker import valid_solution, CollisionException, GoalNotReachedException, \
    _construct_boundary_checker, starts_at_correct_ts, solution_feasible
from simulation.simulations import simulate_with_solution, load_sumo_configuration, simulate_without_ego, \
    SimulationOption, simulate_scenario
from sumocr.maps.sumo_scenario import ScenarioWrapper


import copy
import glob
import itertools
import math
import os.path
import warnings
from typing import List, Tuple

import cv2

import numpy as np
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.solution import VehicleType, CostFunction, CommonRoadSolutionReader, Solution
from commonroad.scenario.scenario import ScenarioID
from commonroad.visualization.mp_renderer import MPRenderer
from commonroad_dc.costs.route_matcher import LaneletRouteMatcher

import matplotlib.pyplot as plt
import pandas as pd
from commonroad_dc.costs.evaluation import PartialCostFunction, required_properties, PartialCostFunctionMapping, \
    cost_function_mapping

class Evaluator:
    def __init__(self):
        # self.test_scenario_dir = "/home/klischat/out/2021_competition_scenarios/examples/selection"
        self.test_scenario_dir = os.path.expanduser(f"/home/klischatm/out/2202_save_the_salary/selected_renamed")
        # self.solutions_dir = "/home/klischat/out/2021_competition_scenarios/examples/solutions"
        self.solutions_dir = os.path.expanduser(f"/home/klischatm/out/2202_save_the_salary/solutions_selected")
        # self.path_videos_out = "/home/klischat/out/2021_competition_scenarios/examples/out_videos_selection"
        self.path_videos_out = os.path.expanduser(f"~/out/2202_save_the_salary/video")
        self.simulated_scenarios_dir = os.path.expanduser(f"~/out/2202_save_the_salary/simscenarios")
        self.i = 0
        self.all_scenario_dir = os.path.expanduser(f"~/GIT_REPOS/commonroad-scenarios-dev/scenarios")
        self.config_paths = list(glob.glob(os.path.join(self.test_scenario_dir, "*_I-*/simulation_config.p"), recursive=True))
        print(self.config_paths)
        self.cost_funcs = [CostFunction.TR1,
                           # CostFunction.MW1,
                           # CostFunction.SA1,
                           # CostFunction.WX1,
                           # CostFunction.SM1,
                           # CostFunction.SM2,
                           # CostFunction.SM3
                           ]

    def _get_scenario_paths(self, scenario_id: ScenarioID = None):
        if scenario_id is None:
            return glob.glob(os.path.join(self.all_scenario_dir, "*.xml"), recursive=True)
        else:
            return glob.glob(os.path.join(self.all_scenario_dir, f"**/*/{str(scenario_id)}.xml"), recursive=True)

    def _get_scenario_paths_interactive(self, scenario_id: ScenarioID = None):
        assert scenario_id.obstacle_behavior == "I"
        id_str = str(scenario_id)
        for path in self.config_paths:
            if id_str in path:
                return os.path.dirname(path)
        raise FileNotFoundError

    def _open_scenario_by_id(self, scenario_id: ScenarioID):
        paths = self._get_scenario_paths(scenario_id)
        if not paths:
            raise ValueError(f"No scenario with ID {scenario_id} found in path {self.all_scenario_dir}")
        scenario, pp = CommonRoadFileReader(paths[0]).open()
        if not scenario.scenario_id == scenario_id:
            warnings.warn(
                f"{str(scenario.scenario_id)}:{scenario.scenario_id.scenario_version} "
                f" != {str(scenario_id)}:{scenario_id.scenario_version}")
        return scenario, pp

    def _open_solution_scenario(self, solution_path: str):
        solution = CommonRoadSolutionReader.open(solution_path)
        s, pp = self._open_scenario_by_id(solution.scenario_id)
        return solution, s, pp

    def compute_costs(self, sol, sce, pp):
        # for i, s in enumerate(files):
        self.i += 1
        print(f"evaluate solution {self.i}")
        evaluation_result = None
        try:
            lm = LaneletRouteMatcher(sce, list(sol.planning_problem_solutions)[0].vehicle_type)
            required_properties_all = set(itertools.chain.from_iterable(required_properties.values()))
            for pp_sol in sol.planning_problem_solutions[:1]:
                trajectory, _, properties = lm.compute_curvilinear_coordinates(pp_sol.trajectory,
                                                                               required_properties=required_properties_all,
                                                                               draw_lanelet_path=False)
                evaluation_result = {"scenario_id": str(sce.scenario_id),
                                     "solution_file": str(os.path.basename(str(sol.scenario_id)))}
                for pcf, pcf_func in PartialCostFunctionMapping.items():
                    # TODO: remove normalization again after tuning
                    evaluation_result[pcf.value] = 1/len(trajectory.state_list)*30 * pcf_func(sce, pp.planning_problem_dict[pp_sol.planning_problem_id],
                                                            trajectory, properties)
        except Exception as e:
            print(traceback.format_exc())
            warnings.warn(f"solution {self.i} fails with error:\n{str(e)}")
            return None
        return evaluation_result

    def resimulate_interactive_scenarios(self, solution_path: str):
        print(f"start {solution_path}")
        # if "DEU_Frankfurt-33_2_I-1.xml" in solution_path:
        #     return
        # scenarios = [os.path.basename(p) for p in glob.glob("/home/klischat/Downloads/test/saveSalary/*.xml")]
        # if os.path.basename(solution_path) in scenarios:
        #     print('ALREWADY EXISTS!')
        #     return
        solution = CommonRoadSolutionReader.open(solution_path)
        try:
            path_scenario = self._get_scenario_paths_interactive(solution.scenario_id)

            scenario, pps, traj_solution = simulate_with_solution(interactive_scenario_path=path_scenario,
                                                                  output_folder_path=self.path_videos_out,
                                                                  solution=solution,
                                                                  create_video=SAVE_VIDEOS)
        except Exception as e:
            # raise
            traceback.print_exc()
            raise
            return

        # list(pps._planning_problem_dict.values())[0]._initial_state.position = list(traj_solution.values())[0].initial_state.position
        # scenario_file = os.path.join(path_scenario, f"{os.path.basename(path_scenario)}.cr.xml")
        # scenario_init, _ = CommonRoadFileReader(scenario_file).open()
        #
        # CommonRoadFileWriter(scenario_init, pps).write_to_file(scenario_file,
        #                                                   overwrite_existing_file=OverwriteExistingFile.ALWAYS)
        #
        # return (list(pps.planning_problem_dict.values())[0].initial_state.position, list(traj_solution.values())[0].initial_state.position)
        # scenario, pps = simulate_without_ego(interactive_scenario_path=path_scenario,
        #                                                     output_folder_path=self.path_videos_out,
        #                                                     create_GIF=True)


        # scenario

        try:
            valid = valid_solution(scenario, pps, solution)
        except (CollisionException, GoalNotReachedException) as e:
            warnings.warn(f"Infeasible {type(e)}: {str(solution.scenario_id)}")
            valid = (False, e)
        # if SAVE_SIMULATED_SCENARIOS and valid[1] != CollisionException:
        #     CommonRoadFileWriter(scenario, pps).write_to_file(os.path.join(self.simulated_scenarios_dir,
        #                                                                    os.path.basename(solution_path)),
        #                                                       overwrite_existing_file=OverwriteExistingFile.ALWAYS)
        #     print(f"XVALID SOLUTION: {valid}")
        # else:
        #     os.remove(solution_path)
        #     print(f"INVALID SOLUTION: {valid}")
        return valid, self.compute_costs(solution, scenario, pps)

    def evaluate_all_solutions(self, files=None):
        if files is None:
            solution_files  = [s for s in (glob.glob(os.path.join(self.solutions_dir, "**/*.xml"), recursive=True))[:] if "NOT_FOUND" not in s]
        else:
            solution_files = files

        # with ZipFile('/home/klischat/LRZSyncShare/09_commonroad/202011_CR_competition/commonroad-competition/workshop/evaluation/scenarios-sumo.zip', 'r') as zipObj:
        #     files = zipObj.namelist()
        # solution_files = [s for s in solution_files if os.path.basename(s) not in files]
        # results = [self.resimulate_interactive_scenarios(s) for s in solution_files[:]]
        n_cores = 10
        pool = Pool(n_cores)
        results = pool.map(self.resimulate_interactive_scenarios, solution_files[:])
        return results

    def check_configs(self, n):
        solution_files  = [s for s in (glob.glob(os.path.join(self.solutions_dir, "*.xml"), recursive=False))[:] if "NOT_FOUND" not in s]
        for sol in solution_files[:n]:
            solution = CommonRoadSolutionReader.open(sol)
            path_scenario = self._get_scenario_paths_interactive(solution.scenario_id)
            conf = load_sumo_configuration(path_scenario)
            print(conf.__dict__)

    def basic_collision_check(self, solution_path):

        solution = CommonRoadSolutionReader.open(solution_path)
        interactive_scenario_path = self._get_scenario_paths_interactive(solution.scenario_id)
        try:
            conf = load_sumo_configuration(interactive_scenario_path)
            conf.simulation_steps = 3
            scenario_file = os.path.join(interactive_scenario_path, f"{conf.scenario_name}.cr.xml")
            scenario, planning_problem_set = CommonRoadFileReader(scenario_file).open()

            scenario_wrapper = ScenarioWrapper()
            scenario_wrapper.sumo_cfg_file = os.path.join(interactive_scenario_path, f"{conf.scenario_name}.sumo.cfg")
            scenario_wrapper.initial_scenario = scenario

            scenario_with_solution, ego_vehicles = simulate_scenario(SimulationOption.SOLUTION, conf,
                                                                     scenario_wrapper,
                                                                     interactive_scenario_path,
                                                                     num_of_steps=conf.simulation_steps,
                                                                     planning_problem_set=planning_problem_set,
                                                                     solution=solution,
                                                                     use_sumo_manager=False)
            scenario_with_solution.scenario_id = scenario.scenario_id

            for pp_id, planning_problem in planning_problem_set.planning_problem_dict.items():
                obstacle_ego = ego_vehicles[pp_id].get_dynamic_obstacle()

            cc = create_collision_checker_scenario(scenario)
            try:
                self.compute_costs(solution, scenario, planning_problem_set)
            except:
                return {interactive_scenario_path: (False, False, True)}
            with timeout(seconds=14):
                t0 = time.time()
                cc_boundary = _construct_boundary_checker(scenario)
                ego_obs = create_collision_object(list(solution.create_dynamic_obstacle().values())[0])
                print("TIMnE", time.time() - t0)
            return {interactive_scenario_path: (cc.collide(create_collision_object(obstacle_ego)), cc_boundary.collide(ego_obs), False)}
        except TimeoutError as e:
            print("UNEX:", e)
            return {interactive_scenario_path: (True, True, False)}

    def delete_collision_scenarios(self, n0=0):
        solution_files  = [s for s in (glob.glob(os.path.join(self.solutions_dir, "*.xml"), recursive=False))[:] if "NOT_FOUND" not in s]
        results = []
        # for i, s in enumerate(solution_files[n0:]):
        #     results.append(self.basic_collision_check(s))
        #
        #     result = {}
        #     for r in results:
        #         result.update(r)
        #
        #     with io.open(f"/home/klischatm/SCENARIO_FACTORY/coll_stat{n0}.json", 'w', encoding='utf8') as outfile:
        #         json.dump(result, outfile, indent=2, sort_keys=True)

        n_cores = 14
        pool = Pool(n_cores)
        for n0_ in range(n0, len(solution_files), n_cores):
            results.extend(pool.map(self.basic_collision_check, solution_files[n0_:n0_+n_cores]))
            with io.open(os.path.expanduser(f"~/SCENARIO_FACTORY/coll_stat{n0}.json"), 'w', encoding='utf8') as outfile:
                json.dump(results, outfile, indent=2, sort_keys=True)

        return results

    def visualize_goals(self):
        solution_files = [s for s in (glob.glob(os.path.join(self.solutions_dir, "*.xml"), recursive=False))[:] if
                          "NOT_FOUND" not in s]
        for s in solution_files:
            solution = CommonRoadSolutionReader.open(s)
            pos = list(solution.create_dynamic_obstacle().values())[0].prediction.trajectory.state_list[-1].position
            plt_limits = [pos[0]-100, pos[0]+100, pos[1]-100, pos[1]+100]
            rnd = MPRenderer(plot_limits=plt_limits, figsize=(20,15))
            list(solution.create_dynamic_obstacle().values())[0].draw(rnd,
                                                                      draw_params={"time_begin": 198, "time_end":199})
            path_scenario = os.path.join(self._get_scenario_paths_interactive(solution.scenario_id),
                                         str(solution.scenario_id) + ".cr.xml")
            sc, pp = CommonRoadFileReader(path_scenario).open()
            sc.draw(rnd)
            pp.draw(rnd)
            rnd.render()
            plt.show(block=False)
            plt.title(str(sc.scenario_id))
            plt.pause(1)
            # pos = list(solution.create_dynamic_obstacle().values())[0].prediction.trajectory.state_list[0].position
            # plt_limits = [pos[0]-60, pos[0]+60, pos[1]-60, pos[1]+60]
            # plt.pause(1)
            plt.close("all")


class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

if __name__ == "__main__":
    files = None # ["/home/klischat/Downloads/test/debug_desmond/fd2145ce-d371-43c9-a40c-d47c53e82600.xml"]
    # SAVE_SIMULATED_SCENARIOS = False
    SAVE_VIDEOS = True
    eval = Evaluator().evaluate_all_solutions(files)
    # dist = []
    # for pos in results:
    #     if pos is not None:
    #         dist.append(np.linalg.norm(pos[0]-pos[1]))

    def copytree2(source, dest):
        # os.mkdir(dest)
        dest_dir = os.path.join(dest,os.path.basename(source))
        shutil.copytree(source, dest_dir)

    # for config_file in eval.config_paths:
    #     # conf = migrate_config_file(str(config_file))
    #     config_file_out = os.path.join(interactive_scenario_path_out,
    #                                    os.path.basename(os.path.dirname(config_file)),
    #                                    os.path.basename(config_file))
    #     if not os.path.isfile(config_file_out):
    #         continue
    #     conf = migrate_competition(str(config_file))
    #     # print(config_file)
    #     # print(conf.scenario_name)
    #     with open(config_file_out, 'wb') as f:
    #         pickle.dump(conf, f)
    #
    #     #
    #     copytree2(file, out)



    # from sumocr.sumo_config import DefaultConfig
    # for config_file in glob.glob(os.path.join(interactive_scenario_path_out, "**/*.p"), recursive=True):
    #     # conf = migrate_config_file(str(config_file))
    #     print(config_file)
    #     with open(config_file, "rb") as input_file:
    #         conf_load = pickle.load(input_file)
    #     print(conf_load.scenario_name)

    # plt.figure()
    # plt.hist(dist)
    # plt.show(block=True)


    # n0 = 0
    # results = Evaluator().delete_collision_scenarios(n0=n0)
    # result = {}
    # for r in results:
    #     result.update(r)
    #
    # with io.open(f"/home/klischatm/SCENARIO_FACTORY/coll_stat_final{n0}.json", 'w', encoding='utf8') as outfile:
    #     json.dump(result, outfile, indent=2, sort_keys=True)
    #
    #
    #


    # def cop_state(inpath):
    #     with io.open(inpath, 'r', encoding='utf8') as outfile:
    #         results = json.load(outfile)
    #
    #     n = 0
    #     print(results)
    #     out = "/home/klischatm/SCENARIO_FACTORY/selection"
    #     for result in results:
    #         for file, res in result.items():
    #             sname = os.path.basename(file)
    #             # file = os.path.join(os.path.dirname(os.path.dirname(file)), "OLD_300/scenarios", sname)
    #             if not True in res:
    #                 try:
    #                     copytree2(file, out)
    #                     n += 1
    #                 except:
    #                     continue
    #     return n
    #
    #
    # n = 0
    # for file in glob.glob("/home/klischatm/SCENARIO_FACTORY/collision_stats/coll_stat*.json"):
    #     n += cop_state(file)
    #
    # print("sucess", n)
    #
    # for p1, p2, p3 in os.walk("/home/klischatm/SCENARIO_FACTORY/selection"):
    #     scenario_files = [os.path.join(p1, p) for p in p2]
    #     break
    #
    # samples = random.sample(scenario_files, 200)
    # for sample in samples:
    #     shutil.move(sample, os.path.join("/home/klischatm/SCENARIO_FACTORY/selection_200", os.path.basename(sample)))
