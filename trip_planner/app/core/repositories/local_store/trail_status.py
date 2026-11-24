"""Trail closures of one simulation run."""

from collections.abc import Sequence

from trip_planner.app.core.schemas import trip


class TrailStatusRepository:
    """Closures announced by the park administration for a scenario."""

    def __init__(self, closures: Sequence[trip.TrailClosure]):
        """Initializes the repository.

        Args:
            closures: Trails closed during the scenario.
        """
        self._closures = {c.trail_id: c for c in closures}

    def get_closure(self, trail_id: str) -> trip.TrailClosure | None:
        """Returns the closure of a trail, or None when it is open."""
        return self._closures.get(trail_id)
