from pathlib import Path

_TEST_ROOT: Path = Path(__file__).parent


def get_test_root() -> Path:
    return _TEST_ROOT
