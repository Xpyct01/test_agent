"""A human of the scenario played by a real person through a UI."""

import asyncio
from collections.abc import Callable, Sequence
import logging

from trip_planner.app.core.schemas import simulation
from trip_planner.app.ml.environment import run_context as run_context_lib

logger = logging.getLogger(__name__)


class HumanChannel:
    """Hands the person's turns to a `LiveHuman`.

    The UI submits turns; the participant takes them one per act. When the
    participant needs a turn and none is queued, `on_waiting` is called so
    the UI knows the simulation is paused on the person.
    """

    def __init__(self, on_waiting: Callable[[], None]):
        """Initializes an empty channel.

        Args:
            on_waiting: Called each time the participant starts waiting.
        """
        self._turns: asyncio.Queue[simulation.HumanTurn] = asyncio.Queue()
        self._on_waiting = on_waiting
        self.waiting = False

    def submit(self, turn: simulation.HumanTurn) -> None:
        """Queues the person's next turn."""
        self.waiting = False
        self._turns.put_nowait(turn)

    async def next_turn(self, timeout_s: float) -> simulation.HumanTurn:
        """Returns the next turn, waiting for the person if needed.

        Raises:
            TimeoutError: No turn arrived within `timeout_s`.
        """
        if self._turns.empty():
            self.waiting = True
            self._on_waiting()
        try:
            return await asyncio.wait_for(self._turns.get(), timeout_s)
        finally:
            self.waiting = False


class LiveHuman:
    """Takes the place of a simulated human; a person types the replies.

    Messages delivered to it are already in the trajectory (the sender
    recorded them), so the UI shows them from there. The simulation is
    paused while the person types: the tick only ends when everyone acted.

    Attributes:
        participant_id: The human's address on the message bus.
    """

    def __init__(
        self,
        participant_id: str,
        assistant_id: str,
        closes_scenario: bool,
        channel: HumanChannel,
        run_context_provider: run_context_lib.RunContextProvider,
        input_timeout_s: float,
    ):
        """Initializes the human; build one per run.

        Args:
            participant_id: The human's address on the message bus.
            assistant_id: The only participant the human talks to.
            closes_scenario: Whether the person ending the conversation
                after the final plan ends the run (the customer).
            channel: Where the person's turns come from.
            run_context_provider: Gives access to the active run.
            input_timeout_s: How long to wait for a turn before staying
                silent, which lets an abandoned run stall and end.
        """
        self.participant_id = participant_id
        self._assistant_id = assistant_id
        self._closes_scenario = closes_scenario
        self._channel = channel
        self._run_context_provider = run_context_provider
        self._input_timeout_s = input_timeout_s
        self._opened = False

    async def act(self, inbox: Sequence[simulation.Message]) -> None:
        """Sends the person's next turn; opens the scenario at tick 0."""
        context = self._run_context_provider.current()
        if not inbox and self._opened:
            return
        self._opened = True
        try:
            turn = await self._channel.next_turn(self._input_timeout_s)
        except TimeoutError:
            logger.info('%s gave no input; staying silent.', self.participant_id)
            return
        if turn.message.strip():
            context.send_message(
                self.participant_id, self._assistant_id, turn.message
            )
        if (
            turn.conversation_complete
            and self._closes_scenario
            and context.final_plan is not None
        ):
            context.customer_done = True
