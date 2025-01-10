from typing import Sequence

from scenario_factory.pipeline import (
    PipelineContext,
    pipeline_filter,
    pipeline_fold,
    pipeline_map,
)


@pipeline_map()
def pipeline_simple_map(ctx: PipelineContext, value: int) -> int:
    return value**2


@pipeline_filter()
def pipeline_even_filter(ctx: PipelineContext, value: int) -> bool:
    return value % 2 == 0


@pipeline_fold()
def pipeline_simple_fold(ctx: PipelineContext, values: Sequence[int]) -> Sequence[int]:
    return [sum(values)]
