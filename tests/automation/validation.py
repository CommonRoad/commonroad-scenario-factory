from typing import Callable, Iterable

import pydantic

from scenario_factory.globetrotter import Coordinates, RegionMetadata


def bool_from_string(string: str) -> bool:
    string = string.lower()
    if string == "true":
        return True
    elif string == "false":
        return False
    else:
        raise ValueError(f'Cannot parse boolean value from "{string}".')


def model_val_bool(v) -> bool:
    if isinstance(v, str):
        return bool_from_string(v)
    elif isinstance(v, bool):
        return v
    else:
        raise ValueError("Invalid format for boolean values.")


def model_val_float(v) -> float:
    if isinstance(v, (str, int)):
        return float(v)
    elif isinstance(v, float):
        return v
    else:
        raise ValueError("Invalid format for float values.")


def model_val_int(v) -> int:
    if isinstance(v, str):
        return int(v)
    if isinstance(v, float) and int(v) == v:
        return int(v)
    elif isinstance(v, int):
        return v
    else:
        raise ValueError("Invalid format for integer values.")


def model_val_coordinates(v) -> Coordinates:
    if isinstance(v, str):
        return Coordinates.from_str(v)
    elif isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], float) and isinstance(v[1], float):
        return Coordinates.from_tuple((v[0], v[1]))
    elif isinstance(v, Coordinates):
        return v
    else:
        raise ValueError("Invalid format for coordinate values.")

def model_val_region_metadata(v) -> RegionMetadata:
    if isinstance(v, dict) and "coordinates" in v and "country_code" in v and "region_name" in v:
        return RegionMetadata(
            coordinates=Coordinates.from_str(v["coordinates"]),
            country_code=v["country_code"],
            region_name=v["region_name"],
            geoname_id=0,
        )
    elif isinstance(v, RegionMetadata):
        return v
    else:
        raise ValueError("Invalid format for region metadata values.")


def decorate_opt(model_val: Callable):
    def dec(v):
        if v is None:
            return None
        return model_val(v)
    return dec


def decorate_iter(model_val: Callable):
    def dec(v):
        if not isinstance(v, Iterable):
            raise ValueError("Invalid format for an iterable.")
        return [model_val(item) for item in v]
    return dec


class LabeledCase(pydantic.BaseModel):
    label: str
