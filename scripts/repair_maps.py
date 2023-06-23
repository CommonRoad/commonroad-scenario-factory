import multiprocessing
import os.path
import time
import traceback
from copy import deepcopy

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.file_writer import CommonRoadFileWriter
from crdesigner.map_validation_repairing.repairing.map_repairer import MapRepairer
from crdesigner.map_validation_repairing.validation.map_validation import MapValidation
from evaluate_solutions import timeout
from scenario_factory.scenario_util import iter_scenario_from_folder, iter_scenario_paths_from_folder

if __name__ == "__main__":
    in_folder = os.path.expanduser("~/out/2202_OSM_crawler/all")
    out_folder = "~/out/2202_OSM_crawlerRepaired"
    out_folder = os.path.join(os.path.expanduser(out_folder), time.strftime("%Y-%m-%d-%H%M%S"))
    out_folder_success =os.path.join(out_folder, "success")
    out_folder_exception_validation = os.path.join(out_folder, "exception_validation")
    out_folder_exception_repairing = os.path.join(out_folder, "exception_repairing")
    out_folder_unsuccessful_repairing = os.path.join(out_folder, "unsuccessful_repairing")
    num_cores = 18

    def repair(args):
        try:
            with timeout(180):
                path = args
                reader = CommonRoadFileReader(path)
                reader._read_header()
                scenario_orig = reader._open_scenario(lanelet_assignment=False)
                scenario = deepcopy(scenario_orig)
                rel_path = os.path.relpath(path, in_folder)
                invalid = None

                try:
                    print("-----------\nCheck!")
                    print(scenario.scenario_id)
                    invalid = MapValidation(scenario.scenario_id, scenario.lanelet_network).validate(1)
                    print("Found Problems!" if len(invalid) != 0 else "No problems, continue!")
                except Exception as e:
                    traceback.print_exc()
                    time.sleep(0.01)
                    out_path = os.path.join(out_folder_exception_validation, rel_path)
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    CommonRoadFileWriter(scenario_orig, planning_problem_set=None).write_scenario_to_file(out_path)
                    return
                if len(invalid) != 0:
                    try:
                        print("Repair!")
                        MapRepairer(scenario.lanelet_network, invalid).repair_map()
                    except Exception as e:
                        traceback.print_exc()
                        time.sleep(0.01)
                        out_path = os.path.join(out_folder_exception_repairing, rel_path)
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        CommonRoadFileWriter(scenario_orig, planning_problem_set=None).write_scenario_to_file(out_path)
                        return

                    invalid = MapValidation(scenario.scenario_id, scenario.lanelet_network).validate(1)
                    print("FAILED" if len(invalid) != 0 else "WORKED!")
                    print(invalid)

                if invalid is not None and len(invalid) == 0:
                    out_path = os.path.join(out_folder_success, rel_path)
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    CommonRoadFileWriter(scenario, planning_problem_set=None).write_scenario_to_file(out_path)
                else:
                    out_path = os.path.join(out_folder_unsuccessful_repairing, rel_path)
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    CommonRoadFileWriter(scenario_orig, planning_problem_set=None).write_scenario_to_file(out_path)
        except TimeoutError:
            return
        except:
            traceback.print_exc()
            return


    args = iter_scenario_paths_from_folder(in_folder)
    pool = multiprocessing.Pool(num_cores)
    data = pool.map(repair, args)