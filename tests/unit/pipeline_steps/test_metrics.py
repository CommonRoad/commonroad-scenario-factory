import math

import pytest
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario

from scenario_factory.metrics import CriticalityMetrics, GeneralScenarioMetric
from scenario_factory.pipeline import PipelineContext
from scenario_factory.pipeline_steps import (
    pipeline_compute_criticality_metrics,
    pipeline_compute_single_scenario_metrics,
)
from scenario_factory.scenario_container import ScenarioContainer
from tests.resources import RESOURCES, ResourceType


class TestPipelineComputeCriticalityMetrics:
    def test_fails_if_no_planning_problem_set_is_provided(self) -> None:
        scenario = Scenario(dt=0.1)
        scenario_container = ScenarioContainer(scenario)
        ctx = PipelineContext()
        with pytest.raises(ValueError):
            pipeline_compute_criticality_metrics()(ctx, scenario_container)

    @pytest.mark.parametrize(
        argnames="scenario_file", argvalues=RESOURCES[ResourceType.CR_SCENARIO]
    )
    def test_computes_criticality_metrics_and_stores_result_in_scenario_container_attachment(
        self, scenario_file: str
    ) -> None:
        scenario_path = ResourceType.CR_SCENARIO.get_folder() / scenario_file
        scenario, planning_problem_set = CommonRoadFileReader(scenario_path).open()
        scenario_container = ScenarioContainer(scenario, planning_problem_set=planning_problem_set)

        ctx = PipelineContext()
        scenario_container_with_criticality_metrics = pipeline_compute_criticality_metrics()(
            ctx, scenario_container
        )

        criticality_metric = scenario_container_with_criticality_metrics.get_attachment(
            CriticalityMetrics
        )
        assert criticality_metric is not None
        # The planning problem set should be preserved
        assert scenario_container_with_criticality_metrics.has_attachment(PlanningProblemSet)


class TestPipelineComputeSingleScenarioMetrics:
    @pytest.mark.parametrize(
        argnames="scenario_file", argvalues=RESOURCES[ResourceType.CR_SCENARIO]
    )
    def test_computes_metrics_and_stores_result_in_scenario_container_attachment(
        self, scenario_file: str
    ) -> None:
        scenario_path = ResourceType.CR_SCENARIO.get_folder() / scenario_file
        scenario, planning_problem_set = CommonRoadFileReader(scenario_path).open()
        scenario_container = ScenarioContainer(scenario, planning_problem_set=planning_problem_set)

        ctx = PipelineContext()
        scenario_container_with_single_scenario_metrics = (
            pipeline_compute_single_scenario_metrics()(ctx, scenario_container)
        )

        general_scenario_metrics = scenario_container_with_single_scenario_metrics.get_attachment(
            GeneralScenarioMetric
        )
        assert general_scenario_metrics is not None
        assert not math.isnan(general_scenario_metrics.frequency)
        assert not math.isnan(general_scenario_metrics.traffic_density_mean)
        assert not math.isnan(general_scenario_metrics.traffic_density_stdev)
        assert not math.isnan(general_scenario_metrics.velocity_mean)
        assert not math.isnan(general_scenario_metrics.velocity_stdev)
