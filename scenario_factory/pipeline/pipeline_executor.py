import builtins
import collections.abc
import logging
import random
import signal
import time
import traceback
import warnings
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from typing import (
    Callable,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
)

import multiprocess
import numpy as np

from scenario_factory.pipeline.pipeline_context import PipelineContext
from scenario_factory.pipeline.pipeline_step import (
    PipelineStep,
    PipelineStepExecutionMode,
    PipelineStepResult,
    PipelineStepType,
)

_LOGGER = logging.getLogger(__name__)


@contextmanager
def _redirect_all_print_calls_to(target: Optional[Callable] = None):
    """
    Patch out the python builtin `print` function so that it becomes a nop.
    """
    backup_print = builtins.print
    if target is None:
        builtins.print = lambda *args, **kwargs: None
    else:
        builtins.print = target
    try:
        yield
    finally:
        builtins.print = backup_print


V = TypeVar("V")
R = TypeVar("R")


def _wrap_pipeline_step(
    ctx: PipelineContext,
    pipeline_step: PipelineStep[V, R],
    input_value: V,
) -> PipelineStepResult[V, R]:
    """
    Helper function to execute a pipeline function on an arbirtary input. Will capture all output and errors.
    """
    value, error = None, None
    with warnings.catch_warnings():
        start_time = time.time_ns()
        try:
            value = pipeline_step(ctx, input_value)
        except Exception:
            error = traceback.format_exc()
        end_time = time.time_ns()

    result = PipelineStepResult(pipeline_step, input_value, value, error, end_time - start_time)
    return result


def _execute_pipeline_step(
    ctx: PipelineContext,
    pipeline_step: PipelineStep[V, R],
    step_index: int,
    input_value: V,
) -> Tuple[int, PipelineStepResult[V, R]]:
    result = _wrap_pipeline_step(ctx, pipeline_step, input_value)
    return step_index + 1, result


def _process_worker_init(seed: int) -> None:
    # Ignore KeyboardInterrupts in the worker processes, so we can orchestrate a clean shutdown.
    # If this is not ignored, all processes will react to the KeyboardInterrupt and spam output to the console.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    random.seed(seed)
    np.random.seed(seed)


class PipelineExecutor:
    """Execute the steps in a pipeline

    :param ctx:
    :param steps: The list of pipeline steps that should be executed. Order dependent.
    :param num_threads: If provided, enables the concurrent execution of pipeline steps on a thread pool with :param:`num_threads` worker threads
    :param num_processes: If provided, enables the parallel execution of pipeline steps on a process pool with :param:`num_processes` worker processes
    """

    def __init__(
        self,
        ctx: PipelineContext,
        steps: List[PipelineStep],
        num_threads: Optional[int] = None,
        num_processes: Optional[int] = None,
    ) -> None:
        self._ctx = ctx
        self._steps = steps

        # Keep track of how many steps are currently being executed in the pipeline.
        # This number is used to determine whether the execution was finished.
        self._num_of_running_pipeline_steps = 0

        self._pipeline_step_results: List[PipelineStepResult] = []

        seed = ctx.get_scenario_factory_config().seed
        random.seed(seed)
        np.random.seed(seed)

        if num_processes is None:
            self._parallism_enabled = False
        else:
            self._process_pool = multiprocess.Pool(
                processes=num_processes,
                initializer=_process_worker_init,
                initargs=(seed,),
            )
            self._parallism_enabled = True

        if num_threads is None:
            self._concurrency_enabled = False
        else:
            self._thread_executor = ThreadPoolExecutor(max_workers=num_threads)
            self._concurrency_enabled = True

        # By default, no tasks may be scheduled on the worker pools
        self._scheduling_enabled = False

        self._reset_fold_state()

    def _is_last_step(self, step_index: int) -> bool:
        return step_index + 1 > len(self._steps)

    def _submit_step_for_execution(self, step: PipelineStep, step_index: int, input_value) -> None:
        if not self._scheduling_enabled:
            return
        self._num_of_running_pipeline_steps += 1

        # To execute a fold step, the executor has to collect all values until the fold step first.
        # This is done by suspending the execution of each specific value,
        # and notifying the executor. The fold operation will then be performed
        # in the main loop on the main thread once all values have been yield.
        if step.type == PipelineStepType.FOLD:
            return self._yield_for_fold(step, step_index, input_value)

        if step.mode == PipelineStepExecutionMode.CONCURRENT and self._concurrency_enabled:
            # Steps that can be executed concurrently, are submitted to the thread pool
            new_f: Future[Tuple[int, PipelineStepResult]] = self._thread_executor.submit(
                _execute_pipeline_step, self._ctx, step, step_index, input_value
            )
            new_f.add_done_callback(self._chain_next_step_from_previous_step_future)
        elif step.mode == PipelineStepExecutionMode.PARALLEL and self._parallism_enabled:
            # Steps that must be executed in parallel, are submitted to the process pool to ensure true parallelism
            self._process_pool.apply_async(
                _execute_pipeline_step,
                (self._ctx, step, step_index, input_value),
                callback=self._chain_next_step_from_previous_step_callback,
            )
        else:
            # Either the step's mode is `PipelineStepMode.SEQUENTIAL` or it is one of
            # the other modes, but the mode is disabled for the executor.
            result: Tuple[int, PipelineStepResult] = _execute_pipeline_step(
                self._ctx, step, step_index, input_value
            )
            self._chain_next_step_from_previous_step_callback(result)

    def _chain_next_step_from_previous_step_callback(
        self, result: Tuple[int, PipelineStepResult]
    ) -> None:
        """
        Create a future from the result of a pipeline step execution and chain the execution of the consecutive pipeline step.
        """
        new_future: Future[Tuple[int, PipelineStepResult]] = Future()
        new_future.set_result(result)
        self._chain_next_step_from_previous_step_future(new_future)

    def _chain_next_step_from_previous_step_future(
        self, future: Future[Tuple[int, PipelineStepResult]]
    ) -> None:
        """
        Handles the result of a pipeline step execution and executes the consecutive pipeline step, if applicable.
        """
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
        # Steps might return None, if the input value could not be processed.
        # If this is the case, the element should not be processed any further.
        if return_value_of_previous_step is None:
            return

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
        Suspend the execution of the fold `step` until all other elements have reached the fold step.
        """
        self._num_of_values_queued_for_fold += 1
        self._values_queued_for_fold.append(input_value)
        if self._fold_step is None:
            # This is the first yield for fold and therefore, we need to mark the relevant step
            self._fold_step = step
            self._fold_step_index = step_index

    def _perform_fold_on_all_queued_values(self):
        """
        After all previous execution strings have reached the fold step, perform the fold.
        """
        if self._fold_step is None or self._fold_step_index is None:
            raise RuntimeError(
                "Tried performing a fold, but the fold step is not set! This is a bug!"
            )

        # The fold counts as one running pipeline step. This is important so that the executor
        # is not shutdown before all values have been processed.
        self._num_of_running_pipeline_steps = 1
        # The fold will be simply executed sequentially on the main thread in the main loop.
        # Although, it could be submitted to the worker pool, there does not seem to be any benefit from doing so
        result = _execute_pipeline_step(
            self._ctx,
            self._fold_step,
            self._fold_step_index,
            self._values_queued_for_fold,
        )

        # Reset the fold state, *before* the next tasks are scheduled.
        # This is done, so that no race-condition is encountered if another fold should be executed right after.
        self._reset_fold_state()

        # Just chain using the standard callback. This might be inefficient,
        # when multiple folds are executed after each other. But normally.
        # folds are rather the exception and so overall this should still be quite efficient.
        self._chain_next_step_from_previous_step_callback(result)

    def _all_steps_ready_for_fold(self) -> bool:
        return self._num_of_running_pipeline_steps == self._num_of_values_queued_for_fold

    def run(self, input_values: Iterable, suppress_print: bool = True):
        # Allow tasks to be scheduled on our worker pools
        self._scheduling_enabled = True
        try:
            # Functions across the CommonRoad ecosystem use debug print statements in
            # the offical released version. When processing large numbers of elements,
            # this results in a ton of unecessary console output. To circumvent this,
            # the whole print function is replaced for the pipeline execution.
            # Generally, all functions should make use of the logging module...
            print_redirection_target = None if suppress_print else print
            with _redirect_all_print_calls_to(print_redirection_target):
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
            if self._concurrency_enabled:
                self._thread_executor.shutdown()
            if self._parallism_enabled:
                self._process_pool.terminate()
                self._process_pool.close()

        return self._pipeline_step_results
