from pathlib import Path
from typing import Iterator

import pytest

from scenario_factory.pipeline.context import EmptyPipelineError, Pipeline, PipelineContext
from scenario_factory.pipeline.utils import keep


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

        def populate_error(ctx: PipelineContext) -> Iterator:
            print(err_value, end=None)
            raise Exception("test")

        with pytest.raises(Exception):
            pipeline.populate(populate_error)

        out, _ = capfd.readouterr()
        assert out.strip() == err_value.strip()
