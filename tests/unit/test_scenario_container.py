import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from commonroad.common.solution import Solution
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario

from scenario_factory.scenario_container import (
    ScenarioContainer,
    load_scenarios_from_folder,
)
from tests.resources import ResourceType


class TestScenarioContainer:
    def test_scenario_container_does_not_have_attachment_by_default(self) -> None:
        scenario_container = ScenarioContainer(Scenario(dt=0.1))
        assert scenario_container.get_attachment(PlanningProblemSet) is None
        assert not scenario_container.has_attachment(PlanningProblemSet)

    def test_delete_attachment_removes_attachment_from_scenario_container(self) -> None:
        scenario_container = ScenarioContainer(
            Scenario(dt=0.1), planning_problem_set=PlanningProblemSet()
        )

        assert scenario_container.has_attachment(PlanningProblemSet)
        scenario_container.delete_attachment(PlanningProblemSet)
        assert not scenario_container.has_attachment(PlanningProblemSet)


class TestLoadScenariosFromFolder:
    def test_throws_file_not_found_error_if_source_folder_does_not_exist(self):
        with pytest.raises(FileNotFoundError):
            load_scenarios_from_folder("non existing folder")

    def test_succesfully_loads_all_scenarios_from_folder(self):
        scenarios_folder = ResourceType.CR_SCENARIO.get_folder()
        scenario_containers = load_scenarios_from_folder(scenarios_folder)

        assert all(
            isinstance(scenario_container, ScenarioContainer)
            for scenario_container in scenario_containers
        )
        assert len(scenario_containers) == len(list(scenarios_folder.glob("*.xml")))

    def test_succesfully_loads_all_scenarios_with_their_solution_from_folder(self):
        temp_dir = TemporaryDirectory()
        temp_dir_path = Path(temp_dir.name)

        solutions_folder = ResourceType.CR_SOLUTION.get_folder()
        scenarios_folder = ResourceType.CR_SCENARIO.get_folder()

        # TODO: The logic below is ugly and very unstable
        # A more advanced resource managment solution would help here, to correlate scenarios with solutions.
        num_solutions = 0
        for file_path in solutions_folder.iterdir():
            shutil.copyfile(file_path, temp_dir_path / file_path.name)
            scenario_name = f"{file_path.name.split('.')[0]}.xml"
            shutil.copyfile(scenarios_folder / scenario_name, temp_dir_path / scenario_name)
            num_solutions += 1

        # santiy check for the functionality above
        assert num_solutions > 0

        scenario_containers = load_scenarios_from_folder(temp_dir_path)
        assert all(
            scenario_container.has_attachment(Solution)
            for scenario_container in scenario_containers
        )
        assert len(scenario_containers) == num_solutions
