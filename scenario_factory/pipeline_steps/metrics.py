import logging
from typing import Callable, Optional, Sequence

from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.scenario import Scenario
from commonroad_crime.data_structure.base import CriMeBase
from commonroad_crime.measure import TTC
from crmonitor.common import World
from crmonitor.evaluation import OfflineRuleEvaluator

from scenario_factory.metrics import (
    compute_criticality_metrics_for_scenario_and_planning_problem_set,
    compute_criticality_metrics_for_scenario_with_ego_trajectory,
    compute_general_scenario_metric,
    compute_waymo_metric,
)
from scenario_factory.pipeline import (
    PipelineContext,
    pipeline_map,
)
from scenario_factory.scenario_container import (
    ReferenceScenario,
    ScenarioContainer,
    TrafficRuleRobustnessAttachment,
)

_LOGGER = logging.getLogger(__name__)


@pipeline_map()
def pipeline_compute_criticality_metrics(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    metrics: Sequence[type[CriMeBase]] = [TTC],
    ego_vehicles_already_in_scenario: bool = False,
) -> ScenarioContainer:
    """
    Compute the criticality metrics for the scenario.

    Currently this step only supports one planning problem in the planning problem set!

    :param ctx: The context for this pipeline execution
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    :param metrics: Specify the metrics that should be computed.
    :param ego_vehicles_already_in_scenario: If set to `True`, the ego vehicles are assumed to be
         in the scenario and to have the same ID as the planning problem(s).
         If set to `False`, the ego vehicles will be created from the planning problems
         and their trajectories will be calculated with the reactive motion planner.
    :returns: The input `ScenarioContainer` with an additional `CriticalityMetric` attachment.
    """
    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            f"Cannot compute criticality metrics for scenario {scenario_container.scenario.scenario_id}: Scenario container has no `PlanningProblemSet` attachment, but one is required!"
        )

    if len(planning_problem_set.planning_problem_dict) != 1:
        raise ValueError(
            f"Cannot compute criticality metrics for scenario {scenario_container.scenario.scenario_id}: `PlanningProblemSet` for scenario contains {len(planning_problem_set.planning_problem_dict)} planning problems, but exactly one is required!"
        )

    if ego_vehicles_already_in_scenario:
        # If the ego vehicle is already in the scenario, it must be mappable based on the planning problem id.
        # As we currently, limit ourselves to processing one planning problem,
        # the following statement simply selectes the sole planning problem.
        ego_id = list(planning_problem_set.planning_problem_dict.keys())[0]
        crime_metrics = compute_criticality_metrics_for_scenario_with_ego_trajectory(
            scenario_container.scenario, ego_id, metrics
        )
    else:
        crime_metrics = compute_criticality_metrics_for_scenario_and_planning_problem_set(
            scenario_container.scenario,
            planning_problem_set,
            metrics,
        )

    return scenario_container.with_attachments(
        criticality_metric=crime_metrics,
    )


@pipeline_map()
def pipeline_compute_waymo_metrics(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    """
    Compute the Waymo metrics for the scenario.

    :param ctx: The context for this pipeline execution
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    :returns: The input `ScenarioContainer` with an additional `WaymoMetric` attachment.
    """
    reference_scenario = scenario_container.get_attachment(ReferenceScenario)
    if reference_scenario is None:
        raise ValueError(
            f"Cannot compute waymo metric for scenario {scenario_container.scenario.scenario_id}: Scenario contaienr must have a `ReferenceScenario` attachment!"
        )
    waymo_metric = compute_waymo_metric(
        scenario_container.scenario, reference_scenario.reference_scenario
    )
    _LOGGER.debug(
        "Computed Waymo metrics for scenario %s: %s",
        str(scenario_container.scenario.scenario_id),
        str(waymo_metric),
    )

    return scenario_container.with_attachments(waymo_metric=waymo_metric)


@pipeline_map()
def pipeline_compute_single_scenario_metrics(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    frame_factor_callback: Optional[Callable[[Scenario], float]] = None,
) -> ScenarioContainer:
    """
    Compute the single scenario metrics for the scenario.

    Example: Compute metrics with frame factor adjustments

        def get_frame_factors(scenario: Scenario) -> float:
            scenario_id = str(scenario.scenario_id).split("-")[-3]
            match scenario_id:
                case "DEU_Example":
                    return 0.78
                case "ESP_Example":
                    return 0.6
                case _:
                    raise ValueError("No frame factor defined for scenario {scenario.scenario_id}")

        pipeline.map(pipeline_compute_single_scenario_metrics(frame_factor_callback))


    :param args: `ComputeSingleScenarioMetricsArguments` that specify the configuration for the computation
    :param scenario_container: The scenario for which the metrics should be computed. Will not be modified.
    :param frame_factor_callback: Optionally specify a frame factor callback, that will be used to
         determine a scaling factor for the given scenario to account for recorded scenarios,
        which lack obstacle trajectories at the fringe of the network.
    :returns: The input `scenario_container` with a `GeneralScenariometric` attachment.
    """

    frame_factor = 1.0
    if frame_factor_callback is not None:
        frame_factor = frame_factor_callback(scenario_container.scenario)

    general_scenario_metric = compute_general_scenario_metric(
        scenario_container.scenario, frame_factor
    )

    return scenario_container.with_attachments(general_scenario_metric=general_scenario_metric)


@pipeline_map()
def pipeline_compute_compliance_robustness_with_traffic_rule(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    traffic_rule_name: str,
    ego_vehicle_id: int | None = None,
) -> ScenarioContainer:
    """
    Compute the compliance robustness of an ego vehicle to a given traffic rule.

    If the `ScenarioContainer` has a `PlanningProblemSet` attachment and the `ego_vehicle_id
    parameter is not set, this will automatically use the planning problem Id as the ego vehicle Id.
    It is assumed that the corresponding vehicle is part of the scenario, e.g., because it was
    already injected using `pipeline_insert_ego_vehicle_solutions_into_scenario`.

    :param ctx: The context for this pipeline execution
    :param scenario_container: The scenario for which the traffic rule compliance should be evaluated.
    :param traffic_rule_name: The name of the traffic rule from `commonroad-stl-monitor` which should be evaluated.
    :param ego_vehicle_id: Optionally provide the Id of a vehicle in the scenario, which should be considered to be the ego vehicle. If this parameter is given, this pipeline step will not try to automatically determine the ego vehicle from the `PlanningProblemSet`.

    :returns: The input `ScenarioContainer` with a `TrafficRuleRobustnessAttachment` and the robustness for the given traffic rule.
    """
    # If no ego vehicle was explicitly specified, it should be determined automatically.
    if ego_vehicle_id is None:
        # If the scenario container has an associated planning problem set, the ego vehicle is the planning problem set.
        planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
        if planning_problem_set is None:
            raise ValueError(
                f"Failed to determine ego vehicle to compute compliance with traffic rule {traffic_rule_name} for scenario {scenario_container.scenario.scenario_id}: No ego vehicle Id was provided and scenario has no associated planning problem set"
            )

        # To be able to determine the ego vehicle from the planning problem set, exactly one planning problem set must be defined.
        ego_vehicle_ids = list(planning_problem_set.planning_problem_dict.keys())
        if len(ego_vehicle_ids) != 1:
            raise ValueError(
                f"Failed to determine ego vehicle to compute compliance with traffic rule {traffic_rule_name} for scenario {scenario_container.scenario.scenario_id}: Associated planning problem set has {len(ego_vehicle_ids)} possible ego vehicles, but must contain of only one ego vehicle"
            )

        ego_vehicle_id = ego_vehicle_ids[0]

        # The possible ego vehicle must be part of the scenario, so that the evaluator can evaluate the traffic rule for the vehicle.
        # It can be injected with, e.g., `pipeline_insert_ego_vehicle_solutions_into_scenario`.
        ego_vehicle = scenario_container.scenario.obstacle_by_id(ego_vehicle_id)
        if ego_vehicle is None:
            raise ValueError(
                f"Failed to determine ego vehicle to compute compliance with traffic rule {traffic_rule_name} for scenario {scenario_container.scenario.scenario_id}: Ego vehicle {ego_vehicle_id} from associated planning problem set is not part of the scenario"
            )

    world = World.create_from_scenario(scenario_container.scenario)

    rule_evaluator = OfflineRuleEvaluator.create_for_rule(
        traffic_rule_name, dt=scenario_container.scenario.dt
    )
    # Evaluate the compliance of the ego vehicle.
    robustness_trace = rule_evaluator.evaluate(world, ego_vehicle_id)

    # Save the robustness trace to the scenario container.
    traffic_rule_robustness_attachment = scenario_container.get_attachment(
        TrafficRuleRobustnessAttachment
    )
    if traffic_rule_robustness_attachment is None:
        traffic_rule_robustness_attachment = TrafficRuleRobustnessAttachment()
        scenario_container.add_attachment(traffic_rule_robustness_attachment)

    traffic_rule_robustness_attachment.robustness[traffic_rule_name] = robustness_trace

    return scenario_container
