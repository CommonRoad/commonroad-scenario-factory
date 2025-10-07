import logging
from typing import Literal

from commonroad.planning.planning_problem import PlanningProblemSet

from scenario_factory.pipeline import PipelineContext, pipeline_map
from scenario_factory.scenario_container import ScenarioContainer
from scenario_factory.utils import copy_scenario

_LOGGER = logging.getLogger(__name__)

try:
    from commonroad_criticality_enhancement import bo, optimization, sa

    _CRITICALITY_ENHANCEMENT_AVAILABLE = True
except ImportError:
    _LOGGER.warning(
        "commonroad-criticality-enhancement is not available! Criticality enhancement will not be available."
    )

    _CRITICALITY_ENHANCEMENT_AVAILABLE = False


@pipeline_map()
def pipeline_enhance_criticality(
    ctx: PipelineContext,
    scenario_container: ScenarioContainer,
    decision_variables: list[tuple[str, str]],
    iterations: int = 10,
    method: Literal["bo", "sa", "gradient"] = "gradient",
) -> ScenarioContainer:
    """
    Enhance the criticality of a scenario by adjusting the velocity and/or position of the ego vehicle.

    :param decision_variables: The variables for which the criticality will be enhanced (e.g. ('velocity', 'ego')).
    :param iterations: The number of iterations for gradient-based optimization.
    :param method: Choose the criticality enhancement method: gradient-based optimization (gradient), simulated annealing (sa) or Bayesian optimization (bo).

    :returns: A re-wrapped scenario container with the enhanced scenario.

    :raises RuntimeError: If criticality enhancement is not available.
    :raises ValueError: If no ego vehicle was found in the scenario container or if an invalid enhancement method is given.
    """

    if not _CRITICALITY_ENHANCEMENT_AVAILABLE:
        raise RuntimeError(
            f"Cannot enhance criticality of scenario {scenario_container.scenario.scenario_id}: Criticality enhancement is not available"
        )

    scenario = copy_scenario(scenario_container.scenario)

    planning_problem_set = scenario_container.get_attachment(PlanningProblemSet)
    if planning_problem_set is None:
        raise ValueError(
            f"Cannot enhance criticality of scenario {scenario.scenario_id}: Missing attachment `{str(PlanningProblemSet)}`"
        )

    if method == "gradient":
        _, _ = optimization.optimize(
            scenario,
            planning_problem_set,
            decision_variables=decision_variables,
            iterations=iterations,
        )
    elif method == "sa":
        _, _ = sa.run_sa_with_scipy(
            scenario, planning_problem_set, decision_variables=decision_variables
        )
    elif method == "bo":
        _, _ = bo.run_bo_multi_variable(scenario, planning_problem_set, decision_variables)
    else:
        raise ValueError(
            f"Cannot enhance criticality of scenario {scenario.scenario_id}: Unknown optimization {method}"
        )

    # Re-wrap the modified scenario.
    return scenario_container.new_with_attachments(scenario)
