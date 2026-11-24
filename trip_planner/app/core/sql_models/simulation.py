"""Simulation batches, runs and their trajectory events (evaluation data)."""

import datetime
import enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

from trip_planner.app.core.sql_models import base


class RunStatus(enum.StrEnum):
    """How a simulation run ended."""

    CONVERGED = 'converged'
    STALLED = 'stalled'
    TIMEOUT = 'timeout'
    FAILED = 'failed'


class EventType(enum.StrEnum):
    """Kind of a trajectory event."""

    MESSAGE = 'message'
    MESSAGE_REJECTED = 'message_rejected'
    LLM_CALL = 'llm_call'
    TOOL_CALL = 'tool_call'
    TOOL_RESULT = 'tool_result'
    TOOL_FAILURE = 'tool_failure'
    RETRY = 'retry'
    PARTICIPANT_ERROR = 'participant_error'
    FINAL_PLAN = 'final_plan'
    END = 'end'


class SimulationBatch(base.CreatedAtMixin, table=True):
    """Repeated runs of one scenario, compared for convergence.

    Attributes:
        id: Batch id.
        scenario: Scenario name.
        runs: Runs requested.
        summary: `BatchSummary` of the finished batch; None while running.
    """

    __tablename__ = 'simulation_batches'

    id: str = sqlmodel.Field(primary_key=True, max_length=64)
    scenario: str = sqlmodel.Field(max_length=64, index=True)
    runs: int
    summary: dict[str, Any] | None = sqlmodel.Field(
        default=None, sa_type=postgresql.JSONB
    )


class SimulationRun(base.CreatedAtMixin, table=True):
    """One run of a scenario: its outcome and key metrics.

    Attributes:
        id: Run id.
        batch_id: Batch the run belongs to.
        run_index: Position of the run in its batch, from 0.
        fault_seed: Seed of the injected tool failures.
        scenario: Scenario name.
        planning_date: Day the run planned from.
        status: How the run ended.
        outcome_key: Fields two runs must share to agree; None without a plan.
        final_plan: `TripPlan` handed to the customer; None without a plan.
        metrics: `RunMetrics` of the run.
        conversation: Human-readable message log.
    """

    __tablename__ = 'simulation_runs'
    __table_args__ = (sa.UniqueConstraint('batch_id', 'run_index'),)

    id: str = sqlmodel.Field(primary_key=True, max_length=64)
    batch_id: str = sqlmodel.Field(
        foreign_key='simulation_batches.id', ondelete='CASCADE', max_length=64
    )
    run_index: int
    fault_seed: int
    scenario: str = sqlmodel.Field(max_length=64)
    planning_date: datetime.date
    status: RunStatus = sqlmodel.Field(
        sa_type=base.pg_enum(RunStatus, 'run_status'), index=True
    )
    outcome_key: str | None = sqlmodel.Field(
        default=None, max_length=256, index=True
    )
    final_plan: dict[str, Any] | None = sqlmodel.Field(
        default=None, sa_type=postgresql.JSONB
    )
    metrics: dict[str, Any] = sqlmodel.Field(
        default_factory=dict, sa_type=postgresql.JSONB
    )
    conversation: list[str] = sqlmodel.Field(
        default_factory=list,
        sa_type=postgresql.ARRAY(sa.Text),
        sa_column_kwargs={'server_default': '{}'},
    )


class TrajectoryEvent(sqlmodel.SQLModel, table=True):
    """One step of a run, in order.

    Attributes:
        id: Surrogate key.
        run_id: Run the event belongs to.
        sequence: Position of the event in its run, from 0.
        tick: Simulation tick the event happened in.
        type: Kind of event.
        participant: Participant or component that produced the event.
        data: Event payload (message text, tool arguments, error, ...).
    """

    __tablename__ = 'trajectory_events'
    __table_args__ = (sa.UniqueConstraint('run_id', 'sequence'),)

    id: int | None = sqlmodel.Field(
        default=None, primary_key=True, sa_type=sa.BigInteger
    )
    run_id: str = sqlmodel.Field(
        foreign_key='simulation_runs.id', ondelete='CASCADE', max_length=64
    )
    sequence: int
    tick: int
    type: EventType = sqlmodel.Field(
        sa_type=base.pg_enum(EventType, 'trajectory_event_type'), index=True
    )
    participant: str = sqlmodel.Field(max_length=32)
    data: dict[str, Any] = sqlmodel.Field(
        default_factory=dict, sa_type=postgresql.JSONB
    )
