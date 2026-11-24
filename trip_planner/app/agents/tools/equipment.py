"""Tools over hiking gear: requirements, rental stock and reservations."""

import datetime

from trip_planner.app.agents.tools import base
from trip_planner.app.core import errors
from trip_planner.app.core.repositories.postgres import (
    equipment_item as equipment_item_lib,
)
from trip_planner.app.core.repositories.postgres import trail as trail_lib
from trip_planner.app.core.schemas import tools
from trip_planner.app.ml.equipment_check import core as equipment_check_lib
from trip_planner.app.ml.weather_forecast import abstract as weather_lib


class EquipmentTools(base.BaseTools):
    """Equipment tools the agents can call."""

    def __init__(
        self,
        equipment_check: equipment_check_lib.EquipmentCheck,
        equipment_repository: equipment_item_lib.EquipmentItemRepository,
        trail_repository: trail_lib.TrailRepository,
        weather_forecast: weather_lib.AbstractWeatherForecast,
        **base_kwargs,
    ):
        """Initializes the tools.

        Args:
            equipment_check: Rule-based gear requirements.
            equipment_repository: The gear catalogue.
            trail_repository: The trail catalogue.
            weather_forecast: Daily forecast, for weather-dependent gear.
            **base_kwargs: Arguments of `base.BaseTools`.
        """
        super().__init__(**base_kwargs)
        self._equipment_check = equipment_check
        self._equipment_repository = equipment_repository
        self._trail_repository = trail_repository
        self._weather_forecast = weather_forecast

    async def check_equipment(
        self,
        trail_id: str,
        date: str,
        owned_items: list[str],
        has_joint_issues: bool,
    ) -> dict[str, object]:
        """Lists the gear a trip requires and what the customer still lacks.

        Args:
            trail_id: Id of the booked trail.
            date: Trip date, YYYY-MM-DD.
            owned_items: Gear the customer owns, in their words, e.g.
                ["hiking boots", "rain jacket"].
            has_joint_issues: Whether the customer has a joint condition.

        Returns:
            Required item ids split into already_owned, missing_rentable
            (the company can rent them) and missing_to_buy, with the reason
            each item is required.
        """
        trail = await self._trail_repository.get(trail_id)
        if trail is None:
            return base.to_result(
                tools.ToolError(error=f'Unknown trail_id {trail_id!r}.')
            )
        try:
            trip_date = datetime.date.fromisoformat(date)
        except ValueError:
            return base.to_result(
                tools.ToolError(error=f'Date {date!r} is not YYYY-MM-DD.')
            )
        context = self._run_context_provider.current()
        # The forecast is cached per batch; this never calls the network
        # again after get_weather_forecast succeeded.
        try:
            days = await self._weather_forecast.forecast(context.planning_date)
        except errors.TransientActionError:
            days = []
        day = next((d for d in days if d.date == trip_date), None)
        return base.to_result(
            await self._equipment_check.check(
                trail, day, owned_items, has_joint_issues
            )
        )

    async def check_rental_stock(self, item_ids: list[str]) -> dict[str, object]:
        """Checks how many units of each gear item the rental shop has.

        Args:
            item_ids: Gear item ids, e.g. ["helmet", "trekking_poles"].

        Returns:
            Units in stock per rentable item, and ids that are unknown or
            never rented.
        """
        context = self._run_context_provider.current()
        in_stock, unknown = {}, []
        for item_id in item_ids:
            units = context.rental_stock.stock_of(item_id)
            if units is None:
                unknown.append(item_id)
            else:
                in_stock[item_id] = units
        return base.to_result(
            tools.RentalStockResult(in_stock=in_stock, unknown_items=unknown)
        )

    async def reserve_rental_gear(
        self, booking_id: str, item_ids: list[str]
    ) -> dict[str, object]:
        """Reserves rental gear for a booking (safe to call again).

        Args:
            booking_id: Booking id returned by create_booking.
            item_ids: Gear item ids to reserve, one unit each.

        Returns:
            The reservation with its total price, and items that could not
            be reserved. May fail transiently; then retry.
        """
        context = self._run_context_provider.current()
        if context.bookings.get(booking_id) is None:
            return base.to_result(
                tools.ToolError(error=f'Unknown booking_id {booking_id!r}.')
            )
        prices = {
            item.item_id: item.rental_price_eur
            for item in await self._equipment_repository.list_all()
        }

        async def reserve() -> tools.RentalReservationResult:
            reservation, unavailable = context.rental_stock.reserve(
                booking_id, item_ids, prices
            )
            return tools.RentalReservationResult(
                reservation=reservation, unavailable_items=unavailable
            )

        return base.to_result(
            await self._call_with_faults('reserve_rental_gear', reserve)
        )
