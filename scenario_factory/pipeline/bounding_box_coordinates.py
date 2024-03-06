import math
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd


def update_cities_file(cities_file: Path, radius: float, do_overwrite: bool = False) -> None:
    """
    Update bounding box coordinates in the cities file.

    Args:
        cities_file (Path): Path to the cities file.
        radius (float): Radius in km.
        do_overwrite (bool): Overwrite the file.
    """
    with open(cities_file, newline="") as csvfile:
        cities = pd.read_csv(csvfile)

    for ind, lat, lon in zip(range(len(cities)), cities.Lat, cities.Lon):
        bbox = compute_bounding_box_coordinates(lat, lon, radius)
        (
            cities.loc[(ind, "West")],
            cities.loc[(ind, "South")],
            cities.loc[(ind, "East")],
            cities.loc[(ind, "North")],
        ) = bbox

    print(cities)
    if do_overwrite:
        cities.to_csv(cities_file, index=False)


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
    radius_earth = 6.371 * 1e3
    dist_degree = radius / radius_earth * 180 / math.pi
    west = lon - dist_degree / np.cos(np.deg2rad(lat))
    south = lat - dist_degree
    east = lon + dist_degree / np.cos(np.deg2rad(lat))
    north = lat + dist_degree

    return west, south, east, north
