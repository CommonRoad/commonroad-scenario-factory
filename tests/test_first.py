import pytest
import os
import random
from files.n1_bounding_box_coordinates import compute_bounding_box_coordinates
from files.n1_bounding_box_coordinates import update_cities_file
import math
from pathlib import Path
import pandas as pd
import osmium

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
    # Values for the first line
    east = 8.8516
    north = 53.0738
    west = 8.8426
    south = 53.0684

    with open(Path("../files/0_cities_selected.csv"), newline='') as csvfile:
        cities = pd.read_csv(csvfile)

    first_line_cities = cities.iloc[0]

    update_cities_file(Path("../files/0_cities_selected.csv"), 0.3, True)

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

    east = 8.8516
    north = 53.0738
    west = 8.8426
    south = 53.0684

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
        assert (west <= node['lon'] <= east) and (south <= node['lat'] <= north)

