import os

import pytest

from scenario_factory.globetrotter import BoundingBox, load_regions_from_csv
from scenario_factory.globetrotter.region import Coordinates, RegionMetadata
from tests.resources.interface import ResourceType, get_test_dataset_csv, get_test_dataset_json


def get_coordinate_parsing_test_dataset():
    return [
        (entry[0], entry[1], entry[2].lower() == "true", float(entry[3]), float(entry[4]))
        for entry in get_test_dataset_csv(
            os.path.join("globetrotter", "region", "coordinate_parsing")
        )
    ]


def get_region_metadata_test_dataset():
    return [
        (entry[0], Coordinates.from_str(entry[1]), entry[2], entry[3])
        for entry in get_test_dataset_csv(os.path.join("globetrotter", "region", "region_metadata"))
    ]


def get_bounding_box_from_coords_test_dataset():
    return [
        (entry[0], Coordinates.from_str(entry[1]), float(entry[2]))
        for entry in get_test_dataset_csv(
            os.path.join("globetrotter", "region", "bounding_box_from_coords")
        )
    ]


def get_bounding_box_to_string_test_dataset():
    return [
        (entry[0], float(entry[1]), float(entry[2]), float(entry[3]), float(entry[4]), entry[5])
        for entry in get_test_dataset_csv(
            os.path.join("globetrotter", "region", "bounding_box_to_string")
        )
    ]


class RegionsFromCsvTestEntry:
    label: str
    csv_file: str
    expected_regions: list[RegionMetadata] | None

    def __init__(self, serial):
        self.label = serial["label"]
        self.csv_file = serial["csv_file"]
        serial_regions = serial["expected_regions"]
        if serial_regions is None:
            self.expected_regions = None
        else:
            self.expected_regions = [
                RegionMetadata(
                    coordinates=Coordinates.from_str(serial_region["coords"]),
                    country_code=serial_region["country_code"],
                    region_name=serial_region["region_name"],
                    geoname_id=0,
                )
                for serial_region in serial_regions
            ]


def get_regions_from_csv_test_dataset():
    return [
        RegionsFromCsvTestEntry(serial)
        for serial in get_test_dataset_json(
            os.path.join("globetrotter", "region", "regions_from_csv")
        )
    ]


_COORDINATE_PARSING_TEST_DATASET = get_coordinate_parsing_test_dataset()
_REGION_METADATA_TEST_DATASET = get_region_metadata_test_dataset()
_BOUNDING_BOX_FROM_COORDS_TEST_DATASET = get_bounding_box_from_coords_test_dataset()
_BOUNDING_BOX_TO_STRING_TEST_DATASET = get_bounding_box_to_string_test_dataset()
_REGIONS_FROM_CSV_TEST_DATASET = get_regions_from_csv_test_dataset()


class TestCoordinates:
    @pytest.mark.parametrize("label, string, valid, lat, lon", _COORDINATE_PARSING_TEST_DATASET)
    def test_parse_from_string(self, label, string, valid, lat, lon):
        if valid:
            coords = Coordinates.from_str(string)
            assert (
                coords.lat == lat and coords.lon == lon
            ), f"Mismatch parsing entry {label} from string."
        else:
            try:
                with pytest.raises(ValueError):
                    Coordinates.from_str(string)
            except pytest.fail.Exception:
                pytest.fail(f"Expected error parsing entry {label} from string.")

    @pytest.mark.parametrize("label, string, valid, lat, lon", _COORDINATE_PARSING_TEST_DATASET)
    def test_parse_from_tuple(self, label, string, valid, lat, lon):
        if not valid:
            return
        coords = Coordinates.from_tuple((lat, lon))
        assert coords.lat == lat and coords.lon == lon, f"Mismatch parsing entry {label} from tuple"

    @pytest.mark.parametrize("label, string, valid, lat, lon", _COORDINATE_PARSING_TEST_DATASET)
    def test_string_serialization_and_parsing_is_idempotent(self, label, string, valid, lat, lon):
        if not valid:
            return
        coords = Coordinates(lat=lat, lon=lon)
        comp = Coordinates.from_str(str(coords))
        assert (
            coords.lat == comp.lat and coords.lon == comp.lon
        ), f"Expected indempotence for entry {label}"

    @pytest.mark.parametrize("label, string, valid, lat, lon", _COORDINATE_PARSING_TEST_DATASET)
    def test_tuple_serialization_and_parsing_is_idempotent(self, label, string, valid, lat, lon):
        if not valid:
            return
        coords = Coordinates(lat=lat, lon=lon)
        comp = Coordinates.from_tuple(coords.as_tuple())
        assert (
            coords.lat == comp.lat and coords.lon == comp.lon
        ), f"Expected indempotence for entry {label}"


class TestRegionMetadata:
    @pytest.mark.parametrize(
        "label, coordinates, country_code, region_name", _REGION_METADATA_TEST_DATASET
    )
    def test_uses_provided_metadata(self, label, coordinates, country_code, region_name):
        # For all coordinates check whether country code and region name are set to the provided values.
        region = RegionMetadata.from_coordinates(
            coordinates, country_code="DEU", region_name="Somewhere"
        )
        assert (
            region.coordinates.lat == coordinates.lat
            and region.coordinates.lon == coordinates.lon
            and region.country_code == "DEU"
            and region.region_name == "Somewhere"
        ), f"Construction using provided metadata failed for entry {label}."

    @pytest.mark.parametrize(
        "label, coordinates, country_code, region_name", _REGION_METADATA_TEST_DATASET
    )
    def test_generates_expected_metadata(self, label, coordinates, country_code, region_name):
        region = RegionMetadata.from_coordinates(coordinates)
        assert (
            region.country_code == country_code
            and region.region_name.lower() == region_name.lower()
        ), f"Construction using generated metadata failed for entry {label}."


class TestBoundingBox:
    @pytest.mark.parametrize(
        "label, coords, radius, expected_west, expected_south, expected_east, expected_north",
        _BOUNDING_BOX_FROM_COORDS_TEST_DATASET,
    )
    def test_from_coordinates(
        self,
        label: str,
        coords: Coordinates,
        radius: float,
        expected_west: float,
        expected_south: float,
        expected_east: float,
        expected_north: float,
    ):
        bbox = BoundingBox.from_coordinates(coords, radius)
        assert expected_west == bbox.west, f"Expected correct west bound for entry: {label}."
        assert expected_south == bbox.south, f"Expected correct south bound for entry: {label}."
        assert expected_east == bbox.east, f"Expected correct east bound for entry: {label}."
        assert expected_north == bbox.north, f"Expected correct north bound for entry: {label}."

    @pytest.mark.parametrize(
        "label, west, south, east, north, expected_string", _BOUNDING_BOX_TO_STRING_TEST_DATASET
    )
    def test_constructor(
        self, label: str, west: float, south: float, east: float, north: float, expected_string: str
    ):
        # TODO: Create test examples
        bbox = BoundingBox(west, south, east, north)
        assert west == bbox.west, f"Expected correct west bound for entry: {label}."
        assert south == bbox.south, f"Expected correct south bound for entry: {label}."
        assert east == bbox.east, f"Expected correct east bound for entry: {label}."
        assert north == bbox.north, f"Expected correct north bound for entry: {label}."

    @pytest.mark.parametrize(
        "label, west, south, east, north, expected_string", _BOUNDING_BOX_TO_STRING_TEST_DATASET
    )
    def test_to_string(
        self, label: str, west: float, south: float, east: float, north: float, expected_string: str
    ):
        bbox = BoundingBox(west, south, east, north)
        assert expected_string == str(
            bbox
        ), f"Expected correct string representation for entry: {label}."


class TestGlobals:
    @pytest.mark.parametrize("entry", _REGIONS_FROM_CSV_TEST_DATASET)
    def test_load_regions_from_csv(self, entry: RegionsFromCsvTestEntry):
        csv_path = ResourceType.CSV_FILES.get_folder() / entry.csv_file
        if entry.expected_regions is None:
            try:
                v = load_regions_from_csv(csv_path)
            except KeyError:
                pass
            else:
                assert False, f"Expected load_regions_from_csv to fail for entry: {entry.label}."
        else:
            idx = 0
            for region in load_regions_from_csv(csv_path):
                expected_region = entry.expected_regions[idx]
                idx += 1
                assert region.coordinates == expected_region.coordinates, (
                    f"Expected correct region coordinates at "
                    f"index {idx} for entry {entry.label}."
                )
                assert region.country_code == expected_region.country_code, (
                    f"Expected correct region country code at "
                    f"index {idx} for entry {entry.label}."
                )
                assert region.region_name == expected_region.region_name, (
                    f"Expected correct region name at " f"index {idx} for entry {entry.label}."
                )
