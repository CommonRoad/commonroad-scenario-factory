from typing import Dict, Iterable, Optional, Union

from commonroad.geometry.shape import Shape
from commonroad.scenario.lanelet import LaneletNetwork
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType
from commonroad.scenario.state import TraceState


def select_by_vehicle_type(
    obstacles: Iterable, vehicle_types: Iterable[ObstacleType] = (ObstacleType.CAR)
) -> Union[Dict[int, DynamicObstacle], Iterable[DynamicObstacle]]:
    """:returns only obstacles with specified vehicle type(s)."""
    if isinstance(obstacles, dict):
        return {obs_id: obs for obs_id, obs in obstacles.items() if (obs.obstacle_type in vehicle_types)}
    else:
        return [obs for obs in obstacles if (obs.obstacle_type in vehicle_types)]


def find_most_likely_lanelet_by_state(lanelet_network: LaneletNetwork, state: TraceState) -> Optional[int]:
    if not isinstance(state.position, Shape):
        return None

    lanelet_ids = lanelet_network.find_lanelet_by_shape(state.position)
    if len(lanelet_ids) == 0:
        return None

    if len(lanelet_ids) == 1:
        return lanelet_ids[0]

    # TODO
    return lanelet_ids[0]
