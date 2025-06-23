import numpy as np
from commonroad_clcs.util import chaikins_corner_cutting, resample_polyline


def smoothen_polyline(
    polyline: np.ndarray, resampling_distance: float = 1.5, n_lengthen: int = 3
) -> np.ndarray:
    """
    Smoothens the given polyline by repeatedly applying Chaikin's corner cutting and
    then resamples it.

    :param polyline: The array of points (shape: Nx2) describing the polyline.
    :param resampling_distance: Distance for resampling the smoothed polyline.
    :param n_lengthen: Number of additional points to be appended to start and end for extension.
    :return: The resulting smoothed and resampled polyline as a NumPy array (shape: Mx2).
    """
    if len(polyline) < 2:
        return polyline

    # Apply Chaikin's corner cutting multiple times
    polyline = chaikins_corner_cutting(polyline, refinements=3)

    # Resample to get uniform distance between points
    resampled_polyline = resample_polyline(polyline, resampling_distance)

    # Extend the polyline by mirroring the first and last segments
    for _ in range(n_lengthen):
        resampled_polyline = np.insert(
            resampled_polyline, 0, 2 * resampled_polyline[0] - resampled_polyline[1], axis=0
        )
        resampled_polyline = np.insert(
            resampled_polyline,
            len(resampled_polyline),
            2 * resampled_polyline[-1] - resampled_polyline[-2],
            axis=0,
        )

    return resampled_polyline
