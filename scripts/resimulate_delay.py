from pathlib import Path

from scenario_factory.pipeline.pipeline import Pipeline
from scenario_factory.pipeline_steps.simulation import (
    pipeline_simulate_scenario_with_sumo,
)
from scenario_factory.pipeline_steps.utils import (
    pipeline_write_scenario_to_file,
)
from scenario_factory.scenario_container import load_scenarios_from_folder
from scenario_factory.simulation.config import SimulationConfig, SimulationMode

input_folder = Path("../cr-ots-interface/resources/mona")
output_folder = Path("/tmp/scenario_factory")
output_folder.mkdir(exist_ok=True)

pipeline = Pipeline()
pipeline.map(pipeline_simulate_scenario_with_sumo(SimulationConfig(mode=SimulationMode.DELAY)))
pipeline.map(pipeline_write_scenario_to_file(output_folder))

scenario_containers = load_scenarios_from_folder(input_folder)
result = pipeline.execute(scenario_containers)
