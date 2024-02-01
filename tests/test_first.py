import pytest
import os
import random
from files.n1_bounding_box_coordinates import compute_bounding_box_coordinates
import math
from pathlib import Path
import pandas as pd
import osmium
import xml.etree.ElementTree as ET

east = 8.851588965027055
north = 53.07375219178576
west = 8.842608084934309
south = 53.068356262150246

# Conversion from WGS84 (GPS) to WGS84 Web Mercator

east_SI = 985354.376
north_SI = 6996651.749
west_SI = 984354.629
south_SI = 6995652.002

error_margin = 0.02
lower_bound = 1 - error_margin
upper_bound = 1 + error_margin


class NodeHandler(osmium.SimpleHandler):
    def __init__(self):
        super(NodeHandler, self).__init__()
        self.nodes = []  # List to store nodes with lat and lon

    def node(self, n):
        # Store node ID, lat, and lon in the list
        self.nodes.append({'id': n.id, 'lat': n.location.lat, 'lon': n.location.lon})


def calculate_area(lat1, lon1, lat2, lon2):
    radius_of_earth = 6.371e3  # in km

    area = math.pi * math.pow(radius_of_earth, 2) * (math.sin(lat1) - math.sin(lat2)) * (lon1 - lon2) / 180
    area = abs(area)

    return area


@pytest.fixture
def random_params():
    lat = random.uniform(-90.0, 90.0)
    lon = random.uniform(-180.0, 180.0)
    radius = random.uniform(0.001, 0.3)
    return lat, lon, radius


@pytest.mark.parametrize("repeat_count", range(50))
def test_area(random_params, repeat_count):
    lat, lon, radius = random_params
    bbox_coordinates = compute_bounding_box_coordinates(lat, lon, radius)
    west, south, east, north = bbox_coordinates
    area = calculate_area(west, north, east, south)
    area_from_radius = math.pow(2 * radius, 2) / 2
    print("Area (km2):", area, "Area from radius (km2):", area_from_radius)
    assert area > area_from_radius


def test_file_after_n1():
    script_name = 'n1_bounding_box_coordinates.py'
    command1 = f"cd ../files"
    command2 = f"poetry run python {script_name}"

    # Values for the first line
    with open(Path("../files/0_cities_selected.csv"), newline='') as csvfile:
        cities = pd.read_csv(csvfile)

    first_line_cities = cities.iloc[0]

    os.system(command1 + " ; " + command2)

    with open(Path("../files/0_cities_selected.csv"), newline='') as csvfile:
        cities_updated = pd.read_csv(csvfile)

    first_line_cities_updated = cities_updated.iloc[0]

    assert first_line_cities.Country == first_line_cities_updated.Country
    assert first_line_cities.City == first_line_cities_updated.City
    assert first_line_cities.Lat == first_line_cities_updated.Lat
    assert first_line_cities.Lon == first_line_cities_updated.Lon
    assert math.isclose(east, first_line_cities_updated.East, rel_tol=1e-3)
    assert math.isclose(north, first_line_cities_updated.North, rel_tol=1e-3)
    assert math.isclose(west, first_line_cities_updated.West, rel_tol=1e-3)
    assert math.isclose(south, first_line_cities_updated.South, rel_tol=1e-3)


def test_file_after_n2():
    script_name = 'n2_osm_map_extraction.py'
    command1 = f"cd ../files"
    command2 = f"poetry run python {script_name}"

    os.system(command1 + " ; " + command2)

    osm_file_path = '../files/extracted_maps/DEU_Bremen.osm'

    handler = NodeHandler()

    reader = osmium.io.Reader(osm_file_path)
    osmium.apply(reader, handler)
    reader.close()

    for node in handler.nodes:
        assert (lower_bound * west <= node['lon'] <= upper_bound * east) and (lower_bound * south <= node['lat'] <= upper_bound * north)


def test_file_after_n3():
    script_name = 'n3_conversion_to_commonroad.py'
    command1 = f"cd ../files"
    command2 = f"poetry run python {script_name}"

    os.system(command1 + " ; " + command2)

    root = ET.parse('../files/commonroad/DEU_Bremen.xml').getroot()

    for lanelet in root.iter('lanelet'):
        for point in lanelet.iter('point'):
            x = float(point.find('x').text)
            y = float(point.find('y').text)
            assert (lower_bound * west_SI <= x <= upper_bound * east_SI) and (lower_bound * south_SI <= y <= upper_bound * north_SI)
