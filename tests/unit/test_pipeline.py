from pathlib import Path

from scenario_factory.pipeline import Pipeline, PipelineContext
from tests.helpers import (
    IsEvenFilter,
    pipeline_simple_filter,
    pipeline_simple_fold,
    pipeline_simple_map,
)


class TestPipeline:
    def test_repeated_execution_with_same_context_fails(self):
        inputs = list(range(10))

        pipeline = (
            Pipeline()
            .map(pipeline_simple_map)
            .filter(pipeline_simple_filter(IsEvenFilter()))
            .fold(pipeline_simple_fold)
        )

        context = PipelineContext(Path("."))
        pipeline.execute(inputs, context, None, None)

        # Want a second execution on the same context to throw.
        try:
            pipeline.execute(inputs, context, None, None)
        except RuntimeError:
            pass
        else:
            assert False, "Expected runtime error and failure of execution."

    def test_repeated_execution_with_new_context(self):
        inputs = list(range(10))
        exp_out = sum(map(lambda x: (x if x % 2 == 0 else 0), map(lambda x: x**2, inputs)))

        pipeline = (
            Pipeline()
            .map(pipeline_simple_map)
            .filter(pipeline_simple_filter(IsEvenFilter()))
            .fold(pipeline_simple_fold)
        )

        context_a = PipelineContext(Path("."))
        context_b = PipelineContext(Path("."))

        result_a = pipeline.execute(inputs, context_a, None, None)
        result_b = pipeline.execute(inputs, context_b, None, None)
        assert len(result_a.errors) == 0, "Expected 0 errors"
        assert len(result_b.errors) == 0, "Expected 0 errors"
        assert (
            len(result_a.values) == 1 and result_a.values[0] == exp_out
        ), "Expected correct output"
        assert (
            len(result_b.values) == 1 and result_b.values[0] == exp_out
        ), "Expected correct output"
