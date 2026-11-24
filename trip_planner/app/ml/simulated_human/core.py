"""A human of the scenario, played by an LLM persona."""

from collections.abc import Sequence
import logging
import time

from langchain_core import language_models
from langchain_core import messages as messages_lib

from trip_planner.app.agents.callbacks import observability as observability_lib
from trip_planner.app.core.schemas import simulation
from trip_planner.app.ml.environment import run_context as run_context_lib
from trip_planner.app.ml.simulated_human import prompts

logger = logging.getLogger(__name__)


class SimulatedHuman:
    """Opens the scenario with a scripted message, then answers via an LLM.

    The persona is fixed by the scenario and sampled at temperature 0, and
    the reply is structured (`HumanTurn`), so the human answers the same
    way to the same messages and the end of the conversation is explicit.

    Attributes:
        participant_id: The human's address on the message bus.
    """

    def __init__(
        self,
        participant_id: str,
        assistant_id: str,
        persona: simulation.Persona,
        closes_scenario: bool,
        chat_model: language_models.BaseChatModel,
        run_context_provider: run_context_lib.RunContextProvider,
        observability: observability_lib.ObservabilityCallbacks,
    ):
        """Initializes the human; build one per run.

        Args:
            participant_id: The human's address on the message bus.
            assistant_id: The only participant the human talks to.
            persona: Who the human is and how they open the scenario.
            closes_scenario: Whether the human ending the conversation
                after the final plan ends the run (the customer).
            chat_model: The LLM playing the persona.
            run_context_provider: Gives access to the active run.
            observability: Tracing callbacks.
        """
        self.participant_id = participant_id
        self._assistant_id = assistant_id
        self._persona = persona
        self._closes_scenario = closes_scenario
        self._model = chat_model.with_structured_output(
            simulation.HumanTurn, include_raw=True
        )
        self._run_context_provider = run_context_provider
        self._observability = observability
        self._history: list[messages_lib.BaseMessage] = []
        self._opened = False

    async def act(self, inbox: Sequence[simulation.Message]) -> None:
        """Opens the scenario on an empty inbox, else answers the messages."""
        context = self._run_context_provider.current()
        if not inbox:
            if not self._opened:
                self._opened = True
                self._say(context, self._persona.initial_message)
            return

        self._history.append(
            messages_lib.HumanMessage(
                '\n\n'.join(f'{self._assistant_id}: {m.content}' for m in inbox)
            )
        )
        system = messages_lib.SystemMessage(
            prompts.SYSTEM.format(
                description=self._persona.description,
                assistant_id=self._assistant_id,
                planning_date=context.planning_date.isoformat(),
                weekday=context.planning_date.strftime('%A'),
            )
        )
        started = time.perf_counter()
        output = await self._model.ainvoke(
            [system, *self._history],
            config=self._observability.run_config(
                context.run_id, context.batch_id, self.participant_id
            ),
        )
        turn: simulation.HumanTurn | None = output['parsed']
        usage = getattr(output['raw'], 'usage_metadata', None) or {}
        context.record(
            'llm_call',
            self.participant_id,
            latency_s=round(time.perf_counter() - started, 3),
            prompt_tokens=usage.get('input_tokens', 0),
            completion_tokens=usage.get('output_tokens', 0),
            text=turn.message if turn else '',
            conversation_complete=bool(turn and turn.conversation_complete),
        )
        if turn is None:
            logger.warning('%s produced no parsable reply', self.participant_id)
            return
        if turn.message.strip():
            self._say(context, turn.message)
        if (
            turn.conversation_complete
            and self._closes_scenario
            and context.final_plan is not None
        ):
            context.customer_done = True

    def _say(self, context: run_context_lib.RunContext, text: str) -> None:
        self._history.append(messages_lib.AIMessage(text))
        context.send_message(self.participant_id, self._assistant_id, text)
