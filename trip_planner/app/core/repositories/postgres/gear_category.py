"""Gear categories stored in the trip planner database."""

from collections.abc import Sequence

from trip_planner.app.core.repositories.postgres import base
from trip_planner.app.core.sql_models import equipment


class GearCategoryRepository(base.BasePostgresRepository):
    """Access to the `gear_categories` table."""

    async def upsert(
        self, categories: Sequence[equipment.GearCategory]
    ) -> dict[str, int]:
        """Inserts the categories whose name is not stored yet.

        Args:
            categories: Categories with distinct names; `id` is ignored.

        Returns:
            The database id of every given category, by name.
        """
        rows = await self._upsert(
            categories, conflict_columns=('name',), returning=('name', 'id')
        )
        return {name: category_id for name, category_id in rows}
