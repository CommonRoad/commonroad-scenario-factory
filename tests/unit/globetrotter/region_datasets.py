from typing import Any

from pydantic import field_validator

from scenario_factory.globetrotter import Coordinates, RegionMetadata
from tests.automation.datasets import FileDataset, FileDatasetFormat, Dataset
from tests.automation.validation import TestCase


# ---------------------------------
# Entry Models
# ---------------------------------

class CoordinateParsingTestCase(TestCase):
    string: str
    valid: bool
    lat: float
    lon: float


class RegionMetadataTestCase(TestCase):
    coordinates: Coordinates
    country_code: str
    region_name: str

    @field_validator("coordinates", mode="before")
    @classmethod
    def parse_coordinates(cls, v: str | Any):
        if isinstance(v, str):
            return Coordinates.from_str(v)
        else:
            raise ValueError("Invalid format for coordinate.")


class BoundingBoxToStringTestCase(TestCase):
    west: float
    south: float
    east: float
    north: float
    expected_string: str


class BoundingBoxFromCoordinatesTestCase(TestCase):
    coordinates: Coordinates
    radius: float
    expected_west: float
    expected_south: float
    expected_east: float
    expected_north: float

    @field_validator("coordinates", mode="before")
    @classmethod
    def parse_coordinates(cls, v: str | Any):
        if isinstance(v, str):
            return Coordinates.from_str(v)
        else:
            raise ValueError("Invalid format for coordinate.")


class RegionsFromCsvTestCase(TestCase):
    csv_file: str
    expected_regions: list[RegionMetadata] | None


# ---------------------------------
# File Datasets
# ---------------------------------

COORDINATE_PARSING_TEST_DATASET = FileDataset(
    ["unit", "globetrotter", "region", "coordinate_parsing"],
    entry_model=CoordinateParsingTestCase,
    dataset_format=FileDatasetFormat.CSV,
)
REGION_METADATA_TEST_DATASET = FileDataset(
    ["unit", "globetrotter", "region", "region_metadata"],
    entry_model=RegionMetadataTestCase,
    dataset_format=FileDatasetFormat.CSV,
)
BOUNDING_BOX_TO_STRING_TEST_DATASET = FileDataset(
    ["unit", "globetrotter", "region", "bounding_box_to_string"],
    entry_model=BoundingBoxToStringTestCase,
    dataset_format=FileDatasetFormat.CSV,
)
BOUNDING_BOX_FROM_COORDINATES_TEST_DATASET = FileDataset(
    dataset_name=["unit", "globetrotter", "region", "bounding_box_from_coordinates"],
    entry_model=BoundingBoxFromCoordinatesTestCase,
    dataset_format=FileDatasetFormat.CSV,
)


# ---------------------------------
# Dynamic Datasets
# ---------------------------------

REGIONS_FROM_CSV_TEST_DATASET = Dataset(
    initial_entries=[
        RegionsFromCsvTestCase(label="empty", csv_file="empty_regions.csv", expected_regions=[]),
        RegionsFromCsvTestCase(label="single_entry", csv_file="single_entry_regions.csv", expected_regions=[
                RegionMetadata("ESP", "retiro", 0, Coordinates(40.4184, -3.6667))
        ]),
        RegionsFromCsvTestCase(label="malformed_lowercase", csv_file="malformed_regions_lowercase.csv",
                               expected_regions=None),
        RegionsFromCsvTestCase(label="malformed_missing_column", csv_file="malformed_regions_missing_columns.csv",
                               expected_regions=None)
    ],
    entry_model=RegionsFromCsvTestCase
)
