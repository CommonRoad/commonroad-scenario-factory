from pathlib import Path

import scenario_factory
from scenario_factory.globetrotter.globetrotter_io import extract_forking_points
from scenario_factory.pipeline.bounding_box_coordinates import (
    ComputeBoundingBoxForCityArguments,
    LoadCitiesFromCsvArguments,
    compute_bounding_box_for_city,
    load_cities_from_csv,
)
from scenario_factory.pipeline.context import Pipeline, PipelineContext
from scenario_factory.pipeline.conversion_to_commonroad import convert_osm_file_to_commonroad_scenario
from scenario_factory.pipeline.generate_scenarios import (
    GenerateRandomTrafficArguments,
    create_sumo_configuration_for_commonroad_scenario,
    generate_random_traffic,
    simulate_scenario,
)
from scenario_factory.pipeline.osm_map_extraction import ExtractOsmMapArguments, extract_osm_map
from scenario_factory.pipeline.run_globetrotter import (
    convert_intersection_to_commonroad_scenario,
    extract_intersections,
)
from scenario_factory.pipeline.utils import flatten


class TestScenarioGeneration:
    def test_scenario_generation(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath("tests/cities_selected_test.csv")
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")

        ctx = PipelineContext(Path("./tests/"))
        pipeline = Pipeline(ctx)

        pipeline.populate(load_cities_from_csv(LoadCitiesFromCsvArguments(cities_file)))
        assert len(pipeline.state) == 1
        pipeline.map(compute_bounding_box_for_city(ComputeBoundingBoxForCityArguments(radius=0.1)))
        assert len(pipeline.state) == 1

        pipeline.map(extract_osm_map(ExtractOsmMapArguments(input_maps_folder, overwrite=True)))
        pipeline.map(convert_osm_file_to_commonroad_scenario)
        pipeline.map(extract_forking_points)
        pipeline.map(extract_intersections)
        pipeline.reduce(flatten)
        pipeline.map(convert_intersection_to_commonroad_scenario)
        pipeline.map(create_sumo_configuration_for_commonroad_scenario)
        pipeline.map(generate_random_traffic(GenerateRandomTrafficArguments(scenarios_per_map=2)))
        pipeline.reduce(flatten)
        pipeline.map(simulate_scenario)

        assert len(pipeline.errors) == 0
        assert len(pipeline.state) == 10
        # use the result, to make sure that everything is evaluated
