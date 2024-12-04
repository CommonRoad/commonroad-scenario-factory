from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from enum import Enum, auto
from pathlib import Path
from typing import Generator, Iterable

from tests.automation.validation import TestCase
from tests.datasets.interface import get_test_dataset_root


class DatasetInterface(ABC):
    """
    Specifies the functionality that should be supported by a dataset containing test cases.
    """

    @abstractmethod
    def iterate_entries(self) -> Generator[TestCase, None, None]:
        """
        Iterates over all test cases in the dataset.
        :return: A generator of the test cases.
        """
        pass

    @abstractmethod
    def create_extended(self, dataset: DatasetInterface) -> DatasetInterface:
        """
        Creates a new dataset referencing all entries from this and the given dataset.
        :param dataset: The other source dataset.
        :return: The newly created dataset with all entries.
        :raises ValueError: If not all test case labels are distinct.
        """
        pass

    @abstractmethod
    def contains_entry(self, label: str) -> bool:
        """
        Indicated whether the dataset contains a test case with the given label.
        :param label: The label to search for.
        :return: True, if a test case in this dataset has the given label. False, otherwise.
        """
        pass


class MergedDataset(DatasetInterface):
    """
    Utility dataset implementation that loads from multiple subsets.
    """

    _subsets: list[DatasetInterface]

    def __init__(self, subsets: Iterable[DatasetInterface]):
        self._subsets = []
        for ds in subsets:
            self.extend(ds)

    def extend(self, subset: DatasetInterface):
        """
        Extends this dataset by adding all test cases from the given subset.
        :param subset: The subset to add the cases from.
        :raises ValueError: If there are duplicated labels.
        """
        for case in subset.iterate_entries():
            if self.contains_entry(case.label):
                raise ValueError(
                    "Cannot extend with a dataset that contains duplicated label names."
                )
        self._subsets.append(subset)

    def iterate_entries(self) -> Generator[TestCase, None, None]:
        for ds in self._subsets:
            for entry in ds.iterate_entries():
                yield entry

    def create_extended(self, dataset: DatasetInterface) -> DatasetInterface:
        result = MergedDataset(self._subsets)
        result.extend(dataset)
        return result

    def contains_entry(self, label: str) -> bool:
        for ds in self._subsets:
            if ds.contains_entry(label):
                return True
        return False


class Dataset(DatasetInterface):
    """
    Implements the dataset interface for dynamically managed datasets.
    """

    _entries: dict[str, TestCase]

    def __init__(self, entries: Iterable[TestCase]):
        self._entries = {}
        for case in entries:
            self.add_entry(case)

    def add_entry(self, case: TestCase):
        if case.label in self._entries:
            raise ValueError(f"Dataset already contains a test case with label: {case.label}")
        self._entries[case.label] = case

    def iterate_entries(self) -> Generator[TestCase, None, None]:
        for entry in self._entries.values():
            yield entry

    def create_extended(self, dataset: DatasetInterface) -> DatasetInterface:
        return MergedDataset([self, dataset])

    def contains_entry(self, label: str) -> bool:
        return label in self._entries


class FileDatasetFormat(Enum):
    CSV = auto()
    JSON = auto()


class FileDataset(DatasetInterface):
    """
    Implements the dataset interface for dataset that are loaded from a file.
    """

    _filename: Path
    _file_format: FileDatasetFormat
    _entry_model: type
    _cache: dict[str, TestCase] | None

    def __init__(self, filename: Path | str, file_format: FileDatasetFormat, entry_model: type):
        """
        Constructs a dataset that is loaded from a file in the tests/datasets/... folder.
        :param filename: The path relative to the tests/datasets/ folder.
        :param file_format: The format of the file (CSV or JSON).
        :param entry_model: The pydantic model (inheriting from TestCase) that should be used to safely load the dataset.
        """
        if isinstance(filename, str):
            self._filename = Path(filename)
        elif isinstance(filename, Path):
            self._filename = filename
        else:
            raise ValueError("Unexpected type for filename argument.")

        self._file_format = file_format
        if not issubclass(entry_model, TestCase):
            raise TypeError("Expected a subclass of TestCase for the entry model.")
        self._entry_model = entry_model
        self._cache = None

    def iterate_entries(self) -> Generator[TestCase, None, None]:
        """
        Iterates over all entries by loading the dataset file.
        :return: An iterator over the entries.
        :raises FileNotFoundError: If the referenced file could not be found.
        """
        for case in self._get_entries().values():
            yield case

    def create_extended(self, dataset: DatasetInterface) -> DatasetInterface:
        return MergedDataset([self, dataset])

    def contains_entry(self, label: str) -> bool:
        return label in self._get_entries()

    def _get_entries(self) -> dict[str, TestCase]:
        if self._cache is None:
            self._cache = {case.label: case for case in self._load_from_file()}
        return self._cache

    def _load_from_file(self) -> list[TestCase]:
        complete_path = get_test_dataset_root() / self._filename
        if not complete_path.exists():
            raise FileNotFoundError(
                f"The dataset could not be loaded, because {complete_path} does not exist."
            )

        if self._file_format == FileDatasetFormat.JSON:
            with open(complete_path, "rt") as file:
                data = json.load(file)
        elif self._file_format == FileDatasetFormat.CSV:
            with open(complete_path, "rt") as file:
                data = list(csv.DictReader(file))
        else:
            raise ValueError(f"Unknown file format: {self._file_format}.")

        return [self._entry_model(**item) for item in data]
