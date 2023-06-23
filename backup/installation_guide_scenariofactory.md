How to install scenario factory
===============================

1. Install sumo: https://sumo.dlr.de/docs/Downloads.php (tested with version 1.12.0; make sure that `sumo` returns the version info)

2. Create a conda environment: `conda create -n "scenariofactory" python=3.9`; activate this environment with `conda activate scenariofactory`

3. Make a directory where all git clones will be stored: `mkdir scenariofactory; navigate to this directory `cd scenariofactory`

4. Clone the following repos into the created directory and check out the specified commits:

| Repo | Commit |
|------|--------|
| `git@gitlab.lrz.de:ss19/commonroad_scenarios.git` | `10cd5f3aab61bad81177d4e55cec601726dec6b9` |
| `git@gitlab.lrz.de:cps/commonroad-scenario-features.git` | `bc313688889cfdc5b47cada557e410a9efef3265` |
| `git@gitlab.lrz.de:cps/commonroad-scenario-designer.git` | `release_0.5.1` |

5. Install the following packages:
- with conda: `conda install -c conda-forge cartopy`
- with pip: `pip install shapely==1.8.5 commonroad-io==2021.4 commonroad-drivability-checker==2021.4.1 sumocr==2021.5`
- with pip: `pip install -r requirements.txt` for all cloned repos. Make sure that shapely is not updated to a version >= 2, and that the commonroad-io versions etc. are not overwrittwen. 

6. Set up PyCharm:
- Open `scenariofactory/commonroad_scenarios` as the workspace. Under `File` → `Settings` → `Project: commonroad_scenarios` → `Project Structure` add `scenariofactory/commonroad-scenario-designer` and `scenariofactory/commonroad-scenario-features` as `content roots`. 
- Add the file `generate_interactive_scenarios.py` in the `scripts` folder. The configuration can be set using the `scenario_configHighWay.py` (also in the `scripts` folder). 
- Example files (recovered from the glados server) can be found [here] (https://nextcloud.in.tum.de/index.php/s/pGQNX5cgzTdW9Ji).
- When running the `generate_interactive_scenarios.py` script, some errors will be thrown. These can be fixed by adding or removing the `lanelet_network` attribute at the given error locations.

7. Hope for a refactored version of the code!
