import tempfile
from pathlib import Path

from sumocr.scenario.scenario_wrapper import CommonRoadFileReader

from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import pipeline_simulate_scenario_with_sumo
from scenario_factory.pipeline_steps.globetrotter import (
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_verify_and_repair_commonroad_scenario,
)
from scenario_factory.pipeline_steps.simulation import (
    SimulateScenarioArguments,
    pipeline_simulate_scenario_with_ots,
)
from scenario_factory.pipeline_steps.utils import (
    WriteScenarioToFileArguments,
    pipeline_add_metadata_to_scenario,
    pipeline_assign_tags_to_scenario,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipelines import create_scenario_generation_pipeline
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.scenario_container import load_scenarios_from_folder
from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from tests.resources import ResourceType


def _is_valid_commonroad_scenario(scenario_path: Path) -> bool:
    _, _ = CommonRoadFileReader(scenario_path).open()
    return True


class TestGlobetrotterPipeline:
    def test_globetrotter_pipeline_extracts_intersections(self):
        input_maps = ResourceType.OSM_MAP.get_folder().glob("*.osm")

        with tempfile.TemporaryDirectory() as tempdir:
            output_folder = Path(tempdir) / "intersections"
            output_folder.mkdir()
            globetrotter_pipeline = Pipeline()
            (
                globetrotter_pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
                .map(pipeline_verify_and_repair_commonroad_scenario)
                .map(pipeline_extract_intersections)
                .map(pipeline_add_metadata_to_scenario)
                .map(
                    pipeline_write_scenario_to_file(
                        WriteScenarioToFileArguments(output_folder=output_folder)
                    )
                )
            )
            ctx = PipelineContext(Path(tempdir))
            execution_result = globetrotter_pipeline.execute(
                input_maps, ctx, num_threads=None, num_processes=None
            )
            assert len(execution_result.errors) == 0
            assert len(execution_result.values) == 39

            for scenario_path in output_folder.glob("*.xml"):
                assert _is_valid_commonroad_scenario(scenario_path)


class TestScenarioGeneration:
    def test_scenario_generation_with_pipeline_creates_no_scenarios_for_empty_input(
        self,
    ):
        scenario_factory_config = ScenarioFactoryConfig(seed=10)
        scenario_generation_pipeline = create_scenario_generation_pipeline(
            scenario_factory_config.criterions, scenario_factory_config.filters
        )
        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir)

            ctx = PipelineContext(output_path, scenario_factory_config)

            result = scenario_generation_pipeline.execute(
                [], ctx, num_threads=None, num_processes=None
            )
            assert len(result.errors) == 0
            assert len(result.values) == 0

    def test_scenario_generation(self):
        input_scenarios = load_scenarios_from_folder(ResourceType.COMMONROAD_SCENARIO.get_folder())
        assert len(input_scenarios) > 0
        scenario_factory_config = ScenarioFactoryConfig(seed=1, cr_scenario_time_steps=15)
        scenario_generation_pipeline = create_scenario_generation_pipeline(
            scenario_factory_config.criterions, scenario_factory_config.filters
        )

        with tempfile.TemporaryDirectory() as tempdir:
            output_folder = Path(tempdir) / "test_result"
            output_folder.mkdir()
            (
                scenario_generation_pipeline.map(pipeline_add_metadata_to_scenario)
                .map(pipeline_assign_tags_to_scenario)
                .map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_folder)))
            )

            ctx = PipelineContext(Path(tempdir), scenario_factory_config)
            result = scenario_generation_pipeline.execute(
                input_scenarios, ctx, num_threads=None, num_processes=None
            )
            assert len(result.errors) == 0
            assert len(result.values) == 4

            for scenario_path in output_folder.glob("*.cr.xml"):
                assert _is_valid_commonroad_scenario(scenario_path)


class TestSimulationWithSumo:
    def test_simulate_scenario_with_sumo_creates_random_traffic_on_empty_map(self):
        input_maps = load_scenarios_from_folder(ResourceType.COMMONROAD_MAP.get_folder())
        assert len(input_maps) > 0

        with tempfile.TemporaryDirectory() as tempdir:
            output_folder = Path(tempdir) / "test_result"
            output_folder.mkdir()
            pipeline = Pipeline()
            (
                pipeline.map(
                    pipeline_simulate_scenario_with_sumo(
                        SimulateScenarioArguments(
                            config=SimulationConfig(
                                mode=SimulationMode.RANDOM_TRAFFIC_GENERATION,
                                simulation_steps=300,
                            )
                        )
                    )
                )
                .map(pipeline_add_metadata_to_scenario)
                .map(
                    pipeline_write_scenario_to_file(
                        WriteScenarioToFileArguments(output_folder=output_folder)
                    )
                )
            )
            ctx = PipelineContext(Path(tempdir))

            result = pipeline.execute(input_maps, ctx, num_threads=None, num_processes=None)
            assert len(result.errors) == 0, str(result.errors)
            assert len(result.values) == 3

            for scenario_container in result.values:
                assert len(scenario_container.scenario.dynamic_obstacles) > 0

            for scenario_path in output_folder.glob("*.xml"):
                assert _is_valid_commonroad_scenario(scenario_path)


class TestSimulationWithOts:
    def test_simulate_scenario_with_ots_creates_random_traffic_on_empty_map(self):
        input_maps = load_scenarios_from_folder(ResourceType.COMMONROAD_MAP.get_folder())
        assert len(input_maps) > 0

        with tempfile.TemporaryDirectory() as tempdir:
            output_folder = Path(tempdir) / "test_result"
            output_folder.mkdir()
            pipeline = Pipeline()
            (
                pipeline.map(
                    pipeline_simulate_scenario_with_ots(
                        SimulateScenarioArguments(
                            config=SimulationConfig(
                                mode=SimulationMode.RANDOM_TRAFFIC_GENERATION,
                                simulation_steps=300,
                            )
                        )
                    )
                )
                .map(pipeline_add_metadata_to_scenario)
                .map(
                    pipeline_write_scenario_to_file(
                        WriteScenarioToFileArguments(output_folder=output_folder)
                    )
                )
            )
            ctx = PipelineContext(Path(tempdir))

            result = pipeline.execute(input_maps, ctx, num_threads=None, num_processes=None)
            assert len(result.errors) == 0, str(result.errors)
            assert len(result.values) == len(input_maps)

            for scenario_container in result.values:
                assert len(scenario_container.scenario.dynamic_obstacles) > 0

            for scenario_path in output_folder.glob("*.xml"):
                assert _is_valid_commonroad_scenario(scenario_path)
