"""Rental gear stock of one simulation run."""

from collections.abc import Mapping

from trip_planner.app.core.schemas import trip


class RentalStockRepository:
    """In-memory stock of one run, counted down by its reservations.

    Starts from the units the company owns (the `rental_stock` table) and
    is built once per run, so runs never see each other's reservations.
    """

    def __init__(self, units_by_item: Mapping[str, int]):
        """Initializes the repository.

        Args:
            units_by_item: Units owned of every rentable item, by item id.
        """
        self._stock: dict[str, int] = dict(units_by_item)
        self._reservations: dict[str, trip.RentalReservation] = {}

    def stock_of(self, item_id: str) -> int | None:
        """Returns units in stock, or None when the item is never rented."""
        return self._stock.get(item_id)

    def get_reservation(self, booking_id: str) -> trip.RentalReservation | None:
        """Returns the reservation of a booking, if any."""
        return self._reservations.get(booking_id)

    def reserve(
        self, booking_id: str, item_ids: list[str], prices: dict[str, float]
    ) -> tuple[trip.RentalReservation, list[str]]:
        """Reserves one unit of each item for a booking.

        Reserving again for the same booking returns the first reservation,
        so a retried call never takes stock twice.

        Args:
            booking_id: Booking the gear is for.
            item_ids: Gear item ids to reserve.
            prices: Rental price of each item id.

        Returns:
            The reservation and the items that were out of stock or unknown.
        """
        existing = self._reservations.get(booking_id)
        if existing is not None:
            return existing, []
        reserved, unavailable = [], []
        for item_id in dict.fromkeys(item_ids):
            if self._stock.get(item_id, 0) > 0:
                self._stock[item_id] -= 1
                reserved.append(item_id)
            else:
                unavailable.append(item_id)
        reservation = trip.RentalReservation(
            booking_id=booking_id,
            items=reserved,
            total_price_eur=sum(prices.get(i, 0.0) for i in reserved),
        )
        self._reservations[booking_id] = reservation
        return reservation, unavailable
