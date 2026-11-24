"""Message passing between connected participants, one tick delayed."""

import collections

from trip_planner.app.core import errors
from trip_planner.app.core.schemas import simulation

# Human A <-> Agent A <-> Agent B <-> Human B, and nothing else (fig. 1).
TOPOLOGY: frozenset[frozenset[str]] = frozenset({
    frozenset({'human_a', 'agent_a'}),
    frozenset({'agent_a', 'agent_b'}),
    frozenset({'agent_b', 'human_b'}),
})


class MessageBus:
    """Queues messages sent in tick `t` for delivery at tick `t + 1`."""

    def __init__(self, topology: frozenset[frozenset[str]] = TOPOLOGY):
        """Initializes an empty bus.

        Args:
            topology: Pairs of participants allowed to talk.
        """
        self._topology = topology
        self._queue: collections.deque[simulation.Message] = (
            collections.deque()
        )

    def neighbours(self, participant: str) -> list[str]:
        """Returns who a participant may send messages to, sorted."""
        return sorted(
            other
            for pair in self._topology if participant in pair
            for other in pair if other != participant
        )

    def send(
        self, sender: str, recipient: str, content: str, tick: int
    ) -> simulation.Message:
        """Queues a message.

        Raises:
            errors.InvalidRequestError: The two are not connected, or the
                message is empty.
        """
        if frozenset({sender, recipient}) not in self._topology:
            raise errors.InvalidRequestError(
                f'{sender} cannot message {recipient!r}; allowed recipients: '
                f'{", ".join(self.neighbours(sender))}.'
            )
        if not content.strip():
            raise errors.InvalidRequestError('Message content is empty.')
        message = simulation.Message(
            sender=sender, recipient=recipient, content=content,
            sent_tick=tick,
        )
        self._queue.append(message)
        return message

    def deliver(self) -> dict[str, list[simulation.Message]]:
        """Pops every queued message, grouped by recipient in send order."""
        inboxes: dict[str, list[simulation.Message]] = {}
        while self._queue:
            message = self._queue.popleft()
            inboxes.setdefault(message.recipient, []).append(message)
        return inboxes
