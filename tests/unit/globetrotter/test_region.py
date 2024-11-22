from typing import Optional

import pytest

from scenario_factory.globetrotter import BoundingBox, load_regions_from_csv
from scenario_factory.globetrotter.region import Coordinates, RegionMetadata
from tests.automation.datasets import Dataset, DatasetFormat
from tests.automation.marks import with_custom, with_dataset
from tests.automation.validation import entry_model
from tests.resources.interface import ResourceType


@entry_model
class CoordinateParsingTestCase:
    string: str
    valid: bool
    lat: float
    lon: float


@entry_model
class RegionMetadataTestCase:
    coordinates: Coordinates
    country_code: str
    region_name: str


@entry_model
class BoundingBoxToStringTestCase:
    west: float
    south: float
    east: float
    north: float
    expected_string: str


@entry_model
class BoundingBoxFromCoordinatesTestCase:
    coordinates: Coordinates
    radius: float
    expected_west: float
    expected_south: float
    expected_east: float
    expected_north: float


@entry_model
class RegionsFromCsvTestCase:
    csv_file: str
    expected_regions: Optional[list[RegionMetadata]]


_COORDINATE_PARSING_TEST_DATASET = Dataset(
    ["unit", "globetrotter", "region", "coordinate_parsing"],
    entry_model=CoordinateParsingTestCase,
    dataset_format=DatasetFormat.CSV,
)
_REGION_METADATA_TEST_DATASET = Dataset(
    ["unit", "globetrotter", "region", "region_metadata"],
    entry_model=RegionMetadataTestCase,
    dataset_format=DatasetFormat.CSV,
)
_BOUNDING_BOX_TO_STRING_TEST_DATASET = Dataset(
    ["unit", "globetrotter", "region", "bounding_box_to_string"],
    entry_model=BoundingBoxToStringTestCase,
    dataset_format=DatasetFormat.CSV,
)


class TestCoordinates:
    @with_dataset(_COORDINATE_PARSING_TEST_DATASET)
    @with_custom([("showcase", "20.0,20.0", True, 20.0, 20.0)])
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

    @with_dataset(_COORDINATE_PARSING_TEST_DATASET)
    def test_parse_from_tuple(self, label, valid, lat, lon):
        if not valid:
            return
        coords = Coordinates.from_tuple((lat, lon))
        assert coords.lat == lat and coords.lon == lon, f"Mismatch parsing entry {label} from tuple"

    @with_dataset(_COORDINATE_PARSING_TEST_DATASET)
    def test_string_serialization_and_parsing_is_idempotent(self, label, valid, lat, lon):
        if not valid:
            return
        coords = Coordinates(lat=lat, lon=lon)
        comp = Coordinates.from_str(str(coords))
        assert (
            coords.lat == comp.lat and coords.lon == comp.lon
        ), f"Expected indempotence for entry {label}"

    @with_dataset(_COORDINATE_PARSING_TEST_DATASET)
    def test_tuple_serialization_and_parsing_is_idempotent(self, label, valid, lat, lon):
        if not valid:
            return
        coords = Coordinates(lat=lat, lon=lon)
        comp = Coordinates.from_tuple(coords.as_tuple())
        assert (
            coords.lat == comp.lat and coords.lon == comp.lon
        ), f"Expected indempotence for entry {label}"


class TestRegionMetadata:
    @with_dataset(_REGION_METADATA_TEST_DATASET)
    def test_uses_provided_metadata(self, label, coordinates):
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

    @with_dataset(_REGION_METADATA_TEST_DATASET)
    def test_generates_expected_metadata(self, label, coordinates, country_code, region_name):
        region = RegionMetadata.from_coordinates(coordinates)
        assert (
            region.country_code == country_code
            and region.region_name.lower() == region_name.lower()
        ), f"Construction using generated metadata failed for entry {label}."


class TestBoundingBox:
    @with_dataset(
        Dataset(
            dataset_name=["unit", "globetrotter", "region", "bounding_box_from_coordinates"],
            entry_model=BoundingBoxFromCoordinatesTestCase,
            dataset_format=DatasetFormat.CSV,
        )
    )
    def test_from_coordinates(
        self,
        label: str,
        coordinates: Coordinates,
        radius: float,
        expected_west: float,
        expected_south: float,
        expected_east: float,
        expected_north: float,
    ):
        bbox = BoundingBox.from_coordinates(coordinates, radius)
        assert expected_west == bbox.west, f"Expected correct west bound for entry: {label}."
        assert expected_south == bbox.south, f"Expected correct south bound for entry: {label}."
        assert expected_east == bbox.east, f"Expected correct east bound for entry: {label}."
        assert expected_north == bbox.north, f"Expected correct north bound for entry: {label}."

    @with_dataset(_BOUNDING_BOX_TO_STRING_TEST_DATASET)
    def test_constructor(self, label: str, west: float, south: float, east: float, north: float):
        # TODO: Create test examples
        bbox = BoundingBox(west, south, east, north)
        assert west == bbox.west, f"Expected correct west bound for entry: {label}."
        assert south == bbox.south, f"Expected correct south bound for entry: {label}."
        assert east == bbox.east, f"Expected correct east bound for entry: {label}."
        assert north == bbox.north, f"Expected correct north bound for entry: {label}."

    @with_dataset(_BOUNDING_BOX_TO_STRING_TEST_DATASET)
    def test_to_string(
        self, label: str, west: float, south: float, east: float, north: float, expected_string: str
    ):
        bbox = BoundingBox(west, south, east, north)
        assert expected_string == str(
            bbox
        ), f"Expected correct string representation for entry: {label}."


class TestGlobals:
    @with_dataset(
        Dataset(
            dataset_name=["unit", "globetrotter", "region", "regions_from_csv"],
            entry_model=RegionsFromCsvTestCase,
            dataset_format=DatasetFormat.JSON,
        )
    )
    def test_load_regions_from_csv(
        self, label: str, csv_file: str, expected_regions: list[RegionMetadata] | None
    ):
        csv_path = ResourceType.CSV_FILES.get_folder() / csv_file
        if expected_regions is None:
            try:
                load_regions_from_csv(csv_path)
            except KeyError:
                pass
            else:
                assert False, f"Expected load_regions_from_csv to fail for entry: {label}."
        else:
            idx = 0
            for region in load_regions_from_csv(csv_path):
                expected_region = expected_regions[idx]
                idx += 1
                assert region.coordinates == expected_region.coordinates, (
                    f"Expected correct region coordinates at " f"index {idx} for entry {label}."
                )
                assert region.country_code == expected_region.country_code, (
                    f"Expected correct region country code at " f"index {idx} for entry {label}."
                )
                assert region.region_name == expected_region.region_name, (
                    f"Expected correct region name at " f"index {idx} for entry {label}."
                )
