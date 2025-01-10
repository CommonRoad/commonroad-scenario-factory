from pathlib import Path

from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.visualization.mp_renderer import MPRenderer
from commonroad_crime.data_structure.configuration import CriMeConfiguration, GeneralConfiguration
from commonroad_crime.measure import TTC

from scenario_factory.globetrotter import Coordinates, OsmApiMapProvider, RegionMetadata
from scenario_factory.pipeline_steps import (
    pipeline_add_metadata_to_scenario,
    pipeline_assign_tags_to_scenario,
    pipeline_simulate_scenario_with_sumo,
    pipeline_write_scenario_to_file,
)
from scenario_factory.pipelines import (
    create_globetrotter_pipeline,
    create_scenario_generation_pipeline,
)
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.simulation import (
    SimulationConfig,
    SimulationMode,
)

output_path = Path("/tmp/use_case")
output_path.mkdir(parents=True, exist_ok=True)

# Get map (Autobahn, near Garching)
coords = "48.264165183714745, 11.64459089457302"  # Garching
# coords = "48.149733892917766, 11.569386416327045"  # Central
simulation_config = SimulationConfig(
    mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_steps=600
)
globetrotter_pipeline = (
    create_globetrotter_pipeline(0.2, OsmApiMapProvider())
    .map(pipeline_add_metadata_to_scenario)
    # .map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    .map(pipeline_simulate_scenario_with_sumo(simulation_config))
)
globetrotter_inputs = [RegionMetadata.from_coordinates(Coordinates.from_str(coords))]

# Create scenarios (10 scenarios)
scenario_config = ScenarioFactoryConfig(seed=1234, cr_scenario_time_steps=150)
scenario_generation_pipeline = create_scenario_generation_pipeline(
    scenario_config.criterions, scenario_config.filters
).map(pipeline_assign_tags_to_scenario)

pipeline = globetrotter_pipeline.chain(scenario_generation_pipeline).map(
    pipeline_write_scenario_to_file(output_path)
)
result = pipeline.execute(globetrotter_inputs)
result.print_cum_time_per_step()

# plotting and criticality
path = Path("/tmp/use_case/DEU_Garching-2_1_T-21.cr.xml")
scenario, _ = CommonRoadFileReader(path).open(lanelet_assignment=True)

rnd = MPRenderer(figsize=(18, 10))
rnd.draw_params.time_begin = 0
rnd.draw_params.time_end = 0
rnd.draw_params.axis_visible = False
rnd.draw_params.dynamic_obstacle.draw_icon = True
scenario.draw(rnd)
rnd.draw_params.dynamic_obstacle.vehicle_shape.occupancy.shape.facecolor = "orange"
rnd.draw_params.dynamic_obstacle.vehicle_shape.occupancy.shape.edgecolor = "black"
scenario._dynamic_obstacles[18].draw(rnd)
rnd.render(show=True, filename="/tmp/paper/use_case.svg")
# tikzplotlib.save("/tmp/paper/use_case.tikz")
#
crime_config = CriMeConfiguration(
    GeneralConfiguration(
        str(path.parent) + "/",
    )
)
crime_config.update(
    ego_id=18,
    sce=scenario,
)
#
evaluator = TTC(crime_config)
for k in range(
    len(scenario.obstacle_by_id(crime_config.vehicle.ego_id).prediction.trajectory.state_list)
):
    print(evaluator.compute(10, k))
