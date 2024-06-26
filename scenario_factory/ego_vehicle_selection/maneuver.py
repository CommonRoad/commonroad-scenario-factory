from dataclasses import dataclass

from commonroad.scenario.obstacle import DynamicObstacle


@dataclass
class EgoVehicleManeuver:
    ego_vehicle: DynamicObstacle
    start_time: int

    def __str__(self) -> str:
        return f"EgoVehicleManeuver(ego_vehicle_id={self.ego_vehicle.obstacle_id}, start_time={self.start_time})"
