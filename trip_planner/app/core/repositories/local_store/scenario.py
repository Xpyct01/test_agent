"""Test scenarios stored as YAML files."""

import pathlib

import yaml

from trip_planner.app.core import errors
from trip_planner.app.core.schemas import simulation


class ScenarioRepository:
    """Loads scenarios from a directory of `<name>.yaml` files."""

    def __init__(self, default_path: pathlib.Path):
        """Initializes the repository.

        Args:
            default_path: Scenario returned when no name is given; its
                directory holds the other scenarios.
        """
        self._default_path = default_path

    def load(self, name: str | None = None) -> simulation.Scenario:
        """Returns a scenario by file stem, or the default one.

        Raises:
            errors.InvalidRequestError: No scenario has that name.
        """
        path = self._default_path
        if name is not None:
            path = self._default_path.parent / f'{pathlib.Path(name).stem}.yaml'
        if not path.is_file():
            raise errors.InvalidRequestError(f'Unknown scenario: {name!r}')
        with path.open(encoding='utf-8') as file:
            return simulation.Scenario.model_validate(yaml.safe_load(file))
