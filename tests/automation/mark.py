from __future__ import annotations
import inspect
import itertools
from typing import Iterable, Sequence
import pytest

from tests.automation.datasets import DatasetInterface

_DATASET_MARKER_ATTRIBUTE_NAME = "__mark_test_with_dataset"


def get_param_names_from_signature(func) -> list[str]:
    """
    Utility function that extracts parameter names from a function signature (similar to what pytest uses).
    :param func: The test function.
    :return: A list of all positional parameters, excluding self.
    """
    sig = inspect.signature(func)
    names = []
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        if p.kind == inspect.Parameter.VAR_POSITIONAL or p.kind == inspect.Parameter.VAR_KEYWORD:
            raise RuntimeError(
                "The with_database decorator does not support test functions with variadic parameters."
            )
        names.append(name)

    return names


class SkipNote:
    """
    An object that contains a label of a test case to be skipped, and the reason why it is skipped.
    """

    @property
    def label(self) -> str:
        """
        Accesses the label of the test case to be skipped.
        :return: The label.
        """
        return self._label

    @property
    def reason(self) -> str:
        """
        Accesses the reason why the test case is skipped.
        :return: The reason.
        """
        return self._reason

    _label: str
    _reason: str

    def __init__(self, label: str, reason: str | None = None):
        self._label = label
        self._reason = "Deactivated" if reason is None else reason


class _DatasetMarker:
    """
    Utility object that is injected on a test function by the with_dataset attribute. Is handled by a pytest hook to load test cases.
    """
    dataset: DatasetInterface
    parameter_names: list[str]
    skips: dict[str, SkipNote]

    def __init__(self, dataset: DatasetInterface, parameter_names: list[str], skips: dict[str, SkipNote]):
        self.dataset = dataset
        self.parameter_names = parameter_names
        self.skips = skips

    def create_extended(self, marker: _DatasetMarker) -> _DatasetMarker:
        if self.parameter_names != marker.parameter_names:
            raise ValueError("Multiple with_dataset annotations are only allowed if the same parameter names are targeted.")
        skips = {}
        for label, skip_note in itertools.chain(self.skips.items(), marker.skips.items()):
            skips[label] = skip_note
        return _DatasetMarker(self.dataset.create_extended(marker.dataset), self.parameter_names, skips)


class with_dataset:
    """
    Decorator to enable dynamically loading test cases from a Dataset.
    """
    _dataset: DatasetInterface
    _parameter_names: list[str] | None
    _skips: dict[str, SkipNote]

    def __init__(self, dataset: DatasetInterface, parameter_names: Sequence[str] | None = None,
                 skips: Iterable[SkipNote | str] | None = None):
        """
        Mark a test function to load cases from a dataset.
        :param dataset: The dataset containing the cases.
        :param parameter_names: If provided, a list of attribute names provided by the entries of the dataset that are mapped onto the position parameters of the test function.
        :param skips: An optional collection of labels/skip notes of cases that should be skipped.
        """
        self._dataset = dataset
        if parameter_names is None:
            self._parameter_names = None
        else:
            self._parameter_names = list(parameter_names)
        if skips is None:
            self._skips = {}
        else:
            self._skips = {}
            for s in skips:
                if isinstance(s, str):
                    self._skips[s] = SkipNote(s)
                elif isinstance(s, SkipNote):
                    self._skips[s.label] = s
                else:
                    raise TypeError(f"Unexpected type {type(s)} for a skip note.")

    def __call__(self, func):
        marker = self._resolve_marker(func)
        if hasattr(func, _DATASET_MARKER_ATTRIBUTE_NAME):
            marker = getattr(func, _DATASET_MARKER_ATTRIBUTE_NAME).create_extended(marker)
        setattr(func, _DATASET_MARKER_ATTRIBUTE_NAME, marker)
        return func

    def _resolve_marker(self, func) -> _DatasetMarker:
        if self._parameter_names is None:
            return _DatasetMarker(self._dataset, get_param_names_from_signature(func), self._skips)
        else:
            return _DatasetMarker(self._dataset, self._parameter_names, self._skips)


def _apply_parametrization(metafunc: pytest.Metafunc):
    """
    Creates the parametrization mark supported by pytest from a _DatasetMarker.
    :param metafunc: The test function to be marked.
    :return:
    """
    marker = getattr(metafunc.function, _DATASET_MARKER_ATTRIBUTE_NAME)
    if not isinstance(marker, _DatasetMarker):
        raise TypeError("Unexpected dataset marker on test function.")
    params = []
    for case in marker.dataset.iterate_entries():
        skip_note = marker.skips.get(case.label, None)
        marks = () if skip_note is None else pytest.mark.skip(reason=skip_note.reason)
        param = pytest.param(*tuple(getattr(case, pname) for pname in marker.parameter_names), marks=marks)
        params.append(param)
    metafunc.parametrize(", ".join(marker.parameter_names), params)


def apply_pytest_hook(metafunc: pytest.Metafunc):
    """
    Running this function from a pytest hook, enables dynamically loading test cases from datasets.
    :param metafunc: The testfunction to apply a parametrization on, if it is marked accordingly.
    """
    if hasattr(metafunc.function, _DATASET_MARKER_ATTRIBUTE_NAME):
        _apply_parametrization(metafunc)