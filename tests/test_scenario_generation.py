from pathlib import Path

import scenario_factory
from scenario_factory.pipeline import Pipeline, PipelineContext
from scenario_factory.pipeline_steps import (
    ComputeBoundingBoxForCityArguments,
    ExtractOsmMapArguments,
    GenerateRandomTrafficArguments,
    LoadCitiesFromCsvArguments,
    pipeline_compute_bounding_box_for_city,
    pipeline_convert_intersection_to_commonroad_scenario,
    pipeline_convert_osm_map_to_commonroad_scenario,
    pipeline_create_sumo_configuration_for_commonroad_scenario,
    pipeline_extract_forking_points,
    pipeline_extract_intersections,
    pipeline_extract_osm_map,
    pipeline_flatten,
    pipeline_generate_random_traffic,
    pipeline_load_plain_cities_from_csv,
    pipeline_simulate_scenario,
)


class TestScenarioGeneration:
    def test_scenario_generation(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath("tests/cities_selected_test.csv")
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")

        ctx = PipelineContext(Path("./tests/"))
        pipeline = Pipeline(ctx)

        pipeline.populate(pipeline_load_plain_cities_from_csv(LoadCitiesFromCsvArguments(cities_file)))
        assert len(pipeline.state) == 1
        pipeline.map(pipeline_compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius=0.1)))
        assert len(pipeline.state) == 1

        pipeline.map(pipeline_extract_osm_map(ExtractOsmMapArguments(input_maps_folder, overwrite=True)))
        pipeline.map(pipeline_convert_osm_map_to_commonroad_scenario)
        pipeline.map(pipeline_extract_forking_points)
        pipeline.map(pipeline_extract_intersections)
        pipeline.reduce(pipeline_flatten)
        pipeline.map(pipeline_convert_intersection_to_commonroad_scenario)
        pipeline.map(pipeline_create_sumo_configuration_for_commonroad_scenario)
        pipeline.map(pipeline_generate_random_traffic(GenerateRandomTrafficArguments(scenarios_per_map=2)))
        pipeline.reduce(pipeline_flatten)
        pipeline.map(pipeline_simulate_scenario)

        assert len(pipeline.errors) == 0
        assert len(pipeline.state) == 10
        # use the result, to make sure that everything is evaluated
