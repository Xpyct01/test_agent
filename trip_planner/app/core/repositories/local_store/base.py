"""Shared loading of the repositories backed by local data files."""

import json
import pathlib
from typing import Any


class BaseJsonRepository:
    """Reads one JSON file of the data directory once, at construction."""

    def __init__(self, path: pathlib.Path):
        """Initializes the repository.

        Args:
            path: JSON file the repository serves.
        """
        self._path = path
        self._raw = self._load()

    def _load(self) -> Any:
        with self._path.open(encoding='utf-8') as file:
            return json.load(file)
