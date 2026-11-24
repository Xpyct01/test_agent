"""Recorded forecast pattern, for offline runs and tests."""

import datetime
import json

from trip_planner.app.config import weather as weather_lib
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.weather_forecast import base


class FixtureWeatherForecast(base.BaseWeatherForecast):
    """Maps day `i` of the fixture file to `start_date + i`."""

    def __init__(self, weather_config: weather_lib.WeatherConfiguration):
        """Initializes the forecast.

        Args:
            weather_config: Weather settings; `fixture_path` is read.
        """
        super().__init__(weather_config)
        with weather_config.fixture_path.open(encoding='utf-8') as file:
            self._days = json.load(file)['days']

    async def _fetch(
        self, start_date: datetime.date
    ) -> list[trip.DailyForecast]:
        return [
            trip.DailyForecast(
                date=start_date + datetime.timedelta(days=offset), **day
            )
            for offset, day in enumerate(self._days[:self._forecast_days])
        ]
