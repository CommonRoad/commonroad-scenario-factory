import pytest

from tests.automation.mark import apply_pytest_hook


def pytest_generate_tests(metafunc: pytest.Metafunc):
    apply_pytest_hook(metafunc)
