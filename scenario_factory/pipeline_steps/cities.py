from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from scenario_factory.city import (
    BoundedCity,
    PlainCity,
    compute_bounding_box_for_city,
    load_plain_cities_from_csv,
    write_bounded_cities_to_csv,
)
from scenario_factory.pipeline import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map_with_args,
    pipeline_populate_with_args,
)


@dataclass
class LoadCitiesFromCsvArguments(PipelineStepArguments):
    cities_path: Path


@pipeline_populate_with_args
def pipeline_load_plain_cities_from_csv(args: LoadCitiesFromCsvArguments, ctx: PipelineContext) -> Iterator[PlainCity]:
    yield from load_plain_cities_from_csv(args.cities_path)


@dataclass
class ComputeBoundingBoxForCityArguments(PipelineStepArguments):
    radius: float


@pipeline_map_with_args
def pipeline_compute_bounding_box_for_city(
    args: ComputeBoundingBoxForCityArguments,
    ctx: PipelineContext,
    city: PlainCity,
) -> BoundedCity:
    return compute_bounding_box_for_city(city, args.radius)


@dataclass
class WriteCitiesToCsvArguments(PipelineStepArguments):
    cities_path: Path


def pipeline_write_cities_to_csv(
    args: WriteCitiesToCsvArguments, ctx: PipelineContext, cities: Iterable[BoundedCity]
) -> None:
    write_bounded_cities_to_csv(cities, args.cities_path)


__all__ = [
    # City I/O and Bounding Box computations
    "LoadCitiesFromCsvArguments",
    "pipeline_load_plain_cities_from_csv",
    "ComputeBoundingBoxForCityArguments",
    "pipeline_compute_bounding_box_for_city",
    "WriteCitiesToCsvArguments",
    "pipeline_write_cities_to_csv",
]
