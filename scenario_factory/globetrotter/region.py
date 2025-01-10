__all__ = [
    "RegionMetadata",
    "BoundingBox",
    "load_regions_from_csv",
]

import csv
import math
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional, Tuple

import iso3166
import numpy as np
import pyproj
from commonroad.scenario.scenario import GeoTransformation, Location, ScenarioID
from crdesigner.map_conversion.osm2cr.converter_modules.utility.geonamesID import (
    find_nearest_neighbor,
)
from crdesigner.map_conversion.osm2cr.converter_modules.utility.labeling_create_tree import (
    create_tree_from_file,
)

RADIUS_EARTH: float = 6.371 * 1e3
PROJECTION_EPSG_4326 = "EPSG:4326"
PROJECTION_EPSG_3857 = "EPSG:3857"


# Cache the geonames database so it is only loaded once
@lru_cache
def _get_geonames_tree():
    with warnings.catch_warnings():
        return create_tree_from_file()


@dataclass
class Coordinates:
    """
    Common representation of latitude and longitude coordinates, that provides utilities for parsing and serialization.
    """

    lat: float
    lon: float

    @classmethod
    def from_str(cls, coords: str) -> "Coordinates":
        """
        Parse latitude and longitude coordinates. The two coordinates can either be seperated by a '/' or ','.

        :param coords: The two coordinates as a string
        :returns: The parsed coordinates
        :raises ValueError: If the coordiantes do not follow the describe schema
        """
        valid_seperators = ["/", ","]
        for seperator in valid_seperators:
            if seperator not in coords:
                continue

            parts = coords.split(seperator)
            if len(parts) != 2:
                raise ValueError(
                    f"Failed to parse coordinates '{coords}': Expected two parts seperated by '{seperator}', but found '{len(parts)}' parts"
                )
            try:
                return cls(float(parts[0]), float(parts[1]))
            except ValueError as e:
                raise ValueError(f"Failed to parse coordinates '{coords}': {e}")

        raise ValueError(
            f"Failed to parse coordinates '{coords}': Expected one of '{' '.join(valid_seperators)}' as seperator"
        )

    @classmethod
    def from_tuple(cls, coords: Tuple[float, float]) -> "Coordinates":
        return cls(coords[0], coords[1])

    @classmethod
    def from_tuple_cartesian(cls, coords: Tuple[float, float]) -> "Coordinates":
        transformer = pyproj.Transformer.from_crs(PROJECTION_EPSG_3857, PROJECTION_EPSG_4326)
        lat, lon = transformer.transform(coords[0], coords[1])
        return cls(lat, lon)

    def as_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lon)

    def as_tuple_cartesian(self) -> Tuple[float, float]:
        transformer = pyproj.Transformer.from_crs(PROJECTION_EPSG_4326, PROJECTION_EPSG_3857)
        return transformer.transform(self.lat, self.lon)

    def __str__(self) -> str:
        return f"{self.lat}/{self.lon}"


@dataclass
class RegionMetadata:
    """
    Hold metadata about a region anywhere on the world. Usefull when more information about a region then just coordinates is needed.

    :param country_code: The Alpha3 country code of this region (e.g. DEU)
    :param region_name: Human readable region name (e.g. Bremen)
    :param geoname_id: The Identifier of this region in the geonames database (e.g. 2944388)
    :param coordinates: The coordinates inside the region
    """

    country_code: str
    region_name: str
    geoname_id: int
    coordinates: Coordinates

    @classmethod
    def from_coordinates(
        cls,
        coordinates: Coordinates,
        country_code: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> "RegionMetadata":
        """
        Construct a :class:`RegionMetadata` from coordinates. Optionally, fetches geonames metadata from a local geonames database. The whole database will be loaded into memory and processed. Therefore, the use of this function might introduce a high runtime penality.

        :param coordinates: The base coordinates
        :param country_code: Optionally provide an Alpha3 country code (e.g. DEU). If no code is given, the country code from the geonames database will be used
        :param region_name: Optionally provide an human readbale region name. If no region name is given, the name from the geonames database will be used
        """
        geonames_tree = _get_geonames_tree()
        nearest_city_information = find_nearest_neighbor(geonames_tree, coordinates.as_tuple())
        if country_code is None:
            # geonames IDs contains only Alpha2 (e.g. DE) country codes, but CommonRoad requires Alpha3 country codes (e.g. DEU). Therefore the Alpha2 codes must be mapped to Alpha3 codes first.
            country = iso3166.countries.get(nearest_city_information.country)
            country_code = country.alpha3

        if region_name is None:
            region_name = nearest_city_information.name

        return cls(
            country_code=country_code,
            region_name=region_name,
            geoname_id=nearest_city_information.geonameID,
            coordinates=coordinates,
        )

    def as_commonroad_scenario_location(self) -> Location:
        return Location(
            gps_latitude=self.coordinates.lat,
            gps_longitude=self.coordinates.lon,
            geo_name_id=self.geoname_id,
            geo_transformation=GeoTransformation(geo_reference=PROJECTION_EPSG_3857),
        )

    def as_commonroad_scenario_id(self) -> ScenarioID:
        return ScenarioID(country_id=self.country_code, map_name=self.region_name)

    def __str__(self) -> str:
        return f"{self.country_code}_{self.region_name} {self.coordinates}"


def _compute_bounding_box_coordinates(
    lat: float, lon: float, radius: float
) -> Tuple[float, float, float, float]:
    """
    Compute the bounding box coordinates for a given latitude, longitude and radius.

    :param lat: Latitude in degree
    :param lon: Longitude in degree
    :param radius: Radius in km
    :returns: West, South, East, North coordinates
    """

    dist_degree = radius / RADIUS_EARTH * 180 / math.pi
    west = lon - dist_degree / np.cos(np.deg2rad(lat))
    south = lat - dist_degree
    east = lon + dist_degree / np.cos(np.deg2rad(lat))
    north = lat + dist_degree

    return west, south, east, north


@dataclass
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def __str__(self):
        return f"{self.west},{self.south},{self.east},{self.north}"

    @classmethod
    def from_coordinates(cls, coordinates: Coordinates, radius: float) -> "BoundingBox":
        west, south, east, north = _compute_bounding_box_coordinates(
            *coordinates.as_tuple(), radius=radius
        )
        return cls(west, south, east, north)


def load_regions_from_csv(regions_file: Path) -> Iterator[RegionMetadata]:
    """
    Read the regions from a CSV file and return them as RegionMetadata
    """
    with regions_file.open() as csvfile:
        cities_reader = csv.DictReader(csvfile)
        for region in cities_reader:
            coordinates = Coordinates(float(region["Lat"]), float(region["Lon"]))
            region_name = (
                region["Region"] if "Region" in region and len(region["Region"]) > 0 else None
            )
            country_code = region["Country"] if len(region["Country"]) > 0 else None
            yield RegionMetadata.from_coordinates(
                coordinates, country_code=country_code, region_name=region_name
            )
