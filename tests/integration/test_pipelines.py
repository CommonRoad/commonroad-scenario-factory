import logging
import tempfile
from pathlib import Path

import scenario_factory
from scenario_factory.globetrotter.osm import LocalFileMapProvider
from scenario_factory.globetrotter.region import Coordinates, RegionMetadata
from scenario_factory.pipeline import PipelineContext
from scenario_factory.pipeline_steps import pipeline_simulate_scenario_with_sumo
from scenario_factory.pipeline_steps.simulation import SimulateScenarioArguments, pipeline_simulate_scenario_with_ots
from scenario_factory.pipelines import create_globetrotter_pipeline, create_scenario_generation_pipeline
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.scenario_types import ScenarioContainer
from scenario_factory.simulation.config import SimulationConfig, SimulationMode


class TestGlobetrotterPipeline:
    def test_globetrotter_pipeline_extracts_exactly_one_intersection(self):
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")
        map_provider = LocalFileMapProvider(input_maps_folder)
        globetrotter_pipeline = create_globetrotter_pipeline(radius=0.1, map_provider=map_provider)
        with tempfile.TemporaryDirectory() as tempdir:
            ctx = PipelineContext(Path(tempdir))
            coords = Coordinates(53.071054226968, 8.847098524980682)
            region = RegionMetadata.from_coordinates(coords)
            execution_result = globetrotter_pipeline.execute([region], ctx, num_threads=1, num_processes=1)
            assert len(execution_result.errors) == 0
            assert len(execution_result.values) == 1

            scenario = execution_result.values[0]
            assert isinstance(scenario, ScenarioContainer)


class TestScenarioGeneration:
    def test_scenario_generation_with_pipeline_creates_no_scenarios_for_empty_input(self):
        scenario_factory_config = ScenarioFactoryConfig(seed=10)
        scenario_generation_pipeline = create_scenario_generation_pipeline(
            scenario_factory_config.criterions, scenario_factory_config.filters
        )
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir)

            ctx = PipelineContext(output_path)

            result = scenario_generation_pipeline.execute([], ctx, num_threads=1, num_processes=1)
            assert len(result.errors) == 0
            assert len(result.values) == 0


class TestSimulationWithSumo:
    def test_globetrotter_and_simulation_with_sumo_creates_one_scenario(self):
        root_logger = logging.getLogger("scenario_factory")
        root_logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
        root_logger.addHandler(handler)
        scenario_factory_config = ScenarioFactoryConfig(seed=100, cr_scenario_time_steps=75)
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")
        map_provider = LocalFileMapProvider(input_maps_folder)
        pipeline = create_globetrotter_pipeline(radius=0.1, map_provider=map_provider)
        pipeline.map(
            pipeline_simulate_scenario_with_sumo(
                SimulateScenarioArguments(
                    config=SimulationConfig(mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=600)
                )
            )
        )

        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir)

            ctx = PipelineContext(output_path, scenario_factory_config)

            coords = Coordinates(53.071054226968, 8.847098524980682)
            region = RegionMetadata.from_coordinates(coords)
            result = pipeline.execute([region], ctx, num_threads=1, num_processes=1)
            assert len(result.errors) == 0, str(result.errors)
            assert len(result.values) == 1
            scenario = result.values[0].scenario
            assert len(scenario.dynamic_obstacles) > 0


class TestSimulationWithOts:
    def test_globetrotter_and_simulation_with_ots_creates_one_scenario(self):
        scenario_factory_config = ScenarioFactoryConfig(seed=100, cr_scenario_time_steps=75)
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")
        map_provider = LocalFileMapProvider(input_maps_folder)
        pipeline = create_globetrotter_pipeline(radius=0.1, map_provider=map_provider)
        pipeline.map(
            pipeline_simulate_scenario_with_ots(
                SimulateScenarioArguments(
                    config=SimulationConfig(mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=600)
                )
            )
        )

        with tempfile.TemporaryDirectory() as tempdir:
            ctx = PipelineContext(Path(tempdir), scenario_factory_config)

            coords = Coordinates(53.071054226968, 8.847098524980682)
            region = RegionMetadata.from_coordinates(coords)
            result = pipeline.execute([region], ctx, num_threads=1, num_processes=1)
            assert len(result.errors) == 0, str(result.errors)
            assert len(result.values) == 1
            scenario = result.values[0].scenario
            assert len(scenario.dynamic_obstacles) > 0
