"""Full run of the scenario with scripted LLMs: graph, tools, bus, service."""

import datetime

from langgraph.checkpoint import memory

from trip_planner.app.agents.callbacks import observability as observability_lib
from trip_planner.app.agents.customer_assistant import core as customer_lib
from trip_planner.app.agents.operations_assistant import core as operations_lib
from trip_planner.app.config import agents as agents_config_lib
from trip_planner.app.config import observability as observability_config_lib
from trip_planner.app.core.repositories.local_store import (
    booking as booking_lib,
)
from trip_planner.app.core.repositories.local_store import (
    scenario as scenario_lib,
)
from trip_planner.app.core.schemas import api
from trip_planner.app.core.schemas import simulation
from trip_planner.app.inference.services import simulation as simulation_lib
from trip_planner.app.ml.evaluation import core as evaluation_lib
from trip_planner.unit_test import fakes
from trip_planner.unit_test.fakes import say, tool_call

_TRAIL = 'bulnes_poncebos'
_DATE = '2026-11-29'
_GEAR = ['map_or_gps', 'trekking_poles', 'helmet']


def _booking_id() -> str:
    booking, _ = booking_lib.BookingRepository().create(
        _TRAIL, datetime.date.fromisoformat(_DATE), '08:00',
        'Alex Moreno', 1, 'Lucia Prieto',
    )
    return booking.booking_id


def _customer_script():
    return [
        # Tick 1: plan and ask agent_b.
        tool_call('assess_fitness', age=45, fitness_level='moderate',
                  conditions=['mild left-knee injury']),
        tool_call('search_trails', max_distance_km=14.0,
                  max_elevation_gain_m=490, max_difficulty='moderate',
                  interests=['lakes', 'gorge']),
        tool_call('get_weather_forecast'),
        tool_call('send_message', recipient='agent_b',
                  content='Book Alex Moreno: trails ruta_del_cares, '
                  'bulnes_poncebos, lagos_covadonga; dates 2026-11-29, '
                  '2026-11-28, 2026-11-27; start 08:00.'),
        say('Waiting for agent_b.'),
        # Tick 5: booking confirmed; ask for rentals.
        tool_call('check_equipment', trail_id=_TRAIL, date=_DATE,
                  owned_items=['hiking boots', 'rain jacket', 'backpack'],
                  has_joint_issues=True),
        tool_call('send_message', recipient='agent_b',
                  content=f'Please reserve {_GEAR} for {_booking_id()}.'),
        say('Waiting for rentals.'),
        # Tick 7: deliver the plan.
        tool_call('deliver_final_plan', plan={
            'booking_id': _booking_id(), 'trail_id': _TRAIL,
            'trail_name': 'Bulnes village from Poncebos', 'date': _DATE,
            'start_time': '08:00', 'guide_name': 'Lucia Prieto',
            'weather_summary': 'Clear sky, 9-18 C.',
            'gear_to_bring': ['hiking_boots', 'backpack'],
            'gear_to_rent': _GEAR,
            'gear_to_buy': ['water_2l', 'sun_protection', 'first_aid_kit'],
            'notes': ['Helmet required.'],
        }),
        say('Plan delivered.'),
    ]


def _operations_script():
    return [
        # Tick 1: guide's notice, no reply.
        say('Noted.'),
        # Tick 2: check and ask the guide.
        tool_call('get_trail_status',
                  trail_ids=['ruta_del_cares', _TRAIL, 'lagos_covadonga']),
        tool_call('check_guide_availability',
                  dates=['2026-11-29', '2026-11-28', '2026-11-27']),
        tool_call('send_message', recipient='human_b',
                  content=f'Approve {_TRAIL} on {_DATE} at 08:00?'),
        # A wrong recipient: rejected by the bus, the agent corrects itself.
        tool_call('send_message', recipient='human_a', content='Hi!'),
        say('Waiting for the guide.'),
        # Tick 4: approved; book and confirm.
        tool_call('create_booking', trail_id=_TRAIL, date=_DATE,
                  start_time='08:00', customer_name='Alex Moreno',
                  party_size=1, guide_name='Lucia Prieto'),
        tool_call('send_message', recipient='agent_a',
                  content=f'Booked {_booking_id()}. Helmet required.'),
        say('Done.'),
        # Tick 6: rentals.
        tool_call('check_rental_stock', item_ids=_GEAR),
        tool_call('reserve_rental_gear', booking_id=_booking_id(),
                  item_ids=_GEAR),
        tool_call('send_message', recipient='agent_a',
                  content=f'Reserved {_GEAR}.'),
        say('Done.'),
    ]


def build_service(tmp_path, provider, tool_set, human_turns, failure_rates=None):
    """Returns a simulation service over the scripted agents and humans."""
    observability = observability_lib.ObservabilityCallbacks(
        observability_config_lib.ObservabilityConfiguration(enabled=False)
    )
    common = dict(tool_set=tool_set, run_context_provider=provider,
                  observability=observability, recursion_limit=40)
    agents = [
        customer_lib.CustomerAssistantAgent(
            chat_model=fakes.scripted_model(_customer_script()),
            checkpointer=memory.InMemorySaver(), **common),
        operations_lib.OperationsAssistantAgent(
            chat_model=fakes.scripted_model(_operations_script()),
            checkpointer=memory.InMemorySaver(), **common),
    ]
    scenario_path = tmp_path / 'pinned.yaml'
    scenario_path.write_text(
        (fakes.DATA_DIR / 'scenarios' / 'default.yaml').read_text(
            encoding='utf-8').replace(
                'start_date: null', f'start_date: {fakes.PLANNING_DATE}'),
        encoding='utf-8',
    )
    return simulation_lib.SimulationService(
        agents=agents,
        human_chat_model=fakes.ScriptedHumanModel(human_turns),
        run_context_provider=provider,
        observability=observability,
        scenario_repository=scenario_lib.ScenarioRepository(scenario_path),
        evaluator=evaluation_lib.BatchEvaluator(),
        simulation_config=fakes.simulation_config(
            output_dir=tmp_path / 'out',
            failure_rates=failure_rates or {},
            max_tool_attempts=10,
        ),
        agents_config=agents_config_lib.AgentsConfiguration(),
    )


APPROVAL = simulation.HumanTurn(
    message='Approved. Helmet required, meet 08:00.',
    conversation_complete=False,
)
THANKS = simulation.HumanTurn(message='Thanks!', conversation_complete=True)


async def test_scenario_converges(tmp_path, provider, tool_set):
    service = build_service(
        tmp_path, provider, tool_set, [APPROVAL, THANKS],
        failure_rates={'get_trail_status': 0.9},
    )

    response = await service.run_batch(api.SimulationRequest(runs=1))

    trajectory = response.trajectories[0]
    assert trajectory.status == 'converged'
    assert trajectory.outcome_key == (
        f'{_TRAIL}|{_DATE}|helmet,map_or_gps,trekking_poles'
    )
    assert trajectory.metrics.ticks == 8
    assert trajectory.metrics.rejected_messages == 1
    assert trajectory.metrics.injected_failures >= 1
    senders = [e.participant for e in trajectory.events if e.type == 'message']
    assert senders[:2] == ['human_a', 'human_b']
    assert senders[-1] == 'human_a'
    assert response.summary.convergence_rate == 1.0
    assert (tmp_path / 'out' / response.summary.batch_id / 'run_0.json').exists()

    stored = await service.get_batch(response.summary.batch_id)
    assert stored.trajectories[0].outcome_key == trajectory.outcome_key
