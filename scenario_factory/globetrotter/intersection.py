import xml.etree.ElementTree as ET
from sys import maxsize

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import shapely
import utm as u
from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.geometry.shape import Polygon
from commonroad.planning.planning_problem import PlanningProblemSet
from commonroad.scenario.lanelet import Lanelet
from commonroad.scenario.scenario import Scenario, Tag
from shapely.ops import cascaded_union


class Intersection:
    graph: nx.DiGraph
    scenario: Scenario

    location: dict
    geonamesId: int
    country: str
    region_ISO3166_2: str
    population: int
    lht: bool
    tag: str

    center: tuple
    lat: float
    lng: float

    forking_points: []
    max_adj_lanes_same_direction: int
    min_adj_lanes_same_direction: int
    avg_adj_lanes_same_direction: float
    mean_distance_fp_center: float
    area: float
    density: float
    num_lanelets: int
    max_speedlimit: float
    lanes_max_crossing: int
    max_pre_suc: int

    shape: shapely.geometry.polygon.Polygon

    def __init__(self, scenario: Scenario, center: tuple, forking_points: list):
        self.scenario = scenario
        self.center = center

        self._center_to_lat_lng()

        self.forking_points = forking_points
        # print(self.center, self.forking_points)
        self.mean_fp_center()
        self.scenario_to_graph()

    def compute_features(self):
        """
        Compute intersection features

        :return: None
        """

        self.min_max_adj_lanes_same_direction()
        self.get_shape()
        self.number_lanelets()
        self.compute_density()
        self.get_max_speed()
        self.max_crossing_lanes()
        self.get_max_pred_suc()

    def get_features(self):
        """
        Return features of intersection

        :return: List of features
        """

        return [
            len(self.forking_points),
            self.num_lanelets,
            self.max_adj_lanes_same_direction,
            # self.min_adj_lanes_same_direction,
            self.avg_adj_lanes_same_direction,
            self.area,
            # self.density,
            self.mean_distance_fp_center,
            self.lanes_max_crossing,
            self.max_pre_suc
            # self.max_speedlimit,
        ]

    def number_lanelets(self):
        """
        Compute the number of lanelets

        :return: None
        """
        self.num_lanelets = len(self.scenario.lanelet_network.lanelets)

    def compute_density(self):
        """
        Compute density of intersection

        :return: None
        """
        self.density = self.area / self.num_lanelets

    def mean_fp_center(self):
        """
        Compute mean distance between forking points and center

        :return: None
        """
        dist = 0.0
        for p in self.forking_points:
            dist += np.linalg.norm(p - self.center)
        self.mean_distance_fp_center = dist / len(self.forking_points)

    def max_crossing_lanes(self):
        """
        Compute the maximum crossing lanes at one point in the intersection

        :return: None
        """
        net = self.scenario.lanelet_network
        lanelets = net.lanelets
        max_crossing = 0
        for idx, l1 in enumerate(lanelets):
            cross_count = 0
            for l2 in lanelets[idx:]:
                # use shapely polygons of lanelets
                polygon1 = Polygon(
                    np.concatenate((l1.left_vertices, np.flip(l1.right_vertices, axis=0)), axis=0)
                ).shapely_object
                polygon2 = Polygon(
                    np.concatenate((l2.left_vertices, np.flip(l2.right_vertices, axis=0)), axis=0)
                ).shapely_object
                # overlaps is the needed function here
                if polygon1.overlaps(polygon2):
                    cross_count += 1
            max_crossing = max(max_crossing, cross_count)

        self.lanes_max_crossing = max_crossing

    def get_max_pred_suc(self):
        """
        Compute the maximum of predecessor or successors a single intersection has

        :return: None
        """
        net = self.scenario.lanelet_network
        lanelets = net.lanelets
        latest_max = 0
        for lanelet in lanelets:
            latest_max = max(latest_max, len(lanelet.successor), len(lanelet.predecessor))
        self.max_pre_suc = latest_max

    def get_max_speed(self):
        """
        Compute maximum speed limit at intersection

        :return: None
        """
        net = self.scenario.lanelet_network
        lanelets = net.lanelets

        maxSpeed = 0
        for lanelet in lanelets:
            if lanelet.speed_limit < 300:
                maxSpeed = max(maxSpeed, lanelet.speed_limit)
        self.max_speedlimit = maxSpeed

    def min_max_adj_lanes_same_direction(self):
        """
        Compute minimum, average and maximum of adjacent lanelets in the same direction

        :return: None
        """
        max_adj = 1
        min_adj = maxsize
        net = self.scenario.lanelet_network
        lanelets = net.lanelets
        checked_lanes = set()
        for lanelet in lanelets:
            if lanelet.lanelet_id in checked_lanes:
                continue

            checked_lanes.add(lanelet.lanelet_id)

            num_lanes = 1
            current_l = lanelet
            # search right site for adjacent lanelets
            while current_l.adj_right_same_direction:
                right = net.find_lanelet_by_id(current_l.adj_right)
                if not right:
                    break
                num_lanes += 1
                checked_lanes.add(right)
                current_l = right

            current_l = lanelet
            # search left site for adjacent lanelets
            while current_l.adj_left_same_direction:
                left = net.find_lanelet_by_id(current_l.adj_left)
                if not left:
                    break
                num_lanes += 1
                checked_lanes.add(left)
                current_l = left

            max_adj = max(num_lanes, max_adj)
            min_adj = min(num_lanes, min_adj)

        self.min_adj_lanes_same_direction = min_adj
        self.max_adj_lanes_same_direction = max_adj
        self.avg_adj_lanes_same_direction = float(min_adj + max_adj) / 2

    def intersection_to_xml(self, file_path):
        """
        Export intersections to the modified CommonRoad format

        :return: None
        """

        author = "Florian Finkeldei"
        affiliation = "TUM - Cyber-Physical Systems"
        source = "OpenStreetMap"
        planning_problem_set = PlanningProblemSet()

        tag = self.tag if hasattr(self, "tag") else {Tag.INTERSECTION}
        fw = CommonRoadFileWriter(self.scenario, planning_problem_set, author, affiliation, source, tag)
        fw.write_to_file(file_path, OverwriteExistingFile.ALWAYS)

        commonRoad = ET.parse(file_path)
        root = commonRoad.getroot()
        intersection = ET.Element("globetrotter")

        location = ET.SubElement(intersection, "location")
        lat = ET.SubElement(location, "latitude")
        lat.text = str(self.lat)
        lng = ET.SubElement(location, "longitude")
        lng.text = str(self.lng)

        if hasattr(self, "population"):
            population = ET.SubElement(intersection, "population")
            population.text = str(self.population)

        if hasattr(self, "geonamesId"):
            geonameid = ET.SubElement(intersection, "geonameId")
            geonameid.text = str(self.geonamesId)
        # max_adj = ET.SubElement(intersection, "max_adj_lanes_same_direction")
        # max_adj.text = str(self.max_adj_lanes_same_direction)
        # min_adj = ET.SubElement(intersection, "min_adj_lanes_same_direction")
        # min_adj.text = str(self.min_adj_lanes_same_direction)

        forking_points = ET.SubElement(intersection, "forking_points")
        for p in self.forking_points:
            point = ET.SubElement(forking_points, "point")
            x = ET.SubElement(point, "x")
            x.text = str(p[0])
            y = ET.SubElement(point, ("y"))
            y.text = str(p[1])

        root.append(intersection)
        commonRoad.write(file_path)

    def get_shape(self):
        """
        Get the shape of the intersection

        :return: Polygon shape of intersection
        """
        net = self.scenario.lanelet_network
        lanelets = net.lanelets
        polygons = []
        for lanelet in lanelets:
            polygon = Polygon(
                np.concatenate(
                    (lanelet.left_vertices, np.flip(lanelet.right_vertices, axis=0)),
                    axis=0,
                )
            )
            polygons.append(polygon.shapely_object)

        poly = cascaded_union(polygons)

        if isinstance(poly, shapely.geometry.polygon.Polygon):
            # x,y = poly.exterior.xy
            # plt.plot(x,y)
            # plt.show()
            self.shape = poly
            self.area = poly.area
            return poly
        else:
            # in case faulty intersection with several polygons was detected

            # for p in list(poly):
            #    x,y = p.exterior.xy
            #    plt.plot(x,y)
            # plt.title(self.tag)
            # plt.show()
            print("Multipolynom detected")
            self.shape = poly
            self.area = poly.area

    def _center_to_lat_lng(self):
        """
        Convert center of intersetion to latitude and longitude

        :return: None
        """
        try:
            zone_number = u.latlon_to_zone_number(self.location.lat, self.location.lng)
            zone_letter = u.latitude_to_zone_letter(self.location.lat)
            self.lat, self.lng = u.to_latlon(self.center[0], self.center[1], zone_number, zone_letter)
        except Exception:
            print("\t error converting utm to lat, lng. Using utm format instead")
            self.lat = self.center[0]
            self.lng = self.center[1]

    def rht_to_lht(self):
        """
        Convert intersection to left hand traffic. Warning! Use with caution. See thesis for more information

        :return: None
        """

        net = self.scenario.lanelet_network
        lanelets = net.lanelets

        lht_lanes = []
        for lanelet in lanelets:
            adj_r_same = False
            adj_l_same = False
            if lanelet.adj_right and lanelet.adj_right_same_direction:
                adj_r_same = True
            if lanelet.adj_left and lanelet.adj_left_same_direction:
                adj_l_same = True

            lht_l = Lanelet(
                lanelet.right_vertices,
                lanelet.center_vertices,
                lanelet.left_vertices,
                lanelet.lanelet_id,
                predecessor=lanelet.successor,
                successor=lanelet.predecessor,
                speed_limit=lanelet.speed_limit,
                adjacent_right=lanelet.adj_left,
                adjacent_left=lanelet.adj_right,
                adjacent_right_same_direction=adj_l_same,
                adjacent_left_same_direction=adj_r_same,
            )
            lht_lanes.append(lht_l)

        self.scenario.lanelet_network = net.create_from_lanelet_list(lht_lanes)
        self.scenario_to_graph()

    def scenario_to_graph(self):
        """
        Convert scenario to NetworkX graph

        :return: None
        """

        net = self.scenario.lanelet_network
        lanelets = net.lanelets
        lanelet_ids = [lanelet.lanelet_id for lanelet in lanelets]

        G = nx.DiGraph(scenario=self.scenario)
        for lanelet in lanelets:
            position = (
                np.mean([p[0] for p in lanelet.center_vertices]),
                np.mean([p[1] for p in lanelet.center_vertices]),
            )
            G.add_node(lanelet.lanelet_id, pos=position, lanelet=lanelet)
            edges = [(lanelet.lanelet_id, s) for s in lanelet.successor if s in lanelet_ids]
            if edges:
                G.add_edges_from(edges)

        self.graph = G

    def update_scenario_from_graph(self):
        """
        Converts NetworkX graph into scenario

        :return: None
        """

        G = self.graph
        lanelets = list(nx.get_node_attributes(G, "lanelet").values())
        self.scenario.lanelet_network = self.scenario.lanelet_network.create_from_lanelet_list(lanelets)

    def show_graph(self):
        """
        plot networkX graph

        :return: None
        """

        pos = nx.get_node_attributes(self.graph, "pos")
        nx.draw(self.graph, pos)
        plt.show()

    def __str__(self):
        return self.tag
