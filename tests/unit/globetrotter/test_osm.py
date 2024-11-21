import os
from pathlib import Path
from typing import Optional

import numpy as np
import pytest

from scenario_factory.globetrotter import (
    LocalFileMapProvider,
    OsmApiMapProvider,
    RegionMetadata,
    verify_and_repair_commonroad_scenario,
)
from scenario_factory.globetrotter.osm import (
    extract_bounding_box_from_osm_map,
    find_osm_file_for_region,
    fix_center_polylines,
    get_canonical_region_name,
)
from scenario_factory.globetrotter.region import BoundingBox, Coordinates
from tests.resources.interface import (
    ResourceType,
    TmpResourceEntry,
    TmpResourceFolder,
    get_test_dataset_csv,
    get_test_dataset_json,
    load_cr_lanelet_network_from_file,
)
from tests.utility import assert_osm_semantic_matches, hash_file


def get_canonical_names_test_dataset():
    return [
        (entry[0], entry[1], entry[2])
        for entry in get_test_dataset_csv(os.path.join("globetrotter", "osm", "canonical_names"))
    ]


class RegionalMapsTestEntry:
    label: str
    map_files: list[str]
    region_map: Optional[str]
    region: RegionMetadata

    def __init__(self, serial):
        self.label = serial["label"]
        self.map_files = serial["map_files"]
        self.region_map = serial["region_map"]
        self.region = RegionMetadata(
            serial["country_code"], serial["region_name"], 0, Coordinates(0, 0)
        )


def get_regional_maps_test_dataset():
    return [
        RegionalMapsTestEntry(serial)
        for serial in get_test_dataset_json(os.path.join("globetrotter", "osm", "regional_maps"))
    ]


def get_map_excerpts_test_dataset():
    return [
        (entry[0], BoundingBox(entry[1], entry[2], entry[3], entry[4]), entry[5], entry[6])
        for entry in get_test_dataset_csv(os.path.join("globetrotter", "osm", "map_excerpts"))
    ]


class LocalProviderTestEntry:
    label: str
    map_files: list[str]
    region: RegionMetadata
    bounding_box: BoundingBox
    expected_excerpt: str

    def __init__(self, serial):
        self.label = serial["label"]
        self.map_files = serial["map_files"]
        self.region = RegionMetadata(
            serial["country_code"], serial["region_name"], 0, Coordinates(0, 0)
        )
        self.bounding_box = BoundingBox(
            serial["west"], serial["south"], serial["east"], serial["north"]
        )
        self.expected_excerpt = serial["expected_excerpt"]


def get_local_provider_test_dataset():
    return [
        LocalProviderTestEntry(serial)
        for serial in get_test_dataset_json(os.path.join("globetrotter", "osm", "local_provider"))
    ]


class CenterPolylinesTestEntry:
    label: str
    lanelet_network: str
    expected_center_polylines: dict[int, list[tuple[float, float]]]

    def __init__(self, serial):
        self.label = serial["label"]
        self.lanelet_network = serial["lanelet_network"]
        self.expected_center_polylines = {
            serial_center_pl["id"]: [
                (serial_point["x"], serial_point["y"])
                for serial_point in serial_center_pl["points"]
            ]
            for serial_center_pl in serial["expected_center_polylines"]
        }


def get_center_polylines_test_dataset():
    return [
        CenterPolylinesTestEntry(serial)
        for serial in get_test_dataset_json(os.path.join("globetrotter", "osm", "center_polylines"))
    ]


_CANONICAL_NAMES_TEST_DATASET = get_canonical_names_test_dataset()
_REGIONAL_MAPS_TEST_DATASET = get_regional_maps_test_dataset()
_MAP_EXCERPTS_TEST_DATASET = get_map_excerpts_test_dataset()
_LOCAL_PROVIDER_TEST_DATASET = get_local_provider_test_dataset()
_CENTER_POLYLINES_TEST_DATASET = get_center_polylines_test_dataset()


class TestGlobals:
    @pytest.mark.parametrize("label, name, canonical_name", _CANONICAL_NAMES_TEST_DATASET)
    def test_get_canonical_region_name(self, label, name, canonical_name):
        assert (
            get_canonical_region_name(name) == canonical_name
        ), f"Expected correct canonical name for entry {label}."

    @pytest.mark.parametrize("entry", _REGIONAL_MAPS_TEST_DATASET)
    def test_find_osm_file_for_region(self, entry: RegionalMapsTestEntry):
        entries = [
            TmpResourceEntry(ResourceType.OSM_SOURCE_MAP, map_name) for map_name in entry.map_files
        ]
        with TmpResourceFolder(*entries) as folder:
            result = find_osm_file_for_region(folder.path, entry.region)
            if result is None:
                assert (
                    entry.region_map is None
                ), f"Expected to get a regional map for entry {entry.label}."
            else:
                assert (
                    result.name == entry.region_map
                ), f"Expected to select the correct region map for entry {entry.label}."

    @pytest.mark.parametrize(
        "label, bounding_box, input_map, expected_excerpt", _MAP_EXCERPTS_TEST_DATASET
    )
    def test_extract_bounding_box_from_osm_map(
        self, label: str, bounding_box: BoundingBox, input_map: str, expected_excerpt: str
    ):
        with TmpResourceFolder() as folder:
            output_path = folder.path / "excerpt.osm"
            input_map_path = ResourceType.OSM_SOURCE_MAP.get_folder() / input_map

            if expected_excerpt == "null":
                try:
                    extract_bounding_box_from_osm_map(
                        bounding_box, input_map_path, output_path, True
                    )
                except RuntimeError:  # TODO: For now
                    pass
                else:
                    assert False, f"Expected exception for entry {label}."
            else:
                expected_excerpt_path = ResourceType.OSM_MAP_EXCERPT.get_folder() / expected_excerpt
                extract_bounding_box_from_osm_map(bounding_box, input_map_path, output_path, True)

                assert os.path.exists(
                    output_path
                ), f"Expected file {output_path} to be created for entry {label}."
                assert_osm_semantic_matches(expected_excerpt_path, output_path)

    @pytest.mark.parametrize("entry", _CENTER_POLYLINES_TEST_DATASET)
    def test_fix_center_polylines(self, entry: CenterPolylinesTestEntry):
        lanelet_network_path = ResourceType.CR_LANELET_NETWORK.get_folder() / entry.lanelet_network
        lanelet_network = load_cr_lanelet_network_from_file(lanelet_network_path)
        for lanelet in lanelet_network.lanelets:
            lanelet.center_vertices = np.zeros_like(lanelet.center_vertices)

        fix_center_polylines(lanelet_network)
        for lanelet in lanelet_network.lanelets:
            assert np.all(
                np.array(entry.expected_center_polylines[lanelet.lanelet_id])
                == lanelet.center_vertices
            ), f"Expected correct center polyline for lanelet {lanelet.lanelet_id} in entry {entry.label}."

    def test_verify_and_repair_commonroad_scenario(self):
        # TODO: Conceive appropriate test model.
        pass


class TestLocalFileMapProvider:
    @pytest.mark.parametrize("entry", _LOCAL_PROVIDER_TEST_DATASET)
    def test_get_map(self, entry: LocalProviderTestEntry):
        entries = [
            TmpResourceEntry(ResourceType.OSM_SOURCE_MAP, map_name, Path("sources", map_name))
            for map_name in entry.map_files
        ]
        with TmpResourceFolder(*entries) as folder:
            prov = LocalFileMapProvider(folder.path / "sources")
            output_path = prov.get_map(entry.region, entry.bounding_box, folder.path)
            expected_excerpt_path = (
                ResourceType.OSM_MAP_EXCERPT.get_folder() / entry.expected_excerpt
            )
            assert_osm_semantic_matches(expected_excerpt_path, output_path)


class TestOsmAPIMapProvider:
    def test_get_map(self):
        # TODO: Conceive appropriate test model - seems hard.
        pass
