"""Catalogue of the park's hiking trails."""

import pathlib

from trip_planner.app.core.repositories.local_store import base
from trip_planner.app.core.schemas import trip


class TrailRepository(base.BaseJsonRepository):
    """Read-only access to `trails.json`."""

    def __init__(self, path: pathlib.Path):
        """Initializes the repository.

        Args:
            path: The trails file.
        """
        super().__init__(path)
        self._trails = {
            trail.trail_id: trail
            for trail in (trip.Trail.model_validate(raw) for raw in self._raw)
        }

    def list_all(self) -> list[trip.Trail]:
        """Returns every trail in catalogue order."""
        return list(self._trails.values())

    def get(self, trail_id: str) -> trip.Trail | None:
        """Returns one trail, or None for an unknown id."""
        return self._trails.get(trail_id)
