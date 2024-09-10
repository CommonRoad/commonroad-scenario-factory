from dataclasses import dataclass
from typing import ClassVar, Sequence

from commonroad.scenario.scenario import Tag

from scenario_factory.ego_vehicle_selection import (
    AccelerationCriterion,
    BrakingCriterion,
    EgoVehicleManeuverFilter,
    EgoVehicleSelectionCriterion,
    EnoughSurroundingVehiclesFilter,
    InterestingLaneletNetworkFilter,
    LaneChangeCriterion,
    LongEnoughManeuverFilter,
    MinimumVelocityFilter,
    TurningCriterion,
)


@dataclass
class ScenarioFactoryConfig:
    # Number of planning problems generated from one scenario
    planning_pro_per_scen: int = 8

    # Define the goal state of the planning problem with a lanelet (if False: define with a state)
    planning_pro_with_lanelet: bool = True

    # scenario length (time of CR scenario -> set simulation duration in sumo_config)
    # The length of the resulting scenarios cut from the simulated scenario. As this determines "how much" will be cut from the simulated scenario, the configured simulation steps must be larger then this option.
    cr_scenario_time_steps: int = 150

    # vehicles are deleted from final scenario if not within sensor_range once
    sensor_range: int = 90

    # Tags in cr scenario file
    author = "Florian Finkeldei"
    affiliation = "TUM - Cyber-Physical Systems"
    source = "OpenStreetMap, SUMO Traffic Simulator"
    tags = {Tag.SIMULATED}

    # EGO VEHICLE SELECTION ############################################################################################
    # obstacle_id of ego vehicles when ego vehicle is exported
    default_ego_id = 8888

    criterions: ClassVar[Sequence[EgoVehicleSelectionCriterion]] = [
        BrakingCriterion(),
        AccelerationCriterion(),
        TurningCriterion(),
        LaneChangeCriterion(),
        # MergingCriterion(),
    ]

    # additional filters to discard uninteresting situations
    filters: ClassVar[Sequence[EgoVehicleManeuverFilter]] = [
        LongEnoughManeuverFilter(),
        MinimumVelocityFilter(),
        EnoughSurroundingVehiclesFilter(),
        InterestingLaneletNetworkFilter(),
    ]
