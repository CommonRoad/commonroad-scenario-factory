import re
from pathlib import Path
from typing import Optional

from commonroad.scenario.scenario import ScenarioID

from scenario_factory.pipeline import Pipeline
from scenario_factory.pipeline_steps import (
    pipeline_compute_waymo_metrics,
)
from scenario_factory.scenario_container import (
    load_scenarios_from_folder,
    write_waymo_metrics_of_scenario_containers_to_csv,
)

scenarios_path = Path("../cr-ots-interface/resources/simulations/")
reference_scenarios_path = Path("../cr-ots-interface/resources/abstractions/")

pipeline = Pipeline()
pipeline.map(pipeline_compute_waymo_metrics)


def find_reference_scenario(scenario_id: ScenarioID) -> Optional[Path]:
    references = {
        "DEU_MONAEast-2": "C-DEU_MONAEast-2_1_T-299",
        "DEU_MONAMerge-2": "C-DEU_MONAMerge-2_1_T-299",
        "DEU_MONAWest-2": "C-DEU_MONAWest-2_1_T-299",
        "DEU_LocationCLower4-1": "DEU_LocationCLower4-1_48255_T-9754",
        "DEU_AachenHeckstrasse-1": "DEU_AachenHeckstrasse-1_3115929_T-17428",
    }
    reference = references[re.match(r"^[^_]+_[^_]+", str(scenario_id)).group(0)]  # type: ignore
    scenario_path = reference_scenarios_path.joinpath(f"{reference}.xml")
    return scenario_path


scenario_containers = load_scenarios_from_folder(
    Path("../cr-ots-interface/resources/simulations/"), find_reference_scenario
)
print(scenario_containers)
result = pipeline.execute(scenario_containers)

write_waymo_metrics_of_scenario_containers_to_csv(result.values, Path("/tmp/waymo_metrics.csv"))
