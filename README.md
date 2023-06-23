# Generation of CommonRoad Scenarios with SUMO
This repo refactors code which was developed mainly by Moritz Klischat. It can generate interactive and non-interactive CommonRoad traffic scenario, as used, e.g., in the CommonRoad competition. 

# Installation
1. Clone this repository.
2. Install `pip -r requirements.txt`.
3. Add the following repos to the project structure:

| Repo | Commit (tested) | Remark |
|------|-----------------|----|
|`git@gitlab.lrz.de:cps/commonroad-scenario-designer.git` | `0616e28756c8e4e69b0fbba354251547a4844025` | `commonroad-scenario-designer>=0.7.2` should work | 
| `git@gitlab.lrz.de:cps/commonroad-scenario-features.git` | `493e745cb81be2a861eb0d9ac002c92560cbada4` ||

4. Use [`generate_interactive_senarios.py`](scripts/generate_interactive_senarios.py) to create interactive scenarios. The required input files (CommonRoad Scenarios, containing a LaneletNetwork), can either be taken from existing CommonRoad scenarios or be created with the [OSM Map Extractor](https://gitlab.lrz.de/cps/osm-map-extractor).

# Previous Version
The [backup](backup) directory contains an [installation guide](backup/installation_guide_scenariofactory.txt) for installing an out-of-date and buggy version of the scenario factory as well as a required [python script](backup/generate_interactive_senarios.py).