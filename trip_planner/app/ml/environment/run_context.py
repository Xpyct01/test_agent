"""State of one simulation run, reachable from tools and participants."""

import contextlib
import contextvars
import dataclasses
import datetime
from collections.abc import Iterator
from typing import Any

from trip_planner.app.core import errors
from trip_planner.app.core.repositories.local_store import (
    booking as booking_lib,
)
from trip_planner.app.core.repositories.local_store import (
    rental_stock as rental_stock_lib,
)
from trip_planner.app.core.repositories.local_store import (
    trail_status as trail_status_lib,
)
from trip_planner.app.core.schemas import simulation
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.environment import message_bus as message_bus_lib
from trip_planner.app.ml.environment import trajectory as trajectory_lib
from trip_planner.app.ml.fault_injection import core as fault_injection_lib


@dataclasses.dataclass
class RunContext:
    """Everything that belongs to one run and must not leak into the next.

    Attributes:
        run_id: Unique id of the run.
        batch_id: Id of the batch the run belongs to.
        run_index: Position of the run in its batch.
        scenario: The scenario being simulated.
        planning_date: The simulated "today".
        fault_seed: Seed of the fault injector.
        bus: Message bus between the participants.
        recorder: Event log of the run.
        fault_injector: Random failures of the environment actions.
        trail_status: Trail closures of the scenario.
        bookings: Bookings made during the run.
        rental_stock: Rental gear stock of the run.
        tick: Current tick.
        final_plan: Plan handed to the customer, once delivered.
        customer_done: Whether the customer closed the conversation.
    """

    run_id: str
    batch_id: str
    run_index: int
    scenario: simulation.Scenario
    planning_date: datetime.date
    fault_seed: int
    bus: message_bus_lib.MessageBus
    recorder: trajectory_lib.TrajectoryRecorder
    fault_injector: fault_injection_lib.FaultInjector
    trail_status: trail_status_lib.TrailStatusRepository
    bookings: booking_lib.BookingRepository
    rental_stock: rental_stock_lib.RentalStockRepository
    tick: int = 0
    final_plan: trip.TripPlan | None = None
    customer_done: bool = False

    def record(
        self, event_type: simulation.EventType, participant: str, **data: Any
    ) -> None:
        """Appends an event at the current tick."""
        self.recorder.record(self.tick, event_type, participant, **data)

    def send_message(
        self, sender: str, recipient: str, content: str
    ) -> simulation.Message:
        """Sends a message over the bus and records it.

        Raises:
            errors.InvalidRequestError: The bus rejected the message.
        """
        try:
            message = self.bus.send(sender, recipient, content, self.tick)
        except errors.InvalidRequestError as error:
            self.record(
                'message_rejected', sender, recipient=recipient,
                reason=str(error),
            )
            raise
        self.record('message', sender, recipient=recipient, content=content)
        return message


class RunContextProvider:
    """Hands out the run context of the task that asks for it.

    Agents and tools are built once and shared by every run; the active
    run lives in a context variable, so concurrent runs stay isolated.
    """

    def __init__(self):
        """Initializes the provider with no active run."""
        self._current: contextvars.ContextVar[RunContext] = (
            contextvars.ContextVar('run_context')
        )

    @contextlib.contextmanager
    def activate(self, context: RunContext) -> Iterator[RunContext]:
        """Makes `context` the active run inside the `with` block."""
        token = self._current.set(context)
        try:
            yield context
        finally:
            self._current.reset(token)

    def current(self) -> RunContext:
        """Returns the active run.

        Raises:
            RuntimeError: Called outside a run.
        """
        try:
            return self._current.get()
        except LookupError as error:
            raise RuntimeError('No simulation run is active.') from error
