__all__ = [
    "Pipeline",
    "PipelineStepArguments",
    "PipelineContext",
    "PipelineStepResult",
    "EmptyPipelineError",
    "pipeline_map",
    "pipeline_map_with_args",
    "pipeline_populate_with_args",
]

import functools
import io
import logging
import time
import traceback
import warnings
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, Iterator, List, Optional, Protocol, Sequence, TypeAlias, TypeVar

from commonroad.scenario.scenario import Scenario
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from multiprocess import Pool

from scenario_factory.scenario_config import ScenarioFactoryConfig

_logger = logging.getLogger("scenario_factory")


def _flatten_iterable(xss: Iterable[Iterable[Any]]) -> Iterable[Any]:
    for xs in xss:
        if not isinstance(xs, Iterable):
            yield xs
        else:
            yield from xs


def _get_function_name(func) -> str:
    """
    Get a human readable name of a python function even if it is wrapped in a partial.
    """
    if isinstance(func, functools.partial) or isinstance(func, functools.partialmethod):
        return func.func.__name__
    else:
        return func.__name__


# Upper Type bound for arguments to pipeline steps
class PipelineStepArguments:
    ...


# We want to use PipelineStepArguments as a type parameter in Callable, which requires covariant types
_PipelineStepArgumentsType = TypeVar("_PipelineStepArgumentsType", bound=PipelineStepArguments, covariant=True)
_PipelineStepInputType = TypeVar("_PipelineStepInputType")
_PipelineStepOutputType = TypeVar("_PipelineStepOutputType")


@dataclass
class PipelineStepResult(Generic[_PipelineStepInputType, _PipelineStepOutputType]):
    """
    Result of the successfull or failed execution of a pipeline step.
    """

    step: str
    input: _PipelineStepInputType
    output: Optional[_PipelineStepOutputType]
    error: Optional[str]
    log: io.StringIO
    exec_time: int


class PipelineContext:
    """The context contains metadata that needs to be passed between the different stages of the scenario factory pipeline"""

    def __init__(
        self,
        base_temp_path: Path,
        scenario_config: Optional[ScenarioFactoryConfig] = None,
        sumo_config: Optional[SumoConfig] = None,
    ):
        self._base_temp_path = base_temp_path

        if scenario_config is None:
            self._scenario_config = ScenarioFactoryConfig()
        else:
            self._scenario_config = scenario_config

        if sumo_config is None:
            self._sumo_config = SumoConfig()
        else:
            self._sumo_config = sumo_config

    def get_temporary_folder(self, folder_name: str) -> Path:
        """
        Get a path to a new temporary directory, that is guaranteed to exist.
        """
        temp_folder = self._base_temp_path.joinpath(folder_name)
        temp_folder.mkdir(parents=True, exist_ok=True)
        return temp_folder

    def get_sumo_config_for_scenario(self, scenario: Scenario) -> SumoConfig:
        """
        Derive a new SumoConfig from the internal base SumoConfig for the given scenario.
        """
        new_sumo_config = deepcopy(self._sumo_config)

        new_sumo_config.scenario_name = str(scenario.scenario_id)
        new_sumo_config.dt = scenario.dt

        return new_sumo_config

    def get_scenario_config(self) -> ScenarioFactoryConfig:
        return self._scenario_config


# Type aliases to make the function definitions more readable
_PipelineMapFuncType: TypeAlias = Callable[[PipelineContext, _PipelineStepInputType], _PipelineStepOutputType]
_PipelineMapFuncWithArgsType: TypeAlias = Callable[
    [_PipelineStepArgumentsType, PipelineContext, _PipelineStepInputType], _PipelineStepOutputType
]

_PipelinePopulateFuncType: TypeAlias = Callable[[PipelineContext], Iterable[_PipelineStepOutputType]]
_PipelinePopulateFuncWithArgsType: TypeAlias = Callable[
    [_PipelineStepArgumentsType, PipelineContext], Iterator[_PipelineStepOutputType]
]


_PipelineFoldFuncType: TypeAlias = Callable[
    [PipelineContext, Sequence[_PipelineStepInputType]], Sequence[_PipelineStepOutputType]
]


class PipelineFilterPredicate(Protocol):
    def matches(self, *args, **kwargs) -> bool:
        ...


_PipelineFilterPredicateType = TypeVar("_PipelineFilterPredicateType", bound=PipelineFilterPredicate)

_PipelineFilterFuncBaseType: TypeAlias = Callable[[PipelineContext, _PipelineStepInputType], bool]
_PipelineFilterFuncType: TypeAlias = Callable[
    [_PipelineFilterPredicateType, PipelineContext, _PipelineStepInputType], bool
]


def pipeline_populate(func: _PipelinePopulateFuncType) -> _PipelinePopulateFuncType:
    """
    Decorate a function to indicate that is used as a populate function for the pipeline.
    """
    return func


def pipeline_populate_with_args(func: _PipelinePopulateFuncWithArgsType):
    """Decorate a function to indicate its use as a populate function for the pipeline. This decorator will partically apply the function by setting the args parameter."""

    def inner_wrapper(
        args: PipelineStepArguments,
    ) -> _PipelinePopulateFuncType:
        # This allows us to write: pipeline.pupulate(example_populate(ExamplePopulateArguments(foo=1))) i.e. partially apply the populate function with the args, while preserving type safety
        return functools.partial(func, args)

    return inner_wrapper


def pipeline_map(func: _PipelineMapFuncType) -> _PipelineMapFuncType:
    """
    Decorate a function to indicate that is used as a map function for the pipeline.
    """
    return func


def pipeline_map_with_args(
    func: _PipelineMapFuncWithArgsType,
) -> Callable[[PipelineStepArguments], _PipelineMapFuncType]:
    """
    Decorate a function to indicate its use as a map function for the pipeline. This decorator will partially apply the function by setting the args parameter.
    """

    def inner_wrapper(
        args: PipelineStepArguments,
    ) -> _PipelineMapFuncType:
        return functools.partial(func, args)

    return inner_wrapper


def pipeline_fold(func: _PipelineFoldFuncType) -> _PipelineFoldFuncType:
    return func


def pipeline_filter(func: _PipelineFilterFuncType) -> Callable[[PipelineFilterPredicate], _PipelineFilterFuncBaseType]:
    """
    Decorate a function to indicate that is used as a filter function for the pipeline.
    """

    def inner_wrapper(
        filter: PipelineFilterPredicate,
    ) -> _PipelineFilterFuncBaseType:
        return functools.partial(func, filter)

    return inner_wrapper


def _execute_pipeline_function(
    ctx: PipelineContext,
    func: Callable[[PipelineContext, _PipelineStepInputType], _PipelineStepOutputType],
    input: _PipelineStepInputType,
) -> PipelineStepResult[_PipelineStepInputType, _PipelineStepOutputType]:
    """
    Helper function to execute a pipeline function on an arbirtary input. Will capture all output and errors.
    """
    stream = io.StringIO()
    value, error = None, None
    with redirect_stdout(stream):
        with redirect_stderr(stream):
            with warnings.catch_warnings():
                start_time = time.time_ns()
                try:
                    value = func(ctx, input)
                except Exception:
                    error = traceback.format_exc()
                end_time = time.time_ns()

    result: PipelineStepResult[_PipelineStepInputType, _PipelineStepOutputType] = PipelineStepResult(
        _get_function_name(func), input, value, error, stream, end_time - start_time
    )
    return result


class EmptyPipelineError(Exception):
    """
    Error that is produced if a function is performed on a pipeline that does not contain any internal state.
    """

    def __init__(self, method: str):
        super().__init__(f"Cannot perform {method} on an empty pipeline!")


class Pipeline:
    """
    Generic pipeline that can apply map or reduce functions on an internal state. This pipeline enables easier orchestration of functions, by centralizing the executing of individual steps and following a functional paradigm.
    """

    _state: Sequence

    def __init__(self, ctx: PipelineContext, num_processes: int = 1):
        self._ctx = ctx
        self._results: List[PipelineStepResult] = []

        self._populated = False

        self._pool = Pool(processes=num_processes)

    @staticmethod
    def _guard_against_unpopulated(guarded_method):
        """
        Only execute the guarded method if the internal state was populated and the _populated flag was set. Otherwise an EmptyPipelineError is raised.
        """

        def wrapper(self, *args, **kwargs):
            if not self._populated:
                raise EmptyPipelineError(_get_function_name(guarded_method))

            guarded_method(self, *args, **kwargs)

        return wrapper

    def populate(
        self,
        populate_func: _PipelinePopulateFuncType,
    ):
        """
        Populates the internal state with the result from the populate_func.
        """
        new_state = None
        stream = io.StringIO()
        try:
            with redirect_stderr(stream):
                with redirect_stdout(stream):
                    new_state = populate_func(self._ctx)
        except Exception as e:
            print(stream.getvalue(), end=None)
            raise e

        if new_state is None:
            print(stream.getvalue())
            raise RuntimeError(
                f"Could not populate pipeline: The populate function {populate_func.__name__} did not produce a value."
            )

        self._state = list(new_state)
        self._populated = True

    @_guard_against_unpopulated
    def map(
        self,
        map_func: _PipelineMapFuncType,
        parallelize: bool = False,
        profile: bool = False,
        auto_flatten: bool = True,
    ) -> None:
        """
        Apply :param:`map_func` individually on every element of the internal state. The results of each map_func invocation are gathered and set as the new internal state of the pipeline.

        :param map_func: The function that will be mapped on the internal pipeline state.
        :param parallelize: Whether the :param:`map_func` should be executed in parallel using the pipelines internal process pool.
        w:param auto_flatten: Whether the new state should be automatically flatten or not.
        """
        _logger.debug(f"Mapping '{_get_function_name(map_func)}' on '{self._state}'")
        results: List[PipelineStepResult[Any, Any]] = []
        if parallelize:
            input = [(self._ctx, map_func, stack_elem) for stack_elem in self._state]
            results = self._pool.starmap(_execute_pipeline_function, input)
        else:
            results = [_execute_pipeline_function(self._ctx, map_func, elem) for elem in self._state]

        self._results.extend(results)
        new_state_possibly_nested = [result.output for result in results if result.output is not None]

        if auto_flatten:
            self._state = list(_flatten_iterable(new_state_possibly_nested))
        else:
            self._state = new_state_possibly_nested

    @_guard_against_unpopulated
    def fold(self, fold_func: _PipelineFoldFuncType) -> None:
        """
        Apply fold_func on the whole internal state and set its result as the new internal state.
        """
        _logger.debug(f"Using '{_get_function_name(fold_func)}' to fold '{self._state}'")
        result = _execute_pipeline_function(self._ctx, fold_func, self._state)
        self._results.append(result)

        if result.output is None:
            raise RuntimeError(f"Method {_get_function_name(fold_func)} failed to to fold pipeline state")
        self._state = result.output

    @_guard_against_unpopulated
    def filter(self, filter_func: _PipelineFilterFuncBaseType) -> None:
        results = [_execute_pipeline_function(self._ctx, filter_func, elem) for elem in self._state]
        self._results.extend(results)
        self._state = [result.input for result in results if result.output]

    def report_results(self):
        cum_time_by_pipeline_step = defaultdict(lambda: 0)
        for result in self.results:
            cum_time_by_pipeline_step[result.step] += result.exec_time
            if result.error is not None:
                print(f"Failed to process '{result.input}' in step '{result.step}' with traceback:")
                print(result.error)

        for pipeline_step, cum_time_ns in cum_time_by_pipeline_step.items():
            print("{:<100} {:>10}s".format(pipeline_step, round(cum_time_ns / 1000000000, 2)))

    @property
    def results(self) -> List[PipelineStepResult]:
        return self._results

    @property
    def errors(self) -> List[PipelineStepResult]:
        return [result for result in self.results if result.error is not None]

    @property
    def state(self):
        return self._state

    @property
    def size(self):
        return len(self._state)
