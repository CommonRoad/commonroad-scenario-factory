# CommonRoad Scenario Factory
[![pipeline status](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/badges/develop/pipeline.svg)](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/-/commits/develop)
[![coverage report](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/badges/develop/coverage.svg)](https://gitlab.lrz.de/cps/commonroad/sumocr-scenario-generation/-/commits/develop)
The CommonRoad Scenario Factory is a toolbox that combines many different tools from the whole CommonRoad ecosystem to efficiently process CommonRoad Scenarios.

# Usage

## Installation

```
$ git clone git@gitlab.lrz.de:cps/commonroad/sumocr-scenario-generation.git
$ cd sumocr-scenario-generation
$ poetry install
```

### Additional Requirements

* [python>=3.10,<3.12`](https://www.python.org/downloads/)
* [poetry](https://python-poetry.org/docs/)
* [SUMO](https://sumo.dlr.de/docs/Downloads.php): Make sure that the environment variable `SUMO_HOME` is set.
* [osmium](https://osmcode.org/osmium-tool/)


## Generate Scenarios

To generate scenarios run:
```
$ poetry run scenario-factory
```
This will read a list of cities from `./files/cities_file.csv` and output the resulting scenarios to `./files/output`.

You can also change the default settings by overriding the CLI options. To see all available options run:

```
$ poetry run scenario-factory --help
```


# Theoretical instructions

## Get CommonRoad LaneletNetwork files
Using the osmium tool, maps of e.g., a certain city can be extracted from large-scale maps (see also [OSM-README](files/example/README.md)).
Parameters are directly set as part of the osmium extract command.

## Choose relevant maps with globetrotter
The small-area osm files are the input to the [globetrotter_usage.py](scripts/globetrotter_usage.py) script. There, the relevant sections of the LaneletNetworks are written to individual LaneletNetwork files.
Parameters can be set #TODO add explanation.

## Generate traffic with SUMO
Once the LaneletNetwork files of relevant sections are available, traffic on them can be simulated using the [generate_scenarios.py](scripts/generate_senarios.py) script.
Parameters can be set in the [scenario_config.py](scenario_factory/config_files/scenario_config.py).

## Optional steps
After creating the scenarios, they can be renamed using the [rename_cr_scenarios.py](scripts/rename_cr_scenarios.py) script.

# Internals

## TL;DR

1. OSM data is converted into CommonRoad LaneletNetworks
2. Relevant intersections are chosen using the globetrotter tool.
3. Traffic is simulated on the extracted lanelet networks.
