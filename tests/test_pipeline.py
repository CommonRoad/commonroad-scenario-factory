import logging
import math
import os
import random
import xml.etree.ElementTree as ET
from pathlib import Path

import osmium
import pandas as pd
import pytest
from commonroad.common.file_reader import CommonRoadFileReader
from pyproj import Proj, transform

from files.script_1_bounding_box_coordinates import compute_bounding_box_coordinates
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

# Change error margin while testing to measure precisety
error_margin = 0.05
lower_bound = 1 - error_margin
upper_bound = 1 + error_margin


@pytest.fixture(autouse=True, scope="session")
def calculate_input_variables(request):
    global country, city, lat, lon, east, north, west, south, east_SI, north_SI, west_SI, south_SI

    random_test = request.config.getoption("--random_test")
    if random_test:
        with open(Path("../files/0_cities_selected.csv"), newline="") as csvfile:
            cities = pd.read_csv(csvfile)

        random_line = cities.sample(n=1).iloc[0]

        country = random_line.Country
        city = random_line.City
        lat = random_line.Lat
        lon = random_line.Lon

        east, north, west, south = calculate_bounding_box(lat, lon, radius=0.3)

        east_SI, north_SI = wgs84_to_web_mercator(east, north)
        west_SI, south_SI = wgs84_to_web_mercator(west, south)

    else:
        # Test with hand-picked and hand-calculated example
        country = "DEU"
        city = "Bremen"
        lat = 53.071054226968
        lon = 8.847098524980682

        east = 8.851588965027055
        north = 53.07375219178576
        west = 8.842608084934309
        south = 53.068356262150246

        # Conversion from WGS84 (GPS) to WGS84 Web Mercator

        east_SI = 985354.376
        north_SI = 6996651.749
        west_SI = 984354.629
        south_SI = 6995652.002


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


def test_bounding_box_coordinates():
    global east, north, west, south
    script_name = "script_1_bounding_box_coordinates.py"
    command1 = "cd ../files"
    command2 = f"poetry run python {script_name}"
    try:
        os.system(command1 + " ; " + command2)
    except Exception:
        logger.warn(f"Error while running {script_name}")
        assert False, f"Error while running {script_name}"

    try:
        with open(Path("../files/0_cities_selected.csv"), newline="") as csvfile:
            cities_updated = pd.read_csv(csvfile)
    except Exception:
        logger.warn("The input file can not be opened.")
        assert False, "The input file can not be opened."

    selected_line = cities_updated[
        (cities_updated["Country"] == country)
        & (cities_updated["City"] == city)
        & (cities_updated["Lat"] == lat)
        & (cities_updated["Lon"] == lon)
    ]

    assert selected_line.shape[0] == 1, "Such input can not be found on input file, or duplicated entry on input."

    selected_line = selected_line.iloc[0]

    assert math.isclose(east, selected_line.East, rel_tol=1e-8), "Coordinates of calculated points doesn't match."
    assert math.isclose(north, selected_line.North, rel_tol=1e-8), "Coordinates of calculated points doesn't match."
    assert math.isclose(west, selected_line.West, rel_tol=1e-8), "Coordinates of calculated points doesn't match."
    assert math.isclose(south, selected_line.South, rel_tol=1e-8), "Coordinates of calculated points doesn't match."


def test_osm_map_extraction():
    global east, north, west, south, country, city

    script_name = "script_2_osm_map_extraction.py"
    command1 = "cd ../files"
    command2 = f"poetry run python {script_name}"

    try:
        os.system(command1 + " ; " + command2)
    except Exception:
        logger.warn(f"Error while running {script_name}")
        assert False, f"Error while running {script_name}"

    osm_file_path = f"../files/extracted_maps/{country}_{city}.osm"

    handler = NodeHandler()

    try:
        reader = osmium.io.Reader(osm_file_path)
        osmium.apply(reader, handler)
        reader.close()
    except Exception:
        logger.warn(f"Error while opening {osm_file_path}")
        assert False, f"Error while opening {osm_file_path}"

    assert count_lines_in_file(osm_file_path) > 20, f"Empty osm file {osm_file_path}"

    for node in handler.nodes:
        assert (lower_bound * west <= node["lon"] <= upper_bound * east) and (
            lower_bound * south <= node["lat"] <= upper_bound * north
        ), "The point is out of bounding box."


def test_conversion_to_commonroad():
    global east_SI, north_SI, west_SI, south_SI, country, city

    script_name = "script_3_conversion_to_commonroad.py"
    command1 = "cd ../files"
    command2 = f"poetry run python {script_name}"

    try:
        os.system(command1 + " ; " + command2)
    except Exception:
        logger.warn(f"Error while running {script_name}")
        assert False, f"Error while running {script_name}"

    filepath = f"../files/commonroad/{country}_{city}.xml"

    try:
        root = ET.parse(filepath).getroot()
    except Exception:
        logger.warn(f"Error while opening {filepath}")
        assert False, f"Error while opening {filepath}"

    assert count_lines_in_file(filepath) > 20, f"Empty file {filepath}"

    for lanelet in root.iter("lanelet"):
        for point in lanelet.iter("point"):
            x = float(point.find("x").text)
            y = float(point.find("y").text)
            assert (lower_bound * west_SI <= x <= upper_bound * east_SI) and (
                lower_bound * south_SI <= y <= upper_bound * north_SI
            ), "The point is out of bounding box."


def test_globetrotter():
    global east_SI, north_SI, west_SI, south_SI, country, city

    script_name = "script_4_globetrotter.py"
    command1 = "cd ../files"
    command2 = f"poetry run python {script_name}"

    try:
        os.system(command1 + " ; " + command2)
    except Exception:
        logger.warn(f"Error while running {script_name}")
        assert False, f"Error while running {script_name}"

    folder_path = f"../files/globetrotter/{country}_{city}"

    for filename in os.listdir(folder_path):
        if filename.endswith(".xml"):
            file_path = os.path.join(folder_path, filename)

            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
            except Exception:
                logger.warn(f"Error while opening {file_path}")
                assert False, f"Error while opening {file_path}"

            assert count_lines_in_file(file_path) > 20, f"Empty file {file_path}"

            for lanelet in root.iter("lanelet"):
                for point in lanelet.iter("point"):
                    x = float(point.find("x").text)
                    y = float(point.find("y").text)
                    assert (lower_bound * west_SI <= x <= upper_bound * east_SI) and (
                        lower_bound * south_SI <= y <= upper_bound * north_SI
                    ), "The point is out of bounding box."


def test_scenario_generation():
    script_name = "script_5_scenario_generation.py"
    command1 = "cd ../files"
    command2 = f"poetry run python {script_name}"
    try:
        os.system(command1 + " ; " + command2)
    except Exception:
        logger.warn(f"Error while running {script_name}")
        assert False, f"Error while running {script_name}"

    cmd_num_of_scenario_files = "ls -1 ../files/output/intermediate | wc -l"

    try:
        num_of_scenario_files = int(os.popen(cmd_num_of_scenario_files).read().strip())
    except Exception:
        logger.warn(f"Execution of cmd {cmd_num_of_scenario_files} is failed.")
        assert False, f"Execution of cmd {cmd_num_of_scenario_files} is failed."

    assert num_of_scenario_files > 30, "Scenario number must be greater than 30."

    traverse_and_check("../files/output/intermediate")
