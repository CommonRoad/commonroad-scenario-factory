# Generation of CommonRoad Scenarios with SUMO
This repo refactors code which was developed mainly by Moritz Klischat. It can generate interactive and non-interactive CommonRoad traffic scenario, as used, e.g., in the CommonRoad competition. 

## Installation
You might be able to skip some of the installation steps if the respective software is already installed. 
1. Install a Python IDE. We suggest using [PyCharm](https://www.jetbrains.com/pycharm/).
2. Install [Python](https://www.python.org/downloads/). Verify successful installation by executing `python3 --version`. 
3. Install [Poetry](https://python-poetry.org/docs/). Verify successful installation by executing `poetry --version`.
4. Install [SUMO](https://sumo.dlr.de/docs/Downloads.php). Don't forget to `export SUMO_HOME="/your/path/to/sumo"` in your `.bashrc`. Verify successful installation by executing `sumo --version`.
5. Install [osmium](https://osmcode.org/osmium-tool/). Verify successful installation by executing `osmium --version`. 
6. Clone this repository.
7. Install poetry environment `poetry install`.
8. Run the [`generate_senarios.py`](scripts/generate_senarios.py) script to create interactive scenarios: `poetry run python scripts/generate_scenarios.py`. With the default settings, 13 solution files should be generated. You'll find these in the output folder. 

The scenario generation proceeds in three steps:
- First, OSM data is converted into CommonRoad LaneletNetworks.
- Second, relevant intersections are chosen using the globetrotter tool.
- Third, traffic is simulated on the extracted lanelet networks.

# Hands on
Theoretical instructions can be found below. 

Go to the [files](files) folder and execute the scripts 1 to 5 one after another. With the default settings, the generated scenarios should be stored in the [output](files/output) folder.

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

