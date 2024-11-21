import csv
import shutil
from enum import Enum, auto
from json import load
from pathlib import Path
from tempfile import TemporaryDirectory

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.util import FileFormat
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.scenario import Scenario


class ResourceType(Enum):
    OSM_MAP = auto()
    OSM_SOURCE_MAP = auto()
    OSM_MAP_EXCERPT = auto()
    CR_LANELET_NETWORK = auto()
    CR_MAP = auto()
    CR_SCENARIO = auto()
    CSV_FILES = auto()

    def get_folder(self) -> Path:
        if self == ResourceType.OSM_MAP:
            return Path(__file__).parent / "osm_maps"
        elif self == ResourceType.OSM_SOURCE_MAP:
            return Path(__file__).parent / "osm_source_maps"
        elif self == ResourceType.OSM_MAP_EXCERPT:
            return Path(__file__).parent / "osm_map_excerpts"
        elif self == ResourceType.CR_LANELET_NETWORK:
            return Path(__file__).parent / "cr_lanelet_networks"
        elif self == ResourceType.CR_MAP:
            return Path(__file__).parent / "cr_maps"
        elif self == ResourceType.CR_SCENARIO:
            return Path(__file__).parent / "cr_scenarios"
        elif self == ResourceType.CSV_FILES:
            return Path(__file__).parent / "csv_files"
        else:
            raise ValueError(f"Invalid resource type {self}")


def get_test_dataset_csv(name: str, skip_first: bool = True) -> list:
    """
    Accesses a dataset from ./test_datasets/<name>.csv and returns it as a list of entries.

    :param name: The name of the dataset.
    :param skip_first: Determines whether the first (label) line of the csv file should be skipped.
    :raises NameError: Invalid dataset name.
    """
    target = Path(__file__).parent / f"test_datasets/{name}.csv"
    if not target.exists():
        raise NameError("")
    with open(target, "rt") as file:
        reader = csv.reader(file)
        if skip_first:
            next(reader)
        data = list(reader)
    return data


def get_test_dataset_json(name: str) -> list:
    """
    Accesses a dataset from ./test_datasets/<name>.json and returns it as a list of entries.

    :param name: The name of the dataset.
    :raises NameError: Invalid dataset name.
    """
    target = Path(__file__).parent / f"test_datasets/{name}.json"
    if not target.exists():
        raise NameError("")
    with open(target, "rt") as file:
        data = load(file)
    return data


class TmpResourceEntry:
    """
    File in a temporary resource folder.
    """

    resource_type: ResourceType
    resource_name: str
    tmp_path: Path

    def __init__(
        self, resource_type: ResourceType, resource_name: str, tmp_path: Path | None = None
    ):
        self.resource_type = resource_type
        self.resource_name = resource_name
        self.tmp_path = tmp_path if tmp_path is not None else Path(resource_name)


class TmpResourceFolder:
    """
    Context for a temporary folder populated with resources.
    """

    @property
    def path(self) -> Path:
        if self._temppath is None:
            raise RuntimeError("The context has not been created.")
        return self._temppath

    _tempdir: TemporaryDirectory | None
    _temppath: Path | None

    def __init__(self, *resources):
        self._resources = list(resources)
        self._tempdir = None
        self._temppath = None

    def __enter__(self):
        if self._tempdir is not None:
            raise RuntimeError("Cannot create a new context before exiting.")
        self._tempdir = TemporaryDirectory()
        self._temppath = Path(self._tempdir.name)
        for res in self._resources:
            resource_path = res.resource_type.get_folder() / res.resource_name
            if not resource_path.exists():
                self._tempdir.cleanup()
                self._tempdir = None
                raise NameError(f"The resource {resource_path.name} does not exist.")
            target_path = self._temppath / res.tmp_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(resource_path, target_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._tempdir is None:
            raise RuntimeError("Cannot exit before creating a context.")
        self._tempdir.cleanup()
        return False

    def get_path(self, relative: Path) -> Path:
        return self.path / relative


def load_cr_scenario_from_file(path: Path) -> Scenario:
    """
    Loads a CommonRoad scenario from the XML file representation.
    """
    raise NotImplementedError()


def load_cr_lanelet_network_from_file(path: Path) -> LaneletNetwork:
    """
    Loads a CommonRoad LaneletNetwork from a stripped down CommonRoad scenario-like XML file.
    """
    reader = CommonRoadFileReader(path, FileFormat.XML)
    network = reader.open_lanelet_network()
    return network


if __name__ == "__main__":
    network = load_cr_lanelet_network_from_file(
        ResourceType.CR_LANELET_NETWORK.get_folder() / "single_intersection.xml"
    )
    pass
