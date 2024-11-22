import xml.etree.ElementTree as xml_tree
from hashlib import md5
from pathlib import Path
from typing import Sequence

from commonroad.common.file_reader import CommonRoadFileReader

from scenario_factory.pipeline import (
    PipelineContext,
    PipelineFilterPredicate,
    pipeline_filter,
    pipeline_fold,
    pipeline_map,
)
from tests.resources.interface import ResourceType

_TEST_ROOT: Path = Path(__file__).parent


def get_test_root() -> Path:
    return _TEST_ROOT
