"""Tests of the message bus and the discrete-time simulation."""

import pytest

from trip_planner.app.core import errors
from trip_planner.app.ml.environment import core as environment_lib
from trip_planner.app.ml.environment import message_bus as message_bus_lib
from trip_planner.unit_test import fakes


def test_bus_enforces_topology():
    bus = message_bus_lib.MessageBus()
    with pytest.raises(errors.InvalidRequestError, match='allowed recipients'):
        bus.send('agent_a', 'human_b', 'hi', 0)
    with pytest.raises(errors.InvalidRequestError):
        bus.send('human_a', 'agent_b', 'hi', 0)
    assert bus.neighbours('agent_a') == ['agent_b', 'human_a']


def test_bus_delivers_in_send_order_grouped_by_recipient():
    bus = message_bus_lib.MessageBus()
    bus.send('human_a', 'agent_a', 'one', 0)
    bus.send('agent_b', 'agent_a', 'two', 0)
    bus.send('agent_a', 'agent_b', 'three', 0)
    inboxes = bus.deliver()
    assert [m.content for m in inboxes['agent_a']] == ['one', 'two']
    assert [m.content for m in inboxes['agent_b']] == ['three']
    assert bus.deliver() == {}


class _Echo:
    """Replies to every message it gets until `limit` replies."""

    def __init__(self, participant_id, peer, provider, limit, fail=False):
        self.participant_id = participant_id
        self._peer = peer
        self._provider = provider
        self._limit = limit
        self._fail = fail
        self.seen_ticks = []

    async def act(self, inbox):
        context = self._provider.current()
        self.seen_ticks.append(context.tick)
        if self._fail:
            raise RuntimeError('boom')
        if self._limit > 0:
            self._limit -= 1
            context.send_message(self.participant_id, self._peer, 'ping')


async def test_simulation_stalls_when_no_message_is_in_flight(provider):
    context = fakes.run_context()
    human = _Echo('human_a', 'agent_a', provider, limit=1)
    agent = _Echo('agent_a', 'human_a', provider, limit=2)
    trajectory = await environment_lib.Simulation(
        [human, agent], ['human_a'], context, provider, max_ticks=10
    ).run()
    assert trajectory.status == 'stalled'
    # Tick 0: human opens; tick 1: agent replies; tick 2: human is silent;
    # tick 3: nothing in flight.
    assert human.seen_ticks == [0, 2]
    assert agent.seen_ticks == [1]
    assert trajectory.metrics.messages == 2


async def test_simulation_times_out(provider):
    context = fakes.run_context()
    human = _Echo('human_a', 'agent_a', provider, limit=100)
    agent = _Echo('agent_a', 'human_a', provider, limit=100)
    trajectory = await environment_lib.Simulation(
        [human, agent], ['human_a'], context, provider, max_ticks=4
    ).run()
    assert trajectory.status == 'timeout'


async def test_simulation_survives_a_crashing_participant(provider):
    context = fakes.run_context()
    human = _Echo('human_a', 'agent_a', provider, limit=1)
    agent = _Echo('agent_a', 'human_a', provider, limit=1, fail=True)
    trajectory = await environment_lib.Simulation(
        [human, agent], ['human_a'], context, provider, max_ticks=5
    ).run()
    assert trajectory.metrics.participant_errors == 1
    assert trajectory.status == 'stalled'
