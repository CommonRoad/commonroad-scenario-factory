from pathlib import Path
from typing import Iterator

from scenario_factory.pipeline import Pipeline, PipelineContext, pipeline_map, pipeline_populate
from scenario_factory.pipeline_steps import pipeline_flatten


@pipeline_populate
def pipeline_simple_populate(ctx: PipelineContext) -> Iterator[int]:
    for i in range(0, 10):
        yield i


@pipeline_map
def pipeline_blow_up(ctx: PipelineContext, value: int) -> Iterator[int]:
    for i in range(0, 10):
        yield value * i


def test_pipeline_flatten_flattens_pipeline_state():
    ctx = PipelineContext(Path("."))
    pipeline = Pipeline(ctx)

    pipeline.populate(pipeline_simple_populate)
    assert len(pipeline.state) == 10
    pipeline.map(pipeline_blow_up)
    assert len(pipeline.state) == 10
    pipeline.reduce(pipeline_flatten)
    assert len(pipeline.state) == 100
    assert all(isinstance(val, int) for val in pipeline.state)


def test_pipeline_flatten_handles_non_nested_pipeline_state():
    ctx = PipelineContext(Path("."))
    pipeline = Pipeline(ctx)

    pipeline.populate(pipeline_simple_populate)
    pipeline.reduce(pipeline_flatten)
    assert len(pipeline.state) == 10


def test_pipeline_flatten_handles_empty_pipeline_state():
    ctx = PipelineContext(Path("."))
    pipeline = Pipeline(ctx)

    pipeline.populate(lambda ctx: [])
    pipeline.reduce(pipeline_flatten)
    assert len(pipeline.state) == 0
