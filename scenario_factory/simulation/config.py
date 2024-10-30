from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class SimulationMode(Enum):
    """
    Choose between the different simulation modes. Not all simulation modes might be supported by all simulators!
    """

    RANDOM_TRAFFIC_GENERATION = auto()
    """Generate traffic on a lanelet network using the simulator."""

    DEMAND_TRAFFIC_GENERATION = auto()
    """Generate traffic on a lanelet network according to the O/D Matrices extracted from the scenario."""

    INFRASTRUCTURE_TRAFFIC_GENERATION = auto()
    """Generate traffic on a lanelet network according to the lanelet capacities that are calculated from the scenario."""

    DELAY = auto()
    """Resimulate a scenario, but optionally delay the insertion of new vehicles if they would cause unsafe situations."""

    RESIMULATION = auto()
    """Resimulate the scenario as close as possible. This can lead to unsafe insertions of """


@dataclass
class SimulationConfig:
    """Generic config that can be used by every simulator."""

    mode: SimulationMode
    """Configure the mode for the simulation"""

    simulation_steps: Optional[int] = None
    """Limit the number of time steps that will be simulated. Must be set for the `SimulationMode.RANDOM_TRAFFIC_GENERATION`"""

    def _post_init__(self):
        if self.mode == SimulationMode.RANDOM_TRAFFIC_GENERATION and self.simulation_steps is None:
            raise ValueError(
                f"Invalid SimulationConfig: if simulation mode is {self.mode}, simualation_steps must also be set!"
            )
