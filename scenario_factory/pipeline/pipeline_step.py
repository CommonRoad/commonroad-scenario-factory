import functools
import uuid
from dataclasses import dataclass
from enum import Enum, auto
from typing import (
    Callable,
    Generic,
    Optional,
    Protocol,
    Sequence,
    TypeAlias,
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


# Upper Type bound for arguments to pipeline steps
class PipelineStepArguments: ...


# We want to use PipelineStepArguments as a type parameter in Callable, which requires covariant types
_PipelineStepArgumentsTypeT = TypeVar(
    "_PipelineStepArgumentsTypeT", bound=PipelineStepArguments, covariant=True
)
PipelineStepInputTypeT = TypeVar("PipelineStepInputTypeT")
PipelineStepOutputTypeT = TypeVar("PipelineStepOutputTypeT")


# Type aliases to make the function definitions more readable
PipelineMapFuncType: TypeAlias = Callable[
    [PipelineContext, PipelineStepInputTypeT], PipelineStepOutputTypeT
]
_PipelineMapFuncWithArgsType: TypeAlias = Callable[
    [_PipelineStepArgumentsTypeT, PipelineContext, PipelineStepInputTypeT],
    PipelineStepOutputTypeT,
]

PipelineFoldFuncType: TypeAlias = Callable[
    [PipelineContext, Sequence[PipelineStepInputTypeT]],
    Sequence[PipelineStepOutputTypeT],
]


class PipelineFilterPredicate(Protocol):
    def matches(self, *args, **kwargs) -> bool: ...


_PipelineFilterPredicateT = TypeVar("_PipelineFilterPredicateT", bound=PipelineFilterPredicate)

PipelineFilterFuncType: TypeAlias = Callable[[PipelineContext, PipelineStepInputTypeT], bool]
_PipelineFilterFuncWithPredicateType: TypeAlias = Callable[
    [_PipelineFilterPredicateT, PipelineContext, PipelineStepInputTypeT], bool
]


class PipelineStepType(Enum):
    MAP = auto()
    FILTER = auto()
    FOLD = auto()


class PipelineStepExecutionMode(Enum):
    CONCURRENT = auto()
    """Run the step in a semi-parellel manner, by distributing the indidivual tasks to different threads"""

    PARALLEL = auto()
    """Run this step in a true parallel manner, by distributing the individual tasks to different processes"""

    SEQUENTIAL = auto()
    """Run this step sequentially on the main thread"""


_AnyPipelineStep = TypeVar(
    "_AnyPipelineStep",
    PipelineMapFuncType,
    PipelineFilterFuncType,
    PipelineFoldFuncType,
)


class PipelineStep(Generic[_AnyPipelineStep]):
    """
    A `PipelineStep` is a wrapper around the real step function, to add more information about the step like its type or preferred execution mode.
    """

    def __init__(
        self,
        step_func: _AnyPipelineStep,
        type: PipelineStepType,
        mode: PipelineStepExecutionMode = PipelineStepExecutionMode.CONCURRENT,
    ):
        self._step_func: _AnyPipelineStep = step_func
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

    def __call__(self, *args, **kwargs):
        return self._step_func(*args, **kwargs)

    def __hash__(self) -> int:
        # bind the hash dunder to the identifier, so it can be used reliably as dict keys
        return self._id.int

    def __str__(self) -> str:
        return f"{self._name} ({self._id})"


def pipeline_map(
    mode: PipelineStepExecutionMode = PipelineStepExecutionMode.CONCURRENT,
) -> Callable[[PipelineMapFuncType], PipelineStep[PipelineMapFuncType]]:
    """
    Decorate a function to indicate that is used as a map function for the pipeline.
    """

    def decorator(func: PipelineMapFuncType) -> PipelineStep[PipelineMapFuncType]:
        return PipelineStep(step_func=func, type=PipelineStepType.MAP, mode=mode)

    return decorator


def pipeline_map_with_args(
    mode: PipelineStepExecutionMode = PipelineStepExecutionMode.CONCURRENT,
) -> Callable[
    [_PipelineMapFuncWithArgsType],
    Callable[[PipelineStepArguments], PipelineStep[PipelineMapFuncType]],
]:
    """
    Decorate a function to indicate its use as a map function for the pipeline. This decorator will partially apply the function by setting the args parameter.
    """

    def decorator(
        func: _PipelineMapFuncWithArgsType,
    ) -> Callable[[PipelineStepArguments], PipelineStep[PipelineMapFuncType]]:
        def inner_wrapper(
            args: PipelineStepArguments,
        ) -> PipelineStep[PipelineMapFuncType]:
            step_func_with_args_applied = functools.partial(func, args)
            return PipelineStep(
                step_func=step_func_with_args_applied,
                type=PipelineStepType.MAP,
                mode=mode,
            )

        return inner_wrapper

    return decorator


def pipeline_fold(mode: PipelineStepExecutionMode = PipelineStepExecutionMode.SEQUENTIAL):
    def decorator(func: PipelineFoldFuncType) -> PipelineStep[PipelineFoldFuncType]:
        return PipelineStep(step_func=func, type=PipelineStepType.FOLD, mode=mode)

    return decorator


def pipeline_filter(
    mode: PipelineStepExecutionMode = PipelineStepExecutionMode.CONCURRENT,
) -> Callable[
    [_PipelineFilterFuncWithPredicateType],
    Callable[[PipelineFilterPredicate], PipelineStep[PipelineFilterFuncType]],
]:
    """
    Decorate a function to indicate that is used as a filter function for the pipeline.
    """

    def decorator(
        func: _PipelineFilterFuncWithPredicateType,
    ) -> Callable[[PipelineFilterPredicate], PipelineStep[PipelineFilterFuncType]]:
        def inner_wrapper(
            filter: PipelineFilterPredicate,
        ) -> PipelineStep[PipelineFilterFuncType]:
            step_func_with_args_applied = functools.partial(func, filter)
            return PipelineStep(
                step_func=step_func_with_args_applied,
                type=PipelineStepType.FILTER,
                mode=mode,
            )

        return inner_wrapper

    return decorator


@dataclass
class PipelineStepResult(Generic[PipelineStepInputTypeT, PipelineStepOutputTypeT]):
    """
    Result of the successfull or failed execution of a pipeline step.
    """

    step: PipelineStep
    input: PipelineStepInputTypeT
    output: Optional[PipelineStepOutputTypeT]
    error: Optional[str]
    exec_time: int
