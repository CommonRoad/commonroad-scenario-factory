import pytest

from scenario_factory.globetrotter.region import Coordinates, RegionMetadata


class TestCoordinates:
    def test_correctly_parses_coordinates_seperated_by_slash(self):
        raw_coordinates = "28.7908/-81.6970"
        coordinates = Coordinates.from_str(raw_coordinates)
        assert coordinates.lat == 28.7908
        assert coordinates.lon == -81.6970

    def test_correctly_parses_coordinates_seperated_by_comma(self):
        raw_coordinates = "-30.107,136.670"
        coordinates = Coordinates.from_str(raw_coordinates)
        assert coordinates.lat == -30.107
        assert coordinates.lon == 136.670

    def test_fails_to_parse_coordinates_with_invalid_seperator(self):
        raw_coordinates = "62.6326A51.5748"

        with pytest.raises(ValueError):
            Coordinates.from_str(raw_coordinates)

    def test_fails_to_parse_only_one_coordinate(self):
        raw_coordinates = "2.6326/"

        with pytest.raises(ValueError):
            Coordinates.from_str(raw_coordinates)

    def test_constructs_coordinates_from_tuple(self):
        raw_coordinates = (-30.107, 136.670)
        coordinates = Coordinates.from_tuple(raw_coordinates)
        assert coordinates.lat == -30.107
        assert coordinates.lon == 136.670

    def test_string_serialization_and_parsing_is_idempotent(self):
        original_coordinates = Coordinates(lat=-12.764, lon=21.484)
        str_coordinates = str(original_coordinates)
        parsed_coordinates = Coordinates.from_str(str_coordinates)
        assert parsed_coordinates.lat == original_coordinates.lat
        assert parsed_coordinates.lon == original_coordinates.lon

    def test_tuple_serialization_and_parsing_is_idempotent(self):
        original_coordinates = Coordinates(lat=42.1294, lon=105.3030)
        tuple_coordinates = original_coordinates.as_tuple()
        parsed_coordinates = Coordinates.from_tuple(tuple_coordinates)
        assert parsed_coordinates.lat == original_coordinates.lat
        assert parsed_coordinates.lon == original_coordinates.lon


class TestRegionMetadata:
    def test_from_coordinates_sets_optional_metadata(self):
        coordinates = Coordinates(lat=42.1294, lon=105.3030)
        region = RegionMetadata.from_coordinates(
            coordinates, country_code="DEU", region_name="Somewhere"
        )
        assert region.coordinates.lat == coordinates.lat
        assert region.coordinates.lon == coordinates.lon
        assert region.country_code == "DEU"
        assert region.region_name == "Somewhere"

    def test_from_coordinates_gets_correct_country_code_from_geonames(self):
        coordinates = Coordinates(lat=40.4184, lon=-3.6667)
        region = RegionMetadata.from_coordinates(coordinates)
        assert region.country_code == "ESP"
        assert region.region_name.lower() == "retiro"
