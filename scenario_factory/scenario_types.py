import logging
import re
import xml.etree.ElementTree
from pathlib import Path
from typing import List, Sequence, Union

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.solution import PlanningProblemSolution, Solution
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from typing_extensions import TypeGuard

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver
from scenario_factory.metrics.single_scenario import SingleScenarioMetricResult
from scenario_factory.metrics.waymo import WaymoMetricResult

_LOGGER = logging.getLogger(__name__)


class ScenarioContainer:
    """
    The ScenarioContainer is used to wrap a scenario, such that it is easy to associate extra data with a scenario. All pipeline steps should use the ScenarioContainer instead of a plain CommonRoad scenario as their input parameter and output values.

    The pipeline steps in the scenario-factory are mostly concerned with handling CommonRoad scenarios. But often, additional data (like a planning problem set) is required or produced during a pipeline step. To ensure that each pipeline step can be applied generally, and does not rely on any specific order. For example, a pipeline step might produce a scenario with a planning problem set and another pipeline step might only require a CommonRoad scenario.
    """

    scenario: Scenario

    def __init__(self, scenario: Scenario):
        self.scenario = scenario

    def __str__(self) -> str:
        return str(self.scenario.scenario_id)


class ScenarioWithPlanningProblemSet(ScenarioContainer):
    planning_problem_set: PlanningProblemSet

    def __init__(self, scenario: Scenario, planning_problem_set: PlanningProblemSet):
        super().__init__(scenario)
        self.planning_problem_set = planning_problem_set


def is_scenario_with_planning_problem_set(
    scenario_container: ScenarioContainer,
) -> TypeGuard[ScenarioWithPlanningProblemSet]:
    return isinstance(scenario_container, ScenarioWithPlanningProblemSet)


class ScenarioWithSolution(ScenarioWithPlanningProblemSet):
    """
    Container for a CommonRoad Scenario, PlanningProblemSet and its associated solutions.
    """

    def __init__(
        self,
        scenario: Scenario,
        planning_problem_set: PlanningProblemSet,
        solutions: Sequence[PlanningProblemSolution],
    ) -> None:
        super().__init__(scenario, planning_problem_set)
        self._solutions = solutions

    @property
    def solution(self):
        # Only construct the Solution object here, to include the 'final' scenario ID.
        # This is required because the scenario ID might be manipulated in different places,
        # and so it would be difficult to track the ID of the scenario and the solution indepdently.
        return Solution(self.scenario.scenario_id, planning_problem_solutions=self._solutions)


def is_scenario_with_solution(
    scenario_container: ScenarioContainer,
) -> TypeGuard[ScenarioWithSolution]:
    return isinstance(scenario_container, ScenarioWithSolution)


class ScenarioWithWaymoMetrics(ScenarioContainer):
    waymo_metrics: WaymoMetricResult

    def __init__(self, scenario: Scenario, waymo_metrics: WaymoMetricResult) -> None:
        super().__init__(scenario)
        self.waymo_metrics = waymo_metrics


def is_scenario_with_waymo_metrics(
    scenario_container: ScenarioContainer,
) -> TypeGuard[ScenarioWithWaymoMetrics]:
    return isinstance(scenario_container, ScenarioWithWaymoMetrics)


class ScenarioWithSingleScenarioMetrics(ScenarioContainer):
    single_scenario_metrics: SingleScenarioMetricResult

    def __init__(
        self, scenario: Scenario, single_scenario_metrics: SingleScenarioMetricResult
    ) -> None:
        super().__init__(scenario)
        self.single_scenario_metrics = single_scenario_metrics


def is_scenario_with_single_scenario_metrics(
    scenario_container: ScenarioContainer,
) -> TypeGuard[ScenarioWithSingleScenarioMetrics]:
    return isinstance(scenario_container, ScenarioWithSingleScenarioMetrics)


class ScenarioWithReferenceScenario(ScenarioContainer):
    reference_scenario: Scenario

    def __init__(self, scenario: Scenario, reference_scenario: Scenario) -> None:
        super().__init__(scenario)
        self.reference_scenario = reference_scenario


def is_scenario_with_reference_scenario(
    scenario_container: ScenarioContainer,
) -> TypeGuard[ScenarioWithReferenceScenario]:
    return isinstance(scenario_container, ScenarioWithReferenceScenario)


class ScenarioWithEgoVehicleManeuver(ScenarioContainer):
    ego_vehicle_maneuver: EgoVehicleManeuver

    def __init__(self, scenario: Scenario, ego_vehicle_maneuver: EgoVehicleManeuver) -> None:
        super().__init__(scenario)
        self.ego_vehicle_maneuver = ego_vehicle_maneuver


def is_scenario_with_ego_vehicle_maneuver(
    scenario_container: ScenarioContainer,
) -> TypeGuard[ScenarioWithEgoVehicleManeuver]:
    return isinstance(scenario_container, ScenarioWithEgoVehicleManeuver)


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
                ScenarioWithPlanningProblemSet(scenario, planning_problem_set)
            )
        else:
            scenario_containers.append(ScenarioContainer(scenario))
    return scenario_containers


def load_scenarios_with_reference_scenarios_from_folders(
    path_scenarios: Path, path_reference_scenarios: Path
) -> List[ScenarioWithReferenceScenario]:
    scenarios_return: List[ScenarioWithReferenceScenario] = []
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
            scenarios_return.append(
                ScenarioWithReferenceScenario(cr_scenario, cr_reference_scenario)
            )
        except FileNotFoundError as e:
            _LOGGER.warning(f"Could not find reference scenario for {cr_scenario.scenario_id}: {e}")

    return scenarios_return
