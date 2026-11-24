"""Recommended gear products stored in the trip planner database."""

from collections.abc import Sequence

from trip_planner.app.core.repositories.postgres import base
from trip_planner.app.core.sql_models import equipment

_KEY_COLUMNS = ('category_id', 'item_type', 'product')


class GearProductRepository(base.BasePostgresRepository):
    """Access to the `gear_products` table."""

    async def upsert(self, products: Sequence[equipment.GearProduct]) -> int:
        """Inserts products, updating the ones already listed.

        A product is identified by its category, item type and name. An
        existing product keeps the equipment item it was mapped to.

        Args:
            products: Products with distinct keys; `id` is ignored.

        Returns:
            The number of rows written.
        """
        rows = await self._upsert(
            products,
            conflict_columns=_KEY_COLUMNS,
            returning=('id',),
            preserved_columns=('equipment_item_id',),
        )
        return len(rows)
