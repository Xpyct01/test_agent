"""Mountain guides stored in the trip planner database."""

import sqlalchemy as sa
import sqlmodel

from trip_planner.app.core.repositories.postgres import base
from trip_planner.app.core.schemas import trip
from trip_planner.app.core.sql_models import guide as guide_model

# ISO weekday numbers (1 = Monday) to English names, independent of locale.
_WEEKDAY_NAMES = (
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
)


class GuideRepository(base.BasePostgresRepository):
    """Read access to the `guides` table; inactive guides are left out."""

    async def list_all(self) -> list[trip.Guide]:
        """Returns every active guide, by name."""
        rows = await self._fetch_models(
            sqlmodel.select(guide_model.Guide)
            .where(guide_model.Guide.is_active)
            .order_by(guide_model.Guide.full_name)
        )
        return [_to_guide(row) for row in rows]

    async def get(self, name: str) -> trip.Guide | None:
        """Returns one active guide by name (case-insensitive), or None."""
        rows = await self._fetch_models(
            sqlmodel.select(guide_model.Guide).where(
                guide_model.Guide.is_active,
                sa.func.lower(guide_model.Guide.full_name)
                == name.strip().lower(),
            )
        )
        return _to_guide(rows[0]) if rows else None


def _to_guide(row: guide_model.Guide) -> trip.Guide:
    """Returns the agents' view of a `guides` row."""
    return trip.Guide(
        name=row.full_name,
        unavailable_weekdays=[
            _WEEKDAY_NAMES[day - 1] for day in sorted(row.unavailable_weekdays)
        ],
        max_party_size=row.max_party_size,
    )
