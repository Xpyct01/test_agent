"""Roster of the company's mountain guides."""

import pathlib

from trip_planner.app.core.repositories.local_store import base
from trip_planner.app.core.schemas import trip


class GuideRepository(base.BaseJsonRepository):
    """Read-only access to `guides.json`."""

    def __init__(self, path: pathlib.Path):
        """Initializes the repository.

        Args:
            path: The guides file.
        """
        super().__init__(path)
        self._guides = [trip.Guide.model_validate(raw) for raw in self._raw]

    def list_all(self) -> list[trip.Guide]:
        """Returns every guide."""
        return list(self._guides)

    def get(self, name: str) -> trip.Guide | None:
        """Returns one guide by name (case-insensitive), or None."""
        wanted = name.strip().lower()
        return next(
            (g for g in self._guides if g.name.lower() == wanted), None
        )
