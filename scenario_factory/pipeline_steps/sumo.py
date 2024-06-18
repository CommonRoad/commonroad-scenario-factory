import shutil
from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable, Optional

from commonroad.scenario.scenario import Scenario
from crdesigner.map_conversion.sumo_map.config import SumoConfig
from crdesigner.map_conversion.sumo_map.cr2sumo.converter import CR2SumoMapConverter
from sumocr.interface.sumo_simulation import SumoSimulation
from sumocr.scenario.scenario_wrapper import ScenarioWrapper

from scenario_factory.config_files.scenario_config import ScenarioConfig
from scenario_factory.cr_scenario_factory import ScenarioFactory
from scenario_factory.generate_senarios import (
    convert_commonroad_scenario_to_sumo,
    generate_random_traffic_on_sumo_network,
)
from scenario_factory.pipeline import PipelineContext, PipelineStepArguments, pipeline_map, pipeline_map_with_args
from scenario_factory.scenario_checker import DeleteScenario


@pipeline_map
def pipeline_create_sumo_configuration_for_commonroad_scenario(
    ctx: PipelineContext, commonroad_scenario: Scenario
) -> CR2SumoMapConverter:
    output_folder = ctx.get_output_folder("output")
    cr2sumo = convert_commonroad_scenario_to_sumo(commonroad_scenario, output_folder)
    return cr2sumo


@dataclass
class GenerateRandomTrafficArguments(PipelineStepArguments):
    scenarios_per_map: int


@pipeline_map_with_args
def pipeline_generate_random_traffic(
    args: GenerateRandomTrafficArguments, ctx: PipelineContext, cr2sumo: CR2SumoMapConverter
) -> Iterable[ScenarioWrapper]:
    output_folder = ctx.get_output_folder("output")
    intermediate_sumo_files_path = output_folder.joinpath("intermediate", str(cr2sumo.initial_scenario.scenario_id))
    sumo_net_path = intermediate_sumo_files_path.joinpath(str(cr2sumo.initial_scenario.scenario_id) + ".net.xml")
    for i in range(args.scenarios_per_map):
        scenario = deepcopy(cr2sumo.initial_scenario)
        sumo_conf = deepcopy(cr2sumo.conf)

        scenario.scenario_id.configuration_id = i + 1
        scenario_name = str(scenario.scenario_id)
        sumo_conf.scenario_name = scenario_name
        cr2sumo_map_converter = CR2SumoMapConverter(scenario, sumo_conf)
        scenario_dir_name = intermediate_sumo_files_path.joinpath(scenario_name)
        if scenario_dir_name.exists():
            shutil.rmtree(scenario_dir_name)
        scenario_dir_name.mkdir(parents=True)
        sumo_net_copy = scenario_dir_name.joinpath(scenario_name + ".net.xml")
        shutil.copy(sumo_net_path, sumo_net_copy)  # copy sumo net file into scenario-specific sub-folder

        cr2sumo_map_converter.conf.random_seed = ctx.seed
        cr2sumo_map_converter.conf.random_seed_trip_generation = ctx.seed
        yield generate_random_traffic_on_sumo_network(cr2sumo_map_converter, sumo_net_copy)


@pipeline_map
def pipeline_simulate_scenario(ctx: PipelineContext, scenario_wrapper: ScenarioWrapper) -> Scenario:
    sumo_conf = SumoConfig()
    sumo_conf.simulation_steps = 300
    sumo_sim = SumoSimulation()
    sumo_sim.initialize(sumo_conf, scenario_wrapper)

    for _ in range(sumo_conf.simulation_steps):
        sumo_sim.simulate_step()
    sumo_sim.simulate_step()

    sumo_sim.stop()

    scenario = sumo_sim.commonroad_scenarios_all_time_steps()

    return scenario


@dataclass
class GenerateCommonRoadScenariosArguments(PipelineStepArguments):
    create_noninteractive: bool
    create_interactive: bool
    max_collisions: Optional[int] = None


@pipeline_map_with_args
def pipeline_generate_cr_scenarios(
    args: GenerateCommonRoadScenariosArguments, ctx: PipelineContext, scenario: Scenario
) -> Scenario:
    sumo_conf = SumoConfig.from_scenario(scenario)
    sumo_conf.simulation_steps = 300
    scenario_config = ScenarioConfig()
    output_path = ctx.get_output_folder("output")
    print(f"Generating Scenarios for {scenario.scenario_id}")

    scenario_factory = ScenarioFactory(
        scenario,
        sumo_conf.simulation_steps,
        scenario_config,
        "",
    )

    num_collisions = len(scenario_factory.delete_colliding_obstacles(all=True))
    if args.max_collisions is not None:
        if num_collisions > args.max_collisions:
            raise RuntimeError(
                f"Skipping scenario {scenario.scenario_id} because it has {num_collisions}, but the maximum allowed number of collisions is {args.max_collisions}"
            )

    scenario_factory.generate_commonroad_scenarios()

    if args.create_noninteractive:
        output_noninteractive = output_path.joinpath("noninteractive")
        output_noninteractive.mkdir(parents=True, exist_ok=True)
        scenario_factory.write_cr_file_and_video(
            create_video=False,
            check_validity=False,  # TODO set True
            output_path=output_noninteractive,
        )

    if args.create_interactive:
        raise RuntimeError("Creating interactive scenarios is currently not possible")
        # output_interactive = output_path.joinpath("interactive")
        # output_interactive.mkdir(parents=True, exist_ok=True)
        scenario_nr_added += scenario_factory.write_interactive_scenarios_and_videos()
        #     scenario_counter_prev,
        #     sumo_sim.ids_cr2sumo[SUMO_VEHICLE_PREFIX],
        #     sumo_net_path=sumo_net_copy,
        #     rou_files=rou_files,
        #     config=sumo_conf_tmp,
        #     default_config=InteractiveSumoConfigDefault(),
        #     create_video=False,
        #     check_validity=False,  # TODO set True
        #     output_path=output_interactive,
        # )

    return True

def pipeline_write_interactive_scenarios(ctx: PipelineContext) -> Tuple[Scenario, PlanningProblemSet]


__all__ = [
    "pipeline_create_sumo_configuration_for_commonroad_scenario",
    "pipeline_generate_random_traffic",
    "pipeline_simulate_scenario",
    "GenerateCommonRoadScenariosArguments",
    "pipeline_generate_cr_scenarios",
    "GenerateRandomTrafficArguments",
]
