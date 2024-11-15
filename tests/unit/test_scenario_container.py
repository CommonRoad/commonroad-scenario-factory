import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from commonroad.common.solution import Solution
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario

from scenario_factory.scenario_container import (
    ScenarioContainer,
    _CommonRoadXmlFileType,
    _determine_xml_file_type,
    _try_load_xml_file_as_commonroad_scenario,
    _try_load_xml_file_as_commonroad_solution,
    load_scenarios_from_folder,
)
from tests.resources import RESOURCES, ResourceType


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


class TestTryLoadXmlFileAsCommonRoadScenario:
    def test_returns_none_if_file_does_not_exist(self) -> None:
        result = _try_load_xml_file_as_commonroad_scenario(Path("not existing path"))
        assert result is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.OSM_MAP])
    def test_returns_none_if_file_is_osm_map(self, file: str) -> None:
        file_path = ResourceType.OSM_MAP.get_folder() / file
        result = _try_load_xml_file_as_commonroad_scenario(file_path)
        assert result is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.COMMONROAD_SOLUTION])
    def test_returns_none_if_file_is_commonroad_solution(self, file: str) -> None:
        file_path = ResourceType.COMMONROAD_SOLUTION.get_folder() / file
        result = _try_load_xml_file_as_commonroad_scenario(file_path)
        assert result is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.COMMONROAD_SCENARIO])
    def test_can_successfully_load_commonroad_scenario(self, file: str) -> None:
        file_path = ResourceType.COMMONROAD_SCENARIO.get_folder() / file
        result = _try_load_xml_file_as_commonroad_scenario(file_path)
        assert result is not None
        assert isinstance(result[0], Scenario)
        assert isinstance(result[1], PlanningProblemSet)


class TestTryLoadXmlFileAsCommonRoadSolution:
    def test_returns_none_if_file_does_not_exist(self) -> None:
        solution = _try_load_xml_file_as_commonroad_solution(Path("not existing path"))
        assert solution is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.OSM_MAP])
    def test_returns_none_if_file_is_osm_map(self, file: str) -> None:
        file_path = ResourceType.OSM_MAP.get_folder() / file
        solution = _try_load_xml_file_as_commonroad_solution(file_path)
        assert solution is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.COMMONROAD_SCENARIO])
    def test_returns_none_if_file_is_commonroad_scenario(self, file: str) -> None:
        file_path = ResourceType.COMMONROAD_SCENARIO.get_folder() / file
        solution = _try_load_xml_file_as_commonroad_solution(file_path)
        assert solution is None

    @pytest.mark.parametrize("file", RESOURCES[ResourceType.COMMONROAD_SOLUTION])
    def test_can_successfully_load_commonroad_solution(self, file: str) -> None:
        file_path = ResourceType.COMMONROAD_SOLUTION.get_folder() / file
        solution = _try_load_xml_file_as_commonroad_solution(file_path)
        assert isinstance(solution, Solution)


class TestDetermineXmlFileType:
    @pytest.mark.parametrize("scenario_file", RESOURCES[ResourceType.COMMONROAD_SCENARIO])
    def test_identifies_all_scenarios(self, scenario_file: str) -> None:
        scenario_path = ResourceType.COMMONROAD_SCENARIO.get_folder() / scenario_file
        determined_xml_file_type = _determine_xml_file_type(scenario_path)
        assert determined_xml_file_type == _CommonRoadXmlFileType.SCENARIO

    @pytest.mark.parametrize("osm_map", RESOURCES[ResourceType.OSM_MAP])
    def test_identifies_osm_maps_as_unkown_file_types(self, osm_map: str) -> None:
        osm_map_path = ResourceType.OSM_MAP.get_folder() / osm_map
        determined_xml_file_type = _determine_xml_file_type(osm_map_path)
        assert determined_xml_file_type == _CommonRoadXmlFileType.UNKNOWN

    @pytest.mark.parametrize("solution_file", RESOURCES[ResourceType.COMMONROAD_SOLUTION])
    def test_identifies_all_solutions(self, solution_file: str) -> None:
        solution_path = ResourceType.COMMONROAD_SOLUTION.get_folder() / solution_file
        determined_xml_file_type = _determine_xml_file_type(solution_path)
        assert determined_xml_file_type == _CommonRoadXmlFileType.SOLUTION


class TestLoadScenariosFromFolder:
    def test_throws_file_not_found_error_if_source_folder_does_not_exist(self):
        with pytest.raises(FileNotFoundError):
            load_scenarios_from_folder("non existing folder")

    def test_succesfully_loads_all_scenarios_from_folder(self):
        scenarios_folder = ResourceType.COMMONROAD_SCENARIO.get_folder()
        scenario_containers = load_scenarios_from_folder(scenarios_folder)

        assert all(
            isinstance(scenario_container, ScenarioContainer)
            for scenario_container in scenario_containers
        )
        assert len(scenario_containers) == len(list(scenarios_folder.glob("*.xml")))

    def test_succesfully_loads_all_scenarios_with_their_solution_from_folder(self):
        temp_dir = TemporaryDirectory()
        temp_dir_path = Path(temp_dir.name)

        solutions_folder = ResourceType.COMMONROAD_SOLUTION.get_folder()
        scenarios_folder = ResourceType.COMMONROAD_SCENARIO.get_folder()

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
