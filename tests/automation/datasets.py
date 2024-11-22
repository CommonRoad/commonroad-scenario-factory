import csv
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import pydantic


class DatasetFormat(Enum):
    CSV = 0
    JSON = 1


@dataclass
class Dataset:
    dataset_name: list[str] | None
    entry_model: type | None
    dataset_format: DatasetFormat | None

    def __init__(
        self,
        dataset_name: Iterable[str] | None = None,
        entry_model: type | None = None,
        dataset_format: DatasetFormat | None = None,
    ):
        """
        Initializes a test dataset.

        :param entry_model: The optional pydantic model to use for each entry from the dataset.

        :param dataset_name: The name of the test dataset relative to the test_datasets folder (without ending). If not provided the name of the test function relative to the tests module is used e.g. ["unit", "globetrotter", "test_osm", "TestGlobals", "test_get_canonical_region_name"].

        :param parameter_names: The names of the parameters of the test dataset in the order they should be inserted into the test function. If not provided the parameter names of the function declaration are used.

        :param dataset_format: The file format to use. Auto-discovered if not provided.
        """
        self.dataset_name = None if dataset_name is None else list(dataset_name)
        if entry_model is None:
            self.entry_model = None
        elif issubclass(entry_model, pydantic.BaseModel):
            self.entry_model = entry_model
        else:
            raise TypeError("entry_model has to be a type inheriting from pydantic.BaseModel.")
        self.dataset_format = dataset_format


def get_test_dataset_csv(path: Path, entry_model: type | None) -> list[Any]:
    """
    Loads a list of named entries from a CSV file that are optionally described by a pydantic model.

    :param path: The path of the dataset.
    :param entry_model: A type that inherits from pydantic.BaseModel and describes the entries in the dataset.
    """
    if entry_model is not None:
        if not issubclass(entry_model, pydantic.BaseModel):
            raise TypeError("Models have to inherit from the pydantic.BaseModel.")

    with open(path, "rt") as file:
        reader = csv.DictReader(file)
        data = list(reader)
    if entry_model is not None:
        data = [entry_model(**item) for item in data]
    return data


def get_test_dataset_json(path: Path, entry_model: type | None) -> list[Any]:
    """
    Loads a list of python objects from a JSON file that are optionally described by a pydantic model.

    :param path: The name of the dataset.
    :param entry_model: A type that inherits from pydantic.BaseModel and describes the entries in the dataset.
    """
    if entry_model is not None:
        if not issubclass(entry_model, pydantic.BaseModel):
            raise TypeError("Models have to inherit from the pydantic.BaseModel.")

    with open(path, "rt") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise RuntimeError("A JSON Test-Dataset has to be list.")
    if entry_model is not None:
        data = [entry_model(**item) for item in data]
    return data
