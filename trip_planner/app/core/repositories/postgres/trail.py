"""Trails stored in the trip planner database."""

from collections.abc import Sequence

import sqlmodel

from trip_planner.app.core.repositories.postgres import base
from trip_planner.app.core.schemas import trip
from trip_planner.app.core.sql_models import trail as trail_model

# Curated by the company, not on the park's pages: a re-index keeps them.
_CURATED_COLUMNS = (
    'massif',
    'start_point',
    'route_type',
    'rockfall_risk',
    'highlights',
)


class TrailRepository(base.BasePostgresRepository):
    """Access to the `trails` table.

    The agents know a trail by its code, which they call `trail_id`.
    """

    async def list_all(self) -> list[trip.Trail]:
        """Returns every trail in catalogue (insertion) order."""
        rows = await self._fetch_models(
            sqlmodel.select(trail_model.Trail).order_by(trail_model.Trail.id)
        )
        return [_to_trail(row) for row in rows]

    async def get(self, trail_id: str) -> trip.Trail | None:
        """Returns one trail by code, or None for an unknown code."""
        rows = await self._fetch_models(
            sqlmodel.select(trail_model.Trail).where(
                trail_model.Trail.code == trail_id
            )
        )
        return _to_trail(rows[0]) if rows else None

    async def upsert(self, trails: Sequence[trail_model.Trail]) -> int:
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


def _to_trail(row: trail_model.Trail) -> trip.Trail:
    """Returns the agents' view of a `trails` row."""
    return trip.Trail(
        trail_id=row.code,
        name=row.name,
        massif=row.massif,
        start_point=row.start_point,
        distance_km=row.length_km,
        elevation_gain_m=row.ascent_m,
        duration_h=row.duration_h,
        difficulty=row.difficulty.value,
        route_type=row.route_type.value if row.route_type else None,
        highlights=list(row.highlights),
        rockfall_risk=row.rockfall_risk,
        source_url=row.source_url,
    )
