"""
Script for naming scenarios according to the CommonRoad xml specification.
Considers names of all existing CR scenarios -> ensures ascending scenario ids and avoids duplicates.
"""
import glob
import os
import pickle
import shutil
from collections import defaultdict

from commonroad.common.file_reader import CommonRoadFileReader

# folder with scenarios which should be renamed
foldername = "/home/klischatm/out/2202_save_the_salary/selected"
solution_folder = "/home/klischatm/out/2202_save_the_salary/20220304-181804/solutions"
solution_folder_out = "/home/klischatm/out/2202_save_the_salary/solutions_selected"
# output folder
foldername_out = "/home/klischatm/out/2202_save_the_salary/selected_renamed"
tags = []

map_id_dict = {}  # if scene id not in map_id_dict -> create new scene id (default case)
config_id_dict = defaultdict(lambda: 0)

# rename scenarios
for cr_file in glob.glob(os.path.join(foldername, "**/*.cr.xml"), recursive=True):
    print("Read scenario with ID:", cr_file)
    scenario_folder_tmp = os.path.dirname(cr_file)
    scenario, pp = CommonRoadFileReader(os.path.join(foldername, cr_file)).open()

    scenario_id_str_old = str(scenario.scenario_id)

    scene_id_orig = (scenario.scenario_id.country_id, scenario.scenario_id.map_name, scenario.scenario_id.map_id)
    config_id_dict[scene_id_orig] += 1
    if scene_id_orig not in map_id_dict:
        map_id_dict[scene_id_orig] = 1 + max(
            (
                map_id_new
                for [country_id, map_name, _], map_id_new in map_id_dict.items()
                if (country_id, map_name) == scene_id_orig[:2]
            ),
            default=0,
        )

    scenario.scenario_id.map_id = map_id_dict[scene_id_orig]
    scenario.scenario_id.configuration_id = config_id_dict[scene_id_orig]

    # # change pickle config
    with open(os.path.join(scenario_folder_tmp, "simulation_config.p"), "rb") as f:
        config = pickle.load(f)

    config.scenario_name = str(scenario.scenario_id)
    with open(os.path.join(scenario_folder_tmp, "simulation_config.p"), "wb") as f:
        pickle.dump(config, f)

    # change ID in scenario file
    files = list(glob.glob(os.path.join(scenario_folder_tmp, "*.xml"))) + list(
        glob.glob(os.path.join(scenario_folder_tmp, "*.cfg"))
    )
    for f in files:
        if not f.endswith("rou.xml"):
            # rename strings
            with open(f, "rt") as file_in:
                file_str = file_in.read()

            file_str = file_str.replace(scenario_id_str_old, str(scenario.scenario_id))
            if f.endswith("net.xml"):
                file_str = file_str[file_str.find("-->") + len("-->") :]

            with open(f, "wt") as file_out:
                file_out.write(file_str)

        # rename filename
        file_new = os.path.basename(f)
        file_new = file_new.replace(scenario_id_str_old, str(scenario.scenario_id))
        file_new = os.path.join(os.path.dirname(f), file_new)
        os.rename(f, file_new)

    scenario_folder_new = os.path.join(foldername_out, str(scenario.scenario_id))
    shutil.move(scenario_folder_tmp, scenario_folder_new)
    scenario_folder_tmp = scenario_folder_new
    # rename solution file
    solution_path_new = os.path.join(solution_folder_out, f"solution_KS1:TR1:{str(scenario.scenario_id)}:2020a.xml")
    shutil.copy(os.path.join(solution_folder, f"solution_KS1:TR1:{scenario_id_str_old}:2020a.xml"), solution_path_new)

    with open(solution_path_new, "rt") as file_in:
        file_str = file_in.read()

    file_str = file_str.replace(scenario_id_str_old, str(scenario.scenario_id))

    with open(solution_path_new, "wt") as file_out:
        file_out.write(file_str)
