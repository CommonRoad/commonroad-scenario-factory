from typing import List, Literal, Optional, Tuple

from commonroad.common.util import Interval
from commonroad.geometry.shape import Rectangle
from commonroad.planning.goal import GoalRegion
from commonroad.planning.planning_problem import PlanningProblem, PlanningProblemSet
from commonroad.scenario.scenario import Lanelet
from commonroad.scenario.state import InitialState, PMState, TraceState

from scenario_factory.builder.core import BuilderCore, BuilderIdAllocator


class PlanningProblemBuilder(BuilderCore[PlanningProblem]):
    """
    The `PlanningProblemBuilder` is used to easily construct simple `PlanningProblem`s. Its main benefit is, that one can simply define a start and multiple goal lanelets, and the initial state and goal region will be automatically infered from this.

    :param planning_problem_id: The unique CommonRoad ID that will be assigned to the resulting planning problem.
    """

    def __init__(self, planning_problem_id: int) -> None:
        self._planning_problem_id = planning_problem_id

        self._initial_state: Optional[InitialState] = None

        # Store each goal state with its according goal lanelet.
        # Note: A goal region could map one goal state to multiple lanelets. This is currently not supported.
        self._goal_tuples: List[Tuple[TraceState, Lanelet]] = []

    def set_start(
        self, lanelet: Lanelet, align: Literal["start", "end"] = "start"
    ) -> "PlanningProblemBuilder":
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

    def add_goal(
        self, lanelet: Lanelet, align: Literal["start", "end"] = "end"
    ) -> "PlanningProblemBuilder":
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

        self._goal_tuples.append((goal_state, lanelet))
        return self

    def build(self) -> PlanningProblem:
        """
        Construct a `PlanningProblem` from the builder configuration.
        """
        if self._initial_state is None:
            raise ValueError(
                f"Cannot build planning problem {self._planning_problem_id}: No initial state!"
            )

        if len(self._goal_tuples) == 0:
            raise ValueError(
                f"Cannot build planning problem {self._planning_problem_id}: No goal state!"
            )

        goal_states = [goal_tuple[0] for goal_tuple in self._goal_tuples]
        # Although goal lanelets could theoretically be a multiple lanelets, we assume only one here
        goal_lanelets = {
            idx: [goal_tuple[1].lanelet_id] for idx, goal_tuple in enumerate(self._goal_tuples)
        }
        goal_region = GoalRegion(goal_states, goal_lanelets)
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

    def create_planning_problem(self) -> PlanningProblemBuilder:
        """
        Create a new `PlanningProblemBuilder` to construct a new `PlanningProblem`.
        If this `PlanningProblemSetBuilder` is built, the new `PlanningProblemBuilder` will also be built.
        """
        planning_problem_builder = PlanningProblemBuilder(self._id_allocator.new_id())
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
