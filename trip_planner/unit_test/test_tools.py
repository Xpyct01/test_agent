"""Tests of the tool concerns with real data and a test run context."""

from trip_planner.app.core.schemas import trip
from trip_planner.unit_test import fakes

_CLOSURE = trip.TrailClosure(trail_id='ruta_del_cares', reason='rockfall')


async def test_retries_recover_from_injected_failures(provider, tool_set):
    context = fakes.run_context({'get_weather_forecast': 0.5}, seed=3)
    with provider.activate(context):
        results = [await tool_set.weather.get_weather_forecast()
                   for _ in range(5)]
    events = context.recorder.build(
        'r', 'b', 0, 3, 's', fakes.PLANNING_DATE, 'converged', None
    ).metrics
    assert events.injected_failures > 0
    assert events.retries > 0
    assert any('best_dates' in r for r in results)


async def test_exhausted_retries_return_a_retryable_error(provider, tool_set):
    context = fakes.run_context({'get_trail_status': 1.0})
    with provider.activate(context):
        result = await tool_set.trails.get_trail_status(['bulnes_poncebos'])
    assert result['retryable'] is True
    metrics = context.recorder.build(
        'r', 'b', 0, 0, 's', fakes.PLANNING_DATE, 'failed', None
    ).metrics
    assert metrics.injected_failures == 3
    assert metrics.unrecovered_calls == 1


async def test_trail_status_reports_closures_and_unknown_ids(provider, tool_set):
    context = fakes.run_context(closures=[_CLOSURE])
    with provider.activate(context):
        result = await tool_set.trails.get_trail_status(
            ['ruta_del_cares', 'bulnes_poncebos', 'made_up']
        )
    assert result['trails'][1]['rockfall_risk'] is True
    assert [t['status'] for t in result['trails']] == [
        'closed', 'open', 'unknown_trail_id'
    ]


async def test_booking_is_idempotent_and_validated(provider, tool_set):
    context = fakes.run_context(closures=[_CLOSURE])
    args = dict(start_time='08:00', customer_name='Alex Moreno',
                party_size=1, guide_name='Lucia Prieto')
    with provider.activate(context):
        first = await tool_set.booking.create_booking(
            'bulnes_poncebos', '2026-11-29', **args)
        again = await tool_set.booking.create_booking(
            'bulnes_poncebos', '2026-11-29', **args)
        closed = await tool_set.booking.create_booking(
            'ruta_del_cares', '2026-11-29', **args)
        monday = await tool_set.booking.create_booking(
            'bulnes_poncebos', '2026-11-30', **args)
    assert first['booking']['booking_id'] == again['booking']['booking_id']
    assert again['already_existed'] is True
    assert 'closed' in closed['error']
    assert 'not available' in monday['error']


async def test_guide_availability_follows_weekdays(provider, tool_set):
    context = fakes.run_context()
    with provider.activate(context):
        result = await tool_set.booking.check_guide_availability(
            ['2026-11-29', '2026-11-30']
        )
    assert result['dates'][0]['available_guides'] == ['Lucia Prieto']
    assert result['dates'][1]['available_guides'] == []


async def test_send_message_rejects_unconnected_recipient(provider, tool_set):
    context = fakes.run_context()
    with provider.activate(context):
        result = await tool_set.communication.send_message(
            'human_b', 'hi', participant_id='agent_a'
        )
    assert 'allowed recipients' in result['error']
    assert context.recorder.build(
        'r', 'b', 0, 0, 's', fakes.PLANNING_DATE, 'failed', None
    ).metrics.rejected_messages == 1


async def test_final_plan_must_match_booking_and_rental(provider, tool_set):
    context = fakes.run_context()
    plan_args = dict(
        trail_id='bulnes_poncebos', trail_name='Bulnes',
        date='2026-11-29', start_time='08:00', guide_name='Lucia Prieto',
        weather_summary='Clear.', gear_to_bring=[], gear_to_buy=[], notes=[],
    )
    with provider.activate(context):
        booking = await tool_set.booking.create_booking(
            'bulnes_poncebos', '2026-11-29', '08:00', 'Alex', 1,
            'Lucia Prieto')
        booking_id = booking['booking']['booking_id']
        rejected = await tool_set.communication.deliver_final_plan(
            trip.TripPlan(booking_id=booking_id, gear_to_rent=['helmet'],
                          **plan_args),
            participant_id='agent_a',
        )
        await tool_set.equipment.reserve_rental_gear(booking_id, ['helmet'])
        accepted = await tool_set.communication.deliver_final_plan(
            trip.TripPlan(booking_id=booking_id, gear_to_rent=['helmet'],
                          **plan_args),
            participant_id='agent_a',
        )
    assert 'not reserved' in rejected['error']
    assert accepted['delivered_to'] == 'human_a'
    assert context.final_plan is not None
