import logging
import xml.etree.ElementTree
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Type,
    TypedDict,
    TypeVar,
    Union,
    overload,
)

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.solution import Solution
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from commonroad_labeling.criticality.input_output.crime_output import ScenarioCriticalityData
from typing_extensions import Self, Unpack

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver

_LOGGER = logging.getLogger(__name__)

ScenarioContainerAttachmentT = TypeVar(
    "ScenarioContainerAttachmentT",
    PlanningProblemSet,
    Solution,
    ScenarioCriticalityData,
    EgoVehicleManeuver,
)


class ScenarioContainerArguments(TypedDict, total=False):
    """
    Typed dictionary for optional arguments that can be passed to a ScenarioContainer to add attachments to it.

    :param planning_problem_set: An optional planning problem set.
    :param solution: An optional planning problem solution, usually for the attached planning problem set.
    :param ego_vehicle_maneuver: An optional ego vehicle maneuver that happend in the scenario.
    :param criticality_data: Optional criticality data for the scenario.
    """

    planning_problem_set: PlanningProblemSet
    solution: Solution
    ego_vehicle_maneuver: EgoVehicleManeuver
    criticality_data: ScenarioCriticalityData


class ScenarioContainer:
    """
    A container for wrapping CommonRoad scenarios with optional attachments.

    The pipeline steps in the scenario-factory are mostly concerned with handling CommonRoad scenarios. But often, additional data (like a planning problem set) is required or produced during a pipeline step. To ensure that each pipeline step can be applied generally, and does not rely on any specific order, scenario containers are used as inputs and ouputs for most pipeline steps.

    :param scenario: The main CommonRoad scenario.
    :param planning_problem_set: An optional planning problem set.
    :param solution: An optional planning problem solution, usually for the attached planning problem set.
    :param ego_vehicle_maneuver: An optional ego vehicle maneuver that happend in the scenario.
    :param criticality_data: Optional criticality data for the scenario.
    """

    def __init__(self, scenario: Scenario, **kwargs: Unpack[ScenarioContainerArguments]):
        self._scenario = scenario

        self._attachments: Dict[Type, Any] = {}
        self._populate_attachments_from_dict(kwargs)

    def _populate_attachments_from_dict(self, attachments_dict: ScenarioContainerArguments) -> None:
        """
        Populate internal attachments from a dictionary of arguments.

        :param attachments_dict: Dictionary containing possible attachments.
        """
        for value in attachments_dict.values():
            if value is not None:
                self._attachments[type(value)] = value

    @property
    def scenario(self) -> Scenario:
        return self._scenario

    def get_attachment(
        self, attachment_locator: Type[ScenarioContainerAttachmentT]
    ) -> Optional[ScenarioContainerAttachmentT]:
        """
        Retrieve an attachment by its locator type.

        :param attachment: Locator class type for the attachment.
        :return: The requested attachment or None if not found.
        """
        return self._attachments.get(attachment_locator)

    def has_attachment(self, attachment_locator: Type[ScenarioContainerAttachmentT]) -> bool:
        """
        Check if a specific attachment is present.

        :param attachment: Locator class type for the attachment.
        :return: True if the attachment is present, False otherwise.
        """
        return attachment_locator in self._attachments

    def add_attachment(self, attachment_value: ScenarioContainerAttachmentT) -> None:
        """
        Add or update an attachment.

        :param attachment_value: Value to attach. If another value with type of `attachment_value` already exists, it will be overriden.
        """
        self._attachments[type(attachment_value)] = attachment_value

    def delete_attachment(self, attachment_locator: Type[ScenarioContainerAttachmentT]) -> None:
        """
        Remove an attachment from this scenario container by its locator.

        :param attachment: Locator class for the attachment.
        """
        del self._attachments[attachment_locator]

    def with_new_attachments(self, **kwargs: Unpack[ScenarioContainerArguments]) -> Self:
        """
        Add the attachments to this scenario container and return it-self.
        """
        self._populate_attachments_from_dict(kwargs)
        return self

    def __str__(self) -> str:
        return str(self.scenario.scenario_id)


def load_scenarios_from_folder(
    folder: Union[str, Path],
) -> List[ScenarioContainer]:
    if isinstance(folder, str):
        folder_path = Path(folder)
    elif isinstance(folder, Path):
        folder_path = folder
    else:
        raise ValueError(
            f"Argument 'folder' must be either 'str' or 'Path', but instead is {type(folder)}"
        )

    scenario_containers: List[ScenarioContainer] = []
    for xml_file_path in folder_path.glob("*.xml"):
        try:
            scenario, planning_problem_set = CommonRoadFileReader(xml_file_path).open()
        except xml.etree.ElementTree.ParseError as e:
            _LOGGER.warning("Failed to load CommonRoad scenario from file %s: %s", xml_file_path, e)
            continue

        if len(planning_problem_set.planning_problem_dict) > 0:
            scenario_containers.append(
                ScenarioContainer(scenario, planning_problem_set=planning_problem_set)
            )
        else:
            scenario_containers.append(ScenarioContainer(scenario))
    return scenario_containers
