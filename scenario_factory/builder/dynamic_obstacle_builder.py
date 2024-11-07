from commonroad.geometry.shape import Rectangle, Shape
from commonroad.prediction.prediction import Prediction
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
        self._prediction = None
        self._initial_signal_state = None
        self._signal_series = None

    @classmethod
    def from_dynamic_obstacle(cls, dynamic_obstacle: DynamicObstacle) -> "DynamicObstacleBuilder":
        dynamic_obstacle_builder = DynamicObstacleBuilder(dynamic_obstacle.obstacle_id)
        dynamic_obstacle_builder.set_obstacle_type(dynamic_obstacle.obstacle_type)
        dynamic_obstacle_builder.set_obstacle_shape(dynamic_obstacle.obstacle_shape)
        dynamic_obstacle_builder.set_initial_state(dynamic_obstacle.initial_state)
        dynamic_obstacle_builder.set_prediction(dynamic_obstacle.prediction)
        return dynamic_obstacle_builder

    def set_obstacle_type(self, obstacle_type: ObstacleType) -> "DynamicObstacleBuilder":
        self._obstacle_type = obstacle_type
        return self

    def set_obstacle_shape(self, obstacle_shape: Shape) -> "DynamicObstacleBuilder":
        self._obstacle_shape = obstacle_shape
        return self

    def set_initial_state(self, initial_state: InitialState) -> "DynamicObstacleBuilder":
        self._initial_state = initial_state
        return self

    def set_prediction(self, prediction: Prediction) -> "DynamicObstacleBuilder":
        self._prediction = prediction
        return self

    def build(self) -> DynamicObstacle:
        new_dynamic_obstacle = DynamicObstacle(
            self._dynamic_obstacle_id,
            obstacle_type=self._obstacle_type,
            obstacle_shape=self._obstacle_shape,
            initial_state=self._initial_state,
            prediction=self._prediction,
            initial_signal_state=self._initial_signal_state,
            signal_series=self._signal_series,  # type: ignore
        )
        return new_dynamic_obstacle
