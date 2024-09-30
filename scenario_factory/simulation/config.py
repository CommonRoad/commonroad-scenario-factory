from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class SimulationMode(Enum):
    RANDOM_TRAFFIC_GENERATION = auto()
    """Generate traffic on a lanelet network using the simulator."""

    DEMAND_TRAFFIC_GENERATION = auto()
    """Generate traffic on a lanelet network according to the O/D Matrices extracted from the scenario."""

    INFRASTRUCTURE_TRAFFIC_GENERATION = auto()
    """Generate traffic on a lanelet network according to the lanelet capacities that are calculated from the scenario."""

    DELAY_RESIMULATION = auto()
    """Resimulate a scenario, but optionally delay the insertion of new vehicles if they would cause unsafe situations."""

    RESIMULATION = auto()
    """Resimulate the scenario."""


@dataclass
class SimulationConfig:
    mode: SimulationMode
    simulation_steps: Optional[int] = None

    def _post_init__(self):
        if self.mode == SimulationMode.RANDOM_TRAFFIC_GENERATION and self.simulation_steps is None:
            raise ValueError(
                f"Invalid SimulationConfig: if simulation mode is {self.mode}, simualation_steps must also be set!"
            )
