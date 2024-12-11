from pathlib import Path
from typing import Sequence

import pytest

from scenario_factory.pipeline import (
    Pipeline,
    PipelineContext,
    pipeline_filter,
    pipeline_fold,
    pipeline_map,
)


@pipeline_map()
def pipeline_simple_map(ctx: PipelineContext, value: int) -> int:
    return value**2


@pipeline_filter()
def pipeline_simple_filter(ctx: PipelineContext, value: int, filter) -> bool:
    return filter.matches(value)


@pipeline_fold()
def pipeline_simple_fold(ctx: PipelineContext, values: Sequence[int]) -> Sequence[int]:
    return [sum(values)]


class TestPipeline:
    def test_execute_fails_for_empty_pipeline(self):
        pipeline = Pipeline()
        ctx = PipelineContext(Path("."))
        with pytest.raises(RuntimeError):
            pipeline.execute([1, 2, 3, 4, 5], ctx, num_threads=None, num_processes=None)

    def test_correctly_executes_map(self):
        pipeline = Pipeline()
        pipeline.map(pipeline_simple_map)
        ctx = PipelineContext(Path("."))
        input_values = [1, 2, 3, 4, 5]
        result = pipeline.execute(input_values, ctx, num_threads=None, num_processes=None)
        assert len(result.errors) == 0
        assert len(result.values) == 5
        assert result.values != input_values

    def test_correctly_executes_filter(self):
        class IsEvenFilter:
            def matches(self, value: int) -> bool:
                return value % 2 == 0

        pipeline = Pipeline()
        pipeline.filter(pipeline_simple_filter(IsEvenFilter()))

        ctx = PipelineContext(Path("."))
        input_values = [1, 2, 3, 4, 5]
        result = pipeline.execute(input_values, ctx, num_threads=None, num_processes=None)
        assert len(result.errors) == 0
        assert len(result.values) == 2

    def test_correctly_executes_fold(self):
        pipeline = Pipeline()
        pipeline.fold(pipeline_simple_fold)
        ctx = PipelineContext(Path("."))
        result = pipeline.execute([1, 2, 3, 4, 5], ctx, num_threads=None, num_processes=None)
        assert len(result.errors) == 0
        assert len(result.values) == 1
        assert result.values[0] == 15
