import logging
import xml.etree.ElementTree
from pathlib import Path
from typing import List, Sequence, Union

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.solution import PlanningProblemSolution, Solution
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from typing_extensions import TypeGuard

from scenario_factory.ego_vehicle_selection import EgoVehicleManeuver

_LOGGER = logging.getLogger(__name__)


class ScenarioContainer:
    """
    The ScenarioContainer is used to wrap a scenario, such that it is easy to associate extra data with a scenario. All pipeline steps should use the ScenarioContainer instead of a plain CommonRoad scenario as their input parameter and output values.

    The pipeline steps in the scenario-factory are mostly concerned with handling CommonRoad scenarios. But often, additional data (like a planning problem set) is required or produced during a pipeline step. To ensure that each pipeline step can be applied generally, and does not rely on any specific order. For example, a pipeline step might produce a scenario with a planning problem set and another pipeline step might only require a CommonRoad scenario.
    """

    scenario: Scenario

    def __init__(self, scenario: Scenario):
        self.scenario = scenario


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
