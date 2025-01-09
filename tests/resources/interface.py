import shutil
from contextlib import contextmanager
from enum import Enum, auto
from pathlib import Path
from tempfile import TemporaryDirectory


class ResourceType(Enum):
    OSM_MAP = auto()
    OSM_SOURCE_MAP = auto()
    CR_MAP = auto()
    CR_SCENARIO = auto()
    CSV_FILES = auto()

    def get_folder(self) -> Path:
        if self == ResourceType.OSM_MAP:
            return Path(__file__).parent / "osm_maps"
        elif self == ResourceType.OSM_SOURCE_MAP:
            return Path(__file__).parent / "osm_source_maps"
        elif self == ResourceType.CR_MAP:
            return Path(__file__).parent / "cr_maps"
        elif self == ResourceType.CR_SCENARIO:
            return Path(__file__).parent / "cr_scenarios"
        elif self == ResourceType.CSV_FILES:
            return Path(__file__).parent / "csv_files"
        else:
            raise ValueError(f"Invalid resource type {self}")


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


@contextmanager
def make_tmp_resource_folder(*resources: TmpResourceEntry):
    """
    Functional context manager that produces a temporary folder populated with the specified resources.
    """
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        for res in resources:
            resource_path = res.resource_type.get_folder() / res.resource_name
            if not resource_path.exists():
                raise RuntimeError(...)
            target_path = temp_path / res.tmp_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(resource_path, target_path)
        yield temp_path
