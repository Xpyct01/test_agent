"""Agent B: the company's operations assistant."""

from langchain_core import language_models
from langgraph.checkpoint import base as checkpoint_lib

from trip_planner.app.agents import base
from trip_planner.app.agents.callbacks import observability as observability_lib
from trip_planner.app.agents.operations_assistant import prompts
from trip_planner.app.agents.tools import core as tools_lib
from trip_planner.app.ml.environment import run_context as run_context_lib

PARTICIPANT_ID = 'agent_b'


class OperationsAssistantAgent(base.BaseAgent):
    """Runs the company side: trail status, guides, bookings, rentals."""

    def __init__(
        self,
        chat_model: language_models.BaseChatModel,
        tool_set: tools_lib.ToolSet,
        run_context_provider: run_context_lib.RunContextProvider,
        observability: observability_lib.ObservabilityCallbacks,
        checkpointer: checkpoint_lib.BaseCheckpointSaver,
        recursion_limit: int,
    ):
        """Initializes the agent.

        Args:
            chat_model: The LLM.
            tool_set: Every tool concern of the module.
            run_context_provider: Gives access to the active run.
            observability: Tracing callbacks.
            checkpointer: Keeps the agent's state between turns.
            recursion_limit: Maximum graph steps of one turn.
        """
        self._tools = [
            tool_set.trails.get_trail_status,
            tool_set.booking.check_guide_availability,
            tool_set.booking.create_booking,
            tool_set.equipment.check_rental_stock,
            tool_set.equipment.reserve_rental_gear,
            tool_set.communication.send_message,
        ]
        super().__init__(
            participant_id=PARTICIPANT_ID,
            instruction=prompts.INSTRUCTION,
            chat_model=chat_model,
            run_context_provider=run_context_provider,
            observability=observability,
            checkpointer=checkpointer,
            recursion_limit=recursion_limit,
        )
