import functools
import uuid
from dataclasses import dataclass
from enum import Enum, auto
from typing import (
    Callable,
    Concatenate,
    Generic,
    Optional,
    ParamSpec,
    TypeVar,
)

from scenario_factory.pipeline.pipeline_context import PipelineContext


def _get_function_name(func) -> str:
    """
    Get a human readable name of a python function even if it is wrapped in a partial.
    """
    if isinstance(func, functools.partial) or isinstance(func, functools.partialmethod):
        return func.func.__name__
    if hasattr(func, "__name__"):
        return func.__name__
    else:
        return str(func)


class PipelineStepType(Enum):
    MAP = auto()
    """Execute the pipeline step for each individual item in the pipeline."""

    FILTER = auto()
    """Execute the pipeline step for each individual item in the pipeline and decide whtether the item should be further processed."""

    FOLD = auto()
    """Execute the pipeline step for all item at together."""


class PipelineStepExecutionMode(Enum):
    CONCURRENT = auto()
    """Run the step in a semi-parellel manner, by distributing the indidivual tasks to different threads"""

    PARALLEL = auto()
    """Run this step in a true parallel manner, by distributing the individual tasks to different processes"""

    SEQUENTIAL = auto()
    """Run this step sequentially on the main thread"""


P = ParamSpec("P")
V = TypeVar("V")
R = TypeVar("R")


class PipelineStep(Generic[V, R]):
    """
    A `PipelineStep` is a wrapper around the real step function, to add more information about the step like its type or preferred execution mode.
    """

    def __init__(
        self,
        step_func: Callable[Concatenate[PipelineContext, V, P], R],
        step_args: tuple,  # We only know that the args are a tuple, but not the type of each element
        step_kwargs: dict,  # We only know that the kwargs are a dict, but not the type of each key/value
        type: PipelineStepType,
        mode: PipelineStepExecutionMode = PipelineStepExecutionMode.CONCURRENT,
    ):
        self._step_func = step_func
        self._step_args = step_args
        self._step_kwargs = step_kwargs
        # self._step_kwargs = step_kwargs
        self._type = type
        self._mode = mode

        self._name = _get_function_name(self._step_func)
        # The id is used to compare pipeline steps to each other.
        # The name cannot be used for this, because multiple pipeline steps with the same name might be used in one pipeline.
        # Additionally, instance checks also don't work because the step objects might be moved around between different processes, resulting in different instances.
        self._id = uuid.uuid4()

    @property
    def type(self):
        return self._type

    @property
    def mode(self):
        return self._mode

    @property
    def name(self):
        return self._name

    @property
    def identifier(self):
        return self._id

    def __eq__(self, other) -> bool:
        if not isinstance(other, PipelineStep):
            return False

        return self.identifier == other.identifier

    def __call__(self, ctx: PipelineContext, input_value: V) -> R:
        return self._step_func(ctx, input_value, *self._step_args, **self._step_kwargs)

    def __hash__(self) -> int:
        # bind the hash dunder to the identifier, so it can be used reliably as dict keys
        return self._id.int

    def __str__(self) -> str:
        return f"{self._name} ({self._id})"


class PipelineMapStep(PipelineStep[V, R]):
    def __init__(self, step_func, step_args, step_kwargs, mode):
        super().__init__(step_func, step_args, step_kwargs, PipelineStepType.MAP, mode)


class PipelineFoldStep(PipelineStep[V, R]):
    def __init__(self, step_func, step_args, step_kwargs, mode):
        super().__init__(step_func, step_args, step_kwargs, PipelineStepType.FOLD, mode)


class PipelineFilterStep(PipelineStep[V, bool]):
    def __init__(self, step_func, step_args, step_kwargs, mode):
        super().__init__(step_func, step_args, step_kwargs, PipelineStepType.FILTER, mode)


# Defines the decorators that must be used on each function that should become a pipeline step.
# To achieve typing transparency `ParamSpec` is used to annotate optional parameters for each spec.
# For the type annotations to work correctly, the `ParamSpec` must be placed at the end of the
# `Concatenate`. This might lead to unintutitive ergonomics because the optional parameters will
# be provided before the other parameters, when the pipeline step is created, but is necessary:
# ```python
# @pipeline_map()
# def pipeline_foo(ctx: PipelineContext, val: int, arg1: float = 1.0, arg2: float = 0.5) -> float:
#     return val * arg1 + arg2

# pipeline = Pipeline()
# pipeline.map(pipeline_foo(arg1=2.0, arg2=0.0))
# ```


def pipeline_map(mode: PipelineStepExecutionMode = PipelineStepExecutionMode.CONCURRENT):
    """
    Decorate a function with `pipeline_map` to make it usable as a `map` pipeline step.
    """

    def decorator(func: Callable[Concatenate[PipelineContext, V, P], R]):
        # Inner wrapper is required to support passing parameters
        def inner_wrapper(*args: P.args, **kwargs: P.kwargs) -> PipelineMapStep[V, R]:
            return PipelineMapStep(func, args, kwargs, mode)

        return inner_wrapper

    return decorator


def pipeline_filter(mode: PipelineStepExecutionMode = PipelineStepExecutionMode.CONCURRENT):
    """
    Decorate a function with `pipeline_filter` to make it usable as a `filter` pipeline step.
    """

    def decorator(func: Callable[Concatenate[PipelineContext, V, P], bool]):
        # Inner wrapper is required to support passing parameters
        def inner_wrapper(*args: P.args, **kwargs: P.kwargs) -> PipelineFilterStep[V]:
            return PipelineFilterStep(func, args, kwargs, mode)

        return inner_wrapper

    return decorator


def pipeline_fold(mode: PipelineStepExecutionMode = PipelineStepExecutionMode.SEQUENTIAL):
    """
    Decorate a function with `pipeline_fold` to make it usable as a `fold` pipeline step.
    """

    def decorator(func: Callable[Concatenate[PipelineContext, V, P], R]):
        # Inner wrapper is required to support passing parameters
        def inner_wrapper(*args: P.args, **kwargs: P.kwargs) -> PipelineFoldStep[V, R]:
            return PipelineFoldStep(func, args, kwargs, mode)

        return inner_wrapper

    return decorator


@dataclass
class PipelineStepResult(Generic[V, R]):
    """
    Result of the successfull or failed execution of a pipeline step.
    """

    step: PipelineStep[V, R]
    input: V
    output: Optional[R]
    error: Optional[str]
    exec_time: int
