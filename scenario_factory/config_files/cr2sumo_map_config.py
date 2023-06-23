from crdesigner.map_conversion.sumo_map.config import SumoConfig


class CR2SumoNetConfig_edited(SumoConfig):
    # [m/s] if not None: use this speed limit instead of speed limit from CommonRoad files
    overwrite_speed_limit = 120 / 3.6
    # [m/s] default max. speed for SUMO for unrestricted sped limits
    unrestricted_max_speed_default = 120 / 3.6

    # default vehicle attributes to determine edge restrictions
    veh_params = {
        # maximum length
        'length': {
            'passenger': 4.7,
            'truck': 7.5,
            'bus': 12.4,
            'bicycle': 2.,
            'pedestrian': 0.415
        },
        # maximum width
        'width': {
            'passenger': 2.,
            'truck': 2.6,
            'bus': 2.7,
            'bicycle': 0.68,
            'pedestrian': 0.678
        }
    }