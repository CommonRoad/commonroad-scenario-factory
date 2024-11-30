import os
from pathlib import Path

import numpy as np
import pytest
from commonroad.scenario.lanelet import LaneletNetwork

from scenario_factory.globetrotter import LocalFileMapProvider, RegionMetadata
from scenario_factory.globetrotter.osm import (
    extract_bounding_box_from_osm_map,
    find_osm_file_for_region,
    fix_center_polylines,
    get_canonical_region_name,
)
from scenario_factory.globetrotter.region import BoundingBox
from tests.automation.marks import with_dataset, with_file_dataset
from tests.resources.interface import (
    ResourceType,
    TmpResourceEntry,
    TmpResourceFolder,
)
from tests.unit.globetrotter.osm_datasets import (
    CANONICAL_NAMES_TEST_DATASET,
    CENTER_POLYLINES_TEST_DATASET,
    LOCAL_PROVIDER_TEST_DATASET,
    MAP_EXCERPTS_TEST_DATASET,
    REGIONAL_MAPS_TEST_DATASET,
)


class TestGlobals:
    @with_file_dataset(CANONICAL_NAMES_TEST_DATASET)
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
        with TmpResourceFolder(*entries) as folder:
            result = find_osm_file_for_region(folder.path, region)
            if result is None:
                assert (
                    expected_region_map is None
                ), f"Expected to get a regional map for entry {label}."
            else:
                assert (
                    result.name == expected_region_map
                ), f"Expected to select the correct region map for entry {label}."

    @with_dataset(MAP_EXCERPTS_TEST_DATASET)
    def test_extract_bounding_box_from_osm_map(
        self, label: str, bounding_box: BoundingBox, input_map: str, expected_excerpt: str | None
    ):
        with TmpResourceFolder() as folder:
            output_path = folder.path / "excerpt.osm"
            input_map_path = ResourceType.OSM_SOURCE_MAP.get_folder() / input_map

            if expected_excerpt is None:
                with pytest.raises(RuntimeError):
                    extract_bounding_box_from_osm_map(
                        bounding_box, input_map_path, output_path, True
                    )
            else:
                expected_excerpt_path = ResourceType.OSM_MAP_EXCERPT.get_folder() / expected_excerpt
                extract_bounding_box_from_osm_map(bounding_box, input_map_path, output_path, True)

                assert os.path.exists(
                    output_path
                ), f"Expected file {output_path} to be created for entry {label}."
                # TODO: Check for required "similarity"

    @with_dataset(CENTER_POLYLINES_TEST_DATASET)
    def test_fix_center_polylines(
        self,
        label: str,
        lanelet_network: LaneletNetwork,
        expected_center_polylines: dict[int, np.ndarray],
    ):
        for lanelet in lanelet_network.lanelets:
            lanelet.center_vertices = np.zeros_like(lanelet.center_vertices)
        assert len(lanelet_network.lanelets) == len(
            expected_center_polylines
        ), f"Lanelet network and test expectations are incompatible for entry {label}."

        fix_center_polylines(lanelet_network)
        for lanelet in lanelet_network.lanelets:
            assert np.all(
                expected_center_polylines[lanelet.lanelet_id] == lanelet.center_vertices
            ), f"Expected correct center polyline for lanelet {lanelet.lanelet_id} in entry {label}."

    def test_verify_and_repair_commonroad_scenario(self):
        # TODO: Conceive appropriate test model.
        pass


class TestLocalFileMapProvider:
    @with_dataset(LOCAL_PROVIDER_TEST_DATASET)
    def test_get_map(
        self,
        map_files: list[str],
        region: RegionMetadata,
        bounding_box: BoundingBox,
        expected_excerpt: str | None,
    ):
        entries = [
            TmpResourceEntry(ResourceType.OSM_SOURCE_MAP, map_name, Path("sources", map_name))
            for map_name in map_files
        ]
        with TmpResourceFolder(*entries) as folder:
            prov = LocalFileMapProvider(folder.path / "sources")

            if expected_excerpt is None:
                with pytest.raises(Exception):
                    prov.get_map(region, bounding_box, folder.path)
            else:
                output_path = prov.get_map(region, bounding_box, folder.path)
                expected_excerpt_path = ResourceType.OSM_MAP_EXCERPT.get_folder() / expected_excerpt
                # TODO: Check for required "similarity"


class TestOsmAPIMapProvider:
    def test_get_map(self):
        # TODO: Conceive appropriate test model - seems hard.
        pass
