from typing import Optional, Union

from commonroad.geometry.shape import Rectangle, Shape
from commonroad.prediction.prediction import Prediction, TrajectoryPrediction
from commonroad.scenario.obstacle import DynamicObstacle, InitialState, ObstacleType
from commonroad.scenario.trajectory import Trajectory

from scenario_factory.builder.core import BuilderCore
from scenario_factory.builder.trajectory_builder import TrajectoryBuilder


class DynamicObstacleBuilder(BuilderCore[DynamicObstacle]):
    """
    The `DynamicObstacleBuilder` makes it easy to create new dynamic obstacles.
    It is espacially usefull if one does not care about the specific properties of a dynamic obstacle (e.g. type, shape, states) and just needs a valid dynamic obstacle.

    :param dynamic_obstacle_id: The unique identifier for the dynamic obstacle to be built.
    """

    def __init__(self, dynamic_obstacle_id: int) -> None:
        self._dynamic_obstacle_id = dynamic_obstacle_id

        self._obstacle_type = ObstacleType.CAR
        self._obstacle_shape = Rectangle(length=3.0, width=2.0)
        # Important to set time_step=0, because otherwise it might become 0.0 with `fill_with_defaults`...
        self._initial_state = InitialState(time_step=0)
        self._initial_state.fill_with_defaults()
        self._prediction = None
        self._trajectory = None
        self._trajectory_builder: Optional[TrajectoryBuilder] = None
        self._initial_signal_state = None
        self._signal_series = None

    @classmethod
    def from_dynamic_obstacle(cls, dynamic_obstacle: DynamicObstacle) -> "DynamicObstacleBuilder":
        """
        Creates a `DynamicObstacleBuilder` from an existing `DynamicObstacle` instance.

        :param dynamic_obstacle: The dynamic obstacle to use as a template for the builder.
        :return: A builder initialized with the properties of the provided dynamic obstacle.
        """
        dynamic_obstacle_builder = DynamicObstacleBuilder(dynamic_obstacle.obstacle_id)
        dynamic_obstacle_builder.set_obstacle_type(dynamic_obstacle.obstacle_type)
        dynamic_obstacle_builder.set_obstacle_shape(dynamic_obstacle.obstacle_shape)
        dynamic_obstacle_builder.set_initial_state(dynamic_obstacle.initial_state)
        dynamic_obstacle_builder.set_prediction(dynamic_obstacle.prediction)
        return dynamic_obstacle_builder

    def set_obstacle_type(self, obstacle_type: ObstacleType) -> "DynamicObstacleBuilder":
        """
        Sets the `ObstacleType` of the obstacle.

        :param obstacle_type: The type of obstacle, such as CAR, TRUCK, etc.
        :return: The builder instance, allowing for method chaining.
        """
        self._obstacle_type = obstacle_type
        return self

    def set_obstacle_shape(self, obstacle_shape: Shape) -> "DynamicObstacleBuilder":
        """
        Sets the shape of the obstacle.

        :param obstacle_shape: The geometric shape of the obstacle.
        :return: The builder instance, allowing for method chaining.
        """
        self._obstacle_shape = obstacle_shape
        return self

    def set_initial_state(self, initial_state: InitialState) -> "DynamicObstacleBuilder":
        """
        Sets the initial state of the obstacle.

        :param initial_state: The initial state of the obstacle, including position, velocity, etc.
        :return: The builder instance, allowing for method chaining.
        """
        self._initial_state = initial_state
        return self

    def set_prediction(self, prediction: Prediction) -> "DynamicObstacleBuilder":
        """
        Sets the prediction of the obstacle's future states.

        :param prediction: The prediction of the obstacle's trajectory.
        :return: The builder instance, allowing for method chaining.
        """
        self._prediction = prediction
        return self

    def set_trajectory(
        self, trajectory_or_builder: Union[Trajectory, TrajectoryBuilder]
    ) -> "DynamicObstacleBuilder":
        if isinstance(trajectory_or_builder, Trajectory):
            self._trajectory = trajectory_or_builder
        else:
            self._trajectory_builder = trajectory_or_builder
        return self

    def create_trajectory(
        self,
    ) -> "TrajectoryBuilder":
        self._trajectory_builder = TrajectoryBuilder()
        return self._trajectory_builder

    def build(self) -> DynamicObstacle:
        """
        Constructs and returns a new `DynamicObstacle` instance based on the builder's current settings.

        :return: A `DynamicObstacle` instance with the specified properties.
        """
        prediction = self._prediction
        if self._prediction is None:
            trajectory = self._trajectory
            if self._trajectory_builder is not None:
                trajectory = self._trajectory_builder.build()

            if trajectory is not None:
                prediction = TrajectoryPrediction(trajectory, self._obstacle_shape)

        new_dynamic_obstacle = DynamicObstacle(
            self._dynamic_obstacle_id,
            obstacle_type=self._obstacle_type,
            obstacle_shape=self._obstacle_shape,
            initial_state=self._initial_state,
            prediction=prediction,
            initial_signal_state=self._initial_signal_state,
            signal_series=self._signal_series,  # type: ignore
        )
        return new_dynamic_obstacle
