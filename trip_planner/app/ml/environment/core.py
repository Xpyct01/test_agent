"""Discrete-time simulation of one run of a scenario."""

import asyncio
from collections.abc import Sequence
import logging

from trip_planner.app.core.schemas import simulation
from trip_planner.app.ml.environment import participant as participant_lib
from trip_planner.app.ml.environment import run_context as run_context_lib

logger = logging.getLogger(__name__)

_ENVIRONMENT = 'environment'


class Simulation:
    """Runs participants tick by tick until the scenario resolves.

    At tick 0 the initiators act on an empty inbox (the triggering input).
    At every later tick the bus delivers what was sent in the previous
    tick, and every participant with mail acts concurrently. The run ends
    when the customer closes the conversation after receiving the plan
    (`converged`), when no message is in flight (`stalled`) or after
    `max_ticks` (`timeout`).
    """

    def __init__(
        self,
        participants: Sequence[participant_lib.Participant],
        initiators: Sequence[str],
        run_context: run_context_lib.RunContext,
        run_context_provider: run_context_lib.RunContextProvider,
        max_ticks: int,
    ):
        """Initializes the simulation.

        Args:
            participants: Everyone taking part, by distinct id.
            initiators: Ids of the participants that act at tick 0.
            run_context: State of this run.
            run_context_provider: Makes the run visible to tools.
            max_ticks: Ticks after which the run times out.
        """
        self._participants = {p.participant_id: p for p in participants}
        self._initiators = list(initiators)
        self._context = run_context
        self._provider = run_context_provider
        self._max_ticks = max_ticks

    async def run(self) -> simulation.Trajectory:
        """Plays the run and returns its trajectory."""
        context = self._context
        with self._provider.activate(context):
            status = await self._loop()
            context.record('end', _ENVIRONMENT, status=status)
        logger.info('Run %s finished: %s', context.run_id, status)
        return context.recorder.build(
            run_id=context.run_id,
            batch_id=context.batch_id,
            run_index=context.run_index,
            fault_seed=context.fault_seed,
            scenario=context.scenario.name,
            planning_date=context.planning_date,
            status=status,
            final_plan=context.final_plan,
        )

    async def _loop(self) -> simulation.RunStatus:
        context = self._context
        context.tick = 0
        await self._step({pid: [] for pid in self._initiators})
        for tick in range(1, self._max_ticks + 1):
            context.tick = tick
            inboxes = context.bus.deliver()
            if not inboxes:
                return 'stalled'
            await self._step(inboxes)
            if context.customer_done and context.final_plan is not None:
                return 'converged'
        return 'timeout'

    async def _step(
        self, inboxes: dict[str, list[simulation.Message]]
    ) -> None:
        ids = sorted(inboxes)
        results = await asyncio.gather(
            *(self._participants[pid].act(inboxes[pid]) for pid in ids),
            return_exceptions=True,
        )
        for pid, result in zip(ids, results):
            if isinstance(result, BaseException):
                # One participant crashing must not take the run down; it
                # is recorded and the others carry on.
                logger.error(
                    'Participant %s failed at tick %d: %r',
                    pid, self._context.tick, result,
                )
                self._context.record(
                    'participant_error', pid,
                    error=f'{type(result).__name__}: {result}',
                )
