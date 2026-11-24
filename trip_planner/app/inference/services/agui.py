"""Streams live simulation runs to a UI over the AG-UI protocol."""

import asyncio
from collections.abc import AsyncIterator
import copy
import dataclasses
import json
import logging
from typing import Any, Literal
import uuid

from ag_ui import core as agui

from trip_planner.app.config import simulation as simulation_config_lib
from trip_planner.app.core import errors
from trip_planner.app.core.schemas import simulation
from trip_planner.app.inference.services import simulation as simulation_lib
from trip_planner.app.ml.live_human import core as live_human_lib

logger = logging.getLogger(__name__)

Mode = Literal['watch', 'play']

# Messages are their own AG-UI text messages; their tool call would repeat
# the content.
_HIDDEN_TOOLS = frozenset({'send_message'})
_INCIDENT_TYPES = frozenset(
    {'tool_failure', 'retry', 'message_rejected', 'participant_error'}
)


@dataclasses.dataclass(frozen=True)
class _Waiting:
    """The live human waits for the person's next message."""


@dataclasses.dataclass(frozen=True)
class _Finished:
    trajectory: simulation.Trajectory


@dataclasses.dataclass(frozen=True)
class _Failed:
    error: str


_Item = simulation.TrajectoryEvent | _Waiting | _Finished | _Failed


class _LiveRun:
    """One simulation running in the background, observed through a queue.

    The run outlives a single AG-UI request in play mode: each request
    hands in one message from the person and streams until the simulation
    waits for the next one or ends.
    """

    def __init__(self, mode: Mode, scenario: str):
        self.mode = mode
        self.items: asyncio.Queue[_Item] = asyncio.Queue()
        self.channel = live_human_lib.HumanChannel(
            lambda: self.items.put_nowait(_Waiting())
        )
        self.stream_lock = asyncio.Lock()
        self.task: asyncio.Task[None] | None = None
        self.step_open = False
        self.state: dict[str, Any] = {
            'mode': mode,
            'scenario': scenario,
            'runId': None,
            'status': 'running',
            'tick': 0,
            'planningDate': None,
            'finalPlan': None,
            'outcomeKey': None,
            'metrics': {
                'llmCalls': 0,
                'promptTokens': 0,
                'completionTokens': 0,
                'toolCalls': 0,
                'injectedFailures': 0,
                'retries': 0,
            },
            'incidents': [],
        }

    @property
    def done(self) -> bool:
        return self.task is not None and self.task.done()


class AgUiService:
    """Runs scenarios for the AG-UI endpoint and translates their events.

    Two modes, picked with `forwardedProps.mode`:
    - `watch`: one AG-UI run plays a whole simulated run (both humans are
      LLM personas). The simulation is cancelled if the client goes away.
    - `play`: the person is Human A. Each AG-UI run sends the last user
      message of the request into the simulation and streams until Agent
      A's reply reaches the person (status `awaiting_input`) or the run
      ends. The simulation is kept per `threadId` between requests. Send
      `forwardedProps.conversationComplete = true` with the message that
      accepts the final plan to end the run as converged.

    Mapping: ticks are steps; messages between participants are text
    messages (`name` = sender, `metadata.recipient`); agent tool calls are
    tool call events (`metadata.participant`); tick, status, live metrics,
    the final plan and incidents (injected failures, retries, rejected
    messages, crashes) are shared state, sent as JSON Patch deltas.
    """

    def __init__(
        self,
        simulation_service: simulation_lib.SimulationService,
        simulation_config: simulation_config_lib.SimulationConfiguration,
    ):
        """Initializes the service.

        Args:
            simulation_service: Builds the runs.
            simulation_config: Live run limits are read.
        """
        self._simulation = simulation_service
        self._config = simulation_config
        self._runs: dict[str, _LiveRun] = {}

    async def run(
        self, run_input: agui.RunAgentInput
    ) -> AsyncIterator[agui.BaseEvent]:
        """Streams the AG-UI events of one request.

        Errors are reported as a `RUN_ERROR` event, as the protocol asks,
        since the HTTP response has already started.
        """
        thread_id, run_id = run_input.thread_id, run_input.run_id
        yield agui.RunStartedEvent(threadId=thread_id, runId=run_id)
        try:
            live = self._live_run_for(run_input)
        except (ValueError, errors.InvalidRequestError) as error:
            yield agui.RunErrorEvent(message=str(error), code='bad_request')
            return
        if live.stream_lock.locked():
            yield agui.RunErrorEvent(
                message='This thread is already streaming.', code='busy'
            )
            return
        async with live.stream_lock:
            yield agui.StateSnapshotEvent(snapshot=copy.deepcopy(live.state))
            finished = False
            try:
                async for event in self._drain(live):
                    yield event
                    if isinstance(event, agui.RunErrorEvent):
                        return
                finished = live.state['status'] != 'awaiting_input'
                yield agui.RunFinishedEvent(
                    threadId=thread_id,
                    runId=run_id,
                    result={
                        'status': live.state['status'],
                        'outcomeKey': live.state['outcomeKey'],
                    },
                )
            finally:
                if live.mode == 'watch' and not finished and live.task:
                    # The client went away: do not spend tokens for nobody.
                    live.task.cancel()

    def _live_run_for(self, run_input: agui.RunAgentInput) -> _LiveRun:
        props = run_input.forwarded_props or {}
        mode = props.get('mode', 'watch')
        if mode not in ('watch', 'play'):
            raise ValueError(f'Unknown mode: {mode!r}.')
        thread_id = run_input.thread_id
        live = self._runs.get(thread_id)
        if live is not None and live.done:
            live = None
        if live is not None and live.mode != mode:
            raise ValueError(f'Thread {thread_id} is a {live.mode} run.')
        if live is not None and mode == 'watch':
            raise ValueError('This thread is already running a simulation.')

        turn = None
        if mode == 'play':
            text = _last_user_text(run_input)
            if not text:
                raise ValueError('Play mode needs a user message.')
            turn = simulation.HumanTurn(
                message=text,
                conversation_complete=bool(props.get('conversationComplete')),
            )
        if live is None:
            live = self._start(thread_id, mode, props.get('scenario'))
        if turn is not None:
            live.state['status'] = 'running'
            live.channel.submit(turn)
        return live

    def _start(
        self, thread_id: str, mode: Mode, scenario_name: str | None
    ) -> _LiveRun:
        active = sum(1 for live in self._runs.values() if not live.done)
        if active >= self._config.max_live_runs:
            raise ValueError('Too many live runs; try again later.')
        scenario = self._simulation.load_scenario(scenario_name)
        live = _LiveRun(mode, scenario.name)
        customer = None
        if mode == 'play':
            customer = live_human_lib.LiveHuman(
                participant_id=simulation_lib.CUSTOMER_ID,
                assistant_id='agent_a',
                closes_scenario=True,
                channel=live.channel,
                run_context_provider=self._simulation.run_context_provider,
                input_timeout_s=self._config.live_input_timeout_s,
            )
        run = self._simulation.build_run(
            self._simulation.new_batch_id(mode), 0, scenario, customer
        )
        context = run.run_context
        live.state['runId'] = context.run_id
        live.state['planningDate'] = context.planning_date.isoformat()
        context.recorder.subscribe(live.items.put_nowait)

        async def play() -> None:
            try:
                trajectory = await run.run()
                await self._simulation.save_live_trajectory(trajectory)
                live.items.put_nowait(_Finished(trajectory))
            except asyncio.CancelledError:
                raise
            except Exception as error:  # pylint: disable=broad-except
                logger.exception('Live run %s failed', context.run_id)
                live.items.put_nowait(_Failed(f'{type(error).__name__}'))
            finally:
                if self._runs.get(thread_id) is live:
                    del self._runs[thread_id]

        live.task = asyncio.create_task(play())
        self._runs[thread_id] = live
        logger.info('Live %s run %s on thread %s', mode, context.run_id, thread_id)
        return live

    async def _drain(self, live: _LiveRun) -> AsyncIterator[agui.BaseEvent]:
        """Translates queued items until the run waits or ends."""
        while True:
            if live.channel.waiting and live.items.empty():
                # The waiting marker was consumed by an earlier request.
                item: _Item = _Waiting()
            else:
                item = await live.items.get()
            if isinstance(item, _Waiting):
                if live.state['status'] == 'running' and live.channel.waiting:
                    # A run may not finish with a step open; the next
                    # request reopens the tick.
                    for event in _close_step(live):
                        yield event
                    yield _replace(live, '/status', 'awaiting_input')
                    return
                continue
            if isinstance(item, _Failed):
                live.state['status'] = 'failed'
                yield agui.RunErrorEvent(
                    message=f'The simulation failed: {item.error}.',
                    code='simulation_failed',
                )
                return
            if isinstance(item, _Finished):
                for event in _close_step(live):
                    yield event
                yield _finish(live, item.trajectory)
                return
            for event in _translate(live, item):
                yield event


def _last_user_text(run_input: agui.RunAgentInput) -> str:
    for message in reversed(run_input.messages):
        if message.role == 'user':
            content = message.content
            if isinstance(content, str):
                return content.strip()
            return ' '.join(
                getattr(part, 'text', '') for part in content
            ).strip()
    return ''


def _replace(live: _LiveRun, path: str, value: Any) -> agui.StateDeltaEvent:
    value = copy.deepcopy(value)
    _set(live.state, path, value)
    return agui.StateDeltaEvent(
        delta=[{'op': 'replace', 'path': path, 'value': value}]
    )


def _set(state: dict[str, Any], path: str, value: Any) -> None:
    *parents, leaf = path.strip('/').split('/')
    target = state
    for key in parents:
        target = target[key]
    target[leaf] = value


def _close_step(live: _LiveRun) -> list[agui.BaseEvent]:
    if not live.step_open:
        return []
    live.step_open = False
    return [agui.StepFinishedEvent(stepName=f'tick {live.state["tick"]}')]


def _translate(
    live: _LiveRun, event: simulation.TrajectoryEvent
) -> list[agui.BaseEvent]:
    if (
        event.type == 'message'
        and live.mode == 'play'
        and event.participant == simulation_lib.CUSTOMER_ID
    ):
        # The person's own message is already in the client.
        return []
    events: list[agui.BaseEvent] = []
    if event.tick != live.state['tick'] or not live.step_open:
        events += _close_step(live)
        if event.tick != live.state['tick']:
            events.append(_replace(live, '/tick', event.tick))
        events.append(agui.StepStartedEvent(stepName=f'tick {event.tick}'))
        live.step_open = True

    data = event.data
    metrics = live.state['metrics']
    if event.type == 'message':
        message_id = str(uuid.uuid4())
        meta = {'recipient': data['recipient'], 'tick': event.tick}
        events += [
            agui.TextMessageStartEvent(
                messageId=message_id, role='assistant',
                name=event.participant, metadata=meta,
            ),
            agui.TextMessageContentEvent(
                messageId=message_id, delta=data['content']
            ),
            agui.TextMessageEndEvent(messageId=message_id),
        ]
    elif event.type == 'llm_call':
        metrics['llmCalls'] += 1
        metrics['promptTokens'] += data.get('prompt_tokens', 0)
        metrics['completionTokens'] += data.get('completion_tokens', 0)
        events.append(_replace(live, '/metrics', metrics))
    elif event.type == 'tool_call':
        metrics['toolCalls'] += 1
        events.append(_replace(live, '/metrics', metrics))
        if data['tool'] not in _HIDDEN_TOOLS:
            meta = {'participant': event.participant, 'tick': event.tick}
            events += [
                agui.ToolCallStartEvent(
                    toolCallId=data['call_id'], toolCallName=data['tool'],
                    metadata=meta,
                ),
                agui.ToolCallArgsEvent(
                    toolCallId=data['call_id'], delta=json.dumps(data['args'])
                ),
                agui.ToolCallEndEvent(toolCallId=data['call_id']),
            ]
    elif event.type == 'tool_result':
        if data['tool'] not in _HIDDEN_TOOLS:
            result = data['result']
            events.append(
                agui.ToolCallResultEvent(
                    messageId=str(uuid.uuid4()),
                    toolCallId=data['call_id'],
                    content=(
                        result if isinstance(result, str)
                        else json.dumps(result)
                    ),
                    role='tool',
                    metadata={'isError': bool(data.get('is_error'))},
                )
            )
    elif event.type == 'final_plan':
        events.append(_replace(live, '/finalPlan', data['plan']))
    elif event.type in _INCIDENT_TYPES:
        if event.type == 'tool_failure':
            metrics['injectedFailures'] += 1
        elif event.type == 'retry':
            metrics['retries'] += 1
        incident = {
            'tick': event.tick, 'type': event.type,
            'participant': event.participant, **data,
        }
        live.state['incidents'].append(incident)
        events += [
            agui.StateDeltaEvent(
                delta=[{'op': 'add', 'path': '/incidents/-', 'value': incident}]
            ),
            _replace(live, '/metrics', metrics),
        ]
    return events


def _finish(
    live: _LiveRun, trajectory: simulation.Trajectory
) -> agui.StateSnapshotEvent:
    state = live.state
    state['status'] = trajectory.status
    state['outcomeKey'] = trajectory.outcome_key
    if trajectory.final_plan is not None:
        state['finalPlan'] = trajectory.final_plan.model_dump(mode='json')
    state['summary'] = trajectory.metrics.model_dump(mode='json')
    return agui.StateSnapshotEvent(snapshot=copy.deepcopy(state))
