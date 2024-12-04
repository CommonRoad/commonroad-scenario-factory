import numpy as np
from commonroad.scenario.lanelet import LaneletNetwork

from scenario_factory.globetrotter import BoundingBox, Coordinates, RegionMetadata
from tests.automation.datasets import Dataset, FileDataset, FileDatasetFormat
from tests.automation.validation import TestCase
from tests.helpers.lanelet_network import UsefulLaneletNetworks

# ---------------------------------
# Entry Models
# ---------------------------------


class CanonicalNamesTestCase(TestCase):
    name: str
    canonical_name: str


class RegionalMapsTestCase(TestCase):
    map_files: list[str]
    region: RegionMetadata
    expected_region_map: str | None


class MapExcerptTestCase(TestCase):
    bounding_box: BoundingBox
    input_map: str
    expected_excerpt: str | None


class CenterPolylinesTestCase(TestCase):
    lanelet_network: LaneletNetwork
    expected_center_polylines: dict[int, np.ndarray]


class LocalProviderTestCase(TestCase):
    map_files: list[str]
    region: RegionMetadata
    bounding_box: BoundingBox
    expected_excerpt: str | None


# ---------------------------------
# File Datasets
# ---------------------------------

CANONICAL_NAMES_TEST_DATASET = FileDataset(
    filename="unit/globetrotter/osm/canonical_names.csv",
    entry_model=CanonicalNamesTestCase,
    file_format=FileDatasetFormat.CSV,
)


# ---------------------------------
# Dynamic Datasets
# ---------------------------------

REGIONAL_MAPS_TEST_DATASET = Dataset(
    [
        RegionalMapsTestCase(
            label="no_maps",
            map_files=[],
            region=RegionMetadata("DE", "Aachen", 0, Coordinates(0, 0)),
            expected_region_map=None,
        ),
        RegionalMapsTestCase(
            label="single_correct_map",
            map_files=["aachen-latest.osm.pbf"],
            region=RegionMetadata("DE", "Aachen", 0, Coordinates(0, 0)),
            expected_region_map="aachen-latest.osm.pbf",
        ),
        RegionalMapsTestCase(
            label="multiple_maps_with_correct",
            map_files=["düren-latest.osm.pbf", "bonn-latest.osm.pbf", "aachen-latest.osm.pbf"],
            region=RegionMetadata("DE", "Bonn", 0, Coordinates(0, 0)),
            expected_region_map="bonn-latest.osm.pbf",
        ),
        RegionalMapsTestCase(
            label="multiple_maps_without_correct",
            map_files=["düren-latest.osm.pbf", "bonn-latest.osm.pbf", "aachen-latest.osm.pbf"],
            region=RegionMetadata("DE", "Köln", 0, Coordinates(0, 0)),
            expected_region_map=None,
        ),
    ]
)

MAP_EXCERPTS_TEST_DATASET = Dataset(
    [
        MapExcerptTestCase(
            label="partial_excerpt",
            bounding_box=BoundingBox(
                west=6.464703, south=51.025325, east=6.486954, north=51.035756
            ),
            input_map="düren-latest.osm.pbf",
            expected_excerpt="düren-partial-excerpt.osm",
        ),
        MapExcerptTestCase(
            label="complete_excerpt",
            bounding_box=BoundingBox(
                west=6.445126, south=51.015997, east=6.451094, north=51.018542
            ),
            input_map="düren-latest.osm.pbf",
            expected_excerpt="düren-complete-excerpt.osm",
        ),
        MapExcerptTestCase(
            label="empty_excerpt",
            bounding_box=BoundingBox(
                west=6.431527, south=51.047268, east=6.442585, north=51.053013
            ),
            input_map="düren-latest.osm.pbf",
            expected_excerpt=None,
        ),
    ]
)

CENTER_POLYLINES_TEST_DATASET = Dataset(
    [
        CenterPolylinesTestCase(
            label="single_lanelet",
            lanelet_network=UsefulLaneletNetworks.single_lanelet_no_meta(),
            expected_center_polylines={1: np.array([[0, -5], [25, -5], [25, 20]])},
        ),
        CenterPolylinesTestCase(
            label="empty",
            lanelet_network=UsefulLaneletNetworks.empty_no_meta(),
            expected_center_polylines={},
        ),
        CenterPolylinesTestCase(
            label="one_split",
            lanelet_network=UsefulLaneletNetworks.one_split_no_meta(),
            expected_center_polylines={
                1: np.array([[0, -5], [20, -5]]),
                2: np.array([[20, -5], [40, -5]]),
                3: np.array([[20, -5], [40, 15]]),
            },
        ),
    ]
)

LOCAL_PROVIDER_TEST_DATASET = Dataset(
    [
        LocalProviderTestCase(
            label="generic1",
            map_files=["aachen-latest.osm.pbf", "düren-latest.osm.pbf", "bonn-latest.osm.pbf"],
            region=RegionMetadata("DE", "Düren", 0, Coordinates(0, 0)),
            bounding_box=BoundingBox(
                west=6.445126, south=51.015997, east=6.451094, north=51.018542
            ),
            expected_excerpt="düren-complete-excerpt.osm",
        )
    ]
)
