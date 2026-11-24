"""Makes environment actions fail at random, reproducibly."""

from collections.abc import Mapping
import random

from trip_planner.app.core import errors


class FaultInjector:
    """Seeded random failures, one independent stream per action.

    Separate streams keep the failure pattern of one action independent
    of how concurrently running agents interleave their calls.
    """

    def __init__(self, seed: int, failure_rates: Mapping[str, float]):
        """Initializes the injector.

        Args:
            seed: Seed of the run.
            failure_rates: Failure probability of one attempt, by action.
        """
        self._seed = seed
        self._failure_rates = dict(failure_rates)
        self._streams: dict[str, random.Random] = {}

    def maybe_fail(self, action: str) -> None:
        """Raises for a simulated failure of one attempt of an action.

        Raises:
            errors.TransientActionError: The attempt failed.
        """
        rate = self._failure_rates.get(action, 0.0)
        if rate <= 0.0:
            return
        stream = self._streams.setdefault(
            action, random.Random(f'{self._seed}:{action}')
        )
        if stream.random() < rate:
            raise errors.TransientActionError(
                f'{action}: upstream service unavailable (simulated 503).'
            )
