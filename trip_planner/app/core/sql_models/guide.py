"""Mountain guides of the company."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

from trip_planner.app.core.sql_models import base


class Guide(base.TimestampMixin, table=True):
    """A mountain guide and the weekdays they never work.

    Attributes:
        id: Surrogate key.
        full_name: Guide's name.
        max_party_size: Most customers the guide takes on one trip.
        unavailable_weekdays: ISO weekdays off (1 = Monday ... 7 = Sunday).
        is_active: Whether the guide takes new bookings.
    """

    __tablename__ = 'guides'
    __table_args__ = (
        sa.CheckConstraint('max_party_size > 0', name='party_size_positive'),
        sa.CheckConstraint(
            'unavailable_weekdays <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]',
            name='weekdays_iso',
        ),
    )

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    full_name: str = sqlmodel.Field(max_length=128, unique=True)
    max_party_size: int
    unavailable_weekdays: list[int] = sqlmodel.Field(
        default_factory=list,
        sa_type=postgresql.ARRAY(sa.SmallInteger),
        sa_column_kwargs={'server_default': '{}'},
    )
    is_active: bool = sqlmodel.Field(
        default=True, sa_column_kwargs={'server_default': sa.true()}
    )
