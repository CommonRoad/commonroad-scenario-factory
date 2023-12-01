# Generation of CommonRoad Scenarios with SUMO
This repo refactors code which was developed mainly by Moritz Klischat. It can generate interactive and non-interactive CommonRoad traffic scenario, as used, e.g., in the CommonRoad competition. 

# Installation
1. Setup of environment
    1. Install a Python IDE. We suggest using [PyCharm](https://www.jetbrains.com/pycharm/).
    2. Install  [Python](https://www.python.org/downloads/) and [Poetry](https://python-poetry.org/docs/).
    3. Install [SUMO](https://sumo.dlr.de/docs/Downloads.php). Don't forget to `export SUMO_HOME="/your/path/to/sumo"` in your `.bashrc`.

2. Clone this repository.
3. Install poetry environment `poetry install`.
4. Run the [`generate_senarios.py`](scripts/generate_senarios.py) script to create interactive scenarios: `poetry run python scripts/generate_scenarios.py`. With the default settings, 13 solution files should be generated. You'll find these in the output folder. 
