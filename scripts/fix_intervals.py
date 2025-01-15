from pathlib import Path
import time

from scenario_factory.pipeline import Pipeline
from scenario_factory.scenario_container import load_scenarios_from_folder
from scenario_factory.pipeline_steps import pipeline_extend_planning_problem_time_interval, \
    pipeline_write_scenario_to_file

time_start = time.time_ns()
scenario_containers = load_scenarios_from_folder(Path("/home/florian/Desktop/dec24_tmp/DEU_Riesa"))
print(f"Loading scenarios took {(time.time_ns() - time_start) / 1e9} s")

pipeline = Pipeline()
pipeline.map(pipeline_extend_planning_problem_time_interval)
pipeline.map(pipeline_write_scenario_to_file(Path("/home/florian/Desktop/dec24_fixed_interval")))

result = pipeline.execute(scenario_containers)

result.print_cum_time_per_step()