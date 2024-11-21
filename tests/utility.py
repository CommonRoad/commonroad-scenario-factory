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


@pipeline_map()
def pipeline_simple_map(ctx: PipelineContext, value: int) -> int:
    return value**2


@pipeline_filter()
def pipeline_simple_filter(
    filter: PipelineFilterPredicate, ctx: PipelineContext, value: int
) -> bool:
    return filter.matches(value)


@pipeline_fold()
def pipeline_simple_fold(ctx: PipelineContext, values: Sequence[int]) -> Sequence[int]:
    return [sum(values)]


class IsEvenFilter(PipelineFilterPredicate):
    def matches(self, value: int) -> bool:
        return value % 2 == 0


def is_valid_commonroad_scenario(scenario_path: Path) -> bool:
    _, _ = CommonRoadFileReader(scenario_path).open()
    return True


def hash_file(path: Path):
    hash_func = md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def assert_osm_semantic_matches(osm1: Path, osm2: Path):
    # TODO: WORK OUT MORE ROBUST EXCERPT CHECK

    with open(osm1, "rt") as file1:
        tree1 = xml_tree.fromstring(file1.read())
    with open(osm2, "rt") as file2:
        tree2 = xml_tree.fromstring(file2.read())

    def compare_attributes_and_children(
        elm1: xml_tree.Element, elm2: xml_tree.Element, skip_attributes: bool = False
    ):
        if not skip_attributes:
            for name, value in elm1.attrib.items():
                assert name in elm2.attrib, f"Attribute {name} not present in both nodes."
                assert value == elm2.attrib[name], f"Value of attribute {name} does not match."
            for name in elm2.attrib:
                assert name in elm1.attrib, f"Attribute {name} not present in both nodes."
        assert len(elm1) == len(elm2), "Number of child nodes did not match."
        candidates = set(i for i in range(len(elm1)))
        for child1 in elm1:
            target = -1
            for j in candidates:
                child2 = elm2[j]
                if child1.tag != child2.tag:
                    continue
                try:
                    compare_attributes_and_children(child1, child2)
                except AssertionError:
                    continue
                else:
                    target = j
                    break
            assert target != -1, f"No matching partner found for a child element."
            candidates.remove(target)

    compare_attributes_and_children(tree1, tree2, True)


def bool_from_string(string: str) -> bool:
    string = string.lower()
    if string == "true":
        return True
    elif string == "false":
        return False
    else:
        raise ValueError(f'Cannot parse boolean value from "{string}".')
