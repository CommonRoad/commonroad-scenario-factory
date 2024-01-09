import pandas as pd
import numpy as np
import math
from pathlib import Path
from typing import Tuple


def update_cities_file(file_path: Path, radius: float, do_overwrite: bool = False):
    with open(file_path, newline='') as csvfile:
        cities = pd.read_csv(csvfile)

    for ind, lat, lon in zip(range(len(cities)), cities.Lat, cities.Lon):
        bbox = compute_bounding_box_coordinates(lat, lon, radius)
        cities.loc[(ind, "West")], cities.loc[(ind, "South")], cities.loc[(ind, "East")], cities.loc[(ind, "North")] = bbox

    print(cities)
    if do_overwrite:
        cities.to_csv(file_path, index=False)


def compute_bounding_box_coordinates(lat: float, lon: float, radius: float) -> Tuple[float, float, float, float]:
    """

    :param lat: in degree
    :param lon: in degree
    :param radius: in km
    :return:
    """
    radius_earth = 6.371*1e3
    dist_degree = radius / radius_earth * 180/math.pi
    west = lon - dist_degree / np.cos(np.deg2rad(lat))
    south = lat - dist_degree
    east = lon + dist_degree / np.cos(np.deg2rad(lat))
    north = lat + dist_degree

    return west, south, east, north


update_cities_file(Path("0_cities_selected.csv"), 0.03, True)
