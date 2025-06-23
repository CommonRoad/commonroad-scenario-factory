import logging
import xml.etree.ElementTree as ET
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Tuple
from xml.dom import pulldom
from xml.sax import SAXParseException

from commonroad.common.file_reader import CommonRoadFileReader, FileFormat
from commonroad.common.solution import CommonRoadSolutionReader, Solution
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario

_LOGGER = logging.getLogger(__name__)


def try_load_xml_file_as_commonroad_scenario(
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


def try_load_xml_file_as_commonroad_solution(xml_file_path: Path) -> Optional[Solution]:
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


class CommonRoadXmlFileType(Enum):
    """
    Helper enum to distinguish the different XML files from the CommonRoad ecosystem.
    """

    UNKNOWN = auto()
    """The file is either no valid XML or no known file from the CommonRoad ecosystem."""

    SCENARIO = auto()
    """Identifies a CommonRoad scenario with planning problem set file."""

    SOLUTION = auto()
    """Identifies a CommonRoad solution file."""


def determine_xml_file_type(xml_file_path: Path) -> CommonRoadXmlFileType:
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
                return CommonRoadXmlFileType.SCENARIO
            elif node.nodeName.lower() == "commonroadsolution":
                return CommonRoadXmlFileType.SOLUTION
            else:
                return CommonRoadXmlFileType.UNKNOWN
    except SAXParseException:
        # fall thourgh to unknown if file is not valid XML
        pass
    return CommonRoadXmlFileType.UNKNOWN
