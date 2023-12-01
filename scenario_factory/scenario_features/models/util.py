import numpy as np
try:
    from commonroad_dc.geometry.util import chaikins_corner_cutting, resample_polyline
except ModuleNotFoundError:
    from commonroad_ccosy.geometry.util import resample_polyline, chaikins_corner_cutting


def smoothen_polyline(polyline, resampling_distance: float = 1.5, n_lengthen = 3):
    for _ in range(3):
        polyline = np.array(chaikins_corner_cutting(polyline))

    resampled_polyline = resample_polyline(polyline, resampling_distance)

    # lengthen by n_lengthen points
    for _ in range(n_lengthen):
        resampled_polyline = np.insert(resampled_polyline, 0,
                                       2 * resampled_polyline[0 ] - resampled_polyline[1 ], axis=0)
        resampled_polyline = np.insert(resampled_polyline,len(resampled_polyline),
                                       2 * resampled_polyline[-1] - resampled_polyline[-2], axis=0)

    return resampled_polyline