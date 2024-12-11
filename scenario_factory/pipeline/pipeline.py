import time
from collections import defaultdict
from dataclasses import dataclass
from typing import (
    Callable,
    Iterable,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

import multiprocess
from typing_extensions import Self

from scenario_factory.pipeline.pipeline_context import PipelineContext
from scenario_factory.pipeline.pipeline_executor import PipelineExecutor
from scenario_factory.pipeline.pipeline_step import (
    PipelineFilterStep,
    PipelineFoldStep,
    PipelineMapStep,
    PipelineStep,
    PipelineStepResult,
    PipelineStepType,
)


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
                    pipeline_step,
                    round(cum_time_ns / 1000000000, 2),
                    cum_elements_by_pipeline_step[pipeline_step],
                )
            )


V = TypeVar("V")
R = TypeVar("R")


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
        map_step: Union[PipelineMapStep, Callable[[], PipelineMapStep]],
    ) -> Self:
        """
        Insert a map step.
        """
        if not isinstance(map_step, PipelineMapStep):
            map_step = map_step()
        self._steps.append(map_step)
        return self

    def fold(self, fold_step: Union[PipelineFoldStep, Callable[[], PipelineFoldStep]]) -> Self:
        """
        Insert a fold step.
        """
        if not isinstance(fold_step, PipelineFoldStep):
            fold_step = fold_step()
        self._steps.append(fold_step)
        return self

    def filter(
        self,
        filter_step: Union[PipelineFilterStep, Callable[[], PipelineFilterStep]],
    ) -> Self:
        """
        Insert a filter step.
        """
        if not isinstance(filter_step, PipelineFilterStep):
            filter_step = filter_step()
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
            return [result.output for result in final_step_results if result.output is not None]
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
        self,
        input_values: Iterable,
        ctx: Optional[PipelineContext] = None,
        num_threads: Optional[int] = multiprocess.cpu_count(),
        num_processes: Optional[int] = multiprocess.cpu_count(),
        debug: bool = False,
    ) -> PipelineExecutionResult:
        """
        Execute the pipeline on the :param:`input_values` with :param:`ctx`.

        :param input_values: An iterable containing the input values for the first step in the pipeline
        :param ctx: The pipeline context for this specific execution. If None is provided, an empty one will be created.
        :param num_threads: Configure the number of threads in the worker pool. If None is provided, multithreading will be disabled.
        :param num_processes: Configure the number of processes in the worker pool. If None is provided, multiprocessing will be disabled.
        :param debug: Enable debug mode. This will disable any concurrency enabled by `num_threads` or `num_processes`, enable prints and run all code on the main thread. You need to enable this option, if you want to use a debugger.

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

        if num_threads is not None and num_threads < 1:
            raise ValueError("Number of threads for pipeline execution must be at least 1")

        if num_processes is not None and num_processes < 1:
            raise ValueError("Number of processes for pipeline execution must be at least 1")

        if debug:
            num_threads = None
            num_processes = None

        if ctx is None:
            ctx = PipelineContext()

        start_time = time.time_ns()

        executor = PipelineExecutor(ctx, self._steps, num_threads, num_processes)
        results = executor.run(input_values, suppress_print=not debug)

        end_time = time.time_ns()

        final_values = self._get_final_values_from_results(results)

        result = PipelineExecutionResult(
            values=final_values, results=results, exec_time_ns=end_time - start_time
        )

        return result
