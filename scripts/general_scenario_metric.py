from pathlib import Path

from resources.paper.frame_factors import get_frame_factor_orig
from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import (
    pipeline_compute_single_scenario_metrics,
    pipeline_remove_parked_dynamic_obstacles,
)
from scenario_factory.scenario_container import (
    load_scenarios_from_folder,
    write_general_scenario_metrics_of_scenario_containers_to_csv,
)

pipeline = Pipeline()
pipeline.map(pipeline_remove_parked_dynamic_obstacles).map(
    pipeline_compute_single_scenario_metrics(get_frame_factor_orig)
)

scenario_containers = load_scenarios_from_folder(
    Path(__file__).parents[1].joinpath("resources/paper/"),
)

result = pipeline.execute(scenario_containers)

write_general_scenario_metrics_of_scenario_containers_to_csv(
    result.values, Path("/tmp/general_scenario_metrics_orig.csv")
)
