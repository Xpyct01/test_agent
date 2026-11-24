"""Guided trips booked by customers and the gear rented for them."""

import datetime
import decimal
import enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

from trip_planner.app.core.sql_models import base


class BookingStatus(enum.StrEnum):
    """Lifecycle state of a booking."""

    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'


class Booking(base.TimestampMixin, table=True):
    """A guided one-day trip.

    The id is derived from the trail, date and customer (an idempotency key),
    so a retried `create_booking` call never inserts a second row. A guide
    has at most one confirmed booking per day.

    Attributes:
        id: Content-derived id, e.g. `BK-1A2B3C4D`.
        customer_id: Customer who booked the trip.
        trail_id: Booked trail.
        guide_id: Guide of the trip.
        trip_date: Day of the trip.
        start_time: Meeting time at the start point.
        party_size: Hikers in the party.
        status: Lifecycle state.
        notes: Safety notes and conditions set by the guide.
    """

    __tablename__ = 'bookings'
    __table_args__ = (
        sa.CheckConstraint('party_size > 0', name='party_size_positive'),
        sa.Index(
            'uq_bookings_guide_id_trip_date_confirmed',
            'guide_id',
            'trip_date',
            unique=True,
            postgresql_where=sa.text("status = 'confirmed'"),
        ),
        sa.Index('ix_bookings_trip_date', 'trip_date'),
    )

    id: str = sqlmodel.Field(primary_key=True, max_length=16)
    customer_id: int = sqlmodel.Field(
        foreign_key='customers.id', ondelete='RESTRICT', index=True
    )
    trail_id: int = sqlmodel.Field(
        foreign_key='trails.id', ondelete='RESTRICT', index=True
    )
    guide_id: int = sqlmodel.Field(
        foreign_key='guides.id', ondelete='RESTRICT'
    )
    trip_date: datetime.date
    start_time: datetime.time
    party_size: int = sqlmodel.Field(
        default=1, sa_column_kwargs={'server_default': '1'}
    )
    status: BookingStatus = sqlmodel.Field(
        default=BookingStatus.CONFIRMED,
        sa_type=base.pg_enum(BookingStatus, 'booking_status'),
        sa_column_kwargs={'server_default': BookingStatus.CONFIRMED.value},
    )
    notes: list[str] = sqlmodel.Field(
        default_factory=list,
        sa_type=postgresql.ARRAY(sa.Text),
        sa_column_kwargs={'server_default': '{}'},
    )


class BookingRental(base.CreatedAtMixin, table=True):
    """Units of one rentable item reserved for a booking.

    The price is copied at reservation time, so later price changes do not
    alter what the customer was quoted.

    Attributes:
        booking_id: Booking the gear is for.
        equipment_item_id: Reserved item.
        quantity: Reserved units.
        unit_price_eur: Rental price of one unit at reservation time.
    """

    __tablename__ = 'booking_rentals'
    __table_args__ = (
        sa.CheckConstraint('quantity > 0', name='quantity_positive'),
        sa.CheckConstraint(
            'unit_price_eur >= 0', name='unit_price_non_negative'
        ),
    )

    booking_id: str = sqlmodel.Field(
        primary_key=True,
        foreign_key='bookings.id',
        ondelete='CASCADE',
        max_length=16,
    )
    equipment_item_id: int = sqlmodel.Field(
        primary_key=True, foreign_key='equipment_items.id', ondelete='RESTRICT'
    )
    quantity: int = sqlmodel.Field(
        default=1, sa_column_kwargs={'server_default': '1'}
    )
    unit_price_eur: decimal.Decimal = sqlmodel.Field(
        max_digits=8, decimal_places=2
    )
