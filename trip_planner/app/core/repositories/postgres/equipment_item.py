"""Gear checklist stored in the trip planner database."""

import sqlmodel

from trip_planner.app.core.repositories.postgres import base
from trip_planner.app.core.schemas import trip
from trip_planner.app.core.sql_models import equipment


class EquipmentItemRepository(base.BasePostgresRepository):
    """Read access to the `equipment_items` table.

    The agents know an item by its slug, which they call `item_id`.
    """

    async def list_all(self) -> list[trip.EquipmentItem]:
        """Returns every gear item in catalogue (insertion) order."""
        rows = await self._fetch_models(
            sqlmodel.select(equipment.EquipmentItem).order_by(
                equipment.EquipmentItem.id
            )
        )
        return [_to_equipment_item(row) for row in rows]


def _to_equipment_item(row: equipment.EquipmentItem) -> trip.EquipmentItem:
    """Returns the agents' view of an `equipment_items` row."""
    return trip.EquipmentItem(
        item_id=row.slug,
        name=row.name,
        aliases=list(row.aliases),
        required_when=row.required_when.value,
        rentable=row.rentable,
        rental_price_eur=float(row.rental_price_eur or 0),
    )
