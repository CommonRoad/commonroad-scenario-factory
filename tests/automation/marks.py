import inspect
import os
import sys
from pathlib import Path
from typing import Any, Iterable

from _pytest.mark import Mark

from tests.automation.datasets import (
    Dataset,
    DatasetFormat,
    get_test_dataset_csv,
    get_test_dataset_json,
)
from tests.datasets.interface import get_test_dataset_root
from tests.interface import get_test_root


def _pop_marks(obj: Any) -> list[Mark]:
    """
    Get the marks imposed using pytest decorators and remove the reference in the object.
    """
    if hasattr(obj, "pytestmark"):
        marks = list(obj.pytestmark)
        delattr(obj, "pytestmark")
    else:
        marks = []
    return marks


def _put_marks(obj: Any, marks: list[Mark]):
    obj.pytestmark = marks


def _select_marks(marks: list[Mark], param_spec: str) -> tuple[list[Mark], int]:
    result = []
    selected = []
    for m in marks:
        if m.name == "parametrize":
            selected.append(m)
        else:
            result.append(m)

    merged_entries = []
    for m in selected:
        if m.args[0] != param_spec:  # TODO: Semantic check
            raise ValueError("The test function has been marked with incompatible marks.")
        merged_entries.extend(m.args[1])
    result.append(Mark("parametrize", (param_spec, merged_entries), {}))
    return result, len(result) - 1


def _name_relative_to_test_root(func: Any) -> list[str]:
    # Use module to get the full path
    mod_path_str = sys.modules[func.__module__].__file__
    if mod_path_str is None:
        raise RuntimeError("The module path is not available.")
    module_path = Path(mod_path_str)
    test_root_path = get_test_root()
    rel_path = module_path.relative_to(test_root_path)

    parts = list(rel_path.parts)
    parts.extend(func.__qualname__.split("."))
    return parts


def _inspect_parameter_names(func: Any) -> list[str]:
    sig = inspect.signature(func)
    names = []
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        if p.kind == inspect.Parameter.VAR_POSITIONAL or p.kind == inspect.Parameter.VAR_KEYWORD:
            raise RuntimeError(
                "The with_... decorators do not support test functions with variadic parameters."
            )
        names.append(name)

    return names


class with_dataset:
    _dataset: Dataset
    _parameter_names: list[str] | None

    def __init__(self, dataset: Dataset, parameter_names: Iterable[str] | str | None = None):
        """
        Initializes a with_dataset decorator.

        :param dataset: The dataset to use.

        :param parameter_names: The names of the parameters of the test dataset in the order they should be inserted into the test function. If not provided the parameter names of the function declaration are used.
        """
        self._dataset = dataset
        if parameter_names is None:
            self._parameter_names = parameter_names
        elif isinstance(parameter_names, Iterable):
            self._parameter_names = list(parameter_names)
        elif isinstance(parameter_names, str):
            self._parameter_names = list(map(lambda s: s.strip(), parameter_names.split(",")))
        else:
            raise ValueError()

    def __call__(self, *args):
        func = args[0]

        # Resolve all names
        self._resolve_dataset_name(func)
        self._resolve_parameter_names(func)

        # This should stack so we have to check for previous marks
        marks = _pop_marks(func)
        param_spec = ", ".join(self._parameter_names)
        marks, target = _select_marks(marks, param_spec)

        # Extend with dataset
        marks[target].args[1].extend(self._load_test_dataset())

        # Put back marks
        _put_marks(func, marks)
        return func

    def _resolve_dataset_name(self, func: Any):
        if self._dataset.dataset_name is None:
            self._dataset.dataset_name = _name_relative_to_test_root(func)

    def _resolve_parameter_names(self, func: Any):
        if self._parameter_names is None:
            self._parameter_names = _inspect_parameter_names(func)

    def _load_test_dataset(self) -> list[tuple]:
        if self._dataset.dataset_name is None:
            raise RuntimeError("The dataset name could not be resolved.")
        rel = os.sep.join(self._dataset.dataset_name)
        csv_ending = get_test_dataset_root() / Path(f"{rel}.csv")
        csv_exists = csv_ending.exists()
        json_ending = get_test_dataset_root() / Path(f"{rel}.json")
        json_exists = json_ending.exists()
        selected_format = self._dataset.dataset_format
        if selected_format is None:
            if csv_exists and json_exists:
                raise RuntimeError(
                    f"Cannot auto-detect the format of the test dataset: {str(rel)} because both a JSON and CSV file exist."
                )
            if csv_exists:
                selected_format = DatasetFormat.CSV
            if json_exists:
                selected_format = DatasetFormat.JSON

        if selected_format == DatasetFormat.CSV:
            dataset = get_test_dataset_csv(csv_ending, self._dataset.entry_model)
        elif selected_format == DatasetFormat.JSON:
            dataset = get_test_dataset_json(json_ending, self._dataset.entry_model)
        else:
            raise RuntimeError(
                f"There is no corresponding dataset at: .../{str(rel)} with CSV or JSON ending."
            )

        if self._parameter_names is None:
            raise RuntimeError("Could not resolve parameter names.")
        if self._dataset.entry_model is None:
            entries = [tuple(obj[pname] for pname in self._parameter_names) for obj in dataset]
        else:
            entries = [
                tuple(getattr(obj, pname) for pname in self._parameter_names) for obj in dataset
            ]
        return entries


class with_custom:
    _entries: list[tuple | Any]
    _parameter_names: list[str] | None

    def __init__(
        self,
        entries: Iterable[tuple] | list[Any] | None = None,
        parameter_names: Iterable[str] | str | None = None,
    ):
        """
        Initializes a with_dataset decorator.

        :param parameter_names: The names of the parameters of the test dataset in the order they should be inserted into the test function. If not provided the parameter names of the function declaration are used.

        :param entries: List of entries that have the parameter names available as attributes or are tuples with the ordered parameters.
        """
        if parameter_names is None:
            self._parameter_names = parameter_names
        elif isinstance(parameter_names, Iterable):
            self._parameter_names = list(parameter_names)
        elif isinstance(parameter_names, str):
            self._parameter_names = list(map(lambda s: s.strip(), parameter_names.split(",")))
        else:
            raise ValueError()
        if entries is None:
            self._entries = []
        else:
            self._entries = list(entries)

    def __call__(self, *args):
        func = args[0]

        # Resolve all names
        self._resolve_parameter_names(func)

        # This should stack so we have to check for previous marks
        marks = _pop_marks(func)
        param_spec = ", ".join(self._parameter_names)
        marks, target = _select_marks(marks, param_spec)

        # Extend with dataset
        marks[target].args[1].extend(self._build_test_dataset())

        # Put back marks
        _put_marks(func, marks)
        return func

    def _resolve_parameter_names(self, func: Any):
        if self._parameter_names is None:
            self._parameter_names = _inspect_parameter_names(func)

    def _build_test_dataset(self) -> list[tuple]:
        dataset = []
        if self._parameter_names is None:
            raise RuntimeError("Could not resolve parameter names.")
        for entry in self._entries:
            if isinstance(entry, tuple):
                dataset.append(entry)
            else:
                dataset.append(tuple(getattr(entry, p_name) for p_name in self._parameter_names))
        return dataset
