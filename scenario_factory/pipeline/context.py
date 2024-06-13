import io
import logging
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path
from typing import Callable, Generic, Iterable, Iterator, List, Optional, TypeAlias, TypeVar

_logger = logging.getLogger("scenario_factory")


class PipelineStepArguments:
    ...


# We want to use PipelineStepArguments as a type parameter in Callable, which requires covariant types
_PipelineStepArgumentsType = TypeVar("_PipelineStepArgumentsType", bound=PipelineStepArguments, covariant=True)
_PipelineStepInputType = TypeVar("_PipelineStepInputType")
_PipelineStepOutputType = TypeVar("_PipelineStepOutputType")


@dataclass
class PipelineStepResult(Generic[_PipelineStepInputType, _PipelineStepOutputType]):
    step: str
    input: _PipelineStepInputType
    output: Optional[_PipelineStepOutputType]
    error: Optional[Exception]
    log: io.StringIO
    exec_time: int


class PipelineContext:
    """The context contains metadata that needs to be passed between the different stages of the scenario factory pipeline"""

    def __init__(self, output_path: Path):
        self._output_path = output_path

    def get_output_folder(self, folder_name: str) -> Path:
        """
        Get the path to a folder that is guaranteed to exist.
        """
        output_folder = self._output_path.joinpath(folder_name)
        output_folder.mkdir(parents=True, exist_ok=True)
        return output_folder


_PipelineMapType: TypeAlias = Callable[[PipelineContext, _PipelineStepInputType], _PipelineStepOutputType]
_PipelineMapWithArgsType: TypeAlias = Callable[
    [PipelineContext, _PipelineStepArgumentsType, _PipelineStepInputType], _PipelineStepOutputType
]

_PipelinePopulateType: TypeAlias = Callable[[PipelineContext], Iterator[_PipelineStepOutputType]]
_PipelinePopulateWithArgsType: TypeAlias = Callable[
    [PipelineContext, _PipelineStepArgumentsType], Iterator[_PipelineStepOutputType]
]


def pipeline_populate_with_args(func: _PipelinePopulateWithArgsType):
    def inner_wrapper(
        args: PipelineStepArguments,
    ) -> _PipelinePopulateType:
        def inner_pipeline_step(ctx: PipelineContext) -> Iterator[_PipelineStepOutputType]:
            return func(ctx, args)

        return inner_pipeline_step

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
        def inner_pipeline_step(ctx: PipelineContext, input_value: _PipelineStepInputType) -> _PipelineStepOutputType:
            return func(ctx, args, input_value)

        # Make sure that we can report the correct name of the function and do not report 'inner_pipeline_step' as the function name
        inner_pipeline_step.__name__ = func.__name__
        return inner_pipeline_step

    return inner_wrapper


def pipeline_map(func: _PipelineMapType) -> _PipelineMapType:
    """
    Decorate a function to indicate that is used as a map function for the pipeline.
    """
    return func


def _execute_pipeline_function(
    ctx: PipelineContext,
    func: _PipelineMapType,
    input: _PipelineStepInputType,
) -> PipelineStepResult[_PipelineStepInputType, _PipelineStepOutputType]:
    stream = io.StringIO()
    value, error = None, None
    with redirect_stdout(stream):
        with redirect_stderr(stream):
            start_time = time.time_ns()
            try:
                value = func(ctx, input)
            except Exception as e:
                error = e
            end_time = time.time_ns()

    result = PipelineStepResult(func.__name__, input, value, error, stream, end_time - start_time)
    return result


class EmptyPipelineError(Exception):
    def __init__(self, method: str):
        super().__init__(f"Cannot perform {method} on an empty pipeline!")


class Pipeline:
    """
    Generic pipeline that can apply map or reduce functions on an internal state. This pipeline enables easier orchestration of functions, by centralizing the executing of individual steps and following a functional paradigm.
    """

    _state: List

    def __init__(self, ctx: PipelineContext):
        self._ctx = ctx
        self._results: List[PipelineStepResult] = []

        self._populated = False

    @staticmethod
    def _guard_against_unpopulated(guarded_method):
        """
        Only execute the guarded method if the internal state was populated and the _populated flag was set. Otherwise an EmptyPipelineError is raised.
        """

        def wrapper(self, *args, **kwargs):
            if not self._populated or len(self._state) == 0:
                raise EmptyPipelineError(guarded_method.__name__)

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

        self._state = list(new_state)
        self._populated = True

    @_guard_against_unpopulated
    def map(
        self,
        map_func: _PipelineMapType,
        num_processes: Optional[int] = None,
    ):
        """
        Apply map_func individually on every element of the internal state. The results of each map_func invocation are gathered and set as the new internal state of the pipeline.
        """
        _logger.debug(f"Mapping '{map_func.__name__}' on '{self._state}'")
        if num_processes is None:
            results = [_execute_pipeline_function(self._ctx, map_func, stack_elem) for stack_elem in self._state]
        else:
            pool = Pool(
                processes=num_processes,
            )
            input = [(self._ctx, map_func, stack_elem) for stack_elem in self._state]
            results = pool.starmap(_execute_pipeline_function, input)

        self._results.extend(results)
        # Only collect non None values
        self._state = [result.output for result in results if result.output is not None]

    @_guard_against_unpopulated
    def reduce(
        self,
        reduce_func: Callable[[PipelineContext, Iterable[_PipelineStepInputType]], Iterable[_PipelineStepOutputType]],
    ):
        """
        Apply reduce_func on the whole internal state and set its result as the new internal state.
        """
        _logger.debug(f"Using '{reduce_func.__name__}' to reduce '{self._state}'")
        self._state = list(reduce_func(self._ctx, self._state))

    def report_results(self):
        for result in self._results:
            if result.error is not None:
                print(f"Failed to process '{result.input}' in step '{result.step}' with error {type(result.error)}:")
                traceback.print_exception(result.error)

    @property
    def errors(self):
        return [result for result in self._results if result.error is not None]

    @property
    def state(self):
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
