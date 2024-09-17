# Develop custom pipeline steps

```python
@pipeline_map()

```

## Working with Scenarios

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
