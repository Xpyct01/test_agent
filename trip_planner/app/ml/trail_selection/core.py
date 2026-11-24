"""Filters the trail catalogue by a hiker's limits and ranks the rest."""

from collections.abc import Sequence

from trip_planner.app.core.repositories.local_store import trail as trail_lib
from trip_planner.app.core.schemas import trip

_INTEREST_SYNONYMS = {
    'lake': 'lakes',
    'canyon': 'gorge',
    'gorges': 'gorge',
    'mountain': 'mountains',
    'peaks': 'mountains',
    'village': 'villages',
    'view': 'views',
    'animals': 'wildlife',
    'rivers': 'river',
}
_INTEREST_WEIGHT = 10.0
# Prefer the longest trail that still fits: the "optimal length" rule.
_LENGTH_WEIGHT = 5.0


class TrailSelection:
    """Deterministic trail ranking; ties break on the trail id."""

    def __init__(self, trail_repository: trail_lib.TrailRepository):
        """Initializes the selector.

        Args:
            trail_repository: The trail catalogue.
        """
        self._trail_repository = trail_repository

    def select(
        self,
        max_distance_km: float,
        max_elevation_gain_m: int,
        max_difficulty: trip.Difficulty,
        interests: Sequence[str],
    ) -> tuple[list[trip.TrailOption], int]:
        """Returns the trails within the limits, best first.

        Args:
            max_distance_km: Longest acceptable distance.
            max_elevation_gain_m: Largest acceptable elevation gain.
            max_difficulty: Hardest acceptable difficulty.
            interests: What the hiker wants to see.

        Returns:
            The ranked fitting trails and how many trails were excluded.
        """
        wanted = {_normalize(i) for i in interests if i.strip()}
        options, excluded = [], 0
        for trail in self._trail_repository.list_all():
            if (
                trail.distance_km > max_distance_km
                or trail.elevation_gain_m > max_elevation_gain_m
                or trip.DIFFICULTY_ORDER[trail.difficulty]
                > trip.DIFFICULTY_ORDER[max_difficulty]
            ):
                excluded += 1
                continue
            matches = sorted(wanted & set(trail.highlights))
            score = _INTEREST_WEIGHT * len(matches) + _LENGTH_WEIGHT * (
                trail.distance_km / max_distance_km
            )
            reasons = [
                f'{trail.distance_km} km and +{trail.elevation_gain_m} m '
                'are within the limits.'
            ]
            if matches:
                reasons.append(f'Matches interests: {", ".join(matches)}.')
            options.append(
                trip.TrailOption(trail=trail, score=round(score, 2),
                                 reasons=reasons)
            )
        options.sort(key=lambda o: (-o.score, o.trail.trail_id))
        return options, excluded


def _normalize(interest: str) -> str:
    word = interest.strip().lower()
    return _INTEREST_SYNONYMS.get(word, word)
