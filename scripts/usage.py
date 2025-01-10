import random
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    pipeline_simulate_scenario_with_sumo,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipelines import (
    create_scenario_generation_pipeline,
    select_osm_map_provider,
)
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.scenario_container import load_scenarios_from_folder
from scenario_factory.simulation import SimulationConfig, SimulationMode
from scenario_factory.utils import configure_root_logger

configure_root_logger()

output_path = Path("/tmp/scenario_factory")
output_path.mkdir(exist_ok=True)
cities_file = Path("./files/cities_selected.csv")
input_maps_folder = Path("input_maps")
radius = 0.1
seed = 100

scenario_factory_config = ScenarioFactoryConfig(seed=seed, cr_scenario_time_steps=150)
simulation_config = SimulationConfig(
    mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=600
)

random.seed(seed)
np.random.seed(seed)


with TemporaryDirectory() as temp_dir:
    ctx = PipelineContext(Path(temp_dir), scenario_factory_config)

    map_provider = select_osm_map_provider(radius, input_maps_folder)

    scenario_generation_pipeline = create_scenario_generation_pipeline(
        scenario_factory_config.criterions, scenario_factory_config.filters
    )

    pipeline = (
        Pipeline()
        .map(pipeline_simulate_scenario_with_sumo(simulation_config))
        .map(pipeline_write_scenario_to_file(output_path))
    )

    inputs = load_scenarios_from_folder(Path("/tmp/intersections"))
    result = pipeline.execute(inputs, ctx)
    result.print_cum_time_per_step()
    print(result.values)
