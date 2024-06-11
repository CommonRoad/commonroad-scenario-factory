import io
from multiprocessing import Pool
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, Iterator, List, Optional, TypeVar


class PipelineStepArguments: ...


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

    # TODO: The handling and passing around of output directories is not ideal and should be replaced by a more sound approach
    def get_output_folder(self, suffix: str) -> Path:
        output_folder = self._output_path.joinpath(suffix)
        output_folder.mkdir(parents=True, exist_ok=True)
        return output_folder


class Pipeline:
    """ """

    _stack: Iterable

    def __init__(self, ctx: PipelineContext):
        self._ctx = ctx
        self._results: List[PipelineStepResult] = []

        self._populated = False

    @staticmethod
    def _guard_against_unpopulated(guarded_method):
        """
        Only execute the guarded method if the internal state was populated and the _populated flag was set. Otherwise a RuntimeError is generated.
        """

        def wrapper(self, *args, **kwargs):
            if not self._populated:
                raise RuntimeError(
                    f"Cannot perform {guarded_method.__name__} on an empty pipeline: pipeline was not yet populated!"
                )

            guarded_method(self, *args, **kwargs)

        return wrapper

    def populate(
        self,
        populate_func: Callable[[PipelineContext, Optional[_PipelineStepArgumentsType]], Iterator[Any]],
        args: Optional[_PipelineStepArgumentsType] = None,
    ):
        """
        Populates the internal state with the result from the populate_func.
        """
        new_stack = None
        stream = io.StringIO()
        try:
            with redirect_stderr(stream):
                with redirect_stdout(stream):
                    new_stack = populate_func(self._ctx, args)
        except Exception as e:
            print(stream.getvalue(), end=None)
            raise e

        if new_stack is None:
            print(stream.getvalue())
            raise RuntimeError(
                f"Could not populate pipeline: The populate function {populate_func.__name__} did not produce a value."
            )

        self._stack = new_stack
        self._populated = True

    @_guard_against_unpopulated
    def map(
        self,
        func: Callable[
            [PipelineContext, _PipelineStepInputType, Optional[_PipelineStepArgumentsType]],
            _PipelineStepOutputType,
        ],
        args: Optional[_PipelineStepArgumentsType] = None,
        num_processes: Optional[int] = None,
    ):
        results = []
        if num_processes is None:
            results = [self._wrap_func(func, stack_elem, args) for stack_elem in self._stack]
        else:
            pool = Pool(
                processes=num_processes,
            )
            input = [(func, stack_elem, args) for stack_elem in self._stack]
            results = pool.starmap(self._wrap_func, input)

        self._results.extend(results)
        self._stack = [result.output for result in results if result.output is not None]

    def _wrap_func(
        self,
        func: Callable[
            [PipelineContext, _PipelineStepInputType, Optional[_PipelineStepArgumentsType]],
            _PipelineStepOutputType,
        ],
        input: _PipelineStepInputType,
        args: Optional[_PipelineStepArgumentsType],
    ) -> PipelineStepResult[_PipelineStepInputType, _PipelineStepOutputType]:
        stream = io.StringIO()
        value, error = None, None
        with redirect_stdout(stream):
            with redirect_stderr(stream):
                start_time = time.time_ns()
                try:
                    value = func(self._ctx, input, args)
                except Exception as e:
                    error = e
                end_time = time.time_ns()

        result = PipelineStepResult(str(func.__name__), input, value, error, stream, end_time - start_time)
        return result

    @_guard_against_unpopulated
    def reduce(
        self,
        reduce_func: Callable[[PipelineContext, Iterable[_PipelineStepInputType]], Iterable[_PipelineStepOutputType]],
    ):
        self._stack = reduce_func(self._ctx, self._stack)

    @_guard_against_unpopulated
    def drain(
        self, drain_func: Callable[[PipelineContext, Iterable[_PipelineStepInputType]], _PipelineStepOutputType]
    ) -> _PipelineStepOutputType:
        self._stack = list(self._stack)
        return drain_func(self._ctx, self._stack)

    def report_results(self):
        for result in self._results:
            if result.error is None:
                continue

            print(f"Error in '{result.step}' while processing '{result.input}'")
            out = result.log.getvalue().strip()
            if len(out) > 0:
                print(out)

            traceback.print_exception(result.error)
