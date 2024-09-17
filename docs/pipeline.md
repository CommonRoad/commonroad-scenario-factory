# Pipeline

The Scenario Factory is centered around a data processing pipeline. This pipeline is composed of many different pipeline steps which mostly work with CommonRoad scenarios. The pipeline supports three different step types:
* *map*: most basic step type, which receives one input (e.g. a scenario) and has one or a sequence of outputs (e.g. pipeline step to write scenarios to disk)
* *fold*: receives the whole pipeline state as input, and is mostly used for reduce functionality, when one needs to consider all elements in the pipeline.
* *filter*: receives one input and returns a boolean to indicate whether this element should be processed further

## Existing Pipeline Steps

Notation:

* pipeline\_*name*(*value*) [*type*]: A pipeline step with *name* that processes *value* and has the pipeline step type *type* (see list above).
* pipeline\_*name*(*param*, ...)(*value*) [*type*]: A pipeline step with the name *name* that processes *value*, has the pipeline step type *type* (see list above) and takes an extra configuration parameter. The pipeline step method will be partially applied with the parameters, during the pipeline definition.

### CommonRoad Utilities

* pipeline_write_scenario_to_folder(output_folder)(commonroad_scenario) [map]: Write all scenarios to the configured folder
* pipeline_add_metadata_to_scenario(commonroad_scenario) [map]: Populate the metadata fields (author, source, affiliation, tags) according to the configuration
* pipeline_assign_tags_to_scenario(commonroad_scenarios) [map]: assign static and dynamic scenario labels.

### Conversions

* pipeline_convert_osm_map_to_commonroad_scenario(osm_map) [map]: Convert an OpenStreetMap map to a CommonRoad Scenario
* pipeline_extract_osm_map(map_provider, radius)(poi) [map]: Using the given map provider extract the OpenStreetMap map in the radius around the poi
* pipeline_verify_and_repair_commonroad_scenario(commonroad_scenario) [map]: After the conversion from any source to CommonRoad, check the scenario for errors and repair them


### Globetrotter

* pipeline_extract_intersections(commonroad_scenario) [map]: Find all intersections inside a CommonRoad Scenario
* pipeline_filter_lanelet_network(lanelet_network_filter)(commonroad_scenario) [filter]: Filter lanelet networks (in the globetrotter context those are usually intersections) that are invalid or contain unwanted properties
  - NoTrafficLightFilter: Only select intersections that do not contain traffic lights


### Scenario Generation

* pipeline_simulate_scenario_with_sumo(sumo_simulation_configuration) [map]: On a CommonRoad Scenario with a LaneletNetwork, random traffic is generated and simulated with SUMO
* pipeline_find_ego_vehicle_maneuvers(criterions)(commonroad_scenarios) [map]: In a CommonRoad scenario find maneuvers that match any of the given criterions. Criterions can be:
  - EgoVehicleSelectionCriterion (Base class for all criterions -> users can provide their own criterions)
  - AccelerationCriterion
  - BrakingCriterion
  - TurningCriterion
  - LaneChangeCriterion
  - MergingCriterion
* pipeline_select_one_maneuver_per_ego_vehicle(ego_vehicle_maneuvers) [fold]: The criterions might find multiple maneuvers per ego vehicle. This method reduces the total number of maneuvers, to only include the most interesting maneuvers. For this, it needs to consider the whole global state and therefore a fold is required.
* pipeline_filter_ego_vehicle_maneuver(filter)(ego_vehicle_maneuver) [filter]: Select interesting ego vehicle maneuvers. Can be parameterized with one filter (for multiple filters, multiple invocations are needed)
  - EgoVehicleFilter (Base class for all filters -> users can provide their own filters)
  - LongEnoughManeuverFilter
  - MinimumVelocityFilter
  - InterestingLaneletNetworkFilter
  - EnoughSurroundingVehiclesFilter
* pipeline_generate_scenario_for_ego_vehicle_maneuver(ego_vehicle_maneuver) [map]: Create a new CommonRoad scenario that starts at the ego vehicle maneuver and has a planning problem for the selected ego vehicle from the maneuver

## Develop custom pipeline steps

It's easy to develop custom pipeline steps:

```python
from scenario_factory.pipeline import pipeline_map, PipelineContext
from scenario_factory.scenario_types import ScenarioContainer

@pipeline_map()
def pipeline_example(ctx: PipelineContext, scenario_container: ScenarioContainer) -> ScenarioContainer:
  # Do something with the scenario
  return scenario_container

```

### Working with Scenarios

> TL;DR: always use `ScenarioContainer`s as input and output for your pipeline steps.

The main focus in the scenario-factory are, as the name implies, CommonRoad Scenarios. Therefore, most pipeline steps take scenarios as inputs and also output one or more scenario. Nevertheless, many steps require or output not only a scenario, but also additional data, like a planning problem. To keep pipeline steps reusable and simple, scenarios should always be wrapped in `ScenarioContainer`s.

To see why this is necessary, consider the following steps as an example:

* pipeline_create_planning_problems
* pipeline_add_metadata
* pipeline_write_scenario_to_file

The step `pipeline_create_planning_problems` will create planning problems for a given scenario. As such, it will return a planning problem alongside its input scenario. The next step `pipeline_add_metadata`, populates the metadata fields (e.g. author) of the scenario. For this  only cares about the scenario, and not any planning problems. In the last step `pipeline_write_scenario_to_file`, the scenario *and* the planning problem should be written to a file. For this purpose, the last step requires the planning problem and the scenario as input.

To effectively work with scenarios Scenario Factory, a few requirements arise regarding CommonRoad scenarios:
* It must be easy to associate additional data with a CommonRoad scenario (e.g. a planning problem)
* Pipeline steps should be as reusable as possible by being agnostic of such additional data

For this purpose `ScenarioContainer`s are used as inputs and outputs for most of the pipeline steps. By default, a `ScenarioContainer` wraps a simple CommonRoad scenario, but additional containers exist to accommodate additional objects like `PlanningProblem`s or `PlanningProblemSolution`s. Your pipeline step should always accept the least specific `ScenarioContainer`.
