import numpy as np
from commonroad.scenario.lanelet import LaneletNetwork

from scenario_factory.globetrotter import RegionMetadata
from scenario_factory.globetrotter.osm import (
    find_osm_file_for_region,
    fix_center_polylines,
    get_canonical_region_name,
)
from tests.automation.mark import with_dataset
from tests.resources.interface import ResourceType, TmpResourceEntry, make_tmp_resource_folder
from tests.unit.globetrotter.osm_datasets import (
    CANONICAL_NAMES_TEST_DATASET,
    CENTER_POLYLINES_TEST_DATASET,
    REGIONAL_MAPS_TEST_DATASET,
)


class TestGlobals:
    @with_dataset(CANONICAL_NAMES_TEST_DATASET)
    def test_get_canonical_region_name(self, label, name, canonical_name):
        assert (
            get_canonical_region_name(name) == canonical_name
        ), f"Expected correct canonical name for entry {label}."

    @with_dataset(REGIONAL_MAPS_TEST_DATASET)
    def test_find_osm_file_for_region(
        self, label: str, map_files: list[str], region: RegionMetadata, expected_region_map: str
    ):
        entries = [
            TmpResourceEntry(ResourceType.OSM_SOURCE_MAP, map_name) for map_name in map_files
        ]
        with make_tmp_resource_folder(*entries) as tmp_path:
            result = find_osm_file_for_region(tmp_path, region)
            if result is None:
                assert (
                    expected_region_map is None
                ), f"Expected to get a regional map for entry {label}."
            else:
                assert (
                    result.name == expected_region_map
                ), f"Expected to select the correct region map for entry {label}."

    @with_dataset(CENTER_POLYLINES_TEST_DATASET)
    def test_fix_center_polylines(
        self,
        label: str,
        lanelet_network: LaneletNetwork,
    ):
        for lanelet in lanelet_network.lanelets:
            lanelet.center_vertices = np.zeros_like(lanelet.center_vertices)

        fix_center_polylines(lanelet_network)
        for lanelet in lanelet_network.lanelets:
            assert np.all(
                lanelet.center_vertices == 0.5 * (lanelet.left_vertices + lanelet.right_vertices)
            )
