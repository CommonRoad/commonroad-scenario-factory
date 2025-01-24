from abc import ABC, abstractmethod
from typing import Generic, Optional, Tuple, TypeVar

import numpy as np

_T = TypeVar("_T")


class BuilderCore(ABC, Generic[_T]):
    """
    Base class for all builders.
    """

    @abstractmethod
    def build(self) -> _T: ...


class BuilderIdAllocator:
    """
    Simple Id allocator that can be used in builders to create unique CommonRoad Ids
    """

    def __init__(self, seed: int = 0):
        self._id_ctr = seed

    def new_id(self) -> int:
        """
        Create a new unique CommonRoad Id.
        """
        self._id_ctr += 1
        return self._id_ctr


def construct_linear_function(line: np.ndarray) -> Optional[Tuple]:
    """
    Construct a linear function through the start and end point of `line`.

    :param line: A line that consists of at least two points.

    :returns: If a linear function can be construct its parameters a, b. If the line is parallel to the y-axis (i.e. delta x is 0), None is returned.
    """
    dx = line[0][0] - line[-1][0]
    if dx == 0.0:
        return None
    dy = line[0][1] - line[-1][1]
    a = dy / dx
    b = ((-a) * line[0][0]) + line[0][1]
    return (a, b)


def intersect_lines(line1: np.ndarray, line2: np.ndarray) -> Tuple:
    """
    Calculate the intersection point of the two straight lines, by constructing linear functions for each line.

    :param line1: A straight line with at least two points.
    :param line2: A straight line with at least two points.

    :returns: The intersections points as (x, y).

    :raises ValueError: If the lines cannot be intersected. Usually, this happens when both are parallel.
    """
    params_line1 = construct_linear_function(line1)
    params_line2 = construct_linear_function(line2)

    # If either one of the lines is parallel to the y-axis, the intersection point
    # is simply given by the x coordinate of the parallel line and the y coordinate of
    # the other line at that x coordinate.
    if params_line1 is None and params_line2 is not None:
        # line1 is parallel to the y-axis
        a2, b2 = params_line2
        x_intersection = line1[0][0]
        y_intersection = a2 * x_intersection + b2
        return (x_intersection, y_intersection)
    elif params_line2 is None and params_line1 is not None:
        # line2 is parallel to the y-axis
        a1, b1 = params_line1
        x_intersection = line2[0][0]
        y_intersection = a1 * x_intersection + b1
        return (x_intersection, y_intersection)
    elif params_line1 is None and params_line2 is None:
        raise ValueError(
            f"Cannot intersect the lines '{line1}' and '{line2}' because they are both parrallel to the y-axis"
        )

    a1, b1 = params_line1  # type: ignore
    a2, b2 = params_line2  # type: ignore

    if a1 == a2:
        raise ValueError(
            f"Cannot intersect the lines '{line1}' and '{line2}' because they are parallel to each other"
        )

    x_intersection = (b1 - b2) / (a2 - a1)
    y_intersection = a1 * x_intersection + b1
    return (x_intersection, y_intersection)


def euclidean_distance(p: Tuple[float, float], q):
    return np.sqrt(np.square(p[0] - q[0]) + np.square(p[1] - q[1]))


def nearest_point(
    reference_point: Tuple[float, float], points: np.ndarray[float, np.dtype]
) -> np.ndarray[float, np.dtype]:
    index = np.argsort(np.array([euclidean_distance(reference_point, point) for point in points]))[
        0
    ]
    return points[index]


def create_curve(
    line1: np.ndarray,
    line2: np.ndarray,
    num_interpolation_points: int = 20,
) -> np.ndarray:
    """
    Construct a bezier curve to connect the straigth lines.

    :param line1: The start straight line with at least two points. The curve will start at the end point of this line.
    :param line2: The end straight line with at least two points. The curve will end at the start point of this line.
    :param num_interpolation_points: Control the resolution of the resulting curve.

    :returns: The coordinates of the curve.
    """
    # Get intersection point of the two lines.
    # This point will be used as the third point for the bezier curve
    p_intersection = intersect_lines(line1, line2)

    # For each line, get the point which is neaerst to the intersection point
    # this point will than be used as one corner for the bezier curve
    p1 = nearest_point(p_intersection, line1)
    p2 = nearest_point(p_intersection, line2)

    # construct the bezier function based on the two corner points and the calculated intersection point
    def b(t):
        x = (
            (np.square(1 - t) * p1[0])
            + (2 * t * (1 - t) * p_intersection[0])
            + (np.square(t) * p2[0])
        )
        y = (
            (np.square(1 - t) * p1[1])
            + (2 * t * (1 - t) * p_intersection[1])
            + (np.square(t) * p2[1])
        )

        return (x, y)

    # evalute the bezier function according to the number of interpolation points
    ts = np.linspace(0, 1, num=num_interpolation_points)
    return np.array([b(t) for t in ts])


def offset_curve(curve: np.ndarray, offset: float) -> np.ndarray:
    x, y = curve[:, 0], curve[:, 1]
    # Tangents via finite difference
    dx = np.gradient(x)
    dy = np.gradient(y)

    # Normals
    norm = np.sqrt(dx**2 + dy**2)
    nx = -dy / norm
    ny = dx / norm

    # Offset
    x_offset = x + offset * nx
    y_offset = y + offset * ny

    return np.column_stack((x_offset, y_offset))
