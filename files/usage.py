import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from scenario_factory.globetrotter.region import load_regions_from_csv
from scenario_factory.pipeline import PipelineContext
from scenario_factory.pipeline_steps import (
    WriteScenarioToFileArguments,
    pipeline_add_metadata_to_scenario,
    pipeline_assign_tags_to_scenario,
    pipeline_simulate_scenario_with_ots,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipeline_steps.simulation import SimulateScenarioArguments
from scenario_factory.pipelines import create_globetrotter_pipeline, create_scenario_generation_pipeline
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from scenario_factory.utils import select_osm_map_provider

root_logger = logging.getLogger("scenario_factory")
root_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
root_logger.addHandler(handler)

output_path = Path("/tmp/scenario_factory")
output_path.mkdir(exist_ok=True)
cities_file = Path("./files/cities_selected.csv")
input_maps_folder = Path("input_maps")
radius = 0.1
seed = 100

scenario_factory_config = ScenarioFactoryConfig(seed=seed, cr_scenario_time_steps=75)
simulation_config = SimulationConfig(mode=SimulationMode.DEMAND_TRAFFIC_GENERATION, simulation_steps=1000)

with TemporaryDirectory() as temp_dir:
    ctx = PipelineContext(Path(temp_dir), scenario_factory_config)

    map_provider = select_osm_map_provider(radius, input_maps_folder)

    base_pipeline = (
        create_globetrotter_pipeline(radius, map_provider)
        .map(pipeline_add_metadata_to_scenario)
        .map(pipeline_simulate_scenario_with_ots(SimulateScenarioArguments(config=simulation_config)))
    )

    scenario_generation_pipeline = create_scenario_generation_pipeline(
        scenario_factory_config.criterions, scenario_factory_config.filters
    )

    pipeline = (
        base_pipeline.chain(scenario_generation_pipeline)
        .map(pipeline_assign_tags_to_scenario)
        .map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    )

    inputs = load_regions_from_csv(cities_file)
    result = pipeline.execute(inputs, ctx)
    result.print_cum_time_per_step()
    print(result.values)
