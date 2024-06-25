from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.scenario.scenario import Scenario
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.scenario.scenario_wrapper import ScenarioWrapper

from scenario_factory.ego_vehicle_selector import select_interesting_ego_vehicle_maneuvers_from_scenario
from scenario_factory.generate_senarios import (
    convert_commonroad_scenario_to_sumo,
    create_planning_problem_set_for_ego_vehicle_maneuver,
    create_scenario_for_ego_vehicle_maneuver,
    delete_colliding_obstacles_from_scenario,
)
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map, pipeline_map_with_args
from scenario_factory.scenario_config import ScenarioConfig
from scenario_factory.scenario_features.models.scenario_model import ScenarioModel


@pipeline_map
def pipeline_create_sumo_configuration_for_commonroad_scenario(
    ctx: PipelineContext, commonroad_scenario: Scenario
) -> ScenarioWrapper:
    output_folder = ctx.get_output_folder("output")
    sumo_config = SumoConfig.from_scenario(commonroad_scenario)
    sumo_config.highway_mode = False
    sumo_config.random_seed = ctx.seed
    sumo_config.random_seed_trip_generation = ctx.seed
    scenario_wrapper = convert_commonroad_scenario_to_sumo(commonroad_scenario, output_folder, sumo_config)
    return scenario_wrapper


@pipeline_map
def pipeline_simulate_scenario(ctx: PipelineContext, scenario_wrapper: ScenarioWrapper) -> Scenario:
    sumo_config = SumoConfig.from_scenario(scenario_wrapper.initial_scenario)
    sumo_config.highway_mode = False
    sumo_config.random_seed = ctx.seed
    sumo_config.random_seed_trip_generation = ctx.seed
    sumo_config.simulation_steps = 300
    sumo_sim = SumoSimulation()
    sumo_sim.initialize(sumo_config, scenario_wrapper)

    for _ in range(sumo_config.simulation_steps):
        sumo_sim.simulate_step()
    sumo_sim.simulate_step()

    sumo_sim.stop()

    scenario = sumo_sim.commonroad_scenarios_all_time_steps()

    return scenario


@dataclass
class GenerateCommonRoadScenariosArguments(PipelineStepArguments):
    create_noninteractive: bool = True
    create_interactive: bool = False
    max_collisions: Optional[int] = None


@pipeline_map_with_args
def pipeline_generate_cr_scenarios(
    args: GenerateCommonRoadScenariosArguments, ctx: PipelineContext, scenario: Scenario
) -> Scenario:
    scenario_config = ScenarioConfig()
    output_path = ctx.get_output_folder("output")
    logger = ctx.get_logger("pipeline_generate_cr_scenarios")
    logger.info(f"Generating Scenarios for {scenario.scenario_id}")

    num_collisions = len(delete_colliding_obstacles_from_scenario(scenario, all=True))
    if args.max_collisions is not None:
        if num_collisions > args.max_collisions:
            raise RuntimeError(
                f"Skipping scenario {scenario.scenario_id} because it has {num_collisions}, but the maximum allowed number of collisions is {args.max_collisions}"
            )

    scenario_model = ScenarioModel(scenario, assign_vehicles_on_the_fly=False)  # TODO: shouldn't this be true?

    ego_vehicle_maneuvers = select_interesting_ego_vehicle_maneuvers_from_scenario(
        scenario, scenario_config, scenario_model
    )

    scenarios = []

    output_noninteractive = output_path.joinpath("noninteractive")
    output_noninteractive.mkdir(parents=True, exist_ok=True)
    for i, maneuver in enumerate(ego_vehicle_maneuvers):
        planning_problem_set = create_planning_problem_set_for_ego_vehicle_maneuver(scenario, scenario_config, maneuver)

        new_noninteractive_scenario = create_scenario_for_ego_vehicle_maneuver(
            scenario, scenario_config, maneuver, interactive=False
        )
        new_scenario_id = deepcopy(scenario.scenario_id)
        new_scenario_id.obstacle_behavior = "T"
        new_scenario_id.prediction_id = i + 1
        new_noninteractive_scenario.scenario_id = new_scenario_id
        CommonRoadFileWriter(
            new_noninteractive_scenario,
            planning_problem_set,
            author=scenario_config.author,
            affiliation=scenario_config.affiliation,
            source=scenario_config.source,
            tags=set(),
        ).write_to_file(
            str(output_noninteractive.joinpath(f"{new_noninteractive_scenario.scenario_id}.xml")),
            overwrite_existing_file=OverwriteExistingFile.ALWAYS,
        )

        scenarios.append(new_noninteractive_scenario)

        # new_interactive_scenario = create_scenario_for_ego_vehicle_maneuver(
        #     scenario, scenario_config, maneuver, interactive=True
        # )

    return scenarios


__all__ = [
    "pipeline_create_sumo_configuration_for_commonroad_scenario",
    "pipeline_simulate_scenario",
    "GenerateCommonRoadScenariosArguments",
    "pipeline_generate_cr_scenarios",
]
