"""What the simulation needs from anyone who takes part in it."""

from collections.abc import Sequence
from typing import Protocol

from trip_planner.app.core.schemas import simulation


class Participant(Protocol):
    """A human or an agent that acts on the messages delivered to it.

    Attributes:
        participant_id: Address of the participant on the message bus.
    """

    participant_id: str

    async def act(self, inbox: Sequence[simulation.Message]) -> None:
        """Handles the messages of one tick; replies go over the bus.

        An empty inbox at tick 0 asks an initiator to open the scenario.
        """
