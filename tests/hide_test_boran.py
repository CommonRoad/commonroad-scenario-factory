import logging
import math
import os
import random

import osmium
import pytest
from commonroad.common.file_reader import CommonRoadFileReader
from pyproj import Proj, transform

from scenario_factory.pipeline.bounding_box_coordinates import compute_bounding_box_coordinates
from scenario_factory.scenario_util import init_logging

# start logging, choose logging levels logging.DEBUG, INFO, WARN, ERROR, CRITICAL
logger = init_logging(__name__, logging.WARN)


# poetry run pytest test_pipeline.py --random_test for randomly selecting an example
class NodeHandler(osmium.SimpleHandler):
    def __init__(self):
        super(NodeHandler, self).__init__()
        self.nodes = []  # List to store nodes with lat and lon

    def node(self, n):
        # Store node ID, lat, and lon in the list
        self.nodes.append({"id": n.id, "lat": n.location.lat, "lon": n.location.lon})


def can_open_CR_file(filepath):
    try:
        scenario, _ = CommonRoadFileReader(filepath).open()
        return True
    except Exception as e:
        print(f"Error opening file {filepath}: {e}")
        return False


def traverse_and_check(directory):
    for root, dirs, files in os.walk(directory):
        # Skip subdirectories
        if root != directory:
            continue

        for file in files:
            filepath = os.path.join(root, file)
            assert can_open_CR_file(filepath)


def calculate_bounding_box(lat, lon, radius):
    # Radius of the Earth in kilometers
    earth_radius = 6371.0

    # Convert latitude and longitude from degrees to radians
    lat_rad = math.radians(lat)
    # lon_rad = math.radians(lon)

    # Calculate the change in latitude and longitude based on the radius
    delta_lat = math.degrees(radius / earth_radius)
    delta_lon = math.degrees(math.asin(math.sin(radius / earth_radius) / math.cos(lat_rad)))

    # Calculate the corner points of the bounding box
    # top_left = (lat + delta_lat, lon - delta_lon)
    top_right = (lat + delta_lat, lon + delta_lon)
    bottom_left = (lat - delta_lat, lon - delta_lon)
    # bottom_right = (lat - delta_lat, lon + delta_lon)

    # East, North, West, South
    return top_right[1], top_right[0], bottom_left[1], bottom_left[0]


def calculate_area(lat1, lon1, lat2, lon2):
    radius_of_earth = 6.371e3  # in km

    area = math.pi * math.pow(radius_of_earth, 2) * (math.sin(lat1) - math.sin(lat2)) * (lon1 - lon2) / 180
    area = abs(area)

    return area


def wgs84_to_web_mercator(lon, lat):
    # Define the WGS84 and Web Mercator coordinate systems
    wgs84 = Proj(init="epsg:4326")  # WGS84
    web_mercator = Proj(init="epsg:3857")  # WGS84 Web Mercator

    # Perform the coordinate transformation
    x, y = transform(wgs84, web_mercator, lon, lat)

    return x, y


def count_lines_in_file(file_path):
    with open(file_path, "r") as file:
        line_count = sum(1 for line in file)
    return line_count


country, city, lat, lon = None, None, None, None
east, north, west, south = None, None, None, None
east_SI, north_SI, west_SI, south_SI = None, None, None, None

# Change error margin while testing to measure precisely
error_margin = 0.05
lower_bound = 1 - error_margin
upper_bound = 1 + error_margin


@pytest.fixture
def random_params():
    lat = random.uniform(-90.0, 90.0)
    lon = random.uniform(-180.0, 180.0)
    radius = random.uniform(0.001, 0.3)
    return lat, lon, radius


@pytest.mark.parametrize("repeat_count", range(50))
def test_area(random_params, repeat_count, request):
    lat, lon, radius = random_params
    bbox_coordinates = compute_bounding_box_coordinates(lat, lon, radius)
    west, south, east, north = bbox_coordinates
    area = calculate_area(west, north, east, south)
    area_from_radius = math.pow(2 * radius, 2) / 2
    print("Area (km2):", area, "Area from radius (km2):", area_from_radius)
    assert area > area_from_radius
