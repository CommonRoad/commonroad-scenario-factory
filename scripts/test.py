import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile

from scenario_factory.builder.scenario_builder import ScenarioBuilder
from scenario_factory.simulation.config import SimulationConfig, SimulationMode
from scenario_factory.simulation.ots import simulate_commonroad_scenario_with_ots
from scenario_factory.simulation.sumo import simulate_commonroad_scenario_with_sumo
from scenario_factory.utils import configure_root_logger

configure_root_logger(logging.DEBUG)

scenario_builder = ScenarioBuilder()
lanelet_network_builder = scenario_builder.create_lanelet_network()
lanelet1 = lanelet_network_builder.add_lanelet(start=(0.0, 0.0), end=(0.0, 10.0))
lanelet2 = lanelet_network_builder.add_adjacent_lanelet(lanelet1, side="left", same_direction=False)
lanelet3 = lanelet_network_builder.add_lanelet(start=(0.0, 30.0), end=(0.0, 40.0))
lanelet4 = lanelet_network_builder.add_adjacent_lanelet(lanelet3, side="left", same_direction=False)
lanelet5 = lanelet_network_builder.add_lanelet(start=(10.0, 18.0), end=(20.0, 18.0))
lanelet6 = lanelet_network_builder.add_adjacent_lanelet(lanelet5, side="left", same_direction=False)
lanelet_network_builder.create_straight_connecting_lanelet(lanelet1, lanelet3)
lanelet_network_builder.create_straight_connecting_lanelet(lanelet4, lanelet2)
lanelet_network_builder.create_curved_connecting_lanelet(lanelet1, lanelet5)
lanelet_network_builder.create_curved_connecting_lanelet(lanelet4, lanelet5)
lanelet_network_builder.create_curved_connecting_lanelet(lanelet6, lanelet2)
lanelet_network_builder.create_curved_connecting_lanelet(lanelet6, lanelet3)
intersection_builder = lanelet_network_builder.create_intersection()
intersection_builder.create_incoming().add_incoming_lanelet(lanelet1).connect_straight(
    lanelet3
).connect_right(lanelet5)
intersection_builder.create_incoming().add_incoming_lanelet(lanelet4).connect_straight(
    lanelet2
).connect_left(lanelet5)
intersection_builder.create_incoming().add_incoming_lanelet(lanelet6).connect_left(
    lanelet2
).connect_right(lanelet3)
lanelet_network_builder.create_traffic_light().for_lanelet(
    lanelet1
).use_default_cycle().set_cycle_offset(0)
lanelet_network_builder.create_traffic_light().for_lanelet(
    lanelet4
).use_default_cycle().set_cycle_offset(0)
traffic_light = (
    lanelet_network_builder.create_traffic_light()
    .for_lanelet(lanelet6)
    .use_default_cycle()
    .set_cycle_offset(60)
    .build()
)
scenario = scenario_builder.build()


simulation_config = SimulationConfig(
    mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=600
)
with TemporaryDirectory() as tempdir:
    simulated_scenario = simulate_commonroad_scenario_with_ots(scenario, simulation_config, seed=10)
assert simulated_scenario is not None

CommonRoadFileWriter(
    simulated_scenario, None, author="", affiliation="", source="", tags=set()
).write_scenario_to_file("/tmp/test.cr.xml", OverwriteExistingFile.ALWAYS)
