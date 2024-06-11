from pathlib import Path

import scenario_factory
from scenario_factory.globetrotter.globetrotter_io import extract_forking_points
from scenario_factory.globetrotter.intersection import Intersection
from scenario_factory.pipeline.bounding_box_coordinates import (
    compute_bounding_box_for_city,
    load_cities_from_file,
    write_cities_to_file,
)
from scenario_factory.pipeline.context import Pipeline, PipelineContext
from scenario_factory.pipeline.conversion_to_commonroad import convert_osm_file_to_commonroad_scenario
from scenario_factory.pipeline.generate_scenarios import generate_scenarios
from scenario_factory.pipeline.osm_map_extraction import extract_osm_map
from scenario_factory.pipeline.run_globetrotter import extract_intersections, write_intersection_to_file
from scenario_factory.pipeline.utils import flatten, keep


class TestPipeline:
    def test_pipeline(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath("tests/cities_selected_test.csv")
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")

        ctx = PipelineContext(cities_file, Path("./tests/"))
        pipeline = Pipeline(ctx)

        pipeline.populate(load_cities_from_file)
        cities = pipeline.drain(keep)
        assert len(cities) == 1

        pipeline.map(compute_bounding_box_for_city, args={"radius": 0.3})
        cities = pipeline.drain(keep)
        assert len(cities) == 1

        pipeline.map(extract_osm_map, args={"input_maps_folder": input_maps_folder, "overwrite": True})
        pipeline.map(convert_osm_file_to_commonroad_scenario)
        pipeline.map(extract_forking_points)
        pipeline.map(extract_intersections)
        pipeline.reduce(flatten)
        pipeline.map(write_intersection_to_file)
        # use the result, to make sure that everything is evaluated
        pipeline.drain(keep)
        pipeline.report_results()

        # scenario generation
        output_path = generate_scenarios(
            ctx.get_output_folder("globetrotter"), scenarios_per_map=2, number_of_processes=8
        )
        assert output_path.exists()
        assert output_path.joinpath("noninteractive").exists()
        assert len(list(output_path.joinpath("noninteractive").rglob("*.xml"))) > 20
        assert output_path.joinpath("interactive").exists()
        assert len(list(output_path.joinpath("interactive").rglob("*.xml"))) > 20
