# Generate Scenarios for the Scenario Database

One of the primary use cases of the Scenario Factory is, to generate new scenarios for the [CommonRoad Scenario Database](https://commonroad.in.tum.de/scenarios). For this purpose a simple CLI application is provided:

```python
$ poetry run scenario-factory -o /tmp/scenario_factory --radius 0.1 --coords 48.264682/11.671399
```
This will start the scenario generation process and place all generated scenarios with their respective solutions in `/tmp/scenario_factory`. By default, the script will simply download the map at the coordinates from Openstreetmap. This means, that you can select coordinates from around the world, and generate scenarios for the locations, as long as your configured radius is smaller than 0.8. If you want to extract a map, that is larger than 0.8, you must manually download the map extracts first from [geofabrik.de](https://download.geofabrik.de/) and make them available to the scenario factory (normally this means placing the `.osm.pbf` file in `./files/input_maps`).

An overview of all arguments and options is provided in the [CLI reference](/reference/cli.md).


## Loading Points of Interest from a CSV File

If you want to generate scenarios for multiple locations at once, you can also have the scenario factory read the coordinates from a CSV file. The same rules for the radius also apply here, but you should be extra cautious, because if your CSV file contains many entries you may encounter an API limit from Openstreetmap.

The CSV input file can be used to specify a list of point of interests (POI), that should be processed by the Scenario Factory. For each POI you can specify:
* `Country` (optional for radius < 0.8): The Alpha3 country code (e.g. DEU)
* `City` (optional): Not used by the scenario factory, and treated as metadata for users to distinguish the entries in the CSV
* `Region` (optional for radius < 0.8): The name of the region. This name will only be used to enable more sophisticated map lookups, e.g. if you do not want to download the whole map for germany, you can instead download only 'oberbayern-latest.osm.pbf' and then specify 'Oberbayern' as the region. You must make sure that the specified region matches (case insensitive) the first part of the map name (e.g. 'Oberbayern' and 'oberbayern-latest.osm.pbf' or 'Mittlefranken' and 'mittlefranken-latest.osm.pbf')
* `Lat` (required)
* `Lon` (required)
