from enum import IntEnum


class EgoSelectionCriterion(IntEnum):
    turning = 0
    acceleration = 1
    braking = 2
    lane_change = 3
    merging = 4