from pathlib import Path
from typing import Iterator

import pytest

from scenario_factory.pipeline.context import (
    EmptyPipelineError,
    Pipeline,
    PipelineContext,
    pipeline_map,
    pipeline_populate,
)
from scenario_factory.pipeline.utils import flatten, keep


class TestPipeline:
    def test_actions_fail_if_not_yet_populated(self):
        ctx = PipelineContext(Path("."))
        pipeline = Pipeline(ctx)

        with pytest.raises(EmptyPipelineError):
            pipeline.map(keep)

        with pytest.raises(EmptyPipelineError):
            pipeline.reduce(keep)

    def test_populate_fails_on_exception(self, capfd):
        ctx = PipelineContext(Path("."))
        pipeline = Pipeline(ctx)

        err_value = "foo\nbar"

        @pipeline_populate
        def populate_error(ctx: PipelineContext) -> Iterator:
            print(err_value, end=None)
            raise Exception("test")

        with pytest.raises(Exception):
            pipeline.populate(populate_error)

        out, _ = capfd.readouterr()
        assert out.strip() == err_value.strip()

    def test_map_updates_internal_state(self):
        ctx = PipelineContext(Path("."))
        pipeline = Pipeline(ctx)

        @pipeline_populate
        def populate_test(ctx: PipelineContext) -> Iterator[int]:
            for i in range(1, 10):
                yield i

        @pipeline_map
        def map_test(ctx: PipelineContext, val: int) -> int:
            return val * 2

        pipeline.populate(populate_test)
        assert len(pipeline.state) > 0
        pipeline.map(map_test)
        assert len(pipeline.state) > 0

    def test_reduce_updates_internal_state(self):
        ctx = PipelineContext(Path("."))
        pipeline = Pipeline(ctx)

        @pipeline_populate
        def populate_test(ctx: PipelineContext) -> Iterator[int]:
            for i in range(1, 10):
                yield i

        @pipeline_map
        def map_blow(ctx: PipelineContext, val: int) -> Iterator[int]:
            for i in range(1, 10):
                yield val * i

        pipeline.populate(populate_test)
        pipeline.map(map_blow)
        pipeline.reduce(flatten)
        assert len(pipeline.state) > 0
