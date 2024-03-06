from pathlib import Path

import scenario_factory
from scenario_factory.pipeline.bounding_box_coordinates import update_cities_file
from scenario_factory.pipeline.conversion_to_commonroad import convert_to_osm_files
from scenario_factory.pipeline.generate_scenarios import generate_scenarios
from scenario_factory.pipeline.osm_map_extraction import extract_osm_maps
from scenario_factory.pipeline.run_globetrotter import run_globetrotter


class TestPipeline:
    def test_pipeline(self):
        cities_file = Path(scenario_factory.__file__).parent.parent.joinpath("tests/cities_selected_test.csv")
        input_maps_folder = Path(scenario_factory.__file__).parent.parent.joinpath("files/input_maps")
        update_cities_file(cities_file, 0.3, True)

        # extraction
        extracted_maps_folder = extract_osm_maps(cities_file, input_maps_folder, True)
        assert extracted_maps_folder.exists()
        assert len(list(extracted_maps_folder.glob("*.osm"))) > 0

        # conversion to commonroad
        commonroad_folder = convert_to_osm_files(extracted_maps_folder)
        assert commonroad_folder.exists()
        assert len(list(commonroad_folder.glob("*.xml"))) > 0

        # globetrotter
        globetrotter_folder = run_globetrotter(commonroad_folder)
        assert globetrotter_folder.exists()
        assert len(list(globetrotter_folder.rglob("*.xml"))) > 20

        # scenario generation
        output_path = generate_scenarios(globetrotter_folder, scenarios_per_map=2, number_of_processes=8)
        assert output_path.exists()
        assert output_path.joinpath("noninteractive").exists()
        assert len(list(output_path.joinpath("noninteractive").rglob("*.xml"))) > 20
        assert output_path.joinpath("interactive").exists()
        assert len(list(output_path.joinpath("interactive").rglob("*.xml"))) > 20
