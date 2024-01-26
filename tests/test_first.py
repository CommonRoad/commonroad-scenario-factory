import pytest
import importlib
from files.dummy import add

module_name = 'files/1_bounding_box_coordinates'
script_module = importlib.import_module(module_name)

script_module.compute_bounding_box_coordinates(1,2,3)

assert add(2, 3) == 6



