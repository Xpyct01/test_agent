"""Records the events of one run and turns them into a trajectory."""

import collections
import datetime
import time
from typing import Any

from trip_planner.app.core.schemas import simulation
from trip_planner.app.core.schemas import trip


class TrajectoryRecorder:
    """Ordered event log of one run, with the metrics derived from it."""

    def __init__(
        self, input_cost_per_million: float, output_cost_per_million: float
    ):
        """Initializes an empty log.

        Args:
            input_cost_per_million: USD per million prompt tokens.
            output_cost_per_million: USD per million completion tokens.
        """
        self._input_cost = input_cost_per_million
        self._output_cost = output_cost_per_million
        self._events: list[simulation.TrajectoryEvent] = []
        self._started = time.perf_counter()

    def record(
        self,
        tick: int,
        event_type: simulation.EventType,
        participant: str,
        **data: Any,
    ) -> None:
        """Appends one event."""
        self._events.append(
            simulation.TrajectoryEvent(
                tick=tick, type=event_type, participant=participant, data=data
            )
        )

    def build(
        self,
        run_id: str,
        batch_id: str,
        run_index: int,
        fault_seed: int,
        scenario: str,
        planning_date: datetime.date,
        status: simulation.RunStatus,
        final_plan: trip.TripPlan | None,
    ) -> simulation.Trajectory:
        """Returns the trajectory of the finished run."""
        return simulation.Trajectory(
            run_id=run_id,
            batch_id=batch_id,
            run_index=run_index,
            fault_seed=fault_seed,
            scenario=scenario,
            planning_date=planning_date,
            status=status,
            outcome_key=final_plan.outcome_key() if final_plan else None,
            final_plan=final_plan,
            metrics=self._metrics(),
            conversation=[
                f'[t{e.tick}] {e.participant} -> {e.data["recipient"]}: '
                f'{e.data["content"]}'
                for e in self._events if e.type == 'message'
            ],
            events=list(self._events),
        )

    def _metrics(self) -> simulation.RunMetrics:
        counts = collections.Counter(e.type for e in self._events)
        llm_calls = [e for e in self._events if e.type == 'llm_call']
        prompt_tokens = sum(e.data.get('prompt_tokens', 0) for e in llm_calls)
        completion_tokens = sum(
            e.data.get('completion_tokens', 0) for e in llm_calls
        )
        latency: dict[str, float] = collections.defaultdict(float)
        for event in llm_calls:
            latency[event.participant] += event.data.get('latency_s', 0.0)
        failures = [e for e in self._events if e.type == 'tool_failure']
        return simulation.RunMetrics(
            ticks=max((e.tick for e in self._events), default=0),
            wall_time_s=round(time.perf_counter() - self._started, 2),
            messages=counts['message'],
            rejected_messages=counts['message_rejected'],
            llm_calls=len(llm_calls),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=round(
                (prompt_tokens * self._input_cost
                 + completion_tokens * self._output_cost) / 1e6,
                5,
            ),
            tool_calls=counts['tool_call'],
            tool_errors_returned=sum(
                1 for e in self._events
                if e.type == 'tool_result' and e.data.get('is_error')
            ),
            injected_failures=len(failures),
            retries=counts['retry'],
            failed_calls=sum(1 for e in failures if e.data['attempt'] == 1),
            unrecovered_calls=sum(1 for e in failures if e.data['final']),
            participant_errors=counts['participant_error'],
            llm_latency_s_by_participant={
                k: round(v, 2) for k, v in sorted(latency.items())
            },
        )
