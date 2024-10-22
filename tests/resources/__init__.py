from enum import Enum, auto
from pathlib import Path


class ResourceType(Enum):
    OSM_MAP = auto()
    COMMONROAD_MAP = auto()
    COMMONROAD_SCENARIO = auto()

    def get_folder(self) -> Path:
        if self == ResourceType.OSM_MAP:
            return Path(__file__).parent / "osm_maps"
        elif self == ResourceType.COMMONROAD_MAP:
            return Path(__file__).parent / "commonroad_maps"
        elif self == ResourceType.COMMONROAD_SCENARIO:
            return Path(__file__).parent / "commonroad_scenarios"
        else:
            raise ValueError(f"Invalid resource type {self}")
