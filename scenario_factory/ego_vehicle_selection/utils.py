__all__ = ["threshold_and_lag_detection", "threshold_and_max_detection"]

from typing import Tuple

import numpy as np
import scipy.signal


def _apply_smoothing_filter(array: np.ndarray, par1=0.05 / 2.5):
    if int(array.size) > 12:  # filter fails for length <= 12!
        # butterworth lowpass filter
        b, a = scipy.signal.butter(1, par1, output="ba")
        zi = scipy.signal.lfilter_zi(b, a)
        z, _ = scipy.signal.lfilter(b, a, array, zi=zi * array[0])
        return True, scipy.signal.filtfilt(b, a, array)
    else:
        # use simple smoothing filter instead
        return False, array


def _find_first_greater(vec: np.ndarray, item):
    """return the index of the first occurence of item in vec"""
    for i in range(len(vec)):
        if item < vec[i]:
            return i
    return None


def threshold_and_lag_detection(
    signal: np.ndarray, threshold: float, lag_threshold: float
) -> Tuple[bool, int]:
    """
    Find whether threshold is exceeded and time step by comparing with lagged signal.

    :param obstacle: the chosen obstacle

    :return: velocity difference of the obstalce's trajectory
    """
    if len(signal) == 0:
        return False, -1

    max_difference = np.abs(np.max(signal) - np.min(signal))
    if max_difference <= threshold:
        return False, -1

    # detect when vehicle is turning by comparred lagging signal to original one
    # -> more time in advance for fast turns
    success, signal_lagged = _apply_smoothing_filter(signal)
    if not success:
        # Could not apply smoothing filter, because there are not enough signals.
        # But the threshold is execeed, so this counts as a match
        return True, 0

    delta_lag = signal - signal_lagged
    init_time = _find_first_greater(np.abs(delta_lag), lag_threshold)
    if init_time is None:
        return False, -1

    return True, init_time


def threshold_and_max_detection(
    signal: np.ndarray, threshold: float, n_hold: int = 2
) -> Tuple[bool, int]:
    """
    Chceks whether signal exceeds threshold for at least n_hold consecutive time steps and
    returns first time_step.
    :param signal:
    :param threshold:
    :param time_gap:
    :return:
    """
    if len(signal) == 0:
        return False, -1

    exceeds = None
    # differentiate between min and max thresholds
    if threshold >= 0:
        if np.max(signal) > threshold:
            exceeds = np.greater(signal, threshold)
    else:
        if np.min(signal) < threshold:
            exceeds = np.less(signal, threshold)

    if exceeds is None:
        return False, -1

    # check if and where threshold is exceed for at least n_hold time steps
    diff = exceeds.astype("int16")
    diff = np.diff(diff)
    i_0 = np.where(diff > 0)[0]
    i_end = np.where(diff < 0)[0]

    if i_0.size > 0:
        if i_end.size == 0 or i_0[-1] > i_end[-1]:
            i_end = np.append(i_end, [exceeds.size - 1])

    if i_0.size == 0 or i_0[0] > i_end[0]:
        i_0 = np.append([0], i_0)

    durations = i_end - i_0

    if durations.size > 0 and np.max(durations) >= n_hold:
        init_time = i_0[np.argmax(durations)]
        if init_time > 0:  # maneuver at time 0 is usually implausible
            return True, init_time

    return False, -1
