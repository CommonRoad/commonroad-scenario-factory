import pathlib
import scenario_factory
from copy import deepcopy
from scenario_factory.globetrotter.clustering import generate_intersections
from scenario_factory.globetrotter.plotting import plot_scenario
from scenario_factory.globetrotter.globetrotter_io import commonroad_parse, osm2commonroad, save_intersections


# write commonroad file
osm_file = pathlib.Path(scenario_factory.__file__).parent.joinpath("../example_files/osm/campus_garching.osm")
commonroad_file = pathlib.Path(scenario_factory.__file__).parent.joinpath("../output/osm/DEU_Garching.xml")
commonroad_file.parent.mkdir(parents=True, exist_ok=True)

osm2commonroad(osm_file, commonroad_file)

# visualization
scenario, forking_points = commonroad_parse(commonroad_file)
plot_scenario(scenario)

# find intersections
scenario, forking_points = commonroad_parse(commonroad_file)

intersections, clustering_result = generate_intersections(scenario, forking_points)

output_dir = deepcopy(commonroad_file).parent.joinpath(commonroad_file.stem)
output_dir.mkdir(parents=True, exist_ok=True)
save_intersections(intersections, output_dir, output_dir.stem)

# plotting
intersection0, _ = commonroad_parse(output_dir.joinpath(f"{output_dir.stem}-0.xml"))
plot_scenario(intersection0)
