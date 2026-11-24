"""Trails stored in the trip planner database."""

from collections.abc import Sequence

from trip_planner.app.core.repositories.postgres import base
from trip_planner.app.core.sql_models import trail

# Curated by the company, not on the park's pages: a re-index keeps them.
_CURATED_COLUMNS = (
    'massif',
    'start_point',
    'route_type',
    'rockfall_risk',
    'highlights',
)


class TrailRepository(base.BasePostgresRepository):
    """Access to the `trails` table."""

    async def upsert(self, trails: Sequence[trail.Trail]) -> int:
        """Inserts trails, updating the ones whose code already exists.

        An existing trail keeps its curated columns (massif, start point,
        route type, rockfall risk, highlights).

        Args:
            trails: Trails to write, with distinct codes; `id` is ignored.

        Returns:
            The number of rows written.
        """
        rows = await self._upsert(
            trails,
            conflict_columns=('code',),
            returning=('id',),
            preserved_columns=_CURATED_COLUMNS,
        )
        return len(rows)
