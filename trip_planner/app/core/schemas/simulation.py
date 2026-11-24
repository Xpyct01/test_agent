"""Schemas of the simulation: scenario, messages, trajectory, metrics."""

import datetime
from typing import Any, Literal

import pydantic

from trip_planner.app.core.schemas import trip

ParticipantId = Literal['human_a', 'agent_a', 'agent_b', 'human_b']
RunStatus = Literal['converged', 'stalled', 'timeout', 'failed']
EventType = Literal[
    'message',
    'message_rejected',
    'llm_call',
    'tool_call',
    'tool_result',
    'tool_failure',
    'retry',
    'participant_error',
    'final_plan',
    'end',
]


class Persona(pydantic.BaseModel):
    """A simulated human and the message that opens their side."""

    name: str
    description: str
    initial_message: str


class Scenario(pydantic.BaseModel):
    """Facts of one test scenario."""

    name: str
    start_date: datetime.date | None = None
    customer: Persona
    guide: Persona
    trail_closures: list[trip.TrailClosure] = []


class Message(pydantic.BaseModel):
    """A message between two connected participants."""

    sender: ParticipantId
    recipient: ParticipantId
    content: str
    sent_tick: int


class HumanTurn(pydantic.BaseModel):
    """What a simulated human answers in one turn."""

    message: str = pydantic.Field(
        description='Your reply to your assistant; empty to stay silent.'
    )
    conversation_complete: bool = pydantic.Field(
        description='True only when you have everything you asked for.'
    )


class TrajectoryEvent(pydantic.BaseModel):
    """One step of a run."""

    tick: int
    type: EventType
    participant: str
    data: dict[str, Any] = {}


class RunMetrics(pydantic.BaseModel):
    """Key performance numbers of one run."""

    ticks: int
    wall_time_s: float
    messages: int
    rejected_messages: int
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    tool_calls: int
    tool_errors_returned: int
    injected_failures: int
    retries: int
    failed_calls: int
    unrecovered_calls: int
    participant_errors: int
    llm_latency_s_by_participant: dict[str, float]


class Trajectory(pydantic.BaseModel):
    """Everything that happened in one run, in order."""

    run_id: str
    batch_id: str
    run_index: int
    fault_seed: int
    scenario: str
    planning_date: datetime.date
    status: RunStatus
    outcome_key: str | None
    final_plan: trip.TripPlan | None
    metrics: RunMetrics
    conversation: list[str]
    events: list[TrajectoryEvent]


class BatchSummary(pydantic.BaseModel):
    """How a batch of runs of one scenario went."""

    batch_id: str
    scenario: str
    runs: int
    statuses: dict[str, int]
    outcome_counts: dict[str, int]
    modal_outcome: str | None
    convergence_rate: float
    success_rate: float
    mean_ticks: float
    mean_wall_time_s: float
    p95_wall_time_s: float
    mean_llm_calls: float
    total_tokens: int
    total_cost_usd: float
    injected_failures: int
    failure_recovery_rate: float
    trajectory_files: list[str]
