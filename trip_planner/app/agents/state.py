"""Graph state shared by every agent built on `base.BaseAgent`."""

import dataclasses
from typing import Annotated

from langchain_core import messages as messages_lib
from langgraph import graph


@dataclasses.dataclass
class AgentState:
    """State of one agent in one run (one checkpointer thread).

    Attributes:
        messages: Conversation of the agent with the LLM and its tools.
        participant_id: The agent's address on the message bus; injected
            into the tools that need it.
    """

    messages: Annotated[
        list[messages_lib.AnyMessage], graph.add_messages
    ] = dataclasses.field(default_factory=list)
    participant_id: str = ''
