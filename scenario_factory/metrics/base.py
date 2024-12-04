import statistics
from collections import defaultdict
from dataclasses import dataclass, fields
from typing import List, Sequence, TypeVar

from commonroad.scenario.scenario import ScenarioID


@dataclass
class BaseMetric:
    """
    Base class for metrics that are processed in the scenario factory.

    All metrics are associated with a scenario by their scenario id.
    """

    scenario_id: ScenarioID


_MetricT = TypeVar("_MetricT", bound=BaseMetric)


def combine_metrics(metric_collection: Sequence[_MetricT]) -> List[_MetricT]:
    """
    Combines metrics for the same scenario by taking the mean over the values for each metric.

    :param metric_collection: A collection of metrics, with multiple metrics per scenario id.

    :returns: Combined metrics, where each scenario id has only one metric.
    """
    if len(metric_collection) < 1:
        return []

    # Use the type of metric to determine the fields of the metric
    metric_type = type(metric_collection[0])

    metrics_by_scenario_id = defaultdict(list)
    for metric in metric_collection:
        metrics_by_scenario_id[metric.scenario_id].append(metric)

    combined_metrics = []
    for scenario_id, metrics_of_scenario_id in metrics_by_scenario_id.items():
        averaged_metrics = {}
        for field in fields(metric_type):
            # scenario id field needs to stay as is...
            if field.name == "scenario_id":
                continue

            averaged_metrics[field.name] = statistics.mean(
                [getattr(metric, field.name) for metric in metrics_of_scenario_id]
            )

        combined_metrics.append(metric_type(scenario_id, **averaged_metrics))

    return combined_metrics
