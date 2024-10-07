# Develop a Custom Pipeline Step

In this tutorial you will learn how to create your own pipeline steps and how to use them in a pipeline.

## A Minimal Pipeline Step

Let's start by creating a `tutorial.py` file in the root of the scenario factory repo. Then copy in the following code snippet to define a new pipeline step `pipeline_hello_world`:

```python linenums="1"
import logging

from scenario_factory.pipeline import pipeline_map, PipelineContext
from scenario_factory.scenario_types import ScenarioContainer

# Make sure that we can log messages
configure_root_logger(logging.INFO)
_LOGGER = logging.getLogger("tutorial")

@pipeline_map()
def pipeline_hello_world(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> None:
    _LOGGER.info("Hello World")

```

This pipeline step `pipeline_hello_world` simply logs "Hello World". Because this is a `map` pipeline step (read more about pipeline step types [here](/reference/pipeline)), our pipeline step will be called for each input element in the pipeline. This means that if we initialize our pipeline with 3 elements (scenarios in this case), our pipeline step would print "Hello World" 3 times.


## Use the Pipeline Step

To use the newly created pipeline step `pipeline_hello_world`, we have to create a pipeline, add the step to it and execute the pipeline. Update the `tutorial.py` file, to include the changes from the following snippet:

```python linenums="1"
import logging

from scenario_factory.pipeline import Pipeline, pipeline_map, PipelineContext
from scenario_factory.scenario_types import (
    ScenarioContainer,
    load_scenarios_from_folder,
)
from scenario_factory.utils import configure_root_logger
from tests.resources import ResourceType

...

# Create an empty pipeline without any steps
pipeline = Pipeline()
# Add our pipeline_hello_world step as the only step for the pipeline
pipeline.map(pipeline_hello_world)


# Load some pre-defined scenarios
input_scenarios = load_scenarios_from_folder(
  ResourceType.COMMONROAD_SCENARIO.get_folder() # (1)
)
pipeline.execute(input_scenarios)
```

1. The `ResourceType` enum is a helper normally used for testing, that contains ready to use scenarios.

Now when you execute the `tutorial.py` file, you should see "Hello World" being printed 3 times on the console, once for each scenario that was loaded:

```sh
$ poetry run python tutorial.py
...
2024-10-02 14:32:25,530 | INFO | tutorial | Hello World
2024-10-02 14:32:25,530 | INFO | tutorial | Hello World
2024-10-02 14:32:25,530 | INFO | tutorial | Hello World
```

> Note: You might see some warning messages regarding traffic signs, but you can safely ignore those

## Process the Input Values

Currently, our pipeline step receives the `scenario_container` argument but does not use it any further. Let's change that, by updating our pipeline step:

```python linenums="11"
...
@pipeline_map()
def pipeline_hello_world(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> None:
    commonroad_scenario = scenario_container.scenario
    _LOGGER.info("Processing CommonRoad Scenario %s in 'pipeline_hello_world'", commonroad_scenario.scenario_id)
...
```

Now, when we execute the pipeline, it will no longer log "Hello World", but instead log the message with the scenario ID for each individual scenario:

```sh
$ poetry run python tutorial.py
...
2024-10-02 14:47:20,247 | INFO | tutorial | Processing CommonRoad Scenario DZA_Annaba-7
2024-10-02 14:47:20,248 | INFO | tutorial | Processing CommonRoad Scenario MDG_Toamasina-3
2024-10-02 14:47:20,248 | INFO | tutorial | Processing CommonRoad Scenario BWA_Tlokweng-6
```

In the example above, the pipeline step receives a `ScenarioContainer` instead of a CommonRoad `Scenario`. The `ScenarioContainer` wraps the scenario along with additional data, such as planning problems that are associated with a specific scenario. You can learn more about scenario containers and why they are used [here](reference/pipeline/#working-with-scenarios). But in short, using containers simplifies writing generalized pipeline steps without having to worry whether the scenario has additional data.

## Return Value(s)

Usually, a `map` pipeline step receives a scenario container as input, processes the input and also returns something. If a `map` pipeline step returns nothing (like `pipeline_hello_world` currently) or explicitly `None`, no consecutive pipeline step will be executed for this value. Assume, you add another pipeline step `pipeline_super_cool_functionality` which should be executed after `pipeline_hello_world`:

```python linenums="19" hl_lines="2-7 11"
...
@pipeline_map()
def pipeline_super_cool_functionality(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> None:
    commonroad_scenario = scenario_container.scenario
    _LOGGER.info("Processing CommonRoad Scenario %s in 'pipeline_super_cool_functionality'", commonroad_scenario.scenario_id)
...
pipeline = Pipeline()
pipeline.map(pipeline_hello_world)
pipeline.map(pipeline_super_cool_functionality)
...
```
If you execute the pipeline, you will see that the messages from `pipeline_hello_world` are logged but no messages from `pipeline_super_cool_functionality`:
```sh
$ poetry run python tutorial.py
...
2024-10-02 15:07:01,907 | INFO | tutorial | Processing CommonRoad Scenario DZA_Annaba-7 in 'pipeline_hello_world'
2024-10-02 15:07:01,908 | INFO | tutorial | Processing CommonRoad Scenario MDG_Toamasina-3 in 'pipeline_hello_world'
2024-10-02 15:07:01,908 | INFO | tutorial | Processing CommonRoad Scenario BWA_Tlokweng-6 in 'pipeline_hello_world'
```

To make sure the execution of the pipeline can carry on, a value must be returned from each pipeline step:

```python linenums="11" hl_lines="4 10 15 21"
@pipeline_map()
def pipeline_hello_world(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    commonroad_scenario = scenario_container.scenario
    _LOGGER.info(
        "Processing CommonRoad Scenario %s in 'pipeline_hello_world'",
        commonroad_scenario.scenario_id,
    )
    return scenario_container

@pipeline_map()
def pipeline_super_cool_functionality(
    ctx: PipelineContext, scenario_container: ScenarioContainer
) -> ScenarioContainer:
    commonroad_scenario = scenario_container.scenario
    _LOGGER.info(
        "Processing CommonRoad Scenario %s in 'pipeline_super_cool_functionality'",
        commonroad_scenario.scenario_id,
    )
    return scenario_container
```

Now if you execute the pipeline again, you will see that both steps log their messages:
```sh
$ poetry run python tutorial.py
2024-10-02 15:14:29,907 | INFO | tutorial | Processing CommonRoad Scenario DZA_Annaba-7 in 'pipeline_hello_world'
2024-10-02 15:14:29,909 | INFO | tutorial | Processing CommonRoad Scenario MDG_Toamasina-3 in 'pipeline_hello_world'
2024-10-02 15:14:29,909 | INFO | tutorial | Processing CommonRoad Scenario DZA_Annaba-7 in 'pipeline_super_cool_functionality'
2024-10-02 15:14:29,909 | INFO | tutorial | Processing CommonRoad Scenario MDG_Toamasina-3 in 'pipeline_super_cool_functionality'
2024-10-02 15:14:29,909 | INFO | tutorial | Processing CommonRoad Scenario BWA_Tlokweng-6 in 'pipeline_hello_world'
2024-10-02 15:14:29,909 | INFO | tutorial | Processing CommonRoad Scenario BWA_Tlokweng-6 in 'pipeline_super_cool_functionality'
```

> When you execute the pipeline, the order of the log message might be different! This is because the pipeline employs seamless concurrency, which means that each step is distributed on a worker pool and the execution order is not deterministic. The important part here is, that you see log messages from `pipeline_hello_world` and `pipeline_super_cool_functionality`, independent of how they are ordered. [Here](/references/pipeline/#pipeline-step-concurrency-and-parallelism-modes) you can read more about the concurrency behavior of the pipeline.

In the above example, each step receives one input and returns one output value. Sometimes, a pipeline step can return multiple values (e.g. a list of scenarios). To handle such cases, the pipeline will automatically flatten the returned iterable.

## Take Arguments

When your pipeline steps are executed the arguments `ctx` and `scenario_container` are automatically filled in by the pipeline. But sometimes it is desirable to further parameterize the execution of a pipeline step. For this purpose [`pipeline_map_with_args`](/reference/api/pipeline/#scenario_factory.pipeline.pipeline_map_with_args) can be used instead of the [`pipeline_map`](/reference/api/pipeline/#scenario_factory.pipeline.pipeline_map) decorator. This enables you to accept an extra static argument. The argument needs to be supplied once, when the step is attached to the pipeline and will be used for every execution of that step.

```python linenums="1" hl_lines="1 5"
from dataclasses import dataclass

from scenario_factory.pipeline import Pipeline, pipeline_map, pipeline_map_with_args, PipelineContext, PipelineStepArguments

...

@dataclass
class SuperCoolFunctionalityArguments(PipelineStepArguments):
    map_id_selector: int

@pipeline_map_with_args()
def pipeline_super_cool_functionality(args: SuperCoolFunctionalityArguments, ctx: PipelineContext, scenario_container: ScenarioContainer) -> ScenarioContainer:
    commonroad_scenario = scenario_container.scenario
    if commonroad_scenario.scenario_id.map_id == args.map_id_selector:
        _LOGGER.info(
            "Processing CommonRoad Scenario %s in 'pipeline_hello_world'",
            commonroad_scenario.scenario_id,
        )
    return scenario_container

...

pipeline = Pipeline()
pipeline.map(pipeline_hello_world)
pipeline.map(pipeline_super_cool_functionality(SuperCoolFunctionalityArguments(map_id_selector=3)))

```

When you execute the pipeline, you can see that the `pipeline_super_cool_functionality` log message is only logged for the scenario `MDG_Toamasina-3`, because this is the only scenario with a Map ID of 3:

```sh
$ poetry run python tutorial.py
...
2024-10-07 08:59:11,569 | INFO | tutorial | Processing CommonRoad Scenario DZA_Annaba-7 in 'pipeline_hello_world'
2024-10-07 08:59:11,572 | INFO | tutorial | Processing CommonRoad Scenario MDG_Toamasina-3 in 'pipeline_hello_world'
2024-10-07 08:59:11,572 | INFO | tutorial | Processing CommonRoad Scenario MDG_Toamasina-3 in 'pipeline_super_cool_functionality'
2024-10-07 08:59:11,572 | INFO | tutorial | Processing CommonRoad Scenario BWA_Tlokweng-6 in 'pipeline_hello_world'

```

You can also try to change the `map_id_selector` (e.g. to 6) to observe, how the behavior changes.

## Filter Individual Values

In the previous section, we used a `map` step to filter values. Because filtering is a common action, the pipeline has an extra step type just for filters. A filter must be indicated by the `pipeline_filter` decorator:

```python linenums="1"
from abc import ABC, abstractmethod

from scenario_factory.pipeline import (
    Pipeline,
    pipeline_map,
    pipeline_map_with_args,
    pipeline_filter,
    PipelineStepArguments,
    PipelineContext,
)

...

class ScenarioIdFilter(ABC):
    @abstractmethod
    def matches(self, scenario_id: ScenarioID) -> bool:
        ...

@pipeline_filter()
def pipeline_scenario_id_filter(predicate: ScenarioIdFilter, ctx: PipelineContext, scenario_container: ScenarioContainer) -> bool:
    return predicate.matches(scenario_container.scenario.scenario_id)

...
```

Similar to the `pipeline_map_with_args`, a filter takes 3 arguments and is pre-conditioned with the filter predicate. The filter step itself does not perform any filtering, but instead defers this to the filter predicate. Usually, a pipeline filter only defines the data type on which it filters and the base class for the filter predicate. This way, many different filters can be defined while the number of total pipeline steps is kept to a minimum and code duplication is reduced. Additionally, this allows users to easily define custom filter predicates, without having to write steps for each filter.

Concrete filter predicates are defined as subclasses of the filter predicate type that the pipeline step accepts:

```python

...

class IsOddMapIdFilter(ScenarioIdFilter):
    def matches(self, scenario_id: ScenarioID) -> bool:
        return scenario_id.map_id % 2 != 0

...

pipeline = Pipeline()
pipeline.filter(pipeline_scenario_id_filter(IsOddMapIdFilter()))
pipeline.map(pipeline_hello_world) # (1)

...
```

1. Make sure to remove the `pipeline_super_cool_functionality` map step and only keep the `pipeline_hello_world` step!


If you execute the new pipeline, you should only see log messages for scenarios with an odd map ID:

```sh
$ poetry run python tutorial.py
...
2024-10-07 09:50:11,459 | INFO | tutorial | Processing CommonRoad Scenario DZA_Annaba-7 in 'pipeline_hello_world'
2024-10-07 09:50:11,460 | INFO | tutorial | Processing CommonRoad Scenario MDG_Toamasina-3 in 'pipeline_hello_world'
```

## Global Filters and Reduce/Fold Operations

Filters are applied to each individual item in the pipeline. When multiple filters are used, they basically act as an `and` operation, because each filter must match, so that the item is processed further. Additionally, filters can only consider one element. For some applications it might be necessary, to implement `or` operations or to compare items to each other (e.g. select the 10 most interesting scenarios). While the first problem can be circumvented, by employing `map` steps, the later one cannot. For this purpose `fold` steps exist, which can process the entire pipeline stack at once, instead of each item individually.

> Caution: Because fold/reduce steps receive the whole pipeline stack, they might introduce a major performance penalty! So use them, only if necessary!

```python

@pipeline_fold()
def pipeline_select_most_interesting_

```


## The Pipeline Context

Each pipeline step must take a `PipelineContext` as its first argument. This context allows pipeline steps to access context information about the current pipeline execution or create temporary files.

### Access the Scenario Factory Config

The `PipelineContext` exposes the `ScenarioFactoryConfig` object, which can be accessed by pipeline steps to retrieve configuration values. This exists mostly due to legacy reasons, and if your step takes arguments you should prefer the `pipeline_<>_with_args` decorators.

### Creating with Temporary Files

To correctly interact with some CommonRoad utilities or external projects, you might need to create extra files. For example, to simulate a scenario with SUMO the CommonRoad Scenario must be converted to SUMO first. To make sure that

```python
...
@pipeline_map()
def pipeline_
...
```
