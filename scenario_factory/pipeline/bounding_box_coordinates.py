import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Tuple

import numpy as np

from scenario_factory.pipeline.context import (
    PipelineContext,
    PipelineStepArguments,
    pipeline_map_with_args,
    pipeline_populate_with_args,
)

RADIUS_EARTH: float = 6.371 * 1e3


def compute_bounding_box_coordinates(lat: float, lon: float, radius: float) -> Tuple[float, float, float, float]:
    """
    Compute the bounding box coordinates for a given latitude, longitude and radius.

    Args:
        lat (float): Latitude in degree
        lon (float): Longitude in degree
        radius (float): Radius in km

    Returns:
        Tuple[float, float, float, float]: West, South, East, North coordinates
    """

    dist_degree = radius / RADIUS_EARTH * 180 / math.pi
    west = lon - dist_degree / np.cos(np.deg2rad(lat))
    south = lat - dist_degree
    east = lon + dist_degree / np.cos(np.deg2rad(lat))
    north = lat + dist_degree

    return west, south, east, north


@dataclass
class PlainCity:
    country: str
    name: str
    lat: float
    lon: float


@dataclass
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def __str__(self):
        return f"{self.west},{self.south},{self.east},{self.north}"


@dataclass
class BoundedCity(PlainCity):
    bounding_box: BoundingBox


@dataclass
class LoadCitiesFromCsvArguments(PipelineStepArguments):
    cities_path: Path


@pipeline_populate_with_args
def load_cities_from_csv(ctx: PipelineContext, args: LoadCitiesFromCsvArguments) -> Iterator[PlainCity]:
    with args.cities_path.open() as csvfile:
        cities_reader = csv.DictReader(csvfile)
        for city in cities_reader:
            yield PlainCity(city["Country"], city["City"], float(city["Lat"]), float(city["Lon"]))


@dataclass
class ComputeBoundingBoxForCityArguments(PipelineStepArguments):
    radius: float


@pipeline_map_with_args
def compute_bounding_box_for_city(
    ctx: PipelineContext,
    args: ComputeBoundingBoxForCityArguments,
    city: PlainCity,
) -> BoundedCity:
    bounding_box_tuple = compute_bounding_box_coordinates(city.lat, city.lon, args.radius)
    bounding_box = BoundingBox(*bounding_box_tuple)
    return BoundedCity(city.country, city.name, city.lat, city.lon, bounding_box=bounding_box)


@dataclass
class WriteCitiesToFileArguments(PipelineStepArguments):
    cities_path: Path


def write_cities_to_file(ctx: PipelineContext, cities: Iterable[BoundedCity], args: WriteCitiesToFileArguments) -> None:
    """
    Update bounding box coordinates in the cities file.

    Args:
        cities_file (Path): Path to the cities file.
        radius (float): Radius in km.
        do_overwrite (bool): Overwrite the file.
    """
    with args.cities_path.open() as csvfile:
        writer = csv.writer(csvfile)
        # Write the header first
        # TODO: Merge the reader and writer to create a matching schema
        writer.writerow(["Country", "City", "Lat", "Lon", "West", "South", "East", "North"])
        for city in cities:
            writer.writerow(
                [
                    city.country,
                    city.name,
                    city.lat,
                    city.lon,
                    city.bounding_box.west,
                    city.bounding_box.south,
                    city.bounding_box.east,
                    city.bounding_box.north,
                ]
            )
