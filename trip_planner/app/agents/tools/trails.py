"""Tools over the park's trails: search and live status."""

from trip_planner.app.agents.tools import base
from trip_planner.app.core.repositories.local_store import trail as trail_lib
from trip_planner.app.core.schemas import tools
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.trail_selection import core as trail_selection_lib

_MAX_TRAILS = 5


class TrailTools(base.BaseTools):
    """Trail tools the agents can call."""

    def __init__(
        self,
        trail_selection: trail_selection_lib.TrailSelection,
        trail_repository: trail_lib.TrailRepository,
        **base_kwargs,
    ):
        """Initializes the tools.

        Args:
            trail_selection: Ranks trails against a fitness profile.
            trail_repository: The trail catalogue.
            **base_kwargs: Arguments of `base.BaseTools`.
        """
        super().__init__(**base_kwargs)
        self._trail_selection = trail_selection
        self._trail_repository = trail_repository

    async def search_trails(
        self,
        max_distance_km: float,
        max_elevation_gain_m: int,
        max_difficulty: trip.Difficulty,
        interests: list[str],
    ) -> dict[str, object]:
        """Finds the trails within the customer's limits, best fit first.

        Args:
            max_distance_km: Longest distance, from assess_fitness.
            max_elevation_gain_m: Largest elevation gain, from assess_fitness.
            max_difficulty: Hardest difficulty, from assess_fitness.
            interests: What the customer wants to see, e.g. ["lakes",
                "gorge", "views", "villages", "wildlife"].

        Returns:
            Up to 5 ranked trails (rank 1 is the best fit) with their ids,
            distance, elevation, difficulty and rockfall risk.
        """
        options, excluded = self._trail_selection.select(
            max_distance_km, max_elevation_gain_m, max_difficulty, interests
        )
        return base.to_result(
            tools.TrailSearchResult(
                trails=[
                    _to_summary(rank, option)
                    for rank, option in enumerate(options[:_MAX_TRAILS], 1)
                ],
                excluded_count=excluded + max(0, len(options) - _MAX_TRAILS),
            )
        )

    async def get_trail_status(self, trail_ids: list[str]) -> dict[str, object]:
        """Checks with the park administration whether trails are open.

        Args:
            trail_ids: Ids of the trails to check.

        Returns:
            For each trail: status "open", "closed" (with the reason) or
            "unknown_trail_id", plus its name, difficulty and rockfall_risk.
            May fail transiently; then retry.
        """
        context = self._run_context_provider.current()

        async def lookup() -> tools.TrailStatusResult:
            statuses = []
            for trail_id in trail_ids:
                closure = context.trail_status.get_closure(trail_id)
                trail = self._trail_repository.get(trail_id)
                if trail is None:
                    statuses.append(
                        tools.TrailStatus(
                            trail_id=trail_id, status='unknown_trail_id'
                        )
                    )
                else:
                    statuses.append(
                        tools.TrailStatus(
                            trail_id=trail_id,
                            status='closed' if closure else 'open',
                            reason=closure.reason if closure else '',
                            name=trail.name,
                            difficulty=trail.difficulty,
                            rockfall_risk=trail.rockfall_risk,
                        )
                    )
            return tools.TrailStatusResult(trails=statuses)

        return base.to_result(
            await self._call_with_faults('get_trail_status', lookup)
        )


def _to_summary(rank: int, option: trip.TrailOption) -> tools.TrailSummary:
    trail = option.trail
    return tools.TrailSummary(
        rank=rank,
        trail_id=trail.trail_id,
        name=trail.name,
        distance_km=trail.distance_km,
        elevation_gain_m=trail.elevation_gain_m,
        duration_h=trail.duration_h,
        difficulty=trail.difficulty,
        highlights=trail.highlights,
        rockfall_risk=trail.rockfall_risk,
        fit_reasons=option.reasons,
    )
