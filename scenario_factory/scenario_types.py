from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from xml.etree import cElementTree as ET

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import SumoConfig
from sumocr.helpers import shutil
from sumocr.interface.id_mapper import IdDomain

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver

logger = logging.getLogger(__name__)


@dataclass
class BaseScenario:
    scenario: Scenario


@dataclass
class SumoScenario(BaseScenario):
    """
    A CommonRoad scenario with additional SUMO configuration files.
    """

    sumo_cfg_file: Path


@dataclass
class SimulatedScenario(SumoScenario):
    sumo_config: SumoConfig

    # The id_mapping is used to correlate CommonRoad obstacle IDs with SUMO vehicle IDs. This is used to patch the resulting SUMO files, when generating interactive scenarios.
    # TODO: is there a cleaner approach, for retriving the IDs in interactive scenarios?
    id_mapping: Dict[int, str]


@dataclass
class EgoScenario(SimulatedScenario):
    """
    A CommonRoad scenario, that is centered around a specific ego vehicle maneuver. It is used to encode a CommonRoad scenario that is aligned to the ego vehicle maneuver, instead of being just a general simulated scenario. This is important, because there is a logical difference between a 'normal'
    """

    # The original ego vehicle maneuver, from which this ego scenario was derived. The maneuver is *not* aligned.
    ego_vehicle_maneuver: EgoVehicleManeuver

    @classmethod
    def from_simulated_scenario(
        cls,
        simulated_scenario: SimulatedScenario,
        ego_vehicle_maneuver: EgoVehicleManeuver,
        scenario: Optional[Scenario] = None,
    ) -> "EgoScenario":
        return EgoScenario(
            scenario=scenario if scenario is not None else simulated_scenario.scenario,
            sumo_cfg_file=simulated_scenario.sumo_cfg_file,
            sumo_config=simulated_scenario.sumo_config,
            id_mapping=simulated_scenario.id_mapping,
            ego_vehicle_maneuver=ego_vehicle_maneuver,
        )


@dataclass
class EgoScenarioWithPlanningProblemSet(EgoScenario):
    """
    A CommonRoad scenario, that is cenetered around a specific ego vehicle maneuver and has a corresponding planning problem set.
    """

    planning_problem_set: PlanningProblemSet

    @classmethod
    def from_ego_scenario(
        cls,
        ego_scenario: EgoScenario,
        planning_problem_set: PlanningProblemSet,
        scenario: Optional[Scenario] = None,
    ):
        return cls(
            scenario=scenario if scenario is not None else ego_scenario.scenario,
            sumo_cfg_file=ego_scenario.sumo_cfg_file,
            sumo_config=ego_scenario.sumo_config,
            ego_vehicle_maneuver=ego_scenario.ego_vehicle_maneuver,
            id_mapping=ego_scenario.id_mapping,
            planning_problem_set=planning_problem_set,
        )

    def write(self, output_path: Path) -> Path:
        file_path = output_path.joinpath(f"{self.scenario.scenario_id}.cr.xml")
        logger.debug(f"Writing scenario {self.scenario.scenario_id} with its planning problem set to {file_path}")
        CommonRoadFileWriter(
            self.scenario, self.planning_problem_set, author="test", affiliation="test", source="test", tags=set()
        ).write_to_file(str(file_path), overwrite_existing_file=OverwriteExistingFile.ALWAYS)
        return file_path


@dataclass
class NonInteractiveEgoScenario(EgoScenarioWithPlanningProblemSet):
    ...


def _patch_vehicle_id_in_sumo_route_file(vehicle_id: str, sumo_file_path: Path):
    """
    To support interactive scenarios in the sumo-interface, we must mark the ego vehicle as such in the SUMO files. This way, the sumo-interface knows which vehicle is the ego vehicle.
    """
    with sumo_file_path.open() as f:
        tree = ET.parse(f)

    vehicle_nodes = tree.findall("vehicle")
    for vehicle_node in vehicle_nodes:
        if vehicle_node.get("id") == vehicle_id:
            vehicle_node.set("id", IdDomain.EGO_VEHICLE.construct_sumo_id(vehicle_id))

    with sumo_file_path.open(mode="wb") as f:
        tree.write(f, xml_declaration=True, encoding="utf-8")


@dataclass
class InteractiveEgoScenario(EgoScenarioWithPlanningProblemSet):
    def write(self, output_path: Path) -> Path:
        scenario_path = output_path.joinpath(str(self.scenario.scenario_id))
        scenario_path.mkdir()

        super().write(scenario_path)

        for file in self.sumo_cfg_file.parent.iterdir():
            if file.suffix != ".xml" and file.suffix != ".cfg":
                continue

            target_file_name = f"{self.scenario.scenario_id}{''.join(file.suffixes)}"
            target_path = scenario_path.joinpath(target_file_name)

            shutil.copy(file, target_path)

            if file.suffixes == [".rou" ".xml"]:
                sumo_ego_vehicle_id = self.id_mapping[self.ego_vehicle_maneuver.ego_vehicle.obstacle_id]
                _patch_vehicle_id_in_sumo_route_file(sumo_ego_vehicle_id, target_path)

        return scenario_path
