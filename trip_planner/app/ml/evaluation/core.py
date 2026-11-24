"""Summarises a batch of runs into convergence and performance numbers."""

import collections
from collections.abc import Sequence
import statistics

from trip_planner.app.core.schemas import simulation


class BatchEvaluator:
    """Computes how often runs agree and how well they performed."""

    def summarize(
        self,
        batch_id: str,
        scenario: str,
        trajectories: Sequence[simulation.Trajectory],
        trajectory_files: Sequence[str],
    ) -> simulation.BatchSummary:
        """Returns the summary of one batch.

        Convergence rate is the share of runs whose outcome key (trail,
        date, rented gear) equals the most common one; success rate is the
        share of runs that ended with status `converged`.
        """
        runs = len(trajectories)
        outcomes = collections.Counter(
            t.outcome_key for t in trajectories if t.outcome_key
        )
        modal, modal_count = (outcomes.most_common(1) or [(None, 0)])[0]
        metrics = [t.metrics for t in trajectories]
        wall_times = sorted(m.wall_time_s for m in metrics)
        failed_calls = sum(m.failed_calls for m in metrics)
        unrecovered = sum(m.unrecovered_calls for m in metrics)
        return simulation.BatchSummary(
            batch_id=batch_id,
            scenario=scenario,
            runs=runs,
            statuses=dict(collections.Counter(t.status for t in trajectories)),
            outcome_counts=dict(outcomes),
            modal_outcome=modal,
            convergence_rate=_ratio(modal_count, runs),
            success_rate=_ratio(
                sum(t.status == 'converged' for t in trajectories), runs
            ),
            mean_ticks=_mean([m.ticks for m in metrics]),
            mean_wall_time_s=_mean(wall_times),
            p95_wall_time_s=_percentile(wall_times, 0.95),
            mean_llm_calls=_mean([m.llm_calls for m in metrics]),
            total_tokens=sum(
                m.prompt_tokens + m.completion_tokens for m in metrics
            ),
            total_cost_usd=round(sum(m.estimated_cost_usd for m in metrics), 4),
            injected_failures=sum(m.injected_failures for m in metrics),
            failure_recovery_rate=(
                1.0 if failed_calls == 0
                else round(1 - unrecovered / failed_calls, 3)
            ),
            trajectory_files=list(trajectory_files),
        )


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


def _mean(values: Sequence[float]) -> float:
    return round(statistics.fmean(values), 2) if values else 0.0


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, round(q * (len(sorted_values) - 1)))
    return sorted_values[index]
