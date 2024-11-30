import csv
import json
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Iterable

import pydantic

from tests.automation.validation import TestCase


@dataclass
class Dataset:
    entries: list[Any]
    entry_model: type

    def __init__(self, entry_model: type, initial_entries: Iterable[Any] | None = None):
        """
        Initializes a test dataset with some dynamically created content.
        """
        self.entries = []
        if issubclass(entry_model, TestCase):
            self.entry_model = entry_model
        else:
            raise TypeError("The entry model has to inherit from TestCase.")
        if initial_entries is not None:
            for entry in initial_entries:
                if isinstance(entry, entry_model):
                    self.entries.append(entry)
                else:
                    raise ValueError(f"Each entry has to be an instance of {entry_model}.")

    def add(self, entry: Any):
        if isinstance(entry, self.entry_model):
            self.entries.append(entry)
        else:
            raise TypeError(f"Each entry has to be an instance of {self.entry_model}")

    def add_all(self, entries: Iterable[Any]):
        for entry in entries:
            self.add(entry)


class FileDatasetFormat(Enum):
    CSV = auto()
    JSON = auto()


@dataclass
class FileDataset:
    dataset_name: list[str] | None
    entry_model: type | None
    dataset_format: FileDatasetFormat | None
    dataset_object: list[Any] | None

    def __init__(
        self,
        dataset_name: Iterable[str] | None = None,
        entry_model: type | None = None,
        dataset_format: FileDatasetFormat | None = None,
    ):
        """
        Initializes a test dataset that is loaded from a file.

        :param entry_model: The optional pydantic model to use for each entry from the dataset.

        :param dataset_name: The name of the test dataset relative to the test_datasets folder (without ending). If not provided the name of the test function relative to the tests module is used e.g. ["unit", "globetrotter", "test_osm", "TestGlobals", "test_get_canonical_region_name"].

        :param dataset_format: The file format to use. Auto-discovered if not provided.
        """
        self.dataset_name = None if dataset_name is None else list(dataset_name)
        if entry_model is None:
            self.entry_model = None
        elif issubclass(entry_model, TestCase):
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
