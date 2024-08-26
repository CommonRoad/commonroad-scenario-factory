import random
import tempfile
from pathlib import Path

import numpy as np
from crdesigner.map_conversion.sumo_map.config import SumoConfig

import scenario_factory
from scenario_factory.globetrotter.osm import LocalFileMapProvider
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    ExtractOsmMapArguments,
    GenerateCommonRoadScenariosArguments,
    LoadRegionsFromCsvArguments,
    pipeline_assign_tags_to_scenario,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_generate_ego_scenarios,
    pipeline_load_regions_from_csv,
    pipeline_simulate_scenario_with_sumo,
    pipeline_verify_and_repair_commonroad_scenario,
)
from scenario_factory.scenario_types import EgoScenarioWithPlanningProblemSet


class TestScenarioGeneration:
    def test_scenario_generation_with_pipeline_creates_scenarios(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath(
            "tests/integration/cities_selected_test.csv"
        )
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")
        map_provider = LocalFileMapProvider(input_maps_folder)

        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir)

            seed = 10
            sumo_config = SumoConfig()
            sumo_config.simulation_steps = 600
            sumo_config.random_seed = seed
            sumo_config.random_seed_trip_generation = seed
            random.seed(seed)
            np.random.seed(seed)

            ctx = PipelineContext(output_path, sumo_config=sumo_config)
            pipeline = Pipeline(ctx)

            pipeline.populate(pipeline_load_regions_from_csv(LoadRegionsFromCsvArguments(cities_file)))
            assert len(pipeline.state) == 1
            assert len(pipeline.errors) == 0

            pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(map_provider, radius=0.3)))
            pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
            pipeline.map(pipeline_verify_and_repair_commonroad_scenario)
            pipeline.map(pipeline_extract_intersections)
            assert len(pipeline.errors) == 0, f"Expected 0 errors, but got {len(pipeline.errors)} errors"
            assert len(pipeline.state) == 39, f"Expected 39 results, but got {len(pipeline.state)} results"
            pipeline.map(pipeline_simulate_scenario_with_sumo)
            pipeline.map(pipeline_generate_ego_scenarios(GenerateCommonRoadScenariosArguments()))
            pipeline.map(pipeline_assign_tags_to_scenario)

            # Expecte that at least one result is generated. We cannot assert the exact number, because this is not deterministic
            assert len(pipeline.state) > 0
            assert isinstance(pipeline.state[0], EgoScenarioWithPlanningProblemSet)

    def test_scenario_generation_with_pipeline_creates_no_scenarios(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath(
            "tests/integration/cities_selected_test.csv"
        )
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")
        map_provider = LocalFileMapProvider(input_maps_folder)

        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir)

            seed = 12
            sumo_config = SumoConfig()
            sumo_config.simulation_steps = 600
            sumo_config.random_seed = seed
            sumo_config.random_seed_trip_generation = seed
            random.seed(seed)
            np.random.seed(seed)

            ctx = PipelineContext(output_path, sumo_config=sumo_config)
            pipeline = Pipeline(ctx)

            pipeline.populate(pipeline_load_regions_from_csv(LoadRegionsFromCsvArguments(cities_file)))
            assert len(pipeline.state) == 1
            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1

            pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(map_provider, radius=0.1)))
            pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
            pipeline.map(pipeline_extract_intersections)
            assert len(pipeline.errors) == 0, f"Expected 0 errors, but got {len(pipeline.errors)} errors"
            assert len(pipeline.state) == 1, f"Expected 1 result, but got {len(pipeline.state)} results"
            pipeline.map(pipeline_simulate_scenario_with_sumo)
            pipeline.map(pipeline_generate_ego_scenarios(GenerateCommonRoadScenariosArguments()))
            pipeline.map(pipeline_assign_tags_to_scenario)

            assert len(pipeline.errors) == 0, f"Expected 0 errors, but got {len(pipeline.errors)} errors"
            assert len(pipeline.state) == 0, f"Expected 0 results, but got {len(pipeline.state)} results"
