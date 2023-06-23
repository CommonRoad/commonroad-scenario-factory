from pandas import DataFrame
from pathlib import Path
import re
import os
import itertools
import warnings
from enum import IntEnum
from typing import List, Tuple, Union
from commonroad.scenario.scenario import Scenario
from commonroad.common.file_writer import CommonRoadFileWriter, OverwriteExistingFile
from commonroad.common.file_reader import CommonRoadFileReader
from commonroad.planning.planning_problem import PlanningProblemSet

class ScenarioKeys(IntEnum):
    cooperative = 0
    country = 1
    scene = 2
    scene_id = 3
    config = 4
    predicition = 5
    predicition_id = 6
    path = 7
    tags = 8
    authors = 9
    affiliation = 10
    source = 11


class PredictionType(IntEnum):
    trajectory = 0
    set_based = 1


class CommonRoadDB:

    def __init__(self):
        self.column_names = [ScenarioKeys(0), ScenarioKeys(1), ScenarioKeys(2), ScenarioKeys(3), ScenarioKeys(4),
                             ScenarioKeys(5), ScenarioKeys(6), ScenarioKeys(7), ScenarioKeys(8), ScenarioKeys(9),
                             ScenarioKeys(10),ScenarioKeys(11)]
        self.db = None

    def __str__(self):
        return self.db.__str__()

    @classmethod
    def init_db_from_root(cls, root_path:str) -> 'CommonRoadDB':
        file_paths = list(Path(root_path).rglob("*.xml"))
        commonroad_db = cls()
        data = commonroad_db.parse_scenario_list(file_paths)
        commonroad_db.db = DataFrame(data, columns=commonroad_db.column_names)
        return commonroad_db

    def _parse_scenario_id(self, name, path=None) -> list:
        # check correctness of id
        if not (name.count('_') == 3 and name.count('-') in [2, 3]):
            warnings.warn('not a valid scenario id: ' + name)
        # split
        if name[0:2] == 'C-':
            cooperative = True
            name = name[2:]
        else:
            cooperative = False

        row = [cooperative] + re.split('_|-', name) + [path] + [None] * (len(self.column_names)-8)
        try:
            row = self._convert_type(row)
        except:
            warnings.warn('not a valid scenario id: ' + name)

        return row

    def _parse_meta_data(self, index: int):
        """Parses meta data 'authors', 'tags', and 'affiliation' from scenario file for given index. """
        file_reader = CommonRoadFileReader(self.db.at[index,ScenarioKeys.path])
        file_reader._read_header()
        self.db.at[index, ScenarioKeys.authors] = set(file_reader._meta_data['author'].split(', '))
        self.db.at[index, ScenarioKeys.tags] = set(file_reader._meta_data['tags'].split(' '))
        self.db.at[index, ScenarioKeys.source] = file_reader._meta_data['source']
        self.db.at[index, ScenarioKeys.affiliation] = file_reader._meta_data['affiliation']

    def parse_scenario_list(self,file_paths: List[Path]) -> list:
        """Parse a list of scenarios."""
        # find all filenames of scenarios
        scenario_names = []
        for path in file_paths:
            scenario_names.append(path.stem)
        data = []
        if isinstance(scenario_names,list):
            for i, scenario_name in enumerate(scenario_names):
                data.append(self._parse_scenario_id(scenario_name, str(file_paths[i])))

        return data

    @staticmethod
    def _convert_type(row):
        """Converts str to correct data types."""
        row[3] = int(row[3])
        row[4] = int(row[4])
        row[5] = PredictionType(0) if row[5] == 'T' else PredictionType(1)
        row[6] = int(row[6])
        return row

    def make_new_id(self, original_id: Union[List[str],str], existing_map=True) -> Tuple[DataFrame, int]:
        # create new id
        if type(original_id) != list:
            row_data = self._parse_scenario_id(original_id)
        else:
            row_data = original_id

        if existing_map is True:
            request:DataFrame = self.db.loc[(self.db[ScenarioKeys.cooperative] == row_data[0])
                               & (self.db[ScenarioKeys.country] == row_data[1])
                               & (self.db[ScenarioKeys.scene] == row_data[2])
                               & (self.db[ScenarioKeys.scene_id] == row_data[3])
                               & (self.db[ScenarioKeys.predicition] == row_data[5])]
            # print(request)
            if len(request) > 0:
                row_data[ScenarioKeys.config] = 1 + request[ScenarioKeys.config].max()
            else:
                row_data[ScenarioKeys.config] = 1

            if len(request) > 0:
                orig_index = request[ScenarioKeys.config].idxmax()
            else:
                orig_index = None

        else:
            request: DataFrame = self.db.loc[(self.db[ScenarioKeys.cooperative] == row_data[0])
                                             & (self.db[ScenarioKeys.country] == row_data[1])
                                             & (self.db[ScenarioKeys.scene] == row_data[2])]
            # print(request)
            if len(request) > 0:
                row_data[ScenarioKeys.scene_id] = 1 + request[ScenarioKeys.scene_id].max()
            else:
                row_data[ScenarioKeys.scene_id] = 1

            row_data[ScenarioKeys.config] = 1

            orig_index = None


        new_row = DataFrame([row_data],columns=self.column_names)
        return new_row, orig_index

    @staticmethod
    def get_benchmark_id(df:DataFrame):
        id_list = []
        for index, row in df.iterrows():
            id = ''
            id += 'C-' if row[ScenarioKeys.cooperative] is True else ''
            id += row[ScenarioKeys.country] + '_' + row[ScenarioKeys.scene] + '-' + str(row[ScenarioKeys.scene_id])
            id += '_' + str(row[ScenarioKeys.config]) + '_'
            id += 'T-' if row[ScenarioKeys.predicition] == PredictionType.trajectory else 'S-'
            id += str(row[ScenarioKeys.predicition_id])
            id_list.append(id)
        return id_list

    def _create_file_for_new_scenario(self, new_row: DataFrame, scenario: Scenario, planning_problem_set: PlanningProblemSet, new_path):
        # assemble meta data
        authors = ', '.join(list(new_row.at[0,ScenarioKeys.authors]))
        affiliation = new_row.at[0,ScenarioKeys.affiliation]
        source = new_row.at[0, ScenarioKeys.source]
        tags = ' '.join(list(new_row.at[0,ScenarioKeys.tags]))
        scenario.benchmark_id = self.get_benchmark_id(new_row)[0]

        #write file
        file_writer = CommonRoadFileWriter(scenario, planning_problem_set, authors, affiliation, source, tags)
        file_writer.write_to_file(os.path.join(new_path,scenario.benchmark_id + '.xml'), overwrite_existing_file=OverwriteExistingFile.ALWAYS)

        # update db
        new_row.at[0,ScenarioKeys.path] = os.path.join(new_path,scenario.benchmark_id + '.xml')
        return new_row

    def _replace_lanelet_network(self, scenario:Scenario, orig_path:str):
        orig_lanelet_network = CommonRoadFileReader(orig_path).open_lanelet_network()
        scenario.lanelet_network = orig_lanelet_network
        return scenario

    def get_path(self, benchmark_id: str) -> str:
        """Returns path for a given benchmark id."""
        row_data = self._parse_scenario_id( benchmark_id)
        request:DataFrame = self.db.loc[(self.db[ScenarioKeys.cooperative] == row_data[0])
                           & (self.db[ScenarioKeys.country] == row_data[1])
                           & (self.db[ScenarioKeys.scene] == row_data[2])
                           & (self.db[ScenarioKeys.scene_id] == row_data[3])
                           & (self.db[ScenarioKeys.scene_id] == row_data[4])
                           & (self.db[ScenarioKeys.predicition] == row_data[5])
                           & (self.db[ScenarioKeys.predicition] == row_data[6])]

        if len(request.index) > 1:
            warnings.warn('More than one entry for ' + benchmark_id)

        return request.loc[0][ScenarioKeys.path]

    def _update_meta_data(self, orig_index: Union[None,int], new_row:DataFrame, add_authors, add_tags, delete_tags, source=None, affiliation=None):
        """Adds meta from orig_row to new_row and updates it."""

        def update_column(new_row:DataFrame, key:ScenarioKeys, orig_index: int, add_value=[], delete_value=[]):
            # add / delete values
            if orig_index is not None:
                if self.db.at[orig_index, key] is None:
                    self._parse_meta_data(orig_index)
                new_row.at[0,key] = self.db.at[orig_index, key]
            else:
                new_row.at[0, key] = set()

            if isinstance(new_row.at[0,key], set):
                new_row.at[0, key].update(set(add_value))
                new_row.at[0, key] = new_row.at[0, key].difference(set(delete_value))

        update_column(new_row, ScenarioKeys.authors, orig_index, add_authors)
        update_column(new_row, ScenarioKeys.tags, orig_index, add_tags, delete_tags)
        if affiliation is None:
            update_column(new_row, ScenarioKeys.affiliation, orig_index)
        else:
            new_row.at[0, ScenarioKeys.affiliation] = affiliation

        if source is None:
            update_column(new_row, ScenarioKeys.source, orig_index)
        else:
            new_row.at[0, ScenarioKeys.source] = source


    def create_new_scenario(self, scenario: Scenario, planning_problem_set: PlanningProblemSet, folder_path:str, original_id: Union[List[str],str]=None, identical_map=False, new_id:str=None,
                            add_authors:List[str]=None, add_tags=None, delete_tags=None, source=None, affiliation=None, keep_meta=True):
        """Creates new database entry from scenario and creates file in folder_path."""
        if identical_map is True and new_id is None:
            new_row, orig_index = self.make_new_id(original_id)
            orig_path = self.db.at[orig_index,ScenarioKeys.path]
            scenario = self._replace_lanelet_network(scenario,orig_path)
        elif identical_map is False and new_id is None:
            new_row, orig_index = self.make_new_id(original_id, existing_map=False)
        elif new_id is not None:
            orig_index = None
            new_row = self._parse_scenario_id(new_id)
        else:
            raise NotImplementedError()

        if not keep_meta:
            orig_index = None

        self._update_meta_data(orig_index, new_row, add_authors=add_authors, add_tags=add_tags, delete_tags=delete_tags, source=source, affiliation=affiliation)
        new_row = self._create_file_for_new_scenario(new_row, scenario, planning_problem_set, folder_path)
        self.db = self.db.append(new_row, ignore_index=True)

        return new_row

