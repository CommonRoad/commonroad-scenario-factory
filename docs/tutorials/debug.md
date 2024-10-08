# Debug

Things go wrong and there are certainly many bugs in the scenario factory. Therefore, it is important to be able to easily debug the different steps that are executed.

## Logging

The logging in the scenario_factory follows the python standard. This means that each module uses an individual logger identified by the module path. E.g. the module `ego_vehicle_selection.filters` has the identifier `scenario_factory.ego_vehicle_selection.filters`.

```python
# Configure the root logger (Note: this includes *all* loggers e.g. also the loggers from the CommonRoad-SUMO Interface)
# Generally it is recommended to configure the root logger with the handler and format you want, and configure the level on the child loggers
logger = logging.getLogger()
logger.setLevel(logging.ERROR)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
logger.addHandler(handler)

# Debug the ego_vehicle_selection filters
logger = logging.getLogger("scenario_factory.ego_vehicle_selection.filters")
logger.setLevel(logging.DEBUG)

# Enable debug logging for the whole scenario_factory, but not for other libraries (e.g. the CommonRoad-SUMO Interface)
logger = logging.getLogger("scenario_factory")
logger.setLevel(logging.DEBUG)

```

## print
!!! warning

    Because the different projects from the CommonRoad contain many `print` debug statements even in their production releases, the pipeline will blackhole all calls to `print`. Therefore, you can also not use `print` inside your pipeline steps and instead you should resort to using descriptive log messages.
