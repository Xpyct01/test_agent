"""Turns a hiker's age, fitness and health conditions into safe limits."""

from collections.abc import Sequence

from trip_planner.app.core.schemas import trip

# (max distance km, max elevation gain m, max difficulty) per fitness level.
_BASE_LIMITS: dict[str, tuple[float, int, trip.Difficulty]] = {
    'low': (8.0, 400, 'easy'),
    'moderate': (14.0, 700, 'moderate'),
    'high': (20.0, 1200, 'hard'),
}
_JOINT_KEYWORDS = ('knee', 'hip', 'ankle', 'joint', 'arthritis', 'back')
_CARDIO_KEYWORDS = (
    'heart', 'cardiac', 'asthma', 'hypertension', 'blood pressure', 'copd'
)
_SENIOR_AGE = 60
_JOINT_ELEVATION_FACTOR = 0.7
_SENIOR_FACTOR = 0.8
_CARDIO_ELEVATION_FACTOR = 0.6


class FitnessAssessment:
    """Rule-based limits, so the same profile always gets the same answer."""

    def assess(
        self,
        age: int,
        fitness_level: trip.FitnessLevel,
        conditions: Sequence[str],
    ) -> trip.FitnessProfile:
        """Returns the limits of one hiker.

        Args:
            age: Age in years.
            fitness_level: Self-reported fitness.
            conditions: Health conditions in free text.

        Returns:
            Distance, elevation and difficulty limits with the reasons.
        """
        max_distance, max_gain, max_difficulty = _BASE_LIMITS[fitness_level]
        notes = [f'Base limits for {fitness_level} fitness.']
        text = ' '.join(conditions).lower()
        has_joint_issues = any(k in text for k in _JOINT_KEYWORDS)
        has_cardio_issues = any(k in text for k in _CARDIO_KEYWORDS)

        if age >= _SENIOR_AGE:
            max_distance *= _SENIOR_FACTOR
            max_gain *= _SENIOR_FACTOR
            notes.append(f'Limits reduced by 20% for age {age}.')
        if has_joint_issues:
            max_gain *= _JOINT_ELEVATION_FACTOR
            notes.append(
                'Elevation gain reduced by 30% for a joint condition; '
                'trekking poles recommended for descents.'
            )
        if has_cardio_issues:
            max_gain *= _CARDIO_ELEVATION_FACTOR
            max_difficulty = 'easy'
            notes.append('Easy trails only for a cardio-respiratory condition.')

        return trip.FitnessProfile(
            max_distance_km=round(max_distance, 1),
            max_elevation_gain_m=round(max_gain),
            max_difficulty=max_difficulty,
            needs_trekking_poles=has_joint_issues,
            has_joint_issues=has_joint_issues,
            notes=notes,
        )
