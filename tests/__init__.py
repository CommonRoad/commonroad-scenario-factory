import logging

try:
    import pytest
    import pydantic
except ImportError as e:
    raise RuntimeError(
        "Test dependencies are not installed. You probably need to run `poetry install --with tests`."
    ) from e

logging.basicConfig(level=logging.DEBUG)
