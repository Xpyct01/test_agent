"""Test doubles: scripted LLMs, the catalogue and a ready-made run context."""

from collections.abc import Iterable, Sequence
import datetime
import itertools
import json
import pathlib
from typing import Any

from langchain_core import messages as messages_lib
from langchain_core import runnables
from langchain_core.language_models import fake_chat_models

from trip_planner.app.config import simulation as simulation_config_lib
from trip_planner.app.core.repositories.local_store import (
    booking as booking_lib,
)
from trip_planner.app.core.repositories.local_store import (
    rental_stock as rental_stock_lib,
)
from trip_planner.app.core.repositories.local_store import (
    trail_status as trail_status_lib,
)
from trip_planner.app.core.schemas import simulation
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.environment import message_bus as message_bus_lib
from trip_planner.app.ml.environment import run_context as run_context_lib
from trip_planner.app.ml.environment import trajectory as trajectory_lib
from trip_planner.app.ml.fault_injection import core as fault_injection_lib

DATA_DIR = pathlib.Path(__file__).resolve().parents[1] / 'data'
# The catalogue the seed migration writes to PostgreSQL, as test fixtures.
CATALOGUE_DIR = pathlib.Path(__file__).resolve().parent / 'data'
# A Wednesday; with the weather fixture the best date is Sunday 29th.
PLANNING_DATE = datetime.date(2026, 11, 25)
_call_ids = itertools.count()


class ScriptedChatModel(fake_chat_models.GenericFakeChatModel):
    """Returns the scripted messages in order; tool binding is a no-op."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> 'ScriptedChatModel':
        del tools, kwargs  # The script already knows which tools to call.
        return self


def scripted_model(
    responses: Iterable[messages_lib.AIMessage],
) -> ScriptedChatModel:
    """Returns a chat model that answers with `responses` in order."""
    return ScriptedChatModel(messages=iter(list(responses)))


def tool_call(name: str, **args: Any) -> messages_lib.AIMessage:
    """Returns an AI message that calls one tool."""
    return messages_lib.AIMessage(
        '',
        tool_calls=[{'name': name, 'args': args, 'id': f'call_{next(_call_ids)}'}],
        usage_metadata={
            'input_tokens': 100, 'output_tokens': 10, 'total_tokens': 110
        },
    )


def say(text: str) -> messages_lib.AIMessage:
    """Returns an AI message that ends the turn."""
    return messages_lib.AIMessage(text)


class ScriptedHumanModel:
    """Stands in for `with_structured_output(HumanTurn, include_raw=True)`."""

    def __init__(self, turns: Sequence[simulation.HumanTurn]):
        """Initializes the model.

        Args:
            turns: Replies returned in order.
        """
        self._turns = iter(turns)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        del schema, kwargs  # Always returns HumanTurn.
        return runnables.RunnableLambda(self._answer)

    def _answer(self, messages: Any) -> dict[str, Any]:
        del messages  # Scripted.
        return {'parsed': next(self._turns), 'raw': messages_lib.AIMessage('')}


def _load(name: str) -> Any:
    return json.loads((CATALOGUE_DIR / name).read_text(encoding='utf-8'))


class FakeTrailRepository:
    """Serves `trails.json` like the Postgres `TrailRepository`."""

    def __init__(self):
        self._trails = {
            raw['trail_id']: trip.Trail.model_validate(raw)
            for raw in _load('trails.json')
        }

    async def list_all(self) -> list[trip.Trail]:
        return list(self._trails.values())

    async def get(self, trail_id: str) -> trip.Trail | None:
        return self._trails.get(trail_id)


class FakeEquipmentItemRepository:
    """Serves `equipment.json` like the Postgres `EquipmentItemRepository`."""

    def __init__(self):
        self._items = [
            trip.EquipmentItem.model_validate(raw)
            for raw in _load('equipment.json')
        ]

    async def list_all(self) -> list[trip.EquipmentItem]:
        return list(self._items)


class FakeGuideRepository:
    """Serves `guides.json` like the Postgres `GuideRepository`."""

    def __init__(self):
        self._guides = [
            trip.Guide.model_validate(raw) for raw in _load('guides.json')
        ]

    async def list_all(self) -> list[trip.Guide]:
        return list(self._guides)

    async def get(self, name: str) -> trip.Guide | None:
        wanted = name.strip().lower()
        return next(
            (g for g in self._guides if g.name.lower() == wanted), None
        )


class FakeRentalStockRepository:
    """Serves `rental_stock.json` like the Postgres `RentalStockRepository`."""

    async def units_by_item(self) -> dict[str, int]:
        return dict(_load('rental_stock.json'))


def run_context(
    failure_rates: dict[str, float] | None = None,
    closures: Sequence[trip.TrailClosure] = (),
    seed: int = 0,
) -> run_context_lib.RunContext:
    """Returns a run context over the catalogue fixtures."""
    persona = simulation.Persona(
        name='x', description='x', initial_message='hello'
    )
    scenario = simulation.Scenario(
        name='test', start_date=PLANNING_DATE, customer=persona,
        guide=persona, trail_closures=list(closures),
    )
    return run_context_lib.RunContext(
        run_id='run-test',
        batch_id='batch-test',
        run_index=0,
        scenario=scenario,
        planning_date=PLANNING_DATE,
        fault_seed=seed,
        bus=message_bus_lib.MessageBus(),
        recorder=trajectory_lib.TrajectoryRecorder(0.4, 1.6),
        fault_injector=fault_injection_lib.FaultInjector(
            seed, failure_rates or {}
        ),
        trail_status=trail_status_lib.TrailStatusRepository(closures),
        bookings=booking_lib.BookingRepository(),
        rental_stock=rental_stock_lib.RentalStockRepository(
            _load('rental_stock.json')
        ),
    )


def simulation_config(**overrides: Any) -> simulation_config_lib.SimulationConfiguration:
    """Returns simulation settings without back-off delays."""
    values = {'retry_base_delay_s': 0.0, 'failure_rates': {}, **overrides}
    return simulation_config_lib.SimulationConfiguration(**values)
