# Generation of CommonRoad Scenarios with SUMO
This repo refactors code which was developed mainly by Moritz Klischat. It can generate interactive and non-interactive CommonRoad traffic scenario, as used, e.g., in the CommonRoad competition. 

# Installation
1. Setup of environment
    1. Install a Python IDE. We suggest using [PyCharm](https://www.jetbrains.com/pycharm/).
    2. Install  [Anaconda](https://www.anaconda.com/) (or [Miniconda](https://conda.io/miniconda.html)).
    3. Install [SUMO](https://sumo.dlr.de/docs/Downloads.php). Don't forget to `export SUMO_HOME="/your/path/to/sumo"` in your `.bashrc`.

2. Clone this repository.
3. Set up a conda environment for the practical course: `conda create -n "mpfav23" python=3.9`.
4. Activate conda environment `conda actiavte mpfav23` & pip install the dependencies `pip install -r requirements.txt`.
5. Open the `sumocr-scenario-generation` repo as a project in PyCharm. Set the PyCharm Python interpreter to `mpfav23`.
6. Add the following repos to the Python path (in PyCharm, this is called project structure: `File` → `Settings` → `Project` → `Project structure` → `Add content root`). Use the current `develop` branch.

| Repo                                                     | Commit (tested)                            |
|----------------------------------------------------------|--------------------------------------------|
| `git@gitlab.lrz.de:cps/commonroad-scenario-designer.git` | `f838d127fcccf758053d5446050289e0ecafed3f` |
| `git@gitlab.lrz.de:cps/sumo-interface.git`               | `91ff00c056b8178d284fa83cc3379df4fa71c064` |

7. Run the [`generate_senarios.py`](scripts/generate_senarios.py) script to create interactive scenarios. The required input files (CommonRoad Scenarios, containing a LaneletNetwork), can either be taken from existing CommonRoad scenarios or be created with the [OSM Map Extractor](https://gitlab.lrz.de/cps/osm-map-extractor). With the default settings, 13 solution files should be generated. You'll find these in the output folder. 
