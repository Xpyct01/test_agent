"""Tests of the AG-UI service: watch and play runs with scripted LLMs."""

from ag_ui import core as agui
from fastapi import testclient

from trip_planner.app import service_launcher
from trip_planner.app.inference.routers import state
from trip_planner.app.inference.services import agui as agui_lib
from trip_planner.unit_test import test_end_to_end as e2e


def _input(thread_id, mode, text=None, **props):
    messages = []
    if text is not None:
        messages.append({'id': 'u1', 'role': 'user', 'content': text})
    return agui.RunAgentInput(
        threadId=thread_id, runId=f'{thread_id}-{len(props)}', state={},
        messages=messages, tools=[], context=[],
        forwardedProps={'mode': mode, **props},
    )


async def _collect(service, run_input):
    return [event async for event in service.run(run_input)]


def _types(events):
    return [event.type.value for event in events]


def _status(events):
    status = None
    for event in events:
        if isinstance(event, agui.StateSnapshotEvent):
            status = event.snapshot['status']
        elif isinstance(event, agui.StateDeltaEvent):
            for op in event.delta:
                if op.path == '/status':
                    status = op.value
    return status


def _assert_steps_closed(events):
    """AG-UI clients reject RUN_FINISHED while a step is open."""
    open_steps = 0
    for event in events:
        if isinstance(event, agui.StepStartedEvent):
            assert open_steps == 0
            open_steps += 1
        elif isinstance(event, agui.StepFinishedEvent):
            open_steps -= 1
    assert open_steps == 0


def _service(tmp_path, provider, tool_set, turns):
    simulation_service = e2e.build_service(tmp_path, provider, tool_set, turns)
    return agui_lib.AgUiService(
        simulation_service, simulation_service._simulation_config  # pylint: disable=protected-access
    )


async def test_watch_streams_whole_run(tmp_path, provider, tool_set):
    service = _service(
        tmp_path, provider, tool_set, [e2e.APPROVAL, e2e.THANKS]
    )

    events = await _collect(service, _input('t-watch', 'watch'))

    types = _types(events)
    assert types[0] == 'RUN_STARTED' and types[-1] == 'RUN_FINISHED'
    assert events[-1].result['status'] == 'converged'
    assert _status(events) == 'converged'
    senders = [
        e.name for e in events if isinstance(e, agui.TextMessageStartEvent)
    ]
    assert senders[:2] == ['human_a', 'human_b']
    tools = {
        e.tool_call_name for e in events
        if isinstance(e, agui.ToolCallStartEvent)
    }
    assert 'create_booking' in tools and 'send_message' not in tools
    assert 'STEP_STARTED' in types and 'TOOL_CALL_RESULT' in types
    assert any((tmp_path / 'out' / 'live').iterdir())
    _assert_steps_closed(events)


async def test_play_pauses_for_the_person(tmp_path, provider, tool_set):
    service = _service(tmp_path, provider, tool_set, [e2e.APPROVAL])

    first = await _collect(
        service, _input('t-play', 'play', 'Hi, I want a hike.')
    )

    assert first[-1].type.value == 'RUN_FINISHED'
    assert first[-1].result['status'] == 'awaiting_input'
    senders = [
        e.name for e in first if isinstance(e, agui.TextMessageStartEvent)
    ]
    assert 'human_a' not in senders  # The person's own words are not echoed.
    assert senders[-1] == 'agent_a'
    _assert_steps_closed(first)

    second = await _collect(
        service,
        _input('t-play', 'play', 'Thanks!', conversationComplete=True),
    )

    assert second[-1].result['status'] == 'converged'
    _assert_steps_closed(second)
    assert second[-1].result['outcomeKey'].startswith(e2e._TRAIL)  # pylint: disable=protected-access


async def test_play_needs_a_message(tmp_path, provider, tool_set):
    service = _service(tmp_path, provider, tool_set, [])

    events = await _collect(service, _input('t-empty', 'play'))

    assert _types(events) == ['RUN_STARTED', 'RUN_ERROR']


def test_agui_route_streams_sse():
    class _FakeAgUiService:

        async def run(self, run_input):
            yield agui.RunStartedEvent(
                threadId=run_input.thread_id, runId=run_input.run_id
            )
            yield agui.RunFinishedEvent(
                threadId=run_input.thread_id, runId=run_input.run_id
            )

    app = service_launcher.app
    app.dependency_overrides[state.agui_service] = _FakeAgUiService
    try:
        with testclient.TestClient(app) as client:
            response = client.post(
                '/agui',
                json=_input('t', 'watch').model_dump(by_alias=True),
                headers={'accept': 'text/event-stream'},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert 'data: {"type":"RUN_STARTED"' in response.text
    assert 'RUN_FINISHED' in response.text
