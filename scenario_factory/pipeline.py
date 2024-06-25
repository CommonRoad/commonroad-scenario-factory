import functools
import io
import itertools
import logging
import random
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, Iterable, Iterator, List, Optional, TypeAlias, TypeVar

import numpy as np
from multiprocess import Pool

_logger = logging.getLogger("scenario_factory")


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

    def __init__(self, output_path: Path, seed: int = 1):
        self._output_path = output_path

        random.seed(seed)
        np.random.seed(seed)
        self.seed = seed

    def get_output_folder(self, folder_name: str) -> Path:
        """
        Get the path to a folder that is guaranteed to exist.
        """
        output_folder = self._output_path.joinpath(folder_name)
        output_folder.mkdir(parents=True, exist_ok=True)
        return output_folder

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)


# Type aliases to make the function definitions more readable
_PipelineMapType: TypeAlias = Callable[[PipelineContext, _PipelineStepInputType], _PipelineStepOutputType]
_PipelineMapWithArgsType: TypeAlias = Callable[
    [_PipelineStepArgumentsType, PipelineContext, _PipelineStepInputType], _PipelineStepOutputType
]

_PipelinePopulateType: TypeAlias = Callable[[PipelineContext], Iterator[_PipelineStepOutputType]]
_PipelinePopulateWithArgsType: TypeAlias = Callable[
    [_PipelineStepArgumentsType, PipelineContext], Iterator[_PipelineStepOutputType]
]


def pipeline_populate(func: _PipelinePopulateType) -> _PipelinePopulateType:
    """
    Decorate a function to indicate that is used as a populate function for the pipeline.
    """
    return func


def pipeline_populate_with_args(func: _PipelinePopulateWithArgsType):
    """Decorate a function to indicate its use as a populate function for the pipeline. This decorator will partically apply the function by setting the args parameter."""

    def inner_wrapper(
        args: PipelineStepArguments,
    ) -> _PipelinePopulateType:
        return functools.partial(func, args)

    return inner_wrapper


def pipeline_map_with_args(
    func: _PipelineMapWithArgsType,
) -> Callable[[PipelineStepArguments], _PipelineMapType]:
    """
    Decorate a function to indicate its use as a map function for the pipeline. This decorator will partially apply the function by setting the args parameter.
    """

    def inner_wrapper(
        args: PipelineStepArguments,
    ) -> _PipelineMapType:
        return functools.partial(func, args)

    return inner_wrapper


def pipeline_map(func: _PipelineMapType) -> _PipelineMapType:
    """
    Decorate a function to indicate that is used as a map function for the pipeline.
    """
    return func


def _get_function_name(func) -> str:
    if isinstance(func, functools.partial) or isinstance(func, functools.partialmethod):
        return func.func.__name__
    else:
        return func.__name__


def _execute_pipeline_function(
    ctx: PipelineContext,
    func: _PipelineMapType,
    input: _PipelineStepInputType,
) -> PipelineStepResult[_PipelineStepInputType, _PipelineStepOutputType]:
    """
    Helper function to execute a pipeline function on an arbirtary input. Will capture all output and errors.
    """
    stream = io.StringIO()
    value, error = None, None
    with redirect_stdout(stream):
        with redirect_stderr(stream):
            start_time = time.time_ns()
            try:
                value = func(ctx, input)
            except Exception:
                error = traceback.format_exc()
            end_time = time.time_ns()

    result = PipelineStepResult(_get_function_name(func), input, value, error, stream, end_time - start_time)
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

    _state: Iterable

    def __init__(self, ctx: PipelineContext):
        self._ctx = ctx
        self._results: Iterable[PipelineStepResult] = []

        self._populated = False

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
        populate_func: _PipelinePopulateType,
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

        self._state = new_state
        self._populated = True

    @_guard_against_unpopulated
    def map(self, map_func: _PipelineMapType, num_processes: Optional[int] = None):
        """
        Apply map_func individually on every element of the internal state. The results of each map_func invocation are gathered and set as the new internal state of the pipeline.
        """
        _logger.debug(f"Mapping '{_get_function_name(map_func)}' on '{self._state}'")
        if num_processes is None:
            results = map(lambda elem: _execute_pipeline_function(self._ctx, map_func, elem), self._state)
        else:
            pool = Pool(
                processes=num_processes,
            )
            input = [(self._ctx, map_func, stack_elem) for stack_elem in self._state]
            results = pool.starmap(_execute_pipeline_function, input)

        results_iter, state_iter = itertools.tee(results)
        self._results = itertools.chain(self._results, results_iter)
        self._state = map(lambda result: result.output, filter(lambda result: result.output is not None, state_iter))

    @_guard_against_unpopulated
    def reduce(
        self,
        reduce_func: Callable[[PipelineContext, Iterable[_PipelineStepInputType]], Iterable[_PipelineStepOutputType]],
    ):
        """
        Apply reduce_func on the whole internal state and set its result as the new internal state.
        """
        _logger.debug(f"Using '{_get_function_name(reduce_func)}' to reduce '{self._state}'")
        self._state = reduce_func(self._ctx, self._state)

    def report_results(self):
        for result in self.results:
            if result.error is not None:
                print(f"Failed to process '{result.input}' in step '{result.step}' with traceback:")
                print(result.error)

    @property
    def results(self) -> List[PipelineStepResult]:
        if not isinstance(self._results, list):
            self._results = list(self._results)
        return self._results

    @property
    def errors(self) -> List[PipelineStepResult]:
        return [result for result in self.results if result.error is not None]

    @property
    def state(self):
        if not isinstance(self._state, list):
            self._state = list(self._state)
        return self._state


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
