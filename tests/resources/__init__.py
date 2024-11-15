from enum import Enum, auto
from pathlib import Path


class ResourceType(Enum):
    OSM_MAP = auto()
    COMMONROAD_MAP = auto()
    COMMONROAD_SCENARIO = auto()
    COMMONROAD_SOLUTION = auto()
    COMMONROAD_SCENARIO_WITHOUT_PLANNING_PROBLEM = auto()

    def get_folder(self) -> Path:
        if self == ResourceType.OSM_MAP:
            return Path(__file__).parent / "osm_maps"
        elif self == ResourceType.COMMONROAD_MAP:
            return Path(__file__).parent / "commonroad_maps"
        elif self == ResourceType.COMMONROAD_SCENARIO:
            return Path(__file__).parent / "commonroad_scenarios"
        elif self == ResourceType.COMMONROAD_SOLUTION:
            return Path(__file__).parent / "commonroad_solutions"
        elif self == ResourceType.COMMONROAD_SCENARIO_WITHOUT_PLANNING_PROBLEM:
            return Path(__file__).parent / "commonroad_scenarios_without_planning_problems"
        else:
            raise ValueError(f"Invalid resource type {self}")


RESOURCES = {
    ResourceType.COMMONROAD_SCENARIO_WITHOUT_PLANNING_PROBLEM: [
        "BWA_Tlokweng-6.cr.xml",
        "DZA_Annaba-7.cr.xml",
        "MDG_Toamasina-3.cr.xml",
    ],
    ResourceType.COMMONROAD_SCENARIO: [
        "ARG_Carcarana-4_4_T-1.xml",
        "DEU_Meckenheim-1_4_T-1.xml",
        "ESP_Toledo-7_5_T-1.xml",
        "BEL_Putte-1_1_T-1.xml",
        "DEU_Moelln-4_4_T-1.xml",
        "HRV_Pula-10_1_T-1.xml",
        "DEU_Ibbenbueren-10_2_T-1.xml",
        "ITA_CarpiCentro-9_6_T-1.xml",
    ],
    ResourceType.COMMONROAD_SOLUTION: [
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
