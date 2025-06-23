import numpy as np
import pytest

from scenario_factory.globetrotter import BoundingBox, load_regions_from_csv
from scenario_factory.globetrotter.region import Coordinates, RegionMetadata
from tests.automation.mark import with_dataset
from tests.resources.interface import ResourceType
from tests.unit.globetrotter.region_datasets import (
    BOUNDING_BOX_FROM_COORDINATES_TEST_DATASET,
    BOUNDING_BOX_TO_STRING_TEST_DATASET,
    COORDINATE_PARSING_TEST_DATASET,
    REGION_METADATA_TEST_DATASET,
    REGIONS_FROM_CSV_TEST_DATASET,
)


class TestCoordinates:
    @with_dataset(COORDINATE_PARSING_TEST_DATASET)
    def test_parse_from_string(self, label, string, valid, lat, lon):
        if valid:
            coords = Coordinates.from_str(string)
            assert (
                coords.lat == lat and coords.lon == lon
            ), f"Mismatch parsing entry {label} from string."
        else:
            with pytest.raises(ValueError):
                Coordinates.from_str(string)

    @with_dataset(COORDINATE_PARSING_TEST_DATASET)
    def test_parse_from_tuple(self, label, valid, lat, lon):
        if not valid:
            pytest.skip("Can only test parsing from valid tuples.")
        coords = Coordinates.from_tuple((lat, lon))
        assert coords.lat == lat and coords.lon == lon, f"Mismatch parsing entry {label} from tuple"

    @with_dataset(COORDINATE_PARSING_TEST_DATASET)
    def test_string_serialization_and_parsing_is_idempotent(self, label, valid, lat, lon):
        if not valid:
            pytest.skip("Can only test indempotence for valid tuples.")
        coords = Coordinates(lat=lat, lon=lon)
        comp = Coordinates.from_str(str(coords))
        assert (
            coords.lat == comp.lat and coords.lon == comp.lon
        ), f"Expected indempotence for entry {label}"

    @with_dataset(COORDINATE_PARSING_TEST_DATASET)
    def test_tuple_serialization_and_parsing_is_idempotent(self, label, valid, lat, lon):
        if not valid:
            pytest.skip("Can only test indempotence for valid tuples.")
        coords = Coordinates(lat=lat, lon=lon)
        comp = Coordinates.from_tuple(coords.as_tuple())
        assert (
            coords.lat == comp.lat and coords.lon == comp.lon
        ), f"Expected indempotence for entry {label}"


class TestRegionMetadata:
    @with_dataset(REGION_METADATA_TEST_DATASET)
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

    @with_dataset(REGION_METADATA_TEST_DATASET)
    def test_generates_expected_metadata(self, label, coordinates, country_code, region_name):
        region = RegionMetadata.from_coordinates(coordinates)
        assert (
            region.country_code == country_code
            and region.region_name.lower() == region_name.lower()
        ), f"Construction using generated metadata failed for entry {label}."


class TestBoundingBox:
    @with_dataset(BOUNDING_BOX_FROM_COORDINATES_TEST_DATASET)
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
        assert np.allclose(
            [expected_west, expected_south, expected_east, expected_north],
            [bbox.west, bbox.south, bbox.east, bbox.north],
            atol=1e-6,
        ), f"Expected bounds close to the provided bounds for entry {label}."

    @with_dataset(BOUNDING_BOX_TO_STRING_TEST_DATASET)
    def test_constructor(self, label: str, west: float, south: float, east: float, north: float):
        bbox = BoundingBox(west, south, east, north)
        assert west == bbox.west, f"Expected correct west bound for entry: {label}."
        assert south == bbox.south, f"Expected correct south bound for entry: {label}."
        assert east == bbox.east, f"Expected correct east bound for entry: {label}."
        assert north == bbox.north, f"Expected correct north bound for entry: {label}."

    @with_dataset(BOUNDING_BOX_TO_STRING_TEST_DATASET)
    def test_to_string(
        self, label: str, west: float, south: float, east: float, north: float, expected_string: str
    ):
        bbox = BoundingBox(west, south, east, north)
        assert expected_string == str(
            bbox
        ), f"Expected correct string representation for entry: {label}."


class TestGlobals:
    @with_dataset(
        REGIONS_FROM_CSV_TEST_DATASET,
        skips=[
            # TODO: Validation on CSV file (Issue: #59)
            "malformed_lowercase",
            "malformed_missing_column",
        ],
    )
    def test_load_regions_from_csv(
        self, label: str, csv_file: str, expected_regions: list[RegionMetadata] | None
    ):
        csv_path = ResourceType.CSV_FILES.get_folder() / csv_file
        if expected_regions is None:
            with pytest.raises(KeyError):
                load_regions_from_csv(csv_path)
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
