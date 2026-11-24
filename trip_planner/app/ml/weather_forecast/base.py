"""Shared scoring and caching of the weather forecast variants."""

import abc
import asyncio
import datetime

from trip_planner.app.config import weather as weather_lib
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.weather_forecast import abstract

_IDEAL_TEMPERATURE_C = 17.0
_WIND_COMFORT_KMH = 20.0


class BaseWeatherForecast(abstract.AbstractWeatherForecast):
    """Scores each day and caches the forecast per start date.

    The cache makes every run of a batch see the same forecast, so the
    choice of date cannot drift between runs of one batch.
    """

    def __init__(self, weather_config: weather_lib.WeatherConfiguration):
        """Initializes the forecast.

        Args:
            weather_config: Weather settings.
        """
        self._forecast_days = weather_config.forecast_days
        self._cache: dict[datetime.date, list[trip.DailyForecast]] = {}
        self._lock = asyncio.Lock()

    async def forecast(
        self, start_date: datetime.date
    ) -> list[trip.DailyForecast]:
        async with self._lock:
            if start_date not in self._cache:
                days = await self._fetch(start_date)
                self._cache[start_date] = [_score(day) for day in days]
            return list(self._cache[start_date])

    async def close(self) -> None:
        return None

    @abc.abstractmethod
    async def _fetch(
        self, start_date: datetime.date
    ) -> list[trip.DailyForecast]:
        """Returns the unscored forecast of `self._forecast_days` days."""


def _score(day: trip.DailyForecast) -> trip.DailyForecast:
    score = (
        100.0
        - 0.6 * day.precipitation_probability
        - 3.0 * day.precipitation_mm
        - 1.5 * max(0.0, day.wind_speed_max_kmh - _WIND_COMFORT_KMH)
        - 1.5 * abs(day.temperature_max_c - _IDEAL_TEMPERATURE_C)
    )
    clamped = min(100.0, max(0.0, score))
    return day.model_copy(update={'hiking_score': round(clamped, 1)})
