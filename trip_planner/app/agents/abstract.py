"""Interface of the agents of the trip planner."""

import abc
from collections.abc import Sequence
from typing import Any

from trip_planner.app.core.schemas import simulation


class AbstractAgent(abc.ABC):
    """An LLM agent that takes part in the simulation.

    Attributes:
        agent: The compiled LangGraph graph.
        participant_id: The agent's address on the message bus.
    """

    agent: Any
    participant_id: str

    @abc.abstractmethod
    async def act(self, inbox: Sequence[simulation.Message]) -> None:
        """Runs one turn on the messages delivered this tick."""

    @abc.abstractmethod
    def _build(self) -> Any:
        """Returns the compiled graph."""
