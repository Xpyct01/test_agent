"""Tools that assess the customer's physical limits."""

from trip_planner.app.agents.tools import base
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.fitness_assessment import core as fitness_lib


class HealthTools(base.BaseTools):
    """Health tools the agents can call."""

    def __init__(
        self,
        fitness_assessment: fitness_lib.FitnessAssessment,
        **base_kwargs,
    ):
        """Initializes the tools.

        Args:
            fitness_assessment: Rule-based fitness limits.
            **base_kwargs: Arguments of `base.BaseTools`.
        """
        super().__init__(**base_kwargs)
        self._fitness_assessment = fitness_assessment

    async def assess_fitness(
        self,
        age: int,
        fitness_level: trip.FitnessLevel,
        conditions: list[str],
    ) -> dict[str, object]:
        """Computes the safe one-day hiking limits of the customer.

        Args:
            age: Customer age in years.
            fitness_level: Customer fitness: low, moderate or high.
            conditions: Health conditions in the customer's words, e.g.
                ["mild left-knee injury"]; empty list if none.

        Returns:
            Maximum distance, elevation gain and difficulty, whether trekking
            poles are needed, whether there are joint issues, and notes.
        """
        return base.to_result(
            self._fitness_assessment.assess(age, fitness_level, conditions)
        )
