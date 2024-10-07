# Pipeline

The Scenario Factory is centered around a data processing pipeline. This pipeline is composed of many different pipeline steps which mostly work with CommonRoad scenarios. The pipeline supports three different step types:

* __map__: most basic step type, which receives one input (e.g. a scenario) and has one or a sequence of outputs (e.g. pipeline step to write scenarios to disk)
* __fold__: receives the whole pipeline state as input, and is mostly used for reduce functionality, when one needs to consider all elements in the pipeline.
* __filter__: receives one input and returns a boolean to indicate whether this element should be processed further

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

### Pipeline Step Concurrency and Parallelism Modes

The pipeline provides seamless concurrency and parallelism to all pipeline steps it executes. This means that
Generally 3 modes are supported:

* __Concurrent__: The preferred mode of execution for each pipeline step. This distributes all tasks on a thread pool and execute the steps in a semi-parallel manner.
* __Parallel__: Real parallelism, which should be used for tasks that cannot be run concurrently or which are long running. This distributes the tasks on a process pool and executes the steps in a true-parallel manner.
* __Sequential__: Runs the tasks on the main thread and does not allow any other tasks to be run at the same time.

By default, each pipeline step is concurrent, but you can change this on a per step basis by setting the `mode` argument in the decorator:

```python
from scenario_factory.pipeline import PipelineContext, PipelineStepMode, pipeline_map
from scenario_factory.scenario_types import ScenarioContainer

@pipeline_map(mode=PipelineStepMode.PARALLEL)
def pipeline_foo(ctx: PipelineContext, scenario_container: ScenarioContainer) -> ScenarioContainer:...

```

Generally, if you don't have any problems with running your step concurrently, there is no need to change it. But if e.g. you interface with a simulator that is executed in the current python process (e.g. SUMO with its libsumo), you must change its mode to parallel or sequential. Otherwise, your pipeline step will fail.

Additionally, you can disable concurrency and parallelism for each execution:

```python
pipeline = Pipeline()
...
pipeline.execute(input_values, num_threads=None, num_processes=None)
```

This way, even steps that would otherwise be executed concurrently or in parallel will be executed sequentially on the main thread. This is also the default behavior for `fold` steps.


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
