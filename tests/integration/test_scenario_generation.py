import random
import tempfile
from pathlib import Path

import numpy as np
from crdesigner.map_conversion.sumo_map.config import SumoConfig

import scenario_factory
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    ComputeBoundingBoxForCityArguments,
    ExtractOsmMapArguments,
    GenerateCommonRoadScenariosArguments,
    LoadCitiesFromCsvArguments,
    pipeline_compute_bounding_box_for_city,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_create_sumo_configuration_for_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_flatten,
    pipeline_generate_ego_scenarios,
    pipeline_load_plain_cities_from_csv,
    pipeline_simulate_scenario,
)
from scenario_factory.pipeline_steps.scenario_generation import pipeline_assign_tags_to_scenario
from scenario_factory.scenario_types import NonInteractiveEgoScenario


class TestScenarioGeneration:
    def test_scenario_generation_with_pipeline_creates_scenarios(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath(
            "tests/integration/cities_selected_test.csv"
        )
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")

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

            pipeline.populate(pipeline_load_plain_cities_from_csv(LoadCitiesFromCsvArguments(cities_file)))
            assert len(pipeline.state) == 1
            pipeline.map(pipeline_compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius=0.1)))
            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1

            pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(input_maps_folder, overwrite=True)))
            pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
            pipeline.map(pipeline_extract_intersections)
            pipeline.reduce(pipeline_flatten)
            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1
            pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario)
            pipeline.reduce(pipeline_flatten)
            pipeline.map(pipeline_simulate_scenario)
            pipeline.map(pipeline_generate_ego_scenarios(GenerateCommonRoadScenariosArguments()))
            pipeline.reduce(pipeline_flatten)
            pipeline.map(pipeline_assign_tags_to_scenario)

            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1
            assert isinstance(pipeline.state[0], NonInteractiveEgoScenario)

    def test_scenario_generation_with_pipeline_creates_no_scenarios(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath(
            "tests/integration/cities_selected_test.csv"
        )
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")

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

            pipeline.populate(pipeline_load_plain_cities_from_csv(LoadCitiesFromCsvArguments(cities_file)))
            assert len(pipeline.state) == 1
            pipeline.map(pipeline_compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius=0.1)))
            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1

            pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(input_maps_folder, overwrite=True)))
            pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
            pipeline.map(pipeline_extract_intersections)
            pipeline.reduce(pipeline_flatten)
            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1
            pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario)
            pipeline.reduce(pipeline_flatten)
            pipeline.map(pipeline_simulate_scenario)
            pipeline.map(pipeline_generate_ego_scenarios(GenerateCommonRoadScenariosArguments()))
            pipeline.reduce(pipeline_flatten)
            pipeline.map(pipeline_assign_tags_to_scenario)

            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 0
