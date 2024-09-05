from pathlib import Path

from scenario_factory.globetrotter.osm import LocalFileMapProvider, MapProvider, OsmApiMapProvider


def select_osm_map_provider(radius: float, maps_path: Path) -> MapProvider:
    # radius > 0.8 would result in an error in the OsmApiMapProvider, because the OSM API limits the amount of data we can download
    if radius > 0.8:
        return LocalFileMapProvider(maps_path)
    else:
        return OsmApiMapProvider()
