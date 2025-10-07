# Customize the Scenario Generation Pipeline

!!! abstract
    In this guide, you will learn how you can customize the standard scenario generation pipeline to adjust it to your needs.

## The Standard Scenario Generation Pipeline

As a starting point we will use the standard scenario generation pipeline that is available through the CLI (the imports were omitted for brevity):

```python linenums="25"
...
output_path = Path("/tmp/scenario_factory")
output_path.mkdir(exist_ok=True)
cities_file = Path("./files/cities_selected.csv")
input_maps_folder = Path("input_maps")
radius = 0.3
seed = 100

random.seed(seed)
np.random.seed(seed)

scenario_factory_config = ScenarioFactoryConfig(
    seed=seed, cr_scenario_time_steps=75
)
with TemporaryDirectory() as temp_dir:
    ctx = PipelineContext(Path(temp_dir), scenario_factory_config)

    map_provider = select_osm_map_provider(radius, input_maps_folder)

    base_pipeline = (
        create_globetrotter_pipeline(radius, map_provider) # (1)
        .map(pipeline_add_metadata_to_scenario)
        .map(pipeline_simulate_scenario_with_sumo(SimulationConfig(mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_length=600)))
    )

    scenario_generation_pipeline = create_scenario_generation_pipeline(
        scenario_factory_config.criterions, scenario_factory_config.filters
    ) # (2)

    pipeline = (
        base_pipeline.chain(scenario_generation_pipeline)
        .map(pipeline_assign_tags_to_scenario)
        .map(pipeline_write_scenario_to_file(WriteScenarioToFileArguments(output_path)))
    )

    inputs = load_regions_from_csv(cities_file)
    result = pipeline.execute(inputs, ctx)
    result.print_cum_time_per_step()
```

1. The Scenario Factory already has some pre-defined [pipelines](../reference/api/pipelines.md), that we can use here.
2. Similarly to the globetrotter pipeline a basic scenario generation pipeline is already provided.

## Simulation

!!! abstract
    Simulation is an integral part for the scenario generation, because it generates the traffic on the lanelet network created by globetrotter. By changing the simulator or by adjusting its parameters, you can influence the results as well as runtime.

### Replace SUMO with OTS

By default, SUMO is used to simulate random traffic on the scenarios create by globetrotter. In Addition to SUMO, the Scenario Factory also supports OpenTrafficSim, which can be used as a drop-in replacement:

!!! tip
    For a comparison of the simulators check out the [simulation reference](../reference/simulation.md).

```python linenums="5" hl_lines="5"
...
    base_pipeline = (
        create_globetrotter_pipeline(radius, map_provider) # (1)
        .map(pipeline_add_metadata_to_scenario)
        .map(pipeline_simulate_scenario_with_ots(SimulationConfig(mode=SimulationMode.RANDOM_TRAFFIC_GENERATION, simulation_length=600)))
    )
...
```
