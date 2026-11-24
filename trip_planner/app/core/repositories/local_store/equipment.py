"""Catalogue of hiking gear."""

import pathlib

from trip_planner.app.core.repositories.local_store import base
from trip_planner.app.core.schemas import trip


class EquipmentRepository(base.BaseJsonRepository):
    """Read-only access to `equipment.json`."""

    def __init__(self, path: pathlib.Path):
        """Initializes the repository.

        Args:
            path: The equipment file.
        """
        super().__init__(path)
        self._items = [trip.EquipmentItem.model_validate(raw) for raw in self._raw]

    def list_all(self) -> list[trip.EquipmentItem]:
        """Returns every gear item in catalogue order."""
        return list(self._items)

    def get(self, item_id: str) -> trip.EquipmentItem | None:
        """Returns one gear item, or None for an unknown id."""
        return next((i for i in self._items if i.item_id == item_id), None)
