import tempfile
from pathlib import Path

import scenario_factory
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    ComputeBoundingBoxForCityArguments,
    ExtractOsmMapArguments,
    LoadCitiesFromCsvArguments,
    pipeline_compute_bounding_box_for_city,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_create_sumo_configuration_for_commonroad_scenario,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_flatten,
    pipeline_load_plain_cities_from_csv,
    pipeline_simulate_scenario,
)
from scenario_factory.pipeline_steps.sumo import GenerateCommonRoadScenariosArguments, pipeline_generate_cr_scenarios


class TestScenarioGeneration:
    def test_scenario_generation(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath(
            "tests/integration/cities_selected_test.csv"
        )
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")

        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir)
            ctx = PipelineContext(output_path, seed=1234)
            pipeline = Pipeline(ctx)

            pipeline.populate(pipeline_load_plain_cities_from_csv(LoadCitiesFromCsvArguments(cities_file)))
            assert len(pipeline.state) == 1
            pipeline.map(pipeline_compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius=0.1)))
            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1

            pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(input_maps_folder, overwrite=True)))
            pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
            pipeline.map(pipeline_extract_intersections)
            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1
            pipeline.reduce(pipeline_flatten)
            pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario)
            pipeline.reduce(pipeline_flatten)
            pipeline.map(pipeline_simulate_scenario)
            pipeline.map(pipeline_generate_cr_scenarios(GenerateCommonRoadScenariosArguments()))

            assert len(pipeline.errors) == 0
            assert len(pipeline.state) == 1
