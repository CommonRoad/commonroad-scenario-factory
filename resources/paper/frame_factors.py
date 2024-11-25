from commonroad.scenario.scenario import Scenario


def get_frame_factor_sim(scenario: Scenario) -> float:
    simulation_mode = int(str(scenario.scenario_id).split("_")[2])
    if simulation_mode > 2:  # demand, infrastructure, or random
        return 1.0
    scenario_id = str(scenario.scenario_id).split("-")[-3]
    match scenario_id:
        case "DEU_MONAEast":
            return 0.86
        case "DEU_MONAMerge":
            return 0.80
        case "DEU_MONAWest":
            return 0.96
        case "DEU_AachenBendplatz":
            return 0.85
        case "DEU_AachenHeckstrasse":
            return 0.90
        case "DEU_LocationCLower4":
            return 0.94
        case _:
            raise ValueError(f"No frame factor defined for scenario {scenario.scenario_id}")


def get_frame_factor_orig(scenario: Scenario) -> float:
    scenario_id = str(scenario.scenario_id).split("-")[-3]
    match scenario_id:
        case "DEU_MONAEast":
            return 0.75
        case "DEU_MONAMerge":
            return 0.6
        case "DEU_MONAWest":
            return 0.9
        case "DEU_AachenBendplatz":
            return 0.7
        case "DEU_AachenHeckstrasse":
            return 0.78
        case "DEU_LocationCLower4":
            return 0.87
        case _:
            raise ValueError(f"No frame factor defined for scenario {scenario.scenario_id}")
