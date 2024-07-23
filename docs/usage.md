# Usage

## regions.csv

The CSV input file can be used to specify a list of regions, that should be processed by the Scenario Factory. For each region you can specify:
* `Country` (optional, for radius < 0.8): The Alpha3 country code (e.g. DEU)
* `City` (optional): Kept for comptability reasons, not used
* `Region` (optional, for radius < 0.8): The name of the region. This name will only be used to enable more sophisticated map lookups, e.g. if you do not want to download the whole map for germany, you can instead download only 'oberbayern-latest.osm.pbf' and then specify 'Oberbayern' as the region. You must make sure that the specified region matches (case insensitive) the first part of the map name (e.g. 'Oberbayern' and 'oberbayern-latest.osm.pbf' or 'Mittlefranken' and 'mittlefranken-latest.osm.pbf')
* `Lat` (required)
* `Lon` (required)
