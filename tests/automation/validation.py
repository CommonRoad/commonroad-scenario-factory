from datetime import datetime
from types import NoneType, UnionType
from typing import Any, Callable, Iterable, List, Optional, Union, get_type_hints

import pydantic
from pydantic import field_validator

from scenario_factory.globetrotter import Coordinates, RegionMetadata

_PARSERS: dict[type, Callable] = {}


def custom_parser(_type: type):
    def register_parser(func):
        if _type in _PARSERS:
            raise RuntimeError("Tried to register multiple parsers for the same type.")
        _PARSERS[_type] = func
        return func

    return register_parser


def bool_from_string(string: str) -> bool:
    string = string.lower()
    if string == "true":
        return True
    elif string == "false":
        return False
    else:
        raise ValueError(f'Cannot parse boolean value from "{string}".')


@custom_parser(str)
def parse_str(v) -> str:
    if isinstance(v, str):
        return v
    else:
        raise ValueError("Invalid format for string values.")


@custom_parser(bool)
def parse_bool(v) -> bool:
    if isinstance(v, str):
        v = v.lower()
        if v == "true":
            return True
        elif v == "false":
            return False
        else:
            raise ValueError(f'Cannot parse boolean value from "{v}".')
    elif isinstance(v, bool):
        return v
    else:
        raise ValueError("Invalid format for boolean values.")


@custom_parser(float)
def parse_float(v) -> float:
    if isinstance(v, (str, int)):
        return float(v)
    elif isinstance(v, float):
        return v
    else:
        raise ValueError("Invalid format for float values.")


@custom_parser(int)
def parse_int(v) -> int:
    if isinstance(v, str):
        return int(v)
    if isinstance(v, float) and int(v) == v:
        return int(v)
    elif isinstance(v, int):
        return v
    else:
        raise ValueError("Invalid format for integer values.")


@custom_parser(Coordinates)
def parse_coordinates(v) -> Coordinates:
    if isinstance(v, str):
        return Coordinates.from_str(v)
    elif (
        isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], float) and isinstance(v[1], float)
    ):
        return Coordinates.from_tuple((v[0], v[1]))
    elif isinstance(v, Coordinates):
        return v
    else:
        raise ValueError("Invalid format for coordinate values.")


@custom_parser(RegionMetadata)
def parse_region_metadata(v) -> RegionMetadata:
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


def decorate_opt(parser_func):
    def dec(v):
        if v is None:
            return None
        return parser_func(v)

    return dec


def decorate_iter(parser_func):
    def dec(v):
        if not isinstance(v, Iterable):
            raise ValueError("Invalid format for an iterable.")
        return [parser_func(item) for item in v]

    return dec


def produce_parser_func(hint):
    if hint in _PARSERS:
        return _PARSERS[hint]
    elif isinstance(hint, UnionType):
        raise RuntimeError(
            "Union types are not supported for test entries. Use Optional[Type] for unions with None."
        )
    elif hasattr(hint, "__origin__") and hasattr(hint, "__args__") and hint.__origin__ is list:
        return decorate_iter(produce_parser_func(hint.__args__[0]))
    elif (
        hasattr(hint, "__origin__")
        and hasattr(hint, "__args__")
        and hint.__origin__ is Union
        and len(hint.__args__) == 2
        and hint.__args__[1] is NoneType
    ):
        return decorate_opt(produce_parser_func(hint.__args__[0]))
    raise RuntimeError(f"Trying to automatically create a model with an unsupported type: {hint}.")


def produce_field_validator(field_name: str, parser_func):
    def validator(cls, v):
        return parser_func(v)

    return field_validator(field_name, mode="before")(classmethod(validator))


def entry_model(cls: type):
    """
    Decorating a type with this decorator will create a pydantic base model using the validations from this module.
    This model accounts only for the type hinted fields of the decorated type and only works for supported types.
    """
    type_hints = get_type_hints(cls)
    model_contents = {"__annotations__": cls.__annotations__}
    if "label" not in type_hints:
        model_contents["__annotations__"]["label"] = str
        type_hints["label"] = str
    for name, hint in type_hints.items():
        func_name = f"parse_{name}"
        parser_func = produce_parser_func(hint)

        func_content = produce_field_validator(name, parser_func)
        model_contents[func_name] = func_content
    model = type(cls.__name__, (pydantic.BaseModel,), model_contents)
    return model
