from pathlib import Path
from tempfile import TemporaryDirectory
from typing import (
    Optional,
)

from scenario_factory.scenario_config import ScenarioFactoryConfig


class PipelineContext:
    """The context contains metadata that needs to be passed between the different stages of the scenario factory pipeline"""

    def __init__(
        self,
        base_temp_path: Optional[Path] = None,
        scenario_factory_config: Optional[ScenarioFactoryConfig] = None,
    ):
        self._base_temp_path = base_temp_path

        if scenario_factory_config is None:
            self._scenario_factory_config = ScenarioFactoryConfig()
        else:
            self._scenario_factory_config = scenario_factory_config

    def get_temporary_folder(self, folder_name: str) -> Path:
        """
        Get a path to a new temporary directory, that is guaranteed to exist.
        """
        if self._base_temp_path is None:
            self._temp_dir_ref = TemporaryDirectory()
            self._base_temp_path = Path(self._temp_dir_ref.name)
        temp_folder = self._base_temp_path.joinpath(folder_name)
        temp_folder.mkdir(parents=True, exist_ok=True)
        return temp_folder

    def get_scenario_factory_config(self) -> ScenarioFactoryConfig:
        return self._scenario_factory_config
