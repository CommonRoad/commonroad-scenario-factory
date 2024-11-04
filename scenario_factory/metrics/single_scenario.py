from dataclasses import dataclass

from commonroad.scenario.scenario import Scenario


@dataclass
class SingleScenarioMetricResult:
    """
    Data class for the initial submission metrics.
    """

    frequency: float
    traffic_density_mean: float
    traffic_density_stdev: float
    velocity_mean: float
    velocity_stdev: float

    def __str__(self) -> str:
        return f"f: {self.frequency:.4f}, rho_mu: {self.traffic_density_mean:.4f}, rho_sigma: {self.traffic_density_stdev:.4f}, v_mu: {self.velocity_mean:.4f}, v_sigma: {self.velocity_stdev:.4f}"


def compute_single_scenario_metrics(scenario: Scenario) -> SingleScenarioMetricResult:
    """
    Compute the initial submission metrics for the scenario.

    :param scenario: The scenario for which the metrics should be computed.
    """
    # calculate traffic density
    traffic_density_mean = 0.0
    traffic_density_stdev = 0.0
    velocity_mean = 0.0
    velocity_stdev = 0.0

    return SingleScenarioMetricResult(
        frequency=0.0,
        traffic_density_mean=traffic_density_mean,
        traffic_density_stdev=traffic_density_stdev,
        velocity_mean=velocity_mean,
        velocity_stdev=velocity_stdev,
    )
