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
    CR_SCENARIO_WITHOUT_PLANNING_PROBLEM = auto()
    CR_SOLUTION = auto()
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
        elif self == ResourceType.CR_SOLUTION:
            return Path(__file__).parent / "cr_solutions"
        elif self == ResourceType.CSV_FILES:
            return Path(__file__).parent / "csv_files"
        else:
            raise ValueError(f"Invalid resource type {self}")


RESOURCES = {
    ResourceType.CR_SCENARIO_WITHOUT_PLANNING_PROBLEM: [
        "BWA_Tlokweng-6.cr.xml",
        "DZA_Annaba-7.cr.xml",
        "MDG_Toamasina-3.cr.xml",
    ],
    ResourceType.CR_SCENARIO: [
        "ARG_Carcarana-4_4_T-1.xml",
        "DEU_Meckenheim-1_4_T-1.xml",
        "ESP_Toledo-7_5_T-1.xml",
        "BEL_Putte-1_1_T-1.xml",
        "DEU_Moelln-4_4_T-1.xml",
        "HRV_Pula-10_1_T-1.xml",
        "DEU_Ibbenbueren-10_2_T-1.xml",
        "ITA_CarpiCentro-9_6_T-1.xml",
    ],
    ResourceType.CR_SOLUTION: [
        "BEL_Putte-1_1_T-1.solution.xml",
        "DEU_Meckenheim-1_4_T-1.solution.xml",
        "DEU_Ibbenbueren-10_2_T-1.solution.xml",
        "ESP_Toledo-7_5_T-1.solution.xml",
    ],
    ResourceType.OSM_MAP: [
        "ALB_Korce-1.osm",
        "HND_Santa_Barbara-1.osm",
        "IND_Jakarta-1.osm",
        "USA_Memphis-1.osm",
    ],
}


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
