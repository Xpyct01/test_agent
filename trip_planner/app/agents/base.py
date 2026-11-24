"""The one generic agent architecture, set up by tools and instructions."""

from collections.abc import Callable, Sequence
import json
import logging
import time
from typing import Any

from langchain_core import language_models
from langchain_core import messages as messages_lib
from langchain_core import tools as tools_lib
from langgraph import graph
from langgraph import prebuilt
from langgraph.checkpoint import base as checkpoint_lib

from trip_planner.app.agents import abstract
from trip_planner.app.agents import state as state_lib
from trip_planner.app.agents.callbacks import observability as observability_lib
from trip_planner.app.core.schemas import simulation
from trip_planner.app.ml.environment import run_context as run_context_lib

logger = logging.getLogger(__name__)

_MODEL_NODE = 'model'
_TOOLS_NODE = 'tools'
_OBSERVE_NODE = 'observe'
_MAX_RECORDED_CHARS = 4000


class BaseAgent(abstract.AbstractAgent):
    """A ReAct-style LangGraph agent: think, act with tools, repeat.

    One turn handles the messages of one tick: the model reads them, calls
    tools until it has nothing left to do (messages to other participants
    are tools too) and ends the turn. Each agent has its own checkpointer
    thread per run, so the agents' states stay independent; the system
    prompt is rebuilt every call and never stored.

    Subclasses only choose `self._tools` and the instruction.
    """

    def __init__(
        self,
        participant_id: str,
        instruction: str,
        chat_model: language_models.BaseChatModel,
        run_context_provider: run_context_lib.RunContextProvider,
        observability: observability_lib.ObservabilityCallbacks,
        checkpointer: checkpoint_lib.BaseCheckpointSaver,
        recursion_limit: int,
    ):
        """Initializes the agent and builds its graph.

        Args:
            participant_id: The agent's address on the message bus.
            instruction: System prompt template with the `participant_id`,
                `neighbours`, `planning_date` and `weekday` fields.
            chat_model: The LLM.
            run_context_provider: Gives access to the active run.
            observability: Tracing callbacks.
            checkpointer: Keeps the agent's state between turns.
            recursion_limit: Maximum graph steps of one turn.
        """
        self.participant_id = participant_id
        self._instruction = instruction
        self._run_context_provider = run_context_provider
        self._observability = observability
        self._checkpointer = checkpointer
        self._recursion_limit = recursion_limit
        self._model = chat_model.bind_tools(
            self._framework_tools(), parallel_tool_calls=False
        )
        self.agent = self._build()

    async def act(self, inbox: Sequence[simulation.Message]) -> None:
        context = self._run_context_provider.current()
        config = {
            'configurable': {
                'thread_id': f'{context.run_id}:{self.participant_id}'
            },
            'recursion_limit': self._recursion_limit,
            **self._observability.run_config(
                context.run_id, context.batch_id, self.participant_id
            ),
        }
        await self.agent.ainvoke(
            {
                'messages': [messages_lib.HumanMessage(_format_inbox(inbox))],
                'participant_id': self.participant_id,
            },
            config,
        )

    def _build(self) -> Any:
        builder = graph.StateGraph(state_lib.AgentState)
        builder.add_node(_MODEL_NODE, self._call_model)
        builder.add_node(_TOOLS_NODE, prebuilt.ToolNode(self._framework_tools()))
        builder.add_node(_OBSERVE_NODE, self._record_tool_results)
        builder.add_edge(graph.START, _MODEL_NODE)
        builder.add_conditional_edges(
            _MODEL_NODE, self._route, [_TOOLS_NODE, graph.END]
        )
        builder.add_edge(_TOOLS_NODE, _OBSERVE_NODE)
        builder.add_edge(_OBSERVE_NODE, _MODEL_NODE)
        return builder.compile(checkpointer=self._checkpointer)

    def _framework_tools(self) -> list[tools_lib.BaseTool]:
        tools: list[Callable[..., Any]] = self._tools
        return [
            tools_lib.StructuredTool.from_function(
                coroutine=tool, parse_docstring=True
            )
            for tool in tools
        ]

    async def _call_model(
        self, state: state_lib.AgentState
    ) -> dict[str, list[messages_lib.BaseMessage]]:
        context = self._run_context_provider.current()
        system = messages_lib.SystemMessage(
            self._instruction.format(
                participant_id=self.participant_id,
                neighbours=', '.join(context.bus.neighbours(self.participant_id)),
                planning_date=context.planning_date.isoformat(),
                weekday=context.planning_date.strftime('%A'),
            )
        )
        started = time.perf_counter()
        response = await self._model.ainvoke([system, *state.messages])
        usage = response.usage_metadata or {}
        context.record(
            'llm_call',
            self.participant_id,
            latency_s=round(time.perf_counter() - started, 3),
            prompt_tokens=usage.get('input_tokens', 0),
            completion_tokens=usage.get('output_tokens', 0),
            text=_truncate(str(response.text)),
            tool_calls=[call['name'] for call in response.tool_calls],
        )
        for call in response.tool_calls:
            context.record(
                'tool_call', self.participant_id, tool=call['name'],
                args=call['args'], call_id=call['id'],
            )
        return {'messages': [response]}

    async def _record_tool_results(
        self, state: state_lib.AgentState
    ) -> dict[str, Any]:
        context = self._run_context_provider.current()
        results = []
        for message in reversed(state.messages):
            if not isinstance(message, messages_lib.ToolMessage):
                break
            results.append(message)
        for message in reversed(results):
            payload = _parse(str(message.text))
            is_error = message.status == 'error' or (
                isinstance(payload, dict) and 'error' in payload
            )
            context.record(
                'tool_result', self.participant_id, tool=message.name,
                call_id=message.tool_call_id, is_error=is_error,
                result=payload,
            )
        return {}

    def _route(self, state: state_lib.AgentState) -> str:
        last = state.messages[-1]
        if isinstance(last, messages_lib.AIMessage) and last.tool_calls:
            return _TOOLS_NODE
        return graph.END


def _format_inbox(inbox: Sequence[simulation.Message]) -> str:
    parts = [
        f'--- message from {m.sender} (sent at tick {m.sent_tick}) ---\n'
        f'{m.content}'
        for m in inbox
    ]
    return '\n\n'.join(parts) or '(no new messages)'


def _parse(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return _truncate(text)


def _truncate(text: str) -> str:
    if len(text) <= _MAX_RECORDED_CHARS:
        return text
    return text[:_MAX_RECORDED_CHARS] + '...'
