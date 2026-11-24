"""Rental gear the company owns, stored in the trip planner database."""

import sqlmodel

from trip_planner.app.core.repositories.postgres import base
from trip_planner.app.core.sql_models import equipment


class RentalStockRepository(base.BasePostgresRepository):
    """Read access to the `rental_stock` table."""

    async def units_by_item(self) -> dict[str, int]:
        """Returns the units owned of every rentable item, by item slug."""
        rows = await self._fetch_rows(
            sqlmodel.select(
                equipment.EquipmentItem.slug,
                equipment.RentalStock.units_total,
            )
            .join(
                equipment.RentalStock,
                equipment.RentalStock.equipment_item_id
                == equipment.EquipmentItem.id,
            )
            .order_by(equipment.EquipmentItem.id)
        )
        return {slug: units for slug, units in rows}
