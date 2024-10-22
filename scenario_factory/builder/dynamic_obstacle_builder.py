from commonroad.geometry.shape import Rectangle
from commonroad.scenario.obstacle import DynamicObstacle, InitialState, ObstacleType

from scenario_factory.builder.core import BuilderCore


class DynamicObstacleBuilder(BuilderCore[DynamicObstacle]):
    """
    The `DynamicObstacleBuilder` makes it easy to create new dynamic obstacles.
    It is espacially usefull if one does not care about the specific properties of a dynamic obstacle (e.g. type, shape, states) and just needs a valid dynamic obstacle.
    """

    def __init__(self, dynamic_obstacle_id: int) -> None:
        self._dynamic_obstacle_id = dynamic_obstacle_id

        self._obstacle_type = ObstacleType.CAR
        self._obstacle_shape = Rectangle(length=3.0, width=2.0)

        self._initial_state = InitialState()
        self._initial_state.fill_with_defaults()

    def set_obstacle_type(self, obstacle_type: ObstacleType) -> "DynamicObstacleBuilder":
        self._obstacle_type = obstacle_type
        return self

    def build(self) -> DynamicObstacle:
        new_dynamic_obstacle = DynamicObstacle(
            self._dynamic_obstacle_id,
            obstacle_type=self._obstacle_type,
            obstacle_shape=self._obstacle_shape,
            initial_state=self._initial_state,
        )
        return new_dynamic_obstacle
