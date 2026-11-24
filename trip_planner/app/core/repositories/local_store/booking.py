"""Bookings of one simulation run."""

import datetime
import hashlib

from trip_planner.app.core.schemas import trip


class BookingRepository:
    """In-memory bookings, built once per run."""

    def __init__(self):
        """Initializes an empty repository."""
        self._bookings: dict[str, trip.Booking] = {}

    def get(self, booking_id: str) -> trip.Booking | None:
        """Returns one booking, or None for an unknown id."""
        return self._bookings.get(booking_id)

    def find(
        self, trail_id: str, date: datetime.date, customer_name: str
    ) -> trip.Booking | None:
        """Returns the booking with this content, if it was already made."""
        return self._bookings.get(_booking_id(trail_id, date, customer_name))

    def is_guide_booked(self, guide_name: str, date: datetime.date) -> bool:
        """Returns whether a guide already has a booking on a date."""
        return any(
            b.guide_name == guide_name and b.date == date
            for b in self._bookings.values()
        )

    def create(
        self,
        trail_id: str,
        date: datetime.date,
        start_time: str,
        customer_name: str,
        party_size: int,
        guide_name: str,
    ) -> tuple[trip.Booking, bool]:
        """Creates a booking, or returns the identical one made before.

        The id is derived from the booking's content (an idempotency key),
        so retrying after a failure that happened after the write never
        creates a second booking.

        Returns:
            The booking and whether it already existed.
        """
        booking_id = _booking_id(trail_id, date, customer_name)
        if booking_id in self._bookings:
            return self._bookings[booking_id], True
        booking = trip.Booking(
            booking_id=booking_id,
            trail_id=trail_id,
            date=date,
            start_time=start_time,
            customer_name=customer_name,
            party_size=party_size,
            guide_name=guide_name,
        )
        self._bookings[booking_id] = booking
        return booking, False


def _booking_id(trail_id: str, date: datetime.date, customer_name: str) -> str:
    key = f'{trail_id}|{date.isoformat()}|{customer_name.strip().lower()}'
    return 'BK-' + hashlib.sha1(key.encode()).hexdigest()[:8].upper()
