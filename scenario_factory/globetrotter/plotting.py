from typing import List

import matplotlib.pyplot as plt
import numpy as np
from commonroad.scenario.scenario import Scenario
from commonroad.visualization.mp_renderer import MPRenderer
from sklearn.cluster import AgglomerativeClustering

from scenario_factory.globetrotter.intersection import Intersection


def _plot_scenario(scenario: Scenario, ax=None) -> None:
    """
    Plot a scenario

    See also https://commonroad.in.tum.de/static/docs/opendrive2lanelet/_modules/opendrive2lanelet/io/visualize_commonroad.html#main

    :param scenario: CommonRoad scenario
    """
    ax = plt.gca() if ax is None else ax

    plt.style.use("classic")
    ax.axis("equal")

    rnd = MPRenderer(ax=ax)
    rnd.draw_lanelet_network(scenario.lanelet_network)
    rnd.render()


def plot_scenario(scenario: Scenario, title: str = "Scenario") -> None:
    _plot_scenario(scenario)

    plt.autoscale()
    plt.title(title)
    plt.axis("off")
    plt.show()


def plot_forking_points(scenario: Scenario, points: np.ndarray) -> None:
    """
    Plot only forking points on scenario

    :param1 points: List of forking points
    :param2 commonroad_xml_file: Path to scenario
    :return: None
    """

    ind = np.lexsort((points[:, 1], points[:, 0]))
    points = points[ind]
    plt.figure(figsize=(10, 7))
    _plot_scenario(scenario)

    plt.subplots_adjust(bottom=0.1)
    plt.scatter(
        points[:, 0], points[:, 1], label="True Position", s=60, c="red", zorder=10
    )
    for idx in range(0, len(points)):
        plt.annotate(str(idx), xy=(points[idx, 0], points[idx, 1]), zorder=11)

    plt.gca().set_aspect("equal")
    plt.autoscale()
    plt.title("Forking points")
    plt.axis("off")
    plt.show()


def plot_clustered_forking_points(
    scenario: Scenario, cluster: AgglomerativeClustering, points: np.ndarray
) -> None:
    """
    Plot cluster with grouped forking points in same color on a large location as background

    :param1 xml_file: Path to converted location
    :param2 cluster: Cluster object received from clustering algorithms
    :param3 points: Forking points
    :return: None
    """
    plt.figure(figsize=(10, 7))

    _plot_scenario(scenario)

    plt.scatter(
        points[:, 0], points[:, 1], c=cluster.labels_, cmap="rainbow", s=60, zorder=10
    )
    plt.gca().set_aspect("equal")

    ind = np.lexsort((points[:, 1], points[:, 0]))
    points = points[ind]
    for idx in range(len(points)):
        plt.annotate(str(idx), xy=(points[idx, 0], points[idx, 1]), zorder=11)

    plt.gca().set_title("Clustered forking points")
    plt.axis("off")
    plt.show()


def plot_intersections_single(
    scenario: Scenario, intersections: List[Intersection]
) -> None:
    plt.figure(figsize=(10, 7))

    _plot_scenario(scenario)

    centers = np.empty(shape=(len(intersections), 2), dtype=np.float64)
    for i, intersection in enumerate(intersections):
        centers[i, 0] = intersection.center[0]
        centers[i, 1] = intersection.center[1]

    plt.scatter(
        centers[:, 0],
        centers[:, 1],
        c=list(range(len(intersections))),
        cmap="rainbow",
        s=60,
        zorder=10,
    )
    for i in range(len(centers)):
        plt.annotate(str(i), xy=(centers[i, 0], centers[i, 1]), zorder=11)

    plt.gca().set_title("Found intersection locations")
    plt.axis("off")
    plt.show()


def _plot_intersections(
    intersections: List[Intersection], start: int = 0, m: int = 5, n: int = 5
) -> None:
    """
    Plot multiple intersections

    :param1 intersections: List of intersections
    :param2 m: number of rows
    :param3 n: number of columns
    :return: None
    """

    fig = plt.figure(figsize=(n, m), frameon=True, facecolor="w", dpi=200)

    fig.suptitle("Intersections")
    for idx, intersection in enumerate(intersections[: n * m]):
        ax = fig.add_subplot(m, n, idx + 1)
        _plot_scenario(intersection.scenario, ax)

        ax.set_title(str(start + idx))
        ax.autoscale()
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)

    fig.tight_layout()
    plt.show()


def plot_intersections(
    intersections: List[Intersection], m: int = 5, n: int = 5
) -> None:
    for start in range(0, len(intersections), m * n):
        _plot_intersections(intersections[start : start + m * n], start, m, n)
