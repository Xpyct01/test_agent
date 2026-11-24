"""Interface of the daily weather forecast."""

import abc
import datetime

from trip_planner.app.core.schemas import trip


class AbstractWeatherForecast(abc.ABC):
    """Daily forecast for the park, scored for hiking."""

    @abc.abstractmethod
    async def forecast(
        self, start_date: datetime.date
    ) -> list[trip.DailyForecast]:
        """Returns the scored forecast of the days from `start_date` on.

        Raises:
            errors.TransientActionError: The forecast source failed.
        """

    @abc.abstractmethod
    async def close(self) -> None:
        """Releases the resources of the forecast source."""
