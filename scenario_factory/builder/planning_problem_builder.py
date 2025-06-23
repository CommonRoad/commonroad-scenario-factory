from collections import defaultdict
from typing import Dict, List, Literal, Optional

from commonroad.common.util import Interval
from commonroad.geometry.shape import Rectangle
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem, PlanningProblemSet
from commonroad.scenario.scenario import Lanelet
from commonroad.scenario.state import InitialState, PMState, TraceState
from commonroad.scenario.trajectory import Trajectory
from typing_extensions import Self

from scenario_factory.builder.core import BuilderCore, BuilderIdAllocator
from scenario_factory.utils import convert_state_to_state_type


class PlanningProblemBuilder(BuilderCore[PlanningProblem]):
    """
    The `PlanningProblemBuilder` is used to easily construct simple `PlanningProblem`s. Its main benefit is, that one can simply define a start and multiple goal lanelets, and the initial state and goal region will be automatically infered from this.

    :param planning_problem_id: The unique CommonRoad ID that will be assigned to the resulting planning problem.
    """

    def __init__(self, planning_problem_id: int) -> None:
        self._planning_problem_id = planning_problem_id

        self._initial_state: Optional[InitialState] = None

        self._goal_dimensions = (6.0, 3.0)

        self._goal_states: List[TraceState] = []
        self._goal_states_idx = 0
        self._goal_states_to_lanelet_ids: Dict[int, List[int]] = defaultdict(list)

    def _add_goal_state(self, goal_state: TraceState, lanelet_id: Optional[int] = None) -> None:
        if lanelet_id is not None:
            self._goal_states_to_lanelet_ids[self._goal_states_idx].append(lanelet_id)
        self._goal_states.append(goal_state)
        self._goal_states_idx += 1

    def from_trajectory(self, trajectory: Trajectory) -> Self:
        if self._initial_state is not None:
            raise RuntimeError(
                "Cannot populate PlanningProblemBuilder from trajectory: The builder was already populated!"
            )

        initial_state = trajectory.state_at_time_step(trajectory.initial_time_step)
        if initial_state is None:
            raise RuntimeError("The first state of the trajectory is None. This is a bug!")

        self._initial_state = convert_state_to_state_type(initial_state, InitialState)

        final_state = trajectory.final_state
        goal_state = PMState(
            time_step=Interval(start=final_state.time_step - 1, end=final_state.time_step),
            position=Rectangle(
                self._goal_dimensions[0],
                self._goal_dimensions[1],
                center=final_state.position,
                orientation=final_state.orientation if final_state.orientation is not None else 0,
            ),
        )
        self._add_goal_state(goal_state)

        return self

    def set_start(self, lanelet: Lanelet, align: Literal["start", "end"] = "start") -> Self:
        """
        Define the start lanelet of this planning problem.

        :param lanelet: The start lanelet, whose dimensions will be used to determine the initial state of the planning problem.
        :param align: Choose whether the initial state position should be at the start or at the end of `lanelet`

        :returns: The builder instance
        """
        if self._initial_state is not None:
            raise RuntimeError(
                f"Cannot set start lanelet for planning problem builder {self._planning_problem_id}: Already has a start lanelet set!"
            )

        if align != "start" and align != "end":
            raise ValueError(f"Align must be either 'start' or 'end', but got '{align}'")

        align_start = align == "start"
        self._initial_state = InitialState()
        self._initial_state.fill_with_defaults()
        if align_start:
            self._initial_state.position = lanelet.center_vertices[0]
        else:
            self._initial_state.position = lanelet.center_vertices[-1]
        return self

    def add_goal(self, lanelet: Lanelet, align: Literal["start", "end"] = "end") -> Self:
        if align != "start" and align != "end":
            raise ValueError(f"Align must be either 'start' or 'end', but got '{align}'")

        align_start = align == "start"

        goal_position_center = (
            lanelet.center_vertices[0] if align_start else lanelet.center_vertices[-1]
        )

        # Use a `PMState`, because it is the smallest state that supports positions
        goal_state = PMState(
            # We do not care about the time step, but it is required by the planning problem
            time_step=Interval(start=0.0, end=float("inf")),
            position=Rectangle(length=5.0, width=5.0, center=goal_position_center),
        )

        self._add_goal_state(goal_state, lanelet_id=lanelet.lanelet_id)
        return self

    def build(self) -> PlanningProblem:
        """
        Construct a `PlanningProblem` from the builder configuration.
        """
        if self._initial_state is None:
            raise ValueError(
                f"Cannot build planning problem {self._planning_problem_id}: No initial state!"
            )

        if len(self._goal_states) == 0:
            raise ValueError(
                f"Cannot build planning problem {self._planning_problem_id}: No goal state!"
            )

        goal_region = GoalRegion(self._goal_states, self._goal_states_to_lanelet_ids)
        return PlanningProblem(self._planning_problem_id, self._initial_state, goal_region)


class PlanningProblemSetBuilder(BuilderCore[PlanningProblemSet]):
    """
    The `PlanningProblemSetBuilder` is used to easily construct `PlanningProblemSet`s. It's main benefit comes from the `PlanningProblemBuilder` which can be used to easily build planning problems for this planning problem set.
    """

    def __init__(self, id_allocator: Optional[BuilderIdAllocator] = None) -> None:
        if id_allocator is not None:
            self._id_allocator = id_allocator
        else:
            self._id_allocator = BuilderIdAllocator()

        self._planning_problem_builders: List[PlanningProblemBuilder] = []

    def create_planning_problem(
        self, planning_problem_id: Optional[int] = None
    ) -> PlanningProblemBuilder:
        """
        Create a new `PlanningProblemBuilder` to construct a new `PlanningProblem`.
        If this `PlanningProblemSetBuilder` is built, the new `PlanningProblemBuilder` will also be built.
        """
        planning_problem_id = (
            planning_problem_id if planning_problem_id is not None else self._id_allocator.new_id()
        )
        planning_problem_builder = PlanningProblemBuilder(planning_problem_id)
        self._planning_problem_builders.append(planning_problem_builder)
        return planning_problem_builder

    def build(self) -> PlanningProblemSet:
        """
        Construct a `PlanningProblemSet` from the builder configuration.
        Also builds all attached `PlanningProblemBuilder`s.
        """
        planning_problems = [
            planning_problem_builder.build()
            for planning_problem_builder in self._planning_problem_builders
        ]
        return PlanningProblemSet(planning_problems)
