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

        # Initialize the metadata. Defaults are not assigned to the scenario, because it should not be overwritten...
        author = "scenario-factory" if self.scenario.author is None else self.scenario.author
        affiliation = "TUM" if self.scenario.affiliation is None else self.scenario.affiliation
        source = "scenario-factory" if self.scenario.source is None else self.scenario.source
        tags = set() if self.scenario.tags is None else self.scenario.tags

        logger.debug(f"Writing scenario {self.scenario.scenario_id} with its planning problem set to {file_path}")
        CommonRoadFileWriter(
            self.scenario, self.planning_problem_set, author=author, affiliation=affiliation, source=source, tags=tags
        ).write_to_file(str(file_path), overwrite_existing_file=OverwriteExistingFile.ALWAYS, check_validity=True)
        return file_path


@dataclass
class NonInteractiveEgoScenario(EgoScenarioWithPlanningProblemSet):
    ...


def _patch_vehicle_id_in_sumo_route_file(vehicle_id: str, sumo_route_file: Path) -> bool:
    """
    To support interactive scenarios in the sumo-interface, we must mark the ego vehicle as such in the SUMO files. This way, the sumo-interface knows which vehicle is the ego vehicle.

    :param vehicle_id: The SUMO ID of the vehicle which should be marked as ego vehicle
    :param sumo_route_file: Path to the SUMO route file that contains vehicles

    :returns: Whether :param:`vehicle_id` was found and could be marked as an ego vehicle
    """
    root_element = ET.fromstring(sumo_route_file.read_text())

    found_vehicle = False
    vehicle_nodes = root_element.findall("vehicle")
    for vehicle_node in vehicle_nodes:
        if vehicle_node.get("id") == vehicle_id:
            vehicle_node.set("id", IdDomain.EGO_VEHICLE.construct_sumo_id(vehicle_id))
            found_vehicle = True
            break

    sumo_route_file.write_bytes(ET.tostring(root_element))
    return found_vehicle


def _patch_input_file_names_in_sumo_cfg_file(file_name_prefix: str, sumo_cfg_path: Path) -> None:
    """
    Patch all input file names found in the :param:`sumo_cfg_path` SUMO configuration file by replacing their file name with :param:`file_name_prefix` and preserving their suffixes

    :param file_name_prefix: The string that will be used to replace all file names
    :param sumo_cfg_path: Path to the SUMO configuration file

    :raises ValueError: If :param:`sumo_cfg_path` is not a valid SUMO configuration file
    """
    root_element = ET.fromstring(sumo_cfg_path.read_text())

    input_tag = root_element.find("input")
    if input_tag is None:
        raise ValueError(f"The SUMO configuration file at {sumo_cfg_path} is invalid: missing 'input' tag")

    input_iterator = input_tag.iter()
    # input_tag.iter() iterates over the tag itself and all child elements. As we only care about the child elements, we skip the first element of the iterator.
    next(input_iterator)
    for input_file_tag in input_iterator:
        # The 'value' attribute contains the file name e.g. DEU_Bremen-19.net.xml. This filename must be replaced with the file_name_prefix, e.g. DEU_Bremen-19_I-1.net.xml
        raw_input_file_name = input_file_tag.get("value")
        if raw_input_file_name is None:
            raise ValueError(
                f"The SUMO configuration file at {sumo_cfg_path} is invalid: tag {input_file_tag} does not have the required attribute 'value'"
            )
        # Use pathlib.Path, so the rename operation is easier to perform
        input_file_name = Path(raw_input_file_name)
        # Replace the the file name, but keep all suffixes
        new_input_file_name = file_name_prefix + "".join(input_file_name.suffixes)
        input_file_tag.set("value", str(new_input_file_name))

    sumo_cfg_path.write_bytes(ET.tostring(root_element))


@dataclass
class InteractiveEgoScenario(EgoScenarioWithPlanningProblemSet):
    def write(self, output_path: Path) -> Path:
        scenario_name = str(self.scenario.scenario_id)
        scenario_path = output_path.joinpath(scenario_name)
        scenario_path.mkdir()

        super().write(scenario_path)

        # We include all relevant SUMO configuration files in an interactice scenario. For this all SUMO files are copied into the new folder,
        # and renamed according to the scenario name (see loop below). As the '.sumo.cfg' file references all those SUMO files, it is possible that the file names differ.
        # This is possible, because one SUMO simulation might produce multiple scenarios.
        # Therefore, we ensure here that the sumo cfg file references the correct files, i.e. all files must start with the scenario name.
        _patch_input_file_names_in_sumo_cfg_file(scenario_name, self.sumo_cfg_file)

        for file in self.sumo_cfg_file.parent.iterdir():
            if file.suffix != ".xml" and file.suffix != ".cfg":
                # Only copy files from SUMO
                continue

            target_file_name = f"{scenario_name}{''.join(file.suffixes)}"
            target_path = scenario_path.joinpath(target_file_name)

            shutil.copy(file, target_path)

            if file.suffixes == [".rou" ".xml"]:
                # Because the sumo-interface relys on a specific id for the ego_vehicles we have to patch the resulting sumo file here
                sumo_ego_vehicle_id = self.id_mapping[self.ego_vehicle_maneuver.ego_vehicle.obstacle_id]
                _patch_vehicle_id_in_sumo_route_file(sumo_ego_vehicle_id, target_path)

        return scenario_path
