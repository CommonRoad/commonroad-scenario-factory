__all__ = [
    "Pipeline",
    "PipelineStepArguments",
    "PipelineContext",
    "PipelineStepResult",
    "PipelineStepType",
    "PipelineStepMode",
    "pipeline_map",
    "pipeline_map_with_args",
    "pipeline_filter",
    "pipeline_fold",
    "PipelineExecutionResult",
]

import builtins
import collections.abc
import functools
import logging
import random
import signal
import time
import traceback
import warnings
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Generic, Iterable, List, Optional, Protocol, Sequence, Tuple, TypeAlias, TypeVar

import numpy as np
from commonroad.scenario.scenario import Scenario
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from multiprocess import Pool

from scenario_factory.scenario_config import ScenarioFactoryConfig

_LOGGER = logging.getLogger(__name__)


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


@contextmanager
def _suppress_all_calls_to_print():
    """
    Patch out the python builtin `print` function so that it becomes a nop.
    """
    backup_print = builtins.print
    builtins.print = lambda *args, **kwargs: None
    try:
        yield
    finally:
        builtins.print = backup_print


# Upper Type bound for arguments to pipeline steps
class PipelineStepArguments:
    ...


# We want to use PipelineStepArguments as a type parameter in Callable, which requires covariant types
_PipelineStepArgumentsTypeT = TypeVar("_PipelineStepArgumentsTypeT", bound=PipelineStepArguments, covariant=True)
_PipelineStepInputTypeT = TypeVar("_PipelineStepInputTypeT")
_PipelineStepOutputTypeT = TypeVar("_PipelineStepOutputTypeT")


class PipelineContext:
    """The context contains metadata that needs to be passed between the different stages of the scenario factory pipeline"""

    def __init__(
        self,
        base_temp_path: Path,
        scenario_factory_config: Optional[ScenarioFactoryConfig] = None,
    ):
        self._base_temp_path = base_temp_path

        if scenario_factory_config is None:
            self._scenario_factory_config = ScenarioFactoryConfig()
        else:
            self._scenario_factory_config = scenario_factory_config

    def get_temporary_folder(self, folder_name: str) -> Path:
        """
        Get a path to a new temporary directory, that is guaranteed to exist.
        """
        temp_folder = self._base_temp_path.joinpath(folder_name)
        temp_folder.mkdir(parents=True, exist_ok=True)
        return temp_folder

    # TODO: This represents are tight coupling of the pipeline with SUMO, which should be removed in the future.
    def get_sumo_config_for_scenario(self, scenario: Scenario) -> SumoConfig:
        """
        Derive a new SumoConfig from the internal base SumoConfig for the given scenario.
        """
        new_sumo_config = SumoConfig()

        new_sumo_config.random_seed = self._scenario_factory_config.seed
        new_sumo_config.random_seed_trip_generation = self._scenario_factory_config.seed
        new_sumo_config.simulation_steps = self._scenario_factory_config.simulation_steps
        new_sumo_config.scenario_name = str(scenario.scenario_id)
        new_sumo_config.dt = scenario.dt

        return new_sumo_config

    def get_scenario_factory_config(self) -> ScenarioFactoryConfig:
        return self._scenario_factory_config


# Type aliases to make the function definitions more readable
_PipelineMapFuncType: TypeAlias = Callable[[PipelineContext, _PipelineStepInputTypeT], _PipelineStepOutputTypeT]
_PipelineMapFuncWithArgsType: TypeAlias = Callable[
    [_PipelineStepArgumentsTypeT, PipelineContext, _PipelineStepInputTypeT], _PipelineStepOutputTypeT
]

_PipelineFoldFuncType: TypeAlias = Callable[
    [PipelineContext, Sequence[_PipelineStepInputTypeT]], Sequence[_PipelineStepOutputTypeT]
]


class PipelineFilterPredicate(Protocol):
    def matches(self, *args, **kwargs) -> bool:
        ...


_PipelineFilterPredicateT = TypeVar("_PipelineFilterPredicateT", bound=PipelineFilterPredicate)

_PipelineFilterFuncType: TypeAlias = Callable[[PipelineContext, _PipelineStepInputTypeT], bool]
_PipelineFilterFuncWithPredicateType: TypeAlias = Callable[
    [_PipelineFilterPredicateT, PipelineContext, _PipelineStepInputTypeT], bool
]


class PipelineStepType(Enum):
    MAP = auto()
    FILTER = auto()
    FOLD = auto()


class PipelineStepMode(Enum):
    CONCURRENT = auto()
    PARALLEL = auto()
    SEQUENTIAL = auto()


_AnyPipelineStep = TypeVar("_AnyPipelineStep", _PipelineMapFuncType, _PipelineFilterFuncType, _PipelineFoldFuncType)


@dataclass
class PipelineStep(Generic[_AnyPipelineStep]):
    step_func: _AnyPipelineStep
    type: PipelineStepType
    mode: PipelineStepMode = PipelineStepMode.CONCURRENT

    @property
    def name(self):
        return _get_function_name(self.step_func)

    def __call__(self, *args, **kwargs):
        return self.step_func(*args, **kwargs)

    def __hash__(self) -> int:
        return hash(self.name)


def pipeline_map(
    mode: PipelineStepMode = PipelineStepMode.CONCURRENT,
) -> Callable[[_PipelineMapFuncType], PipelineStep[_PipelineMapFuncType]]:
    """
    Decorate a function to indicate that is used as a map function for the pipeline.
    """

    def decorator(func: _PipelineMapFuncType) -> PipelineStep[_PipelineMapFuncType]:
        return PipelineStep(step_func=func, type=PipelineStepType.MAP, mode=mode)

    return decorator


def pipeline_map_with_args(
    mode: PipelineStepMode = PipelineStepMode.CONCURRENT,
) -> Callable[[_PipelineMapFuncWithArgsType], Callable[[PipelineStepArguments], PipelineStep[_PipelineMapFuncType]]]:
    """
    Decorate a function to indicate its use as a map function for the pipeline. This decorator will partially apply the function by setting the args parameter.
    """

    def decorator(
        func: _PipelineMapFuncWithArgsType,
    ) -> Callable[[PipelineStepArguments], PipelineStep[_PipelineMapFuncType]]:
        def inner_wrapper(
            args: PipelineStepArguments,
        ) -> PipelineStep[_PipelineMapFuncType]:
            step_func_with_args_applied = functools.partial(func, args)
            return PipelineStep(step_func=step_func_with_args_applied, type=PipelineStepType.MAP, mode=mode)

        return inner_wrapper

    return decorator


def pipeline_fold(mode: PipelineStepMode = PipelineStepMode.SEQUENTIAL):
    def decorator(func: _PipelineFoldFuncType) -> PipelineStep[_PipelineFoldFuncType]:
        return PipelineStep(step_func=func, type=PipelineStepType.FOLD, mode=mode)

    return decorator


def pipeline_filter(
    mode: PipelineStepMode = PipelineStepMode.CONCURRENT,
) -> Callable[
    [_PipelineFilterFuncWithPredicateType],
    Callable[[PipelineFilterPredicate], PipelineStep[_PipelineFilterFuncType]],
]:
    """
    Decorate a function to indicate that is used as a filter function for the pipeline.
    """

    def decorator(
        func: _PipelineFilterFuncWithPredicateType,
    ) -> Callable[[PipelineFilterPredicate], PipelineStep[_PipelineFilterFuncType]]:
        def inner_wrapper(
            filter: PipelineFilterPredicate,
        ) -> PipelineStep[_PipelineFilterFuncType]:
            step_func_with_args_applied = functools.partial(func, filter)
            return PipelineStep(step_func=step_func_with_args_applied, type=PipelineStepType.FILTER, mode=mode)

        return inner_wrapper

    return decorator


@dataclass
class PipelineStepResult(Generic[_PipelineStepInputTypeT, _PipelineStepOutputTypeT]):
    """
    Result of the successfull or failed execution of a pipeline step.
    """

    step: PipelineStep
    input: _PipelineStepInputTypeT
    output: Optional[_PipelineStepOutputTypeT]
    error: Optional[str]
    exec_time: int


def _wrap_pipeline_step(
    ctx: PipelineContext,
    pipeline_step: PipelineStep,
    input: _PipelineStepInputTypeT,
) -> PipelineStepResult[_PipelineStepInputTypeT, _PipelineStepOutputTypeT]:
    """
    Helper function to execute a pipeline function on an arbirtary input. Will capture all output and errors.
    """
    value, error = None, None
    with warnings.catch_warnings():
        start_time = time.time_ns()
        try:
            value = pipeline_step(ctx, input)
        except Exception:
            error = traceback.format_exc()
        end_time = time.time_ns()

    result: PipelineStepResult[_PipelineStepInputTypeT, _PipelineStepOutputTypeT] = PipelineStepResult(
        pipeline_step, input, value, error, end_time - start_time
    )
    return result


def _execute_pipeline_step(
    ctx: PipelineContext, pipeline_step, step_index: int, input_value: _PipelineStepInputTypeT
) -> Tuple[int, PipelineStepResult[_PipelineStepInputTypeT, _PipelineStepOutputTypeT]]:
    result: PipelineStepResult[_PipelineStepInputTypeT, _PipelineStepOutputTypeT] = _wrap_pipeline_step(
        ctx, pipeline_step, input_value
    )
    return step_index + 1, result


def _process_worker_init(seed: int) -> None:
    # Ignore KeyboardInterrupts in the worker processes, so we can orchestrate a clean shutdown.
    # If this is not ignored, all processes will react to the KeyboardInterrupt and spam output to the console.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    random.seed(seed)
    np.random.seed(seed)


class PipelineExecutor:
    def __init__(self, ctx: PipelineContext, steps: List[PipelineStep], num_threads: int, num_processes: int):
        self._ctx = ctx
        self._steps = steps

        self._num_of_running_pipeline_steps = 0

        self._pipeline_step_results: List[PipelineStepResult] = []

        seed = ctx.get_scenario_factory_config().seed

        self._process_pool = Pool(processes=num_processes, initializer=_process_worker_init, initargs=(seed,))
        self._thread_executor = ThreadPoolExecutor(max_workers=num_threads)
        # By default, no tasks may be scheduled on the worker pools
        self._scheduling_enabled = False

        self._reset_fold_state()

    def _is_last_step(self, step_index: int) -> bool:
        return step_index + 1 > len(self._steps)

    def _submit_step_for_execution(self, step: PipelineStep, step_index: int, input_value) -> None:
        if not self._scheduling_enabled:
            return
        self._num_of_running_pipeline_steps += 1
        if step.type == PipelineStepType.FOLD:
            return self._yield_for_fold(step, step_index, input_value)

        if step.mode == PipelineStepMode.CONCURRENT:
            new_f: Future[Tuple[int, PipelineStepResult]] = self._thread_executor.submit(
                _execute_pipeline_step, self._ctx, step, step_index, input_value
            )
            new_f.add_done_callback(self._chain_next_step_from_previous_step_future)
        elif step.mode == PipelineStepMode.PARALLEL:
            self._process_pool.apply_async(
                _execute_pipeline_step,
                (self._ctx, step, step_index, input_value),
                callback=self._chain_next_step_from_previous_step_callback,
            )
        else:
            raise NotImplementedError()

    def _chain_next_step_from_previous_step_callback(self, result: Tuple[int, PipelineStepResult]):
        new_future: Future[Tuple[int, PipelineStepResult]] = Future()
        new_future.set_result(result)
        self._chain_next_step_from_previous_step_future(new_future)

    def _chain_next_step_from_previous_step_future(self, future: Future[Tuple[int, PipelineStepResult]]) -> None:
        # If this method is called, this means that a previous task has finished executing
        self._num_of_running_pipeline_steps -= 1

        current_step_index, result_of_previous_step = future.result()
        # Always record the result object, so that we can extract statistics later
        self._pipeline_step_results.append(result_of_previous_step)

        if result_of_previous_step.error is not None:
            logging.error(
                "Encountered an error in step %s while processing %s: %s",
                result_of_previous_step.step.name,
                result_of_previous_step.input,
                result_of_previous_step.error,
            )
            # If the previous step encountered an error, the element should not be processed any further
            return

        if self._is_last_step(current_step_index):
            # If the previous step was the last step in the pipeline, no next
            # steps need to be executed. Therefore, we can simply finish here.
            return

        return_value_of_previous_step = result_of_previous_step.output
        # Filter pipeline steps are special, because they do not return the input value
        # that is needed for the next step. Instead they return a bool.
        # So, we must first get the 'real' input value for the next step,
        # which is the input value for the filter step.
        if result_of_previous_step.step.type == PipelineStepType.FILTER:
            if not return_value_of_previous_step:
                # If the filter function returned False for the input value
                # it should be discarded. This is done by not scheduling any more tasks
                # for this element.
                return
            # If the filter function returned True, replace the return value with the input value of this step
            return_value_of_previous_step = result_of_previous_step.input

        step = self._steps[current_step_index]

        if isinstance(return_value_of_previous_step, collections.abc.Iterable):
            # Pipeline steps might return lists as values, which get transparently flattened
            for input_value in return_value_of_previous_step:
                self._submit_step_for_execution(step, current_step_index, input_value)
        else:
            self._submit_step_for_execution(step, current_step_index, return_value_of_previous_step)

    def _reset_fold_state(self):
        self._num_of_values_queued_for_fold = 0
        self._values_queued_for_fold = []
        self._fold_step = None
        self._fold_step_index = None

    def _yield_for_fold(self, step: PipelineStep, step_index: int, input_value) -> None:
        """
        Suspend the execution of the fold :param:`step` until all other elements have reached the fold step.
        """
        self._num_of_values_queued_for_fold += 1
        self._values_queued_for_fold.append(input_value)
        if self._fold_step is None:
            self._fold_step = step
            self._fold_step_index = step_index

    def _perform_fold_on_all_queued_values(self):
        if self._fold_step is None or self._fold_step_index is None:
            raise RuntimeError("Tried performing a fold, but the fold step is not set! This is a bug!")

        # The fold counts as one running pipeline step. This is important so that the executor
        # is not shutdown before all values have been processed.
        self._num_of_running_pipeline_steps = 1
        # The fold will be simply executed sequentially on the main thread in the main loop.
        # Although, it could be submitted to the worker pool, there does not seem to be any benefit from doing so
        result = _execute_pipeline_step(self._ctx, self._fold_step, self._fold_step_index, self._values_queued_for_fold)

        # Reset the fold state, *before* the next tasks are scheduled.
        # This is done, so that no race-condition is encountered if the
        self._reset_fold_state()

        # Just chain using the standard callback. This might be inefficient,
        # when multiple folds are executed after each other. But normally.
        # folds are rather the exception and so overall this should still be quite efficient.
        self._chain_next_step_from_previous_step_callback(result)

    def _all_steps_ready_for_fold(self) -> bool:
        return self._num_of_running_pipeline_steps == self._num_of_values_queued_for_fold

    def run(self, input_values: Iterable):
        # Allow tasks to be scheduled on our worker pools
        self._scheduling_enabled = True
        try:
            # Functions across the CommonRoad ecosystem use debug print statements in
            # the offical released version. When processing large numbers of elements,
            # this results in a ton of unecessary console output. To circumvent this,
            # the whole print function is replaced for the pipeline execution.
            # Generally, all functions should make use of the logging module...
            with _suppress_all_calls_to_print():
                for elem in input_values:
                    self._submit_step_for_execution(self._steps[0], 0, elem)

                while self._num_of_running_pipeline_steps > 0:
                    if self._all_steps_ready_for_fold():
                        self._perform_fold_on_all_queued_values()
                    time.sleep(1)
        except KeyboardInterrupt:
            _LOGGER.info("Received shutdown signal, terminating all remaining tasks...")
        finally:
            # make sure that no new tasks will be scheduled during shutdown
            self._scheduling_enabled = False
            self._thread_executor.shutdown()
            self._process_pool.terminate()

        return self._pipeline_step_results


@dataclass
class PipelineExecutionResult:
    values: Sequence
    results: Sequence[PipelineStepResult]
    exec_time_ns: int

    @property
    def errors(self):
        return [result for result in self.results if result.error is not None]

    def print_cum_time_per_step(self):
        cum_time_by_pipeline_step = defaultdict(lambda: 0)
        for result in self.results:
            cum_time_by_pipeline_step[result.step.name] += result.exec_time

        cum_elements_by_pipeline_step = defaultdict(lambda: 0)
        for result in self.results:
            cum_elements_by_pipeline_step[result.step.name] += 1

        fmt_str = "{:<100} {:>10} {:>10}"
        fmt_str.format("Pipeline Step", "Total Execution Time (s)", "Num.")
        for pipeline_step, cum_time_ns in cum_time_by_pipeline_step.items():
            print(
                fmt_str.format(
                    pipeline_step, round(cum_time_ns / 1000000000, 2), cum_elements_by_pipeline_step[pipeline_step]
                )
            )


class Pipeline:
    """
    A pipeline defines the sequential execution of map, filter and fold steps.
    """

    def __init__(self, steps: Optional[List[PipelineStep]] = None):
        if steps is None:
            self._steps: List[PipelineStep] = []
        else:
            self._steps = steps

    def map(
        self,
        map_step: PipelineStep[_PipelineMapFuncType],
    ) -> "Pipeline":
        """
        Insert a map step.
        """
        self._steps.append(map_step)
        return self

    def fold(self, fold_step: PipelineStep[_PipelineFoldFuncType]) -> "Pipeline":
        """
        Insert a fold step.
        """
        self._steps.append(fold_step)
        return self

    def filter(
        self,
        filter_step: PipelineStep[_PipelineFilterFuncType],
    ) -> "Pipeline":
        """
        Insert a filter step.
        """
        self._steps.append(filter_step)
        return self

    def chain(self, other: "Pipeline") -> "Pipeline":
        """
        Create a new pipeline by appending all steps from :param:`other` to the steps of this pipeline.
        """
        new_pipeline = Pipeline(self._steps + other._steps)
        return new_pipeline

    def _get_final_values_from_results(self, results: Iterable[PipelineStepResult]) -> Sequence:
        """
        Get the output values of a pipeline execution.
        """
        final_step = self._steps[-1]
        final_step_results = [result for result in results if result.step == final_step]
        if len(final_step_results) == 0:
            # empty final_step_results are valid, e.g. if the the pre-final step is a filter and
            # it filtered out all values. Then the final step will never be called, and therefore
            # the final_step_results will also be empty
            return []

        if final_step.type == PipelineStepType.MAP:
            # If the last step is no filter, the final values are simply the output values of the last step
            return [result.output for result in final_step_results]
        elif final_step.type == PipelineStepType.FILTER:
            # If the last step is a filter step, than its outputs are boolean values, while the final values are the inputs for the filter step
            return [result.input for result in final_step_results if result.output is True]
        elif self._steps[-1].type == PipelineStepType.FOLD:
            # If the last step was a fold, its output represents the whole new state of the pipeline. Therefore, the final values are simply its output
            if len(final_step_results) != 1:
                raise RuntimeError(
                    f"Multiple results ({len(final_step_results)} for final fold step {final_step} exist! This is a Bug!"
                )

            return final_step_results[0].output  # type: ignore
        else:
            raise NotImplementedError()

    def is_valid(self) -> bool:
        return len(self._steps) == len(set(self._steps))

    def execute(
        self, input_values: Iterable, ctx: PipelineContext, num_threads: int = 4, num_processes: int = 4
    ) -> PipelineExecutionResult:
        """
        Execute the pipeline on the :param:`input_values` with :param:`ctx`.

        :param input_values: An iterable containing the input values for the first step in the pipeline
        :param ctx: The pipeline context for this specific execution
        :param num_threads: Configure the number of threads in the worker pool
        :param num_processes: Configure the number of processes in the worker pool

        :returns: The result of the execution
        """
        if len(self._steps) < 1:
            raise RuntimeError(
                f"Cannot execute pipeline: pipeline has {len(self._steps)} steps, but at least 1 step is required."
            )

        if len(self._steps) > len(set(self._steps)):
            raise RuntimeError(
                "Cannot execute pipeline: pipeline has duplicated steps! Each pipeline step might only occur once in a single pipeline!"
            )

        if num_threads < 1:
            raise ValueError("Number of threads for pipeline execution must be at least 1")

        if num_processes < 1:
            raise ValueError("Number of processes for pipeline execution must be at least 1")

        start_time = time.time_ns()

        executor = PipelineExecutor(ctx, self._steps, num_threads, num_processes)
        results = executor.run(input_values)

        end_time = time.time_ns()

        final_values = self._get_final_values_from_results(results)

        result = PipelineExecutionResult(values=final_values, results=results, exec_time_ns=end_time - start_time)

        return result
