import copy
import csv
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
)
from xml.dom import pulldom
from xml.sax import SAXParseException

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.solution import CommonRoadSolutionReader, Solution
from commonroad.common.util import FileFormat
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario, ScenarioID
from typing_extensions import Self, Unpack

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver
from scenario_factory.metrics import CriticalityMetrics, GeneralScenarioMetric, WaymoMetric

_LOGGER = logging.getLogger(__name__)


@dataclass
class ReferenceScenario:
    reference_scenario: Scenario


ScenarioContainerAttachmentT = TypeVar(
    "ScenarioContainerAttachmentT",
    PlanningProblemSet,
    Solution,
    EgoVehicleManeuver,
    ReferenceScenario,
    CriticalityMetrics,
    WaymoMetric,
    GeneralScenarioMetric,
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
    criticality_metric: CriticalityMetrics
    reference_scenario: ReferenceScenario
    waymo_metric: WaymoMetric
    general_scenario_metric: GeneralScenarioMetric


class ScenarioContainer:
    """
    A container for wrapping CommonRoad scenarios with optional attachments.

    The pipeline steps in the scenario-factory are mostly concerned with handling CommonRoad scenarios. But often, additional data (like a planning problem set) is required or produced during a pipeline step. To ensure that each pipeline step can be applied generally, and does not rely on any specific order, scenario containers are used as inputs and ouputs for most pipeline steps.

    :param scenario: The main CommonRoad scenario.
    :param planning_problem_set: An optional planning problem set.
    :param solution: An optional planning problem solution, usually for the attached planning problem set.
    :param ego_vehicle_maneuver: An optional ego vehicle maneuver that happend in the scenario.
    :param criticality_metric: Optional criticality metric for the scenario.
    :param reference_scenario: An optional reference scenario.
    :param waymo_metric: Optional waymo metrics for the scenario.
    :param general_scenario_metric: Optional general scenario metrics.
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

    def with_attachments(self, **kwargs: Unpack[ScenarioContainerArguments]) -> Self:
        """
        Add the attachments to this scenario container and return it-self.
        """
        self._populate_attachments_from_dict(kwargs)
        return self

    def new_with_attachments(
        self, new_scenario: Scenario, **kwargs: Unpack[ScenarioContainerArguments]
    ) -> "ScenarioContainer":
        """
        Create a new `ScenarioContainer` to wrap `new_scenario`, but copy all attachments from the old `ScenarioContainer` to the new one. If attachments are provided as kwargs, they will override the copied ones.

        :param new_scenario: The new scenario.
        :returns: A new `ScenarioContainer` object, with attachments from the old `ScenarioContainer` and kwargs.
        """
        new_scenario_container = ScenarioContainer(new_scenario)
        for attachment in self._attachments.values():
            attachment_copy = copy.deepcopy(attachment)
            new_scenario_container.add_attachment(attachment_copy)
        return new_scenario_container.with_attachments(**kwargs)

    def __str__(self) -> str:
        return str(self._scenario.scenario_id)


def _try_load_xml_file_as_commonroad_scenario(
    xml_file_path: Path,
) -> Optional[Tuple[Scenario, PlanningProblemSet]]:
    """
    Parse `xml_file_path` as a CommonRoad scenario.

    :returns: The `Scenario` and `PlanningProblemSet` from `xml_file_path`, or None if `xml_file_path` is not a valid CommonRoad XML file.
    """
    if not xml_file_path.exists():
        _LOGGER.warning(
            "Failed to load CommonRoad scenario from %s: File does not exist", xml_file_path
        )
        return None
    try:
        scenario, planning_problem_set = CommonRoadFileReader(
            xml_file_path, file_format=FileFormat.XML
        ).open()
        return scenario, planning_problem_set
    except ET.ParseError as e:
        _LOGGER.warning(
            "Failed to load CommonRoad scenario from file %s, because file does not contain valid XML: %s",
            xml_file_path,
            e,
        )
        return None
    except AssertionError as e:
        # Sadly, the CommonRoadFileReader does not expose a custom error type.
        # Therefore, all AssertionErrors are captured here, because they represent most of the errors that occur.
        _LOGGER.warning("Failed to load CommonRoad scenario from file %s: %s", xml_file_path, e)
        return None


def _try_load_xml_file_as_commonroad_solution(xml_file_path: Path) -> Optional[Solution]:
    """
    Parse `xml_file_path` as a CommonRoad solution.

    :returns: The `Solution` from `xml_file_path`, or None if `xml_file_path` is not a valid CommonRoad XML file.
    """
    if not xml_file_path.exists():
        _LOGGER.warning(
            "Failed to load CommonRoad solution from %s: File does not exist", xml_file_path
        )
        return None
    try:
        solution = CommonRoadSolutionReader().open(str(xml_file_path))
        return solution
    except ET.ParseError as e:
        _LOGGER.warning(
            "Failed to load CommonRoad solution from file %s, because file does not contain valid XML: %s",
            xml_file_path,
            e,
        )
        return None
    except AttributeError as e:
        # Sadly, the CommonRoadSolutionReader does not expose a custom error type.
        # Therefore, all AttributeErrors are captured here,
        # because this is usually the error indicating that the file is indeed valid XML,
        # but not a valid solution file.
        _LOGGER.warning(
            "Failed to load CommonRoad solution from file %s. The file is valid XML, but not a valid CommonRoad solution file: %s",
            xml_file_path,
            e,
        )
        return None


class _CommonRoadXmlFileType(Enum):
    """
    Helper enum to distinguish the different XML files from the CommonRoad ecosystem.
    """

    UNKNOWN = auto()
    """The file is either no valid XML or no known file from the CommonRoad ecosystem."""

    SCENARIO = auto()
    """Identifies a CommonRoad scenario with planning problem set file."""

    SOLUTION = auto()
    """Identifies a CommonRoad solution file."""


def _determine_xml_file_type(xml_file_path: Path) -> _CommonRoadXmlFileType:
    """
    Examines the root node of `xml_file_path` to determine which known CommonRoad format the file has.

    If the file cannot be parsed, the file type is determined to be `_CommonRoadXmlFileType.UNKOWN`.

    :param xml_file_path: Path to the XML file that should be checked. Must exist.
    :returns: The determined file type
    """
    # Use pulldom, so that only the minimum of the document needs to be parsed.
    # This is possible here, because we only need to read the root node,
    # which should occur at the beginning of the document.
    xml_context = pulldom.parse(str(xml_file_path))
    try:
        for event, node in xml_context:
            if event != pulldom.START_ELEMENT:
                continue

            if node.nodeName.lower() == "commonroad":
                return _CommonRoadXmlFileType.SCENARIO
            elif node.nodeName.lower() == "commonroadsolution":
                return _CommonRoadXmlFileType.SOLUTION
            else:
                return _CommonRoadXmlFileType.UNKNOWN
    except SAXParseException:
        # fall thourgh to unknown if file is not valid XML
        pass
    return _CommonRoadXmlFileType.UNKNOWN


def load_scenarios_from_folder(
    folder: Union[str, Path],
    reference_scenario_lookup_key: Optional[Callable[[ScenarioID], Optional[Path]]] = None,
) -> List[ScenarioContainer]:
    """
    Loads CommonRoad scenarios, planning problems, solutions, and optional reference scenarios from XML files in a specified folder.

    This function searches for `.xml` files within the provided folder, attempts to parse each file as a CommonRoad scenario or solution,
    and wraps each successfully loaded scenario and its associated data into `ScenarioContainer` instances.
    If a `reference_scenario_lookup_key` is provided, it will be used to locate and load a reference scenario for each scenario.

    :param folder: The path to the folder containing scenario XML files, provided as a string or `Path` object.
    :param reference_scenario_lookup_key: A callable that returns the path to a reference scenario for a given `ScenarioID`.
                                          If specified, this callable will be called for each loaded scenario to attempt to load an associated reference scenario.

    :raises ValueError: If `folder` is neither a string nor a `Path` instance.

    :return: A list of `ScenarioContainer` objects, each containing a scenario and optionally a planning problem set, solution, and/or reference scenario.
    """
    if isinstance(folder, str):
        folder_path = Path(folder)
    elif isinstance(folder, Path):
        folder_path = folder
    else:
        raise ValueError(
            f"Argument 'folder' must be either 'str' or 'Path', but instead is {type(folder)}"
        )

    if not folder_path.exists():
        raise FileNotFoundError(
            f"Cannot load scenarios from folder {folder_path}: folder does not exist!"
        )

    # Use a dict for containers and solution, so it is easier to merge them later on
    scenario_containers: Dict[ScenarioID, ScenarioContainer] = {}
    solutions: Dict[ScenarioID, Solution] = {}
    for xml_file_path in folder_path.glob("*.xml"):
        # Reliable determine whether the XML file is a known CommonRoad file.
        # If it is a known CommonRoad file type, also determine which one, so that the correct
        # reader can be used.
        xml_file_type = _determine_xml_file_type(xml_file_path)
        if xml_file_type == _CommonRoadXmlFileType.SCENARIO:
            scenario_parse_result = _try_load_xml_file_as_commonroad_scenario(xml_file_path)
            if scenario_parse_result is None:
                continue

            scenario, planning_problem_set = scenario_parse_result
            scenario_container = ScenarioContainer(scenario)
            # If the planning problem set is empty, and its added to the scenario container,
            # this might confuse downstream functionality, which might assume that if a
            # planning problem is attached it also contains planning problems.
            if len(planning_problem_set.planning_problem_dict) > 0:
                scenario_container.add_attachment(planning_problem_set)

            scenario_containers[scenario.scenario_id] = scenario_container

            # If a lookup key for reference scenarios is given, try to load the reference scenario
            if reference_scenario_lookup_key is None:
                continue

            reference_scenario_path = reference_scenario_lookup_key(scenario.scenario_id)
            if reference_scenario_path is None:
                _LOGGER.warning(
                    "Failed to load reference scenario for %s: no mapping to reference scenario path",
                    scenario.scenario_id,
                )
                continue

            reference_scenario_parse_result = _try_load_xml_file_as_commonroad_scenario(
                reference_scenario_path
            )
            if reference_scenario_parse_result is None:
                continue

            reference_scenario = ReferenceScenario(reference_scenario_parse_result[0])
            scenario_container.add_attachment(reference_scenario)
        elif xml_file_type == _CommonRoadXmlFileType.SOLUTION:
            solution = _try_load_xml_file_as_commonroad_solution(xml_file_path)
            if solution is None:
                continue

            solutions[solution.scenario_id] = solution

    # Correlate each solution with the scenario matching its benchmark id.
    # This must be done after all scenarios and solutions have been loaded, because
    # the scenario must be available to attach the solution to it. This order cannot be guaranteed
    # in the loading loop above.
    for scenario_id, solution in solutions.items():
        if scenario_id not in scenario_containers:
            _LOGGER.warning(
                "Loaded solution for scenario %s, but this scenario was not loaded from %s",
                scenario_id,
                folder_path,
            )
            continue

        scenario_containers[scenario_id].add_attachment(solution)

    return list(scenario_containers.values())


def load_scenarios_with_reference_from_folders(
    path_scenarios: Path, path_reference_scenarios: Path
) -> List[ScenarioContainer]:
    scenarios_return: List[ScenarioContainer] = []
    scenarios = path_scenarios.glob("*.xml")
    references = {
        "DEU_MONAEast-2": "C-DEU_MONAEast-2_1_T-299",
        "DEU_MONAMerge-2": "C-DEU_MONAMerge-2_1_T-299",
        "DEU_MONAWest-2": "C-DEU_MONAWest-2_1_T-299",
        "DEU_LocationCLower4-1": "DEU_LocationCLower4-1_48255_T-9754",
        "DEU_AachenHeckstrasse-1": "DEU_AachenHeckstrasse-1_3115929_T-17428",
    }
    for scenario in scenarios:
        if int(re.search(r"_(\d+)_(?=T-\d+)", scenario.stem)[1]) in (3, 4, 5):  # type: ignore
            continue
        cr_scenario, _ = CommonRoadFileReader(scenario).open()
        try:
            reference = references[re.match(r"^[^_]+_[^_]+", str(cr_scenario.scenario_id)).group(0)]  # type: ignore
            reference_scenario = path_reference_scenarios.joinpath(f"{reference}.xml")
            cr_reference_scenario, _ = CommonRoadFileReader(reference_scenario).open()
            scenarios_return.append(ScenarioContainer(scenario=cr_scenario))
            scenarios_return[-1].add_attachment(ReferenceScenario(cr_reference_scenario))
        except FileNotFoundError as e:
            _LOGGER.warning(f"Could not find reference scenario for {cr_scenario.scenario_id}: {e}")

    return scenarios_return


def write_criticality_metrics_of_scenario_containers_to_csv(
    scenario_containers: Iterable[ScenarioContainer], csv_file_path: Path
) -> None:
    """
    Write the cricticality data that is attached to the scenario_containers as CSV to `csv_file_path`.

    :param scenario_containers: Scenario containers with criticality data attached
    :param csv_file_path: Path to the file to which the data should be written. The file will be created if it does not exist, otherwise it will be overwritten.

    :returns: Nothing
    """
    formatted_data = []
    all_measurments = set()
    for scenario_container in scenario_containers:
        criticality_data = scenario_container.get_attachment(CriticalityMetrics)
        if criticality_data is None:
            raise ValueError(
                f"Cannot write criticality metrics of scenario {scenario_container.scenario.scenario_id} to csv file at {csv_file_path}: Scenario does not have a `CriticalityMetric` attachment, but one is required!"
            )

        all_measurments.update(criticality_data.get_metric_names())

        for time_step, measurment in criticality_data.measurments_per_time_step():
            row = {
                "scenarioId": str(scenario_container.scenario.scenario_id),
                "timeStep": time_step,
            }
            metrics = {}
            for metric, value in measurment.items():
                metrics[metric] = value
            row.update(metrics)
            formatted_data.append(row)

    measurment_fields = sorted(list(all_measurments))
    fieldnames = ["scenarioId", "timeStep"] + measurment_fields
    with csv_file_path.open(mode="w") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)


def write_general_scenario_metrics_of_scenario_containers_to_csv(
    scenario_containers: Iterable[ScenarioContainer], csv_file_path: Path
) -> None:
    formatted_data = []

    for scenario_container in scenario_containers:
        general_scenario_metric = scenario_container.get_attachment(GeneralScenarioMetric)
        if general_scenario_metric is None:
            raise ValueError(
                f"Cannot write scenario metrics of scenario {scenario_container.scenario.scenario_id} to csv file at {csv_file_path}: Scenario does not have a `GeneralScenarioMetric` attachment, but one is required!"
            )
        formatted_data.append(
            [
                str(scenario_container.scenario.scenario_id),
                general_scenario_metric.frequency,
                general_scenario_metric.velocity_mean,
                general_scenario_metric.velocity_stdev,
                general_scenario_metric.traffic_density_mean,
                general_scenario_metric.traffic_density_stdev,
            ]
        )

    with open(csv_file_path, "w") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            [
                "scenario_id",
                "f [1/s]",
                "v mean [m/s]",
                "v stdev [m/s]",
                "rho mean [1/km]",
                "rho stdev [1/km]",
            ]
        )
        csv_writer.writerows(formatted_data)


def write_waymo_metrics_of_scenario_containers_to_csv(
    scenario_containers: Iterable[ScenarioContainer], csv_file_path: Path
) -> None:
    formatted_data = []
    for scenario_container in scenario_containers:
        waymo_metrics = scenario_container.get_attachment(WaymoMetric)
        if waymo_metrics is None:
            raise RuntimeError()
        formatted_data.append(
            {
                "scenario_id": str(scenario_container.scenario.scenario_id),
                "ade3": waymo_metrics.ade3,
                "ade5": waymo_metrics.ade5,
                "ade8": waymo_metrics.ade8,
                "fde3": waymo_metrics.fde3,
                "fde5": waymo_metrics.fde5,
                "fde8": waymo_metrics.fde8,
                "mr3": waymo_metrics.mr3,
                "mr5": waymo_metrics.mr5,
                "mr8": waymo_metrics.mr8,
                "rmse_mean": waymo_metrics.rmse_mean,
                "rmse_stdev": waymo_metrics.rmse_stdev,
            }
        )

    with open(csv_file_path, "w") as csv_file:
        csv_writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "scenario_id",
                "ade3",
                "ade5",
                "ade8",
                "fde3",
                "fde5",
                "fde8",
                "mr3",
                "mr5",
                "mr8",
                "rmse_mean",
                "rmse_stdev",
            ],
        )
        csv_writer.writeheader()
        csv_writer.writerows(formatted_data)
