# CommonRoad Scenario Factory

[![PyPI pyversions](https://img.shields.io/pypi/pyversions/commonroad-scenario-factory.svg)](https://pypi.python.org/pypi/commonroad-scenario-factory/)
[![PyPI version fury.io](https://badge.fury.io/py/commonroad-scenario-factory.svg)](https://pypi.python.org/pypi/commonroad-scenario-factory/)
[![PyPI download month](https://img.shields.io/pypi/dm/commonroad-scenario-factory.svg?label=PyPI%20downloads)](https://pypi.python.org/pypi/commonroad-scenario-factory/)
[![PyPI license](https://img.shields.io/pypi/l/commonroad-scenario-factory.svg)](https://pypi.python.org/pypi/commonroad-scenario-factory/)


The CommonRoad Scenario Factory is a toolbox that combines many different tools from the whole CommonRoad ecosystem to efficiently process CommonRoad scenarios.
Its current main use case is the generation of new CommonRoad scenarios with the traffic simulators OpenTrafficSim (OTS) and SUMO.


## Quick Start

### Installation

The CommonRoad Scenario Factory is available on PyPI and can be easily installed with pip:

```sh
$ pip install commonroad-scenario-factory
```

#### Additional Requirements

Most required dependencies are already included, but some have to be installed manually on your system:

* [Java Runtime Environment](https://www.java.com/en/): Required for running simulations with OpenTrafficSim (OTS).
* [osmium](https://osmcode.org/osmium-tool/): Required for extracting segments from pre-downloaded OSM maps.

SUMO and OTS are distributed as python packages and included as dependencies. Therefore, they do not need to be installed separately.

### Example Usage

This example will setup a basic scenario generation pipeline with SUMO and output new scenarios to `/tmp/scenario-factory`:

```python
from pathlib import Path

from scenario_factory.globetrotter import Coordinates, OsmApiMapProvider, RegionMetadata
from scenario_factory.pipelines import (
    create_globetrotter_pipeline,
    create_scenario_generation_pipeline,
)
from scenario_factory.pipeline_steps import (
    pipeline_add_metadata_to_scenario,
    pipeline_simulate_scenario_with_sumo,
    pipeline_assign_tags_to_scenario,
    pipeline_write_scenario_to_file,
)
from scenario_factory.scenario_config import ScenarioFactoryConfig
from scenario_factory.simulation import SimulationConfig, SimulationMode

radius = 0.1
seed = 5678
simulation_steps = 500
cr_scenario_time_steps = 50
coords_str = "48.2570465,11.6580003"
output_path = Path("/tmp/scenario-factory")
output_path.mkdir(exist_ok=True)


map_provider = OsmApiMapProvider()
simulation_config = SimulationConfig(
    mode=SimulationMode.RANDOM_TRAFFIC_GENERATION,
    simulation_steps=simulation_steps,
    seed=seed,
)
scenario_config = ScenarioFactoryConfig(
    seed=seed, cr_scenario_time_steps=cr_scenario_time_steps, source="example"
)

base_pipeline = (
    create_globetrotter_pipeline(radius, map_provider)
    .map(pipeline_add_metadata_to_scenario)
    .map(pipeline_simulate_scenario_with_sumo(simulation_config))
)

scenario_generation_pipeline = create_scenario_generation_pipeline(
    scenario_config.criterions, scenario_config.filters
)

pipeline = (
    base_pipeline.chain(scenario_generation_pipeline)
    .map(pipeline_assign_tags_to_scenario)
    .map(pipeline_write_scenario_to_file(output_path))
)

coordinates = Coordinates.from_str(coords_str)
region = RegionMetadata.from_coordinates(coordinates)

print(f"Starting scenario generation for coordinates {coords_str}.")
result = pipeline.execute([region], num_threads=2, num_processes=2)
result.print_cum_time_per_step()
print(f"Generated {len(result.values)} scenario(s) at {output_path}.")
```

## Documentation

The full documentation can be found at [cps.pages.gitlab.lrz.de/commonroad/scenario-factory](https://cps.pages.gitlab.lrz.de/commonroad/scenario-factory/).
