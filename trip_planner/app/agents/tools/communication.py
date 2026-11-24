"""Tools that let an agent talk to its neighbours on the message bus."""

from typing import Annotated

from langgraph import prebuilt

from trip_planner.app.agents.tools import base
from trip_planner.app.core import errors
from trip_planner.app.core.schemas import tools
from trip_planner.app.core.schemas import trip

_HUMAN_PREFIX = 'human_'


class CommunicationTools(base.BaseTools):
    """Messaging tools the agents can call."""

    async def send_message(
        self,
        recipient: str,
        content: str,
        participant_id: Annotated[str, prebuilt.InjectedState('participant_id')],
    ) -> dict[str, object]:
        """Sends a message; it is delivered at the next tick.

        Args:
            recipient: Id of a participant you are connected to.
            content: The full message; the recipient sees nothing else.
            participant_id: Your own id, filled in by the system.

        Returns:
            The delivery receipt, or an error naming the allowed recipients.
        """
        context = self._run_context_provider.current()
        try:
            context.send_message(participant_id, recipient, content)
        except errors.InvalidRequestError as error:
            return base.to_result(tools.ToolError(error=str(error)))
        return base.to_result(
            tools.MessageResult(
                delivered_to=recipient, delivery_tick=context.tick + 1
            )
        )

    async def deliver_final_plan(
        self,
        plan: trip.TripPlan,
        participant_id: Annotated[str, prebuilt.InjectedState('participant_id')],
    ) -> dict[str, object]:
        """Hands the final, confirmed trip plan to your customer.

        Call it once, only after the booking is confirmed and the rental
        gear is reserved.

        Args:
            plan: The plan, built only from tool results and confirmations.
            participant_id: Your own id, filled in by the system.

        Returns:
            The delivery receipt, or an error when the plan does not match
            the booking or the rental reservation.
        """
        context = self._run_context_provider.current()
        problem = _check_plan(plan, context.bookings.get(plan.booking_id),
                              context.rental_stock.get_reservation(
                                  plan.booking_id))
        if problem is not None:
            return base.to_result(
                tools.ToolError(error=f'Plan rejected: {problem}')
            )
        customer = next(
            (n for n in context.bus.neighbours(participant_id)
             if n.startswith(_HUMAN_PREFIX)),
            None,
        )
        if customer is None:
            return base.to_result(
                tools.ToolError(error='You have no customer to deliver to.')
            )
        context.send_message(participant_id, customer, _format_plan(plan))
        context.final_plan = plan
        context.record(
            'final_plan', participant_id, plan=plan.model_dump(mode='json')
        )
        return base.to_result(
            tools.FinalPlanResult(
                delivered_to=customer, outcome_key=plan.outcome_key()
            )
        )


def _check_plan(
    plan: trip.TripPlan,
    booking: trip.Booking | None,
    reservation: trip.RentalReservation | None,
) -> str | None:
    if booking is None:
        return f'booking {plan.booking_id!r} does not exist.'
    if booking.trail_id != plan.trail_id or booking.date != plan.date:
        return (
            f'booking {booking.booking_id} is for {booking.trail_id} on '
            f'{booking.date}, not {plan.trail_id} on {plan.date}.'
        )
    reserved = set(reservation.items) if reservation else set()
    if not set(plan.gear_to_rent) <= reserved:
        missing = sorted(set(plan.gear_to_rent) - reserved)
        return (
            f'gear {missing} is not reserved for this booking yet. If you '
            'asked agent_b to reserve it, end your turn and wait for its '
            'confirmation; do not remove items from the plan.'
        )
    return None


def _format_plan(plan: trip.TripPlan) -> str:
    lines = [
        f'Your trip is confirmed (booking {plan.booking_id}).',
        f'Trail: {plan.trail_name} ({plan.trail_id})',
        f'Date: {plan.date.isoformat()}, meet at {plan.start_time} '
        f'with guide {plan.guide_name}.',
        f'Weather: {plan.weather_summary}',
        f'Bring: {", ".join(plan.gear_to_bring) or "nothing extra"}',
        f'Rented for you: {", ".join(plan.gear_to_rent) or "nothing"}',
        f'Please buy: {", ".join(plan.gear_to_buy) or "nothing"}',
    ]
    lines += [f'Note: {note}' for note in plan.notes]
    return '\n'.join(lines)
