from typing import Any, Iterable, List

from scenario_factory.pipeline.context import PipelineContext


def flatten(ctx: PipelineContext, xss: Iterable[Iterable[Any]]) -> Iterable[Any]:
    for xs in xss:
        yield from xs


def keep(ctx: PipelineContext, stack: Iterable[Any]) -> List[Any]:
    return [x for x in stack]
