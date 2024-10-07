# Pipeline

The Scenario Factory is centered around a data processing pipeline. This pipeline is composed of many different pipeline steps which mostly work with CommonRoad scenarios. The pipeline supports three different step types:

* __map__: most basic step type, which receives one input (e.g. a scenario) and has one or a sequence of outputs (e.g. pipeline step to write scenarios to disk)
* __fold__: receives the whole pipeline state as input, and is mostly used for reduce functionality, when one needs to consider all elements in the pipeline.
* __filter__: receives one input and returns a boolean to indicate whether this element should be processed further

## Existing Pipeline Steps

A list of all existing pipeline steps can be found [here](../api/pipeline_steps)

## Pipeline Step Concurrency and Parallelism Modes

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


## Working with Scenarios

!!! tip "TL;DR"
    always use `ScenarioContainer`s as input and output for your pipeline steps.

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
