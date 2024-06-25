from typing import Dict, Iterable, Union

import numpy as np
import scipy.signal as signal
from commonroad.scenario.obstacle import DynamicObstacle, ObstacleType


def apply_smoothing_filter(array: np.ndarray, par1=0.05 / 2.5):
    if int(array.size) > 12:  # filter fails for length <= 12!
        # butterworth lowpass filter
        b, a = signal.butter(1, par1, output="ba")
        zi = signal.lfilter_zi(b, a)
        z, _ = signal.lfilter(b, a, array, zi=zi * array[0])
        return True, signal.filtfilt(b, a, array)
    else:
        # use simple smoothing filter instead
        return False, array


def find_first_greater(vec: np.ndarray, item):
    """return the index of the first occurence of item in vec"""
    for i in range(len(vec)):
        if item < vec[i]:
            return i
    return None


def select_by_vehicle_type(
    obstacles: Iterable, vehicle_types: Iterable[ObstacleType] = (ObstacleType.CAR)
) -> Union[Dict[int, DynamicObstacle], Iterable[DynamicObstacle]]:
    """:returns only obstacles with specified vehicle type(s)."""
    if isinstance(obstacles, dict):
        return {obs_id: obs for obs_id, obs in obstacles.items() if (obs.obstacle_type in vehicle_types)}
    else:
        return [obs for obs in obstacles if (obs.obstacle_type in vehicle_types)]
