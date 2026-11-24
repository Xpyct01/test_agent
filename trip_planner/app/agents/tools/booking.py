"""Tools over guide availability and bookings."""

from collections.abc import Sequence
import datetime

from trip_planner.app.agents.tools import base
from trip_planner.app.core.repositories.postgres import guide as guide_lib
from trip_planner.app.core.repositories.postgres import trail as trail_lib
from trip_planner.app.core.schemas import tools
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.environment import run_context as run_context_lib

_BOOKING_WINDOW_DAYS = 14


class BookingTools(base.BaseTools):
    """Booking tools the agents can call."""

    def __init__(
        self,
        guide_repository: guide_lib.GuideRepository,
        trail_repository: trail_lib.TrailRepository,
        **base_kwargs,
    ):
        """Initializes the tools.

        Args:
            guide_repository: The guide roster.
            trail_repository: The trail catalogue.
            **base_kwargs: Arguments of `base.BaseTools`.
        """
        super().__init__(**base_kwargs)
        self._guide_repository = guide_repository
        self._trail_repository = trail_repository

    async def check_guide_availability(
        self, dates: list[str]
    ) -> dict[str, object]:
        """Checks which guides are free on each date.

        Args:
            dates: Dates to check, YYYY-MM-DD.

        Returns:
            For each date: its weekday and the free guides (empty when no
            guide works that day). May fail transiently; then retry.
        """
        parsed = []
        for date in dates:
            try:
                parsed.append(datetime.date.fromisoformat(date))
            except ValueError:
                return base.to_result(
                    tools.ToolError(error=f'Date {date!r} is not YYYY-MM-DD.')
                )
        context = self._run_context_provider.current()

        async def lookup() -> tools.GuideAvailabilityResult:
            guides = await self._guide_repository.list_all()
            return tools.GuideAvailabilityResult(
                dates=[
                    tools.DateAvailability(
                        date=date,
                        weekday=date.strftime('%A'),
                        available_guides=_free_guides(guides, context, date),
                    )
                    for date in parsed
                ]
            )

        return base.to_result(
            await self._call_with_faults('check_guide_availability', lookup)
        )

    async def create_booking(
        self,
        trail_id: str,
        date: str,
        start_time: str,
        customer_name: str,
        party_size: int,
        guide_name: str,
    ) -> dict[str, object]:
        """Books a guided trip (safe to call again: same input, same booking).

        Args:
            trail_id: Id of an open trail.
            date: Trip date, YYYY-MM-DD, on which the guide is free.
            start_time: Meeting time, HH:MM.
            customer_name: Full name of the customer.
            party_size: Number of hikers.
            guide_name: Name of a guide free on that date.

        Returns:
            The booking with its booking_id, or an error explaining what to
            fix. May fail transiently; then retry.
        """
        context = self._run_context_provider.current()
        problem = None
        trip_date = None
        try:
            trip_date = datetime.date.fromisoformat(date)
            datetime.time.fromisoformat(start_time)
        except ValueError:
            problem = 'date must be YYYY-MM-DD and start_time HH:MM.'
        guide = await self._guide_repository.get(guide_name)
        if problem is None and (
            existing := context.bookings.find(trail_id, trip_date, customer_name)
        ):
            # A retry of a booking that was already written: idempotent.
            return base.to_result(
                tools.BookingResult(booking=existing, already_existed=True)
            )
        if problem is None:
            if await self._trail_repository.get(trail_id) is None:
                problem = f'unknown trail_id {trail_id!r}.'
            elif (closure := context.trail_status.get_closure(trail_id)):
                problem = f'trail {trail_id} is closed: {closure.reason}'
            elif not (
                0 <= (trip_date - context.planning_date).days
                < _BOOKING_WINDOW_DAYS
            ):
                problem = f'{date} is outside the booking window.'
            elif guide is None:
                problem = f'unknown guide {guide_name!r}.'
            elif guide.name not in _free_guides(
                await self._guide_repository.list_all(), context, trip_date
            ):
                problem = f'{guide.name} is not available on {date}.'
            elif party_size > guide.max_party_size:
                problem = f'party of {party_size} exceeds the guide limit.'
        if problem is not None:
            return base.to_result(
                tools.ToolError(error=f'Booking refused: {problem}')
            )

        async def book() -> tools.BookingResult:
            booking, existed = context.bookings.create(
                trail_id, trip_date, start_time, customer_name, party_size,
                guide.name,
            )
            return tools.BookingResult(booking=booking, already_existed=existed)

        return base.to_result(
            await self._call_with_faults('create_booking', book)
        )


def _free_guides(
    guides: Sequence[trip.Guide],
    context: run_context_lib.RunContext,
    date: datetime.date,
) -> list[str]:
    """Returns the guides who work on `date` and have no booking on it."""
    weekday = date.strftime('%A')
    return [
        guide.name
        for guide in guides
        if weekday not in guide.unavailable_weekdays
        and not context.bookings.is_guide_booked(guide.name, date)
    ]
