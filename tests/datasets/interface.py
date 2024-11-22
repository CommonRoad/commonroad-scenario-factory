from pathlib import Path

_TEST_DATASET_ROOT = Path(__file__).parent


def get_test_dataset_root() -> Path:
    return _TEST_DATASET_ROOT
